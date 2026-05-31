# ADR-067 — Constitutional Coherence Checker: Storage, CLI, LLM Invocation, and Scheduling

**Status:** Accepted
**Date:** 2026-05-21
**Author:** Darek (Dariusz Newecki)
**Closes:** #374 (paper and ADR acceptance criteria)
**Governing paper:** `.specs/papers/CORE-ConstitutionalCoherenceChecker.md`

---

## Context

`CORE-ConstitutionalCoherenceChecker.md` defines the Constitutional Coherence
Checker (CCC) instrument and defers four implementation decisions to this ADR:

1. Storage schema for CCR records and candidate records.
2. CLI surface (`core-admin coherence`).
3. LLM invocation model: prompt structure, batching strategy, failure handling.
4. Scheduling triggers and daemon integration.
5. Relationship between CCR run status and the governance dashboard signal.

This ADR makes those decisions. Implementation must not begin before this ADR
is accepted.

---

## Decision

### D1 — Storage Schema

Two new tables in the `core` schema.

**`core.coherence_runs`**

```sql
CREATE TABLE core.coherence_runs (
    run_id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    trigger          TEXT        NOT NULL
                                 CHECK (trigger IN ('manual', 'adr_added', 'northstar_changed')),
    run_status       TEXT        NOT NULL DEFAULT 'open'
                                 CHECK (run_status IN ('open', 'closed')),
    input_manifest   JSONB       NOT NULL,
    candidate_count  INTEGER     NOT NULL DEFAULT 0,
    unreviewed_count INTEGER     NOT NULL DEFAULT 0
);
```

`input_manifest` is a JSON array of objects:
`{ "path": "<file path>", "domain": "adr|rule|northstar", "status": "checked|skipped", "skipped_reason": "<string|null>" }`

`unreviewed_count` is maintained by trigger or application logic on every
`INSERT` or `UPDATE` to `core.coherence_candidates`.

**`core.coherence_candidates`**

```sql
CREATE TABLE core.coherence_candidates (
    candidate_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id            UUID        NOT NULL REFERENCES core.coherence_runs(run_id),
    relation          TEXT        NOT NULL CHECK (relation IN ('R1', 'R2', 'R3', 'R4')),
    documents         JSONB       NOT NULL,
    claim             TEXT        NOT NULL,
    rationale         TEXT        NOT NULL,
    triage_decision   TEXT        NOT NULL DEFAULT 'unreviewed'
                                  CHECK (triage_decision IN (
                                      'unreviewed', 'confirmed', 'dismissed', 'deferred'
                                  )),
    triage_note       TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    triaged_at        TIMESTAMPTZ
);
```

`triage_note` is required when `triage_decision = 'dismissed'`. Enforced at
the application layer (not DB constraint) to allow a single UPDATE path.
`triaged_at` is populated by the application when `triage_decision` transitions
away from `unreviewed`.

No foreign key from `coherence_candidates` to `autonomous_proposals` or
`blackboard_entries` — CCC candidates are not proposals and are not blackboard
findings. They are a separate governance artifact.

---

### D2 — CLI Surface

Three subcommands under `core-admin coherence`:

**`core-admin coherence check [--full]`**

Triggers a new CCC run.

Without `--full`: evaluates only documents that are new or changed since the
last completed run (incremental mode). Change detection uses SHA-256 hashes
stored in the previous run's `input_manifest`.

With `--full`: evaluates the full corpus regardless of prior runs. Required
for the first run on any installation.

Prints run_id on start and a summary on completion:
`Coverage: N checked, M skipped · Candidates: K produced`

**`core-admin coherence report [RUN_ID]`**

Displays the CCR for the specified run, or the most recent run if `RUN_ID`
is omitted.

Output sections:
1. Run metadata (run_id, run_at, trigger, run_status).
2. Coverage manifest (one row per input item, status, skipped_reason if applicable).
3. Candidate list (candidate_id, relation, documents, claim, triage_decision).
4. Triage summary (N confirmed, N dismissed, N deferred, N unreviewed).

**`core-admin coherence triage CANDIDATE_ID DECISION [--note TEXT]`**

Records a triage decision for a single candidate.

`DECISION` must be one of: `confirmed`, `dismissed`, `deferred`.

`--note` is required when `DECISION = dismissed`. The CLI rejects the command
without it. When `DECISION = confirmed` or `deferred`, `--note` is optional
but accepted.

A run transitions from `open` to `closed` when `unreviewed_count` reaches 0.
The CLI prints confirmation of the transition when it occurs.

---

### D3 — LLM Invocation Model

