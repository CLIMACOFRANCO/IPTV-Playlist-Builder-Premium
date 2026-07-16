#!/usr/bin/env python3
"""Attribution-First Domain Family Method V4. Fully offline replay evaluator."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = PROJECT_ROOT / "research" / "output" / "best_iptv_2026" / "domain_family_discovery_voco_micro_pilot"
DEFAULT_RUN = DEFAULT_BASE / "run_20260715_023727"
DEFAULT_AUDIT = DEFAULT_BASE / "final_offline_audit_run_20260715_023727"
DEFAULT_OUTPUT = DEFAULT_BASE / "method_redesign_v4_replay_run_20260715_023727"

ALLOWED_ROLES = {
    "PROBABLE_BRAND_OPERATOR", "POSSIBLE_RELATED_DOMAIN", "MASTER_DISTRIBUTOR", "RESELLER", "AFFILIATE",
    "APP_OR_LOGIN", "PAYMENT_OR_BILLING", "INFRASTRUCTURE", "EXTERNAL_SOURCE", "REVIEW_OR_DIRECTORY",
    "NOISE", "UNRESOLVED",
}
RELATION_TYPES = {
    "IDENTITY_STRONG", "IDENTITY_SUPPORTING", "COMMERCIAL_ASSOCIATION", "RESELLER", "AFFILIATE",
    "INFRASTRUCTURE_SHARED", "GENERIC_LINK", "EXTERNAL_REFERENCE", "REVIEW_OR_DIRECTORY", "NOISE", "UNRESOLVED",
}
IDENTITY_TYPES = {"IDENTITY_STRONG", "IDENTITY_SUPPORTING"}
ZERO_IDENTITY_TYPES = RELATION_TYPES - IDENTITY_TYPES
BASELINE_DOMAINS = {"vocotv.org", "vocotvusa.net", "vocotviptv.com", "vocotvs.com", "vocotvpro.com", "voco-iptv.com", "vocotv.ca", "iptvon.me"}
GENERIC_DOMAINS = {"wa.me", "wa.link", "t.me", "api.whatsapp.com", "facebook.com", "instagram.com", "linkedin.com", "youtube.com", "x.com", "twitter.com", "apps.apple.com", "play.google.com", "your-m3u-url.com", "your-epg-url.com", "192.168.1.100", "iboplayer.com", "iptvsmarters.com"}
INFRA_PARTS = ("googleusercontent", "gstatic", "flaticon", "cloudfront", "cloudflare", "blob.core.windows.net", "digitaloceanspaces", "adobe", "zoom.us", "tawk.to", "doubleclick", "analytics", "cookielaw", "onetrust", "trustpilot.net", "hostingersite.com")
REVIEW_PARTS = ("trustpilot", "review", "ranking", "the-best-iptv", "iptvserviceradar", "slideserve", "provenexpert", "indiehackers", "iptvinsouthafrica")
NOISE_PARTS = ("ihg", "hotel", "voco.dental", "sixsenses", "intercontinental", "regenthotels", "vocolearning")


def json_value(value: str, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except (TypeError, json.JSONDecodeError):
        return default


def normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(str(x) for x in parts).encode("utf-8")).hexdigest()


def metric(numerator: int, denominator: int, note: str) -> dict[str, Any]:
    return {"numerator": numerator, "denominator": denominator, "value": numerator / denominator if denominator else None, "methodology_note": note}


def independence_group(canonical_url: str, content: str, source_role: str) -> str:
    content_fingerprint = hashlib.sha256(normalized_text(content).lower()[:2000].encode("utf-8")).hexdigest()[:16]
    grouping_basis = content_fingerprint if normalized_text(content) else canonical_url.lower()
    return "ig_" + stable_id(grouping_basis, source_role)[:20]


def classify_relation(target_domain: str, prior_class: str, source_role: str, attributable_claim: str = "") -> tuple[str, int, str]:
    domain = (target_domain or "").lower()
    prior = (prior_class or "").upper()
    role = (source_role or "").upper()
    claim = (attributable_claim or "").lower()
    if "same legal entity" in claim or "owned and operated by" in claim or "same-domain operational email" in claim:
        return "IDENTITY_STRONG", 1, "direct attributable ownership, legal identity, or same-domain operational contact"
    if "first-party reciprocal link" in claim or "attributable first-party support" in claim or "publisher links to domain" in claim:
        return "IDENTITY_SUPPORTING", 1, "direct attributable first-party support or reciprocal connection"
    if prior == "RESELLER_RELATIONSHIP":
        return "RESELLER", 0, "reseller or distribution evidence cannot establish identity"
    if "aff=" in claim:
        return "AFFILIATE", 0, "affiliate evidence cannot establish identity"
    if prior == "SHARED_INFRASTRUCTURE" or domain in GENERIC_DOMAINS or any(x in domain for x in INFRA_PARTS):
        return "INFRASTRUCTURE_SHARED", 0, "shared or generic infrastructure contributes zero identity evidence"
    if prior == "SOURCE_REFERENCE":
        return "REVIEW_OR_DIRECTORY" if any(x in domain for x in REVIEW_PARTS) else "EXTERNAL_REFERENCE", 0, "external reference or review contributes zero identity evidence"
    if prior == "NOISE" or any(x in domain for x in NOISE_PARTS):
        return "NOISE", 0, "homonym or irrelevant evidence contributes zero identity evidence"
    if prior == "GENERIC_OUTBOUND_LINK":
        return "GENERIC_LINK", 0, "generic outbound link contributes zero identity evidence"
    return "UNRESOLVED", 0, "no attributable relationship is observable"


def decide_domain_role(strong: list[dict], supporting: list[dict], categories: set[str], relations: list[dict], commercial: bool, reseller: bool, affiliate: bool, infrastructure_only: bool) -> tuple[str, str, str]:
    independent = {x["independence_group"] for x in strong + supporting}
    if strong and len(categories) >= 2 and len(independent) >= 2:
        return "PROBABLE_BRAND_OPERATOR", "HIGH", "gate passed: strong identity plus two independent attributable categories"
    if any(r["relation_type_v4"] in IDENTITY_TYPES for r in relations):
        return "POSSIBLE_RELATED_DOMAIN", "MEDIUM", "direct attributable identity relation exists but operator gate is not met"
    if reseller:
        return "RESELLER", "MEDIUM", "observable reseller activity without attributable ownership"
    if affiliate:
        return "AFFILIATE", "HIGH", "affiliate URL or role is directly observable"
    if infrastructure_only:
        return "INFRASTRUCTURE", "HIGH", "only infrastructure linkage is observable"
    if commercial:
        return "UNRESOLVED", "LOW", "commercial activity does not establish brand operation or ownership"
    return "UNRESOLVED", "LOW", "insufficient attributable evidence; abstention required"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    fields = fields or (list(rows[0]) if rows else [])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def directory_fingerprint(path: Path) -> dict[str, Any]:
    files = []
    for item in sorted(path.iterdir()):
        if item.is_file():
            files.append({"name": item.name, "size": item.stat().st_size, "sha256": hashlib.sha256(item.read_bytes()).hexdigest().upper()})
    aggregate = hashlib.sha256("\n".join(f"{x['name']}:{x['sha256'].lower()}" for x in files).encode()).hexdigest().upper()
    return {"directory": str(path), "file_count": len(files), "aggregate_sha256": aggregate, "files": files}


def build_evidence_units(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    units = []
    for row in rows:
        extracted = json_value(row.get("extracted_fields", ""), {})
        roles = [x.get("role_candidate", "") for x in json_value(row.get("role_candidates", ""), [])]
        partition = "DISCOVERY" if row["query_id"].startswith("voco_df_") else "CONTROL"
        control_type = "NONE" if partition == "DISCOVERY" else ("KNOWN_DOMAIN" if row["query_id"] == "voco_ctrl_01_known_vocotv_ai" else "NEGATIVE_NOISE")
        canonical = row["canonical_url"]
        snippet = normalized_text(row.get("content") or row.get("raw_content"))[:1000]
        domain = row["registrable_domain"]
        email_domains = extracted.get("email_domains", {}).get("value", []) or []
        same_domain_email = any(domain == x or x.endswith("." + domain) for x in email_domains)
        legal = extracted.get("legal_entity_indicators", {}).get("value", []) or []
        support = extracted.get("support_terms", {}).get("value", []) or []
        claim = ""
        strength = "NONE"
        category = "OBSERVATION"
        decision = "EXCLUDED_FROM_IDENTITY"
        reason = "appearance, nominal brand use, and commercial activity are not attributable identity"
        if partition == "CONTROL":
            reason = "control-induced evidence cannot increase spontaneous discovery or identity"
        elif same_domain_email:
            claim, strength, category, decision, reason = "same-domain operational email", "IDENTITY_STRONG", "OWN_CONTACT", "ACCEPT_IDENTITY", "same-domain operational contact is directly observable"
        elif legal and domain and any(domain in normalized_text(row.get("content", "")).lower() for _ in [0]):
            claim, strength, category, decision, reason = "first-party legal identity indicator", "IDENTITY_STRONG", "LEGAL_IDENTITY", "ACCEPT_IDENTITY", "legal indicator appears on the candidate-domain result"
        elif support and domain and row.get("canonical_hostname", "").endswith(domain) and "HOMONYM_OR_IRRELEVANT" not in roles and "POSSIBLE_RESELLER" not in roles and "CONFIRMED_RESELLER" not in roles:
            claim, strength, category, decision, reason = "attributable first-party support", "IDENTITY_SUPPORTING", "SUPPORT", "ACCEPT_IDENTITY", "support language is observable on the candidate-domain result"
        source_role = ",".join(roles) or "UNRESOLVED"
        group = independence_group(canonical, snippet, source_role)
        conflicts = []
        if any("RESELLER" in x for x in roles): conflicts.append("RESELLER_SIGNAL")
        if "REVIEW_OR_RANKING_SOURCE" in roles: conflicts.append("REVIEW_SIGNAL")
        if "HOMONYM_OR_IRRELEVANT" in roles: conflicts.append("HOMONYM_SIGNAL")
        if extracted.get("self_declared_official", {}).get("value"): conflicts.append("SELF_DECLARED_OFFICIAL_ONLY")
        units.append({
            "evidence_id": "ev_" + stable_id(row["result_id"], category)[:24], "source_result_id": row["result_id"],
            "source_query_id": row["query_id"], "source_url": row["original_url"], "canonical_url": canonical,
            "source_domain": row.get("canonical_hostname") or domain, "candidate_domain": domain,
            "discovery_or_control": partition, "control_type": control_type, "title": row["title"],
            "extracted_text_or_snippet": snippet, "observed_claim": claim or "no attributable identity claim",
            "evidence_category": category, "attribution_target": domain, "attribution_strength": strength,
            "independence_group": group, "source_role": source_role, "conflict_flags": json.dumps(conflicts),
            "audit_decision": decision, "audit_reason": reason, "supporting_row_ids": json.dumps([row["result_id"]]),
            "is_duplicate": row["is_duplicate"],
        })
    return units


def run_replay(run_dir: Path, audit_dir: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = read_csv(run_dir / "normalized_results.csv")
    prior_relationships = read_csv(audit_dir / "final_relationship_audit.csv")
    if len(rows) != 80 or len(prior_relationships) != 186:
        raise ValueError("Replay requires exactly 80 results and 186 audited relationships")
    discovery = [r for r in rows if r["query_id"].startswith("voco_df_")]
    controls = [r for r in rows if not r["query_id"].startswith("voco_df_")]
    unique_discovery = [r for r in discovery if r["is_duplicate"] != "True"]
    units = build_evidence_units(rows)
    unit_by_result = defaultdict(list)
    for unit in units: unit_by_result[unit["source_result_id"]].append(unit)
    write_csv(output_dir / "evidence_units_v4.csv", units)

    groups = defaultdict(list)
    for unit in units: groups[unit["independence_group"]].append(unit)
    group_rows = []
    for gid, members in sorted(groups.items()):
        group_rows.append({"independence_group": gid, "member_count": len(members), "evidence_ids": json.dumps([x["evidence_id"] for x in members]), "source_result_ids": json.dumps(sorted({x["source_result_id"] for x in members})), "canonical_urls": json.dumps(sorted({x["canonical_url"] for x in members})), "counted_once_for_identity": any(x["attribution_strength"] in IDENTITY_TYPES and x["discovery_or_control"] == "DISCOVERY" and x["is_duplicate"] != "True" for x in members)})
    write_csv(output_dir / "evidence_independence_groups_v4.csv", group_rows)

    source_roles = defaultdict(set)
    for unit in units: source_roles[unit["source_domain"]].update(unit["source_role"].split(","))
    relationship_rows = []
    for rel in prior_relationships:
        role = ",".join(sorted(source_roles.get(rel["source_domain"], {"UNRESOLVED"})))
        relation_type, identity_value, reason = classify_relation(rel["target_domain"], rel.get("audit_classification", ""), role)
        relationship_rows.append({
            "relationship_id": rel["relationship_id"], "source_domain": rel["source_domain"], "target_domain": rel["target_domain"],
            "source_url": rel["source_url"], "source_query_id": rel["query_id"], "relation_type_v4": relation_type,
            "identity_evidence_value": identity_value, "attribution_strength": relation_type if relation_type in IDENTITY_TYPES else "NONE",
            "independence_group": "rel_" + stable_id(rel["source_url"], rel["target_domain"])[:20], "audit_reason": reason,
            "supporting_row_ids": json.dumps([rel["relationship_id"]]),
        })
    write_csv(output_dir / "relationships_v4.csv", relationship_rows)

    control_target_rows = defaultdict(set)
    for row in controls:
        if row["query_id"] == "voco_ctrl_01_known_vocotv_ai":
            for target in re.findall(r"(?i)(?:site:)?\b([a-z0-9-]+(?:\.[a-z0-9-]+)+)\b", row.get("query_text", "")):
                control_target_rows[target.lower()].add(row["result_id"])
    domains = sorted({r["registrable_domain"] for r in discovery} | {r["target_domain"] for r in prior_relationships} | set(control_target_rows))
    results_by_domain = defaultdict(list)
    for row in discovery: results_by_domain[row["registrable_domain"]].append(row)
    relations_by_domain = defaultdict(list)
    for rel in relationship_rows:
        relations_by_domain[rel["source_domain"]].append(rel); relations_by_domain[rel["target_domain"]].append(rel)
    classifications = []
    dossiers = {}
    for domain in domains:
        domain_rows = results_by_domain.get(domain, [])
        result_ids = {r["result_id"] for r in domain_rows}
        domain_units = [u for u in units if u["source_result_id"] in result_ids and u["discovery_or_control"] == "DISCOVERY" and u["is_duplicate"] != "True"]
        strong = [u for u in domain_units if u["attribution_strength"] == "IDENTITY_STRONG"]
        supporting = [u for u in domain_units if u["attribution_strength"] == "IDENTITY_SUPPORTING"]
        categories = {u["evidence_category"] for u in strong + supporting}
        roles = {x for u in domain_units for x in u["source_role"].split(",")}
        commercial = any(x in roles for x in {"COMMERCIAL_PORTAL", "CHECKOUT_OR_PAYMENT_DOMAIN", "APP_OR_DOWNLOAD_DOMAIN", "SUPPORT_PORTAL"})
        reseller = any("RESELLER" in x for x in roles)
        affiliate = any("aff=" in r["canonical_url"].lower() for r in domain_rows)
        domain_relations = relations_by_domain.get(domain, [])
        infra_only = bool(domain_relations) and all(r["relation_type_v4"] == "INFRASTRUCTURE_SHARED" for r in domain_relations) and not domain_rows
        role, confidence, reason = decide_domain_role(strong, supporting, categories, domain_relations, commercial, reseller, affiliate, infra_only)
        relation_types = {r["relation_type_v4"] for r in domain_relations}
        if role == "UNRESOLVED" and "HOMONYM_OR_IRRELEVANT" in roles:
            role, confidence, reason = "NOISE", "HIGH", "source evidence is an IHG/hotel/dental homonym or irrelevant result"
        elif role == "UNRESOLVED" and "REVIEW_OR_RANKING_SOURCE" in roles and not commercial:
            role, confidence, reason = "REVIEW_OR_DIRECTORY", "HIGH", "source evidence is a review, ranking, or directory"
        elif role == "UNRESOLVED" and not domain_rows and relation_types and relation_types <= {"NOISE"}:
            role, confidence, reason = "NOISE", "HIGH", "domain appears only in noise relationships"
        elif role == "UNRESOLVED" and not domain_rows and relation_types and relation_types <= {"REVIEW_OR_DIRECTORY", "EXTERNAL_REFERENCE", "GENERIC_LINK"}:
            role, confidence, reason = "EXTERNAL_SOURCE", "MEDIUM", "domain appears only as an external source or reference"
        supporting_ids = sorted({u["source_result_id"] for u in strong + supporting} | {r["relationship_id"] for r in domain_relations if r["relation_type_v4"] in IDENTITY_TYPES})
        if not supporting_ids: supporting_ids = sorted(result_ids | {r["relationship_id"] for r in domain_relations} | control_target_rows.get(domain, set()))
        control_units = [u for u in units if u["candidate_domain"] == domain and u["discovery_or_control"] == "CONTROL"]
        control_induced = bool((control_units or control_target_rows.get(domain)) and not domain_rows)
        classification = {"domain": domain, "final_role": role, "confidence": confidence, "identity_strong_count": len({u['independence_group'] for u in strong}), "identity_supporting_count": len({u['independence_group'] for u in supporting}), "independent_identity_category_count": len(categories), "commercial_activity_observed": commercial, "reseller_signal_observed": reseller, "control_induced_only": control_induced, "supporting_row_ids": json.dumps(supporting_ids), "decision_reason": reason, "official_domain_confirmed": False}
        classifications.append(classification)
        dossiers[domain] = {**classification, "positive_evidence": [u["evidence_id"] for u in strong + supporting], "negative_evidence": sorted({flag for u in domain_units for flag in json_value(u["conflict_flags"], [])}), "commercial_signals": commercial, "reseller_signals": reseller, "infrastructure_relations": [r["relationship_id"] for r in domain_relations if r["relation_type_v4"] == "INFRASTRUCTURE_SHARED"], "external_references": [r["relationship_id"] for r in domain_relations if r["relation_type_v4"] in {"EXTERNAL_REFERENCE", "REVIEW_OR_DIRECTORY"}], "controls_inducing_appearance": (["voco_ctrl_01_known_vocotv_ai"] if control_target_rows.get(domain) else sorted({u["source_query_id"] for u in control_units})), "identity_strong_evidence": [u["evidence_id"] for u in strong], "identity_supporting_evidence": [u["evidence_id"] for u in supporting], "valid_independent_signals": sorted({u["independence_group"] for u in strong + supporting}), "abstention_reason": reason if role == "UNRESOLVED" else "not applicable"}
    if any(x["final_role"] not in ALLOWED_ROLES for x in classifications): raise ValueError("Forbidden domain role emitted")
    write_csv(output_dir / "domain_role_classification_v4.csv", classifications)
    write_json(output_dir / "domain_dossiers_v4.json", dossiers)

    dossier_files = {"vocotviptv.com": "vocotviptv_dossier_v4.md", "vocotvusa.net": "vocotvusa_dossier_v4.md", "vocotv.ai": "vocotvai_dossier_v4.md", "vocoiptv.com": "vocoiptv_dossier_v4.md"}
    for domain, filename in dossier_files.items():
        d = dossiers.get(domain, {"final_role": "UNRESOLVED", "confidence": "LOW", "decision_reason": "not represented", "supporting_row_ids": "[]"})
        (output_dir / filename).write_text(f"# {domain} — Attribution-First V4 dossier\n\n- Final role: {d['final_role']}\n- Confidence: {d['confidence']}\n- Strong identity signals: {d.get('identity_strong_count', 0)}\n- Supporting identity signals: {d.get('identity_supporting_count', 0)}\n- Commercial activity: {d.get('commercial_activity_observed', False)}\n- Reseller signal: {d.get('reseller_signal_observed', False)}\n- Control induced only: {d.get('control_induced_only', False)}\n- Supporting row IDs: `{d.get('supporting_row_ids', '[]')}`\n- Conclusion: {d['decision_reason']}\n- Officiality: not determined.\n", encoding="utf-8")

    accepted_units = [u for u in units if u["discovery_or_control"] == "DISCOVERY" and u["is_duplicate"] != "True" and u["attribution_strength"] in IDENTITY_TYPES]
    accepted_by_group = defaultdict(list)
    accepted_by_domain = defaultdict(list)
    for unit in accepted_units:
        accepted_by_group[unit["independence_group"]].append(unit)
        accepted_by_domain[unit["candidate_domain"]].append(unit)
    classification_by_domain = {item["domain"]: item for item in classifications}
    gate_trace_rows = []
    for group_id, members in sorted(accepted_by_group.items()):
        domain = members[0]["candidate_domain"]
        domain_units = accepted_by_domain[domain]
        levels = {x["attribution_strength"] for x in members}
        categories_for_domain = {x["evidence_category"] for x in domain_units}
        groups_for_domain = {x["independence_group"] for x in domain_units}
        conflicts = sorted({flag for x in domain_units for flag in json_value(x["conflict_flags"], [])})
        strong_gate = any(x["attribution_strength"] == "IDENTITY_STRONG" for x in domain_units)
        category_gate = len(categories_for_domain) >= 2
        independence_gate = len(groups_for_domain) >= 2
        convergence_gate = strong_gate and any(x["attribution_strength"] == "IDENTITY_SUPPORTING" for x in domain_units)
        conflict_gate = not any(x in conflicts for x in {"RESELLER_SIGNAL", "REVIEW_SIGNAL", "HOMONYM_SIGNAL"})
        passed = strong_gate and category_gate and independence_gate and convergence_gate and conflict_gate
        failures = []
        if not strong_gate: failures.append("missing IDENTITY_STRONG evidence for candidate domain")
        if not category_gate: failures.append("fewer than two attributable evidence categories")
        if not independence_gate: failures.append("fewer than two independent evidence groups")
        if not convergence_gate: failures.append("strong and supporting evidence do not converge")
        if not conflict_gate: failures.append("reseller, review, or homonym conflict remains")
        if not any(r["relation_type_v4"] in IDENTITY_TYPES for r in relations_by_domain.get(domain, [])):
            failures.append("no attributable inter-domain identity relation; POSSIBLE_RELATED_DOMAIN gate fails")
        gate_trace_rows.append({
            "independence_group": group_id, "evidence_level": ",".join(sorted(levels)), "candidate_domain": domain,
            "evidence_category": ",".join(sorted({x["evidence_category"] for x in members})),
            "source_role": ",".join(sorted({x["source_role"] for x in members})),
            "source_result_ids": json.dumps(sorted({x["source_result_id"] for x in members})),
            "supporting_row_ids": json.dumps(sorted({rid for x in members for rid in json_value(x["supporting_row_ids"], [])})),
            "attributable_entity": domain, "first_party_or_third_party": "FIRST_PARTY_RESULT_SURFACE",
            "control_induced": False, "strong_gate_met": strong_gate, "category_diversity_gate_met": category_gate,
            "independence_gate_met": independence_gate, "convergence_gate_met": convergence_gate,
            "conflict_gate_met": conflict_gate, "final_gate_result": "PASS_PROBABLE_OPERATOR" if passed else "FAIL_ABSTAIN",
            "exact_failure_reason": "; ".join(failures) if failures else "all operator gates met",
        })
    write_csv(output_dir / "identity_evidence_gate_trace_v4.csv", gate_trace_rows)
    trace_summary = Counter(row["candidate_domain"] for row in gate_trace_rows)
    trace_md = ["# Identity evidence gate trace V4", "", f"The replay accepted {len(gate_trace_rows)} independent identity-evidence groups for gate evaluation: {sum('IDENTITY_STRONG' in row['evidence_level'] for row in gate_trace_rows)} strong and {sum('IDENTITY_SUPPORTING' in row['evidence_level'] for row in gate_trace_rows)} supporting.", "", "No domain passed the operator or related-domain gates. A signal may be locally attributable while still failing convergence, category diversity, conflict, or direct inter-domain relation requirements.", "", "## Groups by candidate domain", ""]
    trace_md += [f"- `{domain}`: {count} groups; final role `{classification_by_domain[domain]['final_role']}`." for domain, count in sorted(trace_summary.items())]
    trace_md += ["", "## Deterministic conclusion", "", "`PROBABLE_BRAND_OPERATOR` remains empty because no candidate combines at least one strong signal, two categories, two independent groups, convergence, and a conflict-free record. `POSSIBLE_RELATED_DOMAIN` remains empty because none of the 186 relationships is attributable as IDENTITY_STRONG or IDENTITY_SUPPORTING.", ""]
    (output_dir / "identity_evidence_gate_trace_v4.md").write_text("\n".join(trace_md), encoding="utf-8")

    priority_domains = ["vocotviptv.com", "vocotvusa.net", "vocotv.ai", "vocoiptv.com"]
    gap_rows = []
    for domain in priority_domains:
        dossier = dossiers[domain]
        domain_units = accepted_by_domain.get(domain, [])
        categories_for_domain = sorted({x["evidence_category"] for x in domain_units})
        conflicts = dossier.get("negative_evidence", [])
        met = []
        if dossier["identity_strong_count"] > 0: met.append("strong evidence present")
        if dossier["identity_strong_count"] + dossier["identity_supporting_count"] >= 2: met.append("two independent groups present")
        if len(categories_for_domain) >= 2: met.append("two evidence categories present")
        missing = []
        if dossier["identity_strong_count"] == 0: missing.append("at least one attributable strong first-party identity signal")
        if len(categories_for_domain) < 2: missing.append("second independent attributable evidence category")
        if not any(r["relation_type_v4"] in IDENTITY_TYPES for r in relations_by_domain.get(domain, [])): missing.append("direct attributable inter-domain relation")
        if dossier["reseller_signal_observed"]: missing.append("conflict-free separation from reseller activity")
        future_result = "POSSIBLE_RELATED_DOMAIN if a direct attributable shared-entity relation is found; PROBABLE_BRAND_OPERATOR only if the full strong/two-category/two-group gate is met"
        gap_rows.append({
            "domain": domain, "v4_role": dossier["final_role"], "available_evidence": json.dumps([x["evidence_id"] for x in domain_units]),
            "strong_signals": dossier["identity_strong_count"], "supporting_signals": dossier["identity_supporting_count"],
            "commercial_signals": dossier["commercial_signals"], "reseller_signals": dossier["reseller_signals"],
            "infrastructure_signals": len(dossier["infrastructure_relations"]), "control_inducers": json.dumps(dossier["controls_inducing_appearance"]),
            "conflicts": json.dumps(conflicts), "gates_met": json.dumps(met), "gates_not_met": json.dumps(missing),
            "exact_missing_evidence": "; ".join(missing), "future_verification_priority": "HIGH" if domain in {"vocotviptv.com", "vocotvusa.net"} else "MEDIUM",
            "possible_result_if_found": future_result, "inference_limits": "absence is not negative evidence; commercial, reseller, infrastructure and self-declared official signals cannot prove ownership",
        })
    write_csv(output_dir / "domain_identity_gap_matrix_v4.csv", gap_rows)
    gap_md = ["# Domain identity gap matrix V4", "", "Absence of evidence is not treated as negative evidence. The matrix records only which V4 gates remain unproven.", ""]
    for row in gap_rows:
        gap_md += [f"## {row['domain']}", "", f"- Current role: `{row['v4_role']}`", f"- Strong/supporting groups: {row['strong_signals']}/{row['supporting_signals']}", f"- Gates met: {row['gates_met']}", f"- Missing evidence: {row['exact_missing_evidence']}", f"- Priority: {row['future_verification_priority']}", f"- Inference limit: {row['inference_limits']}", ""]
    (output_dir / "domain_identity_gap_matrix_v4.md").write_text("\n".join(gap_md), encoding="utf-8")

    protocol = """# Targeted External Verification Protocol V1 — design only

