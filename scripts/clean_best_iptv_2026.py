from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
from openpyxl.utils import get_column_letter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "research" / "output" / "best_iptv_2026"

INPUT_BRANDS = OUTPUT_DIR / "brands_consolidated_20260713_222351.csv"
INPUT_CORPUS_JSON = OUTPUT_DIR / "tavily_corpus_20260713_222351.json"
INPUT_CORPUS_CSV = OUTPUT_DIR / "tavily_corpus_20260713_222351.csv"

OUTPUT_CLEANED = OUTPUT_DIR / "brands_cleaned_20260713.csv"
OUTPUT_REJECTED = OUTPUT_DIR / "brands_rejected_20260713.csv"
OUTPUT_EXCEL = OUTPUT_DIR / "best_iptv_2026_cleaned_20260713.xlsx"
OUTPUT_REPORT = OUTPUT_DIR / "cleaning_report_20260713.md"

PIPE_SEPARATOR = " | "


GENERIC_FALSE_POSITIVE_NAMES = {
    "best iptv",
    "iptv provider",
    "iptv service",
    "live tv",
    "smart tv",
    "android tv",
    "androidtv",
    "apple tv",
    "iptv player",
    "iptv app",
    "iptv subscription",
    "iptv reseller",
    "iptv panel",
    "iptv server",
    "iptv channels",
    "iptvchannels",
    "iptvfreetrial",
    "iptv free trial",
    "iptv tv",
    "the iptv",
    "popular iptv",
    "any iptv",
}

GENERIC_CORE_WORDS = {
    "a",
    "about",
    "across",
    "although",
    "american",
    "an",
    "and",
    "any",
    "app",
    "apps",
    "are",
    "because",
    "best",
    "brasil",
    "brazil",
    "british",
    "budget",
    "buy",
    "cable",
    "can",
    "canada",
    "canadian",
    "channels",
    "cheap",
    "choose",
    "choosing",
    "click",
    "complete",
    "common",
    "conclusion",
    "configure",
    "content",
    "days",
    "device",
    "devices",
    "each",
    "does",
    "download",
    "easy",
    "edition",
    "effective",
    "efficiency",
    "epg",
    "feature",
    "for",
    "forum",
    "free",
    "global",
    "good",
    "greatest",
    "group",
    "guide",
    "guides",
    "how",
    "install",
    "initiating",
    "international",
    "label",
    "launch",
    "legal",
    "legitimate",
    "lista",
    "live",
    "m3u",
    "m3u8",
    "many",
    "melhor",
    "melhores",
    "mobile",
    "modern",
    "most",
    "movie",
    "movies",
    "optimal",
    "official",
    "other",
    "our",
    "overall",
    "panel",
    "play",
    "player",
    "popular",
    "premium",
    "plus",
    "pro",
    "provider",
    "providers",
    "quality",
    "quick",
    "reliable",
    "reseller",
    "right",
    "server",
    "service",
    "services",
    "smart",
    "some",
    "sports",
    "stable",
    "stream",
    "streaming",
    "subscription",
    "submit",
    "teste",
    "the",
    "these",
    "this",
    "top",
    "track",
    "traditional",
    "unlimited",
    "understanding",
    "usa",
    "using",
    "use",
    "value",
    "watch",
    "web",
    "what",
    "which",
    "with",
    "why",
    "your",
}

CONSUMER_PLATFORM_FALSE_POSITIVES = {
    "android",
    "android tv",
    "androidtv",
    "apple tv",
    "cable tv",
    "chromecast",
    "digital tv",
    "fire stick",
    "fire iptv",
    "fire tv",
    "firestick iptv",
    "firestick",
    "google tv",
    "hisense tv",
    "lg tv",
    "m3u tv",
    "m3u8 iptv",
    "nvidia shield",
    "roku",
    "roku tv",
    "samsung tv",
    "shield iptv",
    "shield tv",
    "smart tv",
    "web tv",
    "xiaomi tv",
}

