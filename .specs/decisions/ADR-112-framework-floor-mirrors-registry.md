---
kind: adr
id: ADR-112
title: ADR-112 — The framework floor mirrors the framework registry (BYOR floor-sync)
status: retired
---

<!-- path: .specs/decisions/ADR-112-framework-floor-mirrors-registry.md -->

# ADR-112 — The framework floor mirrors the framework registry, and drift fails loud

**Status:** Withdrawn — 2026-06-18. Superseded by the Scenario 1+4 scoping decision (commercial focus narrowed to CORE self-governance + GRC gap-analysis). The BYOR onboard / starter-floor work this ADR addressed (Scenario 2) is parked, so its drift problem no longer needs a decision. Recorded, not deleted, so the reasoning is reconciled-against rather than re-derived. See ADR-113 for the live evidence-class work.
**Date:** 2026-06-18
**Grounding paper:** `CORE-BYOR.md` (§3 the Repository floor; §8 ADR-075 framework/project split) — primary.
**Builds on:** ADR-075 (framework/project namespace — the floor is framework-owned), ADR-108 (external adoption ships a minimal authored starter + machinery floor), ADR-111 (onboard delivers the authored starter; **D5 explicitly deferred floor-sync, which this ADR decides**), ADR-008 (impact_level is governed externally, not embedded in `src/`).
**Operationalizes:** UR-01 (Universal Input Acceptance), UR-07 (no overclaiming) — the on-ramp must actually run for an adopter before any doc promises it.
**Closes:** the gating defect behind #640 step 2 (T1 in `CORE-BYOR-Program-Backlog.md`). Unblocks T2 (newcomer docs).

---

## Context

T1 of the BYOR backlog asked a single honest question: *does the delivered
starter actually enforce in a consumer repo?* Reproducing the offline audit from
inside `examples/starter-intent/` (a representative onboarded repo) answered **no**,
for a reason deeper than the backlog's note ("loaded the rules but logged no
enforcement mappings").

**The real blocker is a bootstrap crash, not a mapping miss.** Every `core-admin`
invocation builds the `ActionExecutor`, which calls `registry.apply_risk_config()`.
That method **fail-closes**: it raises `ConstitutionalError` if *any* registered
atomic action lacks an `impact_level` entry in the *active* repo's
`action_risk.yaml` (`src/body/atomic/registry.py`, `apply_risk_config`). CORE's
code registers all 46 of its atomic actions regardless of the consumer's rule set,
because the consumer runs CORE's engine. The shipped starter floor declares only
44 — missing exactly `assisted.apply_diff` and `assisted.validate_diff`, which
**ADR-109 added to CORE's registry but never propagated to the starter floor.**
Result: `core-admin` is dead at bootstrap inside any onboarded repo — the audit
never runs.

Two adjacent findings frame the decision:

- **The "no enforcement mappings" symptom is a source-tree artifact, not a
  consumer-real fault.** `.env` pins `REPO_PATH=/opt/dev/CORE` while `settings.MIND`
  resolves CWD-relative (→ the starter), so the bootstrap's mapping loader reads
  CORE's `.intent` while `IntentRepository` reads the starter's. Built in isolation,
  `AuditorContext` loads the starter's four mappings correctly. A genuine
  pip-installed consumer (no CORE `.env`) would not hit this — which also means
  *true* consumer mode cannot be fully simulated from the source tree; that waits
  on the wheel (ADR-108 D3 / #674).

- **The drift-guard that ADR-111 called "load-bearing for adopters" is falsely
  green.** `examples/starter-intent/verify.sh` reports `OK` *on the crash*: it only
  checks exit≠0 (a crash qualifies) and greps for the substring `starter.symbol_ids`,
  which appears in the *declared-only log line* — not in any finding. The guard
  passes without the audit ever running.

The underlying question the governor named: **must a minimal consumer floor
enumerate risk for all 46 CORE-internal actions, and should any new CORE action
silently brick every consumer until re-synced?** ADR-111 D5 left "keeping the
framework floor in sync with CORE upgrades" as "a separate concern, out of scope
here." T1 forces that concern. This ADR decides it.

## Decision

### D1 — The enforcement/config machinery floor is framework-owned and MUST mirror the framework's authority exactly

Per ADR-075, `action_risk.yaml` and its siblings under `enforcement/config/` are
`framework`-namespace artifacts: they ship with CORE and apply to *any* governed
project. They are **not** adopter-authored law (`project::<external>`), and they are
**not** a curated subset the adopter maintains. The shipped starter floor's
framework-owned configs MUST be a faithful mirror of CORE's canonical
`.intent/enforcement/config/`. Any divergence between the shipped floor and the
running framework's registry is a **framework defect**, not an adopter concern.

The corollary, stated plainly: because a consumer runs CORE's whole engine, the
consumer's `action_risk.yaml` must classify *every* action that engine can
register — including actions the consumer's own rules never invoke. That breadth is
inherent to shipping the engine, not negotiable per adopter.

### D2 — Single source of truth: the floor derives from CORE's canonical config, it is not hand-maintained in parallel

`examples/starter-intent/.intent/enforcement/config/` is **derived from**
`/.intent/enforcement/config/` (CORE's canonical floor), not independently authored.
For `action_risk.yaml` specifically — a domain-neutral `action_id → risk_level`
table — the derived form is a verbatim copy. The starter constitution
(`rules/starter.json`, `constitution/CONSTITUTION.md`) remains separately authored
per ADR-108/111; this ADR governs only the *framework-owned* floor, not the authored
rules layer. `sync-to-demo.sh` already copies starter→demo; the missing direction —
CORE-registry→starter-floor — is what D2 closes.

### D3 — The fail-closed risk gate stays; relaxation is rejected

`apply_risk_config`'s `ConstitutionalError` on an unclassified registered action is
**correct and retained.** It enforces `atomic_actions.impact_level_must_be_governed`
and `governance.no_governance_bypass` ("if a precondition cannot be evaluated,
block"). Relaxing it to let actions execute with ungoverned risk would import this
repo's *development* permissiveness into *runtime* governance — exactly the inversion
CLAUDE.md forbids — and would weaken the guarantee in the very market (regulated GRC,
`CORE-BYOR.md` §7) where fail-closed risk classification is the product. The fix is
to make the shipped floor complete (D1/D2), never to make the gate tolerant.

### D4 — A standing drift-guard enforces floor ⊇ registry, so drift fails loud in CORE's CI — not at an adopter's bootstrap

A deterministic check asserts that the shipped starter floor's `action_risk.yaml`
classifies every action in CORE's registry (`floor.action_ids ⊇ registry.action_ids`).
It runs in CORE's own audit / CI so a newly-added atomic action that is not reflected
in the floor fails CORE's build — the framework catches its own drift before it ships,
rather than an adopter discovering it as an unexplained `core-admin` crash. This is
the durable, enforced form of "add a sync step"; a manual step rots without a standing
rule (the #124→ADR-021→#594 regression is the cautionary precedent).

### D5 — The starter regression guard must prove the audit ran, not pass on a crash

`examples/starter-intent/verify.sh` is corrected to assert positive enforcement:
parse `--format=json`, require a genuine `starter.symbol_ids` **finding** (not a
substring of a log line), and fail on a traceback or `EXIT_INTERNAL_ERROR` (64). A
bootstrap crash must read as RED. The guard's job is to prove the starter *enforces*,
which a crash-then-substring-match never did.

### D6 — Scope, sequencing, and the deferred dependency

- The immediate drift-resync (adding `assisted.apply_diff: moderate` and
  `assisted.validate_diff: safe` to the starter floor, mirroring CORE per D2) is the
  *first application* of D1–D2 and may proceed once this ADR is accepted. It is an
  application of a decided principle, not a fresh decision.
- This ADR governs the **source-tree** floor and CORE's CI guard. It does **not**
  resolve the `.env`/`REPO_PATH` source-tree split (Context, finding 1) — that is a
  source-tree artifact a real consumer never hits, and fully verifying true
  pip-consumer mode still waits on ADR-108 D3 / #674. D4's guard protects the
  *shipped* floor; the wheel-packaging path (#674) is where true-consumer
  verification lands.

## Consequences

- **The on-ramp becomes honest.** An onboarded repo's `core-admin` boots, and the
  delivered four-rule constitution actually enforces — T2 (newcomer docs) is unblocked
  on a verified, not assumed, foundation (UR-07).
- **Drift is structurally impossible to ship silently.** D2 removes the parallel
  hand-maintained copy; D4 fails CORE's build the moment the floor falls behind the
  registry. New atomic actions can no longer brick adopters by omission.
- **The fail-closed posture is preserved** — CORE never executes an action whose risk
  is ungoverned, in its own repo or an adopter's.
- **The drift-guard is real, not decorative.** D5 closes the false-green that let a
  total starter failure read as `OK`.
- **One honesty boundary is restated, not crossed:** true pip-consumer enforcement is
  still pending the wheel (#674); this ADR makes the *source-tree* starter trustworthy
  and keeps CORE's CI honest about floor completeness.

## Alternatives considered

- **Relax `apply_risk_config` to tolerate missing entries (governor option b).**
  Rejected — D3. It would let actions run with ungoverned risk, weakening a
  constitutional invariant and importing dev-permissiveness into runtime.
- **Add a manual CORE→starter sync step (governor option c).** Rejected as the
  *primary* mechanism: a documented step without enforcement rots (memory of
  closures-without-rules regressing). Adopted only in its enforced form — D4.
- **Treat the floor as an adopter-curated subset.** Rejected — contradicts ADR-075
  (the floor is framework-owned) and is unworkable: the adopter runs the whole engine
  and so inherits the whole registry; a subset cannot satisfy the fail-closed gate.

## References

- `CORE-BYOR.md` — §3 (the Repository floor), §8 (ADR-075 framework/project split,
  byor.py disposition); this is grounded work under that paper's §9.
- ADR-075 — framework/project namespace split (the floor is `framework`-owned).
- ADR-108 — external adoption ships a minimal authored starter + machinery floor
  (D3 machinery-in-wheel, the deferred true-consumer dependency / #674).
- ADR-111 — onboard delivers the authored starter; **D5 deferred floor-sync, decided here.**
- ADR-008 — impact_level is governed in `action_risk.yaml`, not embedded in `src/`.
- `src/body/atomic/registry.py` (`apply_risk_config`) — the fail-closed gate retained by D3.
- `examples/starter-intent/.intent/enforcement/config/action_risk.yaml`,
  `examples/starter-intent/verify.sh` — the artifacts D2/D5 correct.
- `CORE-BYOR-Program-Backlog.md` — T1 (this ADR closes the gate), T2 (unblocked).
