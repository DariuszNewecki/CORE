<!-- path: .specs/decisions/ADR-018-decomposed-crawler-embedder-supersedes-vector-sync-worker.md -->

# ADR-018 — Decomposed crawler/embedder supersedes vector_sync_worker on the autonomous path

**Status:** Active
**Date:** 2026-05-01
**Authority:** Architectural
**Supersedes:** none — `vector_sync_worker` is not ADR-grounded
**Preserves:** Atomic action `sync.vectors.code` (unchanged) for the manual `core-admin dev sync --write` path

---

## 1. Context

CORE has two paths from source-tree edits to Qdrant vectors. The manual path is `core-admin dev sync --write`, which invokes `DevSyncWorkflow._run_sync_phase`, which executes the atomic action `sync.vectors.code`. That action does crawl and embed in lockstep: Phase 1 calls `CrawlService.run_crawl()` (registers artifacts in `core.repo_artifacts`, extracts AST call-graph edges into `core.symbol_calls`, cross-references non-Python artifacts in `core.artifact_symbol_links`); Phase 2 walks `repo_artifacts` where `chunk_count = 0`, chunks each artifact, embeds the chunks, and upserts them to the appropriate Qdrant collection.

The autonomous path today is `vector_sync_worker`, an active worker that executes the same `sync.vectors.code` atomic action every 600 seconds. It is a thin wrapper — a schedule and a blackboard surface for an action that already exists.

Two further workers exist in the codebase but are paused: `repo_crawler` (which calls `CrawlService.run_crawl()` directly) and `repo_embedder` (which consumes `repo_artifacts` and writes Qdrant). Their YAML rationales describe them as awaiting activation pending a governor decision. In fact they are functionally superseded by `vector_sync_worker`: the active wrapper already does both jobs through a more constitutional path (atomic-action delegation) at higher frequency. The "awaiting activation" framing is misleading — there is nothing to await.

This ADR addresses the question "is the current arrangement architecturally correct?" and concludes that it is not, for four reasons.

**Failure isolation.** Crawling reads files and writes Postgres; embedding reads Postgres and writes Qdrant via an LLM embedding call. These are different external systems with different failure modes. Under `vector_sync_worker`, a Qdrant outage or LLM rate-limit takes down the structural-self-model sync (`symbol_calls`, `artifact_symbol_links`) too, even though that work has no dependency on either system. Decoupled, the structural model stays current while embeddings catch up.

**Differential rate control.** Crawling is cheap (file reads, hashes, AST parse). Embedding is expensive (network round-trip per chunk to the embedding service). They want different cadences and different rate-limit treatments. The current composite shape forbids that.

**Database-as-queue.** `repo_artifacts.chunk_count = 0` is naturally a work queue. The crawler enqueues — sets `chunk_count = 0` on hash change. The embedder dequeues — `WHERE chunk_count = 0`. This pattern is well-established (it traces back to the design lineage CORE explicitly draws on: control systems, distributed systems, database systems). A composite worker that does both sides obscures the queue; a decomposed pair makes the queue the explicit contract between two workers.

**Class taxonomy.** `repo_crawler.yaml` and `repo_embedder.yaml` declare `class: sensing`, which is correct: each reads-and-records-state, neither invokes LLM-driven mutation against `src/`. `vector_sync_worker.yaml` declares `class: acting`, but the work the wrapped action actually performs is sensing. The decomposed pair gets the constitutional class taxonomy right; the wrapper does not.

A 2026-05-01 read-only investigation of the paused pair (the seven-item activation safety report) found one hard activation blocker, one constitutional hygiene issue, and one production-affecting bug in the shared `CrawlService` engine. The blocker: `repo_embedder` YAML declares `module: will.workers.repo_embedder`, but the package on disk is `will.workers.repo_embedding` — daemon would crash on activation. The hygiene issue: `repo_embedder_workers.py` constructs `QdrantService()` and `CognitiveService(...)` directly instead of routing through `service_registry.get_qdrant_service()` and `service_registry.get_cognitive_service()`. The bug: `CrawlService.upsert_artifact` (the non-Python branch) did not manage `chunk_count` on the `ON CONFLICT` UPDATE path, so any non-Python artifact updated after first embedding silently dropped from re-embedding. That bug was already in production via `vector_sync_worker`. It was fixed in this session before this ADR was authored — the fix is a prerequisite for the decomposed pair's activation, because the decomposed pair leans more heavily on `chunk_count` as the inter-worker queue.

The investigation also surfaced three non-blocking hazards: no-change rerun WAL churn; per-file errors swallowed at WARN with no janitor for stuck-`running` rows; stale `infra/sql/db_schema_live.sql` documentation asset. These are tracked as GitHub issues and do not gate this ADR.

---

## 2. Decisions

### D1 — `vector_sync_worker` is deprecated as the autonomous path

`.intent/workers/vector_sync_worker.yaml` flips from `status: active` to `status: deprecated`. The class file `src/will/workers/vector_sync_worker.py` is retained for now — the daemon's worker loader treats `deprecated` as not-scheduled, so the class becomes inert without being removed. A future cleanup ADR may delete the file outright; that is out of scope here.

