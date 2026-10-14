"""(sampMatCode, substance) -> PARAM code, with the evidence of every step.

sampMatCode --rd_bridge.commodity--> Annex I commodity code
substance   --data/residue_param_map.json--> residue: default definition and (R) exceptions
code        --Annex I hierarchy--> the exception whose scope holds the code, else the default

With --analysed, also says whether those PARAM codes cover the chosen definition: the summed
code, or every part (rd_bridge.components.completeness).

Usage: python -m rd_bridge.resolve <sampMatCode> <substance name, residue id or PARAM code> [--analysed CODE,CODE]
"""
import json
import re
import sys

from rd_bridge import components, compounds, footnotes
from rd_bridge.commodity import Classifier

MARKERS = re.compile(r"\s*(\((R|F|A|\+|\+\+|\*|)\)\s*)+$")
PARAM_CODE = re.compile(r"RF-[0-9A-Z-]+", re.I)


class Resolver:
    def __init__(self, residues: list, classifier: Classifier, active_substances=None,
                 param_terms=None):
        self.residues = residues
        self.classifier = classifier
        self.by_id = {r["residue_id"]: r for r in residues}
        self.by_name = {}
        for r in residues:
            name = MARKERS.sub("", r["name"]).strip()
            for key in {compounds.norm(name), compounds.norm(name.split(" (")[0])}:
                self.by_name.setdefault(key, []).append(r)
        # A caller may only have the PARAM code it mapped: index whole-residue links, default
        # and exceptions. Component codes are left out: one parent is a part of many sums.
        # Near matches too: a suggestion is not a link (see "untrusted_link").
        self.by_code = {}
        for r in residues:
            for entry in [r["default"], *r["exceptions"]]:
                if entry.get("method") == "near":
                    continue
                for code in entry.get("param_codes", []):
                    if r not in self.by_code.setdefault(code, []):
                        self.by_code[code].append(r)
        self.active = {}
        for row in active_substances or []:
            if row.get("name"):
                key = compounds.norm(row["name"])
                self.active.setdefault(key, []).append(row)
        self.param_name, self.param_cas = {}, {}
        for term in param_terms or []:
            if term.get("pestClass") not in ("AS", "RD"):
                continue  # a component or unrelated pesticide group is not the substance itself
            self.param_name.setdefault(compounds.norm(term["name"]), set()).add(term["code"])
            cas = term.get("cas")
            if cas and re.fullmatch(r"\d{2,7}-\d\d-\d", cas):
                self.param_cas.setdefault(cas, set()).add(term["code"])

    @classmethod
    def load(cls, residue_map="data/residue_param_map.json", mapping="data/foodex2_ppp.json",
             active_path="data/active_substances.json", param_path="data/param_pest_terms.json"):
        with open(residue_map, encoding="utf-8") as fh:
            residues = json.load(fh)
        with open(active_path, encoding="utf-8") as fh:
            active = json.load(fh)
        with open(param_path, encoding="utf-8") as fh:
            terms = json.load(fh)
        return cls(residues, Classifier.load(mapping), active, terms)

    def residue(self, substance) -> list:
        if isinstance(substance, int) or str(substance).isdigit():
            hit = self.by_id.get(int(substance))
            return [hit] if hit else []
        if PARAM_CODE.fullmatch(str(substance).strip()):
            return self.by_code.get(str(substance).strip().upper(), [])
        return self.by_name.get(compounds.norm(str(substance)), [])

    def _active_status(self, substance) -> dict | None:
        """An EU-known active substance without an exact residue-name match.

        'pesticide_residue_linked' is an EU *description*, not a foreign-key ID.
        Only the EU's explicit default-MRL wording establishes the no-definition
        state; otherwise a linked definition may have a different name.
        """
        matches = self.active.get(compounds.norm(str(substance)), [])
        if not matches:
            return None
        unique = {(r.get("substance_id"), r.get("cas"), r.get("approval_status"),
                   r.get("pesticide_residue_linked")) for r in matches}
        if len(unique) != 1:
            return {"status": "ambiguous_substance",
                    "candidates": [{"substance_id": r.get("substance_id"),
                                    "linked_definition": r.get("pesticide_residue_linked")} for r in matches]}
        record = matches[0]
        linked = record.get("pesticide_residue_linked") or ""
        status = ("no_residue_definition" if re.match(r"^Default MRL of 0\.01 mg/kg\b", linked, re.I)
                  else "residue_definition_unresolved")
        name_hits = self.param_name.get(compounds.norm(record["name"]), set())
        cas_hits = self.param_cas.get(record.get("cas"), set())
        if name_hits:
            method, codes = "exact", name_hits
        elif cas_hits:
            method, codes = "cas", cas_hits
        else:
            method, codes = "none", set()
        if len(codes) > 1:
            method = "ambiguous"
        result = {"status": status, "approval_status": record.get("approval_status"),
                  "substance_id": record.get("substance_id"),
                  "method": method, "param_codes": sorted(codes),
                  "source": "EU active-substances"}
        if status == "no_residue_definition":
            result["mrl"] = linked  # EU API's exact wording, not a legal judgment
        else:
            result["linked_definition"] = linked
        return result

    @staticmethod
    def _in_scope(exception: dict, code: str) -> bool:
        return (any(footnotes.contains(c, code) for c in exception["commodity_codes"])
                and not any(footnotes.contains(e, code) for e in exception["except_codes"]))

    def resolve(self, samp_mat_code: str, substance, analysed=None) -> dict:
        out = self._resolve(samp_mat_code, substance)
        if analysed is not None:
            if out["status"] in ("no_residue_definition", "residue_definition_unresolved"):
                out["completeness"] = {"status": "not_applicable",
                                       "reason": "no chosen EU residue definition to assess"}
                return out
            chosen = out if "param_codes" in out else None
            if chosen is not None:
                out["completeness"] = components.completeness(chosen, analysed)
            else:  # several candidate definitions: answer for each
                for c in out.get("candidates", []):
                    if isinstance(c, dict) and "components" in c:
                        c["completeness"] = components.completeness(c, analysed)
        return out

    def _resolve(self, samp_mat_code: str, substance) -> dict:
        commodity = self.classifier.classify(samp_mat_code)
        found = self.residue(substance)
        out = {"sampMatCode": commodity["sampMatCode"], "substance": substance,
               "commodity": {k: commodity[k] for k in ("food_class", "annex_code", "annex_subcode", "rule")}}
        if len(found) != 1:
            if not found:
                known = self._active_status(substance)
                if known is not None:
                    return {**out, **known}
            status = "unknown_substance" if not found else "ambiguous_substance"
            return {**out, "status": status, "candidates": [r["residue_id"] for r in found]}
        residue = found[0]
        out.update(
            residue_id=residue["residue_id"], residue_name=residue["name"],
            applicability={
                "status": "presumed_applicable",
                "basis": "Latest EU-published residue definition unless a later application date is known.",
            },
        )
        exceptions = residue["exceptions"]
        code = commodity["annex_code"]

        if code is None and exceptions:
            # EFSA could not place the food in Annex I (XXXXXXA, or a special class such as
            # infant food), and this residue's definition depends on the commodity.
            return {**out, "status": "commodity_unresolved",
                    "candidates": [{"scope": "default", **self._link(residue["default"])}]
                    + [{"scope": "exception", **self._exception(x), **self._link(x)} for x in exceptions]}

        matching = [x for x in exceptions if code and self._in_scope(x, code)]
        if matching:
            depth = {id(x): max(footnotes.level(c) for c in x["commodity_codes"]
                                if footnotes.contains(c, code)) for x in matching}
            deepest = max(depth.values())
            matching = [x for x in matching if depth[id(x)] == deepest]
        if len(matching) > 1:
            return {**out, "status": "ambiguous_exception",
                    "candidates": [{**self._exception(x), **self._link(x)} for x in matching]}
        if matching:
            chosen, scope = matching[0], {"scope": "exception", "exception": self._exception(matching[0])}
        else:
            chosen = residue["default"]
            scope = {"scope": "default" if exceptions else "only definition"}
        link = self._link(chosen)
        if link["method"] == "near":
            status = "untrusted_link"  # fuzzy suggestion, never an authoritative PARAM code
        elif len(link["param_codes"]) == 1:
            status = "resolved"
        else:
            status = "no_param_link" if not link["param_codes"] else "ambiguous_param"
        return {**out, "status": status, **scope, **link}

    @staticmethod
    def _link(entry: dict) -> dict:
        keys = ("definition", "method", "param_codes", "evidence", "score",
                "catalogue_gap", "components", "qualifier_components", "interpretation_evidence")
        return {k: entry[k] for k in keys if k in entry}

    @staticmethod
    def _exception(entry: dict) -> dict:
        keys = ("commodity_codes", "except_codes", "repairs", "issues")
        return {k: entry[k] for k in keys if entry.get(k)}


def main() -> None:
    args, analysed = sys.argv[1:], None
    if "--analysed" in args:
        i = args.index("--analysed")
        analysed = [c for c in args[i + 1].split(",") if c] if i + 1 < len(args) else []
        args = args[:i] + args[i + 2:]
    if len(args) < 2:
        raise SystemExit(__doc__)
    print(json.dumps(Resolver.load().resolve(args[0], " ".join(args[1:]), analysed),
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
