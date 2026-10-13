"""Audit every frozen RD interpretation disagreement against source evidence.

The 40-item baseline is kept immutable to distinguish an actual legal
correction from silently reducing a disagreement count. The output labels
literal aliases as wording resolutions, and source-verified interpretations
as resolved; all other differences remain review items. No LLM voting.
"""
import argparse
import collections
import json
from pathlib import Path
import re

from rd_bridge import guidance

BASELINE = Path("reports/guidance_baseline_2026-10-13.json")
REFERENCE = Path("data/residue_param_map.json")
OUTPUT = Path("reports/guidance_audit.json")

PARAM = re.compile(r"RF-[0-9A-Z-]+")
CATEGORY_ORDER = {
    "legal_source_resolved": 0,
    "source_wording_resolved": 1,
    "component_code_conflict": 2,
    "component_scope_conflict": 3,
    "unlinked_component_identity": 4,
    "naming_or_qualifier_difference": 5,
}


def summaries_codes(parts: list) -> set:
    """Get PARAM codes from the previously recorded, readable part summaries."""
    return {code for part in parts for code in PARAM.findall(part)}


def have_group(parts: list) -> bool:
    return any("[group:" in part for part in parts)


def entry_for(rows: list, residue_id: int, definition: str) -> dict:
    row = next((r for r in rows if r["residue_id"] == residue_id), None)
    if row is None:
        raise ValueError(f"Reference is missing residue {residue_id}")
    matches = [e for e in [row["default"], *row["exceptions"]]
               if e["definition"] == definition]
    if len(matches) != 1:
        raise ValueError(f"Not exactly one definition for residue {residue_id}: {definition}")
    return matches[0]


def classify(diff: dict, entry: dict) -> dict:
    """Conservative, explainable triage. Only original source resolves scope."""
    original = diff["definition"]
    left, right = summaries_codes(diff["model"]), summaries_codes(diff["rules"])
    group_difference = have_group(diff["model"]) != have_group(diff["rules"])
    base = {
        "residue_id": diff["residue_id"],
        "definition": original,
        "whole_rd_param_codes": entry.get("param_codes", []),
        "model_component_codes": sorted(left),
        "parser_component_codes": sorted(right),
        "model_reading": diff["model"],
        "parser_reading": diff["rules"],
        "current_parts_from": entry.get("parts_from"),
    }
    evidence = entry.get("interpretation_evidence")
    if (entry.get("parts_from") == "legal_guidance" and evidence
            and evidence.get("rule_id") == "EU-2023-710-CHLORIDAZON-R"):
        return {
            **base,
            "category": "legal_source_resolved",
            "review_status": "source_verified",
            "resolution": "The legally defined exception names chloridazon-desphenyl "
                          "as the measured component, with chloridazon as expression basis.",
            "evidence": evidence,
        }
    if guidance.lexical_alias_candidate(original) and left == right and not group_difference:
        return {
            **base,
            "category": "source_wording_resolved",
            "review_status": "wording_only",
            "resolution": "The supplied EU wording marks an alias/previous name/identifier. "
                          "It is not by itself a second chemical component; no PARAM link "
                          "has been changed or chemically validated.",
            "evidence": {"source": "EU Pesticides Database, exact quoted definition",
                         "text": original},
        }
    if left != right:
        category = "component_code_conflict"
        reason = ("The interpreters linked different component PARAM codes. "
                  "Resolve from the EU wording, linked legal residue-definition "
                  "entry and EFSA catalogue—not a vote.")
    elif group_difference:
        category = "component_scope_conflict"
        reason = ("The readings disagree whether a separately relevant "
                  "unbounded group of residues is part of the definition.")
    elif not left and not right:
        category = "unlinked_component_identity"
        reason = ("Neither reading establishes a component PARAM link. "
                  "Resolve the named species/chemical identity before mapping.")
    else:
        category = "naming_or_qualifier_difference"
        reason = ("Linked component codes agree, but wording, qualifiers or "
                  "component structure differ. Review before calling it harmless.")
    return {
        **base,
        "category": category,
        "review_status": "requires_source_review",
        "resolution": reason,
        "evidence": {
            "EU_definition": original,
            "efsa_param_guidance": guidance.SOURCES["efsa_chemmon_2026"],
            "oecd_context_not_binding_rule": guidance.SOURCES["oecd_dor_2009"],
        },
    }


