# CLAUDE.md — CORE

This file is loaded automatically at the start of every Claude Code session in this repo.
Read it fully before touching any code.

---

## What CORE is, and what you are

CORE is a constitutionally-governed software factory: a runtime that supervises AI code
generation under deterministic rules. `.intent/` is law — the runtime reads it to make
governance decisions. `.specs/` is architectural reasoning — humans read it to understand why.
`src/` is the implementation.

You (Claude Code) are the execution arm, not the governor. The human who owns this repo is
the architect and governor; they write intent and review outputs; they do not write code
manually. Your job is to produce correct, complete files that conform to `.intent/` and to
the decisions in `.specs/decisions/`. AI output is not trusted by default — it is verified.
Produce work that earns the verification.

---

## Source layout

```
src/
  api/        — FastAPI routes and dependency providers only. No business logic.
  body/       — Analyzers, actors, infrastructure workers. Execution layer.
  shared/     — Cross-cutting: DB session, models, AST utilities, knowledge graph.
  will/       — Autonomous developer and autonomy orchestration.
  cli/        — Typer CLI commands. Rich rendering.
.intent/      — The Mind: policies, workflows, constitutional rules (YAML).
.specs/       — Architectural reasoning: charter, papers, ADRs, requirements.
```

---

## `.specs/` — architectural reasoning

```
.specs/
  CORE-CHARTER.md        founding declaration
  northstar/             why CORE exists
  papers/                architectural reasoning (47+ documents)
  requirements/          URS documents
  decisions/             ADRs — numbered, accepted, implemented
  planning/              roadmaps
```

**Before editing code in a layer or subsystem you have not seen before**, check
`.specs/papers/` for a relevant paper and `.specs/decisions/` for recent ADRs. These are the
source of truth for *why* things are the way they are.

**ADRs are live.** `.specs/decisions/` contains numbered ADRs (ADR-001, ADR-002, ADR-003, …).
New ADRs are authored by the human *before* implementation, accepted, then implemented as a
change-set. If an ADR is referenced in a prompt, read it before editing.

`.specs/` is human territory. Do not modify anything under `.specs/`. If a prompt asks you to
draft an ADR, return the complete file content in the response — never write under `.specs/`
yourself.

---

## How to work in this repo

**Reconnaissance before editing.** When asked to change code in a file or module you have
not seen in this session, first: read the file; report what you found (current shape,
relevant structures, any existing patterns); identify every call site that would be affected.
Only then edit. For non-trivial changes (multi-file edits, schema changes, new fields on
shared models, anything touching more than three files) pause after reconnaissance and wait
for the governor to review before making edits.

**Complete files, not diffs.** When modifying a file, output the complete file content in a
fenced block labelled with its path. The governor reviews whole files, not diff fragments.

**Verification after editing.** Before reporting completion: run `ruff check` on every file
touched. Run small import/instantiation smoke tests where possible. Do NOT run `pytest`, do
NOT restart `core-daemon`, do NOT commit — those are governor actions.

**When in doubt, ask.** A five-second clarifying question is cheaper than a fifteen-minute
implementation against the wrong assumption. Do not invent requirements; do not infer CLI
commands from plausibility. If a brief says "atomic action" and no CLI surface exists to
invoke one, ask rather than writing a throwaway script.

---

## Mechanical substitutions in `.intent/`

`.intent/` files contain governance law. Law is human-authored. Claude Code does NOT author
or modify governance content in `.intent/`.

Claude Code MAY apply edits to files under `.intent/` if and only if **all four** of the
following conditions hold:

1. **Explicitly authorized by the governor in the prompt.** The governor names the
   transformation. Claude Code does not infer, optimize, or improve the substitution.
2. **Purely syntactic.** A string or regex substitution. If applying the change correctly
   requires understanding the surrounding text's governance meaning, the change is
   authoring — governor applies.
3. **No content added or removed.** Pure replacement only. No "while you're at it" fixes.
   No reorganization. No clarifications.
