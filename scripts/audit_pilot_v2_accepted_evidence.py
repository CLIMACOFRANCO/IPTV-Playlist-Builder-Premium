from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
from openpyxl.utils import get_column_letter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = PROJECT_ROOT / "research" / "output" / "best_iptv_2026" / "tavily_due_diligence_v2"

INPUT_CSV = BASE_DIR / "pilot_v2_evidence_20260713.csv"
INPUT_JSON = BASE_DIR / "pilot_v2_evidence_20260713.json"
INPUT_RAW = BASE_DIR / "raw_results.jsonl"
INPUT_REJECTED = BASE_DIR / "rejected_results.jsonl"
INPUT_QUERY_LOG = BASE_DIR / "query_log.jsonl"

OUTPUT_CSV = BASE_DIR / "pilot_v2_accepted_audit_20260714.csv"
OUTPUT_XLSX = BASE_DIR / "pilot_v2_accepted_audit_20260714.xlsx"
OUTPUT_REPORT = BASE_DIR / "pilot_v2_accepted_audit_report_20260714.md"
OUTPUT_ADJUSTMENTS = BASE_DIR / "pilot_v2_filter_adjustments_20260714.json"

PIPE_SEPARATOR = " | "

EVIDENCE_CLASSES = {
    "TRUE_POSITIVE_DIRECT",
    "TRUE_POSITIVE_INDIRECT",
    "FALSE_POSITIVE_HOMONYM",
    "FALSE_POSITIVE_RESELLER",
    "FALSE_POSITIVE_AFFILIATE",
    "FALSE_POSITIVE_UNRELATED",
    "DUPLICATE",
    "UNRESOLVED",
}

OFFICIAL_DOMAIN_CANDIDATES = {
    "Krooz TV": "krooz-tvs.com",
    "Voco TV": "vocotv.org",
    "DigitaLizard IPTV": "digitalizard.app",
    "Sonix IPTV": "sonix-iptv.com",
}

HOMONYM_TERMS = {
    "Voco TV": {"ihg", "hotel", "hotels", "dental", "dentistry", "resort", "hospitality", "voco.dental"},
    "Sonix IPTV": {"sonix.ai", "transcription", "speech to text", "audio transcription"},
    "DigitaLizard IPTV": {"digita.fi", "digital agency", "marketing agency"},
    "Free Go TV": {"freeview", "free tv", "freego bike", "freego mobility"},
}

AFFILIATE_DOMAINS = {
    "bestiptv26.com",
    "bestiptvfinder.com",
    "bestiptvfreetrials.com",
    "guru99.com",
    "iptvrankings.com",
    "iptvserviceradar.com",
    "softwaretestinghelp.com",
    "the-best-iptv.com",
    "topiptvreviews.com",
    "troypoint.com",
    "yttags.com",
}

RESELLER_TERMS = {"reseller", "reseller program", "panel", "supplier", "iptv reseller"}
AFFILIATE_TERMS = {"best iptv", "top iptv", "ranked", "ranking", "review", "comparison", "providers"}
OFFICIAL_SIGNAL_TERMS = {
    "homepage_exact_brand",
    "terms_or_privacy_attributable",
    "same_domain_email",
    "coherent_social_links",
    "official_app_link",
    "corporate_identity",
    "consistent_commercial_contact",
    "independent_reference_links_domain",
}


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return re.sub(r"\s+", " ", str(value)).strip()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def parse_domain(url: str) -> str:
    try:
        return urlparse(clean_text(url)).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def exact_brand_present(text: str, brand: str) -> bool:
    return clean_text(brand).casefold() in clean_text(text).casefold()


def compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", clean_text(value).lower())


def combined_text(row: dict[str, Any]) -> str:
    return clean_text(
        f"{row.get('title', '')} {row.get('url', '')} {row.get('domain', '')} "
        f"{row.get('content', '')} {row.get('raw_content', '')}"
    )


def canonical_url(url: str) -> str:
    parsed = urlparse(clean_text(url))
    path = re.sub(r"/+$", "", parsed.path or "/")
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower().removeprefix('www.')}{path}"


def normalized_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean_text(title).lower()).strip()


def is_homonym(row: dict[str, Any]) -> tuple[bool, str]:
    brand = clean_text(row.get("brand_name"))
    text = combined_text(row).casefold()
    terms = sorted(term for term in HOMONYM_TERMS.get(brand, set()) if term.casefold() in text)
    return bool(terms), PIPE_SEPARATOR.join(terms)


