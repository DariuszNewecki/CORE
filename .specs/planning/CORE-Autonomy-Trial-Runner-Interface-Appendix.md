---
kind: planning
title: CORE Autonomy Trial Runner Interface Appendix
status: draft
---

# CORE Autonomy Trial Runner Interface Appendix

**Status:** Draft — for Governor review. Read-only, object-level inspection of both frozen runner
pins via `git show`/`git grep`/`git ls-tree` against the commit objects directly. **Neither runner
was checked out or executed to produce this document.** No production code, `.intent/`, or test
file was modified to produce it.

**Pins inspected:**

| | Trial 0 runner | Trial 1 runner |
|---|---|---|
| Commit | `27160a0a8768cf72bbe2a8fecc3d9169db758efc` | `b57423dc85c11c6650a9515c136bab49b02107ec` |

Every file cited below as evidence was diffed between the two pins; where the diff is empty this
is stated explicitly, and the finding applies identically to both runners.

---

## Headline finding (item 14) — read this before the item-by-item detail below

**Neither pin exposes a genuine interface that accepts a free-text goal or task statement and
autonomously investigates a subject repository end-to-end, producing planned findings on the
blackboard, in the shape the blind-authored procedures (Document A / Document B) assume.**

This is not an inference from absence — it is stated directly, in-repo, by the code's own
docstrings and control flow, at both pins (all files cited are byte-identical between
`27160a0a` and `b57423dc`):

1. **`ConversationalAgent`** (`src/will/agents/conversational/agent.py`) is the one component
   whose own docstring frames it as "End-user interface to CORE's capabilities... a natural
   language interface." Its docstring states its own current state explicitly:
   > "Phase 1 (Current): Read-only information retrieval — Extract minimal context using
   > ContextBuilder — Send to LLM for analysis — Return natural language response — **NO
   > proposals, NO execution**"

   "Phase 2 (Future): Proposal generation" and "Phase 3 (Future): Full autonomous execution" are
   both explicitly marked as **future, not-yet-implemented** work in the same docstring, at both
   pins.

2. **`core-admin governance validate-request "<free text>"`** (`src/cli/commands/governance.py`)
   is the one CLI command that accepts a free-text request string. Its own module docstring calls
   it: "Demonstrate full pre-flight constitutional validation (5 gates)." Reading the full
   function: it parses the text into a `TaskStructure` (Gate 1), vector-searches matching policies
   (Gate 2), checks for contradictions (Gate 3, hardcoded to "No contradictions detected" — not a
   real check at this pin), extracts assumptions (Gate 4), and prints a summary "authority
   package" table (Gate 5). **The command ends there.** It never constructs a `Proposal`, never
   calls `ActionExecutor`, never invokes a `Worker`, and never writes to the blackboard. It is a
   governance-pipeline demonstration, not an execution path.

3. **`NaturalLanguageInterpreter`** (`src/will/interpreters/natural_language_interpreter.py`),
   the component both of the above rely on to turn text into structure, is a **priority-ordered
   regex classifier**, not a planner: its own docstring examples are single-target commands
   ("refactor UserService for clarity" → one file target; "generate tests for models/user.py" →
   one file target). It extracts one `TaskType` (`TEST`/`REFACTOR`/`FIX`/`GENERATE`/`ANALYZE`/...)
   and a small set of file/symbol targets via regex and CamelCase matching. There is no
   multi-step planning, no open-ended corpus comprehension, and no mechanism for "investigate this
   unfamiliar repository and decide for yourself what to examine" — the entire interpreter is
   built around narrowing a request to one recognizable target, the opposite of what an unfamiliar-
   corpus investigation requires.

4. **The one real, production, end-to-end path that has ever moved a Proposal from creation
   through `ActionExecutor` at these pins is Unit D's** (`c0694953` and later — see below), which
   requires **hand-constructing a `Proposal` Python object with one specific, pre-determined
   action** (`fix.format` on one named file, `package/example.py`) directly in code, then calling
   `ProposalStateManager.approve()` and `ProposalConsumerWorker.start()` directly — not through any
   free-text or CLI surface at all. **Neither Trial 0's pin (`27160a0a`) nor Trial 1's pin
   (`b57423dc`) even contains this — Unit D begins at `c0694953`, after both.** So the one
   demonstrated real write path in this codebase's own history postdates both runner pins.