**Cognitive role.** The CCC uses a dedicated cognitive role:
`constitutional_coherence_analysis`. This role is declared in
`.intent/cognitive_roles/constitutional_coherence_analysis.yaml` before
implementation begins. The role is read-only and analysis-only — it produces
no proposals, no blackboard entries, and no file writes.

**Prompt contract.** Every LLM call in a CCC run carries the following
system-level framing (paraphrased — exact template is implementation detail):

> You are a candidate-finder. Your role is to identify potential contradictions,
> gaps, or drift observations between the constitutional documents provided. You
> do not produce verdicts. You do not recommend amendments. You output a JSON
> array of candidate objects. Each candidate has: relation (R1/R2/R3/R4),
> documents (list of paths), claim (one sentence), rationale (two to four
> sentences). If you find no candidates, return an empty array.

LLM output is parsed as a JSON array. Anything that is not a valid JSON array
of objects with the required fields is treated as a parse failure (see failure
handling below).

**Batching strategy by relation:**

| Relation | Batch unit | Max items per call |
|---|---|---|
| R1 (ADR-vs-ADR) | Cluster of thematically related ADRs | 5 ADRs |
| R2 (rule-vs-northstar) | One rule domain file vs. full northstar corpus | 1 rule domain |
| R3 (rule-vs-ADR) | One rule domain file vs. its governing ADR(s) | 1 rule domain |
| R4 (cross-document drift) | Changed/new document vs. documents it references | 1 document |

For R1, clustering preference: ADRs that share a stated domain, reference each
other by number, or were authored within the same calendar month. Clustering
is best-effort; unclustered ADRs are batched sequentially.

**Failure handling.** All failure modes are non-fatal: the run continues.

| Failure mode | item_status | skipped_reason |
|---|---|---|
| LLM call failure (network, auth, timeout) | `skipped` | `llm_call_failure` |
| LLM output not valid JSON | `skipped` | `llm_parse_failure` |
| LLM output missing required fields | `skipped` | `llm_schema_failure` |
| Input file not readable | `skipped` | `file_read_failure` |

A run where more than 20% of input items are `skipped` emits a WARNING line
in the run summary and in `core-admin coherence report` output. This threshold
is advisory; the run is not failed automatically.

---

### D4 — Scheduling and Daemon Integration

**The CCC is not a daemon worker.** It does not run on a schedule and is not
registered in `.intent/workers/`. It runs as a CLI process only.

**Trigger detection runs at invocation time.** When `core-admin coherence check`
is called without an explicit `--trigger` flag, the CLI detects the appropriate
trigger value by:

1. Comparing current ADR file count against the ADR count recorded in the most
   recent run's `input_manifest`. If the count increased, trigger = `adr_added`.
2. Comparing SHA-256 hashes of all northstar files against hashes in the most
   recent run's `input_manifest`. If any hash differs, trigger = `northstar_changed`.
3. If neither condition holds, trigger = `manual`.

When called with `--full`, trigger = `manual` unless overridden explicitly.

**Automated triggering is deferred.** Hooking the CCC into the daemon event
loop (e.g., firing on ADR commit detection) is a follow-up capability. This
ADR does not implement it. The trigger detection logic in D4 is designed to
be reusable by a future event-driven wrapper without modification.

---

### D5 — Governance Dashboard Signal

The CCR run status surfaces as an advisory line in the `core-admin code audit`
output, appended after the standard verdict block and before the process exits.

Format when at least one run exists:

```
Constitutional Coherence: <N> open run(s) · <M> candidate(s) unreviewed
```

Format when all runs are closed:

```
Constitutional Coherence: clean (last run <YYYY-MM-DD>)
```

Format when no runs exist:

```
Constitutional Coherence: no runs recorded — run `core-admin coherence check --full`
```

This line is advisory only. It has no effect on the PASS/FAIL audit verdict.
It is rendered on every audit run regardless of verdict.

---

### D6 — Cleanup Verbs (added 2026-05-31)

D2 specified three CCC verbs (`check`, `report`, `triage`) covering the
forward path: produce a run, view it, decide each candidate. Two operational
failure modes surfaced in production (planning record:
`.specs/planning/CCC-backlog-cleanup-2026-05-31.md`):

1. The Revisit Trigger fired: `unreviewed_count` drifted from the live
   `triage_decision = 'unreviewed'` row count after an off-path bulk mutation
   bypassed `coherence_service.triage_candidate()` and skipped its decrement.
2. A structural gap not anticipated by D2: when multiple full-scan runs are
   open simultaneously, retiring superseded runs requires per-candidate
   triage of duplicated content (~2400 calls in the 2026-05-31 case) or a
   direct-DB mutation outside the governed loop.

Both are governed by adding two cleanup verbs under `core-admin coherence`.

