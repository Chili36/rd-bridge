"""Conservatively identify PARAM components covered by an EU qualifier.

A definition may say "its esters", "its salts", or "its conjugates" without
naming individual substances. When PARAM explicitly names a form of the same
parent, record a *candidate covered component* with its code and the qualifier
that supports the relation. These are not exhaustive and are not individually
required to claim that the whole residue was analysed.

Only approved, reportable COMPONENT terms are eligible. This intentionally does
not infer chemical structures from arbitrary names or follow an obsolete summed
PARAM term as if it were the current EU residue definition.
"""
import re

from rd_bridge import components, compounds

# Whole-token chemical form labels. In particular, -P- by itself is not an ester.
ESTER = re.compile(
    r"^(?:[PRS]-)?(?:methyl|ethyl|propyl|isopropyl|butyl|"
    r"isobutyl|sec-butyl|tert-butyl|pentyl|amyl|hexyl|heptyl|octyl|"
    r"2-ethylhexyl|decyl|thioethyl)(?: ester)?$", re.I)
SALT = re.compile(
    r"^(?:sodium|potassium|ammonium|calcium|magnesium|lithium|"
    r"dimethylammonium|triethylammonium|isopropylammonium|"
    r"diethanolamine|triethanolamine|choline)(?: salt)?$", re.I)
CONJUGATE = re.compile(
    r"^(?:o-|n-)?(?:sulfate|sulphate|phosphate|glucoside|"
    r"glucuronide|glycoside)(?: conjugate)?$|^.+ conjugate$", re.I)
KINDS = {"esters": ESTER, "salts": SALT, "conjugates": CONJUGATE}


def covered(definition: str, index: components.ComponentIndex) -> list:
    """PARAM-only named forms covered by a specific qualifier (not an exhaustive list)."""
    anchor, parsed = components.parts(definition)
    if not anchor:
        return []

    # Use the rule-parser's qualifiers even if an optional model reading was used
    # for named components. No model can invent or remove a legal qualifier.
    qualifiers = []
    for part in parsed:
        if part["role"] != "qualifier":
            continue
        text = part["text"].lower()
        for kind in KINDS:
            if re.search(r"\b" + kind[:-1] + r"s?\b", text):
                qualifiers.append(kind)
    kinds = set(qualifiers)
    if not kinds:
        return []

    # Name evidence must identify the same anchor, not merely have a similar
    # substring ("bromophos" must not match "bromophos-ethyl" as its parent).
    # Stereoisomer prefixes P/R/S are allowed before an ester suffix.
    prefix = re.compile(r"^" + re.escape(anchor) + r"[- ](.+)$", re.I)
    results = []
    for code, term in sorted(index.terms.items()):
        if not term.get("reportable") or "COMP" not in term.get("pest_class", []):
            continue
        match = prefix.match(term["name"])
        if not match:
            continue
        form = match.group(1)
        for kind in ("esters", "salts", "conjugates"):
            if kind in kinds and KINDS[kind].fullmatch(form):
                results.append({
                    "name": term["name"], "role": "analyte", "method": "qualifier",
                    "qualifier": kind, "param_codes": [code],
                    "evidence": {"anchor": anchor, "term": term["name"],
                                 "basis": "named PARAM COMPONENT matching EU qualifier"},
                })
                break
    return results