The atomic action `sync.vectors.code` is **not** changed. It remains the canonical implementation of the manual `core-admin dev sync --write` workflow. The CLI path is preserved exactly as it operates today — the only thing that changes is who invokes the action autonomously, and how.

### D2 — `repo_crawler` is activated

`.intent/workers/repo_crawler.yaml`:

- `status: paused` → `status: active`.
- `schedule.max_interval: 86400` → `600`. The 86400-second cadence in the original declaration was chosen for a once-a-day sensing pass; under the decomposed pair, the crawler's role as the queue-enqueueing producer requires near-real-time freshness so that `repo_embedder` does not lag indefinitely behind source-tree edits. 600 seconds matches the cadence `vector_sync_worker` runs at today, so the change is operationally equivalent on the crawl side.
- Rationale field is rewritten to reflect the decomposed-pair role and the supersession of `vector_sync_worker`.

### D3 — `repo_embedder` is activated, conditional on two prerequisite fixes

The activation has two prerequisites that are inseparable from the decision; without both, `repo_embedder` either crashes on activation or activates with a known constitutional violation. They are recorded here as sub-points D3a and D3b rather than separate decisions because the decision is "activate, conditional on both."

**D3a — Module path corrected.** `.intent/workers/repo_embedder.yaml` field `implementation.module` changes from `will.workers.repo_embedder` to `will.workers.repo_embedding`. The package on disk is `src/will/workers/repo_embedding/`; the YAML's previous value did not resolve via `importlib.find_spec`, so any flip from `paused` to `active` would have raised `ModuleNotFoundError` in the daemon's worker loader. This is a documentation-vs-code drift, not a code change.

**D3b — Registry singleton invariant restored.** `src/will/workers/repo_embedding/repo_embedder_workers.py` constructs `QdrantService()` and `CognitiveService(repo_path=..., qdrant_service=...)` directly inside `RepoEmbedderWorker.run_loop`. This bypasses `service_registry.get_qdrant_service()` and `service_registry.get_cognitive_service()`, which are the lock-protected singleton accessors used everywhere else in CORE. The bypass is technically functional today (the worker is paused, so the parallel singletons never instantiate in production), but activating without correcting it would put a non-registry pair into the live process. The correction replaces the direct constructions with the registry accessors. The `service_registry` is already imported in the same function.

With both fixes in place, `.intent/workers/repo_embedder.yaml`:

- `status: paused` → `status: active`.
- `schedule.max_interval: 43200` → `600`. Same logic as D2: the 43200-second cadence was chosen for once-or-twice-a-day batch embedding; the decomposed pair's queue semantics (crawler enqueues, embedder dequeues) want the embedder running often enough that the queue does not accumulate.
- Rationale field is rewritten.

### D4 — `repo_artifacts.chunk_count` is the work queue between the two workers

This decision documents an emergent contract as a constitutional one. The crawler writes `chunk_count = 0` whenever an artifact's `content_hash` changes, via the `upsert_python_artifact` and `upsert_artifact` methods of `CrawlService`. The embedder reads `WHERE chunk_count = 0` (with `chunk_count != -1` to exclude artifacts marked permanently empty by `mark_artifact_empty`). The integer column is the queue.

This contract was operating implicitly already, but it had a silent failure mode in `upsert_artifact` until the bug fix landed earlier in this session: the non-Python branch did not reset `chunk_count` on hash change, so any updated non-Python artifact (docs, intent, tests, prompts, reports, infra) was filtered out by the embedder's `chunk_count = 0` predicate and never re-embedded. That gap was invisible while `vector_sync_worker` was the active path because the failure was downstream of the atomic action's read of `repo_artifacts`, but it would have been the same gap under the decomposed pair. With the fix landed, the queue contract holds.

Documenting the contract here means: future changes to either worker that affect `chunk_count` semantics must be coordinated. Future schema or column changes to `repo_artifacts.chunk_count` carry the same coordination cost. The implicit pattern becomes a named architectural invariant.

### D5 — Class taxonomy is left as-declared

Both `repo_crawler.yaml` and `repo_embedder.yaml` declare `class: sensing`, which is correct under the decomposed pair: each reads input state and records derived state in the database, neither invokes LLM-driven mutation against `src/` files. The classification is preserved.

`vector_sync_worker.yaml` declares `class: acting`, which mismatches what its wrapped atomic action does (sensing). Under D1 it becomes `deprecated`; correcting the class on a YAML on its way out of service would be cosmetic. The mismatch is acknowledged here for the record and not corrected.

---

## 3. Consequences

**Operational.** The autonomous path's blackboard surface changes: where `vector_sync_worker` posted a single `sync.vectors.code.complete` (or `.failed`) report per cycle, the decomposed pair posts `repo.crawl.complete` (from `RepoCrawlerWorker`) and `repo.embed.complete` (from `RepoEmbedderWorker`) on independent cadences. Tools that filter blackboard reports by these subjects need to be aware. `core-admin workers blackboard` continues to surface all three subjects without code changes.

