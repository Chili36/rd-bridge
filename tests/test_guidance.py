"""Source-backed interpretation rules and auditable discrepancy triage."""
import json
from pathlib import Path
import unittest

from rd_bridge import compare_parts, components, guidance, guidance_audit, match, model_parts

ROOT = Path(__file__).resolve().parents[1]
CHLORIDAZON_EXCEPTION = "Chloridazon (chloridazon-desphenyl, expressed as chloridazon)"


class SourceRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ROOT / "data" / "residues_en.json").open(encoding="utf-8") as fh:
            cls.raw = json.load(fh)
        with (ROOT / "data" / "param_pest_terms.json").open(encoding="utf-8") as fh:
            cls.param = json.load(fh)
        cls.index = components.ComponentIndex.load(str(ROOT / "data" / "param_components.json"))

    def test_expression_candidate_does_not_mean_an_extra_analyte(self):
        candidate = guidance.expression_candidate(CHLORIDAZON_EXCEPTION)
        self.assertEqual(candidate["component"], "chloridazon-desphenyl")
        self.assertEqual(candidate["expression_basis"].lower(), "chloridazon")
        self.assertIsNone(guidance.expression_candidate(
            "Chloridazon (sum of chloridazon and chloridazon-desphenyl, "
            "expressed as chloridazon)"))
        self.assertIsNone(guidance.expression_candidate(
            "Example (Example, expressed as Example)"))

    def test_legislation_overrides_cached_model_on_verified_exception_only(self):
        raw = [r for r in self.raw if r["pesticide_residue_id"] == 253]
        rows = match.build(raw, self.param, self.index, model_parts.load())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        default = row["default"]
        exception = row["exceptions"][0]
        self.assertEqual(default["parts_from"], "model")
        self.assertEqual({p["name"] for p in default["components"] if p["role"] == "analyte"},
                         {"chloridazon", "chloridazon-desphenyl"})
        self.assertEqual(exception["parts_from"], "legal_guidance")
        self.assertEqual(
            [(p["name"], p["param_codes"]) for p in exception["components"]],
            [("chloridazon-desphenyl", ["RF-00006186-PAR"])])
        self.assertEqual(exception["interpretation_evidence"]["rule_id"],
                         "EU-2023-710-CHLORIDAZON-R")
        self.assertEqual(exception["interpretation_evidence"]["expression_basis"],
                         "chloridazon")
        self.assertIn("CELEX:32023R0710", exception["interpretation_evidence"]["source"][0]["url"])

    def test_never_apply_specific_legislation_by_analogy(self):
        entry = {"definition": CHLORIDAZON_EXCEPTION,
                 "method": "exact",
                 "param_codes": ["RF-00005712-PAR"],
                 "commodity_codes": ["1000000"], "except_codes": ["1040000"]}
        rules = [dict(name="chloridazon-desphenyl", role="analyte",
                      param_codes=["RF-00006186-PAR"])]
        self.assertIsNotNone(guidance.apply_verified(entry, rules, "Chloridazon"))
        for changed in [
            {**entry, "method": "near"},
            {**entry, "param_codes": ["RF-0080-001-PPP"]},
            {**entry, "commodity_codes": ["0100000"]},
            {**entry, "except_codes": []},
            {**entry, "definition": "Example (example-metabolite, expressed as Example)"},
        ]:
            with self.subTest(changed=changed):
                self.assertIsNone(guidance.apply_verified(changed, rules, "Chloridazon"))
        self.assertIsNone(guidance.apply_verified(entry, [dict(
            name="chloridazon", role="analyte", param_codes=["RF-0080-001-PPP"]
        )], "Chloridazon"))

    def test_current_guidance_has_source_and_obsolete_efsa_is_not_normative(self):
        self.assertIn("2026", guidance.SOURCES["efsa_chemmon_2026"]["title"])
        self.assertIn("obsolete", guidance.SOURCES["efsa_reporting_2019_historical"]["role"])
        self.assertEqual(guidance.VERIFIED_INTERPRETATIONS[
            CHLORIDAZON_EXCEPTION]["source_ids"][0], "eu_chloridazon_2023_710")


class GuidanceAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ROOT / "reports" / "guidance_baseline_2026-10-13.json").open(
                encoding="utf-8") as fh:
            cls.baseline = json.load(fh)
        with (ROOT / "data" / "residue_param_map.json").open(encoding="utf-8") as fh:
            cls.map = json.load(fh)
        cls.report = guidance_audit.build(cls.baseline, cls.map)

    def test_all_original_40_cases_are_retained_and_explainable(self):
        self.assertEqual(self.report["total_original_differences"], 40)
        self.assertEqual(self.report["by_status"], {
            "requires_source_review": 33,
            "source_verified": 1,
            "wording_only": 6,
        })
        self.assertEqual(sum(self.report["by_category"].values()), 40)
        verified = [x for x in self.report["findings"]
                    if x["review_status"] == "source_verified"]
        self.assertEqual([x["residue_id"] for x in verified], [253])

    def test_distinct_strains_do_not_become_false_alias_resolutions(self):
        for rid in (2401, 2402):
            item = next(x for x in self.report["findings"] if x["residue_id"] == rid)
            self.assertEqual(item["category"], "component_scope_conflict")
            self.assertEqual(item["review_status"], "requires_source_review")
        putrescine = next(x for x in self.report["findings"]
                          if x["residue_id"] == 399)
        self.assertEqual(putrescine["review_status"], "wording_only")

    def test_saved_audit_is_reproducible_and_unchanged_sources_are_not_votes(self):
        with (ROOT / "reports" / "guidance_audit.json").open(encoding="utf-8") as fh:
            committed = json.load(fh)
        self.assertEqual(committed, self.report)
        self.assertNotIn("agreement", self.report["method"])
        self.assertIn("obsolete", self.report["source_hierarchy"][
            "historical_efsa_examples_not_current"]["role"])

    def test_live_difference_count_declines_but_frozen_baseline_is_40(self):
        with (ROOT / "data" / "parts_comparison.json").open(encoding="utf-8") as fh:
            current = json.load(fh)
        # The original, frozen 40-case baseline stays intact. The current
        # disagreement count is expected to change when ALL definitions are
        # genuinely reread with the new, guidance-backed model.
        self.assertEqual(current["comparison"]["counts"]["different"],
                         len(current["comparison"]["differences"]))
        self.assertEqual(current["comparison"]["counts"]["legal_guidance"], 1)
        self.assertEqual(len(current["cases"]), 34)
        self.assertTrue(all(c["passed"] for c in current["cases"]))
        self.assertEqual(len(self.baseline["differences"]), 40)


if __name__ == "__main__":
    unittest.main()