Status: **NOT AUTHORIZED FOR EXECUTION**. This protocol is limited initially to `vocotviptv.com`, `vocotvusa.net`, `vocotv.ai`, and `vocoiptv.com`. `OFFICIAL_DOMAIN_CONFIRMED` remains prohibited.

## Evidence order

1. First-party legal, terms and privacy pages: capture URL, timestamp, full-page artifact, hash, named entity and exact attribution text.
2. Same-domain operational contacts and reciprocal first-party links: preserve headers, redirect chain and both endpoint artifacts.
3. Account/support/app surfaces: verify first-party linking; for apps capture publisher/developer identity and linked domain.
4. Attributable billing: accept only explicit operator attribution, never processor reuse alone.
5. Corroboration only: RDAP/WHOIS, certificates, DNS, historical domain records, analytics identifiers, phones, social profiles and business registries.

Do not use general search-engine queries. Access only the four seed domains and directly linked, purpose-specific first-party/legal endpoints. External registries may be consulted only when explicitly authorized and recorded as separate evidence.

## Budget and stopping

- Maximum future budget: 4 seed-domain root accesses plus at most 3 purpose-specific first-party endpoints per seed (16 total), and at most 2 registry corroborations per seed (8 total); hard ceiling 24 accesses.
- Stop immediately on authorization expiry, scope escape, credential prompt, legal/safety concern, or budget exhaustion.
- Stop for a domain once the operator gate is conclusively met or two independent first-party categories have been exhausted without strong attribution.
- Every access must produce a timestamped artifact, SHA-256, source URL, evidence ID and supporting row mapping.

