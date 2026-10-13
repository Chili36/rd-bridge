# PARAM component acceptance and independent review

## Why two acceptance cases failed

The previous 30-case acceptance set expected **complete** when supplied with
the generic *active substance* (AS) code for two residue definitions (RDs).
Those codes are not the catalogue's own complete residue-definition codes.

| Source residue | EU definition | Whole RD PARAM code (PARAM 17.6) | Earlier test code |
| --- | --- | --- | --- |
| 321 | Guazatine (guazatine acetate, sum of components) | `RF-00004664-PAR` | `RF-0233-001-PPP` (Guazatine AS) |
| 2655 | Fluvalinate (sum of isomers) resulting from the use of tau-fluvalinate | `RF-00012800-PAR` | `RF-0721-001-PPP` (Fluvalinate AS; **not reportable** in PARAM 17.6) |

The revised acceptance set checks **both directions**: the complete RD code
must be accepted and the unrelated AS code must **not** be treated as proof
that the full, specific RD was analysed.

This is a correction to the *test expectations* based on source definitions
and current EFSA catalogue metadata, not evidence that Haiku improved. A
laboratory's full-coverage status must also depend on actual analytes measured,
which a bare PARAM code cannot establish by itself. See [EFSA's guidance on
`paramType` P005A/P004A/P002A](https://efsa.onlinelibrary.wiley.com/doi/10.2903/j.efsa.2018.5285)
for the full legal-definition versus component distinction.

## Where the genuine disagreements remain

The 40 distinct model-versus-rule differences include substantive disagreements
about analytes, PARAM component codes and grouped residues, as well as purely
structural wording differences. We should *not* treat all 40 as 40 errors.

`rd_bridge.sonnet_review` ranks them reproducibly:
1. Conflicting/missing component PARAM codes (highest priority).
2. Group coverage or unlinked analytes.
3. Pure wording differences.

A focused, **12-call maximum** review includes the two former acceptance cases
and the highest-priority disagreements. Sonnet reads the original EU definition
and PARAM family terms **without seeing the Haiku or rule-parser answers**.
After the independent read, the existing deterministic matcher links Sonnet's
components and compares that third reading with the earlier two.

Run manually after setting `ANTHROPIC_API_KEY` (or through
[the Sonnet review workflow](../.github/workflows/sonnet_review.yml)):

```bash
python -m unittest discover -s tests -t .
python -m rd_bridge.compare_parts
python -m rd_bridge.sonnet_review --limit 12
```

The command creates `reports/sonnet_review.json` (machine-readable evidence)
and `reports/sonnet_review.md` (human summary); the workflow opens a pull
request with both. **None of its proposed conclusions are automatically
promoted into the PARAM reference.** Independent model agreement can help us
choose cases for manual review, but it is not chemical or legal ground truth.

The comparison JSON is regenerated during the normal EU refresh; it is not a
substitute for fixing acceptance definitions when source catalogue semantics
change.
