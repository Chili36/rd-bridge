import io
import json
import os
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from rd_bridge import compare_parts, components, llm, match, model_parts
from rd_bridge.components import ComponentIndex, completeness
from tests.rules_map import rule_rows

ROOT = Path(__file__).resolve().parent.parent
BAC_CODES = ["RF-00003376-PAR", "RF-1078-003-PPP", "RF-1078-004-PPP", "RF-1078-005-PPP",
             "RF-1078-006-PPP", "RF-1078-007-PPP"]


def answering(answer):
    """A fake llm.call that records its prompts and returns `answer` (or answer(prompt))."""
    def caller(system, prompt, tool):
        caller.prompts.append(prompt)
        return answer(prompt) if callable(answer) else answer
    caller.prompts = []
    return caller


class LLMTest(unittest.TestCase):
    SCHEMA = {"type": "object", "properties": {"parts": {"type": "array"}}, "required": ["parts"],
              "additionalProperties": False}

    def reply(self, payload):
        return io.BytesIO(json.dumps(payload).encode())

    def test_needs_a_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(llm.LLMError):
                llm.call("s", "p", self.SCHEMA)

    def test_returns_the_structured_output_and_retries(self):
        busy = urllib.error.HTTPError(llm.API_URL, 529, "overloaded", {}, io.BytesIO(b"{}"))
        ok = self.reply({"stop_reason": "end_turn", "content": [
            {"type": "thinking", "thinking": ""}, {"type": "text", "text": '{"parts": []}'}]})
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}), \
                mock.patch("urllib.request.urlopen", side_effect=[busy, ok]) as urlopen, \
                mock.patch("time.sleep"):
            self.assertEqual(llm.call("s", "p", self.SCHEMA), {"parts": []})
        request = urlopen.call_args[0][0]
        body = json.loads(request.data)
        self.assertEqual(body["model"], llm.MODEL)
        self.assertEqual(body["output_config"]["format"], {"type": "json_schema", "schema": self.SCHEMA})
        self.assertNotIn("tool_choice", body)  # Sonnet 5.5 rejects a forced tool
        self.assertFalse({"temperature", "top_p", "top_k"} & set(body))  # Haiku/Sonnet 5.5 reject them
        self.assertEqual(request.get_header("X-api-key"), "k")

    def test_refusal_or_truncation_is_an_error(self):
        for stop in ("refusal", "max_tokens"):
            reply = self.reply({"stop_reason": stop, "content": [{"type": "text", "text": '{"par'}]})
            with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}), \
                    mock.patch("urllib.request.urlopen", side_effect=[reply]):
                with self.assertRaises(llm.LLMError):
                    llm.call("s", "p", self.SCHEMA)

    def test_every_object_in_the_schema_is_closed(self):
        def objects(node):
            if isinstance(node, dict):
                if node.get("type") == "object":
                    yield node
                for v in node.values():
                    yield from objects(v)
            elif isinstance(node, list):
                for v in node:
                    yield from objects(v)
        for obj in objects(model_parts.SCHEMA):
            self.assertIs(obj.get("additionalProperties"), False)
            self.assertEqual(set(obj["required"]), set(obj["properties"]))

    def test_default_model_and_override(self):
        import importlib
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(importlib.reload(llm).MODEL, "claude-haiku-5-5")
        with mock.patch.dict(os.environ, {"RD_BRIDGE_MODEL": "claude-sonnet-5-5"}):
            self.assertEqual(importlib.reload(llm).MODEL, "claude-sonnet-5-5")
        importlib.reload(llm)  # back to the environment the suite runs in

    def test_client_errors_are_not_retried(self):
        bad = urllib.error.HTTPError(llm.API_URL, 400, "bad", {}, io.BytesIO(b"{}"))
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}), \
                mock.patch("urllib.request.urlopen", side_effect=[bad]):
            with self.assertRaises(llm.LLMError):
                llm.call("s", "p", self.SCHEMA)


class ModelPartsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.idx = ComponentIndex.load(ROOT / "data" / "param_components.json")

    def test_clean_keeps_only_well_formed_parts_and_offered_names(self):
        answer = {"expressed_as": "X", "parts": [
            {"name": "X", "role": "analyte", "param_name": "X term"},
            {"name": "Y", "role": "analyte", "param_name": "invented"},
            {"name": "", "role": "analyte"}, {"name": "Z", "role": "parent"},
            {"name": "its salts", "role": "qualifier"}]}
        cleaned = model_parts.clean(answer, ["X term"])
        self.assertEqual([p["name"] for p in cleaned["parts"]], ["X", "Y", "its salts"])
        self.assertEqual(cleaned["parts"][0]["param_name"], "X term")
        self.assertNotIn("param_name", cleaned["parts"][1])
        # nothing measurable ("Beer"): cached as an empty answer, not asked again, rules used
        self.assertEqual(model_parts.clean({"parts": [{"name": "its salts", "role": "qualifier"}]})["parts"], [])

    def test_prompt_rules_on_isomers_and_determined_products(self):
        # the two patterns behind 7 failed acceptance cases in the first Haiku run; a changed
        # prompt changes its hash, so every cached answer is asked again
        self.assertIn('"X and its E-isomer"', model_parts.SYSTEM)
        self.assertIn('"sum of all isomers of X" means the analyte is X', model_parts.SYSTEM)
        self.assertIn('"determined as"', model_parts.SYSTEM)
        cached = {"model": llm.MODEL, "prompt": "0" * 16, "definitions": {"X": {}}}
        with mock.patch("builtins.open", mock.mock_open(read_data=json.dumps(cached))), \
                mock.patch("os.path.exists", return_value=True):
            self.assertEqual(model_parts.load("x.json"), {})

    def test_prompt_offers_the_family(self):
        definition = ("Benzalkonium chloride (mixture of alkylbenzyldimethylammonium chlorides with alkyl chain "
                      "lengths of C8, C10, C12, C14, C16 and C18)")
        names = model_parts.family_names(self.idx, definition, definition)
        self.assertIn("BAC 8", names)
        caller = answering({"expressed_as": None, "parts": [{"name": "BAC 8", "role": "analyte"}]})
        answer = model_parts.ask(definition, names, caller)
        self.assertIn("- BAC 8", caller.prompts[0])
        self.assertEqual(answer["context"], model_parts.context_hash(names))

    def test_a_text_under_two_residues_gets_both_families(self):
        definition = "Carbendazim and thiophanate-methyl, expressed as carbendazim"
        texts = model_parts.definitions(ROOT / "data" / "residue_param_map.json")
        self.assertGreater(len(texts[definition]), 1)
        names = model_parts.context(self.idx, definition, texts[definition])
        self.assertTrue(any(n.startswith("Thiophanate-methyl") for n in names))

    def test_refresh_reuses_answers_until_the_family_changes(self):
        caller = answering({"expressed_as": None, "parts": [{"name": "A", "role": "analyte"}]})
        answers, errors = model_parts.refresh({"A": ["a"]}, {}, caller, workers=1)
        model_parts.refresh({"A": ["a"]}, answers, caller, workers=1)
        self.assertEqual(len(caller.prompts), 1)
        model_parts.refresh({"A": ["a", "b"]}, answers, caller, workers=1)
        self.assertEqual(len(caller.prompts), 2)
        answers, errors = model_parts.refresh({"B": []}, {}, answering({"parts": []}), workers=1)
        self.assertEqual((answers["B"]["parts"], errors), ([], {}))  # cached, not an error

    def test_answers_for_another_family_are_dropped(self):
        answers = {"A": {"context": model_parts.context_hash(["a"])}, "B": {"context": model_parts.context_hash([])}}
        self.assertEqual(set(model_parts.current(answers, {"A": ["a", "b"], "B": []})), {"B"})

    def test_bac_read_by_model_links_every_chain_length(self):
        definition = ("Benzalkonium chloride (mixture of alkylbenzyldimethylammonium chlorides with alkyl chain "
                      "lengths of C8, C10, C12, C14, C16 and C18)")
        reading = {"expressed_as": None, "parts": [
            {"name": f"benzalkonium chloride C{n}", "role": "analyte", "param_name": f"BAC {n}"}
            for n in (8, 10, 12, 14, 16, 18)]}
        link = {"method": "exact", "param_codes": ["RF-00002582-PAR"]}
        found = self.idx.describe(definition, link, definition, model_parts.as_parts(reading, definition))
        self.assertTrue({p["method"] for p in found} <= {"model", "param_sum", "family"})
        entry = {**link, "components": found}
        self.assertEqual(sorted(c for p in found for c in p["param_codes"]), sorted(BAC_CODES))
        self.assertEqual(completeness(entry, BAC_CODES[1:])["status"], "partial")
        self.assertEqual(completeness(entry, BAC_CODES)["status"], "complete")

    def test_a_code_in_parentheses_names_the_part_not_its_parent(self):
        family = self.idx.family("kresoxim methyl", "kresoxim methyl")
        self.assertEqual(self.idx.link("kresoxim methyl (BF-490-9)", family)["param_codes"], ["RF-0260-002-PPP"])

    def test_rule_links_win_over_the_offered_name(self):
        reading = {"expressed_as": "acetamiprid", "parts": [
            {"name": "acetamiprid", "role": "analyte", "param_name": "IM-2-1 (N1-[(6-chloro-3-pyridyl)methyl]-N2-cyanoacetamidine),(N-desmethyl-acetamiprid)"}]}
        found = self.idx.describe("Acetamiprid", {}, "Acetamiprid", model_parts.as_parts(reading, "Acetamiprid"))
        self.assertEqual(found[0]["param_codes"], ["RF-0014-001-PPP"])
        self.assertFalse(found[0]["model_agrees"])  # kept, so agreement can be measured
        self.assertEqual(found[0]["model_named"], ["RF-00002836-PAR"])

    def test_a_misread_name_never_links_outside_the_family(self):
        reading = {"expressed_as": "acetamiprid", "parts": [{"name": "Glyphosate", "role": "analyte"}]}
        exact = {"method": "exact", "param_codes": ["RF-0014-001-PPP"]}  # as the definition is linked in the map
        found = self.idx.describe("Acetamiprid", exact, "Acetamiprid", model_parts.as_parts(reading, "Acetamiprid"))
        self.assertEqual((found[0]["method"], found[0]["param_codes"]), ("none", []))  # no definition fallback
        offered = {"expressed_as": None, "parts": [{"name": "Glyphosate", "role": "analyte",
                                                    "param_name": "Acetamiprid"}]}
        found = self.idx.describe("Acetamiprid", exact, "Acetamiprid", model_parts.as_parts(offered, "Acetamiprid"))
        self.assertEqual(found[0]["param_codes"], [])  # a rejected name is not re-linked by its param_name
        moved = {"expressed_as": "Glyphosate", "parts": [{"name": "Glyphosate", "role": "analyte"}]}
        found = self.idx.describe("Acetamiprid", exact, "Acetamiprid", model_parts.as_parts(moved, "Acetamiprid"))
        self.assertEqual(found[0]["param_codes"], [])  # a made-up "expressed as" does not move the family
        written = {"expressed_as": None, "parts": [{"name": "Glyphosate", "role": "analyte"}]}
        found = self.idx.describe("Glyphosate", {}, "Glyphosate", model_parts.as_parts(written, "Glyphosate"))
        self.assertTrue(found[0]["param_codes"])  # a name written in the text still links

    def test_a_family_member_not_in_the_text_is_not_a_reading(self):
        exact = {"method": "exact", "param_codes": ["RF-0014-001-PPP"]}
        reading = {"expressed_as": None, "parts": [{"name": "N-desmethyl-acetamiprid (IM-2-1)", "role": "analyte"}]}
        found = self.idx.describe("Acetamiprid", exact, "Acetamiprid", model_parts.as_parts(reading, "Acetamiprid"))
        self.assertEqual(found[0]["param_codes"], [])
        self.assertTrue(components._grounded("aldicarb sulfoxide", "Aldicarb (sum of aldicarb, its sulfoxide and "
                                                                    "its sulfone, expressed as aldicarb)"))
        self.assertTrue(components._grounded("phorate oxygen analogue sulfone",
                                             "phorate, its oxygen analogue and their sulphones"))
        self.assertFalse(components._grounded("Methoxychlorolefin", "Methoxychlor"))  # a longer name
        self.assertTrue(components._grounded("ammonium salt with alkyl chain length of C8",
                                             "alkyl-quaternary ammonium salts with alkyl chain lengths of C8"))

    def test_included_in_needs_inclusion_wording(self):
        definition = "Fipronil (sum fipronil + sulfone metabolite (MB46136) expressed as fipronil)"
        reading = {"expressed_as": "fipronil", "parts": [
            {"name": "fipronil", "role": "analyte"},
            {"name": "fipronil sulfone (MB46136)", "role": "analyte", "included_in": "fipronil"}]}
        found = self.idx.describe(definition, {}, "Fipronil", model_parts.as_parts(reading, definition))
        self.assertNotEqual(completeness({"components": found}, ["RF-0192-003-PPP"])["status"], "complete")

    def test_included_in_gives_covered_by(self):
        definition = "Dichlorprop (sum of dichlorprop, including dichlorprop-P, its salts, esters and conjugates)"
        reading = {"expressed_as": "dichlorprop", "parts": [
            {"name": "dichlorprop", "role": "analyte"},
            {"name": "dichlorprop-P", "role": "analyte", "included_in": "dichlorprop"},
            {"name": "its salts", "role": "qualifier"}]}
        found = self.idx.describe(definition, {}, "Dichlorprop", model_parts.as_parts(reading, definition))
        included = next(p for p in found if p.get("name") == "dichlorprop-P")
        self.assertEqual(included["covered_by"], ["RF-0126-002-PPP"])
        self.assertEqual(completeness({"components": found}, ["RF-0126-002-PPP"])["status"], "complete")


