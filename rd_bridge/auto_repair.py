"""Automatically repair failed RD interpretation regression checks.

This is a bounded closed-loop step between interpretation and adoption:
detect failing existing tests -> use EU wording, source-backed OECD/EFSA
guidance, EFSA PARAM metadata and explicit failure feedback -> ask Sonnet to
reinterpret only the affected text -> rebuild -> check all relevant cases.

If a model cannot fix a regression, retain the PREVIOUS known working model
reading for that exact text (with explicit provenance), not the bad new
reading. This avoids a five-case failure throwing away 760 successful
interpretations. No tests, legal definitions or expectations are rewritten.
No unavailable independent gold-standard dataset is required.
"""
import argparse
import collections
import json
from pathlib import Path

from rd_bridge import (compare_parts, components, guided_model_parts,
                       llm, match, model_match, model_parts)

ROOT = guided_model_parts.ROOT
SONNET = "claude-sonnet-5-5"
POLICY = """
REPAIR A FAILED EU RESIDUE-DEFINITION READING.
Use the original EU wording as the legal source. OECD/EFSA guidance and
the actual PARAM catalogue identify interpretation and reporting concepts;
neither a test nor a model is allowed to invent a new chemical component.
The previous reading was accepted for some coverage checks, but is NOT an
independent legal gold standard. Fix the specific logical contradiction.

Distinguish the whole EU residue definition from individual analytes and
from generic active substances. The name after 'expressed as' is not
automatically a measured parent. Do not add unnamed isomers as separately
measured analytes unless the legal wording/correct PARAM term warrants it.
Where degradation products are 'determined as' a named product, distinguish
the measured marker from its precursor coverage; do not invent another
unmeasured group. Never claim that measuring a generic AS automatically
covers a different legally defined summed residue. Prefer an explicit
qualification to invented chemical identity. Return the actual required
parts in the existing structured schema.
"""


def load_inputs(root=ROOT):
    root = Path(root)
    def read(path):
        return json.loads((root / path).read_text(encoding="utf-8"))
    return (read("data/residues_en.json"), read("data/param_pest_terms.json"),
            components.ComponentIndex.load(str(root / "data/param_components.json")))


def failed_specs(rows):
    """Return failed acceptance scenarios with exact RD ID and exception index."""
    cases = compare_parts.cases(rows)
    if len(cases) != len(compare_parts.CASES):
        raise ValueError("Acceptance metadata changed while diagnosing failures")
    return [
        {"residue_id": rid, "exception": exc, "analysed": codes,
         "expected": expected, "label": label, "actual": observed["status"]}
        for (rid, exc, codes, expected, label), observed
        in zip(compare_parts.CASES, cases) if not observed["passed"]
    ]


def scenarios_for(residue_id):
    return [(exc, codes, expected, label)
            for rid, exc, codes, expected, label in compare_parts.CASES
            if rid == residue_id]


def check_residue(row, residue_id):
    """Must fix the failing case without breaking another case on that RD."""
    outcomes = []
    for exc, codes, expected, label in scenarios_for(residue_id):
        entry = row["default"] if exc is None else row["exceptions"][exc]
        got = components.completeness(entry, codes)["status"]
        outcomes.append({"case": label, "expected": expected, "actual": got,
                         "passed": got == expected})
    return outcomes


def definition_for(rows, rid, exc):
    row = next((r for r in rows if r["residue_id"] == rid), None)
    if row is None:
        raise ValueError("Missing EU residue " + str(rid))
    entry = row["default"] if exc is None else row["exceptions"][exc]
    return row, entry


def reference_terms(entry, previous, catalogue):
    codes = set(entry.get("param_codes", []))
    for e in (entry, previous):
        for p in e.get("components", []):
            codes.update(p.get("param_codes", []))
    return [{"code": code,
             "name": catalogue.terms.get(code, {}).get("name"),
             "pest_class": catalogue.terms.get(code, {}).get("pest_class", []),
             "reportable": catalogue.terms.get(code, {}).get("reportable")}
            for code in sorted(codes)]


