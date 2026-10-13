"""Merge complete guidance-based interpretations, then audit mapping changes.

This is a *migration*, not a search for an unavailable independently reviewed
benchmark. Every unique current EU RD text is reread with versioned guidance.
All prompts, outputs, versions and old answers are retained. Known automated
checks decide whether a change warrants a warning; discrepancies are evidence
for iterative fixes, not a demand for a non-existent validation dataset.

Usage:
  python -m rd_bridge.guided_migration merge --shard-dir shards
  python -m rd_bridge.guided_migration report --baseline /tmp/old-map.json
"""
import argparse
import collections
import json
from pathlib import Path

from rd_bridge import components, guided_model_parts, llm

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "data/residue_param_map.json"
COMPARE = ROOT / "data/parts_comparison.json"
GUIDED_CACHE = ROOT / "data/guided_model_parts.json"
REPORT = ROOT / "reports/full_guidance_migration.md"


def merge_shards(paths, rows, index, *, data=None):
    """Combine complete shard outputs, rejecting missing/old/duplicated answers."""
    data = data or guided_model_parts.catalogue()
    ctxs = guided_model_parts.contexts(rows, index)
    expected = set(ctxs)
    output = {}
    paths = sorted(Path(x) for x in paths)
    if not paths:
        raise ValueError("No shard outputs were provided")
    for path in paths:
        cache = json.loads(path.read_text(encoding="utf-8"))
        if cache.get("model") != llm.MODEL:
            raise ValueError(f"Wrong model in {path}")
        if cache.get("prompt") != guided_model_parts.prompt_hash(data):
            raise ValueError(f"Wrong prompt version in {path}")
        if cache.get("guidance_version") != guided_model_parts.guidance_hash(data):
            raise ValueError(f"Wrong guidance version in {path}")
        shard = cache.get("definitions")
        if not isinstance(shard, dict) or not shard:
            raise ValueError(f"Empty or invalid shard: {path}")
        for definition, reading in shard.items():
            if definition not in expected:
                raise ValueError(f"Unknown definition in {path}: {definition[:80]}")
            if definition in output:
                raise ValueError(f"Duplicate definition across shards: {definition[:80]}")
            if not guided_model_parts.valid(reading, definition, ctxs[definition], data):
                raise ValueError(f"Invalid or outdated guidance record in {path}: {definition[:80]}")
            output[definition] = reading
    missing = expected - set(output)
    if missing:
        raise ValueError(f"Incomplete migration: {len(missing)} of {len(expected)} definitions missing; "
                         f"examples: {sorted(missing)[:3]}")
    return output


def identity(row, definition):
    return row["residue_id"], definition["definition"]


def as_entries(rows):
    return {identity(row, e): e for row in rows
            for e in [row["default"], *row["exceptions"]]}


def measured_parts(entry):
    return sorted((p["role"], p.get("name") or p.get("text") or "",
                   tuple(sorted(p.get("param_codes", []))))
                  for p in entry.get("components", [])
                  if p.get("role") in ("analyte", "group"))


def component_codes(entry):
    return sorted({c for p in entry.get("components", [])
                   if p.get("role") == "analyte"
                   for c in p.get("param_codes", [])})


def compare_maps(previous, updated):
    """Show what changed without declaring model consensus to be ground truth."""
    before, after = as_entries(previous), as_entries(updated)
    if set(before) != set(after):
        raise ValueError("Migration unexpectedly changed the EU RD definitions")
    changed = []
    counts = collections.Counter()
    for key in sorted(before):
        a, b = before[key], after[key]
        if (a.get("method"), a.get("param_codes")) != (b.get("method"), b.get("param_codes")):
            raise ValueError("Migration changed the whole-RD PARAM mapping: " + str(key))
        counts[b.get("parts_from", "unknown")] += 1
        if measured_parts(a) == measured_parts(b):
            continue
        old_codes, new_codes = set(component_codes(a)), set(component_codes(b))
        changed.append({
            "residue_id": key[0],
            "definition": key[1],
            "before_parts_from": a.get("parts_from"),
            "after_parts_from": b.get("parts_from"),
            "before": measured_parts(a),
            "after": measured_parts(b),
            "added_param_codes": sorted(new_codes - old_codes),
            "removed_param_codes": sorted(old_codes - new_codes),
            "same_component_codes": old_codes == new_codes,
        })
    return {"definitions": len(before), "component_changes": changed,
            "parts_from": dict(sorted(counts.items()))}