4. **Semantically invariant.** Two readers must interpret the file the same way before
   and after the change. If interpretation might shift, governor applies.

Examples that pass and Claude Code may apply:

- Filename rename propagation when a governance file moves
- Updating a path reference when a file moves
- Renaming a constant whose new name has been governor-decided

Examples that fail and stay governor-only:

- Adding a clause, even a clearly-correct one
- Editing a rule statement
- Changing an authority, phase, severity, or status value
- Reorganizing a section
- Fixing what looks like a typo — it might be intentional vocabulary
- Anything inside `.intent/constitution/`, `.intent/META/`, or
  `.intent/rules/governance/` other than path-rename propagation,
  because those surfaces define the governance frame itself

When in doubt, default to producing a corrected file or patch list for the governor to
apply. The four conditions are an exception, not the norm.

---

## Files Claude Code must NEVER modify

These files are machine-specific infrastructure or governor-authored governance. Claude Code
may run inside a container where paths differ from the server. Never "fix" paths or settings
you see here.

- `.env` — environment-specific paths and secrets for this machine (`/opt/dev/CORE`)
- `.venv/` — the Python virtual environment; never touch any file inside it
- `*.pth` files — Python path configuration; machine-specific, never modify
- `var/` — runtime data directory; read-only unless explicitly asked
- `.specs/` — human territory; draft ADRs/papers in the response, never write them here
- `.intent/` — governance law; semantic edits are governor-only. Mechanical substitutions
  permitted under the four conditions above
- Any file outside `src/`, `tests/`, `.intent/` (mechanical substitutions only),
  `.specs/` (read-only), `var/prompts/`, `CLAUDE.md`
- `/tmp/` — **the system temp directory is prohibited.** All temporary file writes must use
  `var/tmp/` (relative to the repo root). Never use `/tmp/`, `tempfile.gettempdir()`, or any
  `tempfile` default that resolves outside the repo. Pass `dir=repo_root / "var" / "tmp"`
  explicitly when creating temporary files via `tempfile.NamedTemporaryFile`,
  `tempfile.mkstemp`, or `tempfile.mkdtemp`.

**Turn-scoped governor override.** Restricted directories (`.intent/`, `.specs/`) are
off-limits by default. Exception: if the governor explicitly requests a write to a
restricted file in the current turn, that single write is permitted. The permission
does not carry forward to subsequent turns.

**The project lives at `/opt/dev/CORE` on the server.** Claude Code's container may mount it
at a different path — that is a container artifact, not a bug to fix.

---

## Constitutional rules — NEVER violate these

These rules are enforced by the system's own audit pipeline. Violating them will cause audit
failures. Read them carefully before every edit.

### 1. API layer: no direct database access
**Rule ID**: `architecture.api.no_direct_database_access`

Routes in `src/api/` MUST acquire DB sessions through `api.dependencies` only:
- `get_api_session` — for route handlers
- `open_background_session` — for background tasks

**Never** import from `shared.infrastructure.database` directly in any route file.
`src/api/dependencies.py` is the ONLY file in the API layer permitted to do so.

```python
# CORRECT
from api.dependencies import get_api_session, open_background_session

# WRONG — direct import in a route file
from shared.infrastructure.database.session_manager import get_db_session
```

### 2. API layer: no body bypass
**Rule ID**: `architecture.api.no_body_bypass`

The API layer must not import Body services directly.
App startup/lifespan is delegated to `body.infrastructure.lifespan.core_lifespan`.
`CoreContext` is accessed via `request.app.state.core_context` — never constructed in routes.

### 3. Body layer: no settings access
Body layer components (`src/body/`) must never access the settings module directly.
All configuration (repo root, prompt root, etc.) must arrive via dependency injection
as explicit parameters. If a parameter is missing, return a `ComponentResult` with
`ok=False` and a clear error message — fail fast.