def is_affiliate(row: dict[str, Any]) -> bool:
    domain = clean_text(row.get("domain")).lower() or parse_domain(clean_text(row.get("url")))
    text = combined_text(row).casefold()
    if domain in AFFILIATE_DOMAINS:
        return True
    if any(marker in domain for marker in ("bestiptv", "iptvreview", "topiptv")):
        return True
    return any(term in text for term in AFFILIATE_TERMS) and clean_text(row.get("source_category")) == "AFFILIATE_OR_PROMOTIONAL"


def is_reseller(row: dict[str, Any]) -> bool:
    text = combined_text(row).casefold()
    return clean_text(row.get("source_category")) == "RESELLER" or any(term in text for term in RESELLER_TERMS)


def is_unrelated(row: dict[str, Any]) -> bool:
    brand = clean_text(row.get("brand_name"))
    text = combined_text(row)
    return not exact_brand_present(text, brand)


def audit_evidence_rows(rows: list[dict[str, Any]], evidence_type: str) -> pd.DataFrame:
    audited = []
    seen = set()
    for index, row in enumerate(rows, start=1):
        brand = clean_text(row.get("brand_name"))
        url = clean_text(row.get("url"))
        title_key = normalized_title(clean_text(row.get("title")))
        dedupe_key = (brand, canonical_url(url), title_key)
        homonym, homonym_reason = is_homonym(row)

        if dedupe_key in seen:
            classification = "DUPLICATE"
            reason = "duplicate accepted/ambiguous evidence for same brand/url/title"
        elif homonym:
            classification = "FALSE_POSITIVE_HOMONYM"
            reason = f"homonym terms detected: {homonym_reason}"
        elif is_unrelated(row):
            classification = "FALSE_POSITIVE_UNRELATED"
            reason = "exact brand name absent from stored title/content/url"
        elif is_reseller(row):
            classification = "FALSE_POSITIVE_RESELLER"
            reason = "reseller/panel/supplier signal; not primary brand evidence"
        elif is_affiliate(row):
            classification = "FALSE_POSITIVE_AFFILIATE"
            reason = "affiliate/ranking/review style result"
        else:
            domain = clean_text(row.get("domain")) or parse_domain(url)
            candidate = OFFICIAL_DOMAIN_CANDIDATES.get(brand)
            if candidate and domain == candidate:
                classification = "TRUE_POSITIVE_DIRECT"
                reason = "brand-specific candidate domain and exact brand context"
            elif clean_text(row.get("source_category")) in {"APP_STORE", "REVIEW_PLATFORM", "COMMUNITY"}:
                classification = "TRUE_POSITIVE_INDIRECT"
                reason = "third-party/community/app-store evidence mentioning exact brand"
            elif exact_brand_present(combined_text(row), brand):
                classification = "UNRESOLVED"
                reason = "exact brand present but official/independent relationship not demonstrated"
            else:
                classification = "FALSE_POSITIVE_UNRELATED"
                reason = "no reliable brand relationship"

        seen.add(dedupe_key)
        audited.append(
            {
                "audit_index": index,
                "evidence_type": evidence_type,
                "brand_name": brand,
                "classification": classification,
                "audit_reason": reason,
                "title": clean_text(row.get("title")),
                "url": url,
                "domain": clean_text(row.get("domain")) or parse_domain(url),
                "source_category": clean_text(row.get("source_category")),
                "relevance_score": row.get("relevance_score"),
                "result_bucket": clean_text(row.get("result_bucket")),
                "storage_status": clean_text(row.get("storage_status")),
                "query_category": clean_text(row.get("query_category")),
                "query_text": clean_text(row.get("query_text")),
                "brief_quote": clean_text(row.get("brief_quote")),
                "content_excerpt": clean_text(row.get("content"))[:600],
            }
        )
    dataframe = pd.DataFrame(audited)
    invalid = set(dataframe["classification"]) - EVIDENCE_CLASSES if not dataframe.empty else set()
    if invalid:
        raise RuntimeError(f"Clasificaciones no permitidas: {sorted(invalid)}")
    return dataframe


def is_correctly_rejected(row: dict[str, Any]) -> bool:
    status = clean_text(row.get("storage_status"))
    score = row.get("relevance_score")
    try:
        score_value = float(score)
    except (TypeError, ValueError):
        score_value = 0
    return status.startswith("RELEVANCE_BELOW_30") or score_value < 30 or is_homonym(row)[0] or is_unrelated(row)


