---
kind: adr
id: ADR-110
title: ADR-110 — Exposure is a Trust Tier on the API; Write-Safety Binds to the Operation
status: accepted
---

<!-- path: .specs/decisions/ADR-110-exposure-trust-boundary.md -->

# ADR-110 — Exposure is a Trust Tier on the API; Write-Safety Binds to the Operation

**Status:** Accepted (governor-ratified 2026-06-16)
**Date:** 2026-06-16
**Governing paper:** `.specs/papers/CORE-Constitutional-Foundations.md`
**Builds on:** ADR-050 (CLI is a standalone HTTP client), ADR-053 (API as resource-oriented governance interface), ADR-101/106/107 (commit-authorship, per-execution sandbox, declared-production commit-set)
**Supplies:** the authentication/trust boundary ADR-053 explicitly deferred

---

## Context

A gap-analysis of `StrategicAuditor`'s autonomous remediation path (#115) surfaced a
question that turned out to be general, not agent-specific: when a capability mutates
the repository under AI decision-making, what governs it — and does that governance
depend on *how the request arrived* (terminal, HTTP, blackboard)?

Two prior decisions frame the answer and were, until now, in apparent tension:

- **ADR-050** establishes `Operator → CLI (standalone HTTP client) → API → Will → Body/Mind`,
  and forces **API completeness**: *"every operator capability CLI exposes must have an
  API endpoint; there is no in-process shortcut,"* justified by a GxP audit trail (every
  operator action is one logged HTTP request).
- **ADR-053** declared the API the resource-oriented governance interface and **deferred
  exactly one thing**: *"an authentication/trust boundary before any multi-user or
  remote-access deployment. Phase 1 operates under local-only trust."*

Read together, the missing piece is a **trust axis**: under ADR-050's endgame the API is
the *complete* capability surface, but ADR-053's local-only-trust assumption cannot
survive remote or multi-user access. Some capabilities — writing `.intent/`, managing
secrets or the database, controlling worker lifecycle, **self-extension** (autonomous code
generation/modification), approving proposals — must not be reachable by a lower-trust
caller, even though completeness says they are endpoints.

A second confusion compounded it. The instinct was to treat "who may invoke" and "how is
the resulting change made safe" as one question keyed on the entry surface. They are two
orthogonal axes, and conflating them is what left `StrategicAuditor --execute` writing
directly to the working tree with no sandbox and no attribution (#115).

### Current state (ADR-050 migration debt, not the target)

Some CLI commands (`strategic-audit`, `dev refactor`) still run **in-process** with no API
endpoint. These are precisely the "residual commands without API equivalents" ADR-050 step
4 names — migration debt, not a sanctioned in-process surface. This ADR does not bless
them; it states where they must land.

---

## Decision

### D1 — The API/CLI relationship has an exposure (trust) axis, distinct from layer and behavior

Command metadata already classifies *architectural layer* (`mind`/`body`/`will`) and
*behavior* (`read`/`validate`/`mutate`/`transform`). Neither answers **who may invoke**.
This ADR names a third axis, **exposure**, with two tiers:

- **`user-facing`** — safe to serve to a lower-trust, possibly remote caller. Read/inspect,
  audit, coverage, requesting a fix/quality run, submitting findings or proposals for review.
- **`governor-only`** — requires governor trust. Writes to `.intent/`/constitution; secrets
  and direct database access; daemon/worker lifecycle; vector/KG rebuilds; **self-extension**;
  approving or executing proposals (exercising governance authority).

### D2 — Exposure is a tier on the *complete* API, not a CLI-vs-API split

ADR-050's completeness holds: every operator capability is (or becomes) an API endpoint;
there is no in-process shortcut. Exposure is enforced **on the API**, by authentication and
authorization, not by withholding capabilities from it:

- Every capability is an endpoint (ADR-050 ✓; GxP audit trail intact — every action is one
  logged request).
- Each endpoint carries an `exposure` tier. `governor-only` endpoints require governor
  authentication and are **never served to user-facing or remote callers** — this is the
  authentication/trust boundary ADR-053 deferred.
- The CLI remains a thin client. The *governor's* client authenticates as governor and
  reaches the full surface; a *user-facing* client reaches only the `user-facing` subset.

The informal "the CLI can do more than the API" is thereby made precise: it is
**`user-facing-API ⊂ governor-API`** — the same boundary, enforced at the auth layer, not by
in-process shortcuts.

### D3 — Write-safety binds to the operation, never to the transport or the trust tier

Trust answers *may I run this*; it does **not** answer *is the change correct*. A
governor-trusted operation that delegates to an LLM can still produce a wrong write. So the
mistake-protection rails — per-execution sandbox (ADR-106), declared-production commit-set
(ADR-107), commit-authorship attribution (ADR-101) — apply to **every** repository mutation
that delegates to AI, regardless of exposure tier or entry surface. A `governor-only`
mutation is not exempt from reversibility and attribution because the governor is trusted;
the trust was in the decision to run it, not in the output.

### D4 — Self-extension is a Governor-role capability

Autonomous remediation-campaign execution (and any capability that generates or modifies
production code under AI decision-making) is `governor-only`. It MUST NOT be `user-facing`
and MUST NOT run unattended (scheduled/sensor-triggered) under the directed-invocation
model. If a future design schedules self-extension without a governor in the loop, it leaves
the governor-trust model and MUST route through full proposal gating (approval + sandbox +
commit-set + attribution), per the daemon's model. (#115 is the first instance: its
`--execute` stays governor-only; its write acquires the D3 rails.)