TECH_PLATFORM_NAMES = {
    "cast tv": "Cast TV",
    "ersatztv": "ErsatzTV",
    "jellyfin": "Jellyfin",
    "plex": "Plex",
    "stalker portal": "Stalker Portal",
    "xmltv": "XMLTV",
    "xtream codes": "Xtream Codes",
}

PLAYER_ALIASES = {
    "duplex iptv": "Duplex Play",
    "duplex play": "Duplex Play",
    "gse smart iptv": "GSE Smart IPTV",
    "iduplextv": "Duplex Play",
    "iptv smarters": "IPTV Smarters",
    "iptvsmarters": "IPTV Smarters",
    "kodi": "Kodi",
    "siptv": "Smart IPTV",
    "smart iptv": "Smart IPTV",
    "smarters iptv": "IPTV Smarters",
    "smarters pro": "IPTV Smarters",
    "tivimate": "TiviMate",
    "tivimate iptv": "TiviMate",
    "xciptv": "XCIPTV",
    "xciptv iptv": "XCIPTV",
}

LEGAL_OTT_ALIASES = {
    "amazon prime video": "Amazon Prime Video",
    "apple tv plus": "Apple TV+",
    "dazn": "DAZN",
    "direc tv": "DIRECTV Stream",
    "direct tv": "DIRECTV Stream",
    "directv": "DIRECTV Stream",
    "directv stream": "DIRECTV Stream",
    "disney plus": "Disney+",
    "fubotv": "Fubo",
    "fubo tv": "Fubo",
    "hulu": "Hulu",
    "nba tv": "NBA TV",
    "netflix": "Netflix",
    "now tv": "NOW TV",
    "paramount plus": "Paramount+",
    "peacock": "Peacock",
    "philo": "Philo",
    "pluto tv": "Pluto TV",
    "sling iptv": "Sling TV",
    "sling tv": "Sling TV",
    "tubi": "Tubi",
    "youtube tv": "YouTube TV",
}

DIRECTORY_ALIASES = {
    "bestiptvfinder": "BestIPTVFinder",
    "guru99": "Guru99",
    "iptvrankings": "IPTVRankings",
    "iptvserviceradar": "IPTVServiceRadar",
    "softwaretestinghelp": "SoftwareTestingHelp",
    "techradar": "TechRadar",
    "troypoint": "TROYPOINT",
}

BRAND_ALIAS_OVERRIDES = {
    "area69 iptv": "Area69 IPTV",
    "area69iptv": "Area69 IPTV",
    "digitalizard": "DigitaLizard IPTV",
    "digitalizard iptv": "DigitaLizard IPTV",
    "extremehdiptv": "XtremeHD IPTV",
    "kilo tv": "KiLoTV",
    "kilotv": "KiLoTV",
    "kilotv.com": "KiLoTV",
    "ottocean": "OTTOcean",
    "ottocean iptv": "OTTOcean",
    "playmax tv": "PLAYMAXTV",
    "playmaxtv": "PLAYMAXTV",
    "tvoxo": "TVOXO",
    "tvoxo iptv": "TVOXO",
    "xtreme hd iptv": "XtremeHD IPTV",
    "xtremehd": "XtremeHD IPTV",
    "xtremehd iptv": "XtremeHD IPTV",
    "xtremehdiptv": "XtremeHD IPTV",
}


@dataclass
class BrandAccumulator:
    canonical_brand: str
    aliases: set[str] = field(default_factory=set)
    source_count: int = 0
    platforms: set[str] = field(default_factory=set)
    domains: set[str] = field(default_factory=set)
    evidence_urls: set[str] = field(default_factory=set)
    latest_published_date: str = ""
    original_rows: int = 0
    rejection_reasons: set[str] = field(default_factory=set)


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_spaces_and_signs(value: str) -> str:
    value = strip_accents(clean_text(value))
    value = value.replace("&", " and ")
    value = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value)
    value = re.sub(r"[\u2010-\u2015]", "-", value)
    value = re.sub(r"[\"'`´“”‘’]", "", value)
    value = re.sub(r"[()\[\]{}]", " ", value)
    value = re.sub(r"[._/\\:+,;!?|]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalized_name(value: str) -> str:
    return normalize_spaces_and_signs(value).casefold()


def compact_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalized_name(value))


