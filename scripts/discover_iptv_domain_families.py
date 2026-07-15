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
import shutil
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
MAXIMUM_QUERY_LENGTH = 400
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


def is_nonempty_identifier(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    stripped = value.strip()
    if any(unicodedata.category(ch) == "Cc" for ch in stripped):
        return False
    return re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}", stripped) is not None


def assess_noise_context(text_blob: str, canonical: dict[str, Any], extracted: dict[str, Any]) -> dict[str, Any]:
    hard_hotel_signals = contains_any(
        text_blob,
        ["IHG", "InterContinental Hotels Group", "hotel-online", "IHG careers", "Voco hotel"],
    )
    soft_hospitality_signals = contains_any(text_blob, CONTEXTUAL_SOFT_NEGATIVES)
    dental_signals = contains_any(text_blob, ["voco.dental", "dental", "dentist", "dentistry", "odontologia"])
    strong_iptv_signals = contains_any(
        text_blob,
        ["IPTV", "M3U", "Xtream", "subscription", "plans", "channels", "VOD", "IPTV app", "IPTV player", "activation"],
    )
    domain = canonical.get("canonical_hostname") or ""
    same_domain_email = bool(domain and domain in (extracted.get("email_domains", {}).get("value") or []))
    identity_signals = []
    if same_domain_email:
        identity_signals.append("same_domain_email")
    if extracted.get("support_terms", {}).get("value") and domain:
        identity_signals.append("attributable_support")
    if extracted.get("login_activation_terms", {}).get("value"):
        identity_signals.append("login_or_activation")
    if extracted.get("app_download_terms", {}).get("value"):
        identity_signals.append("app_or_download")
    if extracted.get("checkout_terms", {}).get("value") or extracted.get("payment_terms", {}).get("value"):
        identity_signals.append("checkout_or_payment")
    if extracted.get("legal_entity_indicators", {}).get("value"):
        identity_signals.append("legal_or_corporate_indicator")
    explicit_iptv = term_matches(text_blob, "IPTV") or term_matches(text_blob, "M3U") or term_matches(text_blob, "Xtream")
    robust_iptv_context = bool(explicit_iptv and (len(strong_iptv_signals) >= 2 or identity_signals))
    mixed_weak_context = bool(soft_hospitality_signals and explicit_iptv and not robust_iptv_context)
    hard_irrelevant = bool(dental_signals or hard_hotel_signals or (soft_hospitality_signals and not explicit_iptv))
    requires_context_review = bool(soft_hospitality_signals and explicit_iptv and not hard_hotel_signals and not dental_signals)
    fields = {
        "hard_hotel_signals": hard_hotel_signals,
        "soft_hospitality_signals": soft_hospitality_signals,
        "dental_signals": dental_signals,
        "strong_iptv_signals": strong_iptv_signals,
        "identity_signals": identity_signals,
        "robust_iptv_context": robust_iptv_context,
        "mixed_weak_context": mixed_weak_context,
        "hard_irrelevant": hard_irrelevant,
        "requires_context_review": requires_context_review,
    }
    return fields


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
    fields = {
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
    fields["noise_context"] = observation(assess_noise_context(text_blob, canonical, fields), "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob)
    return fields


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
    noise_context = extracted.get("noise_context", {}).get("value") or assess_noise_context(text_blob, canonical, extracted)
    hard_irrelevant = bool(noise_context.get("hard_irrelevant"))
    contextual_review = bool(noise_context.get("requires_context_review"))
    robust_iptv_context = bool(noise_context.get("robust_iptv_context"))
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
    if brand_signal and iptv_signal and not hard_irrelevant:
        signals.extend(["brand_alias", "iptv_context"])
        if nominal_domain:
            signals.append("domain_name_context")
        signals.extend(infrastructure_signals)
        if confirmed_reseller and infrastructure_signals:
            roles.append(role("POSSIBLE_MASTER_DISTRIBUTOR", "MEDIUM", "reseller program plus infrastructure signals; not officiality", observation(signals, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob)))
        elif not confirmed_reseller and not promotional_source and nominal_domain and len(infrastructure_signals) >= 1 and (not contextual_review or robust_iptv_context):
            roles.append(role("POSSIBLE_BRAND_OPERATOR", "MEDIUM", "nominal domain plus attributable brand/IPTV and infrastructure signals; not officiality", observation(signals, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob)))
    if hard_irrelevant:
        roles.append(role("HOMONYM_OR_IRRELEVANT", "HIGH", "hard hotel/IHG/dental or clearly non-IPTV hospitality signal observed", observation(noise_context, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob)))
    elif contextual_review:
        roles.append(role("REQUIRES_CONTEXT_REVIEW", "UNRESOLVED", "soft hospitality context coexists with IPTV signals; manual context review required", observation(noise_context, "EXTRACTED_FROM_CONTENT", "content/raw_content", text_blob)))
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
        "REQUIRES_CONTEXT_REVIEW",
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
            '(\"Voco TV\" OR VocoTV OR \"Voco IPTV\") IPTV (domain OR website OR portal OR \"official site\" OR \"new domain\" OR \"alternative domain\") -IHG -\"InterContinental Hotels Group\" -hotel -hotels -hospitality -\"hotel-online\" -\"voco.dental\" -dental -dentist -dentistry',
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


def query_length_status(query: QuerySpec) -> dict[str, Any]:
    length = len(query.exact_query)
    return {
        "query_id": query.query_id,
        "query_length": length,
        "maximum_query_length": MAXIMUM_QUERY_LENGTH,
        "query_length_valid": length <= MAXIMUM_QUERY_LENGTH,
    }


def validate_query_lengths(plan: list[QuerySpec]) -> tuple[bool, list[dict[str, Any]]]:
    statuses = [query_length_status(query) for query in plan]
    return all(item["query_length_valid"] for item in statuses), statuses


def require_valid_query_lengths(plan: list[QuerySpec]) -> list[dict[str, Any]]:
    valid, statuses = validate_query_lengths(plan)
    if not valid:
        invalid = [item for item in statuses if not item["query_length_valid"]]
        raise ValueError(f"Query length exceeds {MAXIMUM_QUERY_LENGTH} characters: {json.dumps(invalid, ensure_ascii=True)}")
    return statuses


def validate_query_plan(plan: list[QuerySpec]) -> tuple[bool, list[dict[str, Any]]]:
    checks = []

    def add(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    ids = [q.query_id for q in plan]
    discovery = [q for q in plan if q.included_in_discovery_metrics]
    controls = [q for q in plan if not q.included_in_discovery_metrics]
    minimum_ok, minimum_detail = validate_minimum_methodological_plan(plan)
    add("total_queries_within_methodological_budget", 6 <= len(plan) <= RECOMMENDED_TOTAL_QUERIES, len(plan))
    add("discovery_queries_within_4_to_8", 4 <= len(discovery) <= RECOMMENDED_DISCOVERY_QUERIES, len(discovery))
    add("control_queries_is_2", len(controls) == 2, len(controls))
    add("query_ids_unique", len(set(ids)) == len(ids), ids)
    add("execution_order_is_unique_and_sorted", [q.execution_order for q in plan] == sorted({q.execution_order for q in plan}), [q.execution_order for q in plan])
    add("controls_excluded_from_discovery_metrics", all(not q.included_in_discovery_metrics for q in controls), [q.query_id for q in controls])
    add("required_controls_present", {"voco_ctrl_01_known_vocotv_ai", "voco_ctrl_02_negative_noise"}.issubset(set(ids)), ids)
    add("minimum_methodological_plan_valid", minimum_ok, minimum_detail)
    query_lengths_ok, query_lengths = validate_query_lengths(plan)
    add("all_query_lengths_within_tavily_limit", query_lengths_ok, query_lengths)
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
            normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": f"https://dup{i}.vocotv.org", "title": "Voco TV IPTV", "content": "support@vocotv.org login"}, 3),
        ]
        mark_duplicates(batch)
        duplicate_batches.append(batch)
    add("stop_after_three_high_duplicate_rates", should_stop_after_query(duplicate_batches, 4, 10)[0], should_stop_after_query(duplicate_batches, 4, 10))
    expected_skips = [query.query_id for query in plan if query.included_in_discovery_metrics and query.execution_order > 4]
    add("early_stop_skips_discovery_keeps_controls", discovery_skips_after_early_stop(plan, "voco_df_04_apps_login") == expected_skips and controls_after_early_stop(plan, "voco_df_04_apps_login") == ["voco_ctrl_01_known_vocotv_ai", "voco_ctrl_02_negative_noise"], {"skips": discovery_skips_after_early_stop(plan, "voco_df_04_apps_login"), "controls": controls_after_early_stop(plan, "voco_df_04_apps_login")})
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
    query_lengths_ok, query_lengths = validate_query_lengths(plan)
    q1_length = next(item["query_length"] for item in query_lengths if item["query_id"] == "voco_df_01_identity_variants")
    add("all_ten_queries_within_400_characters", query_lengths_ok and len(query_lengths) == len(plan), query_lengths)
    add("q1_preferably_within_300_characters", q1_length <= 300, q1_length)
    add("q1_does_not_literalize_vocotv_ai", "vocotv.ai" not in next(query.exact_query for query in plan if query.query_id == "voco_df_01_identity_variants").lower(), None)
    oversized_query = QuerySpec(**{**asdict(discovery_query), "exact_query": "x" * 401})
    counters_before_length = (CREDENTIAL_READS, TAVILY_CLIENT_INSTANTIATIONS, NETWORK_CALLS, TAVILY_SEARCH_CALLS)
    oversized_rejected = False
    try:
        require_valid_query_lengths([oversized_query])
    except ValueError:
        oversized_rejected = True
    add("oversized_query_rejected_before_side_effects", oversized_rejected and counters_before_length == (CREDENTIAL_READS, TAVILY_CLIENT_INSTANTIATIONS, NETWORK_CALLS, TAVILY_SEARCH_CALLS), None)
    add("query_too_long_classified_non_retryable", classify_search_error("Query is too long. Max query length is 400 characters.") == "NON_RETRYABLE_ERROR", None)
    add("transient_timeout_classified_retryable", classify_search_error("temporary connection timeout") == "RETRYABLE_TRANSIENT_ERROR", None)
    class SyntheticTooLongClient:
        def __init__(self) -> None:
            self.calls = 0
        def search(self, **_kwargs: Any) -> dict[str, Any]:
            self.calls += 1
            raise RuntimeError("Query is too long. Max query length is 400 characters.")
    synthetic_client = SyntheticTooLongClient()
    counters_before_retry_test = (NETWORK_CALLS, TAVILY_SEARCH_CALLS)
    _response, _error, synthetic_attempts, synthetic_error_class, _records = search_with_retry_policy(synthetic_client, discovery_query, Args)
    add("query_too_long_only_one_attempt", synthetic_attempts == 1 and synthetic_client.calls == 1 and synthetic_error_class == "NON_RETRYABLE_ERROR", {"attempts": synthetic_attempts, "calls": synthetic_client.calls})
    globals()["NETWORK_CALLS"], globals()["TAVILY_SEARCH_CALLS"] = counters_before_retry_test
    low_precision_metrics = {"raw_result_count_discovery": 10, "relevant_domain_precision": 0.1518, "spontaneous_vocotv_ai_recovery": "FALSE", "new_candidate_domain_count": 14, "new_useful_relationship_count": 129}
    add("low_precision_cannot_discovery_pass", evaluate_discovery(low_precision_metrics)["verdict"] != "DISCOVERY_PASS", evaluate_discovery(low_precision_metrics))
    add("technical_failure_forces_incomplete_discovery", evaluate_discovery(low_precision_metrics, technical_failure=True, query_count_discovery_planned=8, query_count_discovery_completed=7)["verdict"] == "DISCOVERY_INCOMPLETE_TECHNICAL_FAILURE", None)
    add("technical_failure_forces_incomplete_utility", evaluate_v3_utility([], low_precision_metrics, technical_failure=True, query_count_discovery_planned=8, query_count_discovery_completed=7)["verdict"] == "V3_UTILITY_INCOMPLETE_TECHNICAL_FAILURE", None)
    add("term_boundaries", contains_any("mobile application unofficial promo reseller panel hotel-online odontologia", ["app", "official", "unofficial", "promo", "reseller panel", "hotel-online", "odontología"]) == ["unofficial", "promo", "reseller panel", "hotel-online", "odontología"], contains_any("mobile application unofficial promo reseller panel hotel-online odontologia", ["app", "official", "unofficial", "promo", "reseller panel", "hotel-online", "odontología"]))
    retained_noise = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "https://vocotv.org", "title": "Voco TV IPTV", "content": "Voco TV IPTV hotel dental support@vocotv.org login"}, 1)
    retained_noise.role_candidates = [role("POSSIBLE_BRAND_OPERATOR", "MEDIUM", "forced retained candidate", observation(["brand_alias", "iptv_context"], "DIRECTLY_OBSERVED", "test")) | {"primary_role_candidate": True}]
    add("safety_hotel_dental", evaluate_safety([retained_noise], plan)["verdict"] == "SAFETY_FAIL", None)
    inferred_result = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "https://vocotv.org", "title": "Voco TV IPTV", "content": "Voco TV IPTV support@vocotv.org login"}, 1)
    inferred_result.role_candidates = [role("POSSIBLE_BRAND_OPERATOR", "MEDIUM", "forced inferred", observation(["brand_alias"], "INFERRED", "test")) | {"primary_role_candidate": True}]
    add("safety_inference_primary_fails", evaluate_safety([inferred_result], plan)["verdict"] == "SAFETY_FAIL", None)
    add("manifest_counters_dry_run", build_manifest(Args, "synthetic", "DRY_RUN", build_paths_for_run_dir(Path("dry_run_synthetic")), plan, True, True)["credential_reads"] == 0 and build_manifest(Args, "synthetic", "DRY_RUN", build_paths_for_run_dir(Path("dry_run_synthetic")), plan, True, True)["tavily_search_calls"] == 0, None)
    minimum_ids = [query.query_id for query in plan if query.phase == "A" or (query.phase == "B" and query.execution_order <= 4) or not query.included_in_discovery_metrics]
    minimum_plan = [query for query in plan if query.query_id in minimum_ids]
    add("minimum_methodological_plan_valid", validate_minimum_methodological_plan(minimum_plan)[0], minimum_ids)
    add("late_queries_cannot_bypass_minimum", not validate_minimum_methodological_plan([query for query in plan if query.phase in {"C", "control"}])[0], None)
    add("one_phase_b_is_insufficient", not validate_minimum_methodological_plan([query for query in plan if query.phase == "A" or query.query_id == "voco_df_03_contact_support" or query.phase == "control"])[0], None)
    add("four_discovery_without_all_phase_a_rejected", not validate_minimum_methodological_plan([query for query in plan if query.query_id in {"voco_df_02_commercial_sales", "voco_df_03_contact_support", "voco_df_04_apps_login", "voco_df_05_checkout_payment_infra", "voco_ctrl_01_known_vocotv_ai", "voco_ctrl_02_negative_noise"}])[0], None)
    add("controls_required_for_executable_plan", not validate_minimum_methodological_plan([query for query in plan if query.included_in_discovery_metrics])[0], None)
    unknown_rejected = False
    try:
        filter_plan(plan, "unknown_query", None)
    except ValueError:
        unknown_rejected = True
    add("unknown_query_ids_rejected", unknown_rejected, None)
    stop_phase_a_rejected = False
    try:
        filter_plan(plan, None, "A")
    except ValueError:
        stop_phase_a_rejected = True
    add("stop_after_phase_a_cannot_bypass_minimum", stop_phase_a_rejected, None)
    add("stop_after_phase_b_satisfies_minimum", validate_minimum_methodological_plan(filter_plan(plan, None, "B"))[0], None)

    def synthetic_noise(index: int, content: str) -> NormalizedResult:
        return normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": f"https://noise-{index}.vocotv.example", "title": "Synthetic", "content": content}, 1)

    exactly_quarter = [synthetic_noise(1, "dental clinic"), synthetic_noise(2, "IPTV plans login"), synthetic_noise(3, "IPTV plans login"), synthetic_noise(4, "IPTV plans login")]
    above_quarter = [synthetic_noise(11, "dental clinic"), synthetic_noise(12, "IHG careers hotel"), synthetic_noise(13, "IPTV plans login"), synthetic_noise(14, "IPTV plans login"), synthetic_noise(15, "IPTV plans login")]
    contextual_hotel = [synthetic_noise(21, "hospitality IPTV subscription plans support login support@noise-21.example")]
    add("retained_noise_exactly_0_25_does_not_stop", evaluate_early_stop([[item] for item in exactly_quarter], 4, 10)["stop"] is False, calculate_retained_noise_provisional(exactly_quarter))
    noise_decision = evaluate_early_stop([[item] for item in above_quarter], 4, 10)
    add("retained_noise_0_40_stops", noise_decision["stop"] and noise_decision["reason"] == "EARLY_STOP_RETAINED_NOISE_THRESHOLD", noise_decision)
    add("retained_noise_zero_denominator_is_null", calculate_retained_noise_provisional([])["retained_noise_rate_provisional"] is None, calculate_retained_noise_provisional([]))
    add("contextual_hotel_not_provisional_noise", calculate_retained_noise_provisional(contextual_hotel)["retained_noise_numerator"] == 0, calculate_retained_noise_provisional(contextual_hotel))
    add("retained_noise_does_not_stop_before_minimum", evaluate_early_stop([[item] for item in above_quarter[:3]], 4, 10)["stop"] is False, None)

    ihg_result = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "https://ihg.example", "title": "IHG careers", "content": "Voco hotel hospitality careers"}, 1)
    hotel_online_result = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "https://hotel-online.example", "title": "hotel-online", "content": "lodging publication"}, 1)
    hospitality_iptv = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "https://vocotv.org", "title": "Voco TV", "content": "hospitality IPTV subscription plans login support support@vocotv.org"}, 1)
    weak_hotel_iptv = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "https://mixed.example", "title": "Hotel TV", "content": "hotel IPTV"}, 1)
    dental_result = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "https://voco.dental", "title": "Voco Dental", "content": "dentistry"}, 1)
    deployment_result = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "https://deployment.example", "title": "Hotel TV deployment", "content": "hospitality IPTV channels VOD player deployment"}, 1)
    add("ihg_careers_is_homonym", "HOMONYM_OR_IRRELEVANT" in [item["role_candidate"] for item in ihg_result.role_candidates], ihg_result.role_candidates)
    add("hotel_online_is_homonym", "HOMONYM_OR_IRRELEVANT" in [item["role_candidate"] for item in hotel_online_result.role_candidates], hotel_online_result.role_candidates)
    add("hospitality_strong_iptv_not_homonym", "HOMONYM_OR_IRRELEVANT" not in [item["role_candidate"] for item in hospitality_iptv.role_candidates] and "REQUIRES_CONTEXT_REVIEW" in [item["role_candidate"] for item in hospitality_iptv.role_candidates], hospitality_iptv.role_candidates)
    add("weak_hotel_iptv_requires_review_not_operator", "REQUIRES_CONTEXT_REVIEW" in [item["role_candidate"] for item in weak_hotel_iptv.role_candidates] and "POSSIBLE_BRAND_OPERATOR" not in [item["role_candidate"] for item in weak_hotel_iptv.role_candidates], weak_hotel_iptv.role_candidates)
    add("voco_dental_is_homonym", "HOMONYM_OR_IRRELEVANT" in [item["role_candidate"] for item in dental_result.role_candidates], dental_result.role_candidates)
    add("hotel_tv_deployment_not_automatic_homonym", "HOMONYM_OR_IRRELEVANT" not in [item["role_candidate"] for item in deployment_result.role_candidates], deployment_result.role_candidates)

    trace_valid = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "https://vocotv.org", "title": "Voco TV IPTV", "content": "IPTV plans login support@vocotv.org"}, 1)
    add("traceability_valid_passes", evaluate_safety([trace_valid], plan)["safety_gate_results"]["TRACEABILITY_COMPLETE"], None)
    for invalid_name, invalid_value in [("empty", ""), ("spaces", "   "), ("control", "bad\nquery")]:
        invalid_trace = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": f"https://trace-{invalid_name}.example", "title": "Voco TV IPTV", "content": "IPTV plans login"}, 1)
        invalid_trace.query_id = invalid_value
        add(f"traceability_query_id_{invalid_name}_fails", not evaluate_safety([invalid_trace], plan)["safety_gate_results"]["TRACEABILITY_COMPLETE"], None)
    empty_evidence = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "https://empty-evidence.example", "title": "", "content": ""}, 1)
    empty_evidence.directly_observed_fields = {}
    add("traceability_empty_observable_evidence_fails", not evaluate_safety([empty_evidence], plan)["safety_gate_results"]["TRACEABILITY_COMPLETE"], None)
    empty_url = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "", "title": "Voco TV IPTV", "content": "IPTV plans login"}, 1)
    add("traceability_empty_source_url_fails", not evaluate_safety([empty_url], plan)["safety_gate_results"]["TRACEABILITY_COMPLETE"], None)
    mixed_invalid = normalize_tavily_result("synthetic", discovery_query, DEFAULT_BRAND, {"url": "https://vocotv.org", "title": "Voco TV IPTV second", "content": "IPTV plans login"}, 2)
    mixed_invalid.query_id = ""
    add("traceability_mixed_valid_and_empty_ids_fails", not evaluate_safety([trace_valid, mixed_invalid], plan)["safety_gate_results"]["TRACEABILITY_COMPLETE"], None)
    # Keep synthetic filesystem checks in a fixed workspace path. Some managed
    # Windows environments deny access to randomly named TemporaryDirectory
    # children and make NamedTemporaryFile retry indefinitely.
    tmp_dir = PROJECT_ROOT / ".tmp_domain_family_selftest"
    if tmp_dir.exists():
        raise RuntimeError(f"Self-test directory already exists: {tmp_dir}")
    tmp_dir.mkdir()
    try:
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

        synthetic_resume_dir = tmp_dir / "run_resume_history"
        synthetic_paths = build_paths_for_run_dir(synthetic_resume_dir)
        synthetic_resume_dir.mkdir()
        q1, q2, q3 = plan[0], plan[1], plan[2]
        synthetic_checkpoint = {
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "queries": {
                q1.query_id: {"status": "COMPLETED", "result_count": 1},
                q2.query_id: {"status": "COMPLETED", "result_count": 1},
                q3.query_id: {"status": "PENDING", "result_count": 0},
            },
        }
        historical_source_1 = {"url": "https://history-one.vocotv.org", "title": "Voco TV IPTV", "content": "IPTV plans login support"}
        historical_source_2 = {"url": "https://history-two.vocotv.org", "title": "Voco TV IPTV", "content": "IPTV app channels VOD support"}
        append_jsonl(synthetic_paths["raw_results"], {"run_id": "resume", "query_id": q1.query_id, "result_position": 1, "source_data": historical_source_1})
        append_jsonl(synthetic_paths["raw_results"], {"run_id": "resume", "query_id": q2.query_id, "result_position": 1, "source_data": historical_source_2})
        append_jsonl(synthetic_paths["query_log"], {"query_id": q1.query_id, "status": "COMPLETED"})
        append_jsonl(synthetic_paths["query_log"], {"query_id": q2.query_id, "status": "COMPLETED"})
        rebuilt, rebuild_detail = rebuild_resume_history(synthetic_paths, synthetic_checkpoint, plan, DEFAULT_BRAND, "resume")
        add("resume_rebuilds_historical_raw_results", len(rebuilt) == 2 and rebuild_detail["resume_historical_result_count"] == 2, rebuild_detail)
        new_resume_result = normalize_tavily_result("resume", q3, DEFAULT_BRAND, {"url": "https://history-three.vocotv.org", "title": "Voco TV IPTV", "content": "IPTV subscription activation support"}, 1)
        combined, removed = combine_normalized_results(rebuilt, [new_resume_result])
        add("resume_combines_historical_and_new", len(combined) == 3 and removed == 0, None)
        add("resume_combined_metrics_include_all_results", calculate_metrics(combined, plan, BASELINE_DOMAINS)["raw_result_count_discovery"] == 3, calculate_metrics(combined, plan, BASELINE_DOMAINS))
        add("resume_combined_family_includes_all_results", len(build_domain_family(combined, DEFAULT_BRAND, plan)["brand_family"]["candidate_domains"]) >= 3, None)
        combined_with_duplicate, removed_duplicate = combine_normalized_results(rebuilt, [rebuilt[0], new_resume_result])
        add("resume_deduplicates_repeated_historical_result", len(combined_with_duplicate) == 3 and removed_duplicate == 1, removed_duplicate)
        second_combined, second_removed = combine_normalized_results(combined, [])
        add("resume_combination_is_idempotent", [item.result_id for item in second_combined] == [item.result_id for item in combined] and second_removed == 0 and calculate_metrics(second_combined, plan, BASELINE_DOMAINS) == calculate_metrics(combined, plan, BASELINE_DOMAINS), None)
        zero_checkpoint = {"schema_version": CHECKPOINT_SCHEMA_VERSION, "queries": {q1.query_id: {"status": "COMPLETED", "result_count": 0}}}
        zero_dir = tmp_dir / "run_resume_zero"
        zero_paths = build_paths_for_run_dir(zero_dir)
        zero_dir.mkdir()
        zero_paths["raw_results"].write_text("", encoding="utf-8")
        append_jsonl(zero_paths["query_log"], {"query_id": q1.query_id, "status": "COMPLETED"})
        zero_rebuilt, _zero_detail = rebuild_resume_history(zero_paths, zero_checkpoint, plan, DEFAULT_BRAND, "zero")
        add("resume_completed_zero_results_preserved", zero_rebuilt == [], None)
        missing_raw_failed = False
        missing_dir = tmp_dir / "run_resume_missing_raw"
        missing_paths = build_paths_for_run_dir(missing_dir)
        missing_dir.mkdir()
        append_jsonl(missing_paths["query_log"], {"query_id": q1.query_id, "status": "COMPLETED"})
        try:
            rebuild_resume_history(missing_paths, zero_checkpoint, plan, DEFAULT_BRAND, "missing")
        except ValueError:
            missing_raw_failed = True
        add("resume_missing_raw_fails_safe", missing_raw_failed, None)
        corrupt_raw_failed = False
        corrupt_dir = tmp_dir / "run_resume_corrupt_raw"
        corrupt_paths = build_paths_for_run_dir(corrupt_dir)
        corrupt_dir.mkdir()
        corrupt_paths["raw_results"].write_text('{"ok": true}\n{"bad":\n{"ok": false}\n', encoding="utf-8")
        append_jsonl(corrupt_paths["query_log"], {"query_id": q1.query_id, "status": "COMPLETED"})
        try:
            rebuild_resume_history(corrupt_paths, zero_checkpoint, plan, DEFAULT_BRAND, "corrupt")
        except ValueError:
            corrupt_raw_failed = True
        add("resume_intermediate_raw_corruption_fails_safe", corrupt_raw_failed, None)

        repair_dir = tmp_dir / "run_repair_fixture"
        repair_paths = build_paths_for_run_dir(repair_dir)
        repair_dir.mkdir()
        class RepairArgs(Args):
            execute = True
            confirm_credit_use = True
            repair_failed_run_dir = str(repair_dir)
            repair_query_id = "voco_df_01_identity_variants"
        repair_manifest = build_manifest(RepairArgs, "repair-fixture", "EXECUTE", repair_paths, plan, True, True)
        write_json(repair_paths["execution_manifest"], repair_manifest)
        repair_checkpoint = {"schema_version": CHECKPOINT_SCHEMA_VERSION, "queries": {}}
        for repair_query in plan:
            repair_checkpoint["queries"][repair_query.query_id] = {
                "status": "FAILED" if repair_query.query_id == RepairArgs.repair_query_id else "CONTROL_COMPLETED" if repair_query.phase == "control" else "COMPLETED",
                "attempts": 3 if repair_query.query_id == RepairArgs.repair_query_id else 1,
                "result_count": 0,
                "execution_compatibility_hash": "legacy-q1-hash" if repair_query.query_id == RepairArgs.repair_query_id else query_compatibility_hash(repair_query, RepairArgs),
            }
        save_checkpoint(repair_paths["checkpoint"], repair_checkpoint)
        repair_valid = False
        try:
            _rd, _rm, repaired_checkpoint, _rp, repair_info = validate_repair_failed_run_dir(RepairArgs, plan)
            repair_valid = repaired_checkpoint["queries"][RepairArgs.repair_query_id]["status"] == "PENDING" and repair_info["previous_query_hash"] == "legacy-q1-hash" and repair_info["repair_reason"] == "QUERY_LENGTH_LIMIT" and repair_info["prior_attempts"] == 3
        except Exception:
            repair_valid = False
        add("repair_accepts_only_explicit_failed_q1", repair_valid, None)
        class CompletedRepairArgs(RepairArgs):
            repair_query_id = "voco_df_02_commercial_sales"
        completed_repair_rejected = False
        try:
            validate_repair_failed_run_dir(CompletedRepairArgs, plan)
        except ValueError:
            completed_repair_rejected = True
        add("repair_rejects_completed_query", completed_repair_rejected, None)
        incompatible_checkpoint = json.loads(json.dumps(repair_checkpoint))
        incompatible_checkpoint["queries"]["voco_df_02_commercial_sales"]["execution_compatibility_hash"] = "changed-completed-query"
        save_checkpoint(repair_paths["checkpoint"], incompatible_checkpoint)
        completed_change_rejected = False
        try:
            validate_repair_failed_run_dir(RepairArgs, plan)
        except ValueError:
            completed_change_rejected = True
        add("repair_rejects_hash_change_in_completed_query", completed_change_rejected, None)
    finally:
        shutil.rmtree(tmp_dir)
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
                    "source_field": "url/title/content",
                    "result_id": result.result_id,
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


