#!/usr/bin/env python3
"""Offline-only consolidation for run_20260718_041625.

This script reads the preserved Search/Map/Extract evidence and the protected
1A/FIX4 universe.  It never imports a network client and writes only derived
artifacts inside the existing 1B run.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import tempfile
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "research/output/best_iptv_2026/brand_first_market_universe_1b/search_map_extract_multiregion_pilot_01/run_20260718_041625"
HIST = ROOT / "research/output/best_iptv_2026/brand_first_market_universe_1a/run_20260717_051437"
SCHEMA = "brand_first_market_universe_1b_offline_evaluation.v1"
PRE_TREE_SHA256 = "5a240ad0fe99d3faf62069ab578bc6290f656f585812599dbeee323cbbf95be1"
HISTORICAL_1035_SHA256 = "c17f14925934861e91da53d44a15c7e98979a03a3cab1b65a5acd5d9f7839b8c"

PROTECTED_RAW_HASHES = {
    "checkpoint.json": "1a003e1894fe150afe0a74361305c5ee2100f7fe46411b056759bb010c1b2135",
    "errors.jsonl": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "extract_selection.json": "c921a8c9d5b54840a373f3d605e2e67d4dabdb75996f43f72a2536a8478273a5",
    "extracted_pages.jsonl": "02c41bb0705b844c5662e4b4465a183730a4c7919188507e144dc461e05fb759",
    "manifest.json": "cb746c1462b37f6a87abc1883b8455b337a3b8767788894a9c979aaa39cea309",
    "mapped_pages.csv": "dc099eda600aef91e4b649d7502e7a3f9bb42380d6036592562d81febf8a2551",
    "operation_ledger.jsonl": "5d763c231bd68243125f4e4a63c8d9430dbf5db98c5312051efec81523ae9100",
    "search_results.jsonl": "c981d920f887c319712109b6eafc4cfe30a3f3ad26525d7ef8bce87f15eda87c",
    "source_registry.csv": "f567be1662e597c9b2e0660d960d261902bff82bc1a2ee46824b5ce6c230c997",
    "source_search_plan.json": "97208996a77ef6dda89b7cc641666b5a186ecb9bec0403d3e598dad8bd461337",
    "source_selection.json": "3e99da9732bce71311bcea42a17abc85356374683a6c0596817ca1e8acbd8ccf",
}


def m(raw: str, canonical: str | None = None, entity: str = "PROVIDER_CANDIDATE", context: str = "NUMBERED_RANKING") -> tuple[str, str, str, str]:
    return raw, canonical or raw, entity, context


# Manually reviewed headings from the eight preserved Extract payloads.  The
# canonical form never asserts identity, quality, legality, or officiality.
PAGE_MENTIONS = {
    "extract_selection_01": [
        m("IPTV Harmony"), m("Velvado IPTV"), m("IPTV France Premium"),
        m("Live-Premium 4k TV"), m("SerieIPTV"), m("MoaTV", "Moa TV"),
        m("FlashLine IPTV"), m("OneTVBox IPTV"),
        m("iScreenHD IPTV", context="TOP_PICKS_SIDEBAR"),
        m("SofaIPTV", context="TOP_PICKS_SIDEBAR"),
        m("USA LIVE IPTV", context="TOP_PICKS_SIDEBAR"),
        m("OrigineTV", context="TOP_PICKS_SIDEBAR"),
        m("Tellystudio", "Tellystudio IPTV", context="TOP_PICKS_SIDEBAR"),
        m("StreamingNordic IPTV", context="TOP_PICKS_SIDEBAR"),
    ],
    "extract_selection_02": [
        m("IPTV Harmony"), m("OrigineTV"), m("ApolloTV"), m("OneMonthIPTV"),
        m("StreamingNordic IPTV"), m("OTTOcean"), m("Worthystream"),
    ],
    "extract_selection_03": [
        m("OrigineTV"), m("Tellystudio", "Tellystudio IPTV"), m("Velvado IPTV"),
        m("USA LIVE IPTV"), m("SofaIPTV"), m("MoaTV", "Moa TV"),
        m("DigitaLizard IPTV"), m("Worthystream"), m("VocoTV"),
    ],
    "extract_selection_04": [
        m("Euro IPTV"), m("MUNDOIPTV.ÉL", "Mundo IPTV"), m("IPTVTienda Smarters"),
        m("OrigineTV"), m("Casa del Streaming"),
        m("ORA IPTV Player", entity="PLAYER_APPLICATION"), m("IPTV Harmony"),
        m("VocoTV"), m("OTTOcean"), m("Worthystream"), m("TV Krooz"),
        m("Double Haga clic en televisión", "Double Click TV"),
    ],
    "extract_selection_05": [
        m("ORA IPTV Player", entity="PLAYER_APPLICATION"), m("MIM IPTV"),
        m("OneTVBox IPTV"), m("VocoTV"), m("OTTOcean"), m("Worthystream"),
        m("TV Krooz"), m("Double Haga clic en televisión", "Double Click TV"),
    ],
    "extract_selection_06": [
        m("iScreenHD IPTV"), m("Transmisión en EE. UU. en 4K", "USA Stream 4K"),
        m("Estados Unidos en vivo IPTV", "USA LIVE IPTV"),
        m("Estudio Telly", "Tellystudio IPTV"), m("Xtreme HD IPTV"),
        m("OSIRISIPTV"), m("Televisión EagleCast", "Eagle Cast TV"),
        m("4K IPTV HABILIDADES", "4K IPTV ZONE"),
        m("Fuerte8K IPTV", "Strong8K IPTV"), m("MoaTV", "Moa TV"),
        m("OrigineTV"), m("IPTVPor", "IPTVDoor"), m("Plevo IPTV"),
        m("SofáIPTV", "SofaIPTV"), m("IPTVStreamz"), m("XCodes IPTV"),
        m("Magnolia IPTV"), m("HoxyTV"),
        m("Transmite IPTV 4K", "Stream IPTV 4K"),
    ],
    "extract_selection_07": [
        m("Magnolia IPTV"), m("Stremzi"), m("Eaglecast TV", "Eagle Cast TV"),
        m("JBNOTT"), m("ChannelMoa", "Moa TV"),
        m("DigitaLizard", "DigitaLizard IPTV"), m("XCodes IPTV"),
        m("IPTV Harmony"), m("WarpIPTV"),
        m("Fubo TV", entity="LEGAL_OTT_NON_TARGET"), m("OTTOcean"),
        m("PerfectIPTV"), m("Bunnystream"), m("Flash 4K IPTV", "Flash4K IPTV"),
        m("TrendyScreen"), m("IPTVtune"), m("Worthystream"),
    ],
    "extract_selection_08": [
        m("EagleCast TV", "Eagle Cast TV"), m("Magnolia IPTV"), m("Stremzi"),
        m("ChannelMoa", "Moa TV"), m("IPTV Harmony"),
        m("XCodes TV", "XCodes IPTV"), m("WarpIPTV"), m("IPTV Trends"),
        m("Honey Bee IPTV"), m("Falcon IPTV"),
        m("Bunny Streams", "Bunnystream"), m("Typhoon TV Labs"),
        m("Comstar IPTV"), m("Liveplayer IPTV"), m("IPTVtune"),
        m("Worthystream"), m("OTTOcean"),
    ],
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_id(prefix: str, value: str) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:24]}"


def phrase_norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def compact_norm(value: str) -> str:
    return phrase_norm(value).replace(" ", "")


def base_without_iptv(value: str) -> str:
    tokens = [token for token in phrase_norm(value).split() if token != "iptv"]
    return "".join(tokens)


def conservative_variant_keys(value: str) -> set[str]:
    tokens = [token for token in phrase_norm(value).split() if token != "iptv"]
    compact = compact_norm(value)
    keys = {"".join(tokens), "".join(sorted(tokens)), compact.replace("iptv", "")}
    return {key for key in keys if len(key) >= 4}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_bytes(path: Path, data: bytes) -> None:
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


def write_json(path: Path, value: object) -> None:
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
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


def all_ids(values) -> str:
    return " | ".join(sorted({str(v) for v in values if v}))


def validate_inputs() -> None:
    if not RUN.is_dir() or not HIST.is_dir():
        raise RuntimeError("Authoritative run or historical FIX4 run is missing")
    for name, expected in PROTECTED_RAW_HASHES.items():
        actual = sha256(RUN / name)
        if actual != expected:
            raise RuntimeError(f"Protected raw hash mismatch: {name}: {actual}")
    historical_path = HIST / "02_raw_brand_mentions.csv"
    if sha256(historical_path) != HISTORICAL_1035_SHA256:
        raise RuntimeError("Historical 1,035-name artifact hash mismatch")
    if len(read_csv(historical_path)) != 1035:
        raise RuntimeError("Historical artifact does not contain exactly 1,035 rows")


def historical_indexes():
    raw_rows = read_csv(HIST / "02_raw_brand_mentions.csv")
    canonical_rows = read_csv(HIST / "03_canonical_brand_universe.csv")
    alias_rows = read_csv(HIST / "04_brand_alias_map.csv")
    raw_phrase, raw_compact, base_index = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in raw_rows:
        raw_phrase[phrase_norm(row["raw_name"])].append(row)
        raw_compact[compact_norm(row["raw_name"])].append(row)
        for base in conservative_variant_keys(row["raw_name"]):
            base_index[base].append(row)
    canonical = defaultdict(list)
    for row in canonical_rows:
        canonical[compact_norm(row["canonical_brand_name"])].append(row)
    aliases = defaultdict(list)
    for row in alias_rows:
        aliases[compact_norm(row["alias_name"])].append(row)
    return raw_phrase, raw_compact, base_index, canonical, aliases


def classify_historical(name: str, entity: str, indexes, force_review: bool = False):
    raw_phrase, raw_compact, base_index, canonical, aliases = indexes
    if entity != "PROVIDER_CANDIDATE":
        return "NOT_A_BRAND", [], [], "Excluded from the unverified IPTV-provider candidate universe."
    phrase, compact = phrase_norm(name), compact_norm(name)
    exact = raw_phrase.get(phrase, [])
    normalized = raw_compact.get(compact, [])
    canonical_hits = canonical.get(compact, [])
    alias_hits = aliases.get(compact, [])
    if force_review:
        hits = exact or normalized
        return "POSSIBLE_VARIANT_REQUIRES_REVIEW", hits, [], "Extracted text was machine-translated or malformed; identity was not forced."
    if exact:
        return "EXACT_HISTORICAL_MATCH", exact, [], "Canonical phrase equals a normalized name in the 1,035-row artifact."
    if normalized or canonical_hits or alias_hits:
        hits = normalized
        return "NORMALIZED_HISTORICAL_MATCH", hits, canonical_hits or alias_hits, "Match requires punctuation, spacing, alias, or FIX4 canonical normalization."
    variants_by_id = {}
    for base in conservative_variant_keys(name):
        for row in base_index.get(base, []):
            variants_by_id[row["mention_id"]] = row
    variants = list(variants_by_id.values())
    if variants:
        return "POSSIBLE_VARIANT_REQUIRES_REVIEW", variants, [], "Same non-generic base tokens after adding, removing, or reordering IPTV; manual adjudication required."
    return "NEW_BRAND_CANDIDATE", [], [], "No exact, normalized, canonical, alias, or conservative IPTV-token variant match in FIX4."


def main() -> int:
    validate_inputs()
    generated_at = datetime.now(timezone.utc).isoformat()
    selection = json.loads((RUN / "extract_selection.json").read_text(encoding="utf-8"))
    selected = {row["selection_id"]: row for row in selection["selected_pages"]}
    envelopes = read_jsonl(RUN / "extracted_pages.jsonl")
    ledger = read_jsonl(RUN / "operation_ledger.jsonl")
    source_rows = read_csv(RUN / "source_registry.csv")
    mapped_rows = read_csv(RUN / "mapped_pages.csv")
    historical = historical_indexes()

    stage_events = Counter((row["stage"], row["event"]) for row in ledger)
    expected = {("search", "ATTEMPT_RESERVED"): 10, ("search", "COMPLETED"): 10,
                ("map", "ATTEMPT_RESERVED"): 5, ("map", "RAW_EVIDENCE"): 5, ("map", "COMPLETED"): 5,
                ("extract", "ATTEMPT_RESERVED"): 8, ("extract", "COMPLETED"): 8}
    for key, count in expected.items():
        if stage_events[key] != count:
            raise RuntimeError(f"Unexpected ledger count {key}: {stage_events[key]} != {count}")
    if len(envelopes) != 8 or set(PAGE_MENTIONS) != set(selected):
        raise RuntimeError("Extract envelope/selection inventory is not the approved eight-page plan")

    envelope_by_selection = {row["selection_id"]: row for row in envelopes}
    raw_mentions = []
    page_quality = []
    for selection_id in sorted(selected):
        page = selected[selection_id]
        envelope = envelope_by_selection[selection_id]
        results = envelope["raw_payload"].get("results", [])
        content = "\n".join(str(result.get("raw_content") or "") for result in results)
        if not content.strip():
            raise RuntimeError(f"Empty Extract content: {selection_id}")
        for position, (raw, canonical, entity, context_type) in enumerate(PAGE_MENTIONS[selection_id], 1):
            mention_id = stable_id("mention1b", f"{selection_id}|{position}|{raw}")
            raw_mentions.append({
                "mention_row_id": mention_id,
                "selection_id": selection_id,
                "extract_operation_id": envelope["operation_id"],
                "raw_record_id": envelope["raw_record_id"],
                "source_url": page["mapped_url"],
                "domain": page["domain"],
                "region": page["region"],
                "language": page["language"],
                "source_level": page["source_level"],
                "independence_group": page["independence_group"],
                "raw_brand_text": raw,
                "proposed_canonical_name": canonical,
                "normalized_name": phrase_norm(canonical),
                "entity_class": entity,
                "context_type": context_type,
                "position": position,
                "section": f"{context_type}:{position}",
                "context": f"Extracted ranking heading: {raw}",
                "supporting_row_ids": all_ids([mention_id, envelope["raw_record_id"], envelope["operation_id"], page["map_source_id"], *page["supporting_row_ids"]]),
            })
        mentions = [row for row in raw_mentions if row["selection_id"] == selection_id]
        page_quality.append({
            "selection_id": selection_id,
            "extract_operation_id": envelope["operation_id"],
            "raw_record_id": envelope["raw_record_id"],
            "source_url": page["mapped_url"],
            "domain": page["domain"],
            "region": page["region"],
            "language": page["language"],
            "source_level": page["source_level"],
            "independence_group": page["independence_group"],
            "result_count": len(results),
            "content_characters": len(content),
            "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "raw_mention_count": len(mentions),
            "provider_candidate_mentions": sum(row["entity_class"] == "PROVIDER_CANDIDATE" for row in mentions),
            "false_positive_mentions": sum(row["entity_class"] != "PROVIDER_CANDIDATE" for row in mentions),
            "unique_provider_candidates": len({compact_norm(row["proposed_canonical_name"]) for row in mentions if row["entity_class"] == "PROVIDER_CANDIDATE"}),
            "quality_status": "USEFUL_NONEMPTY",
            "limitations": "Level C discovery source; ranking/affiliate claims are not evidence of identity, quality, legality, or reputation.",
            "supporting_row_ids": all_ids([envelope["raw_record_id"], envelope["operation_id"], page["map_source_id"], *page["supporting_row_ids"]]),
        })

    by_candidate = defaultdict(list)
    for mention in raw_mentions:
        by_candidate[compact_norm(mention["proposed_canonical_name"])].append(mention)

    candidates, comparison, review_rows, matrix = [], [], [], []
    for key in sorted(by_candidate):
        mentions = by_candidate[key]
        canonical = Counter(row["proposed_canonical_name"] for row in mentions).most_common(1)[0][0]
        entity = Counter(row["entity_class"] for row in mentions).most_common(1)[0][0]
        force_review = any(row["raw_brand_text"] == "MUNDOIPTV.ÉL" for row in mentions)
        status, raw_hits, derived_hits, rationale = classify_historical(canonical, entity, historical, force_review)
        candidate_id = stable_id("candidate1b", key)
        groups = sorted({row["independence_group"] for row in mentions})
        domains = sorted({row["domain"] for row in mentions})
        regions = sorted({row["region"] for row in mentions})
        languages = sorted({row["language"] for row in mentions})
        pages = sorted({row["source_url"] for row in mentions})
        supporting = all_ids([candidate_id, *[row["mention_row_id"] for row in mentions], *[row["raw_record_id"] for row in mentions], *[row["extract_operation_id"] for row in mentions]])
        historical_mentions = all_ids(row.get("mention_id") for row in raw_hits)
        historical_names = all_ids(row.get("raw_name") for row in raw_hits)
        historical_canonicals = all_ids(row.get("canonical_brand_id") for row in derived_hits)
        common = {
            "candidate_id": candidate_id,
            "canonical_brand_name": canonical,
            "normalized_name": phrase_norm(canonical),
            "entity_class": entity,
            "mention_count": len(mentions),
            "page_count": len(pages),
            "source_count": len(domains),
            "independence_group_count": len(groups),
            "region_count": len(regions),
            "language_count": len(languages),
            "domains": all_ids(domains),
            "regions": all_ids(regions),
            "languages": all_ids(languages),
            "independence_groups": all_ids(groups),
            "supporting_row_ids": supporting,
        }
        if entity == "PROVIDER_CANDIDATE":
            candidates.append({**common, "historical_match_status": status,
                               "review_status": "REQUIRES_MANUAL_REVIEW" if status in {"POSSIBLE_VARIANT_REQUIRES_REVIEW", "NEW_BRAND_CANDIDATE", "AMBIGUOUS"} else "DISCOVERY_ONLY_MATCHED"})
        comparison.append({
            **common,
            "historical_match_status": status,
            "historical_raw_names": historical_names,
            "historical_mention_ids": historical_mentions,
            "historical_canonical_or_alias_ids": historical_canonicals,
            "match_basis": rationale,
            "review_status": "REVIEW_REQUIRED" if status in {"POSSIBLE_VARIANT_REQUIRES_REVIEW", "NEW_BRAND_CANDIDATE", "AMBIGUOUS"} else "CLASSIFIED",
        })
        review_rows.append({
            "candidate_id": candidate_id,
            "canonical_brand_name": canonical,
            "entity_class": entity,
            "historical_match_status": status,
            "historical_raw_names": historical_names,
            "historical_mention_ids": historical_mentions,
            "historical_canonical_or_alias_ids": historical_canonicals,
            "match_basis": rationale,
            "manual_review_priority": "HIGH" if status in {"POSSIBLE_VARIANT_REQUIRES_REVIEW", "AMBIGUOUS"} else "MEDIUM" if status == "NEW_BRAND_CANDIDATE" else "NONE",
            "supporting_row_ids": supporting,
        })
        for group in groups:
            gm = [row for row in mentions if row["independence_group"] == group]
            matrix.append({
                "candidate_id": candidate_id,
                "canonical_brand_name": canonical,
                "entity_class": entity,
                "historical_match_status": status,
                "independence_group": group,
                "domains": all_ids(row["domain"] for row in gm),
                "source_urls": all_ids(row["source_url"] for row in gm),
                "regions": all_ids(row["region"] for row in gm),
                "languages": all_ids(row["language"] for row in gm),
                "mention_count": len(gm),
                "supporting_row_ids": all_ids(row["mention_row_id"] for row in gm),
            })

    provider_candidates = [row for row in comparison if row["entity_class"] == "PROVIDER_CANDIDATE"]
    status_counts = Counter(row["historical_match_status"] for row in comparison)
    provider_status_counts = Counter(row["historical_match_status"] for row in provider_candidates)
    independent_repeat = [row for row in provider_candidates if row["independence_group_count"] >= 2]
    new_candidates = [row for row in provider_candidates if row["historical_match_status"] == "NEW_BRAND_CANDIDATE"]
    independent_new = [row for row in new_candidates if row["independence_group_count"] >= 2]

    group_rows = []
    for group in sorted({row["independence_group"] for row in raw_mentions}):
        gm = [row for row in raw_mentions if row["independence_group"] == group and row["entity_class"] == "PROVIDER_CANDIDATE"]
        pages = sorted({row["source_url"] for row in gm})
        page_sets = [{compact_norm(row["proposed_canonical_name"]) for row in gm if row["source_url"] == page} for page in pages]
        jaccards = []
        for left, right in combinations(page_sets, 2):
            jaccards.append(len(left & right) / len(left | right) if left | right else 0)
        group_rows.append({
            "independence_group_id": group,
            "domains": all_ids(row["domain"] for row in gm),
            "source_urls": all_ids(pages),
            "source_row_ids": all_ids(row["raw_record_id"] for row in gm),
            "source_count": len(pages),
            "mention_count": len(gm),
            "unique_provider_candidates": len({compact_norm(row["proposed_canonical_name"]) for row in gm}),
            "average_pairwise_brand_jaccard": f"{(sum(jaccards) / len(jaccards) if jaccards else 0):.6f}",
            "maximum_pairwise_brand_jaccard": f"{(max(jaccards) if jaccards else 0):.6f}",
            "signals": "same-domain ranking template; repeated comparison-table and numbered-review structure; recurring brands",
            "assessment_status": "PROBABLE_INTRA_DOMAIN_SEO_DUPLICATION",
            "rationale": "Pages are useful for discovery but do not count as independent corroboration within this group.",
            "supporting_row_ids": all_ids(row["mention_row_id"] for row in gm),
        })

    # Coverage uses the union of acquisition and Extract region/language pairs.
    source_combo = Counter((row["region"], row["language"]) for row in source_rows)
    operation_combo = defaultdict(set)
    domain_combo = defaultdict(set)
    for row in source_rows:
        operation_combo[(row["region"], row["language"])].add(row["search_operation_id"])
        domain_combo[(row["region"], row["language"])].add(row["domain"])
    extract_combo = Counter((row["region"], row["language"]) for row in page_quality)
    coverage = []
    combos = sorted(set(source_combo) | set(extract_combo))
    for region, language in combos:
        cm = [row for row in raw_mentions if row["region"] == region and row["language"] == language]
        provider_keys = {compact_norm(row["proposed_canonical_name"]) for row in cm if row["entity_class"] == "PROVIDER_CANDIDATE"}
        exclusive_region = {compact_norm(row["canonical_brand_name"]) for row in provider_candidates if row["regions"] == region}
        exclusive_language = {compact_norm(row["canonical_brand_name"]) for row in provider_candidates if row["languages"] == language}
        coverage.append({
            "region": region,
            "language": language,
            "completed_search_operations": len(operation_combo[(region, language)]),
            "search_result_rows": source_combo[(region, language)],
            "unique_search_domains": len(domain_combo[(region, language)]),
            "selected_extract_pages": extract_combo[(region, language)],
            "raw_brand_mentions": len(cm),
            "unique_provider_candidates": len(provider_keys),
            "region_exclusive_candidates": len(provider_keys & exclusive_region),
            "language_exclusive_candidates": len(provider_keys & exclusive_language),
            "limitations": "Extract pages are level C; coverage is discovery-only and not market representativeness.",
        })

    search_urls = {row["canonical_url"] for row in source_rows}
    map_urls = {row["canonical_url"] for row in mapped_rows}
    useful_pages = sum(row["quality_status"] == "USEFUL_NONEMPTY" for row in page_quality)
    stage_rows = [
        {
            "stage": "SEARCH", "operations_used": 10, "primary_output_rows": len(source_rows),
            "unique_outputs": len(search_urls), "useful_downstream_items": 5,
            "value_per_operation": f"{len(search_urls)/10:.3f} unique URLs",
            "marginal_value": "Served: broad discovery across 29 domains, but rankings/promotional noise dominated.",
            "limitations": "49 rows include 8 duplicate URL rows; unique-URL review A/B/C/D/E = 0/5/23/7/6.",
        },
        {
            "stage": "MAP", "operations_used": 5, "primary_output_rows": len(mapped_rows),
            "unique_outputs": len(map_urls), "useful_downstream_items": 8,
            "value_per_operation": f"{len(map_urls)/5:.3f} mapped URLs; {useful_pages/5:.3f} useful Extract pages",
            "marginal_value": f"Served: {len(map_urls-search_urls)} URLs were new versus Search and exposed country-specific ranking pages.",
            "limitations": "Only 3/5 domains returned pages; 111/119 mapped pages were not selected for Extract.",
        },
        {
            "stage": "EXTRACT", "operations_used": 8, "primary_output_rows": len(envelopes),
            "unique_outputs": useful_pages, "useful_downstream_items": len(provider_candidates),
            "value_per_operation": f"{len(raw_mentions)/8:.3f} mentions; {len(new_candidates)/8:.3f} plausible new candidates",
            "marginal_value": "Served: full text exposed ranked names, translated aliases, app/player false positives, and repeated order unavailable from URL/title alone.",
            "limitations": "All pages are level C; high intra-domain duplication and no identity, legality, quality, or reputation proof.",
        },
    ]

    raw_aggregate = hashlib.sha256("\n".join(f"{name}|{digest}" for name, digest in sorted(PROTECTED_RAW_HASHES.items())).encode("utf-8")).hexdigest()
    metrics = {
        "schema_version": SCHEMA,
        "generated_at": generated_at,
        "run_state": "OFFLINE_CONSOLIDATION_COMPLETE",
        "operations_used": {"search": 10, "map": 5, "extract": 8, "global": 23},
        "operations_unused": {"search": 0, "map": 0, "extract": 2, "global": 2},
        "results": {"search_rows": len(source_rows), "search_unique_urls": len(search_urls), "search_unique_domains": len({row['domain'] for row in source_rows}),
                    "map_rows": len(mapped_rows), "map_unique_urls": len(map_urls), "map_new_vs_search": len(map_urls-search_urls),
                    "extract_envelopes": len(envelopes), "extract_nonempty_pages": useful_pages, "extract_empty_pages": len(envelopes)-useful_pages},
        "extract_quality": {"raw_mentions": len(raw_mentions), "unique_normalized_entities": len(comparison), "provider_candidates": len(provider_candidates),
                            "false_positive_entities": len(comparison)-len(provider_candidates), "false_positive_mentions": sum(row['entity_class'] != 'PROVIDER_CANDIDATE' for row in raw_mentions)},
        "historical_comparison": {"historical_rows": 1035, "historical_artifact_sha256": HISTORICAL_1035_SHA256,
                                  "all_entity_status_counts": dict(sorted(status_counts.items())), "provider_status_counts": dict(sorted(provider_status_counts.items())),
                                  "plausible_new_provider_candidates": len(new_candidates), "possible_variants": provider_status_counts["POSSIBLE_VARIANT_REQUIRES_REVIEW"]},
        "independence": {"editorial_groups": len(group_rows), "providers_repeated_across_two_or_more_groups": len(independent_repeat),
                         "new_candidates_repeated_across_two_or_more_groups": len(independent_new)},
        "errors": 0, "automatic_retries": 0, "crawl_operations": 0, "research_operations": 0,
        "global_verdict": "PILOT_SIRVIO_PARCIALMENTE",
        "continuity_decision": "E. Cerrar 1B y pasar a priorización de marcas 1C.",
        "new_calls_authorized": False,
        "protected_raw_aggregate_sha256": raw_aggregate,
    }

    evaluation = {
        "schema_version": SCHEMA,
        "generated_at": generated_at,
        "run_id": "run_20260718_041625",
        "pre_consolidation_tree": {"file_count": 19, "sha256": PRE_TREE_SHA256},
        "historical_universe": {"run_id": "run_20260717_051437", "artifact": "02_raw_brand_mentions.csv", "row_count": 1035, "sha256": HISTORICAL_1035_SHA256},
        "questions": {
            "search_served": True, "map_served": True, "extract_served": True,
            "pilot_really_expanded_historical_universe": bool(new_candidates),
            "plausible_new_candidates": len(new_candidates),
            "plausible_new_candidates_in_independent_groups": len(independent_new),
            "highest_marginal_value_stage": "EXTRACT",
            "next_practical_step": "Manual 1C prioritization of new and variant candidates using source-level and independence caveats; no new acquisition calls.",
        },
        "stage_assessment": {
            "search": "Useful for broad domain discovery, with substantial ranking/promotional noise.",
            "map": "Useful because it exposed 115 URLs not present in Search and enabled eight country/language pages; two selected B domains returned zero.",
            "extract": "Highest semantic value: recovered ranked names, context, translation artifacts, app false positives, and duplication patterns not available from titles/snippets.",
        },
        "duplication_assessment": {
            "within_domain": "High: each publisher repeats templates and brands across regional rankings.",
            "between_domains": f"{len(independent_repeat)} provider candidates recur in at least two independence groups.",
            "independent_corroboration_limit": "Cross-domain repetition is discovery corroboration only; it does not prove a common operator, officiality, legality, quality, or reputation.",
            "seo_affiliate_risk": "Probable, based on affiliate redirects, repeated numbered tables, promotional claims, and similar ranking structures; common ownership was not established.",
        },
        "crawl_evaluation": {
            "execute_now": False, "candidate_domain": "iptvserviceradar.com",
            "potential_additional_information": "Additional country rankings and single-provider review URL topology.",
            "risk": "High template duplication and low marginal independence; could consume pages on near-identical SEO content.",
            "minimum_future_smoke_budget": {"operations": 1, "maximum_pages": 10},
        },
        "research_evaluation": {
            "execute_now": False,
            "candidate_question": "Do public corporate, author, affiliate-disclosure, and contact records show whether the three selected publishers are editorially independent?",
            "why_not_mass_discovery": "Research synthesis can obscure row-level provenance and is inefficient for enumerating brands; it should test a bounded identity/independence question.",
            "minimum_future_smoke_budget": {"operations": 1},
        },
        "global_verdict": "PILOT_SIRVIO_PARCIALMENTE",
        "continuity_decision": {"option": "E", "label": "Cerrar 1B y pasar a priorización de marcas 1C", "authorizes_new_calls": False},
        "limitations": [
            "All eight Extract pages are level C discovery sources.",
            "The two level B selected sources produced zero Map pages.",
            "The pilot does not prove provider identity, quality, legitimacy, legality, reputation, or officiality.",
            "A new candidate is not a valid or recommendable provider.",
            "Spanish machine translation distorted several brand labels; canonical proposals remain reviewable hypotheses.",
        ],
        "protected_raw": {"status": "UNCHANGED", "aggregate_sha256": raw_aggregate, "files": PROTECTED_RAW_HASHES},
        "technical_verdict": "MULTIREGION_PILOT_OFFLINE_EVALUATION_COMPLETE",
    }

    write_csv(RUN / "raw_brand_mentions.csv", list(raw_mentions[0]), raw_mentions)
    write_csv(RUN / "canonical_brand_candidates.csv", list(candidates[0]), candidates)
    write_csv(RUN / "new_vs_historical_brands.csv", list(comparison[0]), comparison)
    write_csv(RUN / "historical_match_review.csv", list(review_rows[0]), review_rows)
    write_csv(RUN / "brand_source_matrix.csv", list(matrix[0]), matrix)
    write_csv(RUN / "source_independence_groups.csv", list(group_rows[0]), group_rows)
    write_csv(RUN / "regional_language_coverage.csv", list(coverage[0]), coverage)
    write_csv(RUN / "extracted_page_quality.csv", list(page_quality[0]), page_quality)
    write_csv(RUN / "stage_value_comparison.csv", list(stage_rows[0]), stage_rows)
    write_json(RUN / "pilot_metrics.json", metrics)
    write_json(RUN / "final_pilot_evaluation.json", evaluation)

    report = f"""# BRAND-FIRST 1B multiregion pilot — offline evaluation

