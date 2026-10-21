"""Centralized configuration for the c1-url-domain-analyzer service.

=============================================================================
COMPONENT 1: INTELLIGENT URL & DOMAIN ANALYZER (C1) - CONFIGURATION MODULE
=============================================================================
This file defines all operational parameters, timeout limits, threat thresholds,
and empirical scoring weights for Component C1.

C1 is designed as a "static inspection engine" - it analyzes URLs and domains
WITHOUT executing dangerous JavaScript or downloading suspicious webpage bodies.
All parameters here govern how sensitive the detection rules are, how external
network queries (DNS/RDAP) behave, and how risk weights are distributed.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine the absolute directory path of this microservice root
SERVICE_ROOT: Path = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime configuration settings for C1 URL and Domain Analyzer.
    
    Settings can be overridden via environment variables or a local .env file.
    Default values are tuned for defensive cybersecurity research and low false-positive rates.
    """

    # Tell Pydantic to read configuration from .env in service root or working directory if present
    model_config = SettingsConfigDict(
        env_file=(SERVICE_ROOT / ".env", Path(".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # 1. Microservice Networking & Identification
    # -------------------------------------------------------------------------
    service_name: str = Field(
        default="c1-url-domain-analyzer",
        validation_alias=AliasChoices("service_name", "c1_service_name"),
    )
    log_level: str = "INFO"
    port: int = Field(default=8001, validation_alias=AliasChoices("port", "c1_port"))
    host: str = Field(default="0.0.0.0", validation_alias=AliasChoices("host", "c1_host"))
    frontend_url: str = Field(
        default="http://localhost:5173",
        validation_alias=AliasChoices("frontend_url", "cors_origins"),
    )

    # Path to trained machine learning model directory (portable default to SERVICE_ROOT / models)
    model_dir: str = Field(
        default=str(SERVICE_ROOT / "models"),
        validation_alias=AliasChoices("model_dir", "c1_model_dir"),
    )

    # Optional database persistence (MongoDB) - if MongoDB is offline, C1 runs in memory
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "url_domain_analyzer"

    # -------------------------------------------------------------------------
    # 2. Domain Intelligence & Registration Thresholds (Research Contribution 2)
    # -------------------------------------------------------------------------
    # Newly Registered Domains (NRDs) are a primary phishing indicator.
    # Attackers frequently register fresh domains, use them for hours, and discard them.
    nrd_threshold_days: int = 30          # Domains <= 30 days old receive an immediate high-risk penalty
    nrd_warning_threshold_days: int = 90  # Domains <= 90 days old receive an elevated warning flag
    dns_timeout_seconds: float = 3.0      # Maximum seconds to wait for a DNS resolver response
    rdap_timeout_seconds: float = 5.0     # Maximum seconds to wait for an RDAP (WHOIS) HTTP query
    rdap_base_url: str = "https://rdap.org/domain"  # Public bootstrap gateway for RDAP domain queries
    cache_ttl_seconds: int = 3600         # Cache network lookup results for 1 hour to prevent rate limiting

    # -------------------------------------------------------------------------
    # 3. Optional External Threat Intelligence API Keys
    # -------------------------------------------------------------------------
    # In production, keys can be set via environment variables. If left blank,
    # the analyzer relies gracefully on internal heuristics and ML models.
    virustotal_api_key: str = ""
    threatfox_api_key: str = ""

    # -------------------------------------------------------------------------
    # 4. DNS Infrastructure & Resolvers
    # -------------------------------------------------------------------------
    # High-reliability public DNS resolvers used to query A, AAAA, MX, NS, and TXT records
    custom_dns_servers: list[str] = ["8.8.8.8", "1.1.1.1", "9.9.9.9"]

    # Dynamic DNS providers (DDNS) frequently abused by malware operators for rapid IP switching
    dynamic_dns_domains: set[str] = {
        "duckdns.org", "no-ip.com", "ddns.net", "zapto.org", "hopto.org",
        "bounceme.net", "myftp.org", "servebeer.com", "freeddns.org",
        "ngrok.io", "loca.lt", "pagekite.me"
    }

    # -------------------------------------------------------------------------
    # 5. Threat-Infrastructure & Redirect Inspection Settings
    # -------------------------------------------------------------------------
    # When following redirects, we enforce strict limits to prevent infinite loops and SSRF attacks
    max_redirect_hops: int = 8             # Abort chain if more than 8 redirects occur (anti-evasion)
    redirect_timeout_seconds: float = 4.0  # Timeout per redirect request
    max_response_bytes: int = 16384        # Read at most 16KB of response headers (never render full body)
    allow_private_ips_for_test: bool = False  # Set to True ONLY in isolated unit tests

    # -------------------------------------------------------------------------
    # 6. DGA (Domain Generation Algorithm) Detection Thresholds (Research Contribution 2)
    # -------------------------------------------------------------------------
    # DGA algorithms generate random-looking domain names (e.g. "xrqmzbptw9.com") for botnet C2 servers.
    # Natural language English words have lower Shannon entropy and balanced vowel-consonant ratios.
    dga_entropy_threshold: float = 3.6    # Shannon entropy > 3.6 bits/char flags random character generation
    dga_vowel_ratio_min: float = 0.15     # Vowels < 15% indicates unnatural consonant clustering
    dga_vowel_ratio_max: float = 0.65     # Vowels > 65% indicates abnormal vowel stuffing

    # -------------------------------------------------------------------------
    # 7. Known URL Shortener Domains
    # -------------------------------------------------------------------------
    # URL shorteners conceal the true destination from the user. We trace shorteners to their final targets.
    known_shorteners: set[str] = {
        "bit.ly", "tinyurl.com", "rebrand.ly", "t.co", "goo.gl", "ow.ly",
        "is.gd", "buff.ly", "cutt.ly", "shorturl.at", "tiny.cc", "rb.gy",
        "bl.ink", "trib.al", "linktr.ee", "snip.ly", "clck.ru", "v.gd",
        "qr.net", "s.id", "t.ly", "rotf.lol", "short.io"
    }

    # -------------------------------------------------------------------------
    # 8. Suspicious Top-Level Domains (TLDs)
    # -------------------------------------------------------------------------
    # Certain TLDs have historically had very low registration costs or lax abuse policies,
    # making them popular for disposable phishing campaigns.
    suspicious_tlds: set[str] = {
        "zip", "mov", "top", "xyz", "work", "gq", "cf", "tk", "ml", "ga",
        "click", "link", "country", "kim", "science", "party", "review",
        "download", "racing", "date", "stream", "men", "win", "bid"
    }

    # -------------------------------------------------------------------------
    # 9. High-Risk Security & Credential Keywords
    # -------------------------------------------------------------------------
    # Phishing URLs frequently include banking, brand, or account-verification keywords
    # to trick users into believing they are visiting an authentic portal.
    suspicious_keywords: set[str] = {
        "login", "signin", "verify", "verification", "account", "update",
        "secure", "security", "banking", "bank", "confirm", "confirmation",
        "support", "service", "credential", "auth", "authorize", "token",
        "wallet", "password", "recovery", "checkout", "payment", "billing",
        "paypal", "appleid", "microsoft", "google", "meta", "netflix",
        "amazon", "facebook", "instagram", "chase", "wellsfargo"
    }

    # =========================================================================
    # CORE RESEARCH CONTRIBUTION 3: Explainable Risk Scoring Engine Weights
    # =========================================================================
    # RATIONALE & CALIBRATION NOTE:
    # These baseline nominal weights represent the relative importance of each
    # security channel in the multi-layer architecture.
    # Crucially, under Research Contribution 3 (Availability-Aware Dynamic Weight Renormalization),
    # if any external channel (like WHOIS or DNS) is unavailable, the remaining active
    # weights are dynamically renormalized so they always sum up to exactly 1.00 (100%).
    # This guarantees that missing data never artificially depresses the risk score!
    
    # 1. Lexical & Structural Analysis (Nominal Weight: 0.15 = 15%)
    # Rationale: Path depth, query complexity, special symbols, and digit ratios provide
    # baseline syntax indicators, but legitimate URLs can also be complex.
    weight_lexical_structural: float = 0.15

    # 2. Entropy & Obfuscation Analysis (Nominal Weight: 0.10 = 10%)
    # Rationale: Percent-encoding (%20), double-encoding (%2520), hex IP formats, and excessive path entropy
    # indicate active evasion or obfuscation techniques designed to bypass security filters.
    weight_entropy_obfuscation: float = 0.10

    # 3. Homoglyph & Lookalike Indicators (Nominal Weight: 0.10 = 10%)
    # Rationale: Confusable scripts (Cyrillic 'а' vs Latin 'a'), Punycode spoofing (xn--),
    # and brand imitation are targeted deception mechanisms with high scam specificity.
    weight_homoglyph_lookalike: float = 0.10

    # 4. Domain Registration Age & Registrar Metadata (Nominal Weight: 0.20 = 20%)
    # Rationale: Newly registered domains (<=30 days) and young domains (<=90 days)
    # account for an overwhelming majority of disposable phishing infrastructure.
    # Long-established domains (>2 years) receive mitigating credit.
    weight_domain_registration: float = 0.20

    # 5. DNS & Infrastructure Reputation (Nominal Weight: 0.15 = 15%)
    # Rationale: Fast-flux rotation (short TTL with shifting IPs), private RFC-1918 resolution,
    # dynamic DNS, and threat intelligence feed matches represent high-confidence infrastructure signals.
    weight_dns_reputation: float = 0.15

    # 6. DGA Classification (Nominal Weight: 0.05 = 5%)
    # Rationale: Algorithmic label randomness (perplexity, vowel-consonant clustering)
    # is specific to malware C2 / botnet rendezvous. Lower weight for general web phishing.
    weight_dga: float = 0.05

    # 7. Shortened URLs & Redirect-Chain Indicators (Nominal Weight: 0.10 = 10%)
    # Rationale: Cloaked shortener destinations, cross-domain redirect hops, loops,
    # and SSRF attempts conceal final destinations from user inspection.
    weight_shortener_redirect: float = 0.10

    # 8. Machine Learning Predictions (Nominal Weight: 0.15 = 15%)
    # Rationale: Supervised classification (Random Forest) captures complex
    # non-linear multi-feature interactions, complementing deterministic rules.
    weight_machine_learning: float = 0.15

    # -------------------------------------------------------------------------
    # 10. Configurable Risk Classification Thresholds (Scale: 0.0 to 100.0)
    # -------------------------------------------------------------------------
    # These cutoffs map the continuous numerical risk score into discrete risk tiers
    risk_threshold_low: float = 25.0       # Scores < 25.0 classified as "Low Risk" (Safe)
    risk_threshold_medium: float = 50.0    # Scores 25.0 - 49.9 classified as "Suspicious"
    risk_threshold_high: float = 75.0      # Scores 50.0 - 74.9: "Medium Risk", >= 75.0: "High Risk Scam"

    # Engine metadata identifier for telemetry and reproducibility
    risk_engine_version: str = "c1-explainable-risk-v1.0.0"


@lru_cache
def get_settings() -> Settings:
    """Return process-wide cached settings singleton.
    
    Using @lru_cache ensures settings are loaded once from disk/environment and reused efficiently.
    """
    return Settings()

