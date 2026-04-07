<!-- path: .intent/papers/CORE-Vocabulary.md -->

# CORE — Vocabulary

**Status:** Canonical
**Authority:** Constitution
**Scope:** Entire CORE system

---

## Purpose

This document is the index of CORE's vocabulary.

Every term used in CORE is listed here with a one-sentence definition and a
pointer to the authoritative document where the full concept is developed.

If a term is used in CORE but not listed here, it is an undeclared assumption.
Declare it here or remove it.

---

## Layer A — Foundational Concepts

| Term | One sentence | Authoritative source |
|------|-------------|----------------------|
| NorthStar | The reason CORE exists: use AI to write code in a controlled way. Law outranks intelligence. Defensibility outranks productivity. | `.intent/northstar/core_northstar.md` |
| UNIX | One component, one job. Composition is the only legitimate source of complexity. | `.intent/papers/CORE-The-Octopus-UNIX-Synthesis.md` |
| Octopus | Distributed intelligence, central law. Arms act locally. Brain governs intent. Nervous system is the only channel. | `.intent/papers/CORE-The-Octopus-UNIX-Synthesis.md` |
| Worker | A constitutional officer with a single declared responsibility, acting under law not intelligence. | `.intent/papers/CORE-Workers-and-Governance-Model.md` |
| Document | A persisted artifact that CORE may load. Has no implicit meaning. | `.intent/constitution/CORE-CONSTITUTION-v0.md` |
| Rule | An atomic normative statement that evaluates to holds or violates. | `.intent/constitution/CORE-CONSTITUTION-v0.md` |
| Phase | When a Rule is evaluated. Every Rule belongs to exactly one Phase. | `.intent/constitution/CORE-CONSTITUTION-v0.md` |
| Authority | Who has the final right to decide. Every Rule has exactly one Authority. | `.intent/constitution/CORE-CONSTITUTION-v0.md` |
| Action | A single-purpose unit of work with a declared contract. | `.intent/papers/CORE-Action.md` |
| Finding | An observation posted to the Blackboard by a sensing Worker. | `.intent/papers/CORE-Finding.md` |
| Proposal | A declared, authorized intent to execute one or more Actions. | `.intent/papers/CORE-Proposal.md` |
| Blackboard | The shared ledger. The only communication channel between Workers. | `.intent/papers/CORE-Blackboard.md` |
| Crate | A staged, sandboxed package of changes. The unit of governed mutation. | `.intent/papers/CORE-Crate.md` |
| Gate | A validation point that must pass before execution continues. | `.intent/papers/CORE-Gate.md` |
| Audit | Inspection of system state against declared Rules. Produces Findings. | `.intent/papers/CORE-Rule-Evaluation-Semantics.md` |
| Remediation | Resolution of a Finding by applying a governed fix. | `.intent/papers/CORE-Remediation.md` |
| Convergence | The state where Finding resolution exceeds Finding creation. The operational goal. | `.intent/papers/CORE-Remediation.md` |

---

## Layer B — CORE Implementations

| Term | One sentence | Authoritative source |
|------|-------------|----------------------|
| Mind | `.intent/` and the governance machinery that reads it. | `.intent/papers/CORE-Mind-Body-Will-Separation.md` |
| Body | The execution surface: atomic actions, gates, file writes. | `.intent/papers/CORE-Mind-Body-Will-Separation.md` |
| Will | The autonomous layer: workers, proposals, the remediation loop. | `.intent/papers/CORE-Mind-Body-Will-Separation.md` |
| Constitution | The supreme law in `.intent/`. Human-authored only. Immutable to CORE at runtime. | `.intent/constitution/CORE-CONSTITUTION-v0.md` |
| AtomicAction | A registered, governed, single-purpose implementation of Action. | `.intent/papers/CORE-Action.md` |
| ActionResult | The structured contract every AtomicAction must return: action_id, ok, data, duration_sec. | `.intent/papers/CORE-Action.md` |
| ActionExecutor | The Body-layer dispatcher that resolves an action_id to its registered AtomicAction and invokes it. | `.intent/papers/CORE-Action.md` |
| ProposalAction | A single AtomicAction within a Proposal, with its parameters and execution order. | `.intent/papers/CORE-Proposal.md` |
| ProposalScope | The declared files and domains a Proposal will touch. | `.intent/papers/CORE-Proposal.md` |
| IntentRepository | The runtime index of all constitutional documents, rules, and policies in `.intent/`. | `.intent/papers/CORE-IntentRepository.md` |
| ViolationSensor | A sensing Worker that posts audit violations as Findings to the Blackboard. | `.intent/papers/CORE-ViolationSensor.md` |
| RemediatorWorker | An acting Worker that claims Findings and creates Proposals via the RemediationMap. | `.intent/papers/CORE-RemediatorWorker.md` |
| ViolationExecutor | An acting Worker. Legacy LLM-direct remediation fallback for unmapped rules. | `.intent/papers/CORE-ViolationExecutor.md` |
| ConsumerWorker | An acting Worker that executes approved Proposals via ActionExecutor. | `.intent/papers/CORE-ConsumerWorker.md` |
| ShopManager | A Worker whose single job is supervising other Workers. | `.intent/papers/CORE-ShopManager.md` |
| IntentGuard | The runtime Gate that evaluates every file write against constitutional Rules. | `.intent/papers/CORE-IntentGuard.md` |
| Canary | The execution Gate that validates a Crate before it is applied. | `.intent/papers/CORE-Canary.md` |
| ConservationGate | The runtime Gate that ensures LLM-produced code preserves the logic it replaces. | `.intent/papers/CORE-ConservationGate.md` |
| ConstitutionalEnvelope | The set of Rules injected into an LLM prompt to constrain its output. | `.intent/papers/CORE-ConstitutionalEnvelope.md` |
| RemediationMap | The declared mapping from Rule to AtomicAction. Lives in `.intent/`. | `.intent/papers/CORE-RemediationMap.md` |
| WorkflowStage | A bounded operational step inside a Phase that groups related Actions. | `.intent/papers/CORE-Workflow-Stages.md` |
| ContextPacket | The minimal evidence set required to evaluate Rules at a specific Phase. | `.intent/papers/CORE-Context-Packet-Doctrine.md` |

---

## Failure modes

| Term | One sentence | Authoritative source |
|------|-------------|----------------------|
| Logic evaporation | LLM-produced code that is syntactically valid but silently deletes existing behavior. | `.intent/papers/CORE-ConservationGate.md` |

---

## Amendment

Terms are added here when a new concept is introduced to CORE.
Terms are removed here when a concept is retired.
Definitions in this index are subordinate to their authoritative sources.
In case of conflict, the authoritative source wins.
