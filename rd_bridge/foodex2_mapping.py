"""Extract EFSA's FoodEx2 -> food-class mapping (pesticides) into data/foodex2_ppp.json.

Source: "EFSA Food classification mapping for legal limit compliance of chemical monitoring
data", Zenodo concept record 3989602 (CC BY 4.0), file Mapping_foodex2_to_foodcategories_v*.zip.
The package holds EFSA's SAS algorithm, its rule table for pesticides (mappingppp) and the
FoodEx2 hierarchies as SAS formats. This keeps only what the pesticide rules read: the rules,
the implicit facets of each base term for the facet categories the rules use, the parent of
each term in the hierarchies the rules use, and the FEED "reportable" flags.

Usage: python -m rd_bridge.foodex2_mapping [package.zip] [data/foodex2_ppp.json]
Without a zip it downloads the latest version from Zenodo. Reading the rule table needs pandas.
"""
import hashlib
import json
import os
import sys
import tempfile
import zipfile

from rd_bridge.fetch_residues import download, get_json
from rd_bridge.sas7bcat import Catalog

CONCEPT_RECORD = "3989602"
LATEST = f"https://zenodo.org/api/records/{CONCEPT_RECORD}/versions/latest"
PACKAGE_PREFIX = "Mapping_foodex2_to_foodcategories"


def download_latest(directory: str) -> tuple:
    record = get_json(LATEST)
    entry = next(f for f in record["files"] if f["key"].startswith(PACKAGE_PREFIX))
    path = os.path.join(directory, entry["key"])
    # the records API gives the bytes at links.self (".../content"); the files API at links.content
    url = entry["links"].get("content") or entry["links"]["self"]
    download(url, path)
    algo, _, expected = entry["checksum"].partition(":")
    digest = hashlib.new(algo)
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise SystemExit(f"{entry['key']}: checksum mismatch")
    source = {"zenodo_record": str(record["id"]), "version": record["metadata"].get("version"),
              "doi": record.get("doi"), "file": entry["key"], "checksum": entry["checksum"]}
    return path, source


def _member(zf: zipfile.ZipFile, suffix: str, directory: str) -> str:
    name = next(n for n in zf.namelist() if n.replace("\\", "/").endswith(suffix))
    return zf.extract(name, directory)


def _read_sas7bdat(path: str):
    try:
        import pandas
    except ImportError as exc:  # only the extractor needs it; the classifier is stdlib
        raise SystemExit("reading the SAS rule table needs pandas (pip install pandas)") from exc
    return pandas.read_sas(path, encoding="latin-1").fillna("")


def _parents(paths: dict) -> dict:
    """{term: 'A - B - term'} -> {term: parent or None}, checked to rebuild every path."""
    parents = {}
    for term, path in paths.items():
        chain = path.split(" - ")
        if chain[-1] != term:
            raise ValueError(f"{term}: path {path!r} does not end in the term")
        parents[term] = chain[-2] if len(chain) > 1 else None
    for term, path in paths.items():
        rebuilt, node = [], term
        while node is not None and len(rebuilt) < 50:
            rebuilt.append(node)
            node = parents.get(node)
        if " - ".join(reversed(rebuilt)) != path:
            raise ValueError(f"{term}: parents do not rebuild {path!r}")
    return parents


def extract(package: str, workdir: str) -> dict:
    with zipfile.ZipFile(package) as zf:
        rules_path = _member(zf, "Supporting_files/mappingppp.sas7bdat", workdir)
        sys_path = _member(zf, "Supporting_files/catalog_sys.sas7bdat", workdir)
        catalog_path = _member(zf, "Supporting_files/Formats2/formats.sas7bcat", workdir)

    table = _read_sas7bdat(rules_path).sort_values("MAPPING_ORDER")
    rules = [{"order": int(r.MAPPING_ORDER), "base_hierarchy": r.BASETERM_HIER.strip() or None,
              "include": r.INCLUDE_FACETS.strip(), "exclude": r.EXCLUDE_FACETS.strip(),
              "food_class": r.MAPPING.strip()} for r in table.itertuples()]

    headers = {f.split(".")[0] for r in rules for f in f"{r['include']}${r['exclude']}".split("$")
               if "." in f} - {"F00"}
    sys_table = _read_sas7bdat(sys_path)
    mtx = sys_table[sys_table.cat_code == "MTX"].sort_values("attr_data_ID")
    facet_hierarchy = {row.attr_code: row.hier_code for row in mtx.itertuples() if row.attr_code in headers}
    missing = headers - set(facet_hierarchy)
    if missing:
        raise SystemExit(f"rules use facet categories without a hierarchy: {sorted(missing)}")
    base_hierarchies = sorted({"MTX"} | {r["base_hierarchy"] for r in rules if r["base_hierarchy"]})
    root_hierarchies = sorted({r["base_hierarchy"] or "MTX" for r in rules
                               if "F00.ROOT" in f"{r['include']}${r['exclude']}"})

    with Catalog(catalog_path) as cat:
        hierarchies = {h: _parents(cat.labels(f"${h.upper()}_CCATLEVEL"))
                       for h in sorted(set(base_hierarchies) | set(facet_hierarchy.values()))}
        reportable = {h: sorted(k for k, v in cat.labels(f"@{h.upper()}_REPORTABLE_").items() if v == 1)
                      for h in root_hierarchies}
        implicit = {}
        for term, code in cat.labels("$MTX_ALLFACETS_").items():
            facets = [f for f in code.partition("#")[2].split("$") if f.split(".")[0] in facet_hierarchy]
            if facets:
                implicit[term] = "$".join(facets)

    return {"rules": rules, "facet_hierarchy": facet_hierarchy, "hierarchies": hierarchies,
            "reportable": reportable, "implicit_facets": implicit}


def main() -> None:
    args = sys.argv[1:]
    out = args[1] if len(args) > 1 else "data/foodex2_ppp.json"
    with tempfile.TemporaryDirectory() as workdir:
        if args and args[0].endswith(".zip"):
            package = args[0]
            with open(package, "rb") as fh:
                md5 = hashlib.md5(fh.read()).hexdigest()  # noqa: S324 - Zenodo publishes md5
            source = {"file": os.path.basename(package), "checksum": f"md5:{md5}"}
        else:
            package, source = download_latest(workdir)
        data = {"source": source, **extract(package, workdir)}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    print(f"{len(data['rules'])} rules, {len(data['implicit_facets'])} base terms with implicit facets, "
          f"hierarchies {sorted(data['hierarchies'])} -> {out}")


if __name__ == "__main__":
    main()
