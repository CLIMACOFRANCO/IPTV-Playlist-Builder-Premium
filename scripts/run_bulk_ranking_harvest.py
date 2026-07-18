#!/usr/bin/env python3
"""Integral Tavily ranking harvest runner with local dynamic filtering.

Preparation, preflight, summaries and tests are offline. Real SDK calls require
the exact approval token, PowerShell origin and an inherited TAVILY_API_KEY.
Raw responses are persisted in the run and are never printed to normal output.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import tempfile
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TASK = "DYNAMIC-SEARCH-INTEGRAL-RUNNER-01"
MILESTONE = "BULK-RANKING-HARVEST-01"
APPROVAL_TOKEN = "BULK-RANKING-HARVEST-01"
SCHEMA_VERSION = "bulk_ranking_harvest.v1"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / (
    "research/output/best_iptv_2026/brand_first_market_universe/"
    "bulk_ranking_harvest_01"
)
FIX4_NAMES = PROJECT_ROOT / (
    "research/output/best_iptv_2026/brand_first_market_universe_1a/"
    "run_20260717_051437/02_raw_brand_mentions.csv"
)

REQUEST_BUDGET = {
    "search": 24,
    "map": 10,
    "crawl": 4,
    "extract": 3,
    "global": 41,
    "max_retry_per_operation": 1,
}
CONTENT_LIMITS = {
    "search_results": 240,
    "mapped_urls": 600,
    "crawled_pages": 100,
    "extract_fallback_urls": 60,
    "extract_batch_size": 20,
}
RANKING_SCORE_THRESHOLD = 60
SEARCH_CONFIG = {
    "search_depth": "advanced",
    "max_results": 10,
    "auto_parameters": False,
    "include_answer": False,
    "include_images": False,
    "include_raw_content": "markdown",
    "topic": "general",
    "include_usage": True,
}
MAP_CONFIG = {
    "max_depth": 2,
    "max_breadth": 50,
    "limit": 60,
    "allow_external": False,
    "timeout": 150,
    "include_usage": True,
    "instructions": (
        "Find IPTV service rankings, provider comparisons, regional IPTV lists, "
        "subscription reviews and pages that compare multiple IPTV services."
    ),
}
CRAWL_CONFIG = {
    "max_depth": 2,
    "max_breadth": 30,
    "limit": 25,
    "allow_external": False,
    "extract_depth": "advanced",
    "format": "markdown",
    "include_images": False,
    "timeout": 150,
    "include_usage": True,
    "instructions": (
        "Find and extract pages that rank, compare or list multiple IPTV "
        "subscription services or IPTV providers. Exclude player apps, setup "
        "tutorials, hardware, TV boxes, privacy, terms, contact and checkout pages."
    ),
}
EXTRACT_CONFIG = {
    "extract_depth": "advanced",
    "format": "markdown",
    "include_images": False,
    "include_usage": True,
    "timeout": 60,
}
EXCLUDE_DOMAINS = (
    "youtube.com", "facebook.com", "instagram.com", "tiktok.com",
    "pinterest.com", "slideshare.net",
)
SELECT_PATHS = (
    r"/best-iptv.*", r"/iptv.*", r"/reviews.*", r"/comparison.*",
    r"/providers.*", r"/services.*",
)
EXCLUDE_PATHS = (
    r"/privacy.*", r"/terms.*", r"/contact.*", r"/login.*",
    r"/author.*", r"/tag.*", r"/player.*", r"/app.*", r"/device.*",
    r"/box.*",
)


def _query(sequence: int, query: str, region: str, language: str, current: bool) -> dict[str, Any]:
    slug = re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")[:44]
    return {
        "sequence": sequence,
        "operation_id": f"search_{sequence:02d}_{slug}",
        "query": query,
        "region": region,
        "language": language,
        "time_range": "year" if current else None,
    }


SEARCH_QUERIES = (
    _query(1, "best IPTV services 2026", "GLOBAL", "en", True),
    _query(2, "best IPTV providers 2026 reviews", "GLOBAL", "en", True),
    _query(3, "top IPTV subscription services 2026", "GLOBAL", "en", True),
    _query(4, "best IPTV services comparison 2026", "GLOBAL", "en", True),
    _query(5, "best IPTV providers tested reviewed", "GLOBAL", "en", False),
    _query(6, "best IPTV services with EPG 2026", "GLOBAL", "en", True),
    _query(7, "best IPTV providers USA 2026", "NORTH_AMERICA", "en", True),
    _query(8, "best IPTV services Canada 2026", "NORTH_AMERICA", "en", True),
    _query(9, "IPTV providers USA Canada reviews", "NORTH_AMERICA", "en", False),
    _query(10, "best IPTV North America 2026", "NORTH_AMERICA", "en", True),
    _query(11, "best IPTV providers Europe 2026", "EUROPE", "en", True),
    _query(12, "best IPTV UK providers 2026", "EUROPE", "en", True),
    _query(13, "best IPTV services Spain Europe 2026", "EUROPE", "en", True),
    _query(14, "European IPTV provider comparison 2026", "EUROPE", "en", True),
    _query(15, "mejores servicios IPTV 2026", "MULTIREGION", "es", True),
    _query(16, "mejores proveedores IPTV España 2026", "EUROPE", "es", True),
    _query(17, "mejores servicios IPTV Latinoamérica", "LATIN_AMERICA", "es", False),
    _query(18, "mejores proveedores IPTV México 2026", "LATIN_AMERICA", "es", True),
    _query(19, "mejores proveedores IPTV Colombia 2026", "LATIN_AMERICA", "es", True),
    _query(20, "servicios IPTV con EPG reseñas", "MULTIREGION", "es", False),
    _query(21, "melhores serviços IPTV 2026", "MULTIREGION", "pt", True),
    _query(22, "melhores provedores IPTV Brasil 2026", "LATIN_AMERICA", "pt", True),
    _query(23, "provedores IPTV Brasil avaliações", "LATIN_AMERICA", "pt", False),
    _query(24, "melhores serviços IPTV Portugal 2026", "EUROPE", "pt", True),
)

CSV_FIELDS: dict[str, tuple[str, ...]] = {
    "ranking_sources.csv": (
        "source_row_id", "operation_id", "raw_record_id", "rank", "title", "url",
        "canonical_url", "domain", "region", "language", "tavily_score",
        "ranking_score", "source_level", "eligibility", "candidate_count",
        "year_apparent", "content_chars", "supporting_row_ids",
    ),
    "ranking_pages.csv": (
        "page_row_id", "evidence_type", "operation_id", "raw_record_id", "title",
        "url", "canonical_url", "domain", "region", "language", "tavily_score",
        "ranking_score", "source_level", "eligibility", "candidate_count",
        "year_apparent", "content_chars", "supporting_row_ids",
    ),
    "dynamic_search_filter.csv": (
        "source_row_id", "ranking_score", "source_level", "eligibility",
        "positive_signals", "negative_signals", "ranking_structure",
        "candidate_count", "selected_for_corpus", "supporting_row_ids",
    ),
    "mapped_pages.csv": (
        "map_row_id", "operation_id", "raw_record_id", "seed_url", "mapped_rank",
        "mapped_url", "canonical_url", "domain", "region", "language",
        "url_ranking_score", "eligibility", "supporting_row_ids",
    ),
    "domain_productivity.csv": (
        "domain", "seed_url", "eligible_pages", "candidate_count", "region_count",
        "language_count", "average_ranking_score", "distinct_pages",
        "duplicate_rows", "productivity_score", "selected_for_map",
        "selected_for_crawl", "supporting_row_ids",
    ),
    "raw_brand_mentions.csv": (
        "mention_row_id", "raw_name", "normalized_name", "classification",
        "evidence_type", "page_row_id", "operation_id", "raw_record_id", "url",
        "domain", "region", "language", "source_level", "position", "context",
        "supporting_row_ids",
    ),
    "canonical_iptv_names.csv": (
        "canonical_id", "canonical_name", "normalized_name", "variant_count",
        "mention_count", "domain_count", "source_quality_points", "recency_points",
        "diversity_points", "ranking_score", "historical_status", "variants",
        "supporting_row_ids",
    ),
    "excluded_non_services.csv": (
        "mention_row_id", "raw_name", "classification", "url", "domain", "context",
        "supporting_row_ids",
    ),
    "ambiguous_review_queue.csv": (
        "mention_row_id", "raw_name", "normalized_name", "url", "domain", "context",
        "reason", "supporting_row_ids",
    ),
    "brand_source_matrix.csv": (
        "canonical_id", "canonical_name", "domain", "source_level", "regions",
        "languages", "mention_count", "supporting_row_ids",
    ),
    "regional_coverage.csv": (
        "region", "language", "ranking_pages", "brand_mentions", "unique_candidates",
        "domains", "supporting_row_ids",
    ),
    "source_quality_summary.csv": (
        "source_level", "page_count", "domain_count", "candidate_mentions",
        "supporting_row_ids",
    ),
    "brand_ranking.csv": (
        "rank", "canonical_id", "canonical_name", "ranking_score", "domain_points",
        "source_quality_points", "recency_points", "diversity_points", "domain_count",
        "region_count", "language_count", "mention_count", "historical_status",
        "supporting_row_ids",
    ),
    "top_50_ranked_names.csv": (
        "rank", "canonical_id", "canonical_name", "ranking_score", "domain_count",
        "mention_count", "historical_status", "supporting_row_ids",
    ),
    "top_20_testing_queue.csv": (
        "rank", "canonical_id", "canonical_name", "ranking_score", "domain_count",
        "mention_count", "historical_status", "testing_status", "supporting_row_ids",
    ),
}
JSONL_FILES = (
    "search_results.jsonl", "mapped_results.jsonl", "crawled_pages.jsonl", "extracted_pages.jsonl",
    "operation_ledger.jsonl", "errors.jsonl",
)
JSON_FILES = (
    "harvest_plan.json", "bulk_harvest_metrics.json", "checkpoint.json",
    "manifest.json", "integrity_manifest.json",
)
MARKDOWN_FILES = ("bulk_harvest_report.md",)

EXIT_SUCCESS = 0
EXIT_CONFIGURATION = 2
EXIT_AUTHENTICATION = 3
EXIT_BUDGET = 4
EXIT_TECHNICAL = 5


class RunnerBlocked(RuntimeError):
    def __init__(self, message: str, code: int = EXIT_CONFIGURATION, reason: str = "BLOCKED") -> None:
        super().__init__(message)
        self.code = code
        self.reason = reason


class StructuralResponseError(RuntimeError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def stable_id(prefix: str, value: Any) -> str:
    return f"{prefix}_{sha256_json(value)[:24]}"


def sanitize_text(value: Any) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = re.sub(r"(?i)tvly-[a-z0-9_-]{8,}", "[REDACTED]", text)
    text = re.sub(r"(?i)(api[_ -]?key\s*[:=]\s*)\S+", r"\1[REDACTED]", text)
    return re.sub(r"\s+", " ", text).strip()[:500]


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    rows = read_jsonl(path)
    rows.append(row)
    atomic_write_text(path, "".join(json.dumps(item, ensure_ascii=False, default=str) + "\n" for item in rows))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: Sequence[str], rows: Iterable[dict[str, Any]]) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def join_ids(values: Iterable[Any]) -> str:
    return " | ".join(sorted({str(value) for value in values if value}))


def normalize_text(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return " ".join(re.findall(r"[a-z0-9]+", plain.lower()))


def canonicalize_url(value: str) -> str:
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return ""
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return ""
    host = (parts.hostname or "").lower().strip(".")
    port = parts.port
    netloc = host if port is None or (parts.scheme.lower() == "https" and port == 443) or (parts.scheme.lower() == "http" and port == 80) else f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.lower().startswith(("utm_", "ref", "aff"))))
    return urlunsplit((parts.scheme.lower(), netloc, path, query, ""))


def domain_from_url(value: str) -> str:
    canonical = canonicalize_url(value)
    return (urlsplit(canonical).hostname or "").removeprefix("www.") if canonical else ""


def apparent_year(*values: str) -> int | None:
    years = [int(year) for value in values for year in re.findall(r"\b(20(?:25|26))\b", value or "")]
    return max(years) if years else None


def clean_candidate(value: str) -> str:
    text = re.sub(r"!\[[^]]*\]\([^)]*\)", "", value)
    text = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^[#>*\-\s]+", "", text)
    text = re.sub(r"^\s*(?:#?\d{1,3}[.)]|\d{1,3}\s*[-:])\s*", "", text)
    text = re.sub(r"[*_`|]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" :-–—.()[]")
    return text[:100]


GENERIC_TERMS = {
    "features", "pricing", "pros", "cons", "conclusion", "verdict", "faq",
    "frequently asked questions", "comparison table", "best iptv services",
    "best iptv providers", "top iptv services", "our methodology", "methodology",
    "caracteristicas", "precios", "ventajas", "desventajas", "veredicto",
    "perguntas frequentes", "recursos", "conclusao", "metodologia",
    "provider", "providers", "service", "services", "iptv provider", "iptv service",
}
HARDWARE_TERMS = ("android tv box", "tv box", "set top box", "decoder", "decodificador", "hardware", "firestick device")
PLAYER_TERMS = ("iptv smarters", "smarters pro", "tivimate", "perfect player", "vlc", "kodi", "player app", "iptv player", "ora iptv player")
PLATFORM_TERMS = ("netflix", "hbo", "espn", "amazon prime", "disney+", "youtube tv", "apple tv")


def classify_candidate(name: str, context: str = "") -> str:
    norm = normalize_text(f"{name} {context}")
    name_norm = normalize_text(name)
    if any(term in norm for term in HARDWARE_TERMS):
        return "EXCLUDED_HARDWARE"
    if any(term in norm for term in PLAYER_TERMS):
        return "EXCLUDED_PLAYER_APP"
    if any(normalize_text(term) == name_norm or normalize_text(term) in name_norm for term in PLATFORM_TERMS):
        return "EXCLUDED_CHANNEL_OR_PLATFORM"
    if name_norm in GENERIC_TERMS or len(name_norm) < 3:
        return "EXCLUDED_GENERIC_TERM"
    if any(term in name_norm for term in ("privacy", "contact", "terms", "login", "checkout", "setup", "installation")):
        return "EXCLUDED_OTHER"
    tokens = name_norm.split()
    if len(tokens) > 7 or len(name) > 70 or name.endswith("?"):
        return "REVIEW"
    if "iptv" in tokens or "tv" in tokens or re.search(r"(?:IPTV|TV)$", name, re.I):
        return "IPTV_SERVICE_CANDIDATE"
    if 1 <= len(tokens) <= 4 and any(marker in normalize_text(context) for marker in ("provider", "service", "servicio", "provedor", "subscription", "ranking")):
        return "IPTV_SERVICE_CANDIDATE"
    return "REVIEW"


def candidate_phrases(content: str) -> list[tuple[str, str, int | None]]:
    found: list[tuple[str, str, int | None]] = []
    for line in (content or "").splitlines():
        stripped = line.strip()
        if not stripped or len(stripped) > 240:
            continue
        position = None
        pos_match = re.match(r"^(?:#{1,6}\s*)?(?:#?)(\d{1,3})[.)]\s+", stripped)
        if pos_match:
            position = int(pos_match.group(1))
        candidates: list[str] = []
        if re.match(r"^#{1,6}\s+", stripped) or re.match(r"^\s*\d{1,3}[.)]\s+", stripped):
            candidates.append(stripped)
        if stripped.startswith("|") and stripped.count("|") >= 2 and "---" not in stripped:
            candidates.append(stripped.split("|")[1])
        candidates.extend(re.findall(r"\*\*([^*]{2,80})\*\*", stripped))
        for raw in candidates:
            name = clean_candidate(raw)
            norm = normalize_text(name)
            if (
                not name or norm in GENERIC_TERMS
                or norm.startswith(("best iptv", "top iptv", "mejores iptv", "melhores iptv"))
                or name.lower().startswith(("how ", "why ", "what ", "como ", "porque "))
            ):
                continue
            found.append((name, stripped[:180], position))
    unique: list[tuple[str, str, int | None]] = []
    seen: set[str] = set()
    for item in found:
        key = normalize_text(item[0])
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


POSITIVE_TERMS = (
    "best", "top", "mejores", "melhores", "provider", "proveedor", "provedor",
    "service", "servicio", "servico", "comparison", "comparativa", "comparacao",
    "review", "resena", "avaliacao", "subscription", "ranking", "tested",
)
NEGATIVE_TERMS = (
    "checkout", "buy now", "login", "install", "setup", "android tv box", "hardware",
    "player app", "iptv player", "support", "privacy", "contact", "terms",
)
AUTHOR_TERMS = ("author", "written by", "methodology", "how we tested", "por:", "metodologia", "como testamos")


def score_ranking_page(
    *, title: str, url: str, snippet: str = "", raw_content: str = "",
    tavily_score: float = 0.0, region: str = "UNKNOWN", language: str = "unknown",
    threshold: int = RANKING_SCORE_THRESHOLD,
) -> dict[str, Any]:
    text = normalize_text(" ".join((title, url, snippet, raw_content[:50000])))
    page_identity = normalize_text(" ".join((title, url, snippet)))
    positives = [term for term in POSITIVE_TERMS if normalize_text(term) in text]
    negatives = [term for term in NEGATIVE_TERMS if normalize_text(term) in text]
    phrases = candidate_phrases(raw_content)
    candidate_count = sum(classify_candidate(name, context) == "IPTV_SERVICE_CANDIDATE" for name, context, _ in phrases)
    numbered = len(re.findall(r"(?m)^(?:#{1,6}\s*)?\d{1,3}[.)]\s+", raw_content or ""))
    markdown_table = bool(re.search(r"(?m)^\s*\|.*\|\s*$", raw_content or "") and re.search(r"(?m)^\s*\|?\s*:?-{3,}", raw_content or ""))
    product_headings = len(re.findall(r"(?m)^#{2,5}\s+(?:#?\d{1,3}[.)]\s*)?.{2,80}$", raw_content or ""))
    structural = numbered >= 3 or markdown_table or product_headings >= 4 or candidate_count >= 4
    year = apparent_year(title, url, snippet, raw_content[:5000])
    score = min(15, max(0, round(float(tavily_score or 0) * 15)))
    score += min(30, len(positives) * 3)
    score += 15 if structural else 0
    score += min(20, candidate_count * 2)
    score += 8 if year == 2026 else 5 if year == 2025 else 0
    score += 7 if any(normalize_text(term) in text for term in AUTHOR_TERMS) else 0
    score -= min(35, len(negatives) * 8)
    if not raw_content.strip():
        score -= 5
    score = max(0, min(100, score))
    # Exclude pages whose own identity is noise, but do not discard a genuine
    # multi-provider ranking merely because one listed entry is hardware or a
    # player application. Those entries are filtered later at candidate level.
    hard_excluded = any(
        term in page_identity
        for term in ("privacy policy", "contact us", "login", "android tv box", "iptv player app")
    )
    if hard_excluded:
        level = "E"
    elif any(normalize_text(term) in text for term in AUTHOR_TERMS) and structural:
        level = "A"
    elif structural and score >= 72:
        level = "B"
    elif structural or candidate_count >= 4:
        level = "C"
    elif any(term in text for term in ("buy now", "checkout", "pricing")):
        level = "D"
    else:
        level = "E"
    eligible = score >= threshold and structural and not hard_excluded and level in {"A", "B", "C"}
    review = not eligible and not hard_excluded and score >= max(40, threshold - 15)
    return {
        "ranking_score": score,
        "source_level": level,
        "eligibility": "ELIGIBLE" if eligible else "REVIEW" if review else "EXCLUDED",
        "positive_signals": positives,
        "negative_signals": negatives,
        "ranking_structure": structural,
        "candidate_count": candidate_count,
        "year_apparent": year or "",
        "region": region,
        "language": language,
    }


def score_mapped_url(url: str) -> int:
    path = urlsplit(url).path.lower()
    positive = sum(token in path for token in ("best-iptv", "iptv", "review", "comparison", "provider", "service"))
    negative = sum(token in path for token in ("privacy", "terms", "contact", "login", "author", "tag", "player", "app", "device", "box"))
    return max(0, min(100, 45 + positive * 12 - negative * 30))


def harvest_plan() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "task": TASK,
        "milestone": MILESTONE,
        "queries": list(SEARCH_QUERIES),
        "configs": {"search": SEARCH_CONFIG, "map": MAP_CONFIG, "crawl": CRAWL_CONFIG, "extract": EXTRACT_CONFIG},
        "exclude_domains": list(EXCLUDE_DOMAINS),
        "select_paths": list(SELECT_PATHS),
        "exclude_paths": list(EXCLUDE_PATHS),
        "request_budget": REQUEST_BUDGET,
        "content_limits": CONTENT_LIMITS,
        "ranking_score_threshold": RANKING_SCORE_THRESHOLD,
        "automatic_flow": [
            "SEARCH", "DYNAMIC_SEARCH_FILTER", "MAP", "DOMAIN_PRODUCTIVITY_FILTER",
            "CRAWL", "EXTRACT_FALLBACK", "DYNAMIC_BRAND_FILTER", "CONSOLIDATE", "COMPLETE",
        ],
        "crawl_research_contract": {"crawl_stage": True, "research_stage": False, "research_authorized": False},
        "console_contract": "COMPACT_ONLY_RAW_NEVER_PRINTED",
    }


PLAN = harvest_plan()
PLAN_HASH = sha256_json(PLAN)


def create_run_dir(output_root: Path = OUTPUT_ROOT, stamp: str | None = None) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_root / f"run_{stamp}"
    if run_dir.exists():
        raise RunnerBlocked(f"run directory already exists: {run_dir}", EXIT_CONFIGURATION, "RUN_EXISTS")
    run_dir.mkdir()
    return run_dir


def initial_checkpoint(created_at: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_hash": PLAN_HASH,
        "state": "READY",
        "active_stage": "SEARCH",
        "created_at": created_at,
        "updated_at": created_at,
        "request_counts": {"search": 0, "map": 0, "crawl": 0, "extract": 0, "global": 0},
        "operations": {},
        "error_signatures": {},
    }


def initialize_run(output_root: Path = OUTPUT_ROOT, stamp: str | None = None) -> Path:
    run_dir = create_run_dir(output_root, stamp)
    created_at = now_utc()
    atomic_write_json(run_dir / "harvest_plan.json", PLAN)
    atomic_write_json(run_dir / "checkpoint.json", initial_checkpoint(created_at))
    atomic_write_json(run_dir / "manifest.json", {
        "schema_version": SCHEMA_VERSION,
        "task": TASK,
        "milestone": MILESTONE,
        "run_id": run_dir.name,
        "state": "READY",
        "created_at": created_at,
        "plan_hash": PLAN_HASH,
        "runner_sha256": sha256_file(Path(__file__)),
        "raw_console_policy": "NEVER_PRINT_RAW",
    })
    for name, fields in CSV_FIELDS.items():
        write_csv(run_dir / name, fields, [])
    for name in JSONL_FILES:
        atomic_write_text(run_dir / name, "")
    atomic_write_json(run_dir / "bulk_harvest_metrics.json", {"schema_version": SCHEMA_VERSION, "state": "READY"})
    atomic_write_text(run_dir / "bulk_harvest_report.md", "# Bulk ranking harvest\n\nState: `READY`\n")
    refresh_integrity(run_dir)
    return run_dir


def checkpoint_write(run_dir: Path, checkpoint: dict[str, Any]) -> None:
    checkpoint["updated_at"] = now_utc()
    atomic_write_json(run_dir / "checkpoint.json", checkpoint)
    refresh_integrity(run_dir)


def ensure_operation(checkpoint: dict[str, Any], operation_id: str, stage: str, params: dict[str, Any]) -> dict[str, Any]:
    operation = checkpoint["operations"].setdefault(operation_id, {
        "operation_id": operation_id,
        "stage": stage,
        "state": "PENDING",
        "attempts": 0,
        "retries": 0,
        "params_hash": sha256_json(params),
    })
    if operation["stage"] != stage or operation["params_hash"] != sha256_json(params):
        raise RunnerBlocked(f"operation contract changed: {operation_id}", EXIT_CONFIGURATION, "OPERATION_TAMPERED")
    return operation


def reserve_operation(run_dir: Path, checkpoint: dict[str, Any], operation_id: str, stage: str, params: dict[str, Any]) -> dict[str, Any]:
    operation = ensure_operation(checkpoint, operation_id, stage, params)
    if operation["state"] == "COMPLETED":
        return operation
    if operation["state"] == "ATTEMPT_RESERVED":
        raise RunnerBlocked(f"ambiguous reserved operation: {operation_id}", EXIT_CONFIGURATION, "AMBIGUOUS_ATTEMPT")
    if operation["state"] == "FAILED":
        return operation
    if checkpoint["request_counts"][stage] >= REQUEST_BUDGET[stage] or checkpoint["request_counts"]["global"] >= REQUEST_BUDGET["global"]:
        raise RunnerBlocked(f"request budget exhausted before {operation_id}", EXIT_BUDGET, "BUDGET_EXHAUSTED")
    checkpoint["request_counts"][stage] += 1
    checkpoint["request_counts"]["global"] += 1
    operation["attempts"] += 1
    operation["state"] = "ATTEMPT_RESERVED"
    operation["reserved_at"] = now_utc()
    checkpoint["active_stage"] = stage.upper()
    checkpoint_write(run_dir, checkpoint)
    append_jsonl(run_dir / "operation_ledger.jsonl", {
        "at": now_utc(), "event": "ATTEMPT_RESERVED", "operation_id": operation_id,
        "stage": stage, "attempt": operation["attempts"],
        "stage_request_number": checkpoint["request_counts"][stage],
        "global_request_number": checkpoint["request_counts"]["global"],
    })
    refresh_integrity(run_dir)
    return operation


def complete_operation(run_dir: Path, checkpoint: dict[str, Any], operation_id: str, response_hash: str, result_count: int) -> None:
    operation = checkpoint["operations"][operation_id]
    operation.update({"state": "COMPLETED", "completed_at": now_utc(), "response_hash": response_hash, "result_count": result_count})
    checkpoint_write(run_dir, checkpoint)
    append_jsonl(run_dir / "operation_ledger.jsonl", {
        "at": now_utc(), "event": "COMPLETED", "operation_id": operation_id,
        "stage": operation["stage"], "attempt": operation["attempts"],
        "response_hash": response_hash, "result_count": result_count,
    })
    refresh_integrity(run_dir)


def error_status(exc: BaseException) -> int | None:
    for attr in ("status_code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    match = re.search(r"\b(400|401|403|429|5\d\d)\b", str(exc))
    return int(match.group(1)) if match else None


def transient_error(exc: BaseException) -> bool:
    status = error_status(exc)
    return status == 429 or (status is not None and 500 <= status <= 599) or isinstance(exc, TimeoutError) or "timeout" in str(exc).lower()


def authentication_error(exc: BaseException) -> bool:
    return error_status(exc) in {401, 403} or "authentication" in str(exc).lower() or "unauthorized" in str(exc).lower()


def record_failure(run_dir: Path, checkpoint: dict[str, Any], operation_id: str, exc: BaseException, retry: bool) -> None:
    operation = checkpoint["operations"][operation_id]
    message = sanitize_text(exc)
    signature = sha256_bytes(f"{type(exc).__name__}|{message}".encode("utf-8"))[:20]
    checkpoint["error_signatures"][signature] = checkpoint["error_signatures"].get(signature, 0) + 1
    operation["state"] = "PENDING_RETRY" if retry else "FAILED"
    operation["last_error_signature"] = signature
    if retry:
        operation["retries"] += 1
    checkpoint_write(run_dir, checkpoint)
    row = {
        "at": now_utc(), "event": "FAILED_TRANSIENT_PENDING_RETRY" if retry else "FAILED",
        "operation_id": operation_id, "stage": operation["stage"],
        "attempt": operation["attempts"], "error_type": type(exc).__name__,
        "status_code": error_status(exc), "error_signature": signature,
        "message": message,
    }
    append_jsonl(run_dir / "operation_ledger.jsonl", row)
    append_jsonl(run_dir / "errors.jsonl", row)
    refresh_integrity(run_dir)
    if isinstance(exc, StructuralResponseError) and checkpoint["error_signatures"][signature] >= 2:
        raise RunnerBlocked("repeated structural response error", EXIT_TECHNICAL, "REPEATED_STRUCTURAL_ERROR")


def response_results(response: Any, key: str = "results") -> list[Any]:
    if not isinstance(response, dict):
        raise StructuralResponseError("response must be an object")
    results = response.get(key, [])
    if not isinstance(results, list):
        raise StructuralResponseError(f"response.{key} must be a list")
    return results


def execute_api_operation(
    *, run_dir: Path, checkpoint: dict[str, Any], operation_id: str, stage: str,
    params: dict[str, Any], invoke: Callable[[], dict[str, Any]], raw_file: str,
    result_counter: Callable[[dict[str, Any]], int],
) -> dict[str, Any] | None:
    operation = ensure_operation(checkpoint, operation_id, stage, params)
    if operation["state"] == "COMPLETED":
        return None
    if operation["state"] == "FAILED":
        return None
    while True:
        reserve_operation(run_dir, checkpoint, operation_id, stage, params)
        try:
            response = invoke()
            count = result_counter(response)
            payload_hash = sha256_json(response)
            raw_record_id = stable_id(f"{stage}_raw", {"operation_id": operation_id, "payload_hash": payload_hash})
            append_jsonl(run_dir / raw_file, {
                "schema_version": SCHEMA_VERSION,
                "raw_record_id": raw_record_id,
                "operation_id": operation_id,
                "stage": stage,
                "retrieved_at": now_utc(),
                "payload_hash": payload_hash,
                "request_id": response.get("request_id") if isinstance(response, dict) else None,
                "usage": response.get("usage") if isinstance(response, dict) else None,
                "raw_payload": response,
            })
            complete_operation(run_dir, checkpoint, operation_id, payload_hash, count)
            return response
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            if authentication_error(exc):
                record_failure(run_dir, checkpoint, operation_id, exc, False)
                raise RunnerBlocked("Tavily authentication failed; batch stopped", EXIT_AUTHENTICATION, "AUTHENTICATION")
            operation = checkpoint["operations"][operation_id]
            can_retry = (
                transient_error(exc)
                and operation["retries"] < REQUEST_BUDGET["max_retry_per_operation"]
                and checkpoint["request_counts"][stage] < REQUEST_BUDGET[stage]
                and checkpoint["request_counts"]["global"] < REQUEST_BUDGET["global"]
            )
            record_failure(run_dir, checkpoint, operation_id, exc, can_retry)
            if can_retry:
                continue
            return None


def sdk_client_factory(api_key: str) -> Any:
    from tavily import TavilyClient
    return TavilyClient(api_key=api_key)


def inherited_api_key_reader(name: str = "TAVILY_API_KEY") -> str | None:
    value = os.environ.get(name)
    return value if value and value.strip() else None


def query_params(query: dict[str, Any]) -> dict[str, Any]:
    params = dict(SEARCH_CONFIG)
    params.update({"query": query["query"], "exclude_domains": list(EXCLUDE_DOMAINS)})
    if query["time_range"]:
        params["time_range"] = query["time_range"]
    return params


def run_search(client: Any, run_dir: Path, checkpoint: dict[str, Any]) -> None:
    for query in SEARCH_QUERIES:
        params = query_params(query)
        execute_api_operation(
            run_dir=run_dir, checkpoint=checkpoint, operation_id=query["operation_id"],
            stage="search", params=params, invoke=lambda p=params: client.search(**p),
            raw_file="search_results.jsonl", result_counter=lambda response: len(response_results(response)),
        )
    build_search_derivatives(run_dir)
    checkpoint["active_stage"] = "DYNAMIC_SEARCH_FILTER"
    checkpoint_write(run_dir, checkpoint)


def query_lookup() -> dict[str, dict[str, Any]]:
    return {row["operation_id"]: row for row in SEARCH_QUERIES}


def build_search_derivatives(run_dir: Path) -> None:
    sources: list[dict[str, Any]] = []
    filters: list[dict[str, Any]] = []
    queries = query_lookup()
    for envelope in read_jsonl(run_dir / "search_results.jsonl"):
        operation_id = envelope["operation_id"]
        query = queries[operation_id]
        results = response_results(envelope["raw_payload"])
        for rank, result in enumerate(results[: SEARCH_CONFIG["max_results"]], 1):
            if not isinstance(result, dict):
                continue
            url = str(result.get("url") or "")
            canonical = canonicalize_url(url)
            if not canonical:
                continue
            title = str(result.get("title") or "")
            snippet = str(result.get("content") or result.get("snippet") or "")
            raw_content = str(result.get("raw_content") or "")
            assessment = score_ranking_page(
                title=title, url=canonical, snippet=snippet, raw_content=raw_content,
                tavily_score=float(result.get("score") or 0), region=query["region"], language=query["language"],
            )
            source_id = stable_id("source", {"operation_id": operation_id, "rank": rank, "url": canonical})
            supporting = join_ids([source_id, envelope["raw_record_id"], operation_id])
            sources.append({
                "source_row_id": source_id, "operation_id": operation_id,
                "raw_record_id": envelope["raw_record_id"], "rank": rank,
                "title": title, "url": url, "canonical_url": canonical,
                "domain": domain_from_url(canonical), "region": query["region"],
                "language": query["language"], "tavily_score": result.get("score", 0),
                "ranking_score": assessment["ranking_score"], "source_level": assessment["source_level"],
                "eligibility": assessment["eligibility"], "candidate_count": assessment["candidate_count"],
                "year_apparent": assessment["year_apparent"], "content_chars": len(raw_content),
                "supporting_row_ids": supporting,
            })
            filters.append({
                "source_row_id": source_id, "ranking_score": assessment["ranking_score"],
                "source_level": assessment["source_level"], "eligibility": assessment["eligibility"],
                "positive_signals": join_ids(assessment["positive_signals"]),
                "negative_signals": join_ids(assessment["negative_signals"]),
                "ranking_structure": "YES" if assessment["ranking_structure"] else "NO",
                "candidate_count": assessment["candidate_count"],
                "selected_for_corpus": "YES" if assessment["eligibility"] == "ELIGIBLE" else "REVIEW" if assessment["eligibility"] == "REVIEW" else "NO",
                "supporting_row_ids": supporting,
            })
    if len(sources) > CONTENT_LIMITS["search_results"]:
        raise RunnerBlocked("search result content ceiling exceeded", EXIT_BUDGET, "CONTENT_CEILING")
    write_csv(run_dir / "ranking_sources.csv", CSV_FIELDS["ranking_sources.csv"], sources)
    write_csv(run_dir / "dynamic_search_filter.csv", CSV_FIELDS["dynamic_search_filter.csv"], filters)
    rebuild_ranking_pages(run_dir)
    rebuild_domain_productivity(run_dir)


def rebuild_ranking_pages(run_dir: Path) -> None:
    pages: list[dict[str, Any]] = []
    for source in read_csv(run_dir / "ranking_sources.csv"):
        pages.append({
            "page_row_id": source["source_row_id"], "evidence_type": "SEARCH",
            "operation_id": source["operation_id"], "raw_record_id": source["raw_record_id"],
            "title": source["title"], "url": source["url"], "canonical_url": source["canonical_url"],
            "domain": source["domain"], "region": source["region"], "language": source["language"],
            "tavily_score": source["tavily_score"], "ranking_score": source["ranking_score"],
            "source_level": source["source_level"], "eligibility": source["eligibility"],
            "candidate_count": source["candidate_count"], "year_apparent": source["year_apparent"],
            "content_chars": source["content_chars"], "supporting_row_ids": source["supporting_row_ids"],
        })
    domain_context = domain_region_language(run_dir)
    for mapped in read_csv(run_dir / "mapped_pages.csv"):
        region, language = domain_context.get(mapped["domain"], (mapped["region"], mapped["language"]))
        pages.append({
            "page_row_id": mapped["map_row_id"], "evidence_type": "MAP",
            "operation_id": mapped["operation_id"], "raw_record_id": mapped["raw_record_id"],
            "title": slug_title(mapped["canonical_url"]), "url": mapped["mapped_url"],
            "canonical_url": mapped["canonical_url"], "domain": mapped["domain"],
            "region": region, "language": language, "tavily_score": "",
            "ranking_score": mapped["url_ranking_score"], "source_level": "C",
            "eligibility": mapped["eligibility"], "candidate_count": 0,
            "year_apparent": apparent_year(mapped["canonical_url"]) or "", "content_chars": 0,
            "supporting_row_ids": mapped["supporting_row_ids"],
        })
    for raw_file, evidence in (("crawled_pages.jsonl", "CRAWL"), ("extracted_pages.jsonl", "EXTRACT")):
        for envelope in read_jsonl(run_dir / raw_file):
            payload = envelope["raw_payload"]
            for result in response_results(payload):
                if not isinstance(result, dict):
                    continue
                url = canonicalize_url(str(result.get("url") or ""))
                if not url:
                    continue
                domain = domain_from_url(url)
                region, language = domain_context.get(domain, ("UNKNOWN", "unknown"))
                content = str(result.get("raw_content") or result.get("content") or "")
                title = str(result.get("title") or slug_title(url))
                assessment = score_ranking_page(title=title, url=url, raw_content=content, region=region, language=language)
                page_id = stable_id("page", {"evidence": evidence, "operation_id": envelope["operation_id"], "url": url})
                pages.append({
                    "page_row_id": page_id, "evidence_type": evidence,
                    "operation_id": envelope["operation_id"], "raw_record_id": envelope["raw_record_id"],
                    "title": title, "url": url, "canonical_url": url, "domain": domain,
                    "region": region, "language": language, "tavily_score": "",
                    "ranking_score": assessment["ranking_score"], "source_level": assessment["source_level"],
                    "eligibility": assessment["eligibility"], "candidate_count": assessment["candidate_count"],
                    "year_apparent": assessment["year_apparent"], "content_chars": len(content),
                    "supporting_row_ids": join_ids([page_id, envelope["raw_record_id"], envelope["operation_id"]]),
                })
    write_csv(run_dir / "ranking_pages.csv", CSV_FIELDS["ranking_pages.csv"], pages)


def slug_title(url: str) -> str:
    slug = Path(urlsplit(url).path).name
    return re.sub(r"[-_]+", " ", slug).strip().title() or domain_from_url(url)


def domain_region_language(run_dir: Path) -> dict[str, tuple[str, str]]:
    votes: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)
    for row in read_csv(run_dir / "ranking_sources.csv"):
        votes[row["domain"]][(row["region"], row["language"])] += 1
    return {domain: counter.most_common(1)[0][0] for domain, counter in votes.items() if counter}


def rebuild_domain_productivity(run_dir: Path, map_selected: set[str] | None = None, crawl_selected: set[str] | None = None) -> None:
    map_selected = map_selected or set()
    crawl_selected = crawl_selected or set()
    pages = read_csv(run_dir / "ranking_pages.csv")
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for page in pages:
        groups[page["domain"]].append(page)
    rows = []
    for domain, items in groups.items():
        eligible = [row for row in items if row["eligibility"] == "ELIGIBLE"]
        urls = [row["canonical_url"] for row in items]
        distinct = set(urls)
        candidate_count = sum(int(row.get("candidate_count") or 0) for row in eligible)
        average = sum(float(row.get("ranking_score") or 0) for row in eligible) / len(eligible) if eligible else 0
        regions = {row["region"] for row in eligible}
        languages = {row["language"] for row in eligible}
        duplicates = len(urls) - len(distinct)
        productivity = min(100, round(len(eligible) * 10 + min(25, candidate_count) + len(regions) * 5 + len(languages) * 5 + average * 0.25 - duplicates * 3))
        seed = max(eligible or items, key=lambda row: float(row.get("ranking_score") or 0))["canonical_url"]
        rows.append({
            "domain": domain, "seed_url": seed, "eligible_pages": len(eligible),
            "candidate_count": candidate_count, "region_count": len(regions),
            "language_count": len(languages), "average_ranking_score": f"{average:.3f}",
            "distinct_pages": len(distinct), "duplicate_rows": duplicates,
            "productivity_score": productivity, "selected_for_map": "YES" if domain in map_selected else "NO",
            "selected_for_crawl": "YES" if domain in crawl_selected else "NO",
            "supporting_row_ids": join_ids(row["page_row_id"] for row in items),
        })
    rows.sort(key=lambda row: (-int(row["productivity_score"]), row["domain"]))
    write_csv(run_dir / "domain_productivity.csv", CSV_FIELDS["domain_productivity.csv"], rows)


def select_map_domains(run_dir: Path) -> list[dict[str, str]]:
    rows = read_csv(run_dir / "domain_productivity.csv")
    eligible = [row for row in rows if int(row["eligible_pages"]) >= 1 and row["domain"] != "reddit.com"]
    selected = eligible[: REQUEST_BUDGET["map"]]
    rebuild_domain_productivity(run_dir, {row["domain"] for row in selected})
    return selected


def extract_map_urls(response: dict[str, Any]) -> list[str]:
    results = response_results(response)
    urls = []
    for item in results:
        value = item if isinstance(item, str) else item.get("url") if isinstance(item, dict) else None
        canonical = canonicalize_url(str(value or ""))
        if canonical:
            urls.append(canonical)
    return urls


def run_map(client: Any, run_dir: Path, checkpoint: dict[str, Any]) -> None:
    selected = select_map_domains(run_dir)
    context = domain_region_language(run_dir)
    for index, row in enumerate(selected, 1):
        operation_id = f"map_{index:02d}_{re.sub(r'[^a-z0-9]+', '_', row['domain'])}"
        params = dict(MAP_CONFIG)
        params.update({"url": row["seed_url"], "select_paths": list(SELECT_PATHS), "exclude_paths": list(EXCLUDE_PATHS)})
        response = execute_api_operation(
            run_dir=run_dir, checkpoint=checkpoint, operation_id=operation_id, stage="map",
            params=params, invoke=lambda p=params: client.map(**p), raw_file="mapped_results.jsonl",
            result_counter=lambda value: len(extract_map_urls(value)),
        )
        envelopes = read_jsonl(run_dir / "mapped_results.jsonl")
        if response is not None and envelopes:
            envelope = envelopes[-1]
            region, language = context.get(row["domain"], ("UNKNOWN", "unknown"))
            existing = read_csv(run_dir / "mapped_pages.csv")
            for rank, url in enumerate(extract_map_urls(response)[: MAP_CONFIG["limit"]], 1):
                map_id = stable_id("maprow", {"operation_id": operation_id, "rank": rank, "url": url})
                score = score_mapped_url(url)
                existing.append({
                    "map_row_id": map_id, "operation_id": operation_id,
                    "raw_record_id": envelope["raw_record_id"], "seed_url": row["seed_url"],
                    "mapped_rank": rank, "mapped_url": url, "canonical_url": url,
                    "domain": domain_from_url(url), "region": region, "language": language,
                    "url_ranking_score": score, "eligibility": "ELIGIBLE" if score >= RANKING_SCORE_THRESHOLD else "REVIEW" if score >= 45 else "EXCLUDED",
                    "supporting_row_ids": join_ids([map_id, envelope["raw_record_id"], operation_id]),
                })
            write_csv(run_dir / "mapped_pages.csv", CSV_FIELDS["mapped_pages.csv"], existing[: CONTENT_LIMITS["mapped_urls"]])
    rebuild_ranking_pages(run_dir)
    rebuild_domain_productivity(run_dir, {row["domain"] for row in selected})
    checkpoint["active_stage"] = "DOMAIN_PRODUCTIVITY_FILTER"
    checkpoint_write(run_dir, checkpoint)


def select_crawl_domains(run_dir: Path) -> list[dict[str, str]]:
    productivity = read_csv(run_dir / "domain_productivity.csv")
    mapped = read_csv(run_dir / "mapped_pages.csv")
    eligible_count = Counter(row["domain"] for row in mapped if row["eligibility"] == "ELIGIBLE")
    candidates = [row for row in productivity if eligible_count[row["domain"]] >= 3 and int(row["productivity_score"]) >= 45]
    candidates.sort(key=lambda row: (-eligible_count[row["domain"]], -int(row["productivity_score"]), row["domain"]))
    selected = candidates[: REQUEST_BUDGET["crawl"]]
    map_selected = {row["domain"] for row in productivity if row["selected_for_map"] == "YES"}
    rebuild_domain_productivity(run_dir, map_selected, {row["domain"] for row in selected})
    return selected


def run_crawl(client: Any, run_dir: Path, checkpoint: dict[str, Any]) -> None:
    selected = select_crawl_domains(run_dir)
    for index, row in enumerate(selected, 1):
        operation_id = f"crawl_{index:02d}_{re.sub(r'[^a-z0-9]+', '_', row['domain'])}"
        params = dict(CRAWL_CONFIG)
        params.update({"url": row["seed_url"], "select_paths": list(SELECT_PATHS), "exclude_paths": list(EXCLUDE_PATHS)})
        execute_api_operation(
            run_dir=run_dir, checkpoint=checkpoint, operation_id=operation_id, stage="crawl",
            params=params, invoke=lambda p=params: client.crawl(**p), raw_file="crawled_pages.jsonl",
            result_counter=lambda value: len(response_results(value)),
        )
    crawled = sum(len(response_results(row["raw_payload"])) for row in read_jsonl(run_dir / "crawled_pages.jsonl"))
    if crawled > CONTENT_LIMITS["crawled_pages"]:
        raise RunnerBlocked("crawl page content ceiling exceeded", EXIT_BUDGET, "CONTENT_CEILING")
    rebuild_ranking_pages(run_dir)
    checkpoint["active_stage"] = "EXTRACT_FALLBACK"
    checkpoint_write(run_dir, checkpoint)


def select_extract_urls(run_dir: Path) -> list[str]:
    crawled = {
        canonicalize_url(str(result.get("url") or ""))
        for envelope in read_jsonl(run_dir / "crawled_pages.jsonl")
        for result in response_results(envelope["raw_payload"])
        if isinstance(result, dict)
    }
    candidates = []
    for row in read_csv(run_dir / "ranking_pages.csv"):
        url = row["canonical_url"]
        if row["evidence_type"] not in {"SEARCH", "MAP"} or row["eligibility"] not in {"ELIGIBLE", "REVIEW"} or url in crawled:
            continue
        insufficient_search = row["evidence_type"] == "MAP" or int(row.get("content_chars") or 0) < 2000
        if insufficient_search:
            candidates.append((int(row.get("ranking_score") or 0), url))
    unique: list[str] = []
    seen: set[str] = set()
    for _, url in sorted(candidates, key=lambda item: (-item[0], item[1])):
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique[: CONTENT_LIMITS["extract_fallback_urls"]]


def run_extract(client: Any, run_dir: Path, checkpoint: dict[str, Any]) -> None:
    urls = select_extract_urls(run_dir)
    batches = [urls[index:index + CONTENT_LIMITS["extract_batch_size"]] for index in range(0, len(urls), CONTENT_LIMITS["extract_batch_size"])]
    for index, batch in enumerate(batches[: REQUEST_BUDGET["extract"]], 1):
        operation_id = f"extract_batch_{index:02d}"
        params = dict(EXTRACT_CONFIG)
        params["urls"] = batch
        execute_api_operation(
            run_dir=run_dir, checkpoint=checkpoint, operation_id=operation_id, stage="extract",
            params=params, invoke=lambda p=params: client.extract(**p), raw_file="extracted_pages.jsonl",
            result_counter=lambda value: len(response_results(value)),
        )
    rebuild_ranking_pages(run_dir)
    checkpoint["active_stage"] = "DYNAMIC_BRAND_FILTER"
    checkpoint_write(run_dir, checkpoint)


def raw_content_index(run_dir: Path) -> dict[tuple[str, str], str]:
    index: dict[tuple[str, str], str] = {}
    for envelope in read_jsonl(run_dir / "search_results.jsonl"):
        for result in response_results(envelope["raw_payload"]):
            if isinstance(result, dict):
                url = canonicalize_url(str(result.get("url") or ""))
                index[("SEARCH", url)] = str(result.get("raw_content") or "")
    for raw_file, evidence in (("crawled_pages.jsonl", "CRAWL"), ("extracted_pages.jsonl", "EXTRACT")):
        for envelope in read_jsonl(run_dir / raw_file):
            for result in response_results(envelope["raw_payload"]):
                if isinstance(result, dict):
                    url = canonicalize_url(str(result.get("url") or ""))
                    index[(evidence, url)] = str(result.get("raw_content") or result.get("content") or "")
    return index


def canonical_brand_key(name: str) -> str:
    tokens = normalize_text(name).split()
    if len(tokens) > 1 and tokens[-1] in {"iptv", "tv"} and len("".join(tokens[:-1])) >= 4:
        tokens = tokens[:-1]
    return " ".join(tokens)


def build_brand_outputs(run_dir: Path) -> None:
    pages = [row for row in read_csv(run_dir / "ranking_pages.csv") if row["evidence_type"] in {"SEARCH", "CRAWL", "EXTRACT"} and row["eligibility"] in {"ELIGIBLE", "REVIEW"}]
    content_index = raw_content_index(run_dir)
    mentions: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    for page in pages:
        content = content_index.get((page["evidence_type"], page["canonical_url"]), "")
        for order, (raw_name, context, position) in enumerate(candidate_phrases(content), 1):
            classification = classify_candidate(raw_name, context)
            mention_id = stable_id("mention", {"page": page["page_row_id"], "order": order, "raw_name": raw_name})
            supporting = join_ids([mention_id, page["page_row_id"], page["raw_record_id"], page["operation_id"]])
            row = {
                "mention_row_id": mention_id, "raw_name": raw_name,
                "normalized_name": canonical_brand_key(raw_name), "classification": classification,
                "evidence_type": page["evidence_type"], "page_row_id": page["page_row_id"],
                "operation_id": page["operation_id"], "raw_record_id": page["raw_record_id"],
                "url": page["canonical_url"], "domain": page["domain"],
                "region": page["region"], "language": page["language"],
                "source_level": page["source_level"], "position": position or "",
                "context": context[:180], "supporting_row_ids": supporting,
            }
            mentions.append(row)
            if classification.startswith("EXCLUDED_"):
                excluded.append({
                    "mention_row_id": mention_id, "raw_name": raw_name,
                    "classification": classification, "url": page["canonical_url"],
                    "domain": page["domain"], "context": context[:180],
                    "supporting_row_ids": supporting,
                })
            elif classification == "REVIEW":
                ambiguous.append({
                    "mention_row_id": mention_id, "raw_name": raw_name,
                    "normalized_name": canonical_brand_key(raw_name), "url": page["canonical_url"],
                    "domain": page["domain"], "context": context[:180],
                    "reason": "Insufficient context for automatic service classification",
                    "supporting_row_ids": supporting,
                })
    write_csv(run_dir / "raw_brand_mentions.csv", CSV_FIELDS["raw_brand_mentions.csv"], mentions)
    write_csv(run_dir / "excluded_non_services.csv", CSV_FIELDS["excluded_non_services.csv"], excluded)
    write_csv(run_dir / "ambiguous_review_queue.csv", CSV_FIELDS["ambiguous_review_queue.csv"], ambiguous)
    build_canonical_and_ranking(run_dir, mentions)


def historical_name_set() -> set[str]:
    if not FIX4_NAMES.exists():
        return set()
    return {canonical_brand_key(row.get("raw_name", "")) for row in read_csv(FIX4_NAMES) if row.get("raw_name")}


def build_canonical_and_ranking(run_dir: Path, mentions: list[dict[str, Any]]) -> None:
    service_mentions = [row for row in mentions if row["classification"] == "IPTV_SERVICE_CANDIDATE"]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in service_mentions:
        key = row["normalized_name"]
        if key:
            groups[key].append(row)
    history = historical_name_set()
    canonical_rows = []
    matrix = []
    rankings = []
    for key, rows in groups.items():
        variants = Counter(row["raw_name"] for row in rows)
        canonical_name = sorted(variants, key=lambda value: (-variants[value], len(value), value.lower()))[0]
        canonical_id = stable_id("brand", key)
        domains = {row["domain"] for row in rows}
        regions = {row["region"] for row in rows}
        languages = {row["language"] for row in rows}
        domain_points = min(50, len(domains) * 10)
        best_by_domain: dict[str, int] = {}
        quality_weight = {"A": 5, "B": 4, "C": 3, "D": 1, "E": 0}
        for row in rows:
            best_by_domain[row["domain"]] = max(best_by_domain.get(row["domain"], 0), quality_weight.get(row["source_level"], 0))
        quality_points = min(25, sum(best_by_domain.values()))
        years = [apparent_year(row["url"], row["context"]) for row in rows]
        recency_points = 15 if 2026 in years else 10 if 2025 in years else 5
        diversity_points = min(10, round(len(regions) * 2.5 + len(languages) * 2.5))
        total = min(100, domain_points + quality_points + recency_points + diversity_points)
        supporting = join_ids(row["mention_row_id"] for row in rows)
        historical_status = "HISTORICAL_MATCH" if key in history else "NEW_OR_VARIANT_CANDIDATE"
        canonical_rows.append({
            "canonical_id": canonical_id, "canonical_name": canonical_name,
            "normalized_name": key, "variant_count": len(variants), "mention_count": len(rows),
            "domain_count": len(domains), "source_quality_points": quality_points,
            "recency_points": recency_points, "diversity_points": diversity_points,
            "ranking_score": total, "historical_status": historical_status,
            "variants": join_ids(variants), "supporting_row_ids": supporting,
        })
        rankings.append({
            "canonical_id": canonical_id, "canonical_name": canonical_name,
            "ranking_score": total, "domain_points": domain_points,
            "source_quality_points": quality_points, "recency_points": recency_points,
            "diversity_points": diversity_points, "domain_count": len(domains),
            "region_count": len(regions), "language_count": len(languages),
            "mention_count": len(rows), "historical_status": historical_status,
            "supporting_row_ids": supporting,
        })
        for domain in sorted(domains):
            subset = [row for row in rows if row["domain"] == domain]
            matrix.append({
                "canonical_id": canonical_id, "canonical_name": canonical_name,
                "domain": domain,
                "source_level": min((row["source_level"] for row in subset), default="E"),
                "regions": join_ids(row["region"] for row in subset),
                "languages": join_ids(row["language"] for row in subset),
                "mention_count": len(subset),
                "supporting_row_ids": join_ids(row["mention_row_id"] for row in subset),
            })
    rankings.sort(key=lambda row: (-row["ranking_score"], -row["domain_count"], -row["mention_count"], row["canonical_name"].lower()))
    for index, row in enumerate(rankings, 1):
        row["rank"] = index
    canonical_rows.sort(key=lambda row: next(item["rank"] for item in rankings if item["canonical_id"] == row["canonical_id"]))
    write_csv(run_dir / "canonical_iptv_names.csv", CSV_FIELDS["canonical_iptv_names.csv"], canonical_rows)
    write_csv(run_dir / "brand_source_matrix.csv", CSV_FIELDS["brand_source_matrix.csv"], matrix)
    write_csv(run_dir / "brand_ranking.csv", CSV_FIELDS["brand_ranking.csv"], rankings)
    top50 = [{**row} for row in rankings[:50]]
    top20 = [{**row, "testing_status": "PENDING_REAL_TEST"} for row in rankings[:20]]
    write_csv(run_dir / "top_50_ranked_names.csv", CSV_FIELDS["top_50_ranked_names.csv"], top50)
    write_csv(run_dir / "top_20_testing_queue.csv", CSV_FIELDS["top_20_testing_queue.csv"], top20)
    build_coverage_outputs(run_dir, service_mentions)


def build_coverage_outputs(run_dir: Path, mentions: list[dict[str, Any]]) -> None:
    pages = read_csv(run_dir / "ranking_pages.csv")
    coverage_rows = []
    combos = sorted({(row["region"], row["language"]) for row in pages})
    for region, language in combos:
        selected_pages = [row for row in pages if row["region"] == region and row["language"] == language and row["eligibility"] == "ELIGIBLE"]
        selected_mentions = [row for row in mentions if row["region"] == region and row["language"] == language]
        coverage_rows.append({
            "region": region, "language": language, "ranking_pages": len({row["canonical_url"] for row in selected_pages}),
            "brand_mentions": len(selected_mentions), "unique_candidates": len({row["normalized_name"] for row in selected_mentions}),
            "domains": len({row["domain"] for row in selected_pages}),
            "supporting_row_ids": join_ids([*[row["page_row_id"] for row in selected_pages], *[row["mention_row_id"] for row in selected_mentions]]),
        })
    write_csv(run_dir / "regional_coverage.csv", CSV_FIELDS["regional_coverage.csv"], coverage_rows)
    quality_rows = []
    for level in "ABCDE":
        level_pages = [row for row in pages if row["source_level"] == level]
        level_mentions = [row for row in mentions if row["source_level"] == level]
        quality_rows.append({
            "source_level": level, "page_count": len(level_pages),
            "domain_count": len({row["domain"] for row in level_pages}),
            "candidate_mentions": len(level_mentions),
            "supporting_row_ids": join_ids([*[row["page_row_id"] for row in level_pages], *[row["mention_row_id"] for row in level_mentions]]),
        })
    write_csv(run_dir / "source_quality_summary.csv", CSV_FIELDS["source_quality_summary.csv"], quality_rows)


def finalize_run(run_dir: Path, checkpoint: dict[str, Any]) -> None:
    build_brand_outputs(run_dir)
    pages = read_csv(run_dir / "ranking_pages.csv")
    mentions = read_csv(run_dir / "raw_brand_mentions.csv")
    candidates = read_csv(run_dir / "canonical_iptv_names.csv")
    top50 = read_csv(run_dir / "top_50_ranked_names.csv")
    top20 = read_csv(run_dir / "top_20_testing_queue.csv")
    useful_pages = len({row["canonical_url"] for row in pages if row["eligibility"] == "ELIGIBLE"})
    service_mentions = sum(row["classification"] == "IPTV_SERVICE_CANDIDATE" for row in mentions)
    if useful_pages >= 30 and service_mentions >= 300 and len(candidates) >= 60 and len(top50) == 50 and len(top20) == 20:
        verdict = "BULK_HARVEST_SIRVIO"
    elif useful_pages >= 15 and service_mentions >= 150 and len(candidates) >= 30:
        verdict = "BULK_HARVEST_SIRVIO_PARCIALMENTE"
    else:
        verdict = "BULK_HARVEST_NO_SIRVIO"
    checkpoint["state"] = "COMPLETE"
    checkpoint["active_stage"] = "COMPLETE"
    checkpoint_write(run_dir, checkpoint)
    manifest = read_json(run_dir / "manifest.json")
    manifest.update({"state": "COMPLETE", "completed_at": now_utc(), "verdict": verdict})
    atomic_write_json(run_dir / "manifest.json", manifest)
    metrics = {
        "schema_version": SCHEMA_VERSION, "state": "COMPLETE", "verdict": verdict,
        "request_counts": checkpoint["request_counts"],
        "search_result_rows": len(read_csv(run_dir / "ranking_sources.csv")),
        "mapped_url_rows": len(read_csv(run_dir / "mapped_pages.csv")),
        "crawled_page_rows": sum(len(response_results(row["raw_payload"])) for row in read_jsonl(run_dir / "crawled_pages.jsonl")),
        "extracted_page_rows": sum(len(response_results(row["raw_payload"])) for row in read_jsonl(run_dir / "extracted_pages.jsonl")),
        "useful_ranking_pages": useful_pages, "raw_brand_mentions": len(mentions),
        "service_candidate_mentions": service_mentions, "unique_candidates": len(candidates),
        "top_50_rows": len(top50), "top_20_rows": len(top20),
        "error_rows": len(read_jsonl(run_dir / "errors.jsonl")),
        "raw_printed_to_console": False, "research_operations": 0,
    }
    atomic_write_json(run_dir / "bulk_harvest_metrics.json", metrics)
    report = f"""# Bulk ranking harvest report

