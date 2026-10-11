# rd-bridge — findings and public-release review
_Reviewed 2026-10-11. Scope: repository `Chili36/rd-bridge`, current-definition reference snapshot and 2024 reporting validation._

## What the project publishes

The primary product is [`data/residue_param_map.json`](../data/residue_param_map.json): a reference map of current EU pesticide residue definitions, the PARAM code of the whole definition, its identifiable parts and their PARAM codes, and commodity-specific `(R)` exceptions. `resolve(food, substance)` is one downstream use. `completeness` is an **optional diagnostic**, not a claim of legal compliance or analytical completeness for every possible chemical form.

The snapshot has **684 current residue records**, **77 with commodity exceptions**, and **767 default/exception definitions**. Whole-definition matching is **601 exact (78% of 767)** and **625 by any deterministic method (81%)**; **6 near suggestions** remain untrusted and **136 definitions** have no PARAM link. These figures are about *whole-definition links*, not a proven end-to-end correctness rate. Some unmatched entries are biologicals or basic substances without a corresponding reportable PARAM term.

## Changes made before publication

| Work | Result and evidence | Merged PR |
|---|---|---|
| Product positioning | README now begins with the reference dataset and an actual acetamiprid JSON entry; resolver is explicitly secondary. | [#28](https://github.com/Chili36/rd-bridge/pull/28), [#33](https://github.com/Chili36/rd-bridge/pull/33) |
| General qualifiers | `qualifier_components` records named, reportable PARAM derivatives supported by “its esters”, “its salts” or “its conjugates”; method `qualifier`. Nine links were added across five definitions, including fluazifop-P-butyl (`RF-0197-002-PPP`) and glufosinate-ammonium (`RF-0231-001-PPP`). This is deliberately **not exhaustive**. | [#29](https://github.com/Chili36/rd-bridge/pull/29) |
| EU-known substances with no current residue definition | A second source, `data/active_substances.json`, retains relevant fields from the EU active-substances API. 4,789 input records yielded **1,532 distinct source records** after removal of exact duplicates; different linked definitions are retained. `resolve` returns `no_residue_definition` *only* when the source explicitly identifies the default MRL, not just because a name is missing. For example, azamethiphos, etrimfos, dichlofluanid and bromophos now carry an exact PARAM code and the source's approval/default-MRL metadata. | [#30](https://github.com/Chili36/rd-bridge/pull/30) |
| PARAM-only pyrethrin constituents | All six constituent chemicals are listed under “Pyrethrins” (`RF-0374-001-PPP`). Pyrethrin I/II and Jasmolin I/II have `param_hierarchy` evidence. Cinerin I/II are **not** descendants of the Pyrethrins PARAM term, so they are marked `scientific_definition` and linked to independent published evidence. PARAM names and CAS identifiers are checked when rebuilding. | [#31](https://github.com/Chili36/rd-bridge/pull/31) |
| License, provenance, security | Original software under [MIT](../LICENSE); third-party EC/EFSA source material and reuse boundaries are documented in [DATA_SOURCES.md](../DATA_SOURCES.md). CI runs unit tests and a Gitleaks full-history scan. | [#32](https://github.com/Chili36/rd-bridge/pull/32) |
| Reproducible 2024 comparison | [Method and counts](monitoring_2024.md), [machine-readable aggregates](monitoring_2024.json), and [validation script](../scripts/validate_monitoring.py) committed. The raw Member State reporting datasets are **not committed**. | [#34](https://github.com/Chili36/rd-bridge/pull/34) |

Pyrethrin evidence: [EFSA Journal 2024, section 5.1/Table 6](https://doi.org/10.2903/j.efsa.2024.8841) compares current published residue definitions and identifies all six constituents; [Commission Implementing Regulation (EU) No 798/2013](https://eur-lex.europa.eu/eli/reg_impl/2013/798/oj/eng) lists their names and CAS numbers. The **EU Pesticides Database entry is simply “Pyrethrins”**; the detailed six-part expansion is therefore transparently labelled as additional published evidence, not invented EU source wording. EFSA's underlying peer-review definition is provisional, so do not present this as a definitive list for every imaginable chemical analysis.

## Validation against EFSA's accepted 2024 reporting

Original records: [Sweden, Zenodo 20036095](https://zenodo.org/records/20036095) and [France, Zenodo 20034822](https://zenodo.org/records/20034822). The source archive sizes/checksums, precise definitions, inclusion rules and output counts are archived in [`monitoring_2024.json`](monitoring_2024.json). Re-run:

```bash
python -m scripts.validate_monitoring --countries SE FR --output reports/monitoring_2024.json
```

| Measurement | Sweden | France | Total |
|---|---:|---:|---:|
| All reported results | 393,998 | 2,164,910 | 2,558,908 |
| Unrecognized in original `d2d1b12` map | 98,383 | 245,670 | 344,053 |
| Unrecognized after extensions | 44,494 | 105,319 | 149,813 |
| Newly recognized candidates | 53,889 | 140,351 | 194,240 |
| **Judgeable full-definition `P005A` results** | **43,220** | **1,367,110** | **1,410,330** |
| `P005A` agreements with current definition | 43,130 | 1,366,940 | 1,410,070 |
| `P005A` disagreements | 90 | 170 | 260 |
| **Conditional `P005A` agreement** | **99.79%** | **99.99%** | **99.98%** |

### Interpretation and limitations

1. **This is concordance with accepted reporting, not measured mapping accuracy.** The reported PARAM code is itself used to find the candidate residue, which creates a non-independent selection step. Ambiguous, unmapped and unjudgeable rows must remain visible in the denominator.
2. **Only `paramType=P005A` is treated as a report of the complete legal residue definition.** `P002A` means an individual part and `P004A` a partial sum. Treating them all as complete definitions incorrectly produced 96.82% agreement for Sweden and 98.54% for France in an earlier diagnostic run.
3. **The 194,240 additional recognitions are candidates, not 194,240 demonstrated fixes.** The new active-substances source accounts for 48,076 Swedish and 140,351 French recognitions as no-specific-residue-definition cases; some records have ambiguous possible matches. Recognition is not a compliance judgment.
4. **The 260 `P005A` disagreements are not automatically bugs.** They group into **12 country/substance/PARAM-code patterns**, six from each country; all 260 records are accounted for in the complete [grouped discrepancy register](monitoring_2024.md#every-full-definition-disagreement-p005a-grouped) and the `full_definition_P005A_disagreements` JSON field, with an invariant checking the totals. The cases may involve a 2024-applicable definition, a current commodity exception, or a genuinely incorrect link/report. [Issue #25](https://github.com/Chili36/rd-bridge/issues/25) covers sampling-date semantics. They still need case-by-case source review before declaring a mapping error.
5. **No concentration, MRL compliance, historical sampling-date eligibility, or laboratory analytical coverage was evaluated.** Some foods lie outside the supported Annex I commodity interpretation, and those results cannot be compared with an unqualified `resolve` answer.

## Public-history and security review

A Gitleaks scan of **125 reachable commits** on 2026-10-11 passed with **no detected secrets**, and the tracked-file audit did not identify obvious credential filenames. See the [CI security workflow](../.github/workflows/security.yml). This is a scanner result, **not a guarantee** that no sensitive data has ever been committed.

**Visibility warning:** that same audit found **48 historical Claude session URLs** in commit messages and **three distinct commit-author email addresses**. Publishing the repository exposes its reachable commit history and these metadata to others. Decide explicitly whether that exposure is acceptable. If it is not, remove/sanitize sensitive metadata in a coordinated history-rewrite before switching visibility; deleting lines from the current README does **not** remove them from prior commits. History rewrites affect SHAs and other branches/clones. The repo is still **private** while this decision is unresolved; the explicit decision and acceptance criteria are tracked in [issue #35](https://github.com/Chili36/rd-bridge/issues/35).

The [MIT software license](../LICENSE) does not override the EC/EFSA upstream rights and citation obligations of the JSON source data; reuse, attributions and non-endorsement are described in [DATA_SOURCES.md](../DATA_SOURCES.md). Verify any release-specific policy requirements before distribution.

## Explicit publication decision

| Gate | Observation as of 2026-10-11 |
|---|---|
| Core purpose and JSON reference | **Documented** |
| Qualifier and pyrethrin part attribution | **Implemented with provenance**; not a chemical completeness guarantee |
| Known active substances lacking definitions | **Implemented**, with source-qualified statuses |
| Unit/regression tests and latest history secret scan | **Passed in CI** |
| Full SE/FR benchmark and reproduction instructions | **Committed**; 260 full-definition discrepancies remain unexplained |
| Historical definitions and automatic refresh | **Not implemented**; [#25](https://github.com/Chili36/rd-bridge/issues/25) and [#4](https://github.com/Chili36/rd-bridge/issues/4) remain open by design |
| Public visibility and historical commit metadata | **Not cleared**: explicit decision on 48 Claude session links and contributor addresses still required ([#35](https://github.com/Chili36/rd-bridge/issues/35)) |

**Conclusion:** The mapping and documentation are ready for a technical public review. **Do not state that the data is authoritative or proven legally correct. Do not make the repository public automatically while the history-exposure decision remains unresolved.** This review records what has been completed, what was measured, and the remaining decision rather than concealing open questions.

## Future checks

- Investigate the `P005A` differences against the actual residue definition in force at each sampling date; retain an auditable case-by-case decision, never relabel disagreements as errors solely because the codes differ.
- [#4](https://github.com/Chili36/rd-bridge/issues/4): introduce scheduled source updates only with failure-on-empty, schema drift detection, approval review and a diff of residue id/version/footnote text.
- Improve automatic ester/salt/conjugate coverage cautiously, testing negative examples; do not promote a general qualifier to a closed list of required compounds.
- Keep the published dataset version, EFSA catalogue version, and source checksums explicit in future release notes.