def evaluate_safety(results: list[NormalizedResult], plan: list[QuerySpec], execution_incomplete: bool = False) -> dict[str, Any]:
    findings = []
    traceability_failures: list[dict[str, Any]] = []
    gate_results: dict[str, bool] = {
        "automatic_officiality_absent": True,
        "controls_not_in_discovery_metrics": True,
        "hotel_ihg_noise_not_retained": True,
        "dental_noise_not_retained": True,
        "inference_not_primary_positive_evidence": True,
        "candidate_traceability_present": True,
        "TRACEABILITY_COMPLETE": True,
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
    for result in results:
        missing = []
        if not is_nonempty_identifier(result.query_id):
            missing.append("query_id")
        if not is_nonempty_identifier(result.result_id):
            missing.append("result_id")
        if not result.canonical_url or canonicalize_url(result.canonical_url).get("validation_error"):
            missing.append("source_url")
        observed = result.directly_observed_fields or {}
        if not observed or not any(item.get("value") is not None and item.get("value") != "" and item.get("value") != [] and item.get("value") != {} for item in observed.values() if isinstance(item, dict)):
            missing.append("observable_evidence")
        if missing:
            traceability_failures.append({"result_id": result.result_id, "invalid_or_missing_fields": missing})
    for candidate in candidates:
        if candidate.get("is_relevant_family_candidate") and candidate.get("hotel_noise_retained"):
            gate_results["hotel_ihg_noise_not_retained"] = False
            findings.append(f"hotel/IHG signal retained as IPTV candidate: {candidate['domain']}")
        if candidate.get("is_relevant_family_candidate") and candidate.get("dental_noise_retained"):
            gate_results["dental_noise_not_retained"] = False
            findings.append(f"dental signal retained as IPTV candidate: {candidate['domain']}")
        valid_query_ids = [value for value in candidate.get("query_ids", []) if is_nonempty_identifier(value)]
        evidence_items = candidate.get("evidence") or []
        valid_evidence = [
            item for item in evidence_items
            if is_nonempty_identifier(item.get("query_id"))
            and item.get("url")
            and canonicalize_url(item.get("url")).get("validation_error") is None
            and isinstance(item.get("observed_signal"), str) and bool(item.get("observed_signal", "").strip())
            and isinstance(item.get("source_field"), str) and bool(item.get("source_field", "").strip())
            and is_nonempty_identifier(item.get("result_id"))
        ]
        invalid_query_entry = len(valid_query_ids) != len(candidate.get("query_ids", []))
        if not valid_query_ids or invalid_query_entry or not candidate.get("evidence_urls") or not valid_evidence:
            gate_results["candidate_traceability_present"] = False
            traceability_failures.append({"domain": candidate["domain"], "invalid_or_missing_fields": ["query_ids/evidence_urls/evidence"]})
    for result in results:
        for role_item in result.role_candidates:
            if role_item.get("primary_role_candidate") and role_item.get("role_candidate") == "POSSIBLE_BRAND_OPERATOR":
                evidence = role_item.get("evidence") or {}
                if evidence.get("observation_type") == "INFERRED":
                    gate_results["inference_not_primary_positive_evidence"] = False
                    findings.append(f"inferred-only operator evidence: {result.canonical_hostname}")
    no_candidate_warning = len(candidates) == 0
    if traceability_failures:
        gate_results["candidate_traceability_present"] = False
        gate_results["TRACEABILITY_COMPLETE"] = False
        findings.append("TRACEABILITY_COMPLETE failed")
    notes = []
    if no_candidate_warning:
        notes.append("SAFETY_PASS_WITH_NO_CANDIDATES: technical safety only; not a discovery success")
    if execution_incomplete:
        notes.append("EXECUTION_INCOMPLETE_TECHNICAL_FAILURE: safety gates do not imply discovery completeness")
    return {
        "verdict": "SAFETY_FAIL" if findings else "SAFETY_PASS",
        "findings": findings,
        "safety_notes": notes,
        "safety_gate_results": gate_results,
        "no_candidate_warning": no_candidate_warning,
        "traceability_failures": traceability_failures,
    }


def evaluate_discovery(metrics: dict[str, Any], technical_failure: bool = False, query_count_discovery_planned: int | None = None, query_count_discovery_completed: int | None = None) -> dict[str, Any]:
    incomplete = bool(technical_failure or (query_count_discovery_planned is not None and query_count_discovery_completed is not None and query_count_discovery_completed < query_count_discovery_planned))
    precision = metrics.get("relevant_domain_precision")
    spontaneous = metrics.get("spontaneous_vocotv_ai_recovery")
    if incomplete:
        verdict = "DISCOVERY_INCOMPLETE_TECHNICAL_FAILURE"
    elif precision is None or precision < 0.70:
        verdict = "DISCOVERY_PARTIAL_LOW_PRECISION" if metrics.get("raw_result_count_discovery", 0) > 0 else "DISCOVERY_FAIL"
    elif spontaneous == "TRUE" or metrics.get("new_candidate_domain_count", 0) >= 1 or metrics.get("new_useful_relationship_count", 0) >= 2:
        verdict = "DISCOVERY_PASS"
    elif metrics.get("raw_result_count_discovery", 0) > 0:
        verdict = "DISCOVERY_PARTIAL"
    else:
        verdict = "DISCOVERY_FAIL"
    return {"verdict": verdict, "basis": f"technical_failure={technical_failure}; completed={query_count_discovery_completed}; planned={query_count_discovery_planned}; relevant_domain_precision={precision}; spontaneous_vocotv_ai_recovery={spontaneous}; no officiality implied"}


def evaluate_v3_utility(results: list[NormalizedResult], metrics: dict[str, Any], technical_failure: bool = False, query_count_discovery_planned: int | None = None, query_count_discovery_completed: int | None = None) -> dict[str, Any]:
    useful = metrics.get("new_useful_relationship_count", 0) or metrics.get("linked_domain_count", 0)
    incomplete = bool(technical_failure or (query_count_discovery_planned is not None and query_count_discovery_completed is not None and query_count_discovery_completed < query_count_discovery_planned))
    if incomplete:
        verdict = "V3_UTILITY_INCOMPLETE_TECHNICAL_FAILURE"
    elif useful >= 2:
        verdict = "V3_UTILITY_PASS"
    elif useful == 1 or results:
        verdict = "V3_UTILITY_PARTIAL"
    else:
        verdict = "V3_UTILITY_FAIL"
    return {"verdict": verdict, "basis": "fingerprints, contacts, support, checkout, app, roles, conflicts, and traceability"}


def calculate_retained_noise_provisional(results: list[NormalizedResult]) -> dict[str, Any]:
    auditable_domains: set[str] = set()
    noise_domains: set[str] = set()
    for result in results:
        if result.query_type != "discovery" or result.is_duplicate or not result.canonical_hostname:
            continue
        if result.directly_observed_fields.get("url_validation_error", {}).get("value"):
            continue
        domain = result.canonical_hostname
        auditable_domains.add(domain)
        context = result.extracted_fields.get("noise_context", {}).get("value") or {}
        if context.get("hard_irrelevant"):
            noise_domains.add(domain)
    denominator = len(auditable_domains)
    numerator = len(noise_domains)
    return {
        "retained_noise_rate_provisional": safe_div(numerator, denominator or None),
        "retained_noise_numerator": numerator,
        "retained_noise_denominator": denominator,
        "retained_noise_domains": sorted(noise_domains),
    }


def evaluate_early_stop(executed_discovery_results: list[list[NormalizedResult]], min_discovery_executed: int, max_discovery_queries: int) -> dict[str, Any]:
    noise = calculate_retained_noise_provisional([result for batch in executed_discovery_results for result in batch])
    decision = {"stop": False, "reason": None, **noise}
    if len(executed_discovery_results) >= max_discovery_queries:
        return {**decision, "stop": True, "reason": "budget_max_reached"}
    if len(executed_discovery_results) < min_discovery_executed:
        return decision
    rate = noise["retained_noise_rate_provisional"]
    if rate is not None and rate > 0.25:
        return {**decision, "stop": True, "reason": "EARLY_STOP_RETAINED_NOISE_THRESHOLD"}
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
            return {**decision, "stop": True, "reason": "duplicate_rate_above_0_50_for_three_discovery_queries"}
        if all(no_new_signal):
            return {**decision, "stop": True, "reason": "three_discovery_queries_without_new_domain_or_relationship"}
    return decision


def should_stop_after_query(executed_discovery_results: list[list[NormalizedResult]], min_discovery_executed: int, max_discovery_queries: int) -> tuple[bool, str | None]:
    decision = evaluate_early_stop(executed_discovery_results, min_discovery_executed, max_discovery_queries)
    return bool(decision["stop"]), decision["reason"]


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


def validate_repair_failed_run_dir(args: argparse.Namespace, plan: list[QuerySpec]) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Path], dict[str, Any]]:
    if not args.repair_failed_run_dir or not args.repair_query_id:
        raise ValueError("Repair requires --repair-failed-run-dir and --repair-query-id")
    run_dir = Path(args.repair_failed_run_dir).resolve()
    if not run_dir.exists() or not run_dir.is_dir():
        raise ValueError(f"Repair run directory does not exist: {run_dir}")
    paths = build_paths_for_run_dir(run_dir)
    if not paths["checkpoint"].exists() or not paths["execution_manifest"].exists():
        raise ValueError("Repair requires an existing checkpoint and execution manifest")
    manifest = json.loads(paths["execution_manifest"].read_text(encoding="utf-8"))
    if manifest.get("mode") != "EXECUTE":
        raise ValueError("Repair source must be an EXECUTE run")
    if manifest.get("parameters", {}).get("brand") != args.brand:
        raise ValueError("Repair brand does not match existing run")
    if manifest.get("design_hash") != file_sha256(DEFAULT_DESIGN_PATH):
        raise ValueError("Repair design hash does not match current design")
    for parameter in ("search_depth", "max_results", "include_raw_content", "include_answer", "timeout"):
        expected = manifest.get("parameters", {}).get(parameter)
        current = {"include_raw_content": True, "include_answer": False}.get(parameter, getattr(args, parameter, None))
        if expected != current:
            raise ValueError(f"Repair parameter mismatch: {parameter}")
    checkpoint = load_checkpoint(paths["checkpoint"])
    plan_by_id = {query.query_id: query for query in plan}
    if args.repair_query_id not in plan_by_id:
        raise ValueError(f"Repair query ID is not in the current plan: {args.repair_query_id}")
    selected_entry = checkpoint.get("queries", {}).get(args.repair_query_id)
    if not selected_entry or selected_entry.get("status") != "FAILED":
        raise ValueError(f"Repair query must currently be FAILED: {args.repair_query_id}")
    for query_id, entry in checkpoint.get("queries", {}).items():
        if query_id not in plan_by_id:
            raise ValueError(f"Checkpoint contains query outside current plan: {query_id}")
        if query_id == args.repair_query_id:
            continue
        if entry.get("status") in {"COMPLETED", "CONTROL_COMPLETED", "SKIPPED_EARLY_STOP"}:
            existing_hash = entry.get("execution_compatibility_hash") or entry.get("query_hash")
            current_hash = query_compatibility_hash(plan_by_id[query_id], args)
            if existing_hash and existing_hash != current_hash:
                raise ValueError(f"Repair rejected change to non-failed query: {query_id}")
    repaired_query = plan_by_id[args.repair_query_id]
    previous_hash = selected_entry.get("execution_compatibility_hash") or selected_entry.get("query_hash")
    repaired_hash = query_compatibility_hash(repaired_query, args)
    repair_details = {
        "repair_mode": True,
        "repair_query_id": args.repair_query_id,
        "previous_query_hash": previous_hash,
        "repaired_query_hash": repaired_hash,
        "repair_reason": "QUERY_LENGTH_LIMIT",
        "prior_attempts": int(selected_entry.get("attempts") or 0),
        "repair_attempts": 0,
    }
    selected_entry.update(
        {
            "status": "PENDING",
            "previous_query_hash": previous_hash,
            "repaired_query_hash": repaired_hash,
            "execution_compatibility_hash": repaired_hash,
            "repair_reason": "QUERY_LENGTH_LIMIT",
            "prior_attempts": repair_details["prior_attempts"],
            "repair_attempts": 0,
        }
    )
    return run_dir, manifest, checkpoint, paths, repair_details


