# CLAUDE.md — CORE

Loaded automatically at the start of every Claude Code session. Read fully before touching code.

---

## What CORE is, and what you are

CORE is a constitutionally-governed software factory: a runtime that supervises AI code
generation under deterministic rules. `.intent/` is law (read by the runtime); `.specs/` is
architectural reasoning (read by humans); `src/` is the implementation.

You (Claude Code) are the execution arm, not the governor. The human owns this repo, writes
intent, and reviews outputs — they do not write code manually. Your job is to produce correct,
complete files that conform to `.intent/` and the decisions in `.specs/decisions/`. AI output
is not trusted by default — it is verified. Produce work that earns the verification.

This file is a **development contract**, not a runtime governance posture. CORE is
bootstrapped on itself; the restrictions here govern how Claude Code works on this repo and
are intentionally permissive under governor confirmation. The strong version — what CORE
enforces on governed projects at runtime — lives in `.intent/`. Do not import that live
strictness into this dev contract, and do not export this dev permissiveness into runtime rules.

---

## Source layout

```
src/
  api/        — FastAPI routes and dependency providers only. No business logic.
  body/       — Analyzers, atomic actions, services, infrastructure workers. Execution layer.
  cli/        — Typer CLI commands. Rich rendering allowed here only.
  mind/       — Constitutional logic engines (ast_gate, glob_gate, llm_gate, runtime_gate, …).
                Reads .intent/ at runtime. No I/O, no execution, no Body/Will invocation.
  shared/     — Cross-cutting substrate. Must not import src/mind/, src/body/, or src/will/.
  will/       — Autonomous developer, cognitive orchestration, agents.
.intent/      — Governance law as data (YAML/JSON). Read at runtime via IntentRepository;
                never imported as Python.
.specs/       — Charter, northstar, papers/ (47+), requirements/ (URS), decisions/ (ADRs),
                planning/ (roadmaps).
```

Mind/Body/Will names *code* layers; `.intent/` and `.specs/` are *data* surfaces. Do not
conflate "the Mind" (`.intent/`) with "the Mind layer in code" (`src/mind/`).

**ADRs are live.** Authored by the human before implementation, then implemented as a
change-set. If an ADR is referenced in a prompt, read it before editing. Before editing a
layer or subsystem you have not seen before, check `.specs/papers/` and `.specs/decisions/`.

---

## How to work in this repo

**Reconnaissance before editing.** For any file/module not seen this session: read it, report
what you found, identify every affected call site — then edit. For non-trivial changes
(multi-file, schema changes, new fields on shared models, >3 files) pause after
reconnaissance for governor review.

