"""Domain Generation Algorithm (DGA) Statistical Analysis & Detection Engine.

=============================================================================
COMPONENT 1: INTELLIGENT URL & DOMAIN ANALYZER (C1) - LAYER 3: DGA DETECTOR
=============================================================================
This module detects procedurally generated domain names created by Domain
Generation Algorithms (DGAs).

What is a DGA and Why Do Attackers Use Them?
- Traditional malware used hardcoded IP addresses or domain names for Command &
  Control (C2) communication. Security teams easily blocked those static addresses.
- Modern malware families (e.g., Conficker, Necurs, Mirai, Gameover Zeus) employ DGAs:
  mathematical algorithms seeded with the current date or pseudo-random keys that generate
  hundreds or thousands of pseudo-random domain names every day (e.g., "xrqmbptw79.biz").
- The infected victim machines and the attacker's server both run the same algorithm.
  The attacker only needs to register ONE of the daily domains to establish control,
  making proactive domain takedowns extremely difficult.

How We Detect DGAs Without Running Malware:
1. Shannon Entropy: Random character strings exhibit much higher entropy (> 3.6 bits/char)
   than natural words ("google", "secure-bank").
2. Vowel-to-Consonant Ratio: English words typically contain 35% - 45% vowels.
   DGAs often output unpronounceable consonant clusters (e.g., "zxcvbnm", vowel ratio < 0.15).
3. Bigram Perplexity (Rarity): Natural language relies on common two-letter pairs ("th", "er", "in").
   DGAs produce letter transitions rarely or never seen in authentic languages (e.g., "qx", "zj", "vf").
4. Hexadecimal Hashes: Identifies MD5/SHA-like hex labels used by crypto-mining botnets.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import tldextract

from app.config import get_settings
from app.schemas.url_schema import DgaAnalysisFeatures

# Common English two-letter combinations (bigrams) derived from natural language corpora.
# In authentic words, letter pairs like "th", "he", "in", and "er" occur frequently.
COMMON_ENGLISH_BIGRAMS = {
    "th", "he", "in", "er", "an", "re", "on", "at", "en", "nd",
    "ti", "es", "or", "te", "of", "ed", "is", "it", "al", "ar",
    "st", "to", "nt", "ng", "se", "ha", "as", "ou", "io", "le",
    "ve", "co", "me", "de", "hi", "ri", "ro", "ic", "ne", "ea",
    "ra", "ce", "li", "ch", "ll", "be", "ma", "si", "om", "ur",
    "ly", "wa", "so", "no", "ta", "ut", "ge", "wi", "pe", "lo"
}

# Regex to identify purely hexadecimal labels (10+ characters of 0-9, a-f)
HEX_LABEL_PATTERN = re.compile(r'^[0-9a-fA-F]{10,}$')
VOWELS = set("aeiou")


def calculate_entropy(text: str) -> float:
    """Calculate Shannon entropy in bits per character.
    
    Formula: -Sum(p(x) * log2(p(x)))
    Higher values indicate greater character randomness.
    """
    if not text:
        return 0.0
    length = len(text)
    counts = Counter(text)
    entropy = -sum((c / length) * math.log2(c / length) for c in counts.values())
    return round(entropy, 4)


def calculate_bigram_rarity(label: str) -> float:
    """Calculate the fraction of bigrams in the label that are improbable in natural language.

    Returns value between 0.0 (all common natural bigrams) and 1.0 (all rare/random bigrams).
    Example:
    - 'bank' -> pairs: 'ba', 'an', 'nk' -> common in English -> low rarity score (~0.0 - 0.3)
    - 'xqzb' -> pairs: 'xq', 'qz', 'zb' -> rare/impossible in English -> high rarity score (~1.0)
    """
    clean_alpha = "".join(c for c in label.lower() if c.isalpha())
    if len(clean_alpha) < 2:
        return 0.0

    total_bigrams = len(clean_alpha) - 1
    rare_count = 0

    for i in range(total_bigrams):
        pair = clean_alpha[i:i+2]
        if pair not in COMMON_ENGLISH_BIGRAMS:
            rare_count += 1

    return round(rare_count / total_bigrams, 4)


def extract_primary_label(domain_name: str) -> str:
    """Extract the most significant domain label for DGA evaluation (SLD or suspicious subdomain)."""
    clean = domain_name.strip().lower().strip(".")
    extracted = tldextract.extract(clean)
    domain_part = extracted.domain

    # If domain_part is very short (e.g. dynamic DNS host) but subdomain is long, analyze subdomain
    if len(domain_part) <= 4 and extracted.subdomain:
        sub_labels = [s for s in extracted.subdomain.split(".") if s and s != "www"]
        if sub_labels:
            # Pick label with highest entropy
            return max(sub_labels, key=lambda s: calculate_entropy(s))

    return domain_part or clean.split(".")[0]


class DgaAnalyzer:
    """Analyzer for detecting Domain Generation Algorithm patterns via statistical metrics."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def analyze(self, domain_name: str) -> DgaAnalysisFeatures:
        """Extract statistical DGA metrics and evaluate algorithmic generation probability."""
        clean_domain = domain_name.strip().lower().strip(".")
        if not clean_domain:
            return self._empty_features("")

        label = extract_primary_label(clean_domain)
        label_len = len(label)
        if label_len == 0:
            return self._empty_features(clean_domain)

        label_entropy = calculate_entropy(label)

        # Character counts
        vowel_count = sum(c in VOWELS for c in label)
        consonant_count = sum(c.isalpha() and c not in VOWELS for c in label)
        digit_count = sum(c.isdigit() for c in label)
        alpha_count = vowel_count + consonant_count

        vowel_ratio = round(vowel_count / alpha_count, 4) if alpha_count > 0 else 0.0
        consonant_ratio = round(consonant_count / alpha_count, 4) if alpha_count > 0 else 0.0
        digit_ratio = round(digit_count / label_len, 4)

        # Longest consecutive consonant cluster
        consonant_clusters = re.findall(r'[bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ]+', label)
        max_consecutive_consonants = max((len(c) for c in consonant_clusters), default=0)

        # Bigram rarity
        bigram_perplexity = calculate_bigram_rarity(label)

        # Statistical DGA Scoring Model
        score_components: List[float] = []
        indicators: List[str] = []
        family_hint: Optional[str] = None

        # 1. High label entropy
        if label_entropy >= self.settings.dga_entropy_threshold and label_len >= 8:
            score_components.append(0.35)
            indicators.append(
                f"Elevated label Shannon entropy ({label_entropy} bits/char, threshold >= {self.settings.dga_entropy_threshold})."
            )

        # 2. Vowel ratio imbalance
        if alpha_count >= 6:
            if vowel_ratio < self.settings.dga_vowel_ratio_min:
                score_components.append(0.25)
                indicators.append(
                    f"Abnormally low vowel-to-consonant ratio ({vowel_ratio:.2f}, expected >= {self.settings.dga_vowel_ratio_min})."
                )
            elif vowel_ratio > self.settings.dga_vowel_ratio_max:
                score_components.append(0.15)
                indicators.append(
                    f"Abnormally high vowel concentration ({vowel_ratio:.2f})."
                )

        # 3. Excessive consecutive consonant run
        if max_consecutive_consonants >= 4 and label_len >= 7:
            score_components.append(0.20)
            indicators.append(
                f"Consecutive consonant cluster ({max_consecutive_consonants} consecutive consonants without vowels)."
            )

        # 4. Bigram transition rarity
        if bigram_perplexity >= 0.70 and label_len >= 8:
            score_components.append(0.25)
            indicators.append(
                f"Unnatural letter transition score ({bigram_perplexity:.2f} improbable bigram transitions)."
            )

        # 5. Hexadecimal MD5/Hash pattern
        if HEX_LABEL_PATTERN.match(label):
            score_components.append(0.40)
            family_hint = "hex_hash_dga"
            indicators.append("Hexadecimal hash string pattern detected in domain label.")

        # 6. Hybrid alphanumeric entropy
        if digit_count >= 3 and alpha_count >= 5 and label_entropy >= 3.3:
            score_components.append(0.20)
            if not family_hint:
                family_hint = "alphanumeric_hybrid_dga"
            indicators.append("Interleaved alphanumeric random pattern detected.")

        if not family_hint and max_consecutive_consonants >= 5:
            family_hint = "pseudo_random_consonant_dga"

        raw_score = sum(score_components)
        dga_score = round(min(1.0, max(0.0, raw_score)), 2)
        is_dga_suspected = dga_score >= 0.60

        if is_dga_suspected:
            indicators.append(
                "Suspicious algorithmic generation characteristics observed. This represents procedural generation rather than confirmed malware execution on its own."
            )
        elif not indicators:
            indicators.append("Domain label exhibits standard natural language phonetic characteristics.")

        return DgaAnalysisFeatures(
            domain_name=clean_domain,
            label=label,
            label_length=label_len,
            label_entropy=label_entropy,
            vowel_count=vowel_count,
            consonant_count=consonant_count,
            digit_count=digit_count,
            vowel_ratio=vowel_ratio,
            consonant_ratio=consonant_ratio,
            digit_ratio=digit_ratio,
            max_consecutive_consonants=max_consecutive_consonants,
            bigram_perplexity=bigram_perplexity,
            dga_score=dga_score,
            is_dga_suspected=is_dga_suspected,
            dga_family_hint=family_hint,
            dga_indicators=indicators,
        )

    def _empty_features(self, domain: str) -> DgaAnalysisFeatures:
        """Return zeroed features model for empty domain input."""
        return DgaAnalysisFeatures(
            domain_name=domain,
            label="",
            label_length=0,
            label_entropy=0.0,
            vowel_count=0,
            consonant_count=0,
            digit_count=0,
            vowel_ratio=0.0,
            consonant_ratio=0.0,
            digit_ratio=0.0,
            max_consecutive_consonants=0,
            bigram_perplexity=0.0,
            dga_score=0.0,
            is_dga_suspected=False,
            dga_family_hint=None,
            dga_indicators=["Empty domain provided."],
        )