- State: `COMPLETE`
- Verdict: `{verdict}`
- Tavily requests: `{checkpoint['request_counts']['global']}` / `{REQUEST_BUDGET['global']}`
- Useful ranking pages: `{useful_pages}`
- Raw mentions: `{len(mentions)}`
- Service candidate mentions: `{service_mentions}`
- Unique canonical candidates: `{len(candidates)}`
- Top 50 rows: `{len(top50)}`
- Top 20 testing queue rows: `{len(top20)}`
- Errors: `{len(read_jsonl(run_dir / 'errors.jsonl'))}`

Raw Search, Crawl and Extract evidence remains on disk and is not reproduced in
this compact report. The ranking measures recurrence, source class, recency and
regional/language diversity; it does not measure stability, price, EPG, support,
legitimacy, trial availability or official-domain identity.
"""
    atomic_write_text(run_dir / "bulk_harvest_report.md", report)
    refresh_integrity(run_dir)


def refresh_integrity(run_dir: Path) -> None:
    artifacts = {}
    for path in sorted(run_dir.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name != "integrity_manifest.json":
            artifacts[path.name] = {"size": path.stat().st_size, "sha256": sha256_file(path)}
    atomic_write_json(run_dir / "integrity_manifest.json", {
        "schema_version": SCHEMA_VERSION, "generated_at": now_utc(),
        "plan_hash": PLAN_HASH, "artifacts": artifacts, "self_hash_omitted": True,
    })


def validate_integrity(run_dir: Path) -> None:
    if read_json(run_dir / "harvest_plan.json") != PLAN:
        raise RunnerBlocked("harvest plan mismatch", EXIT_CONFIGURATION, "PLAN_MISMATCH")
    checkpoint = read_json(run_dir / "checkpoint.json")
    manifest = read_json(run_dir / "manifest.json")
    if checkpoint.get("plan_hash") != PLAN_HASH or manifest.get("plan_hash") != PLAN_HASH:
        raise RunnerBlocked("plan hash mismatch", EXIT_CONFIGURATION, "PLAN_HASH_MISMATCH")
    integrity = read_json(run_dir / "integrity_manifest.json")
    for name, metadata in integrity.get("artifacts", {}).items():
        path = run_dir / name
        if not path.exists() or path.stat().st_size != metadata["size"] or sha256_file(path) != metadata["sha256"]:
            raise RunnerBlocked(f"integrity mismatch: {name}", EXIT_CONFIGURATION, "INTEGRITY_MISMATCH")


def validate_resume(run_dir: Path, output_root: Path = OUTPUT_ROOT) -> Path:
    resolved = run_dir.resolve()
    root = output_root.resolve()
    if root not in resolved.parents:
        raise RunnerBlocked("resume run is outside the output root", EXIT_CONFIGURATION, "FOREIGN_RUN")
    validate_integrity(resolved)
    checkpoint = read_json(resolved / "checkpoint.json")
    if checkpoint["state"] == "COMPLETE":
        raise RunnerBlocked("compatible run is already COMPLETE", EXIT_CONFIGURATION, "RUN_COMPLETE")
    ambiguous = [operation_id for operation_id, row in checkpoint["operations"].items() if row["state"] == "ATTEMPT_RESERVED"]
    if ambiguous:
        raise RunnerBlocked(f"ambiguous reserved operations block resume: {join_ids(ambiguous)}", EXIT_CONFIGURATION, "AMBIGUOUS_ATTEMPT")
    return resolved


def compatible_run(output_root: Path = OUTPUT_ROOT) -> Path | None:
    if not output_root.exists():
        return None
    for run_dir in sorted((path for path in output_root.iterdir() if path.is_dir() and path.name.startswith("run_")), reverse=True):
        try:
            manifest = read_json(run_dir / "manifest.json")
        except (OSError, ValueError):
            continue
        if manifest.get("task") == TASK and manifest.get("plan_hash") == PLAN_HASH:
            return run_dir
    return None


def execute_pipeline(client: Any, run_dir: Path) -> Path:
    checkpoint = read_json(run_dir / "checkpoint.json")
    if checkpoint["state"] == "COMPLETE":
        raise RunnerBlocked("run already complete", EXIT_CONFIGURATION, "RUN_COMPLETE")
    run_search(client, run_dir, checkpoint)
    run_map(client, run_dir, checkpoint)
    run_crawl(client, run_dir, checkpoint)
    run_extract(client, run_dir, checkpoint)
    finalize_run(run_dir, checkpoint)
    return run_dir


def execute_new(client: Any, output_root: Path = OUTPUT_ROOT, stamp: str | None = None) -> Path:
    existing = compatible_run(output_root)
    if existing:
        raise RunnerBlocked(f"compatible run already exists; use --resume-run only if incomplete: {existing}", EXIT_CONFIGURATION, "COMPATIBLE_RUN_EXISTS")
    run_dir = initialize_run(output_root, stamp)
    return execute_pipeline(client, run_dir)


def resume_existing(client: Any, run_dir: Path, output_root: Path = OUTPUT_ROOT) -> Path:
    validated = validate_resume(run_dir, output_root)
    return execute_pipeline(client, validated)


def compact_summary(run_dir: Path) -> list[str]:
    manifest = read_json(run_dir / "manifest.json")
    checkpoint = read_json(run_dir / "checkpoint.json")
    metrics = read_json(run_dir / "bulk_harvest_metrics.json")
    lines = [
        f"STATE={manifest.get('state')}",
        f"REQUESTS_SEARCH={checkpoint['request_counts']['search']}",
        f"REQUESTS_MAP={checkpoint['request_counts']['map']}",
        f"REQUESTS_CRAWL={checkpoint['request_counts']['crawl']}",
        f"REQUESTS_EXTRACT={checkpoint['request_counts']['extract']}",
        f"REQUESTS_GLOBAL={checkpoint['request_counts']['global']}",
        f"SOURCES={metrics.get('search_result_rows', 0)}",
        f"PAGES={metrics.get('useful_ranking_pages', 0)}",
        f"CANDIDATES={metrics.get('unique_candidates', 0)}",
        f"ERRORS={metrics.get('error_rows', len(read_jsonl(run_dir / 'errors.jsonl')))}",
    ]
    top20 = read_csv(run_dir / "top_20_testing_queue.csv")
    if top20:
        lines.append("TOP20=" + " | ".join(row["canonical_name"] for row in top20))
    lines.extend([f"VERDICT={manifest.get('verdict', 'PENDING')}", f"RUN_DIR={run_dir}"])
    return lines


def dry_run_summary() -> dict[str, Any]:
    return {
        "task": TASK, "plan_hash": PLAN_HASH, "search_queries": len(SEARCH_QUERIES),
        "request_budget": REQUEST_BUDGET, "content_limits": CONTENT_LIMITS,
        "output_count": len(CSV_FIELDS) + len(JSONL_FILES) + len(JSON_FILES) + len(MARKDOWN_FILES),
        "ranking_score_threshold": RANKING_SCORE_THRESHOLD,
        "raw_console_policy": "COMPACT_ONLY_RAW_NEVER_PRINTED",
        "real_execution_pending": True,
    }


def powershell_block() -> str:
    return r"""& {
    $projectRoot = 'C:\Proyectos\IPTV-Playlist-Builder-Premium'
    Set-Location -LiteralPath $projectRoot

    if (-not (Test-Path -LiteralPath Env:\TAVILY_API_KEY) -or
        [string]::IsNullOrWhiteSpace($env:TAVILY_API_KEY)) {
        Write-Error 'TAVILY_API_KEY is unavailable in this PowerShell process. No Tavily operation was made.'
        $runnerExitCode = 3
        $runnerOutput = @()
    }
    else {
        $env:PYTHONUTF8 = '1'
        $env:PYTHONIOENCODING = 'utf-8'
        $runnerOutput = & python -B .\scripts\run_bulk_ranking_harvest.py --execute --approval-token 'BULK-RANKING-HARVEST-01' --execution-origin powershell 2>&1
        $runnerExitCode = $LASTEXITCODE
    }

    $runLine = $runnerOutput | Where-Object { $_ -like 'RUN_DIR=*' } | Select-Object -Last 1
    $runnerOutput | Where-Object { $_ -notlike 'RUN_DIR=*' } | ForEach-Object { Write-Output $_ }
    if ($runLine) { Write-Output $runLine }
    else { Write-Output 'RUN_DIR=NOT_CREATED_OR_NOT_REPORTED' }
    Write-Output "RUNNER_EXIT_CODE=$runnerExitCode"
    Write-Output 'DO_NOT_RUN_AGAIN_IF_RUN_DIR_WAS_PRINTED'
    if ($runnerExitCode -eq 0) { Write-Output 'FINAL_STATE=COMPLETE_PENDING_HUMAN_REVIEW' }
    else { Write-Output 'FINAL_STATE=FAILED_OR_BLOCKED_DO_NOT_RETRY_AUTOMATICALLY' }
}"""


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    mode = result.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--summarize-run", type=Path)
    result.add_argument("--approval-token")
    result.add_argument("--execution-origin")
    result.add_argument("--resume-run", type=Path)
    return result


def validate_execute_args(args: argparse.Namespace) -> None:
    if args.approval_token != APPROVAL_TOKEN:
        raise RunnerBlocked("exact approval token is required", EXIT_CONFIGURATION, "APPROVAL_TOKEN")
    if args.execution_origin != "powershell":
        raise RunnerBlocked("execution origin must be powershell", EXIT_CONFIGURATION, "EXECUTION_ORIGIN")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.dry_run:
            print(json.dumps(dry_run_summary(), ensure_ascii=False, sort_keys=True))
            return EXIT_SUCCESS
        if args.preflight:
            print(f"PREFLIGHT=PASS PLAN_HASH={PLAN_HASH} QUERIES={len(SEARCH_QUERIES)} MAX_REQUESTS={REQUEST_BUDGET['global']}")
            return EXIT_SUCCESS
        if args.summarize_run:
            validate_integrity(args.summarize_run.resolve())
            for line in compact_summary(args.summarize_run.resolve()):
                print(line)
            return EXIT_SUCCESS
        validate_execute_args(args)
        if args.resume_run:
            run_dir = validate_resume(args.resume_run, OUTPUT_ROOT)
        else:
            existing = compatible_run(OUTPUT_ROOT)
            if existing:
                raise RunnerBlocked(f"compatible run already exists: {existing}", EXIT_CONFIGURATION, "COMPATIBLE_RUN_EXISTS")
            run_dir = None
        api_key = inherited_api_key_reader()
        if not api_key:
            raise RunnerBlocked("TAVILY_API_KEY is unavailable; no run was created and no request was made", EXIT_AUTHENTICATION, "AUTHENTICATION")
        client = sdk_client_factory(api_key)
        completed = resume_existing(client, run_dir, OUTPUT_ROOT) if run_dir else execute_new(client, OUTPUT_ROOT)
        for line in compact_summary(completed):
            print(line)
        return EXIT_SUCCESS
    except RunnerBlocked as exc:
        print(f"{exc.reason}: {sanitize_text(exc)}", file=sys.stderr)
        return exc.code
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as exc:
        print(f"UNEXPECTED_TECHNICAL_ERROR: {sanitize_text(exc)}", file=sys.stderr)
        return EXIT_TECHNICAL


if __name__ == "__main__":
    raise SystemExit(main())
