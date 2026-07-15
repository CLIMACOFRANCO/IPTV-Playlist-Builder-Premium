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
OUTPUT_DIR = PROJECT_ROOT / "research" / "output" / "best_iptv_2026"

INPUT_BRANDS = OUTPUT_DIR / "brands_cleaned_20260713.csv"
INPUT_CORPUS_JSON = OUTPUT_DIR / "tavily_corpus_20260713_222351.json"

OUTPUT_CSV = OUTPUT_DIR / "top50_due_diligence_preliminary_20260713.csv"
OUTPUT_XLSX = OUTPUT_DIR / "top50_due_diligence_preliminary_20260713.xlsx"
OUTPUT_REPORT = OUTPUT_DIR / "top50_due_diligence_report_20260713.md"
OUTPUT_QUERY_PLAN = OUTPUT_DIR / "top50_query_plan_20260713.json"

PIPE_SEPARATOR = " | "
NOT_FOUND = "NOT_FOUND"
NOT_DEMONSTRATED = "NOT_DEMONSTRATED"
AMBIGUOUS = "AMBIGUOUS"
NOT_APPLICABLE = "NOT_APPLICABLE"

CONFIDENCE_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

FREE_EMAIL_DOMAINS = {
    "aol.com",
    "gmail.com",
    "hotmail.com",
    "icloud.com",
    "live.com",
    "mail.com",
    "outlook.com",
    "proton.me",
    "protonmail.com",
    "yahoo.com",
}

NON_OFFICIAL_DOMAINS = {
    "apps.apple.com",
    "calrecycle.ca.gov",
    "cochranelibrary.com",
    "facebook.com",
    "github.com",
    "hackmd.io",
    "hub.spark.ngo",
    "indiehackers.com",
    "linkedin.com",
    "medium.com",
    "myportal.dfs.ny.gov",
    "news.ycombinator.com",
    "physics.utah.edu",
    "play.google.com",
    "prlog.org",
    "quora.com",
    "reddit.com",
    "researchhub.com",
    "slideshare.net",
    "storage.prod.researchhub.com",
    "t.me",
    "trustpilot.com",
    "tus.santander.es",
    "youtube.com",
}

PROMOTIONAL_DOMAIN_KEYWORDS = {
    "bestiptv",
    "best-iptv",
    "free-trial",
    "freetrial",
    "iptvfinder",
    "iptvrankings",
    "iptvreviews",
    "iptvserviceradar",
    "iptvservice",
    "iptvprovider",
    "topiptv",
}

SELF_PUBLISHING_DOMAINS = {
    "github.com",
    "indiehackers.com",
    "medium.com",
    "prlog.org",
    "sites.google.com",
    "slideshare.net",
}

USER_DOMAINS = {
    "facebook.com",
    "news.ycombinator.com",
    "quora.com",
    "reddit.com",
    "t.me",
    "trustpilot.com",
}

VIDEO_DOMAINS = {"youtube.com", "youtu.be"}
APP_STORE_DOMAINS = {
    "apps.apple.com",
    "play.google.com",
    "amazon.com",
    "amazon.co.uk",
}

REVIEW_OR_DIRECTORY_DOMAINS = {
    "bestiptvfinder.com",
    "geekvibesnation.com",
    "guru99.com",
    "iptvrankings.com",
    "iptvserviceradar.com",
    "softwaretestinghelp.com",
    "techradar.com",
    "topiptvreviews.com",
    "troypoint.com",
}

INDEPENDENT_REFERENCE_DOMAINS = {
    "en.wikipedia.org",
    "linkedin.com",
}

COUNTRIES = [
    "Argentina",
    "Australia",
    "Brazil",
    "Canada",
    "France",
    "Germany",
    "India",
    "Italy",
    "Mexico",
    "Netherlands",
    "Portugal",
    "Spain",
    "United Kingdom",
    "United States",
    "USA",
]

QUERY_CATEGORIES = [
    "identity",
    "official_domain",
    "corporate_registry",
    "terms_privacy",
    "app_stores",
    "licensing",
    "legal_history",
    "trustpilot",
    "reddit",
    "youtube",
    "reseller_panel",
    "technology",
]


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return re.sub(r"\s+", " ", str(value)).strip()


def split_pipe(value: Any) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    return [part.strip() for part in text.split(PIPE_SEPARATOR) if part.strip()]


def parse_domain(url: str) -> str:
    try:
        domain = urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""
    return domain


def registrable_slug(domain: str) -> str:
    domain = domain.lower().removeprefix("www.")
    parts = [part for part in domain.split(".") if part]
    if len(parts) >= 3 and parts[-2] in {"co", "com", "net", "org"}:
        root = parts[-3]
    elif len(parts) >= 2:
        root = parts[-2]
    elif parts:
        root = parts[0]
    else:
        root = domain
    return re.sub(r"[^a-z0-9]+", "", root)


