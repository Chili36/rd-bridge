import io
import json
import unittest
import zipfile
from pathlib import Path

from rd_bridge import components, load_param
from rd_bridge.components import ComponentIndex, completeness, parts
from tests.rules_map import rule_rows

ROOT = Path(__file__).resolve().parent.parent


def names(definition, role="analyte"):
    return [p["name"] for p in parts(definition)[1] if p["role"] == role]


class PartsTest(unittest.TestCase):
    def test_sum_and_anchor(self):
        anchor, found = parts("Sum of acetamiprid and N-desmethyl-acetamiprid (IM-2-1), expressed as acetamiprid")
        self.assertEqual(anchor, "acetamiprid")
        self.assertEqual([p["name"] for p in found], ["acetamiprid", "N-desmethyl-acetamiprid (IM-2-1)"])

    def test_qualifiers_are_notes_not_parts(self):
        self.assertEqual(names("2,4-D (sum of 2,4-D, its salts, its esters and its conjugates, expressed as 2,4-D)"),
                         ["2,4-D"])
        self.assertEqual(names("Cinidon-ethyl (sum of cinidon ethyl and its E-isomer)"), ["cinidon ethyl"])
        self.assertEqual(names("Benthiavalicarb-isopropyl (sum of benthiavalicarb-isopropyl (KIF 230 R-L) and "
                               "its RS enantiomer (KIF 230-S-D))"), ["benthiavalicarb-isopropyl (KIF 230 R-L)"])
        self.assertEqual(names("Bifenthrin (sum of isomers)"), ["Bifenthrin"])

    def test_commas_inside_names_do_not_split(self):
        self.assertEqual(names("DDT (sum of p,p´-DDT, o,p´-DDT, p-p´-DDE and p,p´-TDE (DDD) expressed as DDT)"),
                         ["p,p´-DDT", "o,p´-DDT", "p-p´-DDE", "p,p´-TDE (DDD)"])

    def test_isomer_locants_with_a_space(self):
        self.assertEqual(names("Dicofol (sum of p, p´ and o,p´ isomers)"), ["p,p´-Dicofol", "o,p´-Dicofol"])

    def test_shorthand_is_expanded(self):
        self.assertEqual(names("Aldicarb (sum of aldicarb, its sulfoxide and its sulfone, expressed as aldicarb)"),
                         ["aldicarb", "aldicarb sulfoxide", "aldicarb sulfone"])
        self.assertEqual(names("Sum of the three indicator compounds Parlar No 26, 50 and 62"),
                         ["Parlar No 26", "Parlar No 50", "Parlar No 62"])
        self.assertEqual(names("Endosulfan (sum of alpha- and beta-isomers and endosulfan-sulphate expressed as "
                               "endosulfan)"), ["alpha-endosulfan", "beta-endosulfan", "endosulfan-sulphate"])

    def test_their_derivatives_apply_to_every_substance_before(self):
        self.assertEqual(names("Phorate (sum of phorate, its oxygen analogue and their sulfones expressed as phorate)"),
                         ["phorate", "phorate oxygen analogue", "phorate sulfones", "phorate oxygen analogue sulfones"])
        self.assertEqual(names("Methiocarb (sum of methiocarb and methiocarb sulfoxide and sulfone, expressed as "
                               "methiocarb)"), ["methiocarb", "methiocarb sulfoxide", "methiocarb sulfone"])

    def test_free_and_conjugated_is_a_note(self):
        found = parts("Sum of 1,4-dimethylnaphthalene and its metabolite M23 free and conjugated, "
                      "expressed as 1,4-dimethylnaphthalene")[1]
        self.assertEqual([(p["name"], p["notes"]) for p in found],
                         [("1,4-dimethylnaphthalene", []), ("M23", ["free and conjugated"])])

    def test_named_conjugate_is_a_part(self):
        found = parts("sum of thiabendazole, 5-hydroxythiabendazole and its sulfate conjugate, "
                      "expressed as thiabendazole")[1]
        self.assertEqual([(p["role"], p["name"]) for p in found],
                         [("analyte", "thiabendazole"), ("analyte", "5-hydroxythiabendazole"),
                          ("analyte", "5-hydroxythiabendazole sulfate conjugate")])
        self.assertEqual(names("sum of tebuconazole, hydroxy-tebuconazole, and their conjugates, "
                               "expressed as tebuconazole", "qualifier"), [None])

    def test_trailing_stereo_note_keeps_the_main_clause(self):
        found = parts("Sum of haloxyfop, its salts and conjugates expressed as haloxyfop "
                      "(sum of the R- and S- isomers at any ratio)")[1]
        self.assertEqual([(p["role"], p["name"]) for p in found],
                         [("analyte", "haloxyfop"), ("qualifier", None), ("qualifier", None)])
        self.assertEqual(found[0]["notes"], ["sum of the r- and s-isomers at any ratio"])
        self.assertEqual(names("Lambda-cyhalothrin (includes gamma-cyhalothrin) (sum of R,S and S,R isomers)"),
                         ["Lambda-cyhalothrin", "gamma-cyhalothrin"])

    def test_stereo_note_pattern_is_linear(self):
        import time
        start = time.time()
        components.STEREO_NOTE.fullmatch("R- " * 40 + "x")
        self.assertLess(time.time() - start, 0.5)

    def test_unbalanced_parenthesis_and_common_moieties(self):
        found = parts("Bicyclopyrone (sum of bicyclopyrone and its structurally related metabolites determined as "
                      "the sum of the common moieties 2-(2- methoxyethoxymethyl)-6-(trifluoromethyl) pyridine-3-"
                      "carboxylic acid (SYN503780) and (2-(2-hydroxyethoxymethyl)-6- (trifluoromethyl)pyridine-3-"
                      "carboxylic acid (CSCD686480), expressed as bicyclopyrone)")[1]
        self.assertEqual([p["role"] for p in found], ["analyte"] * 3)
        self.assertEqual(found[0]["name"], "bicyclopyrone")
        self.assertIn("unbalanced parenthesis in the source text repaired", found[0]["notes"])

    def test_inclusions(self):
        found = parts("Sum of dichlorprop (including dichlorprop-P) and its salts, expressed as dichlorprop")[1]
        self.assertEqual([(p["role"], p["name"], p.get("included")) for p in found],
                         [("analyte", "dichlorprop", None), ("analyte", "dichlorprop-P", True), ("qualifier", None, None)])
        quiz = parts("Quizalofop (sum of quizalofop, its salts, its esters (including propaquizafop) and its "
                     "conjugates, expressed as quizalofop (any ratio of constituent isomers))")[1]
        self.assertIn(("propaquizafop", False), [(p["name"], p.get("included")) for p in quiz])
        origin = parts("Carbofuran (sum of carbofuran (including any carbofuran generated from carbosulfan, "
                       "benfuracarb or furathiocarb) and 3-OH carbofuran expressed as carbofuran)")[1]
        self.assertEqual([p["name"] for p in origin], ["carbofuran", "3-OH carbofuran"])

    def test_named_isomers_unless_a_clause_names_the_parts(self):
        self.assertEqual(names("Mevinphos (sum of E- and Z-isomers)"), ["E-Mevinphos", "Z-Mevinphos"])
        self.assertEqual(names("Cinidon-ethyl (sum of cinidon ethyl and its E-isomer)"), ["cinidon ethyl"])

    def test_plus_sign_and_constituent_isomers(self):
        self.assertEqual(names("Fipronil (sum fipronil + sulfone metabolite (MB46136) expressed as fipronil)"),
                         ["fipronil", "fipronil sulfone (MB46136)"])
        self.assertEqual(names("Tralkoxydim (sum of the constituent isomers of tralkoxydim)"), ["tralkoxydim"])
        self.assertEqual(names("Fluazifop-P (sum of all the constituent isomers of fluazifop, its esters and "
                               "its conjugates, expressed as fluazifop)"), ["fluazifop"])

    def test_groups(self):
        found = parts("Sum of iprodione and all metabolites containing the 3,5-dichloroaniline moiety, "
                      "expressed as iprodione")[1]
        self.assertEqual([p["role"] for p in found], ["analyte", "group"])


class LinkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.idx = ComponentIndex.load(ROOT / "data" / "param_components.json")
        cls.rows = {r["residue_id"]: r for r in rule_rows()}  # rule-parser components, not model readings

    def parts_of(self, residue_id, exception=None):
        row = self.rows[residue_id]
        entry = row["default"] if exception is None else row["exceptions"][exception]
        return {p["name"]: (p.get("method"), p["param_codes"]) for p in entry["components"] if p["role"] == "analyte"}

    def test_acetamiprid_parts(self):
        # PARAM files IM-2-1 in acetamiprid's family, not under the summed term
        self.assertEqual(self.parts_of(10, 0), {
            "acetamiprid": ("family", ["RF-0014-001-PPP"]),
            "N-desmethyl-acetamiprid (IM-2-1)": ("family", ["RF-00002836-PAR"])})

    def test_parts_filed_under_the_summed_term(self):
        found = self.parts_of(12)  # aldicarb: PARAM lists the parts under "Aldicarb (sum of ...)"
        self.assertEqual(found, {"aldicarb": ("param_sum", ["RF-0020-002-PPP"]),
                                 "aldicarb sulfoxide": ("param_sum", ["RF-0020-003-PPP"]),
                                 "aldicarb sulfone": ("param_sum", ["RF-0020-004-PPP"])})

    def test_param_spellings(self):
        found = self.parts_of(337)  # methiocarb: PARAM writes Methiocarb-Sulfoxid, -Sulfon
        self.assertEqual(found["methiocarb sulfoxide"][1], ["RF-0291-003-PPP"])
        self.assertEqual(found["methiocarb sulfone"][1], ["RF-0291-004-PPP"])

    def test_named_conjugate_links_to_its_own_code(self):
        found = self.parts_of(210, 1)  # thiabendazole, cow milk exception
        self.assertEqual(found["5-hydroxythiabendazole sulfate conjugate"][1], ["RF-00007631-PAR"])

    def test_single_substance_is_not_its_metabolite(self):
        kresoxim = self.rows[139]["default"]  # PARAM files BF-490-9 under kresoxim-methyl
        self.assertEqual(self.parts_of(139), {"Kresoxim-methyl": ("family", ["RF-0260-001-PPP"])})
        self.assertEqual(completeness(kresoxim, ["RF-0260-002-PPP"])["status"], "not_covered")

    def test_phorate_needs_the_oxon_sulfone(self):
        entry = self.rows[179]["default"]
        self.assertEqual(self.parts_of(179)["phorate oxygen analogue sulfones"][1], ["RF-0336-006-PPP"])
        self.assertEqual(completeness(entry, ["RF-0336-003-PPP", "RF-0336-005-PPP", "RF-0336-002-PPP"])["status"],
                         "partial")

    def test_isomer_names_in_param_word_order(self):
        self.assertEqual(self.parts_of(8)["delta-8,9 isomer of avermectin B1a"][1], ["RF-0011-002-PPP"])
        dicofol = self.parts_of(74)
        self.assertEqual((dicofol["p,p´-Dicofol"][1], dicofol["o,p´-Dicofol"][1]),
                         (["RF-0130-002-PPP"], ["RF-0130-003-PPP"]))
        self.assertEqual(completeness(self.rows[74]["default"], ["RF-0130-002-PPP", "RF-0130-003-PPP"])["status"],
                         "complete")

    def test_codes_behind_notes_and_capitals(self):
        self.assertEqual(self.parts_of(2890, 0)["M4"][1], ["RF-00014209-PAR"])  # "M4 (free and conjugated), ..."
        metalaxyl = next(e for e in [self.rows[3370]["default"]] + self.rows[3370]["exceptions"]
                         if "M3" in e["definition"])
        codes = {p["name"][:2]: p["param_codes"] for p in metalaxyl["components"] if p["role"] == "analyte"}
        self.assertEqual((codes["M3"], codes["M8"]), (["RF-00015696-PAR"], ["RF-00015697-PAR"]))
        self.assertEqual(completeness(self.rows[2536]["default"], ["RF-00011517-PAR"])["status"], "partial")

    def test_other_names_never_pull_in_another_substance(self):
        nag = next(p for p in self.rows[320]["default"]["components"] if p.get("name", "").startswith("N-acetyl"))
        self.assertNotIn("RF-00003362-PAR", nag["param_codes"])  # Penflufen lists N-acetylglufosinate

    def test_included_isomer_is_covered_by_its_parent(self):
        dichlorprop = self.rows[272]["default"]
        self.assertEqual(completeness(dichlorprop, ["RF-0126-002-PPP"])["status"], "complete")
        self.assertEqual(completeness(dichlorprop, ["RF-0126-003-PPP"])["status"], "partial")
        self.assertEqual(completeness(self.rows[370]["default"], ["RF-0384-004-PPP"])["status"], "partial")

    def test_catalogue_prefix_within_family_only_with_a_code(self):
        self.assertEqual(self.parts_of(138)["diketonitrile-metabolite"][1], ["RF-00004677-PAR"])
        self.assertEqual(self.parts_of(162)["milbemycin A4"][1], ["RF-0303-003-PPP"])  # not "8,9-milbemycin A4"

    def test_fipronil_and_its_sulfone(self):
        self.assertEqual(completeness(self.rows[302]["default"], ["RF-0192-003-PPP", "RF-0192-002-PPP"])["status"],
                         "complete")
        self.assertEqual(self.parts_of(304)["fluazifop"][1], ["RF-0698-001-PPP"])

    def test_milbemycin_is_param_milbemectin(self):
        self.assertEqual(completeness(self.rows[162]["default"], ["RF-0303-002-PPP", "RF-0303-003-PPP"])["status"],
                         "complete")

    def test_named_isomers_are_parts(self):
        self.assertEqual(completeness(self.rows[161]["default"], ["RF-00004672-PAR", "RF-00004673-PAR"])["status"],
                         "complete")  # Mevinphos E- and Z-isomer
        self.assertNotEqual(completeness(self.rows[793]["default"], ["RF-00007590-PAR"])["status"], "complete")

    def test_ambiguous_link_is_not_a_part(self):
        found = self.idx.describe("Xyzzyfen", {"method": "ambiguous", "param_codes": ["A", "B"]})
        self.assertEqual(found[0]["param_codes"], [])

    def test_alias_only_stereoisomer_is_not_an_alternate(self):
        self.assertEqual(self.parts_of(2471)["Carvone"][1], ["RF-0538-001-PPP"])  # not L-Carvone "(-)-Carvone"
        self.assertNotEqual(completeness(self.rows[2471]["default"], ["RF-00006897-PAR"])["status"], "complete")

    def test_single_substance_with_a_qualifier_is_its_own_part(self):
        # "Bromoxynil and its salts": the qualifier is not a second part
        self.assertEqual(self.parts_of(33), {"Bromoxynil": ("definition", ["RF-00003327-PAR"])})
        self.assertEqual(completeness(self.rows[33]["default"], ["RF-00003327-PAR"])["status"], "complete")

    def test_haloxyfop_exception(self):
        entry = self.rows[322]["exceptions"][0]
        self.assertEqual(completeness(entry, ["RF-0235-004-PPP"])["status"], "complete")

    def test_metabolite_numbers_never_match_outside_their_family(self):
        found = self.idx.link("M4", family=set())
        self.assertEqual(found["method"], "none")  # not flufenacet's M4

    def test_generic_isomer_text_never_matches_another_substance(self):
        self.assertEqual(self.idx.link("Z-isomer", family=set())["method"], "none")


