# The CORE Autonomy Ladder: Formal Specification

**Version:** 1.0.0
**Status:** Active
**Purpose:** Defines the staged progression of AI autonomy within the CORE Constitutional Software Engineering framework, with precise entry/exit criteria, safety invariants, and measurable capabilities for each level.

---

## 1. Overview and Philosophy

The **Autonomy Ladder** is a staged model for AI agency within self-governing software systems. Unlike traditional AI automation that maximizes capability without constraint, the Autonomy Ladder **progressively relaxes restrictions while maintaining constitutional governance**.

### Core Principles

1. **Governed Progression:** Each level adds **new capabilities** while **preserving all constraints** from previous levels.
2. **Fail-Safe by Design:** Higher autonomy requires stronger guardrails, not weaker ones.
3. **Measurable Transitions:** Entry and exit criteria for each level are **objectively verifiable**.
4. **Human Veto Power:** All levels preserve human authority to halt, reverse, or audit autonomous actions.

---

## 2. Level Definitions

### Level A0: Self-Awareness (Observational Autonomy)

**Capability:** The system can introspect its own codebase and build a machine-readable knowledge graph.

**Constitutional Constraint:** **Read-only**. The system may analyze but not modify any files.

#### Entry Criteria

| ID | Criterion | Verification Method |
|----|-----------|-------------------|
| A0.1 | AST parser can extract all public symbols (functions, classes) from `src/` | Run: `core-admin manage database sync-knowledge --dry-run` → Success |
| A0.2 | Knowledge graph contains ≥95% of public symbols | Query: `SELECT COUNT(*) FROM core.symbols WHERE state='discovered'` |
| A0.3 | Constitutional Auditor can load and validate all `.intent/` policies | Run: `core-admin check audit` → Zero schema validation errors |

#### Core Capabilities

- **Static Analysis:** Parse Python files using AST to extract symbols, dependencies, and metadata
- **Knowledge Graph Construction:** Store symbol relationships in PostgreSQL with UUID-based identity
- **Policy Validation:** Load and validate all YAML policies against JSON schemas

#### Exit Criteria (Sufficient for A1 Entry)

| ID | Criterion | Verification Method |
|----|-----------|-------------------|
| A0.E1 | Knowledge graph is synchronized with codebase state | Run: `core-admin check drift knowledge-graph` → Zero drift |
| A0.E2 | All audit checks pass without ignored violations | Run: `core-admin check audit --severity error` → Exit code 0 |
| A0.E3 | System can detect at least one actionable self-healing task | Query: `SELECT COUNT(*) FROM core.symbols WHERE docstring IS NULL` → >0 |

**Safety Invariant:** `∀ operation ∈ A0: operation.mutates_filesystem = False`

---

### Level A1: Governed Self-Healing (Autonomous Remediation)

**Capability:** The system can autonomously propose, validate, and execute **pre-approved, low-risk** modifications to its own codebase.

**Constitutional Constraint:** Actions limited to the **safe action whitelist** in `micro_proposal_policy.yaml`. All changes must pass pre-flight validation.

#### Entry Criteria

| ID | Criterion | Verification Method |
|----|-----------|-------------------|
| A1.1 | At least 3 self-healing action handlers registered | Run: `python verify_a1_handlers.py` → ≥3 handlers pass |
| A1.2 | Micro-proposal validation pipeline operational | Run: `core-admin manage proposals micro-apply <test-proposal>` → Success |
| A1.3 | Pre-flight audit check integrated into execution flow | Code inspection: `ExecutionAgent.execute_plan()` calls auditor before git commit |

#### Core Capabilities

- **Action Handlers:** Registered handlers for:
  - `autonomy.self_healing.fix_headers` (file header compliance)
  - `autonomy.self_healing.fix_docstrings` (missing docstring detection + generation)
  - `autonomy.self_healing.format_code` (black/ruff formatting)
  - Plus 5 additional handlers (imports, dead code, line length, policy IDs, import sorting)

- **Micro-Proposal Loop:**
  1. **Detect:** Identify non-compliant code via audit findings
  2. **Plan:** Generate action plan restricted to `allowed_actions` whitelist
  3. **Validate:** Run full constitutional audit in canary mode
  4. **Execute:** Apply changes via registered action handlers
  5. **Verify:** Confirm changes pass all audits post-application

#### Exit Criteria (Sufficient for A2 Entry)

| ID | Criterion | Verification Method |
|----|-----------|-------------------|
| A1.E1 | Successfully execute ≥5 autonomous fixes without human intervention | Action log: `grep "a1.apply.succeeded" logs/action_log.jsonl | wc -l` → ≥5 |
| A1.E2 | Zero rollbacks due to failed post-execution audits | Action log: `grep "a1.rollback" logs/action_log.jsonl` → 0 results |
| A1.E3 | Mean time between false positive fixes <5% | Calculate: `(failed_fixes / total_fixes) < 0.05` |
| A1.E4 | CoderAgent separation achieved | Architecture check: `ExecutionAgent` delegates all LLM calls to `CoderAgent` |

