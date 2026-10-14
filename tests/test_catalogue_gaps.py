"""Regression tests for the 2026 Benthiavalicarb legal/PARAM scope gap."""
import json
from pathlib import Path
import unittest

from rd_bridge import catalogue_gaps, match
from rd_bridge.components import ComponentIndex
from rd_bridge.resolve import Resolver

ROOT = Path(__file__).resolve().parents[1]


class CatalogueGapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = ComponentIndex.load(str(ROOT / "data" / "param_components.json"))
        cls.terms = json.loads((ROOT / "data/param_pest_terms.json").read_text(encoding="utf-8"))

    def test_current_eu_definition_has_no_verified_whole_param_code(self):
        definition = catalogue_gaps.BENTHIAVALICARB_2026
        linked = match.Matcher(self.terms).link(definition, "Benthiavalicarb-isopropyl")
        self.assertEqual((linked["method"], linked["param_codes"]), ("none", []))
        issue = catalogue_gaps.explain(definition, linked, self.index)
        self.assertEqual(issue["kind"], "catalogue_scope_mismatch")
        self.assertEqual(issue["applies_from"], "2026-08-12")
        self.assertEqual(issue["param_catalogue_version"], "17.8")
        self.assertEqual([x["code"] for x in issue["related_terms"]],
                         ["RF-00004656-PAR", "RF-0043-003-PPP"])

    def test_record_and_resolver_expose_the_issue_without_a_false_match(self):
        records = json.loads((ROOT / "data/residue_param_map.json").read_text(encoding="utf-8"))
        entry = next(r for r in records if r["residue_id"] == 3950)["default"]
        self.assertEqual((entry["method"], entry["param_codes"]), ("none", []))
        self.assertEqual(entry["catalogue_gap"]["kind"], "catalogue_scope_mismatch")
        result = Resolver.load().resolve("A02LV", "Benthiavalicarb-isopropyl")
        self.assertEqual((result["status"], result["param_codes"]), ("no_param_link", []))
        self.assertEqual(result["catalogue_gap"], entry["catalogue_gap"])
        unmatched = json.loads((ROOT / "data/unmatched.json").read_text(encoding="utf-8"))
        issue = next(r for r in unmatched if r["residue_id"] == 3950)
        self.assertEqual(issue["reason"], "catalogue_scope_mismatch")

    def test_matching_new_catalogue_term_clears_gap_without_manual_review(self):
        definition = catalogue_gaps.BENTHIAVALICARB_2026
        hypothetical = self.terms + [
            {"code": "RF-99999999-PAR", "name": definition, "pestClass": "RD", "cas": None}
        ]
        linked = match.Matcher(hypothetical).link(definition, "Benthiavalicarb-isopropyl")
        self.assertEqual((linked["method"], linked["param_codes"]), ("exact", ["RF-99999999-PAR"]))
        self.assertIsNone(catalogue_gaps.explain(definition, linked, self.index))

    def test_unrelated_missing_links_are_not_misclassified(self):
        missing = {"method": "none", "param_codes": []}
        self.assertIsNone(catalogue_gaps.explain("Ipconazole", missing, self.index))
        self.assertIsNone(catalogue_gaps.explain(
            "Benthiavalicarb (KIF-230 R-L, S-D, S-L, R-D)", missing, self.index))


if __name__ == "__main__":
    unittest.main()
