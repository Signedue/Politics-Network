from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from .config import (
    ALTERNATIVET_HIGHLIGHTED_PRIORITIES,
    DANMARKSDEMOKRATERNE_MAIN_PRIORITIES,
    ENHEDSLISTEN_HIGHLIGHTED_PRIORITIES,
    MODERATERNE_HIGHLIGHTED_PRIORITIES,
    RADIKALE_VISION_THEMES,
)
from .pipeline import (
    HTML_CACHE,
    read_cached_html,
    extract_danmarksdemokraterne_programme,
    extract_alternativet_programme,
    extract_enhedslisten_campaign_priority,
    extract_nye_borgerlige_priorities,
    extract_moderaterne_proposals,
    extract_df_main_content,
    extract_radikale_visions,
    extract_structured_html,
    clean_socialdemokratiet_text,
)

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
PARTIES = {"S", "V", "RV", "KF", "NB", "SF", "LA", "M", "DF", "DD", "EL", "ALT"}


def cached_html(archive_url: str) -> str | None:
    path = HTML_CACHE / (
        f"{hashlib.sha256((archive_url + '|utf8-v2').encode()).hexdigest()}.html"
    )
    return read_cached_html(path) if path.exists() else None


def audit() -> list[dict]:
    rows = [
        row
        for row in csv.DictReader(
            (OUTPUT / "policy_pages.csv").open(encoding="utf-8")
        )
        if row.get("party_code") in PARTIES
    ]
    results = []
    programme_cache: dict[str, list[dict]] = {}
    for row in rows:
        html = cached_html(row.get("archive_url", ""))
        status = "missing_source_cache"
        reason = "archived source HTML is not available in the local cache"
        if html is not None:
            if row["party_code"] in {"RV", "NB", "M", "DD", "EL", "ALT"}:
                if row["party_code"] == "RV":
                    key = f"RV:{row['archive_url']}"
                    programme_cache.setdefault(
                        key,
                        extract_radikale_visions(
                            html,
                            row["resolved_original_url"],
                            RADIKALE_VISION_THEMES,
                        ),
                    )
                    candidates = programme_cache[key]
                    match = next(
                        (
                            item for item in candidates
                            if str(item["order"]) == row["priority_order"]
                        ),
                        None,
                    )
                    extracted = match["text"] if match else None
                elif row["party_code"] == "NB":
                    key = f"NB:{row['archive_url']}"
                    programme_cache.setdefault(
                        key,
                        extract_nye_borgerlige_priorities(
                            html,
                            row["resolved_original_url"],
                        ),
                    )
                    candidates = programme_cache[key]
                    match = next(
                        (
                            item for item in candidates
                            if str(item["number"]) == row["priority_order"]
                        ),
                        None,
                    )
                    extracted = match["text"] if match else None
                elif row["party_code"] == "M":
                    key = f"M:{row['archive_url']}"
                    programme_cache.setdefault(
                        key,
                        extract_moderaterne_proposals(
                            html,
                            row["resolved_original_url"],
                            MODERATERNE_HIGHLIGHTED_PRIORITIES,
                        ),
                    )
                    candidates = programme_cache[key]
                    match = next(
                        (
                            item for item in candidates
                            if str(item["number"]) == row["priority_order"]
                        ),
                        None,
                    )
                    extracted = match["text"] if match else None
                elif row["party_code"] == "DD":
                    key = f"DD:{row['archive_url']}"
                    programme_cache.setdefault(
                        key,
                        extract_danmarksdemokraterne_programme(
                            html,
                            "https://danmarksdemokraterne.dk/parti/program",
                            DANMARKSDEMOKRATERNE_MAIN_PRIORITIES,
                        )[0],
                    )
                    candidates = programme_cache[key]
                    match = next(
                        (
                            item for item in candidates
                            if str(item["number"]) == row["priority_order"]
                        ),
                        None,
                    )
                    extracted = match["text"] if match else None
                elif row["party_code"] == "EL":
                    extracted = extract_enhedslisten_campaign_priority(
                        html,
                        row["title"],
                    )[1]
                else:
                    candidates = extract_alternativet_programme(
                        html,
                        ALTERNATIVET_HIGHLIGHTED_PRIORITIES,
                    )[1]
                    match = next(
                        (
                            item for item in candidates
                            if str(item["number"]) == row["priority_order"]
                        ),
                        None,
                    )
                    extracted = match["text"] if match else None
                if extracted is not None and extracted == row["text"]:
                    status = "verified_exact_source_text"
                    reason = "specialized section extraction exactly reproduces stored text"
                else:
                    status = "unverifiable_or_mismatch"
                    reason = "stored text does not exactly match the specialized source extraction"
            else:
                if row["party_code"] == "S":
                    _, extracted, _, _, _ = extract_structured_html(html)
                    extracted = clean_socialdemokratiet_text(extracted)
                elif row["party_code"] == "DF":
                    _, extracted, _, _ = extract_df_main_content(html)
                else:
                    _, extracted, _, _, _ = extract_structured_html(html)
                if extracted == row["text"]:
                    status = "verified_exact_source_text"
                    reason = "stored text exactly matches structured extraction from archive HTML"
                else:
                    status = "unverifiable_or_mismatch"
                    reason = "stored text does not exactly match structured extraction from archive HTML"
        results.append({
            "party_code": row["party_code"],
            "priority_order": row["priority_order"],
            "title": row["title"],
            "archive_url": row["archive_url"],
            "status": status,
            "reason": reason,
        })
    return results


def main() -> None:
    results = audit()
    summary = {
        "records_checked": len(results),
        "records_verified": sum(
            item["status"] == "verified_exact_source_text" for item in results
        ),
        "records_unverifiable_or_missing": sum(
            item["status"] != "verified_exact_source_text" for item in results
        ),
        "unsupported_additions_detected": sum(
            item["status"] == "unverifiable_or_mismatch" for item in results
        ),
    }
    report = {"summary": summary, "records": results}
    (OUTPUT / "source_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Source correspondence audit",
        "",
        f"- Records checked: {summary['records_checked']}",
        f"- Records verified against cached source text: {summary['records_verified']}",
        f"- Records missing or unverifiable: {summary['records_unverifiable_or_missing']}",
        f"- Unsupported additions detected: {summary['unsupported_additions_detected']}",
        "",
        "| Party | Order | Title | Status |",
        "|---|---:|---|---|",
    ]
    for item in results:
        lines.append(
            f"| {item['party_code']} | {item['priority_order']} | "
            f"{item['title']} | {item['status']} |"
        )
    (OUTPUT / "source_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
