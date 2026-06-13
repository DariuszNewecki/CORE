---
kind: adr
id: ADR-050
title: ADR-050 — CLI is a standalone HTTP client; `src/cli/` extracted from CORE
status: accepted
---

<!-- path: .specs/decisions/ADR-050-cli-positioning.md -->

# ADR-050 — CLI is a standalone HTTP client; `src/cli/` extracted from CORE

**Status:** Accepted (revised 2026-05-17 — supersedes original 2026-05-15 text)
**Date:** 2026-05-15
**Revised:** 2026-05-17
**Authors:** Darek (Dariusz Newecki)
**Closes:** CLI governance gap surfaced by 2026-05-15 full architecture audit
**Resolves deferred:** Network-boundary decision from original §"Deferred decision"
**Relates to:** ADR-049 (doctrine-rule parity), ADR-053 (API as governance interface),
ADR-054 (API Phase 1), CORE-Mind-Body-Will-Separation paper §2 / §6

---

## Context

The original 2026-05-15 text of this ADR established that CLI is outside CORE's
three-layer model and enforced a logical boundary: CLI may only import `api.*`,
not `will.*`, `body.*`, `mind.*`, or `shared.*` directly. It deferred the
stronger alternative — a network boundary where CLI makes HTTP calls to the
running CORE daemon and has zero CORE module imports — pending operational
validation.

That deferral produced `architecture.cli.api_only`, which fired immediately
against ~499 import sites across `src/cli/`. Those 499 findings are not
individually remediable: no remediator is mapped for the rule, the autonomous
loop cannot migrate CLI commands to HTTP on its own, and the API endpoints the
migration requires do not yet exist for most commands. The result was 499
governance findings accumulating with no resolution path — a Convergence
Principle violation embedded in the ADR itself.

The deferred question is now answered: CLI is a standalone client application.
It calls CORE over HTTP. It has no knowledge of CORE's internal module
structure. The logical boundary (import rule) is the wrong instrument for this
boundary; physical separation is the right one.

---

## Decision

### D1 — The deferred network-boundary decision is resolved: HTTP only

CLI communicates with CORE exclusively over HTTP via the API. No Python import
from any `src/` module — including `api.*` — is permitted in CLI. The
interaction topology is:

```
Operator → CLI (standalone process) → HTTP → src/api/ → Will → Body / Mind
```

CLI has no in-process coupling to CORE. The boundary is physical, not logical.

### D2 — `src/cli/` is extracted to a separate repository

`src/cli/` ceases to be part of the CORE codebase. It becomes a standalone
repository (`core-cli` or equivalent), developed, versioned, and deployed
independently. Its only dependency on CORE is the HTTP API contract.

Extraction is a migration, not an immediate deletion. The migration sequence
is defined in the Resolution section below.

### D3 — Will may not import from CLI (already satisfied)

The 5 reverse imports identified in the original ADR-050 (`src/will/workflows/phases/`
importing `cli.commands.*` and `cli.logic.*`) were resolved prior to this
revision. As of 2026-05-17, `grep -rE '^(from cli\.|import cli\.)' src/will/`
returns zero results across the entire subtree. D3 is complete; it is not a
prerequisite step for extraction — it is a closed condition to maintain.

### D4 — `architecture.cli.api_only` is disabled during migration; retired on extraction

The rule `architecture.cli.api_only` was authored under the original ADR's
logical-boundary model. Its 499 findings are not individually fixable — they
dissolve when `src/cli/` is extracted. Continuing to fire 499 governance
findings against an in-progress migration creates noise without signal.

The rule is disabled (not suppressed) for the duration of the extraction
migration. A single tracking issue replaces the per-finding audit output as
the migration backlog surface. On extraction completion, the rule is retired
from `.intent/enforcement/mappings/architecture/layer_separation.yaml`
entirely — it governs a module that no longer exists in this repository.

### D5 — `src/api/cli/client.py` remains in CORE

`src/api/cli/` is CORE's own HTTP client library for the API — used internally
for testing and API-to-API invocations. It is not the operator CLI. It remains
in `src/` and is unaffected by this ADR.

