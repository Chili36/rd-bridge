import json
import os
import tempfile
import unittest
from unittest import mock

from rd_bridge import model_match
from rd_bridge.match import build

TERMS = [
    {"code": "C1", "name": "Chlorates", "pestClass": "AS"},
    {"code": "I1", "name": "indole-3-acetic acid", "pestClass": "AS"},
    {"code": "D1", "name": "Diquat (sum of diquat and its salts, expressed as diquat)", "pestClass": "RD"},
    {"code": "B1", "name": "Bacillus amyloliquefaciens AH2", "pestClass": "AS"},
    {"code": "X1", "name": "Cypermethrin", "pestClass": "AS"},
    {"code": "O1", "name": "Paraffin Oil", "pestClass": "AS", "cas": "64742-55-8"},
]


def residue(rid, name):
    return {"pesticide_residue_id": rid, "pesticide_residue_name": name, "pesticide_residue_version_nbr": 1}


class CandidatesTest(unittest.TestCase):
    def test_shortlist_puts_the_obvious_term_first_and_is_bounded(self):
        found = model_match.candidates("Chlorate", TERMS, limit=3)
        self.assertEqual(found[0]["code"], "C1")
        self.assertLessEqual(len(found), 3)

    def test_head_word_inside_a_longer_term_is_a_candidate(self):
        codes = [t["code"] for t in model_match.candidates("Diquat", TERMS, limit=2)]
        self.assertIn("D1", codes)


class ValidateTest(unittest.TestCase):
    def test_code_must_be_one_of_the_candidates(self):
        listed = [{"code": "C1", "name": "Chlorates"}]
        ok = model_match.validate({"code": "C1", "confidence": "high", "reason": "plural"}, listed)
        self.assertEqual(ok["code"], "C1")
        with self.assertRaises(ValueError):
            model_match.validate({"code": "ZZ", "confidence": "high", "reason": "made up"}, listed)

    def test_no_match_is_allowed(self):
        out = model_match.validate({"code": None, "confidence": "high", "reason": "different strain"}, [])
        self.assertIsNone(out["code"])


class BuildTest(unittest.TestCase):
    def guess(self, code, reason="same substance", confidence="high", candidates=("C1",)):
        return {"code": code, "confidence": confidence, "reason": reason, "candidates": list(candidates)}

    def test_cached_guess_links_an_unmatched_definition(self):
        rows = build([residue(1, "Chlorate")], TERMS, guesses={"Chlorate": self.guess("C1", "plural form")})
        d = rows[0]["default"]
        self.assertEqual((d["method"], d["param_codes"]), ("model", ["C1"]))
        self.assertEqual(d["evidence"]["via"], "model")
        self.assertEqual(d["evidence"]["reason"], "plural form")
        self.assertEqual(d["evidence"]["matched"], ["Chlorates"])
        self.assertEqual(d["evidence"]["model"], model_match.MODEL)

    def test_rule_links_are_never_replaced(self):
        rows = build([residue(1, "Cypermethrin")], TERMS, guesses={"Cypermethrin": self.guess("C1")})
        self.assertEqual(rows[0]["default"]["method"], "exact")

    def test_model_no_match_leaves_the_definition_unlinked(self):
        rows = build([residue(1, "Bacillus amyloliquefaciens str. QST 713")], TERMS,
                     guesses={"Bacillus amyloliquefaciens str. QST 713": self.guess(None, "different strain")})
        d = rows[0]["default"]
        self.assertEqual((d["method"], d["param_codes"]), ("none", []))
        self.assertEqual(d["model_guess"]["reason"], "different strain")

    def test_low_confidence_guess_is_a_suggestion_not_a_link(self):
        rows = build([residue(1, "Chlorate")], TERMS,
                     guesses={"Chlorate": self.guess("C1", confidence="low")})
        d = rows[0]["default"]
        self.assertNotEqual(d["method"], "model")
        self.assertEqual(d["model_guess"]["code"], "C1")
        self.assertIn("low confidence", d["model_guess"]["not_applied"])

    def test_stated_cas_vetoes_a_guess_for_a_term_with_another_cas(self):
        text = "Paraffin oil (CAS 64742-54-7)"
        rows = build([residue(1, text)], TERMS, guesses={text: self.guess("O1", candidates=("O1",))})
        d = rows[0]["default"]
        self.assertEqual((d["method"], d["param_codes"]), ("none", []))
        self.assertIn("CAS 64742-54-7", d["model_guess"]["not_applied"])

    def test_guess_naming_an_unknown_code_is_ignored(self):
        rows = build([residue(1, "Chlorate")], TERMS, guesses={"Chlorate": self.guess("GONE")})
        self.assertNotEqual(rows[0]["default"]["method"], "model")


class CacheTest(unittest.TestCase):
    def test_cache_is_tied_to_model_and_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "m.json")
            model_match.save({"Chlorate": {"code": "C1"}}, path)
            self.assertEqual(model_match.load(path), {"Chlorate": {"code": "C1"}})
            data = json.load(open(path))
            data["prompt"] = "old"
            json.dump(data, open(path, "w"))
            self.assertEqual(model_match.load(path), {})

    def test_run_asks_only_uncached_unlinked_definitions_and_respects_the_budget(self):
        rows = [{"residue_id": 1, "default": {"definition": "Chlorate", "method": "none"}, "exceptions": []},
                {"residue_id": 2, "default": {"definition": "Cypermethrin", "method": "exact"}, "exceptions": []},
                {"residue_id": 3, "default": {"definition": "Indolylacetic acid", "method": "near"},
                 "exceptions": [{"definition": "Diquat", "method": "none",
                                 "catalogue_gap": {"kind": "catalogue_scope_mismatch"}}]}]
        answers = iter([{"code": "C1", "confidence": "high", "reason": "plural"},
                        {"code": "I1", "confidence": "high", "reason": "synonym"}])
        with mock.patch.object(model_match.llm, "call", side_effect=lambda *a, **k: next(answers)) as call:
            cached = model_match.run(rows, TERMS, cached={}, max_calls=5)
        self.assertEqual(call.call_count, 2)  # not the exact link, not the verified catalogue gap
        self.assertEqual(cached["Chlorate"]["code"], "C1")
        self.assertEqual(cached["Indolylacetic acid"]["code"], "I1")
        with mock.patch.object(model_match.llm, "call") as call:
            model_match.run(rows, TERMS, cached=cached, max_calls=5)
        call.assert_not_called()
        with self.assertRaises(SystemExit):
            model_match.run(rows, TERMS, cached={}, max_calls=1)


if __name__ == "__main__":
    unittest.main()