**Constitutional.** The decomposed pair posts at finer event granularity than the wrapper did. This is a direct contribution to the consequence-chain attribution work tracked elsewhere: `Finding → Proposal → Approval → Execution → File Changes → New Findings` is more reconstructable when the file-change event is two events (crawl then embed) than when it is one composite event under one attribution.

**Failure modes.** A Qdrant outage now fails only `repo_embedder`; `repo_crawler` continues to update the structural self-model. A crawler failure (e.g., a Postgres outage on `repo_artifacts`) blocks `repo_embedder` from making progress (no new queue entries) but does not produce embedder failures — the embedder finds nothing pending and posts a clean heartbeat. Failure isolation is improved on both sides.

**No data migration required.** The schema is unchanged. The bug-fix to `upsert_artifact` is already landed. `vector_sync_worker`'s most recent run will have left `repo_artifacts` in a consistent state; the decomposed pair picks up from there with no transition step.

**`vector_sync_worker` history.** Past `sync.vectors.code.complete` reports remain on the blackboard. They are not retroactively renamed.

---

## 4. Alternatives considered

**Status quo — keep `vector_sync_worker` as the autonomous path.** Rejected. The four issues in §1 (failure isolation, differential rate control, queue obscurity, class taxonomy mismatch) are all unaddressed.

**Run all three workers concurrently.** Rejected. Two schedulers calling the same `CrawlService.run_crawl()` produce duplicate `crawl_runs` history, duplicate blackboard reports, and waste DB writes. Three-worker concurrency would create governance debt without offering coverage; the decomposed pair already covers what the wrapper does.

**Keep `repo_crawler` and `repo_embedder` paused as warm spares with corrected rationale.** Rejected. This was the most conservative option — flip the rationale text from "awaiting activation" to "superseded by `vector_sync_worker`; retained for direct-invocation scenarios" and otherwise change nothing. Rejected because it preserves a constitutional class-taxonomy mismatch and forecloses the failure-isolation and rate-control gains. Deferral, not decision.

**Decompose the atomic action `sync.vectors.code` to mirror the worker decomposition.** Considered as a possible future ADR. Two atomic actions (`crawl.repo` and `embed.artifacts`) would let the manual CLI invocation choose between full sync and crawl-only. Not required by this ADR — the manual CLI path is fine as a single composite invocation, and decomposing it is its own decision. Out of scope here.

---

## 5. Out of scope

- Hazard #2 from the 2026-05-01 investigation: `repo_artifacts.last_crawled_at` and `crawl_run_id` are rewritten on every cycle even when no content changed, producing WAL churn. Not a correctness issue. Tracked as a GitHub issue.
- Hazard #3: per-file errors in `_crawl_python_file` / `_crawl_artifact_file` are swallowed at WARN; if every file errors, the run still closes `completed`. The schema permits `partial` but the code never writes that value. Additionally, `close_crawl_run_failed` itself has no fallback if it raises mid-handler — `crawl_runs.status='running'` could persist indefinitely, and there is no janitor. Tracked as a GitHub issue.
- Hazard #4: `infra/sql/db_schema_live.sql` does not contain the `crawl_runs`, `repo_artifacts`, `symbol_calls`, or `artifact_symbol_links` table definitions. The asset is stale; the live DB matches the code. Documentation rot only. Tracked as a GitHub issue.
- Future cleanup: deletion of `src/will/workers/vector_sync_worker.py` once `deprecated` has held for a meaningful period and no regression has surfaced. Out of scope here.
- Future ADR on whether `sync.vectors.code` itself should be decomposed (see §4).

---

## 6. References

- 2026-05-01 read-only investigation: the seven-item activation safety report for `repo_crawler` / `repo_embedder` (in-session Claude Code output; this ADR's commit is the canonical landing point for that investigation).
- Bug fix landed this session: `upsert_artifact` chunk_count handling in `src/body/services/crawl_service/main_module.py`. Prerequisite for D4's queue contract.
- ADR-002 — Shared boundary enforcement (the policy-in-`.intent/`-mechanism-in-`src/` principle backs D5's class-taxonomy framing).
- ADR-011 — Worker attribution for blackboard entries (the decomposed pair posts attributable entries at finer granularity than the wrapper did under one attribution).

---

## 7. Files this ADR commits CORE to changing

- `.intent/workers/vector_sync_worker.yaml` — D1 (status, rationale).
- `.intent/workers/repo_crawler.yaml` — D2 (status, schedule, rationale).
- `.intent/workers/repo_embedder.yaml` — D3a (module path), D3 (status, schedule, rationale).
- `src/will/workers/repo_embedding/repo_embedder_workers.py` — D3b (registry-bypass fix).

The three `.intent/` files come back to the governor as complete files (Claude Code cannot write `.intent/`). The `src/` change goes through Claude Code with a `core-admin context build` precondition per the standing workflow rule.
