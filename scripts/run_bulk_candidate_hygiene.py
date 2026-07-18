#!/usr/bin/env python3
"""Offline candidate hygiene for a completed Bulk Ranking Harvest run.

This script never imports Tavily, reads credentials, or performs network I/O.
Preflight computes the complete result in memory. Execute writes only derived
artifacts and refreshes the run integrity manifest after proving raw inputs are
byte-identical.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import tempfile
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "bulk_candidate_hygiene.v1"
EXPECTED_RUN_ID = "run_20260718_180950"
EXPECTED_PLAN_HASH = "db3b88e7114cb057e24516c75d4a007a1ce838bd2adc5d34f368533acedf01d4"
EXPECTED_INITIAL_CANDIDATES = 960
RAW_FILES = (
    "search_results.jsonl",
    "mapped_results.jsonl",
    "crawled_pages.jsonl",
    "extracted_pages.jsonl",
)
INPUT_FILES = (
    "manifest.json",
    "checkpoint.json",
    "bulk_harvest_metrics.json",
    "canonical_iptv_names.csv",
    "raw_brand_mentions.csv",
    "integrity_manifest.json",
) + RAW_FILES

OUTPUT_CSV_FIELDS: dict[str, tuple[str, ...]] = {
    "candidate_hygiene_audit.csv": (
        "candidate_id", "original_name", "corrected_name", "canonical_key",
        "final_classification", "reason", "mention_count", "page_count",
        "domain_count", "regions", "languages", "source_levels",
        "max_source_level", "historical_status", "supporting_row_ids",
    ),
    "cleaned_iptv_service_candidates.csv": (
        "canonical_id", "original_name", "canonical_name", "normalized_name",
        "variants", "mention_count", "page_count", "domain_count", "regions",
        "languages", "source_levels", "max_source_level", "historical_status",
        "domain_points", "source_quality_points", "recency_points",
        "diversity_points", "penalty_points", "penalty_reasons", "ranking_score",
        "review_status", "supporting_row_ids",
    ),
    "corrected_name_variants.csv": (
        "candidate_id", "original_name", "corrected_name", "canonical_key",
        "correction_applied", "mojibake_repaired", "final_classification",
        "supporting_row_ids",
    ),
    "excluded_promotional_phrases.csv": (
        "candidate_id", "original_name", "corrected_name", "reason",
        "mention_count", "domain_count", "supporting_row_ids",
    ),
    "excluded_players_apps.csv": (
        "candidate_id", "original_name", "corrected_name", "reason",
        "mention_count", "domain_count", "supporting_row_ids",
    ),
    "excluded_hardware.csv": (
        "candidate_id", "original_name", "corrected_name", "reason",
        "mention_count", "domain_count", "supporting_row_ids",
    ),
    "excluded_channels_platforms.csv": (
        "candidate_id", "original_name", "corrected_name", "reason",
        "mention_count", "domain_count", "supporting_row_ids",
    ),
    "excluded_generic_terms.csv": (
        "candidate_id", "original_name", "corrected_name", "reason",
        "mention_count", "domain_count", "supporting_row_ids",
    ),
    "excluded_other_false_positives.csv": (
        "candidate_id", "original_name", "corrected_name", "reason",
        "mention_count", "domain_count", "supporting_row_ids",
    ),
    "ambiguous_review_queue.csv": (
        "candidate_id", "original_name", "corrected_name", "reason",
        "mention_count", "page_count", "domain_count", "regions", "languages",
        "source_levels", "historical_status", "supporting_row_ids",
    ),
    "final_brand_ranking.csv": (
        "rank", "canonical_id", "canonical_name", "ranking_score",
        "domain_points", "source_quality_points", "recency_points",
        "diversity_points", "penalty_points", "penalty_reasons", "mention_count",
        "page_count", "domain_count", "max_source_level", "regions", "languages",
        "historical_status", "review_status", "variants", "supporting_row_ids",
    ),
    "final_top_50_ranked_names.csv": (
        "rank", "canonical_id", "canonical_name", "ranking_score",
        "mention_count", "page_count", "domain_count", "max_source_level",
        "regions", "languages", "historical_status", "review_status",
        "supporting_row_ids",
    ),
    "final_top_20_testing_queue.csv": (
        "rank", "canonical_id", "canonical_name", "ranking_score",
        "mention_count", "page_count", "domain_count", "max_source_level",
        "regions", "languages", "historical_status", "review_status",
        "testing_status", "supporting_row_ids",
    ),
}

PROMOTIONAL_PATTERNS = (
    "comece seu teste", "comece agora", "teste gratis", "testar gratis",
    "assine agora", "compre agora", "clique aqui", "escolha seu plano",
    "seu teste iptv", "teste iptv", "get started", "start your trial",
    "start free trial", "free trial", "buy now", "subscribe now", "sign up",
    "customer support", "customer service", "contact us", "best price",
    "view plans", "check for free trial", "try it free", "teste gratuito", "clique",
    "add your subscription", "comprar iptv", "escolha o provedor",
)
KNOWN_PLAYERS = (
    "gse smart iptv", "iptv smarters pro", "iptv smarters", "smarters pro",
    "tivimate", "iptv extreme", "xciptv player", "xciptv", "smart iptv",
    "perfect player", "ott navigator", "stbemu", "ibo player", "hot iptv",
    "flix iptv player", "smart one iptv", "duplex play", "set iptv",
    "net iptv", "ss iptv", "televizo", "implayer", "sparkle tv player",
    "smarters iptv", "vlc", "kodi",
)
HARDWARE_EXACT = (
    "tv box", "android box", "android tv box", "firestick", "fire tv stick",
    "mag box", "mag device", "set top box", "decoder", "decodificador",
    "dispositivo", "device", "streaming device", "iptv firestick",
    "lg smart tv", "samsung smart tv",
)
KNOWN_PLATFORMS = (
    "netflix", "hulu", "pluto tv", "youtube tv", "sling tv", "fubo tv",
    "fubo iptv", "disney plus", "disney+", "hbo max", "max", "espn plus",
    "amazon prime video", "apple tv plus", "apple tv+", "peacock", "dazn",
    "peacock tv", "fubotv", "tubi tv", "soul tv", "rlaxx tv",
    "samsung tv plus", "claro tv+", "bell fibe tv", "rogers ignite tv",
    "shaw bluesky tv", "spectrum tv", "roku channel", "paramount plus",
    "paramount+",
)
GENERIC_EXACT = {
    "iptv", "iptv service", "iptv services", "iptv provider", "iptv providers",
    "premium iptv", "live tv", "vod", "customer service", "customer support",
    "subscription", "subscriptions", "playlist", "epg", "smart tv", "rank",
    "ranking", "feature", "features", "servicios", "service overview",
    "iptv requirements", "device compatibility", "catch up tv", "monthly cost",
    "multi device support", "no contracts", "use a vpn", "channel lineup",
    "streaming service", "iptv subscription", "tv channels", "movies tv shows",
    "support", "pricing", "plans", "channels", "iptv apps", "iptv app",
    "catch up tv", "day catch up tv", "epg catch up tv", "4k iptv",
    "4k live iptv", "4k en vivo iptv", "iptv us", "euro iptv",
    "vod iptv", "iptv vpn", "m3u playlist", "listas iptv", "televisao iptv",
    "streaming quality", "no of channels", "official website", "sports",
    "verified", "unverified", "movies tv shows", "international viewers",
    "epg tv guide", "stream iptv 4k", "time shifted tv", "movie iptv",
}
EDITORIAL_MARKERS = (
    "best iptv", "top iptv", "melhores ", "mejores ", "ranking ",
    "comparison", "comparativa", "comparacao", "conclusao", "conclusion",
    "perguntas frequentes", "duvidas frequentes", "frequently asked",
    "quick answer", "what is", "o que e", "how to", "como escolher",
    "criterios para", "benefits of", "vantagens", "requirements",
    "terminologia", "understanding ", "guide to", "everything you need",
    "service overview", "channel lineup", "content quality", "reliability",
    "device compatibility", "massive channel", "selection criteria",
    "test during", "atencion al cliente", "atendimento ao cliente",
    "por cidade", "por conteudo", "outras cidades", "plataformas de teste",
    "table of", "comparison table", "pilares del contenido", "faq",
    "affordable iptv", "legal considerations", "key features", "pros and cons",
    "simultaneous connections", "anti freeze technology", "cheapest reliable",
    "not loading", "equipe editorial", "for most people", "github ",
    "installing iptv", "technically stable", "true 4k", "verified 4k",
    "cable vs iptv", "backup server", "consequences of", "legal iptv providers",
    "multi connections", "one click subscription", "time shifted tv",
    "top rated iptv", "unlicensed iptv", "vpn support", "asistencia al cliente",
    "calidad de transmision", "qualidade de transmissao", "visit ",
    "listas iptv", "precios realistas", "relevancia del canal", "original iptv",
    "streaming quality", "no of channels", "who should avoid", "day catch up",
    "how iptv works", "reproductores iptv recomendados", "television a tu manera",
)
GENERIC_BASE_WORDS = {
    "best", "premium", "live", "service", "services", "provider", "providers",
    "subscription", "subscriptions", "streaming", "smart", "digital", "global",
    "online", "official", "review", "reviews", "test", "teste", "gratis",
    "free", "trial", "price", "pricing", "plan", "plans", "support", "channel",
    "channels", "content", "device", "devices", "player", "app", "apps",
    "platform", "platforms", "lista", "ranking", "comparison", "melhor",
    "melhores", "mejor", "mejores", "servico", "servicos", "servicio",
    "servicios", "provedor", "provedores", "proveedor", "proveedores",
}
SOURCE_ORDER = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "": 0}


class HygieneError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def split_ids(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split("|") if part.strip()]


def joined(values: Iterable[str]) -> str:
    return " | ".join(sorted({value for value in values if value}))


def fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return re.sub(r"\s+", " ", "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()).strip()


def normalized_words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", fold(value))


def lexical(value: str) -> str:
    return " ".join(normalized_words(value))


def repair_mojibake(value: str) -> tuple[str, bool]:
    current = unicodedata.normalize("NFC", value or "").strip()
    markers = ("Ã", "Â", "â€", "â€™", "â€œ", "â€�")
    if not any(marker in current for marker in markers):
        return current, False
    candidates = [current]
    for encoding in ("latin-1", "cp1252"):
        try:
            candidates.append(current.encode(encoding).decode("utf-8"))
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    best = min(candidates, key=lambda item: sum(item.count(marker) for marker in markers))
    return unicodedata.normalize("NFC", best), best != current


def clean_name(value: str) -> tuple[str, bool]:
    repaired, mojibake = repair_mojibake(value)
    cleaned = re.sub(r"^[#*`\s]+|[#*`\s]+$", "", repaired)
    cleaned = re.sub(r"^[^\w]+", "", cleaned, flags=re.UNICODE)
    cleaned = re.sub(r"^(?:n\.?\s*[ºo°]?|#)?\s*\d{1,3}\s*[.):\-–—]+\s*", "", cleaned, flags=re.I)
    match = re.match(r"^(?:key features|pros and cons) of\s+(.+)$", cleaned, flags=re.I)
    if match:
        cleaned = match.group(1)
    match = re.match(r"^(?:best overall|best for [^:]+):\s*(.+)$", cleaned, flags=re.I)
    if match:
        cleaned = match.group(1)
    match = re.match(r"^(?:=>\s*)?visit\s+(.+?)\s+website$", cleaned, flags=re.I)
    if match:
        cleaned = match.group(1)
    cleaned = re.sub(
        r"\s*[—–-]\s*(?:key features|pricing|pros and cons|premium .*? iptv service)\s*$",
        "", cleaned, flags=re.I,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" \t\r\n|–—-")
    words = cleaned.split()
    if len(words) >= 2 and len(words) % 2 == 0:
        half = len(words) // 2
        if fold(" ".join(words[:half])) == fold(" ".join(words[half:])):
            cleaned = " ".join(words[:half])
    return cleaned, mojibake


def canonical_key(value: str) -> str:
    words = normalized_words(value)
    if words and words[-1] == "iptv":
        words = words[:-1]
    compact = "".join(words)
    if compact.startswith("iptv") and len(compact) > 8:
        compact = compact[4:]
    if compact.endswith("iptv") and len(compact) > 8:
        compact = compact[:-4]
    elif compact.endswith("tv") and len(compact) > 5:
        compact = compact[:-2]
    return compact


def contains_phrase(text: str, phrases: Iterable[str]) -> str | None:
    folded = lexical(text)
    for phrase in phrases:
        if lexical(phrase) in folded:
            return phrase
    return None


def looks_brandish(name: str) -> bool:
    words = normalized_words(name)
    folded = lexical(name)
    if not words or len(words) > 5:
        return False
    if contains_phrase(folded, EDITORIAL_MARKERS):
        return False
    core = [word for word in words if word not in {"iptv", "tv"}]
    if not core or all(word in GENERIC_BASE_WORDS for word in core):
        return False
    if "iptv" in words or folded.endswith("tv") or " tv" in folded:
        return True
    original_tokens = re.findall(r"[A-Za-z0-9]+", name)
    camel_or_caps = any(re.search(r"[a-z][A-Z]|[A-Z]{3,}|\d", token) for token in original_tokens)
    return len(words) <= 3 and camel_or_caps


def fragment_reason(name: str) -> str | None:
    folded = lexical(name)
    words = normalized_words(name)
    if len(words) > 8:
        return "MORE_THAN_EIGHT_WORDS"
    if re.search(r"[.!?;:]\s*$", name.strip()):
        return "SENTENCE_PUNCTUATION"
    if re.search(r"(?:[$€£]\s*\d|\b\d+[,.]?\d*\+?\s*(?:tv\s+)?(?:channels?|canais|canales|days?|dias|months?|meses|hours?|horas|connections?|gb|mbps)|\b\d[\d,.]*\+?\s+(?:[a-z0-9]+\s+){0,3}(?:channels?|services?\s+tested)\b|\b\d+\+)", folded):
        return "PRICE_DURATION_OR_FEATURE_COUNT"
    marker = contains_phrase(folded, EDITORIAL_MARKERS)
    if marker:
        return f"EDITORIAL_HEADING:{fold(marker)}"
    if re.search(r"(?:→|←|\bselect\b|\bseleccionar\b|\bchoose\b)", folded):
        return "INSTRUCTION_FRAGMENT"
    if len(words) == 1 and (not looks_brandish(name) or words[0].isdigit()):
        return "UNBRANDED_SINGLE_TERM"
    return None


def classify_candidate(row: dict[str, Any]) -> tuple[str, str]:
    name = row["corrected_name"]
    folded = lexical(name)
    promo = contains_phrase(folded, PROMOTIONAL_PATTERNS)
    if promo:
        return "EXCLUDED_PROMOTIONAL_PHRASE", f"PROMOTIONAL:{fold(promo)}"
    if folded in {lexical(item) for item in KNOWN_PLAYERS}:
        return "EXCLUDED_PLAYER_APP", "KNOWN_PLAYER_APP"
    if any(lexical(item) in folded for item in KNOWN_PLAYERS if len(normalized_words(item)) >= 2):
        return "EXCLUDED_PLAYER_APP", "KNOWN_PLAYER_APP_PHRASE"
    if folded in {lexical(item) for item in HARDWARE_EXACT}:
        return "EXCLUDED_HARDWARE", "EVIDENT_HARDWARE_OR_DEVICE"
    if folded in {lexical(item) for item in KNOWN_PLATFORMS} or any(
        folded.startswith(lexical(item) + " ") for item in KNOWN_PLATFORMS if len(normalized_words(item)) >= 2
    ):
        return "EXCLUDED_CHANNEL_OR_PLATFORM", "KNOWN_CHANNEL_OR_LEGAL_PLATFORM"
    compact = "".join(normalized_words(name))
    generic_lexical = {lexical(item) for item in GENERIC_EXACT}
    if folded in generic_lexical or compact in {
        "bestiptv", "bestiptvprovider", "bestiptvproviderplus",
        "bestiptvsubscriptionpro", "iptvsubscriptiontv", "1iptvprovdier",
        "1iptvprovider", "catchuptv", "moviesandtvshows",
    }:
        return "EXCLUDED_GENERIC_TERM", "GENERIC_IPTV_OR_FEATURE_TERM"
    if re.fullmatch(r"(?:iptv\s+)?(?:usa?|canada|germany|brasil|brazil|mexico|colombia|portugal|europe|euro)(?:\s+iptv)?", folded):
        return "EXCLUDED_GENERIC_TERM", "COUNTRY_OR_REGION_PLUS_GENERIC_IPTV"
    reason = fragment_reason(name)
    if reason:
        return "EXCLUDED_OTHER_FALSE_POSITIVE", reason
    possible_hardware = any(term in folded for term in ("box", "firestick", "device", "dispositivo", "decoder", "mag "))
    possible_player = "player" in folded or folded.endswith(" app")
    evidence = row["domain_count"] >= 2 or row["page_count"] >= 2 or row["mention_count"] >= 2
    historical = row["historical_status"] == "HISTORICAL_MATCH"
    if looks_brandish(name) and (evidence or historical) and not (possible_hardware or possible_player):
        return "IPTV_SERVICE_CANDIDATE", "COMMERCIAL_NAME_WITH_RANKING_EVIDENCE"
    if looks_brandish(name):
        qualifier = "POSSIBLE_PLAYER_OR_HARDWARE" if possible_hardware or possible_player else "INSUFFICIENT_CONTEXT"
        return "REVIEW", qualifier
    return "EXCLUDED_OTHER_FALSE_POSITIVE", "NO_CLEAR_COMMERCIAL_IDENTITY"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def validate_jsonl(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                raise HygieneError(f"invalid JSONL {path.name}:{number}: {exc}") from exc
            count += 1
    return count


def tree_hash(run_dir: Path) -> str:
    rows = [f"{path.name}\t{sha256_file(path)}" for path in sorted(run_dir.iterdir(), key=lambda item: item.name) if path.is_file()]
    return sha256_bytes("\n".join(rows).encode("utf-8"))


def validate_run(run_dir: Path) -> dict[str, Any]:
    if run_dir.name != EXPECTED_RUN_ID:
        raise HygieneError(f"unexpected run id: {run_dir.name}")
    for name in INPUT_FILES:
        if not (run_dir / name).is_file():
            raise HygieneError(f"missing required input: {name}")
    for path in run_dir.iterdir():
        if path.is_file():
            path.read_text(encoding="utf-8")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    checkpoint = json.loads((run_dir / "checkpoint.json").read_text(encoding="utf-8"))
    metrics = json.loads((run_dir / "bulk_harvest_metrics.json").read_text(encoding="utf-8"))
    integrity = json.loads((run_dir / "integrity_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("state") != "COMPLETE" or checkpoint.get("state") != "COMPLETE":
        raise HygieneError("manifest and checkpoint must both be COMPLETE")
    if manifest.get("plan_hash") != EXPECTED_PLAN_HASH or checkpoint.get("plan_hash") != EXPECTED_PLAN_HASH:
        raise HygieneError("plan hash mismatch")
    expected_counts = {
        "search": 24, "map": 10, "crawl": 2, "extract": 1, "global": 37,
    }
    if metrics.get("request_counts") != expected_counts:
        raise HygieneError(f"unexpected request counts: {metrics.get('request_counts')}")
    for name, metadata in integrity.get("artifacts", {}).items():
        path = run_dir / name
        if not path.is_file() or sha256_file(path) != metadata.get("sha256"):
            raise HygieneError(f"existing integrity mismatch: {name}")
    jsonl_counts = {name: validate_jsonl(run_dir / name) for name in RAW_FILES + ("operation_ledger.jsonl", "errors.jsonl")}
    if jsonl_counts["search_results.jsonl"] != 24 or jsonl_counts["mapped_results.jsonl"] != 10:
        raise HygieneError(f"unexpected raw operation rows: {jsonl_counts}")
    return {
        "manifest": manifest,
        "checkpoint": checkpoint,
        "metrics": metrics,
        "initial_tree_hash": tree_hash(run_dir),
        "raw_hashes": {name: sha256_file(run_dir / name) for name in RAW_FILES},
        "jsonl_counts": jsonl_counts,
    }


def mention_stats(mentions: list[dict[str, str]]) -> dict[str, Any]:
    pages = {row.get("page_row_id", "") for row in mentions if row.get("page_row_id")}
    domains = {row.get("domain", "") for row in mentions if row.get("domain")}
    regions = {row.get("region", "") for row in mentions if row.get("region")}
    languages = {row.get("language", "") for row in mentions if row.get("language")}
    levels = {row.get("source_level", "") for row in mentions if row.get("source_level")}
    max_level = max(levels, key=lambda item: SOURCE_ORDER.get(item, 0), default="")
    return {
        "mention_count": len(mentions),
        "page_count": len(pages),
        "domain_count": len(domains),
        "regions_set": regions,
        "languages_set": languages,
        "source_levels_set": levels,
        "regions": joined(regions),
        "languages": joined(languages),
        "source_levels": joined(levels),
        "max_source_level": max_level,
        "supporting_ids_set": {row["mention_row_id"] for row in mentions},
        "supporting_row_ids": joined(row["mention_row_id"] for row in mentions),
    }


def initial_rows(run_dir: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    canonical = read_csv(run_dir / "canonical_iptv_names.csv")
    if len(canonical) != EXPECTED_INITIAL_CANDIDATES:
        raise HygieneError(f"expected 960 canonical candidates, found {len(canonical)}")
    mentions = {row["mention_row_id"]: row for row in read_csv(run_dir / "raw_brand_mentions.csv")}
    prepared: list[dict[str, Any]] = []
    for row in canonical:
        ids = [item for item in split_ids(row.get("supporting_row_ids", "")) if item.startswith("mention_")]
        missing = [item for item in ids if item not in mentions]
        if missing:
            raise HygieneError(f"missing supporting mention IDs for {row['canonical_id']}: {missing[:3]}")
        source_mentions = [mentions[item] for item in ids]
        corrected, mojibake = clean_name(row["canonical_name"])
        stats = mention_stats(source_mentions)
        prepared_row: dict[str, Any] = {
            "candidate_id": row["canonical_id"],
            "original_name": row["canonical_name"],
            "corrected_name": corrected,
            "canonical_key": canonical_key(corrected),
            "mojibake_repaired": mojibake,
            "historical_status": row.get("historical_status", ""),
            "variants_set": set(split_ids(row.get("variants", ""))) | {row["canonical_name"], corrected},
            "mentions": source_mentions,
            **stats,
        }
        classification, reason = classify_candidate(prepared_row)
        prepared_row["final_classification"] = classification
        prepared_row["reason"] = reason
        prepared.append(prepared_row)
    return prepared, mentions


def penalty_for(group: dict[str, Any]) -> tuple[int, list[str]]:
    penalties: list[tuple[int, str]] = []
    levels = group["source_levels_set"]
    if group["mention_count"] == 1 and group["domain_count"] == 1 and levels == {"C"}:
        penalties.append((20, "SINGLE_MENTION_SOURCE_C"))
    core = [word for word in normalized_words(group["canonical_name"]) if word not in {"iptv", "tv"}]
    if core and all(word in GENERIC_BASE_WORDS for word in core):
        penalties.append((15, "EXTREMELY_GENERIC_NAME"))
    contexts = [fold(row.get("context", "")) for row in group["mentions"]]
    promotional = sum(any(fold(pattern) in context for pattern in PROMOTIONAL_PATTERNS) for context in contexts)
    if contexts and promotional / len(contexts) >= 0.5:
        penalties.append((10, "PREDOMINANTLY_PROMOTIONAL_CONTEXT"))
    folded_name = fold(group["canonical_name"])
    if any(term in folded_name for term in ("box", "firestick", "device", "player", " app")):
        penalties.append((10, "POSSIBLE_PLAYER_OR_HARDWARE"))
    normalized_contexts = [re.sub(r"\W+", " ", context).strip() for context in contexts if context]
    if len(normalized_contexts) >= 3:
        most_common = Counter(normalized_contexts).most_common(1)[0][1]
        if group["domain_count"] >= 2 and most_common / len(normalized_contexts) >= 0.67:
            penalties.append((10, "HIGH_SEO_DUPLICATION_PROBABILITY"))
    return sum(points for points, _ in penalties), [reason for _, reason in penalties]


def aggregate_services(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["final_classification"] == "IPTV_SERVICE_CANDIDATE":
            groups[row["canonical_key"] or row["candidate_id"]].append(row)
    services: list[dict[str, Any]] = []
    for key, members in groups.items():
        members.sort(key=lambda row: (-row["domain_count"], -row["mention_count"], len(row["corrected_name"]), row["corrected_name"].casefold()))
        display = members[0]["corrected_name"]
        mentions_by_id = {
            mention["mention_row_id"]: mention
            for member in members
            for mention in member["mentions"]
        }
        mentions = list(mentions_by_id.values())
        stats = mention_stats(mentions)
        variants = {variant for member in members for variant in member["variants_set"]}
        historical = "HISTORICAL_MATCH" if any(member["historical_status"] == "HISTORICAL_MATCH" for member in members) else "NEW_OR_VARIANT_CANDIDATE"
        group: dict[str, Any] = {
            "canonical_id": "hygiene_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24],
            "original_name": members[0]["original_name"],
            "canonical_name": display,
            "normalized_name": " ".join(normalized_words(display)),
            "variants": joined(variants),
            "historical_status": historical,
            "mentions": mentions,
            **stats,
        }
        domain_points = min(50, group["domain_count"] * 10)
        source_points = {"A": 25, "B": 20, "C": 12, "D": 5, "E": 0}.get(group["max_source_level"], 0)
        evidence_text = " ".join((row.get("url", "") + " " + row.get("context", "")) for row in mentions)
        recency_points = 15 if "2026" in evidence_text else 10 if "2025" in evidence_text else 5
        diversity_points = min(10, len(group["regions_set"]) * 3 + len(group["languages_set"]) * 2)
        penalty_points, penalty_reasons = penalty_for(group)
        score = max(0, min(100, domain_points + source_points + recency_points + diversity_points - penalty_points))
        group.update({
            "domain_points": domain_points,
            "source_quality_points": source_points,
            "recency_points": recency_points,
            "diversity_points": diversity_points,
            "penalty_points": penalty_points,
            "penalty_reasons": joined(penalty_reasons),
            "ranking_score": score,
            "review_status": "APPROVED_OFFLINE_CANDIDATE",
        })
        services.append(group)
    services.sort(key=lambda row: (-row["ranking_score"], -row["domain_count"], -row["page_count"], -row["mention_count"], row["canonical_name"].casefold()))
    for rank, row in enumerate(services, 1):
        row["rank"] = rank
    return services


def excluded_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": row["candidate_id"],
        "original_name": row["original_name"],
        "corrected_name": row["corrected_name"],
        "reason": row["reason"],
        "mention_count": row["mention_count"],
        "domain_count": row["domain_count"],
        "supporting_row_ids": row["supporting_row_ids"],
    }


def project(row: dict[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    return {field: row.get(field, "") for field in fields}


def quality_control(top20: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    if len(top20) != 20:
        failures.append(f"TOP20_ROW_COUNT:{len(top20)}")
    for row in top20:
        name = row["canonical_name"]
        classification, reason = classify_candidate({
            **row,
            "corrected_name": name,
            "historical_status": row.get("historical_status", ""),
        })
        if classification != "IPTV_SERVICE_CANDIDATE":
            failures.append(f"TOP20_INVALID:{name}:{classification}:{reason}")
        if not row.get("supporting_row_ids"):
            failures.append(f"TOP20_MISSING_SUPPORT:{name}")
    if len({row["canonical_name"].casefold() for row in top20}) != len(top20):
        failures.append("TOP20_DUPLICATE_NAMES")
    return failures


def build_outputs(run_dir: Path, validation: dict[str, Any]) -> dict[str, Any]:
    rows, _ = initial_rows(run_dir)
    services = aggregate_services(rows)
    top50 = services[:50]
    top20 = services[:20]
    qc_failures = quality_control(top20)
    if qc_failures:
        raise HygieneError("; ".join(qc_failures))

    audit = [{
        "candidate_id": row["candidate_id"],
        "original_name": row["original_name"],
        "corrected_name": row["corrected_name"],
        "canonical_key": row["canonical_key"],
        "final_classification": row["final_classification"],
        "reason": row["reason"],
        "mention_count": row["mention_count"],
        "page_count": row["page_count"],
        "domain_count": row["domain_count"],
        "regions": row["regions"],
        "languages": row["languages"],
        "source_levels": row["source_levels"],
        "max_source_level": row["max_source_level"],
        "historical_status": row["historical_status"],
        "supporting_row_ids": row["supporting_row_ids"],
    } for row in rows]
    variants = [{
        "candidate_id": row["candidate_id"],
        "original_name": row["original_name"],
        "corrected_name": row["corrected_name"],
        "canonical_key": row["canonical_key"],
        "correction_applied": row["original_name"] != row["corrected_name"],
        "mojibake_repaired": row["mojibake_repaired"],
        "final_classification": row["final_classification"],
        "supporting_row_ids": row["supporting_row_ids"],
    } for row in rows]
    review = [{
        "candidate_id": row["candidate_id"], "original_name": row["original_name"],
        "corrected_name": row["corrected_name"], "reason": row["reason"],
        "mention_count": row["mention_count"], "page_count": row["page_count"],
        "domain_count": row["domain_count"], "regions": row["regions"],
        "languages": row["languages"], "source_levels": row["source_levels"],
        "historical_status": row["historical_status"],
        "supporting_row_ids": row["supporting_row_ids"],
    } for row in rows if row["final_classification"] == "REVIEW"]

    class_counts = Counter(row["final_classification"] for row in rows)
    metrics = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "run_id": EXPECTED_RUN_ID,
        "source_plan_hash": EXPECTED_PLAN_HASH,
        "initial_tree_hash": validation["initial_tree_hash"],
        "raw_hashes_before": validation["raw_hashes"],
        "raw_byte_identical": True,
        "initial_candidates": len(rows),
        "final_service_candidates": len(services),
        "review_candidates": len(review),
        "excluded_promotional_phrases": class_counts["EXCLUDED_PROMOTIONAL_PHRASE"],
        "excluded_players_apps": class_counts["EXCLUDED_PLAYER_APP"],
        "excluded_hardware": class_counts["EXCLUDED_HARDWARE"],
        "excluded_channels_platforms": class_counts["EXCLUDED_CHANNEL_OR_PLATFORM"],
        "excluded_generic_terms": class_counts["EXCLUDED_GENERIC_TERM"],
        "excluded_other_false_positives": class_counts["EXCLUDED_OTHER_FALSE_POSITIVE"],
        "false_positive_reduction_percent": round((1 - len(services) / len(rows)) * 100, 2),
        "top_50_rows": len(top50),
        "top_20_rows": len(top20),
        "top_20_quality_control": "PASS",
        "mojibake_repairs": sum(bool(row["mojibake_repaired"]) for row in rows),
        "network_operations": 0,
        "tavily_operations": 0,
        "next_phase": "IPTV-SERVICE-REAL-WORLD-TESTING-01",
    }

    csv_outputs: dict[str, list[dict[str, Any]]] = {
        "candidate_hygiene_audit.csv": audit,
        "cleaned_iptv_service_candidates.csv": [project(row, OUTPUT_CSV_FIELDS["cleaned_iptv_service_candidates.csv"]) for row in services],
        "corrected_name_variants.csv": variants,
        "excluded_promotional_phrases.csv": [excluded_row(row) for row in rows if row["final_classification"] == "EXCLUDED_PROMOTIONAL_PHRASE"],
        "excluded_players_apps.csv": [excluded_row(row) for row in rows if row["final_classification"] == "EXCLUDED_PLAYER_APP"],
        "excluded_hardware.csv": [excluded_row(row) for row in rows if row["final_classification"] == "EXCLUDED_HARDWARE"],
        "excluded_channels_platforms.csv": [excluded_row(row) for row in rows if row["final_classification"] == "EXCLUDED_CHANNEL_OR_PLATFORM"],
        "excluded_generic_terms.csv": [excluded_row(row) for row in rows if row["final_classification"] == "EXCLUDED_GENERIC_TERM"],
        "excluded_other_false_positives.csv": [excluded_row(row) for row in rows if row["final_classification"] == "EXCLUDED_OTHER_FALSE_POSITIVE"],
        "ambiguous_review_queue.csv": review,
        "final_brand_ranking.csv": [project(row, OUTPUT_CSV_FIELDS["final_brand_ranking.csv"]) for row in services],
        "final_top_50_ranked_names.csv": [project(row, OUTPUT_CSV_FIELDS["final_top_50_ranked_names.csv"]) for row in top50],
        "final_top_20_testing_queue.csv": [
            project({**row, "testing_status": "PENDING_REAL_WORLD_TESTING"}, OUTPUT_CSV_FIELDS["final_top_20_testing_queue.csv"])
            for row in top20
        ],
    }
    report_lines = [
        "# Final offline candidate hygiene report", "",
        f"- Run: `{EXPECTED_RUN_ID}`",
        f"- Initial candidates: {len(rows)}",
        f"- Final service candidates: {len(services)}",
        f"- REVIEW: {len(review)}",
        f"- Reduction: {metrics['false_positive_reduction_percent']}%",
        f"- Top 20 quality control: PASS", "",
        "## Exclusions", "",
        f"- Promotional phrases: {metrics['excluded_promotional_phrases']}",
        f"- Players/apps: {metrics['excluded_players_apps']}",
        f"- Hardware: {metrics['excluded_hardware']}",
        f"- Channels/platforms: {metrics['excluded_channels_platforms']}",
        f"- Generic terms: {metrics['excluded_generic_terms']}",
        f"- Other false positives: {metrics['excluded_other_false_positives']}", "",
        "## Final Top 20", "",
        "| Rank | Name | Score | Mentions | Domains | Pages | Source | Regions | Languages | Status |",
        "|---:|---|---:|---:|---:|---:|---|---|---|---|",
    ]
    for row in top20:
        report_lines.append(
            f"| {row['rank']} | {row['canonical_name']} | {row['ranking_score']} | "
            f"{row['mention_count']} | {row['domain_count']} | {row['page_count']} | "
            f"{row['max_source_level']} | {row['regions']} | {row['languages']} | "
            f"{row['review_status']} |"
        )
    report_lines.extend(["", "Next phase: `IPTV-SERVICE-REAL-WORLD-TESTING-01` (not executed).", ""])
    return {
        "rows": rows,
        "services": services,
        "review": review,
        "top50": top50,
        "top20": top20,
        "metrics": metrics,
        "csv_outputs": csv_outputs,
        "report": "\n".join(report_lines),
    }


def atomic_bytes(path: Path, data: bytes) -> None:
    handle = tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False)
    temp_path = Path(handle.name)
    try:
        with handle:
            handle.write(data)
            handle.flush()
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def csv_bytes(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> bytes:
    import io
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def write_outputs(run_dir: Path, result: dict[str, Any], validation: dict[str, Any]) -> None:
    for name, rows in result["csv_outputs"].items():
        atomic_bytes(run_dir / name, csv_bytes(rows, OUTPUT_CSV_FIELDS[name]))
    atomic_bytes(
        run_dir / "final_hygiene_metrics.json",
        (json.dumps(result["metrics"], ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    atomic_bytes(run_dir / "final_hygiene_report.md", result["report"].encode("utf-8"))
    after = {name: sha256_file(run_dir / name) for name in RAW_FILES}
    if after != validation["raw_hashes"]:
        raise HygieneError("raw artifact hash changed during offline hygiene")
    artifacts = {
        path.name: {"size": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(run_dir.iterdir(), key=lambda item: item.name)
        if path.is_file() and path.name != "integrity_manifest.json"
    }
    integrity = {
        "schema_version": "bulk_ranking_harvest.v1+hygiene.v1",
        "generated_at": utc_now(),
        "plan_hash": EXPECTED_PLAN_HASH,
        "hygiene_schema_version": SCHEMA_VERSION,
        "initial_tree_hash": validation["initial_tree_hash"],
        "raw_hashes_before": validation["raw_hashes"],
        "raw_hashes_after": after,
        "raw_byte_identical": True,
        "artifacts": artifacts,
        "self_hash_omitted": True,
    }
    atomic_bytes(
        run_dir / "integrity_manifest.json",
        (json.dumps(integrity, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )


def compact_summary(result: dict[str, Any], mode: str) -> None:
    metrics = result["metrics"]
    print(f"MODE={mode}")
    print(f"INITIAL_CANDIDATES={metrics['initial_candidates']}")
    print(f"FINAL_SERVICE_CANDIDATES={metrics['final_service_candidates']}")
    print(f"REVIEW={metrics['review_candidates']}")
    print(
        "EXCLUSIONS="
        f"promo:{metrics['excluded_promotional_phrases']},"
        f"players:{metrics['excluded_players_apps']},"
        f"hardware:{metrics['excluded_hardware']},"
        f"platforms:{metrics['excluded_channels_platforms']},"
        f"generic:{metrics['excluded_generic_terms']},"
        f"other:{metrics['excluded_other_false_positives']}"
    )
    print(f"REDUCTION_PERCENT={metrics['false_positive_reduction_percent']}")
    print("TOP20=" + " | ".join(row["canonical_name"] for row in result["top20"]))
    print("TOP20_QUALITY_CONTROL=PASS")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--run-dir", type=Path, required=True)
    mode = result.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        run_dir = args.run_dir.resolve()
        validation = validate_run(run_dir)
        built = build_outputs(run_dir, validation)
        if args.execute:
            write_outputs(run_dir, built, validation)
            compact_summary(built, "EXECUTE_OFFLINE")
            print(f"RUN_DIR={run_dir}")
        else:
            compact_summary(built, "PREFLIGHT_OFFLINE_NO_WRITES")
            print(f"INITIAL_TREE_HASH={validation['initial_tree_hash']}")
        return 0
    except (HygieneError, UnicodeError, OSError, csv.Error, json.JSONDecodeError) as exc:
        print(f"OFFLINE_HYGIENE_BLOCKED={type(exc).__name__}:{exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