def rebuild_resume_history(
    paths: dict[str, Path],
    checkpoint: dict[str, Any],
    plan: list[QuerySpec],
    brand_name: str,
    run_id: str,
) -> tuple[list[NormalizedResult], dict[str, Any]]:
    if not paths["raw_results"].exists():
        raise ValueError(f"Resume raw results missing: {paths['raw_results']}")
    if not paths["query_log"].exists():
        raise ValueError(f"Resume query log missing: {paths['query_log']}")
    raw_rows, raw_issues = read_jsonl_checked(paths["raw_results"])
    query_log_rows, query_log_issues = read_jsonl_checked(paths["query_log"])
    plan_by_id = {query.query_id: query for query in plan}
    rows_by_query: dict[str, list[dict[str, Any]]] = {}
    for row in raw_rows:
        query_id = row.get("query_id")
        if query_id not in plan_by_id:
            raise ValueError(f"Resume raw result references unknown query: {query_id!r}")
        checkpoint_entry = checkpoint.get("queries", {}).get(query_id)
        if not checkpoint_entry:
            raise ValueError(f"Resume raw result has no checkpoint entry: {query_id}")
        if checkpoint_entry.get("status") not in {"COMPLETED", "CONTROL_COMPLETED"}:
            raise ValueError(f"Resume raw result belongs to non-completed query: {query_id}")
        if not isinstance(row.get("source_data"), dict):
            raise ValueError(f"Resume raw result lacks source_data object: {query_id}")
        rows_by_query.setdefault(query_id, []).append(row)
    for query_id, entry in checkpoint.get("queries", {}).items():
        if entry.get("status") not in {"COMPLETED", "CONTROL_COMPLETED"}:
            continue
        if not any(row.get("query_id") == query_id and row.get("status") in {"COMPLETED", "CONTROL_COMPLETED"} for row in query_log_rows):
            raise ValueError(f"Resume checkpoint has no matching completed query log entry: {query_id}")
        expected = int(entry.get("result_count") or 0)
        actual = len(rows_by_query.get(query_id, []))
        if actual != expected:
            raise ValueError(f"Resume raw/checkpoint result_count mismatch for {query_id}: expected {expected}, found {actual}")
    rebuilt: list[NormalizedResult] = []
    for row in raw_rows:
        query = plan_by_id[row["query_id"]]
        rebuilt.append(
            normalize_tavily_result(
                run_id,
                query,
                brand_name,
                row["source_data"],
                int(row.get("result_position") or 0),
            )
        )
    deduped, duplicates_removed = combine_normalized_results([], rebuilt)
    mark_duplicates(deduped)
    details = {
        "resume_historical_results_loaded": True,
        "resume_historical_result_count": len(deduped),
        "resume_duplicates_removed": duplicates_removed,
        "historical_raw_results_loaded": len(raw_rows),
        "historical_normalized_results_rebuilt": len(deduped),
        "historical_result_count": len(deduped),
        "raw_final_partial_line_issues": raw_issues,
        "query_log_final_partial_line_issues": query_log_issues,
        "prior_normalized_csv_present_but_not_trusted": paths["normalized_results"].exists(),
    }
    return deduped, details


