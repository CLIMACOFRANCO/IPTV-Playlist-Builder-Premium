from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
from openpyxl.utils import get_column_letter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "research" / "output" / "best_iptv_2026"
WORK_DIR = OUTPUT_DIR / "tavily_due_diligence"

INPUT_EXTERNAL_CSV = OUTPUT_DIR / "top50_external_evidence_20260713.csv"
INPUT_EXTERNAL_JSON = OUTPUT_DIR / "top50_external_evidence_20260713.json"
INPUT_REPORT = OUTPUT_DIR / "top50_external_verification_report_20260713.md"
INPUT_RAW_RESULTS = WORK_DIR / "raw_results.jsonl"
INPUT_QUERY_LOG = WORK_DIR / "query_log.jsonl"

OUTPUT_CSV = OUTPUT_DIR / "batch1_quality_audit_20260713.csv"
OUTPUT_XLSX = OUTPUT_DIR / "batch1_quality_audit_20260713.xlsx"
OUTPUT_REPORT = OUTPUT_DIR / "batch1_quality_report_20260713.md"
OUTPUT_QUERY_CORRECTIONS = OUTPUT_DIR / "query_corrections_for_batches_2_5_20260713.json"

PIPE_SEPARATOR = " | "

AUDIT_CLASSES = {
    "RELEVANT_DIRECT",
    "RELEVANT_INDIRECT",
    "AMBIGUOUS",
    "HOMONYM",
    "IRRELEVANT",
    "DUPLICATE",
}

SOURCE_TYPES = {
    "OFFICIAL_PROVIDER",
    "CORPORATE_REGISTRY",
    "GOVERNMENT_OR_COURT",
    "RIGHTS_HOLDER",
    "APP_STORE",
    "NEWS_OR_TRADE_PRESS",
    "REVIEW_PLATFORM",
    "COMMUNITY",
    "AFFILIATE_OR_PROMOTIONAL",
    "RESELLER",
    "UNKNOWN",
}

GENERIC_WORDS = {
    "best",
    "buy",
    "channels",
    "free",
    "guide",
    "iptv",
    "legal",
    "live",
    "m3u",
    "ott",
    "panel",
    "player",
    "provider",
    "reseller",
    "review",
    "service",
    "stream",
    "streaming",
    "subscription",
    "trial",
    "tv",
    "xtream",
}

AFFILIATE_DOMAINS = {
    "bestiptvfinder.com",
    "bestiptvfreetrials.com",
    "guru99.com",
    "iptvrankings.com",
    "iptvserviceradar.com",
    "softwaretestinghelp.com",
    "topiptvreviews.com",
    "troypoint.com",
}

SELF_PUBLISH_DOMAINS = {
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

REVIEW_DOMAINS = {"trustpilot.com", "reviews.io", "sitejabber.com", "scamadviser.com"}
APP_STORE_DOMAINS = {"apps.apple.com", "play.google.com", "amazon.com", "amazon.co.uk"}
RIGHTS_HOLDER_DOMAINS = {"alliance4creativity.com", "fact-uk.org.uk", "ifpi.org", "motionpictures.org", "riaa.com"}
NEWS_DOMAINS = {"torrentfreak.com", "theverge.com", "techcrunch.com", "wired.com", "cordcuttersnews.com"}

CORPORATE_REGISTRY_MARKERS = ("opencorporates", "companieshouse", "sec.gov", "corporations", "registry", "businesssearch")

HOMONYM_TERMS_BY_BRAND = {
    "Voco TV": {"hotel", "hotels", "ihg", "voco hotels", "dental", "dentist", "voco.dental"},
    "Digita Line IPTV": {"digita.fi", "digital agency", "marketing agency", "design agency"},
    "Zorba IPTV": {"zorba softed", "zorbasofted", "education", "school", "software development"},
    "Sonix IPTV": {"sonix.ai", "transcription", "audio transcription", "speech to text"},
}

BASE_NEGATIVE_TERMS = {
    "hotel",
    "hotels",
    "dental",
    "dentist",
    "restaurant",
    "school",
    "education",
    "transcription",
    "agency",
    "pdf",
    "annual report",
    "investor relations",
}


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return re.sub(r"\s+", " ", str(value)).strip()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def parse_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


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


def compact(value: str) -> str:
    value = clean_text(value).lower()
    value = re.sub(r"\b(iptv|tv|ott|hd|4k|plus|pro|stream|streams|service|services)\b", " ", value)
    return re.sub(r"[^a-z0-9]+", "", value)


def split_pipe(value: Any) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    return [part.strip() for part in text.split(PIPE_SEPARATOR) if part.strip()]


def brand_alias_tokens(brand_name: str, aliases: str) -> set[str]:
    tokens = {compact(brand_name), re.sub(r"[^a-z0-9]+", "", brand_name.lower())}
    for alias in split_pipe(aliases):
        tokens.add(compact(alias))
        tokens.add(re.sub(r"[^a-z0-9]+", "", alias.lower()))
    return {token for token in tokens if len(token) >= 4}


def lexical_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]{3,}", clean_text(value).lower())
        if token not in GENERIC_WORDS
    }


