<!-- path: .specs/decisions/ADR-088-pypi-version-alignment.md -->

# ADR-088 — PyPI version alignment with the narrative release track

**Date:** 2026-06-02
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-02 — drafted under Path A execute-verb authorization: governor's "we will bump it to 2.6.0 with CLEAR reason behind it: PyPI" + delegated ADR numbering + explicit "on disk" instruction).
**Grounding papers:** none direct — this ADR resolves a multi-surface drift discovered during an external review of CORE's public-facing version surfaces (README badge, `pyproject.toml`, GitHub release track).
**Related:** ADR-086 D7 (cross-channel semver contract — PyPI/Docker iff); ADR-087 D1 + D9 (OEM API wire-version coordinates with PyPI `info.version`); F-48 #527 (PyPI publish — parent of the bootstrap work that surfaced the drift); F-48.5 #541 (semver policy doc — its scoping premise is overridden by this ADR's D2 and inherits D5 as its baseline); standing tag-collision policy (`feedback_tag_collision_sidestep_first_pypi` — historical tags preserved unchanged).

---

## Context

### Why this ADR exists

CORE arrived at 2026-06-02 with three visible version surfaces:

| Surface | Value | Origin |
|---|---|---|
| README badge | `v0.1.2` | static string set early and never updated |
| `pyproject.toml` (PyPI `core-runtime`) | `0.1.6` | bumped today during F-48 PyPI publish work; landed at `.6` via the tag-collision sidestep |
| GitHub release track | `v2.5.0 — Engine Integrity` (latest) | narrative releases dating to v0.2.0 (August 2025), v1.0.0 (October 2025), v2.0.0 (November 2025), v2.2.x, v2.3.0, v2.4.0, v2.5.0 |

ADR-086 D7 declares the cross-channel semver contract (PyPI/Docker iff, monotonic increase, no re-tagging) but is silent on whether the project is operating in pre-1.0 or post-1.0 territory. F-48.5 #541's scoping body assumed CORE would continue in `0.x` until F-48.4 (public Python surface declaration) ships and then bump to `1.0.0`. That premise no longer matches the project's actual one-year release history.

Without an explicit alignment decision, every future release perpetuates the divergence: a PyPI bump goes `0.1.6 → 0.1.7`, a narrative release goes `v2.5.0 → v2.6.0`, and consumers see two unrelated numbers describing the same release.

### Why now

PyPI distribution went live today. Every release decision from this point depends on which track is the source of truth. Letting the question drift produces compounding divergence and converts a one-line fix today into a multi-file reconciliation later. The version alignment also gates the F-48.5 semver policy doc, the future ADR-087 D6 `/v2/` wire-version coordination, and the README claim hygiene work (ADR-087 already specifies that `info.version` mirrors PyPI; a divergent PyPI track would falsify that mirror).

### Status quo at acceptance

- PyPI publishes `core-runtime 0.1.6` (current as of acceptance).
- GitHub latest release is `v2.5.0 — Engine Integrity`.
- Local tags `v0.1.0` through `v0.1.6` exist and are pushed to the remote — they were created during today's PyPI bootstrap iterations.
- `v0.2.0` exists as a tag and as the project's first GitHub release (August 2025), occupying a number that would otherwise be a candidate for the next forward bump within a `0.x` track.
- The README badge value (`v0.1.2`) and Python requirement (`≥ 3.11`) are stale; both corrected in the same session that produced this ADR.

---

## Decisions

### D1 — `core-runtime` PyPI version aligns with the narrative release track

`pyproject.toml`'s `version` field is bumped from `0.1.6` to **`2.6.0`**. The next PyPI release is `core-runtime 2.6.0`. Per ADR-086 D7, the corresponding Docker image, when that distribution channel ships, is `core-engine:2.6.0`.

The jump is forward-monotonic per PyPI's enforcement rules (PyPI accepts any version higher than `0.1.6`), so ADR-086 D7's monotonicity invariant is preserved.

### D2 — Honest acknowledgment of the SemVer concession

Strictly, SemVer's `2.x` signals "stable public API." CORE's actual posture is **"API approaching stability; the public surface contract is under active definition."** The two active definition vectors are:

- **OEM wire surface** — governed by ADR-087; v1 baseline grandfathered, future evolution rules declared, F-40.3 OpenAPI spec pending.
- **Python public surface** — F-48.4 (sub-issue of F-48 #527) declares which symbols in `core-runtime` are public. Not yet shipped.

This ADR declines to retreat to a `0.x` track on the basis of SemVer purity. The v2.x narrative track represents CORE's actual maturity arc, has a year of release history, and contains codenames already published to readers. Continuing it is the honest move; resetting it would erase real history to chase a convention CORE is genuinely approaching, not currently below.

The PyPI classifier `Development Status` is set to **`4 - Beta`** (from `3 - Alpha`) to surface the approaching-but-not-final stability posture through PyPI's own metadata. Promotion to `5 - Production/Stable` is a future decision, gated on F-40 and F-48.4 closure.

### D3 — `v0.1.x` tags are bootstrap artifacts, not a parallel track

The local + remote tags `v0.1.0` through `v0.1.6` were created during today's F-48 PyPI publish iterations. They are preserved unchanged in accordance with the standing tag-collision policy (`feedback_tag_collision_sidestep_first_pypi` — historical tags are never deleted or force-pushed).

They are **not** a deliberate parallel versioning track. This ADR records their origin so a future reader inspecting the tag list does not infer a `0.x` strategy that CORE never adopted. Going forward, no further `0.x` tags are created.

### D4 — Coordination with existing ADRs

- **ADR-086 D7** — monotonicity satisfied; PyPI/Docker iff invariant inherits the new baseline; no edit required.
- **ADR-087 D1** — illustrative examples (`core-runtime 0.4.X → 0.5.0`, `0.5.0 → 0.5.1`) are stale-by-example and updated to `2.x` form as a follow-up edit; no semantic change.
- **ADR-087 D9** — illustrative `info.version` example (`0.7.2`) likewise updated to a `2.x` example; no semantic change. The substantive rule — `info.version` mirrors `core-runtime`'s PyPI version — is preserved.

### D5 — Forward versioning rules (inherited by F-48.5 #541)

From `2.6.0` forward, every PyPI bump follows standard SemVer with CORE-specific definitions:

- **Major bump** (`2.x → 3.x`) — triggered by a breaking change to the Python public surface (per F-48.4 when defined) OR a wire-surface major bump per ADR-087 D6 (`/v1/` → `/v2/`). Coordinated bumps; one trigger is sufficient.
- **Minor bump** (`2.6 → 2.7`) — additive features, new public symbols, new public routes, new optional response fields. ADR-087 D2's additive-only rules apply at the wire surface.
- **Patch bump** (`2.6.0 → 2.6.1`) — bug fixes, internal-only refactors, documentation. No wire-visible or surface-visible change.

These rules are the baseline F-48.5 #541's deliverable inherits. F-48.5 may refine the definitions but may not reset the version number — `2.6.0` is the starting line.

### D6 — README badge and version-policy sentence

The README "Release" badge is bumped from `v0.1.2` to `v2.5.0` to match the current GitHub latest release. It bumps to `v2.6.0` when that release ships. A single-sentence version-policy note is added to the README (near the badge or in the Requirements section) so external readers can locate the convention without reading this ADR.

The exact sentence wording is delegated to the README rewrite pass (currently pending governor authorization).

---

## Consequences

### Enables

- F-48 PyPI distribution ships against a coherent versioning baseline; no future "which number is canonical" question.
- ADR-086's iff invariant (PyPI/Docker) operates against a single version number from `2.6.0` forward.
- ADR-087's `info.version mirrors PyPI` rule (D9) is honored — the wire-spec version and the PyPI version now agree on the major component.
- F-48.5 #541 unblocks: its scoping body's premise is replaced with this ADR's D5 baseline, and the document can be authored without revisiting the version-number question.
- External readers (an OEM partner, a contributor, a reviewer) see one number on PyPI, one number on GitHub, one number on the README — and a short statement explaining why CORE is in `2.x` rather than `0.x` despite the API still maturing.

### Forbids

- Retreating to a `0.x` PyPI track. The `2.6.0` baseline is committed; SemVer rules cannot legally walk backwards.
- Creating new `v0.1.x` tags. The existing `v0.1.0` through `v0.1.6` tags are frozen history.
- Re-tagging or force-pushing any historical tag, per the standing tag-collision policy.

### Costs

- **Visible SemVer/stability mismatch.** A purist reading PyPI would expect `2.x` to mean "stable public API." CORE's API is approaching, not arrived. D2 mitigates by setting the Beta classifier; the README sentence further mitigates by stating the posture explicitly. The cost is honest residual confusion that cannot be eliminated without either (a) erasing the v2.x history (rejected) or (b) declaring stability prematurely (rejected). This ADR accepts that residual.
- **Major bump triggers are now coordinated, not independent.** Per D5, a `2.x → 3.x` bump requires either a Python public-surface break OR a wire `/v1/` → `/v2/` cut. A future ADR may want to bump major for some other reason (e.g., constitutional re-architecting); D5 would have to be revisited at that point. This ADR does not pre-decide that future case.
- **F-48.5 #541's original framing now requires a rewrite.** The "wait for F-48.4 then bump to 1.0" plan in #541's body is obsolete. A comment on #541 records this; a future edit to the issue body or the doc itself absorbs the change.

### Downstream effects

- **`pyproject.toml`** — version field and classifier updated this session.
- **README** — badge updated this session; version-policy sentence pending governor authorization.
- **ADR-087** — D1 and D9 illustrative examples to be updated as a small follow-up edit (no semantic change; pending governor authorization).
- **F-48.5 #541** — premise comment posted this session; document inherits this ADR's D5 baseline when authored.
- **F-48 #527** — no edit required; this ADR is downstream of F-48's publish work and resolves a question F-48 surfaced.

---

## References

- **Parent context:** F-48 #527 (PyPI publish — the work whose tag-collision sidestep produced `0.1.6` and surfaced the drift)
- **Direct dependents:** F-48.5 #541 (semver policy doc — inherits D5)
- **Constitutional anchors:** ADR-086 D7 (cross-channel semver contract); ADR-087 D1 + D9 (PyPI/wire coordination)
- **Standing policy referenced:** tag-collision sidestep (memory `feedback_tag_collision_sidestep_first_pypi` — never delete or force-push historical tags)
- **External convention referenced:** Semantic Versioning 2.0.0 (`semver.org`); PyPI `Development Status` classifier vocabulary (`pypi.org/classifiers/`)