class MatchWithModelTest(unittest.TestCase):
    def test_build_uses_readings(self):
        terms = json.loads((ROOT / "data" / "param_pest_terms.json").read_text())
        idx = ComponentIndex.load(ROOT / "data" / "param_components.json")
        definition = "Fipronil (sum fipronil + sulfone metabolite (MB46136) expressed as fipronil)"
        residues = [{"pesticide_residue_id": 1, "pesticide_residue_name": "Diquat"},
                    {"pesticide_residue_id": 2, "pesticide_residue_name": definition}]
        readings = {definition: {"expressed_as": "fipronil", "parts": [
            {"name": "fipronil", "role": "analyte"}, {"name": "fipronil sulfone (MB46136)", "role": "analyte"}]}}
        rows = match.build(residues, terms, idx, readings)
        diquat, fipronil = rows[0]["default"], rows[1]["default"]
        self.assertEqual((fipronil["parts_from"], diquat["parts_from"]), ("model", "rules"))
        self.assertEqual(completeness(fipronil, ["RF-0192-003-PPP", "RF-0192-002-PPP"])["status"], "complete")


class ReadingChoiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.terms = json.loads((ROOT / "data" / "param_pest_terms.json").read_text())
        cls.idx = ComponentIndex.load(ROOT / "data" / "param_components.json")

    def build(self, name, reading):
        residues = [{"pesticide_residue_id": 1, "pesticide_residue_name": name}]
        return match.build(residues, self.terms, self.idx, {name: reading})[0]["default"]

    def test_an_empty_reading_leaves_the_rules_in_place(self):
        entry = self.build("Beer", {"expressed_as": None, "parts": []})
        self.assertEqual(entry["parts_from"], "rules")
        self.assertNotIn("model_reading_lost", entry)

    def test_a_reading_that_loses_a_rule_link_is_not_used(self):
        name = "Dicofol (sum of p, p´ and o,p´ isomers)"
        entry = self.build(name, {"expressed_as": None, "parts": [{"name": "Dicofol", "role": "group"}]})
        self.assertEqual(entry["parts_from"], "rules")
        self.assertEqual(entry["model_reading_lost"], ["RF-0130-002-PPP", "RF-0130-003-PPP"])

    def test_a_reading_that_splits_a_whole_into_linked_parts_is_used(self):
        name = ("Benzalkonium chloride (mixture of alkylbenzyldimethylammonium chlorides with alkyl chain "
                "lengths of C8, C10, C12, C14, C16 and C18)")
        reading = {"expressed_as": None, "parts": [
            {"name": f"alkylbenzyldimethylammonium chloride C{n}", "role": "analyte", "param_name": f"BAC {n}"}
            for n in (8, 10, 12, 14, 16, 18)]}
        entry = self.build(name, reading)
        self.assertEqual(entry["parts_from"], "model")
        self.assertEqual(completeness(entry, BAC_CODES)["status"], "complete")

    def test_unlinked_parts_do_not_replace_a_linked_whole(self):
        name = "Indoxacarb (sum of indoxacarb and its R enantiomer)"
        # as Haiku read it: two parts, neither linked, instead of the rules' one linked whole
        reading = {"expressed_as": None, "parts": [{"name": "Indoxacarb", "role": "analyte"},
                                                   {"name": "indoxacarb R enantiomer", "role": "analyte"}]}
        self.assertEqual(self.build(name, reading)["parts_from"], "rules")


    def test_a_reading_may_not_swap_the_code_of_a_whole(self):
        name = "Fluazifop-P (sum of all the constituent isomers of fluazifop, its esters and its conjugates, expressed as fluazifop)"
        reading = {"expressed_as": "fluazifop", "parts": [{"name": "Fluazifop-P", "role": "analyte", "param_name": "Fluazifop-P"}]}
        entry = self.build(name, reading)
        self.assertEqual((entry["parts_from"], entry["model_reading_lost"]), ("rules", ["RF-0698-001-PPP"]))

    def test_a_rule_part_linked_only_to_the_summed_code_is_not_a_lost_link(self):
        name = ("free and conjugated forms of alpha-(3-hydroxybutyl) - alpha - (4-chloro-phenyl) - 1H - 1,2,4 - "
                "triazole -1-propanenitrile (RH9090), expressed as myclobutanil")
        reading = {"expressed_as": "myclobutanil", "parts": [
            {"name": "alpha-(3-hydroxybutyl) - alpha - (4-chloro-phenyl) - 1H - 1,2,4 - triazole -1-propanenitrile (RH9090)",
             "role": "analyte"}, {"name": "free and conjugated forms", "role": "qualifier"}]}
        entry = self.build(name, reading)
        self.assertEqual(entry["parts_from"], "model")
        self.assertEqual(completeness(entry, ["RF-1005-001-PPP"])["status"], "complete")


