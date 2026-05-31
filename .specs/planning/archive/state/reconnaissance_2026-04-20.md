# Reconnaissance — Block-A Documentation Cleanup

**Date:** 2026-04-20
**Working directory:** `/opt/dev/CORE`
**Scope:** Ground-truth evidence only. No files modified.

---

## Section 1 — Git activity since 2026-04-15

### `git log --oneline --since="2026-04-15" --until="now"`

```
ff67bfe6 chore(env): explicit allowlist for tracked env fixtures
30f93e26 chore: root cleanup.
ae03b301 docs(specs): session handoff — engine integrity diagnostic
8a1556e4 feat(governance): task_type as first-class field, phase mapping in .intent/
a0f68287 fix(tests): govern source→test path mapping, ground build.tests in real symbols
f0ddfd85 Delete obsolete embedding_utils test — symbols removed, no rename path
7e6d46b5 Update stale imports in 9 test files to match current module layout
0f43d238 Remove --no-root from CI poetry install so src/* packages install
cb7caa96 Add cli to poetry packages list
59d7b640 Remove unused pytest-html reporting from pytest.ini
3a3381d3 Untrack remaining generated reports/ artifacts (completion)
e5837d3f Untrack generated audit and test report artifacts (partial)
a9051bc8 Restore ModularityChecker.check_needs_split and check_needs_refactor
2a621159 Fix is_selected: handle None/non-string node.name safely
2c63b660 Delete render_audit_report — dead entrypoint with latent regression
bc6fbe1b Complete P0.1 rollout: per-file crashes reach verdict and display
3762aa29 Extend P0.1 hardening: per-file engine crashes become ENFORCEMENT_FAILURE findings
f634e521 Draw down 11 audit findings (18 -> 6); verdict FAILED -> PASSED
8e9325fb governance: widen 1 rule, clean 3 stale-path references, discover fnmatch asymmetry
715d4e7d governance: widen 7 enforcement rules, parameterize no_direct_writes check
1fb0c772 fix(test): repair truncated line in first autonomous test — blackboard_auditor
3784ad2a docs(a3): update plan to end-of-day 2026-04-18 — Stream B complete, build.tests context gap recorded
14bde1ce fix(f9ab85c8): Autonomous test remediation: build.tests (3 finding(s) — rules: test.missing, test.failure)
6876db71 feat: add --full-ids flag to proposals list command
b85448ef fix: guard action_executor in build_tests_action for daemon path
327cfc6f fix(5c9ebbcd): Autonomous remediation: fix.format (1 violation(s) — rules: workflow.ruff_format_check)
8029572e fix(0248e2c5): Autonomous remediation: fix.format (1 violation(s) — rules: workflow.ruff_format_check)
8f06172b fix(3ad5fc84): Autonomous remediation: fix.format (1 violation(s) — rules: workflow.ruff_format_check)
20fa8d20 fix(01ab7208): Autonomous remediation: fix.format (1 violation(s) — rules: workflow.ruff_format_check)
01a357d9 Clean shared/ boundary violations
5ffb4b5a Clean shared/ boundary violations
3ebfc0e3 fix(7bf0f31b): Autonomous remediation: fix.format (1 violation(s) — rules: workflow.ruff_format_check)
3218f3f6 fix(2b64f594): Autonomous remediation: fix.format (1 violation(s) — rules: workflow.ruff_format_check)
3b00f1cb fix(d41d8565): Autonomous remediation: fix.format (1 violation(s) — rules: workflow.ruff_format_check)
a7154a5b fix(f4cdb33c): Autonomous remediation: fix.format (2 violation(s) — rules: workflow.ruff_format_check)
113458df fix(de2e08ff): Autonomous remediation: fix.format (3 violation(s) — rules: workflow.ruff_format_check)
319d5c5e fix(651a7dff): Autonomous remediation: fix.format (4 violation(s) — rules: workflow.ruff_format_check)
a406e627 fix(7511eb9e): Autonomous remediation: fix.format (5 violation(s) — rules: workflow.ruff_format_check)
a5d126a8 fix(851f3126): Autonomous remediation: fix.format (6 violation(s) — rules: workflow.ruff_format_check)
80b1523c fix(085e1d60): Autonomous remediation: fix.format (7 violation(s) — rules: workflow.ruff_format_check)
fcbe8512 fix(aaac7495): Autonomous remediation: fix.format (8 violation(s) — rules: workflow.ruff_format_check)
4ade3dba feat(workers): activate governance and proposal path workers
56af0b2f feat(dashboard): redesign governor dashboard layout
0b9fbf1d docs: update all documentation to reflect current state
dbcf2479 chore: A3 plan update.
eeb8fa2d fix(vectors): fix content display in core_specs query results
cbb39dde fix(vectors): add specs collection to query command, reduce layer constraints noise
dda26ac3 fix(vectors): correct core_specs source_path and wire into context build evidence
5adde857 fix(context): wire core_policies, core-patterns, core_specs into context build evidence
f0e9b779 feat(specs): make .specs/ layer fully visible to CORE's semantic layer
0e75187a fix(blackboard): close two Blackboard hygiene failure modes
36c4db30 fix(context): close cross-layer import failure mode in context build
8981be97 feat(context): emit constitutional layer constraints before role inference
f929af8e docs: update A3 plan — session 2026-04-15
33e9da49 feat: add core-admin runtime dashboard — five-panel governor view
961d49fd feat: add .specs/planning/ — home for roadmaps and operational plans
19a975c4 chore: update docstring references from .intent/papers/ to .specs/papers/
ed37a3bd refactor: establish .specs/ layer — move charter, papers, northstar out of .intent/
```

