"""Fetch DG SANTE source records and propose an updated reference dataset.

The most recent EU-published RD is presumed applicable unless specific
evidence establishes a future application date. Unknown dates do NOT block
refreshing the mapping. Changes are committed only via a reviewed PR.

Raw API rows keep every field; active-substances also gets a compatibility
projection for the existing resolver.

Usage:
    python -m rd_bridge.eu_refresh --report eu-refresh-report.md
"""
import argparse
import collections
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit

from rd_bridge.fetch_active_substances import API as ACTIVE_API
from rd_bridge.fetch_residues import API as RESIDUES_API, get_json

REQUIRED = {
    "residues": ("pesticide_residue_id", "pesticide_residue_name",
                 "pesticide_residue_version_nbr"),
    "active_substances": ("substance_id", "substance_name",
                          "substance_status", "pesticide_residue_linked"),
}
DATE_FIELD = re.compile(r"date|applic|effective|valid_from|entry.into.force", re.I)
MAX_PAGES = 100
MIN_BASELINE_FRACTION = 0.80


def canonical(row: dict) -> str:
    return json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def fetch_pages(url: str, required: tuple, get_page=get_json, max_pages=MAX_PAGES) -> tuple:
    """Read every page, retaining all fields and duplicate records.

    Bad/missing response structure, an empty result, loops, an unsafe nextLink,
    and an unfinished pagination chain are fatal rather than partial success.
    """
    origin = urlsplit(url)
    if origin.scheme != "https" or not origin.hostname:
        raise ValueError("Source URL must use HTTPS")
    rows, visited, pages = [], set(), 0
    while url:
        if url in visited or pages >= max_pages:
            raise RuntimeError("EU API pagination loop or page limit")
        visited.add(url)
        payload = get_page(url)
        if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
            raise RuntimeError("EU API response shape changed: expected a value array")
        batch = payload["value"]
        for item in batch:
            if not isinstance(item, dict):
                raise RuntimeError("EU API returned a non-object row")
            if any(key not in item for key in required):
                raise RuntimeError("EU API changed required fields: " +
                                   ", ".join(sorted(set(required) - set(item))))
            if any(item.get(key) in (None, "") for key in required[:2]):
                raise RuntimeError("EU API returned a row missing its identifier or name")
        rows.extend(batch)
        pages += 1
        link = payload.get("nextLink")
        if link is not None and not isinstance(link, str):
            raise RuntimeError("EU API returned an invalid nextLink")
        if link:
            candidate = urljoin(url, link)
            dest = urlsplit(candidate)
            if dest.scheme != "https" or dest.hostname != origin.hostname:
                raise RuntimeError("EU API nextLink points outside the source host")
            url = candidate
        else:
            url = None
    if not rows:
        raise RuntimeError("EU API returned an empty source dataset")
    return sorted(rows, key=canonical), pages


def project_active_substances(raw: list) -> list:
    """Five-field compatibility index consumed by the existing resolver.

    The full EU records, including duplicates and future fields, are also
    retained as independent raw snapshots.
    """
    projected, seen = [], set()
    for row in raw:
        record = {
            "substance_id": row.get("substance_id"),
            "name": row["substance_name"],
            "cas": row.get("cas_number") or row.get("as_cas_number"),
            "approval_status": row.get("substance_status"),
            "pesticide_residue_linked": row.get("pesticide_residue_linked"),
        }
        key = canonical(record)
        if key not in seen:
            projected.append(record)
            seen.add(key)
    return sorted(projected, key=canonical)


def read_approved(path: Path) -> list:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list) or not data:
        raise RuntimeError(f"Approved baseline is missing or empty: {path}")
    return data


def check_size(name: str, current: list, approved: list) -> None:
    if len(current) < MIN_BASELINE_FRACTION * len(approved):
        raise RuntimeError(
            f"{name}: EU API returned {len(current)} rows vs {len(approved)} "
            "in the approved baseline; refusing a suspiciously incomplete snapshot"
        )


def row_diff(approved: list, current: list) -> dict:
    old = collections.Counter(map(canonical, approved))
    new = collections.Counter(map(canonical, current))
    return {"added_rows": sum((new - old).values()),
            "removed_rows": sum((old - new).values())}


def date_fields(rows: list) -> dict:
    """Potential dates are evidence to review, NOT validated legal applicability."""
    keys = sorted({key for row in rows for key in row if DATE_FIELD.search(key)})
    return {key: {"present": sum(row.get(key) not in (None, "") for row in rows),
                  "examples": sorted({str(row[key]) for row in rows
                                      if row.get(key) not in (None, "")})[:3]}
            for key in keys}


def possible_future_dates(rows: list, as_of: date = None) -> list:
    """Detect dates worth investigating, not a legal determination.

    No record is rejected solely for having a date-like field. The latest RD
    remains the default until the field's legal semantics are established.
    """
    as_of = as_of or datetime.now(timezone.utc).date()
    fields = ("application_date", "pesticide_residue_application_date")
    found = []
    for row in rows:
        for field in fields:
            value = row.get(field)
            if not isinstance(value, str) or not re.match(r"^\d{4}-\d{2}-\d{2}(?:$|T)", value):
                continue
            try:
                parsed = date.fromisoformat(value[:10])
            except ValueError:
                continue
            if parsed > as_of:
                found.append({"residue_id": row.get("pesticide_residue_id"),
                              "residue_name": row.get("pesticide_residue_name"),
                              "field": field, "date": str(parsed)})
    return sorted(found, key=canonical)


