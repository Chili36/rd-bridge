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
| `model` | The rules found no link; the model chose this PARAM term from a shortlist (see below) |
| `none` | No supported link, and the model found no candidate for the same substance |

Before these methods, a trailing conditional clause such as Dinocap's "(Where only
meptyldinocap … is detected …, the residue definition of meptyldinocap is to be applied.)"
is set aside: it is an alternative rule, not part of the summed residue (guidance
`EU-CONDITIONAL-CLAUSE`). The definition is matched without it and the clause is kept as
`evidence.conditional_clause`. Former names in "(formerly …)" are treated like "aka" aliases,
and PARAM element names written with their symbol ("Sulfur (S)") also match the plain name.

### Model guesses for what the rules cannot link

The rules above link only on hard evidence, so many definitions with an obvious PARAM term under
other wording stay unlinked ("Chlorate" / "Chlorates", "Indolylacetic acid" /
"indole-3-acetic acid", PARAM names cut off at their field length). `rd_bridge.model_match`
shortlists the 20 most similar PARAM pesticide terms for each such definition and asks
Claude Sonnet 5.5 for the term a data reporter would use, or none when no candidate is the same
substance (another chemical, another microorganism strain, another CAS number, parent versus
metabolite). Answers are cached in `data/model_matches.json` for one model and prompt;
`rd_bridge.match` applies them as `method: "model"` with the model's confidence and reason in
`evidence`, and records a refusal as `model_guess`. Rule links are never replaced, and a verified
`catalogue_gap` keeps its legal decision. The weekly EU refresh asks only for new or changed
definitions (at most 40 calls).

Whole-definition `param_codes` describe the *sum/whole*, not necessarily
the code of every chemical that a laboratory might measure separately.

### When legislation changes before PARAM

[Benthiavalicarb-isopropyl under Regulation (EU) 2026/147](https://eur-lex.europa.eu/eli/reg/2026/147/oj/eng)
is a real gap, not a spelling error. From **12 August 2026**, its EU
enforcement definition covers **KIF-230 R-L + KIF-230 S-D**. EFSA PARAM
**17.8** still has reportable `RF-00004656-PAR`, which also includes
diastereomers KIF-230 S-L and KIF-230 R-D. `RF-0043-003-PPP` identifies
the individual substance; in the pesticide hierarchy it is not a reportable
whole-residue term. Neither is verified as the exact new legal definition.

Record **3950** therefore has `method = "none"`, `param_codes = []`
and a structured `catalogue_gap` with the relevant terms, source regulation
and application date. The `resolve` response exposes this explanation with
`status = "no_param_link"`. Matching continues automatically when a
later PARAM catalogue supplies a valid new term or revises the old one;
no manually reviewed reference corpus or forced substitution is required.


## Interpreting and linking the parts

The [source-grounded interpretation hierarchy](INTERPRETATION_GUIDANCE.md) distinguishes binding EU wording, OECD principles for defining residues, EFSA's **2026** reporting guidance and the versioned PARAM catalogue. Source-backed cases can override a contradictory model interpretation only with recorded legal evidence and regression tests. The original cached model reading is retained for audit.

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

### Guidance-backed model readings

The normal parser splits a definition into analytes, groups and qualifiers.
The previously generated baseline model readings remain cached in
`data/model_parts.json` for rollback. **All current definitions are migrated
to the guidance-backed model in a one-time, sharded workflow**, and new or
changed definitions are thereafter interpreted by
[`rd_bridge.guided_model_parts`](../rd_bridge/guided_model_parts.py),
which selects and supplies source-located OECD, EU and EFSA principles from
[`interpretation_guidance.json`](../data/interpretation_guidance.json)
in the *actual* model prompt. Guided answers are stored in a separate
versioned `data/guided_model_parts.json` cache and replace legacy answers
only when reviewed and included in an accepted PR.

The deterministic PARAM linker still maps the names, not the model on its
own. All readings must retain rule-linked evidence and pass text grounding;
the source documents included in a prompt are provenance, **not a guarantee
of a correct interpretation**. `rd_bridge.compare_parts` reports
model-versus-rule disagreements and tests known acceptance examples.
The model cache is a build input, not a FoodEx2 runtime dependency.

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
python -m rd_bridge.guided_model_parts --scope new --max-calls 40  # guidance-backed new/changed RD
python -m rd_bridge.guidance_eval --limit 15    # bounded real-model A/B review only
python -m rd_bridge.model_parts               # legacy reader; existing cache is retained
python -m rd_bridge.match                     # primary reference JSON
python -m rd_bridge.compare_parts             # current component comparison + acceptance
python -m rd_bridge.guidance_audit            # source-based audit of the frozen 40 disagreements
python -m unittest discover -s tests -t .     # offline unit tests
python -m scripts.portable_validation --countries SE FR  # public 2024 Zenodo validation
```

`rd_bridge.foodex2_mapping` can independently regenerate the FoodEx2 food-class
extract from EFSA's Zenodo package (requires pandas to read SAS-related data).
It is **not** required to regenerate EU residue-definition → PARAM links.

The committed reference uses the **latest EU-published** definitions by default,
presuming they apply unless specific evidence establishes otherwise. It does not
resolve which historical RD applied on a sampling date. The
[EU reference update workflow](EU_SOURCE_REFRESH.md) refreshes sources weekly
and proposes changes through a pull request. For measured comparison with
accepted 2024 reporting and known methodological limitations, see
[the SE/FR validation report](../reports/monitoring_2024.md).
The separately collected active-substances index can indicate
`no_residue_definition` where the EU API explicitly gives the default MRL;
it never supplies an invented specific residue definition.

## Sources and attribution

The EU Pesticides Database supplies the definitions, EFSA PARAM supplies
chemical/reporting codes, and EFSA FoodEx2 mapping is the optional food
classification stage. Their datasets retain their own reuse conditions;
see [DATA_SOURCES](../DATA_SOURCES.md). This project is not an official
EU or EFSA publication and does not make legal compliance determinations.
