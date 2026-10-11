"""Offline tests for reproducible monitoring comparison; no Zenodo downloads."""
import unittest

from rd_bridge.commodity import Classifier
from scripts.validate_monitoring import category, food_builder, indices, get_column


class MonitoringComparisonTest(unittest.TestCase):
    def test_categorization_respects_whole_parts_and_qualifier_evidence(self):
        rows = [{"residue_id": 1,
                 "default": {"method": "exact", "param_codes": ["WHOLE"],
                             "components": [{"role": "analyte", "param_codes": ["PART"], "method": "family"}],
                             "qualifier_components": [{"param_codes": ["ESTER"]}]},
                 "exceptions": []}]
        idx = indices(rows)
        self.assertEqual(category("WHOLE", idx), ("whole", 1))
        self.assertEqual(category("PART", idx), ("component", 1))
        self.assertEqual(category("ESTER", idx), ("qualifier", 1))
        self.assertEqual(category("ACTIVE", idx, {"ACTIVE": {"Example"}}),
                         ("no_residue_definition", None))
        self.assertEqual(category("MISSING", idx), ("unmapped", None))

    def test_ambiguous_candidate_is_not_judged(self):
        rows = [{"residue_id": n, "default": {"method": "exact", "param_codes": ["SAME"]},
                 "exceptions": []} for n in (1, 2)]
        self.assertEqual(category("SAME", indices(rows)), ("ambiguous", None))

    def test_food_builder_rejects_unmapped_relevant_facet(self):
        cls = Classifier.load("data/foodex2_ppp.json")
        header = ["sampMatCode.base.building", "sampMatCode.source",
                  "sampMatCode.partcon", "sampMatCode.prod", "sampMatCode.racsource"]
        make = food_builder(header, cls)
        code, uncertain = make(["A01DJ", "BOGUS123", "N_A", "BOGUS123", "N_A"])
        self.assertTrue(uncertain)
        self.assertEqual(code, "A01DJ")

    def test_food_builder_ignores_irrelevant_facets(self):
        cls = Classifier.load("data/foodex2_ppp.json")
        header = ["sampMatCode.base.building", "sampMatCode.source",
                  "sampMatCode.partcon", "sampMatCode.prod", "sampMatCode.racsource"]
        make = food_builder(header, cls)
        code, uncertain = make(["A01DJ", "BOGUS123", "N_A", "N_A", "N_A"])
        self.assertFalse(uncertain)
        self.assertEqual(code, "A01DJ")

    def test_missing_required_parameter_column_fails_loud(self):
        with self.assertRaises(RuntimeError):
            get_column(["a", "b"], "paramCode", "paramCode.base")


if __name__ == "__main__":
    unittest.main()
