---
kind: adr
id: ADR-044
title: ADR-044 — Incremental LLM-gate verdict cache
status: accepted
---

<!-- path: .specs/decisions/ADR-044-llm-gate-verdict-cache.md -->

# ADR-044 — Incremental LLM-gate verdict cache

**Status:** Accepted
**Date:** 2026-05-13
**Governing paper:** `.specs/papers/CORE-Gate.md`
**Authors:** Darek (Dariusz Newecki)
**Closes:** #TBD
**Relates to:** ADR-039 (audit-input cache invalidation), ADR-043 (llm_gate
audit throughput — pre-selector primary, semaphore secondary)

---

## Context

Every audit run — whether driven by `AuditViolationSensor` on its 600s daemon
cycle or by `core-admin code audit` on demand — evaluates all llm_gate rules
against their pre-selected file sets from scratch. Results are computed,
findings posted, and the LLM responses discarded. Nothing persists.

The consequence: the same file is evaluated by the same rule on every audit
cycle regardless of whether the file changed. On a stable codebase the cost
is paid repeatedly for zero informational gain.

### Observed cost (2026-05-13 triage)

`purity.docstrings.required` pre-selects ~80 files. At ~9s per file on a
warm qwen2.5-coder:3b (M1, 16GB), this rule alone contributes ~6 minutes to
every full audit run. The daemon's purity sensor and a concurrent manual audit
both pay this cost independently, on the same files, in the same time window.

`architecture.mind.no_execution_semantics` pre-selects ~5–10 files (~25–50s).
`modularity.unix_philosophy` pre-selects ~5 files (~25s). The cumulative llm_gate
cost on a quiet codebase where nothing is changing is 8–10 minutes per full
audit run, repeated every 600s.

ADR-043's pre-selector (`requires_findings_from:`) reduced the candidate set
from 72 to ~5–10 for `no_execution_semantics`. That was the first throughput
intervention. This ADR is the second and more general one: stop re-evaluating
files whose content and governing rule have not changed.

### The double-work observation

CORE already maintains per-file change tracking in `repo_artifacts`. The
`repo_crawler` worker computes a content hash (or equivalent freshness signal)
for every source file it processes and persists it to the DB. The `repo_embedder`
worker uses this signal to decide whether to re-embed. The audit pipeline does
not use this signal — it re-evaluates every pre-selected file on every cycle.

The same infrastructure that makes the embedding pipeline incremental can make
the llm_gate pipeline incremental. This ADR applies the build-system pattern —
only re-evaluate what changed — to LLM-gate rule evaluation.

---

## Options considered

**Option A — DB verdict cache keyed on content hash + rule hash.**
New table `llm_gate_verdicts(rule_id, file_path, file_content_hash,
rule_content_hash, verdict, findings_json, evaluated_at)`. Before dispatching
to Ollama, the llm_gate engine performs a cache lookup. On hit (both hashes
match), it returns the stored verdict without calling Ollama. On miss, it calls
Ollama, stores the result, and returns it. The cache is shared across all
callers — daemon sensor cycles and manual audits read from and write to the
same rows.

**Option B — repo_artifacts staleness signal only, no verdict storage.**
Use `repo_artifacts.last_modified` (or equivalent crawler-maintained field)
versus a per-rule `last_evaluated_at` timestamp to identify which files need
re-evaluation. Don't store verdicts. Simpler schema; avoids re-evaluating
unchanged files but does not share results between daemon and manual audit
within the same time window.

**Option C — In-process LLM result cache (single audit run scope).**
Cache LLM responses in memory for the duration of one audit run. Helps only
if the same file appears in multiple rule scopes within one run. Does not
persist across runs or between daemon and manual audit. Negligible impact on
the dominant cost (cross-cycle repetition).

**Option D — Disable llm_gate rules on the daemon; run LLM audit
on-demand only.**
Separate the two concerns: fast structural sensors run on the 600s daemon
cycle; LLM-heavy rules run manually or on a slower scheduled trigger.
Reduces daemon cost to near-zero but means the autonomous loop is blind to
violations that only llm_gate can detect (e.g., docstring adequacy,
unix_philosophy violations). Breaks the continuous governance model.

