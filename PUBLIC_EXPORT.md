# Publication from a clean history

This repository is a **private development archive**. Do not make the existing
repository public: its old branches and GitHub pull-request references can
still retain previous commit metadata even if `main` is rewritten.

The `public-release-clean` branch is an independent, **single-root-commit**
export generated from the current files. That root commit has neutral,
non-personal author and committer identities, and no inherited parent commits.
The source ZIP and Git bundle are also available from the corresponding
GitHub Actions run on the private archive.

To publish safely:

1. Keep the development archive private. **Before renaming it**, clone
   only the clean export ref, and verify that it has one commit:

   ```bash
   git clone --single-branch --branch public-release-clean \
       https://github.com/Chili36/rd-bridge.git rd-bridge-public
   cd rd-bridge-public
   git rev-list --count HEAD                 # must print 1
   git log -1 --format='%an <%ae> | %cn <%ce>'
   ```

2. Create a **new empty repository** (no generated README or initial commit).
   To retain the public URL `Chili36/rd-bridge`, first rename the original
   *private* repository, for example to `rd-bridge-private-archive`, then
   create a new empty `Chili36/rd-bridge`. If a different public name is
   acceptable, no rename is necessary.

3. Push **only** the clean branch to the *new* repository. Never use
   `--all`, `--mirror`, or the archive's original `main`:

   ```bash
   git remote add public https://github.com/<owner>/<new-repo>.git
   git push public HEAD:refs/heads/main
   ```

4. Check that the new repository has just one commit and no historical PR
   refs. Run unit tests and a Gitleaks scan in the **new** repository before
   changing its visibility. Never push any branch or tag from the private
   archive to the public repository.
5. Do not merge or cherry-pick old private commits into the new history;
   transfer reviewed file changes as new clean commits instead.

The original data snapshot's recognition index was saved in
`data/baselines/d2d1/` so validation does not require carrying the
original Git objects into the new repository. Run the portable comparison
with `python -m scripts.portable_validation --countries SE FR`.
It downloads the same public Zenodo archives and does **not** commit
individual reporting records.

A clean snapshot is a new repository *lineage*, not a sanitization of all
hidden refs in this private GitHub repository. This procedure is necessary
because there are historical closed pull requests whose retained commits
cannot be safely purged by an ordinary force-push to `main`.