def markdown(result, compare, *, guided_count, model, guidance_version, alternate_readings=None):
    alternate_readings = alternate_readings or []
    check = compare["cases"]
    passed = sum(x["passed"] for x in check)
    lines = [
        "# Full guidance-based RD reinterpretation", "",
        "**The independent gold-standard dataset requested previously does not exist "
        "and is not a prerequisite for this migration.** Interpretations are "
        "replaced using the best available EU wording, versioned OECD/EFSA "
        "guidance and reproducible automated checks.", "",
        f"- Model: `{model}`; guidance version: `{guidance_version}`",
        f"- **{guided_count} unique EU definition texts** have guidance-versioned interpretations.",
        f"- Definitions in whole-RD map: {result['definitions']}; "
        "whole-RD PARAM codes retained unchanged.",
        f"- Active component interpretations by source: {result['parts_from']}.",
        f"- Alternative model or source-literal fallbacks: {len(alternate_readings)}.",
        f"- Entries whose analyte/group interpretation changed: "
        f"**{len(result['component_changes'])}**.",
        f"- Existing acceptance scenarios: **{passed}/{len(check)} passed**.",
        f"- Model-vs-rule comparisons remaining: "
        f"{compare.get('comparison', {}).get('counts', {}).get('different', 'n/a')}.",
        "",
        "A passed acceptance test is not proof of legal compliance. Real source "
        "and PARAM consistency checks are retained; uncertainty is documented "
        "and improved iteratively, without waiting for an unavailable manual "
        "reference corpus.", "",
        "## Changes to previously assigned component PARAM codes", "",
        "| RD ID | Removed PARAM codes | Added PARAM codes |",
        "| ---: | --- | --- |",
    ]
    if alternate_readings:
        lines += ["", "## Model fallback provenance", "",
                  "These were not Haiku interpretations and are never concealed:", ""]
        for item in alternate_readings:
            lines.append(f"- **{item['definition']}**: {item['interpretation_source']}; "
                         f"model: {item['model_used']}.")
    conflicts = [x for x in result["component_changes"] if not x["same_component_codes"]]
    if not conflicts:
        lines.append("| — | None | None |")
    for item in conflicts:
        removed = ", ".join(item["removed_param_codes"]) or "—"
        added = ", ".join(item["added_param_codes"]) or "—"
        lines.append(f"| {item['residue_id']} | {removed} | {added} |")
    lines.extend(["", "## Failed existing acceptance scenarios", ""])
    failing = [x for x in check if not x["passed"]]
    if failing:
        lines.extend(f"- RD {x.get('residue_id', '?')}: {x['case']}; "
                     f"expected {x['expected']}, got {x['status']}" for x in failing)
    else:
        lines.append("None.")
    lines.extend(["", "## All changed component interpretations", ""])
    for item in result["component_changes"]:
        lines += [f"### RD {item['residue_id']}: {item['definition']}", "",
                  f"Previous: `{item['before_parts_from']}`; "
                  f"new: `{item['after_parts_from']}`.",
                  f"Removed PARAM codes: {item['removed_param_codes']}; "
                  f"added: {item['added_param_codes']}.", "",
                  "Before:", ""]
        lines += ["- " + str(x) for x in item["before"]]
        lines += ["", "After:", ""]
        lines += ["- " + str(x) for x in item["after"]]
        lines.append("")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    combine = sub.add_parser("merge", help="Check every shard and write the complete guided cache")
    combine.add_argument("--shard-dir", type=Path, required=True)
    combine.add_argument("--output", type=Path, default=GUIDED_CACHE)
    report = sub.add_parser("report", help="Compare original and updated component mappings")
    report.add_argument("--baseline", type=Path, required=True)
    report.add_argument("--updated", type=Path, default=MAP)
    report.add_argument("--comparison", type=Path, default=COMPARE)
    report.add_argument("--output", type=Path, default=REPORT)
    args = parser.parse_args()

    if args.command == "merge":
        rows = json.loads(MAP.read_text(encoding="utf-8"))
        index = components.ComponentIndex.load(str(ROOT / "data/param_components.json"))
        merged = merge_shards(args.shard_dir.glob("*.json"), rows, index)
        guided_model_parts.save(merged, args.output)
        print(f"Merged {len(merged)} complete guided interpretations to {args.output}")
        return

    previous = json.loads(args.baseline.read_text(encoding="utf-8"))
    updated = json.loads(args.updated.read_text(encoding="utf-8"))
    comparison = json.loads(args.comparison.read_text(encoding="utf-8"))
    guide = guided_model_parts.load()
    if not guide:
        raise ValueError("Cannot report migration without a current guided cache")
    result = compare_maps(previous, updated)
    alternate = [{
        "definition": definition,
        "interpretation_source": answer.get("interpretation_source", "model"),
        "model_used": answer.get("model_used", llm.MODEL),
    } for definition, answer in guide.items()
        if answer.get("interpretation_source") == "exact_EU_literal_fallback"
        or answer.get("model_used") not in (None, llm.MODEL)]
    text = markdown(result, comparison, guided_count=len(guide),
                    model=llm.MODEL, guidance_version=guided_model_parts.guidance_hash(),
                    alternate_readings=alternate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    summary_path = args.output.with_suffix(".json")
    summary_path.write_text(json.dumps({
        **result, "guided_readings": len(guide),
        "alternate_readings": alternate,
        "model": llm.MODEL,
        "guidance_version": guided_model_parts.guidance_hash(),
        "acceptance_passed": sum(c["passed"] for c in comparison["cases"]),
        "acceptance_total": len(comparison["cases"]),
        "acceptance_failures": [c for c in comparison["cases"] if not c["passed"]],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(guide)} guided readings, {len(result['component_changes'])} "
          f"component changes, {sum(c['passed'] for c in comparison['cases'])}/"
          f"{len(comparison['cases'])} acceptance checks")


if __name__ == "__main__":
    main()
