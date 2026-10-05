---
kind: adr
id: ADR-169
title: 'ADR-169 — CORE knows its own state: which law it evaluated, which code it ran, and what it knows about every change'
status: accepted
---

<!-- path: .specs/decisions/ADR-169-core-knows-its-own-state.md -->

# ADR-169 — CORE knows its own state

**Date:** 2026-10-05
**Status:** Accepted 2026-10-05 (governor rulings and one external review incorporated)
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-10-05)
**Grounds:** `governance.no_governance_bypass` ("if a precondition cannot be evaluated, block");
ADR-005 S3 (DEGRADED is never silently PASS); ADR-030 (detect-and-DEGRADE, accepted, never
implemented); ADR-101 / ADR-129 (commit authorship); ADR-148 (consequence chain).
**Relates:** ADR-166 (two governed write surfaces) — orders its unit 5 after this ADR;
ADR-168 draft (external assistants are governed producers); ADR-159 (external-run evidence).
**Evidence:** `var/reports/repo-state-awareness-thesis-20261005.md`.

## Governor rulings (2026-10-05) incorporated

1. **D2 posture:** law not of record is flagged, not paused — a finding plus DEGRADED verdicts;
   autonomous work continues. (Pausing, as ADR-030 does for stale code, was considered and not chosen.)
2. **D4 producer identity:** git author metadata is used now; it is recorded as `git-asserted`
   (not authenticated) and upgraded to `authenticated` when #942 / ADR-132 D10 lands.
3. **Process:** one external review of this draft, then acceptance. No implementation before acceptance.

## Context

CORE governs how it writes. It does not know what state results, or whether something else
changed it. Verified against develop @ b3167fca:

- **Boot compares nothing.** `daemon._run_daemon_locked` runs the schema gate (ADR-162), sweeps
  orphan worktrees and loads workers. No previous HEAD, digest or loaded-code identity is
  recorded, so there is nothing to compare against.
- **The law is re-read, not checked.** `IntentRepository.reload()` runs every audit cycle "so
  rules added to .intent/ after daemon boot become enforceable without a restart". An edit to
  `.intent/` (a `cp`, an editor, an assistant) is enforced on the next cycle. Nothing records
  that the law changed, or whether the new law is committed.
- **State is fingerprinted, then forgotten.** `DbSyncWorker` (AST fingerprints in
  `core.symbols`) and `RepoCrawlerWorker` (byte hashes in `core.repo_artifacts`, `.intent/`
  included) detect change and **overwrite** the old value. Only a count survives.
- **Attribution covers CORE's own commits only.** `CommitAuthorshipAuditWorker` starts from
  `core.proposal_consequences`. Changes made outside a proposal are never examined.
- **ADR-030 was never built.** It decided that the daemon DEGRADEs when the code on disk differs
  from the code it loaded, and noted the mechanism "does not yet exist". `governance.stale_daemon`
  appears nowhere in `src/`.
- **Outside the repository**, `byor.py`, `scout.py` and `project_scaffold.py` leave a log line
  and nothing else. ADR-159 external runs are the exception: fingerprinted per-run evidence.

The consequence: a governed change and an ungoverned one look identical to CORE, at boot and while
running. A verdict cannot say which law produced it. ADR-166 unit 5 would extend CORE's write
reach to places it cannot observe at all.

What this ADR does **not** claim: that direct writes are forbidden. ADR-168 D1 holds — a
producer may write bytes directly. What must hold is that CORE *knows*: which law it is
enforcing, which code it is running, and what evidence it has about where each change came from — no more than that evidence supports.

## Decisions

### D1 — A state ledger, append-only

