import csv
import json
import unittest
from pathlib import Path

from rd_bridge.commodity import Classifier
from rd_bridge.foodex2_mapping import _parents

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "data" / "foodex2_ppp.json").read_text(encoding="utf-8"))


def with_rules(rules, flat=False):
    data = {**DATA, "rules": rules}
    if flat:
        data["hierarchies"] = {h: {} for h in DATA["hierarchies"]}
    return Classifier(data)


class TechnicalDocumentTest(unittest.TestCase):
    """Tables 2 and 3 of EFSA's technical document on the mapping algorithm (Zenodo 3989602),
    run on the real FoodEx2 hierarchies and implicit facets."""

    TABLE_2 = [(1, "FEED", "F00.ROOT", "", "P1200000A"), (2, "EXPO", "F00.A03QA", "", "PX100004A"),
               (3, "EXPO", "F00.A03QB", "", "PX100004A"), (4, "EXPO", "F00.A03QC", "", "PX100004A"),
               (5, "EXPO", "F00.A03QD", "", "PX100004A"), (6, None, "F27.ROOT$F27.ROOT", "", "XXXXXXA"),
               (7, None, "F21.A07RY", "", "P1070000A"), (8, None, "F27.A01DH", "", "P0130010A"),
               (9, None, "F27.A01QX", "F20.A0F4V", "P1012000A"), (10, None, "F27.A01QX", "", "P1012010B"),
               (11, None, "other", "", "XXXXXXA")]
    TABLE_3 = [("A0BHH", "P1200000A"), ("A0BHH#F27.A01DH$F27.A01QX", "P1200000A"),
               ("A03QD#F21.A07RY", "PX100004A"), ("A03QC#F27.A01DH$F27.A01QX", "PX100004A"),
               ("A02EP#F21.A07RY", "P1070000A"), ("A02EP#F21.A07RY$F27.A01DH", "XXXXXXA"),
               ("A02EP#F21.A0CAG", "XXXXXXA"), ("A01QX", "P1012000A"), ("A01QX#F20.A0F4V", "P1012010B"),
               # the document's own descendant example: A01DJ sits under A01DH (apples)
               ("A01DJ", "P0130010A")]

    def test_examples(self):
        c = with_rules([dict(order=o, base_hierarchy=h, include=i, exclude=e, food_class=f)
                        for o, h, i, e, f in self.TABLE_2])
        for code, expected in self.TABLE_3:
            with self.subTest(code=code):
                self.assertEqual(c.classify(code)["food_class"], expected)


class EfsaTestOutputTest(unittest.TestCase):
    """EFSA's packaged test_dataset_output (2020-07-30, 2020 rule table) matches its rules on the
    reported codes only, without hierarchy expansion. Replayed the same way, the port agrees on
    all but 26 codes, 25 of which carry an explicit F27 next to the base term's implicit one."""

    def test_flat_replay(self):
        rules = json.loads((ROOT / "tests" / "fixtures" / "mappingppp_v1_rules.json").read_text())
        c = with_rules(rules, flat=True)
        with open(ROOT / "tests" / "fixtures" / "efsa_ppp_test_output.csv", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 2787)
        misses = [(r, c.classify(r["sampmatcode"])) for r in rows]
        misses = [(r, o) for r, o in misses if o["food_class"] != r["FoodClassPPP"]]
        self.assertLessEqual(len(misses), 26)
        double = [o for _, o in misses if sum(f.startswith("F27.") for f in o["facets"]) == 2]
        self.assertGreaterEqual(len(double), len(misses) - 1)


class CurrentRulesTest(unittest.TestCase):
    def setUp(self):
        self.c = Classifier(DATA)

    def test_annex_codes(self):
        for code, food_class, annex in [("A01DJ", "P0130010A", "0130010"), ("A02LV", "P1020010A", "1020010"),
                                        ("A01QX#F20.A0F4V", "P1012010B", "1012010")]:
            with self.subTest(code=code):
                out = self.c.classify(code)
                self.assertEqual((out["food_class"], out["annex_code"]), (food_class, annex))
                self.assertIsNotNone(out["rule"])

    def test_special_and_unknown_have_no_annex_code(self):
        self.assertIsNone(self.c.classify("A03QD")["annex_code"])  # infant food class PX...
        out = self.c.classify("ZZZZZ")
        self.assertEqual((out["food_class"], out["annex_code"]), ("XXXXXXA", None))

    def test_explicit_child_replaces_implicit_parent(self):
        c = Classifier({**DATA, "implicit_facets": {"B": "F27.P"}, "hierarchies": {
            **DATA["hierarchies"], "racsource": {"P": None, "C": "P"}}})
        self.assertEqual(c.facets("B#F27.C")[1], ["F27.C"])

    def test_unknown_facet_category_fails_loudly(self):
        with self.assertRaises(ValueError):
            with_rules([dict(order=1, base_hierarchy=None, include="F99.X", exclude="", food_class="P0100000A")])


class ParentsTest(unittest.TestCase):
    def test_paths_rebuild(self):
        self.assertEqual(_parents({"A": "A", "B": "A - B", "C": "A - B - C"}), {"A": None, "B": "A", "C": "B"})

    def test_inconsistent_paths_fail(self):
        with self.assertRaises(ValueError):
            _parents({"A": "A", "B": "A - B", "C": "Z - B - C"})


if __name__ == "__main__":
    unittest.main()
