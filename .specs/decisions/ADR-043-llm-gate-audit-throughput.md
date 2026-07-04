---
kind: adr
id: ADR-043
title: 'ADR-043: llm_gate audit throughput — pre-selector primary, semaphore secondary'
status: accepted
---

<!-- path: .specs/decisions/ADR-043-llm-gate-audit-throughput.md -->

# ADR-043: llm_gate audit throughput — pre-selector primary, semaphore secondary

**Status:** Accepted
**Date:** 2026-05-13
**Governing paper:** `.specs/papers/CORE-Gate.md`
**Amended:** 2026-05-13 — D4 corrected by recon. The semaphore at the
engine layer is redundant: `LLMClient` already gates concurrency by
provider. D4 replaced with a retry-loop fix in `LLMClient`. D6 updated to
reflect the new mechanism. D1–D3, D5, D7 (order preserved), D8 unchanged.
**Depends on:** ADR-042 (D1 pre-selector framing, generalised here; D4 retirement
of `governed_exclusions` is conditioned on this ADR's implementation)

---

## Context

`llm_gate` rules were operationally inert under `LLMGateStubEngine` until #306 wired
the real LLM client into the audit pipeline. The wiring is mechanically correct
(verified by direct probe). The operational reality, observed on the first wired
audit (2026-05-13), is that every `llm_gate` rule's `verify` call against every file
in scope fails transiently:

| Rule | Files in scope | Transient failures | Real verdicts |
|---|---:|---:|---:|
| `purity.logic_conservation` | ~872 | 872 | 0 |
| `modularity.unix_philosophy` | ~872 | 872 | 0 |
| `modernization.legacy_scars` | ~872 | 872 | 0 |
| `purity.docstrings.required` | ~399 | 399 | 0 |
| `architecture.mind.no_execution_semantics` | ~65 | 65 | 0 |

Audit duration was 54s for ~2300 LLM calls (~24ms per call). The LocalCoder provider
(`ollama_qwen_coder_small`, `max_concurrent=2`) cannot service that arrival rate.
The model responds correctly to single ad-hoc invocations. The bottleneck is
arrival rate against a fixed-concurrency provider, not the model.

`LLMGateEngine` already treats infrastructure failure as `ENFORCEMENT_UNAVAILABLE
→ SYSTEM_ERROR_AI_OFFLINE` per file (`mind/logic/engines/llm_gate.py:139–144`).
`rule_executor` already aggregates those into one WARNING per rule
(`mind/governance/rule_executor.py:208–233`). The failure-mode contract is
correct. The problem is that under audit-scale fan-out, the failure rate is 100%,
so the aggregate WARNING is the only signal — no real verdicts ever materialise.

Two grounding observations shape the option space.

**Layer separation.** The pre-selector and the semaphore are not alternatives at
the same altitude. `rule_executor.py:130` computes `files` from
`context.get_files(include=rule.scope, exclude=rule.exclusions)` — narrowing the
candidate set is a *rule-shape* change in the executor. The semaphore is an
*engine-shape* change inside `LLMGateEngine` (or one layer up around it). They
operate on different things — *which files reach the engine* vs. *how fast files
move through the engine* — and they compose.

**Engine-instance cache interaction.** `LLMGateEngine` caches results in a
per-instance `self._cache` dict keyed by
`sha256(rel_path + instruction + content)` (`llm_gate.py:55, 88–99`). The cache
does nothing for the cold-start audit-scale problem (no prior verdicts to hit)
but it interacts with how the semaphore is scoped: if the semaphore is shared
across rules through a single engine instance, the cache is too; if not, both
are duplicated. Cache and concurrency scope must travel together.

---

## Decision

### D1. Generalise the ADR-042 D1 pre-selector principle to `llm_gate` rules

ADR-042 D1 established that for `modularity.class_too_large`, line count is a
*pre-selector* and responsibility-count is the *verdict*. The same shape applies
to the `llm_gate` family generally: cheap, deterministic gates narrow the
candidate set; the LLM produces the verdict only on the narrowed set. This
principle governs all future `llm_gate` rule authoring.

### D2. Introduce `requires_findings_from:` in the enforcement mapping YAML

`requires_findings_from` is a *mechanism* concern (which file set the engine
evaluates), not a *law* concern (what the rule says). It therefore lives in
the enforcement mapping YAML at
`.intent/enforcement/mappings/<namespace>/<file>.yaml`, as a sibling of
`engine:`, `params:`, `scope:`, and `governed_exclusions:` — the same
artifact ADR-042 D3 chose for exclusions. Rule JSON at `.intent/rules/`
remains unchanged: it continues to declare statement, enforcement, authority,
phase, and rationale only. The two artifacts are joined into `ExecutableRule`
by `rule_extractor.py:184` and the new field rides in on the mapping side as
an optional `list[str]` on `ExecutableRule`.

Example mapping entry:

```yaml
mappings:
  modularity.unix_philosophy:
    engine: llm_gate
    params:
      instruction: "..."
    scope:
      applies_to: ["src/**/*.py"]
      excludes: ["tests/**", "scripts/**", "**/__init__.py"]
    requires_findings_from:
      - modularity.class_too_large
```

Semantics: the rule's per-file scope is intersected with the set of files
that have findings from the named rule(s) in the *current audit run*. Empty
intersection produces no work and no findings — the precondition rule did
not fire on any in-scope file. The field is optional; mappings without it
behave as today.

Validation:

- Each entry in `requires_findings_from` must reference a rule id declared
  in `.intent/rules/`. Reference to a non-existent rule id is a constitution
  validation error.
- Cycles across `requires_findings_from` edges are a validation error.
- The META schema for enforcement mappings
  (`.intent/META/enforcement_mapping.schema.*`) is extended to permit the
  field.

The intent is a directed acyclic graph of cheap-gate → expensive-gate
dependencies, expressed in the mapping layer where engine concerns already
live.

### D3. Pre-selector mechanism in `rule_executor`

`execute_rule` is given access to the findings accumulated so far in the audit
run for any rule listed in `requires_findings_from`. When the field is present
on the `ExecutableRule` (hydrated from the mapping per D2), the file list at
`rule_executor.py:130` is further narrowed by the set
`{f.file_path for f in prior_findings if f.check_id in requires_findings_from}`.
The audit driver is responsible for executing rules in topological order so
prior findings are available when a dependent rule runs.

Rules with `is_context_level=True` on `ExecutableRule`
(`executable_rule.py:67`) cannot use `requires_findings_from` — they do not
iterate per-file. A mapping that combines the two is a validation error
caught at extraction time, not at runtime.

### D4. Move retries outside the semaphore in `LLMClient._request_with_retry`

`LLMClient` already owns a per-instance `asyncio.Semaphore` sized to
`max_concurrent` from the provider's config
(`shared/infrastructure/llm/client.py:39, 76`). Every call through
`PromptModel.invoke` → `make_request_with_system_async` →
`_request_with_retry` is already gated by it. A second semaphore at the
engine layer, as originally drafted, would be redundant.

The throughput pathology is one altitude down: the existing semaphore wraps
the *retry loop*, not the individual call
(`client.py:113–140`). On failure, a call holds its slot through up to
three retries with 1s/2s/4s exponential backoff — roughly seven seconds of
slot tenancy per failing call. Under audit-scale fan-out with
`max_concurrent=2`, the slot pool fills with retrying-failing calls within
seconds and the rest of the queue starves. The semaphore is working — it
is being held by doomed retries.

Correction: restructure `_request_with_retry` so the semaphore is acquired
*per attempt* rather than around the retry loop. A failing call releases
its slot during backoff, the next queued call gets it, and the audit makes
progress. This is a `LLMClient`-layer change; `LLMGateEngine` is
unaffected.

Shape of the change (illustrative, not normative):

```python
for attempt in range(len(backoff_delays) + 1):
    async with self._semaphore:
        await self._enforce_rate_limit()
        try:
            return await method(*args, **kwargs)
        except Exception as e:
            # log and decide whether to retry
            ...
    # backoff sleep happens outside the semaphore
    if attempt < len(backoff_delays):
        await asyncio.sleep(backoff_delays[attempt] + random.uniform(0, 0.5))
```

The retry budget and backoff schedule remain as today
(`client.py:111`). Only the semaphore scope changes.

### D5. Cache scope follows semaphore scope

The engine's `_cache` is promoted from per-instance to per-provider, sharing
the keying surface of the semaphore. Two rules using the same provider on the
same `(file, instruction, content)` triple share a cached verdict. This keeps
cache and concurrency budget consistent and avoids the case where the
semaphore serialises calls that the cache would have answered for free.

The cache key continues to include `instruction`, so different rules with
different prompts against the same file remain independent. Cache size is
bounded by a simple LRU at a fixed entry count (configurable per provider;
default 4096). The cache is process-local — no cross-process sharing in this
ADR.

### D6. Failure-mode contract is unchanged

`ENFORCEMENT_UNAVAILABLE → SYSTEM_ERROR_AI_OFFLINE` remains the per-file
failure result. The per-rule aggregate WARNING in `rule_executor.py:208–233`
remains the audit-visible signal. D1–D3 reduce arrival rate at the engine;
D4 reduces per-failure slot tenancy at the client; D5 raises cache hit-rate
across rules. All three are rate-reduction mechanisms; none change the
failure-mode contract. A throttled run that still misses
verdicts still surfaces the same WARNING shape — the governor's observability
of the throughput problem does not regress as the fix lands.

### D7. Implementation order

1. D4 + D5 (retry-loop fix in `LLMClient` and shared cache in
   `LLMGateEngine`). Smallest change; restores some real verdicts on the
   existing rule set without changing rule shape. Each is independently
   mergeable — the retry-loop fix is a `LLMClient` edit, the cache change
   is an engine edit.
2. D2 + D3 (`requires_findings_from` field and executor wiring). Requires a
   META schema update for rule documents and topological ordering in the
   audit driver.
3. Apply `requires_findings_from` to the five `llm_gate` rules listed in the
   #308 table, choosing the cheapest precondition per rule. Document the
   mapping in the rule files themselves; do not invent precondition rules in
   this ADR.

Each step is independently mergeable and independently observable in audit
output.

### D8. Unblocks ADR-042 D4

Once D1–D5 are implemented and `modularity.unix_philosophy` produces real
verdicts across its precondition-narrowed scope, ADR-042 D4 can fire: the
`governed_exclusions` register is retired, and facade-large / algorithm-large
classes answer the responsibility question through their `unix_philosophy`
verdict directly. The seam-large refactor candidates from #192
(`ContextBuilder`, `ProposalExecutor`, `FileRoleDetector`,
`SystemContextGatherer`, `CrawlService`) acquire real structural verdicts at
the same point and can be reclassified (genuine seam-large vs. facade vs.
algorithm) on the basis of the verdict rather than the LOC pre-selector
alone.

---

## References

- GitHub #306: audit pipeline LLM client wiring (landed; this ADR addresses
  the throughput regime it exposed)
- GitHub #307: silent-stub aggregation (landed; aggregate-WARNING shape is
  preserved by D6)
- GitHub #308: llm_gate audit throughput (issue this ADR resolves)
- ADR-042: modularity governance recalibration (D1 framing generalised here;
  D4 conditioned on this ADR)
- ADR-007: original `class_too_large` introduction (historic context for the
  pre-selector pattern)