def split_pipe(value: Any) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    return [part.strip() for part in text.split(PIPE_SEPARATOR) if part.strip()]


def extract_domain(url: str) -> str:
    try:
        domain = urlparse(url).netloc.lower()
    except Exception:
        return ""
    return domain.removeprefix("www.")


def choose_display_name(aliases: set[str], preferred: str = "") -> str:
    if preferred:
        return preferred
    clean_aliases = sorted((normalize_spaces_and_signs(alias) for alias in aliases if alias), key=lambda x: (len(x), x.casefold()))
    if not clean_aliases:
        return ""

    chosen = clean_aliases[0]
    tokens = []
    for token in chosen.split():
        upper = token.upper()
        lower = token.casefold()
        if upper in {"IPTV", "OTT", "TV", "HD", "USA", "UK", "4K", "M3U", "VOD"}:
            tokens.append(upper)
        elif lower in {"fubotv"}:
            tokens.append("FuboTV")
        elif token.isupper() and len(token) <= 6:
            tokens.append(token)
        else:
            tokens.append(token[:1].upper() + token[1:])
    return " ".join(tokens)


def canonical_brand_for(raw_brand: str) -> tuple[str, str]:
    cleaned = normalize_spaces_and_signs(raw_brand)
    name = normalized_name(cleaned)
    compact = compact_name(cleaned)

    for aliases in (
        PLAYER_ALIASES,
        LEGAL_OTT_ALIASES,
        DIRECTORY_ALIASES,
        BRAND_ALIAS_OVERRIDES,
        TECH_PLATFORM_NAMES,
    ):
        if name in aliases:
            return aliases[name], aliases[name]
        if compact in {compact_name(key) for key in aliases}:
            return aliases[next(key for key in aliases if compact_name(key) == compact)], aliases[next(key for key in aliases if compact_name(key) == compact)]

    key = name
    key = re.sub(r"\b(service|services|provider|providers|subscription|subscriptions|reseller|panel|server|channels|app|apps|player|players)\b", " ", key)
    key = re.sub(r"\s+", " ", key).strip()

    if key.startswith("iptv ") and len(key.split()) > 1:
        key = key[5:]

    tokens = key.split()
    while len(tokens) > 1 and tokens[-1] in {"iptv", "ott", "tv"}:
        tokens.pop()
    no_suffix = " ".join(tokens).strip()
    if len(no_suffix) >= 2:
        key = no_suffix

    if not key:
        key = name or compact

    return key, choose_display_name({cleaned})


def is_title_or_phrase(name: str) -> bool:
    tokens = normalized_name(name).split()
    if len(tokens) >= 5:
        return True
    phrase_markers = {"after", "before", "compared", "complete", "finally", "ranked", "review", "tested", "ultimate", "works"}
    return any(token in phrase_markers for token in tokens) and len(tokens) >= 3


