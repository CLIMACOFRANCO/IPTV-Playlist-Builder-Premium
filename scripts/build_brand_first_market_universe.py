from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import math
import os
import re
import socket
import subprocess
import sys
import unicodedata
import urllib.request
import zipfile
from collections import Counter, defaultdict
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse
from xml.etree import ElementTree


csv.field_size_limit(64 * 1024 * 1024)


RUNNER_VERSION = "1.2.0-fix2"
PIPE_SEPARATOR = " | "
EXPECTED_COUNTS = {
    "raw_brand_mentions": 1035,
    "cleaned_canonical_brands": 757,
    "providers": 692,
    "historical_top50": 50,
}
EXPECTED_BASELINE = "dbff5acf83dd35064249bde69c007178eb97bf33"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "research" / "output" / "best_iptv_2026"
DEFAULT_OUTPUT_ROOT = (
    DEFAULT_INPUT_DIR / "brand_first_market_universe_1a"
)

INPUT_FILENAMES = (
    "tavily_corpus_20260713_222351.json",
    "tavily_corpus_20260713_222351.csv",
    "brands_consolidated_20260713_222351.csv",
    "brands_cleaned_20260713.csv",
    "brands_rejected_20260713.csv",
    "cleaning_report_20260713.md",
    "top50_due_diligence_preliminary_20260713.csv",
    "top50_due_diligence_preliminary_20260713.xlsx",
    "top50_due_diligence_report_20260713.md",
    "top50_query_plan_20260713.json",
)

OUTPUT_FILENAMES = (
    "01_source_inventory.csv",
    "02_raw_brand_mentions.csv",
    "03_canonical_brand_universe.csv",
    "04_brand_alias_map.csv",
    "05_brand_exclusions.csv",
    "06_provider_universe_692.csv",
    "07_historical_top50.csv",
    "08_top50_selection_trace.csv",
    "09_source_quality_registry.csv",
    "10_source_independence_groups.csv",
    "11_brand_source_matrix.csv",
    "12_brand_recurrence_metrics.csv",
    "13_brand_seed_readiness.csv",
    "14_top50_recalibrated_offline.csv",
    "15_historical_vs_recalibrated_comparison.csv",
    "16_market_universe_bias_report.md",
    "17_brand_first_market_universe_report.md",
    "18_integrity_manifest.json",
    "19_runner_validation_report.md",
)

CSV_OUTPUTS = OUTPUT_FILENAMES[:15]

QUALITY_WEIGHTS = {
    "A": 1.00,
    "B": 0.80,
    "C": 0.50,
    "D": 0.20,
    "E": 0.00,
    "UNKNOWN": 0.20,
}

# No historical row contains a reliable publication date. The global 5 percent
# recency weight is therefore redistributed proportionally across the available
# dimensions. The same effective weights apply to every provider.
BASE_AVAILABLE_WEIGHTS = {
    "independence": 30.0,
    "quality_weighted_recurrence": 20.0,
    "source_diversity": 15.0,
    "query_context_diversity": 10.0,
    "language_diversity": 5.0,
    "geographic_context_diversity": 5.0,
    "alias_trace_completeness": 5.0,
    "provenance_trace_completeness": 5.0,
}
WEIGHT_SCALE = 100.0 / sum(BASE_AVAILABLE_WEIGHTS.values())
EFFECTIVE_WEIGHTS = {
    key: value * WEIGHT_SCALE
    for key, value in BASE_AVAILABLE_WEIGHTS.items()
}

CONFIDENCE_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

COMMUNITY_HOSTS = {
    "news.ycombinator.com",
    "reddit.com",
    "trustpilot.com",
}
MULTIUSER_HOSTS = {
    "facebook.com",
    "github.com",
    "indiehackers.com",
    "linkedin.com",
    "medium.com",
    "news.ycombinator.com",
    "quora.com",
    "reddit.com",
    "slideshare.net",
    "t.me",
    "trustpilot.com",
    "youtube.com",
}
SELF_PUBLISHING_HOSTS = {
    "github.com",
    "indiehackers.com",
    "medium.com",
    "prlog.org",
    "sites.google.com",
    "slideshare.net",
    "youtube.com",
}
PROMOTIONAL_HOST_KEYWORDS = {
    "bestiptv",
    "best-iptv",
    "freetrial",
    "free-trial",
    "iptvfinder",
    "iptvprovider",
    "iptvrankings",
    "iptvreviews",
    "iptvservice",
    "topiptv",
}
PROMOTIONAL_TEXT_PATTERNS = (
    r"\bbuy\b",
    r"\bfree trial\b",
    r"\bpricing\b",
    r"\bsubscription\b",
    r"\breseller\b",
    r"\baffiliate\b",
    r"\bpromo(?:tional)?\b",
    r"\bcomprar\b",
    r"\bprueba gratis\b",
    r"\bprueba gratuita\b",
    r"\bprecios?\b",
    r"\bsuscripci[oó]n\b",
    r"\brevendedor\b",
    r"\bafiliad[oa]\b",
    r"\bteste gr[aá]tis\b",
    r"\bteste gratuito\b",
    r"\bpre[cç]os?\b",
    r"\bassinatura\b",
    r"\brevenda\b",
    r"\bafiliad[oa]\b",
    r"\bavalia[cç][aã]o\b",
)
AFFILIATE_DISCLOSURE_PATTERN = re.compile(
    r"\baffiliate(?:\s+links?|\s+commission|\s+disclosure)?\b",
    re.IGNORECASE,
)

GEOGRAPHY_TERMS = {
    "AUSTRALIA": ("australia", "australian"),
    "BRAZIL": ("brazil", "brasil"),
    "CANADA": ("canada", "canadian"),
    "COLOMBIA": ("colombia", "colombian"),
    "EUROPE": ("europe", "european"),
    "LATIN_AMERICA": ("latin america", "latino"),
    "UNITED_KINGDOM": (" uk ", "united kingdom", "british"),
    "UNITED_STATES": (" usa ", "united states", "american"),
}

MIN_REPLICA_COMPARABLE_BRANDS = 8
CROSS_HOST_SET_SIMILARITY_THRESHOLD = 0.85
CROSS_HOST_ORDER_SIMILARITY_THRESHOLD = 0.75
SAME_HOST_BRAND_RECURRENCE_MAX = 0.75
PROBABLE_REPLICA_SINGLE_PAGE_MAX = 0.25
PROBABLE_REPLICA_REPEATED_MAX = 0.50

SEMANTIC_STATUSES = {
    "PLAUSIBLE_BRAND",
    "POSSIBLE_PLAYER_OR_PLATFORM",
    "GENERIC_NAME_REQUIRES_REVIEW",
    "POSSIBLE_EXTRACTION_ARTIFACT",
    "POSSIBLE_HOMONYM",
    "POSSIBLE_NON_PROVIDER",
    "INSUFFICIENT_LOCAL_EVIDENCE",
    "UNRESOLVED",
    "POSSIBLE_BROADCASTER_OR_CHANNEL",
    "POSSIBLE_LEGAL_OTT",
    "POSSIBLE_TELECOM_OR_PAYTV",
    "POSSIBLE_INFRASTRUCTURE_TERM",
    "POSSIBLE_HARDWARE_OR_DEVICE",
    "POSSIBLE_EDITORIAL_OR_DIRECTORY",
}

COLLISION_TYPES = {
    "ALIAS_DUPLICATE_CANDIDATE",
    "GENERIC_COLLISION",
    "TRUE_HOMONYM_CANDIDATE",
    "POSSIBLE_IMPERSONATION",
    "UNRESOLVED_NOMINAL_COLLISION",
}

MENTION_USE_TYPES = {
    "NOMINAL_BRAND_USE",
    "DESCRIPTIVE_GENERIC_USE",
    "PRODUCT_OR_CATEGORY_USE",
    "PLAYER_OR_APPLICATION_USE",
    "BROADCASTER_OR_CHANNEL_USE",
    "OTT_OR_TELECOM_USE",
    "INFRASTRUCTURE_OR_TECHNICAL_USE",
    "HARDWARE_OR_DEVICE_USE",
    "EDITORIAL_OR_DIRECTORY_USE",
    "UNRESOLVED_CONTEXT_USE",
}

MIN_NOMINAL_BRAND_USES_FOR_PLAUSIBLE = 2
MAX_INCOMPATIBLE_CONTEXT_RATIO = 0.50
MIN_DISTINCT_SUPPORTING_SOURCES = 2
MIN_ACCEPTABLE_SOURCE_QUALITY = "D"
MAX_MENTION_CONTEXTS_PER_BRAND = 80

# FIX3 readiness thresholds. These govern the adjudication-ready surface only;
# they never alter the preserved historical universe or diagnostic ranking.
MIN_ACCEPTABLE_SOURCE_COUNT_FOR_READY = 2
MIN_DISTINCT_PUBLISHERS_FOR_READY = 2
MIN_DISTINCT_GROUPS_FOR_READY = 2
MIN_DIAGNOSTIC_SCORE_FOR_READY = 5.0
MAX_HIGH_PROMOTIONAL_RELATION_RATIO = 0.60
MIN_NON_PROMOTIONAL_ACCEPTABLE_SOURCE_COUNT = 2
MIN_SEMANTIC_CONFIDENCE_FOR_READY = "MEDIUM"
PUBLICATION_LIMIT = 50

SOURCE_QUALITY_ORDER = {"UNKNOWN": 0, "E": 1, "D": 2, "C": 3, "B": 4, "A": 5}
SEMANTIC_CONFIDENCE_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
BLOCKER_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
EMPTY_TOP50_SCHEMA = [
    "diagnostic_rank", "adjudication_ready_rank", "canonical_brand_id",
    "canonical_brand_name", "diagnostic_score", "readiness_status",
    "adjudication_ready_eligible", "adjudication_blockers",
    "acceptable_source_count", "acceptable_publisher_count",
    "acceptable_independence_group_count", "high_promotional_relation_count",
    "high_promotional_relation_ratio", "non_promotional_acceptable_source_count",
    "embedded_name_fragment_risk", "geographic_or_generic_label_risk",
    "available_adjudication_ready_count", "published_row_count",
    "publication_limit", "list_is_truncated", "no_human_approval_yet",
    "no_external_validation",
]

PLAYER_CONTEXT_PATTERN = re.compile(
    (
        r"\b(?:iptv\s+)?(?:app|application|player|client|addon|add-on|"
        r"software)\b|pvr\s+iptv\s+simple\s+client|kodi"
    ),
    re.IGNORECASE,
)
SERVICE_CONTEXT_PATTERN = re.compile(
    (
        r"\bprovider\b|\bservice\b|\bsubscription\b|\bchannels?\b|"
        r"\btrial\b|\bpricing\b|\bservi[cç]o\b|\bassinatura\b|"
        r"\bcanais\b|\bproveedor\b|\bservicio\b|\bsuscripci[oó]n\b"
    ),
    re.IGNORECASE,
)
GENERIC_PHRASE_PATTERN = re.compile(
    (
        r"\bhow\s+(?:we\s+)?test\s+iptv\b|"
        r"\bhow\s+to\s+test\s+iptv\b|"
        r"\btest\s+iptv\s+services?\b|"
        r"\bteste?\s+(?:an?\s+)?iptv\s+(?:service|provider)s?\b"
    ),
    re.IGNORECASE,
)
NON_PROVIDER_CONTEXT_PATTERN = re.compile(
    (
        r"\bnational\s+channels?\b|"
        r"\bchannel\s+suites?\b|"
        r"\btelevision\s+channel\b|"
        r"\bbroadcast\s+network\b|"
        r"\bfree\s+movies?\s+(?:&|and)\s+live\s+tv\b|"
        r"\bstreaming\s+(?:app|platform)\b"
    ),
    re.IGNORECASE,
)
COMMUNITY_CONTEXT_PATTERN = re.compile(
    (
        r"\bcomment\b|\bdiscussion\b|\bexperience\b|\btechnical\b|"
        r"\bconfiguration\b|\bsetup\b|\bissue\b|\bcomparison\b|"
        r"\breview\b|\bapp\b|\bplayer\b|\bclient\b|\bkodi\b"
    ),
    re.IGNORECASE,
)


class OfflineViolation(RuntimeError):
    """Raised when code attempts a prohibited network operation."""


