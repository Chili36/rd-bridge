import json
import unittest
from pathlib import Path

from rd_bridge import footnotes


def one(text):
    out = footnotes.parse(text)
    assert len(out) == 1, out
    return out[0]


class ScopeTest(unittest.TestCase):
    def test_code_except(self):
        e = one("Acetamiprid - code 1000000 except 1040000: Sum of acetamiprid and "
                "N-desmethyl-acetamiprid (IM-2-1), expressed as acetamiprid")
        self.assertEqual(e["commodity_codes"], ["1000000"])
        self.assertEqual(e["except_codes"], ["1040000"])
        self.assertTrue(e["definition"].startswith("Sum of acetamiprid"))
        self.assertEqual((e["repairs"], e["issues"]), ([], []))

    def test_slash_list(self):
        e = footnotes.parse("Pyrimethanil - codes 1011000/1012000/1013000: Sum of pyrimethanil")[0]
        self.assertEqual(e["commodity_codes"], ["1011000", "1012000", "1013000"])

    def test_range_expands_siblings(self):
        e = one("Bentazone — codes from 1010000 to 1070000, except 1040000: Sum of bentazone")
        self.assertEqual(e["commodity_codes"],
                         ["1010000", "1020000", "1030000", "1040000", "1050000", "1060000", "1070000"])
        self.assertEqual(e["except_codes"], ["1040000"])

    def test_no_colon(self):
        e = one("Terbuthylazine - code 1020000  Sum of terbuthylazine and desethyl-terbuthylazine, "
                "expressed as terbuthylazine (F)")
        self.assertEqual(e["commodity_codes"], ["1020000"])
        self.assertEqual(e["definition"], "Sum of terbuthylazine and desethyl-terbuthylazine, "
                                          "expressed as terbuthylazine")

    def test_plant_code_without_keyword_prefix(self):
        e = one("Cyprodinil-1020000: Cyprodinil (free and conjugated)")
        self.assertEqual(e["commodity_codes"], ["1020000"])


class SplitTest(unittest.TestCase):
    def test_semicolon_opens_new_clause(self):
        out = footnotes.parse("code 1000000 except 1040000: Sum of THPI, 3-OH THPI and 5-OH THPI, "
                              "expressed as captan; code 0151020: captan")
        self.assertEqual([e["commodity_codes"] for e in out], [["1000000"], ["0151020"]])
        self.assertEqual(out[1]["definition"], "captan")

    def test_semicolon_inside_definition_is_kept(self):
        e = one("code 1000000: sum of A; B and C")
        self.assertEqual(e["definition"], "sum of A; B and C")

    def test_literal_backslash_newlines_and_notes(self):
        out = footnotes.parse("Kresoxim-methyl — code 1000000 except 1040000: kresoxim methyl "
                              "(BF-490-9, expressed as parent)\\n\\rMetabolite BF 490-9 = 2-[2-...]")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["definition"], "kresoxim methyl (BF-490-9, expressed as parent)")

    def test_duplicate_clauses_collapse(self):
        clause = "Flusilazole — code 1000000 except 1040000: Sum of flusilazole and IN-F7321"
        out = footnotes.parse(clause + "\\n\\rThe residue definition differs for the following "
                              "combinations pesticide-code number: " + clause)
        self.assertEqual(len(out), 1)


class RepairTest(unittest.TestCase):
    def test_thiabendazole_missing_zero(self):
        out = footnotes.parse(
            "Thiabendazole — code 100000, except 1020000 and 1040000: sum of thiabendazole and "
            "5-hydroxythiabendazole, expressed as thiabendazole\n\n"
            "Thiabendazole — code 1020000: sum of thiabendazole, 5-hydroxythiabendazole and its "
            "sulfate conjugate, expressed as thiabendazole")
        self.assertEqual(out[0]["commodity_codes"], ["1000000"])
        self.assertEqual(out[0]["except_codes"], ["1020000", "1040000"])
        self.assertEqual(out[0]["repairs"], [{"from": "100000", "to": "1000000",
                                              "reason": "except codes nest inside it"}])
        self.assertEqual(out[0]["issues"], [])
        self.assertEqual(out[1]["commodity_codes"], ["1020000"])

    def test_cereals_leading_zero(self):
        e = one("Chlorpyrifos-methyl  -  code  500000:  sum  of  chlorpyrifos-methyl")
        self.assertEqual(e["commodity_codes"], ["0500000"])
        self.assertEqual(e["repairs"][0]["reason"], "leading zero dropped")


    def test_undecided_repair_is_an_issue(self):
        e = one("code 100000: x")
        self.assertEqual(e["commodity_codes"], ["0100000"])
        self.assertEqual(e["repairs"][0]["reason"], "undecided")
        self.assertIn("100000: could be 0100000 or 1000000", e["issues"])


class CheckTest(unittest.TestCase):
    def test_except_range_expands(self):
        e = one("code 1000000 except codes 1010000 to 1030000: x")
        self.assertEqual(e["except_codes"], ["1010000", "1020000", "1030000"])
        self.assertEqual(e["issues"], [])

    def test_except_outside_scope_is_flagged(self):
        e = one("code 0500000 except 1040000: x")
        self.assertIn("except 1040000: not inside any included code", e["issues"])

    def test_unknown_group_is_flagged(self):
        e = one("code 1300000: x")
        self.assertIn("1300000: not an Annex I group", e["issues"])

    def test_hierarchy(self):
        self.assertTrue(footnotes.contains("1000000", "1040000"))
        self.assertTrue(footnotes.contains("1011000", "1011010"))
        self.assertFalse(footnotes.contains("1000000", "1100000"))
        self.assertFalse(footnotes.contains("1011000", "1012010"))


class NotAClauseTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(footnotes.parse(None), [])
        self.assertEqual(footnotes.parse("(*) Limit of analytical determination"), [])


class CommittedDataTest(unittest.TestCase):
    def test_every_r_footnote_parses_cleanly(self):
        path = Path(__file__).resolve().parent.parent / "data" / "residues_en.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        notes = [r for r in rows if r.get("pesticide_residue_footnote_code") == "(R)"]
        self.assertTrue(notes)
        for r in notes:
            out = footnotes.parse(r["pesticide_residue_footnote_txt"])
            with self.subTest(residue=r["pesticide_residue_id"]):
                self.assertTrue(out)
                for e in out:
                    self.assertEqual(e["issues"], [])
                    self.assertTrue(all(len(c) == 7 for c in e["commodity_codes"] + e["except_codes"]))
                    self.assertTrue(e["definition"])


if __name__ == "__main__":
    unittest.main()
