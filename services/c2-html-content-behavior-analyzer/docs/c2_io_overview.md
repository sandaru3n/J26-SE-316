# C2 – Input / Process / Output overview (progress presentation)

Design-level summary of the 9 implementation parts of **C2 – Multilingual HTML & Content
Analysis Engine** and the runtime `POST /api/v1/analyze` flow. One table per part, sized for a
slide. Details: `README.md`, `CLAUDE.md`, `docs/api_contract.md`, `docs/requirements_traceability.md`.

> **Section numbers.** The proposal document with the 4.3.x numbering is not in the repository.
> Sections 4.3.1–4.3.6 are assumed here to follow the six functional modules of the proposal's
> "Detection Pipeline" slide (same order). Check them against the proposal before presenting.

| § | Proposal module (assumed) | C2 parts |
|---|---|---|
| 4.3.1 | DOM structural analysis | 2, 3, 4 |
| 4.3.2 | Multilingual NLP (XLM-RoBERTa, en / si / ta) | 5, 6 |
| 4.3.3 | Malware & browser-abuse detection | 7, 8 |
| 4.3.4 | Brand impersonation & deceptive UI | 3, 5, 8 (partly, see note) |
| 4.3.5 | Static dataflow tracking | 7, 8 |
| 4.3.6 | Fusion & classification | 9 |
| (data) | Data sources: PhishTank / OpenPhish, custom si / ta scam text | 1 (foundation for all) |

Threat classes everywhere: `benign`, `phishing`, `fake_ecommerce`, `crypto_scam`, `malware_delivery`.

---

## Part 1 – Dataset preparation  ·  foundation for 4.3.1–4.3.6 (data sources)

