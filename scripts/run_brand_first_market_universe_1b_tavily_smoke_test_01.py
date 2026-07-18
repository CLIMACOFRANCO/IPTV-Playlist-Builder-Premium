#!/usr/bin/env python3
"""Auditable Tavily smoke-test runner for BRAND-FIRST-MARKET-UNIVERSE-1B.

The default preparation path is strictly offline. Only ``--execute`` can invoke
``tvly search``; it may optionally target a validated ``--resume-run``. The
execution path requires the frozen approval token and an explicit PowerShell
origin marker. The runner never reads or manages TAVILY_API_KEY.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import ipaddress
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


PHASE = "BRAND-FIRST-MARKET-UNIVERSE-1B"
SUBMILESTONE = "TAVILY-SMOKE-TEST-01"
TASK = "OFFLINE-RUNNER-PREPARATION"
SCHEMA_VERSION = "brand_first_market_universe_1b_tavily_smoke_test_01.v1"
APPROVAL_TOKEN = "BRAND-FIRST-1B-TAVILY-SMOKE-TEST-01"
EXPECTED_TVLY_VERSION = "tavily-cli 0.1.4"
BACKEND = "tvly-cli-search"
CHILD_TEXT_CONTRACT: dict[str, Any] = {
    "child_utf8_mode": True,
    "stdout_decode_encoding": "utf-8",
    "stderr_decode_encoding": "utf-8",
    "decode_errors": "strict",
    "environment_inheritance": "UNCHANGED_WITH_NON_SECRET_UTF8_OVERLAY",
}

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "research/output/best_iptv_2026/brand_first_market_universe_1b/tavily_smoke_test_01"
FIX4_RUN = PROJECT_ROOT / "research/output/best_iptv_2026/brand_first_market_universe_1a/run_20260717_051437"
HISTORICAL_BLOCKED_NAMES = frozenset({"run_20260717_235220", "run_20260718_000536"})
HISTORICAL_BLOCKED_RUNS = tuple(OUTPUT_ROOT / name for name in sorted(HISTORICAL_BLOCKED_NAMES))

QUERY_STATES = frozenset({
    "PENDING", "ATTEMPT_RESERVED", "COMPLETED", "FAILED",
    "SKIPPED_ALREADY_COMPLETED", "BLOCKED",
})
RUN_STATES = frozenset({
    "PREPARED", "EXECUTION_IN_PROGRESS", "EXECUTION_COMPLETED",
    "EXECUTION_PARTIAL", "BLOCKED_AUTHENTICATION", "BLOCKED_BUDGET",
    "BLOCKED_CONFIGURATION", "BLOCKED_INTEGRITY", "FAILED_TECHNICAL",
})

FROZEN_QUERIES: tuple[dict[str, Any], ...] = (
    {
        "sequence": 1,
        "query_id": "digitalizard_q1_official_company",
        "role": "BRAND_CANDIDATE",
        "query": '"DigitaLizard IPTV" official website company',
    },
    {
        "sequence": 2,
        "query_id": "digitalizard_q2_reviews_reseller_operator",
        "role": "BRAND_CANDIDATE",
        "query": '"DigitaLizard IPTV" reviews app reseller operator',
    },
    {
        "sequence": 3,
        "query_id": "smarters_q3_official_player_application",
        "role": "NEGATIVE_CONTROL",
        "query": '"IPTV Smarters Pro" official website player application',
    },
    {
        "sequence": 4,
        "query_id": "smarters_q4_subscription_provider",
        "role": "NEGATIVE_CONTROL",
        "query": '"IPTV Smarters Pro" IPTV subscription provider',
    },
)

FROZEN_CONFIG: dict[str, Any] = {
    "product": "Tavily Search",
    "backend": BACKEND,
    "search_depth": "basic",
    "max_results_per_query": 5,
    "max_physical_calls": 4,
    "max_physical_calls_per_query": 1,
    "automatic_retries": 0,
    "max_theoretical_results": 20,
    "include_answer": False,
    "include_images": False,
    "include_raw_content": False,
    "extract_allowed": False,
    "map_allowed": False,
    "crawl_allowed": False,
    "research_allowed": False,
    "agent_skills_allowed": False,
}

REQUIRED_ARTIFACTS = (
    "query_plan.json", "manifest.json", "checkpoint.json",
    "query_ledger.jsonl", "raw_results.jsonl", "normalized_results.csv",
    "domain_summary.csv", "errors.jsonl", "smoke_test_report.md",
    "integrity_manifest.json",
)
NORMALIZED_FIELDS = (
    "row_id", "query_id", "role", "rank", "title", "url",
    "canonical_url", "hostname", "registrable_domain", "score",
    "snippet_content", "retrieved_at", "raw_payload_hash",
    "raw_response_row_id",
)
DOMAIN_FIELDS = (
    "domain", "query_ids", "roles", "result_count", "best_rank",
    "unique_urls",
)

SECRET_PATTERNS = (
    re.compile(r"(?i)\b(?:bearer)\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)\btvly-[A-Za-z0-9._-]{16,}"),
    re.compile(r"(?i)\b(?:api[_ -]?key|authorization|access[_ -]?token)\b\s*[:=]\s*[^\s,;]+"),
)
AUTH_ERROR_PATTERN = re.compile(
    r"(?i)(authentication|unauthori[sz]ed|forbidden|permission denied|invalid credentials?|api[_ ]?key)"
)
FORBIDDEN_REPORT_TERMS = (
    "SIRVIO", "SIRVIÓ", "SIRVIO PARCIALMENTE", "SIRVIÓ PARCIALMENTE",
    "NO SIRVIO", "NO SIRVIÓ", "OFFICIAL DOMAIN", "DOMINIO OFICIAL",
    "LEGALITY", "LEGALIDAD", "PROVIDER RANKING", "RANKING DE PROVEEDORES",
)


class RunnerBlocked(RuntimeError):
    """A deterministic stop condition with a stable run state and exit code."""

    def __init__(self, message: str, run_state: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.run_state = run_state
        self.exit_code = exit_code


class ChildOutputDecodeError(RuntimeError):
    """The child emitted bytes that are not valid under the UTF-8 contract."""

    def __init__(self, stream_name: str, start: int) -> None:
        super().__init__(f"tvly {stream_name} was not valid UTF-8 at byte offset {start}")
        self.stream_name = stream_name
        self.start = start


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def frozen_plan_body() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "submilestone": SUBMILESTONE,
        "task": TASK,
        "queries": [dict(item) for item in FROZEN_QUERIES],
        "configuration": dict(FROZEN_CONFIG),
        "total_call_budget": FROZEN_CONFIG["max_physical_calls"],
    }


def frozen_plan_hash() -> str:
    return sha256_text(canonical_json(frozen_plan_body()))


def frozen_plan() -> dict[str, Any]:
    value = frozen_plan_body()
    value["canonical_plan_hash"] = frozen_plan_hash()
    return value


def validate_frozen_plan(value: dict[str, Any]) -> None:
    expected = frozen_plan()
    if value != expected:
        raise RunnerBlocked(
            "query plan, order, IDs, queries, or configuration differ from the frozen plan",
            "BLOCKED_CONFIGURATION",
        )
    supplied_hash = value.get("canonical_plan_hash")
    body = {key: item for key, item in value.items() if key != "canonical_plan_hash"}
    if supplied_hash != sha256_text(canonical_json(body)) or supplied_hash != frozen_plan_hash():
        raise RunnerBlocked("canonical plan hash mismatch", "BLOCKED_INTEGRITY")


def validate_budget(checkpoint: dict[str, Any], query_id: str | None = None) -> None:
    reserved = int(checkpoint.get("calls_reserved", 0))
    if reserved >= FROZEN_CONFIG["max_physical_calls"]:
        raise RunnerBlocked("absolute physical-call budget exhausted", "BLOCKED_BUDGET")
    if query_id is not None:
        query_state = checkpoint["queries"].get(query_id, {})
        if int(query_state.get("attempts_reserved", 0)) >= FROZEN_CONFIG["max_physical_calls_per_query"]:
            raise RunnerBlocked(f"physical-call budget exhausted for {query_id}", "BLOCKED_BUDGET")


def atomic_write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_text(path: Path, value: str) -> None:
    atomic_write_bytes(path, value.encode("utf-8"))


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunnerBlocked(f"invalid JSON checkpoint or artifact: {path.name}: {sanitize_text(str(exc))}", "BLOCKED_INTEGRITY") from exc


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("JSONL row is not an object")
                rows.append(value)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise RunnerBlocked(f"invalid JSONL {path.name}: {sanitize_text(str(exc))}", "BLOCKED_INTEGRITY") from exc
    return rows


def atomic_write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    atomic_write_text(path, text)


def atomic_append_jsonl(path: Path, row: dict[str, Any]) -> None:
    rows = read_jsonl(path) if path.exists() else []
    rows.append(row)
    atomic_write_jsonl(path, rows)


def atomic_write_csv(path: Path, fields: tuple[str, ...], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


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


def secret_findings_in_text(value: str) -> list[str]:
    return sorted({pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(value)})


def directory_fingerprint(path: Path) -> dict[str, Any]:
    if not path.is_dir():
        return {"path": str(path), "exists": False, "file_count": 0, "aggregate_sha256": None, "files": []}
    files = []
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        relative = item.relative_to(path).as_posix()
        digest = sha256_file(item).upper()
        files.append({"path": relative, "size": item.stat().st_size, "sha256": digest})
    aggregate = sha256_text("\n".join(f"{item['path']}|{item['sha256']}" for item in files))
    return {
        "path": str(path), "exists": True, "file_count": len(files),
        "aggregate_sha256": aggregate, "files": files,
    }


def protected_fingerprints() -> dict[str, Any]:
    paths = (FIX4_RUN, *HISTORICAL_BLOCKED_RUNS)
    return {path.name: directory_fingerprint(path) for path in paths}


def protected_hashes_match(before: dict[str, Any], after: dict[str, Any]) -> bool:
    keys = set(before) | set(after)
    return all(
        before.get(key, {}).get("aggregate_sha256") == after.get(key, {}).get("aggregate_sha256")
        and before.get(key, {}).get("file_count") == after.get(key, {}).get("file_count")
        for key in keys
    )


def local_git_snapshot() -> dict[str, Any]:
    def git(*args: str) -> str:
        process = subprocess.run(
            ["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True,
            check=False, timeout=15,
        )
        if process.returncode != 0:
            raise RunnerBlocked(f"local git metadata unavailable: {sanitize_text(process.stderr)}", "BLOCKED_INTEGRITY")
        return process.stdout.strip()

    return {
        "head": git("rev-parse", "HEAD"),
        "origin_main_local": git("rev-parse", "refs/remotes/origin/main"),
        "divergence": git("rev-list", "--left-right", "--count", "HEAD...origin/main"),
        "branch": git("branch", "--show-current"),
    }


def local_tvly_version() -> str:
    process = subprocess.run(
        ["tvly", "--version"], cwd=PROJECT_ROOT, capture_output=True, text=True,
        check=False, timeout=15,
    )
    output = sanitize_text((process.stdout + "\n" + process.stderr).strip())
    if process.returncode != 0 or EXPECTED_TVLY_VERSION not in output:
        raise RunnerBlocked(f"unsupported local tvly contract: {output}", "BLOCKED_CONFIGURATION")
    return EXPECTED_TVLY_VERSION


def tvly_command(query_item: dict[str, Any]) -> list[str]:
    validate_frozen_plan(frozen_plan())
    return [
        "tvly", "search", query_item["query"],
        "--depth", FROZEN_CONFIG["search_depth"],
        "--max-results", str(FROZEN_CONFIG["max_results_per_query"]),
        "--json",
    ]


@contextmanager
def child_utf8_environment() -> Iterable[None]:
    """Overlay only non-sensitive UTF-8 controls while preserving inheritance.

    ``env=None`` remains in use for the child, so its normal environment and
    authentication behavior are inherited without copying, enumerating,
    logging, or persisting any environment values. Only the two explicitly
    named, non-secret Python text controls are temporarily changed and restored.
    """
    names = ("PYTHONUTF8", "PYTHONIOENCODING")
    replacements = ("1", "utf-8")
    existed = tuple(name in os.environ for name in names)
    previous = tuple(os.environ.get(name) for name in names)
    try:
        for name, value in zip(names, replacements):
            os.environ[name] = value
        yield
    finally:
        for name, was_present, old_value in zip(names, existed, previous):
            if was_present and old_value is not None:
                os.environ[name] = old_value
            else:
                os.environ.pop(name, None)


def invoke_tvly_search(query_item: dict[str, Any]) -> subprocess.CompletedProcess[bytes]:
    with child_utf8_environment():
        return subprocess.run(
            tvly_command(query_item), cwd=PROJECT_ROOT, capture_output=True,
            text=False, env=None, check=False, timeout=120,
        )


def decode_child_stream(value: bytes | str | None, stream_name: str) -> str:
    """Decode a fully captured child stream without lossy replacement."""
    if value is None:
        return ""
    if isinstance(value, str):  # deterministic test doubles and compatibility
        return value
    if not isinstance(value, bytes):
        raise TypeError(f"unsupported tvly {stream_name} type: {type(value).__name__}")
    try:
        return value.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ChildOutputDecodeError(stream_name, exc.start) from exc


def parse_structured_output(stdout: str) -> Any:
    cleaned = sanitize_text(stdout).strip()
    if not cleaned:
        raise RunnerBlocked("tvly returned empty, unstructured output", "FAILED_TECHNICAL", 4)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as first_error:
        candidates = [position for position in (cleaned.find("{"), cleaned.find("[")) if position >= 0]
        if not candidates:
            raise RunnerBlocked("tvly output is not structured JSON", "FAILED_TECHNICAL", 4) from first_error
        start = min(candidates)
        try:
            value, end = json.JSONDecoder().raw_decode(cleaned[start:])
            if cleaned[start + end:].strip():
                raise ValueError("unexpected trailing output")
        except (json.JSONDecodeError, ValueError) as exc:
            raise RunnerBlocked("tvly output is not deterministic structured JSON", "FAILED_TECHNICAL", 4) from exc
    if not isinstance(value, (dict, list)):
        raise RunnerBlocked("tvly JSON root is neither object nor array", "FAILED_TECHNICAL", 4)
    return sanitize_value(value)


def extract_results(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        results = payload
    elif isinstance(payload, dict) and "results" in payload:
        results = payload["results"]
    else:
        raise RunnerBlocked("tvly JSON does not contain a results array", "FAILED_TECHNICAL", 4)
    if not isinstance(results, list) or any(not isinstance(item, dict) for item in results):
        raise RunnerBlocked("tvly results are not a JSON object array", "FAILED_TECHNICAL", 4)
    if len(results) > FROZEN_CONFIG["max_results_per_query"]:
        raise RunnerBlocked("tvly returned more than the frozen maximum", "BLOCKED_CONFIGURATION")
    return [sanitize_value(item) for item in results]


def canonicalize_url(value: str) -> tuple[str, str]:
    if not value:
        return "", ""
    try:
        parts = urlsplit(value.strip())
        hostname = (parts.hostname or "").lower().rstrip(".")
        if not hostname:
            return value.strip(), ""
        scheme = parts.scheme.lower() or "https"
        port = parts.port
        netloc = hostname
        if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
            netloc = f"{hostname}:{port}"
        path = parts.path or "/"
        query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)), doseq=True)
        return urlunsplit((scheme, netloc, path, query, "")), hostname
    except (ValueError, UnicodeError):
        return value.strip(), ""


def registrable_domain(hostname: str) -> str:
    if not hostname:
        return ""
    try:
        ipaddress.ip_address(hostname)
        return hostname
    except ValueError:
        pass
    labels = hostname.split(".")
    if len(labels) <= 2:
        return hostname
    common_two_part_suffixes = {"co.uk", "com.au", "com.br", "com.mx", "co.nz", "co.jp"}
    suffix = ".".join(labels[-2:])
    return ".".join(labels[-3:]) if suffix in common_two_part_suffixes else suffix


def normalize_results(
    query_item: dict[str, Any], payload: Any, retrieved_at: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    sanitized_payload = sanitize_value(payload)
    results = extract_results(sanitized_payload)
    response_hash = sha256_text(canonical_json(sanitized_payload))
    raw_row_id = "raw_" + sha256_text(query_item["query_id"] + "|" + response_hash)[:24]
    raw_row = {
        "row_id": raw_row_id,
        "query_id": query_item["query_id"],
        "role": query_item["role"],
        "rank": None,
        "retrieved_at": retrieved_at,
        "raw_payload": sanitized_payload,
        "raw_payload_hash": response_hash,
    }
    normalized = []
    for rank, item in enumerate(results, 1):
        item_hash = sha256_text(canonical_json(item))
        url = str(item.get("url") or "")
        canonical_url, hostname = canonicalize_url(url)
        normalized.append({
            "row_id": "norm_" + sha256_text(f"{query_item['query_id']}|{rank}|{item_hash}")[:24],
            "query_id": query_item["query_id"],
            "role": query_item["role"],
            "rank": rank,
            "title": sanitize_text(str(item.get("title") or "")),
            "url": sanitize_text(url),
            "canonical_url": sanitize_text(canonical_url),
            "hostname": hostname,
            "registrable_domain": registrable_domain(hostname),
            "score": item.get("score", ""),
            "snippet_content": sanitize_text(str(item.get("content") or item.get("snippet") or "")),
            "retrieved_at": retrieved_at,
            "raw_payload_hash": item_hash,
            "raw_response_row_id": raw_row_id,
        })
    return raw_row, normalized


def domain_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        domain = str(row.get("registrable_domain") or row.get("hostname") or "")
        if domain:
            grouped.setdefault(domain, []).append(row)
    summary = []
    for domain in sorted(grouped):
        members = grouped[domain]
        summary.append({
            "domain": domain,
            "query_ids": "|".join(sorted({str(item["query_id"]) for item in members})),
            "roles": "|".join(sorted({str(item["role"]) for item in members})),
            "result_count": len(members),
            "best_rank": min(int(item["rank"]) for item in members),
            "unique_urls": "|".join(sorted({str(item["canonical_url"]) for item in members if item.get("canonical_url")})),
        })
    return summary


def ledger_record(
    query_item: dict[str, Any], state: dict[str, Any], *, status: str,
    finished_at: str, result_count: int, exit_code: int | None,
    error_class: str | None, raw_row_ids: list[str],
) -> dict[str, Any]:
    body = {
        "query_id": query_item["query_id"], "role": query_item["role"],
        "query": query_item["query"], "sequence": query_item["sequence"],
        "status": status, "attempt_number": state["attempts_reserved"],
        "physical_call_number": state["physical_call_number"],
        "started_at": state["started_at"], "finished_at": finished_at,
        "result_count": result_count, "exit_code": exit_code,
        "error_class": error_class, "raw_row_ids": raw_row_ids,
    }
    body["record_hash"] = sha256_text(canonical_json(body))
    return body


def initial_checkpoint(run_id: str, runner_hash: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_state": "PREPARED",
        "plan_hash": frozen_plan_hash(),
        "runner_hash": runner_hash,
        "calls_reserved": 0,
        "calls_performed": 0,
        "calls_remaining": FROZEN_CONFIG["max_physical_calls"],
        "results_raw": 0,
        "results_normalized": 0,
        "resume_events": [],
        "queries": {
            item["query_id"]: {
                "sequence": item["sequence"], "status": "PENDING",
                "attempts_reserved": 0, "physical_call_number": None,
                "started_at": None, "finished_at": None, "result_count": None,
                "exit_code": None, "error_class": None, "raw_row_ids": [],
            }
            for item in FROZEN_QUERIES
        },
    }


def relative_artifact_paths(run_dir: Path) -> dict[str, str]:
    return {name: (run_dir / name).relative_to(PROJECT_ROOT).as_posix() for name in REQUIRED_ARTIFACTS}


def initial_manifest(
    run_dir: Path, checkpoint: dict[str, Any], git: dict[str, Any],
    tvly_version: str, originated_from_powershell: bool,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE, "submilestone": SUBMILESTONE, "task": TASK,
        "run_id": checkpoint["run_id"], "created_at": utc_now(),
        "updated_at": utc_now(), "state": checkpoint["run_state"],
        "head": git["head"], "origin_main_local": git["origin_main_local"],
        "divergence": git["divergence"], "branch": git["branch"],
        "runner_hash": checkpoint["runner_hash"], "plan_hash": frozen_plan_hash(),
        "python_version": sys.version.split()[0], "tvly_version": tvly_version,
        "backend": BACKEND, "search_configuration": dict(FROZEN_CONFIG),
        "child_process_text_contract": dict(CHILD_TEXT_CONTRACT),
        "calls_reserved": 0, "calls_performed": 0,
        "calls_remaining": FROZEN_CONFIG["max_physical_calls"],
        "results_raw": 0, "results_normalized": 0,
        "artifact_paths": relative_artifact_paths(run_dir),
        "originated_from_powershell": originated_from_powershell,
        "secrets_persisted": False,
    }


def report_text(manifest: dict[str, Any], checkpoint: dict[str, Any], normalized: list[dict[str, Any]], errors: list[dict[str, Any]]) -> str:
    unique_urls = {row["canonical_url"] for row in normalized if row.get("canonical_url")}
    domains = {row["registrable_domain"] for row in normalized if row.get("registrable_domain")}
    duplicates = max(0, len(normalized) - len(unique_urls))
    completed = sum(1 for state in checkpoint["queries"].values() if state["status"] == "COMPLETED")
    return (
        "# Technical smoke-test report\n\n"
        f"- Phase: `{PHASE}`\n"
        f"- Submilestone: `{SUBMILESTONE}`\n"
        f"- Run ID: `{manifest['run_id']}`\n"
        f"- Technical state: `{checkpoint['run_state']}`\n"
        f"- Completed queries: {completed}/4\n"
        f"- Physical calls reserved: {checkpoint['calls_reserved']}/4\n"
        f"- Physical calls performed: {checkpoint['calls_performed']}/4\n"
        f"- Remaining call budget: {checkpoint['calls_remaining']}\n"
        f"- Normalized results: {len(normalized)}\n"
        f"- Unique canonical URLs: {len(unique_urls)}\n"
        f"- Mechanical duplicate count: {duplicates}\n"
        f"- Distinct registrable domains: {len(domains)}\n"
        f"- Technical errors: {len(errors)}\n\n"
        "## Traceability\n\n"
        f"Plan hash: `{manifest['plan_hash']}`. Runner hash: `{manifest['runner_hash']}`. "
        "Raw response envelopes, normalized rows, ledger records, checkpoints, and file hashes are retained.\n\n"
        "## Limitations\n\n"
        "This report is limited to acquisition mechanics, budgets, schemas, duplicates, domains, errors, and traceability. "
        "Interpretation and adjudication are outside this technical run.\n"
    )


def refresh_manifest(manifest: dict[str, Any], checkpoint: dict[str, Any]) -> None:
    manifest.update({
        "updated_at": utc_now(), "state": checkpoint["run_state"],
        "calls_reserved": checkpoint["calls_reserved"],
        "calls_performed": checkpoint["calls_performed"],
        "calls_remaining": checkpoint["calls_remaining"],
        "results_raw": checkpoint["results_raw"],
        "results_normalized": checkpoint["results_normalized"],
    })


def build_integrity_manifest(
    run_dir: Path, historical_before: dict[str, Any], historical_after: dict[str, Any],
) -> dict[str, Any]:
    artifact_hashes = {}
    for name in REQUIRED_ARTIFACTS:
        if name == "integrity_manifest.json":
            continue
        path = run_dir / name
        artifact_hashes[name] = {"sha256": sha256_file(path), "size": path.stat().st_size}
    runner_path = Path(__file__).resolve()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "run_id": run_dir.name,
        "runner": {"path": runner_path.relative_to(PROJECT_ROOT).as_posix(), "sha256": sha256_file(runner_path)},
        "plan_hash": frozen_plan_hash(),
        "artifacts": artifact_hashes,
        "historical_runs_before": historical_before,
        "historical_runs_after": historical_after,
        "historical_runs_unchanged": protected_hashes_match(historical_before, historical_after),
        "circular_file_omitted": "integrity_manifest.json",
    }


def refresh_outputs(
    run_dir: Path, manifest: dict[str, Any], checkpoint: dict[str, Any],
    historical_before: dict[str, Any], historical_after: dict[str, Any] | None = None,
) -> None:
    raw_rows = read_jsonl(run_dir / "raw_results.jsonl")
    ledger_rows = read_jsonl(run_dir / "query_ledger.jsonl")
    error_rows = read_jsonl(run_dir / "errors.jsonl")
    del raw_rows, ledger_rows  # parsed here to fail closed if either log is corrupt
    with (run_dir / "normalized_results.csv").open("r", encoding="utf-8", newline="") as handle:
        normalized = list(csv.DictReader(handle))
    checkpoint["results_raw"] = sum(int(state.get("result_count") or 0) for state in checkpoint["queries"].values())
    checkpoint["results_normalized"] = len(normalized)
    checkpoint["calls_remaining"] = FROZEN_CONFIG["max_physical_calls"] - checkpoint["calls_reserved"]
    refresh_manifest(manifest, checkpoint)
    atomic_write_json(run_dir / "checkpoint.json", checkpoint)
    atomic_write_csv(run_dir / "domain_summary.csv", DOMAIN_FIELDS, domain_summary(normalized))
    atomic_write_text(run_dir / "smoke_test_report.md", report_text(manifest, checkpoint, normalized, error_rows))
    atomic_write_json(run_dir / "manifest.json", manifest)
    after = historical_after if historical_after is not None else historical_before
    atomic_write_json(run_dir / "integrity_manifest.json", build_integrity_manifest(run_dir, historical_before, after))


def ensure_no_completed_sibling(output_root: Path) -> None:
    if not output_root.exists():
        return
    for child in sorted(output_root.iterdir()):
        if not child.is_dir() or child.name in HISTORICAL_BLOCKED_NAMES:
            continue
        manifest_path = child / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = read_json(manifest_path)
        if manifest.get("plan_hash") != frozen_plan_hash():
            continue
        if manifest.get("state") == "EXECUTION_COMPLETED":
            raise RunnerBlocked(f"completed sibling smoke-test run already exists: {child.name}", "BLOCKED_INTEGRITY")
        if manifest.get("state") in RUN_STATES:
            raise RunnerBlocked(
                f"compatible sibling run already exists and must be resumed instead of duplicated: {child.name}",
                "BLOCKED_INTEGRITY",
            )


def initialize_run(
    run_dir: Path, *, git: dict[str, Any], tvly_version: str,
    historical_before: dict[str, Any], originated_from_powershell: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if run_dir.exists():
        raise RunnerBlocked(f"run directory already exists: {run_dir}", "BLOCKED_INTEGRITY")
    run_dir.mkdir(parents=True, exist_ok=False)
    runner_hash = sha256_file(Path(__file__).resolve())
    checkpoint = initial_checkpoint(run_dir.name, runner_hash)
    manifest = initial_manifest(run_dir, checkpoint, git, tvly_version, originated_from_powershell)
    atomic_write_json(run_dir / "query_plan.json", frozen_plan())
    atomic_write_json(run_dir / "checkpoint.json", checkpoint)
    atomic_write_jsonl(run_dir / "query_ledger.jsonl", [])
    atomic_write_jsonl(run_dir / "raw_results.jsonl", [])
    atomic_write_csv(run_dir / "normalized_results.csv", NORMALIZED_FIELDS, [])
    atomic_write_csv(run_dir / "domain_summary.csv", DOMAIN_FIELDS, [])
    atomic_write_jsonl(run_dir / "errors.jsonl", [])
    atomic_write_text(run_dir / "smoke_test_report.md", report_text(manifest, checkpoint, [], []))
    atomic_write_json(run_dir / "manifest.json", manifest)
    atomic_write_json(run_dir / "integrity_manifest.json", build_integrity_manifest(run_dir, historical_before, historical_before))
    return manifest, checkpoint


def validate_run_compatibility(
    run_dir: Path, output_root: Path = OUTPUT_ROOT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    resolved = run_dir.resolve()
    if resolved.name in HISTORICAL_BLOCKED_NAMES:
        raise RunnerBlocked("historical blocked runs cannot be resumed", "BLOCKED_INTEGRITY")
    if resolved.parent != output_root.resolve():
        raise RunnerBlocked("resume path is foreign to this smoke-test output root", "BLOCKED_INTEGRITY")
    missing = [name for name in REQUIRED_ARTIFACTS if not (resolved / name).is_file()]
    if missing:
        raise RunnerBlocked(f"resume run is missing required artifacts: {', '.join(missing)}", "BLOCKED_INTEGRITY")
    plan = read_json(resolved / "query_plan.json")
    validate_frozen_plan(plan)
    manifest = read_json(resolved / "manifest.json")
    checkpoint = read_json(resolved / "checkpoint.json")
    runner_hash = sha256_file(Path(__file__).resolve())
    checks = (
        manifest.get("schema_version") == SCHEMA_VERSION,
        checkpoint.get("schema_version") == SCHEMA_VERSION,
        manifest.get("run_id") == resolved.name == checkpoint.get("run_id"),
        manifest.get("plan_hash") == checkpoint.get("plan_hash") == frozen_plan_hash(),
        manifest.get("runner_hash") == checkpoint.get("runner_hash") == runner_hash,
        manifest.get("search_configuration") == FROZEN_CONFIG,
        manifest.get("child_process_text_contract") == CHILD_TEXT_CONTRACT,
        manifest.get("backend") == BACKEND,
        manifest.get("originated_from_powershell") is True,
    )
    if not all(checks):
        raise RunnerBlocked("resume run hashes, runner, backend, origin, or configuration are incompatible", "BLOCKED_INTEGRITY")
    for query_id, state in checkpoint.get("queries", {}).items():
        if state.get("status") not in QUERY_STATES:
            raise RunnerBlocked(f"invalid query state in checkpoint: {query_id}", "BLOCKED_INTEGRITY")
        if state.get("status") == "ATTEMPT_RESERVED":
            raise RunnerBlocked(f"ambiguous reserved attempt cannot be repeated: {query_id}", "BLOCKED_INTEGRITY")
    validate_integrity_manifest(resolved)
    validate_artifacts(resolved, require_completed=False)
    return manifest, checkpoint


def add_error(run_dir: Path, query_id: str | None, error_class: str, message: str) -> None:
    body = {
        "timestamp": utc_now(), "query_id": query_id,
        "error_class": error_class, "message": sanitize_text(message),
    }
    body["record_hash"] = sha256_text(canonical_json(body))
    atomic_append_jsonl(run_dir / "errors.jsonl", body)


def process_run(
    run_dir: Path, manifest: dict[str, Any], checkpoint: dict[str, Any],
    historical_before: dict[str, Any],
    backend: Callable[[dict[str, Any]], subprocess.CompletedProcess[Any]] = invoke_tvly_search,
) -> int:
    validate_frozen_plan(read_json(run_dir / "query_plan.json"))
    if checkpoint["run_state"] == "EXECUTION_COMPLETED":
        raise RunnerBlocked("this run is already completed", "BLOCKED_INTEGRITY")
    checkpoint["run_state"] = "EXECUTION_IN_PROGRESS"
    refresh_outputs(run_dir, manifest, checkpoint, historical_before)

    normalized_path = run_dir / "normalized_results.csv"
    for query_item in FROZEN_QUERIES:
        query_id = query_item["query_id"]
        state = checkpoint["queries"][query_id]
        if state["status"] == "COMPLETED":
            checkpoint["resume_events"].append({
                "timestamp": utc_now(), "query_id": query_id,
                "disposition": "SKIPPED_ALREADY_COMPLETED",
            })
            atomic_write_json(run_dir / "checkpoint.json", checkpoint)
            continue
        if state["status"] != "PENDING":
            raise RunnerBlocked(f"query cannot be attempted from state {state['status']}: {query_id}", "BLOCKED_INTEGRITY")
        try:
            validate_budget(checkpoint, query_id)
        except RunnerBlocked as exc:
            state["status"] = "BLOCKED"
            checkpoint["run_state"] = exc.run_state
            add_error(run_dir, query_id, exc.run_state, str(exc))
            refresh_outputs(run_dir, manifest, checkpoint, historical_before)
            return exc.exit_code

        started = utc_now()
        checkpoint["calls_reserved"] += 1
        checkpoint["calls_remaining"] -= 1
        state.update({
            "status": "ATTEMPT_RESERVED",
            "attempts_reserved": state["attempts_reserved"] + 1,
            "physical_call_number": checkpoint["calls_reserved"],
            "started_at": started,
        })
        atomic_write_json(run_dir / "checkpoint.json", checkpoint)
        refresh_outputs(run_dir, manifest, checkpoint, historical_before)

        decode_error: ChildOutputDecodeError | None = None
        try:
            checkpoint["calls_performed"] += 1
            process = backend(query_item)
            exit_code = int(process.returncode)
            try:
                stdout = sanitize_text(decode_child_stream(process.stdout, "stdout"))
                stderr = sanitize_text(decode_child_stream(process.stderr, "stderr"))
            except ChildOutputDecodeError as exc:
                decode_error = exc
                stdout = ""
                stderr = sanitize_text(str(exc))
        except Exception as exc:  # subprocess launch/timeout is a reserved technical attempt
            exit_code = 127
            stdout = ""
            stderr = sanitize_text(str(exc))

        finished = utc_now()
        if exit_code != 0 or decode_error is not None:
            authentication = decode_error is None and bool(AUTH_ERROR_PATTERN.search(stderr + "\n" + stdout))
            if decode_error is not None:
                error_class = "TVLY_OUTPUT_DECODE_ERROR"
            else:
                error_class = "AUTHENTICATION_OR_PERMISSION" if authentication else "TVLY_PROCESS_ERROR"
            state.update({
                "status": "BLOCKED" if authentication else "FAILED",
                "finished_at": finished, "result_count": 0,
                "exit_code": exit_code, "error_class": error_class,
            })
            checkpoint["run_state"] = "BLOCKED_AUTHENTICATION" if authentication else "FAILED_TECHNICAL"
            atomic_append_jsonl(
                run_dir / "query_ledger.jsonl",
                ledger_record(query_item, state, status=state["status"], finished_at=finished,
                              result_count=0, exit_code=exit_code, error_class=error_class, raw_row_ids=[]),
            )
            add_error(run_dir, query_id, error_class, stderr or stdout or "tvly process failed")
            refresh_outputs(run_dir, manifest, checkpoint, historical_before)
            return 3 if authentication else 4

        try:
            payload = parse_structured_output(stdout)
            raw_row, normalized = normalize_results(query_item, payload, finished)
        except RunnerBlocked as exc:
            state.update({
                "status": "FAILED", "finished_at": finished, "result_count": 0,
                "exit_code": exit_code, "error_class": exc.run_state,
            })
            checkpoint["run_state"] = exc.run_state
            atomic_append_jsonl(
                run_dir / "query_ledger.jsonl",
                ledger_record(query_item, state, status="FAILED", finished_at=finished,
                              result_count=0, exit_code=exit_code, error_class=exc.run_state, raw_row_ids=[]),
            )
            add_error(run_dir, query_id, exc.run_state, str(exc))
            refresh_outputs(run_dir, manifest, checkpoint, historical_before)
            return exc.exit_code

        raw_rows = read_jsonl(run_dir / "raw_results.jsonl")
        raw_rows.append(raw_row)
        atomic_write_jsonl(run_dir / "raw_results.jsonl", raw_rows)
        with normalized_path.open("r", encoding="utf-8", newline="") as handle:
            normalized_rows = list(csv.DictReader(handle))
        normalized_rows.extend(normalized)
        atomic_write_csv(normalized_path, NORMALIZED_FIELDS, normalized_rows)
        state.update({
            "status": "COMPLETED", "finished_at": finished,
            "result_count": len(normalized), "exit_code": exit_code,
            "error_class": None, "raw_row_ids": [raw_row["row_id"]],
        })
        atomic_append_jsonl(
            run_dir / "query_ledger.jsonl",
            ledger_record(query_item, state, status="COMPLETED", finished_at=finished,
                          result_count=len(normalized), exit_code=exit_code,
                          error_class=None, raw_row_ids=[raw_row["row_id"]]),
        )
        atomic_write_json(run_dir / "checkpoint.json", checkpoint)
        refresh_outputs(run_dir, manifest, checkpoint, historical_before)

    completed = sum(1 for state in checkpoint["queries"].values() if state["status"] == "COMPLETED")
    checkpoint["run_state"] = "EXECUTION_COMPLETED" if completed == len(FROZEN_QUERIES) else "EXECUTION_PARTIAL"
    historical_after = protected_fingerprints()
    if not protected_hashes_match(historical_before, historical_after):
        checkpoint["run_state"] = "BLOCKED_INTEGRITY"
        add_error(run_dir, None, "BLOCKED_INTEGRITY", "a protected historical run changed during execution")
        refresh_outputs(run_dir, manifest, checkpoint, historical_before, historical_after)
        return 2
    refresh_outputs(run_dir, manifest, checkpoint, historical_before, historical_after)
    validate_artifacts(run_dir, require_completed=checkpoint["run_state"] == "EXECUTION_COMPLETED")
    return 0 if checkpoint["run_state"] == "EXECUTION_COMPLETED" else 5


def validate_artifacts(run_dir: Path, *, require_completed: bool) -> dict[str, Any]:
    missing = [name for name in REQUIRED_ARTIFACTS if not (run_dir / name).is_file()]
    if missing:
        raise RunnerBlocked(f"missing required artifacts: {', '.join(missing)}", "BLOCKED_INTEGRITY")
    plan = read_json(run_dir / "query_plan.json")
    validate_frozen_plan(plan)
    manifest = read_json(run_dir / "manifest.json")
    checkpoint = read_json(run_dir / "checkpoint.json")
    ledger = read_jsonl(run_dir / "query_ledger.jsonl")
    raw = read_jsonl(run_dir / "raw_results.jsonl")
    errors = read_jsonl(run_dir / "errors.jsonl")
    if manifest.get("state") not in RUN_STATES or checkpoint.get("run_state") not in RUN_STATES:
        raise RunnerBlocked("invalid run state in JSON artifacts", "BLOCKED_INTEGRITY")
    if require_completed and checkpoint.get("run_state") != "EXECUTION_COMPLETED":
        raise RunnerBlocked("run is not completed", "BLOCKED_INTEGRITY")
    if any(row.get("status") not in QUERY_STATES for row in ledger):
        raise RunnerBlocked("invalid query ledger state", "BLOCKED_INTEGRITY")
    for row in ledger:
        body = {key: value for key, value in row.items() if key != "record_hash"}
        if row.get("record_hash") != sha256_text(canonical_json(body)):
            raise RunnerBlocked("query ledger record hash mismatch", "BLOCKED_INTEGRITY")
    for row in raw:
        if not {"row_id", "query_id", "rank", "retrieved_at", "raw_payload", "raw_payload_hash"}.issubset(row):
            raise RunnerBlocked("raw-results schema mismatch", "BLOCKED_INTEGRITY")
    with (run_dir / "normalized_results.csv").open("r", encoding="utf-8", newline="") as handle:
        normalized_reader = csv.DictReader(handle)
        if tuple(normalized_reader.fieldnames or ()) != NORMALIZED_FIELDS:
            raise RunnerBlocked("normalized CSV schema mismatch", "BLOCKED_INTEGRITY")
        normalized_count = sum(1 for _ in normalized_reader)
    with (run_dir / "domain_summary.csv").open("r", encoding="utf-8", newline="") as handle:
        domain_reader = csv.DictReader(handle)
        if tuple(domain_reader.fieldnames or ()) != DOMAIN_FIELDS:
            raise RunnerBlocked("domain CSV schema mismatch", "BLOCKED_INTEGRITY")
        domain_count = sum(1 for _ in domain_reader)
    report = (run_dir / "smoke_test_report.md").read_text(encoding="utf-8")
    if not report.startswith("# Technical smoke-test report\n"):
        raise RunnerBlocked("Markdown report schema mismatch", "BLOCKED_INTEGRITY")
    uppercase_report = report.upper()
    if any(term in uppercase_report for term in FORBIDDEN_REPORT_TERMS):
        raise RunnerBlocked("semantic adjudication leaked into technical report", "BLOCKED_INTEGRITY")
    findings = []
    for name in REQUIRED_ARTIFACTS:
        findings.extend(secret_findings_in_text((run_dir / name).read_text(encoding="utf-8")))
    if findings:
        raise RunnerBlocked("secret-like values detected in run artifacts", "BLOCKED_INTEGRITY")
    return {
        "json_files": 4,
        "jsonl_files": 3,
        "csv_files": 2,
        "markdown_files": 1,
        "ledger_rows": len(ledger), "raw_response_rows": len(raw),
        "normalized_rows": normalized_count, "domain_rows": domain_count,
        "error_rows": len(errors), "secret_findings": 0,
    }


def validate_integrity_manifest(run_dir: Path) -> None:
    integrity = read_json(run_dir / "integrity_manifest.json")
    if integrity.get("schema_version") != SCHEMA_VERSION:
        raise RunnerBlocked("integrity-manifest schema mismatch", "BLOCKED_INTEGRITY")
    if integrity.get("plan_hash") != frozen_plan_hash():
        raise RunnerBlocked("integrity-manifest plan hash mismatch", "BLOCKED_INTEGRITY")
    runner_entry = integrity.get("runner", {})
    if runner_entry.get("sha256") != sha256_file(Path(__file__).resolve()):
        raise RunnerBlocked("integrity-manifest runner hash mismatch", "BLOCKED_INTEGRITY")
    expected_names = set(REQUIRED_ARTIFACTS) - {"integrity_manifest.json"}
    entries = integrity.get("artifacts", {})
    if set(entries) != expected_names:
        raise RunnerBlocked("integrity-manifest artifact inventory mismatch", "BLOCKED_INTEGRITY")
    for name in sorted(expected_names):
        path = run_dir / name
        entry = entries[name]
        if entry.get("sha256") != sha256_file(path) or entry.get("size") != path.stat().st_size:
            raise RunnerBlocked(f"artifact hash mismatch on resume: {name}", "BLOCKED_INTEGRITY")


def dry_run_summary() -> dict[str, Any]:
    plan = frozen_plan()
    validate_frozen_plan(plan)
    sample_checkpoint = initial_checkpoint("DRY_RUN_ONLY", sha256_file(Path(__file__).resolve()))
    for item in FROZEN_QUERIES:
        validate_budget(sample_checkpoint, item["query_id"])
        sample_checkpoint["calls_reserved"] += 1
        sample_checkpoint["queries"][item["query_id"]]["attempts_reserved"] = 1
    if sample_checkpoint["calls_reserved"] != 4:
        raise RunnerBlocked("dry-run budget simulation failed", "BLOCKED_CONFIGURATION")
    if OUTPUT_ROOT.name != "tavily_smoke_test_01" or any(path.parent != OUTPUT_ROOT for path in HISTORICAL_BLOCKED_RUNS):
        raise RunnerBlocked("output routing contract mismatch", "BLOCKED_CONFIGURATION")
    if set(REQUIRED_ARTIFACTS) != {
        "query_plan.json", "manifest.json", "checkpoint.json", "query_ledger.jsonl",
        "raw_results.jsonl", "normalized_results.csv", "domain_summary.csv",
        "errors.jsonl", "smoke_test_report.md", "integrity_manifest.json",
    }:
        raise RunnerBlocked("artifact schema inventory mismatch", "BLOCKED_CONFIGURATION")
    return {
        "verdict": "DRY_RUN_OFFLINE_PASS",
        "network_calls": 0, "authentication_checks": 0,
        "environment_reads": 0, "real_run_created": False,
        "plan_hash": frozen_plan_hash(),
        "configuration": dict(FROZEN_CONFIG),
        "child_process_text_contract": dict(CHILD_TEXT_CONTRACT),
        "planned_invocations": [tvly_command(item) for item in FROZEN_QUERIES],
        "required_artifacts": list(REQUIRED_ARTIFACTS),
        "query_states": sorted(QUERY_STATES), "run_states": sorted(RUN_STATES),
    }


def powershell_block() -> str:
    return r"""& {
    $projectRoot = 'C:\Proyectos\IPTV-Playlist-Builder-Premium'
    Set-Location -LiteralPath $projectRoot

    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'

    $tvlyCommand = Get-Command tvly -ErrorAction SilentlyContinue
    if (-not $tvlyCommand) {
        Write-Error 'Tavily CLI was not found. No search was executed.'
        exit 3
    }

    $statusErrorFile = [System.IO.Path]::GetTempFileName()

    try {
        $authenticationJson = & tvly --status --json 2> $statusErrorFile
        $authenticationExitCode = $LASTEXITCODE
        $authenticationText = ($authenticationJson | Out-String).Trim()

        if ($authenticationExitCode -ne 0) {
            Write-Error "Tavily authentication was not confirmed. Exit code: $authenticationExitCode. No search was executed."
            exit 3
        }

        if ([string]::IsNullOrWhiteSpace($authenticationText)) {
            Write-Error 'Tavily returned an empty authentication status. No search was executed.'
            exit 3
        }

        try {
            $null = $authenticationText | ConvertFrom-Json -ErrorAction Stop
        }
        catch {
            Write-Error 'Tavily returned an invalid JSON authentication status. No search was executed.'
            exit 3
        }
    }
    finally {
        Remove-Item -LiteralPath $statusErrorFile -Force -ErrorAction SilentlyContinue
    }

    $runnerOutput = & python -B .\scripts\run_brand_first_market_universe_1b_tavily_smoke_test_01.py --execute --approval-token 'BRAND-FIRST-1B-TAVILY-SMOKE-TEST-01' --execution-origin powershell 2>&1
    $runnerExitCode = $LASTEXITCODE
    $runPathLine = $runnerOutput | Where-Object { $_ -like 'RUN_DIR=*' } | Select-Object -Last 1
    $runnerOutput |
        Where-Object { $_ -notlike 'RUN_DIR=*' } |
        ForEach-Object { Write-Output $_ }

    if ($runPathLine) {
        Write-Output $runPathLine
    }
    else {
        Write-Error 'The runner did not report a run directory.'
    }
    exit $runnerExitCode
}"""


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    modes = result.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--execute", action="store_true")
    result.add_argument("--resume-run", type=Path)
    result.add_argument("--approval-token")
    result.add_argument("--execution-origin", choices=("powershell",))
    result.add_argument("--print-powershell", action="store_true", help=argparse.SUPPRESS)
    return result


def validate_args(args: argparse.Namespace) -> None:
    if args.dry_run:
        if args.approval_token or args.execution_origin or args.resume_run:
            raise RunnerBlocked("dry-run cannot carry execution authorization", "BLOCKED_CONFIGURATION")
        return
    if args.approval_token != APPROVAL_TOKEN:
        raise RunnerBlocked("execute/resume requires the exact explicit approval token", "BLOCKED_CONFIGURATION")
    if args.execution_origin != "powershell":
        raise RunnerBlocked("execute/resume requires explicit PowerShell origin", "BLOCKED_CONFIGURATION")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    run_dir: Path | None = None
    try:
        validate_args(args)
        if args.dry_run:
            print(json.dumps(dry_run_summary(), ensure_ascii=False, indent=2))
            if args.print_powershell:
                print(powershell_block())
            return 0

        # No authentication check and no environment access occur here. The
        # calling PowerShell session owns the prior `tvly --status` gate.
        tvly_version = local_tvly_version()
        git = local_git_snapshot()
        if git != {
            "head": "6a8e129afc1a16c11e36d991f5bd708d9f9f7030",
            "origin_main_local": "6a8e129afc1a16c11e36d991f5bd708d9f9f7030",
            "divergence": "0\t0",
            "branch": "main",
        }:
            raise RunnerBlocked("Git identity no longer matches the prepared execution contract", "BLOCKED_INTEGRITY")
        historical_before = protected_fingerprints()
        if not all(value.get("exists") for value in historical_before.values()):
            raise RunnerBlocked("one or more protected historical runs are missing", "BLOCKED_INTEGRITY")

        if args.resume_run is None:
            ensure_no_completed_sibling(OUTPUT_ROOT)
            run_dir = OUTPUT_ROOT / f"run_{run_stamp()}"
            manifest, checkpoint = initialize_run(
                run_dir, git=git, tvly_version=tvly_version,
                historical_before=historical_before, originated_from_powershell=True,
            )
        else:
            run_dir = args.resume_run.resolve()
            manifest, checkpoint = validate_run_compatibility(run_dir)
        return process_run(run_dir, manifest, checkpoint, historical_before)
    except RunnerBlocked as exc:
        print(f"{exc.run_state}: {sanitize_text(str(exc))}", file=sys.stderr)
        return exc.exit_code
    finally:
        if run_dir is not None:
            print(f"RUN_DIR={run_dir}")


if __name__ == "__main__":
    raise SystemExit(main())
