# rd-bridge — working rules

rd-bridge turns EU pesticide residue definitions into EFSA PARAM codes
(`data/residue_param_map.json`). The ChemMon wiki (`~/Dev/Chemmon_Wiki`) consumes that output and
is maintained by a separate session: **do not edit that repo**. After a merge here, the wiki's daily
`rd-bridge-refresh` workflow opens a PR in Chemmon_Wiki and the wiki session reviews it; nothing
needs doing on the wiki side.

## Decisions (settled — don't re-argue)

- Links guessed by Sonnet 5.5 (`method: "model"`) are shown like normal links. Don't make matching
  strict-only; the model should make good guesses.
- No guards or prompt tweaks aimed at particular failing terms (CAS checks, low-confidence filters,
  special-case prompt lines). These were rejected as overfitting. Improve general methods instead.
- Never change an LLM model name (e.g. `model_match.MODEL`) without asking first.
- `docs/MAPPING_METHOD.md` describes the matcher methods
  (`exact`/`spelling`/`compound_set`/`cas`/`alias`/`near`/`model`/`none`) and the model-guess cache
  `data/model_matches.json`. Keep it current with any change to matching.

## How to work

- Always work on a feature branch; open a GitHub issue first and work in a trackable order.
- Run the full test suite before merging:
  `python -m unittest discover -s tests -t .`
  CI also checks that `python -m rd_bridge.match`, `compare_parts` and `guidance_audit` reproduce
  the committed data (see `.github/workflows/tests.yml`).
- After opening a PR, watch it for a short while. Codex reviews PRs: fix real findings, and ignore
  small nitpicks if they keep coming. Merge with `gh pr merge --admin` only once the tests pass
  locally and every CI check on the PR is green; the bypass is for the review requirement, not
  for pending or failing checks.
