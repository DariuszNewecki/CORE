<!-- path: .specs/planning/CORE-Semver-Policy.md -->

# CORE — Versioning & Release Policy

**Status:** Authoritative (operational surface — implements ADR-086 D7 + ADR-088 D5; deliverable of F-48.5 #541)
**Authority:** governor
**Audience:** Anyone installing, depending on, or releasing `core-runtime` — and future-you deciding the next version number.
**Last updated:** 2026-06-14

---

## 1. What a version number promises

CORE ships as `core-runtime` on PyPI under `MAJOR.MINOR.PATCH` (e.g. `2.7.0`). The number
answers one question for whoever upgrades: **will this hurt?**

- **MAJOR** — something a user touches changed. They may have to edit code, config, or run a
  manual step before the new version works. *Read the notes before upgrading.*
- **MINOR** — capability was added. Existing usage keeps working unchanged. *Safe upgrade.*
- **PATCH** — fixes only; no new surface, nothing breaks. *Safe upgrade.*

Rule of thumb: bump the **leftmost** number whose criterion (§3) applies. When genuinely torn
between two, pick the lower-risk signal **only if** you are certain nothing breaks; otherwise
bump higher. Honest-and-consistent beats clever.

## 2. The source of truth and the current baseline

There is **one** version line. `pyproject.toml`'s `version` is canonical; the PyPI release,
the GitHub release tag, and the OEM wire `info.version` (ADR-087) all mirror it.

- **Baseline:** `2.6.0` (PyPI + GitHub latest, 2026-06-02).
- **Next release:** `2.7.0` — a **minor** bump (additive features and fixes since `2.6.0`;
  no removed or renamed CLI command, no removed API route, no public-surface break).

The `v0.1.0`–`v0.1.6` tags are **bootstrap artifacts** from the first PyPI publish, not a
pre-1.0 track (ADR-088 D3). They are preserved unchanged per the standing tag-collision
policy; no further `0.x` tags are created. **CORE is not in a pre-1.0 phase** — there is no
"`0.y.z` means anything-may-break" caveat to apply.

## 3. Bump criteria (forward rules, per ADR-088 D5)

From `2.6.0` forward, every bump follows standard SemVer with CORE-specific definitions:

- **MAJOR (`2.x → 3.x`)** — a breaking change to the **Python public surface** (per F-48.4
  once that surface is declared) **OR** a wire-surface major bump per ADR-087 D6
  (`/v1/` → `/v2/`). One trigger is sufficient; the two bumps are coordinated.
- **MINOR (`2.6 → 2.7`)** — additive features, new public symbols, new public routes, new
  optional response fields, new additive exit codes. ADR-087 D2's additive-only wire rules apply.
- **PATCH (`2.6.0 → 2.6.1`)** — bug fixes, internal-only refactors, documentation. No
  wire-visible or surface-visible change.

**Internal-only changes are not major.** Changes to CORE's own runtime machinery — the
governance engine, the blackboard, the autonomy daemon, the internal DB schema — do **not**
trigger a major bump, because they are not the Python public surface or the wire surface. A
runtime schema change that needs a manual `ALTER` on an *existing* install ships as a
**documented upgrade note** in the release, not as a `3.0.0`: fresh installs are unaffected
(CORE is schema-as-truth — a new install provisions the current schema directly).

> **Note on ADR-086 D7's broader phrasing.** D7 lists "schema migration that requires manual
> operator action" among major triggers. ADR-088 D5 is the later, narrower *forward* rule this
> document inherits, and it scopes "major" to the public/wire surface. Where the two differ on
> internal schema, D5 governs the version-number decision; D7 governs the cross-channel
> contract in §4. This document may refine these definitions (per ADR-088 D5) but may not reset
> the version number — `2.6.0` is the starting line.

## 4. Cross-channel contract (ADR-086 D7)

- **PyPI ⟺ Docker.** A PyPI release `X.Y.Z` exists **if and only if** Docker image
  `core-engine:X.Y.Z` exists. *Current state: the Docker `core-engine` channel is not yet
  shipped (#539 open) — the PyPI line runs ahead of it. The invariant binds once that channel
  ships; until then it is unmet-by-absence, recorded here honestly rather than asserted.*
- **No implicit "latest".** The install script pulls **pinned** versions; it never resolves
  "latest" implicitly.
- **Monotonic increase.** Every release version is strictly greater than the last.

## 5. Immutability — released versions are frozen

A released version is **immutable**. Re-tagging or force-pushing a published version is
**prohibited**. Corrections ship as a **new patch** version. This holds for PyPI, the Docker
image, and the git tag alike.

## 6. Pre-release candidates

Release candidates use the suffix `X.Y.Z-rc.N` (e.g. `2.7.0-rc.1`), published to PyPI with the
pre-release flag so `pip install core-runtime` **skips them by default**. An `-rc` is promoted
to its final `X.Y.Z` by a new release, never by re-tagging the candidate.

## 7. The 2.x stability posture (honesty, per ADR-088 D2)

Strict SemVer reads `2.x` as "stable public API." CORE's actual posture is **"API approaching
stability; the public surface contract is under active definition"** — two vectors still open:
the **OEM wire surface** (ADR-087; v1 baseline grandfathered, OpenAPI spec pending) and the
**Python public surface** (F-48.4, not yet shipped). The PyPI `Development Status` classifier is
**`4 - Beta`**; promotion to `5 - Production/Stable` is a future decision gated on F-40 and
F-48.4. The v2.x line is kept because it reflects CORE's real one-year maturity arc — resetting
to `0.x` would erase real history to chase a convention CORE is approaching, not below.

## 8. Cadence (informational)

Patches ship as needed. Minor and major releases ship on a regular cadence to be determined
post-1.0-surface-declaration. Cadence is informational, not a contract — correctness gates a
release, not the calendar.

---

## References

- **ADR-086 D7** — cross-channel semver + provenance contract (PyPI/Docker iff, monotonicity,
  no re-tagging). `.specs/decisions/ADR-086-installation-architecture.md`
- **ADR-088** — PyPI version alignment with the narrative release track (D1 the `2.6.0`
  alignment, D2 the honesty posture, D3 the bootstrap-tag record, D5 the forward rules this
  document inherits). `.specs/decisions/ADR-088-pypi-version-alignment.md`
- **ADR-087** — OEM API versioning and stability policy (wire surface; `info.version` mirrors
  the PyPI version). `.specs/decisions/ADR-087-oem-api-versioning-and-stability-policy.md`
- **F-48.5 #541** — the issue this document closes.
- **CHANGELOG** — per-release constitutional change record: `.intent/CHANGELOG.md` (format is a
  separate concern from this policy).
