# Source-grounded interpretation of EU residue definitions

## Source hierarchy

The **legally applicable EU residue definition** establishes which substances,
metabolites or groups belong to the residue. The EU Pesticides Database supplies
the wording used by rd-bridge, with product-specific exceptions in (R) footnotes.
For conflicts, check the applicable EU legal act and the exact commodity scope.

Supporting sources play different roles:

| Source | Role in rd-bridge | Status |
| --- | --- | --- |
| [Regulation (EC) No 396/2005](https://eur-lex.europa.eu/eli/reg/2005/396/oj) and amendments | Defines the legal residue and product scope | Binding legal text |
| [Commission Regulation (EU) 2023/710](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R0710) | Exact source for Chloridazon's (R) animal-product exception | Binding case evidence |
| [OECD, Guidance Document on the Definition of Residue, revised 2009](https://doi.org/10.1787/66ca5caa-en) | Distinguishes residues for MRL enforcement and dietary risk assessment; explains marker compounds, chemical conversions and expression bases (especially scenarios 1–5 and 11) | Supporting principles, **not EU legislation** |
| [EFSA, Chemical monitoring reporting guidance: 2026 data collection](https://doi.org/10.2903/sp.efsa.2026.EN-9911) | Current guidance for SSD2/PARAM reporting, legal-definition codes and parts | Current reporting guidance |
| [EFSA, Reporting data on pesticide residues (2018 data collection, published 2019), §5.5](https://doi.org/10.2903/j.efsa.2019.5655) | Helpful historical examples of P005A (full definition), P004A (subset) and P002A (individual part) | **Obsolete**; not current normative guidance |
| [EFSA PARAM 17.6](https://github.com/openefsa/efsa-catalogues) | Identity and hierarchy of whole residue and component codes | Versioned reference catalogue, not a definition of legal scope |

**Interpret the source first. Map the interpreted whole residue and its actual
parts second.** A PARAM code for a whole definition is not automatically a code
for an independently analysed component. The term after **"expressed as"**
specifies the reporting/calculation basis; it does not, by itself, require the
named substance to be separately measured. This is consistent with OECD's
examples and EFSA's historical reporting examples, but the legally binding
RD wording decides each case.

OECD addresses **how residues are selected and expressed**, not a universal
machine-readable grammar for arbitrary EU text. We therefore do *not* treat
all phrases containing "expressed as" as interchangeable.

## First legally verified correction: Chloridazon

Commission Regulation (EU) 2023/710 explicitly distinguishes:

- **Default RD**: the *sum* of chloridazon and chloridazon-desphenyl, expressed
  as chloridazon. Both components are included. Whole-RD PARAM
  `RF-00005729-PAR`.
- **Animal-product exception** (Annex I `1000000`, except `1040000`):
  Chloridazon (chloridazon-desphenyl, expressed as chloridazon).
  The named measurable component is chloridazon-desphenyl,
  `RF-00006186-PAR`. Chloridazon is the **expression basis**, not a second
  required analyte. Whole-RD PARAM `RF-00005712-PAR`.

The cached Haiku reading incorrectly added the parent as a second analyte for
the exception. `rd_bridge.guidance.apply_verified` now chooses the
independently parsed single metabolite **only when** all four checks match:
the exact EU definition, the EU Annex I scope, the whole-RD PARAM code and the
metabolite's own PARAM code. The resulting entry stores the source link, rule
identifier, reason and expression basis in `interpretation_evidence`.

The resolver also returns that evidence. The default RD is unchanged.
The original Haiku cache is preserved so the change can be audited.

This is **not** a general rewrite of all residues named "X (Y, expressed as
X)". New cases require their own verified source evidence, otherwise the
existing selection is retained and any discrepancy remains reviewable.

## Auditing the original 40 differences

The October 13 baseline is frozen in
[`guidance_baseline_2026-10-13.json`](../reports/guidance_baseline_2026-10-13.json).
[`guidance_audit.json`](../reports/guidance_audit.json) and the
[readable review](../reports/guidance_audit.md) document every item, including
the unchanged model/parser readings and the reasons for categorisation.

| Disposition | Cases | Meaning |
| --- | ---: | --- |
| Legally resolved | 1 | Chloridazon animal exception, legal act linked |
| Explicit naming/alias differences | 6 | EU source uses `aka`, `formerly`, `also called` or an identifier; these are only wording resolutions, **not evidence of chemical equivalence or a PARAM link** |
| Require substantive source review | 33 | No directly supported decision yet |

Of the **33 cases that still require review**, 12 contain differences in
linked component PARAM codes, eight concern component/group scope, nine have
unresolved component identities, and four concern naming or qualifiers with
some matching links. These are **triage categories, not 33 established
mapping errors**. Aliased species with multiple named strains are explicitly
*not* dismissed as mere synonyms.

The live component comparison now has **39** unresolved model-versus-parser
differences; the frozen baseline retains all **40** so a legal correction
cannot silently disappear from the audit denominator.

The independent Sonnet review in
[`sonnet_review.json`](../reports/sonnet_review.json) remains an audit input,
**not a tie-breaking authority**. Two models agreeing may still be wrong
(for example, general AS codes cannot stand in for a legal whole-RD code).

## Use and verification

```bash
python -m rd_bridge.match
python -m rd_bridge.compare_parts
python -m rd_bridge.guidance_audit
python -m unittest discover -s tests -t .
```

The committed `data/parts_comparison.json` is regenerated from the same
mapping and now includes two additional source-backed Chloridazon acceptance
cases: metabolite analysed = covered; parent alone = not covered.

## Guidance is now part of live model interpretation

The earlier `guidance.py` correction was limited to a single verified case.
There is now also an **active, general guidance-aware model reader**:

- [`data/interpretation_guidance.json`](../data/interpretation_guidance.json)
  contains a versioned, citable index of 11 operational principles. The
  paraphrases are grounded in named OECD sections, EU legal definitions and
  reporting rules, with URLs, section/page locators, and a distinction between
  law, guidance and implementation interpretation. These are NOT verbatim
  reproductions of full publications.
- [`rd_bridge/guided_model_parts.py`](../rd_bridge/guided_model_parts.py)
  deterministically retrieves the principles relevant to each definition:
  expressions, sums, common-moiety conversions, named isomers, conjugates,
  commodity exceptions, aliases, and conditional wording. It inserts the
  retrieved principle and its source citation into the **actual LLM request**.
  The response records the guidance rule IDs, source-version hash and the
  current PARAM-family context. The model, not a static example table,
  interprets each new definition.
- The separate `data/guided_model_parts.json` cache is only created when
  guidance-backed results are run. Existing `data/model_parts.json` Haiku
  results are neither overwritten nor invalidated. If the curated guidance
  changes, guided responses must be refreshed or fall back to the existing
  reference; previous answers are not silently relabelled.
- `rd_bridge.match` uses a guided reading when it exists and otherwise the
  legacy cached reading. Both still pass the same deterministic PARAM linking
  and safeguards. Only *verified legal decisions* (such as Chloridazon) can
  apply case-specific authoritative overrides.
- The weekly [EU source refresh](EU_SOURCE_REFRESH.md) and manual
  [Model readings workflow](../.github/workflows/model.yml) now use the guided
  model for **new or changed** definitions. A separate, deliberately initiated
  [full migration workflow](../.github/workflows/full_guided_migration.yml)
  reinterprets **all** existing EU definitions in 16 bounded shards.
  After all existing unit tests, acceptance scenarios and whole-RD PARAM
  consistency checks pass, it creates an evidence PR and merges the complete
  cache automatically. If a regression is found, the proposal remains open
  with the results so the actual issue can be corrected. Previous readings
  remain available for audit and rollback. This migration **does
  not wait for a manually or independently reviewed dataset**, which is not
  available. Routine incremental runs remain capped at 40 calls.

There is **no unsupervised ingestion of arbitrary PDFs** into the model.
This is a compact, provenance-controlled guidance index. OECD 2009
provides most of the actual decomposition semantics. EFSA 2026 EN-9911
is identified as the current reporting manual, not falsely cited as though
specific, unverified sentences had been read from inside it.

### Measured comparison before changing old interpretations

The [12-case gold regression set](../tests/fixtures/rd_guidance_benchmark.json)
lists explicit, independently checkable *analyte names from EU wording*,
plus three additional difficult definitions marked **exploratory**, not
gold. The separate [guidance evaluation](../rd_bridge/guidance_eval.py)
asks the model again WITH the selected guidance and compares the actual
extracted components to previous unguided Haiku responses for the *same*
definitions. It reports every improvement and regression.

```bash
python -m rd_bridge.guidance_eval --limit 15
# New/change-only routine, using ANTHROPIC_API_KEY:
python -m rd_bridge.guided_model_parts --scope new --max-calls 40
# Explicit targeted reading (never automatically promoted):
python -m rd_bridge.guided_model_parts --scope selected --ids 253,301 --max-calls 6 --output reports/experiment.json
```

The evaluation only creates `reports/guidance_model_evaluation.{json,md}`;
it does **not** overwrite the primary map. The model workflow and EU refresh
create review PRs rather than automatically merging changes.
Small preselected tests **cannot establish overall accuracy**. Because no
independently reviewed reference corpus can be obtained, such a corpus is
**not a release gate**. Instead, the complete guidance-based reinterpretation
uses the published EU definition, explicit OECD/EFSA principles, EFSA PARAM
consistency tests, fixed regression examples, and a complete audit of every
changed component. Corrections are incorporated incrementally as evidence
becomes available. A missing external benchmark will never block replacing
the cached model interpretations.

Changes to source evidence, legal wording, commodity scope or EFSA
catalogue version must be checked and tested when rebuilding.
