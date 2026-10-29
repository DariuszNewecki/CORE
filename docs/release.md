# Release Process

CORE is published to PyPI as `core-runtime`. Releases are triggered by
pushing a semver-shaped tag (`vX.Y.Z`) to `main`. The publish workflow
authenticates to PyPI via OIDC — no API token is stored anywhere in the
repository or as a GitHub secret.

## One-time setup (governor action, ~5 minutes)

The Trusted Publisher relationship is configured once per project, then
every future release is automatic.

### 1. Register a pending publisher on PyPI

The `core-runtime` project is live on PyPI (<https://pypi.org/project/core-runtime/>),
and the Trusted Publisher relationship is already established. The steps
below are retained as the original one-time setup record. To allow the
first publish via OIDC (without manually creating + uploading first), a
**pending publisher** was registered:

1. Sign in at <https://pypi.org/manage/account/publishing/>.
2. Under "Add a new pending publisher," fill in:
   - **PyPI project name:** `core-runtime`
   - **Owner:** `DariuszNewecki`
   - **Repository name:** `CORE`
   - **Workflow name:** `publish-pypi.yml`
   - **Environment name:** `pypi`
3. Submit.

PyPI will accept publishes from the matching workflow + environment +
repository tuple. After the first successful publish, the pending
publisher converts to a regular trusted publisher on the project's
settings page.

### 2. Create the `pypi` environment in GitHub

GitHub Actions environments gate which workflow runs can request the
OIDC token. The workflow file declares `environment: pypi`, so the
environment must exist:

1. In the GitHub repo, go to **Settings → Environments → New environment**.
2. Name it `pypi`.
3. Optional protection rules (recommended):
   - Required reviewers (the governor) — adds a manual gate before publish.
   - Deployment branches: restrict to `main` only.

No secrets are stored in the environment — OIDC handles authentication.

## Cutting a release

Once the one-time setup is complete:

1. Update the version in `pyproject.toml` under `[project] version` (PEP 621, per #543).
   It is the only canonical version.
2. Run `python scripts/release_pins.py --write`. It brings every release pin
   to that version: the `Dockerfile` default, the README badge, the
   cold-reviewer Action tag, the GitLab template, the pre-commit example, the
   committed OpenAPI contract's `info.version`, and the CHANGELOG comparison
   links. It lists any pin it cannot rewrite safely
   (the README "Current Release" line, which also describes the release);
   edit those by hand. Run `python scripts/release_pins.py --check` before tagging; no CI job runs it.
3. Commit the bump (`release: X.Y.Z -- <one-line summary>`).
4. Once the bump is merged, start the full CI run on the merge commit before tagging.
   A run tests the head of the branch it starts on, so start it on a branch at the merge
   commit: `git push origin <merge sha>:refs/heads/release-check/X.Y.Z && gh workflow run core-ci.yml --ref release-check/X.Y.Z`. The PyPI publish refuses a
   tag unless the latest CORE CI run on that SHA is green and a full (workflow_dispatch) run on it succeeded;
   the Docker images are built by the same run, after the PyPI publish.
5. Tag the merge commit: `git tag -a vX.Y.Z -m "core-runtime X.Y.Z" <merge sha> && git push origin vX.Y.Z`.
6. Create the GitHub release, so the repository page shows it as Latest:
   `gh release create vX.Y.Z --verify-tag --latest --title "vX.Y.Z — <summary>" --notes-file <the CHANGELOG section>`.
7. Once X.Y.Z is on PyPI, raise `RELEASED_ENGINE` in `.github/workflows/core-ci.yml`
   to X.Y.Z in a pull request. The released-engine audit judges every pull request with
   that exact version, so a tag alone never changes the judge (review finding F10).

### Schema and upgrade-path checklist (ADR-162 D4/D5/D9)

Before tagging a release that changes the database schema:

- **Manifest complete.** Every new `.sql` under `infra/scripts/migrations/` is in
  `infra/migrations/manifest.yaml` `order` with a `verify` probe under `probes:`
  (`tests/shared/infrastructure/test_migration_manifest_completeness.py`).
- **`schema.sql` regenerated** from the migrated database by `infra/scripts/reset_test_db.sh`,
  which appends the ledger seed; seed ids must equal the manifest order
  (`tests/shared/infrastructure/test_schema_ledger_seed.py`).
- **Hop test green.** The previous release's `schema.sql` plus the entries added since must
  reproduce the new `schema.sql` (`migrations/test_hop_equivalence_postgres.py`, integration job).
  A red hop means a change reached `schema.sql` without a migration — write the migration,
  never edit the comparison.
- **Baseline declared.** After tagging, add `vX.Y.Z` to `baselines:` (`through` = the last
  manifest entry the release ships with, with fingerprint + absence probes) and commit
  `tests/fixtures/schema/schema-vX.Y.Z.sql` byte-identical to the tag, so the next hop is
  testable from a shallow checkout.
- **CHANGELOG** lists the release's schema migrations and whether writers must be quiesced.

Before tagging, start the **full** CI run on the commit you will tag:
step 4 above (a `release-check/X.Y.Z` branch at that commit). Push and PR runs skip the
release-upgrade tests (pytest marker `upgrade`); only the full run includes them.

The `publish-pypi.yml` workflow fires on the tag push. It first refuses
unless the latest CORE CI run for the exact tagged SHA concluded success
(#954) and a full (`workflow_dispatch`) run on that SHA succeeded, then verifies the tag version matches `pyproject.toml`, builds the
wheel + sdist, installs the wheel into a clean venv and walks the adopter
path (`project new` → `adopt-pack` → `code audit --offline`, asserting
PASS / DEGRADED / FAIL where each is due), and publishes via OIDC. The release appears at
<https://pypi.org/project/core-runtime/> within a few minutes.

## Semver

CORE follows semantic versioning per ADR-086 D7; the semver policy was
finalized in #541 (F-48.5). CORE is past 1.0, so
minor bumps add backward-compatible surface and patches are fixes only.

Versions are immutable. Mistakes ship as a new patch version, never as
a re-tagged release.

## Notes

- The workflow does **not** run pytest itself; it requires that CORE CI
  (`core-ci.yml`, which runs on pushes to `main`, on PRs and on
  `workflow_dispatch`) passed on the tagged SHA, including a full run. Tag a commit whose CI is green: a failed, cancelled,
  in-progress or missing run refuses the release. Re-run CI, then re-run
  the publish workflow.
- Each tag also publishes `core-engine:X.Y.Z` and `core-audit-gate:X.Y.Z` to GHCR,
  built from the PyPI wheel of the same version (ADR-086 D7). If an image build runs
  before PyPI lists the new version, it fails; re-run it once the version is listed.