CORE records an observation of its own state at daemon boot and on every audit cycle:
repository HEAD, whether the working tree differs from HEAD (and in which paths), a digest of
`.intent/`, and the identity of the code the daemon loaded. Observations are **appended**, never
overwritten, so any two points in time can be compared. The existing hashes
(`repo_artifacts.content_hash`, `verify_floor`'s sha256 manifest) are the building blocks; the
new property is history.

### D2 — Every verdict states the law it evaluated and its relation to the law of record

Two laws are distinguished:

- **law of record** — `.intent/` as committed at HEAD (commit + digest);
- **law evaluated** — the live `.intent/` the audit actually read (digest).

Every audit verdict records both and their **relationship**: `MATCH` or `DRIFT`. With `MATCH`, the
verdict is decided as today (PASS remains possible). With `DRIFT`, CORE:

- posts a finding naming the `.intent/` paths that differ from HEAD;
- returns DEGRADED, never PASS (ADR-005 S3 one level up: the policy exists, but CORE cannot
  establish that it is the policy of record);
- does **not** suspend autonomous execution (governor ruling 2026-10-05; contrast D3).

Example of the recorded evidence: *evaluated law `abc123…`; law of record `def456…` at commit
`b3167fca`; relationship `DRIFT`; verdict `DEGRADED`.*

The governor's normal path (edit, then commit) passes through this state briefly and visibly.
That is intended: the window is shown, not hidden.

### D3 — Implement ADR-030 as decided

The daemon compares the code on disk with the code it loaded (D1's loaded-code identity). On
difference it DEGRADEs, posts `governance.stale_daemon`, and suspends autonomous execution until
the governor restarts it, with ADR-030's escalation window. Nothing here re-decides ADR-030; this
ADR supplies the mechanism ADR-030 said was missing.

### D4 — Every change between observations carries what CORE knows about it

For each path that changed between two ledger observations, CORE records three **independent**
facts. They are not one taxonomy: a proposal-produced commit also has an author; a direct commit
can be attributable without being governed. Recording them separately keeps CORE from discarding
information or claiming more than its evidence.

| Dimension | Values | Evidence |
|---|---|---|
| **Governance provenance** | `proposal` / `direct` / `unknown` | `proposal`: the path is in `proposal_consequences.files_changed` for that commit range. `direct`: committed outside any proposal. `unknown`: not determinable (e.g. uncommitted). |
| **Producer provenance** | `authenticated` / `git-asserted` / `unknown` | `git-asserted`: the commit's author metadata — **asserted, not authenticated**; anyone able to commit can set it. `authenticated` becomes available with #942 / ADR-132 D10. `unknown`: no commit. |
| **Persistence** | `committed` / `uncommitted` | working tree vs HEAD |

Example: `proposal + git-asserted + committed` and `direct + authenticated + committed` are
both meaningful records. CORE never reports a `git-asserted` producer as an identified one.

Findings are raised for `uncommitted` changes and for `unknown` producer provenance on a
committed change. A `direct` change with recorded producer provenance is allowed (ADR-168 D1) and
recorded without a finding. Posture starts as `reporting` and follows the ADR-148 D5 ramp
(reporting → resolve drift → blocking). `.intent/` is covered first (D2); `src/` follows.

### D5 — Writes outside the repository are recorded

Every write CORE makes outside the bound repository appends a ledger entry: target root,
path, operation, content hash, and the operation or proposal that produced it. No key or secret
content is recorded. This is the tracing ADR-166 D2 already requires of the external-target
writer, made a shared ledger rather than per-run files. Until that writer exists, `byor.py`,
`scout.py` and `project_scaffold.py` append their entries directly.

### D6 — Ordering against ADR-166

ADR-166 units 2–4 (inside the repository) may proceed. **ADR-166 unit 5 waits for D1, D2 and
D5**: CORE does not extend its write reach outside the repository before it can record and
attribute what it writes and observe the state it governs. #937 (`keygen`) waits with unit 5.

## Explicitly not decided here

- No file watcher, and no autonomous restart (ADR-030 Option B stays rejected).
- No block on producers writing directly (ADR-168 D1).
- The table design and observation cadence are implementation, not decision.
- Tamper-resistance against a privileged local actor (e.g. root editing the ledger). The ledger
  makes changes visible to an honest system; it is not a security seal.
- No cryptographic chaining, signing, remote attestation or event sourcing. Append-only is the
  decided property; anything stronger needs its own requirement.
- No general filesystem surveillance. Observations happen at CORE's boundaries (boot, audit
  cycle, governed and outside writes), not on every filesystem mutation.

## Consequences

- **Positive.** Every verdict says which law it evaluated, whether that is the law of record, and
  which code produced it. An ungoverned edit to
  the law is visible within one cycle instead of silently enforced. ADR-030's trust boundary
  finally exists in code. Outside writes leave a record.
- **Negative.** The working copy of this repository is routinely dirty during development, so
  DEGRADED verdicts and findings will appear during normal work until the change is committed.
  This is the honest state, but it is noise until the workflow settles.
- **Cost.** Ledger storage grows with time; a retention rule is needed (implementation).

## Acceptance checks

1. Edit a file under `.intent/` without committing → within one cycle a finding names the path;
   the verdict records both digests, relationship `DRIFT`, and is DEGRADED.
2. Commit the edit → the next cycle's verdict records relationship `MATCH` at the new commit; the
   finding resolves.
3. Change a module under `src/` and commit without restarting → the daemon posts
   `governance.stale_daemon` and suspends autonomous execution (ADR-030).
4. Restart the daemon → the boot observation is appended and compared with the previous one;
   each change between them carries its three D4 facts, and no `git-asserted` producer is
   reported as authenticated.
5. A `project new` / onboard write outside the repository → a ledger entry exists with its
   target, path and content hash.

## Review record

- 2026-10-05 — drafted; governor rulings on posture, identity and process incorporated.
- 2026-10-05 — one external review: architecture, evidence, D1, D3, D5, D6 accepted as drafted.
  Incorporated: D4 split into three independent dimensions, git identity recorded as
  `git-asserted` (material); D2 distinguishes law evaluated from law of record with a
  `MATCH`/`DRIFT` relationship; scope exclusions for cryptographic chaining and general
  filesystem surveillance.
- 2026-10-05 — accepted by the governor.
