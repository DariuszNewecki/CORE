# Vocabulary

CORE uses a precise vocabulary. Every term has exactly one meaning.
This page is the index. One sentence per term, one link to the full definition.

If a term appears in CORE but is not listed here, it is an undeclared assumption.

---

## Foundational concepts

These concepts exist independently of any implementation. They would be true
in any system governed by the same principles.

[NorthStar](#northstar) · [UNIX](#unix) · [Octopus](#octopus) · [Worker](#worker) ·
[Document](#document) · [Rule](#rule) · [Phase](#phase) · [Authority](#authority) ·
[Evidence](#evidence) · [Action](#action) · [Finding](#finding) · [Proposal](#proposal) ·
[Blackboard](#blackboard) · [Crate](#crate) · [Gate](#gate) · [Audit](#audit) ·
[Remediation](#remediation) · [Convergence](#convergence) · [Indeterminate](#indeterminate)

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

### Document

A persisted artifact that CORE may load. Has no implicit meaning.

→ [CORE-CONSTITUTION-v0.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/constitution/CORE-CONSTITUTION-v0.md)

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

### Evidence

The minimal set of inputs required to evaluate a Rule at a declared Phase.

→ [CORE-Evidence-as-Input.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Evidence-as-Input.md)

---

### Action

A single-purpose unit of work with a declared contract. The UNIX program
in CORE's pipeline.

→ [CORE-Action.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Action.md)

---

### Finding

An observation posted to the Blackboard by a sensing Worker describing a
violation or condition. Does not prescribe a response.

→ [CORE-Finding.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Finding.md)

---

### Proposal

A declared, authorized intent to execute one or more Actions. Before
authorization: a draft. After authorization: a commitment.

→ [CORE-Proposal.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Proposal.md)

---

### Blackboard

The shared ledger. The only communication channel between Workers.
Remove it and the Octopus cannot coordinate.

→ [CORE-Blackboard.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Blackboard.md)

---

### Crate

A staged, sandboxed package of changes. The unit of governed mutation.
Every file change must pass through a Crate before reaching production.

→ [CORE-Crate.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Crate.md)

---

### Gate

A validation point that must pass before execution continues. Gates block —
they do not advise. There is no override.

→ [CORE-Gate.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Gate.md)

---

### Audit

Inspection of system state against declared Rules. Produces Findings.
Observes. Does not act.

→ [CORE-Rule-Evaluation-Semantics.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Rule-Evaluation-Semantics.md)

---

### Remediation

Resolution of a Finding by applying a governed fix. Every step is traced,
authorized, and reversible.

→ [CORE-Remediation.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Remediation.md)

---

### Convergence

The state where the rate of Finding resolution exceeds the rate of Finding
creation. The operational goal of the autonomous loop.

→ [CORE-Remediation.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Remediation.md)

---

### Indeterminate

An evaluation outcome where a Rule cannot be determined to hold or violate.
Treated as blocking for blocking rules.

→ [CORE-Rule-Evaluation-Semantics.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Rule-Evaluation-Semantics.md)

---

## CORE implementations

These are the concrete realizations of the foundational concepts in CORE.

| Term | One sentence | Source |
|------|-------------|--------|
| Mind | `.intent/` and the governance machinery that reads it. | [CORE-Mind-Body-Will-Separation.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Mind-Body-Will-Separation.md) |
| Body | The execution surface: atomic actions, gates, file writes. | [CORE-Mind-Body-Will-Separation.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Mind-Body-Will-Separation.md) |
| Will | The autonomous layer: workers, proposals, the remediation loop. | [CORE-Mind-Body-Will-Separation.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Mind-Body-Will-Separation.md) |
| Constitution | The supreme law in `.intent/`. Human-authored only. Immutable to CORE at runtime. | [CORE-CONSTITUTION-v0.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/constitution/CORE-CONSTITUTION-v0.md) |
| AtomicAction | A registered, governed, single-purpose implementation of Action. | [CORE-Action.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Action.md) |
| ActionResult | The structured contract every AtomicAction must return: action_id, ok, data, duration_sec. | [CORE-Action.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Action.md) |
| ActionExecutor | The Body-layer dispatcher that resolves an action_id to its registered AtomicAction and invokes it. | [CORE-Action.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Action.md) |
| ProposalAction | A single AtomicAction within a Proposal, with its parameters and execution order. | [CORE-Proposal.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Proposal.md) |
| ProposalScope | The declared files and domains a Proposal will touch. | [CORE-Proposal.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Proposal.md) |
| ProposalExecutor | The Will-layer component that executes an approved Proposal by dispatching its actions via ActionExecutor. | [CORE-Proposal.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Proposal.md) |
| FileHandler | The only governed write path for file system mutations in CORE. All writes pass through it and through IntentGuard. | [CORE-IntentGuard.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-IntentGuard.md) |
| IntentRepository | The runtime index of all constitutional documents, rules, and policies in `.intent/`. | [CORE-IntentRepository.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-IntentRepository.md) |
| CognitiveRole | A declared responsibility assigned to an AI cognitive resource. e.g. Architect, Coder, Auditor. | [CORE-Cognitive-Role-Capability-Resource-Taxonomy.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Cognitive-Role-Capability-Resource-Taxonomy.md) |
| Capability | A technical ability that a cognitive resource provides. e.g. code_generation, reasoning. | [CORE-Capability-Taxonomy.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Capability-Taxonomy.md) |
| Resource | A concrete AI model or service that provides one or more Capabilities. | [CORE-Cognitive-Role-Capability-Resource-Taxonomy.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Cognitive-Role-Capability-Resource-Taxonomy.md) |
| GovernanceDecider | The Will-layer component that evaluates a proposed change against constitutional constraints and returns an authorization decision. | [CORE-Mind-Body-Will-Separation.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Mind-Body-Will-Separation.md) |
| ViolationSensor | A sensing Worker that posts audit violations as Findings to the Blackboard. | [CORE-ViolationSensor.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-ViolationSensor.md) |
| RemediatorWorker | An acting Worker that claims Findings and creates Proposals via the RemediationMap. | [CORE-RemediatorWorker.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-RemediatorWorker.md) |
| ViolationExecutor | An acting Worker. Legacy LLM-direct remediation fallback for unmapped rules. | [CORE-ViolationExecutor.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-ViolationExecutor.md) |
| ConsumerWorker | An acting Worker that executes approved Proposals via ActionExecutor. | [CORE-ConsumerWorker.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-ConsumerWorker.md) |
| ShopManager | A Worker whose single job is supervising other Workers. | [CORE-ShopManager.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-ShopManager.md) |
| IntentGuard | The runtime Gate that evaluates every file write against constitutional Rules. | [CORE-IntentGuard.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-IntentGuard.md) |
| Canary | The execution Gate that validates a Crate before it is applied. | [CORE-Canary.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Canary.md) |
| ConservationGate | The runtime Gate that ensures LLM-produced code preserves the logic it replaces. | [CORE-ConservationGate.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-ConservationGate.md) |
| ConstitutionalEnvelope | The set of Rules injected into an LLM prompt to constrain its output. | [CORE-ConstitutionalEnvelope.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-ConstitutionalEnvelope.md) |
| RemediationMap | The declared mapping from Rule to AtomicAction. Lives in `.intent/`. | [CORE-RemediationMap.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-RemediationMap.md) |
| WorkflowStage | A bounded operational step inside a Phase that groups related Actions. | [CORE-Workflow-Stages.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Workflow-Stages.md) |
| ContextPacket | The minimal evidence set required to evaluate Rules at a specific Phase. | [CORE-Context-Packet-Doctrine.md](https://github.com/DariuszNewecki/CORE/blob/main/.intent/papers/CORE-Context-Packet-Doctrine.md) |

---

## Failure modes

| Term | One sentence | Source |
|------|-------------|--------|
| Logic evaporation | LLM-produced code that
