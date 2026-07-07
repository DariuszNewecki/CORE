---
kind: adr
id: ADR-145
title: 'ADR-145 — Process-Mode Provenance and Startup Mechanism'
status: accepted
---

<!-- path: .specs/decisions/ADR-145-process-mode-provenance.md -->

# ADR-145 — Process-Mode Provenance and Startup Mechanism

**Status:** Accepted
**Date:** 2026-07-07
**Governing paper:** `.specs/papers/CORE-Capability-Scoped-Filesystem-Authority.md`
**Authors:** Darek (Dariusz Newecki)
**Closes:** #492
**Deferred from:** `CORE-Capability-Scoped-Filesystem-Authority.md` §9
**Relates to:** ADR-110 (exposure trust tiers), ADR-086 (pre-flight checks)

---

## Context

`CORE-Capability-Scoped-Filesystem-Authority.md` §6 establishes a process-level
mode flag — *development* or *live* — as a constitutional declaration of who is in
the loop. The chokepoint uses this flag to decide whether a capability's `.intent/`
or `.specs/` write permission is honored in the current process.

The paper's §6 fail-safe says "the default on uncertainty is *live*." This
defends against an absent or malformed mode signal. It does not defend against a
forged development signal in a live deployment — a live process that misreports
itself as development and thereby unlocks capability-mediated writes to governed
namespaces.

The paper's §9 explicitly defers the mode-flag startup mechanism and its
provenance guarantees to this ADR.

**Forward-looking status.** This ADR is not a blocker for current operations.
CORE is operated by its governor on its own development repository; the
development-mode write path is the operating premise. Provenance-forgery as an
attack surface becomes load-bearing only when CORE is deployed to operate
unattended on a third-party codebase or as a hosted service. The trigger
condition for requiring implementation of the mechanism below is given in D6.

---

## Decisions

### D1 — The process-mode flag has exactly two canonical values

The flag's canonical values are `development` and `live`. They are not equivalent
to the deployment-mode (`solo` / `multi_user`) declared in
`.intent/enforcement/config/deployment_mode.yaml` — that governs access-control
trust tiers. The process-mode flag governs filesystem authority: who is in the
loop for privileged writes.

### D2 — The mode flag is read at process startup from two sources with strict precedence

Sources, in descending precedence:

1. **Environment variable** `CORE_PROCESS_MODE` — explicit, per-invocation.
   Values: `development` or `live` (case-insensitive). Any other value is a
   malformed signal; the process MUST treat it as `live` and log a
   `governance.mode_provenance.malformed_signal` finding.

2. **Bootstrap config** `.intent/enforcement/config/process_mode.yaml` — durable,
   per-repository. Declared as:
   ```yaml
   mode: development  # or: live
   ```
   If the file is absent or unparseable, this source is treated as absent (not
   malformed); no finding is posted.

The environment variable always wins over the bootstrap config. This is
intentional: an operator deploying in a container or CI environment can
explicitly override the repository default without editing checked-in config.

If neither source is present, the mode defaults to `live` per the paper's §6
fail-safe.

### D3 — The mode flag is immutable for the lifetime of the process

Once set at startup, the mode value MUST NOT be changed by any runtime path,
configuration reload, or API call. A request to change mode at runtime MUST
be rejected as a constitutional violation. Restart is the only path to a
different mode.

### D4 — Conflicting sources are themselves a governance finding

If `CORE_PROCESS_MODE=development` and the bootstrap config declares `mode:
live`, the sources conflict. The environment variable wins (D2), but the
conflict MUST be posted as a `governance.mode_provenance.source_conflict`
finding at startup. The finding is reporting-severity, not blocking — it does
not prevent the process from starting, but it surfaces the discrepancy for
governor review.

The symmetric case (`CORE_PROCESS_MODE=live`, config says `development`) is
NOT a conflict by this rule: a more-restrictive override does not threaten
provenance integrity. No finding is posted for this case.

### D5 — Every privileged-write authorization logs the mode value and its provenance source

When the chokepoint authorizes a write to a protected namespace (`.intent/`,
`.specs/`), the audit record for that authorization MUST include:

- `mode`: the effective mode value (`development` or `live`)
- `mode_source`: which source produced the effective value
  (`env_var`, `bootstrap_config`, or `default_live_fallback`)

This ensures every privileged write is auditable back to the provenance source
that permitted it.

### D6 — Trigger condition for implementation

The startup-mode mechanism described in D2–D5 MUST be implemented before any of
the following conditions is met:

1. CORE operates unattended on a third-party codebase (any deployment outside
   the governor's direct operation).
2. A second non-governor process begins running CORE code against the same
   `.intent/` tree.
3. The paper's §6 "default on uncertainty is live" fail-safe becomes
   load-bearing for an actual deployment decision.

Until a trigger condition is met, the existing runtime (which reads the mode
from `CORE-Capability-Scoped-Filesystem-Authority.md`'s behavioral description)
is acceptable. The absence of trigger conditions is the reason this ADR is
accepted as doctrine while the implementation is deferred.

---

## Verification

This ADR is verified when:

1. `CORE_PROCESS_MODE` env var is read at startup and its value logged with
   `mode_source: env_var`.
2. `.intent/enforcement/config/process_mode.yaml` is read as the fallback source
   and logged with `mode_source: bootstrap_config`.
3. A missing or unparseable mode signal defaults to `live` and logs
   `mode_source: default_live_fallback`.
4. A malformed signal value posts a `governance.mode_provenance.malformed_signal`
   finding and defaults to `live`.
5. A `development`/`live` source conflict posts
   `governance.mode_provenance.source_conflict` (D4).
6. Every chokepoint authorization log includes `mode` and `mode_source` fields.
7. A runtime mode-change request is rejected with a constitutional-violation error.

Verification is required before any trigger condition in D6 is met.

---

## References

- `CORE-Capability-Scoped-Filesystem-Authority.md` §6, §9 — governing paper;
  defines mode semantics and the fail-safe
- ADR-110 — exposure trust tiers (deployment-mode, distinct from process-mode)
- ADR-086 — pre-flight checks (startup validation context)
- `.intent/enforcement/config/deployment_mode.yaml` — sibling config for
  deployment-mode (`solo`/`multi_user`); process-mode config follows the same
  pattern
- Issue #492 — this issue