def combine_normalized_results(
    historical_results: list[NormalizedResult],
    new_results: list[NormalizedResult],
) -> tuple[list[NormalizedResult], int]:
    combined: list[NormalizedResult] = []
    seen_result_ids: set[str] = set()
    duplicates_removed = 0
    for result in [*historical_results, *new_results]:
        if result.result_id in seen_result_ids:
            duplicates_removed += 1
            continue
        seen_result_ids.add(result.result_id)
        combined.append(result)
    mark_duplicates(combined)
    return combined, duplicates_removed


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
        "| order | query_id | query_type | phase | category | length | valid | included_in_discovery_metrics | exact_query |",
        "|---:|---|---|---|---|---:|---|---|---|",
    ]
    for query in plan:
        escaped = query.exact_query.replace("|", "\\|")
        length_status = query_length_status(query)
        lines.append(f"| {query.execution_order} | `{query.query_id}` | {query.query_type} | {query.phase} | {query.category} | {length_status['query_length']} | {'yes' if length_status['query_length_valid'] else 'no'} | {'yes' if query.included_in_discovery_metrics else 'no'} | `{escaped}` |")
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
        "resume_historical_results_loaded": False,
        "resume_historical_result_count": 0,
        "resume_new_result_count": 0,
        "resume_combined_result_count": 0,
        "resume_duplicates_removed": 0,
        "historical_raw_results_loaded": 0,
        "historical_normalized_results_rebuilt": 0,
        "historical_result_count": 0,
        "new_result_count": 0,
        "combined_result_count": 0,
        "duplicate_results_removed_on_resume": 0,
        "minimum_phase_requirements_validated": validate_minimum_methodological_plan(plan)[0],
        "retained_noise_rate_provisional": None,
        "retained_noise_numerator": None,
        "retained_noise_denominator": None,
        "traceability_gate_passed": None,
        "repair_mode": bool(getattr(args, "repair_failed_run_dir", None)),
        "repair_failed_run_dir": getattr(args, "repair_failed_run_dir", None),
        "repair_query_id": getattr(args, "repair_query_id", None),
        "query_count_discovery_planned": discovery_count,
        "query_count_discovery_completed": 0,
        "execution_incomplete": None if mode == "DRY_RUN" else True,
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
            "repair_failed_run_dir": getattr(args, "repair_failed_run_dir", None),
            "repair_query_id": getattr(args, "repair_query_id", None),
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
    require_valid_query_lengths(plan)
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
    data.update(query_length_status(query))
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


