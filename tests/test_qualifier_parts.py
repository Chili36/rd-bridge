"""Regression tests for explicit PARAM forms covered by qualifiers."""
import unittest
from pathlib import Path

from rd_bridge import qualifier_parts
from rd_bridge.components import ComponentIndex
from tests.rules_map import rule_rows

ROOT = Path(__file__).resolve().parent.parent


class QualifierComponentsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = ComponentIndex.load(ROOT / "data" / "param_components.json")
        cls.residues = {r["residue_id"]: r for r in rule_rows()}

    def qualified(self, residue_id, exception=None):
        row = self.residues[residue_id]
        entry = row["default"] if exception is None else row["exceptions"][exception]
        return entry.get("qualifier_components", [])

    def test_fluazifop_p_butyl_is_part_by_ester_qualifier(self):
        found = self.qualified(304)
        by_code = {code: p for p in found for code in p["param_codes"]}
        for code in ("RF-0197-002-PPP", "RF-0699-001-PPP", "RF-0699-002-PPP"):
            self.assertEqual(by_code[code]["method"], "qualifier")
            self.assertEqual(by_code[code]["qualifier"], "esters")

    def test_glufosinate_ammonium_is_covered_by_salts(self):
        found = [p for row in self.residues.values()
                 for entry in [row["default"], *row["exceptions"]]
                 for p in entry.get("qualifier_components", [])
                 if "RF-0231-001-PPP" in p["param_codes"]]
        self.assertTrue(found)
        self.assertTrue(all(p["qualifier"] == "salts" for p in found))

    def test_no_inferred_ester_when_only_salts_are_named(self):
        # A plain salt/conjugate exception must not adopt a methyl ester.
        definition = "Sum of haloxyfop, its salts and conjugates expressed as haloxyfop"
        found = qualifier_parts.covered(definition, self.index)
        self.assertFalse(any("RF-0235-002-PPP" in p["param_codes"] for p in found))

    def test_pyrethrins_not_inferred_from_qualifier(self):
        self.assertEqual(self.qualified(366), [])
        self.assertEqual(qualifier_parts.covered("Pyrethrins", self.index), [])

    def test_no_obsolete_phosmet_oxon(self):
        self.assertEqual(self.qualified(3190), [])

    def test_qualifier_links_do_not_change_completeness(self):
        from rd_bridge.components import completeness
        entry = self.residues[304]["default"]
        # No individual ester is treated as proof of the full summed residue.
        result = completeness(entry, ["RF-0197-002-PPP"])
        self.assertNotEqual(result["status"], "complete")


if __name__ == "__main__":
    unittest.main()