---

## Decision

**Option A — DB verdict cache keyed on content hash + rule hash.**

The cache key is `(rule_id, file_path, file_content_hash, rule_content_hash)`.

- `file_content_hash`: SHA-256 of the file's byte content at evaluation time.
  Reuse the hash already computed by `repo_crawler` and stored in
  `repo_artifacts` where available, to avoid double-hashing. If
  `repo_artifacts` does not carry a content hash for a given file (e.g.,
  crawler has not yet processed it), compute it inline.

- `rule_content_hash`: SHA-256 of the rule's governing YAML block as loaded
  by `IntentRepository`, computed over a **canonicalized** form (keys sorted,
  whitespace normalized) rather than the raw bytes. This ensures that
  cosmetic edits — blank lines, comment reformatting, key reordering — do not
  invalidate cached verdicts. Only meaningful changes to prompt text,
  thresholds, or enforcement parameters produce a new hash. Computed once per
  audit run during `IntentRepository` load; stored on the rule object.

A cache hit requires both hashes to match. A mismatch on either triggers a
fresh Ollama call and an upsert of the new verdict.

The verdict row stores: `findings_json` (the list of findings the rule would
post, serialised), `verdict` (PASS / FAIL / ERROR), and `evaluated_at`
(timestamp). The audit engine reconstructs findings from the cache row rather
than re-posting from scratch; the consequence chain attribution remains
unchanged because findings are still posted through the normal Blackboard path
— the cache supplies the finding content, not the Blackboard entry.

**Verdict TTL:** rows expire after a governed number of days
(`operational_config.yaml: llm_gate_verdict_cache_ttl_days`, default 30). A
background DB sweep (or a `TRUNCATE`-on-threshold guard in the llm_gate engine)
prevents unbounded table growth. TTL is not a correctness mechanism — content
hash mismatch is — but it prevents stale data accumulation for deleted files
and retired rules.

**Manual invalidation:** `core-admin code audit --force-llm` bypasses cache
reads for that run (still writes updated verdicts). Scoped bypass:
`--force-llm-rule <rule_id>` invalidates one rule's cache.

Rejected: Option B does not eliminate the daemon/manual double-work within the
same time window. Option C has negligible impact on the dominant cost. Option D
breaks continuous governance.

---

## Consequences

**Positive:**
- llm_gate cost on a stable codebase drops from O(all pre-selected files) to
  O(changed files). In steady state, the dominant purity sensor cost falls
  from ~6 minutes to seconds.
- Daemon and manual audit share verdicts. Running `core-admin code audit`
  while the daemon is active no longer doubles the Ollama load.
- The Ollama model stays warm for genuine new-file evaluations rather than
  constant re-evaluation of unchanged content.
- The `repo_artifacts` integration makes the audit pipeline and the embedding
  pipeline share a common change-detection substrate — one signal, two
  consumers.

**Negative:**
- New DB table and migration required. Schema must be versioned under
  `infra/migrations/`.
- Cache coherence: if a file is modified between the crawler's last hash
  computation and the audit engine's lookup, the audit may read a stale hash
  from `repo_artifacts` and incorrectly serve a cache hit. Mitigation: the
  llm_gate engine recomputes the file hash inline if `repo_artifacts`
  `last_crawled` is older than a governed threshold; governed in
  `operational_config.yaml`.
- A rule YAML change (prompt edit, threshold change) invalidates all rows for
  that rule simultaneously. On next audit all pre-selected files for the rule
  are evaluated fresh — equivalent to current behaviour, but a visible latency
  spike if many files are in scope.
- Deleted files accumulate dead verdict rows until TTL expires. TTL handles
  this eventually; for cleaner behaviour, `RepoCrawlerWorker` should delete
  `llm_gate_verdicts` rows for files it detects as removed from the repo
  during a crawl pass.

**Neutral:**
- Finding content and Blackboard attribution are unchanged. The cache is an
  evaluation-layer optimisation; it does not touch the consequence chain.
- The `--force-llm` escape hatch preserves the ability to run a full fresh
  audit when the cache state is suspect.

