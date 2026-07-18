#!/usr/bin/env python3
"""Staged Tavily Search/Map/Extract multiregion pilot for BRAND-FIRST 1B.

Codex may use --dry-run only. Real operations require the exact approval token,
PowerShell origin, an inherited TAVILY_API_KEY, and explicit offline selection
files between Search, Map, and Extract. Crawl and Research are not implemented
as executable stages and remain blocked by contract.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TASK = "SEARCH-MAP-EXTRACT-MULTIREGION-PILOT-01"
SCHEMA_VERSION = "brand_first_market_universe_1b_multiregion_pilot.v1"
APPROVAL_TOKEN = "BRAND-FIRST-1B-MULTIREGION-PILOT-01"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / (
    "research/output/best_iptv_2026/brand_first_market_universe_1b/"
    "search_map_extract_multiregion_pilot_01"
)
BUDGET = {
    "search": 10,
    "map": 5,
    "extract": 10,
    "global": 25,
    "absolute_global_ceiling": 30,
    "automatic_retries": 0,
}
SEARCH_CONFIG: dict[str, Any] = {
    "search_depth": "basic",
    "max_results": 5,
    "auto_parameters": False,
    "include_answer": False,
    "include_images": False,
    "include_raw_content": False,
}
MAP_CONFIG: dict[str, Any] = {
    "max_depth": 2,
    "max_breadth": 20,
    "limit": 50,
    "instructions": "Find concrete IPTV market comparisons, rankings, directories, review, and community pages.",
    "allow_external": False,
    "include_images": False,
}
EXTRACT_CONFIG: dict[str, Any] = {
    "include_images": False,
    "extract_depth": "basic",
    "format": "markdown",
}
SEARCH_QUERIES: tuple[dict[str, Any], ...] = (
    {"sequence": 1, "operation_id": "search_na_en_comparison", "region": "NORTH_AMERICA", "language": "en", "query": "best IPTV services 2026 comparison USA Canada"},
    {"sequence": 2, "operation_id": "search_na_en_reviews", "region": "NORTH_AMERICA", "language": "en", "query": "IPTV providers reviews 2026 USA Canada"},
    {"sequence": 3, "operation_id": "search_na_en_community", "region": "NORTH_AMERICA", "language": "en", "query": "IPTV services community recommendations forum USA Canada"},
    {"sequence": 4, "operation_id": "search_eu_en_comparison", "region": "EUROPE", "language": "en", "query": "IPTV providers Europe 2026 comparison reviews"},
    {"sequence": 5, "operation_id": "search_eu_en_market", "region": "EUROPE", "language": "en", "query": "best IPTV services UK Germany France 2026"},
    {"sequence": 6, "operation_id": "search_eu_es_comparison", "region": "EUROPE", "language": "es", "query": "mejores servicios IPTV Europa 2026 comparativa"},
    {"sequence": 7, "operation_id": "search_latam_es_comparison", "region": "LATIN_AMERICA", "language": "es", "query": "mejores servicios IPTV 2026 Latinoamérica comparativa"},
    {"sequence": 8, "operation_id": "search_latam_es_reviews", "region": "LATIN_AMERICA", "language": "es", "query": "proveedores IPTV reseñas México Argentina Colombia"},
    {"sequence": 9, "operation_id": "search_latam_es_community", "region": "LATIN_AMERICA", "language": "es", "query": "servicios IPTV Latinoamérica recomendaciones comunidad"},
    {"sequence": 10, "operation_id": "search_multiregion_en_directory", "region": "MULTIREGION", "language": "en", "query": "IPTV provider directory market comparison 2026"},
)
SOURCE_TAXONOMY = {
    "A": "Specialized publication with visible authorship and methodology",
    "B": "Technical community, medium, or forum with contextual discussion",
    "C": "Comparator, ranking, or affiliate-oriented publication",
    "D": "Reseller, provider, or promotional content",
    "E": "Copied content, spam, or noise",
}
INDEPENDENCE_SIGNALS = (
    "duplicate_text", "same_brand_order", "same_template", "same_company",
    "same_author", "same_contact", "same_domain_network", "same_affiliate_code",
    "republication",
)
BLOCKED_CAPABILITIES = {
    "crawl": {"designed": True, "authorized": False, "executable_stage": False},
    "research": {"designed": True, "authorized": False, "executable_stage": False},
}
MAX_REPEATED_ERROR_SIGNATURES = 2
EXIT_SUCCESS = 0
EXIT_CONFIGURATION = 2
EXIT_AUTHENTICATION = 3
EXIT_BUDGET = 4
EXIT_TECHNICAL = 5
REQUIRED_ARTIFACTS = (
    "source_search_plan.json", "source_registry.csv", "search_results.jsonl",
    "source_selection.json", "mapped_pages.csv", "extract_selection.json",
    "extracted_pages.jsonl", "raw_brand_mentions.csv", "canonical_brand_candidates.csv",
    "source_independence_groups.csv", "regional_language_coverage.csv",
    "new_vs_historical_brands.csv", "operation_ledger.jsonl", "errors.jsonl",
    "pilot_metrics.json", "pilot_report.md", "manifest.json", "checkpoint.json",
    "integrity_manifest.json",
)
SOURCE_FIELDS = (
    "source_row_id", "search_operation_id", "region", "language", "rank", "title",
    "url", "canonical_url", "domain", "score", "snippet", "provisional_source_level",
    "selected_for_map", "raw_record_id",
)
MAPPED_FIELDS = (
    "map_row_id", "map_operation_id", "selection_id", "source_url", "mapped_rank",
    "mapped_url", "canonical_url", "domain", "raw_record_id",
)
BRAND_MENTION_FIELDS = (
    "mention_row_id", "extract_operation_id", "source_url", "raw_brand_text",
    "context", "supporting_row_ids",
)
BRAND_CANDIDATE_FIELDS = (
    "candidate_id", "canonical_brand_name", "mention_count", "source_count",
    "region_count", "language_count", "supporting_row_ids", "review_status",
)
INDEPENDENCE_FIELDS = (
    "independence_group_id", "source_row_ids", "source_count", "signals",
    "assessment_status", "rationale",
)
COVERAGE_FIELDS = (
    "region", "language", "planned_search_operations", "completed_search_operations",
    "search_result_rows", "unique_domains",
)
NOVELTY_FIELDS = (
    "candidate_id", "canonical_brand_name", "historical_match_status",
    "supporting_row_ids", "review_status",
)
SECRET_PATTERNS = (
    re.compile(r"tvly-[A-Za-z0-9_-]{12,}", re.I),
    re.compile(r"authorization\s*:\s*bearer\s+\S+", re.I),
    re.compile(r"(api[ _-]?key|token)\s*[:=]\s*[^\s,;]+", re.I),
)


class RunnerBlocked(RuntimeError):
    def __init__(
        self, message: str, run_state: str = "BLOCKED_CONFIGURATION",
        exit_code: int = EXIT_CONFIGURATION,
    ) -> None:
        super().__init__(message)
        self.run_state = run_state
        self.exit_code = exit_code


class StructuralResponseError(RuntimeError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def sanitize_text(value: str) -> str:
    result = value
    for pattern in SECRET_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


def sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_value(item) for item in value]
    if isinstance(value, dict):
        return {sanitize_text(str(key)): sanitize_value(item) for key, item in value.items()}
    return value


def secret_count(value: str) -> int:
    return sum(len(pattern.findall(value)) for pattern in SECRET_PATTERNS)


def atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(value, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise RunnerBlocked(f"non-object JSONL row in {path.name}", "BLOCKED_INTEGRITY")
            rows.append(value)
    return rows


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    rows = read_jsonl(path) if path.exists() else []
    rows.append(sanitize_value(value))
    atomic_write_text(path, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: Iterable[str], rows: Iterable[dict[str, Any]]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def canonicalize_url(value: str) -> str:
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return value.strip()
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return value.strip()
    host = parsed.hostname.lower().rstrip(".")
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    return urlunsplit((parsed.scheme.lower(), host + port, path, query, ""))


def domain_from_url(value: str) -> str:
    try:
        host = (urlsplit(value).hostname or "").lower()
    except ValueError:
        return ""
    labels = [item for item in host.split(".") if item]
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def source_search_plan() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "task": TASK,
        "objective": "Discover multiregion market sources, not individual official domains",
        "queries": [dict(item) for item in SEARCH_QUERIES],
        "budgets": dict(BUDGET),
        "search_configuration": dict(SEARCH_CONFIG),
        "map_configuration": dict(MAP_CONFIG),
        "extract_configuration": dict(EXTRACT_CONFIG),
        "source_taxonomy": dict(SOURCE_TAXONOMY),
        "independence_signals": list(INDEPENDENCE_SIGNALS),
        "blocked_capabilities": BLOCKED_CAPABILITIES,
        "stage_contract": [
            "SEARCH", "OFFLINE_SOURCE_SELECTION", "MAP",
            "OFFLINE_EXTRACT_SELECTION", "EXTRACT", "OFFLINE_CONSOLIDATION",
        ],
    }


def validate_plan(plan: dict[str, Any]) -> None:
    if plan != source_search_plan():
        raise RunnerBlocked("pilot plan differs from the frozen contract")
    if BUDGET["global"] != BUDGET["search"] + BUDGET["map"] + BUDGET["extract"]:
        raise RunnerBlocked("stage budgets do not equal global budget")
    if BUDGET["global"] > BUDGET["absolute_global_ceiling"]:
        raise RunnerBlocked("global budget exceeds absolute ceiling")
    if len({item["operation_id"] for item in SEARCH_QUERIES}) != BUDGET["search"]:
        raise RunnerBlocked("search operation count differs from budget")


def create_run_dir(output_root: Path, stamp: str | None = None) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    base = f"run_{stamp or datetime.now().strftime('%Y%m%d_%H%M%S')}"
    candidate = output_root / base
    suffix = 1
    while candidate.exists():
        candidate = output_root / f"{base}_{suffix:02d}"
        suffix += 1
    candidate.mkdir(parents=False, exist_ok=False)
    return candidate


def initial_checkpoint(created_at: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_state": "SEARCH_READY",
        "active_stage": "search",
        "operations_used": {"search": 0, "map": 0, "extract": 0, "global": 0},
        "operations": {
            item["operation_id"]: {
                "stage": "search", "state": "PENDING", "attempts": 0,
                "result_count": 0, "raw_record_ids": [],
            }
            for item in SEARCH_QUERIES
        },
        "error_signatures": {},
        "updated_at": created_at,
    }


def initialize_run(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    created = now_utc()
    plan = source_search_plan()
    validate_plan(plan)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "task": TASK,
        "created_at": created,
        "run_state": "SEARCH_READY",
        "backend": "tavily-python-sdk",
        "budgets": dict(BUDGET),
        "operations_used": {"search": 0, "map": 0, "extract": 0, "global": 0},
        "automatic_retries": 0,
        "staged_offline_selection_required": True,
        "crawl_authorized": False,
        "research_authorized": False,
        "absence_of_secrets": True,
    }
    checkpoint = initial_checkpoint(created)
    atomic_write_json(run_dir / "source_search_plan.json", plan)
    write_csv(run_dir / "source_registry.csv", SOURCE_FIELDS, [])
    atomic_write_text(run_dir / "search_results.jsonl", "")
    atomic_write_json(run_dir / "source_selection.json", {
        "schema_version": SCHEMA_VERSION,
        "selection_status": "PENDING_OFFLINE_REVIEW",
        "selected_sources": [],
        "instructions": "Select at most 5 source URLs from source_registry.csv; do not add unseen URLs.",
    })
    write_csv(run_dir / "mapped_pages.csv", MAPPED_FIELDS, [])
    atomic_write_json(run_dir / "extract_selection.json", {
        "schema_version": SCHEMA_VERSION,
        "selection_status": "PENDING_OFFLINE_REVIEW",
        "selected_pages": [],
        "instructions": "Select at most 10 concrete URLs found by Search or Map.",
    })
    atomic_write_text(run_dir / "extracted_pages.jsonl", "")
    write_csv(run_dir / "raw_brand_mentions.csv", BRAND_MENTION_FIELDS, [])
    write_csv(run_dir / "canonical_brand_candidates.csv", BRAND_CANDIDATE_FIELDS, [])
    write_csv(run_dir / "source_independence_groups.csv", INDEPENDENCE_FIELDS, [])
    write_csv(run_dir / "regional_language_coverage.csv", COVERAGE_FIELDS, [])
    write_csv(run_dir / "new_vs_historical_brands.csv", NOVELTY_FIELDS, [])
    atomic_write_text(run_dir / "operation_ledger.jsonl", "")
    atomic_write_text(run_dir / "errors.jsonl", "")
    atomic_write_json(run_dir / "manifest.json", manifest)
    atomic_write_json(run_dir / "checkpoint.json", checkpoint)
    refresh_outputs(run_dir, manifest, checkpoint)
    return manifest, checkpoint


def sdk_client_factory(api_key: str) -> Any:
    try:
        from tavily import TavilyClient
    except ImportError as exc:
        raise RunnerBlocked("tavily-python is not available locally") from exc
    return TavilyClient(api_key=api_key)


def inherited_api_key_reader(name: str) -> str | None:
    if name != "TAVILY_API_KEY":
        raise RunnerBlocked("unexpected environment variable request")
    return os.environ.get(name)


def compatible_existing_run(output_root: Path = OUTPUT_ROOT) -> Path | None:
    if not output_root.is_dir():
        return None
    for candidate in sorted(item for item in output_root.iterdir() if item.is_dir() and item.name.startswith("run_")):
        try:
            if (
                read_json(candidate / "source_search_plan.json") == source_search_plan()
                and all((candidate / name).exists() for name in REQUIRED_ARTIFACTS)
            ):
                return candidate
        except (OSError, ValueError, KeyError):
            continue
    return None


def safe_error_signature(exc: Exception) -> str:
    text = sanitize_text(f"{type(exc).__name__}: {exc}")
    lowered = text.lower()
    if any(marker in lowered for marker in ("401", "403", "unauthorized", "authentication")):
        return "AUTHENTICATION_ERROR"
    if "429" in lowered or "rate limit" in lowered:
        return "RATE_LIMIT_ERROR"
    if isinstance(exc, StructuralResponseError):
        return "STRUCTURAL_RESPONSE_ERROR"
    return type(exc).__name__


def should_stop_immediately(signature: str) -> bool:
    return signature in {"AUTHENTICATION_ERROR", "RATE_LIMIT_ERROR", "STRUCTURAL_RESPONSE_ERROR"}


def reserve_operation(run_dir: Path, checkpoint: dict[str, Any], operation_id: str, stage: str) -> None:
    operation = checkpoint["operations"][operation_id]
    if operation["attempts"] != 0 or operation["state"] != "PENDING":
        raise RunnerBlocked(f"operation cannot be attempted again: {operation_id}", "BLOCKED_RETRY", EXIT_BUDGET)
    if checkpoint["operations_used"][stage] >= BUDGET[stage]:
        raise RunnerBlocked(f"{stage} budget exhausted", "BLOCKED_BUDGET", EXIT_BUDGET)
    if checkpoint["operations_used"]["global"] >= BUDGET["global"]:
        raise RunnerBlocked("global operation budget exhausted", "BLOCKED_BUDGET", EXIT_BUDGET)
    operation["state"] = "ATTEMPT_RESERVED"
    operation["attempts"] = 1
    checkpoint["operations_used"][stage] += 1
    checkpoint["operations_used"]["global"] += 1
    checkpoint_write(run_dir, checkpoint)
    append_jsonl(run_dir / "operation_ledger.jsonl", {
        "at": now_utc(), "event": "ATTEMPT_RESERVED", "operation_id": operation_id,
        "stage": stage, "global_operation_number": checkpoint["operations_used"]["global"],
    })


def checkpoint_write(run_dir: Path, checkpoint: dict[str, Any]) -> None:
    checkpoint["updated_at"] = now_utc()
    atomic_write_json(run_dir / "checkpoint.json", checkpoint)


def record_failure(
    run_dir: Path, manifest: dict[str, Any], checkpoint: dict[str, Any],
    operation_id: str, stage: str, exc: Exception,
) -> int | None:
    signature = safe_error_signature(exc)
    message = sanitize_text(f"{type(exc).__name__}: {exc}")
    checkpoint["operations"][operation_id]["state"] = "FAILED"
    checkpoint["error_signatures"][signature] = checkpoint["error_signatures"].get(signature, 0) + 1
    append_jsonl(run_dir / "errors.jsonl", {
        "at": now_utc(), "operation_id": operation_id, "stage": stage,
        "error_signature": signature, "message": message, "retry_performed": False,
    })
    append_jsonl(run_dir / "operation_ledger.jsonl", {
        "at": now_utc(), "event": "FAILED", "operation_id": operation_id,
        "stage": stage, "retry_performed": False,
    })
    stop = should_stop_immediately(signature) or checkpoint["error_signatures"][signature] >= MAX_REPEATED_ERROR_SIGNATURES
    if stop:
        checkpoint["run_state"] = "STOPPED_ON_ERROR"
    checkpoint_write(run_dir, checkpoint)
    refresh_outputs(run_dir, manifest, checkpoint)
    if not stop:
        return None
    if signature == "AUTHENTICATION_ERROR":
        return EXIT_AUTHENTICATION
    if signature == "RATE_LIMIT_ERROR":
        return EXIT_BUDGET
    return EXIT_TECHNICAL


def complete_operation(
    run_dir: Path, manifest: dict[str, Any], checkpoint: dict[str, Any],
    operation_id: str, stage: str, result_count: int, raw_record_ids: list[str],
) -> None:
    operation = checkpoint["operations"][operation_id]
    operation["state"] = "COMPLETED"
    operation["result_count"] = result_count
    operation["raw_record_ids"] = raw_record_ids
    checkpoint_write(run_dir, checkpoint)
    append_jsonl(run_dir / "operation_ledger.jsonl", {
        "at": now_utc(), "event": "COMPLETED", "operation_id": operation_id,
        "stage": stage, "result_count": result_count, "raw_record_ids": raw_record_ids,
    })
    refresh_outputs(run_dir, manifest, checkpoint)


def extract_search_results(response: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(response, dict) or not isinstance(response.get("results"), list):
        raise StructuralResponseError("Search response must contain a results list")
    safe = sanitize_value(response)
    results = safe["results"]
    if len(results) > SEARCH_CONFIG["max_results"] or any(not isinstance(item, dict) for item in results):
        raise StructuralResponseError("Search results violate the frozen structure")
    return safe, results


def provisional_source_level(url: str, title: str, snippet: str) -> str:
    domain = domain_from_url(url)
    text = f"{title} {snippet}".lower()
    if domain in {"reddit.com", "quora.com"} or "forum" in text or "community" in text:
        return "B"
    if any(marker in text for marker in ("best ", "review", "comparison", "comparativa", "reseña")):
        return "C"
    return "D"


def run_search_stage(
    run_dir: Path, client: Any, manifest: dict[str, Any], checkpoint: dict[str, Any]
) -> int:
    checkpoint["active_stage"] = "search"
    checkpoint["run_state"] = "SEARCH_IN_PROGRESS"
    checkpoint_write(run_dir, checkpoint)
    source_rows = read_csv(run_dir / "source_registry.csv")
    for query_item in SEARCH_QUERIES:
        operation_id = query_item["operation_id"]
        state = checkpoint["operations"][operation_id]
        if state["state"] == "COMPLETED" or state["state"] == "FAILED":
            continue
        if state["state"] == "ATTEMPT_RESERVED":
            raise RunnerBlocked(
                f"ambiguous reserved Search operation: {operation_id}",
                "BLOCKED_AMBIGUOUS_ATTEMPT", EXIT_TECHNICAL,
            )
        reserve_operation(run_dir, checkpoint, operation_id, "search")
        try:
            response = client.search(query=query_item["query"], **SEARCH_CONFIG)
            safe, results = extract_search_results(response)
        except Exception as exc:
            failure_code = record_failure(run_dir, manifest, checkpoint, operation_id, "search", exc)
            if failure_code is not None:
                return failure_code
            continue
        payload_hash = sha256_json(safe)
        raw_record_id = "search_raw_" + sha256_json({"operation_id": operation_id, "payload_hash": payload_hash})[:24]
        append_jsonl(run_dir / "search_results.jsonl", {
            "schema_version": SCHEMA_VERSION, "raw_record_id": raw_record_id,
            "operation_id": operation_id, "region": query_item["region"],
            "language": query_item["language"], "query": query_item["query"],
            "retrieved_at": now_utc(), "payload_hash": payload_hash,
            "raw_payload": safe,
        })
        for rank, item in enumerate(results, start=1):
            url = sanitize_text(str(item.get("url", "")))
            canonical = canonicalize_url(url)
            title = sanitize_text(str(item.get("title", "")))
            snippet = sanitize_text(str(item.get("content", item.get("snippet", ""))))
            source_rows.append({
                "source_row_id": "source_" + sha256_json({"operation_id": operation_id, "rank": rank, "canonical_url": canonical})[:24],
                "search_operation_id": operation_id, "region": query_item["region"],
                "language": query_item["language"], "rank": rank, "title": title,
                "url": url, "canonical_url": canonical, "domain": domain_from_url(canonical),
                "score": item.get("score", ""), "snippet": snippet,
                "provisional_source_level": provisional_source_level(canonical, title, snippet),
                "selected_for_map": "NO", "raw_record_id": raw_record_id,
            })
        write_csv(run_dir / "source_registry.csv", SOURCE_FIELDS, source_rows)
        complete_operation(run_dir, manifest, checkpoint, operation_id, "search", len(results), [raw_record_id])
    checkpoint["active_stage"] = "offline_source_selection"
    checkpoint["run_state"] = "AWAITING_OFFLINE_SOURCE_SELECTION"
    checkpoint_write(run_dir, checkpoint)
    refresh_outputs(run_dir, manifest, checkpoint)
    return 0


def approved_source_selections(run_dir: Path) -> list[dict[str, Any]]:
    selection = read_json(run_dir / "source_selection.json")
    if selection.get("schema_version") != SCHEMA_VERSION or selection.get("selection_status") != "APPROVED":
        raise RunnerBlocked("source_selection.json requires offline APPROVED status", "BLOCKED_SELECTION")
    selected = selection.get("selected_sources")
    if not isinstance(selected, list) or not 1 <= len(selected) <= BUDGET["map"]:
        raise RunnerBlocked("source selection must contain 1 to 5 entries", "BLOCKED_SELECTION")
    registry = read_csv(run_dir / "source_registry.csv")
    allowed = {row["canonical_url"] for row in registry}
    seen = set()
    for index, item in enumerate(selected, start=1):
        if not isinstance(item, dict):
            raise RunnerBlocked("source selection rows must be objects", "BLOCKED_SELECTION")
        item.setdefault("selection_id", f"map_selection_{index:02d}")
        canonical = canonicalize_url(str(item.get("source_url", "")))
        if canonical not in allowed or canonical in seen:
            raise RunnerBlocked("Map selection must be unique and originate in Search", "BLOCKED_SELECTION")
        item["source_url"] = canonical
        seen.add(canonical)
    return selected


def extract_map_results(response: Any) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(response, dict) or not isinstance(response.get("results"), list):
        raise StructuralResponseError("Map response must contain a results list")
    safe = sanitize_value(response)
    urls = []
    for item in safe["results"]:
        if isinstance(item, str):
            url = item
        elif isinstance(item, dict) and isinstance(item.get("url"), str):
            url = item["url"]
        else:
            raise StructuralResponseError("Map results must be URLs or URL objects")
        canonical = canonicalize_url(url)
        if not canonical.startswith(("http://", "https://")):
            raise StructuralResponseError("Map produced an invalid URL")
        urls.append(canonical)
    return safe, urls


def ensure_stage_operations(checkpoint: dict[str, Any], stage: str, selections: list[dict[str, Any]]) -> None:
    prefix = "map" if stage == "map" else "extract"
    for index, selection in enumerate(selections, start=1):
        operation_id = f"{prefix}_{index:02d}_{sha256_json(selection)[:10]}"
        selection["operation_id"] = operation_id
        checkpoint["operations"].setdefault(operation_id, {
            "stage": stage, "state": "PENDING", "attempts": 0,
            "result_count": 0, "raw_record_ids": [],
        })


def run_map_stage(
    run_dir: Path, client: Any, manifest: dict[str, Any], checkpoint: dict[str, Any]
) -> int:
    selections = approved_source_selections(run_dir)
    ensure_stage_operations(checkpoint, "map", selections)
    checkpoint["active_stage"] = "map"
    checkpoint["run_state"] = "MAP_IN_PROGRESS"
    checkpoint_write(run_dir, checkpoint)
    mapped_rows = read_csv(run_dir / "mapped_pages.csv")
    for selection in selections:
        operation_id = selection["operation_id"]
        state = checkpoint["operations"][operation_id]
        if state["state"] in {"COMPLETED", "FAILED"}:
            continue
        if state["state"] == "ATTEMPT_RESERVED":
            raise RunnerBlocked(
                f"ambiguous reserved Map operation: {operation_id}",
                "BLOCKED_AMBIGUOUS_ATTEMPT", EXIT_TECHNICAL,
            )
        reserve_operation(run_dir, checkpoint, operation_id, "map")
        try:
            response = client.map(url=selection["source_url"], **MAP_CONFIG)
            safe, urls = extract_map_results(response)
        except Exception as exc:
            failure_code = record_failure(run_dir, manifest, checkpoint, operation_id, "map", exc)
            if failure_code is not None:
                return failure_code
            continue
        payload_hash = sha256_json(safe)
        raw_id = "map_raw_" + sha256_json({"operation_id": operation_id, "payload_hash": payload_hash})[:24]
        append_jsonl(run_dir / "operation_ledger.jsonl", {
            "at": now_utc(), "event": "RAW_EVIDENCE", "operation_id": operation_id,
            "stage": "map", "raw_record_id": raw_id, "payload_hash": payload_hash,
            "raw_payload": safe,
        })
        for rank, url in enumerate(urls, start=1):
            mapped_rows.append({
                "map_row_id": "maprow_" + sha256_json({"operation_id": operation_id, "rank": rank, "url": url})[:24],
                "map_operation_id": operation_id, "selection_id": selection["selection_id"],
                "source_url": selection["source_url"], "mapped_rank": rank,
                "mapped_url": url, "canonical_url": url, "domain": domain_from_url(url),
                "raw_record_id": raw_id,
            })
        write_csv(run_dir / "mapped_pages.csv", MAPPED_FIELDS, mapped_rows)
        complete_operation(run_dir, manifest, checkpoint, operation_id, "map", len(urls), [raw_id])
    checkpoint["active_stage"] = "offline_extract_selection"
    checkpoint["run_state"] = "AWAITING_OFFLINE_EXTRACT_SELECTION"
    checkpoint_write(run_dir, checkpoint)
    refresh_outputs(run_dir, manifest, checkpoint)
    return 0


def approved_extract_selections(run_dir: Path) -> list[dict[str, Any]]:
    selection = read_json(run_dir / "extract_selection.json")
    if selection.get("schema_version") != SCHEMA_VERSION or selection.get("selection_status") != "APPROVED":
        raise RunnerBlocked("extract_selection.json requires offline APPROVED status", "BLOCKED_SELECTION")
    selected = selection.get("selected_pages")
    if not isinstance(selected, list) or not 1 <= len(selected) <= BUDGET["extract"]:
        raise RunnerBlocked("extract selection must contain 1 to 10 entries", "BLOCKED_SELECTION")
    selection_plan = selection.get("selection_plan")
    selection_plan_hash = selection.get("selection_plan_sha256")
    if selection_plan is not None or selection_plan_hash is not None:
        if not isinstance(selection_plan, dict) or not isinstance(selection_plan_hash, str):
            raise RunnerBlocked("extract selection plan and hash must both be present", "BLOCKED_SELECTION")
        if sha256_json(selection_plan) != selection_plan_hash:
            raise RunnerBlocked("extract selection plan hash mismatch", "BLOCKED_SELECTION")
        if selection_plan.get("extract_budget_max") != BUDGET["extract"]:
            raise RunnerBlocked("extract selection plan budget mismatch", "BLOCKED_SELECTION")
        planned_row_ids = selection_plan.get("selected_map_row_ids")
        selected_row_ids = [item.get("map_source_id") for item in selected if isinstance(item, dict)]
        if planned_row_ids != selected_row_ids:
            raise RunnerBlocked("extract selection plan rows differ from selected pages", "BLOCKED_SELECTION")
    allowed = {row["canonical_url"] for row in read_csv(run_dir / "source_registry.csv")}
    mapped_rows = read_csv(run_dir / "mapped_pages.csv")
    allowed.update(row["canonical_url"] for row in mapped_rows)
    mapped_by_id = {row["map_row_id"]: row for row in mapped_rows}
    seen = set()
    for index, item in enumerate(selected, start=1):
        if not isinstance(item, dict):
            raise RunnerBlocked("extract selection rows must be objects", "BLOCKED_SELECTION")
        item.setdefault("selection_id", f"extract_selection_{index:02d}")
        canonical = canonicalize_url(str(item.get("url", "")))
        if canonical not in allowed or canonical in seen:
            raise RunnerBlocked("Extract selection must be unique and originate in Search or Map", "BLOCKED_SELECTION")
        map_source_id = item.get("map_source_id")
        if map_source_id is not None:
            mapped_row = mapped_by_id.get(str(map_source_id))
            if mapped_row is None or mapped_row["canonical_url"] != canonical:
                raise RunnerBlocked("Extract selection Map reference does not match its URL", "BLOCKED_SELECTION")
        item["url"] = canonical
        seen.add(canonical)
    return selected


def extract_extract_results(response: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(response, dict) or not isinstance(response.get("results"), list):
        raise StructuralResponseError("Extract response must contain a results list")
    safe = sanitize_value(response)
    if any(not isinstance(item, dict) for item in safe["results"]):
        raise StructuralResponseError("Extract results must be objects")
    return safe, safe["results"]


def run_extract_stage(
    run_dir: Path, client: Any, manifest: dict[str, Any], checkpoint: dict[str, Any]
) -> int:
    selections = approved_extract_selections(run_dir)
    ensure_stage_operations(checkpoint, "extract", selections)
    checkpoint["active_stage"] = "extract"
    checkpoint["run_state"] = "EXTRACT_IN_PROGRESS"
    checkpoint_write(run_dir, checkpoint)
    for selection in selections:
        operation_id = selection["operation_id"]
        state = checkpoint["operations"][operation_id]
        if state["state"] in {"COMPLETED", "FAILED"}:
            continue
        if state["state"] == "ATTEMPT_RESERVED":
            raise RunnerBlocked(
                f"ambiguous reserved Extract operation: {operation_id}",
                "BLOCKED_AMBIGUOUS_ATTEMPT", EXIT_TECHNICAL,
            )
        reserve_operation(run_dir, checkpoint, operation_id, "extract")
        try:
            response = client.extract(urls=[selection["url"]], **EXTRACT_CONFIG)
            safe, results = extract_extract_results(response)
        except Exception as exc:
            failure_code = record_failure(run_dir, manifest, checkpoint, operation_id, "extract", exc)
            if failure_code is not None:
                return failure_code
            continue
        payload_hash = sha256_json(safe)
        raw_id = "extract_raw_" + sha256_json({"operation_id": operation_id, "payload_hash": payload_hash})[:24]
        append_jsonl(run_dir / "extracted_pages.jsonl", {
            "schema_version": SCHEMA_VERSION, "raw_record_id": raw_id,
            "operation_id": operation_id, "selection_id": selection["selection_id"],
            "requested_url": selection["url"], "retrieved_at": now_utc(),
            "payload_hash": payload_hash, "raw_payload": safe,
        })
        complete_operation(run_dir, manifest, checkpoint, operation_id, "extract", len(results), [raw_id])
    checkpoint["active_stage"] = "offline_consolidation"
    checkpoint["run_state"] = "ACQUISITION_COMPLETED_PENDING_OFFLINE_CONSOLIDATION"
    checkpoint_write(run_dir, checkpoint)
    refresh_outputs(run_dir, manifest, checkpoint)
    return 0


def refresh_outputs(run_dir: Path, manifest: dict[str, Any], checkpoint: dict[str, Any]) -> None:
    manifest["run_state"] = checkpoint["run_state"]
    manifest["operations_used"] = dict(checkpoint["operations_used"])
    manifest["updated_at"] = now_utc()
    atomic_write_json(run_dir / "manifest.json", manifest)
    source_rows = read_csv(run_dir / "source_registry.csv") if (run_dir / "source_registry.csv").exists() else []
    coverage = []
    pairs = sorted({(item["region"], item["language"]) for item in SEARCH_QUERIES})
    for region, language in pairs:
        planned = [item for item in SEARCH_QUERIES if item["region"] == region and item["language"] == language]
        operation_ids = {item["operation_id"] for item in planned}
        members = [row for row in source_rows if row["search_operation_id"] in operation_ids]
        coverage.append({
            "region": region, "language": language,
            "planned_search_operations": len(planned),
            "completed_search_operations": sum(checkpoint["operations"][item["operation_id"]]["state"] == "COMPLETED" for item in planned),
            "search_result_rows": len(members), "unique_domains": len({row["domain"] for row in members}),
        })
    write_csv(run_dir / "regional_language_coverage.csv", COVERAGE_FIELDS, coverage)
    source_level_counts = Counter(row["provisional_source_level"] for row in source_rows)
    mapped_rows = read_csv(run_dir / "mapped_pages.csv") if (run_dir / "mapped_pages.csv").exists() else []
    extracted_envelopes = read_jsonl(run_dir / "extracted_pages.jsonl") if (run_dir / "extracted_pages.jsonl").exists() else []
    brand_mentions = read_csv(run_dir / "raw_brand_mentions.csv") if (run_dir / "raw_brand_mentions.csv").exists() else []
    brand_candidates = read_csv(run_dir / "canonical_brand_candidates.csv") if (run_dir / "canonical_brand_candidates.csv").exists() else []
    novelty_rows = read_csv(run_dir / "new_vs_historical_brands.csv") if (run_dir / "new_vs_historical_brands.csv").exists() else []
    independence_rows = read_csv(run_dir / "source_independence_groups.csv") if (run_dir / "source_independence_groups.csv").exists() else []
    unique_source_urls = {row["canonical_url"] for row in source_rows}
    unique_mapped_urls = {row["canonical_url"] for row in mapped_rows}

    def per_operation(numerator: int, stage: str) -> float | None:
        used = checkpoint["operations_used"][stage]
        return round(numerator / used, 6) if used else None

    metrics = {
        "schema_version": SCHEMA_VERSION,
        "run_state": checkpoint["run_state"],
        "budgets": dict(BUDGET),
        "operations_used": dict(checkpoint["operations_used"]),
        "operation_states": dict(Counter(item["state"] for item in checkpoint["operations"].values())),
        "source_rows": len(source_rows),
        "unique_source_urls": len(unique_source_urls),
        "unique_source_domains": len({row["domain"] for row in source_rows}),
        "mapped_page_rows": len(mapped_rows),
        "extracted_page_envelopes": len(extracted_envelopes),
        "brands_mentioned": len(brand_mentions),
        "brand_candidates": len(brand_candidates),
        "new_vs_historical_brand_rows": len(novelty_rows),
        "independence_group_rows": len(independence_rows),
        "sources_by_provisional_level": {
            level: source_level_counts.get(level, 0) for level in SOURCE_TAXONOMY
        },
        "regional_language_coverage_rows": len(coverage),
        "exact_duplicate_source_url_rows": len(source_rows) - len(unique_source_urls),
        "seo_duplication_review_status": "PENDING_OFFLINE_CONSOLIDATION",
        "noise_review_status": "PENDING_OFFLINE_CONSOLIDATION",
        "independent_repetition_review_status": "PENDING_OFFLINE_CONSOLIDATION",
        "information_value_per_operation": {
            "search_unique_source_urls": per_operation(len(unique_source_urls), "search"),
            "map_new_unique_urls": per_operation(len(unique_mapped_urls - unique_source_urls), "map"),
            "extract_page_envelopes": per_operation(len(extracted_envelopes), "extract"),
        },
        "marginal_value_by_stage": {
            "search_unique_source_urls": len(unique_source_urls),
            "map_new_unique_urls": len(unique_mapped_urls - unique_source_urls),
            "extract_page_envelopes": len(extracted_envelopes),
        },
        "error_rows": len(read_jsonl(run_dir / "errors.jsonl")) if (run_dir / "errors.jsonl").exists() else 0,
        "crawl_authorized": False, "research_authorized": False,
        "new_calls_automatically_authorized": False,
    }
    atomic_write_json(run_dir / "pilot_metrics.json", metrics)
    report = (
        "# BRAND-FIRST 1B multiregion pilot\n\n"
        f"- State: `{checkpoint['run_state']}`\n"
        f"- Search operations: `{checkpoint['operations_used']['search']}` / `{BUDGET['search']}`\n"
        f"- Map operations: `{checkpoint['operations_used']['map']}` / `{BUDGET['map']}`\n"
        f"- Extract operations: `{checkpoint['operations_used']['extract']}` / `{BUDGET['extract']}`\n"
        f"- Global operations: `{checkpoint['operations_used']['global']}` / `{BUDGET['global']}`\n"
        "- Automatic retries: `0`\n"
        "- Crawl authorized: `false`\n"
        "- Research authorized: `false`\n\n"
        "Search, Map, and Extract are separated by mandatory offline selections. "
        "This pilot does not confirm official domains, legality, or a definitive ranking.\n"
    )
    atomic_write_text(run_dir / "pilot_report.md", report)
    refresh_integrity(run_dir)


def artifact_secret_findings(run_dir: Path) -> int:
    total = 0
    for name in REQUIRED_ARTIFACTS:
        if name == "integrity_manifest.json":
            continue
        path = run_dir / name
        if path.exists():
            total += secret_count(path.read_text(encoding="utf-8"))
    return total


def refresh_integrity(run_dir: Path) -> None:
    artifacts = {}
    for name in REQUIRED_ARTIFACTS:
        if name == "integrity_manifest.json":
            continue
        path = run_dir / name
        if not path.exists():
            continue
        artifacts[name] = {"size": path.stat().st_size, "sha256": sha256_file(path)}
    atomic_write_json(run_dir / "integrity_manifest.json", {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "artifacts": artifacts,
        "secret_findings": artifact_secret_findings(run_dir),
        "crawl_authorized": False,
        "research_authorized": False,
    })


def validate_artifacts(
    run_dir: Path, *, allow_incomplete: bool,
    mutable_inputs: Iterable[str] = (),
) -> dict[str, Any]:
    missing = [name for name in REQUIRED_ARTIFACTS if not (run_dir / name).is_file()]
    if missing:
        raise RunnerBlocked(f"missing artifacts: {', '.join(missing)}", "BLOCKED_INTEGRITY")
    validate_plan(read_json(run_dir / "source_search_plan.json"))
    manifest = read_json(run_dir / "manifest.json")
    checkpoint = read_json(run_dir / "checkpoint.json")
    integrity = read_json(run_dir / "integrity_manifest.json")
    for jsonl_name in ("search_results.jsonl", "extracted_pages.jsonl", "operation_ledger.jsonl", "errors.jsonl"):
        read_jsonl(run_dir / jsonl_name)
    csv_contracts = {
        "source_registry.csv": SOURCE_FIELDS,
        "mapped_pages.csv": MAPPED_FIELDS,
        "raw_brand_mentions.csv": BRAND_MENTION_FIELDS,
        "canonical_brand_candidates.csv": BRAND_CANDIDATE_FIELDS,
        "source_independence_groups.csv": INDEPENDENCE_FIELDS,
        "regional_language_coverage.csv": COVERAGE_FIELDS,
        "new_vs_historical_brands.csv": NOVELTY_FIELDS,
    }
    for name, fields in csv_contracts.items():
        with (run_dir / name).open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != tuple(fields):
                raise RunnerBlocked(f"CSV schema mismatch: {name}", "BLOCKED_INTEGRITY")
            list(reader)
    if not (run_dir / "pilot_report.md").read_text(encoding="utf-8").startswith("# BRAND-FIRST 1B multiregion pilot"):
        raise RunnerBlocked("pilot report schema mismatch", "BLOCKED_INTEGRITY")
    used = checkpoint["operations_used"]
    if used["search"] > BUDGET["search"] or used["map"] > BUDGET["map"] or used["extract"] > BUDGET["extract"] or used["global"] > BUDGET["global"]:
        raise RunnerBlocked("checkpoint exceeds budget", "BLOCKED_INTEGRITY")
    if any(item["attempts"] > 1 for item in checkpoint["operations"].values()):
        raise RunnerBlocked("retry detected", "BLOCKED_INTEGRITY")
    if not allow_incomplete and checkpoint["run_state"] != "ACQUISITION_COMPLETED_PENDING_OFFLINE_CONSOLIDATION":
        raise RunnerBlocked("acquisition is incomplete", "BLOCKED_INTEGRITY")
    if artifact_secret_findings(run_dir) or integrity["secret_findings"]:
        raise RunnerBlocked("secret-like material found", "BLOCKED_INTEGRITY")
    mutable = set(mutable_inputs)
    if not mutable.issubset({"source_selection.json", "extract_selection.json"}):
        raise RunnerBlocked("unsupported mutable input", "BLOCKED_INTEGRITY")
    for name, metadata in integrity["artifacts"].items():
        if name in mutable:
            continue
        if sha256_file(run_dir / name) != metadata["sha256"] or (run_dir / name).stat().st_size != metadata["size"]:
            raise RunnerBlocked(f"artifact integrity mismatch: {name}", "BLOCKED_INTEGRITY")
    return {"manifest": manifest, "checkpoint": checkpoint, "integrity": integrity}


def acquire_client(
    client_factory: Callable[[str], Any], api_key_reader: Callable[[str], str | None]
) -> Any:
    try:
        api_key = api_key_reader("TAVILY_API_KEY")
    except RunnerBlocked:
        raise
    except SystemExit as exc:
        raise RunnerBlocked(
            f"credential reader terminated unexpectedly with code {exc.code}; no operation was reserved",
            "BLOCKED_CLIENT_INITIALIZATION", EXIT_TECHNICAL,
        ) from exc
    except Exception as exc:
        raise RunnerBlocked(
            f"credential reader failed before any operation reservation: {safe_error_signature(exc)}",
            "BLOCKED_CLIENT_INITIALIZATION", EXIT_TECHNICAL,
        ) from exc
    if not api_key or not api_key.strip():
        raise RunnerBlocked(
            "TAVILY_API_KEY is unavailable; no operation was reserved",
            "BLOCKED_AUTHENTICATION", EXIT_AUTHENTICATION,
        )
    try:
        client = client_factory(api_key)
    except RunnerBlocked:
        raise
    except SystemExit as exc:
        raise RunnerBlocked(
            f"Tavily client initialization terminated unexpectedly with code {exc.code}; no operation was reserved",
            "BLOCKED_CLIENT_INITIALIZATION", EXIT_TECHNICAL,
        ) from exc
    except Exception as exc:
        raise RunnerBlocked(
            f"Tavily client initialization failed before any operation reservation: {safe_error_signature(exc)}",
            "BLOCKED_CLIENT_INITIALIZATION", EXIT_TECHNICAL,
        ) from exc
    api_key = ""
    return client


def execute_new(
    *, output_root: Path = OUTPUT_ROOT,
    client_factory: Callable[[str], Any] = sdk_client_factory,
    api_key_reader: Callable[[str], str | None] = inherited_api_key_reader,
    stamp: str | None = None,
) -> tuple[int, Path | None]:
    existing = compatible_existing_run(output_root)
    if existing is not None:
        raise RunnerBlocked(
            f"compatible pilot run already exists: {existing.name}; resume it instead of starting another",
            "BLOCKED_EXISTING_RUN",
        )
    client = acquire_client(client_factory, api_key_reader)
    run_dir = create_run_dir(output_root, stamp)
    manifest, checkpoint = initialize_run(run_dir)
    return run_search_stage(run_dir, client, manifest, checkpoint), run_dir


def validate_resume_dir(run_dir: Path, output_root: Path, stage: str) -> Path:
    resolved = run_dir.resolve()
    root = output_root.resolve()
    if resolved.parent != root or not resolved.name.startswith("run_"):
        raise RunnerBlocked("resume run must be a direct child of the pilot output root")
    mutable_inputs: tuple[str, ...] = ()
    if stage == "map":
        mutable_inputs = ("source_selection.json",)
    elif stage == "extract":
        mutable_inputs = ("extract_selection.json",)
    validate_artifacts(resolved, allow_incomplete=True, mutable_inputs=mutable_inputs)
    return resolved


def resume_run(
    run_dir: Path, stage: str, *, output_root: Path = OUTPUT_ROOT,
    client_factory: Callable[[str], Any] = sdk_client_factory,
    api_key_reader: Callable[[str], str | None] = inherited_api_key_reader,
) -> tuple[int, Path]:
    run_dir = validate_resume_dir(run_dir, output_root, stage)
    manifest = read_json(run_dir / "manifest.json")
    checkpoint = read_json(run_dir / "checkpoint.json")
    allowed_states = {
        "search": {"SEARCH_READY", "SEARCH_IN_PROGRESS"},
        "map": {"AWAITING_OFFLINE_SOURCE_SELECTION", "MAP_IN_PROGRESS"},
        "extract": {"AWAITING_OFFLINE_EXTRACT_SELECTION", "EXTRACT_IN_PROGRESS"},
    }
    if checkpoint["run_state"] not in allowed_states.get(stage, set()):
        raise RunnerBlocked(
            f"run state {checkpoint['run_state']} cannot resume {stage}; completed stages cannot be repeated",
            "BLOCKED_STAGE",
        )
    if stage == "search":
        client = acquire_client(client_factory, api_key_reader)
        code = run_search_stage(run_dir, client, manifest, checkpoint)
    elif stage == "map":
        approved_source_selections(run_dir)
        client = acquire_client(client_factory, api_key_reader)
        refresh_integrity(run_dir)
        code = run_map_stage(run_dir, client, manifest, checkpoint)
    elif stage == "extract":
        approved_extract_selections(run_dir)
        client = acquire_client(client_factory, api_key_reader)
        refresh_integrity(run_dir)
        code = run_extract_stage(run_dir, client, manifest, checkpoint)
    else:
        raise RunnerBlocked("unsupported resume stage")
    return code, run_dir


def dry_run_summary() -> dict[str, Any]:
    plan = source_search_plan()
    validate_plan(plan)
    return {
        "task": TASK,
        "schema_version": SCHEMA_VERSION,
        "sdk_available_locally": importlib.util.find_spec("tavily") is not None,
        "search_operations": len(SEARCH_QUERIES),
        "search_queries": [dict(item) for item in SEARCH_QUERIES],
        "budgets": dict(BUDGET),
        "stage_contract": plan["stage_contract"],
        "source_taxonomy": dict(SOURCE_TAXONOMY),
        "independence_signals": list(INDEPENDENCE_SIGNALS),
        "blocked_capabilities": BLOCKED_CAPABILITIES,
        "credential_reads": 0,
        "client_instances": 0,
        "network_operations": 0,
        "run_created": False,
    }


def powershell_block() -> str:
    return r"""& {
    $projectRoot = 'C:\Proyectos\IPTV-Playlist-Builder-Premium'
    Set-Location -LiteralPath $projectRoot

    if (-not (Test-Path -LiteralPath Env:\TAVILY_API_KEY) -or
        [string]::IsNullOrWhiteSpace($env:TAVILY_API_KEY)) {
        Write-Error 'TAVILY_API_KEY is unavailable in this PowerShell process. No Tavily operation was made.'
        $runnerExitCode = 3
    }
    else {
        $env:PYTHONUTF8 = '1'
        $env:PYTHONIOENCODING = 'utf-8'

        $runnerOutput = & python -B .\scripts\run_brand_first_1b_multiregion_pilot.py --execute --approval-token 'BRAND-FIRST-1B-MULTIREGION-PILOT-01' --execution-origin powershell 2>&1
        $runnerExitCode = $LASTEXITCODE
        $runPathLine = $runnerOutput | Where-Object { $_ -like 'RUN_DIR=*' } | Select-Object -Last 1
        $runnerOutput |
            Where-Object { $_ -notlike 'RUN_DIR=*' } |
            ForEach-Object { Write-Output $_ }

        if ($runPathLine) {
            Write-Output $runPathLine
        }
        elseif ($runnerExitCode -eq 0) {
            Write-Error 'The runner did not report a run directory.'
            $runnerExitCode = 2
        }
    }
    Write-Output "RUNNER_EXIT_CODE=$runnerExitCode"
    Write-Output 'NEXT_STAGE=OFFLINE_SOURCE_SELECTION_BEFORE_MAP'
    Write-Output 'DO_NOT_RUN_AGAIN_IF_RUN_DIR_WAS_PRINTED'
}"""


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    modes = result.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--execute", action="store_true")
    modes.add_argument("--resume-run", type=Path)
    result.add_argument("--stage", choices=("search", "map", "extract"))
    result.add_argument("--approval-token")
    result.add_argument("--execution-origin", choices=("powershell",))
    result.add_argument("--print-powershell", action="store_true", help=argparse.SUPPRESS)
    return result


def validate_args(args: argparse.Namespace) -> None:
    if args.dry_run:
        if args.stage or args.approval_token or args.execution_origin:
            raise RunnerBlocked("dry-run cannot carry execution authorization")
        return
    if args.approval_token != APPROVAL_TOKEN or args.execution_origin != "powershell":
        raise RunnerBlocked("execute/resume requires the exact token and PowerShell origin")
    if args.execute and args.stage not in {None, "search"}:
        raise RunnerBlocked("new execution starts with Search only")
    if args.resume_run is not None and args.stage is None:
        raise RunnerBlocked("resume requires an explicit stage")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    run_dir = None
    try:
        validate_args(args)
        if args.dry_run:
            print(json.dumps(dry_run_summary(), ensure_ascii=False, indent=2))
            if args.print_powershell:
                print(powershell_block())
            return 0
        if args.execute:
            code, run_dir = execute_new()
        else:
            code, run_dir = resume_run(args.resume_run, args.stage)
        print(f"RUN_DIR={run_dir}")
        return code
    except RunnerBlocked as exc:
        print(f"{exc.run_state}: {sanitize_text(str(exc))}", file=sys.stderr)
        if run_dir is not None:
            print(f"RUN_DIR={run_dir}")
        return exc.exit_code
    except SystemExit as exc:
        print(
            f"UNEXPECTED_SYSTEM_EXIT: dependency terminated with code {exc.code}; no automatic retry is allowed",
            file=sys.stderr,
        )
        return EXIT_TECHNICAL
    except Exception as exc:
        print(
            f"UNEXPECTED_TECHNICAL_FAILURE: {safe_error_signature(exc)}; no automatic retry is allowed",
            file=sys.stderr,
        )
        return EXIT_TECHNICAL


if __name__ == "__main__":
    raise SystemExit(main())