**Tests are part of the change.** Signature/behavior change in `src/` → update the
corresponding test in the same change. New public function/class → at least basic tests. You
cannot run `pytest` (governor verifies) but you must author the tests. Do not rely on the
autonomous test-gen loop to compensate: it is deliberately scope-limited to a single-file
pilot (`include_files` in `.intent/enforcement/config/test_coverage.yaml`), so it does not
cover most of `src/`. Its write-time gates have since hardened — import-resolution + shape
checks (#574, #589) plus a `test.sandbox_validate` execution gate that rejects generated
tests which fail to run — but until that scope opens, tests for your change are on you.
Minimum-scope does **not** exempt test updates.

**Complete files, not diffs.** Output the complete file content in a fenced block labelled
with its path. The governor reviews whole files.

**Verification after editing.** Run `ruff check` on every file touched; run import/
instantiation smoke tests where possible. Do NOT run `pytest`, do NOT commit — governor
actions. Restarting `core-daemon` + `core-api` is in-scope when a fix needs
operationalization (the daemon caches imported modules); avoid restarting mid-flight against
an active CCC scan or long-running remediation.

**When in doubt, ask.** Do not invent requirements or infer CLI commands from plausibility.
If a brief says "atomic action" and no CLI surface exists to invoke one, ask rather than
writing a throwaway script.

---

## Governed and prohibited surfaces

### `.intent/` and `.specs/` — the confirmation gate

Both are human-authored by default. Default posture: **draft-in-response** — produce the
complete corrected file in the response; the governor applies it. Direct writes are permitted
only under one of two paths, both governor-initiated:

**Path A — confirmed write (semantic edits permitted).** The governor explicitly confirms a
write to a named file in the current turn. **Turn-scoped**: authorizes the writes named in
that turn only; does not carry forward.

**Path B — authorized mechanical substitution.** A purely syntactic change the governor named
in the prompt, where all four hold: (1) explicitly authorized — the governor names the
transformation; no inferring, optimizing, or improving it; (2) purely syntactic — a string or
regex substitution; if applying it requires understanding the governance meaning, it is
semantic → Path A; (3) no content added or removed — no "while you're at it" fixes, no
reorganization; (4) semantically invariant — two readers interpret the file the same way
before and after. Passing examples: filename-rename propagation, path-reference updates after
a move, renaming a governor-decided constant.

**Constitutional core — heightened confirmation.** `.intent/constitution/`, `.intent/META/`,
`.intent/rules/governance/` define the governance frame. Path A reaches them, but the
governor must name the **specific** file in the confirmation (no blanket "go ahead"), and
Claude Code surfaces the change for review before writing.

When neither path applies, draft-in-response. Direct writes are the exception.

### Never modify

Machine-specific infrastructure — never "fix" paths or settings here. Your container may
mount the repo at a path other than the server's `/opt/dev/CORE`; that is a container
artifact, not a bug.

- `.env`, `.venv/`, `*.pth` — environment/venv/path config for this machine
- `var/` — runtime data; read-only unless explicitly asked
- Anything outside `src/`, `tests/`, `.intent/`, `.specs/`, `var/prompts/`, `CLAUDE.md`
- `/tmp/` — **prohibited.** All temp writes use `var/tmp/` (repo-relative). Never
  `tempfile.gettempdir()` or any `tempfile` default outside the repo; pass
  `dir=repo_root / "var" / "tmp"` explicitly.

---

## Constitutional rules

Derived operational digest. `.intent/` is canonical: on divergence, `.intent/` wins — surface
the divergence, don't resolve it in code. Severity is read from each rule's on-disk
`enforcement` field (`blocking` / `reporting` / `advisory`); blocking rules stop a commit,
the other two surface findings. At digest time: 31 blocking + 27 reporting + 9 advisory = 67.

**Integrity check (run before trusting this digest):** the digest's rule-id set must equal
`jq -r '.rules[].id' .intent/rules/architecture/*.json | sort -u`. A mismatch means the
digest has drifted — surface it to the governor.

### Blocking rules — stop a commit

**Atomic actions (`src/body/atomic/**/*.py`)**
- `atomic_actions.must_have_decorator` — Functions registered with `@register_action` MUST also have `@atomic_action` with required metadata (action_id, intent, impact, policies).
- `atomic_actions.must_return_action_result` — `@atomic_action` functions MUST declare `ActionResult` as their return type annotation and actually return `ActionResult` instances.
- `atomic_actions.result_must_be_structured` — `ActionResult.data` MUST be a dictionary with string keys; nested structures permitted, top level must be a dict.
- `atomic_actions.no_governance_bypass` — No atomic action MAY return types other than `ActionResult` to bypass governance validation; tuple returns are explicitly forbidden.
- `atomic_actions.must_accept_kwargs` — `@atomic_action` functions MUST include `**kwargs`; the check fires at decoration (import) time.
- `atomic_actions.impact_level_must_be_governed` — Impact classification MUST be declared in `.intent/enforcement/config/action_risk.yaml` keyed by `action_id`, not embedded in `src/`.
- `atomic_actions.fix_action_scope` — `fix.imports` is exclusively import ordering/sorting; `check.imports` is the authority for import-resolution verification.
- `architecture.flows.atomic_action_must_not_compose` — An `@atomic_action` MUST NOT internally invoke other registered AtomicActions via `ActionExecutor.execute()`; composition belongs to Flows.

**Flows**
- `architecture.flows.flow_declared_in_intent` (`src/**`) — Every Flow MUST be declared in `.intent/flows/*.yaml` and registered in `FlowRegistry`; Python-data-structure Flows are forbidden.
- `architecture.flows.flow_must_not_post_to_blackboard` (`src/body/flows/**`) — Flows MUST NOT call `post_finding()`, `post_report()`, `post_heartbeat()`, or INSERT/UPDATE `core.blackboard_entries`.
- `architecture.flows.flow_must_not_create_proposals` (`src/body/flows/**`) — Flows MUST NOT create, submit, or approve `Proposal` objects.
- `architecture.flows.flow_must_propagate_write_false` (`src/body/flows/executor.py`) — FlowExecutor MUST propagate `write=False` to every step; the flag is caller-supplied and immutable per Flow execution.

**Blackboard (`src/**`)**
- `architecture.blackboard.worker_only_inserts` — INSERT against `core.blackboard_entries` MUST originate from the Worker base class; services and atomic actions route through `self.post_finding()` / `post_report()` / `post_heartbeat()`.
- `architecture.blackboard.reaudit_requires_reaudit_mechanism` — Every UPDATE to `status='awaiting_reaudit'` MUST co-occur with `resolution_mechanism = 'reaudit'` in the same WHERE clause.

**Privileged-boundary imports**
- `architecture.boundary.database_session_access` (mind|will) — Only infrastructure, Body, and shared services MAY import `get_session` / `AsyncSession` directly; Mind and Will MUST use DI.
- `architecture.boundary.settings_access` (body|mind|will) — Only infrastructure and bootstrap MAY import `Settings` directly; others receive configuration via DI or environment abstraction.
- `architecture.boundary.file_handler_access` (mind|will) — Only Body and infrastructure MAY instantiate `FileHandler` directly; Will and Mind delegate file operations to Body services.
- `architecture.boundary.llm_client_access` (body|mind) — Only Will and autonomous services MAY import LLM client infrastructure; Body MUST NOT make AI decisions, Mind MUST NOT invoke AI.
- `architecture.shared.no_layer_imports` (`src/shared/**`) — Shared MUST NOT import from `src/mind/`, `src/body/`, or `src/will/`. (8 `excludes:` pending closure ADRs per ADR-049 D1/D3; no new excludes without a companion closure ADR.)

**Channels**
- `architecture.channels.logic_logger_only` (`src/**`) — Non-UI runtime and logic modules MUST use the CORE standard logger for operational output.
- `architecture.channels.api_structured_output_only` (`src/api/**`) — API modules MUST use structured response mechanisms and MUST NOT use terminal-oriented rendering.

**Async / module-time / paths (`src/**` unless noted)**
- `async.no_manual_loop_run` — Logic modules MUST NOT call `asyncio.run()` or manually create event loops.
- `logic.di.no_global_session` (`src/features/** | src/body/services/**`) — MUST NOT import `get_session` globally; database access MUST be injected.
- `architecture.no_module_async_engine` — Async execution engines MUST NOT be instantiated at module import time.
- `architecture.path_access.no_hardcoded_runtime_dirs` — Runtime output directory names MUST NOT appear as string literals in path construction; route through `PathResolver` or `FileHandler`.

**Patterns / mutation surface**
- `architecture.patterns.action_pattern` (`src/body/atomic/** | src/cli/commands/**`) — Action commands MUST use `@atomic_action` and have a `write` parameter defaulting to `False`.
- `governance.mutation_surface.filehandler_required` (`src/** | features/**`) — All filesystem writes MUST route through `FileHandler`; direct `write_text()`, `write_bytes()`, or `open(...)` in write/append mode are prohibited in production code.

**Constitution / governance read-only (`src/**`)**
- `architecture.constitution_read_only` — The constitutional intent directory MUST be immutable.
- `architecture.meta_read_only` — Intent schema and META artifacts MUST NOT be mutated at runtime.
- `governance.constitution.read_only` — `.intent/**` MUST be treated as immutable by all system components.
- `governance.logic_mutation.governed` — Permanent modifications to production logic within `src/` MUST occur only through governed mutation surfaces.

### Reporting / advisory rules — surface findings, do not block

Marked `[r]` reporting / `[a]` advisory per the on-disk `enforcement` field.

**Mind (`src/mind/**`)** — all `[r]`: `no_database_access` (MUST NOT import `get_session`); `no_filesystem_writes`; `no_body_invocation`; `no_will_invocation`; `architecture.layers.no_mind_execution` (no I/O, no action invocation); `no_execution_semantics` (no risk classification, decision-making, caching strategies, validation enforcement); `execution_signal` (pre-selector, no verdict).

**Body** — `architecture.body.no_rule_evaluation` [r] — MUST NOT evaluate constitutional rules directly. `architecture.layers.no_body_to_will` [r] — MUST NOT import/invoke Will (narrow 4-sub-path scope per ADR-049 D1, pending tightening).

**Will** — `architecture.will.no_direct_database_access` [r]; `no_filesystem_operations` [r — SHOULD delegate to Body]; `must_delegate_to_body` [r — orchestration SHOULD import and delegate to Body services].

**API** — `architecture.api.no_direct_database_access` [r] — MUST NOT import `get_session` directly; sanctioned repositories/services via `api/dependencies.py` ARE permitted (ADR-049 D1 §6 supersedes the broader framing). `must_route_through_will` [r — SHOULD; API → Will use-case layer recorded as architectural debt per ADR-049 D1]. `no_body_bypass` [r — SHOULD NOT directly import Body services].

**Shared / layout** — `architecture.shared.no_strategic_decisions` [r]; `architecture.layer_exclusivity` [r] — every `src/` file resides in a constitutional layer, sanctioned infra dir (`shared/`, `api/`), or root entry point.

**Channels** — `architecture.channels.logic_no_terminal_rendering` [r]; `cli_rendering_allowed` [r — positive permission]; `logger_not_presentation` [r — logger MUST NOT be used as a presentation renderer].

**Logging / governance** — `logic.logging.standard_only` [r — standard `getLogger`, no f-strings]; `governance.artifact_mutation.traceable` [r — artifacts/logs/reports SHOULD go via `FileHandler`]; `governance.dangerous_execution_primitives` [r — `eval`/`exec`/`compile`/`subprocess` require documented justification; Will MUST NOT use them; Body MAY in designated sanctuary modules].

**Intent access** — `architecture.intent.no_legacy_root_assumptions` [r]; `architecture.namespace.no_direct_protected_access` [r — no direct filesystem crawling/parsing of `.intent`; route through shared intent infrastructure]; `architecture.intent.gateway_is_shared_infrastructure` [r — consume `.intent` through `src/shared/infrastructure/intent/`].

**Modernization** — `modernization.legacy_signal` [r — pre-selector, no verdict]; `modernization.legacy_scars` [a — SHOULD be free of obsolete shims, unused legacy parameters, wrappers bypassing the Universal Workflow Pattern].

**Workers / discovery / quality** — all `[a]`: `architecture.flows.worker_must_not_hardwire_sequence` (a Worker `run()` MUST NOT contain an explicit ordered sequence of `ActionExecutor.execute()` calls extractable into a named Flow); `architecture.artifact_discovery_through_registry` (declared-only; discovery MUST consult the artifact_type registry via `IntentRepository`; hardcoded extension globs forbidden); `governance.intent_meta.required`; `governance.no_governance_bypass` (if a precondition cannot be evaluated, block); `modularity.unix_philosophy`; `quality.type_safety` (MyPy); `quality.security_audit` (pip-audit); `quality.test_integrity` (suite passing, no collection errors).

### Operational corollaries

- API routes acquire DB sessions through `api.dependencies` (`get_api_session` for handlers,
  `open_background_session` for background tasks). `src/api/dependencies.py` is the single
  sanctioned site for the `shared.infrastructure.database` import in `src/api/`.
- Body components receive configuration via DI (`repo_root`, `prompt_root`, …); on missing
  parameters return `ComponentResult(ok=False, …)` rather than reaching for `settings`.
- `.intent/` is accessed through `IntentRepository` (`get_intent_repository().initialize()`),
  never raw `Path(".intent/…").read_text()` or `glob()`.
- Analyzers in `src/body/analyzers/` are PARSE-phase: read-only, deterministic,
  side-effect-free, returning `ComponentPhase.PARSE`.

---

## Rich rendering rules

Rich objects (Table, Panel, Rule, …) and strings containing Rich markup MUST go through
`console.print()` — never `logger.info()`. Logger strings are plain text only. `console` is a
module-level `Console()` instance. CLI layer (`src/cli/`) may render freely; logic/Will
layers must not import `rich.console` directly.

```python
console.print(table)                              # CORRECT
logger.info(table)                                # WRONG
logger.info("[bold green]Success[/bold green]")   # WRONG — markup in logger
```

---

## Symbol IDs — required on every public definition

Every public class and function carries `# ID: <uuid>` on the line immediately before `def`
or `class`. Generate a fresh UUID v4 per symbol (`python -c 'import uuid; print(uuid.uuid4())'`).
Never reuse or copy existing IDs. Private symbols (`_name`) are exempt. Placeholder
`xxxxxxxx-…` strings are intentionally malformed — never paste them. Worker `identity.uuid`
values in `.intent/workers/*.yaml` follow the same rule.

```python
# ID: <fresh-uuid-v4>
class MyNewComponent(BaseAnalyzer):
    # ID: <fresh-uuid-v4>
    async def execute(self, **kwargs) -> ComponentResult:
        ...
```

---

## Component phases

| Phase | Base Class | Rule |
|-------|-----------|------|
| `INTERPRET` | — | Parse user intent into canonical task structure |
| `PARSE` | `BaseAnalyzer` | Read-only, deterministic fact extraction |
| `LOAD` | — | Pure data retrieval from storage |
| `AUDIT` | `BaseEvaluator` | Quality assessment and pattern detection |
| `RUNTIME` | `BaseStrategist` | Deterministic, rule-based decisions (no LLM calls) |
| `EXECUTION` | Workers / atomic actions | Mutations under constitutional control |

Strategists are not evaluators: evaluators assess quality; strategists make decisions and
produce `next_suggested`. Both are side-effect-free.

**Workflow stage ordering — never skip:**

```
interpret.intent → parse.plan_actions → load.operational_context
  → runtime.{generate_changes | generate_tests | repair_changes}
    → audit.{validate_changes | canary_validation | sandbox_validation | style_check}
      → execution.commit_changes
```

Invariants per stage live in `.intent/workflows/stages/*.yaml`. Stages marked
`must_not: commit changes` never write; only `execution.commit_changes` writes to disk.

---

## The autonomous test-generation loop

`TestCoverageSensor` (governed by `.intent/enforcement/config/test_coverage.yaml`) posts
`test.run_required`; `TestRunnerSensor` posts `test.failure` / `test.missing`;
`TestRemediatorWorker` creates one `build.tests` proposal per source file;
`ProposalConsumerWorker` executes approved proposals via `ActionExecutor` → `build.tests`
atomic action → `CoderAgent` → `ContextService` → LLM. Token-free except `build.tests`
itself. Do not short-circuit it; no direct worker-to-worker calls. Source→test path mapping
is governed — use `shared.infrastructure.intent.test_coverage_paths.source_to_test_path`,
never hardcoded string replacement.

---

## Key patterns

**ActionResult for atomic actions (not ComponentResult):**
```python
from shared.action_types import ActionResult
return ActionResult(action_id=self.action_id, ok=True, data={...},
                    impact=ActionImpact.WRITE_CODE, duration_sec=elapsed)
```

**RefusalResult is a first-class outcome, not an error** — when a component cannot proceed,
use the appropriate factory, not bare `ComponentResult(ok=False)`:
```python
from shared.models.refusal_result import RefusalResult
return RefusalResult.extraction_failed(component_id=self.component_id, reason="...")
# also: .low_confidence, .boundary_violation, .quality_threshold
```

**Mutations use `@atomic_action` and route through `ActionExecutor`** — direct calls to
decorated functions raise `GovernanceBypassError`; the executor sets the governance token:
```python
from shared.atomic_action import atomic_action, ActionImpact

@atomic_action(action_id="my.action.id", intent="Short description",
               impact=ActionImpact.WRITE_CODE, policies=["relevant.policy.id"])
async def my_action(file_path: str, content: str, **kwargs) -> ActionResult: ...
```

**ExecutionTask.task_type carries the caller's actual intent** (`"code_generation"`,
`"test_generation"`, `"code_modification"`, …) — it routes through `CoderAgent` to
`ContextService.build_for_task` and into the correct governance phase. Closed vocabulary in
`shared.models.execution_models`. See ADR-003.