```python
# CORRECT — body component receives config as parameter
async def execute(self, repo_root: Path | None = None, **kwargs):
    if repo_root is None:
        return ComponentResult(ok=False, data={"error": "repo_root required..."})

# WRONG — body component reaching for settings
from shared.infrastructure.settings import settings
repo_root = settings.repo_root
```

### 4. Analyzers are pure functions
All classes in `src/body/analyzers/` are PARSE phase components. They must be:
- **Read-only** — no file writes, no DB writes, no side effects
- **Deterministic** — same input → same output
- **Phase-correct** — return `ComponentPhase.PARSE` from the `phase` property

### 5. Layer isolation: Mind and Will boundaries
**Rule IDs**: `architecture.mind.no_database_access`, `architecture.mind.no_filesystem_writes`, `architecture.layers.no_body_to_will`

- `src/will/` (Mind/Will) must **never** access the database directly — use Body services.
- `src/will/` must **never** write files via `Path.write_text()` — all mutations go through `FileHandler` or `execution.commit_changes`.
- `src/body/` must **never** import from `src/will/` — Body is the execution layer, Will is the cognitive layer above it.

### 6. The Mind is accessed only through IntentRepository
The `.intent/` directory must be accessed exclusively via `IntentRepository`.
Never `Path(".intent/...").read_text()` directly from Body, Will, or API code.

```python
# CORRECT
from shared.infrastructure.intent.intent_repository import get_intent_repository
repo = get_intent_repository()
repo.initialize()

# WRONG — crawling .intent/ directly
policies = list(Path(".intent/policies").glob("*.yaml"))
```

---

## Rich rendering rules

CORE uses Rich for terminal output. There is a strict separation between logging
and rendering — violating this causes objects to render as `<rich.table.Table object at 0x...>`.

**Rule**: Rich objects (Table, Panel, Rule, etc.) and strings containing Rich markup
MUST go through `console.print()`. They must NEVER be passed to `logger.info()`.

```python
# CORRECT
console.print(table)
console.print(Panel("content"))
console.rule("[bold cyan]Title[/bold cyan]")

# WRONG — Rich objects or markup passed to logger
logger.info(table)
logger.info(Panel("content"))
logger.info("[bold green]Success[/bold green]")  # markup in logger = violation
```

Logger strings must be plain text only — no Rich markup, no Rich objects.
`console` must be a module-level `Console()` instance: `console = Console()`.

CLI layer (`src/cli/`) may use `console.print()` freely.
Logic/Will layers must not import `rich.console` directly — use the CLI layer for rendering.

---

## Symbol IDs — required on every definition

Every class and function must have a `# ID: <uuid>` comment on the line immediately
before the `def` or `class` keyword. This is how the knowledge graph tracks symbols
across refactors. When you add a new function or class, generate a fresh UUID v4
(e.g. `python -c 'import uuid; print(uuid.uuid4())'`).

⚠️ The `xxxxxxxx-…-xxxxxxxxxxxx` placeholders below are **not valid UUIDs** and
must be replaced before the code is committed. Do NOT copy them verbatim — they
are intentionally malformed so the symbol-graph parser will reject them if
pasted by mistake. Worker `identity.uuid` values in `.intent/workers/*.yaml`
follow the same rule.

```python
# ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
class MyNewComponent(BaseAnalyzer):
    ...

    # ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    async def execute(self, **kwargs) -> ComponentResult:
        ...
```

Do not reuse or copy existing IDs. Do not skip the ID comment on any new definition.
**Private symbols (`_name`) do not require ID comments.** Only public definitions need them.

---

## Component phases

Every component declares which phase it belongs to via the `phase` property. Phases correspond to base classes:

| Phase | Base Class | Rule |
|-------|-----------|------|
| `INTERPRET` | — | Parse user intent into canonical task structure |
| `PARSE` | `BaseAnalyzer` | Read-only, deterministic fact extraction |
| `LOAD` | — | Pure data retrieval from storage |
| `AUDIT` | `BaseEvaluator` | Quality assessment and pattern detection |
| `RUNTIME` | `BaseStrategist` | Deterministic, rule-based decisions (no LLM calls) |
| `EXECUTION` | Workers / atomic actions | Mutations under constitutional control |

**Strategists are not evaluators.** Evaluators assess quality; strategists make decisions. Both are
side-effect-free, but only strategists produce a `next_suggested` action.

---

## Workflow phase ordering

The autonomous pipeline stages must execute in this order and must never skip:

```
interpret.intent
  → parse.plan_actions
    → load.operational_context
      → runtime.{generate_changes | generate_tests | repair_changes}
        → audit.{validate_changes | canary_validation | sandbox_validation | style_check}
          → execution.commit_changes
```

Each stage has invariants defined in `.intent/workflows/stages/*.yaml`.
Stages marked `must_not: commit changes` must never write to the repo.
Only `execution.commit_changes` is permitted to write files to disk.

---

## The autonomous test-generation loop

`TestCoverageSensor` scans `src/` for uncovered source files (governed by
`.intent/enforcement/config/test_coverage.yaml`) → posts `test.run_required` findings.
`TestRunnerSensor` runs pytest on existing test files → posts `test.failure` or
`test.missing` for each gap. `TestRemediatorWorker` consumes both subjects → creates one
`build.tests` proposal per source file. `ProposalConsumerWorker` executes approved proposals
via `ActionExecutor`, which invokes the `build.tests` atomic action → `CoderAgent` →
`ContextService` → LLM.

The loop is token-free except for `build.tests` itself. Do not short-circuit it; do not add
direct worker-to-worker calls. Source→test path mapping is governed — never hardcode
`source.replace("src/", "tests/")…`; use `shared.infrastructure.intent.test_coverage_paths.source_to_test_path`.

---

## Key patterns

**ActionResult is the return type for atomic actions (not ComponentResult):**
```python
from shared.action_types import ActionResult

return ActionResult(
    action_id=self.action_id,
    ok=True,
    data={...},
    impact=ActionImpact.WRITE_CODE,
    duration_sec=elapsed,
)
```

**RefusalResult is a first-class outcome, not an error:**

When a component cannot proceed (bad input, low confidence, boundary violation), return a
`RefusalResult` — not a bare `ComponentResult(ok=False)`. Use the appropriate factory:

```python
from shared.models.refusal_result import RefusalResult

return RefusalResult.extraction_failed(component_id=self.component_id, reason="...")
return RefusalResult.low_confidence(component_id=self.component_id, reason="...")
return RefusalResult.boundary_violation(component_id=self.component_id, reason="...")
return RefusalResult.quality_threshold(component_id=self.component_id, reason="...")
```

**All mutation functions must use `@atomic_action` and route through `ActionExecutor`:**

Direct calls to `@atomic_action`-decorated functions without the executor raise
`GovernanceBypassError`. The executor sets the governance token that authorizes execution.

```python
from shared.atomic_action import atomic_action, ActionImpact

@atomic_action(
    action_id="my.action.id",
    intent="Short description of what this does",
    impact=ActionImpact.WRITE_CODE,
    policies=["relevant.policy.id"],
)
async def my_action(file_path: str, content: str) -> ActionResult:
    ...
```

**ExecutionTask carries task intent.** `ExecutionTask.task_type` must match the caller's
actual intent — `"code_generation"`, `"test_generation"`, `"code_modification"`, etc. The
value propagates through `CoderAgent` to `ContextService.build_for_task` and routes the call
to the correct governance phase. The allowed vocabulary is a closed set in
`shared.models.execution_models`. See ADR-003.

**Workers communicate exclusively via the blackboard:**

