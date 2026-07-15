from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
from tavily import TavilyClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "research" / "output" / "best_iptv_2026"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MAX_RESULTS_PER_QUERY = 20
SEARCH_DEPTH = "advanced"
PAUSE_SECONDS = 0.8

QUERIES = [
    'site:reddit.com "best IPTV" "2026"',
    'site:reddit.com IPTV provider review 2026',
    'site:reddit.com IPTV service stable 2026',
    'site:indiehackers.com "best IPTV" "2026"',
    'site:indiehackers.com IPTV provider 2026',
    'site:medium.com "best IPTV" "2026"',
    'site:medium.com IPTV provider review 2026',
    'site:quora.com "best IPTV provider" "2026"',
    'site:producthunt.com IPTV streaming',
    'site:news.ycombinator.com IPTV',
    'site:github.com IPTV reseller panel',
    'site:github.com IPTV provider',
    'site:trustpilot.com/review IPTV provider',
    'site:trustpilot.com/review IPTV service',
    '"best IPTV forum" 2026',
    '"IPTV provider forum" 2026',
    'site:youtube.com "best IPTV 2026"',
    'site:youtube.com IPTV provider review 2026',
    'site:facebook.com IPTV reseller 2026',
    'site:t.me IPTV reseller',
    '"best IPTV Colombia" 2026',
    '"best IPTV Latino" 2026',
    '"best IPTV Latin America" 2026',
    '"best IPTV Brazil" 2026',
    '"melhor IPTV" 2026',
    '"best IPTV USA" 2026',
    '"best IPTV Canada" 2026',
    '"best IPTV UK" 2026',
    '"best IPTV Europe" 2026',
    '"best IPTV Australia" 2026',
    '"best IPTV Firestick" 2026',
    '"best IPTV Android TV" 2026',
    '"best IPTV Samsung TV" 2026',
    '"best IPTV LG TV" 2026',
    '"best IPTV Roku" 2026',
    '"IPTV reseller panel" 2026',
    '"IPTV white label" provider 2026',
    '"Xtream Codes" IPTV provider 2026',
    '"M3U" IPTV provider 2026',
    '"IPTV free trial" provider 2026',
    '"IPTV 4K" provider review 2026',
    '"IPTV sports" provider review 2026',
]

BRAND_PATTERNS = [
    r"\b[A-Z][A-Za-z0-9]{2,20}\s+IPTV\b",
    r"\b[A-Z][A-Za-z0-9]{2,20}\s+TV\b",
    r"\b[A-Z][A-Za-z0-9]{2,20}TV\b",
    r"\bIPTV[A-Z][A-Za-z0-9]{2,20}\b",
]

GENERIC_TERMS = {
    "IPTV Service",
    "IPTV Provider",
    "Best IPTV",
    "Live TV",
    "Smart TV",
    "Android TV",
    "Apple TV",
    "IPTV TV",
}


def stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def identify_platform(domain: str) -> str:
    mappings = {
        "reddit.com": "Reddit",
        "indiehackers.com": "Indie Hackers",
        "medium.com": "Medium",
        "quora.com": "Quora",
        "producthunt.com": "Product Hunt",
        "news.ycombinator.com": "Hacker News",
        "github.com": "GitHub",
        "trustpilot.com": "Trustpilot",
        "youtube.com": "YouTube",
        "youtu.be": "YouTube",
        "facebook.com": "Facebook",
        "t.me": "Telegram",
    }

    for known_domain, platform in mappings.items():
        if domain == known_domain or domain.endswith("." + known_domain):
            return platform

    return "Web"


def extract_brands(text: str) -> list[str]:
    brands: set[str] = set()

    for pattern in BRAND_PATTERNS:
        for match in re.findall(pattern, text):
            candidate = clean_text(match).strip(".,:;!?()[]{}\"'")
            if candidate not in GENERIC_TERMS and len(candidate) <= 40:
                brands.add(candidate)

    return sorted(brands)