def corrected_source_type(row: dict[str, Any], brand_name: str, aliases: str) -> tuple[str, str]:
    domain = clean_text(row.get("domain")).lower()
    url = clean_text(row.get("url")).lower()
    text = f"{row.get('title', '')} {row.get('content', '')} {row.get('raw_content', '')}".lower()
    original = clean_text(row.get("source_category")) or "UNKNOWN"

    if domain in RIGHTS_HOLDER_DOMAINS:
        return "RIGHTS_HOLDER", "rights-holder domain"
    if domain.endswith(".gov") or "court" in domain or "justice" in domain or "judiciary" in domain:
        return "GOVERNMENT_OR_COURT", "government/court domain"
    if any(marker in domain or marker in url for marker in CORPORATE_REGISTRY_MARKERS):
        return "CORPORATE_REGISTRY", "corporate registry marker"
    if domain in APP_STORE_DOMAINS or domain.endswith("play.google.com") or domain.endswith("apps.apple.com"):
        return "APP_STORE", "app store domain"
    if domain in REVIEW_DOMAINS:
        return "REVIEW_PLATFORM", "review platform domain"
    if domain in COMMUNITY_DOMAINS:
        return "COMMUNITY", "community/video/social domain"
    if domain in NEWS_DOMAINS:
        return "NEWS_OR_TRADE_PRESS", "news/trade press domain"
    if domain in AFFILIATE_DOMAINS or domain in SELF_PUBLISH_DOMAINS or "bestiptv" in domain or "iptvreview" in domain:
        return "AFFILIATE_OR_PROMOTIONAL", "affiliate/self-published/promotional domain"
    if "reseller" in text or "reseller" in url:
        return "RESELLER", "reseller text/url signal"

    if original == "OFFICIAL_PROVIDER":
        alias_tokens = brand_alias_tokens(brand_name, aliases)
        slug = registrable_slug(domain)
        direct_domain_match = any(slug == token or slug in token or token in slug for token in alias_tokens)
        direct_evidence = any(term in url for term in ("terms", "privacy", "refund", "contact", "about")) or re.search(
            r"\bofficial\s+(website|site|app|store)\b", text
        )
        if direct_domain_match and direct_evidence:
            return "OFFICIAL_PROVIDER", "domain matches brand and direct official/policy signal exists"
        return "UNKNOWN", "downgraded: no direct official evidence"

    return original if original in SOURCE_TYPES else "UNKNOWN", "kept or normalized original source category"


def has_homonym_signal(row: dict[str, Any], brand_name: str) -> tuple[bool, str]:
    text = f"{row.get('title', '')} {row.get('url', '')} {row.get('domain', '')} {row.get('content', '')} {row.get('raw_content', '')}".lower()
    brand_terms = HOMONYM_TERMS_BY_BRAND.get(brand_name, set())
    matched = sorted(term for term in brand_terms if term.lower() in text)
    if matched:
        return True, ", ".join(matched[:5])
    return False, ""


def generic_only_match(row: dict[str, Any], brand_name: str, aliases: str) -> bool:
    text = f"{row.get('title', '')} {row.get('content', '')}".lower()
    alias_tokens = lexical_tokens(brand_name)
    for alias in split_pipe(aliases):
        alias_tokens.update(lexical_tokens(alias))
    if not alias_tokens:
        return True
    text_tokens = lexical_tokens(text)
    return not bool(alias_tokens & text_tokens)