def source_info(url: str, rows: list, pages: int) -> dict:
    keys = sorted({key for row in rows for key in row})
    digest = hashlib.sha256(("\n".join(map(canonical, rows))).encode("utf-8")).hexdigest()
    return {"url": url, "row_count": len(rows), "page_count": pages,
            "sha256": digest, "fields": keys, "date_field_candidates": date_fields(rows)}


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1) + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != serialized:
        path.write_text(serialized, encoding="utf-8")


def stage(approved_dir: Path, out_dir: Path, report: Path, get_page=get_json) -> dict:
    """Download and validate *both* endpoints before writing a single file."""
    old_residues = read_approved(approved_dir / "residues_en.json")
    old_active = read_approved(approved_dir / "active_substances.json")
    residues, residue_pages = fetch_pages(RESIDUES_API, REQUIRED["residues"], get_page)
    active, active_pages = fetch_pages(ACTIVE_API, REQUIRED["active_substances"], get_page)
    projected_active = project_active_substances(active)

    check_size("pesticide-residues", residues, old_residues)
    check_size("active-substances", projected_active, old_active)
    # Compare only the approved schema: new API fields must be retained and
    # reviewed, not reported as deletion+addition of every existing residue.
    approved_fields = {key for row in old_residues for key in row}
    equivalent_residues = [
        {key: row[key] for key in approved_fields if key in row}
        for row in residues
    ]
    baseline = {
        "residues": row_diff(old_residues, equivalent_residues),
        "active_substances": row_diff(old_active, projected_active),
    }
    manifest = {
        "description": "Full-field EU snapshots and proposed latest-version reference update.",
        "api_version": "v3.0",
        "applicability_policy": "presume_latest_applicable_unless_known_future_date",
        "possible_future_application_dates": possible_future_dates(residues),
        "source": {
            "residues": source_info(RESIDUES_API, residues, residue_pages),
            "active_substances": source_info(ACTIVE_API, active, active_pages),
        },
    }
    # Preserve all original fields separately, while proposing usable updates to
    # the existing mapping inputs. These are branch changes, not changes to main:
    # the workflow opens a pull request, and does not auto-merge.
    save_json(out_dir / "residues_full.json", residues)
    save_json(out_dir / "active_substances_full.json", active)
    save_json(out_dir / "manifest.json", manifest)
    save_json(approved_dir / "residues_en.json", residues)
    save_json(approved_dir / "active_substances.json", projected_active)

    lines = [
        "# DG SANTE source snapshot review",
        "",
        f"Fetched (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        "**Proposed update:** use the latest EU-published definitions as "
        "applicable by default, unless there is evidence of a future application "
        "date. Missing date information does not block a reference update. "
        "Historical date-specific lookup is not implemented.",
        "",
        "| API | Full raw rows | Pages | Approved baseline rows | Added rows* | Removed rows* |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        f"| pesticide-residues | {len(residues)} | {residue_pages} | {len(old_residues)} | "
        f"{baseline['residues']['added_rows']} | {baseline['residues']['removed_rows']} |",
        f"| active-substances | {len(active)} | {active_pages} | {len(old_active)} | "
        f"{baseline['active_substances']['added_rows']} | "
        f"{baseline['active_substances']['removed_rows']} |",
        "",
        "*Row diffs compare the raw residue response with the approved residue "
        "snapshot, and a compatibility projection of the active response with "
        "the approved active-substances snapshot. They are not counts of "
        "changed legal definitions.",
        "",
        "## Fields potentially relevant to dates",
        "",
    ]
    for name, source in manifest["source"].items():
        dates = source["date_field_candidates"]
        lines.append(f"**{name}:**")
        if not dates:
            lines.append("- No date-like fields returned by this endpoint.")
        for key, details in dates.items():
            lines.append(f"- `{key}`: {details['present']} non-empty values; "
                         f"examples: {', '.join(details['examples']) or '(none)'}")
        lines.append("")
    candidates = manifest["possible_future_application_dates"]
    if candidates:
        lines += ["## Possible future application dates", "",
                  f"{len(candidates)} source record(s) have a date in the future "
                  "under a field that may be an application date. They are NOT "
                  "automatically excluded; confirm that the date applies to this "
                  "RD before deciding which version is currently applicable.", ""]
        lines += [
            f"- residue {x['residue_id']}: {x['residue_name']} "
            f"({x['field']} = {x['date']})"
            for x in candidates[:50]
        ]
        if len(candidates) > 50:
            lines.append(f"- ... and {len(candidates) - 50} more in the manifest")
        lines.append("")
    lines += [
        "## Review notes",
        "",
        "1. The updated residue and active-substance inputs are proposed in this "
        "same pull request, along with the rebuilt PARAM map.",
        "2. Do not hold back a new RD merely because its application date is not "
        "provided: latest-published is the normal working assumption.",
        "3. Where there is **specific evidence** of a future application date, "
        "check the case and retain the prior applicable definition. The source "
        "fields listed above are candidates for investigation, not proof by name alone.",
        "4. The project does not yet resolve historical RDs for a requested "
        "sampling date; see the dedicated issue for date-aware selection.",
        "",
    ]
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approved-dir", type=Path, default=Path("data"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/eu_sources"))
    parser.add_argument("--report", type=Path, default=Path("eu-refresh-report.md"))
    args = parser.parse_args()
    result = stage(args.approved_dir, args.out_dir, args.report)
    for name, details in result["source"].items():
        print(f"{name}: {details['row_count']} full records, "
              f"{details['page_count']} pages, {len(details['fields'])} fields")
    print(f"Review report: {args.report} (latest definitions presumed applicable)")


if __name__ == "__main__":
    main()
