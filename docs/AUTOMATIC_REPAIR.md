# Automatic interpretation repair

The original migration assembled 765 guided readings successfully, then
[PR #21](https://github.com/Chili36/rd-bridge/pull/21) showed five failed
regression cases. This was a problem in the workflow: it detected known,
machine-testable errors but provided **no correction loop**.

The [automatic repair workflow](../.github/workflows/auto_repair_guidance.yml)
now closes that loop without repeating paid bulk interpretation calls:

1. **Retrieve** all existing versioned guidance readings from the candidate PR.
2. **Detect** failures in the repository's existing `compare_parts.CASES`
   (34 expected scenarios, unchanged). Do not treat every disagreement with
   the rule parser as an established failure.
3. **Diagnose** each failed RD using its exact EU definition, recorded
   OECD/EU/EFSA guidance, current and previously accepted component readings,
   specific failing assertions, and actual PARAM codes, names, `pest_class`
   and `reportable` metadata.
4. **Reinterpret** only the affected definition with Claude Sonnet 5.5,
   not the full batch. Rebuild the mapping and test every existing acceptance
   scenario for the affected RD. Up to two rounds and twelve model calls.
5. **Retain the previous exact-definition reading** if a new model output
   still fails known tests. Mark this entry
   `parts_from=legacy_regression_fallback`,
   `interpretation_source=legacy_retained_after_regression`, and
   `requires_followup=true`. Never rewrite the expected test results,
   hallucinate a new PARAM code or claim this fallback is a new AI success.
   All successful guided readings elsewhere are retained.
6. **Rebuild everything** from original EU source and PARAM snapshots,
   verify that all original whole-RD PARAM codes and EU definition texts
   remain unchanged, rerun all acceptance tests and unit tests, and record
   the complete before/after component-code difference.
7. **Adopt automatically** if known assertions and unit tests pass.
   Preserve a review PR and artifacts if a concrete regression still fails.

Run the latest migration repair manually through
[Actions: Auto-repair guided RD migration](../.github/workflows/auto_repair_guidance.yml)
or allow its one-time initial push trigger. The `candidate_branch` input
makes the repair reusable for future model-generated proposals. The original
full-migration and historical recovery workflows now call the same repair
module directly, so reporting a machine-detectable regression will no
longer be the end of the process.

## What this can and cannot establish

The loop can automatically address **detected, reproducible failures** and
prevent them from blocking adoption of the rest of the dataset. It does not
prove every component is chemically correct, and it cannot safely declare
an undetected ambiguity an error. Changed component PARAM codes, source
provenance and unresolved cases remain explicitly visible in the report.

An independently reviewed gold-standard dataset is not available and is
**not** required. Source documentation, existing acceptance cases, catalogues
and incremental feedback provide the operational basis for improvement.

The baseline `data/model_parts.json` is kept for rollback; the new complete
`data/guided_model_parts.json` remains versioned and auditable.