def validate_minimum_methodological_plan(plan: list[QuerySpec]) -> tuple[bool, dict[str, Any]]:
    full_plan = build_query_plan()
    selected_ids = {query.query_id for query in plan}
    required_phase_a = {query.query_id for query in full_plan if query.included_in_discovery_metrics and query.phase == "A"}
    selected_phase_b = {query.query_id for query in plan if query.included_in_discovery_metrics and query.phase == "B"}
    required_controls = {query.query_id for query in full_plan if not query.included_in_discovery_metrics}
    selected_discovery = {query.query_id for query in plan if query.included_in_discovery_metrics}
    detail = {
        "missing_phase_a_query_ids": sorted(required_phase_a - selected_ids),
        "phase_b_discovery_count": len(selected_phase_b),
        "minimum_phase_b_discovery_count": 2,
        "discovery_count": len(selected_discovery),
        "minimum_discovery_count": 4,
        "missing_control_query_ids": sorted(required_controls - selected_ids),
    }
    ok = not detail["missing_phase_a_query_ids"] and len(selected_phase_b) >= 2 and len(selected_discovery) >= 4 and not detail["missing_control_query_ids"]
    detail["minimum_phase_requirements_validated"] = ok
    return ok, detail


def filter_plan(plan: list[QuerySpec], query_ids: str | None, stop_after_phase: str | None) -> list[QuerySpec]:
    output = plan
    if query_ids:
        wanted = {item.strip() for item in query_ids.split(",") if item.strip()}
        known = {query.query_id for query in plan}
        unknown = sorted(wanted - known)
        if unknown:
            raise ValueError(f"Unknown query IDs: {', '.join(unknown)}")
        output = [query for query in output if query.query_id in wanted]
    if stop_after_phase:
        allowed_phases = {"A": {"A"}, "B": {"A", "B"}, "C": {"A", "B", "C"}, "control": {"A", "B", "C", "control"}}
        phases = allowed_phases.get(stop_after_phase)
        if phases:
            output = [query for query in output if query.phase in phases or query.phase == "control"]
    output = sorted(output, key=lambda q: q.execution_order)
    valid, detail = validate_minimum_methodological_plan(output)
    if not valid:
        raise ValueError(f"Plan does not satisfy minimum methodological requirements: {json.dumps(detail, ensure_ascii=True, sort_keys=True)}")
    return output