**Safety Invariant:** `∀ action ∈ ExecutedActions: action.name ∈ micro_proposal_policy.allowed_actions ∧ pre_flight_audit(action) = PASS`

---

### Level A2: Governed Code Generation (Generative Autonomy)

**Capability:** The system can generate **new code** (functions, classes, tests) that is **guaranteed** to comply with constitutional policies.

**Constitutional Constraint:** Generated code must pass the full validation pipeline (syntax check, linting, testing, constitutional audit) before commit. **All** generated code requires explicit human approval via cryptographic signature.

#### Entry Criteria

| ID | Criterion | Verification Method |
|----|-----------|-------------------|
| A2.1 | CoderAgent can generate and validate code independently | Unit test: `test_coder_agent_generate_and_validate()` → Pass |
| A2.2 | Self-correction engine can fix 80% of validation failures | Metric: `(successful_corrections / total_validation_failures) ≥ 0.8` |
| A2.3 | Proposal signing system enforces quorum for generated code | Integration test: Unsigned proposal → Rejection |

#### Core Capabilities

- **Code Generation with Validation Loop:**
  1. LLM generates code from high-level intent
  2. Syntax validation (AST parse)
  3. Static analysis (ruff, mypy)
  4. Constitutional audit (policy compliance)
  5. Runtime validation (isolated test execution)
  6. Self-correction on failure (max N attempts)

- **Context-Aware Generation:**
  - Read existing files to understand patterns
  - Query knowledge graph for relevant symbols
  - Respect architectural boundaries (no forbidden imports)

- **Human-in-the-Loop Approval:**
  - Generate proposal YAML: `target_path`, `action`, `justification`, `content`
  - Require cryptographic signature from approver in `approvers.yaml`
  - Enforce quorum rules (development: 1 signature, production: 2 signatures)

#### Exit Criteria (Sufficient for A3 Entry)

| ID | Criterion | Verification Method |
|----|-----------|-------------------|
| A2.E1 | Generate ≥10 validated code artifacts across diverse task types | Audit log review: Functions, classes, tests, config files |
| A2.E2 | Generated code has ≤5% post-deployment bug rate | Track: `(bugs_in_generated_code / total_generated_artifacts) ≤ 0.05` |
| A2.E3 | Self-correction success rate ≥80% | Metric: `successful_self_corrections / validation_failures ≥ 0.8` |
| A2.E4 | Zero constitutional violations in committed generated code | Query audit log: `violations WHERE source='generated_code' AND committed=true` → 0 |

**Safety Invariant:** `∀ generated_code ∈ CommittedCode: ∃ human_signature ∧ validation_pipeline(generated_code) = CLEAN ∧ constitutional_audit(generated_code) = PASS`

---

### Level A3: Strategic Self-Improvement (Architectural Autonomy)

**Capability:** The system can **propose architectural refactorings** and **detect strategic opportunities** for consolidation, abstraction, or capability enhancement.

**Constitutional Constraint:** **Advisory only.** The system identifies opportunities but **cannot execute** refactorings without explicit human approval and an approved proposal that passes `critical` quorum (production: 3 signatures).

#### Entry Criteria

| ID | Criterion | Verification Method |
|----|-----------|-------------------|
| A3.1 | Duplicate detection service operational | Run: `core-admin inspect duplicates --threshold 0.9` → Returns ranked list |
| A3.2 | Capability coverage analysis functional | Query: `SELECT COUNT(*) FROM core.symbols WHERE capability_key IS NULL` → <10% orphaned |
| A3.3 | System can generate refactoring proposals with justifications | Test: Create proposal for duplicate consolidation → Valid YAML output |

#### Core Capabilities

- **Architectural Analysis:**
  - Detect code duplication (AST + embedding similarity)
  - Identify orphaned logic (symbols without capability assignment)
  - Measure cognitive complexity and recommend decomposition
  - Detect architectural violations (forbidden imports, layer breaches)

- **Strategic Proposal Generation:**
  - Generate `constitutional_proposal` YAML for architectural changes
  - Provide justification linked to violated principles (e.g., `dry_by_design`)
  - Estimate impact (files touched, risk level, required test coverage)

- **Human-Centric Decision Support:**
  - Present proposals with evidence (similarity scores, complexity metrics)
  - Highlight trade-offs and risks
  - Suggest incremental refactoring paths

#### Exit Criteria (Aspirational - A4 Not Yet Defined)

| ID | Criterion | Verification Method |
|----|-----------|-------------------|
| A3.E1 | System proposes ≥3 validated architectural improvements per quarter | Audit proposal log |
| A3.E2 | Proposed refactorings reduce codebase complexity by ≥10% when accepted | Measure: Mean cyclomatic complexity before/after |
| A3.E3 | Human approval rate for proposals ≥60% | Metric: `approved_proposals / total_proposals ≥ 0.6` |

**Safety Invariant:** `∀ architectural_proposal ∈ A3_Proposals: proposal.requires_human_approval = True ∧ proposal.quorum_level = 'critical'`

