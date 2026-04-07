# Vocabulary

CORE uses a precise vocabulary. Every term has exactly one meaning.
This page is the index. One sentence per term, one link to the full definition.

If a term appears in CORE but is not listed here, it is an undeclared assumption.

---

## Foundational concepts

These concepts exist independently of any implementation. They would be true
in any system governed by the same principles.

[NorthStar](#northstar) · [UNIX](#unix) · [Octopus](#octopus) · [Worker](#worker) ·
[Rule](#rule) · [Phase](#phase) · [Authority](#authority) · [Action](#action) ·
[Finding](#finding) · [Proposal](#proposal) · [Blackboard](#blackboard) ·
[Crate](#crate) · [Gate](#gate) · [Audit](#audit) · [Remediation](#remediation) ·
[Convergence](#convergence)

---

### NorthStar

The reason CORE exists: use AI to write code in a controlled way.
Law outranks intelligence. Defensibility outranks productivity.

→ [core_northstar.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/northstar/core_northstar.md)

---

### UNIX

One component, one job. Composition is the only legitimate source of complexity.

→ [CORE-The-Octopus-UNIX-Synthesis.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-The-Octopus-UNIX-Synthesis.md)

---

### Octopus

Distributed intelligence, central law. Arms act locally. Brain governs intent.
The Blackboard is the only communication channel.

→ [CORE-The-Octopus-UNIX-Synthesis.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-The-Octopus-UNIX-Synthesis.md)

---

### Worker

A constitutional officer with a single declared responsibility, acting under
law not intelligence. Every Worker has exactly one job.

→ [CORE-Workers-and-Governance-Model.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Workers-and-Governance-Model.md)

---

### Rule

An atomic normative statement that evaluates to holds or violates.

→ [CORE-CONSTITUTION-v0.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/constitution/CORE-CONSTITUTION-v0.md)

---

### Phase

When a Rule is evaluated. Every Rule belongs to exactly one Phase.

→ [CORE-CONSTITUTION-v0.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/constitution/CORE-CONSTITUTION-v0.md)

---

### Authority

Who has the final right to decide. Every Rule has exactly one Authority.

→ [CORE-CONSTITUTION-v0.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/constitution/CORE-CONSTITUTION-v0.md)

---

### Action

A single-purpose unit of work with a declared contract. The UNIX program
in CORE's pipeline.

→ [CORE-Adaptive-Workflow-Pattern.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Adaptive-Workflow-Pattern.md)

---

### Finding

An observation posted to the Blackboard by a sensing Worker describing a
violation or condition. Does not prescribe a response.

→ [CORE-Workers-and-Governance-Model.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Workers-and-Governance-Model.md)

---

### Proposal

A declared, authorized intent to execute one or more Actions. Before
authorization: a draft. After authorization: a commitment.

→ [CORE-Workers-and-Governance-Model.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Workers-and-Governance-Model.md)

---

### Blackboard

The shared ledger. The only communication channel between Workers.
Remove it and the Octopus cannot coordinate.

→ [CORE-Workers-and-Governance-Model.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Workers-and-Governance-Model.md)

---

### Crate

A staged, sandboxed package of changes. The unit of governed mutation.
Every file change must pass through a Crate before reaching production.

→ *(paper in progress)*

---

### Gate

A validation point that must pass before execution continues. Gates block —
they do not advise. There is no override.

→ *(paper in progress)*

---

### Audit

Inspection of system state against declared Rules. Produces Findings.
Observes. Does not act.

→ [CORE-Rule-Evaluation-Semantics.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Rule-Evaluation-Semantics.md)

---

### Remediation

Resolution of a Finding by applying a governed fix. Every step is traced,
authorized, and reversible.

→ *(paper in progress)*

---

### Convergence

The state where the rate of Finding resolution exceeds the rate of Finding
creation. The operational goal of the autonomous loop.

→ *(paper in progress)*

---

## CORE implementations

These are the concrete realizations of the foundational concepts in CORE.

| Term | One sentence | Source |
|------|-------------|--------|
| Mind | `.intent/` and the governance machinery that reads it. | [CORE-Mind-Body-Will-Separation.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Mind-Body-Will-Separation.md) |
| Body | The execution surface: atomic actions, gates, file writes. | [CORE-Mind-Body-Will-Separation.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Mind-Body-Will-Separation.md) |
| Will | The autonomous layer: workers, proposals, the remediation loop. | [CORE-Mind-Body-Will-Separation.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Mind-Body-Will-Separation.md) |
| Constitution | The supreme law in `.intent/`. Human-authored only. Immutable to CORE at runtime. | [CORE-CONSTITUTION-v0.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/constitution/CORE-CONSTITUTION-v0.md) |
| AtomicAction | A registered, governed, single-purpose implementation of Action. | [CORE-Adaptive-Workflow-Pattern.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Adaptive-Workflow-Pattern.md) |
| ViolationSensor | A sensing Worker that posts audit violations as Findings to the Blackboard. | [audit_violation_sensor.yaml](https://github.com/DariuszNewecki/CORE/blob/main/.intent/workers/audit_violation_sensor.yaml) |
| RemediatorWorker | An acting Worker that claims Findings and creates Proposals via the RemediationMap. | [violation_remediator.yaml](https://github.com/DariuszNewecki/CORE/blob/main/.intent/workers/violation_remediator.yaml) |
| ViolationExecutor | An acting Worker. Legacy LLM-direct remediation fallback for unmapped rules. | [violation_executor.yaml](https://github.com/DariuszNewecki/CORE/blob/main/.intent/workers/violation_executor.yaml) |
| ConsumerWorker | An acting Worker that executes approved Proposals via ActionExecutor. | [proposal_consumer_worker.yaml](https://github.com/DariuszNewecki/CORE/blob/main/.intent/workers/proposal_consumer_worker.yaml) |
| ShopManager | A Worker whose single job is supervising other Workers. | [CORE-Workers-and-Governance-Model.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Workers-and-Governance-Model.md) |
| IntentGuard | The runtime Gate that evaluates every file write against constitutional Rules. | *(paper in progress)* |
| Canary | The execution Gate that validates a Crate before it is applied. | *(paper in progress)* |
| ConservationGate | The Gate that ensures LLM-produced code preserves the logic it replaces. | *(paper in progress)* |
| ConstitutionalEnvelope | The set of Rules injected into an LLM prompt to constrain its output. | *(paper in progress)* |
| RemediationMap | The declared mapping from Rule to AtomicAction. Lives in `.intent/`. | [auto_remediation.yaml](https://github.com/DariuszNewecki/CORE/blob/main/.intent/enforcement/remediation/auto_remediation.yaml) |

---

## Papers in progress

These concepts are used in CORE but do not yet have an authoritative paper:

- **Crate** — staged sandboxed change package
- **Gate** — blocking validation point (covers IntentGuard, Canary, ConservationGate)
- **Remediation** — governed fix lifecycle
- **Convergence** — operational health metric
- **ConstitutionalEnvelope** — LLM constitutional constraint injection

---

*This page reflects `.intent/papers/CORE-Vocabulary.md` in the repository.
The canonical source is always the repository.*
