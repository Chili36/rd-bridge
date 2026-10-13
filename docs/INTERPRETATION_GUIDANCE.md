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

The cached `model_parts.SYSTEM` prompt already tells Haiku not to
automatically add the heading as an analyte. We have not changed the prompt
hash or silently invalidated hundreds of previously cached readings.
Versioned, source-grounded post-interpretation checks correct known cases
without adding new model costs. A future prompt revision must be evaluated
separately before regenerating the complete cache.

Changes to source evidence, legal wording, commodity scope or EFSA
catalogue version must be checked and tested when rebuilding.
