#!/usr/bin/env python3
"""Offline-only V4-compatible prioritization of existing IPTV domain evidence.

This module never imports an HTTP client, resolves DNS, reads credentials, or
executes Tavily.  It ranks research opportunities; it does not resolve identity.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse, urlunparse

VERDICT = "V4_OFFLINE_CANDIDATE_PRIORITIZATION_COMPLETE"
PROHIBITED_ROLES = {"OFFICIAL_DOMAIN", "CONFIRMED_OFFICIAL_DOMAIN", "VERIFIED_OWNER"}
ALLOWED_CLUSTER_TYPES = {
    "DOMAIN_VARIANT", "POSSIBLE_BRAND_FAMILY", "RESELLER_CLUSTER", "APP_OR_LOGIN_CLUSTER",
    "PAYMENT_CLUSTER", "INFRASTRUCTURE_CLUSTER", "REVIEW_OR_DIRECTORY_CLUSTER", "UNRESOLVED_CLUSTER",
}
OUTPUT_NAMES = [
    "corpus_inventory.json", "corpus_source_files.csv", "candidate_domains.csv", "excluded_domains.csv",
    "domain_family_clusters.json", "domain_family_members.csv", "family_evidence_summary.csv",
    "family_v4_preassessment.csv", "family_identity_gap_matrix.csv", "family_priority_scores.csv",
    "family_priority_ranking.csv", "top_10_candidate_families.md", "top_3_tavily_skill_plans.json",
    "recommended_next_family.md", "tavily_credit_budget_plan.json", "offline_prioritization_metrics.json",
    "offline_prioritization_report.md", "offline_prioritization_integrity_manifest.json",
    "runner_validation_report.md",
]
TEXT_EXTENSIONS = {".csv", ".json", ".jsonl", ".md", ".txt", ".py", ".html", ".htm"}
URL_RE = re.compile(r"https?://[^\s\"'<>|]+", re.I)
PLATFORM_DOMAINS = {
    "trustpilot.com", "google.com", "apple.com", "youtube.com", "facebook.com", "instagram.com",
    "linkedin.com", "reddit.com", "scribd.com", "github.com", "yahoo.com", "x.com", "quora.com",
}
TECHNICAL_SUFFIXES = (
    "cloudflare.com", "cloudflareinsights.com", "azurefd.net", "amazonaws.com", "googleapis.com",
    "gstatic.com", "w3.org", "cdn.jsdelivr.net", "cdnjs.com", "fonts.googleapis.com",
)
BRAND_PATTERNS = {
    "DigitaLizard IPTV": ("digitalizard", "digitallizard", "digital-lizard", "digitallizard"),
    "Krooz TV": ("krooz",),
    "Sonix IPTV": ("sonix", "sonic", "iptvsonix"),
    "Free Go TV": ("freego", "freegotv"),
}
SOURCE_RELATIVE_PATHS = {
    "inventory": Path("domain_inventory_v2_existing_results/run_20260714_062112/domain_inventory_detail.csv"),
    "relationships": Path("domain_inventory_v2_existing_results/run_20260714_062112/linked_domain_relationships.csv"),
    "manual": Path("manual_scouting_comparison/run_20260714_022943/manual_scouting_comparison.csv"),
    "manual_relationships": Path("manual_scouting_comparison/run_20260714_022943/manual_domain_relationships.csv"),
    "v3": Path("tavily_due_diligence_v3_simulation/run_20260714_055747/v3_classification_detail.csv"),
}

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()

def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()

def truthy(value: Any) -> bool:
    return normalize_space(value).casefold() in {"1", "true", "yes", "y"}

def split_values(value: Any) -> list[str]:
    return [x.strip() for x in re.split(r"\s*\|\s*", normalize_space(value)) if x.strip()]

def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)

def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))

def normalize_hostname(value: str) -> str:
    raw = normalize_space(value).lower().rstrip(".")
    if "://" in raw: raw = urlparse(raw).hostname or ""
    return raw[4:] if raw.startswith("www.") else raw

def canonical_url(value: str) -> str:
    try:
        parsed = urlparse(normalize_space(value))
        host = normalize_hostname(parsed.hostname or "")
    except ValueError:
        return ""
    if not host: return ""
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    path = path.rstrip("/") or "/"
    return urlunparse(((parsed.scheme or "https").lower(), host, path, "", parsed.query, ""))

def registrable_domain(host: str) -> str:
    host = normalize_hostname(host)
    parts = host.split(".")
    if len(parts) <= 2: return host
    compound = {"co.uk", "org.uk", "com.au", "co.nz", "com.br", "co.za", "com.mx"}
    suffix = ".".join(parts[-2:])
    return ".".join(parts[-3:]) if suffix in compound else suffix

def recursive_fingerprint(path: Path) -> dict[str, Any]:
    files=[]
    for item in sorted(x for x in path.rglob("*") if x.is_file()):
        files.append({"path":item.relative_to(path).as_posix(),"bytes":item.stat().st_size,"sha256":sha256_bytes(item.read_bytes())})
    aggregate=sha256_text("\n".join(f"{x['path']}:{x['sha256'].lower()}" for x in files)).upper()
    return {"directory":str(path.resolve()),"file_count":len(files),"total_bytes":sum(x["bytes"] for x in files),"aggregate_sha256":aggregate,"files":files}

def frozen_file_fingerprints(files: list[Path], root: Path) -> dict[str, dict[str, Any]]:
    return {p.relative_to(root).as_posix():{"bytes":p.stat().st_size,"sha256":sha256_bytes(p.read_bytes())} for p in files}

def format_name(path: Path) -> str:
    return path.suffix.lower().lstrip(".") or "no_extension"

def inspect_source_file(path: Path, root: Path, model_files: set[Path]) -> dict[str, Any]:
    fmt=format_name(path); records=0; urls=[]; parsed=False
    if path.suffix.lower() in TEXT_EXTENSIONS:
        text=path.read_text(encoding="utf-8",errors="replace")
        urls=URL_RE.findall(text); parsed=True
        if path.suffix.lower()==".csv":
            try:
                with path.open(encoding="utf-8",errors="replace",newline="") as handle: records=max(sum(1 for _ in csv.reader(handle))-1,0)
            except csv.Error: parsed=False
        elif path.suffix.lower()==".jsonl": records=sum(1 for x in text.splitlines() if x.strip())
        elif path.suffix.lower()==".json":
            try:
                value=json.loads(text); records=len(value) if isinstance(value,list) else (len(value) if isinstance(value,dict) else 1)
            except json.JSONDecodeError: parsed=False
    return {"source_file":path.relative_to(root).as_posix(),"format":fmt,"bytes":path.stat().st_size,"records":records,
            "url_occurrences":len(urls),"unique_urls":len({canonical_url(x) for x in urls if canonical_url(x)}),
            "structured_or_text_parse_ok":parsed,"used_for_candidate_model":path.resolve() in model_files,
            "sha256":sha256_bytes(path.read_bytes())}

def brand_matches_domain(brand: str, domain: str) -> bool:
    compact=re.sub(r"[^a-z0-9]", "", domain.casefold())
    return any(re.sub(r"[^a-z0-9]", "", token.casefold()) in compact for token in BRAND_PATTERNS.get(brand,()))

def exclusion_reason(brand: str, domain: str, rows: list[dict[str,str]]) -> str:
    if brand=="Voco TV" or any(x in domain for x in ("voco",)): return "CLOSED_VOCO_FAMILY"
    if not domain: return "NO_REGISTRABLE_DOMAIN"
    if domain in PLATFORM_DOMAINS: return "GENERIC_PLATFORM_OR_REVIEW"
    if domain.endswith(TECHNICAL_SUFFIXES): return "TECHNICAL_INFRASTRUCTURE_ONLY"
    if not brand_matches_domain(brand,domain): return "NOMINAL_OR_UNATTRIBUTED_DOMAIN_MISMATCH"
    max_relevance=max((int(float(x.get("relevance_score") or 0)) for x in rows),default=0)
    if max_relevance<30: return "INSUFFICIENT_MINIMUM_EVIDENCE"
    if all((x.get("source_category_v2") or "").upper() in {"REVIEW_PLATFORM","COMMUNITY"} for x in rows): return "REVIEW_ONLY"
    return ""

def cluster_id_for(brand: str, domain: str) -> tuple[str,str]:
    d=domain.casefold()
    if brand=="DigitaLizard IPTV":
        if d.startswith("digitalizard-iptv"): return "digitalizard-iptv-variant","DOMAIN_VARIANT"
        if d.startswith("digitalizard.") or d in {"digitalizard.app","digitalizard.com","digitalizard.eu","digitalizard.io","digitalizard.site"}: return "digitalizard-core","POSSIBLE_BRAND_FAMILY"
        if "digitallizard" in d: return "digitalizard-spelling-variants","DOMAIN_VARIANT"
        return "digitalizard-iptv-variants","UNRESOLVED_CLUSTER"
    if brand=="Krooz TV":
        if "krooztv" in d: return "krooztv-core","POSSIBLE_BRAND_FAMILY"
        if "krooziptv" in d or "krooz-iptv" in d: return "krooziptv-variants","DOMAIN_VARIANT"
        if "krooz-tv" in d or "tvkrooz" in d: return "krooz-tv-variants","DOMAIN_VARIANT"
        return "krooz-other-variants","UNRESOLVED_CLUSTER"
    if brand=="Sonix IPTV":
        if "soniciptv" in d: return "sonic-iptv-variants","DOMAIN_VARIANT"
        if d.startswith("iptvsonix"): return "iptvsonix-variant","DOMAIN_VARIANT"
        if "sonix-iptv" in d or "sonixiptv" in d: return "sonix-iptv-variants","POSSIBLE_BRAND_FAMILY"
        return "sonix-other-variants","UNRESOLVED_CLUSTER"
    return "freego-variants","UNRESOLVED_CLUSTER"

def aggregate_domain(brand: str, domain: str, rows: list[dict[str,str]], relationship_rows: list[dict[str,str]]) -> dict[str,Any]:
    urls=sorted({canonical_url(x.get("canonical_url") or x.get("original_url") or "") for x in rows if canonical_url(x.get("canonical_url") or x.get("original_url") or "")})
    ids=sorted({x.get("inventory_id","") for x in rows if x.get("inventory_id")})
    legal=sum(bool(split_values(x.get("privacy_policy_url"))+split_values(x.get("terms_url"))) for x in rows)
    contacts=sum(bool(split_values(x.get("contact_email"))+split_values(x.get("support_email"))+split_values(x.get("WhatsApp"))+split_values(x.get("phone"))) for x in rows)
    apps=sum(bool(split_values(x.get("app_url"))) for x in rows)
    payments=sum(bool(split_values(x.get("checkout_url"))+split_values(x.get("payment_url"))) for x in rows)
    potential_entities=sorted({normalize_space(x.get("legal_entity")) for x in rows if normalize_space(x.get("legal_entity"))})
    trusted=lambda x: normalize_space(x.get("v3_final_classification")).upper() in {"DIRECT_ACCEPT","IDENTITY_STRONG"}
    entities=sorted({normalize_space(x.get("legal_entity")) for x in rows if normalize_space(x.get("legal_entity")) and trusted(x)})
    potential_jurisdictions=sorted({z for x in rows for z in split_values(x.get("claimed_country")) if z})
    jurisdictions=sorted({z for x in rows if trusted(x) for z in split_values(x.get("claimed_country")) if z})
    conflicts=sorted({z for x in rows for z in split_values(x.get("v3_conflicts")) if z})
    source_categories=sorted({normalize_space(x.get("source_category_v2")) or "UNKNOWN" for x in rows})
    query_categories=sorted({normalize_space(x.get("query_category")) for x in rows if normalize_space(x.get("query_category"))})
    related=sorted({registrable_domain(x.get("related_registrable_domain") or x.get("related_domain") or "") for x in relationship_rows if registrable_domain(x.get("related_registrable_domain") or x.get("related_domain") or "") and registrable_domain(x.get("related_registrable_domain") or x.get("related_domain") or "")!=domain})
    first_party=sum(registrable_domain(urlparse(x.get("canonical_url") or x.get("original_url") or "").hostname or "")==domain and (x.get("source_category_v2") or "").upper() not in {"REVIEW_PLATFORM","COMMUNITY"} for x in rows)
    duplicate_count=max(len(rows)-len(urls),0)
    return {"brand_name":brand,"registrable_domain":domain,"evidence_count":len(rows),"unique_url_count":len(urls),"urls":urls,
        "supporting_row_ids":ids,"first_party_evidence_count":first_party,"third_party_evidence_count":len(rows)-first_party,
        "legal_page_signal_count":legal,"contact_signal_count":contacts,"application_signal_count":apps,"payment_signal_count":payments,
        "crosslink_count":len(related),"attributable_crosslink_count":0,"related_domains":related,"named_entities":entities,
        "potential_entities":potential_entities,"jurisdictions":jurisdictions,"potential_jurisdictions":potential_jurisdictions,
        "conflicts":conflicts,"source_categories":source_categories,"independent_query_categories":query_categories,
        "duplicate_count":duplicate_count,"duplicate_ratio":round(duplicate_count/max(len(rows),1),4),
        "noise_count":sum(int(float(x.get("relevance_score") or 0))<30 for x in rows),
        "max_relevance":max((int(float(x.get("relevance_score") or 0)) for x in rows),default=0),
        "v3_labels":sorted({normalize_space(x.get("v3_final_classification")) for x in rows if normalize_space(x.get("v3_final_classification"))})}

def aggregate_family(family_id: str, cluster_type: str, members: list[dict[str,Any]]) -> dict[str,Any]:
    ids=sorted({x for m in members for x in m["supporting_row_ids"]})
    urls=sorted({x for m in members for x in m["urls"]})
    sources=sorted({x for m in members for x in m["source_categories"]})
    categories=sorted({x for m in members for x in m["independent_query_categories"]})
    entities=sorted({x for m in members for x in m["named_entities"]}); potential_entities=sorted({x for m in members for x in m["potential_entities"]})
    jurisdictions=sorted({x for m in members for x in m["jurisdictions"]}); potential_jurisdictions=sorted({x for m in members for x in m["potential_jurisdictions"]})
    conflicts=sorted({x for m in members for x in m["conflicts"]})
    total=sum(m["evidence_count"] for m in members); duplicates=sum(m["duplicate_count"] for m in members)
    first=sum(m["first_party_evidence_count"] for m in members)
    legal=sum(m["legal_page_signal_count"] for m in members); contact=sum(m["contact_signal_count"] for m in members)
    apps=sum(m["application_signal_count"] for m in members); payments=sum(m["payment_signal_count"] for m in members)
    cross=sum(m["crosslink_count"] for m in members); noise=sum(m["noise_count"] for m in members)
    strong=len(entities); supporting=sum(bool(x) for x in (legal,contact,apps,payments,cross))
    independent_count=len(set(categories))
    return {"family_id":family_id,"brand_name":members[0]["brand_name"],"cluster_type":cluster_type,
        "domains":sorted(m["registrable_domain"] for m in members),"domain_count":len(members),"evidence_count":total,
        "unique_url_count":len(urls),"first_party_evidence_count":first,"third_party_evidence_count":total-first,
        "legal_page_signal_count":legal,"contact_signal_count":contact,"application_signal_count":apps,
        "payment_signal_count":payments,"crosslink_count":cross,"attributable_crosslink_count":0,"named_entities":entities,"potential_entities":potential_entities,
        "jurisdictions":jurisdictions,"potential_jurisdictions":potential_jurisdictions,
        "identity_strong_count":strong,"identity_supporting_count":supporting,"conflicts":conflicts,
        "independent_source_categories":sources,"independent_query_category_count":independent_count,
        "single_source_dependency":len(sources)<=1,"noise_count":noise,"duplicate_count":duplicates,
        "duplicate_ratio":round(duplicates/max(total,1),4),"supporting_row_ids":ids,"known_urls":urls,
        "identity_gaps":[x for x,ok in (("IDENTITY_STRONG",bool(entities)),("ATTRIBUTABLE_JURISDICTION",bool(jurisdictions)),
            ("TWO_ATTRIBUTABLE_IDENTITY_CATEGORIES",strong>0 and supporting>=2),("ATTRIBUTABLE_CROSS_DOMAIN_RELATION",False)) if not ok]}

def score_family(family: dict[str,Any]) -> dict[str,Any]:
    components={
        "first_party":min(15,5+2*family["domain_count"]) if family["first_party_evidence_count"] else 0,
        "legal_privacy":min(10,4+family["legal_page_signal_count"]*2) if family["legal_page_signal_count"] else 0,
        "contact":min(10,4+family["contact_signal_count"]) if family["contact_signal_count"] else 0,
        "application_publisher":min(10,5+family["application_signal_count"]*2) if family["application_signal_count"] else 0,
        "payment_checkout":min(10,4+family["payment_signal_count"]) if family["payment_signal_count"] else 0,
        "crosslinks":min(10,2+family["crosslink_count"]) if family["crosslink_count"] else 0,
        "independent_sources":min(10,3*len(family["independent_source_categories"])),
        "entity_jurisdiction_potential":min(15,10*bool(family["potential_entities"])+5*bool(family["potential_jurisdictions"])),
        "map_extract_coverage":min(10,2*family["unique_url_count"]+family["domain_count"]),
    }
    review_only=family["first_party_evidence_count"]==0 and family["third_party_evidence_count"]>0
    penalties={
        "noise":-min(15,2*family["noise_count"]),
        "duplication":-min(10,round(family["duplicate_ratio"]*10)),
        "review_directory_dependency":-15 if review_only else 0,
        "nominal_only":-20 if not any((family["legal_page_signal_count"],family["contact_signal_count"],family["application_signal_count"],family["payment_signal_count"],family["crosslink_count"])) else 0,
        "material_conflict":-min(15,5*len(family["conflicts"])),
        "no_first_party":-20 if not family["first_party_evidence_count"] else 0,
    }
    raw=sum(components.values())+sum(penalties.values()); score=max(0,min(100,int(raw)))
    if review_only or (penalties["nominal_only"] and family["evidence_count"]<2): value="DO_NOT_INVESTIGATE"
    elif score>=65: value="HIGH_VALUE"
    elif score>=45: value="MEDIUM_VALUE"
    elif score>=25: value="LOW_VALUE"
    else: value="DO_NOT_INVESTIGATE"
    return {**family,"positive_components":components,"penalties":penalties,"priority_score":score,"priority_class":value,
            "scoring_judgment":"Score orders research value only; it is not an identity or officiality conclusion."}

def rank_families(families: list[dict[str,Any]]) -> list[dict[str,Any]]:
    ranked=sorted(families,key=lambda x:(-x["priority_score"],-x["unique_url_count"],-x["domain_count"],x["family_id"]))
    return [{**x,"rank":i+1} for i,x in enumerate(ranked)]

def choose_recommendations(ranked: list[dict[str,Any]]) -> tuple[dict[str,Any],dict[str,Any]|None]:
    eligible=[x for x in ranked if x["priority_class"] in {"HIGH_VALUE","MEDIUM_VALUE"} and x["first_party_evidence_count"]]
    if not eligible: raise ValueError("corpus has no reproducible investigable family")
    primary=eligible[0]
    reserve=next((x for x in ranked if x["family_id"]!=primary["family_id"] and x["priority_class"]!="DO_NOT_INVESTIGATE" and x["first_party_evidence_count"]),None)
    return primary,reserve

def known_page_urls(family: dict[str,Any]) -> list[str]:
    priority=re.compile(r"privacy|terms|legal|contact|about|payment|checkout|refund|dmca",re.I)
    selected=[x for x in family["known_urls"] if priority.search(urlparse(x).path)]
    return (selected or family["known_urls"])[:6]

def skill_plan(family: dict[str,Any], historical_queries: set[str]) -> dict[str,Any]:
    host_coverage=Counter(registrable_domain(urlparse(x).hostname or "") for x in family["known_urls"])
    initial=sorted(family["domains"],key=lambda x:(-host_coverage[x],x))[0]; extracts=known_page_urls(family)
    proposed=[
        f'site:{initial} ("legal entity" OR company OR operator OR owner OR "data controller")',
        f'"{family["brand_name"]}" (company OR LLC OR Ltd OR registry OR jurisdiction) -review -directory',
        f'"{initial}" (payment OR billing OR merchant OR publisher OR app)',
    ]
    searches=[]
    for query in proposed:
        normalized=normalize_space(query).casefold(); repeated=normalized in historical_queries
        searches.append({"exact_query":query,"query_sha256":sha256_text(normalized),"historical_duplicate":repeated})
    return {"family_id":family["family_id"],"rank":family["rank"],"authorization":"PLAN_ONLY_NOT_AUTHORIZED",
        "map":{"initial_domain":initial,"semantic_instructions":"Find first-party legal, privacy, contact, about, app, reseller and payment paths; do not infer ownership.",
            "max_depth":2,"limit":30,"priority_paths":["/terms","/privacy","/legal","/contact","/about","/payment","/billing","/app"],
            "excluded_paths":["/blog","/tag","/category","/reviews","/wp-content"],"maximum_estimated_credits":20,"human_gate_after":True},
        "extract":{"known_urls":extracts,"extraction_query":"Extract named legal entity, controller, operator, owner, address, jurisdiction, registration, merchant, publisher, contacts and exact supporting fragments.",
            "chunks_per_source":3,"extract_depth":"advanced","format":"markdown","maximum_estimated_credits":30,
            "useful_evidence_criteria":"Named attributable fact with source URL and supporting fragment; generic brand language is insufficient."},
        "search":{"only_after_map_extract":True,"queries":searches,"include_domains":family["domains"],
            "exclude_domains":sorted(PLATFORM_DOMAINS),"search_depth":"advanced","max_results":5,"maximum_estimated_credits":30,
            "deduplication":"Reject any normalized query hash already present in the historical ledger."},
        "crawl":{"default":"BLOCKED","justifiable_only_if":"Map exposes a compact first-party legal subtree not covered by Extract","maximum_estimated_credits":40,"requires_separate_human_authorization":True},
        "research":{"default":"BLOCKED","included_in_base_budget":False},
        "base_budget":80,"maximum_budget":120,"stop_conditions":["named entity plus attributable domain relation found","all legal/contact/payment paths exhausted","two consecutive stages add no identity category","material reseller/template conflict dominates","budget cap reached"]}

def flatten_score(row: dict[str,Any]) -> dict[str,Any]:
    return {"rank":row.get("rank",0),"family_id":row["family_id"],"brand_name":row["brand_name"],"cluster_type":row["cluster_type"],
        "domains":json.dumps(row["domains"]),"priority_score":row["priority_score"],"priority_class":row["priority_class"],
        **{f"positive_{k}":v for k,v in row["positive_components"].items()},**{f"penalty_{k}":v for k,v in row["penalties"].items()},
        "supporting_row_ids":json.dumps(row["supporting_row_ids"])}

def run(corpus_root: Path, output: Path) -> dict[str,Any]:
    corpus_root=corpus_root.resolve(); output=output.resolve()
    if output.exists(): raise ValueError(f"output already exists: {output}")
    sources={name:corpus_root/rel for name,rel in SOURCE_RELATIVE_PATHS.items()}
    missing=[str(x) for x in sources.values() if not x.is_file()]
    if missing: raise ValueError(f"missing canonical sources: {missing}")
    source_dirs={"domain_inventory":sources["inventory"].parent,"manual_scouting":sources["manual"].parent,"v3_simulation":sources["v3"].parent}
    before_dirs={name:recursive_fingerprint(path) for name,path in source_dirs.items()}
    existing_files=sorted(x for x in corpus_root.rglob("*") if x.is_file() and "v4_offline_candidate_prioritization_1a_" not in x.as_posix())
    before_files=frozen_file_fingerprints(existing_files,corpus_root)
    model_files={x.resolve() for x in sources.values()}
    source_inventory=[inspect_source_file(path,corpus_root,model_files) for path in existing_files]
    rows=read_csv(sources["inventory"]); relationships=read_csv(sources["relationships"])
    manual=read_csv(sources["manual"]); manual_relationships=read_csv(sources["manual_relationships"]); v3=read_csv(sources["v3"])
    relationship_by_source=defaultdict(list)
    for rel in relationships+manual_relationships: relationship_by_source[rel.get("source_inventory_id","")].append(rel)
    grouped=defaultdict(list)
    for row in rows: grouped[(row.get("brand_name","") or "UNNAMED",registrable_domain(row.get("registrable_domain") or row.get("canonical_hostname") or ""))].append(row)
    candidates=[]; excluded=[]
    for (brand,domain),members in sorted(grouped.items()):
        reason=exclusion_reason(brand,domain,members)
        ids={x.get("inventory_id","") for x in members}; rel=[x for sid in ids for x in relationship_by_source.get(sid,[])]
        aggregate=aggregate_domain(brand,domain,members,rel)
        if reason:
            excluded.append({"brand_name":brand,"registrable_domain":domain,"reason":reason,"evidence_count":len(members),
                "unique_url_count":aggregate["unique_url_count"],"supporting_row_ids":json.dumps(aggregate["supporting_row_ids"])})
        else: candidates.append(aggregate)
    clusters=defaultdict(list); cluster_types={}
    for item in candidates:
        family_id,kind=cluster_id_for(item["brand_name"],item["registrable_domain"]); clusters[family_id].append(item); cluster_types[family_id]=kind
    families=[score_family(aggregate_family(fid,cluster_types[fid],members)) for fid,members in sorted(clusters.items())]
    ranked=rank_families(families); recommended,alternative=choose_recommendations(ranked)
    historical_queries={normalize_space(x.get("query_text")).casefold() for x in rows if normalize_space(x.get("query_text"))}
    top3=[skill_plan(x,historical_queries) for x in ranked if x["priority_class"]!="DO_NOT_INVESTIGATE"][:3]
    output.mkdir(parents=True)
    write_csv(output/"corpus_source_files.csv",list(source_inventory[0]),source_inventory)
    candidate_fields=["brand_name","registrable_domain","evidence_count","unique_url_count","first_party_evidence_count","third_party_evidence_count","legal_page_signal_count","contact_signal_count","application_signal_count","payment_signal_count","crosslink_count","named_entities","potential_entities","jurisdictions","potential_jurisdictions","conflicts","duplicate_ratio","max_relevance","supporting_row_ids"]
    write_csv(output/"candidate_domains.csv",candidate_fields,[{**x,"named_entities":json.dumps(x["named_entities"]),"potential_entities":json.dumps(x["potential_entities"]),"jurisdictions":json.dumps(x["jurisdictions"]),"potential_jurisdictions":json.dumps(x["potential_jurisdictions"]),"conflicts":json.dumps(x["conflicts"]),"supporting_row_ids":json.dumps(x["supporting_row_ids"])} for x in candidates])
    write_csv(output/"excluded_domains.csv",["brand_name","registrable_domain","reason","evidence_count","unique_url_count","supporting_row_ids"],excluded)
    cluster_json=[{k:v for k,v in x.items() if k not in {"known_urls","positive_components","penalties"}} for x in ranked]
    write_json(output/"domain_family_clusters.json",cluster_json)
    member_rows=[]
    for family in ranked:
        for member in clusters[family["family_id"]]: member_rows.append({"family_id":family["family_id"],"cluster_type":family["cluster_type"],"brand_name":member["brand_name"],"registrable_domain":member["registrable_domain"],"evidence_count":member["evidence_count"],"unique_url_count":member["unique_url_count"],"supporting_row_ids":json.dumps(member["supporting_row_ids"])})
    write_csv(output/"domain_family_members.csv",list(member_rows[0]),member_rows)
    summary_fields=["family_id","brand_name","cluster_type","domain_count","evidence_count","unique_url_count","first_party_evidence_count","third_party_evidence_count","legal_page_signal_count","contact_signal_count","application_signal_count","payment_signal_count","crosslink_count","independent_query_category_count","duplicate_ratio","supporting_row_ids"]
    write_csv(output/"family_evidence_summary.csv",summary_fields,[{**x,"supporting_row_ids":json.dumps(x["supporting_row_ids"])} for x in ranked])
    pre_fields=["family_id","identity_strong_count","identity_supporting_count","named_entities","potential_entities","jurisdictions","potential_jurisdictions","conflicts","single_source_dependency","noise_count","identity_gaps","readiness","classification_provisional","supporting_row_ids"]
    pre_rows=[{"family_id":x["family_id"],"identity_strong_count":x["identity_strong_count"],"identity_supporting_count":x["identity_supporting_count"],"named_entities":json.dumps(x["named_entities"]),"potential_entities":json.dumps(x["potential_entities"]),"jurisdictions":json.dumps(x["jurisdictions"]),"potential_jurisdictions":json.dumps(x["potential_jurisdictions"]),"conflicts":json.dumps(x["conflicts"]),"single_source_dependency":x["single_source_dependency"],"noise_count":x["noise_count"],"identity_gaps":json.dumps(x["identity_gaps"]),"readiness":x["priority_class"],"classification_provisional":True,"supporting_row_ids":json.dumps(x["supporting_row_ids"])} for x in ranked]
    write_csv(output/"family_v4_preassessment.csv",pre_fields,pre_rows)
    gap_rows=[{"family_id":x["family_id"],"priority_class":x["priority_class"],"missing_identity_evidence":json.dumps(x["identity_gaps"]),"early_abandonment_condition":"No attributable identity category after Map and Extract, or material reseller/template conflict","supporting_row_ids":json.dumps(x["supporting_row_ids"])} for x in ranked]
    write_csv(output/"family_identity_gap_matrix.csv",list(gap_rows[0]),gap_rows)
    score_rows=[flatten_score(x) for x in ranked]; write_csv(output/"family_priority_scores.csv",list(score_rows[0]),score_rows)
    ranking_fields=["rank","family_id","brand_name","cluster_type","domains","priority_score","priority_class","identity_gaps","why_investigate","early_stop","supporting_row_ids"]
    ranking_rows=[{"rank":x["rank"],"family_id":x["family_id"],"brand_name":x["brand_name"],"cluster_type":x["cluster_type"],"domains":json.dumps(x["domains"]),"priority_score":x["priority_score"],"priority_class":x["priority_class"],"identity_gaps":json.dumps(x["identity_gaps"]),"why_investigate":"first-party coverage plus legal/contact/payment/app signals" if x["first_party_evidence_count"] else "limited third-party evidence","early_stop":"Map and Extract yield no new attributable category","supporting_row_ids":json.dumps(x["supporting_row_ids"])} for x in ranked]
    write_csv(output/"family_priority_ranking.csv",ranking_fields,ranking_rows)
    top10=ranked[:10]
    investigable=[x for x in ranked if x["priority_class"]!="DO_NOT_INVESTIGATE"][:5]
    md=["# Top 10 offline candidate families","","All classifications are provisional research priorities, not identity findings.","",
        "## Top 5 investigable","",*(f"- {x['rank']}. `{x['family_id']}` — {x['priority_score']}/100 ({x['priority_class']})" for x in investigable),"",
        "## Top 3 for planned Tavily Agent Skills","",*(f"- {x['rank']}. `{x['family_id']}`" for x in ranked[:3]),"",
        "## Full ranked detail",""]
    for x in top10: md += [f"### {x['rank']}. {x['family_id']} — {x['priority_score']}/100 ({x['priority_class']})","",f"Domains: {', '.join(x['domains'])}. Known: {x['evidence_count']} evidence rows and {x['unique_url_count']} unique URLs. Missing: {', '.join(x['identity_gaps']) or 'no modeled gap'}. Early stop: no attributable category after Map and Extract.",""]
    md += ["## Do not investigate","",*(f"- `{x['family_id']}`: score/class gate." for x in ranked if x["priority_class"]=="DO_NOT_INVESTIGATE"),
        "- `Voco TV`: closed family, excluded by mandate.","- `Free Go TV`: no candidate domain met the minimum local evidence gate.",""]
    (output/"top_10_candidate_families.md").write_text("\n".join(md),encoding="utf-8")
    write_json(output/"top_3_tavily_skill_plans.json",{"status":"PLAN_ONLY_NOT_AUTHORIZED","plans":top3})
    alt_text=f"{alternative['family_id']} ({alternative['priority_score']}/100)" if alternative else "none"
    (output/"recommended_next_family.md").write_text(f"# Recommended next family\n\nPrimary: **{recommended['family_id']}** ({recommended['priority_score']}/100, {recommended['priority_class']}).\n\nReserve: **{alt_text}**.\n\nThe primary has the best reproducible combination of first-party pages, legal/contact/payment coverage, independent query categories and Map/Extract coverage after conflict and duplication penalties. It remains unresolved and must pass human authorization before any acquisition.\n\nIdentity gaps: {', '.join(recommended['identity_gaps'])}. Stop after Map and Extract if no attributable category is added, if reseller/template conflict dominates, or if the 80-credit base cap is reached.\n",encoding="utf-8")
    credit={"panel_monthly_credits":4000,"confirmed_prior_usage":548,"informational_only":True,"authorization_granted":False,
        "per_family":{"map_max":20,"extract_max":30,"search_max":30,"base_budget":80,"maximum_budget":120,"crawl_possible_separate_max":40,"research_base":0},
        "top3_base_total":240,"top3_maximum_total":360,"reserve_after_top3_maximum_from_reported_balance":3092,
        "stop_conditions":["identity gate satisfied","Map and Extract add no attributable category","material conflict","duplicate query hash","family cap"],
        "crawl":"BLOCKED_BY_DEFAULT","research":"BLOCKED_BY_DEFAULT_AND_EXCLUDED_FROM_BASE"}
    write_json(output/"tavily_credit_budget_plan.json",credit)
    format_counts=Counter(x["format"] for x in source_inventory)
    all_urls=sum(x["url_occurrences"] for x in source_inventory); unique_primary={canonical_url(x.get("canonical_url") or x.get("original_url") or "") for x in rows}; unique_primary.discard("")
    primary_domains={registrable_domain(x.get("registrable_domain") or x.get("canonical_hostname") or "") for x in rows}; primary_domains.discard("")
    corpus_inventory={"mode":"OFFLINE_ONLY","files_inspected":len(source_inventory),"formats":dict(sorted(format_counts.items())),
        "structured_records_inspected":sum(x["records"] for x in source_inventory),"candidate_model_records":{"inventory":len(rows),"relationships":len(relationships),"manual":len(manual),"manual_relationships":len(manual_relationships),"v3":len(v3),"total":len(rows)+len(relationships)+len(manual)+len(manual_relationships)+len(v3)},
        "textual_url_occurrences":all_urls,"primary_unique_urls":len(unique_primary),"primary_canonical_urls":len(unique_primary),"primary_hostnames":len({normalize_hostname(x.get("canonical_hostname") or x.get("hostname") or "") for x in rows}),
        "primary_registrable_domains":len(primary_domains),"candidate_domains":len(candidates),"excluded_domains":len(excluded),
        "single_appearance_domains":sum(1 for _,members in grouped.items() if len(members)==1),"multiple_appearance_domains":sum(1 for _,members in grouped.items() if len(members)>1),
        "evidence_with_supporting_row_ids":sum(bool(x.get("inventory_id")) for x in rows),"evidence_without_supporting_row_ids":sum(not bool(x.get("inventory_id")) for x in rows),
        "historical_sources_used":[x.relative_to(corpus_root).as_posix() for x in sources.values()],"voco_excluded":True}
    write_json(output/"corpus_inventory.json",corpus_inventory)
    candidate_brands={x["brand_name"] for x in candidates}; excluded_family_names=sorted({x["brand_name"] for x in excluded if x["brand_name"] not in candidate_brands})
    metrics={"verdict":VERDICT,"families_built":len(ranked),"families_excluded":len(excluded_family_names),"excluded_family_names":excluded_family_names,
        "candidate_domains":len(candidates),"excluded_domains":len(excluded),"top10_count":len(top10),"top3_count":len(top3),"primary_recommendation":recommended["family_id"],
        "reserve_recommendation":alternative["family_id"] if alternative else None,"network_calls":0,"tavily_calls":0,"credential_reads":0,
        "crawl_default":"BLOCKED","research_default":"BLOCKED","official_domain_emitted":False}
    write_json(output/"offline_prioritization_metrics.json",metrics)
    (output/"offline_prioritization_report.md").write_text(f"# V4 offline candidate prioritization 1A\n\nVerdict: {VERDICT}.\n\nInspected {len(source_inventory)} local files; the candidate model processed {corpus_inventory['candidate_model_records']['total']} records. Built {len(ranked)} provisional families from {len(candidates)} candidate domains and excluded {len(excluded)} domains.\n\nPrimary recommendation: **{recommended['family_id']}**; reserve: **{alternative['family_id'] if alternative else 'none'}**. Voco is excluded as closed. No official-domain or verified-owner conclusion is emitted.\n\nTavily Map, Extract and Search appear only as unauthorised plans. Crawl and Research remain blocked. Network, Tavily and credential reads: zero.\n",encoding="utf-8")
    (output/"runner_validation_report.md").write_text("# Runner validation report\n\nThe runner uses only Python standard-library file, CSV, JSON, hashing and URL parsing facilities. It has no HTTP client, socket operation, DNS operation, browser operation, credential read or Tavily execution path. Voco is excluded before clustering. Scores are clamped to 0–100; ranking and tie breaks are deterministic. All derived evidence rows preserve supporting_row_ids. Prohibited official or owner roles are never valid outputs.\n",encoding="utf-8")
    after_dirs={name:recursive_fingerprint(path) for name,path in source_dirs.items()}
    after_files=frozen_file_fingerprints(existing_files,corpus_root)
    unchanged=before_files==after_files and all(before_dirs[x]["aggregate_sha256"]==after_dirs[x]["aggregate_sha256"] for x in source_dirs)
    write_json(output/"offline_prioritization_integrity_manifest.json",{"created_at":now_iso(),"source_directories_before":before_dirs,"source_directories_after":after_dirs,
        "frozen_source_file_count":len(existing_files),"frozen_source_files_before":before_files,"frozen_source_files_after":after_files,
        "all_sources_unchanged":unchanged,"output_artifacts":OUTPUT_NAMES,"self_hash_excluded":True})
    return {**metrics,**corpus_inventory,"output":str(output),"all_sources_unchanged":unchanged,"ranked":ranked}

def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="Offline V4 candidate-family prioritization; never executes network or Tavily.")
    p.add_argument("--corpus-root",type=Path,default=Path("research/output/best_iptv_2026"))
    p.add_argument("--output-dir",type=Path,required=True)
    return p

def main(argv: list[str]|None=None) -> int:
    args=parser().parse_args(argv)
    try: result=run(args.corpus_root,args.output_dir)
    except (ValueError,OSError,csv.Error,json.JSONDecodeError) as exc:
        print(f"ERROR={type(exc).__name__}: {exc}"); print("V4_OFFLINE_CANDIDATE_PRIORITIZATION_REQUIRES_FIXES"); return 2
    print(json.dumps({k:v for k,v in result.items() if k!="ranked"},indent=2)); print(result["verdict"])
    return 0 if result["all_sources_unchanged"] else 3

if __name__=="__main__": raise SystemExit(main())