class CompareTest(unittest.TestCase):
    def test_verdicts(self):
        a = [{"role": "analyte", "name": "a", "param_codes": ["A"]}]
        ab = a + [{"role": "analyte", "name": "b", "param_codes": ["B"]}]
        group = a + [{"role": "group", "name": "metabolites containing the 2,4-dimethylaniline moiety"}]
        self.assertEqual(compare_parts.verdict(a, a), "same")
        self.assertEqual(compare_parts.verdict(ab, a), "different")
        self.assertEqual(compare_parts.verdict(a, group), "different")  # the model dropped the group

    def test_agreement_and_model_links_are_reported(self):
        rows = [{"residue_id": 1, "name": "X", "exceptions": [], "default": {
            "definition": "X", "method": "none", "param_codes": [], "parts_from": "model", "components": [
                {"role": "analyte", "name": "x", "method": "family", "param_codes": ["A"], "model_agrees": True},
                {"role": "analyte", "name": "y", "method": "model", "param_codes": ["B"], "param_names": ["Y"]}]}}]
        index = mock.Mock(describe=lambda *a: [])
        result = compare_parts.compare(rows, index)
        self.assertEqual(result["agreement"], {"agree": 1})
        self.assertEqual(result["model_links"][0]["param"], ["Y"])

    def test_another_unlinked_part_is_not_the_same(self):
        tfna = {"role": "analyte", "name": "TFNA", "param_codes": []}
        tfng = {"role": "analyte", "name": "TFNG", "param_codes": []}
        other = {"role": "analyte", "name": "TFNG-AM", "param_codes": []}
        self.assertEqual(compare_parts.verdict([tfna, tfng], [tfna, tfng]), "same")
        self.assertEqual(compare_parts.verdict([tfna, other], [tfna, tfng]), "different")

    def test_a_dropped_coverage_is_a_difference(self):
        parent = {"role": "analyte", "name": "benalaxyl", "param_codes": ["P"]}
        included = {"role": "analyte", "name": "benalaxyl-M", "param_codes": ["M"]}
        rules = [parent, {**included, "covered_by": ["P"]}]
        self.assertEqual(compare_parts.verdict([parent, included], rules), "different")

    def test_rule_parser_fails_the_known_cases(self):
        failed = {c["case"] for c in compare_parts.cases(rule_rows()) if not c["passed"]}
        self.assertIn("BAC C8-C18 chain lengths cover benzalkonium chloride", failed)
        self.assertNotIn("aldicarb, its sulfoxide and sulfone", failed)


if __name__ == "__main__":
    unittest.main()
