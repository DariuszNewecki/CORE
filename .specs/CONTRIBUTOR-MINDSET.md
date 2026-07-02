<!-- path: .specs/CONTRIBUTOR-MINDSET.md -->

# CORE — Contributor Mental Model

**Status:** Canonical
**Scope:** Human contributors and AI execution arms operating on this repository
**Location:** `.specs/CONTRIBUTOR-MINDSET.md`
**Source:** External governance review finding 9b (2026-06-30); issue #725

---

## 1. Who this document is for

You are a contributor to CORE — human or AI — and you have read enough Python to understand the codebase but not yet enough about the governance model to know *why* some things that look legal are actually prohibited and some things that look redundant are mandatory.

This document gives you the mental model in three sections: what you are permitted to do, what you are forbidden from doing, and why the restrictions exist. The *why* is the load-bearing part — if you understand the goal, you can derive most of the rules yourself.

CLAUDE.md is the development contract; this document is the orientation. Read both. On conflict, `.intent/` is canonical.

---

## 2. What you are permitted to do

### Producing code

- **Edit `src/` through governed mutation surfaces.** Mutations go through `@atomic_action`-decorated functions dispatched via `ActionExecutor.execute()`. If you are writing a function that changes files on disk, it is an atomic action. If it is not, it is wrong.
- **Write files through `FileHandler`.** `FileHandler(str(repo_root)).write_runtime_text(rel_path, content)` is the only legal write surface in production code. No `Path.write_text()`, no `open(..., 'w')`.
- **Write tests alongside the change.** A signature or behavior change in `src/` ships with its test update in the same commit. New public symbols ship with at least a basic test. The test-generation loop is scope-limited and does not compensate.

### Reading governance data

- **Read `.intent/` through `IntentRepository`.** Call `get_intent_repository().initialize()` and use the returned object. Never `Path(".intent/...").read_text()` or any direct `glob()`. The repository resolves inheritance, validates schema, and gives you structured objects; raw file reads give you strings that may be stale or malformed.

### Logging and output

- **Use `shared.logger.getLogger(__name__)` for operational output.** Never `logging.getLogger` directly. Rich objects (Table, Panel, Rule) and markup go through `console.print()`, never through `logger.info()`.

### Workers communicating

- **Post to the blackboard.** `Worker.post_finding()`, `post_report()`, and `post_heartbeat()` are the only channels between autonomous entities. Workers discover each other's output through the blackboard; they never call each other directly.

### Making decisions in code

- **Mind layers decide; Body layers execute.** Strategists produce `next_suggested` without side effects. Evaluators assess quality without side effects. Workers execute under constitutional control. Keep the phases separate.

---

## 3. What you must never do

Each prohibition carries its *why* — the structural reason, not just the rule name.

### 3.1 `Path.write_text()` / `open(..., 'w')` in production code

**Why:** Every write that bypasses `FileHandler` bypasses the audit trail. CORE's governance model is built on the premise that mutations are traceable and attributable. A direct write is invisible to the audit engine, the blackboard, and the commit-attribution invariant (ADR-101). It also bypasses sandbox isolation (ADR-071/ADR-106) and may write to the real tree when the governance runtime expects an isolated sandbox. Rule: `governance.mutation_surface.filehandler_required`.

### 3.2 Calling another Worker directly

**Why:** Workers are autonomous entities with declared mandates and blackboard identities. A direct call makes their execution invisible — no blackboard entry, no heartbeat, no discoverable state. The system can no longer audit what ran, when, or whether it completed. Blackboard-mediated coordination is the only form of inter-worker communication the governance model can reason about. CORE-Workers-and-Governance-Model.md §4.

### 3.3 Importing `get_session` / `AsyncSession` in Mind or Will

**Why:** Mind contains rule logic; Will contains orchestration. Neither should hold a database handle. The boundary is not a style convention — it is a load-bearing isolation that ensures Mind is stateless and Will delegates persistence to Body. If Mind or Will can reach the database directly, the layer separation collapses and the entire audit-engine architecture becomes unverifiable. Rule: `architecture.boundary.database_session_access`.

### 3.4 Importing `Settings` in Body, Mind, or Will

**Why:** `Settings` carries machine-specific secrets and environment paths. If any logic layer can reach `Settings` directly, the deployment surface becomes untestable in isolation and configuration drift becomes invisible. Configuration flows into components through dependency injection; the infrastructure bootstrap layer is the single sanctioned import site. Rule: `architecture.boundary.settings_access`.

### 3.5 Calling `asyncio.run()` or creating event loops in logic modules

**Why:** CORE runs on a single shared event loop managed by the daemon. A nested `asyncio.run()` call creates a second loop, which raises `RuntimeError` in the shared context and can deadlock long-running workers. Logic modules receive an already-running loop; they never create one. Rule: `async.no_manual_loop_run`.

### 3.6 Reading `.intent/` via raw `Path.glob()` or `read_text()`

