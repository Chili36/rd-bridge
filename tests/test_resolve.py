import unittest

from pathlib import Path

from rd_bridge.commodity import Classifier
from rd_bridge.resolve import Resolver
from tests.rules_map import rule_rows

ROOT = Path(__file__).resolve().parent.parent


class ResolverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # rule-parser components: the committed map may hold model readings
        cls.r = Resolver(rule_rows(), Classifier.load(str(ROOT / "data" / "foodex2_ppp.json")))

    def check(self, code, substance, scope, param):
        out = self.r.resolve(code, substance)
        self.assertEqual((out["status"], out["scope"], out["param_codes"]), ("resolved", scope, [param]), out)
        self.assertEqual(out["applicability"]["status"], "unverified")
        return out

    def test_readme_examples(self):
        # acetamiprid: plant default, animal-product exception
        self.check("A01DJ", "Acetamiprid", "default", "RF-0014-001-PPP")
        out = self.check("A01QX", "acetamiprid", "exception", "RF-00003326-PAR")
        self.assertEqual(out["exception"]["commodity_codes"], ["1000000"])
        # thiabendazole: milk is finer than the animal-product exception
        self.check("A02LV", "Thiabendazole", "exception", "RF-00007630-PAR")
        self.check("A01QX", "Thiabendazole", "exception", "RF-00007629-PAR")
        self.check("A01DJ", "Thiabendazole", "default", "RF-0416-001-PPP")
        # 2-phenylphenol: animal products (repaired "code 100000") -> parent only
        out = self.check("A01QX", "2-phenylphenol", "exception", "RF-0823-001-PPP")
        self.assertEqual(out["exception"]["repairs"][0]["to"], "1000000")

    def test_near_link_is_not_resolved(self):
        out = self.r.resolve("A01DJ", 109)  # Flucythrinate: near match only
        self.assertEqual((out["status"], out["method"]), ("untrusted_link", "near"))

    def test_completeness_of_an_analysis(self):
        def status(*codes):
            return self.r.resolve("A01QX", "Acetamiprid", list(codes))["completeness"]
        self.assertEqual(status("RF-0014-001-PPP")["status"], "partial")
        self.assertEqual(status("RF-0014-001-PPP", "RF-00002836-PAR")["status"], "complete")
        self.assertEqual(status("RF-00003326-PAR")["via"], "summed code")
        self.assertEqual(status()["status"], "not_covered")

    def test_named_conjugate_is_required(self):
        out = self.r.resolve("A02LV", "Thiabendazole", ["RF-0416-001-PPP", "RF-0926-001-PPP"])
        self.assertEqual(out["completeness"]["status"], "partial")
        self.assertEqual(out["completeness"]["missing"][0]["param_codes"], ["RF-00007631-PAR"])

    def test_residue_id_lookup(self):
        self.assertEqual(self.r.resolve("A01DJ", 10)["residue_id"], 10)

    def test_param_code_lookup(self):
        # a caller with only the PARAM code it mapped: the parent finds the milk sum
        self.check("A02LV", "RF-0416-001-PPP", "exception", "RF-00007630-PAR")
        # an exception's code finds its residue too, so apples get the default back
        self.check("A01DJ", "RF-00007630-PAR", "default", "RF-0416-001-PPP")

    def test_near_link_code_does_not_identify_a_residue(self):
        # a near match is a suggestion, not a link: its code must not pick a residue
        near = {c for r in self.r.residues for e in [r["default"], *r["exceptions"]]
                if e.get("method") == "near" for c in e.get("param_codes", [])}
        trusted = {c for r in self.r.residues for e in [r["default"], *r["exceptions"]]
                   if e.get("method") != "near" for c in e.get("param_codes", [])}
        self.assertTrue(near - trusted)
        for code in near - trusted:
            self.assertEqual(self.r.resolve("A01DJ", code)["status"], "unknown_substance", code)

    def test_component_code_is_not_a_substance(self):
        # 5-hydroxythiabendazole is a part of a sum, not a residue of its own
        self.assertEqual(self.r.resolve("A02LV", "RF-0926-001-PPP")["status"], "unknown_substance")

    def test_unplaceable_food_with_exceptions_is_not_guessed(self):
        out = self.r.resolve("ZZZZZ", "Acetamiprid")
        self.assertEqual(out["status"], "commodity_unresolved")
        self.assertEqual(len(out["candidates"]), 2)

    def test_unplaceable_food_without_exceptions_uses_the_only_definition(self):
        out = self.r.resolve("ZZZZZ", "Glyphosate")
        self.assertEqual((out["status"], out["scope"]), ("resolved", "only definition"))

    def test_unknown_substance(self):
        self.assertEqual(self.r.resolve("A01DJ", "not a pesticide")["status"], "unknown_substance")


class ActiveSubstanceFallbackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = Resolver.load(str(ROOT / "data" / "residue_param_map.json"),
                              str(ROOT / "data" / "foodex2_ppp.json"),
                              str(ROOT / "data" / "active_substances.json"),
                              str(ROOT / "data" / "param_pest_terms.json"))

    def test_four_EU_known_substances_without_residue_definition(self):
        expected = {
            "Azamethiphos": "RF-0484-001-PPP",
            "Etrimfos": "RF-0668-001-PPP",
            "Dichlofluanid": "RF-0453-001-PPP",
            "Bromophos": "RF-0517-001-PPP",
        }
        for name, code in expected.items():
            with self.subTest(name=name):
                out = self.r.resolve("A01DJ", name)
                self.assertEqual(out["status"], "no_residue_definition", out)
                self.assertEqual(out["approval_status"], "Not approved")
                self.assertEqual(out["method"], "exact")
                self.assertEqual(out["param_codes"], [code])
                self.assertIn("Art 18(1)(b)", out["mrl"])

    def test_no_completeness_without_an_EU_definition(self):
        result = self.r.resolve("A01DJ", "Azamethiphos", ["RF-0484-001-PPP"])
        self.assertEqual(result["completeness"]["status"], "not_applicable")

    def test_unknown_is_unknown_in_both_sources(self):
        self.assertEqual(self.r.resolve("A01DJ", "not a pesticide")["status"], "unknown_substance")

    def test_current_residue_takes_precedence_over_active_substance(self):
        self.assertEqual(self.r.resolve("A01DJ", "Acetamiprid")["status"], "resolved")

    def test_known_but_linked_to_different_definition_is_not_default_mrl(self):
        active = [{"name": "Example", "substance_id": 77, "cas": None,
                   "approval_status": "Approved", "pesticide_residue_linked": "Another residue"}]
        r = Resolver([], self.r.classifier, active, [])
        result = r.resolve("A01DJ", "Example")
        self.assertEqual(result["status"], "residue_definition_unresolved")
        self.assertNotIn("mrl", result)

    def test_cas_fallback_is_not_fuzzy(self):
        active = [{"name": "Example", "substance_id": 78, "cas": "35575-96-3",
                   "approval_status": "Not approved",
                   "pesticide_residue_linked": "Default MRL of 0.01 mg/kg according to Art 18(1)(b) Reg 396 / 2005"}]
        param = [{"code": "RF-0484-001-PPP", "name": "Azamethiphos", "pestClass": "AS",
                  "cas": "35575-96-3"}]
        r = Resolver([], self.r.classifier, active, param)
        result = r.resolve("A01DJ", "Example")
        self.assertEqual((result["status"], result["method"], result["param_codes"]),
                         ("no_residue_definition", "cas", ["RF-0484-001-PPP"]))



if __name__ == "__main__":
    unittest.main()
