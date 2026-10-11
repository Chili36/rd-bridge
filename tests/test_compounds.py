import unittest

from rd_bridge import compounds
from rd_bridge.match import Matcher


def term(code, name, pest_class="AS", cas=None):
    return {"code": code, "name": name, "pestClass": pest_class, "cas": cas}


class SignatureTest(unittest.TestCase):
    def test_order_and_wrapping_do_not_matter(self):
        a = compounds.signature("sum of fluopyram and fluopyram-benzamide (M25) expressed as fluopyram")
        b = compounds.signature("Fluopyram (sum fluopyram-benzamide (M25) and fluopyram expressed as fluopyram)")
        self.assertTrue(compounds.compatible(a, b))

    def test_last_expressed_clause_is_the_anchor(self):
        _, anchor = compounds.signature(
            "Cycloxydim including products which can be determined as X or derivatives thereof, "
            "calculated in total as cycloxydim")
        self.assertEqual(anchor, "cycloxydim")

    def test_different_parent_is_incompatible(self):
        a = compounds.signature("Ipconazole (sum of constituent isomers)")
        b = compounds.signature("Penconazole (sum of constituent isomers)")
        self.assertFalse(compounds.compatible(a, b))
        self.assertFalse(compounds.same_parent("Ipconazole (sum of constituent isomers)",
                                               "Penconazole (sum of constituent isomers)"))

    def test_expressed_as_parent_anchors_on_the_head(self):
        a = compounds.signature("Ipconazole (sum of constituent isomers, expressed as parent)")
        b = compounds.signature("Penconazole (sum of constituent isomers, expressed as parent)")
        self.assertEqual(a[1], "ipconazol")
        self.assertFalse(compounds.compatible(a, b))

    def test_plural_parent_counts_as_same_for_near(self):
        self.assertTrue(compounds.same_parent("Chlorate", "Chlorates"))
        self.assertFalse(compounds.same_parent("Phosphonic acid", "Phosphoric acid"))

    def test_stereo_descriptor_counts_as_same_for_near(self):
        self.assertTrue(compounds.same_parent("3-decen-2-one", "(3E) 3-decen-2-one"))
        self.assertTrue(compounds.same_parent("x", "(1R,2S)-x"))
        self.assertFalse(compounds.same_parent("3-decen-2-one", "(3E) 3-undecen-2-one"))

    def test_extra_component_is_incompatible(self):
        a = compounds.signature("Clodinafop and its S-isomers and their salts, expressed as clodinafop")
        b = compounds.signature("Clodinafop and its S-isomers, expressed as clodinafop")
        self.assertFalse(compounds.compatible(a, b))

    def test_nested_parentheses_in_head(self):
        self.assertIn(("name", "1-methyl-3-(trifluoromethyl)-1H-pyrazole-4-carboxamide"),
                      compounds.aliases("1-methyl-3-(trifluoromethyl)-1H-pyrazole-4-carboxamide (PAM)"))


class CanonTest(unittest.TestCase):
    def test_spelling_variants(self):
        for a, b in [("Sulphur", "Sulfur"), ("Phtalimide", "Phthalimide"), ("Flumioxazine", "Flumioxazin"),
                     ("Desethyl ethirimol", "De-ethyl-ethirimol"), ("RR, SS & SR", "RR, SS and SR"),
                     ("Beauveria bassiana strain GHA", "Beauveria bassiana GHA")]:
            self.assertEqual(compounds.canon(a), compounds.canon(b), (a, b))

    def test_distinct_names_stay_distinct(self):
        self.assertNotEqual(compounds.canon("Phosphonic acid"), compounds.canon("Phosphoric acid"))
        self.assertNotEqual(compounds.canon("Ipconazole"), compounds.canon("Penconazole"))