def compact(value: str) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"\b(iptv|tv|ott|hd|4k|plus|pro|stream|streams|service|services)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def compact_aliases(brand: str, aliases: str) -> set[str]:
    values = {compact(brand), re.sub(r"[^a-z0-9]+", "", brand.lower())}
    for alias in split_pipe(aliases):
        values.add(compact(alias))
        values.add(re.sub(r"[^a-z0-9]+", "", alias.lower()))
    return {value for value in values if len(value) >= 4}


def source_text(record: dict[str, Any]) -> str:
    return " ".join(
        clean_text(record.get(key))
        for key in ("title", "summary", "raw_content", "query")
        if clean_text(record.get(key))
    )


def load_corpus_by_url() -> dict[str, dict[str, Any]]:
    records = json.loads(INPUT_CORPUS_JSON.read_text(encoding="utf-8"))
    by_url: dict[str, dict[str, Any]] = {}
    for record in records:
        url = clean_text(record.get("url"))
        if not url:
            continue
        record = dict(record)
        record["domain"] = clean_text(record.get("domain")) or parse_domain(url)
        by_url[url] = record
    return by_url


def select_top50_providers(brands_df: pd.DataFrame) -> pd.DataFrame:
    providers = brands_df[brands_df["category"] == "PROVIDER"].copy()
    providers["confidence_rank"] = providers["confidence"].map(CONFIDENCE_ORDER).fillna(99)
    providers = providers.sort_values(
        by=[
            "confidence_rank",
            "recurrence_score",
            "unique_domains_count",
            "platform_count",
            "evidence_url_count",
            "canonical_brand",
        ],
        ascending=[True, False, False, False, False, True],
    )
    providers = providers.drop_duplicates(subset=["canonical_brand"]).head(50).copy()
    providers.insert(0, "rank", range(1, len(providers) + 1))
    return providers


def classify_domain(domain: str, official_domain: str = "") -> str:
    domain = domain.lower().removeprefix("www.")
    if official_domain and domain == official_domain:
        return "provider_or_probable_official"
    if domain in APP_STORE_DOMAINS:
        return "app_marketplace"
    if domain in USER_DOMAINS:
        return "user_generated_or_reviews"
    if domain in VIDEO_DOMAINS:
        return "video_platform"
    if domain in SELF_PUBLISHING_DOMAINS or domain.endswith(".s3.amazonaws.com"):
        return "self_publishing_or_promotional"
    if domain in REVIEW_OR_DIRECTORY_DOMAINS:
        return "affiliate_review_or_directory"
    if domain in INDEPENDENT_REFERENCE_DOMAINS:
        return "independent_reference"
    if any(keyword in domain for keyword in PROMOTIONAL_DOMAIN_KEYWORDS):
        return "affiliate_review_or_directory"
    if domain.endswith(".gov"):
        return "public_document_repository"
    return "unclassified_web_source"


def is_promotional_category(category: str) -> bool:
    return category in {
        "affiliate_review_or_directory",
        "provider_or_probable_official",
        "self_publishing_or_promotional",
        "video_platform",
    }


def is_independent_category(category: str) -> bool:
    return category in {
        "app_marketplace",
        "independent_reference",
        "public_document_repository",
        "user_generated_or_reviews",
    }


def candidate_official_domain(row: pd.Series, evidence: list[dict[str, Any]]) -> tuple[str, str]:
    aliases = compact_aliases(row["canonical_brand"], row.get("aliases", ""))
    candidates: Counter[str] = Counter()
    strong_candidates: Counter[str] = Counter()

    for item in evidence:
        url = item["url"]
        domain = item["domain"]
        if not domain or domain in NON_OFFICIAL_DOMAINS:
            continue
        if any(keyword in domain for keyword in PROMOTIONAL_DOMAIN_KEYWORDS):
            continue

        slug = registrable_slug(domain)
        if not slug or len(slug) < 4:
            continue

        for alias_slug in aliases:
            if slug == alias_slug or slug in alias_slug or alias_slug in slug:
                candidates[domain] += 1
                if slug == alias_slug or alias_slug in slug:
                    strong_candidates[domain] += 1

        path = urlparse(url).path.lower()
        if any(part in path for part in ("terms", "privacy", "refund", "contact", "about")):
            candidates[domain] += 1

    if not candidates:
        return NOT_FOUND, "NOT_IDENTIFIED"

    domain, count = candidates.most_common(1)[0]
    unique_candidate_count = len(candidates)
    if strong_candidates[domain] >= 2 or (count >= 2 and unique_candidate_count == 1):
        return domain, "HIGH"
    if strong_candidates[domain] >= 1 or count >= 2:
        return domain, "MEDIUM"
    return domain, "LOW"


def detect_url_by_path(evidence: list[dict[str, Any]], official_domain: str, keywords: tuple[str, ...]) -> str:
    for item in evidence:
        url = item["url"]
        domain = item["domain"]
        if official_domain not in {NOT_FOUND, AMBIGUOUS} and domain != official_domain:
            continue
        path = urlparse(url).path.lower()
        if any(keyword in path for keyword in keywords):
            return url
    return NOT_FOUND


