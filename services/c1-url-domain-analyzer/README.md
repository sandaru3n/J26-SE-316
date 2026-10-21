# Component C1 — Intelligent URL and Domain Analyzer
## Research Project: AI-Powered Browser Extension for Intelligent Web Threat Detection and User Protection

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Scikit-Learn](https://img.shields.io/badge/scikit--learn-1.3%2B-F7931E.svg)](https://scikit-learn.org/)
[![Test Suite](https://img.shields.io/badge/Tests-104%20Passed-brightgreen.svg)](#10-testing-and-evaluation)
[![Zero-Leakage ML](https://img.shields.io/badge/ML%20Leakage%20Prevention-Domain--Grouped-success.svg)](#5-machine-learning-model)

---

## Table of Contents
1. [Component Overview](#1-component-overview)
2. [Research Methodology](#2-research-methodology)
3. [System Architecture and Workflow](#3-system-architecture-and-workflow)
4. [Technologies Used](#4-technologies-used)
5. [Machine Learning Model](#5-machine-learning-model)
6. [Risk Assessment and Final Verdict](#6-risk-assessment-and-final-verdict)
7. [Installation and Setup](#7-installation-and-setup)
8. [Environment Configuration](#8-environment-configuration)
9. [API Documentation](#9-api-documentation)
10. [Testing and Evaluation](#10-testing-and-evaluation)
11. [Project Structure](#11-project-structure)
12. [Limitations and Future Improvements](#12-limitations-and-future-improvements)
13. [Troubleshooting](#13-troubleshooting)
14. [Research Contribution](#14-research-contribution)

---

## 1. Component Overview

### 1.1 What is Component C1?
**Component C1 (Intelligent URL and Domain Analyzer)** is a research-grade, pre-execution cybersecurity intelligence engine. It serves as the primary defensive perimeter for the broader **AI-Powered Browser Extension for Intelligent Web Threat Detection and User Protection**. 

Unlike conventional browser defenses that wait for a webpage to download and execute JavaScript inside the Document Object Model (DOM), C1 performs **static and multi-layer structural inspection** of target navigation requests. It examines URLs, domain registrations, Domain Name System (DNS) configurations, and network infrastructure *before* any connection to the destination server's application layer is permitted.

### 1.2 Why is this Component Necessary?
Modern web threats—ranging from credential harvesting and brand impersonation to automated malware distribution and Command-and-Control (C2) rendezvous—have evolved beyond the detection capabilities of static signature lists and basic URL blocklists:
- **Ephemeral Infrastructure**: Phishing kits and drive-by malware campaigns now register disposable domain names that remain active for only hours or minutes, rendering static blocklists obsolete before updates can propagate.
- **Drive-by Exploitation**: Allowing the browser to fetch and render HTML/JavaScript to analyze malicious intent exposes users to zero-day browser vulnerabilities, malicious browser extension takeovers, and cross-site scripting (XSS).
- **Evasion Tactics**: Cybercriminals intentionally obfuscate URLs using Unicode homoglyphs, multiple percent-encoding layers, authority masking (`@`), and domain generation algorithms (DGAs).

### 1.3 The Problem it Addresses
1. **High Latency and Client-Side Risk**: Sandboxed browser detonation is computationally expensive and introduces seconds of latency, while direct rendering exposes the client to exploit payloads.
2. **False Positives on Legitimate Web Traffic**: Naive keyword matching falsely flags modern legitimate URLs that contain tracking parameters (`utm_source`, `gclid`), cryptographic tokens, or developer documentation paths (e.g., `github.com/.../security`).
3. **Information Asymmetry and External Service Failures**: When third-party intelligence services (such as WHOIS/RDAP or public DNS) rate-limit queries or block data via privacy guards, traditional risk engines assign a zero score to missing channels, producing catastrophic false negatives (treating unavailable data as "safe").

### 1.4 Main Objectives of Component C1
- **Sub-Millisecond Pre-Execution Static Inspection**: Extract a 57-dimensional lexical, structural, and obfuscation feature vector without executing remote page content.
- **Resilient Domain & Infrastructure Intelligence**: Query RDAP/WHOIS and DNS records asynchronously to identify Newly Registered Domains (NRDs $\le$ 30 days) and fast-flux botnet hosting.
- **Zero-Leakage Machine Learning Classification**: Train and serve an optimized Random Forest classifier with `GroupShuffleSplit` domain isolation, achieving 98.48% accuracy on unseen apex domains.
- **Availability-Aware Dynamic Weight Renormalization**: Dynamically re-allocate mathematical weights across available signals when external services time out, guaranteeing the risk score is never artificially deflated.
- **Explainable Cybersecurity Risk Scoring (XAI)**: Synthesize multi-layer findings into an auditable evidence breakdown with explicit epistemological tiering (Observed Facts vs. Heuristic Indicators vs. Model Predictions).

### 1.5 Role within the Broader Research Project
Within the ScamTrace AI-Powered Browser Extension architecture, Component C1 is the **first line of defense** (Gate 1). When a user clicks a hyperlink, enters an address, or is redirected:
1. **Gate 1 (C1 - URL & Domain Analyzer)** inspects the target address in real time ($\approx 1.2\,\mu\text{s}$ model latency; $<150\,\text{ms}$ network timeout bounds).
2. If C1 yields a **High Risk** verdict (`MALICIOUS` or `PHISHING`), the browser extension immediately aborts navigation and displays an interactive warning modal.
3. If C1 yields a **Suspicious** or **Low Risk** verdict, navigation proceeds while forwarding C1's extracted feature telemetry to downstream components:
   - **Component C2 (Webpage Content & DOM Analyzer)**: Inspects rendered forms, DOM text, and visual logos.
   - **Component C3 (Transaction & Financial Protection Guard)**: Monitors checkout interactions and payment gateways.
   - **Component C4 (AI Explanation & Audit System)**: Synthesizes explainable reports for users and security operations center (SOC) analysts.

---

## 2. Research Methodology

Component C1 executes a 4-layer inspection pipeline designed to prevent evasive threats from bypassing single-point defenses:

```
+--------------------------------------------------------------------------------------------------+
|                                    INPUT: TARGET URL STRING                                      |
+--------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+--------------------------------------------------------------------------------------------------+
| LAYER 1: Lexical, Structural & Obfuscation Analysis (Pure Static - 0 ms network overhead)         |
| - RFC 3986 Syntax Breakdown (Protocol, Subdomain, Apex Domain, TLD, Path, Query, Fragment)       |
| - 57-Dimensional Quantitative Feature Vector                                                     |
| - Shannon Entropy Calculation: URL, Hostname, Path, and Query Strings                           |
| - Tracking Token Disambiguation (utm_*, gclid, srsltid isolated to prevent False Positives)     |
| - Evasion Analysis: Double Encoding (%25XX), Hex IPs (0x7F000001), @ Masking, Confusables/IDN   |
+--------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+--------------------------------------------------------------------------------------------------+
| LAYER 2: Domain Intelligence & Registration Analytics (Asynchronous Network Queries)             |
| - Public RDAP / WHOIS Querying with Local In-Memory TTL Caching (1 Hour)                         |
| - Newly Registered Domain (NRD) Heuristics: <= 30 Days (Critical), <= 90 Days (Warning)          |
| - Established Domain Mitigation Guardrail: > 5 Years (> 1825 Days) false-positive suppression    |
| - DNS Record Enumeration: A, AAAA, MX, NS, TXT via Resilient Resolvers (8.8.8.8, 1.1.1.1, 9.9.9.9) |
| - Fast-Flux Botnet Turnover & Dynamic DNS (DDNS) Provider Matching                              |
+--------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+--------------------------------------------------------------------------------------------------+
| LAYER 3: Threat Infrastructure & Autonomous Adversary Profiling                                 |
| - Statistical DGA Engine: Shannon entropy (>3.6 bits/char), vowel-consonant ratios, bigram       |
|   perplexity over domain labels (e.g., botnet C2 rendezvous detection)                           |
| - Safe HTTP Redirect Tracer: Follows shortened links (bit.ly, t.co) up to 8 hops                 |
| - Strict SSRF Defense: Prohibits redirection to private RFC 1918 / loopback IP spaces            |
+--------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+--------------------------------------------------------------------------------------------------+
| LAYER 4: Machine Learning Inference (Random Forest Classifier)                                   |
| - Standardized Input Scaling via Pre-Fitted Training Median Imputer & Standard Scaler            |
| - Calibrated Threshold Inference (optimal decision cutoff = 0.4400)                              |
| - Outputs: Calibrated Malicious Probability (0.0 to 1.0) and Predicted Class                     |
+--------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+--------------------------------------------------------------------------------------------------+
| SYNTHESIS: Availability-Aware Explainable Risk Engine                                            |
| - Dynamic Weight Renormalization: Recalculates effective channel weights to sum to 1.00 (100%)  |
| - Collinearity Dampening: Scales manual lexical weight by 40% (x 0.60) when ML model is active   |
| - Contextual Synergy Boosts: NRD + Sensitive Keywords (+25 pts); SSRF Blocked (Min Floor 90.0) |
| - Epistemic Separation: Partitions output into Observed Facts, Heuristics, and Model Predictions |
| - Operational Verdict Matrix: Evaluates >80%, =80%, <80% rules for SAFE/SUSPICIOUS/PHISHING/MALICIOUS|
+--------------------------------------------------------------------------------------------------+
```

### 2.1 URL Lexical and Structural Feature Extraction
The lexical engine parses URLs strictly according to RFC 3986 without network transmission:
- **Structural Properties**: URL length, hostname length, path length, query length, subdomain depth, and path depth.
- **Character Metrics**: Total counts and frequencies of hyphens, dots, digits, special characters, and consecutive digit sequences.
- **Tracking Parameter Isolation**: Commercial tracking parameters (such as `utm_source`, `utm_medium`, `utm_campaign`, `gclid`, `fbclid`, and `srsltid`) introduce high random character counts and artificial entropy. The lexical engine isolates tracking parameters to prevent legitimate marketing links from triggering false positives.
- **Obfuscation Detection**: Identifies hexadecimal IPv4 addresses (`0x7F.0x00.0x00.0x01`), integer-encoded IPs (`http://2130706433`), authority credentials (`https://legit.com@phishing.net`), and multiple percent-encodings (`%252e%252e%252f`).

### 2.2 Shannon Entropy Analysis
Shannon entropy quantifies the information density and randomness of character sequences:

$$H(X) = -\sum_{i=1}^{n} P(x_i) \log_2 P(x_i)$$

Where $P(x_i)$ is the probability of character $x_i$ occurring in the string.
- The engine calculates entropy separately across four URL segments: **Full URL Entropy**, **Hostname Entropy**, **Path Entropy**, and **Query Entropy**.
- High hostname entropy ($H > 3.6$) signals algorithmically generated hostnames or randomized subdomain hashing.
- Path entropy is evaluated in combination with length to distinguish benign cryptographic tokens (e.g., git commit hashes, media IDs) from obfuscated executable payloads.

### 2.3 Domain Intelligence & NRD Heuristics
- **Registration Age Calculation**: Real-time RDAP queries compute the precise elapsed time in days since initial registry creation:

$$\text{Domain Age (Days)} = \frac{t_{\text{current}} - t_{\text{creation}}}{86400}$$

- **Newly Registered Domains (NRD)**: Domains with $\text{Age} \le 30\text{ days}$ receive high-risk penalties, while domains with $\text{Age} \le 90\text{ days}$ receive warning flags.
- **Enterprise Guardrail**: Long-established domains ($\text{Age} \ge 1825\text{ days}$ / 5 years) receive mitigating score caps ($\le 35.0$) unless hard evidence of compromise (such as homoglyphs or verified threat list hits) is confirmed.
- **DNS Telemetry**: Checks for active MX records, resolves multi-homed A/AAAA records, and flags ultra-low Time-To-Live (TTL $< 300\text{s}$) settings indicative of fast-flux botnet networks.

### 2.4 Statistical DGA (Domain Generation Algorithm) Detection
Adversaries use DGAs in botnets and command-and-control communication to dynamically compute rendezvous points. C1 applies three independent statistical checks on the apex domain label:
1. **Shannon Entropy**: Identifies random character noise.
2. **Vowel-to-Consonant Ratio**: English words follow predictable vowel distributions ($15\% \le \text{Vowel Ratio} \le 65\%$). Clustered consonants indicate algorithmic randomness.
3. **English Bigram Perplexity**: Evaluates letter-pair transition frequencies against standard natural language bigram matrices. High perplexity flags non-linguistic character sequences.

---

## 3. System Architecture and Workflow

Component C1 is organized as an asynchronous microservice with clear boundary separation between the frontend presentation layer, API controllers, specialized analyzer engines, machine learning pipelines, and data stores.

```
+----------------------------------------------------------------------------------------------------+
|                                    CLIENT APPLICATION LAYER                                        |
|  ScamTrace Security Operations Center (SOC) Dashboard (React 19 + Vite + TailwindCSS + c1.css)     |
|  - Real-Time URL Analysis View                - 4-Layer Security Intelligence Pipeline Tabs         |
|  - Active Dynamic Weights Gauge (Donut & Bar) - Epistemic Evidence Audit Trail (Facts/Heuristics/ML)|
+----------------------------------------------------------------------------------------------------+
                                                  |
                                      HTTP REST / JSON (Port 8001)
                                                  |
                                                  v
+----------------------------------------------------------------------------------------------------+
|                               FASTAPI ASGI BACKEND CONTROLLER LAYER                                |
|  - /health & /api/v1/health                  - /analyze-url & /api/v1/analyze-url                  |
|  - /api/v1/domain-intelligence               - /api/v1/threat-infrastructure                       |
|  - /api/v1/ml-predict & /api/v1/ml-model-status - /api/v1/explain-risk & /api/v1/scoring-weights   |
+----------------------------------------------------------------------------------------------------+
                                                  |
        +-----------------------------------------+-----------------------------------------+
        |                                         |                                         |
        v                                         v                                         v
+-------------------------------+ +-------------------------------+ +-------------------------------+
|     LAYER 1: LEXICAL ENGINE   | |  LAYER 2: DOMAIN INTEL ENGINE | | LAYER 3: THREAT INFRA ENGINE  |
| UrlLexicalAnalyzer            | | DomainIntelligenceAnalyzer    | | ThreatInfrastructureAnalyzer  |
| - RFC 3986 URL Parser         | | - RegistrationAnalyzer (RDAP) | | - DgaAnalyzer (Perplexity)    |
| - 57-Feature Extractor        | | - DnsAnalyzer (A/MX/TTL)      | | - ControlledRedirectResolver  |
| - Obfuscation & Homoglyphs    | | - ReputationAnalyzer (Feeds)  | | - SSRF Private IP Filter      |
+-------------------------------+ +-------------------------------+ +-------------------------------+
        |                                         |                                         |
        +-----------------------------------------+-----------------------------------------+
                                                  |
                                                  v
+----------------------------------------------------------------------------------------------------+
|                               LAYER 4: MACHINE LEARNING SERVICE                                    |
|  MlModelService (Singleton Engine)                                                                 |
|  - Joblib Deserializer (models/best_model.joblib, models/preprocessor.joblib)                       |
|  - Scikit-learn Random Forest Classifier (100 Trees, Balanced Class Weights)                       |
|  - Calibrated Optimal Threshold Inference (Cutoff = 0.4400)                                       |
+----------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+----------------------------------------------------------------------------------------------------+
|                       SYNTHESIS: EXPLAINABLE RISK-SCORING ENGINE                                   |
|  ExplainableRiskScoringEngine                                                                      |
|  - Availability-Aware Dynamic Weight Renormalization                                               |
|  - Collinearity Dampening (40% Lexical Reduction when ML Active)                                   |
|  - Compound Threat Synergy Boosts & Long-Standing Domain False-Positive Caps                       |
|  - Epistemic Evidence Categorization (Observed Facts | Heuristics | Model Predictions)             |
|  - Final Verdict Determination (SAFE, SUSPICIOUS, PHISHING, MALICIOUS)                             |
+----------------------------------------------------------------------------------------------------+
        |                                                                           |
        v (Optional Scan Persistence)                                               v (Real-Time JSON)
+-------------------------------+                                           +-----------------------+
| LOCAL MONGODB DATABASE        |                                           | CLIENT SOC RESPONSE   |
| (Fails gracefully to memory   |                                           | Complete Multi-Layer  |
| if database is unreachable)   |                                           | Intelligence Schema   |
+-------------------------------+                                           +-----------------------+
```

---

## 4. Technologies Used

Component C1 relies exclusively on tested, modern, open-source libraries:

### 4.1 Backend & Machine Learning Stack
| Technology | Version | Purpose in Component C1 |
| :--- | :--- | :--- |
| **Python** | `3.10+` | Core programming language for microservice logic, statistical analysis, and ML inference. |
| **FastAPI** | `>= 0.100.0` | Asynchronous ASGI web framework providing OpenAPI specifications, high throughput, and Pydantic validation. |
| **Uvicorn** | `>= 0.20.0` | Production ASGI web server powering the backend HTTP service. |
| **Pydantic** | `>= 2.0.0` | Data validation, runtime type enforcement, and schema serialization. |
| **Pydantic-Settings** | `>= 2.0.0` | Centralized environment variable loading and validation. |
| **Scikit-Learn** | `>= 1.3.0` | Random Forest model architecture, tree fitting, median imputing, standard scaling, and ROC evaluation. |
| **Joblib** | `>= 1.3.0` | Serialization and fast deserialization of fitted model artifacts and preprocessing pipelines. |
| **NumPy** | `>= 1.26.0` | High-performance vector operations and contiguous 2D float32 memory allocation for feature extraction. |
| **Pandas** | `>= 2.0.0` | Tabular data manipulation, chunked streaming dataset cleaning, and domain grouping. |
| **tldextract** | `>= 5.0.0` | Accurate apex domain, subdomain, and public suffix parsing using the Mozilla Public Suffix List. |
| **dnspython** | `>= 2.4.0` | Asynchronous and synchronous DNS queries for A, AAAA, MX, NS, and TXT records. |
| **python-whois** | `>= 0.8.0` | Low-level WHOIS query protocol fallback for non-RDAP registrars (macOS/Linux). |
| **httpx** | `>= 0.25.0` | Asynchronous HTTP client for RDAP domain lookups and safe redirect following with hop limits. |
| **PyMongo** | `>= 4.5.0` | MongoDB driver for optional scan result persistence; gracefully falls back to memory mode if offline. |
| **Pytest & Pytest-Asyncio** | `>= 7.4.0` | Comprehensive testing framework running C1's 104 automated test cases. |

### 4.2 Frontend Presentation Stack
| Technology | Version | Purpose in Component C1 |
| :--- | :--- | :--- |
| **React** | `^19.2.8` | Declarative UI library for rendering the real-time C1 security operations center dashboard. |
| **Vite** | `^8.3.0` | Fast next-generation frontend build tool and local development server. |
| **React Router DOM**| `^7.18.4` | Client-side routing between C1 and broader ScamTrace dashboard views. |
| **Axios** | `^1.20.0` | Promise-based HTTP client for dispatching analysis requests to the FastAPI backend. |
| **Lucide React** | `^1.47.0` | Research-grade cybersecurity icons for threat indicators, epistemic tiers, and audit flags. |
| **TailwindCSS** | `^3.4.19` | Utility-first CSS framework coupled with custom `c1.css` design tokens for Light/Dark SOC styling. |

---

## 5. Machine Learning Model

Component C1 incorporates a trained **Random Forest Classifier** (`RandomForestClassifier`) engineered specifically for tabular URL security classification with resistance to academic data leakage.

### 5.1 Dataset Architecture and Zero-Leakage Splitting
- **Total Dataset Size**: **200,000 real-world URLs** assembled from open cybersecurity research repositories (abuse.ch URLhaus, PhishTank, and Tranco Top 1M).
- **Exact Class Balance**: Exactly 50% Benign (100,000 URLs) and 50% Malicious (100,000 URLs).
- **Domain-Level Isolation (`GroupShuffleSplit`)**: URLs belonging to the same registered apex domain (`registered_domain`) are strictly grouped into the same partition. **There is zero domain overlap between train, validation, and test sets**, preventing the model from memorizing benign or malicious domains:
  - **Training Partition**: 145,899 samples (72.95%)
  - **Validation Partition**: 21,071 samples (10.54%)
  - **Held-Out Test Partition**: 33,030 samples (16.51%)
- **Preprocessing Hygiene**: Imputation medians and standard scaling parameters were calculated strictly from the training partition and transformed onto validation and test partitions without data snooping.

### 5.2 Canonical 57-Dimensional Feature Vector
The ML feature extractor (`app/ml/feature_extractor.py`) computes 57 standardized numeric features across 11 functional categories:

| Feature Category | Dim | Exact Feature Names |
| :--- | :---: | :--- |
| **Length Metrics** | 7 | `url_length`, `hostname_length`, `path_length`, `query_length`, `tld_length`, `subdomain_length`, `domain_depth` |
| **Structural & Counts** | 11 | `num_dots`, `num_dots_hostname`, `num_hyphens`, `num_hyphens_hostname`, `num_digits`, `num_digits_hostname`, `num_letters`, `num_special_chars`, `num_subdomains`, `path_depth`, `num_query_params` |
| **Protocol** | 1 | `is_https` |
| **Keyword & High-Risk TLD** | 3 | `suspicious_keyword_count`, `has_suspicious_keyword`, `is_suspicious_tld` |
| **IP Address Indicators** | 2 | `is_ip_address`, `is_private_ip` |
| **Repetition Patterns** | 4 | `max_consecutive_digits`, `digit_ratio`, `max_character_repetition`, `has_excessive_repetition` |
| **Shannon Entropy** | 4 | `url_entropy`, `hostname_entropy`, `path_entropy`, `query_entropy` |
| **Obfuscation & Evasion** | 9 | `is_punycode`, `is_idn`, `has_homoglyphs`, `is_encoded`, `is_double_encoded`, `encoded_char_count`, `has_at_symbol`, `has_hex_obfuscation`, `has_misleading_delimiter` |
| **DGA Statistics** | 7 | `dga_label_length`, `dga_label_entropy`, `dga_vowel_ratio`, `dga_consonant_ratio`, `dga_digit_ratio`, `dga_max_consecutive_consonants`, `dga_bigram_perplexity` |
| **Domain-Level Signals** | 4 | `domain_age_days`, `is_nrd`, `has_dns_records`, `has_domain_data` |
| **FP/FN Reduction Signals** | 5 | `is_shortened_url`, `base_url_entropy`, `has_tracking_param`, `path_to_url_ratio`, `is_standard_port` |

### 5.3 Actual Experimental Performance Metrics
The following metrics represent the actual performance evaluated on the **33,030 unseen domain test partition** (`models/model_comparison_report.md`):

| Evaluation Metric | Baseline Model (Default RF) | Improved Model (Tuned RF + 57 Features) | Experimental Delta |
| :--- | :---: | :---: | :---: |
| **Test Accuracy** | `98.05%` (0.9805) | **`98.48%` (0.9848)** | **+ 0.43%** |
| **Precision** | `97.69%` (0.9769) | **`98.90%` (0.9890)** | **+ 1.21%** |
| **Recall (Sensitivity)** | `97.37%` (0.9737) | **`97.24%` (0.9724)** | - 0.13% |
| **F1-Score** | `0.9753` | **`0.9807`** | **+ 0.0054** |
| **ROC-AUC** | `0.9972` | **`0.9983`** | **+ 0.0011** |
| **False Positive Rate (FPR)** | `1.51%` (0.0151) | **`0.71%` (0.0071)** | **- 0.80% (53% Relative Drop)** |
| **False Negative Rate (FNR)** | `2.63%` (0.0263) | **`2.76%` (0.0276)** | + 0.13% |
| **Calibrated Decision Cutoff** | `0.3400` | **`0.4400`** | Optimized on Validation Set |
| **Inference Latency** | `0.001 ms` / sample | **`0.0012 ms` / sample** | Sub-millisecond evaluation |

### 5.4 Test Set Confusion Matrices (33,030 Unseen Domains)
```
Baseline Random Forest (33,030 samples):
               Predicted Benign    Predicted Malicious
Actual Benign       19,644 (TN)             301 (FP)
Actual Malicious       344 (FN)          12,741 (TP)

Improved & Tuned Random Forest (33,030 samples):
               Predicted Benign    Predicted Malicious
Actual Benign       19,804 (TN)             141 (FP)  <-- 160 False Positives Eliminated!
Actual Malicious       361 (FN)          12,724 (TP)
```

---

## 6. Risk Assessment and Final Verdict

Component C1 synthesizes its multi-layer signals into an explainable, continuous risk score from `0.0` to `100.0`.

### 6.1 Baseline Nominal Weights
When all 8 intelligence channels are operational, the scoring engine allocates nominal prior weights that sum to exactly $1.00$ ($100\%$):

| Channel Name | Nominal Weight | Operational Rationale |
| :--- | :---: | :--- |
| **1. Lexical & Structural** | `0.15` (15%) | Evaluates URL path depth, parameter complexity, and suspicious keywords with logarithmic saturation. |
| **2. Entropy & Obfuscation** | `0.10` (10%) | Detects percent-encoding evasion (`%25`), authority `@` masking, hex IPs, and elevated Shannon entropy. |
| **3. Homoglyph & Lookalike** | `0.10` (10%) | Identifies confusable script spoofs (Cyrillic/Latin lookalikes) and Punycode (`xn--`) brand targeting. |
| **4. Domain Registration** | `0.20` (20%) | Evaluates domain creation age (NRD $\le$ 30d penalty vs. established $>2\text{yr}$ mitigating credit). |
| **5. DNS & Infrastructure** | `0.15` (15%) | Flags fast-flux turnover, private RFC-1918 resolution, dynamic DNS, and threat feed matches. |
| **6. DGA Classification** | `0.05` (5%) | Identifies algorithmic label randomness, consonant clustering, and bigram perplexity for botnet C2s. |
| **7. Shorteners & Redirects** | `0.10` (10%) | Traces cloaked shortener destinations, cross-domain redirect chains, loops, and SSRF violations. |
| **8. Machine Learning** | `0.15` (15%) | Non-linear 57-feature pattern recognition via the trained Random Forest classifier. |
| **Total Nominal Sum** | **`1.00` (100%)** | Fully calibrated multi-channel baseline. |

### 6.2 Availability-Aware Dynamic Weight Renormalization
External network dependencies (e.g., WHOIS servers or public DNS resolvers) frequently fail due to rate limiting, network timeouts, or domain privacy protections. 

**The Renormalization Principle**: Treating missing telemetry as `0.0` falsely suppresses the risk score, creating a false negative. Component C1 dynamically calculates **effective weights** across only the actively responding channels:

$$W_{\text{effective}, i} = \frac{W_i \cdot \mathbb{I}(\text{active}_i) \cdot \delta_{\text{collinear}}(i)}{\sum_{j=1}^{8} W_j \cdot \mathbb{I}(\text{active}_j) \cdot \delta_{\text{collinear}}(j)}$$

Where:
- $\mathbb{I}(\text{active}_i) \in \{0, 1\}$ indicates whether channel $i$ returned valid telemetry.
- $\delta_{\text{collinear}}(\text{lexical\_structural}) = 0.60$ if Machine Learning is active (dampening manual lexical weight by 40% to prevent double-counting features evaluated by the Random Forest). For all other channels, $\delta_{\text{collinear}} = 1.00$.
- Guaranteed Invariant: $\sum_{i=1}^{8} W_{\text{effective}, i} \equiv 1.00$ ($100\%$) under all network conditions.

### 6.3 Risk Classification Tiers
The continuous composite score ($0.0$ to $100.0$) maps into four risk tiers:
- **Low Risk / Safe** (`0.0 - 24.9`): Safe for navigation; no critical indicators observed.
- **Suspicious** (`25.0 - 49.9`): Exercise caution; low-confidence heuristic anomalies or young domain signals present.
- **Medium Risk** (`50.0 - 74.9`): Elevated threat likelihood; multiple correlated suspicious factors detected.
- **High Risk Scam** (`75.0 - 100.0`): Active threat; confirmed malicious infrastructure, phishing synergy, or blocklist hit.

### 6.4 Operational Verdict Matrix
To prevent ambiguous classifications from compromising user security, the engine evaluates the final verdict via three explicit rules:

```
                      +-----------------------------+
                      |   Effective Score Check     |
                      +-----------------------------+
                                     |
         +---------------------------+---------------------------+
         | (Score > 80.0)            | (Score == 80.0)           | (Score < 80.0)
         v                           v                           v
+------------------+        +------------------+        +------------------+
|   NEVER SAFE     |        | Standard Logic   |        | Standard Cutoffs |
| - MALICIOUS if   |        | - MALICIOUS if   |        | - MALICIOUS if   |
|   malware evidence|       |   malware hit    |        |   malware & >=25 |
| - PHISHING if    |        | - PHISHING if    |        | - PHISHING if    |
|   credential hit |        |   phishing hit   |        |   phishing & >=25|
| - SUSPICIOUS if  |        | - SUSPICIOUS if  |        | - SUSPICIOUS if  |
|   uncertain      |        |   neither        |        |   score >= 25.0  |
+------------------+        +------------------+        | - SAFE otherwise |
                                                        +------------------+
```

---

## 7. Installation and Setup

Follow these instructions to configure and run Component C1 on a new developer workstation.

### 7.1 Prerequisites
- **Operating System**: macOS (Apple Silicon or Intel), Linux (Ubuntu 20.04+), or Windows 10/11 (PowerShell or WSL2).
- **Python**: Version `3.10` or higher (`python3 --version`).
- **Node.js**: Version `18.0` or higher (`node --version`) and `npm` (`npm --version`).
- **Git**: Installed and configured.

---

### 7.2 Backend Setup (FastAPI Microservice)

#### macOS & Linux
```bash
# 1. Navigate to the C1 service directory
cd services/c1-url-domain-analyzer

# 2. Create a Python virtual environment
python3 -m venv .venv

# 3. Activate the virtual environment
source .venv/bin/activate

# 4. Upgrade pip and install all required dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 5. Create local environment configuration from example
cp .env.example .env

# 6. Start the FastAPI microservice with hot-reloading
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

#### Windows (PowerShell)
```powershell
# 1. Navigate to the C1 service directory
cd services\c1-url-domain-analyzer

# 2. Create a Python virtual environment
python -m venv .venv

# 3. Activate the virtual environment
.venv\Scripts\Activate.ps1

# 4. Upgrade pip and install all required dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 5. Create local environment configuration from example
Copy-Item .env.example .env

# 6. Start the FastAPI microservice with hot-reloading
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

---

### 7.3 Frontend Setup (React SOC Dashboard)

Open a separate terminal window:

```bash
# 1. Navigate to the frontend dashboard directory
cd frontend/scamtrace-dashboard

# 2. Install Node dependencies
npm install

# 3. Start the Vite development server
npm run dev
```

The frontend dashboard will be available at: **`http://localhost:5173`**  
The URL Analyzer interface is located at: **`http://localhost:5173/url-analyzer`**

---

### 7.4 Verifying Service Operation
In a third terminal, verify that the backend microservice is operational:

```bash
# Verify health check endpoint
curl -s http://localhost:8001/health | jq .

# Verify machine learning model status
curl -s http://localhost:8001/api/v1/ml-model-status | jq .
```

Expected output:
```json
{
  "status": "ok",
  "service": "c1-url-domain-analyzer",
  "component": "C1_URL_DOMAIN",
  "mongodb_connected": false
}
```
*(Note: `mongodb_connected: false` is completely normal if MongoDB is not locally installed. C1 operates in standalone in-memory mode without degradation).*

---

### 7.5 Cross-Device Compatibility Guide for Group Members

If another team member is setting up C1 on their laptop, follow this checklist to prevent common cross-device pitfalls:

1. **Pre-Trained Models are Bundled in Git**:
   - The Random Forest model (`models/best_model.joblib`) and preprocessor (`models/preprocessor.joblib`) are already tracked and included in the repository.
   - **Group members do NOT need to download external weights or retrain models.**
   - The engine automatically resolves `model_dir` to `services/c1-url-domain-analyzer/models` whether the service is started from the C1 directory, the repository root, or an IDE terminal.

2. **Windows PowerShell Execution Policy**:
   - If Windows blocks virtual environment activation (`Activate.ps1 cannot be loaded because running scripts is disabled`), run PowerShell as Administrator or allow process-level script execution:
     ```powershell
     Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
     .\.venv\Scripts\Activate.ps1
     ```

3. **Frontend Dashboard Connectivity**:
   - The frontend (`frontend/scamtrace-dashboard`) includes a `.env.example` file.
   - Ensure `frontend/scamtrace-dashboard/.env` contains:
     ```env
     VITE_C1_URL=http://localhost:8001
     ```
   - If C1 is running on a custom port (e.g. `8005`), update `VITE_C1_URL=http://localhost:8005` in `frontend/scamtrace-dashboard/.env`.

4. **Zero External API Dependency for Testing**:
   - External threat intelligence API keys (`VIRUSTOTAL_API_KEY`, `THREATFOX_API_KEY`) and MongoDB are **100% optional**.
   - C1 operates autonomously in local heuristic + ML mode with full accuracy without needing paid third-party accounts.

5. **Port Conflicts**:
   - If port 8001 is occupied by another application, change `PORT=8005` in `services/c1-url-domain-analyzer/.env` and update `VITE_C1_URL=http://localhost:8005` in `frontend/scamtrace-dashboard/.env`.

---

## 8. Environment Configuration

All configurable parameters are declared in `app/config.py` and can be customized via `.env`.

### 8.1 Configuration Variables Table

| Variable Name | Required | Default Value | Purpose |
| :--- | :---: | :---: | :--- |
| `PORT` / `C1_PORT` | Optional | `8001` | TCP port on which the FastAPI ASGI server listens. |
| `HOST` / `C1_HOST` | Optional | `0.0.0.0` | Network binding interface (`0.0.0.0` permits external/Docker access). |
| `LOG_LEVEL` | Optional | `INFO` | Console logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `FRONTEND_URL` | Optional | `http://localhost:5173` | Allowed CORS origin for browser client requests. |
| `C1_SERVICE_NAME` / `SERVICE_NAME` | Optional | `c1-url-domain-analyzer` | Service identifier string for telemetry and logging. |
| `MODEL_DIR` | Optional | `services/c1-url-domain-analyzer/models` | Path to directory containing `best_model.joblib` and `preprocessor.joblib`. |
| `MONGODB_URI` | Optional | `mongodb://localhost:27017` | Optional MongoDB connection URI for persistent scan telemetry (falls back to memory if offline). |
| `MONGODB_DATABASE` | Optional | `url_domain_analyzer` | Target database name for scan logs. |
| `NRD_THRESHOLD_DAYS` | Optional | `30` | Registration age in days below which a domain is flagged as an NRD. |
| `NRD_WARNING_THRESHOLD_DAYS`| Optional| `90` | Registration age in days below which a domain triggers an elevated warning. |
| `DNS_TIMEOUT_SECONDS` | Optional | `3.0` | Maximum timeout in seconds for DNS resolver lookups. |
| `RDAP_TIMEOUT_SECONDS` | Optional | `5.0` | Maximum timeout in seconds for public RDAP/WHOIS HTTP lookups. |
| `CACHE_TTL_SECONDS` | Optional | `3600` | In-memory cache time-to-live (1 hour) to prevent repeated network queries. |
| `VIRUSTOTAL_API_KEY` | Optional | `""` | Optional VirusTotal API key (leave blank to run in offline heuristic mode). |
| `THREATFOX_API_KEY` | Optional | `""` | Optional ThreatFox API key (leave blank to run in offline heuristic mode). |

> **Security Notice**: Never commit `.env` files containing real API credentials to version control. The repository's `.gitignore` explicitly excludes `.env`.

---

## 9. API Documentation

Component C1 exposes REST API endpoints documented via interactive OpenAPI/Swagger at `http://localhost:8001/docs`.

### 9.1 Master Endpoint: `/analyze-url` (or `/api/v1/analyze-url`)
- **HTTP Method**: `POST`
- **Purpose**: Triggers the complete 4-layer multi-channel inspection pipeline and returns the synthesized explainable verdict.
- **Request Body**:
```json
{
  "url": "https://secure-login.bankofamerica-verify-session.top/auth/signin"
}
```

- **Example Response (High Risk Phishing)**:
```json
{
  "target_url": "https://secure-login.bankofamerica-verify-session.top/auth/signin",
  "analyzed_at": "2026-10-21T04:30:00.000000Z",
  "lexical": {
    "url_length": 68,
    "hostname": "secure-login.bankofamerica-verify-session.top",
    "registered_domain": "bankofamerica-verify-session.top",
    "tld": "top",
    "is_https": true,
    "has_suspicious_keyword": true,
    "suspicious_keyword_count": 2,
    "suspicious_keywords_found": ["login", "verify"],
    "is_suspicious_tld": true,
    "url_entropy": 4.12
  },
  "domain": {
    "registration": {
      "is_data_available": true,
      "age_days": 4,
      "is_nrd": true
    },
    "dns": {
      "dns_resolved": true,
      "ip_count": 1,
      "a_records": ["198.51.100.42"],
      "is_fast_flux": false
    }
  },
  "threat_infrastructure": {
    "dga": {
      "is_dga_suspected": false,
      "dga_score": 0.12
    },
    "redirect_chain": {
      "total_hops": 0,
      "is_shortened": false,
      "ssrf_blocked": false
    }
  },
  "ml_prediction": {
    "is_model_loaded": true,
    "predicted_class": 1,
    "predicted_label": "malicious",
    "malicious_probability": 0.94,
    "confidence": 94.0
  },
  "risk_assessment": {
    "overall_risk_score": 96.5,
    "final_verdict": "PHISHING",
    "confidence_level": "high",
    "active_weights": {
      "lexical_structural": 0.096,
      "entropy_obfuscation": 0.106,
      "homoglyph_lookalike": 0.106,
      "domain_registration": 0.213,
      "dns_reputation": 0.160,
      "dga": 0.053,
      "shortener_redirect": 0.106,
      "machine_learning": 0.160
    },
    "contributing_factors": [
      {
        "factor_id": "compound_nrd_phishing_synergy",
        "title": "Compound Threat Synergy: NRD + Security Keywords",
        "category": "domain_registration",
        "impact_score": 25.0,
        "evidence": "High-risk compound threat alignment detected across freshly registered domain, sensitive credential/login keywords.",
        "confidence": "high",
        "epistemic_type": "heuristic"
      }
    ],
    "epistemic_breakdown": {
      "observed_facts": [
        "Target URL scheme: 'https', host: 'secure-login.bankofamerica-verify-session.top'.",
        "Domain registration creation date: 2026-10-17, calculated age: 4 days."
      ],
      "heuristic_indicators": [
        "Rule-based detection matched 2 sensitive keyword(s): ['login', 'verify'].",
        "Top-level domain '.top' matched curated high-risk TLD list.",
        "Domain classified as Newly Registered Domain (NRD) (age <= 30 days)."
      ],
      "model_predictions": [
        "Supervised ML classifier (Random Forest) predicted class 'malicious' with malicious probability 0.94 (94.0% confidence)."
      ]
    }
  }
}
```

---

### 9.2 Specialized Endpoints Summary

| HTTP Method | Path | Request Body | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | None | Operational uptime and MongoDB connectivity check. |
| `POST` | `/api/v1/extract-features` | `{"url": "..."}` | Returns raw 57-dimensional feature dictionary for training scripts. |
| `POST` | `/api/v1/domain-intelligence` | `{"url": "..."}` | Executes Layer 2 only: RDAP domain age, NRD status, and DNS records. |
| `POST` | `/api/v1/dga-analysis` | `{"url": "..."}` | Executes Layer 3 DGA statistical analysis on domain label. |
| `POST` | `/api/v1/redirect-analysis` | `{"url": "..."}` | Traces redirect hops and tests SSRF boundaries. |
| `POST` | `/api/v1/ml-predict` | `{"url": "..."}` | Runs standalone Random Forest classification without network scans. |
| `GET` | `/api/v1/ml-model-status` | None | Returns active model metadata, feature count, and decision cutoff. |
| `POST` | `/api/v1/explain-risk` | `{"url": "..."}` | Returns full explainable audit trail and dynamic weights telemetry. |
| `GET` | `/api/v1/scoring-weights` | None | Returns nominal prior weights, rationales, and threshold cutoffs. |

---

## 10. Testing and Evaluation

Component C1 includes 104 automated tests spanning 9 test suites verifying all layers, edge cases, and safety bounds.

### 10.1 Running the Automated Test Suite
From the `services/c1-url-domain-analyzer` directory with the virtual environment activated:

```bash
# Run the entire test suite with verbose reporting
.venv/bin/pytest -v
```

Expected output:
```
====================== 104 passed in 50.79s =======================
```

### 10.2 Test Suite Breakdown
| Test Module | Tests | Verification Scope |
| :--- | :---: | :--- |
| `tests/test_lexical_analyzer.py` | 8 | Shannon entropy math, RFC 3986 syntax, tracking token isolation, homoglyphs. |
| `tests/test_domain_intelligence.py` | 12 | RDAP response parsing, NRD age heuristics, DNS record handling, fast-flux detection. |
| `tests/test_threat_infrastructure.py` | 11 | DGA vowel/consonant perplexity, safe redirect following, loop detection, SSRF defenses. |
| `tests/test_ml_pipeline.py` | 13 | 57-feature vector consistency, zero-leakage `domain_grouped` splits, inference latency. |
| `tests/test_risk_scoring_engine.py` | 14 | Dynamic weight renormalization, collinearity dampening, epistemic tier segregation. |
| `tests/test_final_verdict.py` | 16 | Rigorous evaluation of $>80\%$, $=80\%$, and $<80\%$ operational verdict boundaries. |
| `tests/test_fp_fn_reduction.py` | 17 | Edge-case validation against corporate tracking tokens, legitimate auth portals, and raw IPs. |
| `tests/test_api.py` | 13 | HTTP request/response validation, status codes, and error handlers. |
| **Total Test Count** | **104** | **100% Passing Status** |

### 10.3 Illustrative Test Cases
- **Legitimate Corporate Auth Portal**: `https://accounts.google.com/signin/v2/identifier`
  - *Result*: Low Risk (`18.5`), Verdict: `SAFE` (Mitigated by enterprise domain age guardrail $> 5\text{ years}$).
- **Targeted Brand Phishing**: `http://secure-appleid-verification.top/login.php`
  - *Result*: High Risk (`94.0`), Verdict: `PHISHING` (Triggered by NRD $\le 30\text{d}$ + sensitive credential keywords + high-risk TLD).
- **Botnet C2 DGA Domain**: `http://xrqmzbptw9asdf.biz/gateway`
  - *Result*: High Risk (`86.2`), Verdict: `MALICIOUS` (Triggered by label entropy $> 3.6$ + consonant clustering).
- **Legitimate E-Commerce Link with Tracking**: `https://www.nike.com/shoes?utm_source=google&utm_medium=cpc&srsltid=12345`
  - *Result*: Low Risk (`12.0`), Verdict: `SAFE` (Entropy tracking filter successfully isolated tracking tokens).

---

## 11. Project Structure

```
services/c1-url-domain-analyzer/
|-- .env.example                       # Documented environment template with placeholders
|-- .gitignore                         # Excludes .venv, .env, __pycache__, and dataset archives
|-- main.py                            # FastAPI application entry point, CORS, and lifespan
|-- requirements.txt                   # Production Python package dependencies
|-- README.md                          # Comprehensive research component documentation
|-- README_DATASET_PIPELINE.md         # Guide for downloading and preparing 200k+ URL datasets
|
|-- app/
|   |-- config.py                      # Centralized thresholds, nominal weights, and settings
|   |-- database.py                    # MongoDB client with graceful in-memory fallback
|   |
|   |-- analyzers/                     # Core multi-layer security inspection engines
|   |   |-- lexical_analyzer.py        # Layer 1: 57-feature extractor, Shannon entropy, homoglyphs
|   |   |-- registration_analyzer.py   # Layer 2: Public RDAP / WHOIS parser & NRD age calculator
|   |   |-- dns_analyzer.py            # Layer 2: DNS resolver (A, AAAA, MX, NS, TXT) & fast-flux
|   |   |-- domain_intelligence.py     # Layer 2: Consolidated domain intelligence coordinator
|   |   |-- dga_analyzer.py            # Layer 3: Statistical DGA detection (entropy, bigrams)
|   |   |-- redirect_analyzer.py       # Layer 3: Safe HTTP redirect resolver with SSRF filter
|   |   |-- threat_infrastructure.py   # Layer 3: Consolidated DGA + redirect intelligence
|   |   |-- risk_scoring_engine.py     # Synthesis: Dynamic weight renormalization & explainable XAI
|   |
|   |-- api/                           # REST API routes and controllers
|   |   |-- health.py                  # Uptime and service health endpoints
|   |   |-- url_routes.py              # Master and specialized analysis HTTP endpoints
|   |
|   |-- ml/                            # Machine learning training, data preparation & inference
|   |   |-- feature_extractor.py       # Standardized 57-dimensional feature extraction bridge
|   |   |-- model_service.py           # Singleton service loading joblib model and running inference
|   |   |-- prepare_dataset.py         # Chunked streaming cleaner for 200,000+ URL datasets
|   |   |-- train.py                   # Model trainer with zero-leakage GroupShuffleSplit
|   |   |-- build_live_dataset.py      # Automated pipeline downloading URLhaus, PhishTank, Tranco
|   |
|   `-- schemas/
|       `-- url_schema.py              # Pydantic data schemas for all request/response models
|
|-- models/                            # Trained model artifacts and academic reports
|   |-- best_model.joblib              # Serialized Random Forest classifier
|   |-- preprocessor.joblib            # Fitted median imputer and standard scaler
|   |-- model_metadata.json            # 57 feature names, calibrated cutoff (0.44), metrics
|   |-- model_comparison_report.md     # Test set confusion matrices and baseline comparison
|   `-- threshold_tuning_report.md     # Validation set decision threshold calibration curve
|
`-- tests/                             # Automated test suite (104 test cases)
    |-- test_lexical_analyzer.py
    |-- test_domain_intelligence.py
    |-- test_threat_infrastructure.py
    |-- test_ml_pipeline.py
    |-- test_risk_scoring_engine.py
    |-- test_final_verdict.py
    |-- test_fp_fn_reduction.py
    `-- test_api.py
```

---

## 12. Limitations and Future Improvements

### 12.1 Realistic Engineering Limitations
1. **Public RDAP / WHOIS Rate Limits**: Public RDAP bootstrap servers (`rdap.org`) enforce rate limits on high-volume traffic. C1 mitigates this with an in-memory 1-hour cache (`cache_ttl_seconds = 3600`), but sustained scanning of new domains may result in temporary WHOIS unavailability (gracefully handled by dynamic weight renormalization).
2. **Pre-Execution Scope**: C1 analyzes URLs statically and through network metadata without rendering the webpage DOM. Consequently, attacks that serve benign content to security scanners while executing client-side JavaScript cloaking or DOM-based phishing are passed to downstream components (Component C2 Webpage Content Analyzer).
3. **Shortener Redirect Depths**: To prevent denial-of-service and infinite loop exhaustion, redirect resolution is capped at 8 hops (`max_redirect_hops = 8`). Highly convoluted redirect chains exceeding 8 hops will terminate analysis at the 8th hop.

### 12.2 Planned Future Improvements
- **Local TLD Zone File Ingestion**: Ingest daily ICANN zone files directly into a local Redis cache to perform sub-millisecond NRD lookups without querying external RDAP servers.
- **Deep Learning Sequence Models**: Explore character-level Bidirectional LSTM or Transformer architectures to evaluate URL sequences alongside tree ensembles.
- **Client-Side WASM Compilation**: Compile C1's 57-feature lexical extractor to WebAssembly (WASM) to run directly inside the browser extension without microservice network latency.

---

## 13. Troubleshooting

### 13.1 Missing Python Dependencies or Virtual Environment Issues
- **Symptom**: `ModuleNotFoundError: No module named 'fastapi'` or `'tldextract'`.
- **Solution**: Ensure your virtual environment is active (`source .venv/bin/activate` or `.venv\Scripts\Activate.ps1`) and run `pip install -r requirements.txt`.

### 13.2 Port Conflict (`Address already in use: 8001`)
- **Symptom**: `ERROR: [Errno 48] error while attempting to bind on address ('0.0.0.0', 8001)`.
- **Solution**: Identify and terminate the process holding port 8001:
  ```bash
  # macOS / Linux
  lsof -i :8001
  kill -9 <PID>
  
  # Or run C1 on an alternate port:
  uvicorn main:app --port 8005 --reload
  ```

### 13.3 Frontend Cannot Connect to Backend
- **Symptom**: Network error or CORS failure in browser developer console.
- **Solution**: Verify that the FastAPI backend is running (`curl http://localhost:8001/health`). If running on an alternate port, update the API base URL in the frontend configuration.

### 13.4 Model Artifact Not Found
- **Symptom**: Log message `Model artifact not found; falling back to heuristic mode`.
- **Solution**: Check that `models/best_model.joblib` and `models/preprocessor.joblib` exist. If missing, regenerate them using the trained pipeline:
  ```bash
  python -m app.ml.train --data-path data/dataset_200k.csv --output-dir models
  ```

---

## 14. Research Contribution

Component C1 delivers **four primary academic and practical contributions** to the field of cybersecurity:

1. **Multi-Layer Pre-Execution Defense without DOM Rendering**: Eliminates zero-day client-side exploitation by resolving threat intent across 57 static lexical indicators, cryptographic entropy, and infrastructure signals prior to browser execution.
2. **Hybrid Ephemeral Threat Detection**: Unifies Newly Registered Domain (NRD $\le$ 30 days) heuristics with statistical DGA bigram perplexity, neutralizing adversaries who register short-lived domains to bypass static threat feeds.
3. **Availability-Aware Dynamic Weight Renormalization**: Solves the critical real-world problem of external service outages (WHOIS timeouts, DNS privacy guards). By mathematically scaling active channel weights to sum to 100%, missing telemetry never falsely deflates a URL's risk score.
4. **Explainable Risk Scoring with Epistemic Evidence Separation**: Replaces opaque "black-box" scores with an auditable security audit trail separating **Observed Facts**, **Heuristic Indicators**, and **Model Predictions**, empowering human analysts and satisfying ethical AI standards.

---
*Component C1 — Developed as part of the Final Year Research Project: AI-Powered Browser Extension for Intelligent Web Threat Detection and User Protection.*