def reject_reason_for(canonical_brand: str, aliases: set[str]) -> str:
    values = {normalized_name(canonical_brand), compact_name(canonical_brand)}
    for alias in aliases:
        values.add(normalized_name(alias))
        values.add(compact_name(alias))

    normalized_values = {value for value in values if value}
    spaced_values = {normalized_name(alias) for alias in aliases if alias}

    if normalized_values & {compact_name(item) for item in GENERIC_FALSE_POSITIVE_NAMES}:
        return "generic IPTV/search phrase"
    if spaced_values & GENERIC_FALSE_POSITIVE_NAMES:
        return "generic IPTV/search phrase"
    if spaced_values & CONSUMER_PLATFORM_FALSE_POSITIVES:
        return "consumer device, OS, or platform"
    if normalized_values & {compact_name(item) for item in CONSUMER_PLATFORM_FALSE_POSITIVES}:
        return "consumer device, OS, or platform"
    if any(is_title_or_phrase(alias) for alias in aliases):
        return "article title or promotional phrase"

    base = normalized_name(canonical_brand)
    base_no_suffix = re.sub(r"\b(iptv|tv|ott)\b", " ", base)
    base_tokens = [token for token in base_no_suffix.split() if token]

    if not base_tokens:
        return "generic IPTV/search phrase"
    if all(token in GENERIC_CORE_WORDS or token.isnumeric() for token in base_tokens):
        return "generic descriptor"
    if len(base_tokens) == 1 and base_tokens[0] in GENERIC_CORE_WORDS:
        return "generic descriptor"
    if re.fullmatch(r"(iptv|tv|ott)?\d{1,4}(iptv|tv|ott)?", compact_name(canonical_brand)):
        return "non-brand code or numeric fragment"
    return ""


def classify_brand(canonical_brand: str, aliases: set[str], evidence_url_count: int) -> tuple[str, str]:
    values = {normalized_name(canonical_brand), compact_name(canonical_brand)}
    values.update(normalized_name(alias) for alias in aliases)
    values.update(compact_name(alias) for alias in aliases)

    for alias, display in PLAYER_ALIASES.items():
        if normalized_name(alias) in values or compact_name(alias) in values or normalized_name(display) in values:
            return "PLAYER", ""

    for alias, display in LEGAL_OTT_ALIASES.items():
        if normalized_name(alias) in values or compact_name(alias) in values or normalized_name(display) in values:
            return "LEGAL_OTT", ""

    for alias, display in DIRECTORY_ALIASES.items():
        if normalized_name(alias) in values or compact_name(alias) in values or normalized_name(display) in values:
            return "FORUM_OR_DIRECTORY", ""

    for alias, display in TECH_PLATFORM_NAMES.items():
        if normalized_name(alias) in values or compact_name(alias) in values or normalized_name(display) in values:
            return "PLATFORM", ""

    rejection_reason = reject_reason_for(canonical_brand, aliases)
    if rejection_reason:
        return "REJECTED_FALSE_POSITIVE", rejection_reason

    name = normalized_name(canonical_brand)
    compact = compact_name(canonical_brand)

    if compact.startswith("iptv") and len(compact) <= 8:
        return "UNKNOWN", ""
    if evidence_url_count <= 1 and len(re.sub(r"\b(iptv|tv|ott)\b", "", name).strip()) <= 3:
        return "UNKNOWN", ""
    return "PROVIDER", ""


def confidence_for(source_count: int, unique_domains_count: int, platform_count: int, evidence_url_count: int, category: str) -> str:
    if category == "REJECTED_FALSE_POSITIVE":
        return "LOW"
    if category in {"PLAYER", "LEGAL_OTT"} and evidence_url_count >= 1:
        return "HIGH"
    if source_count >= 6 and unique_domains_count >= 3 and platform_count >= 2:
        return "HIGH"
    if source_count >= 3 and unique_domains_count >= 2:
        return "MEDIUM"
    if evidence_url_count >= 3 and unique_domains_count >= 2:
        return "MEDIUM"
    return "LOW"


def evidence_status_for(category: str, confidence: str, evidence_url_count: int, unique_domains_count: int) -> str:
    if category == "REJECTED_FALSE_POSITIVE":
        return "INSUFFICIENT_EVIDENCE"
    if confidence in {"HIGH", "MEDIUM"} and evidence_url_count >= 2 and unique_domains_count >= 1:
        return "VERIFIED_BRAND_EXISTENCE"
    if evidence_url_count >= 1:
        return "NEEDS_DUE_DILIGENCE"
    return "INSUFFICIENT_EVIDENCE"