def first_regex(pattern: str, text: str, flags: int = re.IGNORECASE) -> str:
    match = re.search(pattern, text, flags)
    return match.group(0).strip() if match else NOT_FOUND


def extract_company_name(text: str, brand: str) -> str:
    brand_pattern = re.escape(clean_text(brand))
    patterns = [
        rf"{brand_pattern}\s+(LLC|L\.L\.C\.|Ltd\.?|Limited|Inc\.?|Corporation|Corp\.?|S\.A\.|S\.L\.)",
        r"\b[A-Z][A-Za-z0-9&.,' -]{2,80}\s+(LLC|L\.L\.C\.|Ltd\.?|Limited|Inc\.?|Corporation|Corp\.?|S\.A\.|S\.L\.)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return clean_text(match.group(0))
    return NOT_FOUND


def extract_email(text: str, official_domain: str) -> str:
    emails = sorted(set(re.findall(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.IGNORECASE)))
    if not emails:
        return NOT_FOUND

    if official_domain not in {NOT_FOUND, AMBIGUOUS}:
        official_root = registrable_slug(official_domain)
        for email in emails:
            email_domain = email.split("@", 1)[1].lower()
            if registrable_slug(email_domain) == official_root and email_domain not in FREE_EMAIL_DOMAINS:
                return email

    corporate = [email for email in emails if email.split("@", 1)[1].lower() not in FREE_EMAIL_DOMAINS]
    if len(corporate) == 1:
        return corporate[0]
    if len(corporate) > 1:
        return AMBIGUOUS
    return NOT_FOUND


def extract_phone(text: str) -> str:
    match = re.search(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)", text)
    if not match:
        return NOT_FOUND
    phone = clean_text(match.group(0))
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 8 or len(digits) > 15:
        return NOT_FOUND
    return phone


def extract_country(text: str) -> str:
    found = []
    for country in COUNTRIES:
        if re.search(rf"\b{re.escape(country)}\b", text, re.IGNORECASE):
            found.append(country)
    found = sorted(set("United States" if country == "USA" else country for country in found))
    if not found:
        return NOT_FOUND
    if len(found) > 3:
        return AMBIGUOUS
    return PIPE_SEPARATOR.join(found)


def extract_claim(
    evidence: list[dict[str, Any]],
    pattern: str,
    label: str,
    official_domain: str,
) -> str:
    for item in evidence:
        text = item["text"]
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        source_category = classify_domain(item["domain"], official_domain)
        if source_category == "provider_or_probable_official":
            prefix = "PROVIDER_CLAIM"
        elif source_category == "user_generated_or_reviews":
            prefix = "USER_COMMENT"
        elif source_category in {"independent_reference", "public_document_repository", "app_marketplace"}:
            prefix = "INDEPENDENT_EVIDENCE"
        else:
            prefix = "PROMOTIONAL_SOURCE_CLAIM"
        return f"{prefix}: {clean_text(match.group(0))} ({label})"
    return NOT_DEMONSTRATED


def signal(text: str, patterns: tuple[str, ...]) -> str:
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return "DETECTED_IN_EVIDENCE"
    return NOT_DEMONSTRATED


def find_store_url(evidence: list[dict[str, Any]], domain: str) -> str:
    for item in evidence:
        if item["domain"] == domain:
            return item["url"]
    return NOT_FOUND


def promotional_and_independent_ratios(evidence: list[dict[str, Any]], official_domain: str) -> tuple[float, float, Counter[str]]:
    categories = Counter(classify_domain(item["domain"], official_domain) for item in evidence)
    total = max(len(evidence), 1)
    promotional = sum(count for category, count in categories.items() if is_promotional_category(category))
    independent = sum(count for category, count in categories.items() if is_independent_category(category))
    return round(promotional / total, 3), round(independent / total, 3), categories


def licensing_status(licensing_claim: str, legal_signal: str, independent_ratio: float) -> str:
    if legal_signal == "DETECTED_IN_EVIDENCE" and independent_ratio > 0:
        return "CONTRADICTED_BY_PUBLIC_EVIDENCE"
    if licensing_claim != NOT_DEMONSTRATED:
        return "CLAIMED_NOT_VERIFIED"
    return "NOT_DEMONSTRATED"


def adverse_legal_signal(evidence: list[dict[str, Any]], official_domain: str, brand: str, aliases: str) -> str:
    strong_patterns = (
        r"\btakedown\b",
        r"\bdmca\b",
        r"\blawsuit\b",
        r"\bcourt order\b",
        r"\bseized\b",
        r"\bshutdown\b",
        r"\bshut down\b",
    )
    for item in evidence:
        source_category = classify_domain(item["domain"], official_domain)
        if is_promotional_category(source_category):
            continue
        text = " ".join(clean_text(item.get(field)) for field in ("title", "summary"))
        compact_text = re.sub(r"[^a-z0-9]+", "", text.lower())
        brand_tokens = compact_aliases(brand, aliases)
        brand_mentioned = any(token in compact_text for token in brand_tokens)
        if brand_mentioned and any(re.search(pattern, text, re.IGNORECASE) for pattern in strong_patterns):
            return "DETECTED_IN_EVIDENCE"
    return NOT_DEMONSTRATED


def transparency_score(fields: dict[str, Any]) -> int:
    score = 0
    independent_ratio = float(fields["independent_source_ratio"])

    if fields["company_status"] == "IDENTIFIED" and independent_ratio > 0:
        score += 15
    if fields["country"] not in {NOT_FOUND, AMBIGUOUS} and fields["physical_address"] not in {NOT_FOUND, AMBIGUOUS} and independent_ratio > 0:
        score += 10
    if fields["corporate_email"] not in {NOT_FOUND, AMBIGUOUS} and fields["corporate_phone"] not in {NOT_FOUND, AMBIGUOUS} and independent_ratio > 0:
        score += 5
    if fields["terms_url"] != NOT_FOUND and fields["privacy_url"] != NOT_FOUND and independent_ratio > 0:
        score += 10
    if fields["refund_policy_url"] != NOT_FOUND and independent_ratio > 0:
        score += 5
    if independent_ratio > 0 and (
        fields["paypal_signal"] == "DETECTED_IN_EVIDENCE"
        or fields["card_payment_signal"] == "DETECTED_IN_EVIDENCE"
    ):
        score += 10
    if fields["app_store_presence"] == "DETECTED_IN_EVIDENCE":
        score += 10
    if fields["licensing_evidence_status"] == "PUBLICLY_CONFIRMED":
        score += 20
    if independent_ratio >= 0.25:
        score += 10
    if fields["legal_or_takedown_signal"] == NOT_DEMONSTRATED and independent_ratio >= 0.25:
        score += 5
    return max(0, min(100, score))


def risk_and_status(fields: dict[str, Any]) -> tuple[str, str]:
    if fields["legal_or_takedown_signal"] == "DETECTED_IN_EVIDENCE":
        return "HIGH", "HIGH_RISK"

    identity_unresolved = fields["company_status"] == "NOT_IDENTIFIED"
    domain_unresolved = fields["official_domain_confidence"] in {"LOW", "NOT_IDENTIFIED"}
    if fields["evidence_url_count"] < 3 or fields["confidence"] == "LOW":
        return "MEDIUM", "INSUFFICIENT_EVIDENCE"
    if identity_unresolved or domain_unresolved:
        return "MEDIUM", "NEEDS_IDENTITY_RESOLUTION"
    return "LOW", "PROCEED_TO_EXTERNAL_VERIFICATION"


def missing_information(fields: dict[str, Any]) -> list[str]:
    checks = [
        "probable_official_domain",
        "company_name",
        "country",
        "physical_address",
        "corporate_email",
        "corporate_phone",
        "terms_url",
        "privacy_url",
        "refund_policy_url",
        "licensing_claim",
    ]
    missing = []
    for field in checks:
        if fields[field] in {NOT_FOUND, NOT_DEMONSTRATED, AMBIGUOUS, "NOT_IDENTIFIED"}:
            missing.append(field)
    return missing


def key_findings(fields: dict[str, Any]) -> str:
    findings = []
    if fields["probable_official_domain"] == NOT_FOUND:
        findings.append("official domain not identified from collected evidence")
    else:
        findings.append(f"probable official domain: {fields['probable_official_domain']} ({fields['official_domain_confidence']})")

    if fields["company_status"] == "NOT_IDENTIFIED":
        findings.append("legal entity not identified")
    if fields["licensing_evidence_status"] != "PUBLICLY_CONFIRMED":
        findings.append(f"licensing evidence: {fields['licensing_evidence_status']}")

    signal_bits = []
    for field in ("reseller_signal", "panel_signal", "m3u_signal", "xtream_signal", "free_trial_signal"):
        if fields[field] == "DETECTED_IN_EVIDENCE":
            signal_bits.append(field.replace("_signal", ""))
    if signal_bits:
        findings.append("technical/commercial signals detected: " + ", ".join(signal_bits))

    if fields["legal_or_takedown_signal"] == "DETECTED_IN_EVIDENCE":
        findings.append("legal/takedown language detected in existing evidence")

    return "; ".join(findings)


def build_brand_evidence(row: pd.Series, corpus_by_url: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    evidence = []
    for url in split_pipe(row.get("evidence_urls")):
        record = corpus_by_url.get(url, {})
        domain = clean_text(record.get("domain")) or parse_domain(url)
        text = source_text(record)
        evidence.append(
            {
                "rank": int(row["rank"]),
                "brand_name": row["canonical_brand"],
                "url": url,
                "domain": domain,
                "source_platform": clean_text(record.get("source_platform")) or "UNKNOWN",
                "title": clean_text(record.get("title")),
                "summary": clean_text(record.get("summary")),
                "published_date": clean_text(record.get("published_date")),
                "score": record.get("score", ""),
                "matched_queries": PIPE_SEPARATOR.join(record.get("matched_queries", []))
                if isinstance(record.get("matched_queries"), list)
                else clean_text(record.get("matched_queries")),
                "text": text,
            }
        )
    return evidence


def build_due_diligence_row(row: pd.Series, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    brand_name = clean_text(row["canonical_brand"])
    mentioned_domains = sorted({item["domain"] for item in evidence if item["domain"]})
    probable_domain, domain_confidence = candidate_official_domain(row, evidence)
    all_text = " ".join(item["text"] for item in evidence)
    official_text = " ".join(item["text"] for item in evidence if item["domain"] == probable_domain)
    text_for_identity = official_text or all_text

    promotional_ratio, independent_ratio, source_categories = promotional_and_independent_ratios(evidence, probable_domain)

    google_play_url = find_store_url(evidence, "play.google.com")
    apple_app_store_url = find_store_url(evidence, "apps.apple.com")
    amazon_appstore_url = next((item["url"] for item in evidence if item["domain"].startswith("amazon.")), NOT_FOUND)
    app_store_presence = "DETECTED_IN_EVIDENCE" if any(
        value != NOT_FOUND for value in (google_play_url, apple_app_store_url, amazon_appstore_url)
    ) else NOT_FOUND

    terms_url = detect_url_by_path(evidence, probable_domain, ("terms", "terms-of-service", "terms-and-conditions"))
    privacy_url = detect_url_by_path(evidence, probable_domain, ("privacy", "privacy-policy"))
    refund_policy_url = detect_url_by_path(evidence, probable_domain, ("refund", "cancellation", "return"))

    company_name = extract_company_name(text_for_identity, brand_name)
    corporate_email = extract_email(text_for_identity, probable_domain)
    corporate_phone = extract_phone(text_for_identity)
    country = extract_country(text_for_identity)
    physical_address = NOT_FOUND

    if company_name != NOT_FOUND and probable_domain != NOT_FOUND:
        company_status = "IDENTIFIED"
    elif company_name != NOT_FOUND or probable_domain != NOT_FOUND or corporate_email != NOT_FOUND:
        company_status = "PARTIALLY_IDENTIFIED"
    else:
        company_status = "NOT_IDENTIFIED"

    fields: dict[str, Any] = {
        "rank": int(row["rank"]),
        "brand_name": brand_name,
        "aliases": clean_text(row.get("aliases")),
        "category": clean_text(row.get("category")),
        "confidence": clean_text(row.get("confidence")),
        "recurrence_score": row.get("recurrence_score"),
        "source_count": int(row.get("source_count")),
        "unique_domains_count": int(row.get("unique_domains_count")),
        "platform_count": int(row.get("platform_count")),
        "evidence_url_count": int(row.get("evidence_url_count")),
        "mentioned_domains": PIPE_SEPARATOR.join(mentioned_domains),
        "probable_official_domain": probable_domain,
        "official_domain_confidence": domain_confidence,
        "source_platforms": clean_text(row.get("source_platforms")),
        "latest_source_date": clean_text(row.get("latest_published_date")) or NOT_FOUND,
        "company_name": company_name,
        "company_status": company_status,
        "country": country,
        "physical_address": physical_address,
        "corporate_email": corporate_email,
        "corporate_phone": corporate_phone,
        "terms_url": terms_url,
        "privacy_url": privacy_url,
        "refund_policy_url": refund_policy_url,
        "app_store_presence": app_store_presence,
        "google_play_url": google_play_url,
        "apple_app_store_url": apple_app_store_url,
        "amazon_appstore_url": amazon_appstore_url,
        "samsung_store_presence": "DETECTED_IN_EVIDENCE" if re.search(r"\bsamsung\b", all_text, re.IGNORECASE) else NOT_FOUND,
        "lg_store_presence": "DETECTED_IN_EVIDENCE" if re.search(r"\blg\b", all_text, re.IGNORECASE) else NOT_FOUND,
        "android_apk_only_signal": signal(all_text, (r"\bapk\b", r"\bsideload")),
        "reseller_signal": signal(all_text, (r"\breseller\b", r"\breselling\b")),
        "panel_signal": signal(all_text, (r"\bpanel\b", r"\badmin panel\b")),
        "m3u_signal": signal(all_text, (r"\bm3u\b", r"\bm3u8\b")),
        "xtream_signal": signal(all_text, (r"\bxtream\b", r"\bxtream codes\b", r"\bxc api\b")),
        "free_trial_signal": signal(all_text, (r"\bfree trial\b", r"\btrial\b")),
        "crypto_payment_signal": signal(all_text, (r"\bcrypto\b", r"\bbitcoin\b", r"\bbtc\b", r"\busdt\b")),
        "paypal_signal": signal(all_text, (r"\bpaypal\b",)),
        "card_payment_signal": signal(all_text, (r"\bcredit card\b", r"\bdebit card\b", r"\bvisa\b", r"\bmastercard\b", r"\bstripe\b")),
        "channel_count_claim": extract_claim(evidence, r"\b\d{1,3}(?:,\d{3})+\+?\s*(?:live\s*)?channels\b|\b\d{4,}\+?\s*(?:live\s*)?channels\b", "channel count", probable_domain),
        "vod_count_claim": extract_claim(evidence, r"\b\d{1,3}(?:,\d{3})+\+?\s*(?:vod|movies|series)\b|\b\d{4,}\+?\s*(?:vod|movies|series)\b", "VOD count", probable_domain),
        "uptime_claim": extract_claim(evidence, r"\b99(?:\.\d+)?%\s*(?:uptime|stable|availability)\b|\banti[- ]?freeze\b", "uptime/stability", probable_domain),
        "licensing_claim": extract_claim(evidence, r"\blicen[cs]ed\b|\blicen[cs]e\b|\bofficial rights\b|\bbroadcast rights\b|\blegally\b|\blegal\s+(?:service|provider|streaming|iptv)\b", "licensing/legal claim", probable_domain),
        "legal_or_takedown_signal": adverse_legal_signal(evidence, probable_domain, brand_name, clean_text(row.get("aliases"))),
        "trustpilot_signal": "DETECTED_IN_EVIDENCE" if "trustpilot.com" in mentioned_domains else NOT_FOUND,
        "reddit_signal": "DETECTED_IN_EVIDENCE" if "reddit.com" in mentioned_domains else NOT_FOUND,
        "youtube_signal": "DETECTED_IN_EVIDENCE" if any(domain in VIDEO_DOMAINS for domain in mentioned_domains) else NOT_FOUND,
        "promotional_source_ratio": promotional_ratio,
        "independent_source_ratio": independent_ratio,
        "evidence_urls": clean_text(row.get("evidence_urls")),
    }

    fields["licensing_evidence_status"] = licensing_status(
        fields["licensing_claim"],
        fields["legal_or_takedown_signal"],
        independent_ratio,
    )
    fields["transparency_score_preliminary"] = transparency_score(fields)
    fields["risk_level_preliminary"], fields["due_diligence_status"] = risk_and_status(fields)
    missing = missing_information(fields)
    fields["key_findings"] = key_findings(fields)
    fields["missing_information"] = PIPE_SEPARATOR.join(missing) if missing else NOT_APPLICABLE
    fields["_source_categories"] = source_categories
    return fields


def build_query_plan(due_diligence_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    plan = []
    for row in due_diligence_rows:
        brand = row["brand_name"]
        aliases = split_pipe(row.get("aliases"))
        alias_query = " OR ".join(f'"{alias}"' for alias in aliases[:3]) or f'"{brand}"'
        official_domain = row["probable_official_domain"]
        domain_part = "" if official_domain == NOT_FOUND else f" site:{official_domain}"

        queries = {
            "identity": [
                f'"{brand}" company legal entity',
                f'"{brand}" contact address email',
                f'({alias_query}) "about us"',
            ],
            "official_domain": [
                f'"{brand}" official website',
                f'"{brand}" IPTV official domain',
                f'({alias_query}) "official"',
            ],
            "corporate_registry": [
                f'"{brand}" LLC OR Ltd OR Inc',
                f'"{brand}" company registration',
                f'"{brand}" corporate registry',
            ],
            "terms_privacy": [
                f'"{brand}" terms of service',
                f'"{brand}" privacy policy',
                f'"{brand}" refund policy',
            ],
            "app_stores": [
                f'site:play.google.com "{brand}"',
                f'site:apps.apple.com "{brand}"',
                f'site:amazon.com "{brand}" IPTV app',
            ],
            "licensing": [
                f'"{brand}" licensing broadcast rights',
                f'"{brand}" licensed IPTV',
                f'"{brand}" copyright compliance',
            ],
            "legal_history": [
                f'"{brand}" lawsuit OR court OR takedown OR DMCA',
                f'"{brand}" piracy OR illegal IPTV',
                f'"{brand}" shutdown OR seized',
            ],
            "trustpilot": [
                f'site:trustpilot.com/review "{brand}"',
                f'"{brand}" Trustpilot',
            ],
            "reddit": [
                f'site:reddit.com "{brand}" IPTV',
                f'site:reddit.com "{brand}" review',
            ],
            "youtube": [
                f'site:youtube.com "{brand}" IPTV review',
                f'site:youtube.com "{brand}" setup',
            ],
            "reseller_panel": [
                f'"{brand}" reseller panel',
                f'"{brand}" IPTV panel',
                f'"{brand}" reseller program',
            ],
            "technology": [
                f'"{brand}" Xtream Codes M3U',
                f'"{brand}" APK Android',
                f'"{brand}" EPG API',
            ],
        }

        if domain_part:
            queries["terms_privacy"].extend(
                [
                    f'site:{official_domain} terms privacy',
                    f'site:{official_domain} refund',
                ]
            )

        plan.append(
            {
                "rank": row["rank"],
                "brand_name": brand,
                "probable_official_domain": official_domain,
                "official_domain_confidence": row["official_domain_confidence"],
                "due_diligence_status": row["due_diligence_status"],
                "queries": queries,
            }
        )
    return plan


def flatten_query_plan(query_plan: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for brand_plan in query_plan:
        for category in QUERY_CATEGORIES:
            for query in brand_plan["queries"][category]:
                rows.append(
                    {
                        "rank": brand_plan["rank"],
                        "brand_name": brand_plan["brand_name"],
                        "query_category": category,
                        "query": query,
                        "execute_now": "NO",
                    }
                )
    return pd.DataFrame(rows)


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
        sample = dataframe[column].astype(str).head(200) if column in dataframe else []
        max_len = max([len(str(column)), *(len(value) for value in sample)], default=10)
        worksheet.column_dimensions[get_column_letter(index)].width = min(max(max_len + 2, 10), 48)


def build_report(
    matrix_df: pd.DataFrame,
    domain_df: pd.DataFrame,
    query_plan: list[dict[str, Any]],
) -> str:
    status_counts = matrix_df["due_diligence_status"].value_counts().sort_index()
    risk_counts = matrix_df["risk_level_preliminary"].value_counts().sort_index()
    official_counts = matrix_df["official_domain_confidence"].value_counts().sort_index()
    source_categories = domain_df["source_category"].value_counts().sort_index()

    lines = [
        "# Top 50 IPTV/OTT provider due diligence preliminar - 20260713",
        "",
        "## Alcance",
        "",
        "- La matriz usa exclusivamente `brands_cleaned_20260713.csv` y `tavily_corpus_20260713_222351.json`.",
        "- No se ejecutaron nuevas consultas Tavily.",
        "- La presencia de M3U, Xtream, APK, criptomonedas o falta de datos no se usa para afirmar legalidad o ilegalidad.",
        "- `probable_official_domain` es una inferencia conservadora por similitud de dominio y no prueba propiedad del dominio.",
        "",
        "## Totales",
        "",
        f"- Marcas seleccionadas: {len(matrix_df)}",
        f"- Marcas unicas: {matrix_df['brand_name'].nunique()}",
        f"- Consultas futuras preparadas: {sum(len(queries) for item in query_plan for queries in item['queries'].values())}",
        "",
        "## Due diligence status",
        "",
        "| Status | Marcas |",
        "|---|---:|",
    ]
    for status, count in status_counts.items():
        lines.append(f"| {status} | {count} |")

    lines.extend(["", "## Riesgo preliminar", "", "| Riesgo | Marcas |", "|---|---:|"])
    for risk, count in risk_counts.items():
        lines.append(f"| {risk} | {count} |")

    lines.extend(["", "## Dominio oficial probable", "", "| Confianza | Marcas |", "|---|---:|"])
    for confidence, count in official_counts.items():
        lines.append(f"| {confidence} | {count} |")

    lines.extend(["", "## Clasificacion documentada de dominios", "", "| Categoria | Dominios-marca |", "|---|---:|"])
    for category, count in source_categories.items():
        lines.append(f"| {category} | {count} |")

    lines.extend(
        [
            "",
            "Categorias consideradas promocionales para `promotional_source_ratio`: `provider_or_probable_official`, `affiliate_review_or_directory`, `self_publishing_or_promotional`, `video_platform`.",
            "",
            "Categorias consideradas independientes para `independent_source_ratio`: `user_generated_or_reviews`, `independent_reference`, `public_document_repository`, `app_marketplace`.",
            "",
            "## Top 50 resumen",
            "",
            "| Rank | Marca | Status | Riesgo | Score transparencia | Dominio probable | Hallazgos clave |",
            "|---:|---|---|---|---:|---|---|",
        ]
    )

    for _, row in matrix_df.iterrows():
        findings = str(row["key_findings"]).replace("|", "/")
        lines.append(
            f"| {row['rank']} | {row['brand_name']} | {row['due_diligence_status']} | "
            f"{row['risk_level_preliminary']} | {row['transparency_score_preliminary']} | "
            f"{row['probable_official_domain']} | {findings} |"
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    for path in (INPUT_BRANDS, INPUT_CORPUS_JSON):
        if not path.exists():
            raise FileNotFoundError(f"No existe el archivo requerido: {path}")

    brands_df = pd.read_csv(INPUT_BRANDS)
    corpus_by_url = load_corpus_by_url()
    selected = select_top50_providers(brands_df)

    if selected["canonical_brand"].nunique() != 50:
        raise RuntimeError("La seleccion Top 50 no contiene 50 marcas unicas.")

    matrix_rows = []
    evidence_rows = []
    domain_rows = []
    missing_rows = []

    for _, row in selected.iterrows():
        evidence = build_brand_evidence(row, corpus_by_url)
        matrix_row = build_due_diligence_row(row, evidence)
        matrix_rows.append(matrix_row)

        for item in evidence:
            source_category = classify_domain(item["domain"], matrix_row["probable_official_domain"])
            evidence_rows.append(
                {
                    "rank": item["rank"],
                    "brand_name": item["brand_name"],
                    "url": item["url"],
                    "domain": item["domain"],
                    "source_category": source_category,
                    "source_platform": item["source_platform"],
                    "title": item["title"],
                    "summary": item["summary"],
                    "published_date": item["published_date"],
                    "score": item["score"],
                    "matched_queries": item["matched_queries"],
                }
            )

        domain_counts = Counter(item["domain"] for item in evidence if item["domain"])
        for domain, count in sorted(domain_counts.items()):
            source_category = classify_domain(domain, matrix_row["probable_official_domain"])
            domain_rows.append(
                {
                    "rank": matrix_row["rank"],
                    "brand_name": matrix_row["brand_name"],
                    "domain": domain,
                    "url_count": count,
                    "source_category": source_category,
                    "is_promotional_for_ratio": "YES" if is_promotional_category(source_category) else "NO",
                    "is_independent_for_ratio": "YES" if is_independent_category(source_category) else "NO",
                    "probable_official_domain": matrix_row["probable_official_domain"],
                }
            )

        for field in split_pipe(matrix_row["missing_information"]):
            if field != NOT_APPLICABLE:
                missing_rows.append(
                    {
                        "rank": matrix_row["rank"],
                        "brand_name": matrix_row["brand_name"],
                        "missing_field": field,
                        "reason": "No sufficient evidence in collected corpus.",
                    }
                )

    matrix_df = pd.DataFrame(matrix_rows).drop(columns=["_source_categories"])
    evidence_df = pd.DataFrame(evidence_rows).drop_duplicates()
    domain_df = pd.DataFrame(domain_rows)
    missing_df = pd.DataFrame(missing_rows)
    query_plan = build_query_plan(matrix_rows)
    plan_df = flatten_query_plan(query_plan)

    expected_statuses = {
        "PROCEED_TO_EXTERNAL_VERIFICATION",
        "NEEDS_IDENTITY_RESOLUTION",
        "HIGH_RISK",
        "INSUFFICIENT_EVIDENCE",
    }
    actual_statuses = set(matrix_df["due_diligence_status"])
    if not actual_statuses <= expected_statuses:
        raise RuntimeError(f"Status inesperados: {sorted(actual_statuses - expected_statuses)}")

    expected_licensing = {
        "PUBLICLY_CONFIRMED",
        "CLAIMED_NOT_VERIFIED",
        "NOT_DEMONSTRATED",
        "CONTRADICTED_BY_PUBLIC_EVIDENCE",
    }
    actual_licensing = set(matrix_df["licensing_evidence_status"])
    if not actual_licensing <= expected_licensing:
        raise RuntimeError(f"Licensing status inesperados: {sorted(actual_licensing - expected_licensing)}")

    expected_company = {"IDENTIFIED", "PARTIALLY_IDENTIFIED", "NOT_IDENTIFIED"}
    actual_company = set(matrix_df["company_status"])
    if not actual_company <= expected_company:
        raise RuntimeError(f"Company status inesperados: {sorted(actual_company - expected_company)}")

    expected_domain_confidence = {"HIGH", "MEDIUM", "LOW", "NOT_IDENTIFIED"}
    actual_domain_confidence = set(matrix_df["official_domain_confidence"])
    if not actual_domain_confidence <= expected_domain_confidence:
        raise RuntimeError(f"Official domain confidence inesperados: {sorted(actual_domain_confidence - expected_domain_confidence)}")

    matrix_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    OUTPUT_QUERY_PLAN.write_text(
        json.dumps(query_plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    OUTPUT_REPORT.write_text(
        build_report(matrix_df, domain_df, query_plan),
        encoding="utf-8",
    )

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        write_sheet(writer, matrix_df, "Top 50")
        write_sheet(
            writer,
            matrix_df.sort_values(
                by=["recurrence_score", "unique_domains_count", "platform_count", "evidence_url_count"],
                ascending=[False, False, False, False],
            ),
            "Alta recurrencia",
        )
        write_sheet(
            writer,
            matrix_df[matrix_df["due_diligence_status"] == "NEEDS_IDENTITY_RESOLUTION"],
            "Identidad no resuelta",
        )
        write_sheet(
            writer,
            matrix_df[(matrix_df["due_diligence_status"] == "HIGH_RISK") | (matrix_df["risk_level_preliminary"] == "HIGH")],
            "Riesgo alto",
        )
        write_sheet(writer, evidence_df, "Evidencias")
        write_sheet(writer, domain_df, "Fuentes por dominio")
        write_sheet(writer, missing_df, "Campos faltantes")
        write_sheet(writer, plan_df, "Plan Tavily")

    print("Due diligence preliminar finalizada.")
    print(f"Top 50 marcas unicas: {matrix_df['brand_name'].nunique()}")
    print("Due diligence status:")
    for status, count in matrix_df["due_diligence_status"].value_counts().sort_index().items():
        print(f"  {status}: {count}")
    print(f"CSV: {OUTPUT_CSV}")
    print(f"Excel: {OUTPUT_XLSX}")
    print(f"Reporte: {OUTPUT_REPORT}")
    print(f"Plan Tavily: {OUTPUT_QUERY_PLAN}")


if __name__ == "__main__":
    main()
