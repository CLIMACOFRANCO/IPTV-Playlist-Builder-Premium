#!/usr/bin/env python3
"""
Genera una EPG XMLTV personalizada para Weib Player TV.

Entrada:
  1) Un XMLTV fuente (.xml o .xml.gz).
  2) El reporte CSV de matching generado por IPTV Playlist Builder Premium.

Salida:
  custom_weib_epg.xml.gz

La salida conserva la programación original, pero crea canales cuyo
display-name coincide exactamente con los nombres del proveedor Xtream Codes.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import re
import shutil
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import BinaryIO, Iterable


def open_binary(path: Path) -> BinaryIO:
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rb")
    return path.open("rb")


def safe_target_id(name: str, row_number: int) -> str:
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_")[:80] or "channel"
    return f"weib.{row_number}.{slug}.{digest}"


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "IPTV-Playlist-Builder-Premium/1.0"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        with destination.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)


def load_mapping(csv_path: Path) -> tuple[dict[str, list[dict[str, str]]], int]:
    by_source: dict[str, list[dict[str, str]]] = defaultdict(list)
    total = 0

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"row", "original_name", "matched", "tvg_id"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Faltan columnas requeridas en el CSV: {sorted(missing)}")

        seen_names: set[tuple[str, str]] = set()

        for record in reader:
            if str(record.get("matched", "")).strip().lower() not in {"true", "1", "yes", "sí", "si"}:
                continue

            source_id = str(record.get("tvg_id", "")).strip()
            provider_name = str(record.get("original_name", "")).strip()
            if not source_id or not provider_name:
                continue

            dedupe_key = (source_id, provider_name.casefold())
            if dedupe_key in seen_names:
                continue
            seen_names.add(dedupe_key)

            row_number = int(record.get("row") or 0)
            target_id = safe_target_id(provider_name, row_number)
            by_source[source_id].append(
                {
                    "target_id": target_id,
                    "provider_name": provider_name,
                    "group_title": str(record.get("group_title", "")).strip(),
                    "confidence": str(record.get("confidence", "")).strip(),
                }
            )
            total += 1

    return by_source, total


def clone_element(element: ET.Element) -> ET.Element:
    return ET.fromstring(ET.tostring(element, encoding="utf-8"))


def build_custom_xmltv(
    source_path: Path,
    mapping_csv: Path,
    output_path: Path,
) -> dict[str, int]:
    mapping, mapped_aliases = load_mapping(mapping_csv)
    wanted_ids = set(mapping)

    stats = {
        "source_ids_requested": len(wanted_ids),
        "provider_aliases_requested": mapped_aliases,
        "source_channels_found": 0,
        "custom_channels_written": 0,
        "source_programmes_found": 0,
        "custom_programmes_written": 0,
    }

    with tempfile.TemporaryDirectory(prefix="weib_epg_") as tmpdir:
        temp_xml = Path(tmpdir) / "custom_weib_epg.xml"

        with temp_xml.open("wb") as raw_output:
            raw_output.write(
                b'<?xml version="1.0" encoding="UTF-8"?>\n'
                b'<tv generator-info-name="IPTV Playlist Builder Premium">\n'
            )

            # Primera pasada: canales.
            with open_binary(source_path) as source:
                for event, element in ET.iterparse(source, events=("end",)):
                    if element.tag == "channel":
                        source_id = element.attrib.get("id", "")
                        aliases = mapping.get(source_id)
                        if aliases:
                            stats["source_channels_found"] += 1
                            for alias in aliases:
                                channel = clone_element(element)
                                channel.set("id", alias["target_id"])

                                # El nombre exacto del proveedor va primero.
                                for child in list(channel):
                                    if child.tag == "display-name":
                                        channel.remove(child)
                                display = ET.Element("display-name")
                                display.text = alias["provider_name"]
                                channel.insert(0, display)

                                raw_output.write(ET.tostring(channel, encoding="utf-8"))
                                raw_output.write(b"\n")
                                stats["custom_channels_written"] += 1
                        element.clear()

            # Segunda pasada: programas.
            with open_binary(source_path) as source:
                for event, element in ET.iterparse(source, events=("end",)):
                    if element.tag == "programme":
                        source_id = element.attrib.get("channel", "")
                        aliases = mapping.get(source_id)
                        if aliases:
                            stats["source_programmes_found"] += 1
                            for alias in aliases:
                                programme = clone_element(element)
                                programme.set("channel", alias["target_id"])
                                raw_output.write(ET.tostring(programme, encoding="utf-8"))
                                raw_output.write(b"\n")
                                stats["custom_programmes_written"] += 1
                        element.clear()

            raw_output.write(b"</tv>\n")

        with temp_xml.open("rb") as source, gzip.open(output_path, "wb", compresslevel=6) as target:
            shutil.copyfileobj(source, target, length=1024 * 1024)

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera XMLTV personalizado para Weib Player TV."
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--source-file", type=Path, help="XMLTV fuente .xml o .xml.gz")
    source_group.add_argument("--source-url", help="URL HTTP/HTTPS del XMLTV fuente")
    parser.add_argument(
        "--mapping",
        type=Path,
        required=True,
        help="CSV de matching generado por el proyecto",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("custom_weib_epg.xml.gz"),
        help="Archivo XMLTV personalizado de salida",
    )
    args = parser.parse_args()

    source_path = args.source_file
    temporary_download: Path | None = None

    try:
        if args.source_url:
            suffix = ".xml.gz" if args.source_url.lower().endswith(".gz") else ".xml"
            temporary_download = Path(tempfile.gettempdir()) / f"weib_source{suffix}"
            print(f"Descargando XMLTV: {args.source_url}")
            download(args.source_url, temporary_download)
            source_path = temporary_download

        if source_path is None or not source_path.exists():
            raise FileNotFoundError(f"No se encontró el XMLTV fuente: {source_path}")
        if not args.mapping.exists():
            raise FileNotFoundError(f"No se encontró el CSV de matching: {args.mapping}")

        print("Generando XMLTV personalizado...")
        stats = build_custom_xmltv(source_path, args.mapping, args.output)

        print("\nEjecución terminada")
        for key, value in stats.items():
            print(f"- {key}: {value:,}")
        print(f"- archivo: {args.output.resolve()}")
        print(f"- tamaño: {args.output.stat().st_size:,} bytes")
        return 0

    except (OSError, ValueError, ET.ParseError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if temporary_download and temporary_download.exists():
            temporary_download.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