def normalize_result(
    query: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    url = clean_text(result.get("url"))
    title = clean_text(result.get("title"))
    summary = clean_text(result.get("content"))
    raw_content = clean_text(result.get("raw_content"))
    domain = extract_domain(url)

    searchable_text = " ".join(
        part for part in [title, summary, raw_content[:10000]] if part
    )

    return {
        "record_id": stable_id(url or title),
        "query": query,
        "title": title,
        "url": url,
        "domain": domain,
        "source_platform": identify_platform(domain),
        "published_date": clean_text(result.get("published_date")),
        "score": result.get("score"),
        "summary": summary,
        "raw_content": raw_content,
        "brands_detected": extract_brands(searchable_text),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


def run_searches(client: TavilyClient) -> list[dict[str, Any]]:
    records_by_url: dict[str, dict[str, Any]] = {}

    for index, query in enumerate(QUERIES, start=1):
        print(f"[{index:02d}/{len(QUERIES)}] {query}")

        try:
            response = client.search(
                query=query,
                search_depth=SEARCH_DEPTH,
                max_results=MAX_RESULTS_PER_QUERY,
                include_raw_content=True,
                include_answer=False,
            )
        except Exception as exc:
            print(f"  ERROR: {exc}")
            continue

        results = response.get("results", [])

        for result in results:
            record = normalize_result(query, result)
            key = record["url"] or record["record_id"]

            if key not in records_by_url:
                record["matched_queries"] = [query]
                records_by_url[key] = record
            else:
                matched_queries = records_by_url[key]["matched_queries"]
                if query not in matched_queries:
                    matched_queries.append(query)

                existing_brands = set(
                    records_by_url[key].get("brands_detected", [])
                )
                existing_brands.update(record.get("brands_detected", []))
                records_by_url[key]["brands_detected"] = sorted(existing_brands)

        print(f"  Resultados: {len(results)}")
        time.sleep(PAUSE_SECONDS)

    return list(records_by_url.values())


def build_brand_table(records: list[dict[str, Any]]) -> pd.DataFrame:
    brand_rows: dict[str, dict[str, Any]] = {}

    for record in records:
        for brand in record.get("brands_detected", []):
            normalized = brand.casefold()

            if normalized not in brand_rows:
                brand_rows[normalized] = {
                    "brand_name": brand,
                    "source_count": 0,
                    "platforms": set(),
                    "domains": set(),
                    "urls": set(),
                    "queries": set(),
                    "latest_published_date": "",
                }

            row = brand_rows[normalized]
            row["source_count"] += 1
            row["platforms"].add(record["source_platform"])
            row["domains"].add(record["domain"])
            row["urls"].add(record["url"])
            row["queries"].update(record.get("matched_queries", []))

            published_date = record.get("published_date", "")
            if published_date > row["latest_published_date"]:
                row["latest_published_date"] = published_date

    output_rows = []

    for row in brand_rows.values():
        output_rows.append(
            {
                "brand_name": row["brand_name"],
                "source_count": row["source_count"],
                "platforms": " | ".join(sorted(row["platforms"])),
                "domains": " | ".join(sorted(filter(None, row["domains"]))),
                "latest_published_date": row["latest_published_date"],
                "queries_count": len(row["queries"]),
                "evidence_urls": " | ".join(sorted(filter(None, row["urls"]))),
            }
        )

    dataframe = pd.DataFrame(output_rows)

    if not dataframe.empty:
        dataframe = dataframe.sort_values(
            by=["source_count", "brand_name"],
            ascending=[False, True],
        )

    return dataframe


def export_results(records: list[dict[str, Any]]) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = OUTPUT_DIR / f"tavily_corpus_{timestamp}.json"
    csv_path = OUTPUT_DIR / f"tavily_corpus_{timestamp}.csv"
    brands_csv_path = OUTPUT_DIR / f"brands_consolidated_{timestamp}.csv"
    excel_path = OUTPUT_DIR / f"best_iptv_2026_{timestamp}.xlsx"

    json_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    flat_records = []

    for record in records:
        flat_record = record.copy()
        flat_record["brands_detected"] = " | ".join(
            record.get("brands_detected", [])
        )
        flat_record["matched_queries"] = " | ".join(
            record.get("matched_queries", [])
        )
        flat_records.append(flat_record)

    corpus_df = pd.DataFrame(flat_records)
    brands_df = build_brand_table(records)

    corpus_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    brands_df.to_csv(brands_csv_path, index=False, encoding="utf-8-sig")

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        brands_df.to_excel(
            writer,
            sheet_name="Marcas consolidadas",
            index=False,
        )
        corpus_df.drop(columns=["raw_content"], errors="ignore").to_excel(
            writer,
            sheet_name="Fuentes",
            index=False,
        )

    print()
    print("INVESTIGACIÓN FINALIZADA")
    print(f"Fuentes únicas: {len(records)}")
    print(f"Marcas detectadas: {len(brands_df)}")
    print(f"JSON:  {json_path}")
    print(f"CSV:   {csv_path}")
    print(f"Marcas:{brands_csv_path}")
    print(f"Excel: {excel_path}")


def main() -> None:
    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        raise RuntimeError(
            "No se encontró TAVILY_API_KEY. "
            'Configúrala con: $env:TAVILY_API_KEY="TU_CLAVE"'
        )

    client = TavilyClient(api_key=api_key)
    records = run_searches(client)
    export_results(records)


if __name__ == "__main__":
    main()