class CompletenessTest(unittest.TestCase):
    ENTRY = {"method": "exact", "param_codes": ["SUM"], "components": [
        {"role": "analyte", "name": "A", "param_codes": ["A1"]},
        {"role": "analyte", "name": "B", "param_codes": ["B1", "B2"]},
        {"role": "qualifier", "text": "its salts", "param_codes": []}]}

    def test_statuses(self):
        self.assertEqual(completeness(self.ENTRY, ["SUM"])["via"], "summed code")
        self.assertEqual(completeness(self.ENTRY, ["A1", "B2"])["status"], "complete")
        partial = completeness(self.ENTRY, ["A1"])
        self.assertEqual((partial["status"], [m["name"] for m in partial["missing"]]), ("partial", ["B"]))
        self.assertEqual(completeness(self.ENTRY, ["X"])["status"], "not_covered")

    def test_unlinked_part_makes_it_undetermined(self):
        entry = {**self.ENTRY, "components": self.ENTRY["components"][:1] + [
            {"role": "analyte", "name": "TFNA", "param_codes": []}]}
        self.assertEqual(completeness(entry, ["A1"])["status"], "undetermined")

    def test_near_link_is_not_a_summed_code(self):
        self.assertNotEqual(completeness({**self.ENTRY, "method": "near"}, ["SUM"])["status"], "complete")

    def test_ambiguous_link_is_not_a_summed_code(self):
        entry = {**self.ENTRY, "method": "ambiguous", "param_codes": ["SUM", "OTHER"]}
        self.assertEqual(completeness(entry, ["OTHER"])["status"], "not_covered")


