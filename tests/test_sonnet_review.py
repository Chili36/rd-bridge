"""Offline verification of high-risk case selection and Sonnet review."""
import json
from pathlib import Path
import unittest

from rd_bridge import components, sonnet_review

ROOT = Path(__file__).resolve().parents[1]


class PrioritizationTest(unittest.TestCase):
    def test_param_code_conflicts_outrank_wording_only(self):
        a = [{"role": "analyte", "name": "A", "param_codes": ["A"]}]
        b = [{"role": "analyte", "name": "B", "param_codes": ["B"]}]
        same_code_different_text = [
            {"role": "analyte", "name": "Other label", "param_codes": ["A"]}]
        score, flags = sonnet_review.priority(a, b)
        other_score, _ = sonnet_review.priority(a, same_code_different_text)
        self.assertGreater(score, other_score)
        self.assertIn("different PARAM component codes", flags)

    def test_selected_cases_are_unique_bounded_and_include_acceptance_examples(self):
        with (ROOT / "data/residue_param_map.json").open(encoding="utf-8") as fh:
            rows = json.load(fh)
        index = components.ComponentIndex.load(str(ROOT / "data" / "param_components.json"))
        cases, conflicts = sonnet_review.review_candidates(rows, index, limit=12)
        self.assertEqual(len(conflicts), 39)  # one legally verified correction (Chloridazon)
        self.assertEqual(len(cases), 12)
        self.assertEqual({321, 2655} & {x["residue_id"] for x in cases}, {321, 2655})
        self.assertEqual(len({(c["residue_id"], c["definition"]) for c in cases}), 12)
        self.assertIn("acceptance", next(x["source"] for x in cases if x["residue_id"] == 2655))

    def test_limit_is_technical_cost_cap(self):
        with self.assertRaises(ValueError):
            sonnet_review.review_candidates([], object(), limit=21)

    def test_sonnet_prompt_is_blind_to_previous_model_outputs(self):
        with (ROOT / "data/residue_param_map.json").open(encoding="utf-8") as fh:
            row = next(r for r in json.load(fh) if r["residue_id"] == 321)
        index = components.ComponentIndex.load(str(ROOT / "data" / "param_components.json"))
        seen = []

        def fake_model(system, prompt, schema):
            seen.append(prompt)
            return {"expressed_as": None, "parts": [
                {"name": "guazatine acetate", "role": "analyte"}]}

        case = {"residue_id": 321, "definition": row["default"]["definition"],
                "flags": ["former acceptance case"], "score": 0, "source": "acceptance"}
        result = sonnet_review.inspect_case(case, row, index, caller=fake_model)
        self.assertEqual(len(seen), 1)
        self.assertIn("Residue definition:", seen[0])
        self.assertNotIn("Haiku", seen[0])
        self.assertNotIn("rules:", seen[0])
        self.assertTrue(result["human_review_required"])
        self.assertIn(result["alignment"], ("haiku", "rules", "both", "neither"))


if __name__ == "__main__":
    unittest.main()
