# Building the rd-bridge reference

This page documents the mechanics behind [the reference dataset](../data/residue_param_map.json).
For the project purpose and the separation of residue definitions from FoodEx2, start with
[README](../README.md).

## The two sources joined by rd-bridge

**European Commission — residue definitions.** The EU Pesticides Database `pesticide-residues`
API supplies the current wording and versions of pesticide residue definitions. A residue
record has a default definition. Where an `(R)` footnote specifies a different definition
for products or product groups, rd-bridge parses those EU **Annex I commodity codes** and
any exclusions into `exceptions`. This is product scope *inside the reference data*;
FoodEx2 has no role in creating it.

**EFSA — PARAM catalogue.** EFSA's PARAM terms and hierarchies supply codes for complete
residue definitions and their constituent analytes. A legal residue-definition text
does not itself tell us which EFSA PARAM term represents that definition.
`rd_bridge.match` connects the two sources and records the evidence of each link.

The resulting `data/residue_param_map.json` is the primary output. Its structure is
one current EU residue record with `default`, `exceptions`, original `footnote_r`,
source `version`, whole-definition `param_codes` and available `components`.
Exception entries state the Annex I `commodity_codes` and `except_codes` to which
their definition applies.

## Linking a whole residue definition to PARAM

`rd_bridge.match.Matcher` attempts the following evidence in order. Links are
not forced: an ambiguous or missing link is left visibly unresolved.

| Method | Meaning |
|---|---|
| `exact` | Normalised EU and PARAM definition text is the same |
| `spelling` | Equal after a controlled table of spelling differences |
| `compound_set` | Same constituent set and same anchor substance |
| `cas` | CAS number explicitly stated in the source matches |
| `alias` | An explicit synonym, identifier or alias matches |
| `ambiguous` | Multiple possible PARAM candidates |
| `near` | Similarity ≥0.9 **and** same parent substance: untrusted suggestion |
| `none` | No supported link; do not substitute a fuzzy unrelated match |

Whole-definition `param_codes` describe the *sum/whole*, not necessarily
the code of every chemical that a laboratory might measure separately.

## Interpreting and linking the parts

A definition can name substances, groups or qualifiers. Each element in
`components` is tagged with its role and an evidence method. Typical methods:

| Method | Meaning |
|---|---|
| `param_sum` | PARAM term is filed below the definition's own summed term |
| `family` | Name/code found in the corresponding pesticide family |
| `global` | Full name found elsewhere among pesticide terms |
| `global_code` | Unique identifier found outside the family |
| `definition` | Single-substance definition uses its own code |
| `model` | Optional model suggested a family term when rules found nothing |
| `param_hierarchy` | Published constituent also appears directly under the whole in PARAM |
| `scientific_definition` | Published EFSA/EC evidence establishes a constituent not a direct child in PARAM |
| `none` | No defensible component code |

For **Pyrethrins**, the current EU definition is simply “Pyrethrins”. The
documented six parts are pyrethrin I/II, jasmolin I/II and cinerin I/II.
The four pyrethrin/jasmolin terms are direct children of Pyrethrins in PARAM;
the cinerins are in their own branch, so their relationship is recorded as
`scientific_definition` with [published supporting evidence](../rd_bridge/evidence_parts.py).
The exact PARAM term identities are checked at build time.

Generic qualifiers such as “its esters”, “its salts” and “its conjugates” are
**not** necessarily enumerated in the legal text. Where a named, reportable
PARAM form is identifiable, it is listed separately in `qualifier_components`
with method `qualifier` and the reason for the link. That list is not exhaustive,
and does not silently become a list of required individual analyses.

### Optional model readings

The normal parser splits a definition into analytes, groups and qualifiers.
`rd_bridge.model_parts` can optionally read definitions with a model and cache
its readings in `data/model_parts.json`. The deterministic PARAM linker then
maps the interpreted names, not the model on its own. Readings are accepted
only when they preserve rule-linked evidence and satisfy the text-grounding
checks; rejections are visible in the data. The cached model results are an
input to rebuilding the dataset, not a runtime dependency of the FoodEx2
lookup. `rd_bridge.compare_parts` reports disagreements with the parser and
tests the accepted examples.

## FoodEx2 is a separate use of the reference

**The EU product/commodity scope above is already complete without FoodEx2.**

A laboratory may report a sampled food with a FoodEx2 `sampMatCode`.
`rd_bridge.commodity` applies EFSA's food-class mapping rules to identify an
EU Annex I commodity. **Only then** can `rd_bridge.resolve` select a default
or exceptional residue definition using its stored Annex I scope, and return
the mapped PARAM code for the **whole** definition. For example:

```text
FoodEx2: A02LV (cow milk)
    -> Annex I: 1020010 (under group 1020000)
    -> thiabendazole's milk-specific residue definition
    -> whole PARAM: RF-00007630-PAR
```

The FoodEx2 mapping is a port of EFSA's food-class algorithm, based on the
published rules and hierarchy extract in `data/foodex2_ppp.json`. Some
composite/processed foods are outside Annex I scope. If a product cannot
be reliably classified and a substance has commodity exceptions, the
resolver returns candidates with `commodity_unresolved` instead of guessing.
If there are no exceptions, a FoodEx2 conversion is unnecessary to know
the single current definition.

## Optional completeness check

`python -m rd_bridge.resolve <sampMatCode> <substance> --analysed CODE,CODE`
compares supplied PARAM codes with the identifiable parts and/or whole-residue
code in the chosen definition. Outputs may be `complete`, `partial`,
`undetermined` or `not_covered`. The comparison does **not** establish
laboratory method suitability or chemical/legal compliance, and generic
qualifiers are not treated as exhaustive sets of required analytes.

## Build, regenerate and test

```bash
python -m rd_bridge.fetch_residues           # EU definition source snapshot
python -m rd_bridge.fetch_active_substances  # additional active-substances source
python -m rd_bridge.fetch_param               # EFSA PARAM catalogue extract
python -m rd_bridge.model_parts               # optional; requires ANTHROPIC_API_KEY
python -m rd_bridge.match                     # primary reference JSON
python -m rd_bridge.compare_parts             # comparison of optional model readings
python -m unittest discover -s tests -t .     # offline unit tests
python -m scripts.portable_validation --countries SE FR  # public 2024 Zenodo validation
```

`rd_bridge.foodex2_mapping` can independently regenerate the FoodEx2 food-class
extract from EFSA's Zenodo package (requires pandas to read SAS-related data).
It is **not** required to regenerate EU residue-definition → PARAM links.

The committed reference describes only the **current** definitions, not those
in effect on historical sampling dates. Updating source data is currently
manual. For measured comparison with accepted 2024 reporting and known
methodological limitations, see [the SE/FR validation report](../reports/monitoring_2024.md).
The separately collected active-substances index can indicate
`no_residue_definition` where the EU API explicitly gives the default MRL;
it never supplies an invented specific residue definition.

## Sources and attribution

The EU Pesticides Database supplies the definitions, EFSA PARAM supplies
chemical/reporting codes, and EFSA FoodEx2 mapping is the optional food
classification stage. Their datasets retain their own reuse conditions;
see [DATA_SOURCES](../DATA_SOURCES.md). This project is not an official
EU or EFSA publication and does not make legal compliance determinations.
