"""The CI repair loop fixes concrete failures without waiting for external gold data."""
import json
from pathlib import Path
import unittest

from rd_bridge import (auto_repair, compare_parts, guided_model_parts,
                       model_parts, components, llm, match)

ROOT = Path(__file__).resolve().parents[1]


class FeedbackLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ROOT / "data" / "residue_param_map.json").open(encoding="utf-8") as fh:
            cls.baseline = json.load(fh)
        cls.raw, cls.terms, cls.index = auto_repair.load_inputs()
        cls.context = guided_model_parts.contexts(cls.baseline, cls.index)

    def bad_reading(self, definition, name):
        ctx = self.context[definition]
        answer = {"expressed_as": None,
                  "parts": [{"name": name, "role": "analyte",
                             "param_name": name, "notes": []}]}
        return auto_repair.guided_record(
            answer, definition, ctx, data=guided_model_parts.catalogue(),
            provenance="guided_model", model_used="claude-haiku-5-5")

    def test_existing_correct_map_needs_no_model_repair(self):
        calls = []
        def fail(*args):
            calls.append(args)
            raise AssertionError("Model should not be called for passing cases")
        rows, report = auto_repair.fix_regressions(
            self.baseline, {}, raw=self.raw, terms=self.terms, index=self.index,
            caller=fail, max_rounds=1)
        self.assertEqual(report["initial"], [])
        self.assertEqual(report["sonnet_calls"], 0)
        self.assertEqual(report["final_passed"], len(compare_parts.CASES))
        self.assertEqual(calls, [])

    def test_targeted_sonnet_repair_restores_guazatine_with_same_eu_wording(self):
        row = next(r for r in self.baseline if r["residue_id"] == 321)
        definition = row["default"]["definition"]
        cache = {definition: self.bad_reading(definition, "Guazatine")}
        def fixed(system, prompt, schema):
            self.assertIn("EU_definition", prompt)
            self.assertIn("RF-00004664-PAR", prompt)
            self.assertIn("RF-0233-001-PPP", prompt)
            self.assertIn("OECD", prompt)
            return {"expressed_as": None, "parts": [
                {"name": "guazatine acetate", "role": "analyte",
                 "included_in": None, "param_name": None, "notes": []}]}
        rows, report = auto_repair.fix_regressions(
            self.baseline, cache, raw=self.raw, terms=self.terms, index=self.index,
            caller=fixed, max_rounds=1, max_calls=2)
        self.assertEqual(report["initial"][0]["residue_id"], 321)
        self.assertEqual(report["model_repairs_accepted"], 1)
        self.assertEqual(report["legacy_readings_retained"], [])
        self.assertEqual(report["final_passed"], 34)
        self.assertEqual(cache[definition]["interpretation_source"],
                         "guided_validation_repair")
        new = next(r for r in rows if r["residue_id"] == 321)
        self.assertEqual(new["default"]["parts_from"], "guided_model")
        self.assertEqual(new["default"]["components"][0]["param_codes"],
                         ["RF-00004664-PAR"])

    def test_failed_repair_retains_only_that_exact_previous_interpretation(self):
        row = next(r for r in self.baseline if r["residue_id"] == 2655)
        definition = row["default"]["definition"]
        cache = {definition: self.bad_reading(definition, "Fluvalinate")}
        def refused(system, prompt, schema):
            raise llm.LLMError("HTTP 529, retry exceeded")
        rows, report = auto_repair.fix_regressions(
            self.baseline, cache, raw=self.raw, terms=self.terms, index=self.index,
            caller=refused, max_rounds=1, max_calls=1)
        self.assertEqual(report["sonnet_calls"], 1)
        self.assertEqual(report["model_repairs_accepted"], 0)
        self.assertEqual(len(report["legacy_readings_retained"]), 1)
        self.assertEqual(report["final_passed"], 34)
        self.assertEqual(cache[definition]["interpretation_source"],
                         "legacy_retained_after_regression")
        new = next(r for r in rows if r["residue_id"] == 2655)
        self.assertEqual(new["default"]["parts_from"], "legacy_regression_fallback")
        self.assertTrue(new["default"]["model_guidance"]["requires_followup"])
        self.assertEqual(new["default"]["param_codes"], row["default"]["param_codes"])

    def test_does_not_rewrite_known_acceptance_expectations(self):
        current = list(compare_parts.CASES)
        self.assertEqual(len(current), 34)
        self.assertIn((321, None, ["RF-0233-001-PPP"], "not_covered",
                       "guazatine parent AS code is not the guazatine acetate RD"),
                      current)
        self.assertEqual(auto_repair.scenarios_for(2655)[1][2], "not_covered")


if __name__ == "__main__":
    unittest.main()