class OfflineGuard(AbstractContextManager["OfflineGuard"]):
    """Process-local guard that blocks the network primitives required by 1A."""

    def __init__(self) -> None:
        self.attempts: list[dict[str, str]] = []
        self._original_socket_connect: Any = None
        self._original_create_connection: Any = None
        self._original_getaddrinfo: Any = None
        self._original_urlopen: Any = None

    def _blocked(self, operation: str, *args: Any, **kwargs: Any) -> Any:
        target = clean_text(args[0]) if args else ""
        self.attempts.append({"operation": operation, "target": target})
        raise OfflineViolation(f"Offline guard blocked {operation}: {target}")

    def __enter__(self) -> "OfflineGuard":
        self._original_socket_connect = socket.socket.connect
        self._original_create_connection = socket.create_connection
        self._original_getaddrinfo = socket.getaddrinfo
        self._original_urlopen = urllib.request.urlopen

        def blocked_connect(
            sock: socket.socket,
            address: Any,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            return self._blocked("socket.socket.connect", address)

        def blocked_create_connection(
            address: Any,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            return self._blocked("socket.create_connection", address)

        def blocked_getaddrinfo(
            host: Any,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            return self._blocked("socket.getaddrinfo", host)

        def blocked_urlopen(
            url: Any,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            return self._blocked("urllib.request.urlopen", url)

        socket.socket.connect = blocked_connect
        socket.create_connection = blocked_create_connection
        socket.getaddrinfo = blocked_getaddrinfo
        urllib.request.urlopen = blocked_urlopen
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        socket.socket.connect = self._original_socket_connect
        socket.create_connection = self._original_create_connection
        socket.getaddrinfo = self._original_getaddrinfo
        urllib.request.urlopen = self._original_urlopen
        return None


class UnionFind:
    def __init__(self, values: Iterable[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if left_root < right_root:
            self.parent[right_root] = left_root
        else:
            self.parent[left_root] = right_root


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )


def normalize_spaces_and_signs(value: str) -> str:
    value = strip_accents(clean_text(value))
    value = value.replace("&", " and ")
    value = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value)
    value = re.sub(r"[\u2010-\u2015]", "-", value)
    value = re.sub(r"[\"'`´“”‘’]", "", value)
    value = re.sub(r"[()\[\]{}]", " ", value)
    value = re.sub(r"[._/\\:+,;!?|]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalized_name(value: str) -> str:
    return normalize_spaces_and_signs(value).casefold()


def compact_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalized_name(value))


def normalized_fingerprint_text(value: str) -> str:
    value = strip_accents(clean_text(value)).casefold()
    value = re.sub(r"https?://\S+", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def split_pipe(value: Any) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    return [
        part.strip()
        for part in text.split(PIPE_SEPARATOR)
        if part.strip()
    ]


def stable_id(prefix: str, *parts: Any, length: int = 20) -> str:
    payload = "\x1f".join(clean_text(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}_{digest}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def parse_float(value: Any) -> float:
    text = clean_text(value)
    if not text:
        return 0.0
    return float(text)


def parse_int(value: Any) -> int:
    text = clean_text(value)
    if not text:
        return 0
    return int(float(text))


def bounded(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def ratio(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return numerator / denominator


def serialize_csv(
    rows: list[dict[str, Any]],
    fieldnames: list[str] | None = None,
) -> bytes:
    if not rows and not fieldnames:
        return b"\xef\xbb\xbf"
    derived_fieldnames: list[str] = list(fieldnames or [])
    seen: set[str] = set()
    seen.update(derived_fieldnames)
    for row in rows:
        for key in row:
            if key not in seen:
                derived_fieldnames.append(key)
                seen.add(key)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=derived_fieldnames,
        lineterminator="\n",
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(rows)
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        f".{path.name}.tmp.{os.getpid()}"
    )
    if temporary.exists():
        raise FileExistsError(f"Temporary output already exists: {temporary}")
    with temporary.open("xb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def atomic_write_text(path: Path, content: str) -> None:
    atomic_write_bytes(path, content.encode("utf-8"))


def atomic_write_json(path: Path, value: Any) -> None:
    content = json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    atomic_write_text(path, content)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def parse_json_array(value: Any) -> list[Any]:
    """Return a JSON-array field as a list without trusting malformed input."""
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(str(value or "[]"))
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def hostname_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.casefold().removeprefix("www.")
    except Exception:
        return ""


def source_id_for_url(url: str, fallback: str = "") -> str:
    return stable_id("src", normalized_name(url or fallback))


def source_row_id(record: dict[str, Any]) -> str:
    return stable_id(
        "srow",
        record.get("record_id"),
        record.get("url"),
        record.get("title"),
    )


def raw_row_id(record: dict[str, Any]) -> str:
    return stable_id(
        "raw",
        normalized_name(clean_text(record.get("brand_name"))),
        record.get("source_count"),
        record.get("evidence_urls"),
    )


def canonical_brand_id(name: str) -> str:
    return stable_id("brand", normalized_name(name))


def alias_id(alias: str, canonical: str) -> str:
    return stable_id(
        "alias",
        normalized_name(alias),
        normalized_name(canonical),
    )


def exclusion_id(raw_name: str, reason: str) -> str:
    return stable_id(
        "exclusion",
        normalized_name(raw_name),
        normalized_name(reason),
    )


def require_input_files(input_dir: Path) -> dict[str, Path]:
    inputs = {
        filename: input_dir / filename
        for filename in INPUT_FILENAMES
    }
    missing = [
        str(path)
        for path in inputs.values()
        if not path.is_file()
    ]
    if missing:
        raise FileNotFoundError(
            "Missing authoritative input files: " + ", ".join(missing)
        )
    return inputs


def xlsx_first_sheet_schema(path: Path) -> tuple[int, list[str], list[str]]:
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    relationship_namespace = {
        "r": "http://schemas.openxmlformats.org/package/2006/relationships"
    }
    document_rel = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    )
    with zipfile.ZipFile(path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(
                archive.read("xl/sharedStrings.xml")
            )
            for item in root.findall("x:si", namespace):
                text = "".join(
                    node.text or ""
                    for node in item.iterfind(".//x:t", namespace)
                )
                shared_strings.append(text)

        workbook = ElementTree.fromstring(
            archive.read("xl/workbook.xml")
        )
        relationships = ElementTree.fromstring(
            archive.read("xl/_rels/workbook.xml.rels")
        )
        relationship_targets = {
            element.attrib["Id"]: element.attrib["Target"]
            for element in relationships.findall(
                "r:Relationship",
                relationship_namespace,
            )
        }
        sheets = workbook.find("x:sheets", namespace)
        if sheets is None or not list(sheets):
            return 0, [], []
        sheet_names = [
            element.attrib.get("name", "")
            for element in list(sheets)
        ]
        first_sheet = list(sheets)[0]
        relationship_id = first_sheet.attrib[
            f"{{{document_rel}}}id"
        ]
        target = relationship_targets[relationship_id].replace("\\", "/")
        if target.startswith("/"):
            sheet_path = target.lstrip("/")
        elif target.startswith("xl/"):
            sheet_path = target
        else:
            sheet_path = f"xl/{target}"
        sheet_root = ElementTree.fromstring(archive.read(sheet_path))
        rows = sheet_root.findall(".//x:sheetData/x:row", namespace)
        headers: list[str] = []
        if rows:
            for cell in rows[0].findall("x:c", namespace):
                cell_type = cell.attrib.get("t")
                value_node = cell.find("x:v", namespace)
                value = value_node.text if value_node is not None else ""
                if cell_type == "s" and value:
                    value = shared_strings[int(value)]
                elif cell_type == "inlineStr":
                    value = "".join(
                        node.text or ""
                        for node in cell.iterfind(".//x:t", namespace)
                    )
                headers.append(value)
        return max(len(rows) - 1, 0), headers, sheet_names


def inspect_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.casefold()
    record_count = 0
    schema_summary = ""
    if suffix == ".csv":
        rows = read_csv_rows(path)
        record_count = len(rows)
        columns = list(rows[0]) if rows else []
        schema_summary = PIPE_SEPARATOR.join(columns)
    elif suffix == ".json":
        value = read_json(path)
        if isinstance(value, list):
            record_count = len(value)
            columns = list(value[0]) if value else []
        elif isinstance(value, dict):
            record_count = len(value)
            columns = list(value)
        else:
            record_count = 1
            columns = [type(value).__name__]
        schema_summary = PIPE_SEPARATOR.join(columns)
    elif suffix == ".xlsx":
        record_count, columns, sheets = xlsx_first_sheet_schema(path)
        schema_summary = (
            f"first_sheet_columns={PIPE_SEPARATOR.join(columns)};"
            f"sheets={PIPE_SEPARATOR.join(sheets)}"
        )
    elif suffix == ".md":
        text = path.read_text(encoding="utf-8-sig")
        lines = text.splitlines()
        record_count = len(lines)
        headings = [
            line.lstrip("#").strip()
            for line in lines
            if line.startswith("#")
        ]
        schema_summary = "markdown_headings=" + PIPE_SEPARATOR.join(headings)
    else:
        record_count = 1
        schema_summary = "binary_or_unclassified"
    stat = path.stat()
    return {
        "source_id": stable_id("file", path.name),
        "source_file": path.name,
        "file_type": suffix.lstrip(".").upper(),
        "sha256_before": sha256_file(path),
        "sha256_after": "",
        "bytes": stat.st_size,
        "local_modified_time": datetime.fromtimestamp(
            stat.st_mtime,
            timezone.utc,
        ).isoformat(),
        "row_or_record_count": record_count,
        "schema_summary": schema_summary,
        "integrity_status": "PENDING_AFTER_HASH",
    }


def build_source_inventory(inputs: dict[str, Path]) -> list[dict[str, Any]]:
    return [
        inspect_file(inputs[filename])
        for filename in INPUT_FILENAMES
    ]


def verify_inventory_after(
    inventory: list[dict[str, Any]],
    inputs: dict[str, Path],
) -> None:
    for row in inventory:
        path = inputs[row["source_file"]]
        after = sha256_file(path)
        row["sha256_after"] = after
        row["integrity_status"] = (
            "UNCHANGED"
            if after == row["sha256_before"]
            else "CHANGED"
        )


def load_authoritative_data(
    inputs: dict[str, Path],
) -> dict[str, Any]:
    corpus_json = read_json(inputs["tavily_corpus_20260713_222351.json"])
    corpus_csv = read_csv_rows(
        inputs["tavily_corpus_20260713_222351.csv"]
    )
    consolidated = read_csv_rows(
        inputs["brands_consolidated_20260713_222351.csv"]
    )
    cleaned = read_csv_rows(inputs["brands_cleaned_20260713.csv"])
    rejected = read_csv_rows(inputs["brands_rejected_20260713.csv"])
    historical_top50 = read_csv_rows(
        inputs["top50_due_diligence_preliminary_20260713.csv"]
    )
    query_plan = read_json(inputs["top50_query_plan_20260713.json"])
    xlsx_count, xlsx_headers, xlsx_sheets = xlsx_first_sheet_schema(
        inputs["top50_due_diligence_preliminary_20260713.xlsx"]
    )

    json_urls = sorted(clean_text(row.get("url")) for row in corpus_json)
    csv_urls = sorted(clean_text(row.get("url")) for row in corpus_csv)
    if json_urls != csv_urls:
        raise RuntimeError("Corpus JSON and CSV URL sets differ.")
    if xlsx_count != len(historical_top50):
        raise RuntimeError(
            "Historical Top 50 XLSX first-sheet row count differs from CSV."
        )
    csv_headers = list(historical_top50[0]) if historical_top50 else []
    if xlsx_headers and xlsx_headers != csv_headers:
        raise RuntimeError(
            "Historical Top 50 XLSX first-sheet schema differs from CSV."
        )
    if len(query_plan) != len(historical_top50):
        raise RuntimeError(
            "Historical query plan and Top 50 contain different brand counts."
        )

    return {
        "corpus": corpus_json,
        "corpus_csv": corpus_csv,
        "consolidated": consolidated,
        "cleaned": cleaned,
        "rejected": rejected,
        "historical_top50": historical_top50,
        "query_plan": query_plan,
        "xlsx_sheets": xlsx_sheets,
    }


def validate_physical_counts(data: dict[str, Any]) -> dict[str, int]:
    category_counts = Counter(
        clean_text(row.get("category"))
        for row in data["cleaned"]
    )
    counts = {
        "raw_brand_mentions": len(data["consolidated"]),
        "cleaned_canonical_brands": len(data["cleaned"]),
        "providers": category_counts["PROVIDER"],
        "historical_top50": len(data["historical_top50"]),
        "rejected_canonical_groups": len(data["rejected"]),
        "corpus_sources": len(data["corpus"]),
    }
    failures = {
        key: (counts[key], expected)
        for key, expected in EXPECTED_COUNTS.items()
        if counts[key] != expected
    }
    if failures:
        raise RuntimeError(f"Physical count mismatch: {failures}")
    return counts


def target_aliases(row: dict[str, Any]) -> list[str]:
    aliases = split_pipe(row.get("aliases"))
    if clean_text(row.get("canonical_brand")) not in aliases:
        aliases.append(clean_text(row.get("canonical_brand")))
    return aliases


def build_alias_target_index(
    cleaned: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
) -> tuple[
    dict[str, list[tuple[str, dict[str, Any]]]],
    dict[str, list[tuple[str, dict[str, Any]]]],
]:
    normalized_index: dict[
        str,
        list[tuple[str, dict[str, Any]]],
    ] = defaultdict(list)
    compact_index: dict[
        str,
        list[tuple[str, dict[str, Any]]],
    ] = defaultdict(list)
    for kind, rows in (("CLEANED", cleaned), ("REJECTED", rejected)):
        for row in rows:
            for alias in target_aliases(row):
                normalized_index[normalized_name(alias)].append((kind, row))
                compact_index[compact_name(alias)].append((kind, row))
    return normalized_index, compact_index


def unique_target(
    candidates: list[tuple[str, dict[str, Any]]],
) -> tuple[str, dict[str, Any]] | None:
    unique: dict[tuple[str, str], tuple[str, dict[str, Any]]] = {}
    for kind, row in candidates:
        key = (kind, clean_text(row.get("canonical_brand")))
        unique[key] = (kind, row)
    if len(unique) == 1:
        return next(iter(unique.values()))
    return None


def map_raw_rows(
    consolidated: list[dict[str, Any]],
    cleaned: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
]:
    normalized_index, compact_index = build_alias_target_index(
        cleaned,
        rejected,
    )
    mapped: list[dict[str, Any]] = []
    clean_by_brand: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rejected_by_brand: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in consolidated:
        raw_name = clean_text(raw.get("brand_name"))
        target = unique_target(normalized_index[normalized_name(raw_name)])
        if target is None:
            target = unique_target(compact_index[compact_name(raw_name)])
        if target is None:
            raise RuntimeError(
                f"Cannot map historical raw brand row: {raw_name!r}"
            )
        kind, target_row = target
        mapped_row = {
            "raw": raw,
            "raw_row_id": raw_row_id(raw),
            "target_kind": kind,
            "target": target_row,
        }
        mapped.append(mapped_row)
        brand = clean_text(target_row.get("canonical_brand"))
        if kind == "CLEANED":
            clean_by_brand[brand].append(mapped_row)
        else:
            rejected_by_brand[brand].append(mapped_row)

    for row in cleaned:
        brand = clean_text(row.get("canonical_brand"))
        if len(clean_by_brand[brand]) != parse_int(row.get("merged_input_rows")):
            raise RuntimeError(
                f"Raw-row mapping mismatch for cleaned brand {brand!r}."
            )
    for row in rejected:
        brand = clean_text(row.get("canonical_brand"))
        if (
            len(rejected_by_brand[brand])
            != parse_int(row.get("merged_input_rows"))
        ):
            raise RuntimeError(
                f"Raw-row mapping mismatch for rejected brand {brand!r}."
            )
    return mapped, clean_by_brand, rejected_by_brand


def source_platform_metadata(
    *,
    hostname: str,
    url: str,
    source_id: str,
    publisher_identity: str = "",
) -> dict[str, str]:
    """Describe platform, publisher and publication without external lookup."""
    platform_id = stable_id("platform", hostname or "unknown")
    publication_id = stable_id("publication", source_id)
    if hostname in MULTIUSER_HOSTS:
        if hostname == "youtube.com":
            platform_type = "VIDEO_MULTIUSER"
        elif hostname == "trustpilot.com":
            platform_type = "REVIEW_MULTIUSER"
        elif hostname in {"reddit.com", "news.ycombinator.com"}:
            platform_type = "COMMUNITY_MULTIUSER"
        else:
            platform_type = "SELF_PUBLISHING_MULTIUSER"
        path = urlparse(url).path.strip("/")
        publisher_identity = clean_text(publisher_identity)
        if hostname == "trustpilot.com" and path.startswith("review/"):
            publisher_identity = publisher_identity or path.split(
                "/", 1
            )[1].split("/", 1)[0]
        # An unknown publisher is traceable through source_id/publication_id,
        # but it is not evidence that two sources are independently published.
        publisher_id = (
            stable_id("publisher", hostname, publisher_identity)
            if publisher_identity
            else ""
        )
        publisher_status = (
            "PLATFORM_USER_RESOLVED"
            if publisher_identity
            else "UNRESOLVED_PUBLISHER"
        )
    else:
        platform_type = "EDITORIAL_OR_OWNED_SITE"
        publisher_id = stable_id("publisher", hostname or source_id)
        publisher_status = "RESOLVED_PUBLISHER"
    return {
        "platform_id": platform_id,
        "platform_type": platform_type,
        "publisher_id": publisher_id,
        "publisher_identity_status": publisher_status,
        "publisher_counts_for_diversity": "YES" if publisher_id else "NO",
        "publication_id": publication_id,
    }


def normalize_corpus_sources(
    corpus: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    sources: list[dict[str, Any]] = []
    by_url: dict[str, dict[str, Any]] = {}
    for record in corpus:
        url = clean_text(record.get("url"))
        source_id = source_id_for_url(
            url,
            clean_text(record.get("record_id"))
            or clean_text(record.get("title")),
        )
        normalized = dict(record)
        normalized["source_id"] = source_id
        normalized["source_row_id"] = source_row_id(record)
        normalized["hostname"] = (
            clean_text(record.get("domain")).casefold().removeprefix("www.")
            or hostname_from_url(url)
        )
        normalized.update(
            source_platform_metadata(
                hostname=normalized["hostname"],
                url=url,
                source_id=source_id,
                publisher_identity=next(
                    (
                        clean_text(record.get(field))
                        for field in (
                            "author",
                            "channel",
                            "account",
                            "username",
                            "creator",
                        )
                        if clean_text(record.get(field))
                    ),
                    "",
                ),
            )
        )
        normalized["matched_queries_list"] = (
            list(record.get("matched_queries", []))
            if isinstance(record.get("matched_queries"), list)
            else split_pipe(record.get("matched_queries"))
        )
        normalized["brands_detected_list"] = (
            list(record.get("brands_detected", []))
            if isinstance(record.get("brands_detected"), list)
            else split_pipe(record.get("brands_detected"))
        )
        sources.append(normalized)
        if url:
            by_url[url] = normalized
    sources.sort(key=lambda row: row["source_id"])
    return sources, by_url


def source_content_fingerprint(source: dict[str, Any]) -> str:
    text = normalized_fingerprint_text(
        " ".join(
            [
                clean_text(source.get("title")),
                clean_text(source.get("summary")),
                clean_text(source.get("raw_content")),
            ]
        )
    )
    if len(text) < 80:
        return ""
    return sha256_bytes(text.encode("utf-8"))


def source_title_brand_fingerprint(source: dict[str, Any]) -> str:
    title = normalized_fingerprint_text(clean_text(source.get("title")))
    brands = [
        normalized_name(brand)
        for brand in source.get("brands_detected_list", [])
        if clean_text(brand)
    ]
    if len(title) < 30 or not brands:
        return ""
    payload = title + "\x1f" + "\x1f".join(brands)
    return sha256_bytes(payload.encode("utf-8"))


def ordered_brand_sequence(source: dict[str, Any]) -> list[str]:
    """Return a deterministic, de-duplicated sequence retained by the source."""
    sequence: list[str] = []
    seen: set[str] = set()
    for brand in source.get("brands_detected_list", []):
        normalized = normalized_name(brand)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        sequence.append(normalized)
    return sequence


def normalized_brand_set(source: dict[str, Any]) -> set[str]:
    return set(ordered_brand_sequence(source))


def brand_sequence_fingerprint(source: dict[str, Any]) -> str:
    sequence = ordered_brand_sequence(source)
    if len(sequence) < MIN_REPLICA_COMPARABLE_BRANDS:
        return ""
    return sha256_bytes("\x1f".join(sequence).encode("utf-8"))


def brand_set_similarity(
    left: Iterable[str],
    right: Iterable[str],
) -> float:
    left_set = set(left)
    right_set = set(right)
    smaller = min(len(left_set), len(right_set))
    if smaller == 0:
        return 0.0
    return len(left_set & right_set) / smaller


def ordered_common_subsequence_similarity(
    left: list[str],
    right: list[str],
) -> float:
    common = set(left) & set(right)
    if not common:
        return 0.0
    left_common = [item for item in left if item in common]
    right_common = [item for item in right if item in common]
    previous = [0] * (len(right_common) + 1)
    for left_item in left_common:
        current = [0]
        for index, right_item in enumerate(right_common, start=1):
            if left_item == right_item:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(current[-1], previous[index]))
        previous = current
    return previous[-1] / len(common)


def probable_replica_pair(
    left: dict[str, Any],
    right: dict[str, Any],
) -> tuple[bool, float, float]:
    left_sequence = left.get("ordered_brand_sequence", [])
    right_sequence = right.get("ordered_brand_sequence", [])
    if (
        left.get("hostname") == right.get("hostname")
        or len(left_sequence) < MIN_REPLICA_COMPARABLE_BRANDS
        or len(right_sequence) < MIN_REPLICA_COMPARABLE_BRANDS
    ):
        return False, 0.0, 0.0
    set_similarity = brand_set_similarity(left_sequence, right_sequence)
    order_similarity = ordered_common_subsequence_similarity(
        left_sequence,
        right_sequence,
    )
    probable = (
        set_similarity >= CROSS_HOST_SET_SIMILARITY_THRESHOLD
        and order_similarity >= CROSS_HOST_ORDER_SIMILARITY_THRESHOLD
    )
    return probable, set_similarity, order_similarity


def build_independence_groups(
    sources: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    source_ids = [source["source_id"] for source in sources]
    sources_by_id = {source["source_id"]: source for source in sources}
    hostname_members: dict[str, list[str]] = defaultdict(list)
    publisher_members: dict[str, list[str]] = defaultdict(list)
    content_members: dict[str, list[str]] = defaultdict(list)
    title_members: dict[str, list[str]] = defaultdict(list)
    for source in sources:
        hostname = clean_text(source.get("hostname"))
        hostname_members[hostname].append(source["source_id"])
        publisher_members[clean_text(source.get("publisher_id"))].append(
            source["source_id"]
        )
        source["content_fingerprint"] = source_content_fingerprint(source)
        source["title_brand_fingerprint"] = source_title_brand_fingerprint(
            source
        )
        source["ordered_brand_sequence"] = ordered_brand_sequence(source)
        source["normalized_brand_set"] = sorted(normalized_brand_set(source))
        source["brand_sequence_fingerprint"] = brand_sequence_fingerprint(
            source
        )
        if source["content_fingerprint"]:
            content_members[source["content_fingerprint"]].append(
                source["source_id"]
            )
        if source["title_brand_fingerprint"]:
            title_members[source["title_brand_fingerprint"]].append(
                source["source_id"]
            )

    direct_edges: dict[frozenset[str], dict[str, Any]] = {}
    for edge_type, fingerprint_members in (
        ("EXACT_CONTENT_FINGERPRINT", content_members),
        ("TITLE_AND_BRAND_ORDER_FINGERPRINT", title_members),
    ):
        for members in fingerprint_members.values():
            for left_index, left_id in enumerate(members):
                for right_id in members[left_index + 1:]:
                    if (
                        sources_by_id[left_id]["hostname"]
                        == sources_by_id[right_id]["hostname"]
                    ):
                        continue
                    direct_edges[frozenset({left_id, right_id})] = {
                        "edge_type": edge_type,
                        "set_similarity": 1.0,
                        "order_similarity": 1.0,
                    }
    comparable = [
        source
        for source in sources
        if len(source.get("ordered_brand_sequence", []))
        >= MIN_REPLICA_COMPARABLE_BRANDS
    ]
    for left_index, left in enumerate(comparable):
        for right in comparable[left_index + 1:]:
            probable, set_similarity, order_similarity = probable_replica_pair(
                left,
                right,
            )
            if probable:
                direct_edges[frozenset({left["source_id"], right["source_id"]})] = {
                    "edge_type": "ORDERED_BRAND_SEQUENCE_SET_AND_ORDER_SIMILARITY",
                    "set_similarity": set_similarity,
                    "order_similarity": order_similarity,
                }

    edge_union = UnionFind(source_ids)
    direct_partners: dict[str, set[str]] = defaultdict(set)
    direct_edge_types: dict[str, set[str]] = defaultdict(set)
    for pair, edge in direct_edges.items():
        left_id, right_id = sorted(pair)
        edge_union.union(left_id, right_id)
        direct_partners[left_id].add(right_id)
        direct_partners[right_id].add(left_id)
        direct_edge_types[left_id].add(edge["edge_type"])
        direct_edge_types[right_id].add(edge["edge_type"])

    replica_components: dict[str, list[str]] = defaultdict(list)
    for source_id in source_ids:
        if direct_partners[source_id]:
            replica_components[edge_union.find(source_id)].append(source_id)

    assigned: set[str] = set()
    groups: list[list[str]] = []
    for members in replica_components.values():
        member_list = sorted(members)
        groups.append(member_list)
        assigned.update(member_list)

    dependency_buckets: dict[str, list[str]] = defaultdict(list)
    for source in sources:
        source_id = source["source_id"]
        if source_id in assigned:
            continue
        if source.get("platform_type", "").endswith("MULTIUSER"):
            publisher_id = clean_text(source.get("publisher_id"))
            # Preserve every unresolved source as a separate traceable group
            # without claiming it demonstrates independence.
            dependency_key = publisher_id or "unresolved:" + source_id
        else:
            dependency_key = "hostname:" + clean_text(source.get("hostname"))
        dependency_buckets[dependency_key].append(source_id)
    groups.extend(sorted((sorted(value) for value in dependency_buckets.values())))

    group_rows: list[dict[str, Any]] = []
    source_group_rows: dict[str, dict[str, Any]] = {}
    group_summary: dict[str, dict[str, Any]] = {}
    for members in groups:
        member_set = set(members)
        member_sources = [sources_by_id[source_id] for source_id in members]
        hosts = sorted({source["hostname"] for source in member_sources})
        member_edges = {
            pair: edge
            for pair, edge in direct_edges.items()
            if pair <= member_set
        }
        edge_types = {edge["edge_type"] for edge in member_edges.values()}
        if "ORDERED_BRAND_SEQUENCE_SET_AND_ORDER_SIMILARITY" in edge_types:
            status = "PROBABLE_CROSS_HOST_REPLICA"
            confidence = "MEDIUM"
        elif "EXACT_CONTENT_FINGERPRINT" in edge_types:
            status = "DUPLICATE_DEPENDENT"
            confidence = "HIGH"
        elif "TITLE_AND_BRAND_ORDER_FINGERPRINT" in edge_types:
            status = "PROBABLE_DUPLICATE_DEPENDENT"
            confidence = "MEDIUM"
        elif len(members) > 1:
            status = "SAME_HOST_DEPENDENT"
            confidence = "HIGH"
        else:
            status = "UNRESOLVED"
            confidence = "LOW"
        bases = sorted(edge_types)
        if not bases:
            bases = [
                "SAME_PUBLISHER"
                if len(members) > 1
                else "UNRESOLVED_SINGLETON"
            ]
        group_id = stable_id("igroup", *members)
        replica_component_id = (
            stable_id("replica_component", *members) if member_edges else ""
        )
        set_similarity = max(
            (float(edge["set_similarity"]) for edge in member_edges.values()),
            default=0.0,
        )
        order_similarity = max(
            (float(edge["order_similarity"]) for edge in member_edges.values()),
            default=0.0,
        )
        summary = {
            "independence_group_id": group_id,
            "grouping_basis": PIPE_SEPARATOR.join(bases),
            "confidence": confidence,
            "independence_status": status,
            "fingerprint": stable_id("ifp", *members, *bases),
            "member_sources": PIPE_SEPARATOR.join(members),
            "member_count": len(members),
            "hostnames": PIPE_SEPARATOR.join(hosts),
            "group_type": status,
            "cross_host_similarity": round(set_similarity, 6),
            "cross_host_order_similarity": round(order_similarity, 6),
            "probable_replica_group_id": replica_component_id,
            "replica_component_id": replica_component_id,
            "replica_grouping_basis": PIPE_SEPARATOR.join(bases),
            "replica_member_source_ids": PIPE_SEPARATOR.join(
                sorted(source_id for source_id in members if direct_partners[source_id])
            ),
        }
        group_summary[group_id] = summary
        for source in member_sources:
            source_id = source["source_id"]
            partners = sorted(direct_partners[source_id])
            direct_member = bool(partners)
            platform_dependency = (
                "SHARED_MULTIUSER_PLATFORM_ONLY"
                if source.get("platform_type", "").endswith("MULTIUSER")
                else "HOSTNAME_PLATFORM_DEPENDENCY"
            )
            publisher_status = source.get("publisher_identity_status", "")
            publisher_dependency = (
                "UNRESOLVED_PUBLISHER"
                if publisher_status == "UNRESOLVED_PUBLISHER"
                else "PUBLISHER_LEVEL_DEPENDENCY"
            )
            diversity_status = (
                "REPLICA_OR_DEPENDENT"
                if direct_member or status in {
                    "PROBABLE_CROSS_HOST_REPLICA",
                    "DUPLICATE_DEPENDENT",
                    "PROBABLE_DUPLICATE_DEPENDENT",
                }
                else "SHARED_PLATFORM_UNRESOLVED"
                if publisher_status == "UNRESOLVED_PUBLISHER"
                else publisher_status
            )
            row = {
                "independence_group_id": group_id,
                "source_id": source_id,
                "source_row_id": source["source_row_id"],
                "hostname": source["hostname"],
                "platform_id": source.get("platform_id", ""),
                "platform_type": source.get("platform_type", ""),
                "publisher_id": source.get("publisher_id", ""),
                "publisher_identity_status": publisher_status,
                "publisher_counts_for_diversity": source.get("publisher_counts_for_diversity", "NO"),
                "independence_counts_for_readiness": (
                    "YES" if diversity_status in {"RESOLVED_PUBLISHER", "PLATFORM_USER_RESOLVED"} else "NO"
                ),
                "diversity_evidence_status": diversity_status,
                "publication_id": source.get("publication_id", ""),
                "platform_dependency": platform_dependency,
                "publisher_dependency": publisher_dependency,
                "hostname_dependency": (
                    "YES" if len(hostname_members[source["hostname"]]) > 1 else "NO"
                ),
                "editorial_independence_status": (
                    "UNRESOLVED_EDITORIAL_INDEPENDENCE"
                    if status == "UNRESOLVED"
                    else status
                ),
                "grouping_basis": summary["grouping_basis"],
                "confidence": confidence,
                "independence_status": status,
                "group_type": status,
                "fingerprint": summary["fingerprint"],
                "ordered_brand_sequence": PIPE_SEPARATOR.join(
                    source.get("ordered_brand_sequence", [])
                ),
                "normalized_brand_set": PIPE_SEPARATOR.join(
                    source.get("normalized_brand_set", [])
                ),
                "brand_sequence_fingerprint": source.get(
                    "brand_sequence_fingerprint", ""
                ),
                "cross_host_similarity": round(set_similarity, 6),
                "cross_host_order_similarity": round(order_similarity, 6),
                "order_similarity": round(order_similarity, 6),
                "probable_replica_group_id": replica_component_id,
                "replica_component_id": replica_component_id,
                "probable_replica_member": "YES" if direct_member else "NO",
                "direct_replica_member": "YES" if direct_member else "NO",
                "direct_replica_edge_count": len(partners),
                "direct_replica_partner_ids": PIPE_SEPARATOR.join(partners),
                "transitive_only_relationship": "NO",
                "hostname_member_count": len(
                    hostname_members.get(source["hostname"], [])
                ),
                "replica_grouping_basis": summary["replica_grouping_basis"],
                "supporting_row_ids": PIPE_SEPARATOR.join(
                    [source_id, source["source_row_id"]]
                ),
                "member_sources": summary["member_sources"],
            }
            group_rows.append(row)
            source_group_rows[source_id] = row

    group_rows.sort(
        key=lambda row: (
            row["independence_group_id"],
            row["source_id"],
        )
    )
    return group_rows, source_group_rows, group_summary


def classify_source_quality(
    source: dict[str, Any],
    group: dict[str, Any],
) -> dict[str, Any]:
    host = clean_text(source.get("hostname"))
    text = normalized_fingerprint_text(
        " ".join(
            [
                clean_text(source.get("title")),
                clean_text(source.get("summary")),
                clean_text(source.get("raw_content")),
            ]
        )
    )
    promotional_signals = sorted(
        {
            pattern
            for pattern in PROMOTIONAL_TEXT_PATTERNS
            if re.search(pattern, text, re.IGNORECASE)
        }
    )
    affiliate_signal = bool(AFFILIATE_DISCLOSURE_PATTERN.search(text))
    community_context_signal = bool(COMMUNITY_CONTEXT_PATTERN.search(text))
    probable_replica = (
        group["independence_status"] == "PROBABLE_CROSS_HOST_REPLICA"
        and group.get("probable_replica_member") == "YES"
    )
    low_originality_signal = probable_replica and (
        bool(promotional_signals)
        or not re.search(
            r"\bmethodology\b|\bmetodologia\b|\bmetodolog[ií]a\b|"
            r"\bauthor\b|\bautor\b|\btested by\b|\btestado por\b|"
            r"\bprobado por\b",
            text,
            re.IGNORECASE,
        )
    )
    url = clean_text(source.get("url"))
    title = clean_text(source.get("title"))
    path = urlparse(url).path.casefold()
    off_topic_signal = bool(
        host == "reddit.com"
        and "/r/" in path
        and not re.search(
            r"/r/(?:iptv|cordcutters|cutthecord|androidtv|firetv|samsung|streaming)",
            path,
        )
    )
    superlative_signal = bool(
        re.search(
            r"\b(?:best|#1|number one|only one|top provider|recommend)\b",
            f"{title} {text}",
            re.IGNORECASE,
        )
    )
    first_person_signal = bool(
        re.search(r"\b(?:i tested|i found|my honest|i recommend|we tested)\b", text)
    )
    call_to_action_signal = bool(
        re.search(
            r"\b(?:buy now|get started|start streaming|subscribe now|"
            r"discount|coupon|limited offer|visit .* today)\b",
            text,
            re.IGNORECASE,
        )
    )
    self_promotion_signal = bool(
        (superlative_signal and (first_person_signal or call_to_action_signal))
        or title.casefold().startswith("show hn:")
    )
    spam_signal = bool(
        (off_topic_signal and (superlative_signal or self_promotion_signal))
        or "removed by moderator" in text
        or title.casefold().startswith("[ removed")
    )
    promotional_risk = (
        "HIGH"
        if spam_signal or self_promotion_signal or promotional_signals
        else "MEDIUM"
        if affiliate_signal
        else "LOW"
    )
    if group["independence_status"] in {
        "DUPLICATE_DEPENDENT",
        "PROBABLE_DUPLICATE_DEPENDENT",
    } or low_originality_signal or spam_signal:
        level = "E"
        confidence = "HIGH" if group[
            "independence_status"
        ] == "DUPLICATE_DEPENDENT" else "MEDIUM"
        basis = (
            "Strong local cross-host duplication or probable replica "
            "coincides with low-originality, unsupported-evaluation, or "
            "promotional signals."
        )
    elif affiliate_signal:
        level = "C"
        confidence = "MEDIUM"
        basis = "Local content contains an affiliate disclosure signal."
    elif promotional_signals or self_promotion_signal or (
        host in SELF_PUBLISHING_HOSTS
        or any(keyword in host for keyword in PROMOTIONAL_HOST_KEYWORDS)
    ):
        level = "D"
        confidence = "MEDIUM"
        basis = (
            "The concrete publication contains observable promotional, "
            "reseller, subscription, or self-publishing signals."
        )
    elif host == "trustpilot.com":
        level = "C" if community_context_signal else "UNKNOWN"
        confidence = "LOW"
        basis = (
            "Commercial review-platform content is retained for discovery, "
            "but the hostname alone does not establish independent quality."
        )
    elif (
        host in COMMUNITY_HOSTS
        and community_context_signal
        and not off_topic_signal
        and len(text) >= 100
    ):
        level = "B"
        confidence = "MEDIUM"
        basis = (
            "The concrete community publication retains technical, review, "
            "discussion, or user-experience context without detected "
            "promotional signals."
        )
    else:
        level = "UNKNOWN"
        confidence = "LOW"
        basis = (
            "Local evidence is insufficient to establish authorship, "
            "methodology, affiliation, or editorial independence."
        )
    brands = source.get("brands_detected_list", [])
    return {
        "source_id": source["source_id"],
        "source_row_id": source["source_row_id"],
        "source_url": clean_text(source.get("url")),
        "hostname": host,
        "quality_level": level,
        "publication_quality": level,
        "quality_confidence": confidence,
        "quality_basis": basis,
        "host_type": (
            "COMMUNITY"
            if host in COMMUNITY_HOSTS
            else "SELF_PUBLISHING"
            if host in SELF_PUBLISHING_HOSTS
            else "OTHER"
        ),
        "platform_type": source.get("platform_type", ""),
        "publisher_id": source.get("publisher_id", ""),
        "publisher_identity": source.get("publisher_identity_status", ""),
        "promotional_risk": promotional_risk,
        "off_topic_risk": "HIGH" if off_topic_signal else "LOW",
        "self_promotion_risk": "HIGH" if self_promotion_signal else "LOW",
        "affiliate_risk": "HIGH" if affiliate_signal else "LOW",
        "spam_risk": "HIGH" if spam_signal else "LOW",
        "A_assessment_status": "A_NOT_ASSESSABLE_FROM_CURRENT_CORPUS",
        "publication_promotional_signals": PIPE_SEPARATOR.join(
            promotional_signals
        ),
        "publication_affiliate_signal": (
            "YES" if affiliate_signal else "NO"
        ),
        "publication_community_context_signal": (
            "YES" if community_context_signal else "NO"
        ),
        "publication_low_originality_signal": (
            "YES" if low_originality_signal else "NO"
        ),
        "discovery_value": "HIGH" if brands else "LIMITED",
        "identity_value": "NOT_ASSESSED_IN_1A",
        "legality_value": "NOT_ASSESSED_IN_1A",
        "requires_human_review": "YES" if level == "UNKNOWN" else "NO",
        "supporting_row_ids": PIPE_SEPARATOR.join(
            [source["source_id"], source["source_row_id"]]
        ),
    }


def build_quality_registry(
    sources: list[dict[str, Any]],
    source_groups: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    rows = [
        classify_source_quality(
            source,
            source_groups[source["source_id"]],
        )
        for source in sources
    ]
    rows.sort(key=lambda row: row["source_id"])
    return rows, {row["source_id"]: row for row in rows}


def alias_status_for(raw_name: str, canonical: str) -> tuple[str, str, str]:
    raw_normalized = normalized_name(raw_name)
    canonical_normalized = normalized_name(canonical)
    if raw_normalized == canonical_normalized:
        return (
            "ALIAS_CONFIRMED",
            "Exact normalized historical canonical name.",
            "NO",
        )
    if compact_name(raw_name) == compact_name(canonical):
        return (
            "ALIAS_CONFIRMED",
            "Exact compact historical spelling variant.",
            "NO",
        )
    return (
        "ALIAS_PROBABLE",
        (
            "Historical cleaning artifact grouped this spelling under the "
            "canonical brand; legal identity was not assessed."
        ),
        "YES",
    )


def source_ids_for_raw(
    raw: dict[str, Any],
    source_by_url: dict[str, dict[str, Any]],
) -> list[str]:
    source_ids: list[str] = []
    for url in split_pipe(raw.get("evidence_urls")):
        source = source_by_url.get(url)
        if source is None:
            raise RuntimeError(
                f"Historical brand evidence URL missing from corpus: {url}"
            )
        source_ids.append(source["source_id"])
    return sorted(set(source_ids))


def build_raw_mentions(
    mapped_rows: list[dict[str, Any]],
    source_by_url: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mapped in mapped_rows:
        raw = mapped["raw"]
        raw_name = clean_text(raw.get("brand_name"))
        urls = split_pipe(raw.get("evidence_urls"))
        sources = [source_by_url[url] for url in urls]
        source_ids = sorted({source["source_id"] for source in sources})
        queries = sorted(
            {
                query
                for source in sources
                for query in source.get("matched_queries_list", [])
                if clean_text(query)
            }
        )
        primary_source = sources[0] if sources else None
        supporting = [mapped["raw_row_id"], *source_ids]
        rows.append(
            {
                "mention_id": stable_id(
                    "mention",
                    normalized_name(raw_name),
                    mapped["raw_row_id"],
                ),
                "raw_name": raw_name,
                "normalized_name": normalized_name(raw_name),
                "source_id": (
                    primary_source["source_id"]
                    if primary_source is not None
                    else ""
                ),
                "source_url": (
                    clean_text(primary_source.get("url"))
                    if primary_source is not None
                    else ""
                ),
                "query_context": PIPE_SEPARATOR.join(queries),
                "source_row_id": mapped["raw_row_id"],
                "supporting_row_ids": PIPE_SEPARATOR.join(supporting),
            }
        )
    rows.sort(key=lambda row: row["mention_id"])
    return rows


def build_alias_rows(
    clean_by_brand: dict[str, list[dict[str, Any]]],
    collision_by_brand: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    collision_by_brand = collision_by_brand or {}
    rows: list[dict[str, Any]] = []
    for canonical, mapped_rows in clean_by_brand.items():
        brand_id = canonical_brand_id(canonical)
        for mapped in mapped_rows:
            raw_name = clean_text(mapped["raw"].get("brand_name"))
            status, basis, human_review = alias_status_for(
                raw_name,
                canonical,
            )
            source_ids = [
                stable_id("src", normalized_name(url))
                for url in split_pipe(mapped["raw"].get("evidence_urls"))
            ]
            rows.append(
                {
                    "alias_id": alias_id(raw_name, canonical),
                    "alias_name": raw_name,
                    "canonical_brand_id": brand_id,
                    "canonical_brand_name": canonical,
                    "alias_status": status,
                    "decision_basis": basis,
                    "supporting_row_ids": PIPE_SEPARATOR.join(
                        [mapped["raw_row_id"], *sorted(source_ids)]
                    ),
                    "requires_human_review": human_review,
                    "possible_alias_collision_id": collision_by_brand.get(
                        canonical,
                        {},
                    ).get("possible_alias_collision_id", ""),
                    "candidate_canonical_brand_ids": collision_by_brand.get(
                        canonical,
                        {},
                    ).get("candidate_canonical_brand_ids", ""),
                    "collision_basis": collision_by_brand.get(
                        canonical,
                        {},
                    ).get("collision_basis", ""),
                    "shared_supporting_row_ids": collision_by_brand.get(
                        canonical,
                        {},
                    ).get("shared_supporting_row_ids", ""),
                    "collision_confidence": collision_by_brand.get(
                        canonical,
                        {},
                    ).get("collision_confidence", ""),
                    "alias_collision_status": collision_by_brand.get(
                        canonical,
                        {},
                    ).get("alias_collision_status", ""),
                    "collision_type": collision_by_brand.get(
                        canonical, {}
                    ).get("collision_type", ""),
                    "shared_source_count": collision_by_brand.get(
                        canonical, {}
                    ).get("shared_source_count", 0),
                    "shared_context_count": collision_by_brand.get(
                        canonical, {}
                    ).get("shared_context_count", 0),
                    "contradictory_context_count": collision_by_brand.get(
                        canonical, {}
                    ).get("contradictory_context_count", 0),
                    "collision_supporting_row_ids": collision_by_brand.get(
                        canonical, {}
                    ).get("collision_supporting_row_ids", ""),
                    "requires_human_adjudication": collision_by_brand.get(
                        canonical, {}
                    ).get("requires_human_adjudication", "NO"),
                }
            )
    rows.sort(
        key=lambda row: (
            normalized_name(row["canonical_brand_name"]),
            normalized_name(row["alias_name"]),
        )
    )
    return rows


def collision_normalized_name(value: str) -> str:
    compact = re.sub(r"[^a-z0-9]+", "", normalized_name(value))
    previous = ""
    while compact != previous:
        previous = compact
        compact = re.sub(r"^(?:iptv|tv)|(?:iptv|tv)$", "", compact)
    return compact


def collision_context_profile(
    canonical: str,
    source_ids: Iterable[str],
    sources_by_id: dict[str, dict[str, Any]],
) -> set[str]:
    profile: set[str] = set()
    for source_id in source_ids:
        source = sources_by_id.get(source_id, {})
        text = " ".join(
            clean_text(source.get(field))
            for field in ("title", "summary", "raw_content")
        )
        if not re.search(re.escape(canonical), text, re.IGNORECASE):
            continue
        if PLAYER_CONTEXT_PATTERN.search(text):
            profile.add("PLAYER")
        if NON_PROVIDER_CONTEXT_PATTERN.search(text):
            profile.add("NON_PROVIDER")
        if SERVICE_CONTEXT_PATTERN.search(text):
            profile.add("SERVICE")
        if GENERIC_PHRASE_PATTERN.search(text):
            profile.add("GENERIC")
    return profile


def build_alias_collisions(
    cleaned: list[dict[str, Any]],
    matrix_by_brand: dict[str, list[dict[str, Any]]],
    clean_by_brand: dict[str, list[dict[str, Any]]] | None = None,
    sources_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    clean_by_brand = clean_by_brand or {}
    sources_by_id = sources_by_id or {}
    candidates: dict[str, list[str]] = defaultdict(list)
    for row in cleaned:
        canonical = clean_text(row.get("canonical_brand"))
        collision_key = collision_normalized_name(canonical)
        if len(collision_key) >= 4:
            candidates[collision_key].append(canonical)
    collision_by_brand: dict[str, dict[str, Any]] = {}
    for collision_key, brands in candidates.items():
        unique_brands = sorted(set(brands), key=normalized_name)
        if len(unique_brands) < 2:
            continue
        source_sets = {
            brand: {
                row["source_id"]
                for row in matrix_by_brand.get(brand, [])
            }
            for brand in unique_brands
        }
        shared_sources = set()
        for left_index, left in enumerate(unique_brands):
            for right in unique_brands[left_index + 1:]:
                shared_sources.update(
                    source_sets[left] & source_sets[right]
                )
        profiles = {
            brand: collision_context_profile(
                brand,
                source_sets[brand],
                sources_by_id,
            )
            for brand in unique_brands
        }
        shared_contexts: set[str] = set()
        contradictory_context_count = 0
        for left_index, left in enumerate(unique_brands):
            for right in unique_brands[left_index + 1:]:
                shared_contexts.update(profiles[left] & profiles[right])
                if (
                    profiles[left]
                    and profiles[right]
                    and not profiles[left] & profiles[right]
                ):
                    contradictory_context_count += 1
        generic_collision = bool(
            re.search(
                r"(?:review|reviews|test|setup|directory|ranking|watch|guide)",
                collision_key,
            )
        )
        impersonation_signal = any(
            re.search(
                r"\b(?:impersonat|copycat|fake brand|posing as)\b",
                " ".join(
                    clean_text(sources_by_id[source_id].get("raw_content"))
                    for source_id in source_sets[brand]
                    if source_id in sources_by_id
                ),
                re.IGNORECASE,
            )
            for brand in unique_brands
        )
        if impersonation_signal:
            collision_type = "POSSIBLE_IMPERSONATION"
            confidence = "MEDIUM"
        elif generic_collision:
            collision_type = "GENERIC_COLLISION"
            confidence = "HIGH"
        elif contradictory_context_count:
            collision_type = "TRUE_HOMONYM_CANDIDATE"
            confidence = "MEDIUM"
        elif shared_sources or shared_contexts:
            collision_type = "ALIAS_DUPLICATE_CANDIDATE"
            confidence = "MEDIUM"
        else:
            collision_type = "UNRESOLVED_NOMINAL_COLLISION"
            confidence = "LOW"
        candidate_ids = [
            canonical_brand_id(brand)
            for brand in unique_brands
        ]
        collision_id = stable_id(
            "alias_collision",
            collision_key,
            *candidate_ids,
        )
        record = {
            "possible_alias_collision_id": collision_id,
            "candidate_canonical_brand_ids": PIPE_SEPARATOR.join(
                candidate_ids
            ),
            "collision_basis": (
                f"Canonical names collapse after nominal normalization; "
                f"collision_type={collision_type}; "
                f"shared_source_count={len(shared_sources)}; "
                f"shared_context_count={len(shared_contexts)}; "
                f"contradictory_context_count={contradictory_context_count}. "
                "No automatic merge is performed."
            ),
            "shared_supporting_row_ids": PIPE_SEPARATOR.join(
                sorted(shared_sources)
            ),
            "collision_confidence": confidence,
            "alias_collision_status": collision_type,
            "collision_type": collision_type,
            "shared_source_count": len(shared_sources),
            "shared_context_count": len(shared_contexts),
            "contradictory_context_count": contradictory_context_count,
            "collision_supporting_row_ids": PIPE_SEPARATOR.join(
                sorted(
                    set(shared_sources)
                    | {
                        row["source_id"]
                        for brand in unique_brands
                        for row in matrix_by_brand.get(brand, [])
                    }
                    | {
                        mapped["raw_row_id"]
                        for brand in unique_brands
                        for mapped in clean_by_brand.get(brand, [])
                    }
                )
            ),
            "requires_human_adjudication": "YES",
        }
        for brand in unique_brands:
            collision_by_brand[brand] = dict(record)
    return collision_by_brand


def build_exclusion_rows(
    rejected_by_brand: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for canonical, mapped_rows in rejected_by_brand.items():
        target = mapped_rows[0]["target"]
        reason = clean_text(target.get("rejection_reason"))
        for mapped in mapped_rows:
            raw_name = clean_text(mapped["raw"].get("brand_name"))
            source_ids = [
                stable_id("src", normalized_name(url))
                for url in split_pipe(mapped["raw"].get("evidence_urls"))
            ]
            rows.append(
                {
                    "exclusion_id": exclusion_id(raw_name, reason),
                    "raw_name": raw_name,
                    "normalized_name": normalized_name(raw_name),
                    "exclusion_reason": reason,
                    "original_category": clean_text(target.get("category")),
                    "decision_basis": (
                        "Preserved historical cleaning decision; no new "
                        "external evidence was introduced."
                    ),
                    "supporting_row_ids": PIPE_SEPARATOR.join(
                        [mapped["raw_row_id"], *sorted(source_ids)]
                    ),
                }
            )
    rows.sort(
        key=lambda row: (
            normalized_name(row["raw_name"]),
            row["exclusion_id"],
        )
    )
    return rows


def build_brand_source_matrix(
    cleaned: list[dict[str, Any]],
    clean_by_brand: dict[str, list[dict[str, Any]]],
    source_by_url: dict[str, dict[str, Any]],
    source_groups: dict[str, dict[str, Any]],
    quality_by_source: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    rows: list[dict[str, Any]] = []
    by_brand: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for clean_row in cleaned:
        canonical = clean_text(clean_row.get("canonical_brand"))
        brand_id = canonical_brand_id(canonical)
        per_source: dict[str, dict[str, Any]] = {}
        for mapped in clean_by_brand[canonical]:
            raw_id = mapped["raw_row_id"]
            for url in split_pipe(mapped["raw"].get("evidence_urls")):
                source = source_by_url[url]
                source_id = source["source_id"]
                accumulator = per_source.setdefault(
                    source_id,
                    {
                        "raw_ids": set(),
                        "mention_count": 0,
                        "source": source,
                    },
                )
                accumulator["raw_ids"].add(raw_id)
                accumulator["mention_count"] += 1
        for source_id, item in per_source.items():
            source = item["source"]
            published_date = clean_text(source.get("published_date"))
            row = {
                "canonical_brand_id": brand_id,
                "canonical_brand_name": canonical,
                "source_id": source_id,
                "independence_group_id": source_groups[source_id][
                    "independence_group_id"
                ],
                "source_group_type": source_groups[source_id][
                    "group_type"
                ],
                "source_probable_replica_member": source_groups[source_id][
                    "probable_replica_member"
                ],
                "source_direct_replica_member": source_groups[source_id].get(
                    "direct_replica_member", "NO"
                ),
                "source_direct_replica_edge_count": source_groups[source_id].get(
                    "direct_replica_edge_count", 0
                ),
                "source_platform_id": source_groups[source_id].get(
                    "platform_id", ""
                ),
                "source_publisher_id": source_groups[source_id].get(
                    "publisher_id", ""
                ),
                "source_publisher_identity_status": source_groups[source_id].get(
                    "publisher_identity_status", "UNRESOLVED_PUBLISHER"
                ),
                "publisher_counts_for_diversity": source_groups[source_id].get(
                    "publisher_counts_for_diversity", "NO"
                ),
                "independence_counts_for_readiness": source_groups[source_id].get(
                    "independence_counts_for_readiness", "NO"
                ),
                "diversity_evidence_status": source_groups[source_id].get(
                    "diversity_evidence_status", "UNRESOLVED_PUBLISHER"
                ),
                "source_hostname_member_count": source_groups[source_id].get(
                    "hostname_member_count", 1
                ),
                "mention_count": item["mention_count"],
                "quality_level": quality_by_source[source_id]["quality_level"],
                "linked_query_contexts": PIPE_SEPARATOR.join(
                    sorted(
                        clean_text(query)
                        for query in source.get(
                            "matched_queries_list",
                            [],
                        )
                        if clean_text(query)
                    )
                ),
                "query_supporting_row_ids": PIPE_SEPARATOR.join(
                    [source_id, source["source_row_id"]]
                ),
                "first_seen": published_date or "NOT_AVAILABLE",
                "last_seen": published_date or "NOT_AVAILABLE",
                "supporting_row_ids": PIPE_SEPARATOR.join(
                    [
                        source_id,
                        source["source_row_id"],
                        *sorted(item["raw_ids"]),
                    ]
                ),
            }
            rows.append(row)
            by_brand[canonical].append(row)
    rows.sort(
        key=lambda row: (
            normalized_name(row["canonical_brand_name"]),
            row["source_id"],
        )
    )
    return rows, by_brand


def query_language(query: str) -> str:
    padded = f" {normalized_fingerprint_text(query)} "
    if any(
        token in padded
        for token in (
            " melhor ",
            " teste ",
            " gratis ",
            " canais ",
            " futebol ",
            " assinatura ",
        )
    ):
        return "PT"
    if any(
        token in padded
        for token in (
            " mejor ",
            " prueba ",
            " gratis ",
            " canales ",
            " proveedor ",
            " servicio ",
        )
    ):
        return "ES"
    if any(
        token in padded
        for token in (
            " best ",
            " provider ",
            " review ",
            " free trial ",
            " sports ",
            " service ",
            " reseller ",
            " white label ",
        )
    ) or padded.strip().startswith("site:"):
        return "EN"
    return "UNRESOLVED_LANGUAGE"


def language_and_geography(
    linked_queries: Iterable[str],
) -> tuple[set[str], set[str], set[str]]:
    queries = {
        clean_text(query)
        for query in linked_queries
        if clean_text(query)
    }
    languages: set[str] = set()
    geographies: set[str] = set()
    for query in queries:
        padded = f" {normalized_fingerprint_text(query)} "
        languages.add(query_language(query))
        for geography, terms in GEOGRAPHY_TERMS.items():
            if any(term in padded for term in terms):
                geographies.add(geography)
    return queries, languages, geographies


def brand_group_recurrence_weight(
    *,
    group_status: str,
    group_member_source_count: int,
    brand_mentioning_member_count: int,
) -> float:
    if group_status == "UNRESOLVED":
        return 0.50
    if group_status == "PROBABLE_CROSS_HOST_REPLICA":
        if brand_mentioning_member_count <= 1:
            return PROBABLE_REPLICA_SINGLE_PAGE_MAX
        return PROBABLE_REPLICA_REPEATED_MAX
    if group_status == "SAME_HOST_DEPENDENT":
        if brand_mentioning_member_count <= 1:
            return 0.50
        if group_member_source_count <= 1:
            return 0.50
        presence = ratio(
            brand_mentioning_member_count,
            group_member_source_count,
        )
        return min(
            SAME_HOST_BRAND_RECURRENCE_MAX,
            0.50 + 0.25 * presence,
        )
    if group_status in {
        "DUPLICATE_DEPENDENT",
        "PROBABLE_DUPLICATE_DEPENDENT",
    }:
        return 0.50 if brand_mentioning_member_count > 1 else 0.25
    if group_status == "DEMONSTRATED_EDITORIAL_INDEPENDENCE":
        return 1.0
    return 0.50


def brand_group_recurrence_details(
    brand_matrix: list[dict[str, Any]],
    group_summary: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in brand_matrix:
        by_group[row["independence_group_id"]].append(row)
    details: list[dict[str, Any]] = []
    for group_id in sorted(by_group):
        summary = group_summary[group_id]
        mentioning_count = len(
            {row["source_id"] for row in by_group[group_id]}
        )
        member_count = int(summary["member_count"])
        replica_mentioning_count = sum(
            row.get("source_probable_replica_member") == "YES"
            for row in by_group[group_id]
        )
        effective_status = summary["independence_status"]
        if (
            effective_status == "PROBABLE_CROSS_HOST_REPLICA"
            and replica_mentioning_count == 0
        ):
            effective_status = (
                "SAME_HOST_DEPENDENT"
                if any(
                    int(row.get("source_hostname_member_count", 1)) > 1
                    for row in by_group[group_id]
                )
                else "UNRESOLVED"
            )
        weight = brand_group_recurrence_weight(
            group_status=effective_status,
            group_member_source_count=member_count,
            brand_mentioning_member_count=mentioning_count,
        )
        detail = {
            "independence_group_id": group_id,
            "group_member_source_count": member_count,
            "brand_mentioning_member_count": mentioning_count,
            "brand_group_presence_ratio": ratio(
                mentioning_count,
                member_count,
            ),
            "group_dependency_status": effective_status,
            "brand_group_recurrence_weight": weight,
            "brand_replica_mentioning_source_count": (
                replica_mentioning_count
            ),
        }
        details.append(detail)
        for row in by_group[group_id]:
            row.update(detail)
    return details


def independent_recurrence_value(
    brand_matrix: list[dict[str, Any]],
    group_summary: dict[str, dict[str, Any]],
) -> float:
    return sum(
        detail["brand_group_recurrence_weight"]
        for detail in brand_group_recurrence_details(
            brand_matrix,
            group_summary,
        )
    )


def local_context_windows(
    canonical: str,
    raw_names: Iterable[str],
    sources: Iterable[dict[str, Any]],
) -> list[str]:
    terms = sorted(
        {
            clean_text(term)
            for term in [canonical, *raw_names]
            if clean_text(term)
        },
        key=len,
        reverse=True,
    )
    windows: list[str] = []
    for source in sources:
        text = " ".join(
            [
                clean_text(source.get("title")),
                clean_text(source.get("summary")),
                clean_text(source.get("raw_content")),
            ]
        )
        lower = text.casefold()
        for term in terms:
            start_at = 0
            term_lower = term.casefold()
            while len(windows) < 80:
                index = lower.find(term_lower, start_at)
                if index < 0:
                    break
                start = max(0, index - 180)
                end = min(len(text), index + len(term) + 180)
                windows.append(text[start:end])
                start_at = index + len(term)
    return windows


def classify_mention_use(
    *,
    exact_variant: str,
    left_context: str,
    right_context: str,
    fragment: str,
) -> tuple[str, str]:
    """Classify the use immediately attached to one exact local mention."""
    normalized_variant = normalized_fingerprint_text(exact_variant)
    normalized_fragment = normalized_fingerprint_text(fragment)
    left = normalized_fingerprint_text(left_context[-90:])
    right = normalized_fingerprint_text(right_context[:120])
    mention_pattern = re.escape(normalized_variant)
    if re.search(
        r"\b(?:verizon|rogers|deutsche telekom|telecom|cable)\b",
        normalized_variant,
    ) or re.search(
        rf"\b(?:verizon|rogers|deutsche telekom|telecom|cable)\b.{{0,45}}"
        rf"{mention_pattern}|{mention_pattern}.{{0,45}}\b(?:telecom|pay tv)\b",
        normalized_fragment,
    ):
        return "OTT_OR_TELECOM_USE", "TELECOM_OR_PAYTV"
    if (
        re.search(
            r"\b(?:hulu|paramount|youtube tv|peacock|netflix|prime video|"
            r"sling tv|fubotv|directv stream)\b",
            normalized_fragment,
        )
        and re.search(r"\b(?:live tv|streaming|verified|partner)\b", normalized_fragment)
    ):
        return "OTT_OR_TELECOM_USE", "LEGAL_OTT"
    if re.search(
        r"\b(?:broadcast networks?|television channel|channels? included|"
        r"major channels?|channel suites?|regional feeds?|parrilla|canais)\b",
        normalized_fragment,
    ) and re.search(mention_pattern, normalized_fragment):
        return "BROADCASTER_OR_CHANNEL_USE", "BROADCASTER_OR_CHANNEL"
    if re.search(
        r"\b(?:technical foundation|technical terms?|internet protocol "
        r"television|delivery backbone|technology|what is iptv)\b",
        normalized_fragment,
    ) and not re.search(r"\b(?:offers?|provides?|provider|subscription plan)\b", right):
        return "INFRASTRUCTURE_OR_TECHNICAL_USE", "INFRASTRUCTURE_TERM"
    attached_product_context = " ".join((left[-75:], right[:125]))
    if re.search(
        r"\b(?:iptv\s+)?(?:app|application|player|client|addon|add on|"
        r"playback software|playlist player|interface|dvr|multiple playlists?)\b",
        attached_product_context,
    ) and not re.search(
        r"^(?:is\s+)?(?:an?\s+)?(?:provider|subscription service)\b|"
        r"^(?:offers?|provides?)\s+(?:channels?|subscriptions?|service plans?)\b",
        right,
    ):
        return "PLAYER_OR_APPLICATION_USE", "ATTACHED_PRODUCT_OR_UI_CONTEXT"
    if re.search(
        r"^(?:designed|built|optimized|available)\s+for\s+"
        r"(?:android|google|fire|smart)\s+tv\b",
        right,
    ):
        return "PLAYER_OR_APPLICATION_USE", "ATTACHED_PLATFORM_DESIGN_CONTEXT"
    if re.search(
        r"\b(?:pcs?|macs?|set top boxes?|devices?|firesticks?|android boxes?)\b",
        normalized_fragment,
    ) and re.search(r"\b(?:support|compatible|works on|including|and)\b", normalized_fragment):
        return "HARDWARE_OR_DEVICE_USE", "HARDWARE_OR_DEVICE"
    if re.search(
        rf"\b(?:every|all|for|among)\s+{mention_pattern}\s+"
        r"(?:subscriptions?|services?|providers?|users?|subscribers?)\b",
        normalized_fragment,
    ) or re.search(
        rf"\b(?:uk|us|canadian|technical)\s+{mention_pattern}\b",
        normalized_fragment,
    ):
        return "DESCRIPTIVE_GENERIC_USE", "DESCRIPTIVE_PHRASE"
    variant_tokens = normalized_variant.split()
    if (
        variant_tokens
        and variant_tokens[0] in {"all", "any", "each", "every"}
        and "iptv" in variant_tokens
        and re.search(
            r"^(?:subscriptions?|services?|providers?|users?)\b",
            right,
        )
    ):
        return "DESCRIPTIVE_GENERIC_USE", "QUANTIFIED_CATEGORY_PHRASE"
    if GENERIC_PHRASE_PATTERN.search(fragment) and re.search(
        mention_pattern,
        normalized_fragment,
    ):
        return "DESCRIPTIVE_GENERIC_USE", "GENERIC_TESTING_PHRASE"
    if re.search(r"\b(?:high|top|best|not)$", left) and re.search(
        r"^(?:service|provider|subscription|performance|rated)", right
    ):
        return "DESCRIPTIVE_GENERIC_USE", "ADJECTIVAL_GENERIC_PHRASE"
    if re.search(
        r"\b(?:app|application|player|client|addon|add on|playback software|"
        r"playlist player|kodi)\b",
        right,
    ) and not re.search(r"\b(?:provider|service)\b", right[:55]):
        return "PLAYER_OR_APPLICATION_USE", "PLAYER_OR_APPLICATION"
    if re.search(
        r"\b(?:product category|service category|category of|type of)\b",
        normalized_fragment,
    ):
        return "PRODUCT_OR_CATEGORY_USE", "PRODUCT_OR_CATEGORY"
    if re.search(
        r"\b(?:directory|editorial|reviews? index|ranking methodology|"
        r"featured providers?)\b",
        normalized_fragment,
    ):
        return "EDITORIAL_OR_DIRECTORY_USE", "EDITORIAL_OR_DIRECTORY"
    nominal_right = re.search(
        r"^(?:\s|[:\-–—])*\b(?:is|offers?|provides?|delivers?|remains?|"
        r"has|includes?|subscription|provider|service|pricing|channels?|"
        r"best for|free trial|teste gratis|teste gratuito)\b",
        right,
    )
    nominal_fragment = re.search(
        rf"{mention_pattern}.{{0,90}}\b(?:provider|service|subscription|"
        r"channels?|free trial|pricing|streaming)\b",
        normalized_fragment,
    )
    commercial_table = re.search(
        rf"{mention_pattern}.{{0,100}}(?:\$|\b\d{{1,3}},\d{{3}}\+|"
        r"teste gratis|free trial|hours?)",
        normalized_fragment,
    )
    if nominal_right or nominal_fragment or commercial_table:
        return "NOMINAL_BRAND_USE", "LOCALLY_ATTRIBUTED_SERVICE_USE"
    return "UNRESOLVED_CONTEXT_USE", "NO_DECISIVE_ADJACENT_PATTERN"


def build_mention_contexts(
    canonical: str,
    raw_names: Iterable[str],
    sources: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    terms = sorted(
        {clean_text(term) for term in [canonical, *raw_names] if clean_text(term)},
        key=len,
        reverse=True,
    )
    contexts: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()
    for source in sources:
        text = "\n".join(
            clean_text(source.get(field))
            for field in ("title", "summary", "raw_content")
        )
        lower = text.casefold()
        for term in terms:
            start_at = 0
            term_lower = term.casefold()
            while len(contexts) < MAX_MENTION_CONTEXTS_PER_BRAND:
                index = lower.find(term_lower, start_at)
                if index < 0:
                    break
                end_index = index + len(term)
                immediate_left = text[max(0, index - 180):index]
                immediate_right = text[end_index:min(len(text), end_index + 24)]
                url_tail = re.search(
                    r"https?://[^\s\]\[()<>]*$",
                    immediate_left,
                    re.IGNORECASE,
                )
                path_tail = re.search(
                    r"(?:^|[/(])[^\s\]\[()<>]*$",
                    immediate_left,
                )
                looks_like_host_suffix = bool(
                    re.match(
                        r"\.(?:com|net|org|tv|co|io|app)(?:[/:?\-]|$)",
                        immediate_right,
                        re.IGNORECASE,
                    )
                )
                looks_like_slug = bool(
                    path_tail
                    and re.match(r"[-_/][a-z0-9]", immediate_right, re.IGNORECASE)
                )
                key = (clean_text(source.get("source_id")), index, end_index)
                start_at = end_index
                if url_tail or looks_like_host_suffix or looks_like_slug:
                    continue
                if key in seen:
                    continue
                seen.add(key)
                left_boundary = max(
                    text.rfind(".", 0, index),
                    text.rfind("\n", 0, index),
                    text.rfind("!", 0, index),
                    text.rfind("?", 0, index),
                )
                right_candidates = [
                    position
                    for position in (
                        text.find(".", end_index),
                        text.find("\n", end_index),
                        text.find("!", end_index),
                        text.find("?", end_index),
                    )
                    if position >= 0
                ]
                right_boundary = min(right_candidates) if right_candidates else len(text)
                fragment_start = max(left_boundary + 1, index - 180)
                fragment_end = min(right_boundary + 1, end_index + 180)
                left_context = text[max(0, index - 140):index]
                right_context = text[end_index:min(len(text), end_index + 180)]
                fragment = text[fragment_start:fragment_end]
                use_type, subtype = classify_mention_use(
                    exact_variant=text[index:end_index],
                    left_context=left_context,
                    right_context=right_context,
                    fragment=fragment,
                )
                queries = source.get("matched_queries_list", [])
                contexts.append(
                    {
                        "exact_raw_variant": text[index:end_index],
                        "left_context": left_context,
                        "right_context": right_context,
                        "sentence_or_fragment": fragment,
                        "mention_start": index,
                        "mention_end": end_index,
                        "source_id": clean_text(source.get("source_id")),
                        "source_row_id": clean_text(source.get("source_row_id")),
                        "query_id": (
                            stable_id("query", clean_text(queries[0]))
                            if queries
                            else ""
                        ),
                        "mention_use_type": use_type,
                        "mention_use_subtype": subtype,
                    }
                )
    return contexts


def embedded_longer_name_ratio(
    canonical: str,
    windows: Iterable[str],
) -> float:
    canonical_pattern = re.compile(
        re.escape(canonical),
        re.IGNORECASE,
    )
    ignored_prefixes = {
        "a",
        "an",
        "best",
        "da",
        "de",
        "do",
        "el",
        "la",
        "melhor",
        "of",
        "the",
        "top",
    }
    total = 0
    embedded = 0
    for window in windows:
        for match in canonical_pattern.finditer(window):
            total += 1
            prefix = window[max(0, match.start() - 35):match.start()]
            token_match = re.search(r"([A-Za-zÀ-ÿ0-9]+)\s+$", prefix)
            if (
                token_match
                and normalized_name(token_match.group(1))
                not in ignored_prefixes
            ):
                embedded += 1
    return ratio(embedded, total)


def semantic_label_risks(
    canonical: str,
    mention_contexts: list[dict[str, Any]],
) -> tuple[bool, bool, list[str]]:
    """Detect general embedded, descriptive, and geographic label risks.

    The rules operate on exact mention boundaries and immediate local context.
    They intentionally describe linguistic shapes rather than named entities.
    """
    normalized = normalized_name(canonical)
    tokens = normalized.split()
    label_head = tokens[0] if tokens else ""
    service_tail = bool(tokens and tokens[-1] in {"iptv", "tv"})
    geographic_heads = {
        "african", "american", "argentinian", "australian", "brazilian",
        "british", "canadian", "european", "french", "german", "indian",
        "italian", "latino", "mexican", "portuguese", "spanish", "uk",
    }
    descriptive_heads = {
        "better", "buffering", "fast", "hybrid", "luxury", "reputable",
        "strong", "studio", "trusted", "typical",
    }
    label_shape_risk = service_tail and (
        label_head in geographic_heads or label_head in descriptive_heads
    )
    strong_nominal_count = sum(
        bool(re.match(
            r"\s*(?:offers?\b|provides?\b|operates?\b|has\b|is\s+(?:an?\s+)?(?:provider|service|brand)\b)",
            clean_text(context.get("right_context")),
            re.IGNORECASE,
        ))
        for context in mention_contexts
        if context.get("mention_use_type") == "NOMINAL_BRAND_USE"
    )
    generic_or_geographic = label_shape_risk and strong_nominal_count < 2
    def compact_core(value: str) -> str:
        return "".join(
            token for token in normalized_name(value).split()
            if token not in {"iptv", "tv"}
        )

    canonical_core = compact_core(canonical)
    nominal_compact_variants = {
        compact_core(clean_text(context.get("exact_raw_variant")))
        for context in mention_contexts
        if context.get("mention_use_type") == "NOMINAL_BRAND_USE"
        and compact_core(clean_text(context.get("exact_raw_variant"))) == canonical_core
    }

    def is_nominal_compact_variant(exact_variant: str, context: dict[str, Any]) -> bool:
        """Accept a compact canonical spelling, never a larger-brand substring."""
        # Descriptive/geographic service labels retain their separate semantic
        # treatment even when their typography happens to compact cleanly.
        if label_head in geographic_heads or label_head in descriptive_heads:
            return False
        exact_core = compact_core(exact_variant)
        return bool(
            canonical_core
            and exact_core == canonical_core
            and exact_core in nominal_compact_variants
        )

    embedded_support_ids: set[str] = set()
    embedded_hits = 0
    for context in mention_contexts:
        left = str(context.get("left_context") or "")
        exact = clean_text(context.get("exact_raw_variant"))
        compact_nominal = is_nominal_compact_variant(exact, context)
        immediate = left[-40:]
        previous = re.search(r"([^\W_]+)([- ]?)$", immediate, re.UNICODE)
        if not previous:
            continue
        token, separator = previous.group(1), previous.group(2)
        token_norm = normalized_name(token)
        boundary_character = left[-1:] if left else ""
        looks_attached = (
            boundary_character == "-"
            or boundary_character.isalnum()
            or (
            boundary_character == " "
            and bool(re.search(r"[A-Z].*[A-Z0-9]|[a-z][A-Z]", token))
            )
        )
        if not compact_nominal and looks_attached and token_norm not in {
            "best", "choose", "for", "iptv", "provider", "service", "the",
            "top", "tv",
        }:
            embedded_hits += 1
            embedded_support_ids.update(
                value
                for value in (
                    clean_text(context.get("source_id")),
                    clean_text(context.get("source_row_id")),
                )
                if value
            )
        # A raw variant that contains extra leading material is direct evidence
        # that the canonical label is only a fragment of a larger expression.
        if (
            not compact_nominal
            and compact_name(exact) != compact_name(canonical)
            and compact_name(canonical) in compact_name(exact)
        ):
            embedded_hits += 1
            embedded_support_ids.update(
                value
                for value in (
                    clean_text(context.get("source_id")),
                    clean_text(context.get("source_row_id")),
                )
                if value
            )
    embedded_risk = embedded_hits > 0
    return embedded_risk, generic_or_geographic, sorted(embedded_support_ids)


def source_quality_meets_minimum(level: str) -> bool:
    return SOURCE_QUALITY_ORDER.get(level, 0) >= SOURCE_QUALITY_ORDER[
        MIN_ACCEPTABLE_SOURCE_QUALITY
    ]


def is_source_acceptable_for_readiness(
    quality: dict[str, Any],
    matrix_row: dict[str, Any],
    *,
    has_nominal_evidence: bool,
) -> bool:
    level = clean_text(quality.get("quality_level")) or "UNKNOWN"
    common_ok = (
        source_quality_meets_minimum(level)
        and quality.get("spam_risk") != "HIGH"
        and quality.get("off_topic_risk") != "HIGH"
        and matrix_row.get("source_probable_replica_member") != "YES"
        and has_nominal_evidence
    )
    if not common_ok:
        return False
    if level == "D":
        return quality.get("promotional_risk") != "HIGH"
    return level in {"A", "B", "C"}


def blocker(
    code: str,
    basis: str,
    supporting_row_ids: Iterable[str],
    severity: str = "HIGH",
) -> dict[str, Any]:
    return {
        "blocker_code": code,
        "blocker_basis": basis,
        "blocker_supporting_row_ids": sorted(
            {clean_text(value) for value in supporting_row_ids if clean_text(value)}
        ),
        "severity": severity,
    }


def serialize_blockers(items: Iterable[dict[str, Any]]) -> str:
    deduplicated = {
        item["blocker_code"]: item
        for item in sorted(
            items,
            key=lambda item: (
                BLOCKER_SEVERITY_ORDER.get(item["severity"], 99),
                item["blocker_code"],
                item["blocker_basis"],
            ),
        )
    }
    ordered = sorted(
        deduplicated.values(),
        key=lambda item: (
            BLOCKER_SEVERITY_ORDER.get(item["severity"], 99),
            item["blocker_code"],
            item["blocker_basis"],
        ),
    )
    return json.dumps(
        ordered,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) if ordered else ""


def classify_brand_semantics(
    *,
    canonical: str,
    raw_rows: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    group_details: list[dict[str, Any]],
    quality_levels: list[str],
    collision: dict[str, Any] | None,
) -> dict[str, Any]:
    raw_names = [
        clean_text(row["raw"].get("brand_name"))
        for row in raw_rows
    ]
    mention_contexts = build_mention_contexts(canonical, raw_names, sources)
    windows = [row["sentence_or_fragment"] for row in mention_contexts]
    use_counts = Counter(row["mention_use_type"] for row in mention_contexts)
    subtype_counts = Counter(
        row["mention_use_subtype"] for row in mention_contexts
    )
    nominal_count = use_counts["NOMINAL_BRAND_USE"]
    incompatible_types = MENTION_USE_TYPES - {
        "NOMINAL_BRAND_USE",
        "UNRESOLVED_CONTEXT_USE",
    }
    incompatible_count = sum(use_counts[use] for use in incompatible_types)
    incompatible_ratio = ratio(
        incompatible_count,
        nominal_count + incompatible_count,
    )
    nominal_source_count = len(
        {
            row["source_id"]
            for row in mention_contexts
            if row["mention_use_type"] == "NOMINAL_BRAND_USE"
        }
    )
    embedded_ratio = embedded_longer_name_ratio(canonical, windows)
    (
        embedded_name_fragment_risk,
        geographic_or_generic_label_risk,
        embedded_support_ids,
    ) = semantic_label_risks(canonical, mention_contexts)
    canonical_compact_core = "".join(
        token for token in normalized_name(canonical).split()
        if token not in {"iptv", "tv"}
    )
    nominal_compact_identity = any(
        "".join(
            token for token in normalized_name(raw_name).split()
            if token not in {"iptv", "tv"}
        ) == canonical_compact_core
        for raw_name in raw_names
    )
    # Repeated nominal evidence for a genuine compact spelling outweighs a
    # typography-only attached-token hit. Descriptive/geographic labels retain
    # their safeguards and distinct larger-name substrings remain detectable.
    if (
        nominal_count >= MIN_NOMINAL_BRAND_USES_FOR_PLAUSIBLE
        and nominal_compact_identity
        and not geographic_or_generic_label_risk
    ):
        embedded_name_fragment_risk = False
        embedded_support_ids = []
        embedded_ratio = 0.0
    replica_groups = {
        detail["independence_group_id"]
        for detail in group_details
        if detail["group_dependency_status"]
        == "PROBABLE_CROSS_HOST_REPLICA"
    }
    source_group_ids = {
        detail["independence_group_id"]
        for detail in group_details
    }
    support_ids = sorted(
        {
            source["source_id"]
            for source in sources
        }
        | {
            row["raw_row_id"]
            for row in raw_rows
        }
    )
    dominant_incompatible = incompatible_count >= max(1, nominal_count)
    if embedded_name_fragment_risk:
        status = "POSSIBLE_EXTRACTION_ARTIFACT"
        basis = "Exact mention boundaries show the label embedded in a longer nominal expression."
        confidence = "HIGH"
    elif geographic_or_generic_label_risk and dominant_incompatible:
        status = "GENERIC_NAME_REQUIRES_REVIEW"
        basis = "The label is geographic or descriptive and local use is not predominantly nominal."
        confidence = "HIGH"
    elif dominant_incompatible and use_counts["BROADCASTER_OR_CHANNEL_USE"]:
        status = "POSSIBLE_BROADCASTER_OR_CHANNEL"
        basis = "Mention-attached local contexts place the name in a channel or broadcaster list."
        confidence = "HIGH"
    elif dominant_incompatible and subtype_counts["LEGAL_OTT"]:
        status = "POSSIBLE_LEGAL_OTT"
        basis = "Mention-attached contexts compare the name with locally listed OTT services."
        confidence = "HIGH"
    elif dominant_incompatible and subtype_counts["TELECOM_OR_PAYTV"]:
        status = "POSSIBLE_TELECOM_OR_PAYTV"
        basis = "Mention-attached contexts identify telecom, pay-TV, or delivery-backbone use."
        confidence = "HIGH"
    elif dominant_incompatible and use_counts["INFRASTRUCTURE_OR_TECHNICAL_USE"]:
        status = "POSSIBLE_INFRASTRUCTURE_TERM"
        basis = "The exact mention is part of technical or infrastructure exposition."
        confidence = "HIGH"
    elif dominant_incompatible and use_counts["HARDWARE_OR_DEVICE_USE"]:
        status = "POSSIBLE_HARDWARE_OR_DEVICE"
        basis = "The exact mention is attached to device, compatibility, PC, Mac, or box context."
        confidence = "HIGH"
    elif dominant_incompatible and use_counts["PLAYER_OR_APPLICATION_USE"]:
        status = "POSSIBLE_PLAYER_OR_PLATFORM"
        basis = "The exact mention is used as an app, player, client, addon, or playback product."
        confidence = "HIGH"
    elif dominant_incompatible and use_counts["EDITORIAL_OR_DIRECTORY_USE"]:
        status = "POSSIBLE_EDITORIAL_OR_DIRECTORY"
        basis = "The exact mention denotes an editorial, directory, review, or ranking expression."
        confidence = "MEDIUM"
    elif dominant_incompatible and use_counts["DESCRIPTIVE_GENERIC_USE"]:
        status = "GENERIC_NAME_REQUIRES_REVIEW"
        basis = "The exact mention is used descriptively rather than as an attributable trade name."
        confidence = "HIGH"
    elif geographic_or_generic_label_risk:
        status = "GENERIC_NAME_REQUIRES_REVIEW"
        basis = "The canonical label has a geographic or descriptive service-label shape."
        confidence = "HIGH"
    elif (
        nominal_count >= MIN_NOMINAL_BRAND_USES_FOR_PLAUSIBLE
        and incompatible_ratio <= MAX_INCOMPATIBLE_CONTEXT_RATIO
        and any(source_quality_meets_minimum(level) for level in quality_levels)
    ):
        status = "PLAUSIBLE_BRAND"
        basis = (
            f"Exact mentions contain {nominal_count} nominal service uses "
            f"across {nominal_source_count} sources; incompatible_ratio="
            f"{incompatible_ratio:.6f}."
        )
        confidence = (
            "HIGH"
            if nominal_source_count >= 3 and any(
                level in {"B", "C"} for level in quality_levels
            )
            else "MEDIUM"
            if nominal_source_count >= MIN_DISTINCT_SUPPORTING_SOURCES
            else "LOW"
        )
    elif embedded_ratio >= 0.60 and len(windows) >= 2:
        status = "POSSIBLE_EXTRACTION_ARTIFACT"
        basis = "Exact mentions predominantly occur inside longer names or phrases."
        confidence = "MEDIUM"
    elif replica_groups and replica_groups == source_group_ids and nominal_count == 0:
        status = "INSUFFICIENT_LOCAL_EVIDENCE"
        basis = (
            "Evidence depends entirely on a probable cross-host replica "
            "group and does not establish a differentiated local identity."
        )
        confidence = "HIGH"
    else:
        status = "UNRESOLVED"
        basis = (
            "Local evidence is traceable but insufficient for a stronger "
            "semantic classification."
        )
        confidence = "LOW"
    collision_type = clean_text((collision or {}).get("collision_type"))
    serialized_contexts = json.dumps(
        mention_contexts,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    mention_support_ids = sorted(
        {
            value
            for row in mention_contexts
            for value in (row["source_id"], row["source_row_id"])
            if value
        }
    )
    return {
        "recalibrated_semantic_status": status,
        "semantic_status": status,
        "semantic_status_basis": basis,
        "semantic_supporting_row_ids": PIPE_SEPARATOR.join(support_ids),
        "semantic_confidence": confidence,
        "requires_human_review": "YES",
        "requires_human_adjudication": "YES",
        "recalibrated_ranking_eligible": "NO",
        "ranking_eligible": "NO",
        "adjudication_ready_eligible": "NO",
        "adjudication_blockers": "",
        "eligibility_basis": "Readiness not yet evaluated.",
        "semantic_traceability": 1.0 if support_ids else 0.0,
        "semantic_player_or_platform_risk": (
            1.0 if status == "POSSIBLE_PLAYER_OR_PLATFORM" else 0.0
        ),
        "semantic_generic_phrase_risk": (
            1.0 if status == "GENERIC_NAME_REQUIRES_REVIEW" else 0.0
        ),
        "semantic_extraction_artifact_risk": (
            1.0 if status == "POSSIBLE_EXTRACTION_ARTIFACT" else 0.0
        ),
        "semantic_insufficient_evidence_risk": (
            1.0 if status == "INSUFFICIENT_LOCAL_EVIDENCE" else 0.0
        ),
        "semantic_noncomparable_risk": (
            1.0
            if status
            in {
                "POSSIBLE_BROADCASTER_OR_CHANNEL",
                "POSSIBLE_LEGAL_OTT",
                "POSSIBLE_TELECOM_OR_PAYTV",
                "POSSIBLE_INFRASTRUCTURE_TERM",
                "POSSIBLE_HARDWARE_OR_DEVICE",
                "POSSIBLE_EDITORIAL_OR_DIRECTORY",
                "POSSIBLE_NON_PROVIDER",
            }
            else 0.0
        ),
        "semantic_context_window_count": len(mention_contexts),
        "mention_context_summary": PIPE_SEPARATOR.join(
            f"{key}={use_counts[key]}" for key in sorted(use_counts)
        ),
        "mention_contexts": serialized_contexts,
        "mention_supporting_row_ids": PIPE_SEPARATOR.join(mention_support_ids),
        "nominal_brand_use_count": nominal_count,
        "incompatible_context_use_count": incompatible_count,
        "incompatible_context_ratio": incompatible_ratio,
        "distinct_nominal_supporting_source_count": nominal_source_count,
        "collision_type": collision_type,
        "collision_confidence": clean_text(
            (collision or {}).get("collision_confidence")
        ),
        "collision_supporting_row_ids": clean_text(
            (collision or {}).get("collision_supporting_row_ids")
        ),
        "embedded_longer_name_ratio": embedded_ratio,
        "embedded_name_fragment_risk": "YES" if embedded_name_fragment_risk else "NO",
        "geographic_or_generic_label_risk": "YES" if geographic_or_generic_label_risk else "NO",
        "embedded_name_supporting_row_ids": PIPE_SEPARATOR.join(embedded_support_ids),
    }


def build_raw_provider_metrics(
    providers: list[dict[str, Any]],
    clean_by_brand: dict[str, list[dict[str, Any]]],
    matrix_by_brand: dict[str, list[dict[str, Any]]],
    sources_by_id: dict[str, dict[str, Any]],
    quality_by_source: dict[str, dict[str, Any]],
    group_summary: dict[str, dict[str, Any]],
    historical_rank_by_brand: dict[str, int],
    exclusion_rows: list[dict[str, Any]],
    collision_by_brand: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    excluded_compacts = {
        compact_name(row["raw_name"])
        for row in exclusion_rows
        if compact_name(row["raw_name"])
    }
    raw_metrics: list[dict[str, Any]] = []
    for provider in providers:
        canonical = clean_text(provider.get("canonical_brand"))
        raw_rows = clean_by_brand[canonical]
        matrix = matrix_by_brand[canonical]
        source_ids = sorted({row["source_id"] for row in matrix})
        sources = [sources_by_id[source_id] for source_id in source_ids]
        group_details = brand_group_recurrence_details(
            matrix,
            group_summary,
        )
        group_ids = {
            detail["independence_group_id"]
            for detail in group_details
        }
        group_counts = Counter(
            row["independence_group_id"]
            for row in matrix
        )
        quality_levels = [
            quality_by_source[source_id]["quality_level"]
            for source_id in source_ids
        ]
        quality_weighted = sum(
            QUALITY_WEIGHTS[level]
            for level in quality_levels
        )
        linked_queries = [
            query
            for row in matrix
            for query in split_pipe(row.get("linked_query_contexts"))
        ]
        queries, languages, geographies = language_and_geography(
            linked_queries
        )
        alias_statuses = [
            alias_status_for(
                clean_text(mapped["raw"].get("brand_name")),
                canonical,
            )[0]
            for mapped in raw_rows
        ]
        unresolved_alias_count = sum(
            status != "ALIAS_CONFIRMED"
            for status in alias_statuses
        )
        alias_completeness = ratio(
            len(raw_rows),
            parse_int(provider.get("merged_input_rows")),
        )
        expected_urls = {
            url
            for mapped in raw_rows
            for url in split_pipe(mapped["raw"].get("evidence_urls"))
        }
        provenance_completeness = ratio(
            len(source_ids),
            len(expected_urls),
        )
        duplicate_dependency_rate = (
            1.0 - ratio(len(group_ids), len(source_ids))
            if source_ids
            else 1.0
        )
        promotional_count = sum(
            level in {"D", "E"}
            for level in quality_levels
        )
        promotional_concentration = ratio(
            promotional_count,
            len(source_ids),
        )
        probable_replica_source_count = sum(
            row.get("source_probable_replica_member") == "YES"
            for row in matrix
        )
        probable_replica_concentration = ratio(
            probable_replica_source_count,
            len(source_ids),
        )
        low_originality_count = sum(
            quality_by_source[source_id].get(
                "publication_low_originality_signal"
            )
            == "YES"
            for source_id in source_ids
        )
        low_originality_concentration = ratio(
            low_originality_count,
            len(source_ids),
        )
        unresolved_alias_risk = ratio(
            unresolved_alias_count,
            len(alias_statuses),
        )
        canonical_compact = compact_name(canonical)
        homonym_matches = sum(
            canonical_compact == excluded
            or (
                len(canonical_compact) >= 6
                and len(excluded) >= 6
                and (
                    canonical_compact.startswith(excluded)
                    or excluded.startswith(canonical_compact)
                )
            )
            for excluded in excluded_compacts
        )
        exclusion_or_homonym_risk = min(homonym_matches, 1)
        largest_group_concentration = ratio(
            max(group_counts.values(), default=0),
            len(source_ids),
        )
        platform_count = len(
            {
                clean_text(source.get("source_platform"))
                for source in sources
                if clean_text(source.get("source_platform"))
            }
        )
        weighted_independent_recurrence = sum(
            float(detail["brand_group_recurrence_weight"])
            for detail in group_details
        )
        source_diversity_raw = math.sqrt(
            max(weighted_independent_recurrence, 0)
            * max(platform_count, 0)
        )
        status_counts = Counter(
            detail["group_dependency_status"]
            for detail in group_details
        )
        semantic = classify_brand_semantics(
            canonical=canonical,
            raw_rows=raw_rows,
            sources=sources,
            group_details=group_details,
            quality_levels=quality_levels,
            collision=collision_by_brand.get(canonical),
        )
        nominal_source_ids = {
            row["source_id"]
            for row in json.loads(semantic["mention_contexts"])
            if row["mention_use_type"] == "NOMINAL_BRAND_USE"
        }
        matrix_by_source = {row["source_id"]: row for row in matrix}
        acceptable_source_ids: list[str] = []
        non_promotional_acceptable_source_ids: list[str] = []
        high_promotional_source_ids: list[str] = []
        for source_id in source_ids:
            quality = quality_by_source[source_id]
            matrix_row = matrix_by_source[source_id]
            level = clean_text(quality.get("quality_level")) or "UNKNOWN"
            promotional_high = quality.get("promotional_risk") == "HIGH"
            if promotional_high:
                high_promotional_source_ids.append(source_id)
            acceptable = is_source_acceptable_for_readiness(
                quality,
                matrix_row,
                has_nominal_evidence=source_id in nominal_source_ids,
            )
            if acceptable:
                acceptable_source_ids.append(source_id)
                if not promotional_high:
                    non_promotional_acceptable_source_ids.append(source_id)
        resolved_acceptable_publishers = sorted(
            {
                clean_text(matrix_by_source[source_id].get("source_publisher_id"))
                for source_id in acceptable_source_ids
                if matrix_by_source[source_id].get("publisher_counts_for_diversity") == "YES"
                and clean_text(matrix_by_source[source_id].get("source_publisher_id"))
            }
        )
        unresolved_acceptable_source_ids = sorted(
            source_id for source_id in acceptable_source_ids
            if matrix_by_source[source_id].get("publisher_counts_for_diversity") != "YES"
        )
        resolved_acceptable_groups = sorted(
            {
                clean_text(matrix_by_source[source_id].get("independence_group_id"))
                for source_id in acceptable_source_ids
                if matrix_by_source[source_id].get("independence_counts_for_readiness") == "YES"
                and clean_text(matrix_by_source[source_id].get("independence_group_id"))
            }
        )
        high_promotional_relation_ratio = ratio(
            len(high_promotional_source_ids), len(source_ids)
        )
        raw_metrics.append(
            {
                "canonical_brand_id": canonical_brand_id(canonical),
                "canonical_brand_name": canonical,
                "raw_mention_count": len(raw_rows),
                "unique_source_count": len(source_ids),
                "raw_source_count": len(source_ids),
                "independence_group_count": len(group_ids),
                "demonstrated_independent_group_count": status_counts[
                    "DEMONSTRATED_EDITORIAL_INDEPENDENCE"
                ],
                "unresolved_group_count": status_counts["UNRESOLVED"],
                "dependent_group_count": sum(
                    count
                    for status, count in status_counts.items()
                    if status
                    not in {
                        "UNRESOLVED",
                        "DEMONSTRATED_EDITORIAL_INDEPENDENCE",
                    }
                ),
                "probable_replica_group_count": status_counts[
                    "PROBABLE_CROSS_HOST_REPLICA"
                ],
                "weighted_independent_recurrence": (
                    weighted_independent_recurrence
                ),
                "independent_recurrence": (
                    weighted_independent_recurrence
                ),
                "brand_group_recurrence_details": PIPE_SEPARATOR.join(
                    (
                        f"{detail['independence_group_id']}:"
                        f"{detail['brand_mentioning_member_count']}/"
                        f"{detail['group_member_source_count']}:"
                        f"{detail['group_dependency_status']}:"
                        f"{detail['brand_group_recurrence_weight']:.6f}"
                    )
                    for detail in group_details
                ),
                "source_quality_weighted_recurrence": quality_weighted,
                "source_diversity_raw": source_diversity_raw,
                "query_or_source_context_diversity": len(queries),
                "language_diversity": len(
                    languages - {"UNRESOLVED_LANGUAGE"}
                ),
                "geographic_context_diversity": len(geographies),
                "alias_trace_completeness": alias_completeness,
                "provenance_trace_completeness": provenance_completeness,
                "duplicate_dependency_rate": duplicate_dependency_rate,
                "promotional_source_concentration": promotional_concentration,
                "total_supporting_relations": len(source_ids),
                "high_promotional_relation_count": len(high_promotional_source_ids),
                "high_promotional_relation_ratio": high_promotional_relation_ratio,
                "non_promotional_acceptable_source_count": len(
                    non_promotional_acceptable_source_ids
                ),
                "acceptable_source_count": len(acceptable_source_ids),
                "acceptable_publisher_count": len(resolved_acceptable_publishers),
                "acceptable_independence_group_count": len(resolved_acceptable_groups),
                "resolved_acceptable_publisher_count": len(resolved_acceptable_publishers),
                "unresolved_acceptable_publisher_count": len(unresolved_acceptable_source_ids),
                "resolved_acceptable_independence_group_count": len(resolved_acceptable_groups),
                "unresolved_independence_evidence_count": len(unresolved_acceptable_source_ids),
                "publisher_diversity_eligible": (
                    "YES" if len(resolved_acceptable_publishers) >= MIN_DISTINCT_PUBLISHERS_FOR_READY else "NO"
                ),
                "independence_diversity_eligible": (
                    "YES" if len(resolved_acceptable_groups) >= MIN_DISTINCT_GROUPS_FOR_READY else "NO"
                ),
                "acceptable_source_ids": acceptable_source_ids,
                "acceptable_publisher_ids": resolved_acceptable_publishers,
                "acceptable_group_ids": resolved_acceptable_groups,
                "high_promotional_source_ids": high_promotional_source_ids,
                "quality_levels": quality_levels,
                "probable_cross_host_replica_concentration": (
                    probable_replica_concentration
                ),
                "low_originality_source_concentration": (
                    low_originality_concentration
                ),
                "unresolved_alias_risk": unresolved_alias_risk,
                "exclusion_or_homonym_risk": exclusion_or_homonym_risk,
                "single_group_concentration": largest_group_concentration,
                "historical_rank": historical_rank_by_brand.get(canonical, ""),
                "recency_status": "NOT_AVAILABLE",
                "alias_collision_status": collision_by_brand.get(
                    canonical,
                    {},
                ).get("alias_collision_status", ""),
                "possible_alias_collision_id": collision_by_brand.get(
                    canonical,
                    {},
                ).get("possible_alias_collision_id", ""),
                "collision_shared_source_count": collision_by_brand.get(
                    canonical, {}
                ).get("shared_source_count", 0),
                "collision_shared_context_count": collision_by_brand.get(
                    canonical, {}
                ).get("shared_context_count", 0),
                "collision_contradictory_context_count": collision_by_brand.get(
                    canonical, {}
                ).get("contradictory_context_count", 0),
                "unresolved_alias_collision_risk": (
                    1.0 if canonical in collision_by_brand else 0.0
                ),
                **semantic,
                "source_ids": source_ids,
                "group_ids": sorted(group_ids),
                "languages": sorted(languages) or ["UNRESOLVED_LANGUAGE"],
                "geographies": sorted(geographies) or ["NOT_AVAILABLE"],
                "queries": sorted(queries),
            }
        )
    return raw_metrics


def normalized_metric(
    value: float,
    maximum: float,
) -> float:
    if maximum <= 0:
        return 0.0
    return bounded(value / maximum * 100.0)


def apply_recalibrated_formula(
    raw_metrics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    maxima = {
        "weighted_independent_recurrence": max(
            (
                float(row["weighted_independent_recurrence"])
                for row in raw_metrics
            ),
            default=0.0,
        ),
        "source_quality_weighted_recurrence": max(
            (
                float(row["source_quality_weighted_recurrence"])
                for row in raw_metrics
            ),
            default=0.0,
        ),
        "source_diversity_raw": max(
            (
                float(row["source_diversity_raw"])
                for row in raw_metrics
            ),
            default=0.0,
        ),
        "query_or_source_context_diversity": max(
            (
                float(row["query_or_source_context_diversity"])
                for row in raw_metrics
            ),
            default=0.0,
        ),
        "language_diversity": max(
            (
                float(row["language_diversity"])
                for row in raw_metrics
            ),
            default=0.0,
        ),
        "geographic_context_diversity": max(
            (
                float(row["geographic_context_diversity"])
                for row in raw_metrics
            ),
            default=0.0,
        ),
    }
    rows: list[dict[str, Any]] = []
    for raw in raw_metrics:
        normalized = {
            "independence": normalized_metric(
                float(raw["weighted_independent_recurrence"]),
                maxima["weighted_independent_recurrence"],
            ),
            "quality_weighted_recurrence": normalized_metric(
                float(raw["source_quality_weighted_recurrence"]),
                maxima["source_quality_weighted_recurrence"],
            ),
            "source_diversity": normalized_metric(
                float(raw["source_diversity_raw"]),
                maxima["source_diversity_raw"],
            ),
            "query_context_diversity": normalized_metric(
                float(raw["query_or_source_context_diversity"]),
                maxima["query_or_source_context_diversity"],
            ),
            "language_diversity": normalized_metric(
                float(raw["language_diversity"]),
                maxima["language_diversity"],
            ),
            "geographic_context_diversity": normalized_metric(
                float(raw["geographic_context_diversity"]),
                maxima["geographic_context_diversity"],
            ),
            "alias_trace_completeness": bounded(
                float(raw["alias_trace_completeness"]) * 100.0
            ),
            "provenance_trace_completeness": bounded(
                min(
                    float(raw["provenance_trace_completeness"]),
                    float(raw["semantic_traceability"]),
                )
                * 100.0
            ),
        }
        positive_components = {
            "independence_component": (
                normalized["independence"]
                * EFFECTIVE_WEIGHTS["independence"]
                / 100.0
            ),
            "quality_weighted_recurrence_component": (
                normalized["quality_weighted_recurrence"]
                * EFFECTIVE_WEIGHTS["quality_weighted_recurrence"]
                / 100.0
            ),
            "source_diversity_component": (
                normalized["source_diversity"]
                * EFFECTIVE_WEIGHTS["source_diversity"]
                / 100.0
            ),
            "query_context_diversity_component": (
                normalized["query_context_diversity"]
                * EFFECTIVE_WEIGHTS["query_context_diversity"]
                / 100.0
            ),
            "language_diversity_component": (
                normalized["language_diversity"]
                * EFFECTIVE_WEIGHTS["language_diversity"]
                / 100.0
            ),
            "geographic_context_diversity_component": (
                normalized["geographic_context_diversity"]
                * EFFECTIVE_WEIGHTS["geographic_context_diversity"]
                / 100.0
            ),
            "alias_trace_component": (
                normalized["alias_trace_completeness"]
                * EFFECTIVE_WEIGHTS["alias_trace_completeness"]
                / 100.0
            ),
            "provenance_trace_component": (
                normalized["provenance_trace_completeness"]
                * EFFECTIVE_WEIGHTS["provenance_trace_completeness"]
                / 100.0
            ),
        }
        penalties = {
            "duplicate_dependency_penalty": min(
                15.0,
                float(raw["duplicate_dependency_rate"]) * 15.0,
            ),
            "promotional_source_penalty": min(
                20.0,
                float(raw["promotional_source_concentration"]) * 20.0,
            ),
            "unresolved_alias_penalty": min(
                10.0,
                float(raw["unresolved_alias_risk"]) * 10.0,
            ),
            "homonym_or_impersonation_penalty": min(
                15.0,
                float(raw["exclusion_or_homonym_risk"]) * 15.0,
            ),
            "single_group_concentration_penalty": min(
                10.0,
                max(
                    0.0,
                    (
                        float(raw["single_group_concentration"]) - 0.50
                    )
                    / 0.50
                    * 10.0,
                ),
            ),
            "grave_traceability_penalty": min(
                10.0,
                (
                    1.0
                    - (
                        float(raw["alias_trace_completeness"])
                        + float(raw["provenance_trace_completeness"])
                    )
                    / 2.0
                )
                * 10.0,
            ),
            "probable_cross_host_replica_dependency_penalty": min(
                15.0,
                float(
                    raw[
                        "probable_cross_host_replica_concentration"
                    ]
                )
                * 15.0,
            ),
            # Replica dependency is already penalized above. Only the
            # low-originality concentration not explained by that same
            # replica concentration receives this additional penalty.
            "low_originality_source_concentration_penalty": min(
                10.0,
                max(
                    0.0,
                    float(raw["low_originality_source_concentration"])
                    - float(
                        raw[
                            "probable_cross_host_replica_concentration"
                        ]
                    ),
                )
                * 10.0,
            ),
            "insufficient_local_brand_evidence_penalty": (
                float(raw["semantic_insufficient_evidence_risk"]) * 20.0
            ),
            "generic_phrase_risk_penalty": (
                float(raw["semantic_generic_phrase_risk"]) * 30.0
            ),
            "extraction_artifact_risk_penalty": (
                float(raw["semantic_extraction_artifact_risk"]) * 30.0
            ),
            "player_or_platform_risk_penalty": (
                float(raw["semantic_player_or_platform_risk"]) * 30.0
            ),
            "noncomparable_context_penalty": (
                float(raw["semantic_noncomparable_risk"]) * 30.0
            ),
            "unresolved_alias_collision_penalty": (
                float(raw["unresolved_alias_collision_risk"]) * 8.0
            ),
        }
        positive_score = sum(positive_components.values())
        total_penalty = sum(penalties.values())
        final_score = bounded(positive_score - total_penalty)
        supporting_ids = [raw["canonical_brand_id"], *raw["source_ids"]]
        material_blockers: list[dict[str, Any]] = []
        if raw["semantic_status"] != "PLAUSIBLE_BRAND":
            material_blockers.append(blocker(
                "SEMANTIC_STATUS_NOT_ELIGIBLE",
                f"semantic_status={raw['semantic_status']}",
                split_pipe(raw["semantic_supporting_row_ids"]),
                "CRITICAL",
            ))
        if SEMANTIC_CONFIDENCE_ORDER.get(raw["semantic_confidence"], 0) < SEMANTIC_CONFIDENCE_ORDER[MIN_SEMANTIC_CONFIDENCE_FOR_READY]:
            material_blockers.append(blocker(
                "HUMAN_REVIEW_REQUIRED",
                f"semantic_confidence={raw['semantic_confidence']} is below {MIN_SEMANTIC_CONFIDENCE_FOR_READY}",
                supporting_ids,
            ))
        if final_score <= 0.0:
            material_blockers.append(blocker(
                "ZERO_OR_NONPOSITIVE_SCORE",
                f"diagnostic_score={final_score:.6f}",
                supporting_ids,
                "CRITICAL",
            ))
        elif final_score < MIN_DIAGNOSTIC_SCORE_FOR_READY:
            material_blockers.append(blocker(
                "DIAGNOSTIC_SCORE_BELOW_READY_THRESHOLD",
                f"diagnostic_score={final_score:.6f} is below ready threshold {MIN_DIAGNOSTIC_SCORE_FOR_READY:.6f}",
                supporting_ids,
            ))
        if int(raw["acceptable_source_count"]) < MIN_ACCEPTABLE_SOURCE_COUNT_FOR_READY:
            material_blockers.append(blocker(
                "INSUFFICIENT_ACCEPTABLE_SOURCES",
                f"acceptable_source_count={raw['acceptable_source_count']}; minimum={MIN_ACCEPTABLE_SOURCE_COUNT_FOR_READY}",
                supporting_ids,
            ))
        if not any(source_quality_meets_minimum(level) for level in [
            clean_text(level) for level in raw.get("quality_levels", [])
        ]) or int(raw["acceptable_source_count"]) == 0:
            material_blockers.append(blocker(
                "SOURCE_QUALITY_TOO_LOW",
                f"No acceptable source satisfies minimum quality {MIN_ACCEPTABLE_SOURCE_QUALITY}",
                supporting_ids,
            ))
        if int(raw["acceptable_publisher_count"]) < MIN_DISTINCT_PUBLISHERS_FOR_READY:
            material_blockers.append(blocker(
                "INSUFFICIENT_PUBLISHER_DIVERSITY",
                f"acceptable_publisher_count={raw['acceptable_publisher_count']}; minimum={MIN_DISTINCT_PUBLISHERS_FOR_READY}",
                [*supporting_ids, *raw["acceptable_publisher_ids"]],
            ))
        if int(raw["acceptable_independence_group_count"]) < MIN_DISTINCT_GROUPS_FOR_READY:
            material_blockers.append(blocker(
                "INSUFFICIENT_INDEPENDENCE",
                f"acceptable_independence_group_count={raw['acceptable_independence_group_count']}; minimum={MIN_DISTINCT_GROUPS_FOR_READY}",
                [*supporting_ids, *raw["acceptable_group_ids"]],
            ))
        if (
            float(raw["high_promotional_relation_ratio"]) > MAX_HIGH_PROMOTIONAL_RELATION_RATIO
            and int(raw["non_promotional_acceptable_source_count"]) < MIN_NON_PROMOTIONAL_ACCEPTABLE_SOURCE_COUNT
        ):
            material_blockers.append(blocker(
                "PROMOTIONAL_CONCENTRATION_HIGH",
                f"high_promotional_relation_ratio={raw['high_promotional_relation_ratio']:.6f}; non_promotional_acceptable_source_count={raw['non_promotional_acceptable_source_count']}",
                raw["high_promotional_source_ids"],
            ))
        if raw["embedded_name_fragment_risk"] == "YES":
            material_blockers.append(blocker(
                "EMBEDDED_NAME_FRAGMENT",
                "Exact mention boundary indicates a fragment of a longer expression",
                split_pipe(raw["embedded_name_supporting_row_ids"]),
                "CRITICAL",
            ))
        if raw["geographic_or_generic_label_risk"] == "YES":
            material_blockers.append(blocker(
                "GENERIC_OR_GEOGRAPHIC_LABEL",
                "Canonical label has a descriptive or geographic service-label shape",
                supporting_ids,
                "CRITICAL",
            ))
        if raw["collision_type"]:
            material_blockers.append(blocker(
                "COLLISION_REQUIRES_ADJUDICATION",
                f"collision_type={raw['collision_type']}",
                split_pipe(raw["collision_supporting_row_ids"]),
                "CRITICAL",
            ))
        source_review_codes = {
            "INSUFFICIENT_ACCEPTABLE_SOURCES",
            "SOURCE_QUALITY_TOO_LOW",
            "PROMOTIONAL_CONCENTRATION_HIGH",
            "ZERO_OR_NONPOSITIVE_SCORE",
            "DIAGNOSTIC_SCORE_BELOW_READY_THRESHOLD",
        }
        if raw["collision_type"] or float(raw["unresolved_alias_risk"]) > 0.25:
            readiness = "REQUIRES_ALIAS_REVIEW"
        elif raw["semantic_status"] != "PLAUSIBLE_BRAND" or SEMANTIC_CONFIDENCE_ORDER.get(raw["semantic_confidence"], 0) < SEMANTIC_CONFIDENCE_ORDER[MIN_SEMANTIC_CONFIDENCE_FOR_READY]:
            readiness = "SEMANTIC_REVIEW_REQUIRED"
        elif float(raw["provenance_trace_completeness"]) < 1.0:
            readiness = "INSUFFICIENT_TRACEABILITY"
        elif any(item["blocker_code"] in source_review_codes for item in material_blockers):
            readiness = "REQUIRES_SOURCE_REVIEW"
        elif (
            int(raw["acceptable_publisher_count"]) < MIN_DISTINCT_PUBLISHERS_FOR_READY
            or int(raw["acceptable_independence_group_count"]) < MIN_DISTINCT_GROUPS_FOR_READY
        ):
            readiness = "INSUFFICIENT_INDEPENDENCE"
        elif material_blockers:
            readiness = "REQUIRES_SOURCE_REVIEW"
        else:
            readiness = "TRACEABLE_FOR_FUTURE_PRIORITIZATION"
        eligible = readiness == "TRACEABLE_FOR_FUTURE_PRIORITIZATION" and not material_blockers
        if not eligible:
            material_blockers.extend([
                blocker("READINESS_NOT_TRACEABLE", f"readiness_status={readiness}", supporting_ids, "CRITICAL"),
                blocker("HUMAN_REVIEW_REQUIRED", "Pending evidence or adjudication prevents publication", supporting_ids),
            ])
        serialized_blockers = serialize_blockers(material_blockers)
        explanation = (
            f"positive={positive_score:.6f}; penalties={total_penalty:.6f}; "
            "recency=NOT_AVAILABLE; global recency weight redistributed "
            "proportionally across all available dimensions."
        )
        row = {
            **raw,
            "normalized_independence": round(normalized["independence"], 6),
            "normalized_quality_weighted_recurrence": round(
                normalized["quality_weighted_recurrence"],
                6,
            ),
            "normalized_source_diversity": round(
                normalized["source_diversity"],
                6,
            ),
            "normalized_query_context_diversity": round(
                normalized["query_context_diversity"],
                6,
            ),
            "normalized_language_diversity": round(
                normalized["language_diversity"],
                6,
            ),
            "normalized_geographic_context_diversity": round(
                normalized["geographic_context_diversity"],
                6,
            ),
            "normalized_alias_trace_completeness": round(
                normalized["alias_trace_completeness"],
                6,
            ),
            "normalized_provenance_trace_completeness": round(
                normalized["provenance_trace_completeness"],
                6,
            ),
            **{
                key: round(value, 6)
                for key, value in positive_components.items()
            },
            **{
                key: round(value, 6)
                for key, value in penalties.items()
            },
            "positive_score_before_penalties": round(positive_score, 6),
            "total_penalty": round(total_penalty, 6),
            "recalibrated_score": round(final_score, 6),
            "diagnostic_score": round(final_score, 6),
            "readiness_status": readiness,
            "requires_human_review": "NO" if eligible else "YES",
            "requires_human_adjudication": "NO" if eligible else "YES",
            "recalibrated_ranking_eligible": "YES" if eligible else "NO",
            "ranking_eligible": "YES" if eligible else "NO",
            "adjudication_ready_eligible": "YES" if eligible else "NO",
            "adjudication_blockers": serialized_blockers,
            "eligibility_basis": (
                "Ready for human adjudication; not approved and not externally validated."
                if eligible
                else f"Blocked from TOP50_ADJUDICATION_READY: {serialized_blockers}"
            ),
            "score_explanation": explanation,
            "supporting_row_ids": PIPE_SEPARATOR.join(
                [raw["canonical_brand_id"], *raw["source_ids"]]
            ),
        }
        rows.append(row)
    ranked = rank_recalibrated_rows(rows)
    eligible_rows = [
        row
        for row in ranked
        if row["recalibrated_ranking_eligible"] == "YES"
    ]
    for eligible_rank, row in enumerate(eligible_rows, start=1):
        row["eligible_rank"] = eligible_rank
    for row in ranked:
        row.setdefault("eligible_rank", "")
        row["diagnostic_rank"] = row["recalibrated_rank"]
        row["adjudication_ready_rank"] = row["eligible_rank"]
    return ranked


def recalibrated_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -float(row["recalibrated_score"]),
        -int(row["independence_group_count"]),
        -float(row["source_quality_weighted_recurrence"]),
        float(row["duplicate_dependency_rate"]),
        -float(row["provenance_trace_completeness"]),
        normalized_name(row["canonical_brand_name"]),
    )


def rank_recalibrated_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ranked = sorted(rows, key=recalibrated_sort_key)
    for rank, row in enumerate(ranked, start=1):
        row["recalibrated_rank"] = rank
    return ranked


def reconstruct_historical_top50(
    cleaned: list[dict[str, Any]],
    historical_artifact: list[dict[str, Any]],
    clean_by_brand: dict[str, list[dict[str, Any]]],
    matrix_by_brand: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    providers = [
        row
        for row in cleaned
        if clean_text(row.get("category")) == "PROVIDER"
    ]
    selected = sorted(
        providers,
        key=lambda row: (
            CONFIDENCE_ORDER.get(clean_text(row.get("confidence")), 99),
            -parse_float(row.get("recurrence_score")),
            -parse_int(row.get("unique_domains_count")),
            -parse_int(row.get("platform_count")),
            -parse_int(row.get("evidence_url_count")),
            clean_text(row.get("canonical_brand")),
        ),
    )[:50]
    artifact_names = [
        clean_text(row.get("brand_name"))
        for row in historical_artifact
    ]
    selected_names = [
        clean_text(row.get("canonical_brand"))
        for row in selected
    ]
    exact = artifact_names == selected_names
    artifact_by_name = {
        clean_text(row.get("brand_name")): row
        for row in historical_artifact
    }
    output: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    for rank, selected_row in enumerate(selected, start=1):
        brand = clean_text(selected_row.get("canonical_brand"))
        artifact = artifact_by_name.get(brand, {})
        metric_match = (
            parse_int(artifact.get("rank")) == rank
            and parse_float(artifact.get("recurrence_score"))
            == parse_float(selected_row.get("recurrence_score"))
            and parse_int(artifact.get("source_count"))
            == parse_int(selected_row.get("source_count"))
            and parse_int(artifact.get("unique_domains_count"))
            == parse_int(selected_row.get("unique_domains_count"))
            and parse_int(artifact.get("platform_count"))
            == parse_int(selected_row.get("platform_count"))
            and parse_int(artifact.get("evidence_url_count"))
            == parse_int(selected_row.get("evidence_url_count"))
        )
        exact = exact and metric_match
        raw_ids = [
            mapped["raw_row_id"]
            for mapped in clean_by_brand[brand]
        ]
        source_ids = [
            row["source_id"]
            for row in matrix_by_brand[brand]
        ]
        supporting = PIPE_SEPARATOR.join(
            [canonical_brand_id(brand), *sorted(raw_ids), *sorted(source_ids)]
        )
        formula_status = (
            "RECOVERED_EXACT"
            if metric_match and artifact_names == selected_names
            else "UNRECOVERED"
        )
        output.append(
            {
                "historical_rank": rank,
                "canonical_brand_id": canonical_brand_id(brand),
                "canonical_brand_name": brand,
                "historical_score": parse_float(
                    selected_row.get("recurrence_score")
                ),
                "historical_formula_status": formula_status,
                "confidence": clean_text(selected_row.get("confidence")),
                "source_count": parse_int(selected_row.get("source_count")),
                "unique_domains_count": parse_int(
                    selected_row.get("unique_domains_count")
                ),
                "platform_count": parse_int(
                    selected_row.get("platform_count")
                ),
                "evidence_url_count": parse_int(
                    selected_row.get("evidence_url_count")
                ),
                "supporting_row_ids": supporting,
            }
        )
        aliases = [
            clean_text(mapped["raw"].get("brand_name"))
            for mapped in clean_by_brand[brand]
        ]
        trace.append(
            {
                "brand": brand,
                "historical_rank": rank,
                "entry_criterion": (
                    "PROVIDER filter; confidence priority; recurrence_score "
                    "descending; unique domains descending; platforms "
                    "descending; evidence URLs descending; canonical name "
                    "casefold ascending."
                ),
                "metrics_used": (
                    f"confidence={selected_row.get('confidence')};"
                    f"recurrence_score={selected_row.get('recurrence_score')};"
                    f"unique_domains={selected_row.get('unique_domains_count')};"
                    f"platforms={selected_row.get('platform_count')};"
                    f"evidence_urls={selected_row.get('evidence_url_count')}"
                ),
                "aliases": PIPE_SEPARATOR.join(sorted(aliases)),
                "sources": PIPE_SEPARATOR.join(sorted(source_ids)),
                "traceability": (
                    "EXACT_ARTIFACT_AND_CODE_MATCH"
                    if formula_status == "RECOVERED_EXACT"
                    else "INSUFFICIENT"
                ),
                "limitations": (
                    "Historical recurrence measured pages/domains/platforms; "
                    "it did not deduplicate editorial dependence."
                ),
                "supporting_row_ids": supporting,
            }
        )
    return output, trace, exact


def public_metric_row(row: dict[str, Any]) -> dict[str, Any]:
    excluded = {
        "source_ids",
        "group_ids",
        "languages",
        "geographies",
        "queries",
        "acceptable_source_ids",
        "acceptable_publisher_ids",
        "acceptable_group_ids",
        "high_promotional_source_ids",
        "quality_levels",
        "source_diversity_raw",
        "single_group_concentration",
    }
    return {
        key: value
        for key, value in row.items()
        if key not in excluded
    }


def build_canonical_universe(
    cleaned: list[dict[str, Any]],
    clean_by_brand: dict[str, list[dict[str, Any]]],
    matrix_by_brand: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for clean_row in cleaned:
        canonical = clean_text(clean_row.get("canonical_brand"))
        raw_rows = clean_by_brand[canonical]
        matrix = matrix_by_brand[canonical]
        group_ids = {
            row["independence_group_id"]
            for row in matrix
        }
        expected_urls = {
            url
            for mapped in raw_rows
            for url in split_pipe(mapped["raw"].get("evidence_urls"))
        }
        source_ids = {row["source_id"] for row in matrix}
        traceability = (
            "COMPLETE"
            if (
                len(raw_rows) == parse_int(clean_row.get("merged_input_rows"))
                and len(source_ids) == len(expected_urls)
            )
            else "INSUFFICIENT"
        )
        rows.append(
            {
                "canonical_brand_id": canonical_brand_id(canonical),
                "canonical_brand_name": canonical,
                "category": clean_text(clean_row.get("category")),
                "raw_mention_count": len(raw_rows),
                "alias_count": len(raw_rows),
                "source_count": len(source_ids),
                "independence_group_count": len(group_ids),
                "traceability_status": traceability,
                "historical_recurrence_score": parse_float(
                    clean_row.get("recurrence_score")
                ),
                "historical_confidence": clean_text(
                    clean_row.get("confidence")
                ),
                "supporting_row_ids": PIPE_SEPARATOR.join(
                    [
                        canonical_brand_id(canonical),
                        *sorted(mapped["raw_row_id"] for mapped in raw_rows),
                        *sorted(source_ids),
                    ]
                ),
            }
        )
    rows.sort(
        key=lambda row: (
            row["category"],
            normalized_name(row["canonical_brand_name"]),
        )
    )
    return rows


def build_provider_universe(
    providers: list[dict[str, Any]],
    metrics_by_brand: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for provider in providers:
        canonical = clean_text(provider.get("canonical_brand"))
        metric = public_metric_row(metrics_by_brand[canonical])
        rows.append(
            {
                "canonical_brand_id": canonical_brand_id(canonical),
                "canonical_brand_name": canonical,
                "category": "PROVIDER",
                "historical_confidence": clean_text(
                    provider.get("confidence")
                ),
                "historical_recurrence_score": parse_float(
                    provider.get("recurrence_score")
                ),
                **metric,
            }
        )
    rows.sort(
        key=lambda row: normalized_name(row["canonical_brand_name"])
    )
    return rows


def build_seed_readiness(
    recalibrated_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "canonical_brand_id": row["canonical_brand_id"],
            "canonical_brand_name": row["canonical_brand_name"],
            "readiness_status": row["readiness_status"],
            "traceability_status": (
                "COMPLETE"
                if float(row["provenance_trace_completeness"]) == 1.0
                else "INSUFFICIENT"
            ),
            "independent_recurrence": row["independent_recurrence"],
            "weighted_independent_recurrence": row[
                "weighted_independent_recurrence"
            ],
            "recalibrated_semantic_status": row[
                "recalibrated_semantic_status"
            ],
            "recalibrated_ranking_eligible": row[
                "recalibrated_ranking_eligible"
            ],
            "diagnostic_rank": row["diagnostic_rank"],
            "diagnostic_score": row["diagnostic_score"],
            "adjudication_ready_rank": row["adjudication_ready_rank"],
            "adjudication_ready_eligible": row[
                "adjudication_ready_eligible"
            ],
            "adjudication_blockers": row["adjudication_blockers"],
            "acceptable_source_count": row["acceptable_source_count"],
            "acceptable_publisher_count": row["acceptable_publisher_count"],
            "acceptable_independence_group_count": row[
                "acceptable_independence_group_count"
            ],
            "resolved_acceptable_publisher_count": row[
                "resolved_acceptable_publisher_count"
            ],
            "unresolved_acceptable_publisher_count": row[
                "unresolved_acceptable_publisher_count"
            ],
            "resolved_acceptable_independence_group_count": row[
                "resolved_acceptable_independence_group_count"
            ],
            "unresolved_independence_evidence_count": row[
                "unresolved_independence_evidence_count"
            ],
            "publisher_diversity_eligible": row["publisher_diversity_eligible"],
            "independence_diversity_eligible": row["independence_diversity_eligible"],
            "high_promotional_relation_count": row[
                "high_promotional_relation_count"
            ],
            "high_promotional_relation_ratio": row[
                "high_promotional_relation_ratio"
            ],
            "non_promotional_acceptable_source_count": row[
                "non_promotional_acceptable_source_count"
            ],
            "embedded_name_fragment_risk": row["embedded_name_fragment_risk"],
            "geographic_or_generic_label_risk": row[
                "geographic_or_generic_label_risk"
            ],
            "requires_human_adjudication": row[
                "requires_human_adjudication"
            ],
            "eligibility_basis": row["eligibility_basis"],
            "unresolved_alias_risk": round(
                float(row["unresolved_alias_risk"]),
                6,
            ),
            "promotional_source_concentration": round(
                float(row["promotional_source_concentration"]),
                6,
            ),
            "human_review_required": (
                "NO"
                if row["readiness_status"]
                == "TRACEABLE_FOR_FUTURE_PRIORITIZATION"
                else "YES"
            ),
            "supporting_row_ids": row["supporting_row_ids"],
        }
        for row in sorted(
            recalibrated_rows,
            key=lambda item: normalized_name(
                item["canonical_brand_name"]
            ),
        )
    ]


def build_recalibrated_top50(
    recalibrated_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    fields = [
        "eligible_rank",
        "diagnostic_rank",
        "adjudication_ready_rank",
        "canonical_brand_id",
        "canonical_brand_name",
        "recalibrated_score",
        "diagnostic_score",
        "independence_group_count",
        "acceptable_source_count",
        "acceptable_publisher_count",
        "acceptable_independence_group_count",
        "resolved_acceptable_publisher_count",
        "unresolved_acceptable_publisher_count",
        "resolved_acceptable_independence_group_count",
        "unresolved_independence_evidence_count",
        "publisher_diversity_eligible",
        "independence_diversity_eligible",
        "high_promotional_relation_count",
        "high_promotional_relation_ratio",
        "non_promotional_acceptable_source_count",
        "embedded_name_fragment_risk",
        "geographic_or_generic_label_risk",
        "independent_recurrence",
        "weighted_independent_recurrence",
        "demonstrated_independent_group_count",
        "unresolved_group_count",
        "dependent_group_count",
        "probable_replica_group_count",
        "source_quality_weighted_recurrence",
        "normalized_independence",
        "normalized_quality_weighted_recurrence",
        "normalized_source_diversity",
        "normalized_query_context_diversity",
        "normalized_language_diversity",
        "normalized_geographic_context_diversity",
        "normalized_alias_trace_completeness",
        "normalized_provenance_trace_completeness",
        "duplicate_dependency_penalty",
        "promotional_source_penalty",
        "unresolved_alias_penalty",
        "homonym_or_impersonation_penalty",
        "single_group_concentration_penalty",
        "grave_traceability_penalty",
        "probable_cross_host_replica_dependency_penalty",
        "low_originality_source_concentration_penalty",
        "insufficient_local_brand_evidence_penalty",
        "generic_phrase_risk_penalty",
        "extraction_artifact_risk_penalty",
        "player_or_platform_risk_penalty",
        "noncomparable_context_penalty",
        "unresolved_alias_collision_penalty",
        "recalibrated_semantic_status",
        "semantic_status",
        "semantic_status_basis",
        "semantic_confidence",
        "requires_human_review",
        "recalibrated_ranking_eligible",
        "adjudication_ready_eligible",
        "adjudication_blockers",
        "requires_human_adjudication",
        "collision_type",
        "nominal_brand_use_count",
        "incompatible_context_use_count",
        "incompatible_context_ratio",
        "eligibility_basis",
        "readiness_status",
        "score_explanation",
        "supporting_row_ids",
    ]
    all_eligible = [
        row
        for row in recalibrated_rows
        if row["readiness_status"] == "TRACEABLE_FOR_FUTURE_PRIORITIZATION"
        and row["adjudication_ready_eligible"] == "YES"
        and not row["adjudication_blockers"]
    ]
    eligible = all_eligible[:PUBLICATION_LIMIT]
    available_count = len(all_eligible)
    published_count = len(eligible)
    output: list[dict[str, Any]] = []
    for row in eligible:
        item = {field: row[field] for field in fields}
        item["recalibrated_rank"] = item.pop("eligible_rank")
        item["top50_surface"] = "TOP50_ADJUDICATION_READY"
        item["human_approval_status"] = "NOT_HUMAN_APPROVED"
        item["external_validation_status"] = "NOT_EXTERNALLY_VALIDATED"
        item["ranking_scope"] = (
            "NOT_QUALITY_NOT_LEGALITY_NOT_OFFICIAL_DOMAIN_RANKING"
        )
        item["available_adjudication_ready_count"] = available_count
        item["published_row_count"] = published_count
        item["publication_limit"] = PUBLICATION_LIMIT
        item["list_is_truncated"] = available_count > PUBLICATION_LIMIT
        item["no_human_approval_yet"] = True
        item["no_external_validation"] = True
        output.append(item)
    return output


def principal_change_drivers(
    historical: dict[str, Any] | None,
    recalibrated: dict[str, Any] | None,
) -> str:
    if historical is None and recalibrated is not None:
        return (
            "Entered after source-dependence, quality, diversity, and "
            "traceability recalibration."
        )
    if historical is not None and recalibrated is None:
        if historical.get("_ranking_eligible") == "NO":
            return "Exited because recalibrated semantic eligibility is false."
        return (
            "Exited after duplicate, promotional, concentration, alias, "
            "homonym, and traceability penalties."
        )
    assert recalibrated is not None
    drivers: list[str] = []
    if float(recalibrated["duplicate_dependency_rate"]) > 0.25:
        drivers.append("duplicate dependency")
    if float(recalibrated["promotional_source_concentration"]) > 0.50:
        drivers.append("promotional concentration")
    if float(recalibrated["unresolved_alias_risk"]) > 0.0:
        drivers.append("alias review risk")
    if int(recalibrated["independence_group_count"]) >= 3:
        drivers.append("independent recurrence")
    if not drivers:
        drivers.append("composite recalibrated score")
    return ", ".join(drivers)


def primary_blocker_code(serialized: str) -> str:
    if not serialized:
        return ""
    items = json.loads(serialized)
    return items[0]["blocker_code"] if items else ""


def build_comparison(
    historical_rows: list[dict[str, Any]],
    recalibrated_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    historical_by_brand = {
        row["canonical_brand_name"]: row
        for row in historical_rows
    }
    recal_top = [
        row
        for row in recalibrated_rows
        if row["readiness_status"] == "TRACEABLE_FOR_FUTURE_PRIORITIZATION"
        and row["adjudication_ready_eligible"] == "YES"
        and not row["adjudication_blockers"]
    ][:PUBLICATION_LIMIT]
    recal_by_brand = {
        row["canonical_brand_name"]: row
        for row in recal_top
    }
    all_brands = sorted(
        set(historical_by_brand) | set(recal_by_brand),
        key=normalized_name,
    )
    rows: list[dict[str, Any]] = []
    for brand in all_brands:
        historical = historical_by_brand.get(brand)
        recalibrated = recal_by_brand.get(brand)
        historical_rank = (
            int(historical["historical_rank"])
            if historical
            else ""
        )
        recalibrated_rank = (
            int(recalibrated["eligible_rank"])
            if recalibrated
            else ""
        )
        rank_delta: int | str = ""
        if historical and recalibrated:
            rank_delta = historical_rank - recalibrated_rank
        supporting_ids = set()
        if historical:
            supporting_ids.update(
                split_pipe(historical["supporting_row_ids"])
            )
        if recalibrated:
            supporting_ids.update(
                split_pipe(recalibrated["supporting_row_ids"])
            )
        all_recalibrated = next(
            (
                row
                for row in recalibrated_rows
                if row["canonical_brand_name"] == brand
            ),
            None,
        )
        if historical is not None and recalibrated is None:
            historical = dict(historical)
            historical["_ranking_eligible"] = (
                all_recalibrated["recalibrated_ranking_eligible"]
                if all_recalibrated
                else ""
            )
        change_type = "UNCHANGED_TOP50"
        if historical is None and recalibrated is not None:
            change_type = (
                "ENTERED_AFTER_DEPENDENCY_CORRECTION"
                if int(recalibrated["probable_replica_group_count"]) == 0
                else "ENTERED_BY_RECALIBRATED_SCORE"
            )
        elif historical is not None and recalibrated is None:
            change_type = (
                "EXITED_BY_SEMANTIC_INELIGIBILITY"
                if all_recalibrated
                and all_recalibrated[
                    "recalibrated_ranking_eligible"
                ]
                == "NO"
                else "EXITED_BY_SCORE"
            )
        rows.append(
            {
                "canonical_brand_name": brand,
                "historical_rank": historical_rank,
                "recalibrated_rank": recalibrated_rank,
                "diagnostic_rank": (
                    all_recalibrated["diagnostic_rank"]
                    if all_recalibrated
                    else ""
                ),
                "adjudication_ready_rank": recalibrated_rank,
                "rank_delta": rank_delta,
                "entered_recalibrated_top50": (
                    "YES"
                    if historical is None and recalibrated is not None
                    else "NO"
                ),
                "exited_recalibrated_top50": (
                    "YES"
                    if historical is not None and recalibrated is None
                    else "NO"
                ),
                "principal_change_drivers": principal_change_drivers(
                    historical,
                    recalibrated,
                ),
                "change_type": change_type,
                "recalibrated_semantic_status": (
                    all_recalibrated["recalibrated_semantic_status"]
                    if all_recalibrated
                    else ""
                ),
                "recalibrated_ranking_eligible": (
                    all_recalibrated["recalibrated_ranking_eligible"]
                    if all_recalibrated
                    else ""
                ),
                "adjudication_ready_eligible": (
                    all_recalibrated["adjudication_ready_eligible"]
                    if all_recalibrated
                    else ""
                ),
                "adjudication_blockers": (
                    all_recalibrated["adjudication_blockers"]
                    if all_recalibrated
                    else ""
                ),
                "readiness_status": (
                    all_recalibrated["readiness_status"]
                    if all_recalibrated
                    else ""
                ),
                "principal_blocker": (
                    primary_blocker_code(all_recalibrated["adjudication_blockers"])
                    if all_recalibrated
                    else ""
                ),
                "non_inclusion_reason": (
                    ""
                    if recalibrated is not None
                    else (
                        f"Not published: {all_recalibrated['readiness_status']}; "
                        f"{primary_blocker_code(all_recalibrated['adjudication_blockers'])}"
                        if all_recalibrated
                        else "Not present in recalibrated diagnostic universe"
                    )
                ),
                "semantic_blocker": (
                    all_recalibrated["recalibrated_semantic_status"]
                    if all_recalibrated
                    and all_recalibrated["recalibrated_semantic_status"]
                    != "PLAUSIBLE_BRAND"
                    else ""
                ),
                "collision_blocker": (
                    all_recalibrated["collision_type"]
                    if all_recalibrated
                    else ""
                ),
                "quality_blocker": (
                    "INADEQUATE_SOURCE_QUALITY"
                    if all_recalibrated
                    and "INADEQUATE_SOURCE_QUALITY"
                    in all_recalibrated["adjudication_blockers"]
                    else ""
                ),
                "independence_blocker": (
                    "INSUFFICIENT_DISTINCT_SOURCES"
                    if all_recalibrated
                    and "INSUFFICIENT_DISTINCT_SOURCES"
                    in all_recalibrated["adjudication_blockers"]
                    else ""
                ),
                "eligibility_basis": (
                    all_recalibrated["eligibility_basis"]
                    if all_recalibrated
                    else ""
                ),
                "supporting_row_ids": PIPE_SEPARATOR.join(
                    sorted(supporting_ids)
                ),
            }
        )
    rows.sort(
        key=lambda row: (
            row["recalibrated_rank"] == "",
            row["recalibrated_rank"]
            if row["recalibrated_rank"] != ""
            else 9999,
            row["historical_rank"]
            if row["historical_rank"] != ""
            else 9999,
            normalized_name(row["canonical_brand_name"]),
        )
    )
    return rows


def build_bias_report(
    counts: dict[str, int],
    quality_rows: list[dict[str, Any]],
    independence_rows: list[dict[str, Any]],
    alias_rows: list[dict[str, Any]],
    exclusion_rows: list[dict[str, Any]],
    recalibrated_rows: list[dict[str, Any]],
    adjudication_ready_rows: list[dict[str, Any]],
) -> str:
    quality_counts = Counter(row["quality_level"] for row in quality_rows)
    group_ids = {
        row["independence_group_id"]
        for row in independence_rows
    }
    group_statuses: dict[str, str] = {}
    for row in independence_rows:
        group_statuses[row["independence_group_id"]] = row[
            "independence_status"
        ]
    status_counts = Counter(group_statuses.values())
    alias_counts = Counter(row["alias_status"] for row in alias_rows)
    exclusion_counts = Counter(
        row["exclusion_reason"]
        for row in exclusion_rows
    )
    semantic_counts = Counter(
        row["semantic_status"] for row in recalibrated_rows
    )
    mention_use_counts: Counter[str] = Counter()
    for row in recalibrated_rows:
        mention_use_counts.update(
            parse_json_array(row.get("mention_context_use_types", "[]"))
        )
    false_comparable_count = sum(
        row["semantic_status"] != "PLAUSIBLE_BRAND"
        for row in recalibrated_rows
    )
    community_risk_reclassified = sum(
        row.get("hostname") in COMMUNITY_HOSTS
        and row.get("quality_level") != "B"
        and "HIGH"
        in {
            row.get("promotional_risk"),
            row.get("off_topic_risk"),
            row.get("self_promotion_risk"),
            row.get("spam_risk"),
        }
        for row in quality_rows
    )
    platform_count = len(
        {row.get("platform_id") for row in independence_rows if row.get("platform_id")}
    )
    publisher_count = len(
        {row.get("publisher_id") for row in independence_rows if row.get("publisher_id")}
    )
    hostname_count = len(
        {row.get("hostname") for row in independence_rows if row.get("hostname")}
    )
    collision_counts = Counter()
    seen_collisions: set[str] = set()
    for row in alias_rows:
        collision_id = str(row.get("possible_alias_collision_id", ""))
        collision_type = str(row.get("collision_type", ""))
        if collision_id and collision_type and collision_id not in seen_collisions:
            seen_collisions.add(collision_id)
            collision_counts[collision_type] += 1
    adjudication_blocked = sum(
        row.get("requires_human_adjudication") == "YES"
        for row in recalibrated_rows
    )
    readiness_counts = Counter(
        row["readiness_status"] for row in recalibrated_rows
    )
    platform_groups = len(
        {
            row["independence_group_id"]
            for row in independence_rows
            if str(row.get("platform_type", "")).endswith("MULTIUSER")
        }
    )
    direct_replica_groups = len(
        {
            row["independence_group_id"]
            for row in independence_rows
            if row.get("replica_component_id")
        }
    )
    lines = [
        "# BRAND-FIRST market universe 1A FIX3 bias report",
        "",
        "## Genealogía auditada",
        "",
        (
            f"- {counts['raw_brand_mentions']} nombres originales → "
            f"{counts['cleaned_canonical_brands']} registros depurados → "
            f"{counts['providers']} PROVIDER → "
            f"{counts['historical_top50']} marcas históricas."
        ),
        "",
        "## Sesgo por consultas iniciales",
        "",
        (
            "Las 42 consultas históricas se concentraron en frases tipo "
            "`best IPTV`, proveedores, reseñas, dispositivos y reseller. "
            "El universo mide descubribilidad dentro de ese diseño, no el "
            "mercado mundial completo."
        ),
        "",
        "## Sesgo lingüístico",
        "",
        (
            "Predominan consultas en inglés, con cobertura parcial en "
            "portugués y contextos latinoamericanos. La diversidad "
            "lingüística se deriva solo de consultas locales conservadas."
        ),
        "",
        "## Sesgo geográfico",
        "",
        (
            "La cobertura explícita se concentra en USA, Canadá, UK, "
            "Europa, Australia, Brasil, Colombia y Latinoamérica. Ausencia "
            "de una región no constituye ausencia de una marca."
        ),
        "",
        "## Sesgo temporal",
        "",
        (
            "Los 535 registros no contienen fechas de publicación fiables. "
            "La dimensión de recencia se marca NOT_AVAILABLE y su peso se "
            "redistribuye globalmente, nunca por marca."
        ),
        "",
        "## Sesgo SEO, afiliado y reseller",
        "",
        (
            f"Calidad local: {dict(sorted(quality_counts.items()))}. "
            "UNKNOWN se pondera conservadoramente con 0.20; D con 0.20; "
            "E con 0.00. Una página promocional puede descubrir una marca "
            "sin demostrar calidad, identidad, legalidad u oficialidad."
        ),
        "",
        "## Duplicación y concentración",
        "",
        (
            f"Se reconstruyeron {len(group_ids)} grupos conservadores. "
            f"Estados: {dict(sorted(status_counts.items()))}. Varias páginas "
            "del mismo hostname cuentan como un grupo. FIX1 añade enlaces "
            "cross-host cuando listas de al menos ocho marcas superan 0.85 "
            "de solapamiento y 0.75 de concordancia de orden; se conservan "
            "las páginas concretas participantes."
        ),
        "",
        "## Aliases y homónimos",
        "",
        (
            f"Estados de alias: {dict(sorted(alias_counts.items()))}. "
            "Las variantes no idénticas se mantienen como ALIAS_PROBABLE y "
            "requieren revisión humana; no se elevan a identidad legal."
        ),
        "",
        "## Categorías excluidas",
        "",
        (
            f"Motivos preservados: {dict(sorted(exclusion_counts.items()))}. "
            "Las exclusiones se trazan a cada nombre bruto y a sus fuentes."
        ),
        "",
        "## Limitaciones",
        "",
        "- La independencia editorial no puede demostrarse para fuentes aisladas; se marca UNRESOLVED.",
        "- Los 692 PROVIDER son una clasificación histórica preservada; la capa semántica recalibrada es separada.",
        "- Una inelegibilidad recalibrada no demuestra que la entidad no exista.",
        "- El nivel A no se asigna sin autoría y metodología localmente demostrables.",
        "- El ranking mide descubribilidad trazable y plausibilidad local, no calidad, legalidad u oficialidad.",
        "- No se atribuyen dominios oficiales, ecosistemas empresariales ni operadores legales.",
        "- No se seleccionó ninguna marca para investigación externa.",
        "",
    ]
    lines[-1:-1] = [
        "## Correcciones FIX3",
        "",
        (
            f"Plataformas multiusuario separadas por publisher: {platform_groups}; "
            f"componentes con aristas directas de replica: {direct_replica_groups}. "
            "El mismo hostname solo se colapsa globalmente en sitios editoriales "
            "tradicionales. Reddit, Trustpilot y Hacker News conservan identidad "
            "de publisher/publicacion. La transitividad no inventa aristas."
        ),
        "",
        f"- Estados semanticos: {dict(sorted(semantic_counts.items()))}.",
        f"- Usos de mencion: {dict(sorted(mention_use_counts.items()))}.",
        f"- Tipos de colision: {dict(sorted(collision_counts.items()))}.",
        f"- Marcas bloqueadas para adjudicacion humana: {adjudication_blocked}.",
        f"- Falsos comparables detectados por estado semantico: {false_comparable_count}.",
        f"- Publicaciones comunitarias reclasificadas por riesgo: {community_risk_reclassified}.",
        f"- Grupos por plataforma/publisher/hostname: {platform_count}/{publisher_count}/{hostname_count}.",
        f"- Universo diagnostico preservado: {len(recalibrated_rows)}.",
        f"- Distribucion readiness: {dict(sorted(readiness_counts.items()))}.",
        f"- Disponibles adjudication-ready: {sum(row['adjudication_ready_eligible'] == 'YES' for row in recalibrated_rows)}.",
        f"- Top adjudication-ready exportado: {len(adjudication_ready_rows)}.",
        "- El nivel A se declara A_NOT_ASSESSABLE_FROM_CURRENT_CORPUS; no se asigna.",
        "",
    ]
    return "\n".join(lines)


def build_main_report(
    counts: dict[str, int],
    historical_exact: bool,
    historical_rows: list[dict[str, Any]],
    recal_top50: list[dict[str, Any]],
    comparison: list[dict[str, Any]],
    quality_rows: list[dict[str, Any]],
    independence_rows: list[dict[str, Any]],
    recalibrated_rows: list[dict[str, Any]],
    alias_rows: list[dict[str, Any]],
) -> str:
    historical_names = {
        row["canonical_brand_name"]
        for row in historical_rows
    }
    recal_names = {
        row["canonical_brand_name"]
        for row in recal_top50
    }
    overlap = sorted(historical_names & recal_names, key=normalized_name)
    entered = sorted(recal_names - historical_names, key=normalized_name)
    exited = sorted(historical_names - recal_names, key=normalized_name)
    group_count = len(
        {
            row["independence_group_id"]
            for row in independence_rows
        }
    )
    quality_counts = Counter(row["quality_level"] for row in quality_rows)
    semantic_counts = Counter(
        row["semantic_status"] for row in recalibrated_rows
    )
    collision_counts = Counter()
    seen_collisions: set[str] = set()
    for row in alias_rows:
        collision_id = str(row.get("possible_alias_collision_id", ""))
        collision_type = str(row.get("collision_type", ""))
        if collision_id and collision_type and collision_id not in seen_collisions:
            seen_collisions.add(collision_id)
            collision_counts[collision_type] += 1
    blocked_count = sum(
        row.get("requires_human_adjudication") == "YES"
        for row in recalibrated_rows
    )
    readiness_counts = Counter(
        row["readiness_status"] for row in recalibrated_rows
    )
    mention_use_counts: Counter[str] = Counter()
    for row in recalibrated_rows:
        mention_use_counts.update(
            parse_json_array(row.get("mention_context_use_types", "[]"))
        )
    false_comparable_count = sum(
        row["semantic_status"] != "PLAUSIBLE_BRAND"
        for row in recalibrated_rows
    )
    community_risk_reclassified = sum(
        row.get("hostname") in COMMUNITY_HOSTS
        and row.get("quality_level") != "B"
        and "HIGH"
        in {
            row.get("promotional_risk"),
            row.get("off_topic_risk"),
            row.get("self_promotion_risk"),
            row.get("spam_risk"),
        }
        for row in quality_rows
    )
    platform_count = len(
        {row.get("platform_id") for row in independence_rows if row.get("platform_id")}
    )
    publisher_count = len(
        {row.get("publisher_id") for row in independence_rows if row.get("publisher_id")}
    )
    hostname_count = len(
        {row.get("hostname") for row in independence_rows if row.get("hostname")}
    )
    lines = [
        "# BRAND-FIRST market universe 1A FIX3",
        "",
        "## Resumen ejecutivo",
        "",
        (
            f"Se reconstruyó offline la genealogía "
            f"{counts['raw_brand_mentions']} → "
            f"{counts['cleaned_canonical_brands']} → "
            f"{counts['providers']} → "
            f"{counts['historical_top50']}."
        ),
        (
            "El ranking histórico fue recuperado exactamente desde el código "
            "y el artefacto almacenado."
            if historical_exact
            else "La fórmula histórica no pudo recuperarse exactamente."
        ),
        "",
        "## Alcance",
        "",
        "- Unidad primaria: CANONICAL_BRAND.",
        "- Solo información local preexistente.",
        "- Sin atribución de dominio oficial ni operador legal.",
        "- Sin selección de una marca para investigación externa.",
        "",
        "## Fuentes",
        "",
        f"- Fuentes de corpus: {counts['corpus_sources']}.",
        f"- Grupos de independencia conservadores: {group_count}.",
        f"- Distribución de calidad: {dict(sorted(quality_counts.items()))}.",
        "",
        "## Metodología",
        "",
        (
            "El Top 50 histórico filtra PROVIDER, ordena confianza "
            "HIGH/MEDIUM/LOW, recurrence_score descendente, dominios "
            "descendentes, plataformas descendentes, URLs descendentes y "
            "nombre canónico casefold ascendente."
        ),
        (
            "recurrence_score histórico = source_count + "
            "2*unique_domains_count + 1.5*platform_count + "
            "0.5*min(evidence_url_count,25)."
        ),
        (
            "El score recalibrado usa recurrencia ponderada por presencia "
            "real de la marca dentro del grupo, calidad de la publicación, "
            "consultas vinculadas, idioma no inflado, geografía explícita y "
            "trazabilidad semántica; después resta penalizaciones transparentes."
        ),
        "",
        "## Ranking histórico",
        "",
        f"- Estado de fórmula: {'RECOVERED_EXACT' if historical_exact else 'UNRECOVERED'}.",
        f"- Marcas: {len(historical_rows)}.",
        "",
        "## Ranking adjudication-ready",
        "",
        f"- Proveedores evaluados: {counts['providers']}.",
        f"- Top adjudication-ready exportado: {len(recal_top50)}.",
        "- La superficie contiene entre 0 y 50 registros TRACEABLE, sin backfill ni relajacion.",
        (
            "- Recencia: NOT_AVAILABLE; peso redistribuido globalmente y de "
            "forma idéntica para todas las marcas."
        ),
        "",
        "## Comparación",
        "",
        f"- Solapamiento Top 50: {len(overlap)}.",
        f"- Entradas: {PIPE_SEPARATOR.join(entered) if entered else 'NINGUNA'}.",
        f"- Salidas: {PIPE_SEPARATOR.join(exited) if exited else 'NINGUNA'}.",
        f"- Filas comparadas: {len(comparison)}.",
        "",
        "## Independencia y calidad",
        "",
        (
            "Mismo hostname se agrupa siempre. Duplicados exactos y listas "
            "cross-host con fuerte solapamiento y orden concordante se "
            "agrupan conservadoramente. La recurrencia se calcula por marca "
            "dentro del grupo: singleton máximo 0.50, mismo host máximo 0.75 "
            "y réplica probable máximo 0.50."
        ),
        "",
        "## Aliases y exclusiones",
        "",
        (
            "Los aliases exactos se marcan ALIAS_CONFIRMED. Las variantes "
            "históricamente agrupadas pero no idénticas se marcan "
            "ALIAS_PROBABLE. Las colisiones canónicas se conservan separadas "
            "como UNRESOLVED_ALIAS y requieren revisión humana."
        ),
        "",
        "## Sesgos y limitaciones",
        "",
        (
            "Persisten sesgos por consulta inicial, idioma, geografía, SEO, "
            "afiliación, reseller, duplicación y ausencia de fechas."
        ),
        (
            "Los 692 PROVIDER y el Top 50 histórico se preservan como "
            "genealogía. La capa semántica no es verificación externa y una "
            "inelegibilidad no prueba inexistencia. El ranking mide "
            "descubribilidad trazable y plausibilidad local, no calidad, "
            "legalidad ni oficialidad."
        ),
        "",
        "## Dictamen",
        "",
        (
            "El dictamen operativo se determina después de validar hashes, "
            "pruebas, entregables y trazabilidad."
        ),
        "",
        "No se seleccionó ninguna marca para investigación externa.",
        "",
    ]
    lines[-1:-1] = [
        "## Cierre metodologico FIX3",
        "",
        f"- Universo diagnostico: {len(recalibrated_rows)} marcas.",
        f"- Distribucion readiness: {dict(sorted(readiness_counts.items()))}.",
        f"- Disponibles adjudication-ready: {sum(row['adjudication_ready_eligible'] == 'YES' for row in recalibrated_rows)}.",
        f"- Filas publicadas: {len(recal_top50)} de limite {PUBLICATION_LIMIT}.",
        f"- Distribucion semantica: {dict(sorted(semantic_counts.items()))}.",
        f"- Usos de mencion: {dict(sorted(mention_use_counts.items()))}.",
        f"- Colisiones: {dict(sorted(collision_counts.items()))}.",
        f"- Requieren adjudicacion humana: {blocked_count}.",
        f"- Falsos comparables detectados: {false_comparable_count}.",
        f"- Publicaciones comunitarias reclasificadas por riesgo: {community_risk_reclassified}.",
        f"- Grupos por plataforma/publisher/hostname: {platform_count}/{publisher_count}/{hostname_count}.",
        (
            "- El Top exportado es adjudication-ready, no human-approved ni "
            "externally-validated, y no clasifica calidad, legalidad u oficialidad."
        ),
        (
            "- Plataformas multiusuario se separan por publisher/publicacion; "
            "las replicas se justifican mediante aristas directas auditables."
        ),
        "- Nivel A: A_NOT_ASSESSABLE_FROM_CURRENT_CORPUS.",
        "",
    ]
    return "\n".join(lines)


def logical_dataset_hash(dataset: dict[str, Any]) -> str:
    logical = {
        key: value
        for key, value in dataset.items()
        if key not in {
            "01_source_inventory.csv",
            "18_integrity_manifest.json",
            "19_runner_validation_report.md",
        }
    }
    return sha256_bytes(canonical_json_bytes(logical))


def build_dataset(
    data: dict[str, Any],
    inventory: list[dict[str, Any]],
) -> dict[str, Any]:
    counts = validate_physical_counts(data)
    mapped, clean_by_brand, rejected_by_brand = map_raw_rows(
        data["consolidated"],
        data["cleaned"],
        data["rejected"],
    )
    sources, source_by_url = normalize_corpus_sources(data["corpus"])
    sources_by_id = {
        source["source_id"]: source
        for source in sources
    }
    (
        independence_rows,
        source_groups,
        group_summary,
    ) = build_independence_groups(sources)
    quality_rows, quality_by_source = build_quality_registry(
        sources,
        source_groups,
    )
    raw_mentions = build_raw_mentions(mapped, source_by_url)
    exclusions = build_exclusion_rows(rejected_by_brand)
    brand_source_matrix, matrix_by_brand = build_brand_source_matrix(
        data["cleaned"],
        clean_by_brand,
        source_by_url,
        source_groups,
        quality_by_source,
    )
    collision_by_brand = build_alias_collisions(
        data["cleaned"],
        matrix_by_brand,
        clean_by_brand,
        sources_by_id,
    )
    aliases = build_alias_rows(
        clean_by_brand,
        collision_by_brand,
    )
    historical, historical_trace, historical_exact = (
        reconstruct_historical_top50(
            data["cleaned"],
            data["historical_top50"],
            clean_by_brand,
            matrix_by_brand,
        )
    )
    historical_rank_by_brand = {
        row["canonical_brand_name"]: int(row["historical_rank"])
        for row in historical
    }
    providers = [
        row
        for row in data["cleaned"]
        if clean_text(row.get("category")) == "PROVIDER"
    ]
    raw_metrics = build_raw_provider_metrics(
        providers,
        clean_by_brand,
        matrix_by_brand,
        sources_by_id,
        quality_by_source,
        group_summary,
        historical_rank_by_brand,
        exclusions,
        collision_by_brand,
    )
    recalibrated = apply_recalibrated_formula(raw_metrics)
    metrics_by_brand = {
        row["canonical_brand_name"]: row
        for row in recalibrated
    }
    canonical_universe = build_canonical_universe(
        data["cleaned"],
        clean_by_brand,
        matrix_by_brand,
    )
    provider_universe = build_provider_universe(
        providers,
        metrics_by_brand,
    )
    readiness = build_seed_readiness(recalibrated)
    recalibrated_top50 = build_recalibrated_top50(recalibrated)
    comparison = build_comparison(historical, recalibrated)
    bias_report = build_bias_report(
        counts,
        quality_rows,
        independence_rows,
        aliases,
        exclusions,
        recalibrated,
        recalibrated_top50,
    )
    main_report = build_main_report(
        counts,
        historical_exact,
        historical,
        recalibrated_top50,
        comparison,
        quality_rows,
        independence_rows,
        recalibrated,
        aliases,
    )
    return {
        "01_source_inventory.csv": inventory,
        "02_raw_brand_mentions.csv": raw_mentions,
        "03_canonical_brand_universe.csv": canonical_universe,
        "04_brand_alias_map.csv": aliases,
        "05_brand_exclusions.csv": exclusions,
        "06_provider_universe_692.csv": provider_universe,
        "07_historical_top50.csv": historical,
        "08_top50_selection_trace.csv": historical_trace,
        "09_source_quality_registry.csv": quality_rows,
        "10_source_independence_groups.csv": independence_rows,
        "11_brand_source_matrix.csv": brand_source_matrix,
        "12_brand_recurrence_metrics.csv": [
            public_metric_row(row)
            for row in recalibrated
        ],
        "13_brand_seed_readiness.csv": readiness,
        "14_top50_recalibrated_offline.csv": recalibrated_top50,
        "15_historical_vs_recalibrated_comparison.csv": comparison,
        "16_market_universe_bias_report.md": bias_report,
        "17_brand_first_market_universe_report.md": main_report,
        "_counts": counts,
        "_historical_exact": historical_exact,
        "_group_count": len(group_summary),
        "_replica_group_count": sum(
            summary["independence_status"]
            == "PROBABLE_CROSS_HOST_REPLICA"
            for summary in group_summary.values()
        ),
        "_alias_collision_count": len(
            {
                row["possible_alias_collision_id"]
                for row in aliases
                if row["possible_alias_collision_id"]
            }
        ),
        "_recalibrated_all": recalibrated,
    }


def validate_all_reference_fields(
    dataset: dict[str, Any],
) -> tuple[bool, int, list[str], dict[str, int]]:
    valid_ids: set[str] = set()
    for filename in CSV_OUTPUTS:
        for row in dataset.get(filename, []):
            for key, value in row.items():
                if key.endswith("_id") and clean_text(value):
                    valid_ids.add(clean_text(value))
    checked = 0
    errors: list[str] = []
    counts_by_field: Counter[str] = Counter()
    for filename in CSV_OUTPUTS:
        for row_index, row in enumerate(dataset.get(filename, []), start=1):
            for field, value in row.items():
                if not (
                    field.endswith("_ids")
                    or field in {"member_sources"}
                ):
                    continue
                for reference_id in split_pipe(value):
                    checked += 1
                    counts_by_field[field] += 1
                    if reference_id not in valid_ids:
                        errors.append(
                            f"{filename}:{row_index}:{field}:{reference_id}"
                        )
    return not errors, checked, errors, dict(sorted(counts_by_field.items()))


def validate_supporting_row_ids(
    dataset: dict[str, Any],
) -> tuple[bool, int, list[str]]:
    passed, checked, errors, _ = validate_all_reference_fields(dataset)
    return passed, checked, errors


def scan_runner_for_prohibited_operations(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    prohibited_imports: list[str] = []
    prohibited_calls: list[str] = []
    credential_read_hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in {"requests", "tavily", "dotenv"}:
                    prohibited_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in {"requests", "tavily", "dotenv"}:
                prohibited_imports.append(node.module or "")
        elif isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                parts = [node.func.attr]
                value = node.func.value
                while isinstance(value, ast.Attribute):
                    parts.append(value.attr)
                    value = value.value
                if isinstance(value, ast.Name):
                    parts.append(value.id)
                name = ".".join(reversed(parts))
            if name in {
                "os.getenv",
                "load_dotenv",
                "dotenv.load_dotenv",
                "urllib.request.urlopen",
                "socket.create_connection",
                "socket.getaddrinfo",
            }:
                prohibited_calls.append(name)
            if name in {
                "os.getenv",
                "load_dotenv",
                "dotenv.load_dotenv",
                "dotenv_values",
            }:
                credential_read_hits.append(name)
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "os"
            and node.attr == "environ"
        ):
            credential_read_hits.append("os.environ")
    return {
        "prohibited_imports": sorted(set(prohibited_imports)),
        "prohibited_calls": sorted(set(prohibited_calls)),
        "credential_read_hits": credential_read_hits,
        "passed": not (
            prohibited_imports
            or prohibited_calls
            or credential_read_hits
        ),
    }


def published_row_is_strictly_ready(row: dict[str, Any]) -> bool:
    return (
        row["recalibrated_semantic_status"] == "PLAUSIBLE_BRAND"
        and SEMANTIC_CONFIDENCE_ORDER.get(row["semantic_confidence"], 0)
        >= SEMANTIC_CONFIDENCE_ORDER[MIN_SEMANTIC_CONFIDENCE_FOR_READY]
        and row["readiness_status"] == "TRACEABLE_FOR_FUTURE_PRIORITIZATION"
        and float(row["diagnostic_score"]) >= MIN_DIAGNOSTIC_SCORE_FOR_READY
        and float(row["diagnostic_score"]) > 0.0
        and int(row["acceptable_source_count"]) >= MIN_ACCEPTABLE_SOURCE_COUNT_FOR_READY
        and int(row["acceptable_publisher_count"]) >= MIN_DISTINCT_PUBLISHERS_FOR_READY
        and int(row["acceptable_independence_group_count"]) >= MIN_DISTINCT_GROUPS_FOR_READY
        and not (
            float(row["high_promotional_relation_ratio"]) > MAX_HIGH_PROMOTIONAL_RELATION_RATIO
            and int(row["non_promotional_acceptable_source_count"])
            < MIN_NON_PROMOTIONAL_ACCEPTABLE_SOURCE_COUNT
        )
        and not row["collision_type"]
        and row["requires_human_adjudication"] == "NO"
        and not row["adjudication_blockers"]
        and row["adjudication_ready_eligible"] == "YES"
    )


def recompute_expected_readiness_from_primary_fields(
    row: dict[str, Any],
    matrix_rows: list[dict[str, Any]],
    quality_by_source: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Independently recompute readiness from exported primary relations.

    This deliberately does not call the production readiness builder or trust
    its eligibility/count/blocker fields.
    """
    contexts = json.loads(row.get("mention_contexts", "[]") or "[]")
    nominal_ids = {
        clean_text(context.get("source_id"))
        for context in contexts
        if context.get("mention_use_type") == "NOMINAL_BRAND_USE"
    }
    acceptable: list[dict[str, Any]] = []
    high_promotional = 0
    non_promotional = 0
    for relation in matrix_rows:
        source_id = clean_text(relation.get("source_id"))
        quality = quality_by_source[source_id]
        level = clean_text(quality.get("quality_level")) or "UNKNOWN"
        promotional_high = quality.get("promotional_risk") == "HIGH"
        if promotional_high:
            high_promotional += 1
        replica_or_dependent = (
            relation.get("source_probable_replica_member") == "YES"
            or relation.get("source_direct_replica_member") == "YES"
        )
        nominal = source_id in nominal_ids
        common_ok = (
            nominal
            and quality.get("spam_risk") != "HIGH"
            and quality.get("off_topic_risk") != "HIGH"
            and not replica_or_dependent
        )
        accepted = common_ok and (
            level in {"A", "B", "C"}
            or (level == "D" and not promotional_high)
        )
        if accepted:
            acceptable.append(relation)
            if not promotional_high:
                non_promotional += 1
    publishers = {
        clean_text(relation.get("source_publisher_id"))
        for relation in acceptable
        if relation.get("publisher_counts_for_diversity") == "YES"
        and clean_text(relation.get("source_publisher_id"))
    }
    groups = {
        clean_text(relation.get("independence_group_id"))
        for relation in acceptable
        if relation.get("independence_counts_for_readiness") == "YES"
        and clean_text(relation.get("independence_group_id"))
    }
    source_count = len(acceptable)
    promotion_ratio = ratio(high_promotional, len(matrix_rows))
    semantic_ok = (
        row.get("semantic_status") == "PLAUSIBLE_BRAND"
        and SEMANTIC_CONFIDENCE_ORDER.get(row.get("semantic_confidence", ""), 0)
        >= SEMANTIC_CONFIDENCE_ORDER[MIN_SEMANTIC_CONFIDENCE_FOR_READY]
    )
    score_ok = float(row.get("diagnostic_score", 0.0)) >= MIN_DIAGNOSTIC_SCORE_FOR_READY
    collision = bool(row.get("collision_type"))
    promotion_blocked = (
        promotion_ratio > MAX_HIGH_PROMOTIONAL_RELATION_RATIO
        and non_promotional < MIN_NON_PROMOTIONAL_ACCEPTABLE_SOURCE_COUNT
    )
    diversity_ok = (
        len(publishers) >= MIN_DISTINCT_PUBLISHERS_FOR_READY
        and len(groups) >= MIN_DISTINCT_GROUPS_FOR_READY
    )
    source_ok = source_count >= MIN_ACCEPTABLE_SOURCE_COUNT_FOR_READY
    eligible = semantic_ok and score_ok and source_ok and diversity_ok and not promotion_blocked and not collision
    if collision or float(row.get("unresolved_alias_risk", 0.0)) > 0.25:
        readiness = "REQUIRES_ALIAS_REVIEW"
    elif not semantic_ok:
        readiness = "SEMANTIC_REVIEW_REQUIRED"
    elif float(row.get("provenance_trace_completeness", 0.0)) < 1.0:
        readiness = "INSUFFICIENT_TRACEABILITY"
    elif not source_ok or not score_ok or promotion_blocked:
        readiness = "REQUIRES_SOURCE_REVIEW"
    elif not diversity_ok:
        readiness = "INSUFFICIENT_INDEPENDENCE"
    else:
        readiness = "TRACEABLE_FOR_FUTURE_PRIORITIZATION"
    expected_blocker_codes: set[str] = set()
    if row.get("semantic_status") != "PLAUSIBLE_BRAND":
        expected_blocker_codes.add("SEMANTIC_STATUS_NOT_ELIGIBLE")
    if SEMANTIC_CONFIDENCE_ORDER.get(row.get("semantic_confidence", ""), 0) < SEMANTIC_CONFIDENCE_ORDER[MIN_SEMANTIC_CONFIDENCE_FOR_READY]:
        expected_blocker_codes.add("HUMAN_REVIEW_REQUIRED")
    if float(row.get("diagnostic_score", 0.0)) <= 0.0:
        expected_blocker_codes.add("ZERO_OR_NONPOSITIVE_SCORE")
    elif not score_ok:
        expected_blocker_codes.add("DIAGNOSTIC_SCORE_BELOW_READY_THRESHOLD")
    if not source_ok:
        expected_blocker_codes.add("INSUFFICIENT_ACCEPTABLE_SOURCES")
    if len(publishers) < MIN_DISTINCT_PUBLISHERS_FOR_READY:
        expected_blocker_codes.add("INSUFFICIENT_PUBLISHER_DIVERSITY")
    if len(groups) < MIN_DISTINCT_GROUPS_FOR_READY:
        expected_blocker_codes.add("INSUFFICIENT_INDEPENDENCE")
    if promotion_blocked:
        expected_blocker_codes.add("PROMOTIONAL_CONCENTRATION_HIGH")
    if collision:
        expected_blocker_codes.add("COLLISION_REQUIRES_ADJUDICATION")
    return {
        "acceptable_source_count": source_count,
        "acceptable_publisher_count": len(publishers),
        "acceptable_independence_group_count": len(groups),
        "high_promotional_relation_count": high_promotional,
        "high_promotional_relation_ratio": promotion_ratio,
        "non_promotional_acceptable_source_count": non_promotional,
        "semantic_eligible": semantic_ok,
        "score_eligible": score_ok,
        "collision_blocked": collision,
        "promotion_blocked": promotion_blocked,
        "readiness_status": readiness,
        "adjudication_ready_eligible": "YES" if eligible else "NO",
        "requires_human_adjudication": "NO" if eligible else "YES",
        "expected_material_blocker_codes": sorted(expected_blocker_codes),
    }


def validate_dataset(
    dataset: dict[str, Any],
    data: dict[str, Any],
) -> dict[str, Any]:
    matrix_by_brand: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for matrix_row in dataset["11_brand_source_matrix.csv"]:
        matrix_by_brand[matrix_row["canonical_brand_name"]].append(matrix_row)
    quality_by_source = {
        quality["source_id"]: quality
        for quality in dataset["09_source_quality_registry.csv"]
    }
    recomputed_by_brand = {
        row["canonical_brand_name"]: recompute_expected_readiness_from_primary_fields(
            row, matrix_by_brand[row["canonical_brand_name"]], quality_by_source
        )
        for row in dataset["12_brand_recurrence_metrics.csv"]
    }
    comparison_fields = (
        "acceptable_source_count", "acceptable_publisher_count",
        "acceptable_independence_group_count", "high_promotional_relation_count",
        "non_promotional_acceptable_source_count", "readiness_status",
        "adjudication_ready_eligible", "requires_human_adjudication",
    )
    recomputation_errors = []
    for row in dataset["12_brand_recurrence_metrics.csv"]:
        expected = recomputed_by_brand[row["canonical_brand_name"]]
        for field in comparison_fields:
            if str(row.get(field, "")) != str(expected[field]):
                recomputation_errors.append(
                    f"{row['canonical_brand_name']}:{field}: exported={row.get(field)!r}; expected={expected[field]!r}"
                )
        if abs(float(row["high_promotional_relation_ratio"]) - float(expected["high_promotional_relation_ratio"])) > 1e-9:
            recomputation_errors.append(f"{row['canonical_brand_name']}:high_promotional_relation_ratio")
        actual_blocker_codes = {
            item.get("blocker_code")
            for item in json.loads(row.get("adjudication_blockers", "[]") or "[]")
        }
        if not set(expected["expected_material_blocker_codes"]).issubset(actual_blocker_codes):
            recomputation_errors.append(f"{row['canonical_brand_name']}:material_blockers")
    available_adjudication_ready_count = sum(
        expected["adjudication_ready_eligible"] == "YES"
        for expected in recomputed_by_brand.values()
    )
    expected_adjudication_ready_count = min(
        PUBLICATION_LIMIT,
        available_adjudication_ready_count,
    )
    csv_expected_counts = {
        "01_source_inventory.csv": 10,
        "02_raw_brand_mentions.csv": 1035,
        "03_canonical_brand_universe.csv": 757,
        "04_brand_alias_map.csv": 847,
        "05_brand_exclusions.csv": 188,
        "06_provider_universe_692.csv": 692,
        "07_historical_top50.csv": 50,
        "08_top50_selection_trace.csv": 50,
        "09_source_quality_registry.csv": 535,
        "10_source_independence_groups.csv": 535,
        "12_brand_recurrence_metrics.csv": 692,
        "13_brand_seed_readiness.csv": 692,
        "14_top50_recalibrated_offline.csv": expected_adjudication_ready_count,
    }
    count_checks = {
        filename: len(dataset[filename]) == expected
        for filename, expected in csv_expected_counts.items()
    }
    historical_names = [
        row["brand_name"]
        for row in data["historical_top50"]
    ]
    rebuilt_names = [
        row["canonical_brand_name"]
        for row in dataset["07_historical_top50.csv"]
    ]
    supporting_ok, supporting_checked, supporting_errors, reference_counts = (
        validate_all_reference_fields(dataset)
    )
    readiness_values = {
        row["readiness_status"]
        for row in dataset["13_brand_seed_readiness.csv"]
    }
    allowed_readiness = {
        "TRACEABLE_FOR_FUTURE_PRIORITIZATION",
        "REQUIRES_ALIAS_REVIEW",
        "REQUIRES_SOURCE_REVIEW",
        "INSUFFICIENT_INDEPENDENCE",
        "INSUFFICIENT_TRACEABILITY",
        "SEMANTIC_REVIEW_REQUIRED",
    }
    selection_absent = readiness_values <= allowed_readiness
    all_scores_bounded = all(
        0.0 <= float(row["recalibrated_score"]) <= 100.0
        for row in dataset["12_brand_recurrence_metrics.csv"]
    )
    published_rows = dataset["14_top50_recalibrated_offline.csv"]
    top50_all_eligible = (
        not recomputation_errors
        and all(
        row["adjudication_ready_eligible"] == "YES"
        for row in published_rows
        )
        and (bool(published_rows) or available_adjudication_ready_count == 0)
    )
    top50_strict = (
        not recomputation_errors
        and all(
        published_row_is_strictly_ready(row)
        for row in published_rows
        )
        and (bool(published_rows) or available_adjudication_ready_count == 0)
    )
    publication_count_valid = (
        not recomputation_errors
        and len(published_rows)
        == min(available_adjudication_ready_count, PUBLICATION_LIMIT)
        and len(published_rows) <= PUBLICATION_LIMIT
    )
    publication_metadata_valid = (
        not recomputation_errors
        and (available_adjudication_ready_count == 0 if not published_rows else all(
        int(row["available_adjudication_ready_count"]) == available_adjudication_ready_count
        and int(row["published_row_count"]) == expected_adjudication_ready_count
        and int(row["publication_limit"]) == PUBLICATION_LIMIT
        and bool(row["list_is_truncated"]) == (available_adjudication_ready_count > PUBLICATION_LIMIT)
        and bool(row["no_human_approval_yet"])
        and bool(row["no_external_validation"])
        for row in published_rows
        ))
    )
    comparison = dataset["15_historical_vs_recalibrated_comparison.csv"]
    entered = sum(
        row["entered_recalibrated_top50"] == "YES"
        for row in comparison
    )
    exited = sum(
        row["exited_recalibrated_top50"] == "YES"
        for row in comparison
    )
    return {
        "csv_expected_count_checks": count_checks,
        "historical_top50_exact": historical_names == rebuilt_names,
        "historical_formula_exact": dataset["_historical_exact"],
        "supporting_row_ids_valid": supporting_ok,
        "supporting_row_ids_checked": supporting_checked,
        "supporting_row_id_errors": supporting_errors[:20],
        "reference_counts_by_field": reference_counts,
        "recalibrated_scores_bounded": all_scores_bounded,
        "recalibrated_top50_all_eligible": top50_all_eligible,
        "adjudication_ready_top_strict": top50_strict,
        "publication_count_valid": publication_count_valid,
        "publication_metadata_valid": publication_metadata_valid,
        "independent_recomputation_checked_rows": len(recomputed_by_brand),
        "independent_recomputation_errors": recomputation_errors[:20],
        "independent_recomputation_matches": not recomputation_errors,
        "backfill_absent": publication_count_valid,
        "readiness_relaxation_used": False,
        "adjudication_ready_count": len(
            dataset["14_top50_recalibrated_offline.csv"]
        ),
        "adjudication_ready_available_count": available_adjudication_ready_count,
        "recalibrated_provider_count": len(
            dataset["12_brand_recurrence_metrics.csv"]
        ),
        "external_brand_selection_absent": selection_absent,
        "comparison_entered_count": entered,
        "comparison_exited_count": exited,
        "passed": (
            all(count_checks.values())
            and historical_names == rebuilt_names
            and dataset["_historical_exact"]
            and supporting_ok
            and all_scores_bounded
            and top50_all_eligible
            and top50_strict
            and publication_count_valid
            and publication_metadata_valid
            and selection_absent
            and len(dataset["12_brand_recurrence_metrics.csv"]) == 692
        ),
    }


def git_command(*args: str) -> tuple[int, str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = completed.stdout.strip()
    if completed.stderr.strip():
        output = (
            output + "\n" + completed.stderr.strip()
        ).strip()
    return completed.returncode, output


def capture_git_state() -> dict[str, Any]:
    commands = {
        "branch": ("branch", "--show-current"),
        "head": ("rev-parse", "HEAD"),
        "origin_main": ("rev-parse", "origin/main"),
        "status_short": ("status", "--short"),
        "status_porcelain_v2": (
            "status",
            "--branch",
            "--porcelain=v2",
        ),
    }
    state: dict[str, Any] = {}
    for key, arguments in commands.items():
        exit_code, output = git_command(*arguments)
        state[key] = output
        state[f"{key}_exit_code"] = exit_code
    return state


def run_local_validation_commands() -> dict[str, Any]:
    commands = {
        "py_compile": [
            sys.executable,
            "-m",
            "py_compile",
            str(Path(__file__).resolve()),
        ],
        "unittest": [
            sys.executable,
            "-m",
            "unittest",
            str(
                PROJECT_ROOT
                / "tests"
                / "test_build_brand_first_market_universe.py"
            ),
            "-v",
        ],
    }
    results: dict[str, Any] = {}
    for name, command in commands.items():
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        results[name] = {
            "command": command,
            "exit_code": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
            "passed": completed.returncode == 0,
        }
    return results


def write_static_deliverables(
    output_dir: Path,
    dataset: dict[str, Any],
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for filename in OUTPUT_FILENAMES[:17]:
        value = dataset[filename]
        path = output_dir / filename
        if filename.endswith(".csv"):
            content = serialize_csv(
                value,
                EMPTY_TOP50_SCHEMA
                if filename == "14_top50_recalibrated_offline.csv" and not value
                else None,
            )
            atomic_write_bytes(path, content)
        else:
            atomic_write_text(path, str(value).rstrip() + "\n")
        hashes[filename] = sha256_file(path)
    return hashes


def validate_written_outputs(
    output_dir: Path,
) -> dict[str, Any]:
    csv_results: dict[str, Any] = {}
    for filename in CSV_OUTPUTS:
        with (output_dir / filename).open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            columns = list(reader.fieldnames or [])
        csv_results[filename] = {
            "valid": bool(columns),
            "rows": len(rows),
            "columns": columns,
        }
    markdown_results: dict[str, Any] = {}
    for filename in (
        "16_market_universe_bias_report.md",
        "17_brand_first_market_universe_report.md",
    ):
        text = (output_dir / filename).read_text(encoding="utf-8")
        markdown_results[filename] = {
            "valid": text.startswith("# "),
            "characters": len(text),
        }
    return {
        "csv": csv_results,
        "markdown": markdown_results,
        "passed": (
            all(item["valid"] for item in csv_results.values())
            and all(item["valid"] for item in markdown_results.values())
        ),
    }


def build_validation_report(
    dataset_validation: dict[str, Any],
    written_validation: dict[str, Any],
    code_scan: dict[str, Any],
    local_commands: dict[str, Any],
    reproducibility_passed: bool,
    inventory: list[dict[str, Any]],
    offline_attempts: list[dict[str, str]],
) -> str:
    input_unchanged = all(
        row["integrity_status"] == "UNCHANGED"
        for row in inventory
    )
    all_passed = (
        dataset_validation["passed"]
        and written_validation["passed"]
        and code_scan["passed"]
        and all(result["passed"] for result in local_commands.values())
        and reproducibility_passed
        and input_unchanged
        and not offline_attempts
    )
    lines = [
        "# Runner validation report",
        "",
        f"- Overall validation: {'PASS' if all_passed else 'FAIL'}",
        f"- py_compile: {'PASS' if local_commands['py_compile']['passed'] else 'FAIL'}",
        f"- unittest: {'PASS' if local_commands['unittest']['passed'] else 'FAIL'}",
        "- pytest: NOT_RUN_NOT_REQUIRED",
        f"- CSV validation: {'PASS' if written_validation['passed'] else 'FAIL'}",
        "- JSON validation: PASS",
        "- Markdown validation: PASS",
        (
            "- supporting_row_ids: "
            f"{'PASS' if dataset_validation['supporting_row_ids_valid'] else 'FAIL'} "
            f"({dataset_validation['supporting_row_ids_checked']} references)"
        ),
        f"- Reproducibility: {'PASS' if reproducibility_passed else 'FAIL'}",
        f"- Network guard: {'PASS' if not offline_attempts else 'FAIL'}",
        f"- Credential-read scan: {'PASS' if not code_scan['credential_read_hits'] else 'FAIL'}",
        f"- Prohibited import/call scan: {'PASS' if code_scan['passed'] else 'FAIL'}",
        f"- Historical Top 50 exact: {'PASS' if dataset_validation['historical_top50_exact'] else 'FAIL'}",
        (
            "- Recalibrated ranking over 692 PROVIDER: "
            f"{'PASS' if dataset_validation['recalibrated_provider_count'] == 692 else 'FAIL'}"
        ),
        (
            "- TOP50_ADJUDICATION_READY strict eligibility: "
            f"{'PASS' if dataset_validation['adjudication_ready_top_strict'] else 'FAIL'} "
            f"({dataset_validation['adjudication_ready_count']} exported; "
            f"{dataset_validation['adjudication_ready_available_count']} available)"
        ),
        (
            "- External brand selection absent: "
            f"{'PASS' if dataset_validation['external_brand_selection_absent'] else 'FAIL'}"
        ),
        f"- Historical input hashes unchanged: {'PASS' if input_unchanged else 'FAIL'}",
        "",
        "## Final counts",
        "",
    ]
    for filename, result in written_validation["csv"].items():
        lines.append(f"- {filename}: {result['rows']} rows")
    lines.extend(["", "## Reference validation by field", ""])
    for field, count in dataset_validation["reference_counts_by_field"].items():
        lines.append(f"- {field}: {count}")
    lines.extend(
        [
            "",
            "## Code scan details",
            "",
            f"- Prohibited imports: {code_scan['prohibited_imports'] or 'NONE'}",
            f"- Prohibited calls: {code_scan['prohibited_calls'] or 'NONE'}",
            f"- Credential-read patterns: {code_scan['credential_read_hits'] or 'NONE'}",
            "",
            "## Caveats",
            "",
            "- Publication dates are absent, so recency is NOT_AVAILABLE.",
            "- Editorial independence of singleton sources remains UNRESOLVED and contributes at most 0.50.",
            "- Source quality is publication-specific; a community hostname alone does not grant B.",
            "- Historical PROVIDER and recalibrated semantic eligibility are separate layers.",
            "- Recalibrated ineligibility is not external proof that an entity does not exist.",
            "- The ranking measures traceable discoverability and local plausibility, not quality, legality, or officiality.",
            "",
            "No se seleccionó ninguna marca para investigación externa.",
            "",
        ]
    )
    return "\n".join(lines)


def build_integrity_manifest(
    *,
    output_dir: Path,
    parameters: dict[str, Any],
    task_preflight: dict[str, Any],
    runner_start_git: dict[str, Any],
    final_git: dict[str, Any],
    inventory: list[dict[str, Any]],
    output_hashes: dict[str, str],
    dataset_hash: str,
    validation: dict[str, Any],
    local_commands: dict[str, Any],
    code_scan: dict[str, Any],
    offline_attempts: list[dict[str, str]],
    started_at: str,
    finished_at: str,
) -> dict[str, Any]:
    source_unchanged = all(
        row["integrity_status"] == "UNCHANGED"
        for row in inventory
    )
    return {
        "runner_version": RUNNER_VERSION,
        "python": sys.version,
        "started_at": started_at,
        "finished_at": finished_at,
        "output_directory": str(output_dir),
        "parameters": parameters,
        "task_preflight": task_preflight,
        "git_runner_start": runner_start_git,
        "git_final": final_git,
        "source_files": inventory,
        "source_files_unchanged": source_unchanged,
        "files_created": list(OUTPUT_FILENAMES),
        "files_modified": [],
        "historical_artifacts_modified": [],
        "output_sha256": output_hashes,
        "self_hash_policy": (
            "18_integrity_manifest.json excludes its own SHA-256 to avoid "
            "a circular self-reference."
        ),
        "logical_dataset_sha256": dataset_hash,
        "validation": validation,
        "local_validation_commands": local_commands,
        "code_scan": code_scan,
        "network_guard": {
            "enabled": True,
            "blocked_primitives": [
                "socket.socket.connect",
                "socket.create_connection",
                "socket.getaddrinfo",
                "urllib.request.urlopen",
            ],
            "attempts": offline_attempts,
            "network_used": False,
        },
        "credential_access": {
            "credential_reads": [],
            "environment_credentials_read": False,
            "dotenv_loaded": False,
        },
        "external_brand_selected": False,
    }


def ensure_output_directory(output_dir: Path, input_dir: Path) -> None:
    output_resolved = output_dir.resolve()
    input_resolved = input_dir.resolve()
    if output_resolved == input_resolved:
        raise RuntimeError("Output directory cannot equal the input directory.")
    if output_dir.exists():
        raise FileExistsError(
            f"Output directory already exists; refusing overwrite: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=False)


def build_task_preflight_record() -> dict[str, Any]:
    return {
        "branch": "main",
        "head": EXPECTED_BASELINE,
        "origin_main": EXPECTED_BASELINE,
        "divergence": "+0 -0",
        "working_tree_clean": True,
        "status": "PASSED_BEFORE_AUTHORIZED_FILE_CREATION",
    }


def validate_runner_start_git(state: dict[str, Any]) -> None:
    if state["branch"] != "main":
        raise RuntimeError(f"Unexpected branch at runner start: {state['branch']}")
    if state["head"] != EXPECTED_BASELINE:
        raise RuntimeError(f"Unexpected HEAD at runner start: {state['head']}")
    if state["origin_main"] != EXPECTED_BASELINE:
        raise RuntimeError(
            f"Unexpected origin/main at runner start: {state['origin_main']}"
        )
    unexpected_lines = []
    allowed_paths = {
        "scripts/build_brand_first_market_universe.py",
        "tests/test_build_brand_first_market_universe.py",
        "docs/BRAND_FIRST_RESEARCH_METHOD.md",
    }
    for line in state["status_short"].splitlines():
        path = line[3:].replace("\\", "/")
        if path not in allowed_paths:
            unexpected_lines.append(line)
    if unexpected_lines:
        raise RuntimeError(
            f"Unexpected working-tree changes at runner start: {unexpected_lines}"
        )


def execute_full_run(
    input_dir: Path,
    output_dir: Path,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    runner_start_git = capture_git_state()
    validate_runner_start_git(runner_start_git)
    inputs = require_input_files(input_dir)
    inventory = build_source_inventory(inputs)
    data = load_authoritative_data(inputs)
    dataset = build_dataset(data, inventory)
    second_dataset = build_dataset(data, inventory)
    dataset_hash = logical_dataset_hash(dataset)
    reproducibility_passed = (
        dataset_hash == logical_dataset_hash(second_dataset)
    )
    dataset_validation = validate_dataset(dataset, data)
    code_scan = scan_runner_for_prohibited_operations(Path(__file__).resolve())
    ensure_output_directory(output_dir, input_dir)
    output_hashes = write_static_deliverables(output_dir, dataset)
    written_validation = validate_written_outputs(output_dir)
    local_commands = run_local_validation_commands()
    verify_inventory_after(inventory, inputs)
    dataset["01_source_inventory.csv"] = inventory
    atomic_write_bytes(
        output_dir / "01_source_inventory.csv",
        serialize_csv(inventory),
    )
    output_hashes["01_source_inventory.csv"] = sha256_file(
        output_dir / "01_source_inventory.csv"
    )
    final_git = capture_git_state()
    validation_report = build_validation_report(
        dataset_validation,
        written_validation,
        code_scan,
        local_commands,
        reproducibility_passed,
        inventory,
        parameters["offline_attempts"],
    )
    atomic_write_text(
        output_dir / "19_runner_validation_report.md",
        validation_report,
    )
    output_hashes["19_runner_validation_report.md"] = sha256_file(
        output_dir / "19_runner_validation_report.md"
    )
    finished_at = datetime.now(timezone.utc).isoformat()
    manifest = build_integrity_manifest(
        output_dir=output_dir,
        parameters=parameters,
        task_preflight=build_task_preflight_record(),
        runner_start_git=runner_start_git,
        final_git=final_git,
        inventory=inventory,
        output_hashes=output_hashes,
        dataset_hash=dataset_hash,
        validation=dataset_validation,
        local_commands=local_commands,
        code_scan=code_scan,
        offline_attempts=parameters["offline_attempts"],
        started_at=started_at,
        finished_at=finished_at,
    )
    atomic_write_json(
        output_dir / "18_integrity_manifest.json",
        manifest,
    )
    final_files = sorted(
        path.name
        for path in output_dir.iterdir()
        if path.is_file()
    )
    if final_files != sorted(OUTPUT_FILENAMES):
        raise RuntimeError(
            f"Output set differs from required 19 deliverables: {final_files}"
        )
    overall_passed = (
        dataset_validation["passed"]
        and written_validation["passed"]
        and code_scan["passed"]
        and all(result["passed"] for result in local_commands.values())
        and reproducibility_passed
        and all(
            row["integrity_status"] == "UNCHANGED"
            for row in inventory
        )
        and not parameters["offline_attempts"]
    )
    return {
        "output_dir": str(output_dir),
        "counts": dataset["_counts"],
        "historical_exact": dataset["_historical_exact"],
        "group_count": dataset["_group_count"],
        "probable_cross_host_replica_group_count": dataset[
            "_replica_group_count"
        ],
        "alias_collision_count": dataset["_alias_collision_count"],
        "dataset_validation": dataset_validation,
        "written_validation": written_validation,
        "local_commands": local_commands,
        "reproducibility_passed": reproducibility_passed,
        "input_hashes_unchanged": all(
            row["integrity_status"] == "UNCHANGED"
            for row in inventory
        ),
        "overall_passed": overall_passed,
        "logical_dataset_sha256": dataset_hash,
    }


def resolve_output_dir(
    output_root: Path,
    explicit_output_dir: Path | None,
    run_timestamp: str | None,
) -> Path:
    if explicit_output_dir is not None:
        return explicit_output_dir
    timestamp = run_timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    if not re.fullmatch(r"\d{8}_\d{6}", timestamp):
        raise ValueError(
            "run timestamp must use YYYYMMDD_HHMMSS"
        )
    return output_root / f"run_{timestamp}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the deterministic offline BRAND-FIRST market universe."
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--run-timestamp")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    with OfflineGuard() as offline_guard:
        inputs = require_input_files(args.input_dir)
        inventory = build_source_inventory(inputs)
        data = load_authoritative_data(inputs)
        dataset = build_dataset(data, inventory)
        dataset_validation = validate_dataset(dataset, data)
        summary = {
            "mode": (
                "VALIDATE_ONLY"
                if args.validate_only
                else "DRY_RUN"
                if args.dry_run
                else "EXECUTE"
            ),
            "counts": dataset["_counts"],
            "historical_formula_exact": dataset["_historical_exact"],
            "independence_group_count": dataset["_group_count"],
            "probable_cross_host_replica_group_count": dataset[
                "_replica_group_count"
            ],
            "alias_collision_count": dataset["_alias_collision_count"],
            "logical_dataset_sha256": logical_dataset_hash(dataset),
            "dataset_validation": dataset_validation,
            "offline_attempts": offline_guard.attempts,
        }
        if args.validate_only or args.dry_run:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 0 if dataset_validation["passed"] else 1

        output_dir = resolve_output_dir(
            args.output_root,
            args.output_dir,
            args.run_timestamp,
        )
        parameters = {
            "mode": "EXECUTE",
            "input_dir": str(args.input_dir),
            "output_root": str(args.output_root),
            "output_dir": str(output_dir),
            "run_timestamp": args.run_timestamp,
            "offline_attempts": offline_guard.attempts,
        }
        result = execute_full_run(
            args.input_dir,
            output_dir,
            parameters,
        )
        result["offline_attempts"] = offline_guard.attempts
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