### D5 — `exposure` is a metadata field; the accessibility overview is derived, not hand-maintained

`exposure` is added to the command/endpoint metadata model (`shared.cli.command_meta`,
mirrored on API route declarations) as a required classifying field. The
command-accessibility overview is **derived** from that metadata plus the API router — a
generated artifact (census-style), never a hand-curated table that drifts. The §Overview
below is an illustrative, dated group-level snapshot, not the authority; the authority is
the generated artifact.

### D6 — In-process commands are migration debt and resolve to governor-tier endpoints

`strategic-audit`, `dev refactor`, and any remaining in-process command are ADR-050 debt.
They migrate to API endpoints carrying `exposure: governor-only`, after which the CLI form
becomes a thin governor-authenticated client — closing the in-process shortcut D2 forbids.

---

## Command-accessibility overview (illustrative, group-level — 2026-06-16)

Derived per D5 from `src/cli/` command groups, `src/api/v1/` route modules, and
`command_meta` `layer`/`behavior`/`dangerous`. This is a dated snapshot for legibility; the
generated artifact is the authority. Leaf-level classification belongs in that artifact.

| Capability group | Tier | API-backed today? |
|---|---|---|
| `inspect`, `audit` (read), `coverage`, `search`, `census`, `status` | user-facing | yes |
| `fix`, `quality`, `lint`, `refactor` (request a reviewable run) | user-facing | yes |
| `proposals` (list / submit for review) | user-facing | yes |
| `lane` (assisted-remediation submit), `knowledge`, `integration` | user-facing | yes |
| `proposals` (approve / execute) | governor-only | yes (auth tier TBD) |
| `daemon`, `sync` (write), `workers` | governor-only | partial |
| `constitution`, `intent` (write), `secrets`, `database`, `vectors` (rebuild), `mind`, `admin` | governor-only | no (CLI-local) |
| `develop` / `dev strategic-audit --execute`, `refactor --execute` (**self-extension**) | governor-only | no (in-process debt → D6) |

Reading: the `user-facing` rows are the externally-safe projection; the `governor-only` rows
are the full operator surface that the governor's client reaches under governor
authentication. Several `governor-only` capabilities are not yet endpoints — that is the
ADR-050 + D6 migration backlog, surfaced honestly rather than implied complete.

---

## Consequences

### Positive

- The trust boundary ADR-053 deferred is now specified, unblocking any multi-user/remote
  deployment story.
- `StrategicAuditor` (#115) and `dev refactor` and the API dev routes all acquire the same
  write-safety rails from one principle (D3), instead of bespoke per-caller plumbing.
- Governance stops leaking into the transport layer: the same mutation gets the same safety
  regardless of how it was reached.
- The GxP audit trail (ADR-050) is preserved — governor-only operations are still logged
  API requests, not invisible in-process actions.

### Negative

- Requires building the authentication/trust boundary (governor vs user-facing auth) that
  was deferred — real work, gated before remote/multi-user exposure.
- `exposure` must be backfilled across existing command/endpoint metadata.
- The in-process commands (D6) need API endpoints authored before their CLI forms become
  pure clients — tracked migration debt, consistent with ADR-050.

### Neutral

- No change to operator UX during migration; the change is in enforcement and metadata.

---

## Relationship to prior decisions

- **ADR-050** is refined, not reversed. "API completeness is forced / no in-process shortcut"
  stands; this ADR adds the trust tier that determines *who is served* each complete endpoint.
- **ADR-053** is completed: this supplies its deferred authentication/trust boundary.
- **ADR-101/106/107** are generalized by D3 from the daemon path to *every* AI-delegating
  mutation regardless of entry surface.
- **ADR-034** (OptimizerWorker deferral) is untouched.

---

## Deferred scope (filed)

- **#670** — the authentication mechanism distinguishing governor from user-facing callers (D2);
  design ADR, not specified here.
- **#671** — the generated command-accessibility artifact and its `exposure` backfill (D5).
- **#672** — #115's write-safety rails (D3/D4) on the StrategicAuditor/`dev refactor`/API-dev-route path.

---

## References

- ADR-050 — CLI is a standalone HTTP client; `src/cli/` extracted from CORE
- ADR-053 — CORE API as Resource-Oriented Governance Interface (deferred trust boundary)
- ADR-101 / ADR-106 / ADR-107 — commit-authorship integrity / per-execution sandbox / declared-production commit-set
- `CORE-Specification-as-Source.md` §4.1 — why the #115 calibration signal is observability, not a compilation pair
- Issue #115 — StrategicAuditor self-extension (the motivating instance)
- `src/shared/cli/command_meta.py` — the metadata model `exposure` extends