def build(baseline: dict, rows: list) -> dict:
    if baseline.get("discrepancy_count") != len(baseline.get("differences", [])):
        raise ValueError("Baseline disagreement count is not self-consistent")
    findings = []
    for diff in baseline["differences"]:
        entry = entry_for(rows, diff["residue_id"], diff["definition"])
        findings.append(classify(diff, entry))
    unique = {(f["residue_id"], f["definition"]) for f in findings}
    if len(unique) != len(findings):
        raise ValueError("Baseline contains duplicate entries")
    counts = collections.Counter(f["category"] for f in findings)
    statuses = collections.Counter(f["review_status"] for f in findings)
    return {
        "purpose": "Source-grounded audit of original model-versus-parser disagreements, not model accuracy.",
        "source_snapshot": baseline["source_snapshot"],
        "param_catalogue_version": baseline["efsa_param_version"],
        "method": "exact legal-source correction > explicit EU naming evidence > unresolved",
        "source_hierarchy": {
            "specific_legislation": guidance.SOURCES["eu_chloridazon_2023_710"],
            "current_efsa_reporting": guidance.SOURCES["efsa_chemmon_2026"],
            "oecd_scope_context": guidance.SOURCES["oecd_dor_2009"],
            "historical_efsa_examples_not_current": guidance.SOURCES["efsa_reporting_2019_historical"],
        },
        "total_original_differences": len(findings),
        "by_category": dict(sorted(counts.items())),
        "by_status": dict(sorted(statuses.items())),
        "findings": findings,
    }


def markdown(result: dict) -> str:
    lines = [
        "# Source-grounded review of the original 40 RD discrepancies",
        "",
        "The 40-item baseline is frozen. **Disagreement is not proof that either "
        "parser or model is wrong.** Evidence from the EU legal definition "
        "takes precedence over model agreement.",
        "",
        f"Cases: **{result['total_original_differences']}**. "
        f"Review statuses: {result['by_status']}.",
        "",
        "EFSA's current reporting guidance is 2026; the 2019 pesticide-only "
        "guidance is OBSOLETE and is listed only for its historical worked examples.",
        "",
        "| RD | Type | Status | Interpretation issue |",
        "| ---: | --- | --- | --- |",
    ]
    for f in result["findings"]:
        reason = f["resolution"].replace("|", "/")
        lines.append(f"| {f['residue_id']} | {f['category']} | "
                     f"{f['review_status']} | {reason} |")
    lines.extend([
        "",
        "## Sources",
        "",
        "- [EU Regulation 2023/710, Chloridazon (R) footnote]"
        f"({guidance.SOURCES['eu_chloridazon_2023_710']['url']}).",
        "- [EFSA 2026 chemical monitoring reporting guidance]"
        f"({guidance.SOURCES['efsa_chemmon_2026']['url']}).",
        "- [OECD 2009 definition-of-residue guidance]"
        f"({guidance.SOURCES['oecd_dor_2009']['url']}).",
        "- [EFSA 2019 worked examples (obsolete guidance)]"
        f"({guidance.SOURCES['efsa_reporting_2019_historical']['url']}).",
        "",
        "The machine-readable JSON retains both original readings, their "
        "component PARAM codes, and the reason for each decision.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--reference", type=Path, default=REFERENCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    with args.baseline.open(encoding="utf-8") as fh:
        baseline = json.load(fh)
    with args.reference.open(encoding="utf-8") as fh:
        rows = json.load(fh)
    result = build(baseline, rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    args.output.with_suffix(".md").write_text(markdown(result), encoding="utf-8")
    print(f"Audited {len(result['findings'])} frozen differences: "
          f"{result['by_status']}")


if __name__ == "__main__":
    main()
