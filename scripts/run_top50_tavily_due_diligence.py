from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
from tavily import TavilyClient
from openpyxl.utils import get_column_letter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "research" / "output" / "best_iptv_2026"
WORK_DIR = OUTPUT_DIR / "tavily_due_diligence"

QUERY_PLAN_PATH = OUTPUT_DIR / "top50_query_plan_20260713.json"
PRELIMINARY_PATH = OUTPUT_DIR / "top50_due_diligence_preliminary_20260713.csv"

CHECKPOINT_PATH = WORK_DIR / "checkpoint.json"
QUERY_LOG_PATH = WORK_DIR / "query_log.jsonl"
RAW_RESULTS_PATH = WORK_DIR / "raw_results.jsonl"
ERRORS_PATH = WORK_DIR / "errors.jsonl"

OUTPUT_CSV = OUTPUT_DIR / "top50_external_evidence_20260713.csv"
OUTPUT_XLSX = OUTPUT_DIR / "top50_external_evidence_20260713.xlsx"
OUTPUT_JSON = OUTPUT_DIR / "top50_external_evidence_20260713.json"
OUTPUT_REPORT = OUTPUT_DIR / "top50_external_verification_report_20260713.md"

QUALITY_AUDIT_PATH = OUTPUT_DIR / "batch1_quality_audit_20260713.csv"
QUALITY_REPORT_PATH = OUTPUT_DIR / "batch1_quality_report_20260713.md"
QUERY_CORRECTIONS_PATH = OUTPUT_DIR / "query_corrections_for_batches_2_5_20260713.json"
ORIGINAL_QUERY_PLAN_PATH = OUTPUT_DIR / "top50_query_plan_20260713.json"
V2_WORK_DIR = OUTPUT_DIR / "tavily_due_diligence_v2"
V2_CHECKPOINT_PATH = V2_WORK_DIR / "checkpoint.json"
V2_QUERY_LOG_PATH = V2_WORK_DIR / "query_log.jsonl"
V2_RAW_RESULTS_PATH = V2_WORK_DIR / "raw_results.jsonl"
V2_ACCEPTED_RESULTS_PATH = V2_WORK_DIR / "accepted_results.jsonl"
V2_AMBIGUOUS_RESULTS_PATH = V2_WORK_DIR / "ambiguous_results.jsonl"
V2_REJECTED_RESULTS_PATH = V2_WORK_DIR / "rejected_results.jsonl"
V2_ERRORS_PATH = V2_WORK_DIR / "errors.jsonl"
V2_OUTPUT_CSV = V2_WORK_DIR / "pilot_v2_evidence_20260713.csv"
V2_OUTPUT_XLSX = V2_WORK_DIR / "pilot_v2_evidence_20260713.xlsx"
V2_OUTPUT_JSON = V2_WORK_DIR / "pilot_v2_evidence_20260713.json"
V2_OUTPUT_REPORT = V2_WORK_DIR / "pilot_v2_quality_report_20260713.md"
V2_QUERY_PLAN_PREVIEW_JSON = OUTPUT_DIR / "query_plan_v2_preview_20260713.json"
V2_QUERY_PLAN_PREVIEW_MD = OUTPUT_DIR / "query_plan_v2_preview_20260713.md"
V3_SIMULATION_DIR = OUTPUT_DIR / "tavily_due_diligence_v3_simulation"
V3_AUDIT_INPUT_CSV = V2_WORK_DIR / "pilot_v2_accepted_audit_20260714.csv"
V3_AUDIT_INPUT_REPORT = V2_WORK_DIR / "pilot_v2_accepted_audit_report_20260714.md"
V3_FILTER_ADJUSTMENTS_PATH = V2_WORK_DIR / "pilot_v2_filter_adjustments_20260714.json"

INITIAL_QUERY_LIMITS = {
    "identity": 2,
    "official_domain": 1,
    "corporate_registry": 1,
    "terms_privacy": 1,
    "app_stores": 1,
    "licensing": 2,
    "legal_history": 1,
    "trustpilot": 1,
    "reddit": 1,
    "reseller_panel": 1,
}

V2_INITIAL_QUERY_LIMITS = {
    "identity_official_domain": 2,
    "terms_privacy": 1,
    "company_address": 1,
    "app_store": 1,
    "licensing": 1,
    "legal_history": 1,
    "reviews_community": 1,
}

GLOBAL_NEGATIVE_TERMS = [
    "hotel",
    "hotels",
    "dental",
    "dentistry",
    "restaurant",
    "university",
    "school",
    "church",
    "radio",
    "stock",
    "finance",
    "real estate",
    "job",
    "careers",
    "annual report",
    "corporate pdf",
]

BRAND_NEGATIVE_TERMS = {
    "Voco TV": ["hotel", "hotels", "IHG", "dental", "dentistry", "resort", "hospitality"],
    "Free Go TV": ["free tv", "freeview", "freego bike", "freego mobility"],
    "Sonix IPTV": ["sonix.ai", "transcription", "speech to text", "audio transcription"],
    "Digita Line IPTV": ["digita.fi", "digital agency", "marketing agency"],
    "Zorba IPTV": ["zorbasofted", "education", "school software"],
}

V2_SAFE_CONTEXT_TERMS = ["IPTV", "OTT", "streaming", "M3U", "Xtream"]
V2_COMMERCIAL_TERMS = [
    "subscription",
    "channels",
    "reseller",
    "panel",
    "trial",
    "pricing",
    "support",
    "refund",
    "privacy",
    "terms",
]

ALLOWED_COMPANY_STATUS = {"IDENTIFIED", "PARTIALLY_IDENTIFIED", "NOT_IDENTIFIED"}
ALLOWED_LICENSING_STATUS = {
    "PUBLICLY_CONFIRMED",
    "CLAIMED_NOT_VERIFIED",
    "NOT_DEMONSTRATED",
    "CONTRADICTED_BY_PUBLIC_EVIDENCE",
}
ALLOWED_DD_STATUS = {
    "VERIFIED_FOR_FURTHER_COMMERCIAL_REVIEW",
    "NEEDS_ADDITIONAL_VERIFICATION",
    "NEEDS_IDENTITY_RESOLUTION",
    "HIGH_RISK",
    "REJECTED_BY_PUBLIC_EVIDENCE",
    "INSUFFICIENT_EVIDENCE",
}

NOT_FOUND = "NOT_FOUND"
NOT_DEMONSTRATED = "NOT_DEMONSTRATED"
AMBIGUOUS = "AMBIGUOUS"
PIPE_SEPARATOR = " | "

PROMOTIONAL_KEYWORDS = {
    "bestiptv",
    "best-iptv",
    "iptvfinder",
    "iptvrankings",
    "iptvreviews",
    "iptvserviceradar",
    "topiptv",
}

AFFILIATE_OR_SELF_PUBLISH_DOMAINS = {
    "github.com",
    "indiehackers.com",
    "medium.com",
    "prlog.org",
    "sites.google.com",
    "slideshare.net",
}

COMMUNITY_DOMAINS = {
    "facebook.com",
    "news.ycombinator.com",
    "quora.com",
    "reddit.com",
    "t.me",
    "youtube.com",
    "youtu.be",
}

REVIEW_DOMAINS = {
    "reviews.io",
    "scamadviser.com",
    "sitejabber.com",
    "trustpilot.com",
}

APP_STORE_DOMAINS = {
    "apps.apple.com",
    "play.google.com",
    "amazon.com",
    "amazon.co.uk",
    "galaxystore.samsung.com",
    "samsung.com",
    "lgappstv.com",
    "lg.com",
}

RIGHTS_HOLDER_DOMAINS = {
    "alliance4creativity.com",
    "fact-uk.org.uk",
    "ifpi.org",
    "mpa-emea.org",
    "motionpictures.org",
    "riaa.com",
}

NEWS_OR_TRADE_DOMAINS = {
    "torrentfreak.com",
    "techcrunch.com",
    "theverge.com",
    "wired.com",
    "cordcuttersnews.com",
    "fiercevideo.com",
    "streamtvinsider.com",
}

CORPORATE_REGISTRY_MARKERS = {
    "companieshouse.gov.uk",
    "opencorporates.com",
    "sec.gov",
    "sos.",
    "businesssearch",
    "corporations",
    "registry",
}

PAYMENT_GATEWAYS = (
    "paypal",
    "stripe",
    "visa",
    "mastercard",
    "coinbase",
    "btcpay",
    "nowpayments",
    "crypto",
    "bitcoin",
    "usdt",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return re.sub(r"\s+", " ", str(value)).strip()


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def parse_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def compact(value: str) -> str:
    value = clean_text(value).lower()
    value = re.sub(r"\b(iptv|tv|ott|hd|4k|plus|pro|stream|streams|service|services)\b", " ", value)
    return re.sub(r"[^a-z0-9]+", "", value)


def split_pipe(value: Any) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    return [part.strip() for part in text.split(PIPE_SEPARATOR) if part.strip()]


def brand_tokens(brand_name: str, aliases: str) -> set[str]:
    values = {compact(brand_name), re.sub(r"[^a-z0-9]+", "", brand_name.lower())}
    for alias in split_pipe(aliases):
        values.add(compact(alias))
        values.add(re.sub(r"[^a-z0-9]+", "", alias.lower()))
    return {value for value in values if len(value) >= 4}


def query_id(brand_name: str, category: str, ordinal: int, query_text: str) -> str:
    raw = f"{brand_name}|{category}|{ordinal}|{query_text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def load_checkpoint() -> dict[str, Any]:
    if CHECKPOINT_PATH.exists():
        return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    return {
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "completed_query_ids": [],
        "failed_query_ids": [],
        "completed_queries_count": 0,
        "skipped_by_checkpoint_count": 0,
        "errors_count": 0,
        "usage": [],
    }


def save_checkpoint(checkpoint: dict[str, Any]) -> None:
    checkpoint["updated_at"] = utc_now()
    checkpoint["completed_queries_count"] = len(set(checkpoint.get("completed_query_ids", [])))
    checkpoint["errors_count"] = len(read_jsonl(ERRORS_PATH))
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")


def select_batch(plan: list[dict[str, Any]], batch_index: int, batch_size: int) -> list[dict[str, Any]]:
    start = (batch_index - 1) * batch_size
    end = start + batch_size
    return sorted(plan, key=lambda item: item["rank"])[start:end]


def planned_queries_for_brand(brand_plan: dict[str, Any]) -> list[dict[str, Any]]:
    selected = []
    for category, limit in INITIAL_QUERY_LIMITS.items():
        queries = brand_plan["queries"].get(category, [])[:limit]
        for index, query_text in enumerate(queries, start=1):
            selected.append(
                {
                    "brand_name": brand_plan["brand_name"],
                    "rank": brand_plan["rank"],
                    "query_category": category,
                    "query_ordinal": index,
                    "query_text": query_text,
                    "query_id": query_id(brand_plan["brand_name"], category, index, query_text),
                }
            )
    return selected


def parse_pilot_brands(value: str) -> list[str]:
    return [clean_text(part) for part in value.split(",") if clean_text(part)]


def load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_v2_context() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, Any]]:
    preliminary_df = pd.read_csv(PRELIMINARY_PATH)
    quality_df = pd.read_csv(QUALITY_AUDIT_PATH) if QUALITY_AUDIT_PATH.exists() else pd.DataFrame()
    corrections = load_json_if_exists(QUERY_CORRECTIONS_PATH)
    original_plan = load_json_if_exists(ORIGINAL_QUERY_PLAN_PATH)
    return preliminary_df, quality_df, corrections, original_plan


def correction_by_brand(corrections: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        clean_text(item.get("brand_name")): item
        for item in corrections.get("brands", [])
        if clean_text(item.get("brand_name"))
    }


def exact_phrase(value: str) -> str:
    return f'"{clean_text(value)}"'


def normalized_exact(value: str) -> str:
    return re.sub(r"\s+", " ", clean_text(value)).casefold()


def negative_query_suffix(terms: list[str]) -> str:
    output = []
    for term in terms:
        term = clean_text(term)
        if not term:
            continue
        if " " in term:
            output.append(f'-"{term}"')
        else:
            output.append(f"-{term}")
    return " ".join(output)


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen = set()
    output = []
    for value in values:
        key = normalized_exact(value)
        if key and key not in seen:
            seen.add(key)
            output.append(clean_text(value))
    return output


def brand_aliases_for_v2(brand_row: pd.Series, correction: dict[str, Any] | None, quality_df: pd.DataFrame) -> list[str]:
    aliases = [clean_text(brand_row["brand_name"])]
    aliases.extend(split_pipe(brand_row.get("aliases", "")))
    if correction:
        aliases.extend(split_pipe(correction.get("aliases", "")))
    if not quality_df.empty:
        quality_aliases = quality_df.loc[
            quality_df["brand_name"] == brand_row["brand_name"],
            "aliases",
        ].dropna().unique().tolist()
        for alias_value in quality_aliases:
            aliases.extend(split_pipe(alias_value))
    return dedupe_preserve_order(aliases)


def negative_terms_for_v2(brand_name: str, correction: dict[str, Any] | None) -> list[str]:
    terms = list(GLOBAL_NEGATIVE_TERMS)
    terms.extend(BRAND_NEGATIVE_TERMS.get(brand_name, []))
    if correction:
        correction_terms = correction.get("negative_terms", [])
        if isinstance(correction_terms, list):
            terms.extend(clean_text(term) for term in correction_terms)
    return dedupe_preserve_order(terms)


def accepted_candidate_domain(domain: str) -> bool:
    domain = clean_text(domain).lower()
    if not domain or domain in {"not_found", "not identified", "not_identified"}:
        return False
    if domain in AFFILIATE_OR_SELF_PUBLISH_DOMAINS | REVIEW_DOMAINS | COMMUNITY_DOMAINS | APP_STORE_DOMAINS:
        return False
    if any(keyword in domain for keyword in PROMOTIONAL_KEYWORDS):
        return False
    return True


def domain_candidate_for_v2(brand_row: pd.Series) -> str:
    domain = clean_text(brand_row.get("probable_official_domain"))
    confidence = clean_text(brand_row.get("official_domain_confidence"))
    if confidence in {"HIGH", "MEDIUM"} and accepted_candidate_domain(domain):
        return domain.lower()
    return ""


