"""Reproducible, conservative comparison with EFSA's published 2024 SE/FR reports.

This measures agreement with accepted reporting, NOT legal/chemical correctness.
The reported PARAM code is used to identify a *candidate* residue. Therefore
coverage/accuracy is conditional on independently unambiguous code mappings;
the non-judgeable denominator is always reported to prevent selection bias.

Usage: python -m scripts.validate_monitoring --countries SE FR --output reports/monitoring_2024.json
Downloads public Zenodo ZIPs into temporary space; does not commit sample rows.
"""
import argparse
import collections
import csv
import functools
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile

from rd_bridge import compounds
from rd_bridge.commodity import Classifier
from rd_bridge.resolve import Resolver

RECORDS = {"SE": 20036095, "FR": 20034822}
BASELINE = "d2d1b12ab49df9ee534c4cead132d7b2e9d9e716"
NA = {"", "N_A", "NA", "N/A", "NULL", "NONE"}
HINTS = {"source": "F01", "part": "F02", "state": "F03",
         "prod": "F21", "process": "F28"}


def load_baseline():
    raw = subprocess.check_output(
        ["git", "show", f"{BASELINE}:data/residue_param_map.json"])
    return json.loads(raw)


def indices(residues):
    out = {kind: collections.defaultdict(set)
           for kind in ("whole", "component", "qualifier")}
    for residue in residues:
        rid = residue["residue_id"]
        for entry in [residue["default"], *residue["exceptions"]]:
            if entry.get("method") not in ("none", "near", "ambiguous"):
                for code in entry.get("param_codes", []):
                    out["whole"][code].add(rid)
            for part in entry.get("components", []):
                if part.get("role") == "analyte" and part.get("method") not in ("none",):
                    for code in part.get("param_codes", []):
                        out["component"][code].add(rid)
            for part in entry.get("qualifier_components", []):
                for code in part.get("param_codes", []):
                    out["qualifier"][code].add(rid)
    return out


def active_codes(resolver):
    found = collections.defaultdict(set)
    for rows in resolver.active.values():
        for substance in rows:
            name = substance["name"]
            if resolver.residue(name):
                continue
            status = resolver._active_status(name)
            if status and status["status"] == "no_residue_definition":
                for code in status.get("param_codes", []):
                    found[code].add(name)
    return found


def category(code, index, fallback=None):
    for kind in ("whole", "component", "qualifier"):
        ids = index[kind].get(code, ())
        if ids:
            return (kind if len(ids) == 1 else "ambiguous", next(iter(ids)) if len(ids) == 1 else None)
    names = fallback.get(code, ()) if fallback else ()
    if names:
        return ("no_residue_definition" if len(names) == 1 else "ambiguous", None)
    return "unmapped", None


def get_column(header, *names):
    lookup = {h.lower(): i for i, h in enumerate(header)}
    for name in names:
        if name.lower() in lookup:
            return lookup[name.lower()]
    raise RuntimeError(f"None of {names!r} found; relevant fields: "
                       f"{[h for h in header if 'paramcode' in h.lower() or 'sampmatcode' in h.lower()][:80]}")


def food_builder(header, classifier):
    """Reconstitute only the FoodEx2 facets actually used by EFSA's PPP rules.

    foodex2_ppp.json contains the exact hierarchies the copied algorithm reads:
    F20 (partcon), F21 (prod), F27 (racsource). Other SSD2 facets are irrelevant
    to the rule port, so ignoring them is *not* a classification guess.
    """
    base_idx = get_column(header, "sampMatCode.base.building", "sampMatCode.base",
                          "sampMatCode", "sampMatCode.base.primary")
    fields = {"F20": "sampMatCode.partcon", "F21": "sampMatCode.prod",
              "F27": "sampMatCode.racsource"}
    cols = [(i, facet) for facet, field in fields.items()
            for i, head in enumerate(header) if head == field]
    if len(cols) != len(fields):
        raise RuntimeError(f"CSV is missing the fields required by EFSA's PPP mapping: {fields}")

    @functools.lru_cache(maxsize=100_000)
    def reconstruct(base, vals):
        explicit, unknown = [], []
        for facet, value in vals:
            hierarchy = classifier.facet_hierarchy[facet]
            if value not in classifier.parents[hierarchy]:
                unknown.append(f"{facet}={value}")
            else:
                explicit.append(f"{facet}.{value}")
        return base + ("#" + "$".join(explicit) if explicit else ""), bool(unknown)

    def code(row):
        base = row[base_idx].strip().upper() if base_idx < len(row) else ""
        if base in NA:
            return "", True
        vals = tuple((facet, row[i].strip().upper()) for i, facet in cols
                     if i < len(row) and row[i].strip().upper() not in NA)
        return reconstruct(base, vals)

    return code