def recurrence_score(source_count: int, unique_domains_count: int, platform_count: int, evidence_url_count: int) -> float:
    return round(
        source_count
        + (unique_domains_count * 2.0)
        + (platform_count * 1.5)
        + min(evidence_url_count, 25) * 0.5,
        2,
    )


def load_corpus_metadata() -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}

    if INPUT_CORPUS_CSV.exists():
        corpus_df = pd.read_csv(INPUT_CORPUS_CSV)
        for record in corpus_df.to_dict(orient="records"):
            url = clean_text(record.get("url"))
            if url:
                metadata[url] = record

    if INPUT_CORPUS_JSON.exists():
        records = json.loads(INPUT_CORPUS_JSON.read_text(encoding="utf-8"))
        for record in records:
            url = clean_text(record.get("url"))
            if url:
                metadata.setdefault(url, {}).update(record)

    return metadata


def build_accumulators(brands_df: pd.DataFrame) -> dict[str, BrandAccumulator]:
    accumulators: dict[str, BrandAccumulator] = {}
    display_votes: dict[str, Counter[str]] = defaultdict(Counter)

    for record in brands_df.to_dict(orient="records"):
        raw_brand = clean_text(record.get("brand_name"))
        if not raw_brand:
            continue

        key, display = canonical_brand_for(raw_brand)
        key = normalized_name(key)

        if key not in accumulators:
            accumulators[key] = BrandAccumulator(canonical_brand=display)

        accumulator = accumulators[key]
        source_count = int(record.get("source_count") or 0)
        accumulator.source_count += source_count
        accumulator.aliases.add(normalize_spaces_and_signs(raw_brand))
        accumulator.platforms.update(split_pipe(record.get("platforms")))
        accumulator.domains.update(split_pipe(record.get("domains")))
        accumulator.evidence_urls.update(split_pipe(record.get("evidence_urls")))
        accumulator.original_rows += 1

        latest_date = clean_text(record.get("latest_published_date"))
        if latest_date > accumulator.latest_published_date:
            accumulator.latest_published_date = latest_date

        display_votes[key][display] += max(source_count, 1)

    for key, accumulator in accumulators.items():
        if display_votes[key]:
            accumulator.canonical_brand = display_votes[key].most_common(1)[0][0]

    return accumulators


def row_from_accumulator(accumulator: BrandAccumulator) -> dict[str, Any]:
    evidence_url_count = len(accumulator.evidence_urls)
    unique_domains_count = len({domain for domain in accumulator.domains if domain})
    platform_count = len({platform for platform in accumulator.platforms if platform})
    category, rejection_reason = classify_brand(
        accumulator.canonical_brand,
        accumulator.aliases,
        evidence_url_count,
    )
    confidence = confidence_for(
        accumulator.source_count,
        unique_domains_count,
        platform_count,
        evidence_url_count,
        category,
    )
    evidence_status = evidence_status_for(
        category,
        confidence,
        evidence_url_count,
        unique_domains_count,
    )
    score = recurrence_score(
        accumulator.source_count,
        unique_domains_count,
        platform_count,
        evidence_url_count,
    )

    aliases = sorted(accumulator.aliases, key=lambda value: value.casefold())
    domains = sorted(filter(None, accumulator.domains))
    platforms = sorted(filter(None, accumulator.platforms))
    evidence_urls = sorted(filter(None, accumulator.evidence_urls))

    return {
        "canonical_brand": accumulator.canonical_brand,
        "category": category,
        "confidence": confidence,
        "evidence_status": evidence_status,
        "source_count": accumulator.source_count,
        "unique_domains_count": unique_domains_count,
        "platform_count": platform_count,
        "evidence_url_count": evidence_url_count,
        "recurrence_score": score,
        "aliases_count": len(aliases),
        "merged_input_rows": accumulator.original_rows,
        "aliases": PIPE_SEPARATOR.join(aliases),
        "source_platforms": PIPE_SEPARATOR.join(platforms),
        "domains": PIPE_SEPARATOR.join(domains),
        "evidence_urls": PIPE_SEPARATOR.join(evidence_urls),
        "latest_published_date": accumulator.latest_published_date,
        "rejection_reason": rejection_reason,
    }


