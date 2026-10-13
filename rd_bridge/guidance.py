"""Versioned, source-grounded rules for reading EU residue definitions.

This module is deliberately *not* a second LLM. The legal EU definition is the
authority for which components are included. OECD describes how residue
definitions are established; EFSA reporting guidance explains the distinct
whole-RD, partial-RD and component reporting cases.

Only a directly verified, exact source-text case is automatically corrected.
Unverified generalisations and model agreement are *never* enough to replace
components silently. See docs/INTERPRETATION_GUIDANCE.md.
"""
from copy import deepcopy
import re

from rd_bridge import compounds

SOURCES = {
    "eu_chloridazon_2023_710": {
        "title": "Commission Regulation (EU) 2023/710, Annex V, chloridazon (R) footnote",
        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R0710",
        "role": "binding EU definition and commodity exception",
    },
    "efsa_chemmon_2026": {
        "title": "EFSA Chemical monitoring reporting guidance: 2026 data collection",
        "url": "https://doi.org/10.2903/sp.efsa.2026.EN-9911",
        "role": "current SSD2/PARAM reporting guidance; not a grammar for every RD",
    },
    "oecd_dor_2009": {
        "title": "OECD Guidance Document on the Definition of Residue (2009)",
        "url": "https://doi.org/10.1787/66ca5caa-en",
        "role": "principles and examples for enforcement/risk-assessment definitions",
    },
    "efsa_reporting_2019_historical": {
        "title": "EFSA 2019 pesticide-residue reporting guidance, section 5.5, examples 14-16",
        "url": "https://doi.org/10.2903/j.efsa.2019.5655",
        "role": "historic P005A/P004A/P002A illustrations; document is obsolete",
    },
}

# Case-specific evidence. This avoids declaring the OECD document a legal
# grammar, or extrapolating an EU annex to an unverified substance.
VERIFIED_INTERPRETATIONS = {
    "Chloridazon (chloridazon-desphenyl, expressed as chloridazon)": {
        "rule_id": "EU-2023-710-CHLORIDAZON-R",
        "meaning": "The animal-product exception names only chloridazon-desphenyl; "
                   "chloridazon is the expression basis, not a second analyte.",
        "source_ids": ["eu_chloridazon_2023_710", "oecd_dor_2009"],
        "expected_component": "chloridazon-desphenyl",
        "expected_component_code": "RF-00006186-PAR",
        "expected_whole_code": "RF-00005712-PAR",
        "excluded_heading": "chloridazon",
        "commodity_codes": ["1000000"],
        "except_codes": ["1040000"],
    }
}

# A *candidate*, not an automatic rule. We only use this form after checking
# the relevant EU source and the actual component PARAM term.
EXPRESSION_SHAPE = re.compile(
    r"^(?P<heading>[^():]{2,90})\s+\("
    r"(?P<body>[^(),]+),\s*expressed as\s+(?P<basis>[^(),]+)\)$",
    re.IGNORECASE,
)
ALIAS_MARKER = re.compile(
    r"\((?:aka|also called|formerly|former|CAS\s+\d{2,}-\d{2}-\d)\b",
    re.IGNORECASE,
)


def expression_candidate(text: str) -> dict | None:
    """Find a possible X (Y, expressed as X) pattern; never resolve it alone."""
    match = EXPRESSION_SHAPE.fullmatch(text.strip())
    if not match:
        return None
    heading, body, basis = (match.group(x).strip() for x in ("heading", "body", "basis"))
    if compounds.canon(heading) != compounds.canon(basis):
        return None
    if compounds.canon(body) == compounds.canon(heading):
        return None
    if re.search(r"\b(?:sum|and|including|mixture|all\s+metabolites)\b", body, re.I):
        return None
    return {"heading": heading, "component": body, "expression_basis": basis}


def lexical_alias_candidate(text: str) -> bool:
    """Flag alias-style wording, without deciding the underlying chemistry."""
    return bool(ALIAS_MARKER.search(text))


def apply_verified(entry: dict, rules: list, residue_name: str) -> dict | None:
    """Return a verified override (not a mutation), or None.

    The full RD code, component code, syntactic scope and commodity exception
    must *all* match the legal evidence. Never apply to a sum, a default RD,
    or another chemical by analogy.
    """
    evidence = VERIFIED_INTERPRETATIONS.get(entry["definition"])
    if evidence is None:
        return None
    shape = expression_candidate(entry["definition"])
    if (shape is None
            or compounds.canon(shape["component"]) != compounds.canon(evidence["expected_component"])
            or compounds.canon(shape["heading"]) != compounds.canon(evidence["excluded_heading"])
            or entry.get("param_codes") != [evidence["expected_whole_code"]]
            or entry.get("method") != "exact"
            or entry.get("commodity_codes") != evidence["commodity_codes"]
            or entry.get("except_codes") != evidence["except_codes"]):
        return None
    measured = [p for p in rules if p["role"] in ("analyte", "group")]
    if (len(measured) != 1 or measured[0]["role"] != "analyte"
            or compounds.canon(measured[0]["name"]) != compounds.canon(evidence["expected_component"])
            or measured[0].get("param_codes") != [evidence["expected_component_code"]]):
        return None
    return {
        "components": deepcopy(rules),
        "parts_from": "legal_guidance",
        "interpretation_evidence": {
            "rule_id": evidence["rule_id"],
            "reason": evidence["meaning"],
            "source": [SOURCES[s] for s in evidence["source_ids"]],
            "expression_basis": shape["expression_basis"],
            "measurement_component": shape["component"],
        },
    }
