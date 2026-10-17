"""Link each EU residue definition (default and commodity exceptions) to PARAM codes.

Matching here is deterministic and makes no model calls. Every link records how it was made
(`method`) and, beyond exact text, why (`evidence`). If data/model_parts.json exists (made by
rd_bridge.model_parts), the model's reading of each definition into components is used instead
of the rule parser where it keeps every code the rules link (`parts_from`: model or rules;
`model_reading_lost` lists what a rejected reading would have lost).

Usage: python -m rd_bridge.match [data/residues_en.json] [data/param_pest_terms.json] [data/param_components.json]
Writes data/residue_param_map.json and data/unmatched.json.
"""
import collections
import difflib
import json
import os
import re
import sys

from rd_bridge import catalogue_gaps, components, compounds, evidence_parts, footnotes, guidance, guided_model_parts, model_parts, qualifier_parts

FOOTNOTE_MARKERS = re.compile(r"\s*(\((R|F|A|\+|\+\+|\*|)\)\s*)+$")
NEAR_CUTOFF = 0.9
# "(Where only Y is detected …, the residue definition of Y applies.)" is an alternative rule, not part
# of the summed residue (interpretation guidance EU-CONDITIONAL-CLAUSE); match without it, keep it as evidence.
CONDITIONAL = re.compile(r"\s*(\(\s*where\s+only\b.*\))\s*$", re.I | re.S)
norm = compounds.norm


class Matcher:
    """Try each method in order of trust; the first that finds a PARAM term wins."""

    def __init__(self, terms: list):
        self.names = {t["code"]: t["name"] for t in terms}
        self.index = collections.defaultdict(set)
        self.canon = collections.defaultdict(set)
        self.cas = collections.defaultdict(set)
        self.codes = collections.defaultdict(set)
        self.alias_names = collections.defaultdict(set)
        self.term_cas = {t["code"]: t.get("cas") for t in terms}
        self.signatures = []
        for t in terms:
            self.index[norm(t["name"])].add(t["code"])
            self.canon[compounds.canon(t["name"])].add(t["code"])
            if t.get("cas"):
                self.cas[t["cas"]].add(t["code"])
            for kind, alias in compounds.aliases(t["name"]):
                pool = self.codes if kind == "code" else self.alias_names
                pool[compounds.canon(alias)].add(t["code"])
            head = t["name"].split(" (")[0]
            if compounds.CODE_LIKE.match(head):
                self.codes[compounds.canon(head)].add(t["code"])
            if t.get("pestClass") == "RD":
                self.signatures.append((compounds.signature(t["name"]), t["code"]))
        self.keys = list(self.index)

    def _result(self, method: str, codes: set, **evidence) -> dict:
        codes = sorted(codes)
        out = {"method": method if len(codes) == 1 else "ambiguous", "param_codes": codes}
        if method != "exact":
            out["evidence"] = {"via": method, "matched": [self.names[c] for c in codes], **evidence}
        elif len(codes) > 1:
            out["evidence"] = {"via": method, "matched": [self.names[c] for c in codes]}
        return out

    def link(self, definition: str, head: str) -> dict:
        clause = CONDITIONAL.search(definition)
        if clause:
            out = self.link(definition[:clause.start()], head)
            if out["param_codes"]:
                out.setdefault("evidence", {"via": out["method"]})["conditional_clause"] = clause.group(1)
                return out
        forms = [definition]
        if head and not norm(definition).startswith(norm(head)):
            forms.append(f"{head} ({definition})")

        exact = set().union(*(self.index.get(norm(f), set()) for f in forms))
        if exact:
            return self._result("exact", exact)

        spelled = set().union(*(self.canon.get(compounds.canon(f), set()) for f in forms))
        if spelled:
            return self._result("spelling", spelled)

        for f in forms:
            sig = compounds.signature(f)
            hits = {code for other, code in self.signatures if compounds.compatible(sig, other)}
            if hits:
                return self._result("compound_set", hits, components=sorted(sig[0]), anchor=sig[1])

        by_cas = {n: self.cas[n] for n in compounds.cas_numbers(definition) if self.cas.get(n)}
        if by_cas:
            return self._result("cas", set().union(*by_cas.values()), cas=sorted(by_cas))

        # A CAS written in the definition vetoes any name match to a term with another CAS
        # ("Paraffin oil (CAS 64742-54-7)" is not PARAM's "Paraffin Oil", CAS 64742-55-8).
        stated = set(compounds.cas_numbers(definition))
        # EU-side aliases against PARAM names and PARAM-side aliases; then the definition
        # itself against PARAM-side aliases ("Dimethylaminosulfotoluidide (DMST)").
        candidates = [(kind, alias, [self.codes] if kind == "code" else [self.canon, self.alias_names])
                      for kind, alias in compounds.aliases(definition)]
        candidates += [("param_alias", f, [self.alias_names]) for f in forms]
        # Collect every alias before deciding, so two aliases naming two terms read as ambiguous.
        found, used = set(), []
        for kind, alias, pools in candidates:
            hits = set().union(*(p.get(compounds.canon(alias), set()) for p in pools))
            if stated:
                hits = {c for c in hits if not self.term_cas.get(c) or self.term_cas[c] in stated}
            if hits:
                found |= hits
                used.append({"alias": alias, "kind": kind})
        if found:
            return self._result("alias", found, aliases=used)

        best = max(((difflib.SequenceMatcher(None, norm(f), k).ratio(), k, f)
                    for f in forms for k in difflib.get_close_matches(norm(f), self.keys, n=3,
                                                                      cutoff=NEAR_CUTOFF)),
                   default=None)
        if best:
            score, key, form = best
            codes = self.index[key]
            if any(compounds.same_parent(form, self.names[c]) for c in codes):
                # Same parent, different wording: plausible, still not trusted as-is.
                return {"method": "near", "score": round(score, 3), "param_codes": sorted(codes),
                        "evidence": {"via": "near", "matched": [self.names[c] for c in codes]}}
            # Different parent substance (Ipconazole -> Penconazole): rejected, kept as evidence.
            return {"method": "none", "param_codes": [],
                    "evidence": {"rejected": [self.names[c] for c in codes], "score": round(score, 3),
                                 "reason": "different parent substance"}}
        return {"method": "none", "param_codes": []}


