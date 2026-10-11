# 2024 EFSA pesticide-reporting comparison — Sweden and France

**Scope.** Aggregate, reproducible comparison of the current rd-bridge reference
map (snapshot 2026-10-11) to EFSA's publicly released 2024 pesticide-monitoring
data. It measures agreement with what laboratories **reported and EFSA accepted**,
not legal correctness, completeness or MRL compliance.

Run:

```bash
python -m scripts.validate_monitoring --countries SE FR --output reports/monitoring_2024.json
```

The raw reports are downloaded temporarily. Only aggregated counts, source
checksums and a short list of PARAM-code disagreements are saved in the repo.

## Full-definition codes (P005A)

EFSA's [pesticide reporting guidance](https://doi.org/10.2903/j.efsa.2019.5655)
defines `paramType=P005A` as **full legal residue definition analysed**.
This is the proper subset for assessing agreement on a whole-residue code.
`P004A` denotes a sum calculated from only some components, and `P002A`
denotes a separate component of a sum. They are **not** included in this
full-definition rate.

| 2024 country | P005A codes compared | Agreed with current definition | Different | Agreement |
|---|---:|---:|---:|---:|
| Sweden | 43,220 | 43,130 | 90 | 99.79% |
| France | 1,367,110 | 1,366,940 | 170 | 99.99% |
| **Combined** | **1,410,330** | **1,410,070** | **260** | **99.98%** |

These **260 are differences**, not necessarily incorrect mapping. A definition
that applied at the time of collection in 2024 may have been superseded.
The comparison uses the **current** EU definition, so it is *not* a historical
2024 compliance check. See [#25](https://github.com/Chili36/rd-bridge/issues/25)
for metalaxyl, phosmet and other historical cases.

## Every full-definition disagreement (P005A), grouped

The validator now exports the **complete** `full_definition_P005A_disagreements` array
for each country in [the machine-readable report](monitoring_2024.json), not just the
largest all-type discrepancies. All **260 P005A differences** account for
**12 distinct country/substance/code combinations** (6 in Sweden
and 6 in France). The sum of the grouped counts is
checked automatically against the P005A disagreement totals.

| Country | Residue | Reported code | Selected current code | Results |
|---|---|---|---|---:|
| SE | Fluopyram | `RF-1071-001-PPP` | `RF-00000023-PAR` | 15 |
| SE | Flusilazole | `RF-0218-001-PPP` | `RF-0218-002-PPP` | 15 |
| SE | Metalaxyl and metalaxyl-M | `RF-0281-001-PPP` | `RF-00015695-PAR` | 15 |
| SE | Procymidone | `RF-0350-001-PPP` | `RF-1003-001-PPP` | 15 |
| SE | Tebuconazole | `RF-0403-001-PPP` | `RF-00003037-PAR` | 15 |
| SE | Thiophanate-methyl | `RF-0422-001-PPP` | `RF-1002-001-PPP` | 15 |
| FR | Diflubenzuron | `RF-0134-001-PPP` | `RF-0134-002-PPP` | 36 |
| FR | Ethirimol | `RF-0162-001-PPP` | `RF-00005868-PAR` | 36 |
| FR | Procymidone | `RF-0350-001-PPP` | `RF-1003-001-PPP` | 36 |
| FR | Thiophanate-methyl | `RF-0422-001-PPP` | `RF-1002-001-PPP` | 36 |
| FR | Chlorpyrifos-methyl | `RF-00007588-PAR` | `RF-0088-001-PPP` | 13 |
| FR | Clofentezine | `RF-0098-002-PPP` | `RF-0098-001-PPP` | 13 |

These are differences between **2024 accepted reporting** and the code selected
by **today's** residue definition. They are **not** confirmed laboratory errors or
confirmed defects in the mapping. In particular, the metalaxyl animal-product
case must be evaluated against the version of the definition applicable on
the sampling date. Individual investigation remains open in
[issue #25](https://github.com/Chili36/rd-bridge/issues/25).

## Additional recognized PARAM codes

Counts cover every result in the published files, including component analyses.
Unlike the P005A table, they measure **dataset coverage** rather than agreement.

| 2024 country | Reported rows | Not mapped in baseline `d2d1b12` | Not mapped after changes | Newly recognized candidates |
|---|---:|---:|---:|---:|
| Sweden | 393,998 | 98,383 | 44,494 | 53,889 |
| France | 2,164,910 | 245,670 | 105,319 | 140,351 |
| **Combined** | **2,558,908** | **344,053** | **149,813** | **194,240** |

“Newly recognized candidates” includes a small number of **ambiguous**
substance matches, which must not be presented as determined mappings.
Much of the new recognition is due to the separate active-substances source:
48,076 Swedish and 140,351 French results relate to substances whose EU
active-substances record explicitly reports the default MRL rather than a
specific residue definition. Some of these are **P002A** component results.

## Why the naïve comparison gave worse results

If every reported code is incorrectly treated as a complete legal definition,
the result is only 96.82% for Sweden and 98.54% for France. That comparison is
**not a correctness estimate**. In the published files many results have
`paramType=P002A` (“part of a sum”), so it is *expected* that the laboratory's
code differs from the sum code chosen by `resolve(food, substance)`.
For example, an individual captan result is not the same as the sum of
captan and THPI, although both can be correctly reported.

For completeness, the raw P005A/P004A/P002A/N_A type breakdown and the
diagnostic all-type comparisons are recorded in the
[machine-readable report](monitoring_2024.json).

## What exactly was checked

- **Source:** [Sweden 2024, Zenodo 20036095](https://zenodo.org/records/20036095),
  [France 2024, Zenodo 20034822](https://zenodo.org/records/20034822).
  Exact downloaded ZIP sizes and MD5 checksums are in the JSON output.
- **Food:** reconstructed from SSD2 `sampMatCode.base.building` and the
  only facet categories read by the EFSA pesticide mapping rules
  (`F20=partcon`, `F21=prod`, `F27=racsource`), then classified using
  `data/foodex2_ppp.json`.
- **Residue identification:** the reported PARAM code first identifies a
  candidate substance via the reference dataset. Candidates with multiple
  possible residue owners, unknown foods or unresolved definitions are excluded
  from whole-code agreement, with their counts reported.
- **Comparison:** for an unambiguous candidate residue and food, compare
  reported `paramCode.base.param` with the sum PARAM code chosen by the
  current `resolve(food, substance)`.
- **No compliance judgement:** this does not compare analytical concentrations,
  dates of application, MRLs, or whether the analysis truly measured every part.

### Important limitation: non-independent candidate identification

The reported PARAM code is used to identify the candidate residue whose
expected code is then checked against the reported code. The evaluation is
therefore conditional on being able to identify a single candidate from
that same code. This can introduce selection bias: it validates concordance
on judgeable reporting rows, **not standalone lookup accuracy across all
possible substances**. Unjudgeable and unmapped rows are part of the reported
denominator for this reason.

Outstanding: the twelve patterns in the grouped P005A table still require
case-by-case review against definitions in force during 2024; no inference of
mapping errors is warranted merely from disagreement.