**Why:** `.intent/` documents are law. But law as text is not the same as law as interpreted. The `IntentRepository` validates schema, resolves `$ref` cross-references, applies inheritance rules, and returns structured objects that governance engines can act on. A raw file read gives you the bytes; it does not give you the meaning, and it bypasses validation that catches drift between document versions. Rule: `architecture.intent.gateway_is_shared_infrastructure`.

### 3.7 Returning anything other than `ActionResult` from an `@atomic_action`

**Why:** The governance validation layer reads `ActionResult` to confirm impact classification, verify policy compliance, and decide whether to proceed. A tuple return, a bare dict, or a raised exception short-circuits validation and makes it impossible to audit the outcome. The governance model treats a non-`ActionResult` return as a bypass attempt, not a valid completion. Rule: `atomic_actions.no_governance_bypass`.

### 3.8 Importing LLM client infrastructure in Body or Mind

**Why:** Body executes mutations; it must not make AI decisions. Mind evaluates rules; it must not invoke AI. LLM calls carry non-determinism, cost, and latency that are incompatible with the deterministic, side-effect-free contract of both layers. AI capability is scoped to Will and autonomous services. Rule: `architecture.boundary.llm_client_access`.

### 3.9 Instantiating async engines at module import time

**Why:** Module-level async objects bind to the event loop at import time. When the daemon imports a module before the loop is running (or the wrong loop is active), the binding is wrong and the engine silently fails on first use. Async engines are constructed inside coroutines or factory functions, after the event loop is established. Rule: `architecture.no_module_async_engine`.

### 3.10 Writing to `/tmp/` or outside the repo

**Why:** CORE's sandbox model (ADR-071/ADR-106) isolates mutations to `var/tmp/<uuid>/` within the repo so they can be inspected, rolled back, and attributed. Writes to system `/tmp/` escape the sandbox boundary, cannot be audited, and may pollute another actor's workspace. All temp writes use `var/tmp/` (repo-relative) with `dir=repo_root / "var" / "tmp"` passed explicitly to any `tempfile` call. CLAUDE.md §"Never modify".

---

## 4. Why these rules exist — the constitutional goal

The restrictions above are not style preferences. They are load-bearing constraints on a specific architectural goal:

**CORE must be able to audit, attribute, replay, and govern every mutation it makes to governed projects.**

This requires:

- **Auditability** — every write goes through a surface the audit engine can inspect (`FileHandler`, `@atomic_action`, blackboard entries).
- **Attribution** — every mutation has a traceable author (the `@atomic_action` identity, the Worker's declared UUID, the commit's Co-Authored-By chain).
- **Replayability** — the blackboard contains the complete event log; Workers that read only the blackboard can replay their behavior deterministically.
- **Layer isolation** — Mind is stateless and AI-free; Body is side-effect-gated; Will orchestrates but delegates mutations. This separation is what makes the individual layers testable, auditable, and replaceable.
- **Governed non-determinism** — LLM calls are real but their outputs are mediated. AI generates code; it does not commit code, does not evaluate its own output for constitutional compliance, and does not bypass the human governor review gate.

The 71 rules currently in force (35 blocking, 27 reporting, 9 advisory) are not an enumeration of bad things someone once did. They are the formal expression of these five properties. When a rule feels bureaucratic, the question to ask is: *which of the five properties does this rule protect, and what breaks if it is removed?*

---

## 5. Common failure modes

See `CORE-Common-Governance-Failure-Modes.md` for a full catalog. The three most common for new contributors:

1. **The shortcut write** — using `Path.write_text()` because `FileHandler` is unfamiliar. The fix: every write in `src/` goes through `FileHandler`; find it in `src/shared/infrastructure/file_handler.py`.

2. **The ambient import** — importing a Will or Body symbol at module level in the wrong layer because it "happens to work" in dev. The fix: check the layer of every new import against the boundary rules before committing. Lazy (function-scoped) imports are sometimes the governed escape hatch, but they require a companion closure ADR (ADR-049 D3).

3. **The direct worker call** — calling another worker's method directly because the blackboard feels like indirection. The fix: post a finding or report to the blackboard; the target worker reads it on its next cycle. If the coupling is real, model it as a Flow, not a direct call.

---

## 6. Where to look

| Question | Look here |
|---|---|
| What is this system trying to be? | `.specs/CORE-CHARTER.md` §6; `CORE-Constitutional-Foundations.md` |
| How do the layers relate? | `CORE-Mind-Body-Will-Separation.md` |
| What are the current rules? | `CLAUDE.md` §"Constitutional rules" (digest); `.intent/rules/architecture/` (canonical) |
| How does the blackboard work? | `CORE-Blackboard.md`; `CORE-Workers-and-Governance-Model.md` |
| How does mutation flow? | `CORE-Action.md`; `CORE-Adaptive-Workflow-Pattern.md` |
| What is a Flow? | `CORE-Adaptive-Workflow-Pattern.md` |
| How does governance conflict resolve? | `CORE-Rule-Conflict-Semantics.md` |
| Why does `.intent/` read as data, not code? | `CORE-Constitution-Read-Only-Contract.md` |
| How is a Worker declared? | `.intent/workers/`; `CORE-Workers-and-Governance-Model.md` §3 |
