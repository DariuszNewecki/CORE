# ADR-011: Workers own blackboard attribution; services do not post

**Status:** Accepted
**Date:** 2026-04-24
**Authors:** Darek (Dariusz Newecki)

## Context

The `core.blackboard_entries` schema declares `worker_uuid` as `NOT NULL`. This constraint encodes a constitutional principle that had been implicit until this week: every row on the blackboard must be attributable to a registered Worker whose identity exists in `core.worker_registry`.

On 2026-04-24 afternoon, the §7+§7a Finding↔Proposal contract (ADR-010) shipped. Post-restart, the first execution cycle exposed a latent violation of the attribution principle: `ProposalExecutor._post_test_run_required` raised `NotNullViolationError` on a raw-SQL `INSERT INTO core.blackboard_entries` that omitted `worker_uuid`. The INSERT had no legitimate value to supply — `ProposalExecutor` is a service, not a Worker. It is instantiated as a shared dependency inside `CoreContext`, has no `worker_registry` row, no heartbeat, no phase binding, no UUID of its own. The domain `Proposal` dataclass and the `AutonomousProposal` ORM row also carry no Worker identity. There was no naive plumbing fix.

The evening refactor resolved the immediate bug by moving the `test.run_required` posting out of `ProposalExecutor` entirely into `ProposalConsumerWorker`. `ProposalExecutor.execute()` now returns a richer result dict (`changed_files`, `post_execution_sha`) with no blackboard side-effects. `ProposalConsumerWorker.run()` iterates that result and calls `self.post_finding()` — inherited from the Worker base class — once per modified `src/**/*.py` file. Attribution flows through `Worker._post_entry()`, which fills `worker_uuid` and `phase` from the Worker's own identity. The `NOT NULL` constraint is satisfied at the level where attribution actually exists.

The refactor worked. It also revealed that the architectural issue was larger than the bug: a service was writing directly into the attribution layer of the blackboard via a raw-SQL bypass that the Worker base class exists precisely to prevent. The CLI execution path (`core-admin ... execute <proposal_id>`) exhibits the same shape, degrading cleanly post-refactor — human-invoked executions no longer post `test.run_required`, which is semantically correct: humans run their own tests.

This ADR records the principle the refactor made operational. The paper had not stated it; the schema had (`NOT NULL`); the code mostly honoured it (Workers use the base class); one raw-SQL path violated it. The principle is now written down.

## Decision

**Every INSERT into `core.blackboard_entries` must originate from a registered Worker, routed through the Worker base class's `post_finding()` / `post_report()` / `post_heartbeat()` / `_post_entry()` machinery.**

**Services may UPDATE existing rows on `core.blackboard_entries` (state transitions such as `resolve_entries`, `abandon_entries`, `mark_indeterminate`, `defer_entries_to_proposal`, `revive_findings_for_failed_proposal`) because those operations do not create new attribution — the row already carries the `worker_uuid` of the original poster. Services must NOT execute INSERTs.**

The architectural cut is `INSERT` vs. `UPDATE`:

- **INSERT** creates a new row. A new row requires a responsible agent. Only a Worker has identity. Only Workers may INSERT.
- **UPDATE** transitions state on a row that already has a responsible agent. Any caller — Worker or service — may UPDATE, because no new attribution is being manufactured.

Where a service needs to cause a finding to be posted as a consequence of its work, the service returns the necessary data to the calling Worker via its result object. The calling Worker performs the post. This indirection is the price of attribution integrity; it is small and consistently shaped.

## Alternatives Considered

**Thread `posting_worker_uuid` and `posting_worker_phase` through the service signature.** The initial framing in the 2026-04-24 handoff described this as "a small scope plumbing fix." Rejected after code inspection: the approach propagates Worker concepts through the service layer without closing the architectural violation. The raw-SQL bypass path remains available; every service acquires an attribution parameter; the constraint enforces nothing it could not previously enforce. Plumbing the value does not fix the shape.

**Register a synthetic "proposal_executor" Worker with its own UUID in `core.worker_registry`.** Rejected. Services are not Workers in the constitutional sense. A Worker is a loop-bearing agent with a phase binding, a heartbeat, a registration row, and a constitutional responsibility to advance state on the blackboard. A service is a shared dependency, invoked by Workers and by CLI handlers alike, with no loop and no identity. Giving a service a Worker row to satisfy a `NOT NULL` constraint dilutes the Worker concept and creates a pseudo-agent that no audit can meaningfully attribute behaviour to.

**Make `worker_uuid` nullable.** Rejected. The constraint is load-bearing for consequence-log causality. Every finding must trace to a responsible agent for the Finding → Proposal → Approval → Execution → New Findings chain to be reconstructible. Nullable `worker_uuid` would mean "anonymous finding," which is precisely what the attribution principle forbids.