**Workers communicate exclusively via the blackboard:**
```python
class MyWorker(Worker):
    declaration_name = "my_worker"  # matches .intent/workers/my_worker.yaml
    async def run(self) -> None:
        await self.post_finding("subject", {"key": "value"})
        await self.post_report("subject", {"result": "done"})
        await self.post_heartbeat()
```
At least one blackboard entry per run. Direct inter-worker communication is prohibited.
Payloads are auto-sanitized to ASCII before DB insert.

**CLI commands use `@core_command`** — `ctx: typer.Context` is always the first parameter; it
manages the asyncio loop, injects services, and formats `ActionResult` output. Mutating
commands set `dangerous=True`:
```python
@app.command()
@core_command(dangerous=False, requires_context=True)
async def my_command(ctx: typer.Context) -> ActionResult: ...
```

**Background tasks use `open_background_session`:**
```python
async def run_task() -> None:
    async with open_background_session() as session:
        await do_work(session=session)
background_tasks.add_task(run_task)
```

**ComponentResult is the universal return type for Body components:**
```python
return ComponentResult(component_id=self.component_id, ok=True, data={...},
                       phase=self.phase, confidence=1.0, duration_sec=elapsed,
                       metadata={"rationale": "..."})
```

**File mutations go through FileHandler, never `Path.write_text`:**
```python
from shared.infrastructure.file_handler import FileHandler
FileHandler(str(repo_root)).write_runtime_text("relative/path.py", content)
```