def official_domain_signals(brand: str, domain: str, accepted_rows: list[dict[str, Any]], ambiguous_rows: list[dict[str, Any]]) -> tuple[set[str], list[str]]:
    rows = [
        row for row in [*accepted_rows, *ambiguous_rows]
        if clean_text(row.get("brand_name")) == brand and (clean_text(row.get("domain")) or parse_domain(clean_text(row.get("url")))) == domain
    ]
    signals: set[str] = set()
    notes = []
    for row in rows:
        url = clean_text(row.get("url"))
        path = urlparse(url).path.lower()
        text = combined_text(row)
        if exact_brand_present(clean_text(row.get("title")), brand) and path in {"", "/"}:
            signals.add("homepage_exact_brand")
        if any(part in path for part in ("terms", "privacy", "refund")) and exact_brand_present(text, brand):
            signals.add("terms_or_privacy_attributable")
        if re.search(rf"\b[A-Z0-9._%+-]+@{re.escape(domain)}\b", text, re.IGNORECASE):
            signals.add("same_domain_email")
        if re.search(r"\b(instagram|facebook|twitter|x.com|linkedin|youtube)\b", text, re.IGNORECASE) and exact_brand_present(text, brand):
            signals.add("coherent_social_links")
        if re.search(r"\b(contact|support|pricing|subscription|whatsapp)\b", text, re.IGNORECASE) and exact_brand_present(text, brand):
            signals.add("consistent_commercial_contact")
        if re.search(r"\b(llc|ltd|inc|company|corporation)\b", text, re.IGNORECASE) and exact_brand_present(text, brand):
            signals.add("corporate_identity")
        notes.append(f"{url} -> {clean_text(row.get('title'))[:120]}")
    return signals, notes


def domain_status_from_signals(brand: str, domain: str, signals: set[str], accepted_audit: pd.DataFrame) -> tuple[str, str]:
    if not domain or domain == "NOT_IDENTIFIED":
        return "NOT_IDENTIFIED", "no candidate domain"
    domain_rows = accepted_audit[(accepted_audit["brand_name"] == brand) & (accepted_audit["domain"] == domain)]
    if not domain_rows.empty and domain_rows["classification"].isin(["FALSE_POSITIVE_RESELLER", "FALSE_POSITIVE_AFFILIATE", "FALSE_POSITIVE_HOMONYM"]).any():
        return "REJECTED", "candidate evidence is reseller/affiliate/homonym"
    if len(signals) >= 3:
        return "PROBABLE", "multiple direct signals, but no independent public confirmation in stored evidence"
    if len(signals) >= 2:
        return "PROBABLE", "two direct signals, not enough for CONFIRMED without independent corroboration"
    if len(signals) == 1:
        return "AMBIGUOUS", "single signal only; name/domain match is insufficient"
    return "REJECTED", "no qualifying official-domain signals beyond nominal match"