def build_evidence_rows(rows: list[dict[str, Any]], metadata_by_url: dict[str, dict[str, Any]]) -> pd.DataFrame:
    evidence_rows = []
    for row in rows:
        for url in split_pipe(row.get("evidence_urls")):
            metadata = metadata_by_url.get(url, {})
            domain = clean_text(metadata.get("domain")) or extract_domain(url)
            evidence_rows.append(
                {
                    "canonical_brand": row["canonical_brand"],
                    "category": row["category"],
                    "confidence": row["confidence"],
                    "evidence_status": row["evidence_status"],
                    "url": url,
                    "domain": domain,
                    "source_platform": clean_text(metadata.get("source_platform")),
                    "title": clean_text(metadata.get("title")),
                    "query": clean_text(metadata.get("query")),
                    "published_date": clean_text(metadata.get("published_date")),
                    "score": metadata.get("score", ""),
                    "matched_queries": PIPE_SEPARATOR.join(metadata.get("matched_queries", []))
                    if isinstance(metadata.get("matched_queries"), list)
                    else clean_text(metadata.get("matched_queries")),
                }
            )
    return pd.DataFrame(evidence_rows).drop_duplicates()


def excel_safe_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    safe = dataframe.copy()
    for column in safe.columns:
        if safe[column].dtype == object:
            safe[column] = safe[column].map(
                lambda value: value[:32000] + " [TRUNCATED_FOR_EXCEL]"
                if isinstance(value, str) and len(value) > 32000
                else value
            )
    return safe


def write_sheet(writer: pd.ExcelWriter, dataframe: pd.DataFrame, sheet_name: str) -> None:
    excel_safe_dataframe(dataframe).to_excel(writer, sheet_name=sheet_name, index=False)
    worksheet = writer.sheets[sheet_name]
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions

    for index, column in enumerate(dataframe.columns, start=1):
        series = dataframe[column].astype(str).head(200)
        max_length = max([len(str(column)), *(len(value) for value in series)], default=12)
        worksheet.column_dimensions[get_column_letter(index)].width = min(max(max_length + 2, 10), 48)


def build_report(
    initial_total: int,
    cleaned_df: pd.DataFrame,
    rejected_df: pd.DataFrame,
    all_rows_df: pd.DataFrame,
) -> str:
    aliases_fused = int((all_rows_df["merged_input_rows"] - 1).clip(lower=0).sum())
    category_distribution = all_rows_df["category"].value_counts().sort_index()
    top_50 = cleaned_df.sort_values(
        by=["recurrence_score", "source_count", "unique_domains_count", "canonical_brand"],
        ascending=[False, False, False, True],
    ).head(50)

    lines = [
        "# Limpieza best_iptv_2026 - 20260713",
        "",
        "## Resumen",
        "",
        f"- Total inicial: {initial_total}",
        f"- Total depurado: {len(cleaned_df)}",
        f"- Falsos positivos eliminados: {len(rejected_df)}",
        f"- Aliases fusionados: {aliases_fused}",
        "",
        "## Distribucion por categoria",
        "",
        "| Categoria | Registros |",
        "|---|---:|",
    ]

    for category, count in category_distribution.items():
        lines.append(f"| {category} | {count} |")

    lines.extend(
        [
            "",
            "## Top 50 marcas por recurrencia",
            "",
            "| Rank | Marca | Categoria | Recurrencia | Source count | Dominios | Plataformas | Confidence | Estado evidencia |",
            "|---:|---|---|---:|---:|---:|---:|---|---|",
        ]
    )

    for rank, (_, row) in enumerate(top_50.iterrows(), start=1):
        lines.append(
            "| "
            f"{rank} | {row['canonical_brand']} | {row['category']} | "
            f"{row['recurrence_score']} | {row['source_count']} | "
            f"{row['unique_domains_count']} | {row['platform_count']} | "
            f"{row['confidence']} | {row['evidence_status']} |"
        )

    lines.extend(
        [
            "",
            "## Notas de criterio",
            "",
            "- La columna `evidence_status` no declara legitimidad, licencias ni autorizacion de contenido.",
            "- `VERIFIED_BRAND_EXISTENCE` solo indica que la marca aparece con evidencia suficiente en las fuentes disponibles.",
            "- Las URLs completas se conservan en los CSV y en la hoja `Evidencia` del Excel.",
        ]
    )

    return "\n".join(lines) + "\n"