def linked(found: list) -> set:
    return {c for p in found if p["role"] == "analyte" for c in p.get("param_codes", [])}


def build(residues: list, terms: list, parts=None, readings=None) -> list:
    """`parts` (a components.ComponentIndex) adds each definition's components; `readings`
    ({definition: model_parts answer}) are the model's readings of the definitions."""
    matcher = Matcher(terms)
    readings = readings or {}

    def entry(definition: dict, residue_name: str) -> dict:
        if parts is not None:
            text = definition["definition"]
            gap = catalogue_gaps.explain(text, definition, parts)
            if gap:
                definition["catalogue_gap"] = gap
            rules = parts.describe(text, definition, residue_name)
            definition["components"], definition["parts_from"] = rules, "rules"
            qualified = qualifier_parts.covered(text, parts)
            if qualified:
                definition["qualifier_components"] = qualified
            reading = readings.get(text)
            if reading and reading.get("parts"):  # no parts: the model found nothing to measure
                model = parts.describe(text, definition, residue_name, model_parts.as_parts(reading, text))
                # where the rules see one substance, its code stands for the whole; a model reading
                # that lists the components instead loses nothing (benzalkonium chloride -> BAC 8...)
                # - if it links something itself (two unlinked parts instead of a linked whole is a loss)
                # - and never one code for another (fluazifop -> fluazifop-P); the summed code is not
                #   a component link (a part linked to it says nothing a lab could report apart)
                whole = sum(p["role"] in ("analyte", "group") for p in rules) <= 1
                kept = linked(rules) - set(definition.get("param_codes", []))
                if whole and len(linked(model)) > 1:
                    lost = set()
                elif whole and not linked(model):
                    lost = linked(rules)
                else:
                    lost = kept - linked(model)
                if lost:
                    # the model's reading may add links but never lose one the rules made
                    definition["model_reading_lost"] = sorted(lost)
                else:
                    from_guidance = reading.get("prompt_variant") == guided_model_parts.PROMPT_VERSION
                    origin = reading.get("interpretation_source")
                    literal = origin == "exact_EU_literal_fallback"
                    retained = origin == "legacy_retained_after_regression"
                    definition["components"] = model
                    definition["parts_from"] = ("source_literal_fallback" if literal
                                                else "legacy_regression_fallback" if retained
                                                else "guided_model" if from_guidance else "model")
                    if from_guidance:
                        # The same source-backed prompt and validated cache may
                        # contain a targeted Sonnet repair or a clearly marked
                        # retained legacy reading. Never call either original
                        # source-literal or legacy fallback a new model output.
                        definition["model_guidance"] = {
                            "prompt_variant": reading["prompt_variant"],
                            "guidance_ids": reading["guidance_ids"],
                            "guidance_version": reading["guidance_version"],
                        }
                        if reading.get("model_used"):
                            definition["model_guidance"]["model_used"] = reading["model_used"]
                        if origin:
                            definition["model_guidance"]["interpretation_source"] = origin
                        if literal or retained or reading.get("requires_followup"):
                            definition["model_guidance"]["requires_followup"] = True
            # For a named chemical mixture, published EFSA constituent evidence
            # can be stronger than the short EU API text and model's one-part reading.
            # Only explicit, catalogue-verified cases are overridden.
            documented = evidence_parts.documented_components(text, definition, parts)
            if documented:
                definition["components"], definition["parts_from"] = documented, "published_evidence"
            # Legislation-backed case rules override a contradictory cached model
            # reading only when the exact EU text, exception scope, PARAM code
            # and independently parsed components all match. Never let two LLMs
            # vote an extra analyte into the legal residue definition.
            verified = guidance.apply_verified(definition, rules, residue_name)
            if verified:
                definition.update(verified)
        return definition

    by_id = collections.defaultdict(list)
    for r in residues:
        by_id[r["pesticide_residue_id"]].append(r)
    superseded = {int(r["original_pesticide_residue_id"]) for r in residues
                  if r.get("original_pesticide_residue_id")}
    rows = []
    for rid, entries in sorted(by_id.items()):
        if rid in superseded:
            continue
        first = entries[0]
        name = FOOTNOTE_MARKERS.sub("", first["pesticide_residue_name"]).strip()
        head = re.split(r"\s*\(", name)[0].strip()
        footnote = next((e["pesticide_residue_footnote_txt"] for e in entries
                         if e.get("pesticide_residue_footnote_code") == "(R)"), None)
        rows.append({
            "residue_id": rid,
            "version": first.get("pesticide_residue_version_nbr"),
            "name": first["pesticide_residue_name"],
            "default": entry({"definition": name, **matcher.link(name, head)}, first["pesticide_residue_name"]),
            "exceptions": [entry({**x, **matcher.link(x["definition"], head)}, first["pesticide_residue_name"])
                           for x in footnotes.parse(footnote)],
            "footnote_r": footnote,
        })
    return rows