5. **The real production Proposal-creation path** (`ViolationRemediatorWorker`,
   `src/will/workers/violation_remediator.py`, confirmed present and identical at both pins) creates
   Proposals **from detected constitutional violations already on the blackboard**, not from an
   operator-supplied goal or task statement. There is no "give it a goal, it creates a Proposal to
   pursue that goal" path anywhere in this codebase's history at or before either pin.

**Exact incompatibility, stated plainly:** Document A §A6 and Document B §B6 each describe issuing
"a task statement" to "the runner" and having it "plan its own investigation" and "record its
findings and its reasoning to the blackboard." No component reachable from either pinned commit
does this. The closest real primitives are: (a) a non-executing constitutional-validation demo
that stops after printing an authority-package summary; (b) a read-only, non-proposal,
non-execution conversational Q&A path; and (c) a real but goal-blind worker launcher
(`core-admin workers run <worker_name>`, item 1 below) that starts a *named, already-declared*
worker — it takes no goal text, and for `proposal_consumer_worker` specifically, does nothing
unless an APPROVED Proposal already exists in the database, created by some other means. **This
document does not invent a CLI, wrapper, prompt channel, worker, or production change to close
this gap** — per its own instructions — and reports it as the blocker it is (see "Remaining
decisions," in the companion final report).

---

## Item-by-item findings

### 1. CLI and worker entry points

Top-level `core-admin` subcommand groups at both pins (`src/cli/admin_cli.py`, identical at both
pins): `admin`, `code`, `cognitive-roles`, `context`, `database`, `runtime`, `symbols`, `vectors`,
`workers`, `constitution`, `coherence`, `project`, `grc`, `dev`, `demo`, `intent`,
`interactive-test`, `llm-resources`, `refactor`, `tools`, `daemon`, `capabilities`, `commands`,
`status`, `tests`.

Of these, the two relevant to a governed run:

- **`core-admin workers run <worker_name>`** (`src/cli/resources/workers/run.py`, identical at
  both pins) — a **real, deterministic, mechanical** launcher: looks up
  `.intent/workers/*.yaml` by declaration name, imports the implementation class, constructs it
  (with `core_context` if the declaration requires it), and calls `worker.start()`. Takes exactly
  one argument: `worker_name` (a string matching a declared worker's YAML stem). **No goal, task,
  or free-text parameter of any kind.**
- **`core-admin runtime external-verify --target <path>`** (Unit B; present from `cb47438a`
  onward, so present at both pins) — pre-bootstrap target-binding verification only (Units A/B).
  No mutation, no DB connection, no proposal/action/worker execution — confirmed in this session's
  prior-unit memory and re-confirmed here by re-reading `src/cli/runtime_external_verify.py` at
  both pins (identical).

### 2. Free-text goal/task-statement interface

**Exists as a CLI surface** (`core-admin governance validate-request`) **but does not execute
anything** — see headline finding above. No other free-text entry point exists at either pin.

### 3. Input schema for that interface

`validate_request_command(ctx, request: str, verbose: bool = False)` — a single positional string
argument (`typer.Argument`), passed to `NaturalLanguageInterpreter.execute(user_message=request)`,
which returns a `TaskStructure` with `task_type` (one enum value), `target` (one string — file
path or symbol name, not a corpus or directory), and `constraints` (a small list of hint strings
like "dry run"). There is no field for "subject repository," "investigation scope," or
"comparison arm identity."

### 4. How a subject repository/path is bound

Via `REPO_PATH` and `MIND` environment variables, validated by Unit A's
`shared.infrastructure.external_target_binding.validate_external_target_binding()` (present from
`660834c6` onward — at both pins). This is a process-level binding (one CORE process ↔ one
external Git repo ↔ one isolated database), read once at bootstrap — not a per-invocation
parameter of any CLI command. Confirmed unchanged between both pins.

### 5. Required environment variables and bootstrap order

`REPO_PATH`, `MIND` (target's `.intent/`), `DATABASE_URL` — the same three Unit A/B/D/E all
require, confirmed present and required at both pins via `external_target_binding.py`'s own
signature (`repo_path_value`, `mind_value`, `database_url_value` — all required, fail-closed if
absent). Bootstrap order (per `runtime_external_verify.py`'s own docstring, unchanged at both
pins): the binding guard must run **before** `body.infrastructure.bootstrap` is imported, because
that import transitively initializes `GitService`, which loads
`shared.infrastructure.intent.operational_config`, which calls `get_intent_repository()` as a
module-level side effect — binding the process to whatever `REPO_PATH`/`MIND` existed at that
point. This import-order constraint is unchanged at both pins.

### 6. Database and service dependencies

PostgreSQL (schema per `schema.sql`), accessed via `service_registry.session()`
(`body/services/service_registry.py`, unchanged at both pins). No other datastore dependency found
in the proposal/worker/blackboard path. Migration bootstrapping (`bootstrap_migrations()`,
`migrate_db()`) is CORE's own ledger, unrelated to any external target.

### 7. Proposal creation and approval entry points

- **Creation:** `will.autonomy.proposal_repository.ProposalRepository.create()` — a direct
  Python/DB call, not a CLI or natural-language surface. In production, Proposals are created by
  `ViolationRemediatorWorker` from detected blackboard findings (present and identical at both
  pins) — not from an operator-supplied goal.
- **Approval:** `will.autonomy.proposal_state_manager.ProposalStateManager.approve()` — evaluates
  the target's safe-auto-approval envelope; also a direct Python/DB call, not a CLI command.

No CLI command at either pin creates or approves a Proposal.

### 8. Blackboard/evidence export facilities

`body.services.blackboard_service.blackboard_query_service.BlackboardQueryService` (identical at
both pins) — `fetch_latest_report_payload(subject)` reads the most recent report for a given
subject string. `core-admin workers show`/`purge`/`resolve`
(`src/cli/resources/workers/blackboard.py`) are the CLI-level read/administration surface. No
single "export everything from this run" command was found; evidence export as Document A/B
describe it (a sealed bundle of blackboard contents, refusal records, write inventory, etc.) is
not a built-in CLI feature at either pin — it would need to be assembled by the operator harness
from the underlying tables/queries, the same way Unit D/E's own test scaffolding already does.

### 9. Model-provider selection and model configuration

Database-backed (`shared.infrastructure.config_service.ConfigService`, `LLMResourceConfig`),
resolved per `cognitive_role`, not hardcoded in `src/` — confirmed via `client.py`'s own docstring
("NOW USES: Database-backed configuration instead of environment variables") at both pins. This
means the *code* is silent on which model runs; the *database row* for a given cognitive role
decides. An operator harness driving a trial would need to provision the relevant
`core.cognitive_roles`/`core.llm_resources` rows in the disposable database before the run — not
something either pin's `src/` alone determines.

### 10. Timeouts, budgets, and stopping controls

- Per-worker cadence: `max_interval` (declared per-worker in `.intent/workers/*.yaml`; enforced as
  a cycle cap, ADR-103 — `sleep(max(max_interval - elapsed, 0))`).
- Per-LLM-call HTTP timeouts (`shared/infrastructure/intent/operational_config.py`,
  `LLMConfig`, identical at both pins): `http_timeout_sec=60`, `request_timeout_sec=300`,
  `provider_timeout_sec=180`, `default_max_tokens=4096`.
- **No concept of a whole-trial or whole-investigation token/time budget exists in either pin's
  configuration surface.** Timeouts are per-HTTP-call or per-worker-cycle, not per-investigation.
  Document A/B's "declared-equal resource and time budgets" for comparison arms (B8, C6) would have
  to be enforced externally by the operator harness (e.g., a wall-clock cutoff on the whole
  process), not by any native CORE mechanism at these pins.

### 11. Tool/action schemas available to the runner

38 `@register_action`-decorated atomic actions at `b57423dc` (confirmed identical set of action
IDs present at `27160a0a` — no action-registration file differs between the two pins per the
commit ledger in the companion design document): `action.execute`, `assisted.apply_diff`,
`assisted.validate_diff`, `author.llm_resource`, `build.test_for_symbol`, `build.tests`,
`check.imports`, `claim.proposal`, `crate.create`, `document.gap_analysis`, `file.create`,
`file.edit`, `file.read`, `file.tag_metadata`, `fix.atomic_actions`, `fix.capability_tagging`,
`fix.docstrings`, `fix.duplicate_ids`, `fix.format`, `fix.headers`, `fix.ids`, `fix.imports`,
`fix.logging`, `fix.modularity`, `fix.path_resolver`, `fix.placeholders`, `fix.settings_access`,
`fix.vulture_heal`, `log.archive_partitions`, `log.maintain_partitions`,
`project.cognitive_roles`, `refactor.apply_split`, `remediate.cognitive_role`, `sync.db`,
`sync.vectors_code`, `sync.vectors_constitution`, `test.candidate_validate`, `test.execute`,
`test.sandbox_validate`. All are file/crate/proposal/sync/test/fix/build/refactor/document-scoped.
None accepts or produces a corpus-wide "investigation plan."

### 12. Network-facing functionality

Only two categories found in `src/` at either pin: (a) LLM provider HTTP calls (Anthropic/OpenAI/
Ollama endpoints, model/credentials DB-configured — see item 9); (b) `GitService`'s own `git`
subprocess calls (`shared/infrastructure/git_service.py`), which reach the network only if
operated against a remote (e.g., cloning the pinned runner/subject, done by the operator before
isolation, per the companion design document's ordering). No other outbound-network-capable
production code was found.

### 13. Provider request payloads — tools/search/fetch/browser/connector exposure

**None found at either pin.** Full detail already recorded in the companion design document's
"Exact-runner verification" section, reproduced in summary here: `AnthropicProvider.chat_completion`
(`src/shared/infrastructure/llm/providers/anthropic.py`, confirmed byte-identical between both
pins) builds a request payload with exactly `model`, `max_tokens`, `system`, `messages` —
**no `tools` key at all** — via raw `httpx.AsyncClient.post()`, no Anthropic SDK. Same absence of
any `tools=`/`tool_choice` parameter in the OpenAI and Ollama provider implementations. No
`web_search`/`computer_use`/`bash_2*`/`code_execution`/server-tool identifier found anywhere in
`src/` at either pin. The two "connector"-string hits at each pin
(`src/mind/governance/executable_rule.py`, `src/shared/infrastructure/intent/intent_connector.py`)
are confirmed false positives — an internal governance-rule dataclass comment and an
`.intent/`-loading class name, unrelated to any web/GitHub connector concept.

### 14. Do the blind output's assumed procedures map to real interfaces without production changes?

**No — see the headline finding above.** Neither Document A's Trial 0 procedure (A6: "the runner
is invoked once against the pinned subject snapshot with a task statement") nor Document B's
Trial 1 procedure (B6: "one statement, issued identically to all three arms") corresponds to any
real, executing interface at either pin. Realizing either procedure as written would require new
production code — at minimum, some component that accepts a free-text goal and drives an actual
multi-step governed investigation to completion, recording its own plan and findings to the
blackboard, which does not exist at either pin today. This document does not propose what that
component should look like; it reports that it does not yet exist, precisely, with the evidence
above, and does not invent one.

---

## Summary table — proved at both pins / one pin / inference / open

| # | Item | Status |
|---|---|---|
| 1 | CLI/worker entry points | Proved, both pins, identical |
| 2 | Free-text goal interface exists but non-executing | Proved, both pins, identical |
| 3 | Input schema (single string → single-target TaskStructure) | Proved, both pins, identical |
| 4 | Subject binding via REPO_PATH/MIND | Proved, both pins, identical |
| 5 | Required env vars + bootstrap order | Proved, both pins, identical |
| 6 | DB/service deps | Proved, both pins, identical |
| 7 | Proposal creation/approval entry points | Proved, both pins, identical |
| 8 | Blackboard export — no single "export all" command | Proved (absence), both pins, identical |
| 9 | Model-provider selection is DB-configured, not in src/ | Proved, both pins, identical |
| 10 | No whole-trial budget concept in config | Proved (absence), both pins, identical |
| 11 | 38 registered actions, none investigation-shaped | Proved, both pins, identical |
| 12 | Network surface: LLM + git remote only | Proved, both pins, identical |
| 13 | No tool-use/search/fetch/connector capability | Proved, both pins, identical |
| 14 | No real end-to-end free-text-goal interface | Proved (absence), both pins, identical — **the blocker** |

No item above rests on inference alone; every row cites a specific file, docstring, or diffed
absence. No open/unresolved-classification item remains — the evidence for item 14 is conclusive,
not ambiguous, which is itself the finding.
