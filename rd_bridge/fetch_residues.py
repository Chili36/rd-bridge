"""Download every pesticide residue definition (English) from the EU Pesticides Database API.

Usage: python -m rd_bridge.fetch_residues [data/residues_en.json]
"""
import json
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

API = ("https://api.datalake.sante.service.ec.europa.eu/sante/pesticides/pesticide-residues"
       "?format=json&pesticide_residue_lg=EN&api-version=v3.0")
MAX_PAGES = 100


def _fetch(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=90) as resp:
            return json.load(resp)
    except urllib.error.URLError as exc:
        if not isinstance(exc.reason, ssl.SSLError):
            raise
        # Some machines (TLS-inspecting networks, python.org builds without certificates)
        # reject the chain that the system curl accepts.
        out = subprocess.run(["curl", "-sf", "--max-time", "90", url],
                             capture_output=True, check=True).stdout
        return json.loads(out)


def download(url: str, path: str, timeout: int = 600) -> str:
    """Save `url` to `path`; falls back to curl like _fetch."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp, open(path, "wb") as out:
            shutil.copyfileobj(resp, out)
    except OSError:
        subprocess.run(["curl", "-sfL", "--max-time", str(2 * timeout), "-o", path, url], check=True)
    return path


def get_json(url: str, attempts: int = 4) -> dict:
    for attempt in range(attempts):
        try:
            return _fetch(url)
        except Exception as exc:  # network or 5xx: the API is known to be flaky
            if attempt == attempts - 1:
                raise
            print(f"retry {attempt + 1}: {exc}", file=sys.stderr)
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("unreachable")


def fetch_all() -> list:
    rows, url, pages = [], API, 0
    while url and pages < MAX_PAGES:
        page = get_json(url)
        rows += page.get("value", [])
        url = page.get("nextLink")
        pages += 1
    if not rows:
        # An empty download must never look like a successful run.
        raise SystemExit("EU API returned no residue definitions")
    return rows


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else "data/residues_en.json"
    rows = fetch_all()
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)
    print(f"{len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
