"""Explain legal-residue/PARAM scope gaps without guessing missing codes.

EFSA PARAM may lag behind legally effective residue definitions. A mismatch
is diagnostic evidence, not permission to use a broader or component code.
"""
from rd_bridge import compounds

BENTHIAVALICARB_2026 = (
    "Benthiavalicarb-isopropyl (sum of benthiavalicarb-isopropyl "
    "(KIF 230 R-L) and its RS enantiomer (KIF 230-S-D))"
)
PREVIOUS_WHOLE = "RF-00004656-PAR"
PARENT_SUBSTANCE = "RF-0043-003-PPP"
LEGAL_SOURCE = "https://eur-lex.europa.eu/eli/reg/2026/147/oj/eng"


def explain(definition: str, matched: dict, param_index) -> dict | None:
    """Annotate this verified mismatch while the catalogue is still incompatible.

    A matching reportable term added in a future PARAM release is linked by
    Matcher first, so the diagnostic is then omitted automatically.
    """
    if param_index is None or matched.get("param_codes") or matched.get("method") not in ("none", "near"):
        return None
    if compounds.norm(definition) != compounds.norm(BENTHIAVALICARB_2026):
        return None
    broad = param_index.terms.get(PREVIOUS_WHOLE)
    component = param_index.terms.get(PARENT_SUBSTANCE)
    if not broad or not component or not broad.get("reportable") or component.get("reportable"):
        return None
    normalized = compounds.norm(broad["name"])
    if not all(isomer in normalized for isomer in ("kif230rl", "kif230sd", "kif230sl", "kif230rd")):
        return None
    if compounds.norm(component["name"]) != compounds.norm("Benthiavalicarb isopropyl"):
        return None
    return {
        "kind": "catalogue_scope_mismatch",
        "legal_source": LEGAL_SOURCE,
        "applies_from": "2026-08-12",
        "param_catalogue_version": param_index.version.get("version"),
        "reason": ("EU Regulation 2026/147 defines the enforcement residue as "
                   "KIF-230 R-L plus KIF-230 S-D. The available reportable "
                   "PARAM term also includes KIF-230 S-L and KIF-230 R-D."),
        "related_terms": [
            {"code": PREVIOUS_WHOLE, "name": broad["name"],
             "relationship": "broader_four_isomer_residue"},
            {"code": PARENT_SUBSTANCE, "name": component["name"],
             "relationship": "nonreportable_individual_substance"},
        ],
        "resolution": ("Use an updated EFSA code for this legal residue definition "
                       "when one exists, or explicit EFSA reporting guidance "
                       "confirming a code. Do not treat either related code "
                       "as an exact whole-definition match."),
    }
