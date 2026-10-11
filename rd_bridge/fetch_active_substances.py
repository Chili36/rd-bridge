"""Fetch the EU active-substance index as an auditable second source.

Unlike pesticide-residues, active-substances also lists substances without a
current residue definition. Keep only the attributes needed for identification,
approval status and verifying the linked residue id.

Usage: python -m rd_bridge.fetch_active_substances [data/active_substances.json]
"""
import json
import sys

from rd_bridge.fetch_residues import get_json

API = ("https://api.datalake.sante.service.ec.europa.eu/sante/pesticides/active-substances"
       "?format=json&api-version=v3.0")
MAX_PAGES = 100


def fetch_all(url=API, get_page=get_json) -> list:
    rows, pages, seen, seen_records = [], 0, set(), set()
    while url:
        if url in seen or pages >= MAX_PAGES:
            raise RuntimeError("active-substances pagination loop or page limit")
        seen.add(url)
        payload = get_page(url)
        if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
            raise RuntimeError("active-substances API changed its response shape")
        for row in payload["value"]:
            if not isinstance(row, dict) or not row.get("substance_name"):
                raise RuntimeError("active-substances API returned a row without a name")
            if "substance_status" not in row or "pesticide_residue_linked" not in row:
                raise RuntimeError("active-substances API changed required fields")
            record = {
                "substance_id": row.get("substance_id"),
                "name": row["substance_name"],
                "cas": row.get("cas_number") or row.get("as_cas_number"),
                "approval_status": row.get("substance_status"),
                "pesticide_residue_linked": row.get("pesticide_residue_linked"),
            }
            # API rows repeat identical substance/definition combinations.
            # Keep distinct definitions but don't repeat identical records.
            key = json.dumps(record, sort_keys=True)
            if key not in seen_records:
                seen_records.add(key)
                rows.append(record)
        url = payload.get("nextLink")
        pages += 1
    if not rows:
        raise RuntimeError("EU API returned no active substances")
    return rows


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "data/active_substances.json"
    rows = fetch_all()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)
    print(f"{len(rows)} active substance rows -> {path}")


if __name__ == "__main__":
    main()