def classify_search_error(error: Exception | str) -> str:
    text = normalize_search_text(str(error))
    non_retryable_patterns = [
        "query is too long",
        "query too long",
        "invalid parameter",
        "malformed request",
        "authentication error",
        "unauthorized",
        "unsupported argument",
    ]
    transient_patterns = ["timeout", "timed out", "rate limit", "too many requests", "connection", "temporarily unavailable", "http 500", "http 502", "http 503", "http 504"]
    if any(pattern in text for pattern in non_retryable_patterns):
        return "NON_RETRYABLE_ERROR"
    if any(pattern in text for pattern in transient_patterns):
        return "RETRYABLE_TRANSIENT_ERROR"
    return "NON_RETRYABLE_ERROR"


def search_with_retry_policy(client: Any, query: QuerySpec, args: argparse.Namespace) -> tuple[dict[str, Any] | None, str | None, int, str | None, list[dict[str, Any]]]:
    global NETWORK_CALLS, TAVILY_SEARCH_CALLS
    response: dict[str, Any] | None = None
    error_text: str | None = None
    error_classification: str | None = None
    attempt_records: list[dict[str, Any]] = []
    attempts = 0
    for attempt in range(1, args.max_retries + 1):
        attempts = attempt
        try:
            NETWORK_CALLS += 1
            TAVILY_SEARCH_CALLS += 1
            candidate = client.search(
                query=query.exact_query,
                search_depth=args.search_depth,
                max_results=args.max_results,
                include_raw_content=True,
                include_answer=False,
                timeout=args.timeout,
            )
            response = candidate if isinstance(candidate, dict) else {}
            error_text = None
            error_classification = None
            break
        except Exception as exc:
            error_text = str(exc)
            error_classification = classify_search_error(exc)
            attempt_records.append({"attempt": attempt, "error": error_text, "error_classification": error_classification})
            if error_classification == "NON_RETRYABLE_ERROR":
                break
            if attempt < args.max_retries:
                time.sleep(min(60, 3 * (2 ** (attempt - 1))))
    return response, error_text, attempts, error_classification, attempt_records