- Run: `run_20260718_041625`
- Acquisition: Search `10/10`, Map `5/5`, Extract `8/8`; global `23/25`
- Errors/retries: `0/0`; Crawl/Research: `0/0`
- Extract quality: `{useful_pages}/8` non-empty useful pages, `{len(raw_mentions)}` raw mentions
- Unique normalized entities: `{len(comparison)}`; provider candidates: `{len(provider_candidates)}`; excluded non-target entities: `{len(comparison)-len(provider_candidates)}`
- Historical universe: `02_raw_brand_mentions.csv`, `1,035` rows, SHA-256 `{HISTORICAL_1035_SHA256}`
- Exact historical matches: `{provider_status_counts['EXACT_HISTORICAL_MATCH']}`
- Normalized historical matches: `{provider_status_counts['NORMALIZED_HISTORICAL_MATCH']}`
- Possible variants requiring review: `{provider_status_counts['POSSIBLE_VARIANT_REQUIRES_REVIEW']}`
- Plausible new provider candidates: `{len(new_candidates)}`
- Providers repeated across >=2 independence groups: `{len(independent_repeat)}`
- New candidates repeated across >=2 independence groups: `{len(independent_new)}`

## Stage value

Search served for broad discovery, but contained ranking/promotional noise. Map
served by adding `{len(map_urls-search_urls)}` URLs beyond Search and exposing the eight country/language pages.
Extract added the highest semantic value because full content revealed ranked
names, translated labels, false positives and duplication that titles/snippets
could not establish.

