<!-- path: .specs/papers/CORE-TestGovernance.md -->

# CORE — Test Governance

**Status:** Canonical
**Authority:** Constitution
**Scope:** Autonomous test existence enforcement pipeline

---

## 1. Purpose

This paper declares the constitutional identity, responsibility boundaries,
and operational pipeline of CORE's autonomous test governance stream.

CORE governs test existence and test execution. It does not govern test
quality, coverage thresholds, or test design. Those are human decisions.

---

## 2. Problem Statement

Source files without tests are invisible to the feedback loop. A system
that can generate code but cannot detect missing tests accumulates
untestable surface area autonomously. Test governance closes this gap by
making test existence a first-class governed invariant — sensed,
validated, and remediated within the same constitutional loop that governs
source code.

---

## 3. The Pipeline

Test governance operates as a three-stage sensing-remediation pipeline.
Each stage produces a finding consumed by the next.

### Stage 1 — Coverage Sensing

**Worker:** `TestCoverageSensor`
**Declaration:** `.intent/workers/test_coverage_sensor.yaml`

Scans the source tree against the test tree. For every source file that
has no corresponding test file, posts a `test.run_required` finding to
the Blackboard.

Path mapping is governed entirely by
`.intent/enforcement/config/test_coverage.yaml`. No path logic lives in
the worker.

### Stage 2 — Test Execution

**Worker:** `TestRunnerSensor`
**Declaration:** `.intent/workers/test_runner_sensor.yaml`

Consumes `test.run_required` findings. For each:

- If the test file does not exist: posts `test.missing`.
- If the test file exists: executes it via pytest and posts `test.failure`
  for each failing test, or resolves the finding on success.

`TestRunnerSensor` is the sole producer of `test.missing` and
`test.failure`. Any other component claiming to post these subjects is in
violation of this paper.

### Stage 3 — Test Remediation

**Worker:** `TestRemediatorWorker`
**Declaration:** `.intent/workers/test_remediator.yaml`

Consumes `test.missing` and `test.failure` findings. Generates a test
file via the constitutional LLM path and submits a `build.tests` proposal
through the standard proposal pipeline.

`TestRemediatorWorker` does not execute file writes directly. All writes
are performed by the `build.tests` atomic action under proposal governance.

---

## 4. Finding Types

The following finding subjects are canonical to this pipeline:

| Subject prefix | Producer | Consumer |
|---|---|---|
| `test.run_required` | `TestCoverageSensor`, `ProposalConsumerWorker` (re-post after commit) | `TestRunnerSensor` |
| `test.missing` | `TestRunnerSensor` | `TestRemediatorWorker` |
| `test.failure` | `TestRunnerSensor` | `TestRemediatorWorker` |

These are operational finding subjects, not rule_ids. They are not
declared in `.intent/rules/` and are not evaluated by the audit engine.
They are signals within the worker pipeline only.

---

## 5. Responsibility Boundary

This pipeline governs:

- Whether a test file exists for a source file.
- Whether an existing test file passes.
- Generation of a test file where one is absent or broken.

This pipeline does not govern:

- Test quality or design adequacy.
- Coverage percentage thresholds.
- Which source files must have tests (that is a coverage policy decision
  declared in `.intent/enforcement/config/test_coverage.yaml`).
- CI/CD integration or external test orchestration.

---

## 6. Authority and Phase

All three workers operate under **Policy** authority.

| Worker | Phase |
|---|---|
| `TestCoverageSensor` | audit |
| `TestRunnerSensor` | audit |
| `TestRemediatorWorker` | execution |

---

## 7. Known Implementation State

As of initial paper authorship:

- `TestCoverageSensor` and `TestRunnerSensor` are active.
- `TestRemediatorWorker` is active. The first autonomous test
  (`tests/will/workers/blackboard_auditor/test_generated.py`) was
  produced by this worker. Test quality is a known open item — the
  worker produces structurally valid tests; correctness is not yet
  guaranteed.
- `build.tests` proposals require a `ContextBuilder` pass before
  `CoderAgent` invocation to prevent hallucinated test content. This
  is a known gap tracked separately.

This section is informational. It does not alter the constitutional
declarations above.

---

## 8. Non-Goals

This paper does not define:

- the LLM prompt used by `TestRemediatorWorker`
- the pytest invocation strategy
- coverage reporting format
- test file naming conventions beyond what `test_coverage.yaml` declares

---

## 9. Amendment Discipline

This paper may be amended only by explicit constitutional replacement, in
accordance with the CORE amendment mechanism.

---

## 10. Closing Statement

A codebase under autonomous governance must know where its tests are.
Test governance makes test existence enforceable — not as a quality
judgment, but as a structural invariant that the system can detect,
report, and repair within its own loop.
