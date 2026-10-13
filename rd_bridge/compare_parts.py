"""Report on the model's readings (data/residue_param_map.json after rd_bridge.model_parts):

- readings: for every definition the model read, both readings are linked to PARAM the same way;
  "same" when they give the same linked codes, the same unlinked parts and the same coverage;
- agreement: where the rules link a component and the model also named a PARAM term for it, how
  often the two agree. This is what the model's own links (method `model`) are trusted on;
- model links: every component linked only by the model's choice, for a person to read;
- acceptance cases either reader must get right.

Writes data/parts_comparison.json and prints a Markdown summary (used as the PR text by the
model workflow). Exits with CASES_FAILED (3) when an acceptance case fails, so the workflow can
tell that apart from a crash (1).

Usage: python -m rd_bridge.compare_parts
"""
import collections
import json
import sys

from rd_bridge import components, compounds
from rd_bridge.components import completeness

CASES_FAILED = 3

# (residue id, exception index or None, analysed codes, expected status, what it shows)
CASES = [
    (2530, None, ["RF-00012387-PAR"], "partial", "the acid alone does not cover the acid and its methyl ester"),
    (2530, None, ["RF-00012387-PAR", "RF-00001604-PAR"], "complete", "acid plus methyl ester covers it"),
    (2333, None, ["RF-00003376-PAR", "RF-1078-003-PPP", "RF-1078-004-PPP", "RF-1078-005-PPP",
                  "RF-1078-006-PPP", "RF-1078-007-PPP"], "complete", "BAC C8-C18 chain lengths cover benzalkonium chloride"),
    (2333, None, ["RF-00003376-PAR"], "partial", "BAC 8 alone is part of benzalkonium chloride"),
    (2332, None, ["RF-00007495-PAR", "RF-00007627-PAR", "RF-00007489-PAR"], "complete",
     "DDAC C8, C10 and C12 cover didecyldimethylammonium chloride"),
    (10, 0, ["RF-0014-001-PPP"], "partial", "acetamiprid without IM-2-1"),
    (12, None, ["RF-0020-002-PPP", "RF-0020-003-PPP", "RF-0020-004-PPP"], "complete", "aldicarb, its sulfoxide and sulfone"),
    (179, None, ["RF-0336-003-PPP", "RF-0336-005-PPP", "RF-0336-002-PPP"], "partial", "phorate still needs the oxon sulfone"),
    (161, None, ["RF-00004672-PAR", "RF-00004673-PAR"], "complete", "mevinphos E- and Z-isomer"),
    (302, None, ["RF-0192-003-PPP", "RF-0192-002-PPP"], "complete", "fipronil + its sulfone"),
    (272, None, ["RF-0126-002-PPP"], "complete", "dichlorprop covers the included dichlorprop-P"),
    (139, None, ["RF-0260-002-PPP"], "not_covered", "kresoxim-methyl is not its metabolite BF-490-9"),
    (139, 0, ["RF-0260-002-PPP"], "complete", "BF-490-9 is the whole kresoxim-methyl exception"),
    (259, None, ["RF-0096-003-PPP", "RF-0096-005-PPP"], "complete",
     "sethoxydim and clethodim: the degradation products are determined as sethoxydim, not measured apart"),
    (3050, None, ["RF-0106-002-PPP", "RF-00006227-PAR", "RF-00006240-PAR"], "complete",
     "cycloxydim plus the two acids its products are determined as"),
    (135, 0, ["RF-0255-001-PPP"], "undetermined", "iprodione alone does not cover the 3,5-dichloroaniline metabolites"),
    (59, None, ["RF-0095-002-PPP"], "complete", "cinidon-ethyl covers its E-isomer"),
    (251, None, ["RF-0064-001-PPP"], "complete", "carbetamide covers its S isomer"),
    (310, None, ["RF-0211-001-PPP"], "complete", "fluoxastrobin covers its Z-isomer"),
    (3950, None, ["RF-0043-003-PPP"], "complete", "benthiavalicarb-isopropyl covers its RS enantiomer"),
    (304, None, ["RF-0698-001-PPP"], "complete", "fluazifop covers all its isomers, fluazifop-P included"),
    (322, None, ["RF-0235-004-PPP"], "complete", "haloxyfop covers the R- and S-isomers at any ratio"),
    # The general active-substance code is NOT equivalent to the reportable whole RD.
    (321, None, ["RF-00004664-PAR"], "complete",
     "guazatine acetate sum: exact whole-RD PARAM code"),
    (321, None, ["RF-0233-001-PPP"], "not_covered",
     "guazatine parent AS code is not the guazatine acetate RD"),
    (778, None, ["RF-0194-002-PPP", "RF-00003348-PAR", "RF-00003349-PAR"], "complete", "flonicamid, TFNA and TFNG"),
    (778, None, ["RF-0194-002-PPP"], "partial", "flonicamid alone misses TFNA and TFNG, which have codes"),
    # RF-0721-001-PPP is a non-reportable AS term in PARAM 17.6, not the whole RD.
    (2655, None, ["RF-00012800-PAR"], "complete",
     "fluvalinate sum of isomers: exact whole-RD PARAM code"),
    (2655, None, ["RF-0721-001-PPP"], "not_covered",
     "non-reportable fluvalinate AS code is not the whole RD"),
    (166, 0, ["RF-1005-001-PPP"], "complete", "RH9090 measured is the free and conjugated RH9090 residue"),
    (307, 0, ["RF-0202-001-PPP", "RF-00004643-PAR"], "complete", "fludioxonil plus the acid its metabolites are oxidized to"),
    (307, 0, ["RF-0202-001-PPP"], "partial", "fludioxonil alone misses the acid, which has a code"),
    (2750, None, ["RF-00003368-PAR"], "partial", "spirotetramat alone misses spirotetramat-enol"),
    # EU Regulation 2023/710 explicitly names just the metabolite for the animal exception.
    # "expressed as chloridazon" is a reporting/conversion basis, not an extra analyte.
    (253, 0, ["RF-00006186-PAR"], "complete",
     "chloridazon animal exception: desphenyl metabolite alone covers the definition"),
    (253, 0, ["RF-0080-001-PPP"], "not_covered",
     "chloridazon animal exception: parent alone is not the named metabolite"),
]


