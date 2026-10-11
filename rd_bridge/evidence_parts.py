"""Evidence-backed constituent parts that the current EU residue text does not spell out.

Some current definitions are chemical mixture names (for example "Pyrethrins")
rather than an explicit list of analytes. EFSA's published scientific residue
definition can identify the constituents even when the EU API's short name
does not. PARAM's actual hierarchy is separate evidence, but cannot be used
blindly: e.g. PARAM files Cinerin I and II under the Cinerin branch, not
directly under its term for Pyrethrins.

The curated evidence is deliberately small. It is only applied when both the
whole and all six component identities have been verified against the current
catalogue; failure is loud, not a silent new link. This data is *not* read
from an LLM or inferred from every descendant of a matched whole.
"""
from rd_bridge import compounds

PYRETHRINS = "RF-0374-001-PPP"
EFSA_RESIDUE_REVIEW = "https://doi.org/10.2903/j.efsa.2024.8841"
EU_COMPOSITION = "https://eur-lex.europa.eu/eli/reg_impl/2013/798/oj/eng"
# PARAM codes and names, checked against the saved PARAM 17.6 catalogue.
# The direct Pyrethrins children have PARAM-hierarchy evidence; the two
# Cinerins are not children of the Pyrethrins term and need EFSA evidence.
MEMBERS = (
    ("RF-0374-002-PPP", "Pyrethrin I", "121-21-1"),
    ("RF-0374-003-PPP", "Pyrethrin II", "121-29-9"),
    ("RF-0374-004-PPP", "Jasmolin I", "4466-14-2"),
    ("RF-0374-005-PPP", "Jasmolin II", "1172-63-0"),
    ("RF-1066-002-PPP", "Cinerin I", "25402-06-6"),
    ("RF-1066-003-PPP", "Cinerin II", "121-20-0"),
)


def documented_components(definition: str, link: dict, index) -> list:
    """Return a validated six-part description, or [] if not Pyrethrins.

    A definition's own code remains the whole. Its six components carry
    evidence independent of the EU API's abbreviated wording.
    """
    if compounds.norm(definition) != compounds.norm("Pyrethrins"):
        return []
    if link.get("method") != "exact" or link.get("param_codes") != [PYRETHRINS]:
        return []  # never override a less-than-exact or different definition

    whole = index.terms.get(PYRETHRINS)
    if not whole or compounds.norm(whole["name"]) != compounds.norm("Pyrethrins"):
        raise ValueError("PARAM no longer contains the expected Pyrethrins whole")

    result = []
    for code, name, cas in MEMBERS:
        term = index.terms.get(code)
        if not term or (compounds.norm(term.get("name", "")) != compounds.norm(name)
                        or term.get("cas") != cas or not term.get("reportable")
                        or "COMP" not in term.get("pest_class", [])):
            raise ValueError(f"PARAM pyrethrins component changed: {code} {name}")

        parent = term.get("param_parent")
        direct_child = parent == PYRETHRINS
        if (code.startswith("RF-0374-")) != direct_child:
            raise ValueError(f"Unexpected PARAM hierarchy for {code}: {parent}")
        method = "param_hierarchy" if direct_child else "scientific_definition"
        result.append({
            "text": name, "name": name, "role": "analyte", "method": method,
            "param_codes": [code], "param_names": [term["name"]],
            "evidence": {
                "param_parent": parent,
                "relation": ("direct PARAM child of the whole" if direct_child
                             else "scientific component; not a direct PARAM child"),
                "sources": [
                    {"authority": "EFSA", "title": "EFSA Journal 2024;22:e8841, Table 6",
                     "url": EFSA_RESIDUE_REVIEW},
                    {"authority": "European Commission", "title": "Commission Implementing Regulation (EU) No 798/2013",
                     "url": EU_COMPOSITION},
                ],
            },
        })
    return result