---

## Implementation guidance

Six sites, in order:

1. **DB migration (`infra/migrations/`):** create table
   `llm_gate_verdicts` with columns `rule_id`, `file_path`,
   `file_content_hash`, `rule_content_hash`, `verdict`, `findings_json`,
   `evaluated_at`. Unique constraint on `(rule_id, file_path,
   file_content_hash, rule_content_hash)`. Index on `(rule_id, file_path)`
   for lookup performance. Consult the existing migration conventions in
   `infra/migrations/` for naming and versioning.

2. **`IntentRepository` (`src/shared/infrastructure/intent/intent_repository.py`):**
   compute and attach `rule_content_hash` to each loaded rule object at
   `initialize()` time. Hash over the canonicalized YAML block: parse the rule's
   YAML subtree, re-serialize with sorted keys and normalized whitespace, then
   SHA-256 the result. Expose it as a field on the rule dataclass so the llm_gate
   engine can read it without re-parsing.

3. **`repo_artifacts` content hash (`src/` — crawler side):** verify whether
   `repo_artifacts` already carries a per-file content hash column. If yes,
   expose a lookup method on the relevant service/repository. If no, add the
   column in a migration and populate it in `RepoCrawlerWorker` alongside
   existing crawl metadata. Do not recompute the hash in the audit engine if
   the crawler already has it. Additionally, when `RepoCrawlerWorker` detects
   a file has been removed from the repo during a crawl pass, delete the
   corresponding rows from `llm_gate_verdicts` for that `file_path`.

4. **llm_gate engine (`src/mind/governance/engines/llm_gate.py` or
   equivalent):** before dispatching a file to Ollama, compute (or retrieve)
   `file_content_hash` and read `rule_content_hash` from the rule object.
   Perform a cache lookup against `llm_gate_verdicts`. On hit, return stored
   findings. On miss, call Ollama, upsert the verdict row, return findings.
   TTL sweep: on each audit run, delete rows where `evaluated_at < NOW() -
   INTERVAL '<ttl_days> days'` (governed value from `operational_config`).
   Honour `--force-llm` flag by skipping the cache read (but still writing).

5. **`OperationalConfig` (`src/shared/infrastructure/intent/operational_config.py`)
   + `.intent/enforcement/config/operational_config.yaml`:** add
   `llm_gate_verdict_cache_ttl_days` (default 30) and
   `llm_gate_cache_staleness_threshold_seconds` (the age of
   `repo_artifacts.last_crawled` above which the engine recomputes the hash
   inline rather than trusting the stored value; default 3600).

6. **Acceptance conditions:**
   - A file evaluated on audit run N produces a cache hit on audit run N+1
     with no content change.
   - Modifying the file between runs produces a cache miss and a fresh Ollama
     call on the next run.
   - Editing a rule's YAML prompt produces a cache miss for all files under
     that rule on the next run.
   - `core-admin code audit --force-llm` produces fresh Ollama calls for all
     llm_gate rules regardless of cache state, and updates the cache with
     new verdicts.
   - Daemon sensor and concurrent `core-admin code audit` share verdict rows;
     the second caller to evaluate an unchanged file reads the first caller's
     cached result.
   - Cache hit rate exceeds 95% after 24h of daemon runtime on a stable
     codebase (no commits landing). Measured via a count of cache hits vs.
     Ollama calls logged by the llm_gate engine.

---

## References

- ADR-039 — Audit-input cache invalidation (per-cycle file list + rule reload)
- ADR-043 — llm_gate audit throughput, pre-selector primary
- `repo_artifacts` table — crawler-maintained per-file metadata including
  freshness signals
- `src/mind/governance/engines/` — llm_gate engine location (verify path
  before implementation)
- `.intent/enforcement/config/operational_config.yaml` — governed config
  home for TTL and staleness threshold
- 2026-05-13 triage: `purity.docstrings.required` ~80 files, ~6 min/run;
  `architecture.mind.no_execution_semantics` ~5–10 files, ~25–50s/run;
  `modularity.unix_philosophy` ~5 files, ~25s/run