def main() -> None:
    for path in (INPUT_BRANDS, INPUT_CORPUS_JSON, INPUT_CORPUS_CSV):
        if not path.exists():
            raise FileNotFoundError(f"No existe la fuente requerida: {path}")

    brands_df = pd.read_csv(INPUT_BRANDS)
    metadata_by_url = load_corpus_metadata()
    accumulators = build_accumulators(brands_df)

    rows = [row_from_accumulator(accumulator) for accumulator in accumulators.values()]
    all_rows_df = pd.DataFrame(rows).sort_values(
        by=["category", "recurrence_score", "source_count", "canonical_brand"],
        ascending=[True, False, False, True],
    )

    cleaned_df = all_rows_df[all_rows_df["category"] != "REJECTED_FALSE_POSITIVE"].copy()
    rejected_df = all_rows_df[all_rows_df["category"] == "REJECTED_FALSE_POSITIVE"].copy()

    cleaned_df = cleaned_df.sort_values(
        by=["recurrence_score", "source_count", "unique_domains_count", "canonical_brand"],
        ascending=[False, False, False, True],
    )
    rejected_df = rejected_df.sort_values(
        by=["recurrence_score", "source_count", "canonical_brand"],
        ascending=[False, False, True],
    )

    evidence_df = build_evidence_rows(rows, metadata_by_url).sort_values(
        by=["canonical_brand", "url"],
        ascending=[True, True],
    )
    high_priority_df = cleaned_df[cleaned_df["confidence"].isin(["HIGH", "MEDIUM"])].sort_values(
        by=["recurrence_score", "unique_domains_count", "source_count", "canonical_brand"],
        ascending=[False, False, False, True],
    )

    cleaned_df.to_csv(OUTPUT_CLEANED, index=False, encoding="utf-8-sig")
    rejected_df.to_csv(OUTPUT_REJECTED, index=False, encoding="utf-8-sig")
    OUTPUT_REPORT.write_text(
        build_report(len(brands_df), cleaned_df, rejected_df, all_rows_df),
        encoding="utf-8",
    )

    with pd.ExcelWriter(OUTPUT_EXCEL, engine="openpyxl") as writer:
        write_sheet(writer, cleaned_df, "Marcas depuradas")
        write_sheet(writer, high_priority_df, "Prioridad alta")
        write_sheet(writer, cleaned_df[cleaned_df["category"] == "PLAYER"], "Players")
        write_sheet(writer, cleaned_df[cleaned_df["category"] == "PLATFORM"], "Plataformas")
        write_sheet(writer, cleaned_df[cleaned_df["category"] == "LEGAL_OTT"], "OTT legales")
        write_sheet(writer, evidence_df, "Evidencia")
        write_sheet(writer, rejected_df, "Falsos positivos")

    print("Limpieza finalizada.")
    print(f"CSV depurado: {OUTPUT_CLEANED}")
    print(f"CSV rechazados: {OUTPUT_REJECTED}")
    print(f"Excel: {OUTPUT_EXCEL}")
    print(f"Reporte: {OUTPUT_REPORT}")


if __name__ == "__main__":
    main()
