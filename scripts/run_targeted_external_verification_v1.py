#!/usr/bin/env python3
"""Targeted external verification V1 runner.

Dry-run and preflight are deliberately offline.  External integrations are
loaded only inside execute-only functions after every local safety gate passes.
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
import html
from html.parser import HTMLParser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

VERDICT_READY = "TARGETED_EXTERNAL_VERIFICATION_V1_READY_FOR_AUTHORIZATION"
VERDICT_FIXES = "TARGETED_EXTERNAL_VERIFICATION_V1_REQUIRES_FIXES"
VERDICT_INTEGRITY = "TARGETED_EXTERNAL_VERIFICATION_V1_BLOCKED_BY_INTEGRITY"
VERDICT_SCOPE = "TARGETED_EXTERNAL_VERIFICATION_V1_BLOCKED_BY_SCOPE"
ALLOWED_DOMAINS = ("vocotviptv.com", "vocotvusa.net", "vocotv.ai", "vocoiptv.com")
MAX_TAVILY_QUERIES = 12
MAX_EXTERNAL_ACCESSES = 40
PROTOCOL_ACCESS_CEILING = 24
MAX_RESULTS = 8
EXPECTED_HASHES = {
    "run_20260715_023727": "286501151DB0DCFAA6383C0AB718B1F26250E7FA91D231C962EAB0B8B67A857C",
    "final_offline_audit_run_20260715_023727": "E67364695B94A18278823963F46C37A05661D551E78E4CF38B3DFB47EE394F8E",
}
OUTPUT_BASE = Path("research/output/best_iptv_2026/domain_family_discovery_voco_micro_pilot")
HISTORICAL_QUERY_PLAN = OUTPUT_BASE / "run_20260715_023727/query_plan.json"
FORBIDDEN_QUERY_PATTERNS = ("best iptv", "top iptv providers", "official voco tv", "iptv review", "best iptv 2026")
VALID_ROLES = {"PROBABLE_BRAND_OPERATOR", "POSSIBLE_RELATED_DOMAIN", "RESELLER", "UNRESOLVED"}
ZERO_IDENTITY_SIGNALS = {"INFRASTRUCTURE", "CLOUDFLARE", "HOSTING", "ASN", "REGISTRAR", "CDN", "PAYMENT_PROCESSOR", "RESELLER", "AFFILIATE", "REVIEW", "DIRECTORY", "CONTROL", "OFFICIAL_WORD", "LOGO", "BRAND_MATCH"}
AUTHORIZED_REPAIR_ACCESS_IDS = (
    "access_vocotviptv_com_root", "access_vocotviptv_com_legal",
    "access_vocotviptv_com_privacy", "access_vocotviptv_com_contact",
)
FINAL_TWO_URLS = (
    "https://www.vocotviptv.com/terms/",
    "https://www.vocotviptv.com/privacy-policy/",
)

CSV_SCHEMAS = {
    "normalized_external_evidence.csv": ["evidence_id", "domain", "source_url", "category", "attribution_strength", "independence_group", "supporting_row_ids"],
    "evidence_independence_groups.csv": ["independence_group", "category", "member_evidence_ids", "counted_once_for_identity"],
    "domain_redirects.csv": ["source_url", "target_url", "status_code", "in_scope", "supporting_row_ids"],
    "domain_legal_identity_evidence.csv": ["evidence_id", "domain", "entity", "source_url", "supporting_row_ids"],
    "domain_contact_evidence.csv": ["evidence_id", "domain", "contact_type", "contact_domain", "source_url", "supporting_row_ids"],
    "domain_application_evidence.csv": ["evidence_id", "domain", "publisher", "application", "source_url", "supporting_row_ids"],
    "domain_payment_evidence.csv": ["evidence_id", "domain", "billing_entity", "source_url", "supporting_row_ids"],
    "domain_social_link_evidence.csv": ["evidence_id", "domain", "platform", "profile_url", "first_party_linked", "supporting_row_ids"],
    "domain_dns_certificate_evidence.csv": ["evidence_id", "domain", "signal_type", "value", "identity_value", "supporting_row_ids"],
    "domain_business_registry_evidence.csv": ["evidence_id", "domain", "registry", "entity", "source_url", "supporting_row_ids"],
    "domain_crosslink_matrix.csv": ["source_domain", "target_domain", "relation", "attributable", "supporting_row_ids"],
    "attribution_relationships_external.csv": ["relationship_id", "source_domain", "target_domain", "relation_type", "identity_value", "supporting_row_ids"],
    "attribution_gate_trace_external.csv": ["domain", "strong_count", "category_count", "independence_group_count", "first_party", "conflicts", "result", "supporting_row_ids"],
    "domain_role_classification_external.csv": ["domain", "final_role", "confidence", "decision_reason", "supporting_row_ids", "official_domain_confirmed"],
    "domain_identity_gap_matrix_external.csv": ["domain", "current_role", "missing_evidence", "supporting_row_ids"],
}

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def write_json_atomic(path: Path, value: Any) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        handle.flush(); os.fsync(handle.fileno())
    os.replace(tmp, path)

def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")
        handle.flush(); os.fsync(handle.fileno())

def write_empty_csv(path: Path, fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.DictWriter(handle, fieldnames=fields).writeheader()

def directory_fingerprint(path: Path) -> dict[str, Any]:
    files = []
    for item in sorted(path.iterdir()):
        if item.is_file():
            files.append({"name": item.name, "size": item.stat().st_size, "sha256": hashlib.sha256(item.read_bytes()).hexdigest().upper()})
    aggregate = hashlib.sha256("\n".join(f"{x['name']}:{x['sha256'].lower()}" for x in files).encode()).hexdigest().upper()
    return {"directory": str(path), "file_count": len(files), "aggregate_sha256": aggregate, "files": files}

def recursive_directory_fingerprint(path: Path) -> dict[str, Any]:
    files = []
    for item in sorted(x for x in path.rglob("*") if x.is_file()):
        files.append({"name": item.relative_to(path).as_posix(), "size": item.stat().st_size,
                      "sha256": hashlib.sha256(item.read_bytes()).hexdigest().upper()})
    aggregate = hashlib.sha256("\n".join(f"{x['name']}:{x['sha256'].lower()}" for x in files).encode()).hexdigest().upper()
    return {"directory": str(path), "file_count": len(files), "total_bytes": sum(x["size"] for x in files),
            "aggregate_sha256": aggregate, "files": files}

def verify_integrity() -> dict[str, Any]:
    results = {}
    for name, expected in EXPECTED_HASHES.items():
        path = OUTPUT_BASE / name
        actual = directory_fingerprint(path) if path.is_dir() else {"directory": str(path), "aggregate_sha256": None, "file_count": 0, "files": []}
        actual["expected_aggregate_sha256"] = expected
        actual["matches"] = actual["aggregate_sha256"] == expected
        results[name] = actual
    return {"checked_at": now_iso(), "all_match": all(x["matches"] for x in results.values()), "directories": results}

def normalize_query(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()

def historical_queries() -> set[str]:
    data = json.loads(HISTORICAL_QUERY_PLAN.read_text(encoding="utf-8"))
    return {normalize_query(x.get("exact_query") or x.get("query") or x.get("tavily_parameters_prepared", {}).get("query", "")) for x in data.get("queries", [])}

def build_query_plan(domains: list[str], search_depth: str, timeout: float) -> list[dict[str, Any]]:
    templates = (
        ("legal_identity", 'site:{d} (terms OR privacy OR legal OR "operated by" OR "owned by" OR company OR copyright)'),
        ("contact_application", 'site:{d} (contact OR support OR email OR app OR publisher OR developer OR account)'),
        ("attributable_relationships", '"{d}" ("vocotviptv.com" OR "vocotvusa.net" OR "vocotv.ai" OR "vocoiptv.com") (redirect OR linked OR support OR publisher OR billing OR company)'),
    )
    plan = []
    for domain in domains:
        for category, template in templates:
            query = template.format(d=domain)
            plan.append({
                "query_id": f"tev1_{domain.replace('.', '_')}_{category}", "target_domain": domain,
                "category": category, "exact_query": query, "query_hash": sha256_text(normalize_query(query)),
                "max_results": MAX_RESULTS, "search_depth": search_depth, "timeout": timeout,
                "status": "PLANNED", "identity_claim_prohibited": True,
            })
    return plan

def build_access_plan(domains: list[str]) -> list[dict[str, Any]]:
    paths = (("root", "/"), ("legal", "/terms"), ("privacy", "/privacy-policy"), ("contact", "/contact"))
    return [{"access_id": f"access_{domain.replace('.', '_')}_{kind}", "target_domain": domain, "purpose": kind,
             "url": f"https://{domain}{path}", "status": "PLANNED", "redirect_policy": "DIRECT_ONLY_WITHIN_AUTHORIZED_DOMAINS"}
            for domain in domains for kind, path in paths]

def validate_domain(value: str) -> str:
    domain = value.strip().lower().rstrip(".")
    if domain not in ALLOWED_DOMAINS:
        raise argparse.ArgumentTypeError(f"target domain outside fixed allowlist: {value}")
    return domain

def validate_plan(queries: list[dict[str, Any]], accesses: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    errors, historical = [], historical_queries()
    duplicates = []
    if len(queries) > args.max_tavily_queries or args.max_tavily_queries > MAX_TAVILY_QUERIES:
        errors.append("Tavily query budget exceeded")
    if len(accesses) > args.max_external_accesses or args.max_external_accesses > MAX_EXTERNAL_ACCESSES:
        errors.append("external access budget exceeded")
    if len(accesses) > PROTOCOL_ACCESS_CEILING:
        errors.append("protocol access ceiling exceeded")
    for item in queries:
        q = normalize_query(item["exact_query"])
        if q in historical:
            duplicates.append(item["query_id"]); errors.append(f"historical query rejected: {item['query_id']}")
        if any(pattern in q for pattern in FORBIDDEN_QUERY_PATTERNS):
            errors.append(f"general query rejected: {item['query_id']}")
        if item["max_results"] > MAX_RESULTS:
            errors.append(f"max_results exceeded: {item['query_id']}")
        if item["target_domain"] not in ALLOWED_DOMAINS:
            errors.append(f"query scope violation: {item['query_id']}")
    for item in accesses:
        host = (urlparse(item["url"]).hostname or "").lower()
        if host not in ALLOWED_DOMAINS:
            errors.append(f"access scope violation: {item['access_id']}")
    return {"valid": not errors, "errors": errors, "historical_queries_detected_and_excluded": duplicates,
            "historical_query_count_loaded": len(historical)}

def classify_identity(signals: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [s for s in signals if s.get("signal_type") not in ZERO_IDENTITY_SIGNALS]
    strong = [s for s in usable if s.get("attribution_strength") == "IDENTITY_STRONG"]
    categories = {s.get("category") for s in usable if s.get("category")}
    groups = {s.get("independence_group") for s in usable if s.get("independence_group")}
    row_ids = sorted({row for s in signals for row in s.get("supporting_row_ids", [])})
    conflicts = any(s.get("material_conflict") for s in signals)
    first_party = any(s.get("first_party") for s in usable)
    if strong and len(categories) >= 2 and len(groups) >= 2 and first_party and not conflicts:
        role = "PROBABLE_BRAND_OPERATOR"
    elif any(s.get("direct_attributable_relation") for s in usable):
        role = "POSSIBLE_RELATED_DOMAIN"
    elif any(s.get("signal_type") == "RESELLER" for s in signals):
        role = "RESELLER"
    else:
        role = "UNRESOLVED"
    assert role in VALID_ROLES and row_ids
    return {"final_role": role, "supporting_row_ids": row_ids, "official_domain_confirmed": False}

def deterministic_retryable(error: BaseException) -> bool:
    text = str(error).casefold()
    deterministic = ("authentication", "unauthorized", "invalid", "too long", "400", "401", "403", "404")
    return not any(token in text for token in deterministic)

def load_checkpoint(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": "targeted_external_verification_v1", "queries": {}, "accesses": {}, "tavily_query_count": 0,
                "tavily_attempt_count": 0, "logical_direct_access_count": 0, "physical_http_attempt_count": 0,
                "redirect_event_count": 0, "capture_event_count": 0, "log_event_count": 0, "total_budget_units_consumed": 0}
    value = json.loads(path.read_text(encoding="utf-8"))
    value.setdefault("tavily_attempt_count", value.get("tavily_query_count", 0))
    for key in ("logical_direct_access_count", "physical_http_attempt_count", "redirect_event_count", "capture_event_count", "log_event_count", "total_budget_units_consumed"):
        value.setdefault(key, 0)
    return value

def execute_tavily(queries: list[dict[str, Any]], checkpoint: dict[str, Any], run_dir: Path, args: argparse.Namespace, client: Any = None) -> None:
    # Credential access and SDK import exist only on this execute-only path.
    if client is None:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise RuntimeError("TAVILY_API_KEY is required before any external call")
        from tavily import TavilyClient  # type: ignore
        client = TavilyClient(api_key=api_key)
    for query in queries:
        if checkpoint["queries"].get(query["query_id"], {}).get("status") == "COMPLETED":
            continue
        if checkpoint["tavily_query_count"] >= args.max_tavily_queries or checkpoint["total_budget_units_consumed"] >= args.max_external_accesses:
            break
        attempts = 0
        while attempts < 2:
            attempts += 1
            started = now_iso()
            append_jsonl(run_dir / "query_log.jsonl", {"query_id": query["query_id"], "query_hash": query["query_hash"],
                "status": "STARTED", "attempt": attempts, "started_at": started, "completed_at": None, "result_count": None,
                "error_type": None, "retryable": None, "raw_row_ids": []})
            try:
                result = client.search(query=query["exact_query"], search_depth=args.search_depth,
                                       max_results=MAX_RESULTS, include_raw_content=True, include_answer=False)
                checkpoint["tavily_query_count"] += 1; checkpoint["tavily_attempt_count"] += 1
                checkpoint["total_budget_units_consumed"] += 1
                row_id = "tavily_" + sha256_text(query["query_id"] + started)[:24]
                append_jsonl(run_dir / "raw_external_evidence.jsonl", {"row_id": row_id, "source_type": "TAVILY", "query_id": query["query_id"], "result": result})
                count = len(result.get("results", [])) if isinstance(result, dict) else 0
                completed = now_iso()
                checkpoint["queries"][query["query_id"]] = {"status": "COMPLETED", "attempts": attempts, "result_count": count,
                    "raw_row_ids": [row_id], "started_at": started, "completed_at": completed}
                append_jsonl(run_dir / "query_log.jsonl", {"query_id": query["query_id"], "query_hash": query["query_hash"], "status": "COMPLETED",
                    "attempt": attempts, "started_at": started, "completed_at": completed, "result_count": count, "error_type": None,
                    "retryable": False, "raw_row_ids": [row_id]})
                write_json_atomic(run_dir / "checkpoint.json", checkpoint)
                break
            except Exception as exc:
                checkpoint["tavily_attempt_count"] += 1; checkpoint["total_budget_units_consumed"] += 1
                retryable = deterministic_retryable(exc)
                append_jsonl(run_dir / "query_log.jsonl", {"query_id": query["query_id"], "query_hash": query["query_hash"], "status": "FAILED",
                    "attempt": attempts, "started_at": started, "completed_at": now_iso(), "result_count": 0,
                    "error_type": type(exc).__name__, "retryable": retryable, "raw_row_ids": []})
                if not retryable or attempts >= 2:
                    checkpoint["queries"][query["query_id"]] = {"status": "FAILED", "attempts": attempts, "error_type": type(exc).__name__, "retryable": retryable}
                    write_json_atomic(run_dir / "checkpoint.json", checkpoint)
                    break
                time.sleep(args.pause_seconds)

def registrable_domain(host: str) -> str:
    host = host.lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host

def is_authorized_host_for_target(host: str, target_domain: str) -> bool:
    host = (host or "").strip().lower().rstrip(".")
    target = (target_domain or "").strip().lower().rstrip(".")
    return target in ALLOWED_DOMAINS and host in {target, "www." + target}

def classify_redirect(source_url: str, target_url: str) -> str:
    source, target = (urlparse(source_url).hostname or "").lower(), (urlparse(target_url).hostname or "").lower()
    base_source = registrable_domain(source)
    if base_source not in ALLOWED_DOMAINS:
        return "CROSS_DOMAIN_REDIRECT_REJECTED"
    if {source, target} <= {base_source, "www." + base_source}:
        return "SAME_AUTHORIZED_DOMAIN_WWW_REDIRECT"
    if target.endswith("." + base_source):
        return "ARBITRARY_SUBDOMAIN_REDIRECT_REJECTED"
    return "CROSS_DOMAIN_REDIRECT_REJECTED"

def validate_redirect_chain(initial_url: str, redirects: list[str], target_domain: str) -> bool:
    hosts = [(urlparse(initial_url).hostname or "")] + [(urlparse(x).hostname or "") for x in redirects]
    return bool(hosts) and all(is_authorized_host_for_target(host, target_domain) for host in hosts)

def sanitize_url_error(exc: BaseException) -> dict[str, Any]:
    reason = getattr(exc, "reason", exc)
    text = re.sub(r"(?i)(api[_-]?key|authorization|token|password)\s*[:=]\s*\S+", r"\1=[REDACTED]", str(reason))[:300]
    reason_class = type(reason).__name__
    transient = reason_class in {"TimeoutError", "ConnectionResetError", "ConnectionRefusedError", "gaierror"}
    return {"error_type": type(exc).__name__, "reason_class": reason_class, "reason_text": text,
            "transient_or_deterministic": "TRANSIENT" if transient else "UNKNOWN", "retryable": transient}

def execute_direct_accesses(accesses: list[dict[str, Any]], checkpoint: dict[str, Any], run_dir: Path, args: argparse.Namespace) -> None:
    """Execute isolated public-page GETs; never used by dry-run/preflight."""
    import urllib.error
    import urllib.request

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    for access in accesses:
        access_id = access["access_id"]
        prior = checkpoint["accesses"].get(access_id, {})
        if prior.get("status") in {"COMPLETED", "TERMINAL_404", "FAILED_REASON_NOT_PRESERVED"}:
            continue
        if prior.get("status") == "FAILED" and not prior.get("reason_class"):
            prior["status"] = "FAILED_REASON_NOT_PRESERVED"
            continue
        if prior.get("status") == "SCOPE_BLOCKED" and not args.authorize_http_repair:
            continue
        if args.http_repair_only and prior.get("status") != "SCOPE_BLOCKED":
            continue
        if checkpoint["total_budget_units_consumed"] >= args.max_external_accesses:
            break
        checkpoint["logical_direct_access_count"] += 1
        url, redirects, completed = access["url"], [], False
        for _ in range(2):
            host = (urlparse(url).hostname or "").lower()
            if host not in ALLOWED_DOMAINS:
                checkpoint["accesses"][access_id] = {"status": "SCOPE_BLOCKED", "url": url}
                break
            request = urllib.request.Request(url, method="GET", headers={"User-Agent": "IPTV-Targeted-Verification/1.0"})
            checkpoint["physical_http_attempt_count"] += 1; checkpoint["total_budget_units_consumed"] += 1
            try:
                with opener.open(request, timeout=args.timeout) as response:
                    body = response.read(2_000_000)
                    row_id = "http_" + sha256_text(url + hashlib.sha256(body).hexdigest())[:24]
                    append_jsonl(run_dir / "raw_external_evidence.jsonl", {"row_id": row_id, "access_id": access_id, "source_url": url,
                        "status_code": response.status, "content_sha256": hashlib.sha256(body).hexdigest(), "content": body.decode("utf-8", errors="replace")})
                    checkpoint["accesses"][access_id] = {"status": "COMPLETED", "url": url, "supporting_row_ids": [row_id]}
                    checkpoint["capture_event_count"] += 1; completed = True; break
            except urllib.error.HTTPError as exc:
                if exc.code in (301, 302, 303, 307, 308) and exc.headers.get("Location"):
                    from urllib.parse import urljoin
                    target = urljoin(url, exc.headers["Location"]); redirect_class = classify_redirect(url, target)
                    checkpoint["redirect_event_count"] += 1; redirects.append({"target": target, "classification": redirect_class})
                    if redirect_class != "SAME_AUTHORIZED_DOMAIN_WWW_REDIRECT":
                        checkpoint["accesses"][access_id] = {"status": "SCOPE_BLOCKED", "url": target, "redirect_class": redirect_class}; break
                    url = target; continue
                status = "TERMINAL_404" if exc.code == 404 else "FAILED_REASON_KNOWN"
                checkpoint["accesses"][access_id] = {"status": status, "url": url, "status_code": exc.code, "retryable": False}; break
            except (urllib.error.URLError, TimeoutError) as exc:
                checkpoint["accesses"][access_id] = {"status": "FAILED_REASON_KNOWN", "url": url, "access_id": access_id, "attempt": 1, **sanitize_url_error(exc)}; break
        append_jsonl(run_dir / "external_access_log.jsonl", {"access_id": access_id, "url": access["url"], "redirects": redirects,
            "status": "COMPLETED" if completed else checkpoint["accesses"].get(access_id, {}).get("status", "FAILED")})
        checkpoint["log_event_count"] += 1; write_json_atomic(run_dir / "checkpoint.json", checkpoint)
        if checkpoint["total_budget_units_consumed"] >= args.max_external_accesses: break

def write_csv_rows(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)

def read_jsonl(path: Path) -> list[tuple[int, str, dict[str, Any]]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if line.strip(): rows.append((number, line, json.loads(line)))
    return rows

def html_title(content: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", content)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", match.group(1)))).strip() if match else ""

def target_from_query_id(query_id: str) -> str:
    for domain in ALLOWED_DOMAINS:
        if domain.replace(".", "_") in query_id: return domain
    return ""

def category_from_query_id(query_id: str) -> str:
    for category in ("legal_identity", "contact_application", "attributable_relationships"):
        if query_id.endswith(category): return category
    return "unknown"

def offline_replay(source: Path, output: Path) -> dict[str, Any]:
    if not source.is_dir(): raise ValueError(f"source run does not exist: {source}")
    if output.exists(): raise ValueError(f"recovery output already exists: {output}")
    before = recursive_directory_fingerprint(source)
    output.mkdir(parents=True)
    plan = json.loads((source / "query_plan.json").read_text(encoding="utf-8"))
    checkpoint = json.loads((source / "checkpoint.json").read_text(encoding="utf-8"))
    raw_lines = read_jsonl(source / "raw_external_evidence.jsonl")
    access_logs = read_jsonl(source / "external_access_log.jsonl")
    plan_by_query = {q["query_id"]: q for q in plan["queries"]}

    inventory, query_raw, normalized = [], {}, []
    tavily_records = http_records = internal_results = 0
    all_urls = []
    for number, line, obj in raw_lines:
        record_hash = hashlib.sha256(line.encode("utf-8")).hexdigest().upper()
        row_id = obj.get("row_id") or f"raw_line_{number:04d}"
        source_type = "TAVILY" if "result" in obj else "HTTP"
        query_id, access_id = obj.get("query_id", ""), obj.get("access_id", "")
        target_domain = target_from_query_id(query_id) if query_id else registrable_domain(urlparse(obj.get("source_url", "")).hostname or "")
        result = obj.get("result", {}) if source_type == "TAVILY" else {}
        items = result.get("results", []) if isinstance(result, dict) else []
        available = sorted(obj.keys()); expected = ["row_id", "source_type", "query_id" if source_type == "TAVILY" else "access_id", "timestamp"]
        missing = [x for x in expected if not obj.get(x)]
        inventory.append({"line_number": number, "row_id": row_id, "source_type": source_type, "query_id": query_id,
            "access_id": access_id, "target_domain": target_domain, "url": obj.get("source_url", ""),
            "title": html_title(obj.get("content", "")) if source_type == "HTTP" else "", "category": category_from_query_id(query_id),
            "origin": source_type, "record_bytes": len(line.encode("utf-8")), "internal_result_count": len(items),
            "record_sha256": record_hash, "supporting_row_ids": json.dumps([row_id]), "parse_status": "PARSED",
            "available_fields": json.dumps(available), "missing_fields": json.dumps(missing)})
        if source_type == "TAVILY":
            tavily_records += 1; query_raw.setdefault(query_id, []).append(row_id); internal_results += len(items)
            for index, item in enumerate(items, 1):
                evidence_id = f"{row_id}_result_{index:02d}"; url = item.get("url", ""); all_urls.append(url)
                content = item.get("raw_content") or item.get("content") or ""
                canonical = url.rstrip("/").casefold(); group = "grp_" + sha256_text(canonical + "|" + sha256_text(content))[:20]
                normalized.append({"evidence_id": evidence_id, "source_type": "TAVILY", "query_id": query_id, "access_id": "",
                    "target_domain": target_domain, "source_url": url, "title": item.get("title", ""), "category": category_from_query_id(query_id),
                    "content_sha256": sha256_text(content), "independence_group": group, "attribution_strength": "NONE",
                    "identity_value": 0, "is_duplicate": False, "supporting_row_ids": json.dumps([row_id]), "provenance": "PRESERVED_RAW_TAVILY_RESULT"})
        else:
            http_records += 1; url = obj.get("source_url", ""); all_urls.append(url); content = obj.get("content", "")
            canonical = url.rstrip("/").casefold(); group = "grp_" + sha256_text(canonical + "|" + obj.get("content_sha256", sha256_text(content)))[:20]
            normalized.append({"evidence_id": row_id, "source_type": "HTTP", "query_id": "", "access_id": access_id,
                "target_domain": target_domain, "source_url": url, "title": html_title(content), "category": next((x for x in ("legal", "privacy", "contact", "root") if access_id.endswith(x)), "unknown"),
                "content_sha256": obj.get("content_sha256", sha256_text(content)), "independence_group": group,
                "attribution_strength": "NONE", "identity_value": 0, "is_duplicate": False,
                "supporting_row_ids": json.dumps([row_id]), "provenance": "PRESERVED_RAW_HTTP_CAPTURE"})
    seen = set()
    for row in normalized:
        key = row["source_url"].rstrip("/").casefold()
        row["is_duplicate"] = key in seen
        seen.add(key)

    inventory_fields = ["line_number", "row_id", "source_type", "query_id", "access_id", "target_domain", "url", "title", "category", "origin", "record_bytes", "internal_result_count", "record_sha256", "supporting_row_ids", "parse_status", "available_fields", "missing_fields"]
    write_csv_rows(output / "forensic_raw_evidence_inventory.csv", inventory_fields, inventory)
    write_json(output / "forensic_raw_evidence_inventory.json", {"provenance": "SOURCE_RUN_READ_ONLY", "records": inventory})

    ledger, query_summary = [], []
    for q in plan["queries"]:
        state = checkpoint.get("queries", {}).get(q["query_id"], {})
        row_ids = query_raw.get(q["query_id"], [])
        preserved = [x for x in normalized if x["query_id"] == q["query_id"]]
        urls = [x["source_url"] for x in preserved]
        item = {"marker": "RECONSTRUCTED_FROM_CHECKPOINT_PLAN_AND_RAW_EVIDENCE", "query_id": q["query_id"], "query_hash": q.get("query_hash"),
            "exact_query": q.get("exact_query"), "target_domain": q.get("target_domain"), "category": q.get("category"),
            "status": state.get("status", "UNKNOWN"), "attempts": state.get("attempts"), "result_count": len(preserved),
            "raw_row_ids": row_ids, "urls": urls, "started_at": state.get("started_at"), "completed_at": state.get("completed_at"),
            "nonrecoverable_fields": [x for x in ("started_at", "completed_at") if not state.get(x)],
            "provenance": "query_plan.json + checkpoint.json + raw_external_evidence.jsonl", "confidence_of_reconstruction": "HIGH" if row_ids else "MEDIUM"}
        ledger.append(item)
        query_summary.append({"query_id": item["query_id"], "query_hash": item["query_hash"], "target_domain": item["target_domain"], "category": item["category"],
            "status": item["status"], "attempts": item["attempts"], "result_count": item["result_count"], "raw_row_ids": json.dumps(row_ids),
            "unique_url_count": len(set(urls)), "timestamps_recoverable": not item["nonrecoverable_fields"], "provenance": item["provenance"], "confidence_of_reconstruction": item["confidence_of_reconstruction"]})
    with (output / "reconstructed_query_ledger.jsonl").open("w", encoding="utf-8") as handle:
        for item in ledger: handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    write_csv_rows(output / "reconstructed_query_summary.csv", list(query_summary[0]), query_summary)

    logs_by_access: dict[str, list[dict[str, Any]]] = {}
    for _, _, event in access_logs: logs_by_access.setdefault(event["access_id"], []).append(event)
    access_rows, redirect_events = [], 0
    for access in plan["direct_access_plan"]:
        aid = access["access_id"]; events = logs_by_access.get(aid, []); state = checkpoint.get("accesses", {}).get(aid, {})
        redirects = [r for event in events for r in event.get("redirects", [])]; redirect_events += len(redirects)
        captures = [event for event in events if event.get("row_id")]
        status, classification = state.get("status", "UNRESOLVED"), "UNRESOLVED"
        if state.get("status_code") == 404: classification = "TERMINAL_404"
        elif status == "COMPLETED": classification = "COMPLETED"
        elif status == "FAILED" and state.get("error_type") == "URLError": classification = "FAILED_REASON_NOT_PRESERVED"
        elif status == "SCOPE_BLOCKED" and redirects:
            classification = "REPAIRABLE_WWW_REDIRECT" if all(classify_redirect(access["url"], str(r)) == "SAME_AUTHORIZED_DOMAIN_WWW_REDIRECT" for r in redirects) else "SCOPE_BLOCKED_VALID"
        elif status == "SCOPE_BLOCKED": classification = "SCOPE_BLOCKED_VALID"
        access_rows.append({"access_id": aid, "target_domain": access["target_domain"], "planned_url": access["url"], "checkpoint_status": status,
            "forensic_classification": classification, "logical_access_count": 1, "physical_http_attempts": 1 + (1 if status == "COMPLETED" and redirects else 0),
            "redirect_event_count": len(redirects), "capture_event_count": len(captures), "log_event_count": len(events),
            "duplicate_log_events": max(0, len(events) - 1), "reason_recoverable": classification != "FAILED_REASON_NOT_PRESERVED",
            "supporting_row_ids": json.dumps([x.get("row_id") for x in captures if x.get("row_id")])})
    physical_http = sum(int(x["physical_http_attempts"]) for x in access_rows)
    duplicate_logs = sum(int(x["duplicate_log_events"]) for x in access_rows)
    write_csv_rows(output / "logical_access_reconciliation.csv", list(access_rows[0]), access_rows)
    access_reconciliation = {"planned_logical_accesses": len(access_rows), "logical_accesses": len(access_rows), "physical_http_attempts": physical_http,
        "redirect_events": redirect_events, "capture_events": sum(int(x["capture_event_count"]) for x in access_rows), "log_events": len(access_logs),
        "duplicate_log_events": duplicate_logs, "tavily_logical_queries": len(plan["queries"]), "tavily_attempts": checkpoint.get("tavily_query_count", 0),
        "total_budget_units_consumed_reconstructed": checkpoint.get("tavily_query_count", 0) + physical_http,
        "checkpoint_external_access_count": checkpoint.get("external_access_count"), "methodological_budget_remaining_from_40": max(0, 40 - checkpoint.get("tavily_query_count", 0) - physical_http),
        "cause_of_30": "12 Tavily attempts + 18 physical HTTP attempts (16 initial attempts + 2 followed redirects)", "accesses": access_rows}
    write_json(output / "logical_access_reconciliation.json", access_reconciliation)

    normalized_fields = ["evidence_id", "source_type", "query_id", "access_id", "target_domain", "source_url", "title", "category", "content_sha256", "independence_group", "attribution_strength", "identity_value", "is_duplicate", "supporting_row_ids", "provenance"]
    write_csv_rows(output / "normalized_external_evidence_recovered.csv", normalized_fields, normalized)
    groups = {}
    for row in normalized: groups.setdefault(row["independence_group"], []).append(row)
    group_rows = [{"independence_group": gid, "member_count": len(members), "evidence_ids": json.dumps([x["evidence_id"] for x in members]),
        "categories": json.dumps(sorted({x["category"] for x in members})), "identity_counted": False,
        "supporting_row_ids": json.dumps(sorted({r for x in members for r in json.loads(x["supporting_row_ids"])}))} for gid, members in sorted(groups.items())]
    write_csv_rows(output / "evidence_independence_groups_recovered.csv", list(group_rows[0]), group_rows)
    relations = []
    for row in normalized:
        for other in ALLOWED_DOMAINS:
            if other != row["target_domain"] and other in row["source_url"].casefold():
                relations.append({"relationship_id": "rel_" + sha256_text(row["evidence_id"] + other)[:20], "source_domain": row["target_domain"],
                    "target_domain": other, "relation_type": "NOMINAL_OR_URL_REFERENCE", "identity_value": 0,
                    "supporting_row_ids": row["supporting_row_ids"], "decision_reason": "reference alone contributes zero identity"})
    relation_fields = ["relationship_id", "source_domain", "target_domain", "relation_type", "identity_value", "supporting_row_ids", "decision_reason"]
    write_csv_rows(output / "attribution_relationships_recovered.csv", relation_fields, relations)
    gate_rows, roles, gaps = [], [], []
    for domain in ALLOWED_DOMAINS:
        rows = [x for x in normalized if x["target_domain"] == domain]
        row_ids = sorted({r for x in rows for r in json.loads(x["supporting_row_ids"])}) or ["NO_PRESERVED_EVIDENCE_ROW"]
        decision = classify_identity([{"signal_type": "CONTROL", "supporting_row_ids": row_ids}])
        gate_rows.append({"domain": domain, "strong_count": 0, "category_count": 0, "independence_group_count": 0, "first_party_identity": False,
            "material_conflicts": False, "final_role": decision["final_role"], "supporting_row_ids": json.dumps(row_ids),
            "gate_reason": "no attributable strong identity signal preserved; nominal, technical, review and commercial signals count zero"})
        roles.append({"domain": domain, "final_role": decision["final_role"], "confidence": "HIGH_ABSTENTION", "official_domain_confirmed": False,
            "supporting_row_ids": json.dumps(row_ids), "decision_reason": gate_rows[-1]["gate_reason"]})
        gaps.append({"domain": domain, "current_role": decision["final_role"], "preserved_evidence_count": len(rows),
            "missing_evidence": "IDENTITY_STRONG plus two independent attributable categories and first-party convergence", "supporting_row_ids": json.dumps(row_ids)})
    write_csv_rows(output / "attribution_gate_trace_recovered.csv", list(gate_rows[0]), gate_rows)
    write_csv_rows(output / "domain_role_classification_recovered.csv", list(roles[0]), roles)
    write_csv_rows(output / "domain_identity_gap_matrix_recovered.csv", list(gaps[0]), gaps)

    names = {"vocotviptv.com": "vocotviptv_recovered_dossier.md", "vocotvusa.net": "vocotvusa_recovered_dossier.md", "vocotv.ai": "vocotvai_recovered_dossier.md", "vocoiptv.com": "vocoiptv_recovered_dossier.md"}
    for domain, name in names.items():
        count = sum(1 for x in normalized if x["target_domain"] == domain)
        (output / name).write_text(f"# Recovered dossier: {domain}\n\nFinal role: UNRESOLVED.\n\nPreserved normalized evidence rows: {count}.\n\nNo official-domain conclusion is permitted. V4 identity gates are not met.\n", encoding="utf-8")
    tavily_summary = {"raw_records": tavily_records, "queries_with_raw_evidence": len(query_raw), "queries_completed": sum(x["status"] == "COMPLETED" for x in ledger),
        "internal_results": internal_results, "queries_without_results": [x["query_id"] for x in ledger if x["result_count"] == 0],
        "unique_result_urls": len({x["source_url"] for x in normalized if x["source_type"] == "TAVILY"}), "do_not_repeat_completed_queries": True}
    http_summary = {"raw_records": http_records, "captured_accesses": [x["access_id"] for x in normalized if x["source_type"] == "HTTP"],
        "logical_accesses": len(access_rows), "physical_http_attempts": physical_http, "repairable_www_redirects": [x["access_id"] for x in access_rows if x["forensic_classification"] == "REPAIRABLE_WWW_REDIRECT"],
        "terminal_404": [x["access_id"] for x in access_rows if x["forensic_classification"] == "TERMINAL_404"],
        "failed_reason_not_preserved": [x["access_id"] for x in access_rows if x["forensic_classification"] == "FAILED_REASON_NOT_PRESERVED"]}
    write_json(output / "preserved_tavily_results_summary.json", tavily_summary)
    write_json(output / "preserved_http_evidence_summary.json", http_summary)
    metrics = {"mode": "OFFLINE_REPLAY", "raw_records": len(raw_lines), "tavily_raw_records": tavily_records, "http_raw_records": http_records,
        "internal_tavily_results": internal_results, "normalized_evidence_rows": len(normalized), "all_url_occurrences": len(all_urls), "unique_urls": len(set(all_urls)),
        "duplicate_url_occurrences": len(all_urls) - len(set(all_urls)), **{k: v for k, v in access_reconciliation.items() if k != "accesses"},
        "credential_reads": 0, "tavily_calls_added": 0, "http_attempts_added": 0, "dns_attempts_added": 0, "official_domain_emitted": False}
    write_json(output / "recovery_metrics.json", metrics)
    report = ("# Execution truth report\n\nProvenance: RECONSTRUCTED_FROM_CHECKPOINT_PLAN_AND_RAW_EVIDENCE.\n\n"
        f"Preserved raw records: {len(raw_lines)} ({tavily_records} Tavily, {http_records} HTTP).\n\n"
        f"Recovered Tavily results: {internal_results}; unique URLs across preserved evidence: {len(set(all_urls))}.\n\n"
        f"Logical HTTP accesses: {len(access_rows)}; physical HTTP attempts: {physical_http}; log events: {len(access_logs)}; duplicate log events: {duplicate_logs}.\n\n"
        "The historical count 30 equals 12 Tavily attempts plus 18 physical HTTP attempts. No timestamp was invented.\n\n"
        "All four domains remain UNRESOLVED under V4. No official domain is declared.\n")
    (output / "execution_truth_report.md").write_text(report, encoding="utf-8")
    (output / "runner_fix_validation_report.md").write_text("# Runner fix validation report\n\nMode: OFFLINE_REPLAY. The derived replay made zero credential reads and zero network calls. The runner includes durable query logging, separated counters, redirect policy, sanitized URL errors, terminal-state resume guards, execution-aware reports, V4 abstention, and immutable-source replay.\n", encoding="utf-8")
    after = recursive_directory_fingerprint(source)
    manifest = {"mode": "OFFLINE_REPLAY", "source_run_read_only": True, "source_before": before, "source_after": after,
        "source_unchanged": before["aggregate_sha256"] == after["aggregate_sha256"], "created_at": now_iso(),
        "output_files": sorted(x.name for x in output.iterdir() if x.is_file()), "self_hash_excluded": True}
    write_json(output / "recovery_integrity_manifest.json", manifest)
    return {"output": str(output), "source_hash": before["aggregate_sha256"], "source_unchanged": manifest["source_unchanged"], **metrics,
            "repairable_accesses": len(http_summary["repairable_www_redirects"]), "terminal_accesses": len(http_summary["terminal_404"]),
            "failed_reason_not_preserved": len(http_summary["failed_reason_not_preserved"])}

def validate_derived_repair(source: Path, selected_ids: list[str], combined_limit: int, max_http_attempts: int = 3) -> dict[str, Any]:
    if not source.is_dir(): raise ValueError(f"source run does not exist: {source}")
    if len(selected_ids) != len(set(selected_ids)): raise ValueError("duplicate --repair-access-id is not allowed")
    if set(selected_ids) != set(AUTHORIZED_REPAIR_ACCESS_IDS):
        extra = sorted(set(selected_ids) - set(AUTHORIZED_REPAIR_ACCESS_IDS)); missing = sorted(set(AUTHORIZED_REPAIR_ACCESS_IDS) - set(selected_ids))
        raise ValueError(f"repair selection must be exactly the four authorized IDs; extra={extra}; missing={missing}")
    checkpoint = json.loads((source / "checkpoint.json").read_text(encoding="utf-8"))
    plan = json.loads((source / "query_plan.json").read_text(encoding="utf-8"))
    access_plan = {x["access_id"]: x for x in plan["direct_access_plan"]}
    logs_by_access: dict[str, list[dict[str, Any]]] = {}
    for _, _, event in read_jsonl(source / "external_access_log.jsonl"):
        logs_by_access.setdefault(event["access_id"], []).append(event)
    selected = []
    for access_id in selected_ids:
        if access_id not in checkpoint.get("accesses", {}): raise ValueError(f"access ID absent from source checkpoint: {access_id}")
        state = checkpoint["accesses"][access_id]
        if state.get("status") != "SCOPE_BLOCKED": raise ValueError(f"access is not SCOPE_BLOCKED: {access_id} ({state.get('status')})")
        access = access_plan.get(access_id)
        if not access: raise ValueError(f"access ID absent from source plan: {access_id}")
        redirects = [str(x) for event in logs_by_access.get(access_id, []) for x in event.get("redirects", [])]
        if not redirects or not all(classify_redirect(access["url"], x) == "SAME_AUTHORIZED_DOMAIN_WWW_REDIRECT" for x in redirects):
            raise ValueError(f"access is not REPAIRABLE_WWW_REDIRECT: {access_id}")
        if not validate_redirect_chain(access["url"], redirects, access["target_domain"]):
            raise ValueError(f"historical redirect chain escaped authorized hosts: {access_id}")
        selected.append({**access, "source_status": state["status"], "historical_redirects": redirects,
                         "forensic_classification": "REPAIRABLE_WWW_REDIRECT", "supporting_row_ids": []})
    historical = int(checkpoint.get("external_access_count", 0)); budget=project_repair_budget(historical,len(selected),max_http_attempts,combined_limit)
    projected=budget["repair_projected_max"]; combined=budget["combined_projected_max"]
    if budget["budget_gate"] != "PASS": raise ValueError(f"repair budget would exceed limit: {historical}+{projected}>{combined_limit}")
    return {"source_fingerprint": recursive_directory_fingerprint(source), "source_checkpoint": checkpoint, "selected_accesses": selected,
            "historical_budget_units": historical, "repair_projected_max": projected, "max_http_attempts": max_http_attempts, "combined_projected_max": combined,
            "combined_limit": combined_limit, "remaining_budget_units_projected": combined_limit - combined, "budget_gate": "PASS"}

def project_repair_budget(historical: int, access_count: int, max_http_attempts: int, combined_limit: int) -> dict[str, Any]:
    projected=access_count*max_http_attempts; combined=historical+projected
    return {"historical_budget_units":historical,"repair_projected_max":projected,"combined_projected_max":combined,
        "combined_limit":combined_limit,"remaining_budget_units":combined_limit-combined,"budget_gate":"PASS" if combined<=combined_limit else "BLOCK"}

def repair_artifact_names() -> list[str]:
    return ["repair_authorization_and_scope.json", "repair_preflight_report.md", "repair_plan.json", "repair_checkpoint.json",
            "repair_external_access_log.jsonl", "repair_raw_http_evidence.jsonl", "repair_domain_redirects.csv",
            "repair_normalized_evidence.csv", "repair_access_reconciliation.csv", "repair_metrics.json",
            "repair_safety_and_scope_audit.md", "repair_report.md", "repair_integrity_manifest.json"]

def repair_powershell_command(args: argparse.Namespace, for_future_execution: bool = False) -> str:
    ids = " ".join(f'--repair-access-id "{x}"' for x in args.repair_access_id)
    output = args.repair_output_dir
    if for_future_execution:
        name = output.name
        future_name = name.replace("http_repair_preflight", "http_repair_run") if "http_repair_preflight" in name else name + "_execute"
        output = output.with_name(future_name)
    return (f'python .\\scripts\\run_targeted_external_verification_v1.py --execute --http-repair-only --authorize-http-repair '
            f'--source-run-dir "{args.source_run_dir}" --repair-output-dir "{output}" {ids} '
            f'--max-external-accesses {args.max_external_accesses} --max-http-attempts {args.max_http_attempts} '
            f'--max-redirect-hops {args.max_redirect_hops} --timeout {args.timeout:g} --pause-seconds {args.pause_seconds:g}')

def initialize_derived_repair_output(output: Path, source: Path, validation: dict[str, Any], args: argparse.Namespace, mode: str) -> None:
    if output.exists(): raise ValueError(f"repair output already exists: {output}")
    output.mkdir(parents=True)
    source_hash = validation["source_fingerprint"]["aggregate_sha256"]
    ids = [x["access_id"] for x in validation["selected_accesses"]]
    provenance = {"mode": "DERIVED_HTTP_REPAIR", "phase": mode, "source_run_path": str(source.resolve()), "source_run_hash": source_hash,
                  "authorized_access_ids": ids, "tavily_calls_added": 0, "credential_reads": 0, "official_domain_prohibited": True}
    write_json(output / "repair_authorization_and_scope.json", provenance)
    write_json(output / "repair_plan.json", {**provenance, "accesses": validation["selected_accesses"],
        "historical_budget_units": validation["historical_budget_units"], "repair_projected_max": validation["repair_projected_max"],
        "combined_projected_max": validation["combined_projected_max"], "combined_limit": validation["combined_limit"], "budget_gate": validation["budget_gate"]})
    checkpoint = {**provenance, "schema_version": "derived_http_repair_v1", "accesses": {x: {"status": "PLANNED_DERIVED_REPAIR", "attempts": 0} for x in ids},
        "historical_budget_units": validation["historical_budget_units"], "repair_logical_access_count": 0, "repair_physical_http_attempt_count": 0,
        "repair_redirect_event_count": 0, "repair_capture_event_count": 0, "repair_log_event_count": 0,
        "combined_budget_units": validation["historical_budget_units"], "remaining_budget_units": validation["combined_limit"] - validation["historical_budget_units"]}
    write_json_atomic(output / "repair_checkpoint.json", checkpoint)
    for name in ("repair_external_access_log.jsonl", "repair_raw_http_evidence.jsonl"): (output / name).write_text("", encoding="utf-8")
    write_empty_csv(output / "repair_domain_redirects.csv", ["access_id", "source_url", "target_url", "classification", "supporting_row_ids"])
    write_empty_csv(output / "repair_normalized_evidence.csv", ["evidence_id", "access_id", "target_domain", "source_url", "title", "content_sha256", "supporting_row_ids"])
    write_empty_csv(output / "repair_access_reconciliation.csv", ["access_id", "source_status", "repair_status", "physical_attempts", "redirect_events", "capture_events", "supporting_row_ids"])
    metrics = {**provenance, "historical_budget_units": validation["historical_budget_units"], "repair_logical_access_count": len(ids),
        "repair_projected_max": validation["repair_projected_max"], "repair_physical_http_attempt_count": 0,
        "repair_redirect_event_count": 0, "repair_capture_event_count": 0, "repair_log_event_count": 0,
        "combined_projected_max": validation["combined_projected_max"], "combined_limit": validation["combined_limit"],
        "combined_budget_units": validation["historical_budget_units"], "remaining_budget_units": validation["combined_limit"] - validation["historical_budget_units"],
        "budget_gate": validation["budget_gate"], "http_attempts_added": 0, "dns_attempts_added": 0}
    write_json(output / "repair_metrics.json", metrics)
    command = repair_powershell_command(args, for_future_execution=mode == "PREFLIGHT")
    preflight = ("# Derived HTTP repair preflight\n\nMode: DERIVED_HTTP_REPAIR / " + mode + ".\n\n"
        f"Source hash: `{source_hash}`.\n\nAuthorized access IDs: {', '.join(ids)}.\n\n"
        f"Budget: {validation['historical_budget_units']} + {validation['repair_projected_max']} = {validation['combined_projected_max']} <= {validation['combined_limit']} (PASS).\n\n"
        f"```powershell\n{command}\n```\n\nWARNING: do not execute this command twice. Do not use --resume or --run-dir.\n")
    (output / "repair_preflight_report.md").write_text(preflight, encoding="utf-8")
    (output / "repair_safety_and_scope_audit.md").write_text("# Repair safety and scope audit\n\nDERIVED_HTTP_REPAIR preflight: zero Tavily, credentials, HTTP, DNS, sockets, forms, authenticated access and APK operations.\n", encoding="utf-8")
    (output / "repair_report.md").write_text("# Derived HTTP repair report\n\nNo repair executed. Preflight only. Results remain PLANNED_DERIVED_REPAIR.\n", encoding="utf-8")
    after = recursive_directory_fingerprint(source)
    write_json(output / "repair_integrity_manifest.json", {**provenance, "source_before": validation["source_fingerprint"], "source_after": after,
        "source_unchanged": after["aggregate_sha256"] == source_hash, "artifacts": repair_artifact_names(), "created_at": now_iso()})

def execute_derived_http_repair(validation: dict[str, Any], output: Path, args: argparse.Namespace) -> None:
    """Execute only the selected derived HTTP accesses; never touches Tavily or source artifacts."""
    import urllib.error
    import urllib.request
    from urllib.parse import urljoin
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl): return None
    opener = urllib.request.build_opener(NoRedirect)
    checkpoint = json.loads((output / "repair_checkpoint.json").read_text(encoding="utf-8"))
    for access in validation["selected_accesses"]:
        aid, target, url = access["access_id"], access["target_domain"], access["url"]
        checkpoint["repair_logical_access_count"] += 1; redirects = []; row_ids = []; status = "FAILED"; attempts = 0; final_url_requested = False; reason_class = "UNRESOLVED"
        for attempt in range(1, args.max_http_attempts + 1):
            host = urlparse(url).hostname or ""
            if not is_authorized_host_for_target(host, target): raise ValueError(f"repair host rejected before HTTP: {host}")
            if checkpoint["combined_budget_units"] >= args.max_external_accesses: raise ValueError("repair budget exhausted before HTTP")
            checkpoint["repair_physical_http_attempt_count"] += 1; checkpoint["combined_budget_units"] += 1
            attempts += 1; final_url_requested = True
            request = urllib.request.Request(url, method="GET", headers={"User-Agent": "IPTV-Derived-HTTP-Repair/1.0"})
            try:
                with opener.open(request, timeout=args.timeout) as response:
                    body = response.read(2_000_000); row_id = "repair_http_" + sha256_text(aid + url + hashlib.sha256(body).hexdigest())[:24]
                    append_jsonl(output / "repair_raw_http_evidence.jsonl", {"row_id": row_id, "source_type": "DERIVED_HTTP_REPAIR", "access_id": aid,
                        "target_domain": target, "source_url": url, "status_code": response.status, "content_sha256": hashlib.sha256(body).hexdigest(),
                        "content": body.decode("utf-8", errors="replace"), "supporting_row_ids": [row_id]})
                    row_ids.append(row_id); checkpoint["repair_capture_event_count"] += 1; status = "COMPLETED"; reason_class = "CAPTURED"; break
            except urllib.error.HTTPError as exc:
                if exc.code in (301, 302, 303, 307, 308) and exc.headers.get("Location"):
                    target_url = urljoin(url, exc.headers["Location"])
                    if not validate_redirect_chain(access["url"], redirects + [target_url], target): raise ValueError(f"repair redirect chain rejected: {aid}")
                    redirects.append(target_url); checkpoint["repair_redirect_event_count"] += 1; url = target_url; final_url_requested = False
                    if len(redirects) > args.max_redirect_hops or attempt >= args.max_http_attempts:
                        status = "REDIRECT_CHAIN_INCOMPLETE"; reason_class = "REDIRECT_LIMIT_OR_ATTEMPT_LIMIT"; break
                    continue
                status = "TERMINAL_404" if exc.code == 404 else "FAILED_REASON_KNOWN"; reason_class = f"HTTP_{exc.code}"; break
            except (urllib.error.URLError, TimeoutError) as exc:
                status = "FAILED_REASON_KNOWN"; reason_class = sanitize_url_error(exc)["reason_class"]; break
        event = {"access_id": aid, "target_domain": target, "initial_url": access["url"], "final_url": url, "redirects": redirects,
                 "status": status, "attempts": attempts, "redirect_hops": len(redirects), "final_url_requested": final_url_requested,
                 "reason_class": reason_class, "supporting_row_ids": row_ids}
        append_jsonl(output / "repair_external_access_log.jsonl", event); checkpoint["repair_log_event_count"] += 1
        checkpoint["accesses"][aid] = {"status": status, "attempts": attempts, "redirect_hops": len(redirects),
            "final_url_requested": final_url_requested, "reason_class": reason_class, "supporting_row_ids": row_ids}
        checkpoint["remaining_budget_units"] = args.max_external_accesses - checkpoint["combined_budget_units"]
        write_json_atomic(output / "repair_checkpoint.json", checkpoint)

def finalize_derived_repair(output: Path, source: Path, validation: dict[str, Any], args: argparse.Namespace) -> None:
    checkpoint = json.loads((output / "repair_checkpoint.json").read_text(encoding="utf-8"))
    events = [x[2] for x in read_jsonl(output / "repair_external_access_log.jsonl")]
    raw = [x[2] for x in read_jsonl(output / "repair_raw_http_evidence.jsonl")]
    redirect_rows, normalized, reconciliation = [], [], []
    for event in events:
        ids = event.get("supporting_row_ids", [])
        for target in event.get("redirects", []):
            redirect_rows.append({"access_id": event["access_id"], "source_url": event["initial_url"], "target_url": target,
                "classification": "SAME_AUTHORIZED_DOMAIN_WWW_REDIRECT", "supporting_row_ids": json.dumps(ids)})
        state = checkpoint["accesses"][event["access_id"]]
        reconciliation.append({"access_id": event["access_id"], "source_status": "SCOPE_BLOCKED", "repair_status": state["status"],
            "physical_attempts": state["attempts"], "redirect_events": state.get("redirect_hops", len(event.get("redirects", []))),
            "capture_events": len(ids), "final_url_requested": state.get("final_url_requested"), "reason_class": state.get("reason_class"),
            "supporting_row_ids": json.dumps(ids)})
    for item in raw:
        normalized.append({"evidence_id": item["row_id"], "access_id": item["access_id"], "target_domain": item["target_domain"],
            "source_url": item["source_url"], "title": html_title(item.get("content", "")), "content_sha256": item["content_sha256"],
            "supporting_row_ids": json.dumps(item["supporting_row_ids"])})
    write_csv_rows(output / "repair_domain_redirects.csv", ["access_id", "source_url", "target_url", "classification", "supporting_row_ids"], redirect_rows)
    write_csv_rows(output / "repair_normalized_evidence.csv", ["evidence_id", "access_id", "target_domain", "source_url", "title", "content_sha256", "supporting_row_ids"], normalized)
    write_csv_rows(output / "repair_access_reconciliation.csv", ["access_id", "source_status", "repair_status", "physical_attempts", "redirect_events", "capture_events", "final_url_requested", "reason_class", "supporting_row_ids"], reconciliation)
    metrics = {"mode": "DERIVED_HTTP_REPAIR", "source_run_path": str(source.resolve()), "source_run_hash": validation["source_fingerprint"]["aggregate_sha256"],
        "authorized_access_ids": args.repair_access_id, "historical_budget_units": validation["historical_budget_units"],
        "repair_logical_access_count": checkpoint["repair_logical_access_count"], "repair_physical_http_attempt_count": checkpoint["repair_physical_http_attempt_count"],
        "repair_redirect_event_count": checkpoint["repair_redirect_event_count"], "repair_capture_event_count": checkpoint["repair_capture_event_count"],
        "repair_log_event_count": checkpoint["repair_log_event_count"], "combined_budget_units": checkpoint["combined_budget_units"],
        "remaining_budget_units": checkpoint["remaining_budget_units"], "tavily_calls_added": 0, "credential_reads": 0, "official_domain_prohibited": True}
    write_json(output / "repair_metrics.json", metrics)
    (output / "repair_safety_and_scope_audit.md").write_text(f"# Repair safety and scope audit\n\nMode: DERIVED_HTTP_REPAIR. Credential reads: 0. Tavily calls: 0. HTTP attempts: {metrics['repair_physical_http_attempt_count']}. Authenticated accesses: 0. Forms: 0. APK: 0. Secrets exposed: 0.\n", encoding="utf-8")
    (output / "repair_report.md").write_text(f"# Derived HTTP repair report\n\nLogical repairs: {metrics['repair_logical_access_count']}. Captures: {metrics['repair_capture_event_count']}. Combined budget: {metrics['combined_budget_units']}/{args.max_external_accesses}. Results remain derived and are not merged with the source run.\n", encoding="utf-8")
    manifest = json.loads((output / "repair_integrity_manifest.json").read_text(encoding="utf-8")); after = recursive_directory_fingerprint(source)
    manifest["source_after"] = after; manifest["source_unchanged"] = after["aggregate_sha256"] == validation["source_fingerprint"]["aggregate_sha256"]
    write_json(output / "repair_integrity_manifest.json", manifest)

def run_derived_repair(args: argparse.Namespace, preflight_only: bool) -> dict[str, Any]:
    validation = validate_derived_repair(args.source_run_dir, args.repair_access_id, args.max_external_accesses, args.max_http_attempts)
    initialize_derived_repair_output(args.repair_output_dir, args.source_run_dir, validation, args, "PREFLIGHT" if preflight_only else "EXECUTE")
    if not preflight_only:
        execute_derived_http_repair(validation, args.repair_output_dir, args)
        finalize_derived_repair(args.repair_output_dir, args.source_run_dir, validation, args)
    final = recursive_directory_fingerprint(args.source_run_dir)
    if final["aggregate_sha256"] != validation["source_fingerprint"]["aggregate_sha256"]: raise RuntimeError("source run changed during derived repair")
    statuses = [] if preflight_only else [x.get("status") for x in json.loads((args.repair_output_dir / "repair_checkpoint.json").read_text(encoding="utf-8"))["accesses"].values()]
    execution_verdict = "TEV1_DERIVED_HTTP_REPAIR_READY_FOR_AUTHORIZATION" if preflight_only else (
        "TEV1_DERIVED_HTTP_REPAIR_COMPLETED" if statuses and all(x == "COMPLETED" for x in statuses) else
        "TEV1_DERIVED_HTTP_REPAIR_PARTIAL" if any(x == "COMPLETED" for x in statuses) else "TEV1_DERIVED_HTTP_REPAIR_FAILED")
    return {"output": str(args.repair_output_dir), "source_hash_before": validation["source_fingerprint"]["aggregate_sha256"],
            "source_hash_after": final["aggregate_sha256"], "source_unchanged": True, "selected_access_ids": args.repair_access_id,
            "historical_budget_units": validation["historical_budget_units"], "repair_projected_max": validation["repair_projected_max"],
            "combined_projected_max": validation["combined_projected_max"], "combined_limit": validation["combined_limit"],
            "tavily_calls_added": 0, "credential_reads": 0, "http_attempts_added": 0 if preflight_only else None, "verdict": execution_verdict}

class RootCaptureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(); self.links=[]; self.scripts=[]; self.structured=[]; self.text=[]; self.footer=[]; self.canonical=""; self._ld=False; self._ld_data=[]; self._footer=0
    def handle_starttag(self, tag, attrs):
        values=dict(attrs)
        if tag == "a" and values.get("href"): self.links.append(values["href"])
        if tag == "link" and "canonical" in values.get("rel", "").lower(): self.canonical=values.get("href", "")
        if tag == "script":
            if values.get("src"): self.scripts.append(values["src"])
            self._ld = values.get("type", "").lower() == "application/ld+json"; self._ld_data=[]
        if tag == "footer": self._footer += 1
    def handle_endtag(self, tag):
        if tag == "script" and self._ld:
            raw="".join(self._ld_data).strip()
            if raw:
                try: self.structured.append(json.loads(raw))
                except json.JSONDecodeError: self.structured.append({"parse_error": True, "raw_sha256": sha256_text(raw)})
            self._ld=False
        if tag == "footer" and self._footer: self._footer -= 1
    def handle_data(self, data):
        self.text.append(data)
        if self._footer: self.footer.append(data)
        if self._ld: self._ld_data.append(data)

def canonical_url(value: str) -> str:
    parsed=urlparse(value); host=(parsed.hostname or "").lower(); host=host[4:] if host.startswith("www.") else host
    path=(parsed.path or "/").rstrip("/") or "/"
    return f"{parsed.scheme.lower() or 'https'}://{host}{path}"

def merged_artifact_names() -> list[str]:
    return ["root_capture_forensic_inventory.json", "root_capture_internal_links.csv", "root_capture_external_links.csv",
        "root_capture_identity_signals.csv", "incomplete_redirect_chain_analysis.csv", "merged_normalized_external_evidence.csv",
        "merged_duplicate_audit.csv", "merged_evidence_independence_groups.csv", "merged_attribution_relationships.csv",
        "merged_attribution_gate_trace.csv", "merged_domain_role_classification.csv", "merged_domain_identity_gap_matrix.csv",
        "merged_vocotviptv_dossier.md", "merged_vocotvusa_dossier.md", "merged_vocotvai_dossier.md", "merged_vocoiptv_dossier.md",
        "remaining_budget_decision.json", "merged_metrics.json", "merged_external_verification_report.md",
        "runner_final_fix_validation.md", "merged_integrity_manifest.json"]

def merged_offline_evaluation(source: Path, recovery: Path, repair: Path, output: Path) -> dict[str, Any]:
    sources={"historical_run":source,"offline_recovery":recovery,"derived_http_repair":repair}
    if output.exists(): raise ValueError(f"merged output already exists: {output}")
    for name,path in sources.items():
        if not path.is_dir(): raise ValueError(f"missing immutable source {name}: {path}")
    before={name:recursive_directory_fingerprint(path) for name,path in sources.items()}
    output.mkdir(parents=True)
    repair_raw=read_jsonl(repair/"repair_raw_http_evidence.jsonl")
    target=next((obj for _,_,obj in repair_raw if obj.get("row_id")=="repair_http_77ef11f9e7bc683add08b682"),None)
    if not target: raise ValueError("expected root repair capture not found")
    content=target.get("content",""); base_url=target["source_url"]; parser=RootCaptureParser(); parser.feed(content)
    absolute_links=[urljoin(base_url,x) for x in parser.links]; unique_links=list(dict.fromkeys(absolute_links))
    internal=[x for x in unique_links if is_authorized_host_for_target(urlparse(x).hostname or "","vocotviptv.com")]
    external=[x for x in unique_links if x not in internal]
    text=re.sub(r"\s+"," "," ".join(parser.text)).strip(); footer=re.sub(r"\s+"," "," ".join(parser.footer)).strip()
    title=html_title(content); emails=sorted(set(re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",text)))
    phones=sorted(set(re.findall(r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)",text)))
    whatsapp=sorted({x for x in unique_links if "wa.me" in x or "whatsapp" in x.casefold()})
    social=sorted({x for x in external if any(k in (urlparse(x).hostname or "") for k in ("facebook","instagram","youtube","tiktok","twitter","x.com","telegram","t.me"))})
    classified=lambda pattern:[x for x in internal if re.search(pattern,x,re.I)]
    structured_names=sorted({str(x.get("name")) for x in parser.structured if isinstance(x,dict) and x.get("name")})
    analytics=sorted({x for x in parser.scripts if any(k in x.casefold() for k in ("googletagmanager","analytics","cloudflareinsights"))})
    inventory={"row_id":target["row_id"],"source_run":"derived_http_repair","source_artifact":"repair_raw_http_evidence.jsonl",
        "supporting_row_ids":[target["row_id"]],"initial_url":"https://vocotviptv.com/","final_url":base_url,"status_code":target.get("status_code"),
        "title":title,"content_available":bool(content),"content_bytes":len(content.encode("utf-8")),"content_sha256":target.get("content_sha256"),
        "record_sha256":hashlib.sha256(json.dumps(target,ensure_ascii=False,sort_keys=True).encode()).hexdigest().upper(),
        "canonical":parser.canonical or canonical_url(base_url),"internal_link_count":len(internal),"external_link_count":len(external),
        "terms_links":classified(r"terms|legal"),"privacy_links":classified(r"privacy"),"contact_links":classified(r"contact"),
        "support_links":classified(r"support|help"),"emails":emails,"obfuscated_email_placeholders":sorted(set(re.findall(r"\[email protected\]",text,re.I))),"phones":phones,"whatsapp":whatsapp,
        "telegram":[x for x in external if "t.me" in x or "telegram" in x.casefold()],"social_profiles":social,
        "application_links":classified(r"app|android|ios|download"),"publishers":[],"account_portals":classified(r"login|account|portal"),
        "payment_links":[x for x in external if any(k in x.casefold() for k in ("step/","checkout","pay","billing"))],
        "business_names":structured_names,"copyright_texts":re.findall(r"(?i).{0,50}(?:copyright|©).{0,100}",text)[:10],
        "operator_phrases":re.findall(r"(?i).{0,40}(?:operated by|owned by|company).{0,100}",text)[:20],
        "visible_technical_identifiers":sorted(set(re.findall(r"G-[A-Z0-9]+",content))),"analytics_scripts":analytics,
        "structured_data":parser.structured,"footer":footer,"inference_limit":"self-declared site content and technical identifiers do not prove operator identity"}
    write_json(output/"root_capture_forensic_inventory.json",inventory)
    link_fields=["source_url","target_url","link_type","supporting_row_ids"]
    write_csv_rows(output/"root_capture_internal_links.csv",link_fields,[{"source_url":base_url,"target_url":x,"link_type":"INTERNAL_FIRST_PARTY","supporting_row_ids":json.dumps([target["row_id"]])} for x in internal])
    write_csv_rows(output/"root_capture_external_links.csv",link_fields,[{"source_url":base_url,"target_url":x,"link_type":"EXTERNAL","supporting_row_ids":json.dumps([target["row_id"]])} for x in external])
    signals=[
        {"signal_id":"root_structured_org","category":"SELF_DECLARED_ORGANIZATION","observed_fact":"Organization structured data names VocoTV","attribution_strength":"NONE","independence_group":"root_site_claim","supporting_row_ids":json.dumps([target["row_id"]]),"inference_limit":"self-declared organization schema is not ownership proof"},
        {"signal_id":"root_whatsapp_contact","category":"SUPPORT_CONTACT","observed_fact":"first-party page links WhatsApp +212714633888","attribution_strength":"IDENTITY_SUPPORTING","independence_group":"root_contact","supporting_row_ids":json.dumps([target["row_id"]]),"inference_limit":"contact channel does not establish legal ownership"},
        {"signal_id":"root_checkout_links","category":"PAYMENT_LINK","observed_fact":"pricing links target wp.vibeflixtv.com","attribution_strength":"NONE","independence_group":"root_checkout","supporting_row_ids":json.dumps([target["row_id"]]),"inference_limit":"external checkout target alone is not attributable ownership"},
        {"signal_id":"root_analytics","category":"TECHNICAL","observed_fact":"Google and Cloudflare analytics scripts observed","attribution_strength":"NONE","independence_group":"root_technical","supporting_row_ids":json.dumps([target["row_id"]]),"inference_limit":"analytics and infrastructure contribute zero identity alone"},
    ]
    write_csv_rows(output/"root_capture_identity_signals.csv",list(signals[0]),signals)

    repair_checkpoint=json.loads((repair/"repair_checkpoint.json").read_text(encoding="utf-8")); repair_events=[x[2] for x in read_jsonl(repair/"repair_external_access_log.jsonl")]
    chain_rows=[]
    for event in repair_events:
        if event["status"]=="COMPLETED": continue
        state=repair_checkpoint["accesses"][event["access_id"]]; redirects=event.get("redirects",[])
        chain_rows.append({"access_id":event["access_id"],"initial_url":event["initial_url"],"requested_urls":json.dumps([event["initial_url"]]+redirects[:-1]),
            "calculated_not_requested_urls":json.dumps(redirects[-1:] if redirects else []),"final_url":event["final_url"],"checkpoint_attempts":state.get("attempts"),
            "physical_http_attempts":2,"redirect_hops":len(redirects),"final_url_requested":False,"classification":"REDIRECT_CHAIN_INCOMPLETE",
            "reason_class":"LOOP_COUNTED_REDIRECT_AS_ATTEMPT","supporting_row_ids":json.dumps([])})
    write_csv_rows(output/"incomplete_redirect_chain_analysis.csv",list(chain_rows[0]),chain_rows)

    with (recovery/"normalized_external_evidence_recovered.csv").open(encoding="utf-8") as handle:
        recovered=list(csv.DictReader(handle))
    merged=[]
    for row in recovered:
        merged.append({"source_run":"historical_run_via_offline_recovery","source_artifact":"normalized_external_evidence_recovered.csv","row_id":row["evidence_id"],
            "supporting_row_ids":row["supporting_row_ids"],"provenance":row["provenance"],"source_type":row["source_type"],
            "target_domain":row["target_domain"],"source_url":row["source_url"],"canonical_url":canonical_url(row["source_url"]),"title":row["title"],
            "category":row["category"],"first_party_or_third_party":"FIRST_PARTY" if is_authorized_host_for_target(urlparse(row["source_url"]).hostname or "",row["target_domain"]) else "THIRD_PARTY",
            "observed_fact":"preserved result or capture","inference":"none","inference_limit":"preserved appearance alone does not establish identity","independence_group":row["independence_group"],
            "attribution_strength":row["attribution_strength"],"is_duplicate":row["is_duplicate"]})
    merged.append({"source_run":"derived_http_repair","source_artifact":"repair_raw_http_evidence.jsonl","row_id":target["row_id"],
        "supporting_row_ids":json.dumps([target["row_id"]]),"provenance":"PRESERVED_DERIVED_HTTP_REPAIR_CAPTURE","source_type":"HTTP_REPAIR",
        "target_domain":"vocotviptv.com","source_url":base_url,"canonical_url":canonical_url(base_url),"title":title,"category":"ROOT_FIRST_PARTY_CAPTURE",
        "first_party_or_third_party":"FIRST_PARTY","observed_fact":"HTTP 200 root page with structured contact, internal policy links and external checkout links",
        "inference":"site operates a commercial VocoTV-branded surface","inference_limit":"does not establish legal owner or official status","independence_group":"grp_"+sha256_text(target["content_sha256"])[:20],
        "attribution_strength":"IDENTITY_SUPPORTING","is_duplicate":False})
    counts={}; duplicate_rows=[]
    for row in merged: counts.setdefault(row["canonical_url"],[]).append(row)
    for canonical,members in counts.items():
        for index,row in enumerate(members):
            row["is_duplicate"]=index>0
        if len(members)>1: duplicate_rows.append({"canonical_url":canonical,"occurrence_count":len(members),"row_ids":json.dumps([x["row_id"] for x in members]),"kept_distinct_artifacts":True,"reason":"same URL can preserve independent acquisition artifacts"})
    merged_fields=list(merged[0]); write_csv_rows(output/"merged_normalized_external_evidence.csv",merged_fields,merged)
    dup_fields=["canonical_url","occurrence_count","row_ids","kept_distinct_artifacts","reason"]
    write_csv_rows(output/"merged_duplicate_audit.csv",dup_fields,duplicate_rows)
    groups={}
    for row in merged: groups.setdefault(row["independence_group"],[]).append(row)
    group_rows=[{"independence_group":gid,"member_count":len(rows),"row_ids":json.dumps([x["row_id"] for x in rows]),"source_types":json.dumps(sorted({x["source_type"] for x in rows})),
        "attribution_strengths":json.dumps(sorted({x["attribution_strength"] for x in rows})),"supporting_row_ids":json.dumps(sorted({y for x in rows for y in json.loads(x["supporting_row_ids"])}))} for gid,rows in sorted(groups.items())]
    write_csv_rows(output/"merged_evidence_independence_groups.csv",list(group_rows[0]),group_rows)
    relationships=[]
    for x in internal:
        relationships.append({"relationship_id":"rel_"+sha256_text(base_url+x)[:20],"source_domain":"vocotviptv.com","target":x,"relationship_type":"FIRST_PARTY_INTERNAL_LINK","attribution_strength":"IDENTITY_SUPPORTING" if any(k in x for k in ("contact","terms","privacy")) else "NONE","supporting_row_ids":json.dumps([target["row_id"]]),"inference_limit":"link existence alone is not ownership"})
    for x in external:
        relation="SUPPORT_CONTACT" if "wa.me" in x else ("PAYMENT_OR_CHECKOUT_LINK" if "vibeflixtv.com" in x else "EXTERNAL_LINK")
        relationships.append({"relationship_id":"rel_"+sha256_text(base_url+x)[:20],"source_domain":"vocotviptv.com","target":x,"relationship_type":relation,
            "attribution_strength":"IDENTITY_SUPPORTING" if relation=="SUPPORT_CONTACT" else "NONE","supporting_row_ids":json.dumps([target["row_id"]]),"inference_limit":"direct link is attributable but not ownership proof"})
    write_csv_rows(output/"merged_attribution_relationships.csv",list(relationships[0]),relationships)
    gates=[]; roles=[]; gaps=[]
    for domain in ALLOWED_DOMAINS:
        supporting=1 if domain=="vocotviptv.com" else 0; ids=[target["row_id"]] if supporting else sorted({y for x in merged if x["target_domain"]==domain for y in json.loads(x["supporting_row_ids"])})
        ids=ids or ["NO_PRESERVED_EVIDENCE_ROW"]
        gates.append({"domain":domain,"identity_strong_count":0,"identity_supporting_count":supporting,"independent_category_count":supporting,
            "first_party_evidence":domain=="vocotviptv.com","convergence":False,"material_conflicts":False,"operator_gate":"FAIL","related_domain_gate":"FAIL",
            "result":"INSUFFICIENT_EVIDENCE_TO_RESOLVE_IDENTITY","supporting_row_ids":json.dumps(ids)})
        roles.append({"domain":domain,"final_role":"UNRESOLVED","confidence":"HIGH_ABSTENTION","decision":"INSUFFICIENT_EVIDENCE_TO_RESOLVE_IDENTITY",
            "official_domain_confirmed":False,"supporting_row_ids":json.dumps(ids)})
        gaps.append({"domain":domain,"current_role":"UNRESOLVED","missing_evidence":"IDENTITY_STRONG plus two independent attributable categories and convergence","supporting_row_ids":json.dumps(ids)})
    write_csv_rows(output/"merged_attribution_gate_trace.csv",list(gates[0]),gates); write_csv_rows(output/"merged_domain_role_classification.csv",list(roles[0]),roles); write_csv_rows(output/"merged_domain_identity_gap_matrix.csv",list(gaps[0]),gaps)
    names={"vocotviptv.com":"merged_vocotviptv_dossier.md","vocotvusa.net":"merged_vocotvusa_dossier.md","vocotv.ai":"merged_vocotvai_dossier.md","vocoiptv.com":"merged_vocoiptv_dossier.md"}
    for domain,name in names.items():
        count=sum(x["target_domain"]==domain for x in merged); extra=" Root capture adds a first-party WhatsApp contact and exact policy/contact URLs." if domain=="vocotviptv.com" else ""
        (output/name).write_text(f"# Merged dossier: {domain}\n\nRole: UNRESOLVED. Decision: INSUFFICIENT_EVIDENCE_TO_RESOLVE_IDENTITY.\n\nMerged rows assigned: {count}.{extra}\n\nNo official-domain or verified-owner conclusion is permitted.\n",encoding="utf-8")
    budget={"decision":"TWO_FINAL_ACCESSES_HIGH_VALUE","remaining_budget_units":2,"do_not_use_now":True,"priorities":[
        {"priority":1,"access_id":"access_vocotviptv_com_legal","url":"https://www.vocotviptv.com/terms/","identity_value_reason":"highest chance of named legal entity or operator terms"},
        {"priority":2,"access_id":"access_vocotviptv_com_privacy","url":"https://www.vocotviptv.com/privacy-policy/","identity_value_reason":"high chance of controller, company or jurisdiction identity"}],
        "not_prioritized":{"access_id":"access_vocotviptv_com_contact","reason":"root capture already preserves WhatsApp contact; marginal identity value is lower"},
        "warning":"No access authorized or executed in this offline evaluation"}
    write_json(output/"remaining_budget_decision.json",budget)
    unique=len(counts); strong=0; supporting=1; attributable=sum(x["attribution_strength"]=="IDENTITY_SUPPORTING" for x in relationships)
    metrics={"mode":"MERGED_OFFLINE_EVALUATION","historical_tavily_internal_results":59,"historical_http_captures":3,"repair_http_captures":1,
        "input_normalized_rows":62,"merged_normalized_rows":len(merged),"unique_exact_urls":len({x['source_url'] for x in merged}),"unique_canonical_urls":unique,"duplicate_canonical_groups":len(duplicate_rows),
        "independence_groups":len(groups),"identity_strong_signals":strong,"identity_supporting_signals":supporting,"attributable_supporting_relationships":attributable,
        "domain_roles":{"vocotviptv.com":"UNRESOLVED","vocotvusa.net":"UNRESOLVED","vocotv.ai":"UNRESOLVED","vocoiptv.com":"UNRESOLVED"},
        "remaining_budget_units":2,"network_calls_added":0,"tavily_calls_added":0,"credential_reads":0,"official_domain_emitted":False}
    write_json(output/"merged_metrics.json",metrics)
    report=(f"# Merged external verification report\n\nMode: MERGED_OFFLINE_EVALUATION. Rows: {len(merged)}; unique canonical URLs: {unique}.\n\n"
        "The root repair capture confirms exact `/terms/`, `/privacy-policy/`, and `/contact/` links, WhatsApp contact, self-declared Organization schema, analytics, and external checkout links. It does not provide a named legal owner.\n\n"
        "The three failed repairs are REDIRECT_CHAIN_INCOMPLETE: two requests and two redirect hops occurred; the third URL was calculated but not requested.\n\n"
        "All four domains remain UNRESOLVED under V4. Decision: INSUFFICIENT_EVIDENCE_TO_RESOLVE_IDENTITY.\n\n"
        "Budget decision: TWO_FINAL_ACCESSES_HIGH_VALUE, prioritizing terms then privacy. No network use is authorized by this report.\n")
    (output/"merged_external_verification_report.md").write_text(report,encoding="utf-8")
    (output/"runner_final_fix_validation.md").write_text("# Runner final fix validation\n\nThe runner separates physical attempts from redirect hops, preserves REDIRECT_CHAIN_INCOMPLETE, records final_url_requested and reason_class, gates projected budget, and emits execution-specific repair verdicts. The merged evaluation is offline and source-immutable.\n",encoding="utf-8")
    after={name:recursive_directory_fingerprint(path) for name,path in sources.items()}
    unchanged=all(before[x]["aggregate_sha256"]==after[x]["aggregate_sha256"] for x in sources)
    write_json(output/"merged_integrity_manifest.json",{"mode":"MERGED_OFFLINE_EVALUATION","sources_before":before,"sources_after":after,"all_sources_unchanged":unchanged,
        "artifacts":merged_artifact_names(),"created_at":now_iso(),"self_hash_excluded":True})
    return {**metrics,"output":str(output),"source_hashes":{x:before[x]["aggregate_sha256"] for x in sources},"all_sources_unchanged":unchanged,
        "budget_decision":budget["decision"],"verdict":"TEV1_MERGED_OFFLINE_EVALUATION_COMPLETE" if unchanged else "TEV1_MERGED_OFFLINE_EVALUATION_BLOCKED_BY_INTEGRITY"}

def completed_final_access_runs(source_evaluation: Path) -> list[Path]:
    """Return completed sibling runs without reading credentials or touching network."""
    completed = []
    for candidate in sorted(source_evaluation.parent.glob("targeted_external_verification_v1_final_two_access_run_*")):
        metrics_path = candidate / "final_access_metrics.json"
        if not metrics_path.is_file():
            continue
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        if (metrics.get("verdict") == "TEV1_FINAL_TWO_ACCESS_COMPLETED"
                and int(metrics.get("combined_budget_units", -1)) >= MAX_EXTERNAL_ACCESSES
                and int(metrics.get("remaining_after_execution", -1)) == 0):
            completed.append(candidate)
    return completed

def voco_network_budget_exhausted(output_base: Path = OUTPUT_BASE) -> bool:
    """Treat a durable completed final run as the global Voco 40/40 network lock."""
    for candidate in sorted(output_base.glob("targeted_external_verification_v1_final_two_access_run_*")):
        metrics_path = candidate / "final_access_metrics.json"
        if not metrics_path.is_file(): continue
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        if (metrics.get("verdict") == "TEV1_FINAL_TWO_ACCESS_COMPLETED"
                and int(metrics.get("combined_budget_units", -1)) == MAX_EXTERNAL_ACCESSES
                and int(metrics.get("remaining_after_execution", -1)) == 0):
            return True
    return False

def validate_final_two_accesses(source_evaluation: Path, urls: list[str], combined_limit: int, max_final_http_attempts: int,
                                enforce_completion_guard: bool = True) -> dict[str, Any]:
    if not source_evaluation.is_dir(): raise ValueError(f"source evaluation does not exist: {source_evaluation}")
    if tuple(urls) != FINAL_TWO_URLS:
        raise ValueError(f"final URL list must match exactly and in order: {FINAL_TWO_URLS}")
    if len(urls) != len(set(urls)): raise ValueError("duplicate final URLs are prohibited")
    if max_final_http_attempts != 2: raise ValueError("--max-final-http-attempts must equal exactly 2")
    if enforce_completion_guard:
        completed = completed_final_access_runs(source_evaluation)
        if completed:
            raise ValueError(f"budget exhausted at 40/40; completed final accesses cannot be repeated: {completed[0]}")
    metrics=json.loads((source_evaluation/"merged_metrics.json").read_text(encoding="utf-8"))
    remaining=int(metrics.get("remaining_budget_units",-1)); historical=combined_limit-remaining
    if historical != 38 or remaining != 2: raise ValueError(f"historical budget integrity mismatch: consumed={historical}, remaining={remaining}")
    planned=len(urls); combined=historical+planned
    if planned != 2 or combined > combined_limit: raise ValueError(f"final access budget blocked: {historical}+{planned}>{combined_limit}")
    merged_integrity=json.loads((source_evaluation/"merged_integrity_manifest.json").read_text(encoding="utf-8"))
    if not merged_integrity.get("all_sources_unchanged"): raise RuntimeError("merged source integrity is not proven")
    return {"source_fingerprint":recursive_directory_fingerprint(source_evaluation),"embedded_source_hashes":{
            x:p["aggregate_sha256"] for x,p in merged_integrity["sources_before"].items()},
        "historical_budget_units":historical,"planned_final_http_attempts":planned,"combined_budget_units":combined,
        "combined_limit":combined_limit,"remaining_after_execution":combined_limit-combined,"budget_gate":"PASS","urls":urls}

def final_closure_artifact_names() -> list[str]:
    return [
        "final_terms_forensic_inventory.json", "final_privacy_forensic_inventory.json",
        "final_legal_identity_signals.csv", "final_contact_and_jurisdiction_signals.csv",
        "final_payment_and_crossdomain_relations.csv", "final_template_and_placeholder_audit.csv",
        "final_merged_normalized_external_evidence.csv", "final_evidence_independence_groups.csv",
        "final_attribution_relationships.csv", "final_attribution_gate_trace.csv",
        "final_domain_role_classification.csv", "final_domain_identity_gap_matrix.csv",
        "final_vocotviptv_dossier.md", "final_vocotvusa_dossier.md", "final_vocotvai_dossier.md",
        "final_vocoiptv_dossier.md", "final_voco_family_closure_report.md",
        "final_method_reuse_protocol.md", "final_metrics.json", "final_integrity_manifest.json",
        "runner_closure_validation.md",
    ]

def _forensic_page(content: str) -> dict[str, Any]:
    parser = RootCaptureParser(); parser.feed(content)
    clean = lambda value: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", value))).strip()
    headings = [clean(x) for x in re.findall(r"(?is)<h[1-3][^>]*>(.*?)</h[1-3]>", content)]
    text = re.sub(r"\s+", " ", " ".join(parser.text)).strip()
    return {"title": html_title(content), "headings": headings, "links": list(dict.fromkeys(parser.links)),
            "visible_text_sha256": sha256_text(text), "updated_dates": re.findall(r"Updated as of:\s*([^<]+)", content, re.I)}

def final_offline_closure(merged_dir: Path, final_run_dir: Path, output: Path,
                          immutable_sources: dict[str, Path]) -> dict[str, Any]:
    """Build the definitive Voco closure from preserved files only; no external integrations are loaded."""
    if output.exists(): raise ValueError(f"final closure output already exists: {output}")
    for name, path in {**immutable_sources, "merged_evaluation": merged_dir, "final_two_accesses": final_run_dir}.items():
        if not path.is_dir(): raise ValueError(f"missing immutable source {name}: {path}")
    sources = {**immutable_sources, "merged_evaluation": merged_dir, "final_two_accesses": final_run_dir}
    before = {name: recursive_directory_fingerprint(path) for name, path in sources.items()}
    metrics = json.loads((final_run_dir / "final_access_metrics.json").read_text(encoding="utf-8"))
    if metrics.get("verdict") != "TEV1_FINAL_TWO_ACCESS_COMPLETED" or metrics.get("combined_budget_units") != 40 or metrics.get("remaining_after_execution") != 0:
        raise ValueError("final access completion or 40/40 budget integrity mismatch")
    raw = [obj for _, _, obj in read_jsonl(final_run_dir / "final_access_raw_evidence.jsonl")]
    expected = {
        "final_http_80ec9ac102d47aaa3171b849": "914519a584b3abfba16c23ba362ce011a5478c513676749f2184dc3c614de990",
        "final_http_1fa871718eaa215ec5a38519": "fb3e305648cad95d606488c6569967e4e6d987b1ec080935ac355e6dac99947c",
    }
    by_id = {x.get("row_id"): x for x in raw}
    if set(by_id) != set(expected) or any(by_id[row]["content_sha256"] != digest for row, digest in expected.items()):
        raise ValueError("final raw evidence row IDs or content hashes do not match authorization")
    terms = by_id["final_http_80ec9ac102d47aaa3171b849"]
    privacy = by_id["final_http_1fa871718eaa215ec5a38519"]
    term_page, privacy_page = _forensic_page(terms["content"]), _forensic_page(privacy["content"])
    if "{Your Business Country}" not in terms["content"] or "tvplansiptvstore.com/terms.html" not in terms["content"]:
        raise ValueError("expected Terms template provenance markers absent")
    if "tvplansiptvstore.com/privacy-policy.html" not in privacy["content"]:
        raise ValueError("expected Privacy template provenance marker absent")
    output.mkdir(parents=True)
    term_id, privacy_id = terms["row_id"], privacy["row_id"]
    common_limit = "Self-declared brand wording and generic pronouns do not identify a legal entity."
    terms_inventory = {
        "source_run":"final_two_accesses", "source_artifact":"final_access_raw_evidence.jsonl", "row_id":term_id,
        "supporting_row_ids":[term_id], "requested_url":terms["requested_url"], "final_url":terms["final_url"],
        "status_code":terms["status_code"], "content_sha256":terms["content_sha256"], **term_page,
        "effective_date":None, "updated_date":"September 14, 2025", "company_name":None, "legal_entity":None,
        "trade_name":"VocoTV (self-asserted brand)", "operator":None, "owner":None,
        "contracting_party":"VocoTV wording only; no named legal entity", "service_provider":"VocoTV brand assertion",
        "merchant":None, "seller":None, "reseller":None, "affiliate":None,
        "jurisdiction":None, "governing_law":"{Your Business Country}'s laws (unresolved placeholder)",
        "address":None, "postal_address":None, "country":None, "city":None, "business_registry":None,
        "company_number":None, "vat":None, "ein":None, "tax_number":None,
        "email":"Cloudflare-obfuscated placeholder; address not recoverable from preserved visible text",
        "telephone":None, "whatsapp":"+212714633888", "payment_methods":"unspecified payment method",
        "billing_entity":None, "payment_processor":None,
        "refund_policy":"Cancellation at any point; refunds delegated to /refund-policy/",
        "cancellation":"Auto-renewal unless canceled; cancellation stated as available at any point",
        "liability":"Service as-is; VocoTV brand disclaims direct, indirect and consequential damages",
        "copyright":"VocoTV © 2025 (brand footer only)", "mentioned_domains":["vocotviptv.com","VocoTV.com","tvplansiptvstore.com"],
        "vibeflixtv_mentions":[], "operator_owner_provider_seller_phrases":["contract between User and VocoTV", "Service provided by VocoTV"],
        "placeholders":["{Your Business Country}", "[email protected]"],
        "template_indicators":["Mirrored from tvplansiptvstore.com/terms.html", "generic jurisdiction placeholder"],
        "contradictions":["canonical uses vocotviptv.com while OpenGraph/JSON-LD use VocoTV.com", "governing-law country is unresolved"],
        "classification":"LEGAL_TEMPLATE_ONLY", "observation_type":"OBSERVED_FACT", "inference":"operational VocoTV-branded legal surface",
        "inference_limit":common_limit, "provenance_sections":["Agreement & Acceptance","Payment & Billing","Refund & Cancellation Policy","Governing Law","Contact Information","footer","HTML mirror comment"]}
    privacy_inventory = {
        "source_run":"final_two_accesses", "source_artifact":"final_access_raw_evidence.jsonl", "row_id":privacy_id,
        "supporting_row_ids":[privacy_id], "requested_url":privacy["requested_url"], "final_url":privacy["final_url"],
        "status_code":privacy["status_code"], "content_sha256":privacy["content_sha256"], **privacy_page,
        "updated_date":"September 14, 2025", "data_controller":None, "data_processor":None, "business_name":None,
        "legal_entity":None, "operator":None, "owner":None, "contact_person":None, "privacy_contact":"WhatsApp +212714633888",
        "dpo":None, "email":"Cloudflare-obfuscated placeholder; address not recoverable", "telephone":None,
        "address":None, "country":None, "jurisdiction":None, "gdpr":False, "ccpa":False, "uk_gdpr":False,
        "legal_bases":["consent","legitimate interests","performance of a contract"],
        "providers":["generic third-party vendors/service providers/agents"], "payment_processors":["unnamed payment processor"],
        "hosting_providers":[], "analytics_providers":["Google Analytics"], "cookies":"functional cookies and comparable tracking tools",
        "international_transfers":None, "retention":"only as required for stated purposes, subject to legal/tax/accounting needs",
        "user_rights":["access","rectification","erasure","opt-out"], "third_party_links":[],
        "mentioned_domains":["vocotviptv.com","tvplansiptvstore.com"], "vibeflixtv_mentions":[], "whatsapp":"+212714633888",
        "placeholders":["[email protected]"], "template_indicators":["Mirrored from tvplansiptvstore.com/privacy-policy.html","generic we/our wording","unnamed payment processor"],
        "inconsistencies":["policy describes payment processor but does not name it or the controller"],
        "classification":"PRIVACY_TEMPLATE_ONLY", "observation_type":"OBSERVED_FACT", "inference":"VocoTV-branded privacy practices are asserted",
        "inference_limit":"We, our company and website-owner wording are not treated as a named controller.",
        "provenance_sections":["Data We Collect","Legal Bases for Processing","Data Retention","Cookies & Tracking Technologies","Third-Party Services","Your Data Protection Rights","Contact Us","HTML mirror comment"]}
    write_json(output/"final_terms_forensic_inventory.json", terms_inventory)
    write_json(output/"final_privacy_forensic_inventory.json", privacy_inventory)
    signal_fields=["signal_id","page","signal_class","evidence_category","observed_fact","inference","inference_limit","fragment_or_section","supporting_row_ids","independence_group"]
    legal_rows=[
        {"signal_id":"terms_brand_contract","page":"TERMS","signal_class":"BRAND_SELF_ASSERTION","evidence_category":"CONTRACT_WORDING","observed_fact":"Text calls the agreement a contract between User and VocoTV","inference":"VocoTV is presented as the service brand/counterparty label","inference_limit":common_limit,"fragment_or_section":"1. Agreement & Acceptance","supporting_row_ids":json.dumps([term_id]),"independence_group":"final_terms_brand_claim"},
        {"signal_id":"terms_provider_claim","page":"TERMS","signal_class":"BRAND_SELF_ASSERTION","evidence_category":"SERVICE_PROVIDER","observed_fact":"Definition states service is provided by VocoTV","inference":"brand asserts service provision","inference_limit":common_limit,"fragment_or_section":"2. Definitions","supporting_row_ids":json.dumps([term_id]),"independence_group":"final_terms_brand_claim"},
        {"signal_id":"terms_no_legal_entity","page":"TERMS","signal_class":"UNRESOLVED","evidence_category":"LEGAL_IDENTITY","observed_fact":"No legal entity, registration or tax identifier is named","inference":"none","inference_limit":"absence does not prove no entity exists","fragment_or_section":"entire preserved page","supporting_row_ids":json.dumps([term_id]),"independence_group":"final_terms_legal_gap"},
        {"signal_id":"privacy_no_controller","page":"PRIVACY","signal_class":"UNRESOLVED","evidence_category":"DATA_CONTROLLER","observed_fact":"No data controller or legal entity is named","inference":"none","inference_limit":"generic we wording is not an entity","fragment_or_section":"entire preserved page","supporting_row_ids":json.dumps([privacy_id]),"independence_group":"final_privacy_controller_gap"},
        {"signal_id":"privacy_brand_claim","page":"PRIVACY","signal_class":"BRAND_SELF_ASSERTION","evidence_category":"PRIVACY_PRACTICE","observed_fact":"VocoTV/we asserts collection and processing practices","inference":"brand presents itself as handling data","inference_limit":"does not name the controller","fragment_or_section":"Introduction; sections 1-10","supporting_row_ids":json.dumps([privacy_id]),"independence_group":"final_privacy_brand_claim"},
    ]
    write_csv_rows(output/"final_legal_identity_signals.csv", signal_fields, legal_rows)
    contact_rows=[
        {"signal_id":"terms_whatsapp","page":"TERMS","signal_class":"CONTACT_ONLY","evidence_category":"WHATSAPP","observed_fact":"WhatsApp +212714633888 is linked","inference":"support contact","inference_limit":"country-code/contact does not establish jurisdiction or ownership","fragment_or_section":"13. Contact Information; footer","supporting_row_ids":json.dumps([term_id]),"independence_group":"voco_whatsapp_contact"},
        {"signal_id":"privacy_whatsapp","page":"PRIVACY","signal_class":"CONTACT_ONLY","evidence_category":"WHATSAPP","observed_fact":"WhatsApp +212714633888 is used for policy inquiries and rights requests","inference":"privacy contact channel","inference_limit":"not a named DPO or controller","fragment_or_section":"Introduction; 8. Rights; 10. Contact","supporting_row_ids":json.dumps([privacy_id]),"independence_group":"voco_whatsapp_contact"},
        {"signal_id":"terms_jurisdiction_placeholder","page":"TERMS","signal_class":"CONFLICT","evidence_category":"JURISDICTION","observed_fact":"Governing law contains {Your Business Country}","inference":"jurisdiction was not completed","inference_limit":"no country may be inferred","fragment_or_section":"12. Governing Law","supporting_row_ids":json.dumps([term_id]),"independence_group":"final_terms_template"},
        {"signal_id":"privacy_no_jurisdiction","page":"PRIVACY","signal_class":"UNRESOLVED","evidence_category":"JURISDICTION","observed_fact":"No jurisdiction, postal address or country is provided","inference":"none","inference_limit":"user-location wording is non-attributable","fragment_or_section":"entire preserved page","supporting_row_ids":json.dumps([privacy_id]),"independence_group":"final_privacy_controller_gap"},
    ]
    write_csv_rows(output/"final_contact_and_jurisdiction_signals.csv", signal_fields, contact_rows)
    relation_fields=["relationship_id","source_domain","target","relation_type","signal_class","observed_fact","inference_limit","supporting_row_ids","independence_group"]
    relations=[
        {"relationship_id":"terms_refund_internal","source_domain":"vocotviptv.com","target":"https://www.vocotviptv.com/refund-policy/","relation_type":"FIRST_PARTY_INTERNAL_LINK","signal_class":"NO_IDENTITY_VALUE","observed_fact":"Terms links refund policy","inference_limit":"internal link is not ownership evidence","supporting_row_ids":json.dumps([term_id]),"independence_group":"final_terms_links"},
        {"relationship_id":"terms_vocotv_com_metadata","source_domain":"vocotviptv.com","target":"VocoTV.com","relation_type":"CROSS_DOMAIN_METADATA_REFERENCE","signal_class":"CROSS_DOMAIN_RELATION","observed_fact":"Terms OpenGraph/JSON-LD references VocoTV.com","inference_limit":"metadata reference does not prove common ownership","supporting_row_ids":json.dumps([term_id]),"independence_group":"final_terms_metadata"},
        {"relationship_id":"terms_template_origin","source_domain":"vocotviptv.com","target":"tvplansiptvstore.com","relation_type":"HTML_MIRROR_PROVENANCE","signal_class":"CONFLICT","observed_fact":"HTML comment says page mirrored from tvplansiptvstore.com/terms.html","inference_limit":"copy provenance does not establish current operator","supporting_row_ids":json.dumps([term_id]),"independence_group":"final_terms_template"},
        {"relationship_id":"privacy_template_origin","source_domain":"vocotviptv.com","target":"tvplansiptvstore.com","relation_type":"HTML_MIRROR_PROVENANCE","signal_class":"CONFLICT","observed_fact":"HTML comment says page mirrored from tvplansiptvstore.com/privacy-policy.html","inference_limit":"copy provenance does not establish current operator","supporting_row_ids":json.dumps([privacy_id]),"independence_group":"final_privacy_template"},
        {"relationship_id":"privacy_payment_processor","source_domain":"vocotviptv.com","target":"UNNAMED_PAYMENT_PROCESSOR","relation_type":"PAYMENT_PROCESSOR_REFERENCE","signal_class":"PAYMENT_RELATION","observed_fact":"Privacy says payment data is stored by our payment processor","inference_limit":"processor and billing entity are unnamed","supporting_row_ids":json.dumps([privacy_id]),"independence_group":"final_privacy_payment"},
        {"relationship_id":"root_vibeflixtv_checkout","source_domain":"vocotviptv.com","target":"wp.vibeflixtv.com","relation_type":"PAYMENT_OR_CHECKOUT_LINK","signal_class":"CROSS_DOMAIN_RELATION","observed_fact":"Preserved root capture links pricing/checkout to wp.vibeflixtv.com","inference_limit":"checkout link does not prove ownership, merchant identity or common control","supporting_row_ids":json.dumps(["repair_http_77ef11f9e7bc683add08b682"]),"independence_group":"root_checkout"},
    ]
    write_csv_rows(output/"final_payment_and_crossdomain_relations.csv", relation_fields, relations)
    template_rows=[x for x in relations if x["signal_class"]=="CONFLICT"] + [
        {"relationship_id":"terms_country_placeholder","source_domain":"vocotviptv.com","target":"{Your Business Country}","relation_type":"PLACEHOLDER","signal_class":"LEGAL_TEMPLATE_ONLY","observed_fact":"Unreplaced governing-law placeholder","inference_limit":"jurisdiction unresolved","supporting_row_ids":json.dumps([term_id]),"independence_group":"final_terms_template"},
        {"relationship_id":"shared_email_placeholder","source_domain":"vocotviptv.com","target":"[email protected]","relation_type":"OBFUSCATED_PLACEHOLDER","signal_class":"NO_IDENTITY_VALUE","observed_fact":"Visible email placeholder occurs in both final pages","inference_limit":"no email address inferred","supporting_row_ids":json.dumps([term_id,privacy_id]),"independence_group":"voco_footer_template"},
    ]
    write_csv_rows(output/"final_template_and_placeholder_audit.csv", relation_fields, template_rows)
    with (merged_dir/"merged_normalized_external_evidence.csv").open(encoding="utf-8") as handle: merged=list(csv.DictReader(handle))
    merged_fields=list(merged[0])
    for page, row, parsed, category, group in (("Terms",terms,term_page,"FINAL_TERMS_CAPTURE","final_terms_capture"),("Privacy",privacy,privacy_page,"FINAL_PRIVACY_CAPTURE","final_privacy_capture")):
        merged.append({"source_run":"final_two_accesses","source_artifact":"final_access_raw_evidence.jsonl","row_id":row["row_id"],
            "supporting_row_ids":json.dumps([row["row_id"]]),"provenance":"PRESERVED_FINAL_HTTP_CAPTURE","source_type":"FINAL_TWO_ACCESS",
            "target_domain":"vocotviptv.com","source_url":row["final_url"],"canonical_url":canonical_url(row["final_url"]),"title":parsed["title"],
            "category":category,"first_party_or_third_party":"FIRST_PARTY","observed_fact":f"HTTP 200 {page} page preserved",
            "inference":"operational VocoTV-branded surface","inference_limit":"does not identify a legal entity or official domain",
            "independence_group":group,"attribution_strength":"NONE","is_duplicate":str(any(x["canonical_url"]==canonical_url(row["final_url"]) for x in merged))})
    write_csv_rows(output/"final_merged_normalized_external_evidence.csv", merged_fields, merged)
    groups={}
    for row in merged: groups.setdefault(row["independence_group"],[]).append(row)
    group_rows=[{"independence_group":gid,"member_count":len(rows),"row_ids":json.dumps([x["row_id"] for x in rows]),
        "source_types":json.dumps(sorted({x["source_type"] for x in rows})),"attribution_strengths":json.dumps(sorted({x["attribution_strength"] for x in rows})),
        "supporting_row_ids":json.dumps(sorted({rid for x in rows for rid in json.loads(x["supporting_row_ids"])}))} for gid,rows in sorted(groups.items())]
    write_csv_rows(output/"final_evidence_independence_groups.csv",list(group_rows[0]),group_rows)
    with (merged_dir/"merged_attribution_relationships.csv").open(encoding="utf-8") as handle: old_rel=list(csv.DictReader(handle))
    relationship_fields=list(old_rel[0])
    appended=[]
    for item in relations:
        appended.append({"relationship_id":item["relationship_id"],"source_domain":item["source_domain"],"target":item["target"],
            "relationship_type":item["relation_type"],"attribution_strength":"NONE","supporting_row_ids":item["supporting_row_ids"],"inference_limit":item["inference_limit"]})
    write_csv_rows(output/"final_attribution_relationships.csv",relationship_fields,old_rel+appended)
    support_ids={d:[] for d in ALLOWED_DOMAINS}
    for row in merged:
        support_ids[row["target_domain"]].extend(json.loads(row["supporting_row_ids"]))
    gates=[]; roles=[]; gaps=[]
    for domain in ALLOWED_DOMAINS:
        ids=sorted(set(support_ids[domain])) or ["NO_PRESERVED_EVIDENCE_ROW"]
        supporting=1 if domain=="vocotviptv.com" else 0
        gates.append({"domain":domain,"identity_strong_count":0,"identity_supporting_count":supporting,"independent_category_count":supporting,
            "first_party_evidence":domain=="vocotviptv.com","convergence":False,"material_conflicts":domain=="vocotviptv.com",
            "named_entity_gate":"FAIL","two_category_gate":"FAIL","convergence_gate":"FAIL","conflict_gate":"FAIL" if domain=="vocotviptv.com" else "PASS_NO_CONFLICT_OBSERVED",
            "attributable_domain_entity_gate":"FAIL","result":"INSUFFICIENT_EVIDENCE_TO_RESOLVE_IDENTITY","supporting_row_ids":json.dumps(ids)})
        roles.append({"domain":domain,"final_role":"UNRESOLVED","confidence":"HIGH_ABSTENTION","decision":"INSUFFICIENT_EVIDENCE_TO_RESOLVE_IDENTITY",
            "operational_surface_observed":domain=="vocotviptv.com","official_domain_confirmed":False,"supporting_row_ids":json.dumps(ids)})
        gaps.append({"domain":domain,"current_role":"UNRESOLVED","missing_evidence":"named IDENTITY_STRONG plus two independent attributable categories, convergence and attributable entity-domain relation",
            "conflicts":"template provenance and jurisdiction placeholder" if domain=="vocotviptv.com" else "none observed; evidence remains insufficient","supporting_row_ids":json.dumps(ids)})
    write_csv_rows(output/"final_attribution_gate_trace.csv",list(gates[0]),gates)
    write_csv_rows(output/"final_domain_role_classification.csv",list(roles[0]),roles)
    write_csv_rows(output/"final_domain_identity_gap_matrix.csv",list(gaps[0]),gaps)
    dossier_names={"vocotviptv.com":"final_vocotviptv_dossier.md","vocotvusa.net":"final_vocotvusa_dossier.md","vocotv.ai":"final_vocotvai_dossier.md","vocoiptv.com":"final_vocoiptv_dossier.md"}
    for domain,name in dossier_names.items():
        extra=("An HTTP 200 branded root, Terms and Privacy surface is observed. Terms names only the VocoTV brand, Privacy names no controller, "
               "the governing-law country is a placeholder, and mirror provenance conflicts prevent attribution. The root preserves a checkout link to wp.vibeflixtv.com; this is a relation, not ownership proof."
               if domain=="vocotviptv.com" else "No new final capture concerns this domain; the prior merged evidence remains insufficient for attribution.")
        (output/name).write_text(f"# Final dossier: {domain}\n\nRole: UNRESOLVED. Identity gate: FAIL. Official-domain conclusion: prohibited.\n\n{extra}\n",encoding="utf-8")
    verdict="VOCO_DOMAIN_FAMILY_UNRESOLVED_AFTER_TARGETED_VERIFICATION"
    report=(f"# Final Voco family closure\n\nVerdict: {verdict}.\n\n## Confirmed fact\n\nThe targeted process preserved 59 Tavily results, three original HTTP captures, one repair root capture and two final HTTP 200 captures. The final pages expose a VocoTV-branded service surface and WhatsApp +212714633888.\n\n## Controlled inference\n\nThe vocotviptv.com surface appears operational as a VocoTV-branded commercial site. A checkout relation to wp.vibeflixtv.com is observed.\n\n## Unresolved\n\nNo named legal entity, controller, owner, operator, merchant, billing entity, business registration or jurisdiction is attributable. Terms contains an unreplaced country placeholder; both pages preserve template-mirror provenance.\n\n## Prohibited conclusion\n\nNo official domain, verified owner or common ownership may be declared. Budget is 40/40, so no additional Voco network use is authorized.\n")
    (output/"final_voco_family_closure_report.md").write_text(report,encoding="utf-8")
    (output/"final_method_reuse_protocol.md").write_text("# V4 method reuse protocol\n\n1. Select one family from offline corpus and freeze source hashes.\n2. Deduplicate by canonical URL while preserving acquisition artifacts and supporting row IDs.\n3. Separate brand, contact, template, payment, infrastructure and attributable identity signals.\n4. Require a named IDENTITY_STRONG signal, two independent categories, convergence, no material conflict, and a domain-entity relationship.\n5. Abstain when any gate fails; never promote brand, footer, analytics, checkout, pronouns or templates to identity.\n6. Prepare any later micro-pilot separately and require explicit authorization and a fresh budget.\n",encoding="utf-8")
    final_metrics={"mode":"FINAL_OFFLINE_CLOSURE","verdict":verdict,"historical_tavily_internal_results":59,"historical_http_captures":3,
        "repair_http_captures":1,"final_http_captures":2,"final_normalized_rows":len(merged),"unique_exact_urls":len({x["source_url"] for x in merged}),
        "unique_canonical_urls":len({x["canonical_url"] for x in merged}),"independence_groups":len(groups),"identity_strong_signals":0,
        "identity_supporting_signals":1,"conflicts":3,"combined_budget_units":40,"remaining_budget_units":0,"network_calls_added":0,
        "dns_calls_added":0,"tavily_calls_added":0,"credential_reads":0,"official_domain_emitted":False,
        "domain_roles":{d:"UNRESOLVED" for d in ALLOWED_DOMAINS}}
    write_json(output/"final_metrics.json",final_metrics)
    after={name:recursive_directory_fingerprint(path) for name,path in sources.items()}
    unchanged=all(before[name]["aggregate_sha256"]==after[name]["aggregate_sha256"] for name in sources)
    write_json(output/"final_integrity_manifest.json",{"mode":"FINAL_OFFLINE_CLOSURE","sources_before":before,"sources_after":after,
        "all_sources_unchanged":unchanged,"artifacts":final_closure_artifact_names(),"self_hash_excluded":True})
    (output/"runner_closure_validation.md").write_text("# Runner closure validation\n\n- Final completed sibling runs are detected locally before output or network initialization.\n- A completed 40/40 run blocks repetition of both final accesses.\n- Completed Tavily query checkpoints remain skipped; final closure performs no credential read or integration loading.\n- Counters represent physical requests; non-followed redirects are separate response events.\n- Every derived evidence row preserves supporting_row_ids.\n- OFFICIAL_DOMAIN is absent from valid roles and prohibited in closure outputs.\n",encoding="utf-8")
    return {**final_metrics,"output":str(output),"all_sources_unchanged":unchanged,
            "source_hashes":{name:before[name]["aggregate_sha256"] for name in sources}}

def project_final_access_budget(historical: int, planned: int, combined_limit: int) -> dict[str, Any]:
    combined=historical+planned
    return {"historical_budget_units":historical,"planned_final_http_attempts":planned,"combined_budget_units":combined,
        "combined_limit":combined_limit,"remaining_after_execution":combined_limit-combined,"budget_gate":"PASS" if planned<=2 and combined<=combined_limit else "BLOCK"}

def final_access_artifact_names() -> list[str]:
    return ["final_access_authorization.json","final_access_plan.json","final_access_preflight_report.md","final_access_checkpoint.json",
        "final_access_http_log.jsonl","final_access_raw_evidence.jsonl","final_access_normalized_evidence.csv","final_access_redirects.csv",
        "final_access_metrics.json","final_access_safety_audit.md","final_access_report.md","final_access_integrity_manifest.json"]

def final_access_future_output(path: Path) -> Path:
    name=path.name
    return path.with_name(name.replace("final_two_access_preflight","final_two_access_run") if "final_two_access_preflight" in name else name+"_execute")

def final_access_command(args: argparse.Namespace) -> str:
    urls=" ".join(f'--final-url "{x}"' for x in args.final_url)
    return (f'python .\\scripts\\run_targeted_external_verification_v1.py --execute --final-two-access-only --authorize-final-two-accesses '
        f'--source-evaluation-dir "{args.source_evaluation_dir}" --final-output-dir "{final_access_future_output(args.final_output_dir)}" '
        f'{urls} --max-final-http-attempts 2 --max-external-accesses 40 --timeout {args.timeout:g} --pause-seconds {args.pause_seconds:g}')

def initialize_final_access_output(output: Path, source: Path, validation: dict[str, Any], args: argparse.Namespace, mode: str) -> None:
    if output.exists(): raise ValueError(f"final output already exists: {output}")
    output.mkdir(parents=True)
    source_hash=validation["source_fingerprint"]["aggregate_sha256"]
    base={"mode":"FINAL_TWO_ACCESS","phase":mode,"source_evaluation_dir":str(source.resolve()),"source_evaluation_hash":source_hash,
        "authorized_urls":list(FINAL_TWO_URLS),"tavily_calls_added":0,"credential_reads":0,"official_domain_prohibited":True}
    write_json(output/"final_access_authorization.json",base)
    write_json(output/"final_access_plan.json",{**base,"ordered_requests":[{"order":i+1,"url":url,"max_requests":1,"follow_redirects":False} for i,url in enumerate(FINAL_TWO_URLS)],
        "historical_budget_units":validation["historical_budget_units"],"planned_final_http_attempts":2,"combined_budget_units":40,"combined_limit":40,"remaining_after_execution":0,"budget_gate":"PASS"})
    checkpoint={**base,"schema_version":"final_two_access_v1","accesses":{url:{"status":"PLANNED","attempts":0,"supporting_row_ids":[]} for url in FINAL_TWO_URLS},
        "historical_budget_units":38,"final_http_attempt_count":0,"redirect_response_count":0,"capture_count":0,"combined_budget_units":38,"remaining_budget_units":2}
    write_json_atomic(output/"final_access_checkpoint.json",checkpoint)
    for name in ("final_access_http_log.jsonl","final_access_raw_evidence.jsonl"): (output/name).write_text("",encoding="utf-8")
    write_empty_csv(output/"final_access_normalized_evidence.csv",["row_id","requested_url","final_url","status_code","title","content_sha256","content_bytes","supporting_row_ids"])
    write_empty_csv(output/"final_access_redirects.csv",["row_id","requested_url","status_code","location","classification","supporting_row_ids"])
    metrics={**base,"historical_budget_units":38,"planned_final_http_attempts":2,"final_http_attempt_count":0,"combined_budget_units":38,
        "combined_projected_budget_units":40,"combined_limit":40,"remaining_budget_units":2,"remaining_after_execution_projected":0,
        "budget_gate":"PASS","http_attempts_added":0,"dns_attempts_added":0,"redirects_followed":0}
    write_json(output/"final_access_metrics.json",metrics)
    command=final_access_command(args)
    (output/"final_access_preflight_report.md").write_text(f"# Final two-access preflight\n\nMode: FINAL_TWO_ACCESS / PREFLIGHT.\n\nURLs, in order:\n\n1. `{FINAL_TWO_URLS[0]}`\n2. `{FINAL_TWO_URLS[1]}`\n\nBudget: 38 + 2 = 40/40 (PASS).\n\n```powershell\n{command}\n```\n\nWARNING: command not executed. Use a new output directory and do not use --resume or --run-dir.\n",encoding="utf-8")
    (output/"final_access_safety_audit.md").write_text("# Final access safety audit\n\nPreflight only: zero HTTP, DNS, sockets, Tavily, credentials, redirects followed, forms, APK and authenticated access.\n",encoding="utf-8")
    (output/"final_access_report.md").write_text("# Final access report\n\nPreflight complete. No real request executed.\n",encoding="utf-8")
    after=recursive_directory_fingerprint(source)
    write_json(output/"final_access_integrity_manifest.json",{**base,"embedded_historical_source_hashes":validation["embedded_source_hashes"],
        "source_before":validation["source_fingerprint"],"source_after":after,"source_unchanged":source_hash==after["aggregate_sha256"],
        "artifacts":final_access_artifact_names(),"created_at":now_iso()})

def sanitize_location(value: str) -> str:
    return re.sub(r"(?i)(token|key|password|authorization)=[^&\s]+",r"\1=[REDACTED]",str(value))[:1000]

def execute_final_two_accesses(output: Path, args: argparse.Namespace) -> None:
    import urllib.error
    import urllib.request
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl): return None
    opener=urllib.request.build_opener(NoRedirect); checkpoint=json.loads((output/"final_access_checkpoint.json").read_text(encoding="utf-8"))
    for url in FINAL_TWO_URLS:
        if checkpoint["final_http_attempt_count"]>=2: break
        request=urllib.request.Request(url,method="GET",headers={"User-Agent":"IPTV-Final-Two-Access/1.0"})
        checkpoint["final_http_attempt_count"]+=1; checkpoint["combined_budget_units"]+=1; checkpoint["remaining_budget_units"]-=1
        started=now_iso(); status_code=None; body=b""; location=""; final_url=""; status="FAILED"; reason_class="UNRESOLVED"
        try:
            with opener.open(request,timeout=args.timeout) as response:
                status_code=response.status; body=response.read(2_000_000); final_url=response.geturl() if hasattr(response,"geturl") else url
                status="COMPLETED" if 200<=status_code<300 else "FAILED"; reason_class="CAPTURED" if status=="COMPLETED" else f"HTTP_{status_code}"
        except urllib.error.HTTPError as exc:
            status_code=exc.code; location=sanitize_location(exc.headers.get("Location","") if exc.headers else "")
            if status_code in (301,302,303,307,308): status="REDIRECT_NOT_FOLLOWED_BUDGET_LIMIT"; reason_class="REDIRECT_RESPONSE"
            else: status="FAILED"; reason_class=f"HTTP_{status_code}"
        except (urllib.error.URLError,TimeoutError) as exc:
            status="FAILED"; reason_class=sanitize_url_error(exc)["reason_class"]
        row_id="final_http_"+sha256_text(url+str(status_code)+hashlib.sha256(body).hexdigest())[:24]
        raw={"row_id":row_id,"source_type":"FINAL_TWO_ACCESS","requested_url":url,"final_url":final_url,"status_code":status_code,
            "location":location,"status":status,"reason_class":reason_class,"content_sha256":hashlib.sha256(body).hexdigest() if body else "",
            "content_bytes":len(body),"content":body.decode("utf-8",errors="replace") if body else "","supporting_row_ids":[row_id]}
        append_jsonl(output/"final_access_raw_evidence.jsonl",raw); append_jsonl(output/"final_access_http_log.jsonl",{k:v for k,v in raw.items() if k!="content"})
        checkpoint["accesses"][url]={"status":status,"attempts":1,"status_code":status_code,"final_url":final_url,"reason_class":reason_class,"supporting_row_ids":[row_id],"completed_at":now_iso(),"started_at":started}
        if status=="COMPLETED": checkpoint["capture_count"]+=1
        if status=="REDIRECT_NOT_FOLLOWED_BUDGET_LIMIT": checkpoint["redirect_response_count"]+=1
        write_json_atomic(output/"final_access_checkpoint.json",checkpoint)

def finalize_final_two_accesses(output: Path, source: Path, validation: dict[str, Any]) -> str:
    checkpoint=json.loads((output/"final_access_checkpoint.json").read_text(encoding="utf-8")); raw=[x[2] for x in read_jsonl(output/"final_access_raw_evidence.jsonl")]
    normalized=[]; redirects=[]
    for x in raw:
        normalized.append({"row_id":x["row_id"],"requested_url":x["requested_url"],"final_url":x["final_url"],"status_code":x["status_code"],
            "title":html_title(x.get("content","")),"content_sha256":x["content_sha256"],"content_bytes":x["content_bytes"],"supporting_row_ids":json.dumps(x["supporting_row_ids"])})
        if x["status"]=="REDIRECT_NOT_FOLLOWED_BUDGET_LIMIT": redirects.append({"row_id":x["row_id"],"requested_url":x["requested_url"],"status_code":x["status_code"],
            "location":x["location"],"classification":x["status"],"supporting_row_ids":json.dumps(x["supporting_row_ids"])})
    write_csv_rows(output/"final_access_normalized_evidence.csv",["row_id","requested_url","final_url","status_code","title","content_sha256","content_bytes","supporting_row_ids"],normalized)
    write_csv_rows(output/"final_access_redirects.csv",["row_id","requested_url","status_code","location","classification","supporting_row_ids"],redirects)
    statuses=[checkpoint["accesses"][x]["status"] for x in FINAL_TWO_URLS]; completed=sum(x=="COMPLETED" for x in statuses)
    verdict="TEV1_FINAL_TWO_ACCESS_COMPLETED" if completed==2 else ("TEV1_FINAL_TWO_ACCESS_PARTIAL" if completed or any(x=="REDIRECT_NOT_FOLLOWED_BUDGET_LIMIT" for x in statuses) else "TEV1_FINAL_TWO_ACCESS_FAILED")
    metrics={"mode":"FINAL_TWO_ACCESS","phase":"EXECUTE","historical_budget_units":38,"planned_final_http_attempts":2,"final_http_attempt_count":checkpoint["final_http_attempt_count"],
        "combined_budget_units":checkpoint["combined_budget_units"],"combined_limit":40,"remaining_after_execution":checkpoint["remaining_budget_units"],
        "capture_count":checkpoint["capture_count"],"redirect_response_count":checkpoint["redirect_response_count"],"redirects_followed":0,
        "tavily_calls_added":0,"credential_reads":0,"verdict":verdict}
    write_json(output/"final_access_metrics.json",metrics)
    (output/"final_access_safety_audit.md").write_text(f"# Final access safety audit\n\nExactly {checkpoint['final_http_attempt_count']} HTTP requests; redirects followed: 0; Tavily: 0; credential reads: 0.\n",encoding="utf-8")
    (output/"final_access_report.md").write_text(f"# Final access report\n\nVerdict: {verdict}. Requests: {checkpoint['final_http_attempt_count']}/2. Captures: {completed}/2. Redirect responses were recorded and not followed.\n",encoding="utf-8")
    manifest=json.loads((output/"final_access_integrity_manifest.json").read_text(encoding="utf-8")); after=recursive_directory_fingerprint(source)
    manifest["source_after"]=after; manifest["source_unchanged"]=after["aggregate_sha256"]==validation["source_fingerprint"]["aggregate_sha256"]; write_json(output/"final_access_integrity_manifest.json",manifest)
    if not manifest["source_unchanged"]: return "TEV1_FINAL_TWO_ACCESS_BLOCKED_BY_INTEGRITY"
    return verdict

def run_final_two_access(args: argparse.Namespace,preflight_only: bool) -> dict[str, Any]:
    validation=validate_final_two_accesses(args.source_evaluation_dir,args.final_url,args.max_external_accesses,args.max_final_http_attempts)
    initialize_final_access_output(args.final_output_dir,args.source_evaluation_dir,validation,args,"PREFLIGHT" if preflight_only else "EXECUTE")
    verdict="TEV1_FINAL_TWO_ACCESS_READY_FOR_AUTHORIZATION"
    if not preflight_only:
        execute_final_two_accesses(args.final_output_dir,args); verdict=finalize_final_two_accesses(args.final_output_dir,args.source_evaluation_dir,validation)
    after=recursive_directory_fingerprint(args.source_evaluation_dir)
    if after["aggregate_sha256"]!=validation["source_fingerprint"]["aggregate_sha256"]: verdict="TEV1_FINAL_TWO_ACCESS_BLOCKED_BY_INTEGRITY"
    return {"output":str(args.final_output_dir),"source_hash_before":validation["source_fingerprint"]["aggregate_sha256"],"source_hash_after":after["aggregate_sha256"],
        "source_unchanged":after["aggregate_sha256"]==validation["source_fingerprint"]["aggregate_sha256"],"urls":args.final_url,
        "historical_budget_units":38,"planned_final_http_attempts":2,"combined_budget_units":40,"combined_limit":40,"remaining_after_execution":0,
        "tavily_calls_added":0,"credential_reads":0,"http_attempts_added":0 if preflight_only else 2,"verdict":verdict}
def artifact_names() -> list[str]:
    return ["authorization_and_scope.json", "preflight_report.md", "external_access_log.jsonl", "query_plan.json", "query_log.jsonl", "checkpoint.json", "raw_external_evidence.jsonl",
            *CSV_SCHEMAS, "vocotviptv_external_dossier.md", "vocotvusa_external_dossier.md", "vocotvai_external_dossier.md", "vocoiptv_external_dossier.md",
            "targeted_external_verification_metrics.json", "targeted_external_verification_report.md", "safety_and_scope_audit.md", "integrity_manifest.json"]

def initialize_artifacts(run_dir: Path, args: argparse.Namespace, queries: list[dict[str, Any]], accesses: list[dict[str, Any]], integrity: dict[str, Any], mode: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=False)
    write_json(run_dir / "authorization_and_scope.json", {"mode": mode, "execute_authorized": False if mode != "EXECUTE" else args.confirm_credit_use,
        "authorized_domains": list(args.target_domain), "no_official_domain_claim": True, "created_at": now_iso()})
    write_json(run_dir / "query_plan.json", {"mode": mode, "queries": queries, "direct_access_plan": accesses})
    write_json(run_dir / "checkpoint.json", load_checkpoint(run_dir / "checkpoint.json"))
    for name in ("external_access_log.jsonl", "query_log.jsonl", "raw_external_evidence.jsonl"):
        (run_dir / name).write_text("", encoding="utf-8")
    for name, fields in CSV_SCHEMAS.items(): write_empty_csv(run_dir / name, fields)
    for name, domain in (("vocotviptv_external_dossier.md", "vocotviptv.com"), ("vocotvusa_external_dossier.md", "vocotvusa.net"), ("vocotvai_external_dossier.md", "vocotv.ai"), ("vocoiptv_external_dossier.md", "vocoiptv.com")):
        (run_dir / name).write_text(f"# External dossier: {domain}\n\nStatus: UNRESOLVED. No external evidence collected.\n", encoding="utf-8")
    metrics = {"mode": mode, "planned_tavily_queries": len(queries), "planned_direct_accesses": len(accesses), "tavily_calls": 0, "http_calls": 0, "dns_calls": 0,
               "max_tavily_queries": args.max_tavily_queries, "max_external_accesses": args.max_external_accesses, "max_results": MAX_RESULTS}
    write_json(run_dir / "targeted_external_verification_metrics.json", metrics)
    command = powershell_command(args)
    report = f"# Targeted external verification V1\n\nMode: {mode}\n\nPlanned Tavily queries: {len(queries)}\n\nPlanned direct accesses: {len(accesses)}\n\nFuture PowerShell command:\n\n```powershell\n{command}\n```\n\nWARNING: DO NOT EXECUTE THIS COMMAND TWICE. Resume with --resume and --run-dir only.\n"
    (run_dir / "preflight_report.md").write_text(report, encoding="utf-8")
    (run_dir / "targeted_external_verification_report.md").write_text(report, encoding="utf-8")
    (run_dir / "safety_and_scope_audit.md").write_text("# Safety and scope audit\n\nOffline mode: zero credential reads, Tavily calls, HTTP, DNS, browser, form, APK, and authenticated access.\n", encoding="utf-8")
    write_json(run_dir / "integrity_manifest.json", {"created_at": now_iso(), "protected_integrity_before": integrity, "artifacts": artifact_names()})

def regenerate_execution_reports(run_dir: Path, mode: str, checkpoint: dict[str, Any]) -> None:
    metrics = {"mode": mode, "tavily_query_count": checkpoint.get("tavily_query_count", 0), "tavily_attempt_count": checkpoint.get("tavily_attempt_count", 0),
        "logical_direct_access_count": checkpoint.get("logical_direct_access_count", 0), "physical_http_attempt_count": checkpoint.get("physical_http_attempt_count", 0),
        "redirect_event_count": checkpoint.get("redirect_event_count", 0), "capture_event_count": checkpoint.get("capture_event_count", 0),
        "log_event_count": checkpoint.get("log_event_count", 0), "total_budget_units_consumed": checkpoint.get("total_budget_units_consumed", 0),
        "credential_read": bool(checkpoint.get("credential_read", False)), "authenticated_accesses": 0, "forms_submitted": 0, "apk_downloaded_or_executed": 0,
        "secrets_exposed": 0, "dns_implicit": mode == "EXECUTE" and checkpoint.get("physical_http_attempt_count", 0) > 0}
    write_json(run_dir / "targeted_external_verification_metrics.json", metrics)
    report = (f"# Targeted external verification V1\n\nMode: {mode}.\n\nTavily attempts: {metrics['tavily_attempt_count']}.\n\n"
        f"Physical HTTP attempts: {metrics['physical_http_attempt_count']}.\n\nTotal budget units consumed: {metrics['total_budget_units_consumed']}.\n")
    (run_dir / "targeted_external_verification_report.md").write_text(report, encoding="utf-8")
    safety = ("# Safety and scope audit\n\n"
        f"Mode: {mode}. Credential read: {'yes' if metrics['credential_read'] else 'no'} (value never recorded). "
        f"Tavily calls: {metrics['tavily_attempt_count']}. HTTP attempts: {metrics['physical_http_attempt_count']}. "
        f"Implicit DNS: {'yes' if metrics['dns_implicit'] else 'no'}. Authenticated accesses: 0. Forms: 0. APK: 0. Secrets exposed: 0.\n")
    (run_dir / "safety_and_scope_audit.md").write_text(safety, encoding="utf-8")

def run_acquisition(queries: list[dict[str, Any]], accesses: list[dict[str, Any]], checkpoint: dict[str, Any], run_dir: Path, args: argparse.Namespace) -> None:
    if not args.http_repair_only:
        checkpoint["credential_read"] = True
        execute_tavily(queries, checkpoint, run_dir, args)
    execute_direct_accesses(accesses, checkpoint, run_dir, args)

def powershell_command(args: argparse.Namespace) -> str:
    targets = " ".join(f'--target-domain "{d}"' for d in args.target_domain)
    return (f'python .\\scripts\\run_targeted_external_verification_v1.py --execute --confirm-credit-use {targets} '
            f'--output-root "{args.output_root}" --max-tavily-queries {args.max_tavily_queries} --max-external-accesses {args.max_external_accesses} '
            f'--timeout {args.timeout:g} --pause-seconds {args.pause_seconds:g} --search-depth {args.search_depth}')

def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--offline-replay", action="store_true")
    mode.add_argument("--http-repair-preflight", action="store_true")
    mode.add_argument("--merged-offline-evaluation", action="store_true")
    mode.add_argument("--final-two-access-preflight", action="store_true")
    p.add_argument("--confirm-credit-use", action="store_true")
    p.add_argument("--output-root", type=Path, default=OUTPUT_BASE)
    p.add_argument("--max-tavily-queries", type=int, default=12)
    p.add_argument("--max-external-accesses", type=int, default=40)
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--pause-seconds", type=float, default=1.0)
    p.add_argument("--max-http-attempts", type=int, default=3)
    p.add_argument("--max-redirect-hops", type=int, default=2)
    p.add_argument("--search-depth", choices=("basic", "advanced"), default="advanced")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--run-dir", type=Path)
    p.add_argument("--target-domain", action="append", type=validate_domain, default=[])
    p.add_argument("--source-run-dir", type=Path)
    p.add_argument("--recovery-output-dir", type=Path)
    p.add_argument("--repair-output-dir", type=Path)
    p.add_argument("--repair-access-id", action="append", default=[])
    p.add_argument("--recovery-run-dir", type=Path)
    p.add_argument("--repair-run-dir", type=Path)
    p.add_argument("--merged-output-dir", type=Path)
    p.add_argument("--source-evaluation-dir", type=Path)
    p.add_argument("--final-output-dir", type=Path)
    p.add_argument("--final-url", action="append", default=[])
    p.add_argument("--max-final-http-attempts", type=int, default=2)
    p.add_argument("--http-repair-only", action="store_true")
    p.add_argument("--authorize-http-repair", action="store_true")
    p.add_argument("--final-two-access-only", action="store_true")
    p.add_argument("--authorize-final-two-accesses", action="store_true")
    return p

def validate_args(args: argparse.Namespace) -> None:
    args.target_domain = list(dict.fromkeys(args.target_domain or ALLOWED_DOMAINS))
    repair_mode = args.http_repair_preflight or args.http_repair_only
    final_mode = args.final_two_access_preflight or args.final_two_access_only
    if args.execute and not (args.http_repair_only or args.final_two_access_only) and not args.confirm_credit_use:
        raise ValueError("--execute requires --confirm-credit-use")
    if args.offline_replay and (not args.source_run_dir or not args.recovery_output_dir):
        raise ValueError("--offline-replay requires --source-run-dir and --recovery-output-dir")
    if args.merged_offline_evaluation and (not args.source_run_dir or not args.recovery_run_dir or not args.repair_run_dir or not args.merged_output_dir):
        raise ValueError("--merged-offline-evaluation requires all three source directories and --merged-output-dir")
    if args.recovery_output_dir and not args.offline_replay:
        raise ValueError("--recovery-output-dir is valid only with --offline-replay")
    if args.http_repair_only and not (args.execute and args.authorize_http_repair):
        raise ValueError("HTTP repair requires --execute and --authorize-http-repair")
    if args.http_repair_preflight and (args.execute or args.authorize_http_repair):
        raise ValueError("repair preflight must not use --execute or --authorize-http-repair")
    if repair_mode:
        if args.resume or args.run_dir: raise ValueError("derived HTTP repair rejects --resume and --run-dir")
        if not args.source_run_dir: raise ValueError("derived HTTP repair requires --source-run-dir")
        if not args.repair_output_dir: raise ValueError("derived HTTP repair requires --repair-output-dir")
        if not args.repair_access_id: raise ValueError("derived HTTP repair requires --repair-access-id")
    elif args.source_run_dir or args.repair_output_dir or args.repair_access_id:
        if not (args.offline_replay or args.merged_offline_evaluation): raise ValueError("repair paths and IDs require derived HTTP repair mode")
    if not args.merged_offline_evaluation and (args.recovery_run_dir or args.repair_run_dir or args.merged_output_dir):
        raise ValueError("merged evaluation paths require --merged-offline-evaluation")
    if args.final_two_access_only and not (args.execute and args.authorize_final_two_accesses):
        raise ValueError("final two-access execution requires --execute and --authorize-final-two-accesses")
    if args.final_two_access_preflight and (args.execute or args.authorize_final_two_accesses):
        raise ValueError("final two-access preflight must not use execution authorization")
    if final_mode:
        if args.resume or args.run_dir: raise ValueError("final two-access mode rejects --resume and --run-dir")
        if not args.source_evaluation_dir: raise ValueError("final two-access mode requires --source-evaluation-dir")
        if not args.final_output_dir: raise ValueError("final two-access mode requires --final-output-dir")
        if not args.final_url: raise ValueError("final two-access mode requires exactly two --final-url values")
    elif args.source_evaluation_dir or args.final_output_dir or args.final_url:
        raise ValueError("final access paths and URLs require final two-access mode")
    if not repair_mode and args.resume != bool(args.run_dir):
        raise ValueError("--resume and --run-dir must be used together")
    if not 1 <= args.max_tavily_queries <= MAX_TAVILY_QUERIES: raise ValueError("--max-tavily-queries must be 1..12")
    if not 1 <= args.max_external_accesses <= MAX_EXTERNAL_ACCESSES: raise ValueError("--max-external-accesses must be 1..40")
    if args.timeout <= 0 or args.pause_seconds < 0: raise ValueError("timeout must be positive and pause non-negative")
    if args.max_http_attempts < 1 or args.max_redirect_hops < 0: raise ValueError("HTTP attempts must be positive and redirect hops non-negative")

def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        validate_args(args)
        network_oriented_preflight = args.preflight_only or args.http_repair_preflight
        if (args.execute and not args.final_two_access_only or network_oriented_preflight) and voco_network_budget_exhausted():
            print("ERROR=Voco network budget exhausted at 40/40; no new network authorization is available",file=sys.stderr)
            print("TEV1_NETWORK_BLOCKED_BY_BUDGET")
            return 4
        if args.final_two_access_preflight or args.final_two_access_only:
            try:
                result=run_final_two_access(args,preflight_only=args.final_two_access_preflight)
            except RuntimeError as exc:
                print(f"ERROR={exc}",file=sys.stderr); print("TEV1_FINAL_TWO_ACCESS_BLOCKED_BY_INTEGRITY"); return 3
            except ValueError as exc:
                verdict="TEV1_FINAL_TWO_ACCESS_BLOCKED_BY_BUDGET" if "budget" in str(exc).casefold() else "TEV1_FINAL_TWO_ACCESS_BLOCKED_BY_SCOPE"
                print(f"ERROR={exc}",file=sys.stderr); print(verdict); return 4
            print(json.dumps(result,indent=2)); print(result["verdict"])
            return 0 if result["verdict"] in {"TEV1_FINAL_TWO_ACCESS_READY_FOR_AUTHORIZATION","TEV1_FINAL_TWO_ACCESS_COMPLETED"} else 2
        if args.merged_offline_evaluation:
            result=merged_offline_evaluation(args.source_run_dir,args.recovery_run_dir,args.repair_run_dir,args.merged_output_dir)
            print(json.dumps(result,indent=2)); print(result["verdict"]); return 0 if result["all_sources_unchanged"] else 3
        if args.http_repair_preflight or args.http_repair_only:
            try:
                result = run_derived_repair(args, preflight_only=args.http_repair_preflight)
            except ValueError as exc:
                verdict = "TEV1_DERIVED_HTTP_REPAIR_BLOCKED_BY_BUDGET" if "budget" in str(exc).casefold() else "TEV1_DERIVED_HTTP_REPAIR_BLOCKED_BY_SCOPE"
                print(f"ERROR={exc}", file=sys.stderr); print(verdict); return 4
            print(json.dumps(result, indent=2)); print(result["verdict"])
            return 0 if result["verdict"] in {"TEV1_DERIVED_HTTP_REPAIR_READY_FOR_AUTHORIZATION", "TEV1_DERIVED_HTTP_REPAIR_COMPLETED"} else 2
        if args.offline_replay:
            result = offline_replay(args.source_run_dir, args.recovery_output_dir)
            print(json.dumps(result, indent=2)); print("TEV1_ACQUISITION_PRESERVED_REPAIR_READY" if result["source_unchanged"] else "TEV1_BLOCKED_BY_INTEGRITY")
            return 0 if result["source_unchanged"] else 3
        integrity = verify_integrity()
        if not integrity["all_match"]:
            print(VERDICT_INTEGRITY); return 3
        queries = build_query_plan(args.target_domain, args.search_depth, args.timeout)
        accesses = build_access_plan(args.target_domain)
        validation = validate_plan(queries, accesses, args)
        if not validation["valid"]:
            print(json.dumps(validation, indent=2)); print(VERDICT_SCOPE); return 4
        mode = "EXECUTE" if args.execute else ("PREFLIGHT_ONLY" if args.preflight_only else "DRY_RUN")
        if args.resume:
            run_dir = args.run_dir
            checkpoint = load_checkpoint(run_dir / "checkpoint.json")
        else:
            prefix = "targeted_external_verification_v1_run" if args.execute else "targeted_external_verification_v1_dry_run"
            run_dir = args.output_root / f"{prefix}_{stamp()}"
            initialize_artifacts(run_dir, args, queries, accesses, integrity, mode)
            checkpoint = load_checkpoint(run_dir / "checkpoint.json")
        if args.execute:
            run_acquisition(queries, accesses, checkpoint, run_dir, args)
            regenerate_execution_reports(run_dir, "EXECUTE", checkpoint)
        after = verify_integrity()
        manifest = json.loads((run_dir / "integrity_manifest.json").read_text(encoding="utf-8"))
        manifest["protected_integrity_after"] = after
        manifest["self_sha256_excluded"] = True
        write_json(run_dir / "integrity_manifest.json", manifest)
        print(f"RUN_DIR={run_dir}")
        print(f"PLANNED_TAVILY_QUERIES={len(queries)}")
        print(f"PLANNED_DIRECT_ACCESSES={len(accesses)}")
        print(f"HISTORICAL_QUERIES_EXCLUDED={len(validation['historical_queries_detected_and_excluded'])}")
        print(f"FUTURE_POWERSHELL_COMMAND={powershell_command(args)}")
        print("WARNING=DO_NOT_EXECUTE_REAL_COMMAND_TWICE")
        print(VERDICT_READY if not args.execute else VERDICT_FIXES)
        return 0
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR={type(exc).__name__}: {exc}", file=sys.stderr)
        print(VERDICT_FIXES)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