**Leave it as one-off and patch only the immediate call site.** Rejected. The `ProposalExecutor` case was the observed instance; the principle it violates is general. Codifying the principle and closing the observed violation together costs no more than closing only the observed violation, and makes the next violation detectable as a category rather than rediscovered as a novelty.

## Consequences

**Positive:**

- The raw-SQL INSERT bypass into `core.blackboard_entries` from a non-Worker site is closed. Attribution now flows through the Worker base class for every `test.run_required` finding emitted as a consequence of proposal execution.
- Consequence-log causality is structurally preserved. Every finding has a responsible Worker by constraint, not by convention.
- `ProposalExecutor` is now a pure executor: runs actions, returns structured results, produces no side-effects on the attribution layer. Unit of responsibility is cleaner.
- Services are kept pure: they do work and return data; they do not manufacture attribution. This aligns the service layer with its intended shape.
- The INSERT/UPDATE cut makes the principle tractable to audit. A future sensor can flag `INSERT INTO core.blackboard_entries` string occurrences in any file under `src/body/**` or outside `src/**/workers/**` as a governance-debt signal.

**Negative:**

- CLI-invoked executions (`core-admin ... execute <proposal_id>`) no longer post `test.run_required` findings. Semantically correct — humans run their own tests — but a behavioural change relative to pre-refactor. Worth noting for operators who may have been observing CLI-path findings on the blackboard.
- Services that need to cause a finding to be posted must now return the relevant data to a calling Worker and rely on that Worker to post. One layer of indirection. In practice this matches the existing pattern for `ViolationRemediatorWorker` / `ProposalConsumerWorker`, so no new shape is introduced; it becomes the canonical shape.
- The principle is not yet enforced by a rule. Violations are detectable only by code review or by the `NOT NULL` constraint firing at runtime. A raw-SQL INSERT into `core.blackboard_entries` from a service site would compile, load, and run until the first execution produces a `NotNullViolationError` — which is what happened on 2026-04-24. Enforcement-real for this principle is a future item (see Open Debts).

**Neutral:**

- `ProposalConsumerWorker.run()` now carries a small loop over `result["changed_files"]` to post one finding per modified source file. The loop is simple and local; no new shape.
- `ProposalExecutor.execute()` and `execute_batch()` have richer return shapes (`changed_files`, `post_execution_sha`). Both fields default to safe zero-values (`[]`, `None`) on dry-run, failed-action, and batch-iteration-failure paths. No unbound-access surface.

**Open Debts:**

- No sweep has been performed for other raw-SQL INSERT paths against `core.blackboard_entries` from non-Worker sites. This ADR operationalises the principle; a one-time grep (`grep -rn "INSERT INTO core\.blackboard_entries" src/`) against the tree, filtering to non-Worker files, is candidate work for a future session.
- A governance rule encoding this principle is not yet authored. Candidate statement: *"Only files under `src/**/workers/**` (or the Worker base class itself) may contain INSERT statements against `core.blackboard_entries`. Service-layer INSERTs into the attribution table are forbidden."* Enforcement via an AST/string sensor on `src/**/*.py` is straightforward. Mapping and rule authoring are governor-domain work.
- The historical debt of 28,287 all-time `resolved` rows with `resolved_at IS NULL` (surfaced by the 2026-04-24 evening state scan) is a separate matter. It predates the attribution principle and does not bear on it; named here only to keep the two issues distinct.

## References

- ADR-010 — Finding↔Proposal contract (§7 + §7a). This ADR is adjacent: ADR-010 introduces the terminal `deferred_to_proposal` transition and the `revive_findings_for_failed_proposal` path; ADR-011 codifies the attribution constraint on the POSTING half of that contract.
- 2026-04-24 evening refactor (commit hash pending in the handoff) — the concrete change that operationalised this principle. Two files: `src/will/autonomy/proposal_executor.py` (loses both `test.run_required` INSERT blocks, loses unused `text` and `json` imports, gains `changed_files` and `post_execution_sha` in result dicts with safe method-scope defaults) and `src/will/workers/proposal_consumer_worker.py` (gains the posting loop in `run()`).
- Schema: `core.blackboard_entries.worker_uuid NOT NULL` (see `infra/sql/db_schema_live.sql`).
- Worker base class: `shared/workers/base.py` — `post_finding()`, `post_report()`, `post_heartbeat()`, `_post_entry()`. These are the attribution-flow-preserving APIs.
- `core.worker_registry` — the table that gives Workers their constitutional identity. The join target that `worker_uuid` on `blackboard_entries` implicitly references.

---

*Written by the principal architect after the 2026-04-24 evening refactor verified passively (§§2–5 of the state scan showed attribution intact across 257 terminal-state transitions; `test.run_required` path unexercised since restart, expected, passively parked).*