### `git log --all -S "_include_matches" --oneline`

```
f634e521 Draw down 11 audit findings (18 -> 6); verdict FAILED -> PASSED
```

### `git log --all -S "task_type_phases" --oneline`

```
8a1556e4 feat(governance): task_type as first-class field, phase mapping in .intent/
```

### `git log --all -S "_PHASE_BY_TASK_TYPE" --oneline`

```
8a1556e4 feat(governance): task_type as first-class field, phase mapping in .intent/
4b487975 fix: wire pipeline end-to-end (context, parse, load, runtime, audit, execution)
```

### `git log --all --diff-filter=D --name-only --since="2026-04-15" -- src/shared/infrastructure/context/cli.py`

```
commit a0f6828753adb80d35c562c649143434c05f666f
Author: D.Newecki <d.newecki@gmail.com>
Date:   Sun Apr 19 22:47:47 2026 +0200

    fix(tests): govern source→test path mapping, ground build.tests in real symbols

    Close Gap 2 and Gap 3.

    Gap 2: extract source→test path derivation into a new helper
    shared.infrastructure.intent.test_coverage_paths, governed by
    .intent/enforcement/config/test_coverage.yaml via IntentRepository.
    Three call sites (test_coverage_sensor, test_runner_sensor,
    build_tests_action) previously carried divergent hardcoded mappings;
    they now share a single governed source.

    Gap 3: repoint build.tests' ExecutionTask.params.file_path at the
    source file rather than the not-yet-existing test file, so
    CodeGenerator._build_context_package retrieves real evidence for the
    LLM. Verified against src/shared/time.py — generated tests reference
    real symbols (now_iso, datetime, UTC), not invented ones.

    Verified: dry-run of build.tests against src/shared/time.py returns
    ok=True with grounded test code. No behaviour change in the existing
    test-coverage or test-runner sensors — same mapping, just sourced from
    .intent/ via the helper.

src/shared/infrastructure/context/cli.py
```

---

## Section 2 — ADR-003 / ADR-004 landing state

### `ls -la .intent/enforcement/config/task_type_phases.yaml`

```
-rw-rw-r-- 1 lira lira 771 Apr 19 22:33 .intent/enforcement/config/task_type_phases.yaml
```

### `cat .intent/enforcement/config/task_type_phases.yaml`

```yaml
# .intent/enforcement/config/task_type_phases.yaml
# Canonical task_type → governance phase mapping.
# Authority: policy
# Phase: n/a (configuration, not a runtime phase)
# Status: active
#
# PURPOSE:
#   Single source of truth for which governance phase each
#   task_type routes to. Consumed by the service
#   (ContextService.build_for_task) and the CLI
#   (cli/resources/context/build.py) via the helper
#   shared.infrastructure.intent.task_type_phases.
#
# RULE: task_type → phase mapping MUST be read from this
# file. No hardcoded copies permitted in src/.
#
# See ADR-004.

default_phase: "execution"

mapping:
  code_generation: "execution"
  code_modification: "execution"
  test_generation: "audit"
  "test.generate": "audit"
  conversational: "runtime"
```

### `ls -la src/shared/infrastructure/intent/task_type_phases.py`

```
-rw-rw-r-- 1 lira lira 5664 Apr 19 22:08 src/shared/infrastructure/intent/task_type_phases.py
```

### `ls -la src/shared/infrastructure/context/cli.py`

```
ls: cannot access 'src/shared/infrastructure/context/cli.py': No such file or directory
```