def public_zip(country, folder):
    record = RECORDS[country]
    headers = {"User-Agent": "rd-bridge-monitoring-validator/1.0"}
    with urllib.request.urlopen(urllib.request.Request(
            f"https://zenodo.org/api/records/{record}", headers=headers), timeout=120) as f:
        metadata = json.load(f)
    files = [f for f in metadata["files"]
             if "2024" in f["key"] and f["key"].upper().endswith(".ZIP")]
    if len(files) != 1:
        raise RuntimeError(f"Expected one 2024 ZIP for {country}: {[f['key'] for f in files]}")
    file = files[0]
    path = os.path.join(folder, f"{country}.zip")
    request = urllib.request.Request(file["links"]["self"], headers=headers)
    with urllib.request.urlopen(request, timeout=300) as src, open(path, "wb") as dst:
        shutil.copyfileobj(src, dst)
    if os.stat(path).st_size != file["size"]:
        raise RuntimeError(f"Incomplete download for {country}")
    md5 = hashlib.file_digest(open(path, "rb"), "md5").hexdigest()
    listed_md5 = file.get("checksum", "").removeprefix("md5:")
    if listed_md5 and md5 != listed_md5:
        raise RuntimeError(f"Checksum mismatch for {country}")
    return path, {"zenodo_record": record, "doi": f"10.5281/zenodo.{record}",
                  "file": file["key"], "bytes": file["size"], "md5": md5}


