"""Offline regression tests for source-driven LLM prompts and cache isolation."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from rd_bridge import components, guidance_eval, guided_model_parts, model_parts

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "rd_guidance_benchmark.json"


class GuidanceSelectionTest(unittest.TestCase):
    def test_every_rule_references_real_sources(self):
        data = guided_model_parts.catalogue()
        self.assertEqual(len(data["rules"]), 11)
        self.assertEqual(len({r["id"] for r in data["rules"]}), 11)
        for rule in data["rules"]:
            for source_id in rule["sources"]:
                source = data["sources"][source_id]
                self.assertTrue(source["url"].startswith("https://"))
                self.assertTrue(source["locator"])
            self.assertTrue(rule["locator"])
            self.assertTrue(rule["principle"])

    def test_relevant_evidence_is_actually_retrieved(self):
        text = "Chloridazon (chloridazon-desphenyl, expressed as chloridazon)"
        guidance, ids = guided_model_parts.render(text, is_exception=True)
        self.assertIn("OECD-EXPRESSION-BASIS", ids)
        self.assertIn("OECD-COMMODITY-VARIANTS", ids)
        self.assertIn("EU-TEXT-CONTROLS", ids)
        self.assertIn("EFSA-WHOLE-VS-PARTS", ids)
        self.assertIn("https://doi.org/10.1787/66ca5caa-en", guidance)
        self.assertIn("https://doi.org/10.2903/sp.efsa.2026.EN-9911", guidance)
        self.assertIn("measuring X", guidance)
        _, isomer_ids = guided_model_parts.render("Mevinphos (sum of E- and Z-isomers)")
        self.assertIn("OECD-ISOMER-COVERAGE", isomer_ids)
        self.assertNotIn("EU-CONDITIONAL-CLAUSE", isomer_ids)
        _, conditional = guided_model_parts.render("Where only meptyldinocap is found")
        self.assertIn("EU-CONDITIONAL-CLAUSE", conditional)

    def test_live_prompt_receives_source_evidence_and_separate_reference_names(self):
        calls = []

        def fake(system, prompt, schema):
            calls.append((system, prompt, schema))
            return {"expressed_as": "chloridazon", "parts": [{
                "name": "chloridazon-desphenyl", "role": "analyte",
                "included_in": None, "param_name": None, "notes": []}]}

        result = guided_model_parts.ask(
            "Chloridazon (chloridazon-desphenyl, expressed as chloridazon)",
            ["Chloridazon", "Chloridazon-desphenyl"],
            is_exception=True, caller=fake)
        self.assertEqual(len(calls), 1)
        self.assertIn("SOURCE-GROUNDED INTERPRETATION", calls[0][0])
        self.assertIn("OECD-EXPRESSION-BASIS", calls[0][1])
        self.assertIn("Authoritative EU residue definition", calls[0][1])
        self.assertIn("Candidate EFSA PARAM family names", calls[0][1])
        self.assertEqual(result["parts"][0]["name"], "chloridazon-desphenyl")
        self.assertEqual(result["expressed_as"], "chloridazon")
        self.assertEqual(result["prompt_variant"], "guided-rd-v1")
        self.assertEqual(result["guidance_version"], guided_model_parts.guidance_hash())
        self.assertTrue(guided_model_parts.valid(result,
            "Chloridazon (chloridazon-desphenyl, expressed as chloridazon)",
            {"is_exception": True, "family": ["Chloridazon", "Chloridazon-desphenyl"]}))

    def test_guidance_change_invalidates_only_guided_cache(self):
        data = guided_model_parts.catalogue()
        version = guided_model_parts.prompt_hash(data)
        changed = copy.deepcopy(data)
        changed["rules"][0]["principle"] += " A controlled revision."
        self.assertNotEqual(version, guided_model_parts.prompt_hash(changed))
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "cache.json"
            result = {"example": {"context": "c"}}
            guided_model_parts.save(result, p, data=data)
            self.assertEqual(guided_model_parts.load(p, data=data), result)
            self.assertEqual(guided_model_parts.load(p, data=changed), {})
        self.assertIsInstance(model_parts.prompt_hash(), str)

    def test_new_only_preserves_current_baseline_readings(self):
        data = guided_model_parts.catalogue()
        family = ["A", "B"]
        contexts = {
            "Existing": {"family": family, "is_exception": False},
            "New": {"family": family, "is_exception": False},
        }
        legacy = {"Existing": {"context": model_parts.context_hash(family)}}
        todo = guided_model_parts.choose_todo(contexts, legacy, {}, data=data)
        self.assertEqual(todo, ["New"])
        legacy["Existing"]["context"] = "stale"
        self.assertEqual(guided_model_parts.choose_todo(
            contexts, legacy, {}, data=data), ["Existing", "New"])

    def test_no_new_rd_does_not_write_empty_guided_cache(self):
        with mock.patch("rd_bridge.guided_model_parts.choose_todo", return_value=[]), \
                mock.patch("rd_bridge.guided_model_parts.load", return_value={}), \
                mock.patch("rd_bridge.guided_model_parts.save") as save, \
                mock.patch("sys.argv", ["guided_model_parts"]):
            guided_model_parts.main()
        save.assert_not_called()

    def test_independent_guide_is_not_made_up_when_api_fails(self):
        text = "Chloridazon (chloridazon-desphenyl, expressed as chloridazon)"
        def failed(system, prompt, schema):
            raise ValueError("Model failed")
        ctx = {text: {"family": ["Chloridazon"], "is_exception": True}}
        answers, errors = guided_model_parts.refresh(
            [text], ctx, {}, caller=failed, workers=1)
        self.assertEqual(answers, {})
        self.assertIn(text, errors)


class EvaluationTest(unittest.TestCase):
    def test_gold_is_frozen_separately_from_exploration(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(len(fixture["cases"]), 12)
        self.assertEqual(len(fixture["exploratory"]), 3)
        self.assertEqual(len({x["id"] for x in fixture["cases"]}), 12)
        self.assertEqual(len({x["id"] for x in fixture["exploratory"]}), 3)
        for case in fixture["cases"]:
            self.assertTrue(case["required"])
            self.assertTrue(case["source"])
        for case in fixture["exploratory"]:
            self.assertNotIn("required", case)
        baseline_ids = {x["residue_id"] for x in fixture["cases"]}
        self.assertIn(253, baseline_ids)

    def test_name_checks_are_per_analyte_not_expression_basis(self):
        e = {"parts": [{"name": "chloridazon-desphenyl", "role": "analyte"}],
             "expressed_as": "chloridazon"}
        test = {"required": ["chloridazon desphenyl"], "forbidden": ["^chloridazon$"]}
        self.assertTrue(guidance_eval.score(e, test)["passed"])
        wrong = {"parts": [{"name": "chloridazon", "role": "analyte"}, *e["parts"]]}
        self.assertFalse(guidance_eval.score(wrong, test)["passed"])
        self.assertFalse(guidance_eval.score(None, test)["passed"])

    def test_all_gold_definitions_exist_in_current_eu_snapshot(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        rows = json.loads((ROOT / "data" / "residue_param_map.json").read_text(encoding="utf-8"))
        for case in fixture["cases"] + fixture["exploratory"]:
            with self.subTest(case=case["id"]):
                r, e = guidance_eval.picked_case(case, rows)
                self.assertEqual(r["residue_id"], case["residue_id"])
                self.assertTrue(e["definition"])


if __name__ == "__main__":
    unittest.main()