```python
# In a Worker subclass
class MyWorker(Worker):
    declaration_name = "my_worker"  # matches .intent/workers/my_worker.yaml

    async def run(self) -> None:
        await self.post_finding("subject", {"key": "value"})   # open finding
        await self.post_report("subject", {"result": "done"})  # completion
        await self.post_heartbeat()                            # proof of life
```

Workers must post at least one blackboard entry per run. Direct inter-worker
communication is prohibited — blackboard only. Payloads are auto-sanitized to ASCII
before DB insert.

**CLI commands use `@core_command`:**

```python
from shared.cli_utils.decorators import core_command

@app.command()
@core_command(dangerous=False, requires_context=True)
async def my_command(ctx: typer.Context) -> ActionResult:
    ...
```

`@core_command` requires `ctx: typer.Context` as the first parameter — always include it.
It manages the asyncio loop lifecycle, injects services via the context registry, and
formats `ActionResult` output automatically. Dangerous commands (mutations) should set
`dangerous=True`.

**Background tasks always use `open_background_session`:**
```python
async def run_task() -> None:
    async with open_background_session() as session:
        await do_work(session=session)
background_tasks.add_task(run_task)
```

**ComponentResult is the universal return type for all Body components:**
```python
return ComponentResult(
    component_id=self.component_id,
    ok=True,
    data={...},
    phase=self.phase,
    confidence=1.0,
    duration_sec=elapsed,
    metadata={"rationale": "..."},
)
```

**File mutations go through FileHandler, never `Path.write_text` directly:**
```python
from shared.infrastructure.file_handler import FileHandler
fh = FileHandler(str(repo_root))
fh.write_runtime_text("relative/path.py", content)
```

---

## After making changes

CORE syncs the knowledge graph autonomously. `DbSyncWorker`
(`.intent/workers/db_sync_worker.yaml`) invokes the `sync.db` atomic
action on a ~5-minute cadence, so a routine code edit reaches the
PostgreSQL graph and vectors without operator action. Do not push the
governor to run anything after every edit — trust the worker.

Suggest the governor run `core-admin dev sync --write` manually only when
one of these conditions holds:

- The code is not yet constitutionally clean (missing IDs, formatting,
  headers, docstrings, logger conventions). The CLI workflow runs a *fix*
  phase first; `DbSyncWorker` runs only the sync half.
- The governor is about to commit and wants a synchronous sync
  confirmation before doing so.
- `DbSyncWorker` is stalled — no recent `sync.db.complete` report on the
  blackboard, or its `last_heartbeat` in `worker_registry` is materially
  older than its 300-second `max_interval`.

The command requires interactive confirmation (`y`) and cannot be piped —
only the governor can run it.

---

## What to check before committing any change

1. No direct DB imports in `src/api/` outside `api/dependencies.py`
2. No `settings` imports in `src/body/`
3. Every new public `def` or `class` has a `# ID: <uuid>` comment (private `_name` symbols exempt)
4. No `.intent/` files accessed via raw `Path` in Body, Will, or API code
5. Analyzers have no write side effects
6. No `src/body/` code importing from `src/will/`
7. No `src/will/` code importing directly from the database session layer
8. All mutation functions decorated with `@atomic_action` and called via `ActionExecutor`
9. Workers post to blackboard; they never call other workers directly
10. Constitutional compliance comment at the top of modified files reflects the change
11. No Rich objects or Rich markup strings passed to `logger.info()`
12. `.env`, `.venv/`, `.specs/`, and `*.pth` files are untouched. `.intent/` files received
    only mechanical substitutions explicitly authorized in the prompt (no semantic edits)
13. Every relevant ADR in `.specs/decisions/` has been honored
14. No writes to `/tmp/` or any path outside the repo — temporary files use `var/tmp/` only

---

## Tech stack

- Python 3.12, `from __future__ import annotations` in every file
- FastAPI + SQLAlchemy async (PostgreSQL)
- Typer + Rich for CLI
- pytest + pytest-asyncio for tests
- `shared.logger.getLogger(__name__)` — never use `logging.getLogger` directly