def build_brand_summary(
    pilot_df: pd.DataFrame,
    accepted_audit: pd.DataFrame,
    ambiguous_audit: pd.DataFrame,
    rejected_rows: list[dict[str, Any]],
    accepted_rows: list[dict[str, Any]],
    ambiguous_rows: list[dict[str, Any]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rejected_counter = Counter(clean_text(row.get("brand_name")) for row in rejected_rows)
    summary_rows = []
    domain_rows = []
    for _, pilot in pilot_df.iterrows():
        brand = clean_text(pilot["brand_name"])
        accepted_brand = accepted_audit[accepted_audit["brand_name"] == brand]
        ambiguous_brand = ambiguous_audit[ambiguous_audit["brand_name"] == brand]
        accepted_count = int(pilot["accepted_count"])
        ambiguous_count = int(pilot["ambiguous_count"])
        rejected_count = int(pilot["rejected_count"])
        total_raw = int(pilot["total_results"])
        true_positive = int(accepted_brand["classification"].isin(["TRUE_POSITIVE_DIRECT", "TRUE_POSITIVE_INDIRECT"]).sum())
        false_positive = int(accepted_brand["classification"].str.startswith("FALSE_POSITIVE").sum())
        unresolved = int((accepted_brand["classification"] == "UNRESOLVED").sum())
        accepted_precision = round(true_positive / max(len(accepted_brand), 1), 4)
        false_acceptance_rate = round(false_positive / max(len(accepted_brand), 1), 4)
        candidate = clean_text(pilot.get("probable_official_domain")) or OFFICIAL_DOMAIN_CANDIDATES.get(brand, "NOT_IDENTIFIED")
        signals, notes = official_domain_signals(brand, candidate, accepted_rows, ambiguous_rows)
        official_status, official_reason = domain_status_from_signals(brand, candidate, signals, accepted_audit)
        domain_rows.append(
            {
                "brand_name": brand,
                "candidate_domain": candidate,
                "official_domain_evidence_count": len(signals),
                "official_domain_status": official_status,
                "signals": PIPE_SEPARATOR.join(sorted(signals)) if signals else "NOT_FOUND",
                "reason": official_reason,
                "evidence_notes": PIPE_SEPARATOR.join(notes[:8]),
            }
        )
        adjustments = []
        if false_positive:
            adjustments.append("lower or reject reseller/affiliate accepted evidence")
        if unresolved:
            adjustments.append("require policy/contact/corporate corroboration")
        if official_status != "CONFIRMED":
            adjustments.append("do not authorize official domain as confirmed")
        if brand == "Voco TV" and not accepted_brand[accepted_brand["classification"] == "FALSE_POSITIVE_HOMONYM"].empty:
            adjustments.append("tighten Voco hotel/dental negatives")
        key_findings = [
            f"accepted TP={true_positive}",
            f"accepted FP={false_positive}",
            f"official_domain={official_status}",
        ]
        summary_rows.append(
            {
                "brand_name": brand,
                "total_raw_results": total_raw,
                "accepted_count": accepted_count,
                "ambiguous_count": ambiguous_count,
                "rejected_count": rejected_count,
                "accepted_true_positive_count": true_positive,
                "accepted_false_positive_count": false_positive,
                "accepted_unresolved_count": unresolved,
                "accepted_precision": accepted_precision,
                "false_acceptance_rate": false_acceptance_rate,
                "official_domain_candidate": candidate,
                "official_domain_evidence_count": len(signals),
                "official_domain_status": official_status,
                "key_findings": PIPE_SEPARATOR.join(key_findings),
                "required_adjustments": PIPE_SEPARATOR.join(adjustments) if adjustments else "NONE",
                "correctly_rejected_count": rejected_counter.get(brand, 0),
            }
        )
    return pd.DataFrame(summary_rows), pd.DataFrame(domain_rows)


ILLEGAL_EXCEL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]")
MAX_EXCEL_CELL_LENGTH = 32000


def excel_safe_value(value: Any) -> Any:
    if value is None:
        return value
    try:
        if pd.isna(value):
            return value
    except (TypeError, ValueError):
        pass
    if isinstance(value, (dict, list, set, tuple)):
        try:
            if isinstance(value, set):
                value = sorted(value)
            value = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            value = str(value)
    elif not isinstance(value, str):
        return value
    text = ILLEGAL_EXCEL_CHARS_RE.sub("", str(value))
    if len(text) > MAX_EXCEL_CELL_LENGTH:
        suffix = " [TRUNCATED_FOR_EXCEL]"
        text = text[: MAX_EXCEL_CELL_LENGTH - len(suffix)] + suffix
    return text


def excel_safe_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    safe = dataframe.copy()
    safe.columns = [excel_safe_value(column) for column in safe.columns]
    for column in safe.columns:
        if safe[column].dtype == object or pd.api.types.is_string_dtype(safe[column]):
            safe[column] = safe[column].map(excel_safe_value)
    return safe


def write_sheet(writer: pd.ExcelWriter, dataframe: pd.DataFrame, sheet_name: str) -> None:
    safe = excel_safe_dataframe(dataframe)
    safe.to_excel(writer, sheet_name=sheet_name, index=False)
    worksheet = writer.sheets[sheet_name]
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions
    for index, column in enumerate(safe.columns, start=1):
        sample = safe[column].astype(str).head(200) if column in safe else []
        width = max([len(str(column)), *(len(value) for value in sample)], default=10)
        worksheet.column_dimensions[get_column_letter(index)].width = min(max(width + 2, 10), 48)


def build_report(
    summary_df: pd.DataFrame,
    accepted_audit: pd.DataFrame,
    ambiguous_audit: pd.DataFrame,
    rejected_rows: list[dict[str, Any]],
    metrics: dict[str, Any],
    verdict: str,
    recommendation: str,
) -> str:
    lines = [
        "# Pilot V2 accepted evidence audit - 20260714",
        "",
        "## Scope",
        "",
        "- No Tavily calls were executed.",
        "- Audited exactly 50 accepted and 5 ambiguous retained evidences.",
        "- Recalculated precision on retained evidence instead of penalizing correctly rejected raw results.",
        "",
        "## Global metrics",
        "",
        f"- acceptance_rate: {metrics['acceptance_rate']:.4f}",
        f"- retained_rate: {metrics['retained_rate']:.4f}",
        f"- accepted_precision: {metrics['accepted_precision']:.4f}",
        f"- false_acceptance_rate: {metrics['false_acceptance_rate']:.4f}",
        f"- ambiguous_precision: {metrics['ambiguous_precision']:.4f}",
        f"- rejection_selectivity: {metrics['rejection_selectivity']:.4f}",
        f"- verdict: {verdict}",
        f"- recommendation: {recommendation}",
        "",
        "## Brand summary",
        "",
        "| Brand | Accepted precision | False acceptance | Official domain | Status | Key findings |",
        "|---|---:|---:|---|---|---|",
    ]
    for _, row in summary_df.iterrows():
        lines.append(
            f"| {row['brand_name']} | {row['accepted_precision']} | {row['false_acceptance_rate']} | "
            f"{row['official_domain_candidate']} | {row['official_domain_status']} | {row['key_findings']} |"
        )
    lines.extend(
        [
            "",
            "## Voco control",
            "",
            f"- Voco accepted hotel/dental/IHG evidence retained: {'YES' if metrics['voco_homonym_retained'] else 'NO'}",
            "",
            "## Notes",
            "",
            "- CONFIRMED official domains require stronger independent evidence than found in this pilot.",
            "- Reseller/ranking/SEO pages are treated as false accepted evidence, even when they mention the exact brand.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    for path in (INPUT_CSV, INPUT_JSON, INPUT_RAW, INPUT_REJECTED, INPUT_QUERY_LOG):
        if not path.exists():
            raise FileNotFoundError(f"No existe entrada requerida: {path}")
    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    pilot_df = pd.read_csv(INPUT_CSV)
    accepted_rows = data.get("accepted", [])
    ambiguous_rows = data.get("ambiguous", [])
    rejected_rows = read_jsonl(INPUT_REJECTED)
    raw_rows = read_jsonl(INPUT_RAW)
    query_rows = read_jsonl(INPUT_QUERY_LOG)

    if len(accepted_rows) != 50:
        raise RuntimeError(f"Se esperaban 50 aceptadas y se encontraron {len(accepted_rows)}")
    if len(ambiguous_rows) != 5:
        raise RuntimeError(f"Se esperaban 5 ambiguas y se encontraron {len(ambiguous_rows)}")

    accepted_audit = audit_evidence_rows(accepted_rows, "ACCEPTED")
    ambiguous_audit = audit_evidence_rows(ambiguous_rows, "AMBIGUOUS")
    if len(accepted_audit) != 50 or len(ambiguous_audit) != 5:
        raise RuntimeError("La auditoria no conserva exactamente 50 aceptadas y 5 ambiguas.")

    summary_df, domain_df = build_brand_summary(
        pilot_df,
        accepted_audit,
        ambiguous_audit,
        rejected_rows,
        accepted_rows,
        ambiguous_rows,
    )

    accepted_tp = int(accepted_audit["classification"].isin(["TRUE_POSITIVE_DIRECT", "TRUE_POSITIVE_INDIRECT"]).sum())
    accepted_fp = int(accepted_audit["classification"].str.startswith("FALSE_POSITIVE").sum())
    ambiguous_relevant = int(ambiguous_audit["classification"].isin(["TRUE_POSITIVE_DIRECT", "TRUE_POSITIVE_INDIRECT", "UNRESOLVED"]).sum())
    correctly_rejected_count = sum(1 for row in rejected_rows if is_correctly_rejected(row))
    total_raw = len(raw_rows)
    total_accepted = len(accepted_audit)
    total_ambiguous = len(ambiguous_audit)
    total_rejected = len(rejected_rows)
    voco_accepted = accepted_audit[accepted_audit["brand_name"] == "Voco TV"]
    voco_homonym_retained = bool(voco_accepted["classification"].isin(["FALSE_POSITIVE_HOMONYM"]).any())
    official_nominal_only = bool(domain_df["official_domain_status"].eq("CONFIRMED").any())
    reseller_official = bool(
        accepted_audit[
            (accepted_audit["classification"] == "FALSE_POSITIVE_RESELLER")
            & (accepted_audit["domain"].isin(domain_df["candidate_domain"]))
        ].shape[0]
    )
    metrics = {
        "acceptance_rate": total_accepted / max(total_raw, 1),
        "retained_rate": (total_accepted + total_ambiguous) / max(total_raw, 1),
        "accepted_precision": accepted_tp / max(total_accepted, 1),
        "false_acceptance_rate": accepted_fp / max(total_accepted, 1),
        "ambiguous_precision": ambiguous_relevant / max(total_ambiguous, 1),
        "rejection_selectivity": correctly_rejected_count / max(total_rejected, 1),
        "accepted_true_positive": accepted_tp,
        "accepted_false_positive": accepted_fp,
        "correctly_rejected": correctly_rejected_count,
        "voco_homonym_retained": voco_homonym_retained,
        "official_nominal_only": official_nominal_only,
        "reseller_official": reseller_official,
    }
    if (
        metrics["accepted_precision"] >= 0.80
        and metrics["false_acceptance_rate"] <= 0.10
        and not official_nominal_only
        and not voco_homonym_retained
        and not reseller_official
    ):
        verdict = "PASS"
        recommendation = "Autorizar lote 2 con monitoreo."
    elif metrics["accepted_precision"] >= 0.60 and metrics["false_acceptance_rate"] <= 0.25 and not voco_homonym_retained:
        verdict = "PASS_WITH_ADJUSTMENTS"
        recommendation = "No autorizar automaticamente lote 2; aplicar ajustes a revendedores/oficialidad."
    else:
        verdict = "FAIL"
        recommendation = "No autorizar lote 2; ajustar filtros de aceptacion y oficialidad."

    false_positive_df = accepted_audit[accepted_audit["classification"].str.startswith("FALSE_POSITIVE")].copy()
    official_sources_df = accepted_audit[
        accepted_audit["domain"].isin(domain_df["candidate_domain"])
    ].copy()
    reseller_df = accepted_audit[accepted_audit["classification"] == "FALSE_POSITIVE_RESELLER"].copy()
    affiliate_df = accepted_audit[accepted_audit["classification"] == "FALSE_POSITIVE_AFFILIATE"].copy()
    adjustments = {
        "verdict": verdict,
        "recommendation": recommendation,
        "metrics": metrics,
        "filter_adjustments": [
            "Do not auto-accept RESELLER source_category regardless of relevance_score.",
            "Do not auto-confirm official domains from nominal domain match alone.",
            "Require policy/contact/corporate/app-store/independent-reference signals before official domain confirmation.",
            "Keep Voco hotel/dental/IHG negatives active.",
            "Downgrade affiliate/ranking domains to rejected or manual-only review.",
        ],
        "brand_adjustments": summary_df[["brand_name", "required_adjustments"]].to_dict(orient="records"),
    }

    accepted_audit.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    OUTPUT_ADJUSTMENTS.write_text(json.dumps(adjustments, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    OUTPUT_REPORT.write_text(
        build_report(summary_df, accepted_audit, ambiguous_audit, rejected_rows, metrics, verdict, recommendation),
        encoding="utf-8",
    )
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        write_sheet(writer, summary_df, "Resumen por marca")
        write_sheet(writer, accepted_audit, "Aceptadas auditadas")
        write_sheet(writer, ambiguous_audit, "Ambiguas auditadas")
        write_sheet(writer, false_positive_df, "Falsos positivos aceptados")
        write_sheet(writer, domain_df, "Dominios oficiales")
        write_sheet(writer, official_sources_df, "Fuentes oficiales")
        write_sheet(writer, reseller_df, "Revendedores")
        write_sheet(writer, affiliate_df, "Afiliados")
        write_sheet(writer, pd.DataFrame(adjustments["brand_adjustments"]), "Ajustes recomendados")

    print("Auditoria de evidencias aceptadas V2 finalizada.")
    print(f"Aceptadas auditadas: {len(accepted_audit)}")
    print(f"Ambiguas auditadas: {len(ambiguous_audit)}")
    print(f"accepted_precision real: {metrics['accepted_precision']:.4f}")
    print(f"false_acceptance_rate: {metrics['false_acceptance_rate']:.4f}")
    print(f"ambiguous_precision: {metrics['ambiguous_precision']:.4f}")
    print(f"rejection_selectivity: {metrics['rejection_selectivity']:.4f}")
    print(f"Dictamen global: {verdict}")
    print(f"Recomendacion lote 2: {recommendation}")
    print(f"CSV: {OUTPUT_CSV}")
    print(f"Excel: {OUTPUT_XLSX}")
    print(f"Reporte: {OUTPUT_REPORT}")
    print(f"Ajustes JSON: {OUTPUT_ADJUSTMENTS}")


if __name__ == "__main__":
    main()