class AliasTest(unittest.TestCase):
    def test_kinds(self):
        self.assertIn(("code", "BAS 670H"), compounds.aliases("Topramezone (BAS 670H)"))
        self.assertIn(("aka", "Putrescine"), compounds.aliases("1,4-Diaminobutane  (aka Putrescine)"))
        self.assertIn(("name", "Magnesium hydroxide"), compounds.aliases("Magnesium hydroxide E528"))
        self.assertIn(("name", "Octanoic acid"), compounds.aliases("Fatty acids:  Octanoic acid"))

    def test_cas_is_not_a_code(self):
        self.assertNotIn(("code", "CAS 64742-54-7"), compounds.aliases("Paraffin oil (CAS 64742-54-7)"))
        self.assertEqual(compounds.cas_numbers("Paraffin oil (CAS 64742-54-7)"), ["64742-54-7"])


class MatcherTest(unittest.TestCase):
    def setUp(self):
        self.m = Matcher([
            term("P1", "Penconazole (sum of constituent isomers)", "RD"),
            term("F1", "Folpet (sum of folpet and phthalimide, expressed as folpet)", "RD"),
            term("C1", "sum of chlorpyrifos-methyl and desmethyl chlorpyrifos-methyl, "
                       "expressed as chlorpyrifos-methyl", "RD"),
            term("O1", "Paraffin Oil", cas="64742-55-8"),
            term("O2", "Residues of petroleum oil", cas="92062-35-6"),
            term("T1", "Topramezone", cas="210631-68-8"),
            term("D1", "Dimethylaminosulfotoluidide (DMST)", None),
            term("S1", "SDS-3701 (4-hydroxy-2,5,6- trichloroisophthalonitrile)", "RD"),
        ])

    def link(self, text, head=""):
        return self.m.link(text, head)

    def test_ipconazole_is_rejected_not_near(self):
        out = self.link("Ipconazole (sum of constituent isomers)")
        self.assertEqual(out["method"], "none")
        self.assertEqual(out["param_codes"], [])
        self.assertEqual(out["evidence"]["rejected"], ["Penconazole (sum of constituent isomers)"])

    def test_spelling(self):
        out = self.link("Folpet (sum of folpet and phtalimide, expressed as folpet)")
        self.assertEqual((out["method"], out["param_codes"]), ("spelling", ["F1"]))

    def test_compound_set_ignores_order(self):
        out = self.link("sum of desmethyl chlorpyrifos-methyl and chlorpyrifos-methyl, "
                        "expressed as chlorpyrifos-methyl")
        self.assertEqual((out["method"], out["param_codes"]), ("compound_set", ["C1"]))
        self.assertEqual(out["evidence"]["anchor"], "chlorpyrifosmethyl")

    def test_compound_set_without_expressed_as_anchors_on_first_component(self):
        self.assertEqual(self.link("sum of chlorpyrifos-methyl and desmethyl chlorpyrifos-methyl")
                         ["param_codes"], ["C1"])
        self.assertEqual(self.link("sum of desmethyl chlorpyrifos-methyl and chlorpyrifos-methyl")
                         ["method"], "none")

    def test_cas(self):
        out = self.link("Petroleum oils (CAS 92062-35-6)")
        self.assertEqual((out["method"], out["param_codes"]), ("cas", ["O2"]))

    def test_conflicting_cas_vetoes_name(self):
        self.assertEqual(self.link("Paraffin oil (CAS 64742-54-7)")["method"], "none")

    def test_aliases(self):
        self.assertEqual(self.link("Topramezone (BAS 670H)")["param_codes"], ["T1"])
        self.assertEqual(self.link("Dimethylaminosulfotoluidide")["param_codes"], ["D1"])
        self.assertEqual(self.link("2,5,6-trichloro-4-hydroxyphtalonitrile (SDS-3701)")["param_codes"], ["S1"])

    def test_two_aliases_naming_two_terms_are_ambiguous(self):
        m = Matcher([term("A", "Putrescine"), term("B", "1,4-Diaminobutane")])
        out = m.link("1,4-Diaminobutane (aka Putrescine)", "")
        self.assertEqual((out["method"], out["param_codes"]), ("ambiguous", ["A", "B"]))
        self.assertEqual(out["evidence"]["via"], "alias")

    def test_exact_carries_no_evidence(self):
        out = self.link("Topramezone")
        self.assertEqual(out, {"method": "exact", "param_codes": ["T1"]})


if __name__ == "__main__":
    unittest.main()