def relevance_status(
    row: dict[str, Any],
    brand_name: str,
    aliases: str,
    duplicate_urls_seen: set[tuple[str, str]],
    corrected_type: str,
) -> tuple[str, str]:
    brand_url_key = (brand_name, clean_text(row.get("url")))
    if brand_url_key in duplicate_urls_seen:
        return "DUPLICATE", "duplicate brand-url in raw results"
    duplicate_urls_seen.add(brand_url_key)

    homonym, homonym_reason = has_homonym_signal(row, brand_name)
    if homonym:
        return "HOMONYM", f"homonym signal: {homonym_reason}"

    domain = clean_text(row.get("domain")).lower()
    url = clean_text(row.get("url")).lower()
    title = clean_text(row.get("title"))
    content = clean_text(row.get("content"))
    raw_content = clean_text(row.get("raw_content"))
    full_text = f"{title} {content} {raw_content}".lower()

    if url.endswith(".pdf") and not any(token in full_text for token in brand_alias_tokens(brand_name, aliases)):
        return "IRRELEVANT", "PDF with no brand/alias evidence"

    if generic_only_match(row, brand_name, aliases):
        return "IRRELEVANT", "match appears based only on generic IPTV terms"

    if corrected_type == "OFFICIAL_PROVIDER":
        return "RELEVANT_DIRECT", "direct official/policy/domain evidence"
    if corrected_type in {"APP_STORE", "CORPORATE_REGISTRY", "GOVERNMENT_OR_COURT", "RIGHTS_HOLDER", "NEWS_OR_TRADE_PRESS", "REVIEW_PLATFORM"}:
        return "RELEVANT_INDIRECT", f"indirect corroborating source: {corrected_type}"
    if corrected_type in {"AFFILIATE_OR_PROMOTIONAL", "COMMUNITY", "RESELLER"}:
        return "RELEVANT_INDIRECT", f"mention from {corrected_type}; not proof of official identity"
    if domain and registrable_slug(domain) in brand_alias_tokens(brand_name, aliases):
        return "AMBIGUOUS", "domain slug resembles brand but lacks direct official evidence"
    return "AMBIGUOUS", "brand mention present but source relationship unclear"


def safe_quote(row: dict[str, Any], brand_name: str, aliases: str) -> str:
    text = clean_text(f"{row.get('title', '')}. {row.get('content', '')}. {row.get('raw_content', '')}")
    tokens = brand_alias_tokens(brand_name, aliases)
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        compact_sentence = re.sub(r"[^a-z0-9]+", "", sentence.lower())
        if any(token in compact_sentence for token in tokens):
            return " ".join(sentence.split()[:24])
    return " ".join(text.split()[:24])


def build_audit_rows(raw_rows: list[dict[str, Any]], summary_df: pd.DataFrame) -> pd.DataFrame:
    summary_by_brand = summary_df.set_index("brand_name").to_dict(orient="index")
    batch1_brands = summary_df.sort_values("rank").head(10)["brand_name"].tolist()
    raw_rows = [row for row in raw_rows if row.get("brand_name") in batch1_brands]
    audited = []
    duplicate_seen: set[tuple[str, str]] = set()

    for raw_index, row in enumerate(raw_rows, start=1):
        brand_name = clean_text(row.get("brand_name"))
        summary = summary_by_brand[brand_name]
        aliases = clean_text(summary.get("aliases"))
        corrected_type, correction_reason = corrected_source_type(row, brand_name, aliases)
        audit_class, audit_reason = relevance_status(row, brand_name, aliases, duplicate_seen, corrected_type)
        audited.append(
            {
                "raw_index": raw_index,
                "rank": int(row.get("rank") or summary.get("rank")),
                "brand_name": brand_name,
                "aliases": aliases,
                "url": clean_text(row.get("url")),
                "domain": clean_text(row.get("domain")) or parse_domain(clean_text(row.get("url"))),
                "query_category": clean_text(row.get("query_category")),
                "query_text": clean_text(row.get("query_text")),
                "title": clean_text(row.get("title")),
                "original_source_type": clean_text(row.get("source_category")) or "UNKNOWN",
                "corrected_source_type": corrected_type,
                "source_type_correction_reason": correction_reason,
                "evidence_quality": audit_class,
                "quality_reason": audit_reason,
                "tavily_score": row.get("tavily_score"),
                "brief_quote": safe_quote(row, brand_name, aliases),
                "is_unique_url": "",
                "raw_duplicate_group_count": 0,
                "retrieved_at": clean_text(row.get("retrieved_at")),
            }
        )

    dataframe = pd.DataFrame(audited)
    if dataframe.empty:
        return dataframe

    brand_url_counts = dataframe.groupby(["brand_name", "url"]).size().to_dict()
    global_url_counts = dataframe.groupby("url").size().to_dict()
    first_url_seen = set()
    is_unique_url = []
    for _, row in dataframe.iterrows():
        url = row["url"]
        is_unique_url.append("YES" if url not in first_url_seen else "NO")
        first_url_seen.add(url)
    dataframe["is_unique_url"] = is_unique_url
    dataframe["raw_duplicate_group_count"] = dataframe.apply(
        lambda row: int(brand_url_counts.get((row["brand_name"], row["url"]), 1)),
        axis=1,
    )
    dataframe["shared_url_brand_count"] = dataframe["url"].map(global_url_counts)
    return dataframe


