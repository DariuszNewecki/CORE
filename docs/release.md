# Release Process

CORE is published to PyPI as `core-runtime`. Releases are triggered by
pushing a semver-shaped tag (`vX.Y.Z`) to `main`. The publish workflow
authenticates to PyPI via OIDC — no API token is stored anywhere in the
repository or as a GitHub secret.

## One-time setup (governor action, ~5 minutes)

The Trusted Publisher relationship is configured once per project, then
every future release is automatic.

### 1. Register a pending publisher on PyPI

The `core-runtime` project does not exist on PyPI yet. To allow the
first publish via OIDC (without manually creating + uploading first),
register a **pending publisher**:

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

1. Update the version in `pyproject.toml` under `[tool.poetry] version`.
2. Update the release badge in `README.md` to match.
3. Commit the bump (`chore: bump version to X.Y.Z`).
4. Tag the commit: `git tag vX.Y.Z && git push --tags`.

The `publish-pypi.yml` workflow fires on the tag push, verifies the tag
version matches `pyproject.toml`, builds the wheel + sdist, and
publishes via OIDC. The release appears at
<https://pypi.org/project/core-runtime/> within a few minutes.

## Semver

CORE follows semantic versioning per ADR-086 D7. Pre-1.0 releases
(`0.y.z`) signal the public API is still evolving — see issue #541
(F-48.5) for the in-progress semver policy document.

Versions are immutable. Mistakes ship as a new patch version, never as
a re-tagged release.

## Notes

- The workflow does **not** run pytest. Pre-tag validation is the
  responsibility of the existing CI workflow (`ci.yml`), which runs on
  every PR and push to `main`. Only tag commits that have already
  passed CI.
- The Docker image counterpart (`core-engine:X.Y.Z`) ships via F-48.3
  (#539). Per ADR-086 D7, PyPI and Docker versions are paired — see
  that issue for the matched-version invariant once it lands.