---

## 3. Safety Properties Across All Levels

### Global Invariants

These properties **MUST** hold at every autonomy level:

1. **Constitutional Supremacy:** `∀ action: passes_audit(action, constitution) ∨ rejected(action)`
2. **Reversibility:** `∀ commit ∈ AutonomousCommits: ∃ rollback_procedure`
3. **Human Veto:** `∃ halt_command: stops_all_autonomous_activity`
4. **Auditability:** `∀ action: logged(action, timestamp, justification, result)`
5. **Fail-Closed:** `∀ ambiguity: halt_and_escalate(ambiguity) ∨ user_clarifies(ambiguity)`

### Progressive Capability Lattice

Each level is a **strict superset** of capabilities:

```
A0 ⊂ A1 ⊂ A2 ⊂ A3
```

Regression to a lower level is possible if safety invariants are violated.

---

## 4. Measurement Framework

### Key Performance Indicators (KPIs) by Level

| Level | Primary KPI | Target | Measurement Frequency |
|-------|------------|--------|---------------------|
| A0 | Knowledge graph completeness | ≥95% of public symbols | Daily (CI) |
| A0 | Audit pass rate | 100% (zero errors) | Per commit |
| A1 | Autonomous fix success rate | ≥95% | Weekly |
| A1 | False positive rate | <5% | Weekly |
| A2 | Generated code validation pass rate (first attempt) | ≥80% | Per generation |
| A2 | Human approval rate | ≥90% | Monthly |
| A3 | Proposal acceptance rate | ≥60% | Quarterly |
| A3 | Complexity reduction from accepted proposals | ≥10% | Quarterly |

### Safety Metrics (All Levels)

| Metric | Threshold | Action on Violation |
|--------|-----------|-------------------|
| Rollback rate | <1% | Halt autonomy, require manual review |
| Constitutional violations in committed code | 0 | Immediate rollback, disable autonomy |
| Unapproved critical path modifications | 0 | Halt system, security audit |

---

## 5. Operational Procedures

### Level Certification Process

To declare a level "operational," the system must:

1. **Pass all entry criteria** with documented evidence
2. **Execute a certification test suite** specific to that level
3. **Undergo human review** of at least 10 sample autonomous actions
4. **Document all known limitations** in `.intent/charter/mission/autonomy_status.yaml`

### Regression Protocol

If a level's safety invariants are violated:

1. **Immediate Halt:** All autonomous operations at that level stop
2. **Incident Analysis:** Root cause investigation (log review, code audit)
3. **Remediation:** Fix underlying issue (code, policy, or training data)
4. **Re-Certification:** Re-run certification test suite before re-enabling

### Human Override Commands

At any level, humans can:

- **Pause:** `core-admin autonomy pause` (temporary halt, resumes after approval)
- **Disable:** `core-admin autonomy disable --level A2` (permanent until re-enabled)
- **Rollback:** `git revert <autonomous-commit-hash>` (undo specific action)
- **Audit:** `core-admin check audit --autonomy-only` (review all autonomous actions)

---

## 6. Research and Validation Needs

### Open Questions for Academic Evaluation

1. **Generalizability:** Can the Autonomy Ladder framework transfer to non-Python codebases or different domains (e.g., infrastructure-as-code)?
2. **Scalability:** How does autonomous fix accuracy degrade as codebase size increases?
3. **Human Trust Calibration:** At what autonomy level do developers stop reviewing autonomous changes?
4. **Threat Model:** Can adversarial prompts cause the system to violate its constitution?

### Proposed Experiments

| Experiment ID | Description | Measured Outcome | Resources Required |
|--------------|-------------|------------------|-------------------|
| EXP-A1-01 | Run 100 autonomous A1 fixes on real codebase | Success rate, false positive rate | CORE system, test repo |
| EXP-A2-01 | Generate 50 functions from natural language specs | Validation pass rate, human acceptance rate | CORE + human study (N=10 developers) |
| EXP-A3-01 | Propose 10 architectural refactorings | Proposal quality rating (Likert scale), acceptance rate | CORE + expert panel (N=5) |
| EXP-THREAT-01 | Attempt to inject malicious proposals via prompt injection | Constitutional violation detection rate | Red team, CORE system |

---

## 7. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-01-XX | CORE Team | Initial formal specification for academic documentation |

---

## 8. References and Related Work

- **Models@Runtime:** Bencomo et al. (2014) - Dynamic adaptation frameworks
- **Architecture Description Languages (ADLs):** Medvidovic & Taylor (2000) - Formal architectural constraints
- **Policy-as-Code:** NIST SP 800-207 (Zero Trust Architecture) - Declarative security policies
- **Self-Adaptive Systems:** Salehie & Tahvildari (2009) - MAPE-K loops and adaptation strategies
- **Formal Methods in SE:** Jackson (2006) - Lightweight formal methods for software design

---

**Status:** This specification is **normative** for the CORE project and **informative** for external academic evaluation. All autonomy implementations MUST conform to this specification.