class LoadParamTest(unittest.TestCase):
    XML = """<message><catalogue><catalogueVersion><version>9.9</version><validFrom>2026-01-01T00:00:00</validFrom>
      </catalogueVersion></catalogue><terms>
      {terms}</terms></message>"""
    TERM = """<term><termDesc><termCode>{code}</termCode><termExtendedName>{name}</termExtendedName></termDesc>
      <termVersion><status>APPROVED</status></termVersion><hierarchyAssignments>{hier}</hierarchyAssignments>
      <implicitAttributes>{attrs}</implicitAttributes></term>"""

    def term(self, code, name, param_parent, pest=None, cls=None):
        hier = f"<hierarchyAssignment><hierarchyCode>PARAM</hierarchyCode><reportable>true</reportable>" \
               f"<parentCode>{param_parent}</parentCode></hierarchyAssignment>"
        if pest:
            hier += f"<hierarchyAssignment><hierarchyCode>pestParam</hierarchyCode><reportable>true</reportable>" \
                    f"<parentCode>{pest}</parentCode></hierarchyAssignment>"
        attrs = f"<implicitAttribute><attributeCode>pestClass</attributeCode><attributeValues>" \
                f"<attributeValue>{cls}</attributeValue></attributeValues></implicitAttribute>" if cls else ""
        return self.TERM.format(code=code, name=name, hier=hier, attrs=attrs)

    def test_components_keep_families(self):
        terms = [self.term("P", "Parent", "ROOT", "AS_GROUP", "AS"),
                 self.term("G", "Parent and M1 metabolite", "P"),
                 self.term("M", "M1 (metabolite)", "G", load_param.EXCLUDED_PARENT, "COMP")]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("PARAM.xml", self.XML.format(terms="".join(terms)))
        version, catalogue = load_param.read_catalogue(io.BytesIO(buf.getvalue()))
        self.assertEqual(version, {"version": "9.9", "valid_from": "2026-01-01T00:00:00"})
        self.assertEqual([t["code"] for t in load_param.pest_terms(catalogue)], ["P"])  # M is a component
        comps = load_param.components(catalogue)
        self.assertEqual(set(comps), {"P", "G", "M"})  # G kept as the family node between P and M
        idx = components.ComponentIndex({"terms": comps})
        self.assertEqual(idx.family("Parent"), {"P", "M"})


if __name__ == "__main__":
    unittest.main()