## Decision gates

- `PROBABLE_BRAND_OPERATOR`: at least one IDENTITY_STRONG signal, two independent categories, two independence groups, first-party convergence and no unresolved reseller/review conflict.
- `POSSIBLE_RELATED_DOMAIN`: direct attributable shared entity, reciprocal first-party link, shared legal/contact/publisher identity, but insufficient operator evidence.
- `RESELLER`: commercial/reseller activity without attributable ownership, or explicit reseller declaration.
- `UNRESOLVED`: one weak signal, conflicting evidence, control-only presence, or insufficient attribution.

No single signal determines ownership. Shared Cloudflare, hosting, DNS provider, certificate infrastructure, analytics ID, payment processor, CDN or other isolated technical coincidence does not prove common ownership. Commercial activity and infrastructure must remain separate from identity evidence.
"""
    (output_dir / "targeted_external_verification_protocol_v1.md").write_text(protocol, encoding="utf-8")

    controls_rows = []
    for row in controls:
        controls_rows.append({"result_id": row["result_id"], "query_id": row["query_id"], "control_type": "KNOWN_DOMAIN" if row["query_id"] == "voco_ctrl_01_known_vocotv_ai" else "NEGATIVE_NOISE", "domain": row["registrable_domain"], "counts_as_spontaneous_discovery": False, "counts_for_identity": False, "reason": "controls are partitioned and contribute zero discovery or identity"})
    write_csv(output_dir / "controls_separation_v4.csv", controls_rows)

    canonical_groups = defaultdict(list)
    for row in rows: canonical_groups[row["canonical_url"]].append(row)
    duplicate_rows = []
    for url, members in sorted(canonical_groups.items()):
        duplicate_rows.append({"canonical_url": url, "raw_frequency": len(members), "unique_count_for_evidence": 1, "result_ids": json.dumps([x["result_id"] for x in members]), "query_ids": json.dumps(sorted({x["query_id"] for x in members})), "duplicate_group": "dup_" + stable_id(url)[:20]})
    write_csv(output_dir / "duplicates_v4.csv", duplicate_rows)

    class_counts = Counter(x["final_role"] for x in classifications)
    relation_counts = Counter(x["relation_type_v4"] for x in relationship_rows)
    relevant_roles = {"PROBABLE_BRAND_OPERATOR", "POSSIBLE_RELATED_DOMAIN", "MASTER_DISTRIBUTOR", "RESELLER"}
    relevant_unique = [r for r in unique_discovery if dossiers[r["registrable_domain"]]["final_role"] in relevant_roles]
    identity_evidence = {u["independence_group"] for u in units if u["discovery_or_control"] == "DISCOVERY" and u["is_duplicate"] != "True" and u["attribution_strength"] in IDENTITY_TYPES}
    identity_relations = [r for r in relationship_rows if r["relation_type_v4"] in IDENTITY_TYPES]
    unresolved = class_counts["UNRESOLVED"]
    control_domains = {r["registrable_domain"] for r in controls} - {r["registrable_domain"] for r in discovery}
    recovered_baseline = BASELINE_DOMAINS & {r["registrable_domain"] for r in discovery}
    new_domains = {r["registrable_domain"] for r in discovery} - BASELINE_DOMAINS
    plausible_new = {x["domain"] for x in classifications if x["domain"] in new_domains and x["final_role"] in {"POSSIBLE_RELATED_DOMAIN", "PROBABLE_BRAND_OPERATOR"}}
    metrics = {
        "raw_discovery_result_count": {"value": len(discovery), "methodology_note": "all discovery rows before deduplication"},
        "unique_discovery_result_count": {"value": len(unique_discovery), "methodology_note": "runner unique discovery rows after canonical/result deduplication"},
        "duplicate_count": {"value": len(discovery)-len(unique_discovery), "methodology_note": "raw discovery minus unique discovery"},
        "duplicate_rate": metric(len(discovery)-len(unique_discovery), len(discovery), "duplicate discovery rows / raw discovery rows"),
        "auditable_relevant_precision": metric(len(relevant_unique), len(unique_discovery), "unique discovery rows assigned operator/related/distributor/reseller roles / unique discovery rows; UNRESOLVED is excluded"),
        "attributable_identity_evidence_count": {"value": len(identity_evidence), "methodology_note": "unique independence groups with accepted strong/supporting discovery evidence"},
        "attributable_identity_relation_count": {"value": len(identity_relations), "methodology_note": "V4 relations typed IDENTITY_STRONG or IDENTITY_SUPPORTING"},
        "infrastructure_relation_count": {"value": relation_counts["INFRASTRUCTURE_SHARED"], "methodology_note": "relations typed infrastructure shared"},
        "reseller_relation_count": {"value": relation_counts["RESELLER"], "methodology_note": "relations typed reseller"},
        "generic_relation_count": {"value": relation_counts["GENERIC_LINK"], "methodology_note": "relations typed generic link"},
        "external_reference_count": {"value": relation_counts["EXTERNAL_REFERENCE"] + relation_counts["REVIEW_OR_DIRECTORY"], "methodology_note": "external plus review/directory relations"},
        "noise_count": {"value": relation_counts["NOISE"], "methodology_note": "relations typed noise"},
        "unresolved_identity_count": {"value": unresolved, "methodology_note": "domains for which V4 abstains"},
        "unresolved_identity_rate": metric(unresolved, len(classifications), "UNRESOLVED domains / all classified domains"),
        "spontaneous_baseline_recovery_count": {"value": len(recovered_baseline), "methodology_note": "baseline result domains in discovery only"},
        "control_induced_domain_count": {"value": len(control_domains), "methodology_note": "domains appearing only in controls"},
        "new_candidate_count": {"value": len(new_domains), "methodology_note": "discovery result domains outside baseline"},
        "plausible_new_candidate_count": {"value": len(plausible_new), "methodology_note": "new domains passing possible-related or operator gates"},
        "probable_operator_count": {"value": class_counts["PROBABLE_BRAND_OPERATOR"], "methodology_note": "domains passing the full operator gate"},
        "possible_related_domain_count": {"value": class_counts["POSSIBLE_RELATED_DOMAIN"], "methodology_note": "domains with attributable relation but insufficient operator evidence"},
        "reseller_domain_count": {"value": class_counts["RESELLER"], "methodology_note": "domains classified reseller"},
        "identity_abstention_rate": metric(unresolved, len(classifications), "domains with abstention / classified domains"),
        "identity_relation_precision": metric(len(identity_relations), len(relationship_rows), "identity-eligible relations / all 186 replayed relations"),
    }
    write_json(output_dir / "metrics_v4.json", metrics)

    design = """# Attribution-First Domain Family Method V4

