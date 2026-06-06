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
  body/       — Analyzers, atomic actions, services, infrastructure workers. Execution layer.
  cli/        — Typer CLI commands. Rich rendering is allowed here only
                (architecture.channels.cli_rendering_allowed).
  mind/       — Constitutional logic engines (ast_gate, glob_gate, llm_gate, runtime_gate, …).
                Reads .intent/ at runtime and evaluates rules. Mind layer in code: declares no
                I/O, no execution, no Body or Will invocation. Permitted by
                architecture.layer_exclusivity; constrained by architecture.mind.* and
                architecture.layers.no_mind_execution.
  shared/     — Cross-cutting substrate: DB session, models, AST utilities, knowledge graph,
                intent infrastructure. Forbidden from importing src/mind/, src/body/, or
                src/will/ (architecture.shared.no_layer_imports).
  will/       — Autonomous developer, cognitive orchestration, agents.
.intent/      — Governance law as data: YAML/JSON policies, rules, mappings, META schemas.
                Read at runtime by IntentRepository; never imported as Python.
.specs/       — Architectural reasoning: charter, papers, ADRs, requirements.
```

The Mind/Body/Will distinction is between *code* layers (`src/mind/`, `src/body/`, `src/will/`)
and *data* surfaces (`.intent/` is the governance law that `src/mind/` reads; `.specs/` is the
reasoning behind it). They are not the same thing — do not conflate "the Mind" (`.intent/`)
with "the Mind layer in code" (`src/mind/`).

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

`.specs/` is human territory. **By default, do not modify anything under `.specs/`**; when
asked to draft an ADR or paper, return the complete file content in the response for the
governor to apply. **Exception — confirmed write:** if the governor explicitly confirms a
write to a `.specs/` file in the current turn, Claude Code may write that file directly. The
confirmation is per-turn and does not carry forward. Absent that confirmation, draft in the
response and never write under `.specs/` yourself.

---

## How to work in this repo

**Reconnaissance before editing.** When asked to change code in a file or module you have
not seen in this session, first: read the file; report what you found (current shape,
relevant structures, any existing patterns); identify every call site that would be affected.
Only then edit. For non-trivial changes (multi-file edits, schema changes, new fields on
shared models, anything touching more than three files) pause after reconnaissance and wait
for the governor to review before making edits.

**Tests are part of the change.** When you change a public function/class signature or
behavior in `src/`, update the corresponding test in the same change. When you add a new
public function/class, write at least basic tests for it. You cannot run `pytest` yourself
— the governor verifies — but you must author the tests. Do not rely on the autonomous
test-generation loop to compensate for skipped tests: the loop has a known import-validation
gap (#574) and a known semantic-miscapture rate of roughly 30% (see #572), and signature
drift accumulates silently across sessions when source ships without test updates (#572 Cat
B, ~80–100 tests, is the canonical evidence). The minimum-scope principle does **not**
exempt test updates — tests are part of the change, not scope expansion.

**Complete files, not diffs.** When modifying a file, output the complete file content in a
fenced block labelled with its path. The governor reviews whole files, not diff fragments.

**Verification after editing.** Before reporting completion: run `ruff check` on every file
touched. Run small import/instantiation smoke tests where possible. Do NOT run `pytest`, do
NOT commit — those are governor actions. Restarting `core-daemon` + `core-api` is in-scope
when a fix needs operationalization (the running daemon caches imported modules, so a code
fix only lands after restart). Avoid restarting mid-flight against an active CCC scan or
long-running remediation; otherwise it's a normal step in the development loop.

**When in doubt, ask.** A five-second clarifying question is cheaper than a fifteen-minute
implementation against the wrong assumption. Do not invent requirements; do not infer CLI
commands from plausibility. If a brief says "atomic action" and no CLI surface exists to
invoke one, ask rather than writing a throwaway script.

---

## Writing to `.intent/` and `.specs/` — the confirmation gate

**This file is a development contract, not a runtime governance posture.** CORE is
bootstrapped on itself — we develop CORE using CORE. The restrictions here govern how Claude
Code works on *this repo during development*; they are intentionally permissive under governor
confirmation so the bootstrap can never lock itself out of evolving its own governance frame.
The *strong* version of these restrictions — what CORE enforces on governed projects at
runtime — lives in `.intent/` rules read by the runtime, not here. Do not import that live
strictness into this dev contract, and do not export this dev permissiveness into runtime
rules. (This conflation is the framework/project namespace fusion the namespace-split work
exists to resolve.)

`.intent/` files contain governance law; `.specs/` files contain architectural reasoning.
Both are human-authored by default. Claude Code's default posture toward both is
**draft-in-response**: produce the complete corrected file in the response and let the
governor apply it.

Claude Code MAY write directly to `.intent/` or `.specs/` only under one of these paths:

**Path A — confirmed write (semantic edits permitted).** The governor explicitly confirms a
write to a named file in the current turn. That single write is permitted, including
semantic changes. The confirmation is **turn-scoped**: it authorizes the writes named in
that turn and does not carry forward to later turns.

**Path B — authorized mechanical substitution (no fresh confirmation needed per write).**
A purely syntactic change the governor named in the prompt, where **all four** conditions hold:

1. **Explicitly authorized by the governor in the prompt.** The governor names the
   transformation. Claude Code does not infer, optimize, or improve the substitution.
2. **Purely syntactic.** A string or regex substitution. If applying the change correctly
   requires understanding the surrounding text's governance meaning, it is a semantic edit —
   use Path A.
3. **No content added or removed.** Pure replacement only. No "while you're at it" fixes.
   No reorganization. No clarifications.
4. **Semantically invariant.** Two readers must interpret the file the same way before
   and after the change.

Examples that pass Path B and Claude Code may apply:

- Filename rename propagation when a governance file moves
- Updating a path reference when a file moves
- Renaming a constant whose new name has been governor-decided

**The constitutional core requires heightened confirmation.** Files under
`.intent/constitution/`, `.intent/META/`, and `.intent/rules/governance/` define the
governance frame itself. A confirmed write (Path A) reaches them too — the bootstrap must be
able to evolve its own frame — but with one added condition: the governor must name the
**specific** constitutional file in the confirmation, not a blanket "go ahead," and Claude
Code surfaces the change for review before writing. Per-file authorization plus visibility is
the residual safety here; it is not a lockout.

When neither path applies, default to producing a corrected file or patch list for the
governor to apply. Direct writes are the exception, not the norm.

---

## Files Claude Code must NEVER modify

These files are machine-specific infrastructure. Claude Code may run inside a container where
paths differ from the server. Never "fix" paths or settings you see here.

- `.env` — environment-specific paths and secrets for this machine (`/opt/dev/CORE`)
- `.venv/` — the Python virtual environment; never touch any file inside it
- `*.pth` files — Python path configuration; machine-specific, never modify
- `var/` — runtime data directory; read-only unless explicitly asked
- Any file outside `src/`, `tests/`, `.intent/`, `.specs/`, `var/prompts/`, `CLAUDE.md`

`.intent/` and `.specs/` are governed surfaces, not hard-prohibited ones: writes are
permitted under the confirmation gate above, with the constitutional core carved out.

**Turn-scoped governor override.** `.intent/` and `.specs/` are draft-in-response by default.
If the governor explicitly confirms a write to one of these files in the current turn, that
write — including semantic edits — is permitted for that turn only. The permission does not
carry forward to subsequent turns. It reaches the constitutional core only under heightened
confirmation — the governor names the specific constitutional file in the same turn.

**The project lives at `/opt/dev/CORE` on the server.** Claude Code's container may mount it
at a different path — that is a container artifact, not a bug to fix.

- `/tmp/` — **the system temp directory is prohibited.** All temporary file writes must use
  `var/tmp/` (relative to the repo root). Never use `/tmp/`, `tempfile.gettempdir()`, or any
  `tempfile` default that resolves outside the repo. Pass `dir=repo_root / "var" / "tmp"`
  explicitly when creating temporary files via `tempfile.NamedTemporaryFile`,
  `tempfile.mkstemp`, or `tempfile.mkdtemp`.

---

## Constitutional rules

This section is a derived operational digest of constitutional rules. `.intent/` is canonical.
On any divergence between this section and `.intent/`, `.intent/` wins; surface the
divergence to the governor rather than resolving it in code.

Severity below is read from each rule's on-disk `enforcement` field, not inferred from the
file the rule lives in. **Blocking** rules stop a commit through the audit pipeline.
**Reporting / advisory** rules surface findings to the governor without blocking. On-disk
enforcement enum is `blocking` / `reporting` / `advisory` (three tiers, per
`.intent/META/rule_document.schema.json`); the digest groups the latter two into one
operational bucket since both surface findings without blocking.

At the time of this digest: 31 blocking + 27 reporting + 9 advisory = 67 rules. Verify by
re-reading `.intent/rules/architecture/*.json` and
`.intent/enforcement/mappings/architecture/*.yaml`.

**Integrity check (run before trusting this digest).** The digest's rule-id set must equal
the `.intent/rules/architecture/*.json` set. Re-derive with
`jq -r '.rules[].id' .intent/rules/architecture/*.json | sort -u` and compare against the
backticked ids below. A mismatch means the digest has drifted — surface it to the governor,
don't edit around it.

### Blocking rules — stop a commit

Format: `rule_id` — scope (`applies_to`) — one-line statement (MUST/SHOULD wording from the
rule preserved).

**Atomic actions (`src/body/atomic/`)**

- `atomic_actions.must_have_decorator` — `src/body/atomic/**/*.py` — Functions registered with `@register_action` MUST also have `@atomic_action` with required metadata (action_id, intent, impact, policies).
- `atomic_actions.must_return_action_result` — `src/body/atomic/**/*.py` — `@atomic_action` functions MUST declare `ActionResult` as their return type annotation and actually return `ActionResult` instances.
- `atomic_actions.result_must_be_structured` — `src/body/atomic/**/*.py` — `ActionResult.data` MUST be a dictionary with string keys; nested structures permitted, top level must be a dict.
- `atomic_actions.no_governance_bypass` — `src/body/atomic/**/*.py` — No atomic action MAY return types other than `ActionResult` to bypass governance validation; tuple returns are explicitly forbidden.
- `atomic_actions.must_accept_kwargs` — `src/body/atomic/**/*.py` — `@atomic_action` functions MUST include `**kwargs` in their signature; the check fires at decoration (import) time.
- `atomic_actions.impact_level_must_be_governed` — `src/body/atomic/**/*.py` — Action impact classification MUST be declared in `.intent/enforcement/config/action_risk.yaml` keyed by `action_id`, not embedded in registration calls in `src/`.
- `atomic_actions.fix_action_scope` — `src/body/atomic/**/*.py` — `fix.imports` is exclusively scoped to import ordering/sorting; the separate `check.imports` action is the designated authority for import-resolution verification.
- `architecture.flows.atomic_action_must_not_compose` — `src/body/atomic/**/*.py` — An `@atomic_action` MUST NOT internally invoke other registered AtomicActions via `ActionExecutor.execute()`; composition is the sole responsibility of a Flow.

**Flows (`src/body/flows/`)**

- `architecture.flows.flow_declared_in_intent` — `src/**/*.py` — Every Flow MUST be declared in `.intent/flows/*.yaml` and registered in `FlowRegistry`; Python-data-structure Flows are forbidden.
- `architecture.flows.flow_must_not_post_to_blackboard` — `src/body/flows/**/*.py` — Flows MUST NOT call `post_finding()`, `post_report()`, `post_heartbeat()`, or INSERT/UPDATE `core.blackboard_entries`.
- `architecture.flows.flow_must_not_create_proposals` — `src/body/flows/**/*.py` — Flows MUST NOT create, submit, or approve `Proposal` objects.
- `architecture.flows.flow_must_propagate_write_false` — `src/body/flows/executor.py` — FlowExecutor MUST propagate `write=False` to every step; the flag is caller-supplied and immutable for the duration of a Flow execution.

**Blackboard**

- `architecture.blackboard.worker_only_inserts` — `src/**/*.py` — INSERT against `core.blackboard_entries` MUST originate from the Worker base class; services and atomic actions route through `self.post_finding()` / `post_report()` / `post_heartbeat()`.
- `architecture.blackboard.reaudit_requires_reaudit_mechanism` — `src/**/*.py` — Every UPDATE transitioning a row to `status='awaiting_reaudit'` MUST co-occur with `resolution_mechanism = 'reaudit'` in the same WHERE clause.

**Privileged-boundary imports**

- `architecture.boundary.database_session_access` — `src/mind/**/*.py | src/will/**/*.py` — Only infrastructure, Body, and shared services MAY import `get_session` / `AsyncSession` directly; Mind and Will MUST use dependency injection.
- `architecture.boundary.settings_access` — `src/body/**/*.py | src/mind/**/*.py | src/will/**/*.py` — Only infrastructure and bootstrap modules MAY import `Settings` directly; all other components MUST receive configuration through DI or environment abstraction.
- `architecture.boundary.file_handler_access` — `src/mind/**/*.py | src/will/**/*.py` — Only Body and infrastructure MAY instantiate `FileHandler` directly; Will and Mind MUST delegate file operations to Body services.
- `architecture.boundary.llm_client_access` — `src/body/**/*.py | src/mind/**/*.py` — Only Will and autonomous services MAY import LLM client infrastructure; Body MUST NOT make AI decisions, Mind MUST NOT invoke AI.
- `architecture.shared.no_layer_imports` — `src/shared/**/*.py` — Shared infrastructure components MUST NOT import from `src/mind/`, `src/body/`, or `src/will/`. (Per ADR-049 D1/D3 the YAML carries 8 `excludes:` pending closure ADRs; no new excludes without a companion closure ADR.)

**Channels — blocking**

- `architecture.channels.logic_logger_only` — `src/**/*.py` — Non-UI runtime and logic modules MUST use the CORE standard logger for operational output.
- `architecture.channels.api_structured_output_only` — `src/api/**/*.py` — API modules MUST communicate through structured response mechanisms and MUST NOT use terminal-oriented rendering.

**Async / module-time / paths**

- `async.no_manual_loop_run` — `src/**/*.py` — Logic modules MUST NOT call `asyncio.run()` or manually create new event loops.
- `logic.di.no_global_session` — `src/features/**/*.py | src/body/services/**/*.py` — Modules MUST NOT import `get_session` globally; database access MUST be injected.
- `architecture.no_module_async_engine` — `src/**/*.py` — Async execution engines MUST NOT be instantiated at module import time.
- `architecture.path_access.no_hardcoded_runtime_dirs` — `src/**/*.py` — Runtime output directory names (logs, reports) MUST NOT appear as string literals in path construction in `src/`; route through `PathResolver` or `FileHandler`.

**Patterns / mutation surface**

- `architecture.patterns.action_pattern` — `src/body/atomic/**/*.py | src/cli/commands/**/*.py` — Action commands MUST use `@atomic_action` and have a `write` parameter defaulting to `False`.
- `governance.mutation_surface.filehandler_required` — `src/**/*.py | features/**/*.py` — All filesystem writes MUST route through `FileHandler`; direct `write_text()`, `write_bytes()`, or `open(...)` in write/append mode are prohibited in production code.

**Constitution / governance read-only**

- `architecture.constitution_read_only` — `src/**/*.py` — The constitutional intent directory MUST be immutable.
- `architecture.meta_read_only` — `src/**/*.py` — Intent schema and META artifacts MUST NOT be mutated at runtime.
- `governance.constitution.read_only` — `src/**/*.py` — `.intent/**` MUST be treated as immutable by all system components.
- `governance.logic_mutation.governed` — `src/**/*.py` — Permanent modifications to production logic within `src/` MUST occur only through governed mutation surfaces.

### Reporting / advisory rules — surface findings, do not block

Same format. Marked `[reporting]` or `[advisory]` per the on-disk `enforcement` field.

**Layer scope — Mind (`src/mind/`)**

- `architecture.mind.no_database_access` — `src/mind/**/*.py` — Mind layer components MUST NOT import database session infrastructure (`get_session`). [reporting]
- `architecture.mind.no_filesystem_writes` — `src/mind/**/*.py` — Mind layer components MUST NOT write to filesystem. [reporting]
- `architecture.mind.no_body_invocation` — `src/mind/**/*.py` — Mind layer components MUST NOT import or invoke Body layer. [reporting]
- `architecture.mind.no_will_invocation` — `src/mind/**/*.py` — Mind layer components MUST NOT import or invoke Will layer. [reporting]
- `architecture.layers.no_mind_execution` — `src/mind/**/*.py` — Mind layer components MUST NOT perform I/O operations or invoke actions. [reporting]
- `architecture.mind.no_execution_semantics` — `src/mind/**/*.py` — Mind components MUST NOT contain execution logic (risk classification, decision-making, caching strategies, validation enforcement). [reporting]
- `architecture.mind.execution_signal` — `src/mind/**/*.py` — Pre-selector flagging files with structural markers of execution semantics for review (produces no verdict). [reporting]

**Layer scope — Body (`src/body/`)**

- `architecture.body.no_rule_evaluation` — `src/body/**/*.py` — Body layer components MUST NOT evaluate constitutional rules directly. [reporting]
- `architecture.layers.no_body_to_will` — `src/body/**/*.py` — Body layer components MUST NOT import or invoke Will layer. [reporting; narrow 4-sub-path scope per ADR-049 D1 pending tightening to bare prefix]

**Layer scope — Will (`src/will/`)**

- `architecture.will.no_direct_database_access` — `src/will/**/*.py` — Will layer components MUST NOT import `get_session` directly. [reporting]
- `architecture.will.no_filesystem_operations` — `src/will/**/*.py` — Will layer components SHOULD delegate filesystem operations to Body. [reporting — SHOULD, not MUST]
- `architecture.will.must_delegate_to_body` — `src/will/agents/**/*.py | src/will/orchestration/**/*.py` — Will orchestration components SHOULD import and delegate to Body services. [reporting]

**Layer scope — API (`src/api/`)**

- `architecture.api.no_direct_database_access` — `src/api/**/*.py | src/api/*.py` — API layer components MUST NOT import `get_session` directly. Sanctioned repositories and services accessed via `api/dependencies.py` and named providers ARE permitted; the broader "MUST NOT access infrastructure directly" framing is superseded by ADR-049 D1 (§6). [reporting]
- `architecture.api.must_route_through_will` — `src/api/**/*_routes.py` — API route handlers SHOULD delegate all logic to Will layer. [reporting; API → Will use-case layer recorded as architectural debt per ADR-049 D1]
- `architecture.api.no_body_bypass` — `src/api/**/*.py | src/api/*.py` — API layer components SHOULD NOT directly import Body services. [reporting]

**Layer scope — Shared (`src/shared/`)**

- `architecture.shared.no_strategic_decisions` — `src/shared/**/*.py` — Shared infrastructure components MUST NOT make strategic decisions or orchestrate workflows. [reporting]
- `architecture.layer_exclusivity` — `src/**/*.py` — All `src/` Python files MUST reside within a constitutional layer (`mind/`, `body/`, `will/`), a sanctioned infrastructure directory (`shared/`, `api/`), or be a root entry point. [reporting]

**Channels — non-blocking**

- `architecture.channels.logic_no_terminal_rendering` — `src/**/*.py` — Non-UI runtime and logic modules MUST NOT perform terminal-oriented rendering. [reporting]
- `architecture.channels.cli_rendering_allowed` — `src/cli/**/*.py` — CLI surface modules MAY use terminal-oriented rendering for user-facing output. [reporting — positive permission]
- `architecture.channels.logger_not_presentation` — `src/**/*.py` — The CORE logger MUST be used for operational logging and MUST NOT be used as a presentation renderer. [reporting]

**Logging / governance — non-blocking**

- `logic.logging.standard_only` — `src/**/*.py` — Operational logs MUST use standard `getLogger` and avoid f-strings for lazy evaluation. [reporting]
- `governance.artifact_mutation.traceable` — `src/**/*.py` — System artifacts, logs, and reports SHOULD be generated via `FileHandler` to ensure audit traceability. [reporting]
- `governance.dangerous_execution_primitives` — `src/**/*.py` — Dangerous primitives (`eval`, `exec`, `compile`, `subprocess`) require documented justification; Will MUST NOT use them; Body MAY use them in designated sanctuary modules with clear operational need. [reporting]

**Intent access — non-blocking**

- `architecture.intent.no_legacy_root_assumptions` — `src/**/*.py` — Governance consumers MUST NOT hardcode legacy `.intent` root assumptions (`policies/`, `standards/`, `charter/policies/`). [reporting]
- `architecture.namespace.no_direct_protected_access` — `src/**/*.py` — Non-gateway Python components MUST NOT discover, scan, or load `.intent` governance artifacts through direct filesystem crawling or local parsing logic; access MUST route through shared intent infrastructure. [reporting]
- `architecture.intent.gateway_is_shared_infrastructure` — `src/**/*.py` — Components outside `src/shared/infrastructure/intent/` SHOULD consume `.intent` through that layer rather than implementing local resolvers. [reporting]

**Modernization — non-blocking**

- `modernization.legacy_signal` — `src/**/*.py` — Pre-selector flagging files with structural markers of legacy / shim / deprecation for evolutionary-purity review (no verdict). [reporting]
- `modernization.legacy_scars` — `src/**/*.py` — Source code SHOULD be free of obsolete structural shims, unused parameters from prior iterations, and internal logic wrappers that bypass the Universal Workflow Pattern. [advisory]

**Workers / discovery / quality — advisory**

- `architecture.flows.worker_must_not_hardwire_sequence` — `src/**/workers/**/*.py | src/shared/workers/**/*.py` — A Worker's `run()` method MUST NOT contain an explicit ordered sequence of `ActionExecutor.execute()` calls that could be extracted into a named Flow. [advisory]
- `architecture.artifact_discovery_through_registry` — declared-only (no enforcement mapping) — Discovery components (sensors, validators, crawlers) MUST consult the artifact_type registry via `IntentRepository.list_artifact_types()` / `get_artifact_type(id)`; hardcoded extension-based discovery globs are forbidden. [advisory]
- `governance.intent_meta.required` — `.intent/META/GLOBAL-DOCUMENT-META-SCHEMA.json` — A single META directory MUST exist at `.intent/META` to serve as the authoritative contract for intent artifacts. [advisory]
- `governance.no_governance_bypass` — `src/**/*.py` — No action or workflow MAY bypass governance validation; if a precondition cannot be evaluated, the operation MUST be blocked. [advisory]
- `modularity.unix_philosophy` — `src/**/*.py` — Components SHOULD follow UNIX philosophy: do one thing well, compose via clear interfaces, minimize coupling. [advisory]
- `quality.type_safety` — `src/**/*.py` — Production code SHOULD be type-safe as verified by MyPy static analysis. [advisory]
- `quality.security_audit` — `pyproject.toml` — The project dependency tree SHOULD be free of known vulnerabilities as verified by pip-audit. [advisory]
- `quality.test_integrity` — `tests/**/*.py` — The project test suite SHOULD be functional and passing without collection errors. [advisory]

### Operational corollaries

A few operational corollaries follow from the rule set; they are not separate constitutional
claims, just the practical shape of conforming code:

- API routes acquire DB sessions through `api.dependencies` (`get_api_session` for handlers,
  `open_background_session` for background tasks). `src/api/dependencies.py` is the single
  sanctioned site for the `shared.infrastructure.database` import; direct imports elsewhere
  in `src/api/` trip `architecture.api.no_direct_database_access`.
- Body components receive configuration via DI (`repo_root`, `prompt_root`, …); on missing
  parameters return `ComponentResult(ok=False, …)` rather than reaching for `settings`. This
  is the practical shape of `architecture.boundary.settings_access`.
- `.intent/` is accessed through `IntentRepository` (`get_intent_repository().initialize()`),
  never through raw `Path(".intent/…").read_text()` or `glob()`. This is the practical shape
  of `architecture.namespace.no_direct_protected_access` /
  `architecture.intent.gateway_is_shared_infrastructure`.
- Analyzers in `src/body/analyzers/` are PARSE-phase components: read-only, deterministic,
  side-effect-free, returning `ComponentPhase.PARSE`. This sits under
  `architecture.body.no_rule_evaluation` and the general phase discipline (see "Component
  phases" below).

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
12. `.env`, `.venv/`, and `*.pth` files are untouched. Any write to `.specs/` or `.intent/`
    came from either an authorized mechanical substitution or a write the governor explicitly
    confirmed this turn; any write to the constitutional core (`.intent/constitution/`,
    `.intent/META/`, `.intent/rules/governance/`) was confirmed by the governor naming that
    specific file this turn
13. Every relevant ADR in `.specs/decisions/` has been honored
14. No writes to `/tmp/` or any path outside the repo — temporary files use `var/tmp/` only
15. Any signature/behavior change in `src/` has a corresponding test update in the same
    commit. Any new public symbol has at least a basic test. See "Tests are part of the
    change" above for why this isn't covered by the autonomous test-gen loop

---

## Tech stack

- Python 3.12, `from __future__ import annotations` in every file
- FastAPI + SQLAlchemy async (PostgreSQL)
- Typer + Rich for CLI
- pytest + pytest-asyncio for tests
- `shared.logger.getLogger(__name__)` — never use `logging.getLogger` directly
