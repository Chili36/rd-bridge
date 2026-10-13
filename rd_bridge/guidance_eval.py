"""Bounded baseline-vs-guided evaluation using named EU RD test cases.

The evaluation is a transparent *regression probe* on a small fixed set of
literal, unambiguous definitions. It is NOT an unbiased benchmark of all EU RDs
or evidence of legal compliance. Exploratory cases never count as gold.
The evaluation writes a report, not the production guided cache.
"""
import argparse
import collections
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from rd_bridge import components, guided_model_parts, llm, model_parts

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "rd_guidance_benchmark.json"
DEFAULT_OUTPUT = ROOT / "reports" / "guidance_model_evaluation.json"


def canonical(name):
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


def score(answer, case):
    """Concept checks on extracted analyte names—not PARAM-code matching."""
    if answer is None:
        return {"passed": False, "found": [], "missing": case["required"],
                "prohibited": [], "available": False}
    names = [canonical(p["name"]) for p in answer.get("parts", [])
             if p.get("role") == "analyte"]
    missing = [term for term in case["required"]
               if not any(re.search(term, n) for n in names)]
    prohibited = [term for term in case["forbidden"]
                  if any(re.search(term, n) for n in names)]
    return {"passed": not missing and not prohibited,
            "found": names, "missing": missing, "prohibited": prohibited,
            "available": True}


def picked_case(case, rows):
    row = next((r for r in rows if r["residue_id"] == case["residue_id"]), None)
    if row is None:
        raise ValueError("RD not found " + str(case["residue_id"]))
    e = row["default"] if case["exception"] is None else row["exceptions"][case["exception"]]
    return row, e


def evaluate(fixture, rows, index, *, limit=15, caller=llm.call):
    if limit < 1 or limit > len(fixture["cases"]) + len(fixture["exploratory"]):
        raise ValueError("Unexpected evaluation limit")
    current = guided_model_parts.contexts(rows, index)
    previous = model_parts.load()
    tasks = ([(True, c) for c in fixture["cases"]] +
             [(False, c) for c in fixture["exploratory"]])[:limit]
    findings = []
    for is_gold, case in tasks:
        row, entry = picked_case(case, rows)
        definition = entry["definition"]
        ctx = current[definition]
        # Existing answers do not see guidance; new call explicitly does.
        old = previous.get(definition)
        if old and old.get("context") != model_parts.context_hash(ctx["family"]):
            old = None
        new = guided_model_parts.ask(
            definition, ctx["family"], is_exception=ctx["is_exception"],
            caller=caller)
        item = {
            "case_id": case["id"],
            "residue_id": case["residue_id"],
            "exception": case["exception"],
            "definition": definition,
            "source_evidence": case["source"],
            "guidance_ids": new["guidance_ids"],
            "guided_reading": new,
            "baseline_reading": old,
        }
        if is_gold:
            item["gold_rule_checks"] = {
                "required": case["required"], "forbidden": case["forbidden"]}
            item["baseline"] = score(old, case)
            item["guided"] = score(new, case)
        else:
            item["exploratory_review_only"] = True
        findings.append(item)
    gold = [r for r in findings if "guided" in r]
    base = sum(r["baseline"]["passed"] for r in gold)
    guided = sum(r["guided"]["passed"] for r in gold)
    regressions = [r["case_id"] for r in gold if r["baseline"]["passed"]
                   and not r["guided"]["passed"]]
    improvements = [r["case_id"] for r in gold if not r["baseline"]["passed"]
                    and r["guided"]["passed"]]
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": llm.MODEL,
        "guidance_version": guided_model_parts.guidance_hash(),
        "prompt_version": guided_model_parts.prompt_hash(),
        "scope": "bounded targeted regression; no independent corpus-wide accuracy claim",
        "gold_cases_checked": len(gold),
        "exploratory_cases_checked": len(findings) - len(gold),
        "baseline_gold_passed": base,
        "guided_gold_passed": guided,
        "improvements": improvements,
        "regressions": regressions,
        "safe_to_auto_promote": False,
        "findings": findings,
    }


def markdown(report):
    lines = [
        "# Guidance-in-the-loop evaluation", "",
        f"Model: `{report['model']}`; prompt: `{report['prompt_version']}`; "
        f"guidance: `{report['guidance_version']}`.", "",
        "This evaluates only explicit, preselected EU-text component checks. "
        "**Neither an overall accuracy measure nor an automatic approval.**", "",
        f"Baseline cached Haiku: **{report['baseline_gold_passed']}/"
        f"{report['gold_cases_checked']}** checks passed; guided: "
        f"**{report['guided_gold_passed']}/{report['gold_cases_checked']}**.", "",
        f"Improved: {', '.join(report['improvements']) or 'none'}. "
        f"Regressed: {', '.join(report['regressions']) or 'none'}.", "",
        "| Case | Baseline | Guided | Guidance source IDs |",
        "| --- | --- | --- | --- |",
    ]
    for c in report["findings"]:
        b = ("PASS" if c["baseline"]["passed"] else "FAIL") if "baseline" in c else "review"
        g = ("PASS" if c["guided"]["passed"] else "FAIL") if "guided" in c else "review"
        lines.append(f"| {c['case_id']} | {b} | {g} | "
                     f"{', '.join(c['guidance_ids'])} |")
    lines += ["", "## Readings requiring review", ""]
    for c in report["findings"]:
        if c.get("exploratory_review_only") or not c["guided"]["passed"]:
            lines += [f"### {c['case_id']} — RD {c['residue_id']}", "",
                      f"EU definition: {c['definition']}", ""]
            if "guided" in c:
                lines.append(f"Missing checks: {c['guided']['missing']}; "
                             f"prohibited parts: {c['guided']['prohibited']}.")
            lines += ["Guided extracted analytes: " + "; ".join(
                p["name"] for p in c["guided_reading"].get("parts", [])
                if p.get("role") == "analyte"), ""]
    lines += [
        "## Provenance", "",
        "Rule text, source location and source URL are versioned in "
        "[data/interpretation_guidance.json](../data/interpretation_guidance.json).",
        "Complete prompt-response interpretation objects for every case are "
        "in [guidance_model_evaluation.json](guidance_model_evaluation.json).",
        "No model results are accepted into the PARAM map by this experiment.", ""
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    fixture = json.loads(FIXTURES.read_text(encoding="utf-8"))
    rows = json.loads((ROOT / "data" / "residue_param_map.json").read_text(encoding="utf-8"))
    index = components.ComponentIndex.load(str(ROOT / "data" / "param_components.json"))
    report = evaluate(fixture, rows, index, limit=args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    args.output.with_suffix(".md").write_text(markdown(report) + "\n", encoding="utf-8")
    print(f"Source-guided: {report['guided_gold_passed']}/{report['gold_cases_checked']}, "
          f"baseline: {report['baseline_gold_passed']}/{report['gold_cases_checked']}; "
          f"improved {len(report['improvements'])}, regressed {len(report['regressions'])}. "
          "No production cache modified.")


if __name__ == "__main__":
    main()
