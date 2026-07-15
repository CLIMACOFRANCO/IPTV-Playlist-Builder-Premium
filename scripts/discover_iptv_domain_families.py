#!/usr/bin/env python
"""
Independent DOMAIN FAMILY DISCOVERY runner.

This script is intentionally separate from run_top50_tavily_due_diligence.py.
It supports a fully offline dry-run and a protected future execution mode.

Identifier policy:
- query_id: stable ID from the design document.
- result_id: sha256(query_id + canonical_url + normalized_title).
- domain_id: normalized hostname.
- relationship_id: sha256(source_domain + relationship_type + target_domain + source_url).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
import tempfile
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
DEFAULT_DESIGN_PATH = PROJECT_ROOT / "research" / "output" / "best_iptv_2026" / "domain_family_discovery_voco_micro_pilot" / "DESIGN_voco_domain_family_discovery_micro_pilot_20260714.md"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "research" / "output" / "best_iptv_2026" / "domain_family_discovery_voco_micro_pilot"

LOGIC_VERSION = "domain_family_discovery_voco_v1.1"
CHECKPOINT_SCHEMA_VERSION = "domain_family_checkpoint_v1"
ALLOWED_MAX_RESULTS = 8
RECOMMENDED_DISCOVERY_QUERIES = 8
RECOMMENDED_CONTROL_QUERIES = 2
RECOMMENDED_TOTAL_QUERIES = 10
ABSOLUTE_MAX_QUERIES = 12

DEFAULT_BRAND = "Voco TV"
DEFAULT_ALIASES = ["Voco TV", "VocoTV", "Voco IPTV", "VocoTV IPTV", "Voco TV IPTV"]
BASELINE_DOMAINS = [
    "vocotv.org",
    "vocotvusa.net",
    "vocotviptv.com",
    "vocotvs.com",
    "vocotvpro.com",
    "voco-iptv.com",
    "vocotv.ca",
    "iptvon.me",
]

GENERAL_HARD_NEGATIVES = [
    "IHG",
    "InterContinental Hotels Group",
    "voco.dental",
    "careers",
    "hotel-online",
    "dental",
    "dentist",
    "dentistry",
    "odontologia",
]
CONTEXTUAL_SOFT_NEGATIVES = ["hotel", "hotels", "hospitality", "lodging", "resort"]
TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "gbraid",
    "wbraid",
    "mc_cid",
    "mc_eid",
    "igshid",
    "msclkid",
    "ref",
    "ref_src",
}

NETWORK_CALLS = 0
TAVILY_CLIENT_INSTANTIATIONS = 0
CREDENTIAL_READS = 0
TAVILY_SEARCH_CALLS = 0


@dataclass(frozen=True)
class QuerySpec:
    query_id: str
    query_type: str
    phase: str
    category: str
    exact_query: str
    positive_terms: list[str]
    hard_negative_terms: list[str]
    soft_negative_terms: list[str]
    post_retrieval_noise_signals: list[str]
    purpose: str
    gap_tested: str
    success_signal: str
    expected_noise: str
    execution_order: int
    included_in_discovery_metrics: bool

    def query_hash(self, search_depth: str, max_results: int, include_raw_content: bool, include_answer: bool) -> str:
        payload = {
            "query_id": self.query_id,
            "query_type": self.query_type,
            "phase": self.phase,
            "category": self.category,
            "exact_query": self.exact_query,
            "positive_terms": self.positive_terms,
            "hard_negative_terms": self.hard_negative_terms,
            "soft_negative_terms": self.soft_negative_terms,
            "post_retrieval_noise_signals": self.post_retrieval_noise_signals,
            "included_in_discovery_metrics": self.included_in_discovery_metrics,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_raw_content": include_raw_content,
            "include_answer": include_answer,
        }
        return stable_hash(payload)


@dataclass
class Observation:
    value: Any
    observation_type: str
    source_field: str
    source_text_excerpt: str | None = None


@dataclass
class NormalizedResult:
    run_id: str
    query_id: str
    query_type: str
    phase: str
    category: str
    query_text: str
    brand_name: str
    result_position: int
    original_url: str
    canonical_url: str
    hostname: str
    canonical_hostname: str
    registrable_domain: str | None
    subdomain: str | None
    title: str
    content: str
    raw_content: str
    tavily_score: float | None
    result_id: str
    directly_observed_fields: dict[str, Any] = field(default_factory=dict)
    extracted_fields: dict[str, Any] = field(default_factory=dict)
    inferred_fields: dict[str, Any] = field(default_factory=dict)
    unavailable_fields: dict[str, Any] = field(default_factory=dict)
    role_candidates: list[dict[str, Any]] = field(default_factory=list)
    ambiguous_text_only: list[dict[str, Any]] = field(default_factory=list)
    duplicate_key: str | None = None
    is_duplicate: bool = False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def local_run_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: Any) -> None:
    write_json_atomic(path, data)


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=True, indent=2, sort_keys=False)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", delete=False, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp") as handle:
            tmp_path = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=True, sort_keys=False) + "\n")


def read_jsonl_checked(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    if not path.exists():
        return rows, issues
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            issue = {"line_number": index, "error": str(exc), "is_final_line": index == len(lines)}
            issues.append(issue)
            if index != len(lines):
                raise ValueError(f"JSONL corruption before final line in {path}: line {index}") from exc
    return rows, issues


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field_name: serialize_cell(row.get(field_name)) for field_name in fields})


def serialize_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    return str(value)


def normalize_title(title: str | None) -> str:
    return re.sub(r"\s+", " ", (title or "").strip().lower())


def normalize_search_text(text: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = re.sub(r"[\u2010-\u2015_]+", "-", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def looks_like_hostname(hostname: str) -> bool:
    if not hostname or " " in hostname or "." not in hostname:
        return False
    labels = hostname.strip(".").split(".")
    if len(labels) < 2:
        return False
    label_re = re.compile(r"^(?:xn--)?[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)
    return all(label_re.match(label) for label in labels)


def canonicalize_url(url: str | None) -> dict[str, Any]:
    """Canonicalize a URL without collapsing distinct Voco family domains."""
    original_url = (url or "").strip()
    if not original_url:
        return {
            "original_url": original_url,
            "canonical_url": None,
            "hostname": None,
            "canonical_hostname": None,
            "registrable_domain": None,
            "subdomain": None,
            "validation_error": "missing_url",
        }
    candidate = original_url if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", original_url) else f"https://{original_url}"
    parsed = urlparse(candidate)
    scheme = (parsed.scheme or "https").lower()
    hostname = (parsed.hostname or "").lower().strip(".")
    if scheme not in {"http", "https"} or not looks_like_hostname(hostname):
        return {
            "original_url": original_url,
            "canonical_url": None,
            "hostname": hostname or None,
            "canonical_hostname": None,
            "registrable_domain": None,
            "subdomain": None,
            "validation_error": "invalid_url_or_hostname",
        }
    canonical_hostname = hostname[4:] if hostname.startswith("www.") else hostname
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{canonical_hostname}{port}"
    path = re.sub(r"/+", "/", parsed.path or "/")
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    filtered_query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered in TRACKING_QUERY_KEYS or any(lowered.startswith(prefix) for prefix in TRACKING_QUERY_PREFIXES):
            continue
        filtered_query.append((key, value))
    query = urlencode(filtered_query, doseq=True)
    canonical_url = urlunparse((scheme, netloc, path, "", query, ""))
    registrable_domain, subdomain = split_domain(canonical_hostname)
    return {
        "original_url": original_url,
        "canonical_url": canonical_url,
        "hostname": hostname,
        "canonical_hostname": canonical_hostname,
        "registrable_domain": registrable_domain,
        "subdomain": subdomain,
        "validation_error": None,
    }


def split_domain(hostname: str) -> tuple[str | None, str | None]:
    if not hostname:
        return None, None
    parts = hostname.split(".")
    if len(parts) <= 2:
        return hostname, None
    two_level_suffixes = {"co.uk", "com.au", "com.br", "com.mx", "co.in", "com.ar", "com.co"}
    suffix = ".".join(parts[-2:])
    if suffix in two_level_suffixes and len(parts) >= 3:
        registrable = ".".join(parts[-3:])
        subdomain = ".".join(parts[:-3]) or None
        return registrable, subdomain
    registrable = ".".join(parts[-2:])
    subdomain = ".".join(parts[:-2]) or None
    return registrable, subdomain


def build_result_id(query_id: str, canonical_url: str | None, title: str | None) -> str:
    return hashlib.sha256(f"{query_id}|{canonical_url or ''}|{normalize_title(title)}".encode("utf-8")).hexdigest()


def build_relationship_id(source_domain: str, relationship_type: str, target_domain: str, source_url: str) -> str:
    return hashlib.sha256(f"{source_domain}|{relationship_type}|{target_domain}|{source_url}".encode("utf-8")).hexdigest()


def extract_excerpt(text: str, value: str, window: int = 80) -> str:
    idx = text.lower().find(value.lower())
    if idx < 0:
        return text[: window * 2].strip()
    start = max(0, idx - window)
    end = min(len(text), idx + len(value) + window)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def observation(value: Any, observation_type: str, source_field: str, source_text: str | None = None) -> dict[str, Any]:
    excerpt = None
    if isinstance(value, str) and source_text:
        excerpt = extract_excerpt(source_text, value)
    return asdict(Observation(value=value, observation_type=observation_type, source_field=source_field, source_text_excerpt=excerpt))


def extract_urls(text: str) -> list[str]:
    pattern = re.compile(r"https?://[^\s\"'<>),]+|(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s\"'<>),]*)?")
    values = []
    for match in pattern.findall(text or ""):
        value = match.rstrip(".,;:")
        if "." in value and value not in values:
            values.append(value)
    return values


def is_structured_link(value: str) -> bool:
    return bool(re.match(r"^https?://", value or "", re.IGNORECASE) or re.match(r"^www\.", value or "", re.IGNORECASE))


def term_matches(text: str, term: str) -> bool:
    haystack = normalize_search_text(text)
    needle = normalize_search_text(term)
    if not needle:
        return False
    if "." in needle:
        return needle in haystack
    if " " in needle:
        return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", haystack) is not None
    if "-" in needle:
        flexible = re.escape(needle).replace(r"\-", r"[-\s]")
        return re.search(rf"(?<![a-z0-9]){flexible}(?![a-z0-9])", haystack) is not None
    return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", haystack) is not None


def extract_emails(text: str) -> list[str]:
    emails = re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text or "")
    return sorted({email.lower() for email in emails})


def extract_phones(text: str) -> list[str]:
    pattern = re.compile(r"(?:(?:\+|00)\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,5}\d{2,4}")
    phones = []
    for match in pattern.findall(text or ""):
        digits = re.sub(r"\D", "", match)
        if 7 <= len(digits) <= 16:
            cleaned = re.sub(r"\s+", " ", match).strip()
            if cleaned not in phones:
                phones.append(cleaned)
    return phones


def contains_any(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term_matches(text, term)]


def extract_counts(text: str) -> list[str]:
    pattern = re.compile(r"\b\d{2,6}\s*(?:channels?|live channels?|vod|movies?|series)\b", re.IGNORECASE)
    return sorted({re.sub(r"\s+", " ", match.strip()) for match in pattern.findall(text or "")})


def extract_prices(text: str) -> list[str]:
    pattern = re.compile(r"(?:USD|US\$|\$|EUR|€|GBP|£)\s?\d+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?\s?(?:USD|EUR|GBP)", re.IGNORECASE)
    return sorted({match.strip() for match in pattern.findall(text or "")})


def normalize_tavily_result(
    run_id: str,
    query: QuerySpec,
    brand_name: str,
    result: dict[str, Any],
    result_position: int,
) -> NormalizedResult:
    title = result.get("title") or ""
    url = result.get("url") or ""
    content = result.get("content") or ""
    raw_content = result.get("raw_content") or ""
    score = result.get("score")
    canonical = canonicalize_url(url)
    result_id = build_result_id(query.query_id, canonical["canonical_url"], title)
    text_blob = "\n".join([title, url, content, raw_content])
    extracted = extract_observable_fields(text_blob, canonical)
    roles = infer_role_candidates(query, canonical, text_blob, extracted)
    ambiguous = detect_ambiguous_text_only(query, canonical, text_blob, extracted)
    return NormalizedResult(
        run_id=run_id,
        query_id=query.query_id,
        query_type=query.query_type,
        phase=query.phase,
        category=query.category,
        query_text=query.exact_query,
        brand_name=brand_name,
        result_position=result_position,
        original_url=canonical["original_url"],
        canonical_url=canonical["canonical_url"],
        hostname=canonical["hostname"],
        canonical_hostname=canonical["canonical_hostname"],
        registrable_domain=canonical["registrable_domain"],
        subdomain=canonical["subdomain"],
        title=title,
        content=content,
        raw_content=raw_content,
        tavily_score=score if isinstance(score, (int, float)) else None,
        result_id=result_id,
        directly_observed_fields={
            "url": observation(url, "DIRECTLY_OBSERVED", "url", url),
            "hostname": observation(canonical["canonical_hostname"], "DIRECTLY_OBSERVED", "url", url),
            "title": observation(title, "DIRECTLY_OBSERVED", "title", title),
            "content_available": observation(bool(content), "DIRECTLY_OBSERVED", "content"),
            "raw_content_available": observation(bool(raw_content), "DIRECTLY_OBSERVED", "raw_content"),
            "url_validation_error": observation(canonical.get("validation_error"), "DIRECTLY_OBSERVED", "url", url),
        },
        extracted_fields=extracted,
        inferred_fields={"role_candidates": observation(roles, "INFERRED", "deterministic_rules")},
        unavailable_fields={"redirect_target": observation("UNAVAILABLE", "UNAVAILABLE", "tavily_result")},
        role_candidates=roles,
        ambiguous_text_only=ambiguous,
        duplicate_key=stable_hash({"url": canonical["canonical_url"], "title": normalize_title(title)}),
    )


def extract_observable_fields(text_blob: str, canonical: dict[str, Any]) -> dict[str, Any]:
    urls = extract_urls(text_blob)
    linked_domains = []
    for value in urls:
        if not is_structured_link(value):
            continue
        c = canonicalize_url(value)
        domain = c["canonical_hostname"]
        if domain and domain != canonical.get("canonical_hostname") and domain not in linked_domains:
            linked_domains.append(domain)
    emails = extract_emails(text_blob)
    email_domains = sorted({email.split("@", 1)[1] for email in emails})
    phones = extract_phones(text_blob)
    whatsapp_terms = contains_any(text_blob, ["WhatsApp", "wa.me", "api.whatsapp.com"])
    support_terms = contains_any(text_blob, ["support", "help center", "customer service", "ticket"])
    contact_terms = contains_any(text_blob, ["contact", "email", "phone", "WhatsApp"])
    checkout_terms = contains_any(text_blob, ["checkout", "cart", "order", "billing", "invoice"])
    payment_terms = contains_any(text_blob, ["payment", "PayPal", "credit card", "crypto", "bitcoin", "USDT", "stripe"])
    login_terms = contains_any(text_blob, ["login", "activation", "activate", "portal"])
    app_terms = contains_any(text_blob, ["app", "APK", "Android", "iOS", "Smart TV", "download", "downloader"])
    reseller_terms = contains_any(text_blob, ["reseller", "reseller panel", "sub-reseller", "wholesale", "dealer", "credits"])
    affiliate_terms = contains_any(text_blob, ["affiliate", "best iptv", "top iptv", "review", "coupon", "promo"])
    official_terms = contains_any(text_blob, ["official", "official website", "official site"])
    ihg_hotel_signals = contains_any(text_blob, ["IHG", "InterContinental Hotels Group", "hotel", "hotels", "hospitality", "lodging", "resort"])
    dental_signals = contains_any(text_blob, ["voco.dental", "dental", "dentist", "dentistry", "odontologia"])
    legal_entity_indicators = contains_any(text_blob, ["legal entity", "operated by", "owned by", "company registration", "business address", "billing entity", "copyright holder", "LLC", "Ltd", "Inc"])
    address_indicators = extract_addresses(text_blob)
    prices = extract_prices(text_blob)
    product_counts = extract_counts(text_blob)
    return {
        "emails": observation(emails, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob),
        "email_domains": observation(email_domains, "EXTRACTED_FROM_CONTENT", "emails", text_blob),
        "phones": observation(phones, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob),
        "whatsapp_terms": observation(whatsapp_terms, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob),
        "urls": observation(urls, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob),
        "linked_domains": observation(linked_domains, "EXTRACTED_FROM_CONTENT", "urls", text_blob),
        "support_terms": observation(support_terms, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob),
        "contact_terms": observation(contact_terms, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob),
        "checkout_terms": observation(checkout_terms, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob),
        "payment_terms": observation(payment_terms, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob),
        "login_activation_terms": observation(login_terms, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob),
        "app_download_terms": observation(app_terms, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob),
        "reseller_terms": observation(reseller_terms, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob),
        "affiliate_promotional_terms": observation(affiliate_terms, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob),
        "self_declared_official": observation(official_terms, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob),
        "ihg_hotel_signals": observation(ihg_hotel_signals, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob),
        "dental_signals": observation(dental_signals, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob),
        "legal_entity_indicators": observation(legal_entity_indicators, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob),
        "addresses": observation(address_indicators, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob),
        "prices": observation(prices, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob),
        "product_counts": observation(product_counts, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob),
    }


def extract_addresses(text: str) -> list[str]:
    # Conservative, explicit-only address snippets. These are not identity proof.
    pattern = re.compile(
        r"\b\d{1,6}\s+[A-Za-z0-9 .'-]{3,80}\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Suite|Unit)\b[^.\n]{0,80}",
        re.IGNORECASE,
    )
    return sorted({re.sub(r"\s+", " ", match.strip()) for match in pattern.findall(text or "")})


def infer_role_candidates(
    query: QuerySpec,
    canonical: dict[str, Any],
    text_blob: str,
    extracted: dict[str, Any],
) -> list[dict[str, Any]]:
    """Assign descriptive role candidates only; these never confirm officiality."""
    roles: list[dict[str, Any]] = []
    lower_text = normalize_search_text(text_blob)
    domain = canonical.get("canonical_hostname") or ""
    signals: list[str] = []
    brand_signal = any(term_matches(text_blob, alias) for alias in DEFAULT_ALIASES)
    iptv_signal = term_matches(text_blob, "iptv") or term_matches(text_blob, "streaming")
    promotional_source = bool(extracted["affiliate_promotional_terms"]["value"])
    explicit_reseller_terms = contains_any(
        text_blob,
        ["reseller panel", "become a reseller", "reseller credits", "sub-reseller", "wholesale IPTV"],
    )
    reseller_terms = extracted["reseller_terms"]["value"]
    infrastructure_signals = []
    email_domains = extracted["email_domains"]["value"] or []
    if domain and domain in email_domains:
        infrastructure_signals.append("same_domain_email")
    if extracted["checkout_terms"]["value"] or extracted["payment_terms"]["value"]:
        infrastructure_signals.append("checkout_or_payment")
    if extracted["login_activation_terms"]["value"]:
        infrastructure_signals.append("login_or_activation")
    if extracted["app_download_terms"]["value"]:
        infrastructure_signals.append("app_or_download")
    if extracted["legal_entity_indicators"]["value"]:
        infrastructure_signals.append("legal_or_corporate_indicator")
    if extracted["support_terms"]["value"] and (domain and any(domain in value for value in (extracted["urls"]["value"] or []))):
        infrastructure_signals.append("support_on_same_domain")
    nominal_domain = bool(domain and any(token in domain for token in ("voco", "iptv")))
    confirmed_reseller = bool(explicit_reseller_terms and not promotional_source)
    possible_reseller = bool(reseller_terms and not confirmed_reseller)
    if possible_reseller:
        roles.append(role("POSSIBLE_RESELLER", "MEDIUM", "reseller terminology observed", extracted["reseller_terms"]))
    if confirmed_reseller:
        roles.append(role("CONFIRMED_RESELLER", "HIGH", "explicit attributable reseller terminology observed", observation(explicit_reseller_terms, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob)))
    if extracted["affiliate_promotional_terms"]["value"]:
        roles.append(role("REVIEW_OR_RANKING_SOURCE", "MEDIUM", "affiliate/promotional or ranking terminology observed", extracted["affiliate_promotional_terms"]))
    if extracted["checkout_terms"]["value"] or extracted["payment_terms"]["value"]:
        roles.append(role("CHECKOUT_OR_PAYMENT_DOMAIN", "LOW", "checkout/payment terminology observed", extracted["checkout_terms"]))
    if extracted["support_terms"]["value"] or extracted["contact_terms"]["value"]:
        roles.append(role("SUPPORT_PORTAL", "LOW", "support/contact terminology observed", extracted["support_terms"]))
    if extracted["app_download_terms"]["value"] or extracted["login_activation_terms"]["value"]:
        roles.append(role("APP_OR_DOWNLOAD_DOMAIN", "LOW", "app/download/login terminology observed", extracted["app_download_terms"]))
    if brand_signal and iptv_signal and not extracted["ihg_hotel_signals"]["value"] and not extracted["dental_signals"]["value"]:
        signals.extend(["brand_alias", "iptv_context"])
        if nominal_domain:
            signals.append("domain_name_context")
        signals.extend(infrastructure_signals)
        if confirmed_reseller and infrastructure_signals:
            roles.append(role("POSSIBLE_MASTER_DISTRIBUTOR", "MEDIUM", "reseller program plus infrastructure signals; not officiality", observation(signals, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob)))
        elif not confirmed_reseller and not promotional_source and nominal_domain and len(infrastructure_signals) >= 1:
            roles.append(role("POSSIBLE_BRAND_OPERATOR", "MEDIUM", "nominal domain plus attributable brand/IPTV and infrastructure signals; not officiality", observation(signals, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob)))
    if extracted["ihg_hotel_signals"]["value"] or extracted["dental_signals"]["value"]:
        roles.append(role("HOMONYM_OR_IRRELEVANT", "HIGH", "hotel/IHG/dental noise signal observed", observation(extracted["ihg_hotel_signals"]["value"] + extracted["dental_signals"]["value"], "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob)))
    if query.category == "comercial" and brand_signal and iptv_signal:
        roles.append(role("COMMERCIAL_PORTAL", "LOW", "commercial query plus brand/IPTV context", observation(query.query_id, "INFERRED", "query_context")))
    if not roles:
        roles.append(role("UNKNOWN_ROLE", "UNRESOLVED", "insufficient deterministic signals", observation("UNAVAILABLE", "UNAVAILABLE", "role_rules")))
    return prioritize_roles(dedupe_roles(roles))


def role(role_candidate: str, confidence: str, reason: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "role_candidate": role_candidate,
        "role_confidence": confidence,
        "reason": reason,
        "evidence": evidence,
        "officiality_confirmed": False,
    }


def dedupe_roles(roles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    output = []
    for item in roles:
        key = (item["role_candidate"], item["reason"])
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def prioritize_roles(roles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = [
        "HOMONYM_OR_IRRELEVANT",
        "CONFIRMED_RESELLER",
        "POSSIBLE_MASTER_DISTRIBUTOR",
        "POSSIBLE_BRAND_OPERATOR",
        "POSSIBLE_RESELLER",
        "CHECKOUT_OR_PAYMENT_DOMAIN",
        "SUPPORT_PORTAL",
        "APP_OR_DOWNLOAD_DOMAIN",
        "COMMERCIAL_PORTAL",
        "REVIEW_OR_RANKING_SOURCE",
        "SOCIAL_OR_COMMUNITY_SOURCE",
        "UNKNOWN_ROLE",
    ]
    ordered = sorted(roles, key=lambda item: priority.index(item["role_candidate"]) if item["role_candidate"] in priority else len(priority))
    for index, item in enumerate(ordered):
        item["primary_role_candidate"] = index == 0
    return ordered


def detect_ambiguous_text_only(
    query: QuerySpec,
    canonical: dict[str, Any],
    text_blob: str,
    extracted: dict[str, Any],
) -> list[dict[str, Any]]:
    """Record domains that appear only in unstructured text and not as structured domains."""
    structured_domains = set(extracted["linked_domains"]["value"] or [])
    structured_domains.add(canonical.get("canonical_hostname") or "")
    ambiguous = []
    for value in extract_urls(text_blob):
        domain = canonicalize_url(value)["canonical_hostname"]
        if not domain or domain in structured_domains:
            continue
        if is_structured_link(value):
            continue
        ambiguous.append(
            {
                "state": "AMBIGUOUS_TEXT_ONLY",
                "domain": domain,
                "query_id": query.query_id,
                "source_url": canonical.get("canonical_url"),
                "field": "content/raw_content/title",
                "observed_text": extract_excerpt(text_blob, value),
                "counts_as_spontaneous_recovery": False,
                "counts_as_candidate_domain": False,
                "counts_as_linked_discovery": False,
                "counts_as_family_expansion": False,
            }
        )
    return ambiguous


def build_query_plan() -> list[QuerySpec]:
    hard_general = GENERAL_HARD_NEGATIVES
    soft_context = CONTEXTUAL_SOFT_NEGATIVES
    return [
        QuerySpec(
            "voco_df_01_identity_variants",
            "discovery",
            "A",
            "identidad_variantes",
            '(\"Voco TV\" OR VocoTV OR \"Voco IPTV\" OR \"VocoTV IPTV\" OR \"Voco TV IPTV\") (IPTV OR streaming) (domain OR website OR \"official site\" OR \"official website\" OR portal OR platform OR \"new domain\" OR \"alternative domain\" OR regional OR USA OR Canada) -IHG -\"InterContinental Hotels Group\" -\"voco.dental\" -careers -\"hotel-online\" -dental -dentist -dentistry -odontologia -hotel -hotels -hospitality -lodging -resort',
            ["marca", "IPTV", "domain", "website", "official site", "portal", "platform", "regional"],
            hard_general + soft_context,
            [],
            ["official-only sin corroboracion", "ranking SEO"],
            "descubrir dominios/variantes nominales sin mencionar vocotv.ai",
            "H1a, H1b",
            "dominio Voco nuevo o conocido con URL principal no hotel/dental",
            "rankings SEO, self-declared official",
            1,
            True,
        ),
        QuerySpec(
            "voco_df_02_commercial_sales",
            "discovery",
            "A",
            "comercial",
            '(\"Voco TV\" OR VocoTV OR \"Voco IPTV\" OR \"VocoTV IPTV\") IPTV (subscription OR pricing OR plans OR trial OR buy OR \"service package\" OR \"IPTV package\") -IHG -\"InterContinental Hotels Group\" -\"voco.dental\" -careers -\"hotel-online\" -dental -dentist -dentistry -odontologia',
            ["subscription", "pricing", "plans", "trial", "buy", "package"],
            hard_general,
            soft_context,
            ["reseller", "affiliate", "generic pricing", "copied SEO"],
            "buscar portales de venta y ofertas comerciales",
            "H1b",
            "portal comercial con dominio y contenido Voco IPTV",
            "revendedores, afiliados, pricing copiado",
            2,
            True,
        ),
        QuerySpec(
            "voco_df_03_contact_support",
            "discovery",
            "B",
            "contacto_soporte",
            '(\"Voco TV\" OR VocoTV OR \"Voco IPTV\" OR \"VocoTV IPTV\") IPTV (contact OR support OR email OR WhatsApp OR \"customer service\" OR \"help center\" OR \"support portal\") -IHG -\"InterContinental Hotels Group\" -\"voco.dental\" -careers -\"hotel-online\" -dental -dentist -dentistry -odontologia',
            ["contact", "support", "email", "WhatsApp", "customer service", "help center"],
            hard_general,
            soft_context,
            ["soporte hotelero", "contacto dental", "directorios"],
            "encontrar contacto, soporte y dominios de ayuda",
            "H1b, V3 utility",
            "email/support domain directamente observado",
            "directorios, soporte no relacionado",
            3,
            True,
        ),
        QuerySpec(
            "voco_df_04_apps_login",
            "discovery",
            "B",
            "apps_login",
            '(\"Voco TV\" OR VocoTV OR \"Voco IPTV\" OR \"VocoTV IPTV\") IPTV (app OR APK OR Android OR iOS OR \"Smart TV\" OR downloader OR login OR player) -IHG -\"InterContinental Hotels Group\" -\"voco.dental\" -careers -dental -dentist -dentistry -odontologia',
            ["app", "APK", "Android", "iOS", "Smart TV", "downloader", "login", "player"],
            ["IHG", "InterContinental Hotels Group", "voco.dental", "careers", "dental", "dentist", "dentistry", "odontologia"],
            soft_context,
            ["IHG apps", "unrelated apps", "generic player"],
            "buscar apps, login y descargas relacionadas",
            "H1b, V3 utility",
            "app/download/login domain trazable",
            "apps IHG, players genericos",
            4,
            True,
        ),
        QuerySpec(
            "voco_df_05_checkout_payment_infra",
            "discovery",
            "B",
            "checkout_pago_infra",
            '(\"Voco TV\" OR VocoTV OR \"Voco IPTV\" OR \"VocoTV IPTV\") IPTV (checkout OR payment OR billing OR \"login portal\" OR activation OR \"app download\" OR \"support portal\") -IHG -\"InterContinental Hotels Group\" -\"voco.dental\" -careers -dental -dentist -dentistry -odontologia',
            ["checkout", "payment", "billing", "login portal", "activation", "app download"],
            ["IHG", "InterContinental Hotels Group", "voco.dental", "careers", "dental", "dentist", "dentistry", "odontologia"],
            soft_context,
            ["pasarela externa sin relacion", "portal generico"],
            "buscar infraestructura y relaciones entre dominios",
            "H1b, V3 utility",
            "checkout/payment/login/support relation estructurada",
            "pasarelas externas, portales genericos",
            5,
            True,
        ),
        QuerySpec(
            "voco_df_06_cross_reference_known_domains",
            "discovery",
            "B",
            "cross_reference",
            '(\"vocotv.org\" OR \"vocotvusa.net\" OR \"vocotviptv.com\" OR \"voco-iptv.com\" OR \"vocotv.ca\") (\"Voco TV\" OR VocoTV OR IPTV) (link OR contact OR support OR login OR app OR checkout OR payment OR distributor OR regional) -IHG -\"InterContinental Hotels Group\" -\"voco.dental\" -careers -dental -dentist -dentistry -odontologia',
            ["dominios baseline", "link", "contact", "support", "app", "checkout", "distributor", "regional"],
            ["IHG", "InterContinental Hotels Group", "voco.dental", "careers", "dental", "dentist", "dentistry", "odontologia"],
            soft_context,
            ["loop SEO", "dominios conocidos sin relacion nueva"],
            "descubrir enlaces cruzados desde/hacia dominios ya conocidos",
            "H1b, V3 utility",
            "relacion nueva no presente en baseline",
            "loops SEO, dominios conocidos sin novedad",
            6,
            True,
        ),
        QuerySpec(
            "voco_df_07_reseller_distribution",
            "discovery",
            "C",
            "reseller_distribucion",
            '(\"Voco TV\" OR VocoTV OR \"Voco IPTV\" OR \"VocoTV IPTV\") IPTV (reseller OR \"reseller panel\" OR credits OR \"sub-reseller\" OR distributor OR wholesale OR dealer) -IHG -\"InterContinental Hotels Group\" -\"voco.dental\" -careers -\"hotel-online\" -dental -dentist -dentistry -odontologia',
            ["reseller", "panel", "credits", "distributor", "wholesale", "dealer"],
            hard_general,
            soft_context,
            ["reseller como rol descriptivo", "no oficialidad"],
            "mapear distribucion como rol descriptivo, no oficialidad",
            "V3 utility",
            "reseller/distributor clasificado como rol, no operador",
            "promocional, afiliados",
            7,
            True,
        ),
        QuerySpec(
            "voco_df_08_corporate_identity",
            "discovery",
            "C",
            "identidad_corporativa",
            '(\"Voco TV\" OR VocoTV OR \"Voco IPTV\" OR \"VocoTV IPTV\") IPTV (\"legal entity\" OR \"operated by\" OR \"owned by\" OR \"company registration\" OR \"business address\" OR \"support company\" OR \"billing entity\" OR \"copyright holder\") -IHG -\"InterContinental Hotels Group\" -\"voco.dental\" -careers -\"hotel-online\" -dental -dentist -dentistry -odontologia',
            ["legal entity", "operated by", "owned by", "company registration", "billing entity"],
            hard_general,
            soft_context,
            ["entidad hotelera", "entidad dental", "claims sin registro"],
            "buscar identidad verificable sin repetir terms/company de V2",
            "V3 utility",
            "identidad o entidad observada con URL y fuente",
            "claims sin registro, homonimos",
            8,
            True,
        ),
        QuerySpec(
            "voco_ctrl_01_known_vocotv_ai",
            "known-domain control",
            "control",
            "control_positivo",
            '(\"vocotv.ai\") (\"Voco TV\" OR VocoTV OR IPTV OR subscription OR app OR support) -IHG -\"InterContinental Hotels Group\" -\"voco.dental\" -careers -\"hotel-online\" -dental -dentist -dentistry -odontologia',
            ["vocotv.ai", "Voco TV", "IPTV", "subscription", "app", "support"],
            hard_general,
            soft_context,
            ["no aplica a discovery"],
            "probar indexabilidad cuando el dominio se conoce",
            "control tecnico",
            "confirma indexabilidad, no discovery espontaneo",
            "bajo",
            9,
            False,
        ),
        QuerySpec(
            "voco_ctrl_02_negative_noise",
            "negative-noise control",
            "control",
            "control_negativo",
            '(\"Voco TV\" OR VocoTV) (IHG OR \"InterContinental Hotels Group\" OR hotel OR hotels OR hospitality OR dental OR dentistry OR \"voco.dental\") IPTV',
            ["ruido esperado", "Voco TV", "IPTV"],
            [],
            [],
            ["IHG", "hotel", "hotels", "hospitality", "dental", "dentist", "dentistry", "voco.dental"],
            "forzar ruido para probar clasificacion y gates",
            "control de ruido",
            "resultados deben quedar como noise, no candidatos IPTV",
            "intencionalmente alto",
            10,
            False,
        ),
    ]


def validate_query_plan(plan: list[QuerySpec]) -> tuple[bool, list[dict[str, Any]]]:
    checks = []

    def add(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    ids = [q.query_id for q in plan]
    discovery = [q for q in plan if q.included_in_discovery_metrics]
    controls = [q for q in plan if not q.included_in_discovery_metrics]
    add("total_queries_is_10", len(plan) == 10, len(plan))
    add("discovery_queries_is_8", len(discovery) == 8, len(discovery))
    add("control_queries_is_2", len(controls) == 2, len(controls))
    add("query_ids_unique", len(set(ids)) == len(ids), ids)
    add("execution_order_1_to_10", [q.execution_order for q in plan] == list(range(1, 11)), [q.execution_order for q in plan])
    add("controls_excluded_from_discovery_metrics", all(not q.included_in_discovery_metrics for q in controls), [q.query_id for q in controls])
    add("required_controls_present", {"voco_ctrl_01_known_vocotv_ai", "voco_ctrl_02_negative_noise"}.issubset(set(ids)), ids)
    identity = next(q for q in plan if q.query_id == "voco_df_01_identity_variants")
    add("identity_query_uses_contextual_terms_as_hard", all(term in identity.hard_negative_terms for term in CONTEXTUAL_SOFT_NEGATIVES), identity.hard_negative_terms)
    non_identity_discovery = [q for q in discovery if q.query_id != "voco_df_01_identity_variants"]
    add(
        "contextual_terms_not_universal_hard_negatives",
        all(not set(CONTEXTUAL_SOFT_NEGATIVES).issubset(set(q.hard_negative_terms)) for q in non_identity_discovery),
        {q.query_id: q.hard_negative_terms for q in non_identity_discovery},
    )
    add("vocotv_ai_literal_only_in_control_or_cross_reference_absent", "vocotv.ai" not in " ".join(q.exact_query for q in discovery), None)
    add("no_execute_side_effects_in_validation", NETWORK_CALLS == 0 and TAVILY_CLIENT_INSTANTIATIONS == 0 and CREDENTIAL_READS == 0, {"network_calls": NETWORK_CALLS, "client_instantiations": TAVILY_CLIENT_INSTANTIATIONS, "credential_reads": CREDENTIAL_READS})
    return all(item["ok"] for item in checks), checks


def run_internal_self_tests(plan: list[QuerySpec]) -> tuple[bool, list[dict[str, Any]]]:
    tests = []

    def add(name: str, ok: bool, detail: Any = None) -> None:
        tests.append({"test": name, "ok": bool(ok), "detail": detail})

    class Args:
        brand = DEFAULT_BRAND
        search_depth = "advanced"
        max_results = 8
        timeout = 60.0
        execute = False
        confirm_credit_use = False
        resume_run_dir = None
        pause_seconds = 1.0
        max_retries = 3
        query_ids = None
        stop_after_phase = None

    c = canonicalize_url("HTTPS://www.VocoTV.org/path/?utm_source=x&plan=1#frag")
    add("canonicalization", c["canonical_url"] == "https://vocotv.org/path?plan=1" and c["canonical_hostname"] == "vocotv.org", c)
    invalid = canonicalize_url("not a url")
    add("invalid_url_not_candidate", invalid["canonical_url"] is None and invalid["validation_error"] is not None, invalid)
    rid1 = build_result_id("q1", "https://vocotv.org", " Voco TV ")
    rid2 = build_result_id("q1", "https://vocotv.org", "voco tv")
    add("stable_result_ids", rid1 == rid2 and len(rid1) == 64, rid1)
    metrics = calculate_metrics([], plan, BASELINE_DOMAINS)
    add("zero_denominator_metrics_are_null", metrics["relevant_domain_precision"] is None and metrics["duplicate_rate"] is None, metrics)
    add("max_results_limited", 1 <= Args.max_results <= ALLOWED_MAX_RESULTS and ALLOWED_MAX_RESULTS == 8, ALLOWED_MAX_RESULTS)

    control_query = next(q for q in plan if q.query_id == "voco_ctrl_01_known_vocotv_ai")
    discovery_query = next(q for q in plan if q.query_id == "voco_df_02_commercial_sales")
    synthetic_control = normalize_tavily_result("synthetic", control_query, DEFAULT_BRAND, {"url": "https://vocotv.ai", "title": "Voco TV", "content": "Voco TV IPTV support"}, 1)
    synthetic_discovery = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "https://example.com", "title": "Voco TV IPTV", "content": "Visit https://vocotv.ai support portal"}, 1)
    add("controls_excluded_from_spontaneous_recovery", calculate_metrics([synthetic_control], plan, BASELINE_DOMAINS)["spontaneous_vocotv_ai_recovery"] == "FALSE", None)
    add("spontaneous_recovery_true", calculate_metrics([synthetic_discovery], plan, BASELINE_DOMAINS)["spontaneous_vocotv_ai_recovery"] == "TRUE", asdict(synthetic_discovery))

    ambiguous_result = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "https://example.com", "title": "Voco TV IPTV", "content": "Plain text vocotv.ai appears with no link"}, 1)
    add("ambiguous_text_only_state", bool(ambiguous_result.ambiguous_text_only), ambiguous_result.ambiguous_text_only)
    linked_result = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "https://example.com", "title": "Voco TV IPTV", "content": "Link https://portal.vocotv.org/login"}, 1)
    add("linked_domain_extraction", "portal.vocotv.org" in linked_result.extracted_fields["linked_domains"]["value"], linked_result.extracted_fields["linked_domains"])

    hotel_context_query = next(q for q in plan if q.query_id == "voco_df_03_contact_support")
    add("hotel_contextual_not_universal_hard", "hotel" not in hotel_context_query.hard_negative_terms and "hotel" in hotel_context_query.soft_negative_terms, asdict(hotel_context_query))
    reseller_result = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "https://reseller.example", "title": "Voco TV IPTV reseller", "content": "reseller panel for Voco TV IPTV"}, 1)
    add("roles_do_not_confirm_officiality", all(not r["officiality_confirmed"] for r in reseller_result.role_candidates), reseller_result.role_candidates)
    add("confirmed_reseller_excludes_operator", "CONFIRMED_RESELLER" in [r["role_candidate"] for r in reseller_result.role_candidates] and "POSSIBLE_BRAND_OPERATOR" not in [r["role_candidate"] for r in reseller_result.role_candidates], reseller_result.role_candidates)
    master_result = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "https://reseller.vocotv.org", "title": "Voco TV IPTV reseller panel", "content": "reseller panel Voco TV IPTV login app download support https://reseller.vocotv.org/login"}, 1)
    add("reseller_with_infra_becomes_master_distributor", "POSSIBLE_MASTER_DISTRIBUTOR" in [r["role_candidate"] for r in master_result.role_candidates] and "POSSIBLE_BRAND_OPERATOR" not in [r["role_candidate"] for r in master_result.role_candidates], master_result.role_candidates)
    weak_homepage = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "https://vocotv.example", "title": "Voco TV IPTV", "content": "official Voco TV IPTV"}, 1)
    add("self_declared_official_not_operator", "POSSIBLE_BRAND_OPERATOR" not in [r["role_candidate"] for r in weak_homepage.role_candidates], weak_homepage.role_candidates)
    operator_result = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "https://vocotv.org", "title": "Voco TV IPTV", "content": "Voco TV IPTV login app download support contact support@vocotv.org"}, 1)
    add("operator_requires_infra_signals", "POSSIBLE_BRAND_OPERATOR" in [r["role_candidate"] for r in operator_result.role_candidates], operator_result.role_candidates)
    review_reseller = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "https://review.example", "title": "Voco TV review", "content": "review says reseller panel for Voco TV IPTV"}, 1)
    add("external_review_does_not_confirm_reseller", "CONFIRMED_RESELLER" not in [r["role_candidate"] for r in review_reseller.role_candidates], review_reseller.role_candidates)
    add("execute_requires_double_barrier", execute_barrier_allows(False, True) is False and execute_barrier_allows(True, False) is False and execute_barrier_allows(True, True) is True, None)
    no_perf_batches = [[normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": f"https://noise{i}.example", "title": "noise", "content": "nothing useful"}, 1)] for i in range(4)]
    add("no_stop_before_minimum", should_stop_after_query(no_perf_batches[:3], 4, 10) == (False, None), None)
    add("stop_after_three_no_yield_after_minimum", should_stop_after_query(no_perf_batches, 4, 10)[0], should_stop_after_query(no_perf_batches, 4, 10))
    duplicate_batches = []
    for i in range(4):
        batch = [
            normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": f"https://dup{i}.vocotv.org", "title": "Voco TV IPTV", "content": "support@vocotv.org login"}, 1),
            normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": f"https://dup{i}.vocotv.org", "title": "Voco TV IPTV", "content": "support@vocotv.org login"}, 2),
        ]
        mark_duplicates(batch)
        duplicate_batches.append(batch)
    add("stop_after_three_high_duplicate_rates", should_stop_after_query(duplicate_batches, 4, 10)[0], should_stop_after_query(duplicate_batches, 4, 10))
    add("early_stop_skips_discovery_keeps_controls", discovery_skips_after_early_stop(plan, "voco_df_04_apps_login") and controls_after_early_stop(plan, "voco_df_04_apps_login") == ["voco_ctrl_01_known_vocotv_ai", "voco_ctrl_02_negative_noise"], {"skips": discovery_skips_after_early_stop(plan, "voco_df_04_apps_login"), "controls": controls_after_early_stop(plan, "voco_df_04_apps_login")})
    add("vocotv_ai_does_not_stop_by_itself", should_stop_after_query([[synthetic_discovery]], 4, 10) == (False, None), None)
    compat_a = query_compatibility_hash(discovery_query, Args)
    compat_b = query_compatibility_hash(discovery_query, Args)
    changed_query = QuerySpec(**{**asdict(discovery_query), "exact_query": discovery_query.exact_query + " extra"})
    changed_negative = QuerySpec(**{**asdict(discovery_query), "hard_negative_terms": discovery_query.hard_negative_terms + ["extra-negative"]})
    class ArgsBrand(Args):
        brand = "Other Brand"
    class ArgsMax(Args):
        max_results = 7
    add("functional_hash_stable", compat_a == compat_b, compat_a)
    add("functional_hash_changes_query", compat_a != query_compatibility_hash(changed_query, Args), None)
    add("functional_hash_changes_negatives", compat_a != query_compatibility_hash(changed_negative, Args), None)
    add("functional_hash_changes_brand", compat_a != query_compatibility_hash(discovery_query, ArgsBrand), None)
    add("functional_hash_changes_max_results", compat_a != query_compatibility_hash(discovery_query, ArgsMax), None)
    add("term_boundaries", contains_any("mobile application unofficial promo reseller panel hotel-online odontologia", ["app", "official", "unofficial", "promo", "reseller panel", "hotel-online", "odontología"]) == ["unofficial", "promo", "reseller panel", "hotel-online", "odontología"], contains_any("mobile application unofficial promo reseller panel hotel-online odontologia", ["app", "official", "unofficial", "promo", "reseller panel", "hotel-online", "odontología"]))
    add("safety_hotel_dental", evaluate_safety([normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "https://vocotv.org", "title": "Voco TV IPTV", "content": "Voco TV IPTV hotel dental support@vocotv.org login"}, 1)], plan)["verdict"] == "SAFETY_FAIL", None)
    inferred_result = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "https://vocotv.org", "title": "Voco TV IPTV", "content": "Voco TV IPTV support@vocotv.org login"}, 1)
    inferred_result.role_candidates = [role("POSSIBLE_BRAND_OPERATOR", "MEDIUM", "forced inferred", observation(["brand_alias"], "INFERRED", "test")) | {"primary_role_candidate": True}]
    add("safety_inference_primary_fails", evaluate_safety([inferred_result], plan)["verdict"] == "SAFETY_FAIL", None)
    add("manifest_counters_dry_run", build_manifest(Args, "synthetic", "DRY_RUN", build_paths_for_run_dir(Path("dry_run_synthetic")), plan, True, True)["credential_reads"] == 0 and build_manifest(Args, "synthetic", "DRY_RUN", build_paths_for_run_dir(Path("dry_run_synthetic")), plan, True, True)["tavily_search_calls"] == 0, None)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        checkpoint_path = tmp_dir / "checkpoint.json"
        save_checkpoint(checkpoint_path, {"queries": {discovery_query.query_id: {"status": "COMPLETED", "execution_compatibility_hash": compat_a}}})
        loaded = load_checkpoint(checkpoint_path)
        add("checkpoint_valid_roundtrip", loaded["queries"][discovery_query.query_id]["status"] == "COMPLETED", loaded)
        checkpoint_path.write_text('{"queries": ', encoding="utf-8")
        corrupt_failed = False
        try:
            load_checkpoint(checkpoint_path)
        except ValueError:
            corrupt_failed = True
        add("checkpoint_corrupt_preserved", corrupt_failed and not checkpoint_path.exists(), None)
        jsonl_path = tmp_dir / "log.jsonl"
        jsonl_path.write_text('{"ok": true}\n{"partial": ', encoding="utf-8")
        rows, issues = read_jsonl_checked(jsonl_path)
        add("jsonl_final_partial_detected", len(rows) == 1 and issues and issues[0]["is_final_line"], issues)
        jsonl_path.write_text('{"ok": true}\n{"bad": \n{"ok": false}\n', encoding="utf-8")
        mid_corrupt_failed = False
        try:
            read_jsonl_checked(jsonl_path)
        except ValueError:
            mid_corrupt_failed = True
        add("jsonl_intermediate_corruption_fails", mid_corrupt_failed, None)
        atomic_path = tmp_dir / "atomic.json"
        write_json_atomic(atomic_path, {"ok": True})
        add("atomic_json_write", json.loads(atomic_path.read_text(encoding="utf-8"))["ok"] is True, None)
        run_dir = tmp_dir / "run_20260714_000000"
        paths = build_paths_for_run_dir(run_dir)
        run_dir.mkdir()
        manifest = build_manifest(Args, "20260714_000000", "EXECUTE", paths, plan, True, True)
        manifest["mode"] = "EXECUTE"
        write_json(paths["execution_manifest"], manifest)
        save_checkpoint(paths["checkpoint"], {"queries": {discovery_query.query_id: {"status": "COMPLETED", "execution_compatibility_hash": compat_a}}})
        class ResumeArgs(Args):
            resume_run_dir = str(run_dir)
            execute = True
            confirm_credit_use = True
        try:
            _run_dir, _manifest, resumed_checkpoint, _paths = validate_resume_run_dir(ResumeArgs, plan)
            resume_ok = resumed_checkpoint["queries"][discovery_query.query_id]["status"] == "COMPLETED"
        except Exception:
            resume_ok = False
        add("resume_existing_run_compatible", resume_ok, None)
        missing_failed = False
        class MissingResumeArgs(ResumeArgs):
            resume_run_dir = str(tmp_dir / "missing")
        try:
            validate_resume_run_dir(MissingResumeArgs, plan)
        except ValueError:
            missing_failed = True
        add("resume_missing_dir_fails", missing_failed, None)
        dry_run_dir = tmp_dir / "dry_run_bad"
        dry_paths = build_paths_for_run_dir(dry_run_dir)
        dry_run_dir.mkdir()
        dry_manifest = build_manifest(Args, "dry", "DRY_RUN", dry_paths, plan, True, True)
        write_json(dry_paths["execution_manifest"], dry_manifest)
        save_checkpoint(dry_paths["checkpoint"], {"queries": {}})
        class DryResumeArgs(ResumeArgs):
            resume_run_dir = str(dry_run_dir)
        dry_rejected = False
        try:
            validate_resume_run_dir(DryResumeArgs, plan)
        except ValueError:
            dry_rejected = True
        add("resume_dry_run_rejected", dry_rejected, None)
    return all(item["ok"] for item in tests), tests


def execute_barrier_allows(execute: bool, confirm_credit_use: bool) -> bool:
    return bool(execute and confirm_credit_use)


def calculate_metrics(results: list[NormalizedResult], plan: list[QuerySpec], baseline_domains: list[str]) -> dict[str, Any]:
    discovery_query_ids = {q.query_id for q in plan if q.included_in_discovery_metrics}
    control_query_ids = {q.query_id for q in plan if not q.included_in_discovery_metrics}
    discovery_results = [r for r in results if r.query_id in discovery_query_ids]
    control_results = [r for r in results if r.query_id in control_query_ids]
    non_duplicate_discovery = [r for r in discovery_results if not r.is_duplicate]
    candidate_domains = collect_candidate_domains(non_duplicate_discovery)
    relevant_candidates = [d for d in candidate_domains if d.get("is_relevant_family_candidate")]
    hotel_noise = [d for d in candidate_domains if d.get("hotel_noise_retained")]
    dental_noise = [d for d in candidate_domains if d.get("dental_noise_retained")]
    linked_domains = set()
    useful_relationships = set()
    for r in non_duplicate_discovery:
        for domain in r.extracted_fields.get("linked_domains", {}).get("value", []):
            linked_domains.add(domain)
            useful_relationships.add(build_relationship_id(r.canonical_hostname, "linked_domain", domain, r.canonical_url))
    recovered_baseline = {d["domain"] for d in relevant_candidates if d["domain"] in baseline_domains}
    baseline_denominator = len(baseline_domains) or None
    candidate_denominator = len(candidate_domains) or None
    raw_discovery_denominator = len(discovery_results) or None
    spontaneous = calculate_spontaneous_vocotv_ai_recovery(non_duplicate_discovery)
    new_relevant_domains = {d["domain"] for d in relevant_candidates if d["domain"] not in baseline_domains}
    unresolved_relevant = [d for d in relevant_candidates if d.get("role_candidate") == "UNKNOWN_ROLE" or d.get("signal_count", 0) < 2]
    query_yield: dict[str, dict[str, Any]] = {}
    for query in [q for q in plan if q.included_in_discovery_metrics]:
        q_results = [r for r in non_duplicate_discovery if r.query_id == query.query_id]
        q_domains = collect_candidate_domains(q_results)
        query_yield[query.category] = {
            "query_id": query.query_id,
            "new_relevant_domains_or_useful_relationships": len({d["domain"] for d in q_domains if d.get("is_relevant_family_candidate") and d["domain"] not in baseline_domains}),
        }
    return {
        "query_count_discovery": len({r.query_id for r in discovery_results}),
        "query_count_control": len({r.query_id for r in control_results}),
        "raw_result_count_discovery": len(discovery_results),
        "known_domain_recovery_rate": safe_div(len(recovered_baseline), baseline_denominator),
        "spontaneous_vocotv_ai_recovery": spontaneous,
        "new_candidate_domain_count": len(new_relevant_domains),
        "relevant_domain_precision": safe_div(len(relevant_candidates), candidate_denominator),
        "hotel_noise_rate": safe_div(len(hotel_noise), candidate_denominator),
        "dental_noise_rate": safe_div(len(dental_noise), candidate_denominator),
        "linked_domain_count": len(linked_domains),
        "new_useful_relationship_count": len(useful_relationships),
        "domain_family_expansion_index": safe_div(len(new_relevant_domains) + len(useful_relationships), baseline_denominator),
        "unresolved_identity_rate": safe_div(len(unresolved_relevant), len(relevant_candidates) or None),
        "duplicate_rate": safe_div(len([r for r in discovery_results if r.is_duplicate]), raw_discovery_denominator),
        "query_yield_by_category": query_yield,
        "officiality_metrics": None,
        "metric_notes": {
            "controls_excluded_where_required": True,
            "domain_family_expansion_index_is_not_a_natural_percentage": True,
            "zero_denominators_return_null": True,
        },
    }


def safe_div(numerator: int, denominator: int | None) -> float | None:
    if not denominator:
        return None
    return numerator / denominator


def calculate_spontaneous_vocotv_ai_recovery(results: list[NormalizedResult]) -> str:
    ambiguous_text_only = False
    for result in results:
        if result.query_type != "discovery":
            continue
        q = result.query_text.lower()
        if "vocotv.ai" in q or "site:vocotv.ai" in q:
            continue
        structured = result.canonical_hostname == "vocotv.ai" or "vocotv.ai" in (result.extracted_fields.get("linked_domains", {}).get("value") or [])
        if structured:
            return "TRUE"
        if any(item.get("domain") == "vocotv.ai" for item in result.ambiguous_text_only):
            ambiguous_text_only = True
    return "AMBIGUOUS_TEXT_ONLY" if ambiguous_text_only else "FALSE"


def collect_candidate_domains(results: list[NormalizedResult]) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    for result in results:
        if result.directly_observed_fields.get("url_validation_error", {}).get("value"):
            continue
        domains = [result.canonical_hostname]
        domains.extend(result.extracted_fields.get("linked_domains", {}).get("value") or [])
        for domain in domains:
            if not domain:
                continue
            role_candidates = result.role_candidates
            primary_role = next((role for role in role_candidates if role.get("primary_role_candidate")), role_candidates[0] if role_candidates else None)
            role_name = primary_role["role_candidate"] if primary_role else "UNKNOWN_ROLE"
            is_noise = any(role["role_candidate"] == "HOMONYM_OR_IRRELEVANT" for role in role_candidates)
            is_promotional = any(role["role_candidate"] == "REVIEW_OR_RANKING_SOURCE" for role in role_candidates)
            text_blob = result.title + " " + result.content + " " + result.raw_content
            is_relevant = not is_noise and not is_promotional and ("voco" in domain or any(term_matches(text_blob, alias) for alias in DEFAULT_ALIASES))
            item = candidates.setdefault(
                domain,
                {
                    "domain": domain,
                    "role_candidate": role_name,
                    "primary_role_candidate": role_name,
                    "query_ids": set(),
                    "evidence_urls": set(),
                    "evidence": [],
                    "is_relevant_family_candidate": False,
                    "hotel_noise_retained": False,
                    "dental_noise_retained": False,
                    "signal_count": 0,
                },
            )
            item["query_ids"].add(result.query_id)
            if result.canonical_url:
                item["evidence_urls"].add(result.canonical_url)
            item["evidence"].append(
                {
                    "query_id": result.query_id,
                    "url": result.canonical_url,
                    "observed_signal": role_name,
                    "evidence_origin": "directly_observed" if result.canonical_url else "unavailable",
                }
            )
            item["is_relevant_family_candidate"] = item["is_relevant_family_candidate"] or is_relevant
            item["hotel_noise_retained"] = item["hotel_noise_retained"] or bool(result.extracted_fields.get("ihg_hotel_signals", {}).get("value")) and is_relevant
            item["dental_noise_retained"] = item["dental_noise_retained"] or bool(result.extracted_fields.get("dental_signals", {}).get("value")) and is_relevant
            item["signal_count"] += len([role for role in role_candidates if role["role_candidate"] != "UNKNOWN_ROLE"])
    output = []
    for item in candidates.values():
        item["query_ids"] = sorted(item["query_ids"])
        item["evidence_urls"] = sorted(item["evidence_urls"])
        output.append(item)
    return output


def evaluate_safety(results: list[NormalizedResult], plan: list[QuerySpec]) -> dict[str, Any]:
    findings = []
    gate_results: dict[str, bool] = {
        "automatic_officiality_absent": True,
        "controls_not_in_discovery_metrics": True,
        "hotel_ihg_noise_not_retained": True,
        "dental_noise_not_retained": True,
        "inference_not_primary_positive_evidence": True,
        "candidate_traceability_present": True,
    }
    discovery_query_ids = {q.query_id for q in plan if q.included_in_discovery_metrics}
    for result in results:
        if result.query_type != "discovery" and result.query_id in discovery_query_ids:
            gate_results["controls_not_in_discovery_metrics"] = False
            findings.append("control result contaminated discovery metrics")
    if any(any(role.get("officiality_confirmed") for role in r.role_candidates) for r in results):
        gate_results["automatic_officiality_absent"] = False
        findings.append("automatic officiality confirmation detected")
    candidates = collect_candidate_domains([r for r in results if not r.is_duplicate])
    for candidate in candidates:
        if candidate.get("is_relevant_family_candidate") and candidate.get("hotel_noise_retained"):
            gate_results["hotel_ihg_noise_not_retained"] = False
            findings.append(f"hotel/IHG signal retained as IPTV candidate: {candidate['domain']}")
        if candidate.get("is_relevant_family_candidate") and candidate.get("dental_noise_retained"):
            gate_results["dental_noise_not_retained"] = False
            findings.append(f"dental signal retained as IPTV candidate: {candidate['domain']}")
        if not candidate.get("query_ids") or not candidate.get("evidence_urls") or not candidate.get("evidence"):
            gate_results["candidate_traceability_present"] = False
            findings.append(f"candidate lacks traceability: {candidate['domain']}")
    for result in results:
        for role_item in result.role_candidates:
            if role_item.get("primary_role_candidate") and role_item.get("role_candidate") == "POSSIBLE_BRAND_OPERATOR":
                evidence = role_item.get("evidence") or {}
                if evidence.get("observation_type") == "INFERRED":
                    gate_results["inference_not_primary_positive_evidence"] = False
                    findings.append(f"inferred-only operator evidence: {result.canonical_hostname}")
    no_candidate_warning = len(candidates) == 0
    notes = []
    if no_candidate_warning:
        notes.append("SAFETY_PASS_WITH_NO_CANDIDATES: technical safety only; not a discovery success")
    return {
        "verdict": "SAFETY_FAIL" if findings else "SAFETY_PASS",
        "findings": findings,
        "safety_notes": notes,
        "safety_gate_results": gate_results,
        "no_candidate_warning": no_candidate_warning,
    }


def evaluate_discovery(metrics: dict[str, Any]) -> dict[str, Any]:
    if metrics.get("spontaneous_vocotv_ai_recovery") == "TRUE" or metrics.get("new_candidate_domain_count", 0) >= 1 or metrics.get("new_useful_relationship_count", 0) >= 2:
        verdict = "DISCOVERY_PASS"
    elif metrics.get("raw_result_count_discovery", 0) > 0:
        verdict = "DISCOVERY_PARTIAL"
    else:
        verdict = "DISCOVERY_FAIL"
    return {"verdict": verdict, "basis": "spontaneous domain, new domains, or useful relationships only; no officiality implied"}


def evaluate_v3_utility(results: list[NormalizedResult], metrics: dict[str, Any]) -> dict[str, Any]:
    useful = metrics.get("new_useful_relationship_count", 0) or metrics.get("linked_domain_count", 0)
    if useful >= 2:
        verdict = "V3_UTILITY_PASS"
    elif useful == 1 or results:
        verdict = "V3_UTILITY_PARTIAL"
    else:
        verdict = "V3_UTILITY_FAIL"
    return {"verdict": verdict, "basis": "fingerprints, contacts, support, checkout, app, roles, conflicts, and traceability"}


def should_stop_after_query(executed_discovery_results: list[list[NormalizedResult]], min_discovery_executed: int, max_discovery_queries: int) -> tuple[bool, str | None]:
    if len(executed_discovery_results) >= max_discovery_queries:
        return True, "budget_max_reached"
    if len(executed_discovery_results) < min_discovery_executed:
        return False, None
    recent = executed_discovery_results[-3:]
    if len(recent) == 3:
        duplicate_rates = []
        no_new_signal = []
        for batch in recent:
            total = len(batch)
            duplicate_rates.append(safe_div(len([r for r in batch if r.is_duplicate]), total or None) or 0)
            domains = collect_candidate_domains([r for r in batch if not r.is_duplicate])
            no_new_signal.append(not any(d.get("is_relevant_family_candidate") for d in domains))
        if all(rate > 0.50 for rate in duplicate_rates):
            return True, "duplicate_rate_above_0_50_for_three_discovery_queries"
        if all(no_new_signal):
            return True, "three_discovery_queries_without_new_domain_or_relationship"
    return False, None


def discovery_skips_after_early_stop(plan: list[QuerySpec], trigger_query_id: str) -> list[str]:
    trigger = next((query for query in plan if query.query_id == trigger_query_id), None)
    if not trigger:
        return []
    return [
        query.query_id
        for query in plan
        if query.included_in_discovery_metrics and query.execution_order > trigger.execution_order
    ]


def controls_after_early_stop(plan: list[QuerySpec], trigger_query_id: str) -> list[str]:
    trigger = next((query for query in plan if query.query_id == trigger_query_id), None)
    if not trigger:
        return []
    return [
        query.query_id
        for query in plan
        if not query.included_in_discovery_metrics and query.execution_order > trigger.execution_order
    ]


def build_execution_compatibility_hash(
    query: QuerySpec,
    *,
    brand: str,
    aliases: list[str],
    search_depth: str,
    max_results: int,
    include_raw_content: bool,
    include_answer: bool,
    timeout: float,
    design_hash: str | None,
) -> str:
    payload = {
        "logic_version": LOGIC_VERSION,
        "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
        "brand": brand,
        "aliases": aliases,
        "query_id": query.query_id,
        "query_type": query.query_type,
        "phase": query.phase,
        "category": query.category,
        "exact_query": query.exact_query,
        "positive_terms": query.positive_terms,
        "hard_negative_terms": query.hard_negative_terms,
        "soft_negative_terms": query.soft_negative_terms,
        "post_retrieval_noise_signals": query.post_retrieval_noise_signals,
        "included_in_discovery_metrics": query.included_in_discovery_metrics,
        "search_depth": search_depth,
        "max_results": max_results,
        "include_raw_content": include_raw_content,
        "include_answer": include_answer,
        "timeout": timeout,
        "design_hash": design_hash,
    }
    return stable_hash(payload)


def query_compatibility_hash(query: QuerySpec, args: argparse.Namespace) -> str:
    return build_execution_compatibility_hash(
        query,
        brand=args.brand,
        aliases=DEFAULT_ALIASES if args.brand == DEFAULT_BRAND else [args.brand],
        search_depth=args.search_depth,
        max_results=args.max_results,
        include_raw_content=True,
        include_answer=False,
        timeout=args.timeout,
        design_hash=file_sha256(DEFAULT_DESIGN_PATH),
    )


def load_checkpoint(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            corrupt_path = path.with_name(f"{path.name}.corrupt_{local_run_stamp()}")
            os.replace(path, corrupt_path)
            raise ValueError(f"Checkpoint is corrupt and was preserved as {corrupt_path}") from exc
    return {"schema_version": CHECKPOINT_SCHEMA_VERSION, "queries": {}}


def save_checkpoint(path: Path, checkpoint: dict[str, Any]) -> None:
    checkpoint.setdefault("schema_version", CHECKPOINT_SCHEMA_VERSION)
    write_json(path, checkpoint)


def checkpoint_status_for_query(checkpoint: dict[str, Any], query: QuerySpec, compatibility_hash: str, resume: bool) -> str:
    if checkpoint.get("schema_version") not in {None, CHECKPOINT_SCHEMA_VERSION}:
        raise ValueError(f"Incompatible checkpoint schema: {checkpoint.get('schema_version')}")
    if not resume:
        return "PENDING"
    existing = checkpoint.get("queries", {}).get(query.query_id)
    if not existing:
        return "PENDING"
    existing_hash = existing.get("execution_compatibility_hash") or existing.get("query_hash")
    if existing_hash and existing_hash != compatibility_hash:
        raise ValueError(f"Checkpoint hash mismatch for {query.query_id}")
    if existing.get("status") in {"COMPLETED", "CONTROL_COMPLETED"}:
        return "SKIPPED"
    if existing.get("status") == "SKIPPED_EARLY_STOP":
        return "SKIPPED_EARLY_STOP"
    if existing.get("status") in {"FAILED", "RUNNING", "PENDING"}:
        return "PENDING"
    return "PENDING"


def build_domain_family(results: list[NormalizedResult], brand_name: str, plan: list[QuerySpec]) -> dict[str, Any]:
    candidate_domains = collect_candidate_domains([r for r in results if not r.is_duplicate])
    relationships = []
    for result in results:
        for domain in result.extracted_fields.get("linked_domains", {}).get("value", []):
            relationships.append(
                {
                    "relationship_id": build_relationship_id(result.canonical_hostname, "linked_domain", domain, result.canonical_url),
                    "source_domain": result.canonical_hostname,
                    "relationship_type": "linked_domain",
                    "target_domain": domain,
                    "source_url": result.canonical_url,
                    "query_id": result.query_id,
                    "officiality_confirmed": False,
                }
            )
    return {
        "brand_family": {
            "brand_name": brand_name,
            "aliases": DEFAULT_ALIASES if brand_name == DEFAULT_BRAND else [brand_name],
            "baseline_domains": BASELINE_DOMAINS if brand_name == DEFAULT_BRAND else [],
            "candidate_domains": candidate_domains,
            "domain_relationships": relationships,
            "identity_fingerprints": [],
            "conflicting_claims": [],
            "source_roles": [],
            "discovery_queries": [asdict(q) for q in plan],
            "evidence_gaps": ["officiality_not_evaluated", "identity_not_confirmed"],
        }
    }


def build_output_paths(output_root: Path, mode: str, run_id: str) -> dict[str, Path]:
    prefix = "dry_run" if mode == "DRY_RUN" else "run"
    run_dir = output_root / f"{prefix}_{run_id}"
    return build_paths_for_run_dir(run_dir)


def build_paths_for_run_dir(run_dir: Path) -> dict[str, Path]:
    return {
        "run_dir": run_dir,
        "query_plan_preview_json": run_dir / "query_plan_preview.DRY_RUN.NO_NETWORK.json",
        "query_plan_preview_md": run_dir / "query_plan_preview.DRY_RUN.NO_NETWORK.md",
        "validation_report": run_dir / "validation_report.DRY_RUN.NO_NETWORK.json",
        "execution_manifest": run_dir / "execution_manifest.json",
        "query_plan_json": run_dir / "query_plan.json",
        "query_plan_md": run_dir / "query_plan.md",
        "checkpoint": run_dir / "checkpoint.json",
        "query_log": run_dir / "query_log.jsonl",
        "raw_results": run_dir / "raw_results.jsonl",
        "normalized_results": run_dir / "normalized_results.csv",
        "domain_candidates": run_dir / "domain_candidates.csv",
        "domain_family": run_dir / "domain_family.json",
        "domain_relationships": run_dir / "domain_relationships.csv",
        "noise_results": run_dir / "noise_results.csv",
        "metrics": run_dir / "metrics.json",
        "micro_pilot_report": run_dir / "micro_pilot_report.md",
        "errors": run_dir / "errors.jsonl",
    }


def validate_resume_run_dir(args: argparse.Namespace, plan: list[QuerySpec]) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Path]]:
    if not args.resume_run_dir:
        raise ValueError("resume_run_dir is required")
    run_dir = Path(args.resume_run_dir).resolve()
    if not run_dir.exists() or not run_dir.is_dir():
        raise ValueError(f"Resume run directory does not exist: {run_dir}")
    paths = build_paths_for_run_dir(run_dir)
    if not paths["checkpoint"].exists():
        raise ValueError(f"Resume checkpoint missing: {paths['checkpoint']}")
    if not paths["execution_manifest"].exists():
        raise ValueError(f"Resume manifest missing: {paths['execution_manifest']}")
    manifest = json.loads(paths["execution_manifest"].read_text(encoding="utf-8"))
    if manifest.get("mode") == "DRY_RUN":
        raise ValueError("Cannot resume from DRY_RUN manifest")
    if manifest.get("parameters", {}).get("brand") != args.brand:
        raise ValueError("Resume brand does not match current brand")
    current_design_hash = file_sha256(DEFAULT_DESIGN_PATH)
    if manifest.get("design_hash") != current_design_hash:
        raise ValueError("Resume design hash does not match current design")
    checkpoint = load_checkpoint(paths["checkpoint"])
    for query in plan:
        existing = checkpoint.get("queries", {}).get(query.query_id)
        if not existing:
            continue
        existing_hash = existing.get("execution_compatibility_hash") or existing.get("query_hash")
        current_hash = query_compatibility_hash(query, args)
        if existing_hash and existing_hash != current_hash:
            raise ValueError(f"Resume checkpoint incompatible for {query.query_id}")
        if existing.get("status") == "RUNNING":
            existing["status"] = "PENDING"
            existing["recovered_from_interrupted_running"] = utc_now()
    return run_dir, manifest, checkpoint, paths


def render_query_plan_markdown(plan: list[QuerySpec], mode: str, max_results: int, search_depth: str) -> str:
    lines = [
        f"# Domain Family Discovery Query Plan - {mode}",
        "",
        "- network_calls: 0" if mode == "DRY_RUN" else "- network_calls: enabled only during protected execute mode",
        f"- search_depth: `{search_depth}`",
        f"- max_results: `{max_results}`",
        "- include_raw_content: `True`",
        "- include_answer: `False`",
        "",
        "| order | query_id | query_type | phase | category | included_in_discovery_metrics | exact_query |",
        "|---:|---|---|---|---|---|---|",
    ]
    for query in plan:
        escaped = query.exact_query.replace("|", "\\|")
        lines.append(f"| {query.execution_order} | `{query.query_id}` | {query.query_type} | {query.phase} | {query.category} | {'yes' if query.included_in_discovery_metrics else 'no'} | `{escaped}` |")
    lines.extend(
        [
            "",
            "## Dry-run guardrails" if mode == "DRY_RUN" else "## Execution guardrails",
            "",
            "- TavilyClient is not instantiated in dry-run.",
            "- TAVILY_API_KEY is not read in dry-run.",
            "- Controls are excluded from discovery metrics.",
            "- No official domain is declared by this plan.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_manifest(args: argparse.Namespace, run_id: str, mode: str, paths: dict[str, Path], plan: list[QuerySpec], validation_ok: bool, self_tests_ok: bool) -> dict[str, Any]:
    discovery_count = len([q for q in plan if q.included_in_discovery_metrics])
    control_count = len([q for q in plan if not q.included_in_discovery_metrics])
    compatibility_hash = stable_hash([query_compatibility_hash(query, args) for query in plan])
    return {
        "script_path": str(SCRIPT_PATH),
        "script_hash": file_sha256(SCRIPT_PATH),
        "design_path": str(DEFAULT_DESIGN_PATH),
        "design_hash": file_sha256(DEFAULT_DESIGN_PATH),
        "logic_version": LOGIC_VERSION,
        "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
        "execution_compatibility_hash": compatibility_hash,
        "run_id": run_id,
        "mode": mode,
        "network_enabled": False if mode == "DRY_RUN" else bool(args.execute and args.confirm_credit_use),
        "tavily_enabled": False if mode == "DRY_RUN" else bool(args.execute and args.confirm_credit_use),
        "credential_read": False if mode == "DRY_RUN" else None,
        "credential_reads": CREDENTIAL_READS,
        "tavily_client_instantiations": TAVILY_CLIENT_INSTANTIATIONS,
        "network_calls": NETWORK_CALLS,
        "tavily_search_calls": TAVILY_SEARCH_CALLS,
        "checkpoint_reused": bool(getattr(args, "resume_run_dir", None)),
        "resumed_run": bool(getattr(args, "resume_run_dir", None)),
        "early_stop_triggered": False,
        "discovery_queries_skipped": 0,
        "controls_executed": 0,
        "query_counts": {"discovery": discovery_count, "control": control_count, "total": len(plan)},
        "budget": {
            "configured_max_results": args.max_results,
            "allowed_max_results": ALLOWED_MAX_RESULTS,
            "recommended_total_queries": RECOMMENDED_TOTAL_QUERIES,
            "absolute_max_queries": ABSOLUTE_MAX_QUERIES,
            "max_results_per_query": args.max_results,
            "recommended_max_raw_results": discovery_count * args.max_results + control_count * args.max_results,
            "recommended_result_ceiling": RECOMMENDED_TOTAL_QUERIES * args.max_results,
            "absolute_result_ceiling": ABSOLUTE_MAX_QUERIES * args.max_results,
            "absolute_max_raw_results": ABSOLUTE_MAX_QUERIES * args.max_results,
            "budget_validation_passed": 1 <= args.max_results <= ALLOWED_MAX_RESULTS,
        },
        "parameters": {
            "brand": args.brand,
            "search_depth": args.search_depth,
            "max_results": args.max_results,
            "include_raw_content": True,
            "include_answer": False,
            "timeout": args.timeout,
            "pause_seconds": args.pause_seconds,
            "max_retries": args.max_retries,
            "resume_run_dir": getattr(args, "resume_run_dir", None),
            "query_ids": args.query_ids,
            "stop_after_phase": args.stop_after_phase,
        },
        "timestamps": {"created_at": utc_now()},
        "output_paths": {key: str(value) for key, value in paths.items()},
        "checkpoint_path": str(paths["checkpoint"]),
        "verdict_availability": {
            "SAFETY_VERDICT": "available_after_real_results",
            "DISCOVERY_VERDICT": "available_after_real_results",
            "V3_UTILITY_VERDICT": "available_after_real_results",
        },
        "historical_artifacts_modified": False,
        "raw_results_generated": False if mode == "DRY_RUN" else None,
        "real_results_generated": False if mode == "DRY_RUN" else None,
        "validation_ok": validation_ok,
        "self_tests_ok": self_tests_ok,
        "status": "DRY_RUN_NO_NETWORK_NO_REAL_RESULTS" if mode == "DRY_RUN" else "EXECUTION_MODE_PREPARED",
    }


def run_dry_run(args: argparse.Namespace) -> int:
    run_id = local_run_stamp()
    plan = filter_plan(build_query_plan(), args.query_ids, args.stop_after_phase)
    paths = build_output_paths(Path(args.output_root).resolve(), "DRY_RUN", run_id)
    validation_ok, validation_checks = validate_query_plan(plan)
    self_tests_ok, self_tests = run_internal_self_tests(plan)
    paths["run_dir"].mkdir(parents=True, exist_ok=True)
    plan_payload = {
        "mode": "DRY_RUN",
        "network_calls": 0,
        "tavily_client_instantiations": 0,
        "credential_reads": 0,
        "brand": args.brand,
        "queries": [query_payload(q, args) for q in plan],
        "budget": {
            "recommended_discovery_queries": RECOMMENDED_DISCOVERY_QUERIES,
            "recommended_control_queries": RECOMMENDED_CONTROL_QUERIES,
            "recommended_total_queries": RECOMMENDED_TOTAL_QUERIES,
            "absolute_max_queries": ABSOLUTE_MAX_QUERIES,
            "configured_max_results": args.max_results,
            "allowed_max_results": ALLOWED_MAX_RESULTS,
            "max_results_per_query": args.max_results,
            "recommended_result_ceiling": RECOMMENDED_TOTAL_QUERIES * args.max_results,
            "absolute_result_ceiling": ABSOLUTE_MAX_QUERIES * args.max_results,
            "recommended_max_raw_results": RECOMMENDED_TOTAL_QUERIES * args.max_results,
            "absolute_max_raw_results": ABSOLUTE_MAX_QUERIES * args.max_results,
            "budget_validation_passed": 1 <= args.max_results <= ALLOWED_MAX_RESULTS,
        },
        "notes": [
            "DRY_RUN",
            "NO_NETWORK",
            "NO_REAL_RESULTS",
            "controls_excluded_from_discovery_metrics",
            "no_official_domain_declared",
        ],
    }
    write_json(paths["query_plan_preview_json"], plan_payload)
    paths["query_plan_preview_md"].write_text(render_query_plan_markdown(plan, "DRY_RUN", args.max_results, args.search_depth), encoding="utf-8")
    validation_payload = {
        "mode": "DRY_RUN",
        "network_calls": NETWORK_CALLS,
        "tavily_client_instantiations": TAVILY_CLIENT_INSTANTIATIONS,
        "credential_reads": CREDENTIAL_READS,
        "validation_ok": validation_ok,
        "validation_checks": validation_checks,
        "self_tests_ok": self_tests_ok,
        "self_tests": self_tests,
    }
    write_json(paths["validation_report"], validation_payload)
    manifest = build_manifest(args, run_id, "DRY_RUN", paths, plan, validation_ok, self_tests_ok)
    write_json(paths["execution_manifest"], manifest)
    summary = {
        "mode": "DRY_RUN",
        "run_dir": str(paths["run_dir"]),
        "discovery_queries": len([q for q in plan if q.included_in_discovery_metrics]),
        "control_queries": len([q for q in plan if not q.included_in_discovery_metrics]),
        "total_queries": len(plan),
        "absolute_max_queries": 12,
        "network_calls": NETWORK_CALLS,
        "credential_reads": CREDENTIAL_READS,
        "tavily_client_instantiations": TAVILY_CLIENT_INSTANTIATIONS,
        "tavily_search_calls": TAVILY_SEARCH_CALLS,
        "real_results_generated": False,
        "validation_ok": validation_ok,
        "self_tests_ok": self_tests_ok,
        "outputs": {
            "query_plan_preview_json": str(paths["query_plan_preview_json"]),
            "query_plan_preview_md": str(paths["query_plan_preview_md"]),
            "validation_report": str(paths["validation_report"]),
            "execution_manifest": str(paths["execution_manifest"]),
        },
    }
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return 0 if validation_ok and self_tests_ok else 2


def query_payload(query: QuerySpec, args: argparse.Namespace) -> dict[str, Any]:
    data = asdict(query)
    data["included_in_discovery_metrics"] = bool(query.included_in_discovery_metrics)
    data["query_hash"] = query.query_hash(args.search_depth, args.max_results, True, False)
    data["execution_compatibility_hash"] = query_compatibility_hash(query, args)
    data["logic_version"] = LOGIC_VERSION
    data["checkpoint_schema_version"] = CHECKPOINT_SCHEMA_VERSION
    data["tavily_parameters_prepared"] = {
        "query": query.exact_query,
        "search_depth": args.search_depth,
        "max_results": args.max_results,
        "include_raw_content": True,
        "include_answer": False,
        "timeout": args.timeout,
    }
    data["officiality_declared"] = False
    return data


def filter_plan(plan: list[QuerySpec], query_ids: str | None, stop_after_phase: str | None) -> list[QuerySpec]:
    output = plan
    if query_ids:
        wanted = {item.strip() for item in query_ids.split(",") if item.strip()}
        output = [query for query in output if query.query_id in wanted]
    if stop_after_phase:
        allowed_phases = {"A": {"A"}, "B": {"A", "B"}, "C": {"A", "B", "C"}, "control": {"A", "B", "C", "control"}}
        phases = allowed_phases.get(stop_after_phase)
        if phases:
            output = [query for query in output if query.phase in phases or query.phase == "control"]
    return sorted(output, key=lambda q: q.execution_order)


def run_execute(args: argparse.Namespace) -> int:
    global CREDENTIAL_READS, TAVILY_CLIENT_INSTANTIATIONS, NETWORK_CALLS, TAVILY_SEARCH_CALLS
    if not execute_barrier_allows(args.execute, args.confirm_credit_use):
        print("Execution refused: --execute and --confirm-credit-use are both required.", file=sys.stderr)
        return 2
    if args.dry_run:
        print("Execution refused: --dry-run and --execute are mutually exclusive.", file=sys.stderr)
        return 2
    plan = filter_plan(build_query_plan(), args.query_ids, args.stop_after_phase)
    checkpoint_reused = False
    resume_manifest: dict[str, Any] | None = None
    if args.resume_run_dir:
        try:
            run_dir, resume_manifest, checkpoint, paths = validate_resume_run_dir(args, plan)
        except Exception as exc:
            print(json.dumps({"status": "FAILED_SAFE_RESUME_VALIDATION", "error": str(exc)}), file=sys.stderr)
            return 2
        run_id = str(resume_manifest.get("run_id") or run_dir.name.replace("run_", ""))
        checkpoint_reused = True
    else:
        run_id = local_run_stamp()
        paths = build_output_paths(Path(args.output_root).resolve(), "EXECUTE", run_id)
        checkpoint = {"schema_version": CHECKPOINT_SCHEMA_VERSION, "queries": {}}
    CREDENTIAL_READS += 1
    api_key = os.environ.get("TAVILY_API_KEY")
    credential_available = bool(api_key)
    if not credential_available:
        print(json.dumps({"credential_available": False, "status": "FAILED_SAFE_NO_CREDENTIAL"}), file=sys.stderr)
        return 2
    try:
        from tavily import TavilyClient  # type: ignore
    except Exception as exc:  # pragma: no cover - future execution path only
        print(json.dumps({"credential_available": True, "status": "FAILED_IMPORTING_TAVILY_SDK", "error": str(exc)}), file=sys.stderr)
        return 2

    paths["run_dir"].mkdir(parents=True, exist_ok=True)
    write_json(paths["query_plan_json"], {"mode": "EXECUTE", "queries": [query_payload(q, args) for q in plan]})
    paths["query_plan_md"].write_text(render_query_plan_markdown(plan, "EXECUTE", args.max_results, args.search_depth), encoding="utf-8")
    client = TavilyClient(api_key=api_key)
    TAVILY_CLIENT_INSTANTIATIONS += 1
    normalized_results: list[NormalizedResult] = []
    query_batches: list[list[NormalizedResult]] = []
    technical_failure = False
    early_stop_info: dict[str, Any] | None = None
    discovery_queries_skipped = 0
    controls_executed = 0

    for query in plan:
        compatibility_hash = query_compatibility_hash(query, args)
        q_hash = query.query_hash(args.search_depth, args.max_results, True, False)
        if early_stop_info and query.included_in_discovery_metrics:
            checkpoint.setdefault("queries", {})[query.query_id] = {
                "query_id": query.query_id,
                "status": "SKIPPED_EARLY_STOP",
                "attempts": 0,
                "started_at": None,
                "completed_at": utc_now(),
                "error": None,
                "result_count": 0,
                "query_hash": q_hash,
                "execution_compatibility_hash": compatibility_hash,
                "stop_reason": early_stop_info["stop_reason"],
                "stop_trigger_query_id": early_stop_info["stop_trigger_query_id"],
            }
            discovery_queries_skipped += 1
            save_checkpoint(paths["checkpoint"], checkpoint)
            append_jsonl(paths["query_log"], log_query(run_id, query, "SKIPPED_EARLY_STOP", 0, 0, early_stop_info["stop_reason"], compatibility_hash))
            continue
        status = checkpoint_status_for_query(checkpoint, query, compatibility_hash, checkpoint_reused)
        if status == "SKIPPED":
            append_jsonl(paths["query_log"], log_query(run_id, query, "SKIPPED", 0, 0, None, compatibility_hash))
            continue
        if status == "SKIPPED_EARLY_STOP":
            discovery_queries_skipped += 1
            append_jsonl(paths["query_log"], log_query(run_id, query, "SKIPPED_EARLY_STOP", 0, 0, "resume_preserved_early_stop", compatibility_hash))
            continue
        checkpoint.setdefault("queries", {})[query.query_id] = {
            "query_id": query.query_id,
            "status": "RUNNING",
            "attempts": 0,
            "started_at": utc_now(),
            "completed_at": None,
            "error": None,
            "result_count": 0,
            "query_hash": q_hash,
            "execution_compatibility_hash": compatibility_hash,
        }
        save_checkpoint(paths["checkpoint"], checkpoint)
        results_for_query: list[NormalizedResult] = []
        error_text = None
        for attempt in range(1, args.max_retries + 1):
            checkpoint["queries"][query.query_id]["attempts"] = attempt
            try:
                NETWORK_CALLS += 1
                TAVILY_SEARCH_CALLS += 1
                response = client.search(
                    query=query.exact_query,
                    search_depth=args.search_depth,
                    max_results=args.max_results,
                    include_raw_content=True,
                    include_answer=False,
                    timeout=args.timeout,
                )
                raw_results = response.get("results", []) if isinstance(response, dict) else []
                for idx, item in enumerate(raw_results, start=1):
                    record = {
                        "run_id": run_id,
                        "query_id": query.query_id,
                        "query_type": query.query_type,
                        "phase": query.phase,
                        "category": query.category,
                        "query_text": query.exact_query,
                        "timestamp": utc_now(),
                        "result_position": idx,
                        "source_data": item,
                    }
                    append_jsonl(paths["raw_results"], record)
                    results_for_query.append(normalize_tavily_result(run_id, query, args.brand, item, idx))
                error_text = None
                break
            except Exception as exc:  # pragma: no cover - future execution path only
                error_text = str(exc)
                append_jsonl(paths["errors"], {"run_id": run_id, "query_id": query.query_id, "attempt": attempt, "error": error_text, "timestamp": utc_now()})
                if attempt < args.max_retries:
                    time.sleep(min(60, 3 * (2 ** (attempt - 1))))
        final_status = "CONTROL_COMPLETED" if query.phase == "control" and error_text is None else "COMPLETED" if error_text is None else "FAILED"
        checkpoint["queries"][query.query_id].update(
            {
                "status": final_status,
                "completed_at": utc_now(),
                "error": error_text,
                "result_count": len(results_for_query),
                "query_hash": q_hash,
                "execution_compatibility_hash": compatibility_hash,
            }
        )
        save_checkpoint(paths["checkpoint"], checkpoint)
        append_jsonl(paths["query_log"], log_query(run_id, query, final_status, checkpoint["queries"][query.query_id]["attempts"], len(results_for_query), error_text, compatibility_hash))
        normalized_results.extend(results_for_query)
        if query.phase == "control" and final_status == "CONTROL_COMPLETED":
            controls_executed += 1
        if query.included_in_discovery_metrics:
            query_batches.append(results_for_query)
            mark_duplicates(normalized_results)
            stop, reason = should_stop_after_query(query_batches, min_discovery_executed=4, max_discovery_queries=10)
            if stop:
                early_stop_info = {
                    "stop_reason": reason,
                    "stop_trigger_query_id": query.query_id,
                    "stop_triggered_at": utc_now(),
                    "discovery_queries_completed": len(query_batches),
                    "discovery_queries_skipped": len([q for q in plan if q.included_in_discovery_metrics and q.execution_order > query.execution_order]),
                }
                checkpoint["early_stop"] = early_stop_info
                save_checkpoint(paths["checkpoint"], checkpoint)
                append_jsonl(paths["query_log"], {"run_id": run_id, "status": "STOPPING_DISCOVERY", **early_stop_info})
        if args.pause_seconds > 0:
            time.sleep(args.pause_seconds)
        if final_status == "FAILED":
            technical_failure = True

    mark_duplicates(normalized_results)
    metrics = calculate_metrics(normalized_results, plan, BASELINE_DOMAINS)
    write_csv(paths["normalized_results"], [asdict(r) for r in normalized_results])
    write_csv(paths["domain_candidates"], collect_candidate_domains(normalized_results))
    family = build_domain_family(normalized_results, args.brand, plan)
    write_json(paths["domain_family"], family)
    relationships = family["brand_family"]["domain_relationships"]
    write_csv(paths["domain_relationships"], relationships)
    noise_rows = [asdict(r) for r in normalized_results if any(role["role_candidate"] == "HOMONYM_OR_IRRELEVANT" for role in r.role_candidates)]
    write_csv(paths["noise_results"], noise_rows)
    write_json(paths["metrics"], metrics)
    safety = evaluate_safety(normalized_results, plan)
    discovery = evaluate_discovery(metrics)
    utility = evaluate_v3_utility(normalized_results, metrics)
    report = render_micro_pilot_report(args.brand, metrics, safety, discovery, utility, technical_failure)
    paths["micro_pilot_report"].write_text(report, encoding="utf-8")
    manifest = build_manifest(args, run_id, "EXECUTE", paths, plan, True, True)
    manifest.update(
        {
            "network_enabled": True,
            "tavily_enabled": True,
            "credential_read": True,
            "credential_available": credential_available,
            "credential_reads": CREDENTIAL_READS,
            "tavily_client_instantiations": TAVILY_CLIENT_INSTANTIATIONS,
            "network_calls": NETWORK_CALLS,
            "tavily_search_calls": TAVILY_SEARCH_CALLS,
            "checkpoint_reused": checkpoint_reused,
            "resumed_run": checkpoint_reused,
            "early_stop_triggered": bool(early_stop_info),
            "discovery_queries_skipped": discovery_queries_skipped,
            "controls_executed": controls_executed,
            "raw_results_generated": paths["raw_results"].exists(),
            "real_results_generated": paths["raw_results"].exists(),
            "status": "EXECUTION_COMPLETED_WITH_ERRORS" if technical_failure else "EXECUTION_COMPLETED",
        }
    )
    write_json(paths["execution_manifest"], manifest)
    print(json.dumps({"mode": "EXECUTE", "run_dir": str(paths["run_dir"]), "network_calls": NETWORK_CALLS, "status": manifest["status"]}, ensure_ascii=True, indent=2))
    return 1 if technical_failure else 0


def mark_duplicates(results: list[NormalizedResult]) -> None:
    seen = set()
    for result in results:
        key = result.duplicate_key or result.result_id
        result.is_duplicate = key in seen
        seen.add(key)


def log_query(run_id: str, query: QuerySpec, status: str, attempts: int, result_count: int, error: str | None, query_hash: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "query_id": query.query_id,
        "query_type": query.query_type,
        "phase": query.phase,
        "category": query.category,
        "query_text": query.exact_query,
        "timestamp": utc_now(),
        "status": status,
        "attempts": attempts,
        "result_count": result_count,
        "error": error,
        "query_hash": query_hash,
    }


def render_micro_pilot_report(
    brand: str,
    metrics: dict[str, Any],
    safety: dict[str, Any],
    discovery: dict[str, Any],
    utility: dict[str, Any],
    technical_failure: bool,
) -> str:
    lines = [
        f"# Domain Family Discovery Micro-pilot - {brand}",
        "",
        "This report does not declare official domains.",
        "",
        "## Verdicts",
        "",
        f"- SAFETY_VERDICT: `{safety['verdict']}`",
        f"- DISCOVERY_VERDICT: `{discovery['verdict']}`",
        f"- V3_UTILITY_VERDICT: `{utility['verdict']}`",
        f"- technical_failure: `{technical_failure}`",
        "",
        "## Metrics",
        "",
    ]
    for key, value in metrics.items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Independent IPTV domain family discovery runner.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Validate/export plan offline; no API key, no Tavily, no network.")
    mode.add_argument("--execute", action="store_true", help="Future protected real execution mode.")
    mode.add_argument("--validate-design", action="store_true", help="Alias for offline design validation.")
    parser.add_argument("--confirm-credit-use", action="store_true", help="Required together with --execute before Tavily can be used.")
    parser.add_argument("--brand", default=DEFAULT_BRAND)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--pause-seconds", type=float, default=1.0)
    parser.add_argument("--max-results", type=int, default=8)
    parser.add_argument("--search-depth", choices=["basic", "advanced"], default="advanced")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--resume-run-dir", default=None, help="Resume a protected execution from an existing run directory.")
    parser.add_argument("--query-ids", default=None, help="Comma-separated query IDs.")
    parser.add_argument("--stop-after-phase", choices=["A", "B", "C", "control"], default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.validate_design:
        args.dry_run = True
    if args.confirm_credit_use and not args.execute:
        print("--confirm-credit-use has no effect without --execute.", file=sys.stderr)
    if args.max_results < 1 or args.max_results > ALLOWED_MAX_RESULTS:
        print(f"--max-results must be an integer between 1 and {ALLOWED_MAX_RESULTS}.", file=sys.stderr)
        return 2
    if args.max_retries <= 0:
        print("--max-retries must be positive.", file=sys.stderr)
        return 2
    if args.resume_run_dir and not args.execute:
        print("--resume-run-dir requires --execute.", file=sys.stderr)
        return 2
    if args.resume_run_dir and args.dry_run:
        print("--resume-run-dir is incompatible with --dry-run.", file=sys.stderr)
        return 2
    if args.dry_run:
        return run_dry_run(args)
    return run_execute(args)


if __name__ == "__main__":
    raise SystemExit(main())
