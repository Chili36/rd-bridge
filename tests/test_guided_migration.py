"""Regression tests for replacing all historical Haiku readings with guidance."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from rd_bridge import guided_migration, guided_model_parts, model_parts, components

ROOT = Path(__file__).resolve().parents[1]


class FullGuidedMigrationTests(unittest.TestCase):
    def test_all_scope_does_not_depend_on_unavailable_manual_gold_standard(self):
        contexts = {f"RD-{i:03}": {"family": ["a"], "is_exception": False}
                    for i in range(20)}
        baseline = {k: {"context": model_parts.context_hash(["a"])}
                    for k in contexts}
        todo = guided_model_parts.choose_todo(contexts, baseline, {}, scope="all")
        self.assertEqual(len(todo), 20)
        # The old 'new' mode keeps existing cached readings untouched.
        self.assertEqual(guided_model_parts.choose_todo(
            contexts, baseline, {}, scope="new"), [])

    def test_16_shards_cover_every_definition_exactly_once(self):
        names = {f"Def {i:03}": {} for i in range(765)}
        all_keys = sorted(names)
        assignments = [guided_model_parts.in_shard(
            all_keys, names, index, 16) for index in range(16)]
        self.assertEqual([len(keys) for keys in assignments].count(48), 13)
        self.assertEqual([len(keys) for keys in assignments].count(47), 3)
        together = [t for shard in assignments for t in shard]
        self.assertEqual(sorted(together), all_keys)
        self.assertEqual(len(set(together)), len(all_keys))
        subset = set(all_keys[:100])
        self.assertTrue(all(set(guided_model_parts.in_shard(
            sorted(subset), names, i, 16)) <= set(assignments[i]) for i in range(16)))
        with self.assertRaises(ValueError):
            guided_model_parts.in_shard(all_keys, names, 16, 16)

    def test_merge_checks_every_version_and_all_expected_definitions(self):
        with (ROOT / "data" / "residue_param_map.json").open(encoding="utf-8") as fh:
            rows = json.load(fh)
        rows = [r for r in rows if r["residue_id"] in (253, 301)]
        index = components.ComponentIndex.load(str(ROOT / "data/param_components.json"))
        ctxs = guided_model_parts.contexts(rows, index)
        data = guided_model_parts.catalogue()
        answers = {}
        for text, ctx in ctxs.items():
            parts = [{"name": text.split(" (")[0], "role": "analyte",
                      "included_in": None, "param_name": None, "notes": []}]
            def fake(*args, parts=parts):
                return {"expressed_as": None, "parts": parts}
            answers[text] = guided_model_parts.ask(
                text, ctx["family"], is_exception=ctx["is_exception"],
                data=data, caller=fake)

        keys = sorted(answers)
        with tempfile.TemporaryDirectory() as td:
            paths = [Path(td) / f"part-{i}.json" for i in range(2)]
            for i in range(2):
                subset = {key: answers[key] for n, key in enumerate(keys) if n % 2 == i}
                guided_model_parts.save(subset, paths[i], data=data)
            output = guided_migration.merge_shards(paths, rows, index, data=data)
            self.assertEqual(set(output), set(ctxs))
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                guided_migration.merge_shards([paths[0], paths[0], paths[1]],
                                               rows, index, data=data)
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                guided_migration.merge_shards([paths[0]], rows, index, data=data)
            corrupt = json.loads(paths[1].read_text(encoding="utf-8"))
            corrupt["guidance_version"] = "old"
            paths[1].write_text(json.dumps(corrupt), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "guidance version"):
                guided_migration.merge_shards(paths, rows, index, data=data)

    def test_whole_rd_codes_cannot_be_silently_changed_by_migration(self):
        old = [{"residue_id": 1, "default": {
            "definition": "X (sum of X and M)", "method": "exact",
            "param_codes": ["SUM"], "components": [
                {"role": "analyte", "name": "X", "param_codes": ["A"]}]},
            "exceptions": []}]
        new = deepcopy(old)
        new[0]["default"]["components"] = [
            {"role": "analyte", "name": "M", "param_codes": ["B"]}]
        comparison = guided_migration.compare_maps(old, new)
        self.assertEqual(len(comparison["component_changes"]), 1)
        self.assertEqual(comparison["component_changes"][0]["added_param_codes"], ["B"])
        self.assertEqual(comparison["component_changes"][0]["removed_param_codes"], ["A"])
        new[0]["default"]["param_codes"] = ["CHANGED"]
        with self.assertRaisesRegex(ValueError, "whole-RD PARAM"):
            guided_migration.compare_maps(old, new)


if __name__ == "__main__":
    unittest.main()
