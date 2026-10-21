"""Domain Registration & WHOIS/RDAP Intelligence Analyzer.

=============================================================================
COMPONENT 1: INTELLIGENT URL & DOMAIN ANALYZER (C1) - LAYER 2: REGISTRATION
=============================================================================
This module inspects domain registration records (WHOIS / RDAP) to calculate
domain age and identify Newly Registered Domains (NRDs).

Why Domain Registration Age is a Critical Security Signal (Contribution 2):
- Over 70% of active phishing and scam sites are hosted on domains registered
  less than 30 days prior.
- Malicious actors purchase cheap disposable domains, deploy landing pages,
  send mass scam messages, and abandon the domains once blacklisted.
- Conversely, well-established domains (> 2 years old like apple.com or github.com)
  have extensive trust history and receive mitigating credits to avoid false alarms.

Protocol Information (RDAP vs WHOIS):
- Traditional WHOIS operates on raw TCP port 43 with free-form unstructured text.
- RDAP (Registration Data Access Protocol, RFC 7480-7484) is the modern successor
  standardized by ICANN. It delivers structured JSON over standard HTTPS (port 443).
- This module queries public RDAP bootstrap servers first, with automated fallback
  to python-whois if needed.

Core Research Contribution 3 Principle:
- In the real world, RDAP/WHOIS queries frequently fail due to registrar rate limits,
  network timeouts, or strict privacy redaction (GDPR masking).
- Our system STRICTLY ensures that unavailable or timed-out registration data is
  NEVER penalized as malicious evidence. Missing evidence triggers dynamic weight
  renormalization rather than false accusations!
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import httpx

try:
    import whois
    _HAS_PYTHON_WHOIS = True
except ImportError:  # pragma: no cover
    _HAS_PYTHON_WHOIS = False

from app.config import get_settings
from app.schemas.url_schema import DomainRegistrationFeatures

logger = logging.getLogger(__name__)

# Known privacy/proxy service strings indicating masked owner information
PRIVACY_INDICATORS = {
    "privacy", "proxy", "whoisguard", "withheld", "redacted",
    "domains by proxy", "private protect", "identity protect",
    "contact privacy", "anonym", "gdpr masked"
}


def parse_iso_datetime(date_str: str) -> Optional[datetime]:
    """Parse various ISO-8601 timestamp formats to timezone-aware UTC datetime.
    
    Handles standard Zulu timestamps ("2024-05-01T12:00:00Z") as well as
    common registrar variants without timezone offsets.
    """
    if not date_str:
        return None
    try:
        # Standard ISO format with trailing Z
        cleaned = date_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass

    # Fallback formats without 'T' separator
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


class RegistrationAnalyzer:
    """Analyzer for domain registration age, registrar, and RDAP/WHOIS metadata."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def analyze(self, domain_name: str) -> DomainRegistrationFeatures:
        """Query RDAP / WHOIS for domain registration metadata.

        Safe Multi-Tier Query Flow:
        1. Validate domain input string.
        2. Primary Tier: Query public RESTful RDAP gateway (standard JSON).
        3. Secondary Tier: Fallback to socket WHOIS query if RDAP failed.
        4. Fallback: If both fail or time out, return an 'unavailable' status
           with is_data_available=False without assigning any risk penalty.
        """
        clean_domain = domain_name.strip().lower()
        if not clean_domain:
            return self._unavailable_result(clean_domain)

        # 1. Primary: Query public RDAP service (standardized JSON REST endpoint)
        rdap_result = await self._query_rdap(clean_domain)
        if rdap_result.is_data_available:
            return rdap_result

        # 2. Secondary fallback: Query python-whois if available
        if _HAS_PYTHON_WHOIS:
            whois_result = self._query_whois(clean_domain)
            if whois_result.is_data_available:
                return whois_result

        # Return unavailable structure without penalty (triggers dynamic renormalization)
        return self._unavailable_result(clean_domain)

    async def _query_rdap(self, domain: str) -> DomainRegistrationFeatures:
        """Query public RDAP service for domain registration data."""
        url = f"{self.settings.rdap_base_url.rstrip('/')}/{domain}"
        headers = {
            "Accept": "application/rdap+json, application/json",
            "User-Agent": "ScamTrace-DomainIntelligence/1.0",
        }

        try:
            async with httpx.AsyncClient(timeout=self.settings.rdap_timeout_seconds) as client:
                response = await client.get(url, headers=headers, follow_redirects=True)
                if response.status_code != 200:
                    logger.debug("RDAP lookup for %s returned status %d", domain, response.status_code)
                    return self._unavailable_result(domain)

                data = response.json()
                return self._parse_rdap_payload(domain, data)
        except Exception as exc:
            logger.debug("RDAP query failed for %s: %s", domain, exc)
            return self._unavailable_result(domain)

    def _parse_rdap_payload(self, domain: str, data: Dict[str, Any]) -> DomainRegistrationFeatures:
        """Parse structured RDAP JSON payload into DomainRegistrationFeatures."""
        creation_str: Optional[str] = None
        expiration_str: Optional[str] = None
        updated_str: Optional[str] = None

        # Extract timestamps from events array
        events = data.get("events", [])
        for event in events:
            action = event.get("eventAction", "").lower()
            date_val = event.get("eventDate", "")
            if action in ("registration", "created"):
                creation_str = date_val
            elif action in ("expiration", "registrar expiration"):
                expiration_str = date_val
            elif action in ("last changed", "last update"):
                updated_str = date_val

        # Extract registrar name and privacy status from entities
        registrar: Optional[str] = None
        registrant_country: Optional[str] = None
        privacy_protected = False

        entities = data.get("entities", [])
        for entity in entities:
            roles = [r.lower() for r in entity.get("roles", [])]
            vcard_array = entity.get("vcardArray", [])
            fn_name = ""

            if len(vcard_array) >= 2 and isinstance(vcard_array[1], list):
                for item in vcard_array[1]:
                    if isinstance(item, list) and len(item) >= 4:
                        if item[0] == "fn":
                            fn_name = str(item[3])
                        elif item[0] == "adr" and isinstance(item[3], list) and len(item[3]) >= 7:
                            registrant_country = str(item[3][6])

            if "registrar" in roles:
                registrar = fn_name or entity.get("handle")

            # Check for privacy indicators
            combined_entity_str = (fn_name + " " + str(entity.get("handle", ""))).lower()
            if any(p in combined_entity_str for p in PRIVACY_INDICATORS):
                privacy_protected = True

        # Check DNSSEC status
        secure_dns = data.get("secureDNS", {})
        dnssec_enabled = bool(secure_dns.get("delegationSigned", False))

        # Compute age and expiration delta
        now = datetime.now(timezone.utc)
        age_days: Optional[int] = None
        days_until_expiration: Optional[int] = None

        if creation_str:
            created_dt = parse_iso_datetime(creation_str)
            if created_dt:
                age_days = max(0, (now - created_dt).days)

        if expiration_str:
            exp_dt = parse_iso_datetime(expiration_str)
            if exp_dt:
                days_until_expiration = (exp_dt - now).days

        is_nrd = age_days is not None and age_days <= self.settings.nrd_threshold_days
        is_young = age_days is not None and age_days <= self.settings.nrd_warning_threshold_days

        return DomainRegistrationFeatures(
            domain_name=domain,
            creation_date=creation_str,
            expiration_date=expiration_str,
            updated_date=updated_str,
            age_days=age_days,
            days_until_expiration=days_until_expiration,
            registrar=registrar,
            registrant_country=registrant_country,
            dnssec_enabled=dnssec_enabled,
            is_nrd=is_nrd,
            is_young_domain=is_young,
            privacy_protected=privacy_protected,
            data_source="rdap",
            is_data_available=bool(creation_str or registrar),
        )

    def _query_whois(self, domain: str) -> DomainRegistrationFeatures:
        """Fallback query using python-whois library."""
        try:
            w = whois.whois(domain)
            if not w or not w.domain_name:
                return self._unavailable_result(domain)

            # Dates can be a datetime or list of datetimes
            creation_val = w.creation_date
            if isinstance(creation_val, list) and creation_val:
                creation_val = creation_val[0]

            expiration_val = w.expiration_date
            if isinstance(expiration_val, list) and expiration_val:
                expiration_val = expiration_val[0]

            updated_val = w.updated_date
            if isinstance(updated_val, list) and updated_val:
                updated_val = updated_val[0]

            now = datetime.now(timezone.utc)
            age_days: Optional[int] = None
            days_until_expiration: Optional[int] = None

            if isinstance(creation_val, datetime):
                c_dt = creation_val.replace(tzinfo=timezone.utc) if creation_val.tzinfo is None else creation_val
                age_days = max(0, (now - c_dt).days)
                creation_str = c_dt.isoformat()
            else:
                creation_str = str(creation_val) if creation_val else None

            if isinstance(expiration_val, datetime):
                e_dt = expiration_val.replace(tzinfo=timezone.utc) if expiration_val.tzinfo is None else expiration_val
                days_until_expiration = (e_dt - now).days
                expiration_str = e_dt.isoformat()
            else:
                expiration_str = str(expiration_val) if expiration_val else None

            updated_str = updated_val.isoformat() if isinstance(updated_val, datetime) else None

            registrar = str(w.registrar) if w.registrar else None
            country = str(w.country) if getattr(w, "country", None) else None

            combined_str = f"{registrar or ''} {w.org or ''} {w.name or ''}".lower()
            privacy_protected = any(p in combined_str for p in PRIVACY_INDICATORS)

            is_nrd = age_days is not None and age_days <= self.settings.nrd_threshold_days
            is_young = age_days is not None and age_days <= self.settings.nrd_warning_threshold_days

            return DomainRegistrationFeatures(
                domain_name=domain,
                creation_date=creation_str,
                expiration_date=expiration_str,
                updated_date=updated_str,
                age_days=age_days,
                days_until_expiration=days_until_expiration,
                registrar=registrar,
                registrant_country=country,
                dnssec_enabled=False,
                is_nrd=is_nrd,
                is_young_domain=is_young,
                privacy_protected=privacy_protected,
                data_source="whois",
                is_data_available=bool(creation_str or registrar),
            )
        except Exception as exc:
            logger.debug("python-whois lookup failed for %s: %s", domain, exc)
            return self._unavailable_result(domain)

    def _unavailable_result(self, domain: str) -> DomainRegistrationFeatures:
        """Return structured model when registration data is unavailable or rate-limited."""
        return DomainRegistrationFeatures(
            domain_name=domain,
            creation_date=None,
            expiration_date=None,
            updated_date=None,
            age_days=None,
            days_until_expiration=None,
            registrar=None,
            registrant_country=None,
            dnssec_enabled=False,
            is_nrd=False,
            is_young_domain=False,
            privacy_protected=False,
            data_source="unavailable",
            is_data_available=False,
        )
