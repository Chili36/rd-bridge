"""Independently reread disputed EU residue definitions with Claude Sonnet.

The Sonnet prompt receives the EU definition and relevant PARAM family names,
but never the Haiku or rule-parser answers. Afterwards the *same deterministic*
component linker compares the independent Sonnet reading to each existing
candidate. No result in this report is automatically promoted to the mapping.

Usage:
    RD_BRIDGE_MODEL=claude-haiku-5-5 python -m rd_bridge.sonnet_review --limit 12
Requires ANTHROPIC_API_KEY; output JSON and Markdown are audit/review material.
"""
import argparse
import collections
from datetime import datetime, timezone
import json
from pathlib import Path

from rd_bridge import compare_parts, components, llm, model_parts

SONNET = "claude-sonnet-5-5"
FOCUS_IDS = (321, 2655)
MAX_CASES = 20


def linked_codes(parts):
    return {code for p in parts if p.get("role") == "analyte"
            for code in p.get("param_codes", [])}


def priority(model, rules):
    """Prioritize substantive missing or different codes over name-only diffs."""
    a, b = linked_codes(model), linked_codes(rules)
    score = 0
    flags = []
    if a != b:
        score += 100
        flags.append("different PARAM component codes")
    if (bool(a) != bool(b)):
        score += 50
        flags.append("one interpretation lacks any linked component")
    model_groups = {p.get("name") or p.get("text") for p in model if p["role"] == "group"}
    rule_groups = {p.get("name") or p.get("text") for p in rules if p["role"] == "group"}
    if model_groups != rule_groups:
        score += 20
        flags.append("group/coverage difference")
    unlinked_a = {p.get("name") or p.get("text") for p in model
                  if p["role"] == "analyte" and not p.get("param_codes")}
    unlinked_b = {p.get("name") or p.get("text") for p in rules
                  if p["role"] == "analyte" and not p.get("param_codes")}
    if unlinked_a != unlinked_b:
        score += 10
        flags.append("different unlinked analytes")
    return max(score, 1), flags or ["wording/structure difference"]


def review_candidates(rows, index, limit=12, focus=FOCUS_IDS):
    """Find/rank each disagreement and include the two former acceptance cases."""
    if not 1 <= limit <= MAX_CASES:
        raise ValueError(f"--limit must be between 1 and {MAX_CASES}")
    by_id = {r["residue_id"]: r for r in rows}
    candidates = []
    for row in rows:
        for entry in [row["default"], *row["exceptions"]]:
            if entry.get("parts_from") not in ("model", "guided_model", "legacy_regression_fallback"):
                continue
            rules = index.describe(entry["definition"], entry, row["name"])
            if compare_parts.verdict(entry["components"], rules) == "same":
                continue
            score, flags = priority(entry["components"], rules)
            candidates.append({
                "residue_id": row["residue_id"],
                "definition": entry["definition"],
                "score": score,
                "flags": flags,
                "source": "model_vs_rules",
            })
    candidates.sort(key=lambda x: (-x["score"], x["residue_id"], x["definition"]))

    # "limit" is the total number of calls, not limit + focus; no accidental
    # extra cost. A focused ID already in the ranked list is not duplicated.
    focused = []
    for rid in focus:
        row = by_id.get(rid)
        if row is None:
            raise ValueError(f"Focus residue {rid} is missing")
        value = next((x for x in candidates if x["residue_id"] == rid
                      and x["definition"] == row["default"]["definition"]), None)
        focused.append(value or {
            "residue_id": rid, "definition": row["default"]["definition"],
            "score": 0, "flags": ["former acceptance test"], "source": "acceptance",
        })
    chosen = list(focused)
    keys = {(x["residue_id"], x["definition"]) for x in chosen}
    for case in candidates:
        key = case["residue_id"], case["definition"]
        if len(chosen) >= limit:
            break
        if key not in keys:
            chosen.append(case)
            keys.add(key)
    return chosen[:limit], candidates


def call_sonnet(system, prompt, schema):
    # Output is a reading of public EU text, not a judgement of legal compliance.
    return llm.call(system, prompt, schema, model=SONNET,
                    max_tokens=5000, retries=3)