def main() -> None:
    res_path = sys.argv[1] if len(sys.argv) > 1 else "data/residues_en.json"
    term_path = sys.argv[2] if len(sys.argv) > 2 else "data/param_pest_terms.json"
    with open(res_path, encoding="utf-8") as fh:
        residues = json.load(fh)
    with open(term_path, encoding="utf-8") as fh:
        terms = json.load(fh)
    comp_path = sys.argv[3] if len(sys.argv) > 3 else "data/param_components.json"
    parts = components.ComponentIndex.load(comp_path) if os.path.exists(comp_path) else None
    readings = model_parts.load() if parts is not None else {}
    if parts is not None:
        # New/changed definitions can be read with a versioned evidence-backed
        # prompt. Old Haiku cache stays intact; only independently cached guided
        # readings supersede entries with the same exact EU definition.
        readings.update(guided_model_parts.load())
    rows = build(residues, terms, parts, readings)
    links = [r["default"] for r in rows] + [x for r in rows for x in r["exceptions"]]
    unmatched = [{"residue_id": r["residue_id"], "definition": d["definition"], "method": d["method"],
                  **({"reason": d["catalogue_gap"]["kind"]} if "catalogue_gap" in d else {})}
                 for r in rows for d in [r["default"], *r["exceptions"]] if d["method"] != "exact"]
    with open("data/residue_param_map.json", "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)
    with open("data/unmatched.json", "w", encoding="utf-8") as fh:
        json.dump(unmatched, fh, ensure_ascii=False, indent=1)
    counts = collections.Counter(l["method"] for l in links)
    print(f"{len(rows)} residues, {sum(bool(r['exceptions']) for r in rows)} with exceptions, "
          f"{len(links)} definitions: {dict(counts)}")
    if parts is not None:
        needed = [[p for p in l["components"] if p["role"] in ("analyte", "group")] for l in links]
        multi = [n for n in needed if len(n) > 1]
        full = sum(all(p["role"] == "analyte" and p["param_codes"] for p in n) for n in multi)
        found = collections.Counter(p.get("method", "group") for n in needed for p in n)
        print(f"components (PARAM {parts.version.get('version')}): {len(multi)} multi-part definitions, "
              f"{full} with every part linked; parts by method: {dict(found)}; "
              f"read by model: {sum(l['parts_from'] == 'model' for l in links)}/{len(links)}, "
              f"model reading not used (would lose links): {sum('model_reading_lost' in l for l in links)}")


if __name__ == "__main__":
    main()
