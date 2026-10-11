"""Regressions for EFSA-supported PARAM-only components (issue #26)."""
import json
import unittest
from pathlib import Path

from rd_bridge import evidence_parts
from rd_bridge.components import ComponentIndex, completeness
from rd_bridge.match import build

ROOT = Path(__file__).resolve().parent.parent
CODES = {code for code, _, _ in evidence_parts.MEMBERS}


class DocumentedComponentsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = ComponentIndex.load(ROOT / "data" / "param_components.json")
        with open(ROOT / "data" / "residues_en.json", encoding="utf-8") as f:
            cls.residues = [r for r in json.load(f) if r["pesticide_residue_id"] == 366]
        with open(ROOT / "data" / "param_pest_terms.json", encoding="utf-8") as f:
            cls.terms = json.load(f)

    def test_all_six_are_named_and_evidenced(self):
        entry = build(self.residues, self.terms, self.index)[0]["default"]
        self.assertEqual(entry["parts_from"], "published_evidence")
        self.assertEqual(len(entry["components"]), 6)
        self.assertEqual({c for p in entry["components"] for c in p["param_codes"]}, CODES)
        self.assertEqual(entry["param_codes"], [evidence_parts.PYRETHRINS])
        methods = {c: p["method"] for p in entry["components"] for c in p["param_codes"]}
        for code in CODES:
            self.assertEqual(methods[code], ("param_hierarchy" if code.startswith("RF-0374-")
                                             else "scientific_definition"))
        for part in entry["components"]:
            sources = part["evidence"]["sources"]
            self.assertTrue(any(s["authority"] == "EFSA" for s in sources))

    def test_completeness_requires_all_six_when_no_summed_code_reported(self):
        entry = build(self.residues, self.terms, self.index)[0]["default"]
        self.assertEqual(completeness(entry, CODES)["status"], "complete")
        self.assertEqual(completeness(entry, CODES - {"RF-1066-003-PPP"})["status"], "partial")
        self.assertEqual(completeness(entry, ["RF-0374-001-PPP"])["status"], "complete")
        self.assertEqual(completeness(entry, ["RF-0374-001-PPP"])["via"], "summed code")

    def test_not_inferred_for_unrelated_single_substance(self):
        p = evidence_parts.documented_components(
            "Phosmet", {"method": "exact", "param_codes": ["RF-0338-002-PPP"]}, self.index)
        self.assertEqual(p, [])

    def test_not_guessed_if_param_whole_is_wrong(self):
        p = evidence_parts.documented_components(
            "Pyrethrins", {"method": "near", "param_codes": ["RF-0374-001-PPP"]}, self.index)
        self.assertEqual(p, [])

    def test_raises_if_param_source_changes(self):
        data = {"terms": dict(self.index.terms)}
        data["terms"]["RF-1066-002-PPP"] = {
            **data["terms"]["RF-1066-002-PPP"], "cas": "WRONG"}
        with self.assertRaisesRegex(ValueError, "RF-1066-002"):
            evidence_parts.documented_components(
                "Pyrethrins", {"method": "exact", "param_codes": ["RF-0374-001-PPP"]},
                ComponentIndex(data))

    def test_committed_map_is_regenerated(self):
        with open(ROOT / "data" / "residue_param_map.json", encoding="utf-8") as f:
            rows = json.load(f)
        entry = next(r["default"] for r in rows if r["residue_id"] == 366)
        self.assertEqual(entry["parts_from"], "published_evidence")
        self.assertEqual({c for p in entry["components"] for c in p["param_codes"]}, CODES)


if __name__ == "__main__":
    unittest.main()