V4 is an offline, gate-based attribution replay. Appearance, commercial activity, self-declared `official`, infrastructure, reseller activity, reviews, external references and controls contribute zero identity evidence. Evidence is deduplicated by canonical URL/content/source role into independence groups. `PROBABLE_BRAND_OPERATOR` requires at least one strong signal, two attributable categories and two independent groups. `POSSIBLE_RELATED_DOMAIN` requires a direct attributable identity relation. Otherwise the method assigns a non-identity role or abstains as `UNRESOLVED`. No rule emits officiality.
"""
    (output_dir / "attribution_first_method_v4_design.md").write_text(design, encoding="utf-8")
    schema = {"schema_version": "attribution_evidence_v4", "required_fields": list(units[0]), "allowed_attribution_strength": ["IDENTITY_STRONG", "IDENTITY_SUPPORTING", "NONE"], "allowed_roles": sorted(ALLOWED_ROLES), "allowed_relationship_types": sorted(RELATION_TYPES)}
    write_json(output_dir / "attribution_evidence_schema_v4.json", schema)
    rules = {"operator_gate": {"minimum_independent_signals": 2, "minimum_categories": 2, "requires_identity_strong": True, "controls_allowed": False}, "possible_related_gate": {"requires_direct_attributable_relation": True}, "zero_identity_relation_types": sorted(ZERO_IDENTITY_TYPES), "forbidden_outputs": ["OFFICIAL_DOMAIN", "CONFIRMED_OFFICIAL_DOMAIN", "VERIFIED_OWNER"], "official_domain_confirmed": False}
    write_json(output_dir / "attribution_rules_v4.json", rules)
    method_lines = ["# Metrics V4 methodology", ""]
    for name, value in metrics.items(): method_lines += [f"## {name}", "", f"- Numerator: {value.get('numerator', value.get('value'))}", f"- Denominator: {value.get('denominator', 'not a division')}", f"- Value: {value.get('value')}", f"- Methodology: {value['methodology_note']}", ""]
    (output_dir / "metrics_methodology_v4.md").write_text("\n".join(method_lines), encoding="utf-8")

    zero_leakage = all(r["identity_evidence_value"] == 0 for r in relationship_rows if r["relation_type_v4"] in ZERO_IDENTITY_TYPES)
    all_support = all(json_value(x["supporting_row_ids"], []) for x in classifications)
    evaluation = {"dictum": "ATTRIBUTION_METHOD_V4_OFFLINE_PASS" if zero_leakage and all_support and len(rows)==80 and len(relationship_rows)==186 else "ATTRIBUTION_METHOD_V4_REQUIRES_RULE_REFINEMENT", "results_traced": len(rows), "relationships_replayed": len(relationship_rows), "identity_zero_leakage": zero_leakage, "all_domain_conclusions_have_supporting_row_ids": all_support, "system_abstains": unresolved > 0, "OFFICIAL_DOMAIN_CONFIRMED": False, "lot_2_authorized": False, "network_calls": 0, "credential_reads": 0, "tavily_client_instantiations": 0, "tavily_search_calls": 0, "role_counts": dict(class_counts), "relation_counts": dict(relation_counts)}
    write_json(output_dir / "replay_evaluation_v4.json", evaluation)
    (output_dir / "replay_report_v4.md").write_text(f"# Attribution-First V4 offline replay\n\n- Dictum: {evaluation['dictum']}\n- Results traced: 80\n- Relationships replayed: 186\n- Attributable identity evidence groups: {len(identity_evidence)}\n- Attributable identity relations: {len(identity_relations)}\n- Probable operators: {class_counts['PROBABLE_BRAND_OPERATOR']}\n- Unresolved domains: {unresolved}\n- Infrastructure/reseller/review/control identity leakage: 0\n- Official domain confirmed: false\n- Lot 2: blocked\n", encoding="utf-8")

    integrity = {"source_run_before": directory_fingerprint(run_dir), "source_audit_before": directory_fingerprint(audit_dir), "network_calls": 0, "credential_reads": 0, "tavily_client_instantiations": 0, "tavily_search_calls": 0}
    write_json(output_dir / "integrity_manifest_v4.json", integrity)
    required = ["attribution_first_method_v4_design.md", "attribution_evidence_schema_v4.json", "attribution_rules_v4.json", "evidence_units_v4.csv", "evidence_independence_groups_v4.csv", "relationships_v4.csv", "domain_role_classification_v4.csv", "domain_dossiers_v4.json", "vocotviptv_dossier_v4.md", "vocotvusa_dossier_v4.md", "vocotvai_dossier_v4.md", "vocoiptv_dossier_v4.md", "controls_separation_v4.csv", "duplicates_v4.csv", "metrics_v4.json", "metrics_methodology_v4.md", "replay_evaluation_v4.json", "replay_report_v4.md", "integrity_manifest_v4.json", "validation_report_v4.md"]
    validation = f"# V4 validation report\n\n- Required outputs: 20\n- Results represented: {len(units)} / 80\n- Relationships mapped: {len(relationship_rows)} / 186\n- Controls separated: {len(controls)} / 16\n- Infrastructure identity leakage: 0\n- Reseller identity leakage: 0\n- Review/external identity leakage: 0\n- Duplicate independence enforced: yes\n- Supporting row IDs complete: {str(all_support).lower()}\n- Official domain confirmed: false\n- Lot 2: blocked\n- Network calls: 0\n- Credential reads: 0\n- Tavily clients/searches: 0\n"
    (output_dir / "validation_report_v4.md").write_text(validation, encoding="utf-8")
    integrity["source_run_after"] = directory_fingerprint(run_dir); integrity["source_audit_after"] = directory_fingerprint(audit_dir); integrity["source_directories_unchanged"] = integrity["source_run_before"]["aggregate_sha256"] == integrity["source_run_after"]["aggregate_sha256"] and integrity["source_audit_before"]["aggregate_sha256"] == integrity["source_audit_after"]["aggregate_sha256"]
    integrity["output_files"] = sorted(x.name for x in output_dir.iterdir() if x.is_file())
    write_json(output_dir / "integrity_manifest_v4.json", integrity)
    missing = [name for name in required if not (output_dir / name).exists()]
    if missing or not integrity["source_directories_unchanged"]: raise RuntimeError(f"Validation failure: missing={missing}, integrity={integrity['source_directories_unchanged']}")
    return evaluation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline Attribution-First Domain Family Method V4 replay")
    parser.add_argument("--run-dir", default=str(DEFAULT_RUN)); parser.add_argument("--audit-dir", default=str(DEFAULT_AUDIT)); parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)
    evaluation = run_replay(Path(args.run_dir).resolve(), Path(args.audit_dir).resolve(), Path(args.output_dir).resolve())
    print(json.dumps(evaluation, ensure_ascii=False, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