**`core-admin coherence repair-counts`**

For every run in `run_status = 'open'`, recompute `unreviewed_count` from
`SELECT COUNT(*) FROM core.coherence_candidates WHERE run_id = :run_id AND
triage_decision = 'unreviewed'` and write the value back. Then evaluate the
zero-candidate auto-close path (the existing `close_run_if_empty` companion)
on each affected run.

Idempotent. No schema change. Output: one row per open run with old count,
new count, delta, and whether the run was auto-closed by the repair.

**`core-admin coherence supersede <old_run_id> --by <canonical_run_id> --note "..."`**

Bulk-dismisses every candidate in `<old_run_id>` whose
`triage_decision = 'unreviewed'`, setting `triage_decision = 'dismissed'`,
`triage_note = <note>`, and `triaged_at = now()`. Sets
`run_status = 'closed'` on `<old_run_id>`. Repairs `<canonical_run_id>`'s
denormalized `unreviewed_count` (same recompute path as `repair-counts`).

Guards:
- Both `<old_run_id>` and `<canonical_run_id>` must exist.
- `<old_run_id>` must be `run_status = 'open'`.
- `<canonical_run_id>`'s `run_at` should be newer than `<old_run_id>`'s.
  If not, the CLI emits a warning but proceeds; the mandatory `--note`
  records the governor's choice honestly.
- The CLI prints the count of candidates that would be dismissed and
  requires interactive confirmation before applying.
- `--note` is mandatory at the CLI option layer. The supersession is
  recorded on every dismissed candidate's `triage_note`, so the cleanup
  is fully auditable through the same triage history that records
  ordinary dismissals.

`dangerous = True`. Per-CLI convention.

**Atomicity.** Both verbs run inside a single DB session and commit once at
the end of the operation. `supersede` does not partially close: if the
bulk-dismiss or the canonical recount fails, the session rolls back and the
old run remains open.

**What D6 does NOT introduce.** Cross-run dedup at candidate generation —
the substantive fix that prevents the regrowth pattern motivating
`supersede` — is out of scope here. It is ADR-shaped on its own, design
candidates recorded in `.specs/planning/CCC-backlog-cleanup-2026-05-31.md`,
and owned by a dedicated session.

---

## Consequences

**Positive:**
- The CCC has a complete, buildable specification. Implementation can proceed
  from this ADR without further architectural decisions.
- Storage is isolated in two new tables with no foreign-key entanglement with
  the existing proposal/finding/blackboard schema. CCC artifacts cannot be
  confused with autonomous proposals or blackboard findings.
- The CLI surface is minimal and deliberate — three subcommands, each with a
  single responsibility.
- Failure modes are graceful: a partial run with skipped items is surfaced
  honestly, not silently discarded.

**Negative:**
- Automated triggering is deferred. Until the daemon event hook is built,
  the governor must remember to run `core-admin coherence check` after ADR
  authoring. The advisory audit line partially compensates (it shows "no runs
  recorded" as a prompt).
- `unreviewed_count` denormalization on `coherence_runs` requires consistent
  maintenance at the application layer. A missed decrement is the failure mode.
  The count is recoverable by re-querying `coherence_candidates`; a repair
  command should be considered if drift is observed.

---

## Non-Goals

- This ADR does not specify the exact LLM prompt templates. Those are
  implementation details owned by the CCC module.
- This ADR does not define the `constitutional_coherence_analysis` cognitive
  role's model assignment. That follows the existing cognitive role assignment
  pattern in `.intent/cognitive_roles/`.
- This ADR does not specify how confirmed findings are tracked after triage.
  Confirmed findings become governor-authored constitutional amendment proposals;
  their tracking is through the existing issue tracker, not through new schema.
- This ADR does not implement automated daemon triggering.

---

## Revisit Triggers

- `unreviewed_count` drift was observed in production (2026-05-31). Repair
  verb landed as **D6** (`core-admin coherence repair-counts`); the original
  Revisit Trigger is closed.
- Automated triggering becomes necessary → extend this ADR with a D6 covering
  the daemon event hook and the worker declaration.
- ADR corpus grows beyond ~100 entries and R1 batching becomes a throughput
  problem → revisit cluster sizing and introduce parallel LLM calls with
  concurrency limit.

---

## References

- Governing paper: `.specs/papers/CORE-ConstitutionalCoherenceChecker.md`
- Related: `.specs/papers/CORE-Rule-Conflict-Semantics.md`
- Related: `.specs/papers/CORE-Constitution-Read-Only-Contract.md`
- Related: ADR-027 (CoherenceSensor — runtime loop coherence, distinct scope)
- Issue: #374