def inspect_case(case, row, index, caller=call_sonnet):
    entry = next(e for e in [row["default"], *row["exceptions"]]
                 if e["definition"] == case["definition"])
    names = model_parts.context(index, entry["definition"], [row["name"]])
    # Do NOT show Sonnet the earlier model/rules interpretations: blind reread.
    reading = model_parts.ask(entry["definition"], names, caller=caller)
    parsed = model_parts.as_parts(reading, entry["definition"])
    sonnet = index.describe(entry["definition"], entry, row["name"], parsed)
    rules = index.describe(entry["definition"], entry, row["name"])
    model = entry["components"]
    matches_model = compare_parts.verdict(sonnet, model) == "same"
    matches_rules = compare_parts.verdict(sonnet, rules) == "same"
    alignment = ("both" if matches_model and matches_rules
                 else "haiku" if matches_model else "rules" if matches_rules
                 else "neither")
    return {
        **case,
        "residue_name": row["name"],
        "whole_residue_param_codes": entry.get("param_codes", []),
        "reading": reading,
        "sonnet_parts": sonnet,
        "haiku_parts": model,
        "rule_parts": rules,
        "alignment": alignment,
        "human_review_required": True,
    }


def run(rows, index, limit=12, caller=call_sonnet):
    chosen, all_disagreements = review_candidates(rows, index, limit=limit)
    by_id = {r["residue_id"]: r for r in rows}
    cases = []
    for case in chosen:
        try:
            cases.append(inspect_case(case, by_id[case["residue_id"]], index, caller))
        except (llm.LLMError, ValueError, KeyError, TypeError) as exc:
            # Preserve the case even when Sonnet fails; do not claim success.
            cases.append({**case, "alignment": "model_error",
                          "error_type": type(exc).__name__,
                          "human_review_required": True})
    return {
        "model": SONNET,
        "method": "blind independent reading, then deterministic PARAM linking",
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_model_rule_disagreements": len(all_disagreements),
        "selected_cases": len(chosen),
        "cases": cases,
    }


def markdown(report):
    tally = collections.Counter(x["alignment"] for x in report["cases"])
    lines = [
        "# Independent Sonnet review of RD component disagreements", "",
        f"Sonnet model: `{report['model']}`",
        f"Disagreements eligible for review: **{report['total_model_rule_disagreements']}**",
        f"Cases independently reread: **{report['selected_cases']}**",
        f"Alignment: {dict(tally)}", "",
        "**This is a model-generated second opinion, not independently verified "
        "chemical evidence or a legal interpretation.** No proposed links or "
        "decisions are automatically merged.", "",
        "| RD ID | Score | Sonnet aligns with | Priority reasons |",
        "| ---: | ---: | --- | --- |",
    ]
    for case in report["cases"]:
        flags = "; ".join(case["flags"])
        lines.append(f"| {case['residue_id']} | {case['score']} | "
                     f"{case['alignment']} | {flags} |")
    for case in report["cases"]:
        lines.extend(["", f"## Residue {case['residue_id']}: {case['definition']}", "",
                      f"Reason: {', '.join(case['flags'])}.",
                      f"Sonnet alignment: **{case['alignment']}**."])
        if "error_type" in case:
            lines.append("The model call failed (" + case["error_type"] +
                         "); no judgement has been made.")
        else:
            lines += ["", "Sonnet parts:", ""]
            for part in case["sonnet_parts"]:
                if part.get("role") in ("analyte", "group"):
                    lines.append("- " + compare_parts.summary(part))
            lines += ["", "See the accompanying JSON for both previous readings, "
                      "the Sonnet reading and the actual PARAM codes.", ""]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--output", type=Path,
                        default=Path("reports/sonnet_review.json"))
    args = parser.parse_args()
    if not __import__("os").environ.get("ANTHROPIC_API_KEY"):
        parser.error("ANTHROPIC_API_KEY is required; refusing a fake model review")
    with Path("data/residue_param_map.json").open(encoding="utf-8") as fh:
        rows = json.load(fh)
    index = components.ComponentIndex.load()
    report = run(rows, index, limit=args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    args.output.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
    count = collections.Counter(c["alignment"] for c in report["cases"])
    print(f"Sonnet: {report['selected_cases']}/{report['total_model_rule_disagreements']}"
          f" targeted cases; alignment: {dict(count)}")
    if count["model_error"]:
        raise SystemExit("Some Sonnet evaluations failed; review partial output")


if __name__ == "__main__":
    main()
