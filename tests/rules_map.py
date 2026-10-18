"""The committed map with every definition's components re-read by the rule parser.

The committed data/residue_param_map.json holds model readings once the Model readings
workflow has run, and model-guessed whole-definition links (rd_bridge.model_match); tests
about the rule parser and linking must not depend on them, so both are undone here.
"""
import functools
import json
from pathlib import Path

from rd_bridge.components import ComponentIndex

ROOT = Path(__file__).resolve().parent.parent


@functools.lru_cache(maxsize=1)
def _rows() -> str:
    index = ComponentIndex.load(ROOT / "data" / "param_components.json")
    rows = json.loads((ROOT / "data" / "residue_param_map.json").read_text())
    for r in rows:
        for entry in [r["default"], *r["exceptions"]]:
            if entry.get("method") == "model":
                entry["method"] = entry["evidence"]["rule_method"]
                entry["param_codes"] = entry["evidence"]["rule_codes"]
            entry["components"] = index.describe(entry["definition"], entry, r["name"])
            entry["parts_from"] = "rules"
    return json.dumps(rows)


def rule_rows() -> list:
    """A fresh copy each call, so a test cannot change another test's rows."""
    return json.loads(_rows())