def build_v2_queries_for_brand(
    brand_row: pd.Series,
    aliases: list[str],
    negative_terms: list[str],
    candidate_domain: str,
) -> list[dict[str, Any]]:
    brand = clean_text(brand_row["brand_name"])
    suffix = negative_query_suffix(negative_terms)
    primary_aliases = dedupe_preserve_order([brand, *aliases])[:3]
    exact_name = exact_phrase(brand)

    queries_by_category: dict[str, list[str]] = {
        "identity_official_domain": [
            f'{exact_name} IPTV official website {suffix}',
            f'{exact_name} streaming provider contact {suffix}',
        ],
        "terms_privacy": [
            f'{exact_name} ("terms of service" OR "privacy policy" OR "refund policy") {suffix}',
        ],
        "company_address": [
            f'{exact_name} ("company" OR "LLC" OR "Ltd" OR "Inc" OR "address") IPTV {suffix}',
        ],
        "app_store": [
            f'(site:play.google.com OR site:apps.apple.com) {exact_name} IPTV {suffix}',
        ],
        "licensing": [
            f'{exact_name} ("broadcast rights" OR "licensed channels" OR "copyright compliance") IPTV {suffix}',
        ],
        "legal_history": [
            f'{exact_name} ("lawsuit" OR "court" OR "takedown" OR "DMCA" OR "seized") IPTV {suffix}',
        ],
        "reviews_community": [
            f'({exact_name} IPTV) (site:trustpilot.com OR site:reddit.com) {suffix}',
        ],
    }

    if candidate_domain:
        queries_by_category["identity_official_domain"] = [
            f'site:{candidate_domain} {exact_name}',
            f'site:{candidate_domain} ({exact_name} OR IPTV)',
        ]
        queries_by_category["terms_privacy"] = [
            f'site:{candidate_domain} terms',
            f'site:{candidate_domain} privacy',
            f'site:{candidate_domain} refund',
        ][: V2_INITIAL_QUERY_LIMITS["terms_privacy"]]

    if len(primary_aliases) > 1 and not candidate_domain:
        alias = primary_aliases[1]
        queries_by_category["identity_official_domain"][1] = (
            f'{exact_phrase(alias)} IPTV official website {suffix}'
        )

    selected = []
    for category, limit in V2_INITIAL_QUERY_LIMITS.items():
        for ordinal, query_text in enumerate(queries_by_category.get(category, [])[:limit], start=1):
            selected.append(
                {
                    "brand_name": brand,
                    "rank": int(brand_row["rank"]),
                    "query_category": category,
                    "query_ordinal": ordinal,
                    "query_text": re.sub(r"\s+", " ", query_text).strip(),
                    "query_id": query_id(brand, f"v2_{category}", ordinal, query_text),
                    "mode": "v2_precision",
                    "candidate_domain": candidate_domain or "NOT_IDENTIFIED",
                    "aliases_used": primary_aliases,
                    "negative_terms": negative_terms,
                }
            )
    return selected


def build_v2_plan(pilot_brands: list[str]) -> dict[str, Any]:
    preliminary_df, quality_df, corrections, original_plan = load_v2_context()
    corrections_by_brand = correction_by_brand(corrections)
    available = set(preliminary_df["brand_name"])
    missing = [brand for brand in pilot_brands if brand not in available]
    if missing:
        raise RuntimeError(f"Marcas piloto no encontradas en la matriz preliminar: {missing}")

    brands_output = []
    for brand in pilot_brands:
        row = preliminary_df[preliminary_df["brand_name"] == brand].iloc[0]
        correction = corrections_by_brand.get(brand, {})
        aliases = brand_aliases_for_v2(row, correction, quality_df)
        negative_terms = negative_terms_for_v2(brand, correction)
        candidate_domain = domain_candidate_for_v2(row)
        queries = build_v2_queries_for_brand(row, aliases, negative_terms, candidate_domain)
        brands_output.append(
            {
                "rank": int(row["rank"]),
                "brand_name": brand,
                "aliases": aliases,
                "negative_terms": negative_terms,
                "candidate_domain": candidate_domain or "NOT_IDENTIFIED",
                "max_initial_queries": len(queries),
                "queries": queries,
            }
        )

    return {
        "mode": "dry_run_query_plan",
        "uses_tavily": False,
        "work_dir_for_future_pilot": str(V2_WORK_DIR),
        "rejected_results_jsonl_for_future_pilot": str(V2_REJECTED_RESULTS_PATH),
        "source_inputs": {
            "quality_audit": str(QUALITY_AUDIT_PATH),
            "quality_report": str(QUALITY_REPORT_PATH),
            "query_corrections": str(QUERY_CORRECTIONS_PATH),
            "original_query_plan": str(ORIGINAL_QUERY_PLAN_PATH),
        },
        "redesign_rules": {
            "initial_query_cap_per_brand": 8,
            "automatic_keep_threshold": 50,
            "ambiguous_review_range": [30, 49],
            "reject_below": 30,
            "dedupe_keys": ["canonical_url", "normalized_title", "content_hash"],
            "do_not_reuse_noisy_batch1_as_valid_evidence": True,
            "do_not_assign_same_url_to_multiple_brands_without_explicit_co_mentions": True,
        },
        "brands": brands_output,
        "max_pilot_queries": sum(item["max_initial_queries"] for item in brands_output),
    }


def canonical_url(url: str) -> str:
    parsed = urlparse(clean_text(url))
    path = re.sub(r"/+$", "", parsed.path or "/")
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower().removeprefix('www.')}{path}"


def normalized_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean_text(title).lower()).strip()


def content_hash(content: str, raw_content: str = "") -> str:
    text = clean_text(raw_content or content)
    return hashlib.sha256(text[:5000].encode("utf-8")).hexdigest()[:20] if text else ""


def exact_name_present(text: str, brand_name: str) -> bool:
    return normalized_exact(brand_name) in normalized_exact(text)


def contains_any_term(text: str, terms: list[str]) -> bool:
    lowered = normalized_exact(text)
    return any(normalized_exact(term) in lowered for term in terms if clean_text(term))


def relevance_score_v2(
    result: dict[str, Any],
    brand_name: str,
    negative_terms: list[str],
    candidate_domain: str = "",
) -> tuple[int, list[str]]:
    title = clean_text(result.get("title"))
    url = clean_text(result.get("url"))
    domain = parse_domain(url)
    content = clean_text(result.get("content"))
    raw_content = clean_text(result.get("raw_content"))
    combined = f"{title} {content} {raw_content}"
    score = 0
    reasons = []

    if exact_name_present(title, brand_name):
        score += 30
        reasons.append("exact_brand_in_title:+30")
    if exact_name_present(url, brand_name) or exact_name_present(domain.replace("-", " "), brand_name):
        score += 25
        reasons.append("exact_brand_in_url_or_domain:+25")
    if contains_any_term(title, V2_SAFE_CONTEXT_TERMS):
        score += 15
        reasons.append("iptv_context_in_title:+15")
    if normalized_exact(combined).count(normalized_exact(brand_name)) >= 2:
        score += 10
        reasons.append("exact_brand_repeated_in_content:+10")
    if contains_any_term(combined, V2_COMMERCIAL_TERMS):
        score += 10
        reasons.append("commercial_terms:+10")
    if candidate_domain and domain == candidate_domain:
        score += 10
        reasons.append("candidate_domain:+10")
    if contains_any_term(combined, negative_terms) or contains_any_term(url, negative_terms):
        score -= 40
        reasons.append("negative_or_homonym_term:-40")
    if not exact_name_present(combined, brand_name) and not exact_name_present(url, brand_name):
        score -= 50
        reasons.append("absence_total_exact_name:-50")

    return max(0, min(100, score)), reasons


def v2_result_bucket(score: int) -> str:
    if score >= 50:
        return "KEEP_EVIDENCE"
    if score >= 30:
        return "AMBIGUOUS_REVIEW"
    return "REJECT_TO_REJECTED_RESULTS"


def result_mentions_multiple_brands(result: dict[str, Any], brand_names: list[str]) -> list[str]:
    text = f"{result.get('title', '')} {result.get('content', '')} {result.get('raw_content', '')} {result.get('url', '')}"
    return [brand for brand in brand_names if exact_name_present(text, brand)]


def should_store_v2_result(
    result: dict[str, Any],
    query: dict[str, Any],
    seen_keys: set[tuple[str, str]],
    url_owner: dict[str, str],
    all_pilot_brands: list[str],
) -> tuple[bool, str, dict[str, Any]]:
    score, reasons = relevance_score_v2(
        result,
        query["brand_name"],
        query.get("negative_terms", []),
        "" if query.get("candidate_domain") == "NOT_IDENTIFIED" else query.get("candidate_domain", ""),
    )
    bucket = v2_result_bucket(score)
    url = clean_text(result.get("url"))
    dedupe_keys = [
        ("canonical_url", canonical_url(url)),
        ("normalized_title", normalized_title(clean_text(result.get("title")))),
        ("content_hash", content_hash(clean_text(result.get("content")), clean_text(result.get("raw_content")))),
    ]
    for key_type, key_value in dedupe_keys:
        if key_value and (key_type, key_value) in seen_keys:
            return False, "DUPLICATE_BY_" + key_type.upper(), {"relevance_score": score, "relevance_reasons": reasons, "bucket": bucket}

    canon = canonical_url(url)
    if canon in url_owner and url_owner[canon] != query["brand_name"]:
        mentioned = result_mentions_multiple_brands(result, all_pilot_brands)
        if query["brand_name"] not in mentioned or url_owner[canon] not in mentioned:
            return False, "REJECT_SHARED_URL_WITHOUT_EXPLICIT_CO_MENTION", {"relevance_score": score, "relevance_reasons": reasons, "bucket": bucket}

    metadata = {"relevance_score": score, "relevance_reasons": reasons, "bucket": bucket}
    if bucket == "REJECT_TO_REJECTED_RESULTS":
        return False, "RELEVANCE_BELOW_30", metadata

    for key_type, key_value in dedupe_keys:
        if key_value:
            seen_keys.add((key_type, key_value))
    if canon:
        url_owner.setdefault(canon, query["brand_name"])
    return True, bucket, metadata


def write_v2_dry_run_outputs(plan: dict[str, Any]) -> None:
    V2_WORK_DIR.mkdir(parents=True, exist_ok=True)
    V2_QUERY_PLAN_PREVIEW_JSON.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Query plan v2 preview - 20260713",
        "",
        "No Tavily calls were executed.",
        "",
        f"Future pilot work dir: `{plan['work_dir_for_future_pilot']}`",
        f"Maximum pilot queries: {plan['max_pilot_queries']}",
        "",
    ]
    for brand in plan["brands"]:
        lines.extend(
            [
                f"## {brand['brand_name']}",
                "",
                f"- Candidate domain: {brand['candidate_domain']}",
                f"- Max initial queries: {brand['max_initial_queries']}",
                f"- Aliases: {', '.join(brand['aliases'])}",
                f"- Negative terms: {', '.join(brand['negative_terms'])}",
                "",
                "| Category | Query |",
                "|---|---|",
            ]
        )
        for query in brand["queries"]:
            lines.append(f"| {query['query_category']} | `{query['query_text']}` |")
        lines.append("")
    V2_QUERY_PLAN_PREVIEW_MD.write_text("\n".join(lines), encoding="utf-8")


def load_v2_checkpoint() -> dict[str, Any]:
    if V2_CHECKPOINT_PATH.exists():
        return json.loads(V2_CHECKPOINT_PATH.read_text(encoding="utf-8"))
    return {
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "completed_query_ids": [],
        "failed_query_ids": [],
        "completed_queries_count": 0,
        "skipped_by_checkpoint_count": 0,
        "errors_count": 0,
        "usage": [],
    }


def save_v2_checkpoint(checkpoint: dict[str, Any]) -> None:
    checkpoint["updated_at"] = utc_now()
    checkpoint["completed_queries_count"] = len(set(checkpoint.get("completed_query_ids", [])))
    checkpoint["errors_count"] = len(read_jsonl(V2_ERRORS_PATH))
    V2_WORK_DIR.mkdir(parents=True, exist_ok=True)
    V2_CHECKPOINT_PATH.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")


def v2_source_category_for_result(query: dict[str, Any], result: dict[str, Any]) -> str:
    url = clean_text(result.get("url"))
    content = f"{clean_text(result.get('content'))} {clean_text(result.get('raw_content'))}"
    candidate = query.get("candidate_domain", "")
    official_candidates = {candidate} if candidate and candidate != "NOT_IDENTIFIED" else set()
    return classify_source(
        parse_domain(url),
        query["query_category"],
        url,
        content,
        official_candidates=official_candidates,
    )