## Independence and limitations

The eight pages belong to only three editorial independence groups. Within each
domain, repeated templates and recurring brand order indicate probable SEO or
affiliate duplication. Cross-domain repetition is discovery corroboration only.
All Extract sources are level C; the selected level B sources returned zero Map
pages. No result proves identity, officiality, legality, legitimacy, quality or
reputation, and a new candidate is not a recommendation.

## Decision

- Global verdict: `PILOT_SIRVIO_PARCIALMENTE`
- Continuity: `E. Cerrar 1B y pasar a priorización de marcas 1C.`
- New Crawl/Research calls authorized: `NO`
- Technical verdict: `MULTIREGION_PILOT_OFFLINE_EVALUATION_COMPLETE`
"""
    atomic_bytes(RUN / "pilot_report.md", report.encode("utf-8"))

    artifact_names = sorted(path.name for path in RUN.iterdir() if path.is_file() and path.name != "integrity_manifest.json")
    integrity = {
        "schema_version": SCHEMA,
        "generated_at": generated_at,
        "run_id": "run_20260718_041625",
        "artifacts": {name: {"size": (RUN / name).stat().st_size, "sha256": sha256(RUN / name),
                             "role": "PROTECTED_RAW" if name in PROTECTED_RAW_HASHES else "DERIVED_OR_CONTROL"}
                      for name in artifact_names},
        "protected_raw_status": "UNCHANGED",
        "protected_raw_aggregate_sha256": raw_aggregate,
        "historical_reference": {"path": str((HIST / "02_raw_brand_mentions.csv").relative_to(ROOT)), "rows": 1035, "sha256": HISTORICAL_1035_SHA256},
        "self_hash_omitted": True,
    }
    write_json(RUN / "integrity_manifest.json", integrity)

    # Final invariant check after every write.
    validate_inputs()
    print(f"RAW_MENTIONS={len(raw_mentions)}")
    print(f"UNIQUE_ENTITIES={len(comparison)}")
    print(f"PROVIDER_CANDIDATES={len(provider_candidates)}")
    print(f"NEW_BRAND_CANDIDATES={len(new_candidates)}")
    print(f"INDEPENDENT_NEW_CANDIDATES={len(independent_new)}")
    print("OFFLINE_CONSOLIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
