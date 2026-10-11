"""Run the SE/FR validation without any private Git commit history.

The original baseline's whole/component recognition index is retained as compact
code-to-residue fragments in data/baselines/d2d1/. No old commits or personal
author metadata are needed. Outputs must match the original baseline benchmark.

Usage: python -m scripts.portable_validation --countries SE FR
"""
import json
from pathlib import Path

from scripts import validate_monitoring as benchmark

DIRECTORY = Path("data/baselines/d2d1")


def reconstruct_baseline():
    with (DIRECTORY / "manifest.json").open(encoding="utf-8") as stream:
        info = json.load(stream)
    if info != {"commit": benchmark.BASELINE, "residues": 684, "whole": 4, "component": 5}:
        raise RuntimeError("Baseline manifest differs from the verified source")

    by_id = {}
    for kind in ("whole", "component"):
        seen_codes = set()
        for n in range(info[kind]):
            with (DIRECTORY / f"{kind}-{n}.json").open(encoding="utf-8") as stream:
                subset = json.load(stream)
            if seen_codes.intersection(subset):
                raise RuntimeError(f"Overlapping baseline {kind} code segments")
            seen_codes.update(subset)
            for code, owners in subset.items():
                for rid in owners:
                    item = by_id.setdefault(rid, {"whole": [], "component": []})
                    item[kind].append(code)
        expected = {"whole": 623, "component": 730}[kind]
        if len(seen_codes) != expected:
            raise RuntimeError(f"Baseline {kind} index incomplete: {len(seen_codes)} / {expected}")

    if len(by_id) > info["residues"]:
        raise RuntimeError("More baseline residue ids than the original dataset")
    rows = []
    for rid, fields in sorted(by_id.items()):
        rows.append({
            "residue_id": rid, "name": f"baseline-reference-{rid}",
            "default": {
                "method": "exact",
                "param_codes": sorted(fields["whole"]),
                "components": [
                    {"role": "analyte", "method": "family", "param_codes": [c]}
                    for c in sorted(fields["component"])
                ],
            },
            "exceptions": [],
        })

    # The index deliberately omits records with no recognizable code. Preserve
    # their existence in the denominator without inventing matching evidence.
    for i in range(info["residues"] - len(rows)):
        rows.append({
            "residue_id": -(i + 1), "name": f"baseline-unmatched-{i + 1}",
            "default": {"method": "none", "param_codes": [], "components": []},
            "exceptions": [],
        })
    return rows


def main():
    benchmark.load_baseline = reconstruct_baseline
    benchmark.main()


if __name__ == "__main__":
    main()