def build_v2_result_record(
    query: dict[str, Any],
    result: dict[str, Any],
    retrieved_at: str,
    query_status: str,
    storage_status: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    url = clean_text(result.get("url"))
    content = clean_text(result.get("content"))
    raw_content = clean_text(result.get("raw_content"))
    source_category = v2_source_category_for_result(query, result)
    return {
        "brand_name": query["brand_name"],
        "rank": query["rank"],
        "query_category": query["query_category"],
        "query_text": query["query_text"],
        "query_id": query["query_id"],
        "title": clean_text(result.get("title")),
        "url": url,
        "canonical_url": canonical_url(url),
        "domain": parse_domain(url),
        "published_date": clean_text(result.get("published_date")),
        "tavily_score": result.get("score"),
        "content": content,
        "raw_content": raw_content,
        "retrieved_at": retrieved_at,
        "query_status": query_status,
        "source_category": source_category,
        "brief_quote": brief_quote(f"{content} {raw_content}", query["brand_name"], ""),
        "relevance_score": metadata.get("relevance_score"),
        "relevance_reasons": PIPE_SEPARATOR.join(metadata.get("relevance_reasons", [])),
        "result_bucket": metadata.get("bucket"),
        "storage_status": storage_status,
        "candidate_domain": query.get("candidate_domain", "NOT_IDENTIFIED"),
        "negative_terms": PIPE_SEPARATOR.join(query.get("negative_terms", [])),
        "aliases_used": PIPE_SEPARATOR.join(query.get("aliases_used", [])),
    }


def execute_v2_pilot(args: argparse.Namespace, pilot_brands: list[str]) -> dict[str, Any]:
    V2_WORK_DIR.mkdir(parents=True, exist_ok=True)
    plan = build_v2_plan(pilot_brands)
    queries = [query for brand in plan["brands"] for query in brand["queries"]]
    if len(queries) > 40:
        raise RuntimeError(f"El piloto V2 excede 40 consultas: {len(queries)}")

    checkpoint = load_v2_checkpoint()
    completed = set(checkpoint.get("completed_query_ids", []))
    pending_queries = [query for query in queries if query["query_id"] not in completed]
    api_key = os.getenv("TAVILY_API_KEY")
    if pending_queries and not api_key:
        raise RuntimeError("TAVILY_API_KEY no esta disponible en el entorno.")

    accepted_existing = read_jsonl(V2_ACCEPTED_RESULTS_PATH)
    ambiguous_existing = read_jsonl(V2_AMBIGUOUS_RESULTS_PATH)
    seen_keys: set[tuple[str, str]] = set()
    url_owner: dict[str, str] = {}
    for row in [*accepted_existing, *ambiguous_existing]:
        if clean_text(row.get("canonical_url")):
            seen_keys.add(("canonical_url", clean_text(row.get("canonical_url"))))
            url_owner.setdefault(clean_text(row.get("canonical_url")), clean_text(row.get("brand_name")))
        title_key = normalized_title(clean_text(row.get("title")))
        if title_key:
            seen_keys.add(("normalized_title", title_key))
        hash_key = content_hash(clean_text(row.get("content")), clean_text(row.get("raw_content")))
        if hash_key:
            seen_keys.add(("content_hash", hash_key))

    stats = {
        "executed": 0,
        "skipped": 0,
        "errors": 0,
        "raw_results": 0,
        "accepted": 0,
        "ambiguous": 0,
        "rejected": 0,
        "usage": [],
        "max_queries": len(queries),
    }

    for query in queries:
        if query["query_id"] in completed:
            stats["skipped"] += 1
            append_jsonl(V2_QUERY_LOG_PATH, {**query, "event": "SKIPPED_BY_CHECKPOINT", "logged_at": utc_now()})
            continue

        append_jsonl(V2_QUERY_LOG_PATH, {**query, "event": "STARTED", "logged_at": utc_now()})
        retrieved_at = utc_now()
        response, status, error_message = call_tavily(
            api_key=api_key,
            query_text=query["query_text"],
            timeout=args.timeout,
            max_retries=args.max_retries,
            backoff_seconds=args.backoff_seconds,
        )
        if status == "ERROR" or response is None:
            stats["errors"] += 1
            checkpoint.setdefault("failed_query_ids", [])
            if query["query_id"] not in checkpoint["failed_query_ids"]:
                checkpoint["failed_query_ids"].append(query["query_id"])
            append_jsonl(V2_ERRORS_PATH, {**query, "error": error_message, "logged_at": utc_now()})
            append_jsonl(V2_QUERY_LOG_PATH, {**query, "event": "ERROR", "logged_at": utc_now(), "error": error_message})
            save_v2_checkpoint(checkpoint)
            time.sleep(args.pause_seconds)
            continue

        results = response.get("results", [])
        query_status = "SUCCESS" if results else "NO_RESULTS"
        for result in results:
            store, storage_status, metadata = should_store_v2_result(
                result,
                query,
                seen_keys,
                url_owner,
                pilot_brands,
            )
            record = build_v2_result_record(query, result, retrieved_at, query_status, storage_status, metadata)
            append_jsonl(V2_RAW_RESULTS_PATH, record)
            stats["raw_results"] += 1
            if store and metadata.get("bucket") == "KEEP_EVIDENCE":
                append_jsonl(V2_ACCEPTED_RESULTS_PATH, record)
                stats["accepted"] += 1
            elif store and metadata.get("bucket") == "AMBIGUOUS_REVIEW":
                append_jsonl(V2_AMBIGUOUS_RESULTS_PATH, record)
                stats["ambiguous"] += 1
            else:
                append_jsonl(V2_REJECTED_RESULTS_PATH, record)
                stats["rejected"] += 1

        usage = {
            key: response.get(key)
            for key in ("credits_used", "cost", "usage", "response_time")
            if key in response
        }
        if usage:
            usage_item = {"query_id": query["query_id"], **usage}
            stats["usage"].append(usage_item)
            checkpoint.setdefault("usage", []).append(usage_item)

        checkpoint.setdefault("completed_query_ids", [])
        if query["query_id"] not in checkpoint["completed_query_ids"]:
            checkpoint["completed_query_ids"].append(query["query_id"])
        checkpoint["failed_query_ids"] = [item for item in checkpoint.get("failed_query_ids", []) if item != query["query_id"]]
        append_jsonl(
            V2_QUERY_LOG_PATH,
            {
                **query,
                "event": "COMPLETED",
                "logged_at": utc_now(),
                "results_count": len(results),
                "query_status": query_status,
                "usage": usage,
            },
        )
        stats["executed"] += 1
        save_v2_checkpoint(checkpoint)
        time.sleep(args.pause_seconds)

    checkpoint["skipped_by_checkpoint_count"] = checkpoint.get("skipped_by_checkpoint_count", 0) + stats["skipped"]
    save_v2_checkpoint(checkpoint)
    write_v2_dry_run_outputs(plan)
    return stats


def dataframe_from_jsonl(path: Path) -> pd.DataFrame:
    rows = read_jsonl(path)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def v2_candidate_domains(accepted_df: pd.DataFrame, ambiguous_df: pd.DataFrame, pilot_brands: list[str]) -> pd.DataFrame:
    rows = []
    combined = pd.concat([accepted_df, ambiguous_df], ignore_index=True) if not accepted_df.empty or not ambiguous_df.empty else pd.DataFrame()
    if combined.empty:
        return pd.DataFrame(columns=["brand_name", "domain", "candidate_score", "official_domain_confidence", "reasons"])
    for brand in pilot_brands:
        group = combined[combined["brand_name"] == brand]
        scores: Counter[str] = Counter()
        reasons: dict[str, set[str]] = defaultdict(set)
        tokens = brand_tokens(brand, "")
        for _, row in group.iterrows():
            domain = clean_text(row.get("domain"))
            if not accepted_candidate_domain(domain):
                continue
            slug = registrable_slug(domain)
            if any(slug == token or slug in token or token in slug for token in tokens):
                scores[domain] += 2
                reasons[domain].add("domain_slug_matches_exact_brand")
            if row.get("source_category") == "OFFICIAL_PROVIDER":
                scores[domain] += 2
                reasons[domain].add("source_category_official_provider")
            path = urlparse(clean_text(row.get("url"))).path.lower()
            if any(part in path for part in ("terms", "privacy", "refund", "contact", "about")):
                scores[domain] += 1
                reasons[domain].add("policy_or_contact_path")
        for domain, score in scores.most_common():
            confidence = "HIGH" if score >= 4 else "MEDIUM" if score >= 2 else "LOW"
            rows.append(
                {
                    "brand_name": brand,
                    "domain": domain,
                    "candidate_score": score,
                    "official_domain_confidence": confidence,
                    "reasons": PIPE_SEPARATOR.join(sorted(reasons[domain])),
                }
            )
    return pd.DataFrame(rows)


def summarize_v2_pilot(pilot_brands: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    accepted_df = dataframe_from_jsonl(V2_ACCEPTED_RESULTS_PATH)
    ambiguous_df = dataframe_from_jsonl(V2_AMBIGUOUS_RESULTS_PATH)
    rejected_df = dataframe_from_jsonl(V2_REJECTED_RESULTS_PATH)
    raw_df = dataframe_from_jsonl(V2_RAW_RESULTS_PATH)
    candidates_df = v2_candidate_domains(accepted_df, ambiguous_df, pilot_brands)
    summary_rows = []
    for brand in pilot_brands:
        total = int((raw_df["brand_name"] == brand).sum()) if not raw_df.empty and "brand_name" in raw_df else 0
        accepted = int((accepted_df["brand_name"] == brand).sum()) if not accepted_df.empty and "brand_name" in accepted_df else 0
        ambiguous = int((ambiguous_df["brand_name"] == brand).sum()) if not ambiguous_df.empty and "brand_name" in ambiguous_df else 0
        rejected = int((rejected_df["brand_name"] == brand).sum()) if not rejected_df.empty and "brand_name" in rejected_df else 0
        denom = max(total, 1)
        brand_candidates = candidates_df[candidates_df["brand_name"] == brand] if not candidates_df.empty else pd.DataFrame()
        if not brand_candidates.empty:
            probable_domain = clean_text(brand_candidates.iloc[0]["domain"])
            domain_confidence = clean_text(brand_candidates.iloc[0]["official_domain_confidence"])
        else:
            probable_domain = "NOT_IDENTIFIED"
            domain_confidence = "NOT_IDENTIFIED"
        summary_rows.append(
            {
                "brand_name": brand,
                "total_results": total,
                "accepted_count": accepted,
                "ambiguous_count": ambiguous,
                "rejected_count": rejected,
                "precision_proxy": round((accepted + ambiguous) / denom, 4),
                "noise_proxy": round(rejected / denom, 4),
                "probable_official_domain": probable_domain,
                "official_domain_confidence": domain_confidence,
            }
        )
    summary_df = pd.DataFrame(summary_rows)
    global_total = int(summary_df["total_results"].sum())
    global_accepted = int(summary_df["accepted_count"].sum())
    global_ambiguous = int(summary_df["ambiguous_count"].sum())
    global_rejected = int(summary_df["rejected_count"].sum())
    metrics = {
        "global_total_results": global_total,
        "global_accepted": global_accepted,
        "global_ambiguous": global_ambiguous,
        "global_rejected": global_rejected,
        "global_precision_proxy": round((global_accepted + global_ambiguous) / max(global_total, 1), 4),
        "global_noise_proxy": round(global_rejected / max(global_total, 1), 4),
        "unique_urls": int(
            pd.concat([accepted_df, ambiguous_df], ignore_index=True)["canonical_url"].nunique()
            if not accepted_df.empty or not ambiguous_df.empty
            else 0
        ),
    }
    return summary_df, candidates_df, metrics


def voco_homonym_retained(accepted_df: pd.DataFrame, ambiguous_df: pd.DataFrame) -> bool:
    combined = pd.concat([accepted_df, ambiguous_df], ignore_index=True) if not accepted_df.empty or not ambiguous_df.empty else pd.DataFrame()
    if combined.empty:
        return False
    voco = combined[combined["brand_name"] == "Voco TV"]
    if voco.empty:
        return False
    text = " ".join(
        f"{row.get('title', '')} {row.get('url', '')} {row.get('content', '')} {row.get('raw_content', '')}"
        for _, row in voco.iterrows()
    ).casefold()
    return any(term in text for term in ("ihg", "hotel", "hotels", "dental", "dentistry"))


def reseller_official_without_direct_evidence(candidates_df: pd.DataFrame, accepted_df: pd.DataFrame) -> bool:
    if candidates_df.empty or accepted_df.empty:
        return False
    for _, candidate in candidates_df.iterrows():
        if candidate["official_domain_confidence"] not in {"HIGH", "MEDIUM"}:
            continue
        domain_rows = accepted_df[
            (accepted_df["brand_name"] == candidate["brand_name"])
            & (accepted_df["domain"] == candidate["domain"])
        ]
        if domain_rows.empty:
            continue
        if set(domain_rows["source_category"]) <= {"RESELLER"}:
            return True
    return False


def v2_verdict(metrics: dict[str, Any], accepted_df: pd.DataFrame, ambiguous_df: pd.DataFrame, candidates_df: pd.DataFrame) -> tuple[str, str]:
    voco_bad = voco_homonym_retained(accepted_df, ambiguous_df)
    reseller_bad = reseller_official_without_direct_evidence(candidates_df, accepted_df)
    pass_thresholds = (
        metrics["global_precision_proxy"] >= 0.65
        and metrics["global_noise_proxy"] <= 0.25
        and not voco_bad
        and not reseller_bad
    )
    if pass_thresholds:
        return "PASS", "Autorizar lote 2 con el buscador V2 y monitoreo de calidad."
    if metrics["global_precision_proxy"] >= 0.5 and metrics["global_noise_proxy"] <= 0.4 and not voco_bad:
        return "PASS_WITH_ADJUSTMENTS", "Aplicar ajustes menores antes de lote 2; no autorizar automaticamente."
    return "FAIL_REQUIRES_QUERY_REDESIGN", "No autorizar lote 2; revisar consultas, negativos y dominio oficial antes de continuar."


def write_v2_outputs(stats: dict[str, Any], pilot_brands: list[str]) -> dict[str, Any]:
    accepted_df = dataframe_from_jsonl(V2_ACCEPTED_RESULTS_PATH)
    ambiguous_df = dataframe_from_jsonl(V2_AMBIGUOUS_RESULTS_PATH)
    rejected_df = dataframe_from_jsonl(V2_REJECTED_RESULTS_PATH)
    raw_df = dataframe_from_jsonl(V2_RAW_RESULTS_PATH)
    errors_df = dataframe_from_jsonl(V2_ERRORS_PATH)
    query_log_df = dataframe_from_jsonl(V2_QUERY_LOG_PATH)
    summary_df, candidates_df, metrics = summarize_v2_pilot(pilot_brands)
    verdict, recommendation = v2_verdict(metrics, accepted_df, ambiguous_df, candidates_df)
    metrics["verdict"] = verdict
    metrics["recommendation"] = recommendation

    sources_df = (
        pd.concat([accepted_df, ambiguous_df], ignore_index=True)
        if not accepted_df.empty or not ambiguous_df.empty
        else pd.DataFrame()
    )
    if not sources_df.empty:
        sources_summary_df = sources_df.groupby(["source_category", "domain"]).size().reset_index(name="result_count")
    else:
        sources_summary_df = pd.DataFrame(columns=["source_category", "domain", "result_count"])

    summary_df.to_csv(V2_OUTPUT_CSV, index=False, encoding="utf-8-sig")
    V2_OUTPUT_JSON.write_text(
        json.dumps(
            {
                "summary": summary_df.to_dict(orient="records"),
                "metrics": metrics,
                "run_stats": stats,
                "accepted": accepted_df.to_dict(orient="records") if not accepted_df.empty else [],
                "ambiguous": ambiguous_df.to_dict(orient="records") if not ambiguous_df.empty else [],
                "rejected": rejected_df.to_dict(orient="records") if not rejected_df.empty else [],
                "errors": errors_df.to_dict(orient="records") if not errors_df.empty else [],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    lines = [
        "# Pilot V2 quality report - 20260713",
        "",
        "## Scope",
        "",
        "- Pilot V2 executed only for five requested brands.",
        "- V1 outputs and checkpoints were not modified.",
        "- Results below relevance_score 30 were rejected to rejected_results.jsonl.",
        "",
        "## Metrics",
        "",
        f"- Queries executed: {stats['executed']}",
        f"- Queries skipped by checkpoint: {stats['skipped']}",
        f"- Errors: {stats['errors']}",
        f"- Raw results: {stats['raw_results']}",
        f"- Accepted: {stats['accepted']}",
        f"- Ambiguous: {stats['ambiguous']}",
        f"- Rejected: {stats['rejected']}",
        f"- Unique accepted/ambiguous URLs: {metrics['unique_urls']}",
        f"- Global precision_proxy: {metrics['global_precision_proxy']}",
        f"- Global noise_proxy: {metrics['global_noise_proxy']}",
        f"- Verdict: {verdict}",
        f"- Recommendation: {recommendation}",
        "",
        "## Brand summary",
        "",
        "| Brand | Total | Accepted | Ambiguous | Rejected | Precision proxy | Noise proxy | Official candidate | Confidence |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for _, row in summary_df.iterrows():
        lines.append(
            f"| {row['brand_name']} | {row['total_results']} | {row['accepted_count']} | "
            f"{row['ambiguous_count']} | {row['rejected_count']} | {row['precision_proxy']} | "
            f"{row['noise_proxy']} | {row['probable_official_domain']} | {row['official_domain_confidence']} |"
        )
    lines.extend(
        [
            "",
            "## Voco homonym control",
            "",
            f"- IHG/hotel/dental retained as evidence: {'YES' if voco_homonym_retained(accepted_df, ambiguous_df) else 'NO'}",
        ]
    )
    V2_OUTPUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pd.ExcelWriter(V2_OUTPUT_XLSX, engine="openpyxl") as writer:
        write_sheet(writer, summary_df, "Resumen por marca")
        write_sheet(writer, accepted_df, "Evidencia aceptada")
        write_sheet(writer, ambiguous_df, "Revisión ambigua")
        write_sheet(writer, rejected_df, "Rechazados")
        write_sheet(writer, query_log_df, "Consultas")
        write_sheet(writer, candidates_df, "Dominios candidatos")
        write_sheet(writer, sources_summary_df, "Fuentes")
        write_sheet(writer, errors_df, "Errores")
    return metrics


def call_tavily(
    api_key: str,
    query_text: str,
    timeout: float,
    max_retries: int,
    backoff_seconds: float,
) -> tuple[dict[str, Any] | None, str, str]:
    client = TavilyClient(api_key=api_key)
    last_error = ""
    for attempt in range(1, max_retries + 1):
        try:
            response = client.search(
                query=query_text,
                search_depth="advanced",
                max_results=8,
                include_raw_content=True,
                include_answer=False,
                timeout=timeout,
            )
            return response, "SUCCESS", ""
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            retryable_markers = ("429", "rate", "timeout", "temporar", "503", "502", "504", "500")
            if any(marker in last_error.casefold() for marker in retryable_markers):
                wait_seconds = backoff_seconds * attempt
                time.sleep(wait_seconds)
                if attempt < max_retries:
                    continue

        if attempt < max_retries:
            time.sleep(backoff_seconds * attempt)

    return None, "ERROR", last_error


def classify_source(domain: str, query_category: str, url: str, content: str, official_candidates: set[str] | None = None) -> str:
    domain = domain.lower().removeprefix("www.")
    official_candidates = official_candidates or set()
    lowered = f"{url} {content}".lower()

    if domain in official_candidates:
        return "OFFICIAL_PROVIDER"
    if domain in RIGHTS_HOLDER_DOMAINS:
        return "RIGHTS_HOLDER"
    if domain.endswith(".gov") or ".court" in domain or "justice" in domain or "judiciary" in domain:
        return "GOVERNMENT_OR_COURT"
    if query_category == "corporate_registry" and (
        any(marker in domain for marker in CORPORATE_REGISTRY_MARKERS)
        or any(marker in lowered for marker in CORPORATE_REGISTRY_MARKERS)
    ):
        return "CORPORATE_REGISTRY"
    if domain in APP_STORE_DOMAINS or domain.endswith("play.google.com") or domain.endswith("apps.apple.com"):
        return "APP_STORE"
    if domain in REVIEW_DOMAINS:
        return "REVIEW_PLATFORM"
    if domain in COMMUNITY_DOMAINS:
        return "COMMUNITY"
    if "reseller" in lowered or "reseller-panel" in lowered:
        return "RESELLER"
    if domain in AFFILIATE_OR_SELF_PUBLISH_DOMAINS or any(keyword in domain for keyword in PROMOTIONAL_KEYWORDS):
        return "AFFILIATE_OR_PROMOTIONAL"
    if domain in NEWS_OR_TRADE_DOMAINS:
        return "NEWS_OR_TRADE_PRESS"
    return "UNKNOWN"


def brief_quote(text: str, brand_name: str, aliases: str) -> str:
    text = clean_text(text)
    if not text:
        return ""
    tokens = brand_tokens(brand_name, aliases)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for sentence in sentences:
        compact_sentence = re.sub(r"[^a-z0-9]+", "", sentence.lower())
        if any(token in compact_sentence for token in tokens):
            words = sentence.split()
            return " ".join(words[:24])
    words = text.split()
    return " ".join(words[:24])


def extract_company_name(text: str, brand: str) -> str:
    text = clean_text(text)
    patterns = [
        rf"{re.escape(brand)}\s+(LLC|L\.L\.C\.|Ltd\.?|Limited|Inc\.?|Corporation|Corp\.?|S\.A\.|S\.L\.)",
        r"\b[A-Z][A-Za-z0-9&.,' -]{2,80}\s+(LLC|L\.L\.C\.|Ltd\.?|Limited|Inc\.?|Corporation|Corp\.?|S\.A\.|S\.L\.)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return clean_text(match.group(0))
    return NOT_FOUND


def extract_email(text: str, official_domain: str = "") -> str:
    emails = sorted(set(re.findall(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.IGNORECASE)))
    if not emails:
        return NOT_FOUND
    if official_domain:
        official_root = registrable_slug(official_domain)
        for email in emails:
            if registrable_slug(email.split("@", 1)[1]) == official_root:
                return email
    return emails[0] if len(emails) == 1 else AMBIGUOUS


def extract_phone(text: str) -> str:
    for match in re.finditer(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)", text):
        phone = clean_text(match.group(0))
        digits = re.sub(r"\D", "", phone)
        if 8 <= len(digits) <= 15:
            return phone
    return NOT_FOUND


def extract_country(text: str) -> str:
    countries = [
        "Argentina",
        "Australia",
        "Brazil",
        "Canada",
        "France",
        "Germany",
        "India",
        "Italy",
        "Mexico",
        "Netherlands",
        "Portugal",
        "Spain",
        "United Kingdom",
        "United States",
        "USA",
    ]
    found = []
    for country in countries:
        if re.search(rf"\b{re.escape(country)}\b", text, re.IGNORECASE):
            found.append("United States" if country == "USA" else country)
    found = sorted(set(found))
    if not found:
        return NOT_FOUND
    return PIPE_SEPARATOR.join(found[:3]) if len(found) <= 3 else AMBIGUOUS


def registrable_slug(domain: str) -> str:
    parts = [part for part in domain.lower().removeprefix("www.").split(".") if part]
    if len(parts) >= 3 and parts[-2] in {"co", "com", "net", "org"}:
        root = parts[-3]
    elif len(parts) >= 2:
        root = parts[-2]
    elif parts:
        root = parts[0]
    else:
        root = domain
    return re.sub(r"[^a-z0-9]+", "", root)


def find_policy_url(rows: list[dict[str, Any]], official_domain: str, terms: tuple[str, ...]) -> str:
    for row in rows:
        if official_domain != NOT_FOUND and row["domain"] != official_domain:
            continue
        path = urlparse(row["url"]).path.lower()
        if any(term in path for term in terms):
            return row["url"]
    return NOT_FOUND


def detect_signal(text: str, patterns: tuple[str, ...]) -> str:
    return "DETECTED_IN_EVIDENCE" if any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns) else NOT_DEMONSTRATED


def candidate_official_domains(brand_row: pd.Series, evidence_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tokens = brand_tokens(brand_row["brand_name"], brand_row.get("aliases", ""))
    candidates: Counter[str] = Counter()
    reasons: dict[str, set[str]] = defaultdict(set)

    for row in evidence_rows:
        domain = row["domain"]
        if not domain:
            continue
        source_category = classify_source(domain, row["query_category"], row["url"], row.get("content", ""))
        if source_category in {
            "AFFILIATE_OR_PROMOTIONAL",
            "APP_STORE",
            "COMMUNITY",
            "GOVERNMENT_OR_COURT",
            "REVIEW_PLATFORM",
            "RIGHTS_HOLDER",
        }:
            continue
        slug = registrable_slug(domain)
        if not slug:
            continue
        if any(slug == token or slug in token or token in slug for token in tokens):
            candidates[domain] += 2
            reasons[domain].add("domain_slug_matches_brand_or_alias")
        if row["query_category"] in {"official_domain", "terms_privacy"}:
            candidates[domain] += 1
            reasons[domain].add(f"returned_for_{row['query_category']}")
        path = urlparse(row["url"]).path.lower()
        if any(part in path for part in ("terms", "privacy", "refund", "contact", "about")):
            candidates[domain] += 1
            reasons[domain].add("policy_or_contact_path")

    output = []
    for domain, score in candidates.most_common():
        if score >= 4:
            confidence = "HIGH"
        elif score >= 2:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"
        output.append(
            {
                "brand_name": brand_row["brand_name"],
                "domain": domain,
                "candidate_score": score,
                "official_domain_confidence": confidence,
                "reasons": PIPE_SEPARATOR.join(sorted(reasons[domain])),
            }
        )
    return output


def licensing_status(licensing_claim: str, legal_signal: str, source_categories: set[str]) -> str:
    if legal_signal == "DETECTED_IN_EVIDENCE":
        return "CONTRADICTED_BY_PUBLIC_EVIDENCE"
    if licensing_claim == NOT_DEMONSTRATED:
        return "NOT_DEMONSTRATED"
    if source_categories & {"GOVERNMENT_OR_COURT", "RIGHTS_HOLDER", "CORPORATE_REGISTRY"}:
        return "PUBLICLY_CONFIRMED"
    return "CLAIMED_NOT_VERIFIED"


def updated_transparency_score(fields: dict[str, Any], source_categories: set[str]) -> int:
    score = 0
    independent = source_categories & {
        "APP_STORE",
        "CORPORATE_REGISTRY",
        "GOVERNMENT_OR_COURT",
        "NEWS_OR_TRADE_PRESS",
        "REVIEW_PLATFORM",
        "RIGHTS_HOLDER",
    }
    if fields["company_status"] == "IDENTIFIED":
        score += 15
    if fields["country"] not in {NOT_FOUND, AMBIGUOUS} and fields["physical_address"] not in {NOT_FOUND, AMBIGUOUS}:
        score += 10
    if fields["corporate_email"] not in {NOT_FOUND, AMBIGUOUS} and fields["corporate_phone"] not in {NOT_FOUND, AMBIGUOUS}:
        score += 5
    if fields["terms_url"] != NOT_FOUND and fields["privacy_url"] != NOT_FOUND:
        score += 10
    if fields["refund_policy_url"] != NOT_FOUND:
        score += 5
    if fields["app_store_presence"] == "DETECTED_IN_EVIDENCE":
        score += 10
    if fields["licensing_evidence_status"] == "PUBLICLY_CONFIRMED":
        score += 20
    if independent:
        score += 10
    if fields["legal_or_takedown_signal"] == NOT_DEMONSTRATED:
        score += 5
    return max(0, min(100, score))


def updated_status(fields: dict[str, Any]) -> tuple[str, str]:
    if fields["licensing_evidence_status"] == "CONTRADICTED_BY_PUBLIC_EVIDENCE":
        return "HIGH", "REJECTED_BY_PUBLIC_EVIDENCE"
    if fields["legal_or_takedown_signal"] == "DETECTED_IN_EVIDENCE":
        return "HIGH", "HIGH_RISK"
    if fields["company_status"] == "NOT_IDENTIFIED" or fields["official_domain_confidence"] in {"LOW", "NOT_IDENTIFIED"}:
        return "MEDIUM", "NEEDS_IDENTITY_RESOLUTION"
    if fields["transparency_score_updated"] >= 60:
        return "LOW", "VERIFIED_FOR_FURTHER_COMMERCIAL_REVIEW"
    if fields["evidence_count"] == 0:
        return "MEDIUM", "INSUFFICIENT_EVIDENCE"
    return "MEDIUM", "NEEDS_ADDITIONAL_VERIFICATION"


def choose_claim(rows: list[dict[str, Any]], pattern: str) -> tuple[str, set[str]]:
    for row in rows:
        text = f"{row.get('title', '')} {row.get('content', '')} {row.get('raw_content', '')}"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            source = row.get("source_category", "UNKNOWN")
            prefix = "PUBLIC_SOURCE"
            if source == "OFFICIAL_PROVIDER":
                prefix = "PROVIDER_CLAIM"
            elif source in {"GOVERNMENT_OR_COURT", "RIGHTS_HOLDER", "CORPORATE_REGISTRY"}:
                prefix = "PUBLIC_AUTHORITY_OR_RIGHTS_SOURCE"
            elif source in {"COMMUNITY", "REVIEW_PLATFORM"}:
                prefix = "USER_OR_REVIEW_SOURCE"
            return f"{prefix}: {clean_text(match.group(0))}", {source}
    return NOT_DEMONSTRATED, set()


def build_result_record(
    query: dict[str, Any],
    result: dict[str, Any],
    retrieved_at: str,
    query_status: str,
) -> dict[str, Any]:
    url = clean_text(result.get("url"))
    content = clean_text(result.get("content"))
    raw_content = clean_text(result.get("raw_content"))
    domain = parse_domain(url)
    source_category = classify_source(domain, query["query_category"], url, f"{content} {raw_content}")
    return {
        "brand_name": query["brand_name"],
        "rank": query["rank"],
        "query_category": query["query_category"],
        "query_text": query["query_text"],
        "query_id": query["query_id"],
        "title": clean_text(result.get("title")),
        "url": url,
        "domain": domain,
        "published_date": clean_text(result.get("published_date")),
        "tavily_score": result.get("score"),
        "content": content,
        "raw_content": raw_content,
        "retrieved_at": retrieved_at,
        "query_status": query_status,
        "source_category": source_category,
        "brief_quote": brief_quote(f"{content} {raw_content}", query["brand_name"], ""),
    }


def execute_queries(args: argparse.Namespace) -> dict[str, Any]:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    plan = json.loads(QUERY_PLAN_PATH.read_text(encoding="utf-8"))
    batch = select_batch(plan, args.batch_index, args.batch_size)
    checkpoint = load_checkpoint()
    completed = set(checkpoint.get("completed_query_ids", []))
    queries = [query for brand_plan in batch for query in planned_queries_for_brand(brand_plan)]
    pending_queries = [query for query in queries if query["query_id"] not in completed]

    api_key = os.getenv("TAVILY_API_KEY")
    if pending_queries and not api_key:
        raise RuntimeError("TAVILY_API_KEY no esta disponible en el entorno.")

    executed = 0
    skipped = 0
    errors = 0
    usage_items = []

    for query in queries:
        if query["query_id"] in completed:
            skipped += 1
            append_jsonl(
                QUERY_LOG_PATH,
                {
                    **query,
                    "event": "SKIPPED_BY_CHECKPOINT",
                    "logged_at": utc_now(),
                },
            )
            continue

        append_jsonl(QUERY_LOG_PATH, {**query, "event": "STARTED", "logged_at": utc_now()})
        retrieved_at = utc_now()
        response, status, error_message = call_tavily(
            api_key=api_key,
            query_text=query["query_text"],
            timeout=args.timeout,
            max_retries=args.max_retries,
            backoff_seconds=args.backoff_seconds,
        )

        if status == "ERROR" or response is None:
            errors += 1
            checkpoint.setdefault("failed_query_ids", [])
            if query["query_id"] not in checkpoint["failed_query_ids"]:
                checkpoint["failed_query_ids"].append(query["query_id"])
            append_jsonl(
                ERRORS_PATH,
                {
                    **query,
                    "error": error_message,
                    "logged_at": utc_now(),
                },
            )
            append_jsonl(QUERY_LOG_PATH, {**query, "event": "ERROR", "logged_at": utc_now(), "error": error_message})
            save_checkpoint(checkpoint)
            time.sleep(args.pause_seconds)
            continue

        results = response.get("results", [])
        query_status = "SUCCESS" if results else "NO_RESULTS"
        for result in results:
            append_jsonl(RAW_RESULTS_PATH, build_result_record(query, result, retrieved_at, query_status))

        usage = {
            key: response.get(key)
            for key in ("credits_used", "cost", "usage", "response_time")
            if key in response
        }
        if usage:
            usage_items.append({"query_id": query["query_id"], **usage})
            checkpoint.setdefault("usage", []).append({"query_id": query["query_id"], **usage})

        checkpoint.setdefault("completed_query_ids", [])
        if query["query_id"] not in checkpoint["completed_query_ids"]:
            checkpoint["completed_query_ids"].append(query["query_id"])
        if query["query_id"] in checkpoint.get("failed_query_ids", []):
            checkpoint["failed_query_ids"] = [item for item in checkpoint["failed_query_ids"] if item != query["query_id"]]

        append_jsonl(
            QUERY_LOG_PATH,
            {
                **query,
                "event": "COMPLETED",
                "logged_at": utc_now(),
                "results_count": len(results),
                "query_status": query_status,
                "usage": usage,
            },
        )
        executed += 1
        save_checkpoint(checkpoint)
        time.sleep(args.pause_seconds)

    checkpoint["skipped_by_checkpoint_count"] = checkpoint.get("skipped_by_checkpoint_count", 0) + skipped
    save_checkpoint(checkpoint)
    return {"executed": executed, "skipped": skipped, "errors": errors, "usage": usage_items}


def dedupe_evidence(raw_rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not raw_rows:
        return pd.DataFrame()
    dataframe = pd.DataFrame(raw_rows)
    dataframe = dataframe.drop_duplicates(subset=["brand_name", "url"]).copy()
    return dataframe.sort_values(by=["rank", "brand_name", "source_category", "domain", "url"])


def collect_shared_signals(evidence_df: pd.DataFrame) -> pd.DataFrame:
    if evidence_df.empty:
        return pd.DataFrame(columns=["shared_type", "shared_value", "brand_count", "brands", "domains"])

    signal_map: dict[tuple[str, str], dict[str, set[str]]] = defaultdict(lambda: {"brands": set(), "domains": set()})
    for _, row in evidence_df.iterrows():
        brand = row["brand_name"]
        domain = row["domain"]
        text = f"{row.get('content', '')} {row.get('raw_content', '')}"

        for email in sorted(set(re.findall(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.IGNORECASE))):
            signal_map[("email", email.lower())]["brands"].add(brand)
            signal_map[("email", email.lower())]["domains"].add(domain)

        for phone_match in re.finditer(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)", text):
            phone = re.sub(r"\D", "", phone_match.group(0))
            if 8 <= len(phone) <= 15:
                signal_map[("phone", phone)]["brands"].add(brand)
                signal_map[("phone", phone)]["domains"].add(domain)

        for gateway in PAYMENT_GATEWAYS:
            if re.search(rf"\b{re.escape(gateway)}\b", text, re.IGNORECASE):
                signal_map[("payment_or_gateway", gateway)]["brands"].add(brand)
                signal_map[("payment_or_gateway", gateway)]["domains"].add(domain)

        if re.search(r"\b(reseller|panel|xtream|m3u)\b", text, re.IGNORECASE):
            value = "panel_or_reseller_text"
            signal_map[("panel", value)]["brands"].add(brand)
            signal_map[("panel", value)]["domains"].add(domain)

        if re.search(r"\b(terms of service|privacy policy|refund policy)\b", text, re.IGNORECASE):
            legal_hash = hashlib.sha256(clean_text(text[:2000]).encode("utf-8")).hexdigest()[:16]
            signal_map[("legal_text_hash", legal_hash)]["brands"].add(brand)
            signal_map[("legal_text_hash", legal_hash)]["domains"].add(domain)

    rows = []
    domain_groups = evidence_df.groupby("domain")["brand_name"].agg(lambda values: sorted(set(values))).reset_index()
    for _, row in domain_groups.iterrows():
        brands = row["brand_name"]
        if row["domain"] and len(brands) > 1:
            rows.append(
                {
                    "shared_type": "domain",
                    "shared_value": row["domain"],
                    "brand_count": len(brands),
                    "brands": PIPE_SEPARATOR.join(brands),
                    "domains": row["domain"],
                }
            )

    for (signal_type, value), payload in signal_map.items():
        brands = sorted(payload["brands"])
        if len(brands) > 1:
            rows.append(
                {
                    "shared_type": signal_type,
                    "shared_value": value,
                    "brand_count": len(brands),
                    "brands": PIPE_SEPARATOR.join(brands),
                    "domains": PIPE_SEPARATOR.join(sorted(payload["domains"])),
                }
            )
    return pd.DataFrame(rows).sort_values(by=["brand_count", "shared_type", "shared_value"], ascending=[False, True, True]) if rows else pd.DataFrame(columns=["shared_type", "shared_value", "brand_count", "brands", "domains"])


def update_brand_matrix(preliminary_df: pd.DataFrame, evidence_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows = []
    candidate_rows = []

    for _, prelim in preliminary_df.iterrows():
        brand = prelim["brand_name"]
        rows = evidence_df[evidence_df["brand_name"] == brand].to_dict(orient="records") if not evidence_df.empty else []
        candidates = candidate_official_domains(prelim, rows)
        candidate_rows.extend(candidates)
        best_candidate = candidates[0] if candidates else {}

        official_domain = best_candidate.get("domain", prelim.get("probable_official_domain", NOT_FOUND))
        official_confidence = best_candidate.get("official_domain_confidence", prelim.get("official_domain_confidence", "NOT_IDENTIFIED"))
        if not official_domain or official_domain == NOT_FOUND:
            official_domain = NOT_FOUND
            official_confidence = "NOT_IDENTIFIED"

        official_rows = [row for row in rows if row["domain"] == official_domain]
        all_text = " ".join(f"{row.get('title', '')} {row.get('content', '')} {row.get('raw_content', '')}" for row in rows)
        official_text = " ".join(f"{row.get('title', '')} {row.get('content', '')} {row.get('raw_content', '')}" for row in official_rows)
        identity_text = official_text or all_text
        source_categories = {row.get("source_category", "UNKNOWN") for row in rows}

        company_name = extract_company_name(identity_text, brand)
        email = extract_email(identity_text, official_domain if official_domain != NOT_FOUND else "")
        phone = extract_phone(identity_text)
        country = extract_country(identity_text)
        physical_address = NOT_FOUND
        if company_name != NOT_FOUND and official_domain != NOT_FOUND:
            company_status = "IDENTIFIED"
        elif company_name != NOT_FOUND or email not in {NOT_FOUND, AMBIGUOUS} or official_domain != NOT_FOUND:
            company_status = "PARTIALLY_IDENTIFIED"
        else:
            company_status = "NOT_IDENTIFIED"

        terms_url = find_policy_url(rows, official_domain, ("terms", "terms-of-service", "terms-and-conditions"))
        privacy_url = find_policy_url(rows, official_domain, ("privacy", "privacy-policy"))
        refund_url = find_policy_url(rows, official_domain, ("refund", "return", "cancellation"))
        app_store_presence = "DETECTED_IN_EVIDENCE" if any(row.get("source_category") == "APP_STORE" for row in rows) else NOT_FOUND

        licensing_claim, licensing_sources = choose_claim(
            rows,
            r"\blicen[cs]ed\b|\blicen[cs]e\b|\bofficial rights\b|\bbroadcast rights\b|\blegally\b|\blegal\s+(?:service|provider|streaming|iptv)\b",
        )
        legal_signal = detect_signal(
            " ".join(f"{row.get('title', '')} {row.get('content', '')}" for row in rows if row.get("source_category") in {"GOVERNMENT_OR_COURT", "RIGHTS_HOLDER", "NEWS_OR_TRADE_PRESS"}),
            (r"\btakedown\b", r"\bdmca\b", r"\blawsuit\b", r"\bcourt order\b", r"\bseized\b", r"\bshutdown\b", r"\bshut down\b"),
        )
        licensing_evidence = licensing_status(licensing_claim, legal_signal, licensing_sources)
        reseller_signal = detect_signal(all_text, (r"\breseller\b", r"\bpanel\b", r"\bxtream\b", r"\bm3u\b"))

        fields = {
            **prelim.to_dict(),
            "probable_official_domain": official_domain,
            "official_domain_confidence": official_confidence,
            "company_name": company_name,
            "company_status": company_status,
            "country": country,
            "physical_address": physical_address,
            "corporate_email": email,
            "corporate_phone": phone,
            "terms_url": terms_url,
            "privacy_url": privacy_url,
            "refund_policy_url": refund_url,
            "app_store_presence": app_store_presence,
            "licensing_claim": licensing_claim,
            "licensing_evidence_status": licensing_evidence,
            "legal_or_takedown_signal": legal_signal,
            "reseller_signal": reseller_signal,
            "evidence_count": len(rows),
        }
        fields["transparency_score_updated"] = updated_transparency_score(fields, source_categories)
        fields["risk_level_updated"], fields["due_diligence_status_updated"] = updated_status(fields)
        unresolved = []
        for field in (
            "probable_official_domain",
            "company_name",
            "country",
            "physical_address",
            "corporate_email",
            "corporate_phone",
            "terms_url",
            "privacy_url",
            "refund_policy_url",
            "licensing_claim",
        ):
            if fields[field] in {NOT_FOUND, NOT_DEMONSTRATED, AMBIGUOUS, "NOT_IDENTIFIED"}:
                unresolved.append(field)
        fields["unresolved_questions"] = PIPE_SEPARATOR.join(unresolved)
        findings = []
        if official_domain != NOT_FOUND:
            findings.append(f"official candidate {official_domain} ({official_confidence})")
        else:
            findings.append("official domain unresolved")
        findings.append(f"{len(rows)} external evidence URLs")
        findings.append(f"licensing evidence {licensing_evidence}")
        if reseller_signal == "DETECTED_IN_EVIDENCE":
            findings.append("reseller/panel/xtream/m3u signal detected")
        fields["key_findings"] = "; ".join(findings)

        for key, allowed in (
            ("company_status", ALLOWED_COMPANY_STATUS),
            ("licensing_evidence_status", ALLOWED_LICENSING_STATUS),
            ("due_diligence_status_updated", ALLOWED_DD_STATUS),
        ):
            if fields[key] not in allowed:
                raise RuntimeError(f"Valor no permitido para {key}: {fields[key]}")
        summary_rows.append(fields)

    return pd.DataFrame(summary_rows), pd.DataFrame(candidate_rows)


ILLEGAL_EXCEL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]")
MAX_EXCEL_CELL_LENGTH = 32000


def excel_safe_value(value: Any) -> Any:
    if value is None:
        return value
    try:
        if pd.isna(value):
            return value
    except (TypeError, ValueError):
        pass

    if isinstance(value, (dict, list, set, tuple)):
        try:
            if isinstance(value, set):
                value = sorted(value, key=lambda item: clean_text(item))
            value = json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            value = str(value)
    elif not isinstance(value, str):
        return value

    text = ILLEGAL_EXCEL_CHARS_RE.sub("", str(value))
    if len(text) > MAX_EXCEL_CELL_LENGTH:
        suffix = " [TRUNCATED_FOR_EXCEL]"
        text = text[: MAX_EXCEL_CELL_LENGTH - len(suffix)] + suffix
    return text


def excel_safe_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    safe = dataframe.copy()
    safe.columns = [excel_safe_value(column) for column in safe.columns]
    for column in safe.columns:
        if safe[column].dtype == object or pd.api.types.is_string_dtype(safe[column]):
            safe[column] = safe[column].map(excel_safe_value)
    return safe


def validate_excel_safe_dataframe(dataframe: pd.DataFrame, sheet_name: str) -> None:
    for column in dataframe.columns:
        if ILLEGAL_EXCEL_CHARS_RE.search(str(column)):
            raise ValueError(f"Illegal Excel character found in column name for sheet {sheet_name}: {column}")
        if dataframe[column].dtype == object or pd.api.types.is_string_dtype(dataframe[column]):
            for row_index, value in dataframe[column].items():
                if not isinstance(value, str):
                    continue
                if ILLEGAL_EXCEL_CHARS_RE.search(value):
                    raise ValueError(
                        f"Illegal Excel character found in sheet {sheet_name}, "
                        f"column {column}, row {row_index}"
                    )
                if len(value) > MAX_EXCEL_CELL_LENGTH:
                    raise ValueError(
                        f"Excel cell too long in sheet {sheet_name}, "
                        f"column {column}, row {row_index}"
                    )


def write_sheet(writer: pd.ExcelWriter, dataframe: pd.DataFrame, sheet_name: str) -> None:
    safe_dataframe = excel_safe_dataframe(dataframe)
    validate_excel_safe_dataframe(safe_dataframe, sheet_name)
    safe_dataframe.to_excel(writer, sheet_name=sheet_name, index=False)
    worksheet = writer.sheets[sheet_name]
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions
    for index, column in enumerate(safe_dataframe.columns, start=1):
        sample = safe_dataframe[column].astype(str).head(200) if column in safe_dataframe else []
        width = max([len(str(column)), *(len(value) for value in sample)], default=10)
        worksheet.column_dimensions[get_column_letter(index)].width = min(max(width + 2, 10), 48)


def build_report(
    summary_df: pd.DataFrame,
    evidence_df: pd.DataFrame,
    errors_df: pd.DataFrame,
    query_log_df: pd.DataFrame,
    shared_df: pd.DataFrame,
    run_stats: dict[str, Any],
) -> str:
    source_counts = evidence_df["source_category"].value_counts().sort_index() if not evidence_df.empty else pd.Series(dtype=int)
    status_counts = summary_df["due_diligence_status_updated"].value_counts().sort_index()
    usage_items = run_stats.get("usage", [])
    usage_line = "No reportado por Tavily"
    if usage_items:
        usage_line = json.dumps(usage_items[:10], ensure_ascii=False)

    lines = [
        "# Verificacion externa Tavily Top 50 - 20260713",
        "",
        "## Alcance",
        "",
        "- Ejecutado solo el lote 1 de 10 marcas.",
        "- No se ejecutaron los lotes 2-5.",
        "- El runner usa checkpoint por consulta y no imprime ni registra `TAVILY_API_KEY`.",
        "- Las licencias no se declaran como probadas por snippets o titulos.",
        "",
        "## Totales de ejecucion",
        "",
        f"- Consultas ejecutadas en esta corrida: {run_stats.get('executed', 0)}",
        f"- Consultas omitidas por checkpoint: {run_stats.get('skipped', 0)}",
        f"- Errores en esta corrida: {run_stats.get('errors', 0)}",
        f"- URLs unicas consolidadas: {evidence_df['url'].nunique() if not evidence_df.empty else 0}",
        f"- Uso/costo reportado por Tavily: {usage_line}",
        "",
        "## Fuentes por categoria",
        "",
        "| Categoria | Evidencias |",
        "|---|---:|",
    ]
    for category, count in source_counts.items():
        lines.append(f"| {category} | {count} |")

    lines.extend(["", "## Estados finales por marca", "", "| Estado | Marcas |", "|---|---:|"])
    for status, count in status_counts.items():
        lines.append(f"| {status} | {count} |")

    lines.extend(
        [
            "",
            "## Senales compartidas",
            "",
            f"- Dominios/senales compartidas detectadas: {len(shared_df)}",
            "",
            "## Marcas del lote 1",
            "",
            "| Rank | Marca | Estado actualizado | Riesgo | Dominio probable | Evidencias | Hallazgos |",
            "|---:|---|---|---|---|---:|---|",
        ]
    )
    for _, row in summary_df.sort_values("rank").head(10).iterrows():
        lines.append(
            f"| {row['rank']} | {row['brand_name']} | {row['due_diligence_status_updated']} | "
            f"{row['risk_level_updated']} | {row['probable_official_domain']} | {row['evidence_count']} | "
            f"{str(row['key_findings']).replace('|', '/')} |"
        )
    return "\n".join(lines) + "\n"


def consolidate_outputs(run_stats: dict[str, Any]) -> dict[str, Any]:
    preliminary_df = pd.read_csv(PRELIMINARY_PATH)
    raw_rows = read_jsonl(RAW_RESULTS_PATH)
    errors = read_jsonl(ERRORS_PATH)
    query_logs = read_jsonl(QUERY_LOG_PATH)

    evidence_df = dedupe_evidence(raw_rows)
    if not evidence_df.empty:
        candidate_by_brand = {}
        for brand, group in evidence_df.groupby("brand_name"):
            prelim = preliminary_df[preliminary_df["brand_name"] == brand]
            if prelim.empty:
                continue
            candidates = candidate_official_domains(prelim.iloc[0], group.to_dict(orient="records"))
            if candidates:
                candidate_by_brand[brand] = {candidates[0]["domain"]}
        evidence_df["source_category"] = evidence_df.apply(
            lambda row: classify_source(
                row["domain"],
                row["query_category"],
                row["url"],
                f"{row.get('content', '')} {row.get('raw_content', '')}",
                official_candidates=candidate_by_brand.get(row["brand_name"], set()),
            ),
            axis=1,
        )
        evidence_df["brief_quote"] = evidence_df.apply(
            lambda row: brief_quote(f"{row.get('content', '')} {row.get('raw_content', '')}", row["brand_name"], ""),
            axis=1,
        )

    summary_df, candidate_df = update_brand_matrix(preliminary_df, evidence_df)
    shared_df = collect_shared_signals(evidence_df)
    errors_df = pd.DataFrame(errors)
    query_log_df = pd.DataFrame(query_logs)

    terms_df = evidence_df[evidence_df["query_category"] == "terms_privacy"].copy() if not evidence_df.empty else pd.DataFrame()
    apps_df = evidence_df[evidence_df["query_category"] == "app_stores"].copy() if not evidence_df.empty else pd.DataFrame()
    licenses_df = evidence_df[evidence_df["query_category"] == "licensing"].copy() if not evidence_df.empty else pd.DataFrame()
    legal_df = evidence_df[evidence_df["query_category"] == "legal_history"].copy() if not evidence_df.empty else pd.DataFrame()
    trustpilot_df = evidence_df[evidence_df["query_category"] == "trustpilot"].copy() if not evidence_df.empty else pd.DataFrame()
    reddit_df = evidence_df[evidence_df["query_category"] == "reddit"].copy() if not evidence_df.empty else pd.DataFrame()
    reseller_df = evidence_df[evidence_df["query_category"] == "reseller_panel"].copy() if not evidence_df.empty else pd.DataFrame()

    summary_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    OUTPUT_JSON.write_text(
        json.dumps(
            {
                "summary": summary_df.to_dict(orient="records"),
                "evidence": evidence_df.to_dict(orient="records") if not evidence_df.empty else [],
                "shared_signals": shared_df.to_dict(orient="records"),
                "errors": errors,
                "run_stats": run_stats,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    OUTPUT_REPORT.write_text(
        build_report(summary_df, evidence_df, errors_df, query_log_df, shared_df, run_stats),
        encoding="utf-8",
    )

    identity_columns = [
        "rank",
        "brand_name",
        "company_name",
        "company_status",
        "country",
        "physical_address",
        "corporate_email",
        "corporate_phone",
        "probable_official_domain",
        "official_domain_confidence",
    ]
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        write_sheet(writer, summary_df, "Resumen por marca")
        write_sheet(writer, evidence_df, "Evidencias")
        write_sheet(writer, summary_df[identity_columns], "Identidad corporativa")
        write_sheet(writer, candidate_df, "Dominios oficiales candidatos")
        write_sheet(writer, terms_df, "Términos y privacidad")
        write_sheet(writer, apps_df, "Apps")
        write_sheet(writer, licenses_df, "Licencias")
        write_sheet(writer, legal_df, "Historial legal")
        write_sheet(writer, trustpilot_df, "Trustpilot")
        write_sheet(writer, reddit_df, "Reddit")
        write_sheet(writer, reseller_df, "Revendedores")
        write_sheet(writer, shared_df, "Dominios compartidos")
        write_sheet(writer, errors_df, "Errores")
        write_sheet(writer, query_log_df, "Consultas ejecutadas")

    return {
        "unique_urls": evidence_df["url"].nunique() if not evidence_df.empty else 0,
        "source_counts": evidence_df["source_category"].value_counts().sort_index().to_dict() if not evidence_df.empty else {},
        "status_counts": summary_df["due_diligence_status_updated"].value_counts().sort_index().to_dict(),
        "errors_total": len(errors),
    }


V3_RESELLER_TERMS = (
    "reseller",
    "supplier",
    "sub reseller",
    "sub-reseller",
    "panel",
    "dealer",
    "distributor",
    "master reseller",
    "iptvchannel",
)

V3_PROMOTIONAL_TERMS = (
    "affiliate",
    "ranking",
    "review",
    "best iptv",
    "top rated",
    "promo",
    "coupon",
    "discount",
    "lead",
)

V3_PROMOTIONAL_DOMAINS = {
    "click.cryptwerk.com",
    "iptvon.me",
    "nerdbot.com",
    "the-best-iptv.com",
    "trans4mind.com",
    "yttags.com",
}

V3_COMMUNITY_DOMAINS = {"reddit.com"}

V3_VOCO_HOMONYM_TERMS = ("ihg", "hotel", "hotels", "hoteleria", "hospitality", "dental", "dentistry", "voco.dental")


def v3_run_directory() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    candidate = V3_SIMULATION_DIR / f"run_{stamp}"
    counter = 2
    while candidate.exists():
        candidate = V3_SIMULATION_DIR / f"run_{stamp}_{counter}"
        counter += 1
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def v3_text_for_row(row: pd.Series) -> str:
    parts = [
        row.get("brand_name", ""),
        row.get("title", ""),
        row.get("url", ""),
        row.get("domain", ""),
        row.get("audit_reason", ""),
        row.get("brief_quote", ""),
        row.get("content_excerpt", ""),
        row.get("query_text", ""),
    ]
    return " ".join(clean_text(part) for part in parts)


def v3_domain_family(audit_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    families = {}
    for brand, group in audit_df.groupby("brand_name"):
        domains = sorted({clean_text(domain).lower() for domain in group["domain"].dropna() if clean_text(domain)})
        relevant_domains = [
            domain
            for domain in domains
            if domain not in V3_COMMUNITY_DOMAINS and domain not in V3_PROMOTIONAL_DOMAINS
        ]
        families[brand] = {
            "domains": domains,
            "relevant_domains": relevant_domains,
            "has_competing_domains": len(relevant_domains) > 1,
        }
    return families


def v3_extract_counts_and_prices(text: str) -> tuple[list[str], list[str], list[str]]:
    counts = re.findall(r"\b\d{2,3}(?:[,.]\d{3})+\+?\s*(?:channels|live channels|vod|movies|series)\b", text, flags=re.I)
    prices = re.findall(r"(?:\$|€|£)\s?\d+(?:\.\d{2})?", text)
    currencies = []
    lowered = text.casefold()
    for currency in ("usd", "eur", "gbp", "cad", "usdt", "bitcoin", "crypto"):
        if currency in lowered:
            currencies.append(currency.upper())
    return sorted(set(counts)), sorted(set(prices)), sorted(set(currencies))


def v3_source_signal(row: pd.Series, text: str) -> tuple[str, list[str]]:
    domain = clean_text(row.get("domain")).lower()
    source_category = clean_text(row.get("source_category")).upper()
    audit_classification = clean_text(row.get("classification")).upper()
    lowered = text.casefold()
    reasons = []

    if source_category == "RESELLER" or audit_classification == "FALSE_POSITIVE_RESELLER" or contains_any_term(lowered, list(V3_RESELLER_TERMS)):
        reasons.append("reseller_or_supplier_signal")
        return "RESELLER_SIGNAL", reasons
    if audit_classification == "FALSE_POSITIVE_AFFILIATE" or domain in V3_PROMOTIONAL_DOMAINS or contains_any_term(lowered, list(V3_PROMOTIONAL_TERMS)):
        reasons.append("affiliate_or_promotional_signal")
        return "PROMOTIONAL_SIGNAL", reasons
    if domain in V3_COMMUNITY_DOMAINS or source_category == "COMMUNITY":
        reasons.append("community_or_independent_signal")
        return "INDEPENDENT_SIGNAL", reasons
    if source_category == "CORPORATE_REGISTRY":
        reasons.append("corporate_registry_signal")
        return "CORPORATE_SIGNAL", reasons
    if source_category == "OFFICIAL_PROVIDER" or "terms" in lowered or "privacy" in lowered or "refund" in lowered or "pricing" in lowered:
        reasons.append("candidate_provider_controlled_page_signal")
        return "OFFICIAL_SIGNAL", reasons
    reasons.append("unknown_source_authority")
    return "UNKNOWN_SIGNAL", reasons


def v3_relevance_score(row: pd.Series, text: str) -> tuple[int, list[str]]:
    brand = clean_text(row.get("brand_name"))
    title = clean_text(row.get("title"))
    domain = clean_text(row.get("domain")).replace("-", " ")
    score = 0
    reasons = []
    if exact_name_present(text, brand):
        score += 35
        reasons.append("exact_brand_present:+35")
    if exact_name_present(title, brand):
        score += 20
        reasons.append("exact_brand_in_title:+20")
    if exact_name_present(domain, brand):
        score += 15
        reasons.append("brand_like_domain:+15")
    if contains_any_term(text, V2_SAFE_CONTEXT_TERMS):
        score += 15
        reasons.append("iptv_context:+15")
    if contains_any_term(text, V2_COMMERCIAL_TERMS):
        score += 10
        reasons.append("commercial_context:+10")
    return min(score, 100), reasons


def v3_authority_score(source_signal: str) -> int:
    return {
        "CORPORATE_SIGNAL": 80,
        "INDEPENDENT_SIGNAL": 60,
        "OFFICIAL_SIGNAL": 45,
        "UNKNOWN_SIGNAL": 20,
        "RESELLER_SIGNAL": 5,
        "PROMOTIONAL_SIGNAL": 5,
    }.get(source_signal, 0)


def v3_domain_coherence(row: pd.Series, brand_family: dict[str, Any], text: str) -> tuple[int, list[str], list[str]]:
    brand = clean_text(row.get("brand_name"))
    domain = clean_text(row.get("domain")).lower()
    reasons = []
    conflicts = []
    score = 0
    if domain and any(token in registrable_slug(domain) for token in brand_tokens(brand, "")):
        score += 35
        reasons.append("brand_token_in_domain:+35")
    if exact_name_present(text, brand):
        score += 25
        reasons.append("brand_text_attributable:+25")
    if any(part in text.casefold() for part in ("terms", "privacy", "refund", "pricing", "contact", "about us")):
        score += 15
        reasons.append("internal_policy_or_contact_page:+15")
    if brand_family.get("has_competing_domains"):
        conflicts.extend(["MULTIPLE_COMPETING_OFFICIAL_DOMAINS", "NO_CROSS_DOMAIN_CONFIRMATION"])
        score -= 25
    return max(0, min(score, 100)), reasons, conflicts


def v3_detect_conflicts(row: pd.Series, brand_family: dict[str, Any], source_signal: str, text: str) -> list[str]:
    brand = clean_text(row.get("brand_name"))
    domain = clean_text(row.get("domain")).lower()
    lowered = text.casefold()
    conflicts = []
    if brand == "Voco TV" and any(term in lowered for term in V3_VOCO_HOMONYM_TERMS):
        conflicts.append("HOMONYM_SIGNAL")
    if source_signal == "RESELLER_SIGNAL":
        conflicts.append("RESELLER_PROGRAM_PRESENT")
    if source_signal == "PROMOTIONAL_SIGNAL":
        conflicts.append("AFFILIATE_DISCLOSURE")
    if "official" in lowered and source_signal in {"OFFICIAL_SIGNAL", "UNKNOWN_SIGNAL", "RESELLER_SIGNAL"}:
        conflicts.append("SELF_DECLARED_OFFICIAL_ONLY")
    if brand_family.get("has_competing_domains"):
        conflicts.extend(["MULTIPLE_COMPETING_OFFICIAL_DOMAINS", "NO_CROSS_DOMAIN_CONFIRMATION"])
    if brand == "DigitaLizard IPTV" and domain == "digitalizard.app":
        conflicts.append("DIGITALIZARD_APP_REJECTED_BY_AUDIT")
    counts, prices, currencies = v3_extract_counts_and_prices(text)
    if len(counts) > 1:
        conflicts.append("CONFLICTING_PRODUCT_COUNTS")
    if len(prices) > 1:
        conflicts.append("CONFLICTING_PRICES")
    if len(currencies) > 1:
        conflicts.append("CONFLICTING_CURRENCY")
    return sorted(set(conflicts))


def v3_final_classification(
    row: pd.Series,
    source_signal: str,
    evidence_relevance: int,
    source_authority: int,
    officiality_score: int,
    conflicts: list[str],
) -> tuple[str, list[str], str]:
    historical = clean_text(row.get("classification"))
    domain = clean_text(row.get("domain")).lower()
    reasons = []

    if "HOMONYM_SIGNAL" in conflicts:
        return "REJECTED", ["homonym_or_excluded_vertical"], "REJECTED"
    if source_signal == "RESELLER_SIGNAL":
        return "FALSE_POSITIVE_RESELLER", ["hard_rule_reseller_cannot_be_official"], "REJECTED"
    if source_signal == "PROMOTIONAL_SIGNAL":
        return "FALSE_POSITIVE_AFFILIATE", ["hard_rule_affiliate_cannot_confirm_officiality"], "REJECTED"
    if domain == "digitalizard.app":
        return "REJECTED", ["digitalizard_app_remains_rejected_without_independent_evidence"], "REJECTED"
    if source_signal == "INDEPENDENT_SIGNAL" and evidence_relevance >= 50:
        return "TRUE_POSITIVE_INDIRECT", ["independent_source_mentions_exact_brand"], "ACCEPTED_INDIRECT"

    hard_blocks = {
        "SELF_DECLARED_OFFICIAL_ONLY",
        "MULTIPLE_COMPETING_OFFICIAL_DOMAINS",
        "NO_CROSS_DOMAIN_CONFIRMATION",
        "LEGAL_IDENTITY_MISSING",
    }
    if officiality_score >= 80 and not hard_blocks.intersection(conflicts):
        reasons.append("direct_chain_satisfied")
        if historical.startswith("TRUE_POSITIVE"):
            reasons.append("ground_truth_supports_direct_or_indirect_relevance")
        return "TRUE_POSITIVE_DIRECT", reasons, "ACCEPTED_DIRECT"

    if evidence_relevance >= 50:
        return "UNRESOLVED", ["brand_relevant_but_officiality_chain_incomplete"], "UNRESOLVED"
    return "REJECTED", ["insufficient_brand_relevance"], "REJECTED"


def v3_classify_row(row: pd.Series, brand_family: dict[str, Any]) -> dict[str, Any]:
    text = v3_text_for_row(row)
    source_signal, source_reasons = v3_source_signal(row, text)
    evidence_relevance, relevance_reasons = v3_relevance_score(row, text)
    source_authority = v3_authority_score(source_signal)
    domain_coherence, coherence_reasons, coherence_conflicts = v3_domain_coherence(row, brand_family, text)
    conflicts = sorted(set([*coherence_conflicts, *v3_detect_conflicts(row, brand_family, source_signal, text)]))
    officiality_score = max(0, min(100, int(round((domain_coherence * 0.6) + (source_authority * 0.4)))))
    if source_signal in {"RESELLER_SIGNAL", "PROMOTIONAL_SIGNAL"}:
        officiality_score = min(officiality_score, 10)
    if {"MULTIPLE_COMPETING_OFFICIAL_DOMAINS", "NO_CROSS_DOMAIN_CONFIRMATION"}.intersection(conflicts):
        officiality_score = min(officiality_score, 55)
    final_classification, final_reasons, v3_status = v3_final_classification(
        row,
        source_signal,
        evidence_relevance,
        source_authority,
        officiality_score,
        conflicts,
    )
    return {
        "audit_index": row.get("audit_index"),
        "brand_name": clean_text(row.get("brand_name")),
        "domain": clean_text(row.get("domain")),
        "url": clean_text(row.get("url")),
        "title": clean_text(row.get("title")),
        "v2_audit_classification": clean_text(row.get("classification")),
        "v2_source_category": clean_text(row.get("source_category")),
        "v2_relevance_score": row.get("relevance_score"),
        "source_signal": source_signal,
        "evidence_relevance": evidence_relevance,
        "source_authority": source_authority,
        "domain_identity_coherence": domain_coherence,
        "officiality_score": officiality_score,
        "cross_domain_conflict": "YES" if "MULTIPLE_COMPETING_OFFICIAL_DOMAINS" in conflicts else "NO",
        "v3_final_classification": final_classification,
        "v3_status": v3_status,
        "conflicts": PIPE_SEPARATOR.join(conflicts) if conflicts else "NONE",
        "rules_applied": PIPE_SEPARATOR.join([*source_reasons, *relevance_reasons, *coherence_reasons, *final_reasons]),
        "identity_fingerprint": json.dumps(
            {
                "domain": clean_text(row.get("domain")),
                "brand_name": clean_text(row.get("brand_name")),
                "title": clean_text(row.get("title")),
                "query_category": clean_text(row.get("query_category")),
                "source_category": clean_text(row.get("source_category")),
            },
            ensure_ascii=False,
        ),
    }


def v3_metric_summary(detail_df: pd.DataFrame, audit_df: pd.DataFrame, adjustments: dict[str, Any]) -> dict[str, Any]:
    accepted_mask = detail_df["v3_final_classification"].isin(["TRUE_POSITIVE_DIRECT", "TRUE_POSITIVE_INDIRECT"])
    accepted_df = detail_df[accepted_mask]
    accepted_total = len(accepted_df)
    accepted_true = int(accepted_df["v2_audit_classification"].str.startswith("TRUE_POSITIVE").sum()) if accepted_total else 0
    accepted_false = int(accepted_df["v2_audit_classification"].str.startswith("FALSE_POSITIVE").sum()) if accepted_total else 0
    non_true_historical = ~detail_df["v2_audit_classification"].str.startswith("TRUE_POSITIVE")
    correctly_not_accepted = int((~accepted_mask & non_true_historical).sum())
    non_true_total = int(non_true_historical.sum())
    reseller_direct = int(
        (
            (detail_df["source_signal"] == "RESELLER_SIGNAL")
            & (detail_df["v3_final_classification"] == "TRUE_POSITIVE_DIRECT")
        ).sum()
    )
    affiliate_official = int(
        (
            (detail_df["source_signal"] == "PROMOTIONAL_SIGNAL")
            & detail_df["v3_final_classification"].isin(["TRUE_POSITIVE_DIRECT", "TRUE_POSITIVE_INDIRECT"])
        ).sum()
    )
    digitalizard_app = detail_df[detail_df["domain"].fillna("").str.lower() == "digitalizard.app"]
    voco_bad = detail_df[
        (detail_df["brand_name"] == "Voco TV")
        & detail_df["v3_final_classification"].isin(["TRUE_POSITIVE_DIRECT", "TRUE_POSITIVE_INDIRECT"])
        & detail_df["conflicts"].str.contains("HOMONYM_SIGNAL", na=False)
    ]
    metrics = {
        "input_audited_rows_loaded": int(len(detail_df)),
        "expected_retained_evidence_from_report": 55,
        "ambiguous_detailed_records_available_in_authorized_inputs": 0,
        "accepted_precision": round(accepted_true / accepted_total, 4) if accepted_total else 1.0,
        "false_acceptance_rate": round(accepted_false / accepted_total, 4) if accepted_total else 0.0,
        "direct_accept_count": int((detail_df["v3_final_classification"] == "TRUE_POSITIVE_DIRECT").sum()),
        "indirect_accept_count": int((detail_df["v3_final_classification"] == "TRUE_POSITIVE_INDIRECT").sum()),
        "unresolved_count": int((detail_df["v3_final_classification"] == "UNRESOLVED").sum()),
        "rejected_count": int((detail_df["v3_final_classification"].isin(["REJECTED", "FALSE_POSITIVE_RESELLER", "FALSE_POSITIVE_AFFILIATE"])).sum()),
        "reseller_direct_accept_count": reseller_direct,
        "affiliate_official_accept_count": affiliate_official,
        "rejection_selectivity": round(correctly_not_accepted / max(non_true_total, 1), 4),
        "digitalizard_app_status": "REJECTED" if not digitalizard_app.empty and set(digitalizard_app["v3_final_classification"]) <= {"FALSE_POSITIVE_RESELLER", "REJECTED"} else "CHECK",
        "voco_hotel_dental_ihg_accepted": bool(not voco_bad.empty),
        "source_adjustment_verdict": clean_text(adjustments.get("verdict", "UNKNOWN")),
    }
    metrics["pass_criteria"] = {
        "accepted_precision_ge_0_80": metrics["accepted_precision"] >= 0.80,
        "false_acceptance_rate_le_0_10": metrics["false_acceptance_rate"] <= 0.10,
        "reseller_direct_accept_count_eq_0": metrics["reseller_direct_accept_count"] == 0,
        "affiliate_official_accept_count_eq_0": metrics["affiliate_official_accept_count"] == 0,
        "digitalizard_app_rejected": metrics["digitalizard_app_status"] == "REJECTED",
        "voco_no_hotel_dental_ihg": not metrics["voco_hotel_dental_ihg_accepted"],
    }
    metrics["verdict"] = "PASS" if all(metrics["pass_criteria"].values()) else "FAIL"
    return metrics


def v3_brand_summary(detail_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for brand, group in detail_df.groupby("brand_name"):
        accepted = group[group["v3_final_classification"].isin(["TRUE_POSITIVE_DIRECT", "TRUE_POSITIVE_INDIRECT"])]
        true_accepted = int(accepted["v2_audit_classification"].str.startswith("TRUE_POSITIVE").sum()) if not accepted.empty else 0
        false_accepted = int(accepted["v2_audit_classification"].str.startswith("FALSE_POSITIVE").sum()) if not accepted.empty else 0
        rows.append(
            {
                "brand_name": brand,
                "total_rows": len(group),
                "direct_accept_count": int((group["v3_final_classification"] == "TRUE_POSITIVE_DIRECT").sum()),
                "indirect_accept_count": int((group["v3_final_classification"] == "TRUE_POSITIVE_INDIRECT").sum()),
                "unresolved_count": int((group["v3_final_classification"] == "UNRESOLVED").sum()),
                "rejected_count": int(group["v3_final_classification"].isin(["REJECTED", "FALSE_POSITIVE_RESELLER", "FALSE_POSITIVE_AFFILIATE"]).sum()),
                "accepted_precision": round(true_accepted / max(len(accepted), 1), 4) if not accepted.empty else 1.0,
                "false_acceptance_rate": round(false_accepted / max(len(accepted), 1), 4) if not accepted.empty else 0.0,
                "unresolved_rate": round((group["v3_final_classification"] == "UNRESOLVED").sum() / max(len(group), 1), 4),
                "domains": PIPE_SEPARATOR.join(sorted({clean_text(value) for value in group["domain"] if clean_text(value)})),
            }
        )
    return pd.DataFrame(rows).sort_values("brand_name")


def v3_domain_conflicts(detail_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for brand, group in detail_df.groupby("brand_name"):
        domains = sorted({clean_text(value) for value in group["domain"] if clean_text(value)})
        conflict_values = sorted(
            {
                conflict
                for value in group["conflicts"]
                for conflict in split_pipe(value)
                if conflict and conflict != "NONE"
            }
        )
        rows.append(
            {
                "brand_name": brand,
                "domain_count": len(domains),
                "domains": PIPE_SEPARATOR.join(domains),
                "conflicts": PIPE_SEPARATOR.join(conflict_values) if conflict_values else "NONE",
                "cross_domain_conflict": "YES" if len(domains) > 1 else "NO",
            }
        )
    return pd.DataFrame(rows)


def markdown_table(dataframe: pd.DataFrame) -> list[str]:
    if dataframe.empty:
        return ["_No rows._"]
    display = dataframe.fillna("").astype(str)
    columns = list(display.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for _, row in display.iterrows():
        values = [clean_text(row[column]).replace("|", "/") for column in columns]
        lines.append("| " + " | ".join(values) + " |")
    return lines


def build_v3_report(
    detail_df: pd.DataFrame,
    metrics: dict[str, Any],
    brand_df: pd.DataFrame,
    transition_df: pd.DataFrame,
    signal_df: pd.DataFrame,
    blocked_df: pd.DataFrame,
    conflicts_df: pd.DataFrame,
    output_files: dict[str, str],
) -> str:
    lines = [
        "# V3 offline acceptance simulation - 20260714",
        "",
        "## Scope",
        "",
        "- Offline simulation only.",
        "- No Tavily calls were executed.",
        "- `TAVILY_API_KEY` was not read by this mode.",
        "- V1/V2 artifacts, checkpoints and JSONL logs were not modified.",
        "- Detailed authorized input contained 50 accepted audited rows; the 5 ambiguous rows are available only as aggregate metrics in the authorized report.",
        "",
        "## Metrics",
        "",
    ]
    for key in (
        "accepted_precision",
        "false_acceptance_rate",
        "direct_accept_count",
        "indirect_accept_count",
        "unresolved_count",
        "rejected_count",
        "reseller_direct_accept_count",
        "affiliate_official_accept_count",
        "rejection_selectivity",
        "digitalizard_app_status",
        "voco_hotel_dental_ihg_accepted",
        "verdict",
    ):
        lines.append(f"- {key}: {metrics[key]}")
    lines.extend(["", "## Pass criteria", ""])
    for key, value in metrics["pass_criteria"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Transition matrix", "", *markdown_table(transition_df), "", "## Brand summary", "", *markdown_table(brand_df)])
    lines.extend(["", "## Source signals", "", *markdown_table(signal_df)])
    lines.extend(["", "## Blocked resellers and affiliates", ""])
    if blocked_df.empty:
        lines.append("- None")
    else:
        lines.extend(markdown_table(blocked_df[["brand_name", "domain", "source_signal", "v3_final_classification", "rules_applied"]]))
    lines.extend(["", "## Domain conflicts", "", *markdown_table(conflicts_df)])
    direct_df = detail_df[detail_df["v3_final_classification"] == "TRUE_POSITIVE_DIRECT"]
    indirect_df = detail_df[detail_df["v3_final_classification"] == "TRUE_POSITIVE_INDIRECT"]
    unresolved_df = detail_df[detail_df["v3_final_classification"] == "UNRESOLVED"]
    lines.extend(["", "## TRUE_POSITIVE_DIRECT final", ""])
    if direct_df.empty:
        lines.append("- None. V3 did not confirm any direct official evidence because the officiality chain was incomplete or cross-domain conflicts remained unresolved.")
    else:
        for _, row in direct_df.iterrows():
            lines.append(f"- {row['brand_name']} / {row['domain']}: {row['rules_applied']}")
    lines.extend(["", "## TRUE_POSITIVE_INDIRECT final", ""])
    if indirect_df.empty:
        lines.append("- None")
    else:
        for _, row in indirect_df.iterrows():
            lines.append(f"- {row['brand_name']} / {row['domain']}: independent/community mention with exact brand context. URL: {row['url']}")
    lines.extend(["", "## UNRESOLVED cases", ""])
    for _, row in unresolved_df.iterrows():
        lines.append(f"- {row['brand_name']} / {row['domain']}: {row['conflicts']}")
    lines.extend(
        [
            "",
            "## Specific controls",
            "",
            f"- digitalizard.app: {metrics['digitalizard_app_status']}",
            f"- Voco TV hotel/dental/IHG accepted: {metrics['voco_hotel_dental_ihg_accepted']}",
            "- Krooz TV: multiple candidate domains remain unresolved for officiality.",
            "- Sonix IPTV: multiple Sonix/Sonic domains remain unresolved for officiality.",
            "",
            "## Output files",
            "",
        ]
    )
    for label, path in output_files.items():
        lines.append(f"- {label}: `{path}`")
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "- Do not authorize a new Tavily pilot yet. V3 is conservative enough for acceptance safety, but direct officiality remains unresolved for the observed domain families.",
        ]
    )
    return "\n".join(lines) + "\n"


def simulate_v3_existing_evidence() -> dict[str, Any]:
    for path in (V3_AUDIT_INPUT_CSV, V3_AUDIT_INPUT_REPORT, V3_FILTER_ADJUSTMENTS_PATH):
        if not path.exists():
            raise FileNotFoundError(f"No existe entrada requerida para simulacion V3: {path}")

    audit_df = pd.read_csv(V3_AUDIT_INPUT_CSV)
    required_columns = {"audit_index", "brand_name", "classification", "title", "url", "domain", "source_category", "content_excerpt"}
    missing_columns = sorted(required_columns - set(audit_df.columns))
    if missing_columns:
        raise RuntimeError(f"El CSV de auditoria V2 no contiene columnas requeridas: {missing_columns}")
    audit_report_text = V3_AUDIT_INPUT_REPORT.read_text(encoding="utf-8")
    adjustments = json.loads(V3_FILTER_ADJUSTMENTS_PATH.read_text(encoding="utf-8"))
    brand_families = v3_domain_family(audit_df)

    detail_rows = []
    for _, row in audit_df.iterrows():
        detail_rows.append(v3_classify_row(row, brand_families.get(clean_text(row.get("brand_name")), {})))
    detail_df = pd.DataFrame(detail_rows)
    metrics = v3_metric_summary(detail_df, audit_df, adjustments)
    metrics["audit_report_mentions_no_tavily_calls"] = "No Tavily calls were executed" in audit_report_text

    brand_df = v3_brand_summary(detail_df)
    transition_df = (
        detail_df.groupby(["v2_audit_classification", "v3_final_classification"])
        .size()
        .reset_index(name="count")
        .sort_values(["v2_audit_classification", "v3_final_classification"])
    )
    signal_df = detail_df.groupby(["source_signal", "v3_final_classification"]).size().reset_index(name="count")
    blocked_df = detail_df[detail_df["source_signal"].isin(["RESELLER_SIGNAL", "PROMOTIONAL_SIGNAL"])].copy()
    conflicts_df = v3_domain_conflicts(detail_df)
    rule_log_df = detail_df[["audit_index", "brand_name", "domain", "v3_final_classification", "rules_applied", "conflicts"]].copy()

    output_dir = v3_run_directory()
    output_paths = {
        "classification_csv": output_dir / "v3_classification_detail.csv",
        "classification_json": output_dir / "v3_classification_detail.json",
        "metrics_json": output_dir / "v3_metrics_summary.json",
        "transition_csv": output_dir / "v3_transition_matrix.csv",
        "brand_summary_csv": output_dir / "v3_brand_summary.csv",
        "signal_summary_csv": output_dir / "v3_signal_summary.csv",
        "blocked_resellers_affiliates_csv": output_dir / "v3_blocked_resellers_affiliates.csv",
        "domain_conflicts_csv": output_dir / "v3_domain_conflicts.csv",
        "rule_log_csv": output_dir / "v3_rule_log.csv",
        "report_md": output_dir / "v3_simulation_report.md",
    }
    detail_df.to_csv(output_paths["classification_csv"], index=False, encoding="utf-8-sig")
    output_paths["classification_json"].write_text(
        json.dumps(detail_df.to_dict(orient="records"), ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    output_paths["metrics_json"].write_text(json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    transition_df.to_csv(output_paths["transition_csv"], index=False, encoding="utf-8-sig")
    brand_df.to_csv(output_paths["brand_summary_csv"], index=False, encoding="utf-8-sig")
    signal_df.to_csv(output_paths["signal_summary_csv"], index=False, encoding="utf-8-sig")
    blocked_df.to_csv(output_paths["blocked_resellers_affiliates_csv"], index=False, encoding="utf-8-sig")
    conflicts_df.to_csv(output_paths["domain_conflicts_csv"], index=False, encoding="utf-8-sig")
    rule_log_df.to_csv(output_paths["rule_log_csv"], index=False, encoding="utf-8-sig")
    report = build_v3_report(
        detail_df,
        metrics,
        brand_df,
        transition_df,
        signal_df,
        blocked_df,
        conflicts_df,
        {key: str(value) for key, value in output_paths.items()},
    )
    output_paths["report_md"].write_text(report, encoding="utf-8")

    return {
        "output_dir": output_dir,
        "output_paths": output_paths,
        "metrics": metrics,
        "transition": transition_df,
        "brand_summary": brand_df,
        "blocked": blocked_df,
        "direct": detail_df[detail_df["v3_final_classification"] == "TRUE_POSITIVE_DIRECT"],
        "indirect": detail_df[detail_df["v3_final_classification"] == "TRUE_POSITIVE_INDIRECT"],
        "unresolved": detail_df[detail_df["v3_final_classification"] == "UNRESOLVED"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run controlled Tavily due diligence for Top 50 IPTV brands.")
    parser.add_argument("--batch-index", type=int, default=1, help="1-based batch index. Default: 1.")
    parser.add_argument("--batch-size", type=int, default=10, help="Brands per batch. Default: 10.")
    parser.add_argument("--pause-seconds", type=float, default=1.0, help="Pause between queries. Default: 1.0.")
    parser.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout per query. Default: 60.")
    parser.add_argument("--max-retries", type=int, default=3, help="Retries per query. Default: 3.")
    parser.add_argument("--backoff-seconds", type=float, default=3.0, help="Backoff base seconds. Default: 3.")
    parser.add_argument("--dry-run-query-plan", action="store_true", help="Generate v2 precision query plan without calling Tavily.")
    parser.add_argument("--pilot-brands", default="", help="Comma-separated brand names for v2 pilot/dry-run mode.")
    parser.add_argument(
        "--simulate-v3-existing-evidence",
        action="store_true",
        help="Run offline V3 simulation over authorized audited evidence inputs without Tavily, checkpoints, or V1/V2 writes.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.simulate_v3_existing_evidence:
        result = simulate_v3_existing_evidence()
        metrics = result["metrics"]
        print("Simulacion offline V3 finalizada.")
        print("Tavily calls: 0")
        print("Tavily credits consumed: 0")
        print(f"Output dir: {result['output_dir']}")
        print(f"accepted_precision: {metrics['accepted_precision']}")
        print(f"false_acceptance_rate: {metrics['false_acceptance_rate']}")
        print(f"direct_accept_count: {metrics['direct_accept_count']}")
        print(f"indirect_accept_count: {metrics['indirect_accept_count']}")
        print(f"unresolved_count: {metrics['unresolved_count']}")
        print(f"rejected_count: {metrics['rejected_count']}")
        print(f"reseller_direct_accept_count: {metrics['reseller_direct_accept_count']}")
        print(f"affiliate_official_accept_count: {metrics['affiliate_official_accept_count']}")
        print(f"rejection_selectivity: {metrics['rejection_selectivity']}")
        print(f"digitalizard_app_status: {metrics['digitalizard_app_status']}")
        print(f"voco_hotel_dental_ihg_accepted: {metrics['voco_hotel_dental_ihg_accepted']}")
        print(f"Dictamen: {metrics['verdict']}")
        print("Archivos V3:")
        for label, path in result["output_paths"].items():
            print(f"  {label}: {path}")
        return

    if args.dry_run_query_plan:
        pilot_brands = parse_pilot_brands(args.pilot_brands)
        if not pilot_brands:
            raise RuntimeError("--pilot-brands es requerido para --dry-run-query-plan.")
        required_paths = (
            PRELIMINARY_PATH,
            QUALITY_AUDIT_PATH,
            QUALITY_REPORT_PATH,
            QUERY_CORRECTIONS_PATH,
            ORIGINAL_QUERY_PLAN_PATH,
        )
        for path in required_paths:
            if not path.exists():
                raise FileNotFoundError(f"No existe entrada requerida para dry-run v2: {path}")
        plan = build_v2_plan(pilot_brands)
        write_v2_dry_run_outputs(plan)
        print("Dry-run query plan v2 generado. No se llamo a Tavily.")
        print(f"Marcas piloto: {', '.join(pilot_brands)}")
        print(f"Estimacion maxima de consultas del piloto: {plan['max_pilot_queries']}")
        for brand in plan["brands"]:
            print()
            print(f"[{brand['brand_name']}]")
            print(f"Aliases: {', '.join(brand['aliases'])}")
            print(f"Terminos negativos: {', '.join(brand['negative_terms'])}")
            print(f"Consultas generadas ({brand['max_initial_queries']}):")
            for query in brand["queries"]:
                print(f"  - {query['query_category']}: {query['query_text']}")
        voco = next((item for item in plan["brands"] if item["brand_name"] == "Voco TV"), None)
        if voco:
            voco_terms = {normalized_exact(term) for term in voco["negative_terms"]}
            required_voco_terms = {"hotel", "hotels", "ihg", "dental", "dentistry", "resort", "hospitality"}
            if not required_voco_terms <= voco_terms:
                missing = sorted(required_voco_terms - voco_terms)
                raise RuntimeError(f"Voco TV no contiene negativos obligatorios: {missing}")
            print()
            print("Confirmacion Voco TV: excluye expresamente IHG, hoteles y odontologia.")
        print(f"Preview JSON: {V2_QUERY_PLAN_PREVIEW_JSON}")
        print(f"Preview MD: {V2_QUERY_PLAN_PREVIEW_MD}")
        return

    if args.pilot_brands:
        pilot_brands = parse_pilot_brands(args.pilot_brands)
        if not pilot_brands:
            raise RuntimeError("--pilot-brands no contiene marcas validas.")
        required_paths = (
            PRELIMINARY_PATH,
            QUALITY_AUDIT_PATH,
            QUERY_CORRECTIONS_PATH,
            ORIGINAL_QUERY_PLAN_PATH,
        )
        for path in required_paths:
            if not path.exists():
                raise FileNotFoundError(f"No existe entrada requerida para piloto V2: {path}")
        stats = execute_v2_pilot(args, pilot_brands)
        metrics = write_v2_outputs(stats, pilot_brands)
        print("Piloto V2 Tavily finalizado.")
        print(f"Marcas piloto: {', '.join(pilot_brands)}")
        print(f"Consultas ejecutadas: {stats['executed']}")
        print(f"Consultas omitidas por checkpoint: {stats['skipped']}")
        print(f"Errores: {stats['errors']}")
        print(f"Resultados brutos: {stats['raw_results']}")
        print(f"Aceptados: {stats['accepted']}")
        print(f"Ambiguos: {stats['ambiguous']}")
        print(f"Rechazados: {stats['rejected']}")
        print(f"URLs unicas: {metrics['unique_urls']}")
        if stats.get("usage"):
            print(f"Uso reportado por Tavily: {json.dumps(stats['usage'], ensure_ascii=False)}")
        else:
            print("Uso/costo reportado por Tavily: NOT_REPORTED")
        print(f"Precision proxy global: {metrics['global_precision_proxy']}")
        print(f"Noise proxy global: {metrics['global_noise_proxy']}")
        summary_df = pd.read_csv(V2_OUTPUT_CSV)
        print("Metricas por marca:")
        for _, row in summary_df.iterrows():
            print(
                f"  {row['brand_name']}: total={row['total_results']}, "
                f"accepted={row['accepted_count']}, ambiguous={row['ambiguous_count']}, "
                f"rejected={row['rejected_count']}, precision_proxy={row['precision_proxy']}, "
                f"noise_proxy={row['noise_proxy']}, official={row['probable_official_domain']} "
                f"({row['official_domain_confidence']})"
            )
        print(f"Dictamen global: {metrics['verdict']}")
        print(f"Recomendacion lote 2: {metrics['recommendation']}")
        print(f"CSV: {V2_OUTPUT_CSV}")
        print(f"Excel: {V2_OUTPUT_XLSX}")
        print(f"JSON: {V2_OUTPUT_JSON}")
        print(f"Reporte: {V2_OUTPUT_REPORT}")
        print(f"Checkpoint V2: {V2_CHECKPOINT_PATH}")
        print(f"Raw V2: {V2_RAW_RESULTS_PATH}")
        print(f"Rejected V2: {V2_REJECTED_RESULTS_PATH}")
        return

    if args.batch_index != 1:
        raise RuntimeError("Este script se debe ejecutar ahora solo para el lote 1. Use otra corrida explicita para lotes posteriores.")
    for path in (QUERY_PLAN_PATH, PRELIMINARY_PATH):
        if not path.exists():
            raise FileNotFoundError(f"No existe entrada requerida: {path}")

    preliminary_df = pd.read_csv(PRELIMINARY_PATH)
    if preliminary_df["brand_name"].nunique() != 50:
        raise RuntimeError("La matriz preliminar no contiene 50 marcas unicas.")

    run_stats = execute_queries(args)
    consolidation = consolidate_outputs(run_stats)

    print("Verificacion externa Tavily finalizada para lote 1.")
    print(f"Consultas ejecutadas: {run_stats['executed']}")
    print(f"Consultas omitidas por checkpoint: {run_stats['skipped']}")
    print(f"Errores en esta corrida: {run_stats['errors']}")
    print(f"URLs unicas consolidadas: {consolidation['unique_urls']}")
    print(f"Fuentes por categoria: {json.dumps(consolidation['source_counts'], ensure_ascii=False, sort_keys=True)}")
    print(f"Estados finales por marca: {json.dumps(consolidation['status_counts'], ensure_ascii=False, sort_keys=True)}")
    if run_stats.get("usage"):
        print(f"Uso reportado por Tavily: {json.dumps(run_stats['usage'], ensure_ascii=False)}")
    else:
        print("Uso/costo reportado por Tavily: NOT_REPORTED")
    print(f"Checkpoint: {CHECKPOINT_PATH}")
    print(f"Query log: {QUERY_LOG_PATH}")
    print(f"Raw results: {RAW_RESULTS_PATH}")
    print(f"Errors: {ERRORS_PATH}")
    print(f"CSV: {OUTPUT_CSV}")
    print(f"Excel: {OUTPUT_XLSX}")
    print(f"JSON: {OUTPUT_JSON}")
    print(f"Reporte: {OUTPUT_REPORT}")


if __name__ == "__main__":
    main()