---

## After making changes

`DbSyncWorker` (`.intent/workers/db_sync_worker.yaml`) runs `sync.db` on a ~5-minute cadence;
routine edits reach the PostgreSQL graph and vectors without operator action. Suggest the
governor run `core-admin dev sync --write` (interactive-confirm; governor-only) **only** when:
the code is not yet constitutionally clean (the CLI runs a *fix* phase first; the worker
syncs only); the governor wants synchronous confirmation before committing; or `DbSyncWorker`
is stalled (no recent `sync.db.complete` report, or `last_heartbeat` materially older than
its 300-second `max_interval`).

---

## Commit authorship integrity (ADR-101 D1)

A commit's diff MUST contain only bytes its author produced. Constitutional; applies to every
committer. Path scope is a permission boundary; authorship is a production boundary — two
separate surfaces. Operationally:

- **Stage specific files by name.** Never `git add -A`, `git add .`, or `git commit -a` when
  the tree may contain other actors' work.
- **Never amend a commit you didn't author this turn** — `--amend` re-attributes the prior
  commit to your session.
- **Never `git checkout .`, `git restore .`, or `git clean -f`** — restore only specific
  paths the governor explicitly authorized.
- **Co-Authored-By trailers** are the explicit-consent mechanism for jointly-authored
  commits; use them for genuine collaboration, omit when the bytes are purely the user's.

