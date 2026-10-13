"""Regression tests for the sole refused EU biological isolate."""
import json
from pathlib import Path
import unittest

from rd_bridge import components, guided_model_parts, guided_migration, llm, match, recover_refused

ROOT = Path(__file__).resolve().parents[1]


class RefusalRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.name = recover_refused.NAME
        self.index = components.ComponentIndex.load(str(ROOT / "data" / "param_components.json"))
        with (ROOT / "data" / "residue_param_map.json").open(encoding="utf-8") as fh:
            self.rows = json.load(fh)
        self.ctx = guided_model_parts.contexts(self.rows, self.index)[self.name]
        self.row = next(r for r in self.rows if r["residue_id"] == 2436)

    def test_only_exact_source_label_can_fallback(self):
        answer = recover_refused.exact_fallback(self.name, self.ctx)
        self.assertEqual(answer["parts"], [{"name": self.name, "role": "analyte"}])
        self.assertIsNone(answer["expressed_as"])
        self.assertEqual(answer["model_used"], "none")
        self.assertTrue(answer["requires_followup"])
        self.assertTrue(guided_model_parts.valid(answer, self.name, self.ctx))
        with self.assertRaises(ValueError):
            recover_refused.exact_fallback("Guazatine", self.ctx)

    def test_fallback_in_map_is_not_falsely_called_model_generated(self):
        answer = recover_refused.exact_fallback(self.name, self.ctx)
        raw = [{
            "pesticide_residue_id": 2436,
            "pesticide_residue_name": self.name,
            "pesticide_residue_version_nbr": 1,
            "original_pesticide_residue_id": None,
        }]
        rows = match.build(raw, [], self.index, {self.name: answer})
        entry = rows[0]["default"]
        self.assertEqual(entry["parts_from"], "source_literal_fallback")
        self.assertEqual(entry["components"][0]["name"], self.name)
        self.assertEqual(entry["components"][0].get("param_codes"), [])
        self.assertTrue(entry["model_guidance"]["requires_followup"])

    def test_refusal_is_not_a_fake_chemical_identification(self):
        response = recover_refused.exact_fallback(self.name, self.ctx)
        self.assertIn("source-literal", guided_migration.markdown(
            {"definitions": 1, "parts_from": {"source_literal_fallback": 1},
             "component_changes": []}, {"cases": [], "comparison": {"counts": {}}},
            guided_count=1, model="claude-haiku-5-5", guidance_version="x",
            alternate_readings=[{"definition": self.name, "interpretation_source":
                                 response["interpretation_source"],
                                 "model_used": response["model_used"]}]))


if __name__ == "__main__":
    unittest.main()
