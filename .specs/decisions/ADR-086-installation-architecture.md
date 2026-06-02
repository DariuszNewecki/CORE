<!-- path: .specs/decisions/ADR-086-installation-architecture.md -->

# ADR-086 — Installation Architecture

**Date:** 2026-06-02
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-02 — drafted under Path A execute-verb authorization, "draft ADR-086" + governor confirmation of expanded scope after the F-10.3 / installation-script memory thread surfaced the Band E Track 2 ADR trigger and the `lira_user`/`core_db` ownership split)
**Grounding papers:** `papers/CORE-Product-Tiers.md` §3.1 ("First findings visible within minutes of installation" — F-10's deployment claim); `commercial/CORE-Competitive.md` §"Setup cost" — install friction explicitly named as competitive disadvantage; `commercial/CORE-Market-ICP.md` §"longest horizon" — install story named as the hard problem; `planning/archive/CORE-band-E-planning-input-2026-05-16.md` §Track 2 — the original "ADR trigger: Installation architecture ADR before any packaging work" pre-declaration this ADR honors.
**Related:** ADR-084 D7 §4 (library-grade openness — F-48 is the library distribution; this ADR is the *product* distribution); ADR-085 D1 (operational completeness as engineering's sole goal — installation is a precondition of completeness because Tiers §3.1 names installation in F-10's deployment claim); F-10.3 #530 (CI gate Action + Dockerfile — one slice of this architecture); F-48 #527 (PyPI publish — different surface, treated separately here); F-47 #526 (managed Qdrant — operator choice, out of self-host install scope); #536 (the schema ownership split this ADR's D4 canonicalises away).

---

## Context

### Why this ADR exists, and why now

`.specs/planning/archive/CORE-band-E-planning-input-2026-05-16.md` §Track 2 names "Installation & Upgrade" as a strategically-distinct planning track and pre-declares an explicit ADR trigger: *"ADR trigger: Installation architecture ADR before any packaging work."* That sentence is doing load-bearing work. It exists specifically to prevent the failure mode of shipping a Dockerfile (F-10.3), then a pip wheel (F-48), then a managed-service config (F-47), then a Solo install script — each invented separately, each making incompatible choices about DB provisioning, first-run wizard semantics, pre-flight checks, and upgrade paths.

F-10.3 reconnaissance (2026-06-02) hit exactly this trigger. The narrow F-10.3 work (action.yml + Dockerfile for the CI gate) cannot honestly proceed without acknowledging that it's the first packaging unit to ship, and that its choices implicitly establish patterns for everything downstream. Two things compound:

1. **The install story is already named a competitive disadvantage.** `commercial/CORE-Competitive.md` §37 contrasts *"A copilot is one extension install. CORE is a runtime with..."*. `commercial/CORE-Market-ICP.md` §35 names install story as "longest horizon" hardest problem. Solving it ad-hoc one tier at a time amplifies the disadvantage.

2. **The reconnaissance surfaced an active growth-pain.** `infra/sql/db_schema_live.sql` shows the `core` schema with 28 objects owned by `lira_user` (the developer's Linux account) and 76 by `core_db` (the canonical service role). This breaks `pg_dump`+restore, breaks fresh production install, and would break any first-run wizard a customer might encounter. Tracked separately as #536; the ADR canonicalises the role decision the cleanup migration implements.

### What "installation" actually means here

This ADR uses "installation" to mean the entire path from *a customer first encountering CORE* to *CORE running successfully in their environment*. Not just the bytes-on-disk step. Specifically:

| Phase | What happens | Today (informally) | This ADR (canonical) |
|---|---|---|---|
| Discovery | Customer learns CORE exists | F-10 Action in PR (when shipped); GitHub README | F-10 stays the discovery surface (Tiers §2 funnel); README documents the install paths this ADR defines |
| Distribution | Bytes reach the customer's machine | git clone | Three channels per D1: pip, Docker, install script — each with declared role |
| Provisioning | DB, Qdrant, `.intent/` scaffold appear | Manual `psql`, manual scaffold | First-run wizard (D2) drives a single command from clean machine to working `.intent/` |
| Verification | "Did it actually work?" | "Try running `core-admin code audit`" | Health-check / readiness probe (D5) returns a structured pass/fail |
| Upgrade | New version replaces old | Manual `git pull` + manual migration run | Versioned upgrade path with rollback (D6) |

The current state is "git-clone + manual everything." This ADR is the bridge from that to the funnel architecture Tiers §2 describes.

### The five-tier picture this ADR has to fit

Each tier has a distinct install profile. The architecture is not five separate stories; it is one architecture with tier-specific specialisations.

| Tier | Install posture | Distribution unit | First-run state |
|---|---|---|---|
| Audit (F-10) | CI / pre-commit; no daemon, no DB, no Qdrant | Reusable GH Action (F-10.3), pre-commit hook (F-10.5), Docker image | `.intent/` from the consumer's repo; F-10.1a stateless runner |
| Solo | Single dev machine; full daemon + Postgres + Qdrant | pip + Docker Compose, OR install script bundling both | DB initialised, `.intent/` scaffolded, first audit runs clean |
| Team | Multi-user; shared infra | Docker Compose / Helm chart against customer Postgres + Qdrant | DB initialised with multi-user RBAC schema (runtime fork) |
| Enterprise | Air-gapped or regulated; on-prem | Signed Docker images + offline installer | Validated install package, IQ/OQ-shaped (regulated industries) |
| Embedded | Library inside another product | F-48 PyPI / Docker registry library | Embedder owns their install; CORE only provides the library |

The Audit and Solo install paths are in immediate ADR-085 scope (operational completeness gate items). Team / Enterprise / Embedded are stamped commercial per ADR-083 / ADR-084 and out of engineering scope until exit; their install profiles are described here so the architecture survives them, not implemented.

### Why the F-10.3 narrow scope is structurally insufficient

F-10.3 alone is "ship a Docker image and an action.yml." That's a packaging unit, not an install. Without this ADR's surrounding decisions, F-10.3 would silently make choices that bind every downstream surface:

- Which Python version the image runs (ripples to F-48 wheel targets, Solo's pip install, Enterprise's air-gap image)
- How `.intent/` is mounted (ripples to first-run wizard semantics for Solo)
- What "DB unavailable" means (ripples to pre-flight checks; today the stateless runner survives this by skipping DB rules, but Solo expects a real DB)
- What exit codes mean for "install broken" vs "install fine, findings exist" (already partially settled by F-10.1b's `EXIT_CONFIG_ERROR` vs `EXIT_FINDINGS` distinction, but the boundary needs to extend to pre-install probes)

The right pattern: ADR-086 makes the architectural decisions; F-10.3 implements the Audit-tier slice of them; F-48 implements the library-distribution slice; Solo/Team/Enterprise install pieces (when commercial work resumes after ADR-085 exit) implement their slices.

---

## Decisions

### D1 — Three distribution channels, each with a declared role

CORE ships through three distribution channels. Each has a single declared purpose; mixing them is forbidden by construction.

1. **PyPI (F-48)** — the library distribution. Python developers running `pip install core-runtime` get the importable Python package. Used by runtime forks (ADR-084 D4), third-party plugins (ADR-084 D2), and the install-script + Docker-image build pipelines themselves. This is the foundation; everything else is built on top.

2. **Docker registry** — the runtime distribution. Both first-party (`core-engine` for Solo+, `core-audit-gate` for F-10.3 Audit) and operator-controlled (customers build their own image from a published base for air-gap deployments). Versions of the Docker image are pinned to the same semver as the PyPI release (per D7).

3. **Install script (`install.sh` + Windows-PowerShell sibling)** — the operator-facing distribution. A single curl-able script that detects the host platform, verifies pre-flight conditions (D3), pulls the appropriate Docker image (or pip wheels), provisions the DB (D4), scaffolds `.intent/` (D2), and prints a "next step" pointer. This is the "first-findings-within-minutes" surface Tiers §3.1 commits to.

**Forbidden combinations:** the install script MUST NOT contain bundled Python code that duplicates what the PyPI package provides. The Docker image MUST NOT contain a `pip install` step that pins to a non-published SHA. The PyPI package MUST NOT contain installer scripts. Each channel does one job; cross-channel concerns flow through the contracts D7 defines.

### D2 — First-run wizard, single declared command

CORE provides a single command — `core-admin init` — that performs the first-run wizard. The command is idempotent: re-running it on a configured installation is a no-op that reports the state.

Scope of `core-admin init`:

1. Detect or accept `--db-url` and `--qdrant-url` (Solo: localhost defaults; Team+: customer-supplied)
2. Verify pre-flight conditions per D3; abort with `EXIT_CONFIG_ERROR` on any failure
3. Apply schema migrations from a clean baseline (D4 canonical-role provisioning)
4. Scaffold `.intent/` from a documented seed (the existing `.intent/` in this repo serves as the seed pattern)
5. Run a smoke audit against the scaffolded `.intent/` to prove the install is functional
6. Print a structured success record with `next-step` URLs

Tier-specific extensions ride on `core-admin init` as flags or follow-on commands, not separate wizards. Audit-tier customers don't run `init` at all (the CI gate has no DB or Qdrant to provision — it just runs the stateless audit from F-10.1a).

### D3 — Pre-flight checks, declared and machine-checkable

A pre-flight check is a single question with a single structured answer. The full set lives in `.intent/operational/pre_flight_checks.yaml` (new) so customers and CI consumers can read the contract.

Minimum set:

- Python version >= 3.12 (matches CLAUDE.md tech stack declaration)
- Postgres reachable + version >= 15 (Solo+ only)
- Qdrant reachable + API responsive (Solo+ only)
- Local LLM endpoint reachable OR external LLM API key present (Solo+ only; the per-resource model from ADR-052 governs which is required)
- Disk space >= 2 GB free in the install target directory
- `.intent/` is either absent (clean install) OR present and validates against the META schemas (upgrade install)
- For each schema object created in the DB: owner equals the configured canonical role (the regression guard for the #536 cleanup; documented here as the cross-cutting pre-flight rule)

Pre-flight checks run before any state-mutating step. Failure is `EXIT_CONFIG_ERROR` (matches F-10.1b's already-shipped exit code semantics).

### D4 — Single canonical Postgres role; ownership leakage prohibited

The canonical Postgres role for CORE schema objects is `core_db`. The Linux account that runs the installer or migration MUST NOT appear as an owner of any schema object after `core-admin init` completes.

The migration that consolidates the current 28/76 split (#536) is the one-shot fix for the existing state. After it lands:

- Every new migration MUST create objects under `core_db`. Tooling enforces this via a CI grep on the dump.
- The pre-flight check (D3) asserts single-owner state and fails the install if violated.
- `pg_dump` + restore to a fresh DB without a `lira_user` role succeeds; that becomes a release-pipeline test.

`feedback_ambient_identity_leakage_in_declared_infra` captures the broader pattern (Linux user becoming a second owner in Postgres / files / configs / YAML literals); D4 here is the Postgres-specific instance, but the discipline generalises and the memory points future investigations at sibling surfaces.

### D5 — Health check / readiness probe

A single command — `core-admin health` — returns a structured JSON record describing the install's state. Suitable for:

- Smoke verification immediately after `core-admin init`
- Kubernetes / Docker readiness probes (Team+ deployments)
- Periodic monitoring (any tier)

Output shape:

```json
{
  "verdict": "OK" | "DEGRADED" | "FAILED",
  "components": {
    "database":   {"status": "...", "version": "...", "owner_check": "pass|fail"},
    "qdrant":     {"status": "...", "version": "..."},
    "intent_dir": {"status": "...", "schema_version": "..."},
    "llm":        {"status": "...", "provider": "local|external"},
    "daemon":     {"status": "...", "pid": ..., "uptime_sec": ...}
  },
  "checked_at": "ISO-8601"
}
```

Exit codes mirror F-10.1b (`EXIT_OK` for verdict=OK, `EXIT_FINDINGS` for DEGRADED, `EXIT_INTERNAL_ERROR` for FAILED).

### D6 — Upgrade path: versioned, rollback-capable, with a single command

`core-admin upgrade` performs an in-place upgrade between consecutive minor or patch versions. Major-version upgrades require a separate documented procedure (out of scope for this ADR; declared so the constraint is visible).

Scope of `core-admin upgrade`:

1. Capture the current schema version + a backup snapshot of `core.audit_runs`, `core.blackboard_entries`, and `core.autonomous_proposals` (the three load-bearing tables for state recovery)
2. Run the migration sequence between current and target versions
3. Re-run the pre-flight checks (D3) against the new state
4. On any failure: print the rollback command (`core-admin upgrade --rollback <snapshot_id>`) and exit `EXIT_INTERNAL_ERROR` without committing the partial state

The rollback command restores the snapshot and downgrades the migration table. Rollback to an arbitrary version is out of scope; only the immediately-previous snapshot is supported. Customers wanting deeper history take their own `pg_dump`.

### D7 — Cross-channel contracts: semver + provenance

The three distribution channels (D1) share a single versioning contract:

- PyPI release `X.Y.Z` exists if and only if Docker image `core-engine:X.Y.Z` exists.
- The install script downloads pinned versions; it does not resolve "latest" implicitly.
- Each release artifact carries a signed SBOM (software bill of materials) so customers can audit the dependency graph.
- A release version monotonically increments. Re-tagging a released version is prohibited — corrections ship as a new patch version.

Semver semantics:

- Major: any constitutional change (new mandatory pre-flight check, removed CLI command, schema migration that requires manual operator action)
- Minor: new optional features, new schema migrations that auto-apply, new exit codes (additive only)
- Patch: bug fixes, performance improvements, no contract surface change

### D8 — Out-of-scope (named for foreclosure)

This ADR explicitly does NOT decide:

- **Air-gapped installer for Enterprise tier (F-38).** That commercial-tier installer is its own ADR when commercial engineering work begins (post ADR-085 exit). The contracts D1/D5/D7 will be reused; the offline-bundle mechanism is the new piece.
- **Managed-service automation for F-47.** A customer using managed Qdrant points their `core-admin init --qdrant-url ...` at the managed endpoint; the operator runs whatever automation manages the managed-service offering. F-47's contracts live elsewhere.
- **Helm chart for Team-tier Kubernetes deployments.** Team is post-exit; Helm wraps D1's Docker channel.
- **Windows installer parity beyond PowerShell `install.ps1`.** A native MSI / wix is out of scope; the PowerShell sibling handles the Windows path.
- **Linux package manager integration (apt/yum/brew).** These are downstream of D1's install script; package maintainers can wrap the install script if they choose.
- **Migration from a non-CORE governance tool.** Customers transitioning from a non-CORE state machine to CORE is not an install flow; it's a separate concern.

---

## Consequences

### Unblocks the F-10.3 work without it being ad-hoc

F-10.3 (action.yml + Dockerfile for the CI gate) is now the Audit-tier slice of D1. Specifically:

- The Docker image F-10.3 publishes is `core-audit-gate:X.Y.Z` per D7 versioning
- The Action wraps `core-admin code audit --offline --format=github-annotations`
- The image's `core-admin` invocation MUST NOT do anything outside the F-10.1a stateless path; the Audit tier has no DB, no daemon
- The image gets its own minimal Dockerfile that pulls from `core-runtime:X.Y.Z` on PyPI

This is a concrete shape for F-10.3 that didn't exist before the ADR. The next session that picks F-10.3 up can implement against it without re-litigating the architectural questions.

### Documents the open-question that's actually decided

`commercial/CORE-Products.md` §"GOVERNOR decisions still open" no longer needs an "install architecture" item — D1/D2/D3/D4/D5/D6/D7 close it. The remaining open questions in that doc (first-SKU selection, repo topology for the runtime fork) stand.

### Re-anchors the broken nightly-audit.yml fix (#534)

#534 (filed earlier today) tracked the broken nightly-audit.yml workflow that references a phantom `src.core.capabilities` module. The fix is now obvious: replace with `core-admin code audit --offline --format=github-annotations` once F-10.3 ships the Docker image, OR remove the workflow if the in-repo nightly is supplanted by the Action running against this very repo (which it would, naturally).

### Makes the schema-ownership split (#536) the canonical first cleanup

D4 declares `core_db` as the canonical role. #536 is the migration that brings the current state into compliance. The two are paired: D4 is the architectural decision, #536 is its implementation. Future migrations that try to create objects under any other owner fail the pre-flight check D3 codifies.

### Connects the previously-stamped commercial features to this architecture

F-47 (Managed Qdrant, ADR-083), F-37 (Regulatory export, deferred per ADR-085 D1), F-38 (Air-gapped deployment guarantee) — each of these has install-architecture surface area. D8 explicitly defers each, but the contract surfaces in D1/D5/D7 are designed to extend cleanly when those commercial features ship.

### Pre-emptively forecloses an entire class of growth-pain

ADR-085 D7 already committed that "if the open base regresses (e.g., a feature transitions back from `shipping` to `partial`), the governor may re-impose the operational-completeness constraint." Without an installation architecture, the open base would regress in exactly this way — each new packaging shape (Audit Action, Solo install, Team Helm, etc.) would slightly drift the install behaviour and the "fully operational" claim would become harder to honestly assert over time. D1-D7 lock the architecture in advance.

### Two implementation-tracking issues filed in this session

- #534 — nightly-audit.yml broken (one-shot fix; now has a clear target: rewrite against F-10.3's Action)
- #536 — schema ownership cleanup (the D4-implementation migration)

Both should be picked up early in the next session per the "growth-pains cleanup" lead the governor named.

### What this ADR does NOT change

- ADR-085 D1's "engineering capacity routes only to the 5+3 list until exit" stays binding. This ADR is governance-frame work (ADR-085 D2 allowed) that anchors future engineering, not engineering itself.
- The F-10 sub-issue decomposition (#528-#535) stays. F-10.3 now has a concrete shape per the §Consequences above.
- The tracker doc `planning/CORE-Operational-Completeness.md` does not need updating for ADR-086 itself — the gate items are unchanged.

---

## Verification

- ADR file exists at `.specs/decisions/ADR-086-installation-architecture.md`.
- ADR explicitly honors the Band E Track 2 ADR trigger from `planning/archive/CORE-band-E-planning-input-2026-05-16.md` (cited in §Context and the Drafter line).
- ADR D4 names `core_db` as the canonical Postgres role; the cleanup migration referenced by #536 implements it.
- ADR D1 lists exactly three distribution channels (PyPI/Docker/install script) and names them as mutually exclusive in role.
- The CI/CD gate (F-10.3) is named in §Consequences as the Audit-tier slice of D1, not as the architecture itself.
- F-10.1a/F-10.1b/F-10.2 are referenced (not modified) — they form the offline-audit primitive this architecture builds atop.

---

## References

- `planning/archive/CORE-band-E-planning-input-2026-05-16.md` §Track 2 — the pre-declared ADR trigger this ADR honors.
- `commercial/CORE-Competitive.md` §"Setup cost" — install friction as competitive disadvantage.
- `commercial/CORE-Market-ICP.md` §"longest horizon" — install story named as hard problem.
- `papers/CORE-Product-Tiers.md` §3.1 — F-10's "first findings within minutes of installation" claim that this ADR makes structurally honest.
- ADR-084 D7 §4 — library-grade openness; F-48 is the library distribution this ADR composes with.
- ADR-085 D1 — engineering-capacity constraint; this ADR is governance-frame work (D2-permitted) that anchors future engineering.
- Memory `feedback_ambient_identity_leakage_in_declared_infra` — pattern memory for the class of issue D4 forecloses on the Postgres surface.
- #534 — nightly-audit.yml broken; now has a concrete fix target via this ADR.
- #536 — schema ownership cleanup; the D4-implementation migration.
- ADR-052 — `core.llm_resources` per-resource model; D3's LLM pre-flight check derives from it.