def analytes(found: list) -> tuple:
    """What decides completeness: (linked codes, unlinked parts, coverage relations)."""
    linked = {c for p in found if p["role"] == "analyte" for c in p.get("param_codes", [])}
    # groups never link, and they change completeness: keep them with the unlinked analytes, by name
    unlinked = frozenset(compounds.canon(p.get("name") or p["text"]) for p in found
                         if p["role"] == "group" or (p["role"] == "analyte" and not p.get("param_codes")))
    covered = {(tuple(sorted(p.get("param_codes", []))), tuple(sorted(p["covered_by"])))
               for p in found if p.get("covered_by")}
    return linked, unlinked, covered


def verdict(model: list, rules: list) -> str:
    return "same" if analytes(model) == analytes(rules) else "different"


def summary(part: dict) -> str:
    codes = ",".join(part.get("param_codes", [])) or "-"
    return f"{part.get('name') or part.get('text')} [{part['role']}: {codes}]"


def compare(rows: list, index: components.ComponentIndex) -> dict:
    counts, agreement, differences, model_links = collections.Counter(), collections.Counter(), [], []
    for r in rows:
        for entry in [r["default"], *r["exceptions"]]:
            if entry.get("parts_from") not in ("model", "guided_model", "legacy_regression_fallback"):
                counts["rules_only"] += 1  # retained key for compatible statistics
                if entry.get("parts_from") == "legal_guidance":
                    counts["legal_guidance"] += 1
                if entry.get("model_reading_lost"):
                    counts["model_not_used"] += 1
                continue
            if entry.get("parts_from") == "guided_model":
                counts["guided_model"] += 1
            if entry.get("parts_from") == "legacy_regression_fallback":
                counts["legacy_regression_fallback"] += 1
            for p in entry["components"]:
                if "model_agrees" in p:
                    agreement["agree" if p["model_agrees"] else "disagree"] += 1
                if p.get("method") == "model":
                    model_links.append({"residue_id": r["residue_id"], "definition": entry["definition"],
                                        "component": p["name"], "param": p.get("param_names", [])})
            rules = index.describe(entry["definition"], entry, r["name"])
            v = verdict(entry["components"], rules)
            counts[v] += 1
            if v != "same":
                differences.append({"residue_id": r["residue_id"], "definition": entry["definition"],
                                    "model": [summary(p) for p in entry["components"]],
                                    "rules": [summary(p) for p in rules]})
    return {"counts": dict(counts), "agreement": dict(agreement), "model_links": model_links,
            "differences": differences}