### D6 — Architecture paper updated

`CORE-Mind-Body-Will-Separation.md` §2 and §6 are updated to show CLI as an
external application. CLI does not appear inside the system boundary diagram.
The topology diagram at §6 is updated per D1.

---

## Resolution sequence

1. ~~Resolve Will → CLI inversions (D3).~~ **Already complete.** Verified
   2026-05-17: zero `from cli.*` / `import cli.*` in `src/will/`.

2. **Disable `architecture.cli.api_only` (D4).** Open a single tracking issue
   titled "CLI extraction migration backlog" under the active band milestone.
   The tracking issue replaces the 499 individual audit findings as the
   migration surface.

3. **Implement API endpoints per ADR-054 phase map.** As each API phase
   delivers endpoints, the corresponding CLI commands can be migrated to HTTP
   calls and removed from `src/cli/`. Phase 1 (ADR-054: `/audit`,
   `/proposals`) is the first batch.

4. **Extract `src/cli/` to a separate repository.** When the API surface is
   sufficient to cover the operator use cases currently in `src/cli/`,
   `src/cli/` is removed from this repository and replaced by the standalone
   `core-cli` client. Residual commands without API equivalents are either
   given API endpoints first or retired.

5. **Retire `architecture.cli.api_only` (D4).** Once `src/cli/` does not exist
   in this repository, the rule is removed from the enforcement mappings.

---

## Consequences

### Positive

- **499 governance findings dissolve.** The divergence they were causing is
  resolved structurally, not by fixing 499 individual sites.
- **The boundary is physically unbreakable.** No import rule is required to
  enforce what a separate repository makes architecturally impossible.
- **API completeness is forced.** Every operator capability CLI exposes must
  have an API endpoint. There is no in-process shortcut.
- **CLI can evolve independently.** Versioning, packaging, and distribution of
  the operator client decouples from CORE's release cycle.
- **Will → CLI inversions eliminated.** CORE stops depending on its own
  operator client.
- **GxP / audit trail.** Every operator action becomes an HTTP request logged
  by the API — per-request attribution (ADR-053 D7) is a natural consequence.

### Negative

- **Every CLI command requires a running daemon.** Operator commands that
  previously ran in-process now require the CORE daemon to be reachable. This
  is the accepted operational cost of the network boundary.
- **API must grow to cover all current CLI capabilities.** Commands that reach
  Body/Mind for diagnostics, administrative operations, or one-off queries need
  API endpoints authored before the corresponding CLI commands can be migrated.
  The ADR-054 phase map governs this sequencing.
- **Migration is not atomic.** `src/cli/` persists in the repository until
  the API surface is sufficient. The tracking issue is the migration backlog;
  it is treated as tracked debt, not normal operating state.

### Neutral

- Operator user experience does not change during migration. Commands continue
  to work; the change is in their implementation.
- `src/api/cli/client.py` is unaffected (D5).

---

## Verification

This ADR is verified when:

1. **`src/cli/` does not exist in this repository.** A `find src/cli` returns
   nothing.
2. **Zero Will → CLI imports exist.** `grep -r 'from cli\.' src/will/` and
   `grep -r 'import cli\.' src/will/` return no results.
3. **`architecture.cli.api_only` is absent from enforcement mappings.** The
   rule has been retired from `layer_separation.yaml`.
4. **The tracking issue is closed.** All CLI commands have been migrated to
   HTTP or explicitly retired.
5. **Architecture paper §2 and §6 reflect D6.** CLI appears outside the system
   boundary diagram.

---

## References

- `.specs/papers/CORE-Mind-Body-Will-Separation.md:§2` — "exactly three
  layers" claim.
- `.specs/papers/CORE-Mind-Body-Will-Separation.md:§6` — API as sole governed
  entry point.
- ADR-049 — doctrine-rule parity.
- ADR-053 — API as resource-oriented governance interface.
- ADR-054 — API Phase 1 (`/audit`, `/proposals`); first migration batch.
- `.intent/enforcement/mappings/architecture/layer_separation.yaml` —
  target file for rule disable and eventual retirement.