| | |
|---|---|
| **Input** | URL feeds (OpenPhish, PhishTank, URLhaus, Tranco, ThreatRadar Telegram / Reddit exports, manual CSV) |
| **Processing** | 1. Import URLs as candidates and remove repeats<br>2. Fetch each page safely (static, no JavaScript, private addresses blocked)<br>3. Register the page with its label, language and source<br>4. Flag poor pages (parking, bot challenge, empty) and group near-duplicates<br>5. Human label review + peer agreement (Cohen's kappa)<br>6. Statistics, then freeze a dataset version |
| **Output** | `data/raw/<label>/*.html`, `data/metadata/metadata.csv`, `data/metadata/manifests/dataset_v0.3.{csv,json}` (459 pages), `reports/dataset_stats/dataset_stats.{md,json}`, shared split `data/splits/v0.3/{split.csv, cv_folds.csv}` |

## Part 2 – HTML preprocessing  ·  4.3.1

| | |
|---|---|
| **Input** | Raw HTML of one page (+ optional page URL) |
| **Processing** | 1. Parse the HTML (never runs JavaScript, never fetches)<br>2. Separate visible text and hidden text<br>3. Extract forms, inputs, links, scripts, iframes, meta tags<br>4. Mask personal data in stored values |
| **Output** | `ParsedPage` JSON → `data/processed/parsed_html/<version>/<sample_id>.json` · API `POST /api/v1/preprocess` |

## Part 3 – DOM structural analysis  ·  4.3.1 (and 4.3.4: hidden elements, external links / CSS)

| | |
|---|---|
| **Input** | `ParsedPage` (+ raw HTML for tree metrics) |
| **Processing** | 1. Classify form fields (password, card, OTP / PIN, email, username)<br>2. Measure forms, form targets, hidden elements, iframes, links, page structure<br>3. Build a fixed-order vector of 52 features<br>4. Write plain-English evidence for notable values |
| **Output** | `DomResult` JSON, `data/processed/dom_features/<version>/dom_features.csv` · API `POST /api/v1/dom-features` |

## Part 4 – DOM baseline classifier  ·  4.3.1 (ablation "DOM-only")

| | |
|---|---|
| **Input** | `dom_features.csv` + shared train / val / test split |
| **Processing** | 1. Drop constant / duplicate features (train split only)<br>2. Train Logistic Regression, Random Forest, XGBoost; pick by cross-validation<br>3. Evaluate once on the test split<br>4. Explain with feature importance / SHAP |
| **Output** | `models/dom_baseline/<version>/*.joblib` + `model_card.json`, `reports/dom_baseline/<version>/results.{md,json}`, `DomPrediction` |

## Part 5 – Multilingual content analyzer  ·  4.3.2 (and 4.3.4: urgency / impersonation cues)

| | |
|---|---|
| **Input** | `ParsedPage` (+ raw HTML for buttons / alert banners) |
| **Processing** | 1. Collect text by role: title, headings, buttons (CTA), form labels, alerts, paragraphs<br>2. Detect language per segment and per page (en / si / ta / Singlish / Tanglish / mixed / other)<br>3. Build one tagged `page_text` for the text models<br>4. Intent taxonomy (credential request, payment, investment lure, fake warning, fake reward, urgency, impersonation) and a scam-text corpus |
| **Output** | `PageText` JSON → `data/processed/text/<version>/`, `text_index.csv`, `configs/intent_taxonomy.yaml`, `data/corpus/corpus_v1.{csv,jsonl}` · API `POST /api/v1/content` |

## Part 6 – XLM-R classification  ·  4.3.2 (ablation "NLP-only")

| | |
|---|---|
| **Input** | `page_text` from Part 5 + shared split |
| **Processing** | 1. Fine-tune XLM-RoBERTa on Colab (3 seeds, early stopping on validation)<br>2. Train a TF-IDF + Logistic Regression text baseline on the same split<br>3. Check Colab vs local CPU predictions match, evaluate on test, per language<br>4. 6B (sentence-level intent model) postponed until real si / ta scam text exists |
| **Output** | `models/xlmr/<version>/final/` + `model_card.json`, `TextPrediction` JSON (both text models) · API `POST /api/v1/text-prediction` |

## Part 7 – Static JavaScript analyzer  ·  4.3.3, 4.3.5

| | |
|---|---|
| **Input** | Inline scripts, event handlers, `javascript:` URLs and external script references from `ParsedPage` |
| **Processing** | 1. Parse each script into a syntax tree (tree-sitter; regex fallback when broken)<br>2. Detect risky API use (eval, network requests, redirects, clipboard, key listeners, …)<br>3. Recognise known libraries and keep them apart<br>4. Measure obfuscation (entropy, packers, encoded strings)<br>— JavaScript is never executed |
| **Output** | `JsAnalysisResult` JSON, `data/processed/js/<version>/js_features.csv` (51 features) · API `POST /api/v1/js-analysis` |

## Part 8 – Behavioral intent mapping  ·  4.3.3, 4.3.5 (and 4.3.4: right-click blocking, hidden redirects)

| | |
|---|---|
| **Input** | `ParsedPage` + `JsAnalysisResult` |
| **Processing** | 1. Find sources (password, card, keystrokes, clipboard) and sinks (network, redirect, eval, download)<br>2. Follow data from source to sink (static taint tracking)<br>3. Match behavior patterns: credential exfiltration, keylogging, forced redirect, clipboard hijack / ClickFix, risky download, obfuscated execution, anti-analysis<br>4. Score severity, build an evidence chain and a 39-value intent vector<br>5. Behavior-only baseline classifier |
| **Output** | `BehaviorResult` JSON, `data/processed/behavior/<version>/behavior_features.csv`, `reports/behavior/benchmark_v1.md` · API `POST /api/v1/behavior` |

## Part 9 – Fusion, API, ingestion  ·  4.3.6

| | |
|---|---|
| **Input** | Per-arm class probabilities (DOM, Behavior, TF-IDF text, XLM-R text); at runtime a URL or HTML; ThreatRadar URL batches |
| **Processing** | **9A** Out-of-fold probabilities per arm → compare mean / weighted / stacking / hybrid fusion → ablation (single, pairs, tri-modal) with bootstrap CIs<br>**9B-1** Verdict tiers (Malicious ≤ 2 % benign FPR, Suspicious ≥ 95 % threat recall) + evidence-floor rules; `/analyze` endpoint<br>**9B-2** ThreatRadar push / daily pull → queue → background worker → results store → human review queue → dashboard APIs |
| **Output** | `models/fusion/<version>/fusion.joblib`, `configs/verdict.yaml` (thresholds), `reports/ablation/<version>/ablation.md`, `reports/verdict/v0.3_operating_points.md`, `AnalysisResponse` JSON (`c2.analysis.v1`), results DB (`scan_jobs`, `scan_results`, `review_queue`) · APIs `/api/v1/analyze`, `/ingest`, `/scans`, `/stats/overview`, `/feed/stream`, `/research/summary` |

> **Note on 4.3.4 (brand impersonation & deceptive UI).** There is no dedicated logo / brand
> matcher yet. The module is covered by existing signals: hidden elements and external links /
> stylesheets (Part 3), urgency and impersonation cue words (Part 5), right-click / DevTools
> blocking and hidden redirects (Part 8), and look-alike brand hosts in ThreatRadar stats (9B-2).

---

## Runtime flow – `POST /api/v1/analyze`  ·  4.3.1–4.3.6 end to end

| | |
|---|---|
| **Input** | JSON `{ "url": … }` (C2 fetches) **or** `{ "html": …, "url"?: … }`, plus `request_id`, `source` |
| **Processing** | 1. **Fetch** safely (static GET, private addresses refused, 10 s, 5 MB) or take the pasted HTML<br>2. **Preprocess** (Part 2) and check page quality (parking / challenge → inconclusive)<br>3. **Structure lane:** DOM features → DOM model (Parts 3–4)<br>4. **Content lane:** text + language → TF-IDF and XLM-R models (Parts 5–6)<br>5. **Behavior lane:** JS analysis → behavior mapping → behavior model (Parts 7–8)<br>6. **Fuse** the arm probabilities (failed arm → reweight, marked `degraded`)<br>7. **Decide** verdict tier + apply evidence-floor rules<br>8. **Explain:** rank findings, arm contributions, top features; store the result |
| **Output** | `AnalysisResponse` JSON: `status`, `verdict` (Legitimate / Suspicious / Malicious), `threat_class`, `risk_score` 0–100, `class_probabilities`, `findings[]` (≤ 10, with evidence chain), `modalities.{dom, content, behavior}`, `explanation`, `warnings`, `timings_ms` |

```
URL / HTML → Fetch → Preprocess ─┬─ DOM features → DOM model ──────────────┐
                                 ├─ Text + language → TF-IDF / XLM-R ──────┼→ Fusion → Verdict + evidence floor → JSON
                                 └─ JS AST → source→sink → Behavior model ─┘
```