def repairing_prompt(definition, entry, original, scenarios, catalogue,
                     attempted=None):
    terms = reference_terms(entry, original, catalogue)
    previous = [{"role": p["role"], "name": p.get("name") or p.get("text"),
                 "param_codes": p.get("param_codes", [])}
                for p in original.get("components", [])]
    candidate = [{"role": p["role"], "name": p.get("name") or p.get("text"),
                  "param_codes": p.get("param_codes", [])}
                 for p in entry.get("components", [])]
    result = {
        "EU_definition": definition,
        "whole_RD_PARAM_codes": entry.get("param_codes", []),
        "current_guided_reading": candidate,
        "previous_accepted_reading_for_comparison_only": previous,
        "relevant_PARAM_term_metadata": terms,
        "existing_regression_scenarios": scenarios,
        "previous_attempt": attempted,
    }
    return ("\n\nAutomated consistency feedback. These EXISTING scenarios "
            "have fixed expectations. Do not change them; reinterpret the "
            "actual EU definition according to its guidance and PARAM terms.\n"
            + json.dumps(result, ensure_ascii=False, indent=2))


def sonnet(system, prompt, schema):
    return llm.call(system, prompt, schema, model=SONNET, max_tokens=6000,
                    retries=3)


def guided_record(answer, definition, ctx, *, data, provenance, **details):
    """Wrap a structured reading in the existing versioned guidance envelope."""
    ids = [r["id"] for r in guided_model_parts.select(
        definition, is_exception=ctx["is_exception"], data=data)]
    digest = guided_model_parts.guidance_hash(data)
    return {
        **model_parts.clean(answer, ctx["family"]),
        "context": model_parts.context_hash(ctx["family"]),
        "guidance_context": guided_model_parts.contextual_hash(
            ctx["family"], ids, digest),
        "guidance_ids": ids,
        "guidance_version": digest,
        "prompt_variant": guided_model_parts.PROMPT_VERSION,
        "interpretation_source": provenance,
        **details,
    }


def rebuild(raw, terms, index, answers, root=ROOT):
    """Full reconstruction uses the original full EU records and PARAM matcher."""
    # All old baseline cache answers are present for definitions not in guided
    # results; no source or whole-RD text is changed by this step.
    base = model_parts.load(str(Path(root) / "data/model_parts.json"))
    guesses = model_match.load(str(Path(root) / "data/model_matches.json"))
    return match.build(raw, terms, index, {**base, **answers}, guesses)


