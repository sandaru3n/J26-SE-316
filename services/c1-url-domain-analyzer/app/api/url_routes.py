"""API routes for URL feature extraction, domain intelligence, and threat infrastructure.

=============================================================================
COMPONENT 1: INTELLIGENT URL & DOMAIN ANALYZER (C1) - REST API ROUTING
=============================================================================
This module defines the HTTP REST API endpoints for Component C1.

Architecture Overview:
- Master Endpoint: `/analyze-url` (and `/api/v1/analyze-url`)
  Triggers the complete 4-layer analysis pipeline and synthesizes all signals into
  a single explainable risk score and operational verdict.
- Specialized Sub-Endpoints:
  `/api/v1/domain-intelligence`    -> Runs Layer 2 (WHOIS/RDAP, DNS, and reputation)
  `/api/v1/dga-analysis`           -> Runs Layer 3 (Domain Generation Algorithm detection)
  `/api/v1/redirect-analysis`      -> Runs Layer 3 (Safe HTTP redirect follower & shortener tracer)
  `/api/v1/threat-infrastructure`  -> Combines DGA and redirect analysis
  `/api/v1/extract-features`       -> Extracts raw 57-dimensional lexical vector
  `/api/v1/ml-predict`             -> Runs inference with the trained Random Forest classifier
  `/api/v1/explain-risk`           -> Returns explainable risk factors and dynamic weights
  `/api/v1/scoring-weights`        -> Returns nominal baseline weights and rationales
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

# Import specialized analyzer engines
from app.analyzers.dga_analyzer import DgaAnalyzer
from app.analyzers.domain_intelligence import DomainIntelligenceAnalyzer
from app.analyzers.lexical_analyzer import UrlLexicalAnalyzer
from app.analyzers.redirect_analyzer import ControlledRedirectResolver
from app.analyzers.threat_infrastructure import ThreatInfrastructureAnalyzer
from app.config import get_settings
from app.database import save_scan_result
from app.schemas.url_schema import (
    CompleteUrlDomainAnalysisResult,
    DgaAnalysisFeatures,
    DomainIntelligenceReport,
    ExplainableRiskAssessment,
    MlPredictionResult,
    RedirectChainFeatures,
    ThreatInfrastructureReport,
    UrlAnalysisRequest,
    UrlLexicalFeatures,
)
from app.ml.model_service import get_ml_service

# Create FastAPI router instance
router = APIRouter(tags=["URL, Domain & Threat Infrastructure Intelligence"])

# Instantiate singleton analyzer services for reuse across incoming requests
lexical_analyzer = UrlLexicalAnalyzer()
domain_intelligence_analyzer = DomainIntelligenceAnalyzer()
dga_analyzer = DgaAnalyzer()
redirect_resolver = ControlledRedirectResolver()
threat_infra_analyzer = ThreatInfrastructureAnalyzer()
ml_service = get_ml_service()


# =============================================================================
# MASTER ANALYSIS ENDPOINT (Full Multi-Layer Pipeline)
# =============================================================================
@router.post(
    "/analyze-url",
    response_model=CompleteUrlDomainAnalysisResult,
    summary="Full Multi-Layer Analysis (Gateway endpoint)",
)
@router.post(
    "/api/v1/analyze-url",
    response_model=CompleteUrlDomainAnalysisResult,
    summary="Full Multi-Layer Analysis (v1 API)",
)
async def analyze_url(payload: UrlAnalysisRequest) -> CompleteUrlDomainAnalysisResult:
    """Analyze a URL without executing or rendering destination webpages.

    How the analysis pipeline executes:
    1. Validation: Ensures the target URL string is non-empty and well-formed.
    2. Layer 1 (Lexical): Extracts 57 structural, entropy, homoglyph, and keyword features.
    3. Layer 2 (Domain Intel): Queries DNS records and RDAP/WHOIS for domain age (NRD detection).
    4. Layer 3 (Threat Infra): Inspects DGA likelihood and safely traces redirect chains (with SSRF protection).
    5. Layer 4 (ML & Fusion): Evaluates the Random Forest model, dynamically renormalizes weights,
       applies collinearity dampening, and produces the final risk score and verdict.
    """
    # Reject empty URL submissions
    if not payload.url or not payload.url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL field cannot be empty.",
        )

    # Execute full multi-layer scan asynchronously
    result = await domain_intelligence_analyzer.analyze_full(payload.url)

    # Optionally persist result if MongoDB is connected; fails silently if offline
    save_scan_result(result.model_dump())

    return result


# =============================================================================
# SPECIALIZED LAYER 2 ENDPOINT: Domain Intelligence
# =============================================================================
@router.post(
    "/api/v1/domain-intelligence",
    response_model=DomainIntelligenceReport,
    summary="Extract Domain Intelligence (RDAP/WHOIS, DNS, and Threat Reputation)",
)
async def analyze_domain_only(payload: UrlAnalysisRequest) -> DomainIntelligenceReport:
    """Analyze domain registration, DNS records, and infrastructure reputation only.
    
    This endpoint isolates Layer 2 of the pipeline:
    - Queries public RDAP/WHOIS to calculate domain age and flag Newly Registered Domains (NRDs).
    - Resolves DNS records (A, AAAA, MX, NS, TXT) and detects fast-flux botnet turnover.
    - Checks threat intelligence blocklists.
    """
    if not payload.url or not payload.url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL field cannot be empty.",
        )

    # Extract clean domain name from URL before querying network services
    features = lexical_analyzer.extract_features(payload.url)
    target_domain = features.registered_domain or features.hostname or payload.url.strip()

    return await domain_intelligence_analyzer.analyze_domain(target_domain)


# =============================================================================
# SPECIALIZED LAYER 3 ENDPOINT: Domain Generation Algorithm (DGA) Analysis
# =============================================================================
@router.post(
    "/api/v1/dga-analysis",
    response_model=DgaAnalysisFeatures,
    summary="Analyze Domain Generation Algorithm (DGA) statistical features",
)
async def analyze_dga_only(payload: UrlAnalysisRequest) -> DgaAnalysisFeatures:
    """Evaluate DGA entropy, vowel-consonant ratios, and algorithmic likelihood on domain label.
    
    This endpoint isolates the DGA statistical engine:
    - Measures Shannon entropy of the domain label (e.g. bits per character).
    - Evaluates vowel-to-consonant distribution and bigram perplexity.
    - Distinguishes human-readable dictionary words from algorithmically generated botnet labels.
    """
    if not payload.url or not payload.url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL field cannot be empty.",
        )

    features = lexical_analyzer.extract_features(payload.url)
    target_domain = features.registered_domain or features.hostname or payload.url.strip()

    return dga_analyzer.analyze(target_domain)


# =============================================================================
# SPECIALIZED LAYER 3 ENDPOINT: Controlled HTTP Redirect Resolution
# =============================================================================
@router.post(
    "/api/v1/redirect-analysis",
    response_model=RedirectChainFeatures,
    summary="Controlled HTTP redirect chain resolution and URL shortener analysis",
)
async def analyze_redirect_only(payload: UrlAnalysisRequest) -> RedirectChainFeatures:
    """Trace HTTP redirect hops with strict SSRF validation and hop limits.
    
    Security Controls:
    - Unshortens URLs (bit.ly, tinyurl.com, etc.) to uncover the hidden destination.
    - Enforces SSRF defense: aborts immediately if a hop attempts to route to private IP ranges (127.0.0.1, 10.0.0.0/8).
    - Prevents denial-of-service by capping the maximum redirects at 8 hops.
    """
    if not payload.url or not payload.url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL field cannot be empty.",
        )

    return await redirect_resolver.resolve(payload.url)


# =============================================================================
# CONSOLIDATED LAYER 3 ENDPOINT: Threat Infrastructure
# =============================================================================
@router.post(
    "/api/v1/threat-infrastructure",
    response_model=ThreatInfrastructureReport,
    summary="Consolidated Threat Infrastructure report (DGA + Redirect Chains)",
)
async def analyze_threat_infrastructure_only(payload: UrlAnalysisRequest) -> ThreatInfrastructureReport:
    """Evaluate DGA algorithmic generation and controlled redirect infrastructure in one call."""
    if not payload.url or not payload.url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL field cannot be empty.",
        )

    features = lexical_analyzer.extract_features(payload.url)
    target_domain = features.registered_domain or features.hostname or payload.url.strip()

    return await threat_infra_analyzer.analyze(payload.url, target_domain)


# =============================================================================
# FEATURE EXTRACTION ENDPOINT: Raw 57-Dimensional Feature Vector
# =============================================================================
@router.post(
    "/api/v1/extract-features",
    response_model=UrlLexicalFeatures,
    summary="Extract raw URL lexical features dictionary for ML pipelines",
)
async def extract_features(payload: UrlAnalysisRequest) -> UrlLexicalFeatures:
    """Extract raw structured features from URL for machine learning model pipelines.
    
    Performs purely static lexical analysis (no network lookups, no HTML execution).
    Used by training scripts, ML pipelines, and dataset generation pipelines.
    """
    if not payload.url or not payload.url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL field cannot be empty.",
        )

    return lexical_analyzer.extract_features(payload.url)


# =============================================================================
# MACHINE LEARNING INFERENCE ENDPOINT: Random Forest Classifier
# =============================================================================
@router.post(
    "/api/v1/ml-predict",
    response_model=MlPredictionResult,
    summary="Direct Machine Learning classifier prediction",
)
async def ml_predict(payload: UrlAnalysisRequest) -> MlPredictionResult:
    """Classify a URL using the loaded machine learning model without running full multi-layer scans.
    
    Transforms the URL into a feature vector and passes it through the trained
    Random Forest model to output a malicious probability (0.0 to 1.0) and predicted class.
    """
    if not payload.url or not payload.url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL field cannot be empty.",
        )

    return ml_service.predict(payload.url)


# =============================================================================
# MODEL STATUS & METADATA ENDPOINT
# =============================================================================
@router.get(
    "/api/v1/ml-model-status",
    summary="Get active ML model metadata and operational status",
)
async def ml_model_status():
    """Retrieve metadata, active algorithm, decision threshold, and performance metrics of the loaded model."""
    return {
        "is_model_loaded": ml_service.is_loaded,
        "model_dir": str(ml_service.model_dir),
        "metadata": ml_service.metadata,
    }


# =============================================================================
# EXPLAINABLE RISK ASSESSMENT ENDPOINT (Core Research Contribution 4)
# =============================================================================
@router.post(
    "/api/v1/explain-risk",
    response_model=ExplainableRiskAssessment,
    summary="Direct Explainable Multi-Channel Risk Assessment",
)
async def explain_risk_assessment(payload: UrlAnalysisRequest) -> ExplainableRiskAssessment:
    """Execute full multi-layer scan and return detailed explainable risk scoring breakdown.
    
    Returns the complete research audit trail:
    - Active renormalized weights across all 8 channels (Research Contribution 3).
    - Ranked contributing risk factors (with positive impact penalties or mitigating credits).
    - Epistemic evidence breakdown separating empirical facts, heuristics, and ML predictions (Contribution 4).
    - Transparent documentation of any external service limitations or timeouts.
    """
    if not payload.url or not payload.url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL field cannot be empty.",
        )

    full_res = await domain_intelligence_analyzer.analyze_full(payload.url)
    if full_res.risk_assessment is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Risk assessment engine failed to compute audit trail.",
        )
    return full_res.risk_assessment


# =============================================================================
# SCORING CONFIGURATION & TRANSPARENCY ENDPOINT
# =============================================================================
@router.get(
    "/api/v1/scoring-weights",
    summary="Retrieve configurable risk scoring weights, rationale, and thresholds",
)
async def get_scoring_weights():
    """Retrieve nominal scoring configuration weights, rationales, and classification thresholds.
    
    Used by the frontend dashboard to display the dynamic weights comparison chart
    (Nominal baseline vs Effective dynamically renormalized weights).
    """
    settings = get_settings()
    return {
        "engine_version": settings.risk_engine_version,
        "calibration_status": "Empirical prior baseline (Configurable; calibrated on benchmark validation datasets)",
        "nominal_weights": {
            "lexical_structural": {
                "weight": settings.weight_lexical_structural,
                "rationale": "Evaluates URL syntax, path depth, query complexity, and sensitive keyword presence with logarithmic saturation.",
            },
            "entropy_obfuscation": {
                "weight": settings.weight_entropy_obfuscation,
                "rationale": "Identifies percent-encoding evasion (%25XX), authority @ masking, hex/octal IPs, and elevated Shannon entropy.",
            },
            "homoglyph_lookalike": {
                "weight": settings.weight_homoglyph_lookalike,
                "rationale": "Detects confusable script lookalikes (Cyrillic/Latin) and Punycode spoofing targeting high-value brands.",
            },
            "domain_registration": {
                "weight": settings.weight_domain_registration,
                "rationale": "Evaluates domain age (NRD <= 30d penalty vs >2yr mitigating credit), registrar metadata, and DNSSEC validation.",
            },
            "dns_reputation": {
                "weight": settings.weight_dns_reputation,
                "rationale": "Flags fast-flux DNS turnover, private RFC-1918 resolution, dynamic DNS hosting, and threat feed matches.",
            },
            "dga": {
                "weight": settings.weight_dga,
                "rationale": "Measures domain label statistical randomness, consonant clustering, and bigram perplexity for botnet C2 detection.",
            },
            "shortener_redirect": {
                "weight": settings.weight_shortener_redirect,
                "rationale": "Traces cloaked URL shorteners, cross-domain redirection chains, cyclic loops, and SSRF violation attempts.",
            },
            "machine_learning": {
                "weight": settings.weight_machine_learning,
                "rationale": "Inputs 47-dimensional feature vectors into supervised classifier (Random Forest/XGBoost) for non-linear pattern recognition.",
            },
        },
        "thresholds": {
            "low_risk": {
                "max_score": settings.risk_threshold_low,
                "label": "Low Risk",
                "action": "Permit traffic; no critical indicators observed.",
            },
            "suspicious": {
                "min_score": settings.risk_threshold_low,
                "max_score": settings.risk_threshold_medium,
                "label": "Suspicious",
                "action": "Exercise caution; elevated lexical or young domain signals present.",
            },
            "medium_risk": {
                "min_score": settings.risk_threshold_medium,
                "max_score": settings.risk_threshold_high,
                "label": "Medium Risk",
                "action": "Elevated threat likelihood; multiple correlated suspicious factors.",
            },
            "high_risk": {
                "min_score": settings.risk_threshold_high,
                "max_score": 100.0,
                "label": "High Risk Scam",
                "action": "Block / warn user; confirmed malicious infrastructure, phishing synergy, or threat feed hit.",
            },
        },
    }