def summarize_by_brand(audit_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for brand_name, group in audit_df.groupby("brand_name", sort=False):
        non_duplicate = group[group["evidence_quality"] != "DUPLICATE"]
        denom = max(len(non_duplicate), 1)
        counts = group["evidence_quality"].value_counts().to_dict()
        relevant = counts.get("RELEVANT_DIRECT", 0) + counts.get("RELEVANT_INDIRECT", 0)
        noisy = counts.get("HOMONYM", 0) + counts.get("IRRELEVANT", 0)
        rows.append(
            {
                "rank": int(group["rank"].iloc[0]),
                "brand_name": brand_name,
                "total_evidence": len(group),
                "unique_urls": group["url"].nunique(),
                "relevant_direct_count": counts.get("RELEVANT_DIRECT", 0),
                "relevant_indirect_count": counts.get("RELEVANT_INDIRECT", 0),
                "ambiguous_count": counts.get("AMBIGUOUS", 0),
                "homonym_count": counts.get("HOMONYM", 0),
                "irrelevant_count": counts.get("IRRELEVANT", 0),
                "duplicate_count": counts.get("DUPLICATE", 0),
                "precision_rate": round(relevant / denom, 4),
                "noise_rate": round(noisy / denom, 4),
            }
        )
    return pd.DataFrame(rows).sort_values("rank")


def shared_domains_and_signals(audit_df: pd.DataFrame, raw_rows: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for domain, group in audit_df.groupby("domain"):
        brands = sorted(set(group["brand_name"]))
        if domain and len(brands) > 1:
            rows.append(
                {
                    "shared_type": "domain",
                    "shared_value": domain,
                    "brand_count": len(brands),
                    "brands": PIPE_SEPARATOR.join(brands),
                    "evidence_count": len(group),
                }
            )

    signal_map: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in raw_rows:
        brand = clean_text(row.get("brand_name"))
        text = clean_text(f"{row.get('content', '')} {row.get('raw_content', '')}")
        for email in sorted(set(re.findall(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.IGNORECASE))):
            signal_map[("email", email.lower())].add(brand)
        for phone_match in re.finditer(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)", text):
            digits = re.sub(r"\D", "", phone_match.group(0))
            if 8 <= len(digits) <= 15:
                signal_map[("phone", digits)].add(brand)
        for gateway in ("paypal", "stripe", "visa", "mastercard", "bitcoin", "crypto", "usdt", "coinbase"):
            if re.search(rf"\b{re.escape(gateway)}\b", text, re.IGNORECASE):
                signal_map[("payment_account_or_gateway", gateway)].add(brand)
        if re.search(r"\b(terms of service|privacy policy|refund policy)\b", text, re.IGNORECASE):
            legal_hash = hashlib.sha256(clean_text(text[:2000]).encode("utf-8")).hexdigest()[:16]
            signal_map[("legal_text_hash", legal_hash)].add(brand)

    for (signal_type, value), brands_set in signal_map.items():
        brands = sorted(brand for brand in brands_set if brand)
        if len(brands) > 1:
            rows.append(
                {
                    "shared_type": signal_type,
                    "shared_value": value,
                    "brand_count": len(brands),
                    "brands": PIPE_SEPARATOR.join(brands),
                    "evidence_count": "",
                }
            )

    return pd.DataFrame(rows).sort_values(["brand_count", "shared_type", "shared_value"], ascending=[False, True, True]) if rows else pd.DataFrame(columns=["shared_type", "shared_value", "brand_count", "brands", "evidence_count"])


def official_domain_audit(audit_df: pd.DataFrame, summary_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    summary_by_brand = summary_df.set_index("brand_name").to_dict(orient="index")
    for brand_name in summary_df.sort_values("rank").head(10)["brand_name"]:
        summary = summary_by_brand[brand_name]
        candidate = clean_text(summary.get("probable_official_domain"))
        if candidate in {"", "NOT_FOUND"}:
            rows.append(
                {
                    "rank": int(summary["rank"]),
                    "brand_name": brand_name,
                    "candidate_domain": "NOT_FOUND",
                    "audit_decision": "NO_OFFICIAL_DOMAIN_CONFIRMED",
                    "reason": "no candidate domain in consolidated output",
                }
            )
            continue
        group = audit_df[(audit_df["brand_name"] == brand_name) & (audit_df["domain"] == candidate)]
        direct_count = int((group["corrected_source_type"] == "OFFICIAL_PROVIDER").sum())
        homonym_count = int((group["evidence_quality"] == "HOMONYM").sum())
        if direct_count > 0 and homonym_count == 0:
            decision = "OFFICIAL_CANDIDATE_RETAINED"
            reason = "direct official/policy signal found"
        elif homonym_count > 0:
            decision = "REJECT_OFFICIAL_CANDIDATE"
            reason = "homonym evidence detected"
        else:
            decision = "DOWNGRADE_TO_UNCONFIRMED"
            reason = "no direct official evidence; do not declare official"
        rows.append(
            {
                "rank": int(summary["rank"]),
                "brand_name": brand_name,
                "candidate_domain": candidate,
                "audit_decision": decision,
                "reason": reason,
                "candidate_evidence_count": len(group),
                "direct_count": direct_count,
                "homonym_count": homonym_count,
            }
        )
    return pd.DataFrame(rows)


def query_problem_rows(query_log_rows: list[dict[str, Any]], audit_df: pd.DataFrame) -> pd.DataFrame:
    problem_counter = defaultdict(lambda: Counter())
    for _, row in audit_df.iterrows():
        if row["evidence_quality"] in {"HOMONYM", "IRRELEVANT", "AMBIGUOUS"}:
            key = (row["brand_name"], row["query_category"], row["query_text"])
            problem_counter[key][row["evidence_quality"]] += 1

    rows = []
    for (brand, category, query_text), counts in problem_counter.items():
        rows.append(
            {
                "brand_name": brand,
                "query_category": category,
                "query_text": query_text,
                "ambiguous": counts.get("AMBIGUOUS", 0),
                "homonym": counts.get("HOMONYM", 0),
                "irrelevant": counts.get("IRRELEVANT", 0),
                "problem_score": counts.get("AMBIGUOUS", 0) + counts.get("HOMONYM", 0) * 2 + counts.get("IRRELEVANT", 0) * 2,
                "recommended_fix": "Add exact brand phrase plus IPTV/provider/service and brand-specific negative terms.",
            }
        )
    return pd.DataFrame(rows).sort_values(["problem_score", "brand_name"], ascending=[False, True]) if rows else pd.DataFrame(columns=["brand_name", "query_category", "query_text", "ambiguous", "homonym", "irrelevant", "problem_score", "recommended_fix"])


def negative_terms(summary_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in summary_df.sort_values("rank").iterrows():
        brand = row["brand_name"]
        terms = set(BASE_NEGATIVE_TERMS)
        terms.update(HOMONYM_TERMS_BY_BRAND.get(brand, set()))
        if row["rank"] > 10:
            terms.update({"unrelated company", "jobs", "linkedin", "stock", "hotel", "restaurant", "school"})
        rows.append(
            {
                "rank": int(row["rank"]),
                "brand_name": brand,
                "negative_terms": sorted(terms),
            }
        )
    return pd.DataFrame(rows)


def corrected_queries(summary_df: pd.DataFrame, negatives_df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    negative_by_brand = {row["brand_name"]: row["negative_terms"] for _, row in negatives_df.iterrows()}
    json_plan = []
    flat_rows = []
    categories = {
        "identity": [
            '"{brand}" ("IPTV" OR "TV service") ("about" OR "contact")',
            '"{brand}" ("LLC" OR "Ltd" OR "Inc" OR "company") IPTV',
        ],
        "official_domain": [
            '"{brand}" "official" ("IPTV" OR "streaming") -review -best',
        ],
        "corporate_registry": [
            '"{brand}" ("company registration" OR "corporate registry") IPTV',
        ],
        "terms_privacy": [
            '"{brand}" ("terms of service" OR "privacy policy" OR "refund policy") IPTV',
        ],
        "app_stores": [
            'site:play.google.com OR site:apps.apple.com "{brand}" IPTV',
        ],
        "licensing": [
            '"{brand}" ("broadcast rights" OR "licensed channels" OR "copyright compliance") IPTV',
            '"{brand}" ("DMCA" OR "copyright" OR "rights holder") IPTV',
        ],
        "legal_history": [
            '"{brand}" ("lawsuit" OR "court" OR "takedown" OR "seized") IPTV',
        ],
        "trustpilot": [
            'site:trustpilot.com/review "{brand}"',
        ],
        "reddit": [
            'site:reddit.com "{brand}" IPTV -hotel -restaurant -dental',
        ],
        "reseller_panel": [
            '"{brand}" ("reseller panel" OR "Xtream Codes" OR "M3U")',
        ],
    }
    for _, row in summary_df[summary_df["rank"].between(11, 50)].sort_values("rank").iterrows():
        brand = row["brand_name"]
        negatives = negative_by_brand.get(brand, [])
        suffix = " ".join(f'-"{term}"' if " " in term else f"-{term}" for term in negatives[:14])
        brand_plan = {"rank": int(row["rank"]), "brand_name": brand, "negative_terms": negatives, "queries": {}}
        for category, templates in categories.items():
            queries = [f"{template.format(brand=brand)} {suffix}".strip() for template in templates]
            brand_plan["queries"][category] = queries
            for query in queries:
                flat_rows.append(
                    {
                        "rank": int(row["rank"]),
                        "brand_name": brand,
                        "query_category": category,
                        "corrected_query": query,
                        "execute_now": "NO",
                    }
                )
        json_plan.append(brand_plan)
    return pd.DataFrame(flat_rows), json_plan


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
                value = sorted(value)
            value = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
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


def write_sheet(writer: pd.ExcelWriter, dataframe: pd.DataFrame, sheet_name: str) -> None:
    safe = excel_safe_dataframe(dataframe)
    safe.to_excel(writer, sheet_name=sheet_name, index=False)
    worksheet = writer.sheets[sheet_name]
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions
    for index, column in enumerate(safe.columns, start=1):
        sample = safe[column].astype(str).head(200) if column in safe else []
        width = max([len(str(column)), *(len(value) for value in sample)], default=10)
        worksheet.column_dimensions[get_column_letter(index)].width = min(max(width + 2, 10), 48)


def build_report(
    summary_df: pd.DataFrame,
    audit_df: pd.DataFrame,
    official_df: pd.DataFrame,
    shared_df: pd.DataFrame,
    problem_df: pd.DataFrame,
    global_precision: float,
    global_noise: float,
    verdict: str,
    recommendation: str,
) -> str:
    counts = audit_df["evidence_quality"].value_counts()
    corrected_source_counts = audit_df["corrected_source_type"].value_counts().sort_index()
    lines = [
        "# Auditoria de calidad Tavily batch 1 - 20260713",
        "",
        "## Alcance",
        "",
        "- No se realizaron consultas nuevas a Tavily.",
        "- Se auditaron las 10 marcas procesadas en el lote 1.",
        f"- Pares marca-URL auditados: {len(audit_df)}.",
        f"- URLs unicas contabilizadas: {audit_df['url'].nunique()}.",
        "",
        "## Dictamen global",
        "",
        f"- Dictamen: {verdict}",
        f"- Recomendacion: {recommendation}",
        f"- Precision global: {global_precision:.4f}",
        f"- Ruido global: {global_noise:.4f}",
        f"- Falsos positivos/irrelevantes: {int(counts.get('IRRELEVANT', 0))}",
        f"- Homonimos: {int(counts.get('HOMONYM', 0))}",
        f"- Duplicados: {int(counts.get('DUPLICATE', 0))}",
        "",
        "## Precision por marca",
        "",
        "| Rank | Marca | Evidencias | URLs unicas | Precision | Ruido | Homonimos | Irrelevantes | Duplicados |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in summary_df.iterrows():
        lines.append(
            f"| {row['rank']} | {row['brand_name']} | {row['total_evidence']} | {row['unique_urls']} | "
            f"{row['precision_rate']:.4f} | {row['noise_rate']:.4f} | {row['homonym_count']} | "
            f"{row['irrelevant_count']} | {row['duplicate_count']} |"
        )

    lines.extend(["", "## Source type corregido", "", "| Source type | Evidencias |", "|---|---:|"])
    for source_type, count in corrected_source_counts.items():
        lines.append(f"| {source_type} | {count} |")

    lines.extend(
        [
            "",
            "## Voco / IHG hotels",
            "",
            "Se detectaron y marcaron como HOMONYM las evidencias asociadas a `voco hotels`, `IHG` o dominios/fragmentos no relacionados con Voco TV. Estas evidencias no deben alimentar dominio oficial ni licencias de la marca IPTV.",
            "",
            "## Dominios oficiales",
            "",
        ]
    )
    for _, row in official_df.iterrows():
        lines.append(f"- {row['brand_name']}: {row['candidate_domain']} -> {row['audit_decision']} ({row['reason']})")

    lines.extend(
        [
            "",
            "## Problemas de consulta",
            "",
            f"- Consultas problematicas detectadas: {len(problem_df)}",
            "- Ajuste recomendado: usar frase exacta de marca, anclar a IPTV/streaming, excluir homonimos por marca y reducir dominios afiliados en busquedas de identidad/oficialidad.",
            "",
            "## Senales compartidas",
            "",
            f"- Dominios o senales compartidas detectadas: {len(shared_df)}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    for path in (INPUT_EXTERNAL_CSV, INPUT_EXTERNAL_JSON, INPUT_REPORT, INPUT_RAW_RESULTS, INPUT_QUERY_LOG):
        if not path.exists():
            raise FileNotFoundError(f"No existe entrada requerida: {path}")

    external_df = pd.read_csv(INPUT_EXTERNAL_CSV)
    if external_df["brand_name"].nunique() != 50:
        raise RuntimeError("La matriz externa no contiene 50 marcas unicas.")

    batch1_brands = external_df.sort_values("rank").head(10)["brand_name"].tolist()
    raw_rows = read_jsonl(INPUT_RAW_RESULTS)
    query_log_rows = read_jsonl(INPUT_QUERY_LOG)

    audit_df = build_audit_rows(raw_rows, external_df)
    if sorted(audit_df["brand_name"].unique()) != sorted(batch1_brands):
        raise RuntimeError("No se identificaron exactamente las 10 marcas del lote 1.")

    unique_urls = audit_df["url"].nunique()
    if unique_urls != 625:
        raise RuntimeError(f"Se esperaban 625 URLs unicas contabilizadas y se encontraron {unique_urls}.")

    invalid_classes = set(audit_df["evidence_quality"]) - AUDIT_CLASSES
    if invalid_classes:
        raise RuntimeError(f"Clases de auditoria no permitidas: {sorted(invalid_classes)}")

    invalid_sources = set(audit_df["corrected_source_type"]) - SOURCE_TYPES
    if invalid_sources:
        raise RuntimeError(f"Source types corregidos no permitidos: {sorted(invalid_sources)}")

    summary_df = summarize_by_brand(audit_df)
    non_duplicate = audit_df[audit_df["evidence_quality"] != "DUPLICATE"]
    relevant_total = int(non_duplicate["evidence_quality"].isin(["RELEVANT_DIRECT", "RELEVANT_INDIRECT"]).sum())
    noise_total = int(non_duplicate["evidence_quality"].isin(["HOMONYM", "IRRELEVANT"]).sum())
    global_precision = round(relevant_total / max(len(non_duplicate), 1), 4)
    global_noise = round(noise_total / max(len(non_duplicate), 1), 4)

    if global_precision < 0.55 or global_noise > 0.35:
        verdict = "FAIL_REQUIRES_QUERY_REDESIGN"
        recommendation = "No ejecutar lote 2; primero modificar el buscador y consultas negativas."
    elif global_precision < 0.75 or global_noise > 0.20:
        verdict = "PASS_WITH_ADJUSTMENTS"
        recommendation = "Ejecutar lote 2 solo despues de aplicar consultas corregidas y negativas por marca."
    else:
        verdict = "PASS"
        recommendation = "Puede ejecutarse lote 2 con monitoreo normal."

    official_df = official_domain_audit(audit_df, external_df)
    shared_df = shared_domains_and_signals(audit_df, raw_rows)
    problem_df = query_problem_rows(query_log_rows, audit_df)
    negatives_df = negative_terms(external_df)
    corrected_queries_df, corrected_json = corrected_queries(external_df, negatives_df)

    false_positive_df = audit_df[audit_df["evidence_quality"].isin(["IRRELEVANT", "HOMONYM"])].copy()
    homonym_df = audit_df[audit_df["evidence_quality"] == "HOMONYM"].copy()
    source_corrections_df = audit_df[
        audit_df["original_source_type"] != audit_df["corrected_source_type"]
    ][
        [
            "rank",
            "brand_name",
            "url",
            "domain",
            "original_source_type",
            "corrected_source_type",
            "source_type_correction_reason",
            "evidence_quality",
        ]
    ].copy()

    audit_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    OUTPUT_QUERY_CORRECTIONS.write_text(
        json.dumps(
            {
                "global_verdict": verdict,
                "recommendation": recommendation,
                "batches": "2-5",
                "query_design_rules": [
                    "Use exact brand phrase plus IPTV or streaming context.",
                    "Do not use snippets/titles alone for official domain or licensing proof.",
                    "Add brand-specific negative terms for homonyms.",
                    "Avoid treating affiliate/review domains as official identity evidence.",
                ],
                "brands": corrected_json,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    OUTPUT_REPORT.write_text(
        build_report(
            summary_df,
            audit_df,
            official_df,
            shared_df,
            problem_df,
            global_precision,
            global_noise,
            verdict,
            recommendation,
        ),
        encoding="utf-8",
    )

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        write_sheet(writer, summary_df, "Resumen por marca")
        write_sheet(writer, audit_df, "Evidencias auditadas")
        write_sheet(writer, false_positive_df, "Falsos positivos")
        write_sheet(writer, homonym_df, "Homónimos")
        write_sheet(writer, official_df, "Dominios oficiales")
        write_sheet(writer, source_corrections_df, "Clasificación corregida")
        write_sheet(writer, shared_df, "Dominios compartidos")
        write_sheet(writer, problem_df, "Consultas problemáticas")
        write_sheet(writer, corrected_queries_df, "Consultas corregidas")
        write_sheet(writer, negatives_df, "Términos negativos")

    print("Auditoria de calidad batch 1 finalizada.")
    print(f"Marcas lote 1: {', '.join(batch1_brands)}")
    print(f"URLs unicas contabilizadas: {unique_urls}")
    print(f"Pares marca-URL auditados: {len(audit_df)}")
    print(f"Precision global: {global_precision:.4f}")
    print(f"Ruido global: {global_noise:.4f}")
    print(f"Falsos positivos/irrelevantes: {int((audit_df['evidence_quality'] == 'IRRELEVANT').sum())}")
    print(f"Homonimos: {int((audit_df['evidence_quality'] == 'HOMONYM').sum())}")
    print(f"Duplicados: {int((audit_df['evidence_quality'] == 'DUPLICATE').sum())}")
    print("Precision por marca:")
    for _, row in summary_df.iterrows():
        print(f"  {row['brand_name']}: {row['precision_rate']:.4f}")
    print(f"Dictamen global: {verdict}")
    print(f"Recomendacion lote 2: {recommendation}")
    print(f"CSV: {OUTPUT_CSV}")
    print(f"Excel: {OUTPUT_XLSX}")
    print(f"Reporte: {OUTPUT_REPORT}")
    print(f"Consultas corregidas JSON: {OUTPUT_QUERY_CORRECTIONS}")


if __name__ == "__main__":
    main()