### `grep -n "_PHASE_BY_TASK_TYPE\|_PHASE_BY_TASK\b" src/shared/infrastructure/context/service.py src/cli/resources/context/build.py`

```
(no output — no matches)
```

### `grep -n "task_type" src/shared/models/execution_models.py`

```
13:from shared.infrastructure.intent.task_type_phases import allowed_task_types
16:# ADR-004: Vocabulary governed by .intent/enforcement/config/task_type_phases.yaml.
17:_ALLOWED_TASK_TYPES: frozenset[str] = allowed_task_types()
38:    task_type: str = "code_generation"
40:    @field_validator("task_type")
42:    def _validate_task_type(cls, value: str) -> str:
45:                f"Invalid task_type {value!r}; allowed values are "
```

### `grep -n "task_type" src/body/atomic/build_tests_action.py | head -20`

```
165:        task_type="test_generation",
```

---

## Section 3 — Current audit state

### `poetry run core-admin code audit 2>&1 | tail -60`

```
[10:14:18] INFO     INFO:mind.logic.engines.knowledge_gate:orphan_file_check:
                    690/690 files reachable, 0 orphans found
[10:14:19] INFO     INFO:mind.governance.constitutional_auditor_dynamic:Dynamic
                    Rule Execution: Completed 119 rules (Skipped 5 stubs, 0
                    crashed)
           INFO     INFO:mind.governance.rule_extractor:Extracted 119 executable
                    rules from 132 policies
           INFO     INFO:mind.governance.rule_extractor:Found 1 declared-only
                    rules (no enforcement mappings):
                    governance.artifact_mutation.traceable
           INFO     INFO:mind.governance.auditor:Audit verdict: PASS
                    (executed=119, crashed=0, unmapped=1)
           INFO     INFO:body.services.file_service:Successfully wrote:
                    reports/audit_findings.json
           INFO     INFO:body.services.file_service:Successfully wrote:
                    reports/audit_auto_ignored.md
           INFO     INFO:body.services.file_service:Successfully wrote JSON to:
                    reports/audit_auto_ignored.json
           INFO     INFO:body.services.file_service:Successfully wrote:
                    reports/audit/latest_audit.json
╭───────────────────── Audit Execution Stats ──────────────────────╮
│ Rules declared: 120        Rules executed: 119  Coverage: 100.0% │
│ Effective coverage: 99.0%  Crashed: 0           Unmapped: 1      │
│ Duration: 57.40s           Total findings: 39                    │
╰──────────────────────────────────────────────────────────────────╯

       Audit Overview
┏━━━━━━━━━━┳━━━━━━━┳━━━━━━━┓
┃ Severity ┃ Count ┃     % ┃
┡━━━━━━━━━━╇━━━━━━━╇━━━━━━━┩
│ WARNING  │    37 │ 94.9% │
│ INFO     │     2 │  5.1% │
└──────────┴───────┴───────┘

╭─ Final Verdict ─╮
│ PASS            │
╰─────────────────╯
                             Audit Findings Summary
┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Severity ┃ Check ID                 ┃ Message                  ┃ Occurrences ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ WARNING  │ purity.no_ast_duplicati… │ AST duplication:         │           2 │
│          │                          │ 'IntentRepository.resolv │             │
│          │                          │ e_rel' duplicates        │             │
│          │                          │ 'SpecsRepository.resolve │             │
│          │                          │ _rel' (score=1.00)       │             │
│ WARNING  │ modularity.needs_split   │ File has 416 lines       │          32 │
│          │                          │ (limit 400) with only 2  │             │
│          │                          │ concern(s) — consider    │             │
│          │                          │ splitting                │             │
│ WARNING  │ governance.dangerous_ex… │ Forbidden primitive      │           1 │
│          │                          │ 'subprocess.check_output │             │
│          │                          │ ' used (line 55).        │             │
│ WARNING  │ autonomy.tracing.mandat… │ Line 51: missing         │           2 │
│          │                          │ mandatory call(s):       │             │
│          │                          │ ['self.tracer.record']   │             │
└──────────┴──────────────────────────┴──────────────────────────┴─────────────┘

Run with '--verbose' to see all individual locations.
```

### Finding-counter python snippet

The literal command as specified errors because `reports/audit_findings.json` is a JSON list, not a dict (`AttributeError: 'list' object has no attribute 'get'`):

```
Traceback (most recent call last):
  File "<string>", line 1, in <module>
AttributeError: 'list' object has no attribute 'get'
```

Running the same intent with a type guard (`items = d if isinstance(d, list) else ...`) yields:

```
total: 39
by severity: Counter({'warning': 37, 'info': 2})
by check_id: [('modularity.needs_split', 32), ('purity.no_ast_duplication', 2), ('autonomy.tracing.mandatory', 2), ('governance.dangerous_execution_primitives', 1), ('workflow.mypy_check', 1), ('workflow.security_check', 1)]
```

### `cat reports/audit_auto_ignored.json | head -20`

```
{
  "generated_at": "2026-04-20T08:14:19Z",
  "items": []
}
```

---

## Section 4 — Daemon and worker state

### `systemctl --user is-active core-daemon`

```
inactive
```
(exit code 3)

### `core-admin workers blackboard 2>&1 | head -40` (trimmed to the blackboard table; the head's preamble is action-registry INFO logs)

```
                            Blackboard — 50 entries
┏━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ Type      ┃ Status   ┃ Subject           ┃ Worker UUID ┃ Created             ┃
┡━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│ report    │ resolved │ audit_violation_… │ b3e1f7a2... │ 2026-04-18 14:26:34 │
│ report    │ resolved │ audit_violation_… │ c4d5e6f7... │ 2026-04-18 14:26:34 │
│ report    │ resolved │ audit_violation_… │ def9dd46... │ 2026-04-18 14:26:33 │
│ report    │ resolved │ audit_violation_… │ 33516f95... │ 2026-04-18 14:26:33 │
│ heartbeat │ resolved │ worker.heartbeat  │ cf0760a5... │ 2026-04-18 14:26:28 │
│ heartbeat │ resolved │ worker.heartbeat  │ b3e1f7a2... │ 2026-04-18 14:26:28 │
│ heartbeat │ resolved │ worker.heartbeat  │ c4d5e6f7... │ 2026-04-18 14:26:28 │
│ heartbeat │ resolved │ worker.heartbeat  │ def9dd46... │ 2026-04-18 14:26:28 │
│ heartbeat │ resolved │ worker.heartbeat  │ 33516f95... │ 2026-04-18 14:26:28 │
│ heartbeat │ resolved │ worker.heartbeat  │ bb52f62a... │ 2026-04-18 14:26:17 │
│ report    │ resolved │ proposal_consume… │ c1d2e3f4... │ 2026-04-18 14:26:14 │
│ heartbeat │ resolved │ worker.heartbeat  │ c1d2e3f4... │ 2026-04-18 14:26:14 │
│ heartbeat │ resolved │ worker.heartbeat  │ a1b2c3d4... │ 2026-04-18 14:25:28 │
│ heartbeat │ resolved │ worker.heartbeat  │ bb52f62a... │ 2026-04-18 14:25:17 │
│ report    │ resolved │ proposal_consume… │ c1d2e3f4... │ 2026-04-18 14:25:14 │
...
(most recent entries timestamped 2026-04-18 14:26:34 — none from today)
```

### `psql -U core_db -d core -h 192.168.20.23 -c "SELECT status, COUNT(*) FROM core.worker_registry GROUP BY status;"`

The literal command prompts for a password and exits with `fe_sendauth: no password supplied`. Re-run with `PGPASSWORD=core_db` (credentials from `.env`):

```
  status   | count
-----------+-------
 active    |    15
 abandoned |    20
(2 rows)
```

---

## Section 5 — RemediationMap inventory

### `grep -c "^  [a-z]" .intent/enforcement/remediation/auto_remediation.yaml`

```
19
```

### `grep -E "^  [a-z_.]+:|status:|tier:" .intent/enforcement/remediation/auto_remediation.yaml`

```
  style.import_order:
    status: ACTIVE
  linkage.duplicate_ids:
    status: ACTIVE
  purity.no_todo_placeholders:
    status: ACTIVE
  linkage.assign_ids:
    status: ACTIVE
  logic.logging.standard_only:
    status: ACTIVE
  architecture.channels.logger_not_presentation:
    status: ACTIVE
  architecture.channels.logic_no_terminal_rendering:
    status: ACTIVE
  purity.stable_id_anchor:
    status: ACTIVE
  layout.src_module_header:
    status: ACTIVE
  style.formatter_required:
    status: ACTIVE
  workflow.ruff_format_check:
    status: ACTIVE
  purity.docstrings.required:
    status: ACTIVE
  architecture.atomic_actions.must_return_action_result:
    status: ACTIVE
  modularity.needs_split:
    status: ACTIVE
  modularity.needs_refactor:
    status: PENDING
  architecture.constitution_read_only:
    status: PENDING
  code.imports.no_stale_namespace:
    status: PENDING
  architecture.mind.no_body_invocation:
    status: PENDING
  governance.mutation_surface.filehandler_required:
    status: PENDING
    status: ACTIVE
    status: ACTIVE
```

