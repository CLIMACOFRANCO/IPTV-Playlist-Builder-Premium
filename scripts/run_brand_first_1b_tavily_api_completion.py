#!/usr/bin/env python3
"""Prepare and, only with explicit PowerShell approval, complete Q3/Q4 via Tavily SDK.

Dry-run is strictly local: it does not read credentials, create run directories,
instantiate TavilyClient, or make network calls. Real execution is intentionally
separate from the historical CLI run and has no resume mode.
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TASK = "API-COMPLETION-RUNNER-PREPARATION-01"
SCHEMA_VERSION = "brand_first_market_universe_1b_api_completion.v1"
APPROVAL_TOKEN = "BRAND-FIRST-1B-API-COMPLETION-01"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / (
    "research/output/best_iptv_2026/brand_first_market_universe_1b/"
    "tavily_smoke_test_01_api_completion"
)
PARTIAL_RUN = PROJECT_ROOT / (
    "research/output/best_iptv_2026/brand_first_market_universe_1b/"
    "tavily_smoke_test_01/run_20260718_014913"
)
EXPECTED_PARTIAL_RUN_SHA256 = "734cd73bd74d8c5c344e6b9446c7d3d00bf0b21f3062e54dc63e0cd108ced1d3"
AUTHORITATIVE_RUN_ID = "run_20260718_031814"
MAX_CALLS = 2
SEARCH_CONFIG: dict[str, Any] = {
    "search_depth": "basic",
    "max_results": 5,
    "auto_parameters": False,
    "include_answer": False,
    "include_images": False,
    "include_raw_content": False,
}
AUTHORIZED_QUERIES: tuple[dict[str, Any], ...] = (
    {
        "sequence": 3,
        "query_id": "smarters_q3_official_player_application_api_recovery",
        "authorization": "ONE_TECHNICAL_REPEAT_AFTER_CLI_ENCODING_LOSS",
        "query": '"IPTV Smarters Pro" official website player application',
    },
    {
        "sequence": 4,
        "query_id": "smarters_q4_subscription_provider_api_completion",
        "authorization": "FIRST_EXECUTION",
        "query": '"IPTV Smarters Pro" IPTV subscription provider',
    },
)
Q1_Q2_IDS = frozenset({
    "digitalizard_q1_official_company",
    "digitalizard_q2_reviews_reseller_operator",
})
REQUIRED_ARTIFACTS = (
    "query_plan.json",
    "manifest.json",
    "checkpoint.json",
    "query_ledger.jsonl",
    "raw_results.jsonl",
    "normalized_results.csv",
    "errors.jsonl",
    "completion_report.md",
    "integrity_manifest.json",
)
CSV_FIELDS = (
    "query_sequence",
    "query_id",
    "result_rank",
    "result_id",
    "title",
    "url",
    "canonical_url",
    "registrable_domain",
    "content",
    "score",
    "retrieved_at",
    "raw_record_id",
)
SECRET_PATTERNS = (
    re.compile(r"tvly-[A-Za-z0-9_-]{12,}", re.IGNORECASE),
    re.compile(r"(?i)authorization\s*:\s*bearer\s+\S+"),
    re.compile(r"(?i)(api[ _-]?key|token)\s*[:=]\s*[^\s,;]+"),
)


class RunnerBlocked(RuntimeError):
    def __init__(
        self, message: str, run_state: str = "BLOCKED_CONFIGURATION",
        run_dir: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.run_state = run_state
        self.run_dir = run_dir


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


def secret_finding_count(value: str) -> int:
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
    rows: list[dict[str, Any]] = []
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


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def directory_fingerprint(path: Path) -> dict[str, Any]:
    if not path.is_dir():
        return {"exists": False, "file_count": 0, "aggregate_sha256": None}
    files: list[dict[str, Any]] = []
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        files.append({
            "path": item.relative_to(path).as_posix(),
            "size": item.stat().st_size,
            "sha256": sha256_file(item),
        })
    aggregate = sha256_bytes(
        "\n".join(f"{item['path']}|{item['sha256'].upper()}" for item in files).encode("utf-8")
    )
    return {"exists": True, "file_count": len(files), "aggregate_sha256": aggregate, "files": files}


def canonicalize_url(value: str) -> str:
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return value.strip()
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return value.strip()
    host = parsed.hostname.lower()
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    return urlunsplit((parsed.scheme.lower(), host + port, path, query, ""))


def registrable_domain(value: str) -> str:
    try:
        host = (urlsplit(value).hostname or "").lower()
    except ValueError:
        return ""
    parts = [part for part in host.split(".") if part]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def query_plan() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "task": TASK,
        "authorized_q3_technical_repeat": True,
        "q1_q2_not_repeated": True,
        "max_calls": MAX_CALLS,
        "retry_limit": 0,
        "search_configuration": dict(SEARCH_CONFIG),
        "queries": [dict(item) for item in AUTHORIZED_QUERIES],
    }


def validate_frozen_plan(plan: dict[str, Any]) -> None:
    if plan != query_plan():
        raise RunnerBlocked("query plan differs from the frozen API completion contract")
    ids = {item["query_id"] for item in plan["queries"]}
    if ids & Q1_Q2_IDS or len(ids) != 2:
        raise RunnerBlocked("only the authorized Q3 and Q4 IDs may be present")


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


def initialize_run(run_dir: Path, partial_before: dict[str, Any], created_at: str) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = query_plan()
    validate_frozen_plan(plan)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "task": TASK,
        "created_at": created_at,
        "run_state": "PREPARED",
        "backend": "tavily-python-sdk",
        "authorized_q3_technical_repeat": True,
        "q1_q2_not_repeated": True,
        "budget": {"max_calls": MAX_CALLS, "calls_used": 0, "retry_limit": 0},
        "results": {item["query_id"]: 0 for item in AUTHORIZED_QUERIES},
        "search_configuration": dict(SEARCH_CONFIG),
        "partial_run_link": str(PARTIAL_RUN.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "partial_run_initial_sha256": partial_before["aggregate_sha256"],
        "absence_of_secrets": True,
    }
    checkpoint = {
        "schema_version": SCHEMA_VERSION,
        "run_state": "PREPARED",
        "calls_used": 0,
        "max_calls": MAX_CALLS,
        "queries": {
            item["query_id"]: {"state": "PENDING", "attempts": 0, "result_count": 0}
            for item in AUTHORIZED_QUERIES
        },
        "updated_at": created_at,
    }
    atomic_write_json(run_dir / "query_plan.json", plan)
    atomic_write_json(run_dir / "manifest.json", manifest)
    atomic_write_json(run_dir / "checkpoint.json", checkpoint)
    atomic_write_text(run_dir / "query_ledger.jsonl", "")
    atomic_write_text(run_dir / "raw_results.jsonl", "")
    write_csv(run_dir / "normalized_results.csv", [])
    atomic_write_text(run_dir / "errors.jsonl", "")
    write_report(run_dir, manifest, checkpoint)
    refresh_integrity(run_dir, partial_before, partial_before)
    return manifest, checkpoint


def normalize_response(
    query_item: dict[str, Any], response: Any, retrieved_at: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(response, dict):
        raise RunnerBlocked("Tavily SDK returned a non-object response", "FAILED_TECHNICAL")
    safe_response = sanitize_value(response)
    results = safe_response.get("results", [])
    if not isinstance(results, list):
        raise RunnerBlocked("Tavily SDK response has a non-list results field", "FAILED_TECHNICAL")
    if len(results) > SEARCH_CONFIG["max_results"]:
        raise RunnerBlocked("Tavily SDK response exceeded max_results", "FAILED_TECHNICAL")
    raw_payload_sha256 = sha256_json(safe_response)
    raw_record_id = "raw_" + sha256_json({
        "query_id": query_item["query_id"],
        "payload_sha256": raw_payload_sha256,
    })[:24]
    raw_record = {
        "schema_version": SCHEMA_VERSION,
        "raw_record_id": raw_record_id,
        "query_sequence": query_item["sequence"],
        "query_id": query_item["query_id"],
        "retrieved_at": retrieved_at,
        "result_count": len(results),
        "raw_payload_sha256": raw_payload_sha256,
        "raw_payload": safe_response,
    }
    normalized: list[dict[str, Any]] = []
    for rank, item in enumerate(results, start=1):
        if not isinstance(item, dict):
            raise RunnerBlocked("Tavily SDK returned a non-object result", "FAILED_TECHNICAL")
        title = sanitize_text(str(item.get("title", "")))
        url = sanitize_text(str(item.get("url", "")))
        canonical_url = canonicalize_url(url)
        content = sanitize_text(str(item.get("content", "")))
        stable = {
            "query_id": query_item["query_id"],
            "rank": rank,
            "canonical_url": canonical_url,
            "title": title,
        }
        normalized.append({
            "query_sequence": query_item["sequence"],
            "query_id": query_item["query_id"],
            "result_rank": rank,
            "result_id": "norm_" + sha256_json(stable)[:24],
            "title": title,
            "url": url,
            "canonical_url": canonical_url,
            "registrable_domain": registrable_domain(canonical_url),
            "content": content,
            "score": item.get("score", ""),
            "retrieved_at": retrieved_at,
            "raw_record_id": raw_record_id,
        })
    return raw_record, normalized


def write_report(run_dir: Path, manifest: dict[str, Any], checkpoint: dict[str, Any]) -> None:
    lines = [
        "# Tavily API completion report",
        "",
        f"- State: `{checkpoint['run_state']}`",
        f"- Calls used: `{checkpoint['calls_used']}` / `{MAX_CALLS}`",
        "- Q1/Q2 repeated: `false`",
        "- Q3 technical repeat authorized: `true`",
        "- Retries: `0`",
        "- Original partial run modified: `false`",
        "",
        "## Query state",
        "",
    ]
    for item in AUTHORIZED_QUERIES:
        state = checkpoint["queries"][item["query_id"]]
        lines.append(
            f"- `{item['query_id']}`: `{state['state']}`, results `{state['result_count']}`"
        )
    lines.extend([
        "",
        "This mechanical completion report makes no claim about officiality, legality, or identity.",
        "",
    ])
    atomic_write_text(run_dir / "completion_report.md", "\n".join(lines))


def artifact_secret_findings(run_dir: Path) -> int:
    total = 0
    for name in REQUIRED_ARTIFACTS:
        if name == "integrity_manifest.json":
            continue
        path = run_dir / name
        if path.exists():
            total += secret_finding_count(path.read_text(encoding="utf-8"))
    return total


def refresh_integrity(
    run_dir: Path, partial_before: dict[str, Any], partial_after: dict[str, Any]
) -> dict[str, Any]:
    artifacts: dict[str, Any] = {}
    for name in REQUIRED_ARTIFACTS:
        if name == "integrity_manifest.json":
            continue
        path = run_dir / name
        artifacts[name] = {"size": path.stat().st_size, "sha256": sha256_file(path)}
    integrity = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "artifacts": artifacts,
        "partial_run_initial_sha256": partial_before["aggregate_sha256"],
        "partial_run_final_sha256": partial_after["aggregate_sha256"],
        "partial_run_unchanged": (
            partial_before["aggregate_sha256"] == partial_after["aggregate_sha256"]
            and partial_before["file_count"] == partial_after["file_count"]
        ),
        "secret_findings": artifact_secret_findings(run_dir),
    }
    atomic_write_json(run_dir / "integrity_manifest.json", integrity)
    return integrity


def checkpoint_write(run_dir: Path, checkpoint: dict[str, Any]) -> None:
    checkpoint["updated_at"] = now_utc()
    atomic_write_json(run_dir / "checkpoint.json", checkpoint)


def persist_state(
    run_dir: Path,
    manifest: dict[str, Any],
    checkpoint: dict[str, Any],
    partial_before: dict[str, Any],
) -> dict[str, Any]:
    manifest["run_state"] = checkpoint["run_state"]
    manifest["budget"]["calls_used"] = checkpoint["calls_used"]
    atomic_write_json(run_dir / "manifest.json", manifest)
    write_report(run_dir, manifest, checkpoint)
    partial_after = directory_fingerprint(PARTIAL_RUN)
    return refresh_integrity(run_dir, partial_before, partial_after)


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


def completed_compatible_run(output_root: Path = OUTPUT_ROOT) -> Path | None:
    """Return the first complete compatible run, preferring the declared authority."""
    if not output_root.is_dir():
        return None
    candidates = sorted(
        (item for item in output_root.iterdir() if item.is_dir() and item.name.startswith("run_")),
        key=lambda item: (item.name != AUTHORITATIVE_RUN_ID, item.name),
    )
    for candidate in candidates:
        try:
            validation = validate_artifacts(candidate, require_completed=True)
            if (
                read_json(candidate / "query_plan.json") == query_plan()
                and validation["checkpoint"]["calls_used"] == MAX_CALLS
                and validation["manifest"]["q1_q2_not_repeated"] is True
            ):
                return candidate
        except (OSError, ValueError, KeyError, RunnerBlocked):
            continue
    return None


def execute_completion(
    *,
    output_root: Path = OUTPUT_ROOT,
    client_factory: Callable[[str], Any] = sdk_client_factory,
    api_key_reader: Callable[[str], str | None] = inherited_api_key_reader,
    stamp: str | None = None,
) -> tuple[int, Path | None]:
    completed = completed_compatible_run(output_root)
    if completed is not None:
        raise RunnerBlocked(
            f"compatible completed API run already exists: {completed.name}; do not execute again",
            "BLOCKED_ALREADY_COMPLETED",
            completed,
        )
    partial_before = directory_fingerprint(PARTIAL_RUN)
    if not partial_before["exists"]:
        raise RunnerBlocked("the protected partial run is missing", "BLOCKED_INTEGRITY")
    if partial_before["aggregate_sha256"] != EXPECTED_PARTIAL_RUN_SHA256:
        raise RunnerBlocked("the protected partial run hash differs from the approved baseline", "BLOCKED_INTEGRITY")

    api_key = api_key_reader("TAVILY_API_KEY")
    if not api_key or not api_key.strip():
        raise RunnerBlocked("TAVILY_API_KEY is unavailable; no API call or run was created")
    client = client_factory(api_key)
    api_key = ""

    run_dir = create_run_dir(output_root, stamp=stamp)
    manifest, checkpoint = initialize_run(run_dir, partial_before, now_utc())
    normalized_rows: list[dict[str, Any]] = []
    checkpoint["run_state"] = "EXECUTION_IN_PROGRESS"

    for query_item in AUTHORIZED_QUERIES:
        query_id = query_item["query_id"]
        if checkpoint["calls_used"] >= MAX_CALLS:
            raise RunnerBlocked("the absolute two-call budget is exhausted", "BLOCKED_BUDGET")
        if checkpoint["queries"][query_id]["attempts"] != 0:
            raise RunnerBlocked("retry is forbidden", "BLOCKED_BUDGET")

        checkpoint["calls_used"] += 1
        checkpoint["queries"][query_id]["state"] = "ATTEMPT_RESERVED"
        checkpoint["queries"][query_id]["attempts"] = 1
        checkpoint_write(run_dir, checkpoint)
        append_jsonl(run_dir / "query_ledger.jsonl", {
            "at": now_utc(),
            "event": "ATTEMPT_RESERVED",
            "query_id": query_id,
            "call_number": checkpoint["calls_used"],
        })
        persist_state(run_dir, manifest, checkpoint, partial_before)

        try:
            response = client.search(query=query_item["query"], **SEARCH_CONFIG)
            retrieved_at = now_utc()
            raw_record, new_rows = normalize_response(query_item, response, retrieved_at)
        except Exception as exc:  # SDK errors are persisted only after sanitization.
            safe_error = sanitize_text(f"{type(exc).__name__}: {exc}")
            checkpoint["queries"][query_id]["state"] = "FAILED"
            checkpoint["run_state"] = "FAILED_TECHNICAL"
            checkpoint_write(run_dir, checkpoint)
            append_jsonl(run_dir / "errors.jsonl", {
                "at": now_utc(),
                "query_id": query_id,
                "error_class": type(exc).__name__,
                "message": safe_error,
                "retry_performed": False,
            })
            append_jsonl(run_dir / "query_ledger.jsonl", {
                "at": now_utc(),
                "event": "FAILED",
                "query_id": query_id,
                "retry_performed": False,
            })
            persist_state(run_dir, manifest, checkpoint, partial_before)
            return 1, run_dir

        append_jsonl(run_dir / "raw_results.jsonl", raw_record)
        normalized_rows.extend(new_rows)
        write_csv(run_dir / "normalized_results.csv", normalized_rows)
        checkpoint["queries"][query_id]["state"] = "COMPLETED"
        checkpoint["queries"][query_id]["result_count"] = len(new_rows)
        manifest["results"][query_id] = len(new_rows)
        checkpoint_write(run_dir, checkpoint)
        append_jsonl(run_dir / "query_ledger.jsonl", {
            "at": now_utc(),
            "event": "COMPLETED",
            "query_id": query_id,
            "result_count": len(new_rows),
        })
        persist_state(run_dir, manifest, checkpoint, partial_before)

    checkpoint["run_state"] = "EXECUTION_COMPLETED"
    checkpoint_write(run_dir, checkpoint)
    integrity = persist_state(run_dir, manifest, checkpoint, partial_before)
    validate_artifacts(run_dir, require_completed=True)
    if not integrity["partial_run_unchanged"] or integrity["secret_findings"]:
        raise RunnerBlocked("final integrity validation failed", "BLOCKED_INTEGRITY")
    return 0, run_dir


def validate_artifacts(run_dir: Path, *, require_completed: bool) -> dict[str, Any]:
    missing = [name for name in REQUIRED_ARTIFACTS if not (run_dir / name).is_file()]
    if missing:
        raise RunnerBlocked(f"missing artifacts: {', '.join(missing)}", "BLOCKED_INTEGRITY")
    plan = read_json(run_dir / "query_plan.json")
    validate_frozen_plan(plan)
    manifest = read_json(run_dir / "manifest.json")
    checkpoint = read_json(run_dir / "checkpoint.json")
    ledger = read_jsonl(run_dir / "query_ledger.jsonl")
    raw_rows = read_jsonl(run_dir / "raw_results.jsonl")
    error_rows = read_jsonl(run_dir / "errors.jsonl")
    integrity = read_json(run_dir / "integrity_manifest.json")
    with (run_dir / "normalized_results.csv").open(encoding="utf-8", newline="") as handle:
        normalized = list(csv.DictReader(handle))
        if tuple(handle.seek(0) or next(csv.reader(handle))) != CSV_FIELDS:
            raise RunnerBlocked("normalized CSV header mismatch", "BLOCKED_INTEGRITY")
    report = (run_dir / "completion_report.md").read_text(encoding="utf-8")
    if not report.startswith("# Tavily API completion report\n"):
        raise RunnerBlocked("completion report schema mismatch", "BLOCKED_INTEGRITY")
    if checkpoint["calls_used"] > MAX_CALLS:
        raise RunnerBlocked("checkpoint exceeds call budget", "BLOCKED_INTEGRITY")
    if set(checkpoint["queries"]) != {item["query_id"] for item in AUTHORIZED_QUERIES}:
        raise RunnerBlocked("checkpoint contains unauthorized queries", "BLOCKED_INTEGRITY")
    if require_completed and checkpoint["run_state"] != "EXECUTION_COMPLETED":
        raise RunnerBlocked("run is not completed", "BLOCKED_INTEGRITY")
    for raw in raw_rows:
        if raw["raw_payload_sha256"] != sha256_json(raw["raw_payload"]):
            raise RunnerBlocked("raw payload hash mismatch", "BLOCKED_INTEGRITY")
    if artifact_secret_findings(run_dir) or integrity["secret_findings"]:
        raise RunnerBlocked("secret-like material found in artifacts", "BLOCKED_INTEGRITY")
    for name, metadata in integrity["artifacts"].items():
        if sha256_file(run_dir / name) != metadata["sha256"]:
            raise RunnerBlocked(f"integrity hash mismatch: {name}", "BLOCKED_INTEGRITY")
    return {
        "manifest": manifest,
        "checkpoint": checkpoint,
        "ledger_rows": len(ledger),
        "raw_rows": len(raw_rows),
        "normalized_rows": len(normalized),
        "error_rows": len(error_rows),
        "integrity": integrity,
    }


def dry_run_summary() -> dict[str, Any]:
    return {
        "task": TASK,
        "schema_version": SCHEMA_VERSION,
        "sdk_available_locally": importlib.util.find_spec("tavily") is not None,
        "authorized_query_ids": [item["query_id"] for item in AUTHORIZED_QUERIES],
        "q1_q2_not_repeated": True,
        "max_calls": MAX_CALLS,
        "retry_limit": 0,
        "search_configuration": dict(SEARCH_CONFIG),
        "credential_reads": 0,
        "client_instances": 0,
        "network_calls": 0,
        "run_created": False,
    }


def powershell_block() -> str:
    return r"""& {
    $projectRoot = 'C:\Proyectos\IPTV-Playlist-Builder-Premium'
    Set-Location -LiteralPath $projectRoot

    if (-not (Test-Path -LiteralPath Env:\TAVILY_API_KEY) -or
        [string]::IsNullOrWhiteSpace($env:TAVILY_API_KEY)) {
        Write-Error 'TAVILY_API_KEY is unavailable in this PowerShell process. No API call was made.'
        $runnerExitCode = 3
    }
    else {
        $env:PYTHONUTF8 = '1'
        $env:PYTHONIOENCODING = 'utf-8'

        $runnerOutput = & python -B .\scripts\run_brand_first_1b_tavily_api_completion.py --execute --approval-token 'BRAND-FIRST-1B-API-COMPLETION-01' --execution-origin powershell 2>&1
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
    Write-Output 'DO_NOT_RUN_AGAIN_IF_RUN_DIR_WAS_PRINTED'
}"""


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    modes = result.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--execute", action="store_true")
    result.add_argument("--approval-token")
    result.add_argument("--execution-origin", choices=("powershell",))
    result.add_argument("--print-powershell", action="store_true", help=argparse.SUPPRESS)
    return result


def validate_args(args: argparse.Namespace) -> None:
    if args.dry_run:
        if args.approval_token or args.execution_origin:
            raise RunnerBlocked("dry-run cannot carry execution authorization")
        return
    if args.approval_token != APPROVAL_TOKEN:
        raise RunnerBlocked("execute requires the exact API completion approval token")
    if args.execution_origin != "powershell":
        raise RunnerBlocked("execute requires explicit PowerShell origin")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        validate_args(args)
        if args.dry_run:
            print(json.dumps(dry_run_summary(), ensure_ascii=False, indent=2))
            if args.print_powershell:
                print(powershell_block())
            return 0
        exit_code, run_dir = execute_completion()
        if run_dir is not None:
            print(f"RUN_DIR={run_dir}")
        return exit_code
    except RunnerBlocked as exc:
        print(f"{exc.run_state}: {sanitize_text(str(exc))}", file=sys.stderr)
        if exc.run_dir is not None:
            print(f"RUN_DIR={exc.run_dir}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