def run_execute(args: argparse.Namespace) -> int:
    global CREDENTIAL_READS, TAVILY_CLIENT_INSTANTIATIONS, NETWORK_CALLS, TAVILY_SEARCH_CALLS
    if not execute_barrier_allows(args.execute, args.confirm_credit_use):
        print("Execution refused: --execute and --confirm-credit-use are both required.", file=sys.stderr)
        return 2
    if args.dry_run:
        print("Execution refused: --dry-run and --execute are mutually exclusive.", file=sys.stderr)
        return 2
    plan = filter_plan(build_query_plan(), args.query_ids, args.stop_after_phase)
    require_valid_query_lengths(plan)
    checkpoint_reused = False
    resume_manifest: dict[str, Any] | None = None
    repair_details: dict[str, Any] = {"repair_mode": False}
    historical_results: list[NormalizedResult] = []
    resume_details: dict[str, Any] = {
        "resume_historical_results_loaded": False,
        "resume_historical_result_count": 0,
        "resume_duplicates_removed": 0,
        "historical_raw_results_loaded": 0,
        "historical_normalized_results_rebuilt": 0,
        "historical_result_count": 0,
        "raw_final_partial_line_issues": [],
        "query_log_final_partial_line_issues": [],
    }
    if args.repair_failed_run_dir:
        try:
            run_dir, resume_manifest, checkpoint, paths, repair_details = validate_repair_failed_run_dir(args, plan)
        except Exception as exc:
            print(json.dumps({"status": "FAILED_SAFE_REPAIR_VALIDATION", "error": str(exc)}, ensure_ascii=True), file=sys.stderr)
            return 2
        run_id = str(resume_manifest.get("run_id") or run_dir.name.replace("run_", ""))
        checkpoint_reused = True
        try:
            historical_results, resume_details = rebuild_resume_history(paths, checkpoint, plan, args.brand, run_id)
        except Exception as exc:
            print(json.dumps({"status": "FAILED_SAFE_REPAIR_HISTORY", "error": str(exc)}, ensure_ascii=True), file=sys.stderr)
            return 2
    elif args.resume_run_dir:
        try:
            run_dir, resume_manifest, checkpoint, paths = validate_resume_run_dir(args, plan)
        except Exception as exc:
            print(json.dumps({"status": "FAILED_SAFE_RESUME_VALIDATION", "error": str(exc)}), file=sys.stderr)
            return 2
        run_id = str(resume_manifest.get("run_id") or run_dir.name.replace("run_", ""))
        checkpoint_reused = True
        try:
            historical_results, resume_details = rebuild_resume_history(paths, checkpoint, plan, args.brand, run_id)
        except Exception as exc:
            append_jsonl(paths["errors"], {"run_id": run_id, "status": "FAILED_SAFE_RESUME_HISTORY", "error": str(exc), "timestamp": utc_now()})
            print(json.dumps({"status": "FAILED_SAFE_RESUME_HISTORY", "error": str(exc)}, ensure_ascii=True), file=sys.stderr)
            return 2
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
    normalized_results: list[NormalizedResult] = list(historical_results)
    new_normalized_results: list[NormalizedResult] = []
    query_batches: list[list[NormalizedResult]] = []
    if checkpoint_reused:
        historical_by_query = {query.query_id: [] for query in plan if query.included_in_discovery_metrics}
        for result in historical_results:
            if result.query_id in historical_by_query:
                historical_by_query[result.query_id].append(result)
        for query in plan:
            entry = checkpoint.get("queries", {}).get(query.query_id, {})
            if query.included_in_discovery_metrics and entry.get("status") == "COMPLETED":
                query_batches.append(historical_by_query.get(query.query_id, []))
    technical_failure = False
    early_stop_info: dict[str, Any] | None = None
    discovery_queries_skipped = 0
    controls_executed = 0

    for query in plan:
        if args.repair_failed_run_dir and query.query_id != args.repair_query_id:
            entry = checkpoint.get("queries", {}).get(query.query_id, {})
            if entry.get("status") not in {"COMPLETED", "CONTROL_COMPLETED", "SKIPPED_EARLY_STOP"}:
                append_jsonl(paths["query_log"], log_query(run_id, query, "REPAIR_NOT_SELECTED", 0, 0, None, query_compatibility_hash(query, args)))
            continue
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
        repair_entry_metadata = {}
        if args.repair_failed_run_dir:
            repair_entry_metadata = {key: value for key, value in checkpoint.get("queries", {}).get(query.query_id, {}).items() if key in {"previous_query_hash", "repaired_query_hash", "repair_reason", "prior_attempts", "repair_attempts"}}
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
            **repair_entry_metadata,
        }
        save_checkpoint(paths["checkpoint"], checkpoint)
        if args.repair_failed_run_dir:
            append_jsonl(paths["query_log"], {"run_id": run_id, "query_id": query.query_id, "status": "REPAIR_PREPARED", "timestamp": utc_now(), **repair_details})
        results_for_query: list[NormalizedResult] = []
        response, error_text, attempts, error_classification, attempt_records = search_with_retry_policy(client, query, args)
        checkpoint["queries"][query.query_id]["attempts"] = attempts
        if getattr(args, "repair_failed_run_dir", None):
            checkpoint["queries"][query.query_id]["repair_attempts"] = attempts
        for attempt_record in attempt_records:
            append_jsonl(paths["errors"], {"run_id": run_id, "query_id": query.query_id, "timestamp": utc_now(), **attempt_record})
        raw_results = response.get("results", []) if response is not None else []
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
        final_status = "CONTROL_COMPLETED" if query.phase == "control" and error_text is None else "COMPLETED" if error_text is None else "FAILED"
        checkpoint["queries"][query.query_id].update(
            {
                "status": final_status,
                "completed_at": utc_now(),
                "error": error_text,
                "error_classification": error_classification,
                "result_count": len(results_for_query),
                "query_hash": q_hash,
                "execution_compatibility_hash": compatibility_hash,
            }
        )
        save_checkpoint(paths["checkpoint"], checkpoint)
        log_status = "NON_RETRYABLE_ERROR" if error_classification == "NON_RETRYABLE_ERROR" else final_status
        append_jsonl(paths["query_log"], log_query(run_id, query, log_status, checkpoint["queries"][query.query_id]["attempts"], len(results_for_query), error_text, compatibility_hash))
        normalized_results.extend(results_for_query)
        new_normalized_results.extend(results_for_query)
        if query.phase == "control" and final_status == "CONTROL_COMPLETED":
            controls_executed += 1
        if query.included_in_discovery_metrics:
            query_batches.append(results_for_query)
            mark_duplicates(normalized_results)
            early_stop_decision = evaluate_early_stop(query_batches, min_discovery_executed=4, max_discovery_queries=10)
            stop, reason = bool(early_stop_decision["stop"]), early_stop_decision["reason"]
            if stop:
                early_stop_info = {
                    "stop_reason": reason,
                    "stop_trigger_query_id": query.query_id,
                    "stop_triggered_at": utc_now(),
                    "discovery_queries_completed": len(query_batches),
                    "discovery_queries_skipped": len([q for q in plan if q.included_in_discovery_metrics and q.execution_order > query.execution_order]),
                    "retained_noise_rate_provisional": early_stop_decision["retained_noise_rate_provisional"],
                    "retained_noise_numerator": early_stop_decision["retained_noise_numerator"],
                    "retained_noise_denominator": early_stop_decision["retained_noise_denominator"],
                }
                checkpoint["early_stop"] = early_stop_info
                save_checkpoint(paths["checkpoint"], checkpoint)
                append_jsonl(paths["query_log"], {"run_id": run_id, "status": "STOPPING_DISCOVERY", **early_stop_info})
        if args.pause_seconds > 0:
            time.sleep(args.pause_seconds)
        if final_status == "FAILED":
            technical_failure = True

    normalized_results, combined_duplicates_removed = combine_normalized_results(historical_results, new_normalized_results)
    final_noise_summary = calculate_retained_noise_provisional(normalized_results)
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
    planned_discovery_count = len([query for query in plan if query.included_in_discovery_metrics])
    completed_discovery_count = len([query for query in plan if query.included_in_discovery_metrics and checkpoint.get("queries", {}).get(query.query_id, {}).get("status") == "COMPLETED"])
    execution_incomplete = bool(technical_failure or completed_discovery_count < planned_discovery_count)
    safety = evaluate_safety(normalized_results, plan, execution_incomplete=execution_incomplete)
    discovery = evaluate_discovery(metrics, technical_failure=technical_failure, query_count_discovery_planned=planned_discovery_count, query_count_discovery_completed=completed_discovery_count)
    utility = evaluate_v3_utility(normalized_results, metrics, technical_failure=technical_failure, query_count_discovery_planned=planned_discovery_count, query_count_discovery_completed=completed_discovery_count)
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
            **resume_details,
            "resume_new_result_count": len(new_normalized_results),
            "resume_combined_result_count": len(normalized_results),
            "resume_duplicates_removed": resume_details.get("resume_duplicates_removed", 0) + combined_duplicates_removed,
            "new_result_count": len(new_normalized_results),
            "combined_result_count": len(normalized_results),
            "duplicate_results_removed_on_resume": resume_details.get("resume_duplicates_removed", 0) + combined_duplicates_removed,
            "retained_noise_rate_provisional": final_noise_summary["retained_noise_rate_provisional"],
            "retained_noise_numerator": final_noise_summary["retained_noise_numerator"],
            "retained_noise_denominator": final_noise_summary["retained_noise_denominator"],
            "traceability_gate_passed": safety["safety_gate_results"].get("TRACEABILITY_COMPLETE"),
            "query_count_discovery_planned": planned_discovery_count,
            "query_count_discovery_completed": completed_discovery_count,
            "execution_incomplete": execution_incomplete,
            **repair_details,
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


GENERIC_EXTERNAL_DOMAINS = {
    "wa.me", "wa.link", "api.whatsapp.com", "t.me", "youtube.com", "facebook.com", "web.facebook.com", "instagram.com", "linkedin.com", "x.com", "twitter.com", "t.co", "pin.it", "pinterest.com",
    "apps.apple.com", "play.google.com", "chrome.google.com", "android.com", "apple.com", "amazon.com", "w3.org", "adobe.com", "get.adobe.com", "zoom.us", "vimeo.com",
    "your-m3u-url.com", "your-epg-url.com", "192.168.1.100", "iboplayer.com", "iptvsmarters.com",
}
GENERIC_EXTERNAL_FRAGMENTS = ("googleusercontent.com", "gstatic.com", "flaticon.com", "trustpilot", "doubleclick", "analytics", "onetrust", "cookielaw", "cookiepedia", "adnxs", "mathtag", "adsrvr", "blob.core.windows.net", "cloudflare", "licdn.com", "imgkit.net", "pixlee.com")


def audit_domain_classification(domain: str, role_name: str) -> tuple[str, str]:
    lowered = (domain or "").lower()
    if role_name == "HOMONYM_OR_IRRELEVANT" or any(token in lowered for token in ("ihg", "hotel", "voco.dental")):
        return "HOMONYM_OR_IRRELEVANT", "hotel/IHG/dental or explicit homonym signal"
    if lowered in GENERIC_EXTERNAL_DOMAINS or any(fragment in lowered for fragment in GENERIC_EXTERNAL_FRAGMENTS):
        return "GENERIC_EXTERNAL_NOT_IDENTITY", "social, player, placeholder, CDN, analytics, or shared infrastructure"
    if lowered in BASELINE_DOMAINS:
        return "BASELINE_FAMILY_DOMAIN", "already present in the historical Voco baseline"
    if "voco" in lowered and role_name in {"CONFIRMED_RESELLER", "POSSIBLE_RESELLER", "POSSIBLE_MASTER_DISTRIBUTOR"}:
        return "RESELLER_OR_DISTRIBUTION_SIGNAL", "Voco-related reseller/distribution role; not operator identity"
    if "voco" in lowered:
        return "POTENTIAL_FAMILY_DOMAIN_REVIEW", "Voco-related hostname requiring identity review; no officiality implied"
    if role_name in {"CONFIRMED_RESELLER", "POSSIBLE_RESELLER", "POSSIBLE_MASTER_DISTRIBUTOR"}:
        return "RESELLER_OR_DISTRIBUTION_SIGNAL", "reseller/distribution evidence only"
    return "UNRESOLVED_EXTERNAL_RELATION", "external domain with no independent identity attribution"