def validate(country, classifier, before, after, resolver_before, resolver_after, fallback):
    counters, disagreements = collections.Counter(), collections.Counter()
    old_categories, new_categories = collections.Counter(), collections.Counter()
    examples = collections.Counter()
    types = collections.defaultdict(collections.Counter)

    @functools.lru_cache(maxsize=100_000)
    def chosen(rid, food):
        return resolver_after.resolve(food, rid)

    with tempfile.TemporaryDirectory() as tmp:
        path, source = public_zip(country, tmp)
        with zipfile.ZipFile(path) as archive:
            members = [x for x in archive.namelist() if x.lower().endswith(".csv")]
            if len(members) != 1:
                raise RuntimeError(f"Expected one CSV in {country} ZIP, found: {members!r}")
            with archive.open(members[0]) as raw:
                stream = io.TextIOWrapper(raw, encoding="utf-8-sig",
                                          errors="replace", newline="")
                reader = csv.reader(stream)
                header = next(reader)
                print(f"{country}: {len(header)} columns; parameter fields: "
                      f"{[h for h in header if 'paramcode' in h.lower() or 'paramtype' in h.lower()]}",
                      flush=True)
                param_idx = get_column(header, "paramCode.base.param", "paramCode.base", "paramCode", "paramCode.base.building")
                food_code = food_builder(header, classifier)
                param_type_idx = get_column(header, "paramType")
                for row in reader:
                    counters["total_reporting_rows"] += 1
                    if param_idx >= len(row):
                        counters["short_rows"] += 1
                        continue
                    param = row[param_idx].strip().upper()
                    if not param or param in NA:
                        counters["no_param_code"] += 1
                        continue
                    counters["rows_with_param_code"] += 1
                    param_type = row[param_type_idx].strip().upper() or "MISSING"
                    types["all"][param_type] += 1
                    old_kind, _ = category(param, before)
                    kind, rid = category(param, after, fallback)
                    old_categories[old_kind] += 1
                    new_categories[kind] += 1
                    if old_kind == "unmapped" and kind != "unmapped":
                        counters["previously_unmapped_now_recognized"] += 1
                    if kind == "no_residue_definition":
                        examples[param] += 1
                    if kind != "whole" or rid is None:
                        continue
                    types["whole_code_candidates"][param_type] += 1
                    food, uncertain = food_code(row)
                    if not food:
                        counters["whole_missing_food_code"] += 1
                        continue
                    if uncertain:
                        counters["whole_unmapped_food_facets"] += 1
                        continue
                    out = chosen(rid, food)
                    if out["status"] not in ("resolved",):
                        counters["whole_not_judgeable"] += 1
                        continue
                    expected = out["param_codes"]
                    if len(expected) != 1:
                        counters["whole_not_judgeable"] += 1
                        continue
                    counters["whole_judgeable"] += 1
                    types["compared"][param_type] += 1
                    if param == expected[0]:
                        counters["whole_agreement"] += 1
                        types["agreed"][param_type] += 1
                    else:
                        counters["whole_disagreement"] += 1
                        types["disagreed"][param_type] += 1
                        disagreements[(out.get("residue_name", str(rid)), param, expected[0], param_type)] += 1
                    if counters["total_reporting_rows"] % 250_000 == 0:
                        print(f"{country}: processed {counters['total_reporting_rows']:,} records", flush=True)
    # P005A is the EFSA code for the *full* legal residue definition.
    # P004A (sum of subset) and P002A (part of sum) must NOT be counted
    # as independently accepted full legal definitions; N_A is unknown.
    full_n = types["compared"]["P005A"]
    full_ok = types["agreed"]["P005A"]
    full_wrong = types["disagreed"]["P005A"]
    counters["full_definition_P005A_judgeable"] = full_n
    counters["full_definition_P005A_agreement"] = full_ok
    counters["full_definition_P005A_disagreement"] = full_wrong
    counters["full_definition_P005A_agreement_fraction"] = (
        round(full_ok / full_n, 8) if full_n else None)
    # Preserve ALL grouped P005A differences rather than burying small cases
    # behind a top-30 list dominated by correctly reported components.
    full_differences = sorted(
        (({"residue": key[0], "reported": key[1],
           "expected_current": key[2], "param_type": key[3], "rows": n})
         for key, n in disagreements.items() if key[3] == "P005A"),
        key=lambda d: (-d["rows"], d["residue"], d["reported"]))
    if sum(x["rows"] for x in full_differences) != full_wrong:
        raise RuntimeError("P005A disagreement detail does not match its total")
    counters["all_param_types_candidate_agreement_fraction"] = (
        round(counters["whole_agreement"] / counters["whole_judgeable"], 8)
        if counters["whole_judgeable"] else None)
    return {"source": source, "counts": dict(counters),
            "parameter_type_breakdown": {k: dict(count) for k, count in types.items()},
            "recognized_before": dict(old_categories),
            "recognized_after": dict(new_categories),
            "new_no_definition_param_codes": examples.most_common(30),
            "full_definition_P005A_disagreements": full_differences,
            "whole_disagreements_top": [
                {"residue": key[0], "reported": key[1], "expected_current": key[2], "param_type": key[3], "rows": n}
                for key, n in disagreements.most_common(30)],
            "limitations": [
                "The reported PARAM code itself identifies candidate residue(s); this is not an independent accuracy estimate.",
                 "paramType is stratified: only P005A declares a fully analysed residue definition; P004A is a subset sum, P002A is an individual part, N_A has unknown coverage. The all-param-types agreement figure is diagnostic only.",
                "Only reported whole-residue codes uniquely attributable to a current residue and food codes with interpretable facets are compared for agreement.",
                "Reported parts are recognized as parts and are not judged as complete whole-residue reports.",
                "The reference map contains current definitions; 2024 reports may legitimately use definitions applicable on sampling dates.",
                "Accepted reporting agreement is not proof of correctness; no MRL compliance assessment is performed."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--countries", nargs="+", choices=RECORDS, default=list(RECORDS))
    parser.add_argument("--output", default="reports/monitoring_2024.json")
    args = parser.parse_args()
    with open("data/residue_param_map.json", encoding="utf-8") as f:
        current = json.load(f)
    baseline = load_baseline()
    with open("data/active_substances.json", encoding="utf-8") as f:
        active = json.load(f)
    with open("data/param_pest_terms.json", encoding="utf-8") as f:
        terms = json.load(f)
    classifier = Classifier.load("data/foodex2_ppp.json")
    # Millions of rows reuse the same FoodEx2 description across many
    # substances. Classify each distinct food once, not once per result.
    classifier.classify = functools.lru_cache(maxsize=40_000)(classifier.classify)
    old_resolver = Resolver(baseline, classifier)
    new_resolver = Resolver(current, classifier, active, terms)
    old_idx, new_idx = indices(baseline), indices(current)
    fallback = active_codes(new_resolver)
    report = {
        "purpose": "Reference-map recognition and concordance with accepted 2024 reporting, not proof of correctness",
        "definition_snapshot": "current (2026-10-11)", "baseline_commit": BASELINE,
        "before_map_residues": len(baseline), "after_map_residues": len(current),
        "countries": {}}
    for country in args.countries:
        report["countries"][country] = validate(
            country, classifier, old_idx, new_idx, old_resolver, new_resolver, fallback)
        print(country, json.dumps(report["countries"][country]["counts"]), flush=True)
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("Report saved to", args.output, flush=True)


if __name__ == "__main__":
    main()