def fix_regressions(baseline, answers, *, raw, terms, index, data=None,
                    caller=sonnet, max_rounds=2, max_calls=12):
    if max_rounds < 0 or max_calls < 0:
        raise ValueError("max_rounds and max_calls cannot be negative")
    data = data or guided_model_parts.catalogue()
    baseline_by_id = {r["residue_id"]: r for r in baseline}
    context = guided_model_parts.contexts(baseline, index)
    rows = rebuild(raw, terms, index, answers)
    initial = failed_specs(rows)
    log = []
    calls = 0

    for round_number in range(1, max_rounds + 1):
        failed = failed_specs(rows)
        if not failed or calls >= max_calls:
            break
        targets = list(dict.fromkeys((x["residue_id"], x["exception"])
                                     for x in failed))
        improved = False
        for rid, exc in targets:
            if calls >= max_calls:
                break
            _, current = definition_for(rows, rid, exc)
            _, original = definition_for(baseline, rid, exc)
            definition = current["definition"]
            if definition not in context or definition not in answers:
                raise ValueError("Missing versioned guided interpretation: " + definition)
            scenarios = [s for s in failed if s["residue_id"] == rid]
            previous_attempt = next((x for x in reversed(log)
                                     if x["residue_id"] == rid
                                     and x["definition"] == definition), None)
            background = repairing_prompt(
                definition, current, original, scenarios, index, previous_attempt)
            def call_with_feedback(system, prompt, schema):
                return caller(system + "\n" + POLICY, prompt + background, schema)
            calls += 1
            attempt = {"round": round_number, "residue_id": rid,
                       "definition": definition, "attempt": "sonnet",
                       "reason": [s["label"] for s in scenarios]}
            try:
                candidate = guided_model_parts.ask(
                    definition, context[definition]["family"],
                    is_exception=context[definition]["is_exception"],
                    data=data, caller=call_with_feedback)
                candidate.update(
                    interpretation_source="guided_validation_repair",
                    model_used=SONNET, repair_round=round_number)
                tentative = dict(answers)
                tentative[definition] = candidate
                rebuilt = rebuild(raw, terms, index, tentative)
                updated = next(r for r in rebuilt if r["residue_id"] == rid)
                checks = check_residue(updated, rid)
                attempt["checks"] = checks
                attempt["accepted"] = all(s["passed"] for s in checks)
                if attempt["accepted"]:
                    answers[definition] = candidate
                    rows = rebuilt
                    improved = True
                else:
                    attempt["reason_failed"] = "Existing acceptance cases still fail"
            except (llm.LLMError, ValueError, KeyError, TypeError) as excp:
                attempt["accepted"] = False
                attempt["error"] = f"{type(excp).__name__}: {excp}"
            log.append(attempt)
        if not improved:
            break

    # If the source-backed retry did not satisfy the known regression, prefer
    # the same definition's previous passing reading over a newly *worse*
    # output. This is a documented local fallback, not a fabricated correction.
    remaining = failed_specs(rows)
    reverts = []
    prior = model_parts.load()
    for rid, exc in dict.fromkeys((x["residue_id"], x["exception"])
                                  for x in remaining):
        _, entry = definition_for(rows, rid, exc)
        definition = entry["definition"]
        if definition not in prior:
            raise ValueError("No baseline reading for failed definition: " + definition)
        ctx = context[definition]
        record = guided_record(
            prior[definition], definition, ctx, data=data,
            provenance="legacy_retained_after_regression",
            model_used="claude-haiku-5-5 (old cache)",
            requires_followup=True,
            reason="Source-guided reading failed existing automated tests; "
                   "previous exact-definition reading retained.",
        )
        trial = dict(answers)
        trial[definition] = record
        built = rebuild(raw, terms, index, trial)
        candidate = next(x for x in built if x["residue_id"] == rid)
        if not all(v["passed"] for v in check_residue(candidate, rid)):
            raise ValueError("Previous reading does not restore known acceptance checks: "
                             + definition)
        answers[definition] = record
        rows = built
        reverts.append({"residue_id": rid, "definition": definition,
                        "reason": "previous passing interpretation retained"})

    final = failed_specs(rows)
    # Never claim success if failures remain or if source coverage changed.
    if final:
        raise ValueError("Unresolved known acceptance cases after repair/fallback: "
                         + repr(final))
    original_ids = {(r["residue_id"], e["definition"]) for r in baseline
                    for e in [r["default"], *r["exceptions"]]}
    new_ids = {(r["residue_id"], e["definition"]) for r in rows
               for e in [r["default"], *r["exceptions"]]}
    if original_ids != new_ids:
        raise ValueError("Automatic repair changed the EU definition set")
    for row in rows:
        prev = baseline_by_id[row["residue_id"]]
        for old, now in zip([prev["default"], *prev["exceptions"]],
                            [row["default"], *row["exceptions"]]):
            if old["definition"] != now["definition"] or old["param_codes"] != now["param_codes"]:
                raise ValueError("Automatic repair modified whole-RD PARAM links")
    return rows, {"initial": initial, "attempts": log,
                  "sonnet_calls": calls,
                  "model_repairs_accepted": sum(x.get("accepted", False) for x in log),
                  "legacy_readings_retained": reverts,
                  "remaining": final,
                  "final_passed": len(compare_parts.CASES),
                  "final_total": len(compare_parts.CASES),
                  "guidance_version": guided_model_parts.guidance_hash(data)}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--baseline", type=Path, required=True,
                        help="previous main reference, before guided migration")
    parser.add_argument("--max-rounds", type=int, default=2)
    parser.add_argument("--max-calls", type=int, default=12)
    parser.add_argument("--report", type=Path,
                        default=Path("reports/automatic_interpretation_repair.json"))
    args = parser.parse_args()
    old = json.loads(args.baseline.read_text(encoding="utf-8"))
    cache = guided_model_parts.load()
    if not cache:
        raise ValueError("No guidance-backed cache: nothing to repair")
    raw, terms, index = load_inputs()
    updated, summary = fix_regressions(
        old, cache, raw=raw, terms=terms, index=index,
        max_rounds=args.max_rounds, max_calls=args.max_calls)
    guided_model_parts.save(cache)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    Path("data/residue_param_map.json").write_text(
        json.dumps(updated, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Automatic feedback loop: {len(summary['initial'])} failing tests, "
          f"{summary['sonnet_calls']} targeted Sonnet calls, "
          f"{summary['model_repairs_accepted']} repaired, "
          f"{len(summary['legacy_readings_retained'])} previous readings retained; "
          f"{summary['final_passed']}/{summary['final_total']} acceptance tests pass.")


if __name__ == "__main__":
    main()