def run_offline_audit(args: argparse.Namespace) -> int:
    run_dir = Path(args.audit_run_dir).resolve()
    if not run_dir.exists() or not run_dir.is_dir():
        raise ValueError(f"Audit run directory does not exist: {run_dir}")
    paths = build_paths_for_run_dir(run_dir)
    manifest = json.loads(paths["execution_manifest"].read_text(encoding="utf-8"))
    checkpoint = load_checkpoint(paths["checkpoint"])
    plan = build_query_plan()
    require_valid_query_lengths(plan)
    run_id = str(manifest.get("run_id") or run_dir.name.replace("run_", ""))
    results, rebuild_details = rebuild_resume_history(paths, checkpoint, plan, manifest.get("parameters", {}).get("brand") or DEFAULT_BRAND, run_id)
    mark_duplicates(results)
    discovery_query_ids = {query.query_id for query in plan if query.included_in_discovery_metrics}
    nonduplicate_discovery = [result for result in results if result.query_id in discovery_query_ids and not result.is_duplicate]
    candidates = collect_candidate_domains(nonduplicate_discovery)
    candidate_rows = []
    for candidate in candidates:
        classification, reason = audit_domain_classification(candidate["domain"], candidate.get("role_candidate") or "UNKNOWN_ROLE")
        candidate_rows.append(
            {
                "domain": candidate["domain"],
                "automatic_role_candidate": candidate.get("role_candidate"),
                "automatic_relevant_family_candidate": candidate.get("is_relevant_family_candidate"),
                "automatic_signal_count": candidate.get("signal_count"),
                "is_baseline_domain": candidate["domain"] in BASELINE_DOMAINS,
                "is_one_of_14_automatic_new_candidates": bool(candidate.get("is_relevant_family_candidate") and candidate["domain"] not in BASELINE_DOMAINS),
                "offline_audit_classification": classification,
                "offline_audit_reason": reason,
                "identity_confirmed": False,
                "query_ids": candidate.get("query_ids"),
                "evidence_urls": candidate.get("evidence_urls"),
            }
        )
    relationship_map: dict[str, dict[str, Any]] = {}
    for result in nonduplicate_discovery:
        for target in result.extracted_fields.get("linked_domains", {}).get("value", []):
            relationship_id = build_relationship_id(result.canonical_hostname, "linked_domain", target, result.canonical_url)
            classification, reason = audit_domain_classification(target, "UNKNOWN_ROLE")
            relationship_map.setdefault(
                relationship_id,
                {
                    "relationship_id": relationship_id,
                    "source_domain": result.canonical_hostname,
                    "target_domain": target,
                    "source_url": result.canonical_url,
                    "query_id": result.query_id,
                    "offline_audit_classification": classification,
                    "offline_audit_reason": reason,
                    "identity_useful": classification in {"BASELINE_FAMILY_DOMAIN", "POTENTIAL_FAMILY_DOMAIN_REVIEW", "RESELLER_OR_DISTRIBUTION_SIGNAL"},
                    "officiality_confirmed": False,
                },
            )
    relationship_rows = list(relationship_map.values())
    metrics = calculate_metrics(results, plan, BASELINE_DOMAINS)
    planned_discovery = len([query for query in plan if query.included_in_discovery_metrics])
    completed_discovery = len([query for query in plan if query.included_in_discovery_metrics and checkpoint.get("queries", {}).get(query.query_id, {}).get("status") == "COMPLETED"])
    technical_failure = completed_discovery < planned_discovery or any(entry.get("status") == "FAILED" for entry in checkpoint.get("queries", {}).values())
    audited_new_candidates = [row for row in candidate_rows if row["is_one_of_14_automatic_new_candidates"]]
    generic_new_candidates = [row for row in audited_new_candidates if row["offline_audit_classification"] == "GENERIC_EXTERNAL_NOT_IDENTITY"]
    useful_relationships = [row for row in relationship_rows if row["identity_useful"]]
    generic_relationships = [row for row in relationship_rows if not row["identity_useful"]]
    recalculated = {
        **metrics,
        "query_count_discovery_planned": planned_discovery,
        "query_count_discovery_completed": completed_discovery,
        "technical_failure": technical_failure,
        "automatic_candidate_domain_denominator": len(candidates),
        "automatic_relevant_candidate_count": len([row for row in candidate_rows if row["automatic_relevant_family_candidate"]]),
        "automatic_new_candidate_count": len(audited_new_candidates),
        "automatic_new_candidates_generic_external_count": len(generic_new_candidates),
        "unique_relationship_count_recalculated": len(relationship_rows),
        "identity_useful_relationship_count_offline_audit": len(useful_relationships),
        "generic_or_unresolved_relationship_count_offline_audit": len(generic_relationships),
        "unresolved_identity_rate_explanation": "The prior 0.0 is an artifact of inherited source-level roles and signal_count; it does not demonstrate resolved domain identity.",
        "discovery_evaluation": evaluate_discovery(metrics, technical_failure=technical_failure, query_count_discovery_planned=planned_discovery, query_count_discovery_completed=completed_discovery),
        "v3_utility_evaluation": evaluate_v3_utility(results, metrics, technical_failure=technical_failure, query_count_discovery_planned=planned_discovery, query_count_discovery_completed=completed_discovery),
        "v3_utility_pass_defensible": False,
        "rebuild_details": rebuild_details,
    }
    output_dir = Path(args.audit_output_dir).resolve() if args.audit_output_dir else run_dir.parent / f"audit_run_{run_id}"
    if output_dir.exists():
        raise ValueError(f"Audit output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    write_csv(output_dir / "current_candidates_audit.csv", candidate_rows)
    write_csv(output_dir / "current_relationships_audit.csv", relationship_rows)
    write_json(output_dir / "current_metrics_recalculated.json", recalculated)
    report_lines = [
        f"# Offline audit of run {run_id}", "", "No network, Tavily, credit use, or officiality determination was performed.", "",
        "## Execution completeness", "", f"- discovery planned: {planned_discovery}", f"- discovery completed: {completed_discovery}", f"- technical failure: {technical_failure}",
        f"- spontaneous_vocotv_ai_recovery: {metrics.get('spontaneous_vocotv_ai_recovery')}", f"- relevant_domain_precision: {metrics.get('relevant_domain_precision')}", "",
        "## Candidate audit", "", f"- auditable candidate denominator: {len(candidates)}", f"- automatically relevant candidates: {recalculated['automatic_relevant_candidate_count']}",
        f"- automatic new candidates: {len(audited_new_candidates)}", f"- automatic new candidates that are generic external infrastructure: {len(generic_new_candidates)}", "",
        "The automatic candidate rule propagates source-page brand context to linked domains. Therefore social links, shared players, placeholders, CDN assets and infrastructure can be counted as relevant without independent identity attribution.", "",
        "## Relationship audit", "", f"- unique relationships recalculated: {len(relationship_rows)}", f"- identity-useful after offline classification: {len(useful_relationships)}", f"- generic or unresolved external relationships: {len(generic_relationships)}", "",
        "The previous new_useful_relationship_count treats every unique linked-domain relationship as useful. This includes generic social, CDN, analytics, player and infrastructure links, so 129 is not defensible as an identity-utility count.", "",
        "## Identity resolution", "", "The previous unresolved_identity_rate of 0.0 is not evidence that identity was resolved. Linked domains inherit roles and signal counts from their source result, which suppresses UNKNOWN_ROLE without independently attributing the target domain.", "",
        "## Verdict", "", f"- DISCOVERY_VERDICT: {recalculated['discovery_evaluation']['verdict']}", f"- V3_UTILITY_VERDICT: {recalculated['v3_utility_evaluation']['verdict']}", "- Prior V3_UTILITY_PASS defensible: NO", "- Officiality determined: NO", "",
    ]
    (output_dir / "current_run_audit_report.md").write_text("\n".join(report_lines), encoding="utf-8")
    print(json.dumps({"mode": "OFFLINE_AUDIT", "source_run_dir": str(run_dir), "output_dir": str(output_dir), "historical_results": len(results), "network_calls": NETWORK_CALLS, "credential_reads": CREDENTIAL_READS, "tavily_client_instantiations": TAVILY_CLIENT_INSTANTIATIONS, "tavily_search_calls": TAVILY_SEARCH_CALLS}, ensure_ascii=True, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Independent IPTV domain family discovery runner.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Validate/export plan offline; no API key, no Tavily, no network.")
    mode.add_argument("--execute", action="store_true", help="Future protected real execution mode.")
    mode.add_argument("--validate-design", action="store_true", help="Alias for offline design validation.")
    mode.add_argument("--audit-run-dir", default=None, help="Audit one existing run fully offline without Tavily or credentials.")
    parser.add_argument("--confirm-credit-use", action="store_true", help="Required together with --execute before Tavily can be used.")
    parser.add_argument("--brand", default=DEFAULT_BRAND)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--pause-seconds", type=float, default=1.0)
    parser.add_argument("--max-results", type=int, default=8)
    parser.add_argument("--search-depth", choices=["basic", "advanced"], default="advanced")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--resume-run-dir", default=None, help="Resume a protected execution from an existing run directory.")
    parser.add_argument("--repair-failed-run-dir", default=None, help="Repair one explicitly selected FAILED query in an existing execution run.")
    parser.add_argument("--repair-query-id", default=None, help="FAILED query ID to repair; requires --repair-failed-run-dir.")
    parser.add_argument("--audit-output-dir", default=None, help="Output directory for --audit-run-dir.")
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
    if args.resume_run_dir and args.repair_failed_run_dir:
        print("--resume-run-dir and --repair-failed-run-dir are mutually exclusive.", file=sys.stderr)
        return 2
    if args.repair_failed_run_dir and not args.execute:
        print("--repair-failed-run-dir requires --execute.", file=sys.stderr)
        return 2
    if args.repair_failed_run_dir and not args.repair_query_id:
        print("--repair-failed-run-dir requires --repair-query-id.", file=sys.stderr)
        return 2
    if args.repair_query_id and not args.repair_failed_run_dir:
        print("--repair-query-id requires --repair-failed-run-dir.", file=sys.stderr)
        return 2
    if args.repair_failed_run_dir and args.query_ids:
        print("Use --repair-query-id, not --query-ids, in repair mode.", file=sys.stderr)
        return 2
    if args.audit_output_dir and not args.audit_run_dir:
        print("--audit-output-dir requires --audit-run-dir.", file=sys.stderr)
        return 2
    try:
        if args.audit_run_dir:
            return run_offline_audit(args)
        if args.dry_run:
            return run_dry_run(args)
        return run_execute(args)
    except ValueError as exc:
        print(json.dumps({"status": "FAILED_SAFE_VALIDATION", "error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