def cases(rows: list) -> list:
    by_id = {r["residue_id"]: r for r in rows}
    out = []
    for rid, exception, analysed, expected, label in CASES:
        row = by_id.get(rid)
        if row is None:
            out.append({"case": label, "status": "missing residue", "expected": expected, "passed": False})
            continue
        entry = row["default"] if exception is None else row["exceptions"][exception]
        got = completeness(entry, analysed)["status"]
        out.append({"case": label, "residue_id": rid, "status": got, "expected": expected,
                    "passed": got == expected, "parts_from": entry.get("parts_from")})
    return out


def markdown(result: dict) -> str:
    c, a = result["comparison"]["counts"], result["comparison"]["agreement"]
    read = c.get("same", 0) + c.get("different", 0)
    lines = [f"Definitions selected from the model: {read} "
             f"(guidance-backed: {c.get('guided_model', 0)}; "
             f"old readings explicitly retained after regression: "
             f"{c.get('legacy_regression_fallback', 0)}); "
             f"not selected from the model: {c.get('rules_only', 0)} "
             f"(source-verified legal guidance: {c.get('legal_guidance', 0)}). "
             f"Compared model/rule agreements: {c.get('same', 0)}, "
             f"differences: {c.get('different', 0)}. "
             f"Model readings rejected because they would lose a rule link: {c.get('model_not_used', 0)}.", "",
             f"Where the rules link a component, the model's PARAM term agrees {a.get('agree', 0)} times "
             f"and disagrees {a.get('disagree', 0)} times.", ""]
    passed = sum(x["passed"] for x in result["cases"])
    lines += [f"Acceptance cases: {passed}/{len(result['cases'])} pass", ""]
    lines += [f"- {'✅' if x['passed'] else '❌'} {x['case']}: {x['status']} (expected {x['expected']})"
              for x in result["cases"]]
    links = result["comparison"]["model_links"]
    if links:
        lines += ["", f"Components linked only by the model ({len(links)}):", ""]
        lines += [f"- {m['component']} → {', '.join(m['param'])} ({m['definition'][:80]})" for m in links]
    differences = result["comparison"]["differences"][:20]
    if differences:
        lines += ["", "Readings that differ (first 20):", ""]
        for d in differences:
            lines += [f"- **{d['definition'][:120]}**",
                      f"  - model: {'; '.join(d['model'])}", f"  - rules: {'; '.join(d['rules'])}"]
    return "\n".join(lines)


def main() -> None:
    with open("data/residue_param_map.json", encoding="utf-8") as fh:
        rows = json.load(fh)
    index = components.ComponentIndex.load()
    result = {"comparison": compare(rows, index), "cases": cases(rows)}
    with open("data/parts_comparison.json", "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
    print(markdown(result))
    if not all(x["passed"] for x in result["cases"]):
        sys.exit(CASES_FAILED)


if __name__ == "__main__":
    main()