The autonomous daemon is bounded the same way (ADR-101 D2: commit set derives from the
action's sandbox production, not `proposal.scope.files`). ADR-021's path-shaped guards are
superseded by ADR-101 and removed from the codebase — don't reach for them.

---

## Pre-commit checklist

1. The diff contains only bytes you produced this turn — no user WIP, no stash residue (ADR-101 D1)
2. No direct DB imports in `src/api/` outside `api/dependencies.py`
3. No `settings` imports in `src/body/`
4. Every new public `def`/`class` has a `# ID: <uuid>` comment (private `_name` exempt)
5. No `.intent/` access via raw `Path` in Body, Will, or API code
6. Analyzers have no write side effects
7. No `src/body/` imports from `src/will/`
8. No `src/will/` direct imports from the database session layer
9. All mutation functions use `@atomic_action` via `ActionExecutor`
10. Workers post to blackboard; never call other workers directly
11. Constitutional compliance comment at the top of modified files reflects the change
12. No Rich objects or markup passed to `logger.info()`
13. `.env`, `.venv/`, `*.pth` untouched; any `.intent/`/`.specs/` write satisfied the
    confirmation gate (Path A or B); any constitutional-core write was confirmed by the
    governor naming that specific file this turn
14. Every relevant ADR in `.specs/decisions/` honored
15. No writes to `/tmp/` or outside the repo — temp files in `var/tmp/` only
16. Signature/behavior changes have test updates in the same commit; new public symbols have
    at least a basic test ("Tests are part of the change")

---

## Tech stack

Python 3.12 (`from __future__ import annotations` in every file) · FastAPI + SQLAlchemy
async (PostgreSQL) · Typer + Rich · pytest + pytest-asyncio ·
`shared.logger.getLogger(__name__)` — never `logging.getLogger` directly.