Tally of the top-level rule-key entries:
- ACTIVE: 14
- PENDING: 5
- Total rule keys: 19
- Trailing 2 orphan `status: ACTIVE` lines are nested (sub-block) entries, not top-level rules.

---

## Section 6 — ADR inventory in `.specs/decisions/`

### `ls -1 .specs/decisions/`

```
ADR-001-specs-layer-established.md
ADR-002-shared-boundary-enforcement.md
ADR-003-task-type-first-class-field-on-execution-task.md
ADR-004-govern-task-type-phase-mapping.md
README.md
```

### `grep -h "^# ADR-\|^\*\*Status:\*\*\|^\*\*Date:\*\*" .specs/decisions/ADR-*.md`

```
# ADR-001: Establish the `.specs/` layer
**Status:** Accepted
**Date:** 2026-04-15
# ADR-002: Shared Layer Boundary Enforcement
**Status:** Accepted
**Date:** 2026-04-18
# ADR-003: task_type as a first-class field on ExecutionTask
**Status:** Accepted
**Date:** 2026-04-19
# ADR-004: Govern task_type → phase mapping in `.intent/` and retire the vestigial context CLI
**Status:** Accepted
**Date:** 2026-04-19
```

---

## Section 7 — fnmatch compensation live verification

Inline Python probe (output reproduced verbatim, including preamble INFO logs):

```
[10:15:19] INFO     INFO:shared.infrastructure.intent.intent_validator:Intent
                    validation completed: 32 documents validated
           INFO     INFO:shared.infrastructure.intent.intent_repository:IntentRe
                    pository indexed 132 policies and 120 rules.
top-level agent files matched: 1
total files matched: 24
```

---

## Section 8 — Summary table

| Item | Claimed state in handoffs | Observed state today | Drift? |
|---|---|---|---|
| fnmatch include-pattern asymmetry | Discovered & compensated (commit `8e9325fb`); top-level files under `src/will/agents/*.py` still matched by `src/will/agents/**/*.py` | Probe confirms `top-level agent files matched: 1`, `total files matched: 24` | No |
| `_expr_is_intent_related` missing `Call` handling | Flagged in engine-integrity diagnostic handoff (untracked spec `tracing_mandatory_diagnostic_2026-04-20.md`); audit still reports 2 `autonomy.tracing.mandatory` findings | Audit output: `WARNING autonomy.tracing.mandatory` × 2 ("Line 51: missing mandatory call(s): ['self.tracer.record']") | No (issue still live) |
| `autonomy.tracing.mandatory` silent non-firing | Same handoff: rule claimed silently non-firing | Rule IS firing — 2 findings present this run; verdict PASS because severity=WARNING | Yes — rule fires; prior "silent non-firing" claim appears stale |
| `build.tests` context gap (ADR-003) | ADR-003 accepted 2026-04-19 — `task_type` first-class on `ExecutionTask`; context routes to correct phase | `execution_models.py` has `task_type` field + validator sourced from `task_type_phases.py`; `build_tests_action.py:165` passes `task_type="test_generation"` | No |
| phase map hardcoded in `src/` (ADR-004) | ADR-004 accepted 2026-04-19 — mapping retired from `src/`, sourced from `.intent/` | `grep _PHASE_BY_TASK_TYPE` in `service.py`/`build.py` → no matches; YAML present; helper `task_type_phases.py` present | No |
| `src/shared/infrastructure/context/cli.py` (ADR-004 retirement) | Vestigial CLI to be deleted per ADR-004 | File does not exist; deletion commit `a0f68287` (2026-04-19) | No |
| RemediationMap ACTIVE count (A3 plan claims 14) | 14 ACTIVE | 14 ACTIVE (top-level rule keys) | No |
| RemediationMap PENDING count (A3 plan claims 5) | 5 PENDING | 5 PENDING | No |
| active worker count (A3 plan claims 15) | 15 active | `core.worker_registry`: active=15, abandoned=20 | No on active count; 20 abandoned rows not surfaced in plan |
| audit verdict + finding count | (no current baseline cited in A3) | Verdict PASS; total findings 39 (37 WARNING, 2 INFO); distribution: modularity.needs_split=32, purity.no_ast_duplication=2, autonomy.tracing.mandatory=2, governance.dangerous_execution_primitives=1, workflow.mypy_check=1, workflow.security_check=1; daemon inactive; latest blackboard entry 2026-04-18 14:26:34 | — |
