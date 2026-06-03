<!-- path: .specs/decisions/ADR-089-f27-exit-criterion-capability-not-usage.md -->

# ADR-089 — F-27 exit criterion: capability proof replaces usage window

**Date:** 2026-06-03
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-03 — drafted under Path A execute-verb authorization, "draft the ADR-085 amendment", after the governor interrogated the original "≥7-day reliable run" criterion and arrived at "local Ollama is weak, DeepSeek is cheap enough — why run that observation at all?")
**Grounding decisions:** ADR-085 D5 (exit criteria are checked against §Context's table) — this ADR amends the F-27 row of that table. ADR-024 D1 (cognitive role assignments via evaluation harness — the capability instrument that already exists). ADR-052 (`llm_resources` configuration schema — the routing surface that already exists). ADR-084 D7 §1 (completeness as constitutional commitment — interpreted here as *capability* completeness, not *usage* completeness).
**Related:** ADR-074 D13 + ADR-080 §D5 precedent — "ADRs are append-only law; reconciliation goes in the later ADR." ADR-085 itself — the constitutional surface this ADR amends one row of.

---

## Context

### The criterion being amended

ADR-085's §Context table line 43 reads:

> | | F-27 Local LLM | registry | promotes from `partial` to `shipping`; reliable local-LLM-only Solo run for ≥7 days |

This ADR amends the third column of that row only. The row in ADR-085 stays verbatim — closure markers and amendments are additive, not in-place, per the same append-only discipline ADR-085 §Context applies to its own Verification log ("The original row above is preserved verbatim — closure markers are additive, not in-place").

### Why the original criterion does not earn its keep

The other four feature commitments in ADR-085's 5+3 list have *capability* exit criteria:

- F-10: "PR annotations + merge-blocking demonstrated against a real external repo" — one demonstration, then ship.
- F-40: "documented public contract; sidecar-shape commercial features F-20/F-34/F-45/F-47 can attach against it without private hooks" — one walk, then ship.
- F-41/F-42/F-43: "one first-party non-code instantiation exists as proof of the plugin-interface contract" — one instantiation, then ship.
- F-48: "`pip install` works; semver tags; CI publishes on tag" — one publish, then ship.

F-27's "reliable local-LLM-only Solo run for ≥7 days" is a *usage* criterion. It does not measure whether the local route works; it measures whether the governor used CORE on local-only for a week. Three problems follow.

**First, the criterion is not load-bearing for what F-27 promises.** Per `papers/CORE-Features.md` F-27 entry, the feature claim is: "CORE supports any HTTP-API-served local LLM... no external provider traffic occurs unless explicitly configured. Provider selection is governed by configuration." That is a capability claim about routing flexibility. The capability is verified by one demonstration that routing to a local model works end-to-end. A 7-day window observes nothing the demonstration does not already prove.

**Second, the criterion conflicts with operational economics.** As of 2026-06-03 the governor's local Ollama deployment runs qwen2.5-coder:3b (ADR-024 D1 LocalCoder) on commodity hardware. DeepSeek-chat is priced at ~$0.27/M output tokens. Switching the governor's day-to-day workflow to local for a measurement window is a deliberate regression in code-generation quality with no offsetting benefit — the capability is already evaluated (ADR-024 D1 with role-qualification matrix and per-prompt scores), the infrastructure exists (`core.llm_resources` schema with per-row `is_available` and `locality`), and the cost calculus says external for the architect's own work.

**Third, the criterion conflates F-27 with F-38.** F-38 (air-gapped deployment, guaranteed) is the feature where local-only actually earns its keep — it is the commercial commitment that says "no provider traffic, contractually." F-27's job is to *make F-38 possible*, not to *be F-38*. F-27 promotes on capability; F-38 promotes (separately, post-exit, commercial) on operational guarantee. Conflating them inside F-27's exit criterion pulls F-38's burden up-funnel and weakens both features' framing.

### Why this is an amendment and not a reframing of ADR-085's intent

ADR-085 D5 says: "Exit criteria are checked against §Context's table, not interpreted." That clause exists so the constraint cannot be relaxed by reinterpretation — the criterion has to be met as written. This ADR is the formal mechanism for *changing what is written*, on the same footing as the original imposition (per ADR-085 D7 "amendment requires written justification on the ADR's footing, not a verbal redirection"). The intent of ADR-085 — engineering capacity concentrates on open-operational-completeness until exit — is unchanged. The shape of one of its exit criteria changes.

### What "demonstrated end-to-end Solo task on local-LLM-only routing" looks like

The new criterion below requires one demonstration with three observable properties:

1. **Routing.** Local Ollama rows backing ADR-024 D1 cognitive roles are enabled (`is_available=true`) for the duration of the demonstration. External provider rows are either disabled or unused.
2. **End-to-end Solo task.** A representative consequence-chain runs to completion — the `build.tests` chain on a real source file is the worked example, since it exercises `ContextService` → `CoderAgent` → LLM routing through the cognitive-role mapping.
3. **Zero external generative traffic during the window.** `core.llm_exchange_log` shows zero entries against remote-locality resources for generative capabilities during the demonstration. Embedding traffic to a remote embedder, if any, is not disqualifying — F-27 governs generative routing; embedding is a separate axis (see Consequences).

The demonstration is a one-shot verification, not a window. Successful completion records as a §Verification entry on ADR-085 (the append-only Verification log it already maintains for closed gate items).

---

## Decisions

### D1 — F-27 exit criterion is amended to a capability demonstration

The third column of ADR-085 §Context table line 43 is amended from:

> promotes from `partial` to `shipping`; reliable local-LLM-only Solo run for ≥7 days

to:

> promotes from `partial` to `shipping`; demonstrated end-to-end Solo task on local-LLM-only routing (capability proof — one consequence-chain run with ADR-024 D1 local rows enabled in `core.llm_resources` and zero generative entries in `llm_exchange_log` against remote-locality resources during the run)

The original row in ADR-085 stays verbatim; this ADR is the controlling statement of the F-27 exit criterion from the date of acceptance forward. When F-27 is closed, ADR-085's §Context Verification log entry cites this ADR as the criterion source.

### D2 — F-27 promotion does not require a measurement window

There is no time component to F-27's exit criterion. The demonstration in D1 satisfies the criterion in one session. ADR-085 D5's "mechanical check" rule continues to apply — the planning doc records the demonstration date; ADR-085's §Context Verification log records the closure; no sustained-window confirmation is required for F-27.

### D3 — Longitudinal local-LLM reliability is not gated by F-27

If longitudinal observation of local-LLM reliability is later judged valuable (operator confidence, regression detection across model updates, F-38 prerequisite work), it is tracked separately — either as a successor ADR on the same footing as ADR-024 D2's "production on-prem role assignments are deferred" clause, or absorbed into ADR-085's signal-quality quality goal if its measurement window is the right surface. F-27 promotion is not blocked behind that future work.

### D4 — Embedding routing is out of F-27's scope

`ollama_nomic_embedding` is currently the only available local resource and serves embedding traffic. F-27's capability claim is about *generative* routing (the cognitive roles assigned in ADR-024 D1 are all generative roles). Embedding routing is governed by the same `llm_resources` configuration but is a separate capability axis. F-27 closure does not assert anything about embedding-side local-only operation; if a separate "local embedder" capability claim is later wanted, it is filed separately.

### D5 — ADR-024 D1 is the qualification instrument, unchanged

ADR-024 D1's per-role local-model assignments (`qwen2.5-coder:3b` for LocalCoder/Architect/LocalReasoner/Planner; `qwen2.5:7b` for DocstringWriter) and ADR-024 D5's qualification harness (`scripts/eval_ollama.py`) remain the canonical instruments for *whether* a given local model qualifies for a role. This ADR does not relitigate that. The F-27 demonstration in D1 uses the existing ADR-024 D1 assignments; if those assignments need refresh against newer local models, that is a successor ADR-024 evaluation pass, independent of F-27.

---

## Consequences

### F-27 promotion collapses from ~7 days to one session

The Tier-3 line in ADR-085 §Consequences (and the planning doc §3) currently anticipates F-27 as a longitudinal commitment. After this amendment, F-27 promotion is a ~30-minute verification act: flip local rows on, run one `build.tests` consequence chain, capture `llm_exchange_log` evidence, flip rows back, update registry + planning doc, record the closure in ADR-085's §Context Verification log.

The Tier-3 sequencing in the planning doc updates as a consequence (operational, per ADR-085 D6 — internal ordering is updateable without ADR amendment).

### F-38 remains the load-bearing local-only commitment

F-38 (air-gapped deployment, guaranteed) was already a commercial, post-exit feature behind the ADR-085 D1 constraint. This amendment makes the F-27 / F-38 separation explicit: F-27 says *the capability exists*; F-38 says *the deployment guarantees it*. Both are real claims; they live at different points on the open/commercial line per ADR-084.

### The 2026-06-03 economic reality is now reflected in the gate

The original F-27 criterion was authored when "local LLM" still carried operator-default connotations from earlier in the project's life. By 2026-06-03, external providers (DeepSeek, Anthropic) have become the day-to-day routing target for the governor's own work — the local rows are disabled in the production `core.llm_resources` precisely because the local models are qualitatively weaker for the governor's tasks. Requiring the governor to regress to local for a week to satisfy a tracker row was theater. This amendment removes the theater.

### ADR-024 evaluation harness remains the place for "is the local route healthy?"

If F-27 closure verification reveals the ADR-024 D1 assignments no longer hold — e.g., the LocalCoder role can no longer pass `violation_remediator` because qwen2.5-coder:3b drifted or the prompt evolved — that surfaces as a known ADR-024 debt item (already tracked under ADR-024 D4 for the `clarity_v2_refactor` fixture gap). It does not block F-27 closure if the *capability* demonstration succeeds with whatever the current ADR-024-qualified local models are.

### Planning doc updates are operational, not constitutional

The amendment lands in three documents:

- This ADR (constitutional) — controlling.
- ADR-085 §Context Verification log, when F-27 closes — references this ADR as the criterion source.
- `planning/CORE-Operational-Completeness.md` §2.1 F-27 "Done" cell, §3 Tier-3, §6 activity log — updated to reflect the new criterion shape.

The planning-doc updates are operational per ADR-085 D6 and do not require ADR amendments of their own. They reference this ADR as the source.

### No effect on the other gate items

This amendment touches only the F-27 row. F-41/F-42/F-43 (extension interfaces) and the three quality goals retain their original ADR-085 criteria. The total exit-criteria count remains 5+3.

---

## Verification

- This ADR exists at `.specs/decisions/ADR-089-f27-exit-criterion-capability-not-usage.md`.
- ADR-085 §Context table line 43 is unchanged (append-only discipline).
- `planning/CORE-Operational-Completeness.md` §2.1 F-27 row "Done looks like" cell is updated to reference this ADR's D1 criterion.
- `planning/CORE-Operational-Completeness.md` §3 Tier-3 F-27 wording updates from "requires the window to complete" to "requires the capability demonstration per ADR-089."
- `planning/CORE-Operational-Completeness.md` §6 activity log records this amendment with date 2026-06-03 and a one-line summary.
- When F-27 closes, the closure entry in ADR-085's §Context Verification log cites ADR-089 D1 as the criterion source and records the `build.tests` consequence-chain evidence + `llm_exchange_log` zero-remote-generative confirmation.

---

## References

- ADR-085 §Context (the 5+3 table whose F-27 row this ADR amends) + §D5 (the mechanical-check clause that makes this amendment necessary) + §D7 (the on-equal-footing-amendment clause that makes this ADR the right surface).
- ADR-084 D7 §1 — "completeness as constitutional commitment." This ADR clarifies that completeness is capability completeness, not usage completeness.
- ADR-024 D1 — local cognitive role assignments. The capability instrument that already exists; this ADR does not relitigate it.
- ADR-024 D2 — "production on-prem role assignments are deferred." Precedent for "we evaluate capability separately from operational deployment."
- ADR-052 — `llm_resources` configuration schema. The routing surface this ADR's D1 demonstration exercises.
- ADR-074 D13 + ADR-080 §D5 — the append-only-amendment precedent this ADR follows.
- `papers/CORE-Features.md` F-27 entry — the capability claim being honored. F-38 entry — the operational commitment F-27 enables but does not impersonate.
- `planning/CORE-Operational-Completeness.md` §2.1, §3, §6 — the operational surfaces this ADR triggers updates in.
- Memory `feedback_hardening_over_coverage` — "hardening live audit violations" beats "authoring more contract surface." The original F-27 criterion drifted toward the latter.
- Memory `feedback_trust_audit_stop_stacking_rungs` — "process for its own sake" is a known anti-pattern. A 7-day window measuring the architect's personal usage habits was that.
