---
kind: paper
id: CORE-Vocabulary
title: CORE — Vocabulary
status: canonical
doctrine_tier: constitution
---

<!-- path: .specs/papers/CORE-Vocabulary.md -->

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

The `## Canonical Vocabulary (Machine Section)` below is the sole machine-readable
source for CORE's governance-ontology vocabulary. The narrative layers above it are
human-facing commentary — they are no longer the source of any term entry. In case
of conflict between a narrative layer and the canonical section, the canonical section
governs.

---

## Layer A — Foundational Concepts

*Commentary layer. The canonical section below is authoritative.*

| Term | One sentence | Authoritative source |
|------|-------------|----------------------|
| NorthStar | The reason CORE exists: use AI to write code in a controlled way. Law outranks intelligence. Defensibility outranks productivity. | `.specs/northstar/core_northstar.md` |
| UNIX | One component, one job. Composition is the only legitimate source of complexity. | `.specs/papers/CORE-The-Octopus-UNIX-Synthesis.md` |
| Octopus | Distributed intelligence, central law. Arms act locally. Brain governs intent. Nervous system is the only channel. | `.specs/papers/CORE-The-Octopus-UNIX-Synthesis.md` |
| Worker | A constitutional officer with a single declared responsibility, acting under law not intelligence. | `.specs/papers/CORE-Workers-and-Governance-Model.md` |
| Document | A persisted artifact that CORE may load. Has no implicit meaning. | `.intent/constitution/CORE-CONSTITUTION.md` |
| Rule | An atomic normative statement that evaluates to holds or violates. | `.intent/constitution/CORE-CONSTITUTION.md` |
| Phase | When a Rule is evaluated. Every Rule belongs to exactly one Phase. | `.intent/constitution/CORE-CONSTITUTION.md` |
| Authority | Who has the final right to decide. Every Rule has exactly one Authority. | `.intent/constitution/CORE-CONSTITUTION.md` |
| Evidence | The minimal set of inputs required to evaluate a Rule at a declared Phase. | `.specs/papers/CORE-Evidence-as-Input.md` |
| Action | A single-purpose unit of work with a declared contract. | `.specs/papers/CORE-Action.md` |
| Finding | An observation posted to the Blackboard by a sensing Worker. | `.specs/papers/CORE-Finding.md` |
| Proposal | A declared, authorized intent to execute one or more Actions. | `.specs/papers/CORE-Proposal.md` |
| Blackboard | The shared ledger. The only communication channel between Workers. | `.specs/papers/CORE-Blackboard.md` |
| Crate | A staged, sandboxed package of changes. The unit of governed mutation. | `.specs/papers/CORE-Crate.md` |
| Gate | A validation point that must pass before execution continues. | `.specs/papers/CORE-Gate.md` |
| Audit | Inspection of system state against declared Rules. Produces Findings. | `.specs/papers/CORE-Rule-Evaluation-Semantics.md` |
| Remediation | Resolution of a Finding by applying a governed fix. | `.specs/papers/CORE-Remediation.md` |
| Convergence | The state where Finding resolution exceeds Finding creation. The operational goal. | `.specs/papers/CORE-Remediation.md` |
| Indeterminate | An evaluation outcome where a Rule cannot be determined to hold or violate. Treated as blocking for blocking rules. | `.specs/papers/CORE-Rule-Evaluation-Semantics.md` |

---

## Layer B — CORE Implementations

*Commentary layer. The canonical section below is authoritative.*

| Term | One sentence | Authoritative source |
|------|-------------|----------------------|
| Mind | `.intent/` and the governance machinery that reads it. | `.specs/papers/CORE-Mind-Body-Will-Separation.md` |
| Body | The execution surface: atomic actions, gates, file writes. | `.specs/papers/CORE-Mind-Body-Will-Separation.md` |
| Will | The autonomous layer: workers, proposals, the remediation loop. | `.specs/papers/CORE-Mind-Body-Will-Separation.md` |
| Constitution | The supreme law in `.intent/`. Human-authored only. Immutable to CORE at runtime. | `.intent/constitution/CORE-CONSTITUTION.md` |
| AtomicAction | A registered, governed, single-purpose implementation of Action. | `.specs/papers/CORE-Action.md` |
| ActionResult | The structured contract every AtomicAction must return: action_id, ok, data, duration_sec. | `.specs/papers/CORE-Action.md` |
| ActionExecutor | The Body-layer dispatcher that resolves an action_id to its registered AtomicAction and invokes it. | `.specs/papers/CORE-Action.md` |
| ProposalAction | A single AtomicAction within a Proposal, with its parameters and execution order. | `.specs/papers/CORE-Proposal.md` |
| ProposalScope | The declared files and domains a Proposal will touch. | `.specs/papers/CORE-Proposal.md` |
| ProposalExecutor | The Will-layer component that executes an approved Proposal by dispatching its actions via ActionExecutor. | `.specs/papers/CORE-Proposal.md` |
| FileHandler | The only governed write path for file system mutations in CORE. All writes pass through it and through IntentGuard. | `.specs/papers/CORE-IntentGuard.md` |
| IntentRepository | The runtime index of all constitutional documents, rules, and policies in `.intent/`. | `.specs/papers/CORE-IntentRepository.md` |
| CognitiveRole | A declared responsibility assigned to an AI cognitive resource. e.g. Architect, Coder, Auditor. | `.specs/papers/CORE-Cognitive-Role-Capability-Resource-Taxonomy.md` |
| Capability | A technical ability that a cognitive resource provides. e.g. code_generation, reasoning. | `.specs/papers/CORE-Capability-Taxonomy.md` |
| Resource | A concrete AI model or service that provides one or more Capabilities. | `.specs/papers/CORE-Cognitive-Role-Capability-Resource-Taxonomy.md` |
| GovernanceDecider | The Will-layer component that evaluates a proposed change against constitutional constraints and returns an authorization decision. | `.specs/papers/CORE-Mind-Body-Will-Separation.md` |
| ViolationSensor | A sensing Worker that posts audit violations as Findings to the Blackboard. | `.specs/papers/CORE-ViolationSensor.md` |
| RemediatorWorker | An acting Worker that claims Findings and creates Proposals via the RemediationMap. | `.specs/papers/CORE-RemediatorWorker.md` |
| ViolationExecutor | An acting Worker. Discovers remediation patterns for unmapped rules via LLM reasoning. Surfaces AtomicAction candidates for codification. | `.specs/papers/CORE-ViolationExecutor.md` |
| OptimizerWorker | An acting Worker. Observes repeated ViolationExecutor patterns and proposes AtomicAction codification for graduation to the constitutional path. Not yet designed. | `.specs/papers/CORE-OptimizerWorker.md` |
| ConsumerWorker | An acting Worker that executes approved Proposals via ActionExecutor. | `.specs/papers/CORE-ConsumerWorker.md` |
| ShopManager | A Worker whose single job is supervising other Workers. | `.specs/papers/CORE-ShopManager.md` |
| IntentGuard | The runtime Gate that evaluates every file write against constitutional Rules. | `.specs/papers/CORE-IntentGuard.md` |
| Canary | The execution Gate that validates a Crate before it is applied. | `.specs/papers/CORE-Canary.md` |
| ConservationGate | The runtime Gate that ensures LLM-produced code preserves the logic it replaces. | `.specs/papers/CORE-ConservationGate.md` |
| ConstitutionalEnvelope | The set of Rules injected into an LLM prompt to constrain its output. | `.specs/papers/CORE-ConstitutionalEnvelope.md` |
| RemediationMap | The declared mapping from Rule to AtomicAction. Lives in `.intent/`. | `.specs/papers/CORE-RemediationMap.md` |
| WorkflowStage | A bounded operational step inside a Phase that groups related Actions. | `.specs/papers/CORE-Workflow-Stages.md` |
| ContextPacket | The minimal evidence set required to evaluate Rules at a specific Phase. | `.specs/papers/CORE-Context-Packet-Doctrine.md` |

---

## Failure Modes

*Commentary layer. The canonical section below is authoritative.*

| Term | One sentence | Authoritative source |
|------|-------------|----------------------|
| Logic evaporation | LLM-produced code that is syntactically valid but silently deletes existing behavior. | `.specs/papers/CORE-ConservationGate.md` |

---

## Canonical Vocabulary (Machine Section)

<!-- This section is the sole machine-readable source for CORE's governance-ontology vocabulary.
     It is parsed by `core-admin intent sync vocabulary` to produce `.intent/META/vocabulary.json`.
     Grammar: one markdown table with required columns term | definition | not | authoritative_paper
     and optional columns aliases | see_also. aliases and see_also values are pipe-separated lists.
     DO NOT edit vocabulary.json directly. Edit this section and run `core-admin intent sync vocabulary`.

     Excluded from this section (separate vocabulary families per ADR-023 D7):
       - CognitiveRole  (.specs/papers/CORE-Cognitive-Role-Capability-Resource-Taxonomy.md)
       - Capability     (.specs/papers/CORE-Capability-Taxonomy.md)
       - Resource       (.specs/papers/CORE-Cognitive-Role-Capability-Resource-Taxonomy.md)

     Authoritative-paper path rule (ADR-023 D5.3 as clarified): paths must resolve to existing
     files within the governed tree (.specs/ or .intent/). The constraint is existence, not prefix.
     .intent/constitution/ and .specs/northstar/ are first-class governed locations. -->

| term | definition | not | authoritative_paper | aliases | see_also |
|------|------------|-----|---------------------|---------|----------|
| Action | A single-purpose unit of work with a declared contract. | Action is not a function call or an arbitrary execution step. In CORE, Action names the abstract concept; AtomicAction is its constitutional implementation. An Action without a declared contract is an untracked mutation. | `.specs/papers/CORE-Action.md` | | AtomicAction \| ActionExecutor |
| ActionExecutor | The Body-layer dispatcher that resolves an action_id to its registered AtomicAction and invokes it. | ActionExecutor is not a generic executor or task runner. It is the sole sanctioned dispatcher for AtomicActions. Code that invokes an AtomicAction implementation directly — bypassing ActionExecutor — violates the constitutional action contract and circumvents enforcement gates. | `.specs/papers/CORE-Action.md` | | AtomicAction \| ProposalExecutor |
| ActionResult | The structured contract every AtomicAction must return: action_id, ok, data, duration_sec. | ActionResult is not a generic return value or an HTTP response object. It is the constitutional fulfillment contract for AtomicActions. An AtomicAction that does not return an ActionResult is not a governed action — it is an untracked execution. | `.specs/papers/CORE-Action.md` | | AtomicAction \| ActionExecutor |
| Acting Worker | A Worker whose responsibility is to consume Blackboard Findings and produce governed outputs — Proposals, reports, or remediation artifacts. It reacts; it does not sense. | An Acting Worker must not run the auditor or scan the filesystem for new violations. Sensing is not its role. | `.specs/papers/CORE-Workers-and-Governance-Model.md` | | Sensing Worker \| Worker \| Proposal |
| AtomicAction | A registered, governed, deterministic operation that produces a Crate. Declared with @atomic_action, registered in the ActionRegistry, and executed exclusively via ActionExecutor. The unit of constitutional remediation. | AtomicAction is not a ProposalAction line item and is not a generic verb for what a Worker does. The statement 'all actions must go through ActionExecutor' applies only to AtomicActions — not to Worker run-loop steps or Component invocations. | `.specs/papers/CORE-Action.md` | | ProposalAction \| ActionExecutor \| Crate |
| Audit | Inspection of system state against declared Rules. Produces Findings. | Audit is not a test run, a lint pass, or a code review. Audit is systematic constitutional inspection: it evaluates every in-scope file against every declared Rule and produces Findings that enter the remediation loop. | `.specs/papers/CORE-Rule-Evaluation-Semantics.md` | | Finding \| Rule \| Remediation |
| Authority | Who has the final right to decide. Every Rule has exactly one Authority. | Authority is not rank or seniority in the human sense. Authority is a declared field on a Rule that names the source with final say: Meta, Constitution, Policy, or Code. Informal authority — assumed from experience or seniority — has no constitutional standing. | `.intent/constitution/CORE-CONSTITUTION.md` | | Rule \| Constitution \| Policy |
| Blackboard | The shared ledger. The only communication channel between Workers. | Blackboard is not a message queue, event bus, or logging system. It is the coordination surface for the autonomous loop: Workers do not communicate with each other — they communicate through the Blackboard. No Worker may act on information received directly from another Worker. | `.specs/papers/CORE-Blackboard.md` | | Worker \| Finding \| Proposal |
| Body | The execution surface: atomic actions, gates, file writes. | Body is not the daemon or the runtime. Body is the execution surface: AtomicActions, Gates, and FileHandler constitute it. Body executes what Will authorizes; it does not plan, propose, or reason about what to do. | `.specs/papers/CORE-Mind-Body-Will-Separation.md` | | Mind \| Will \| AtomicAction |
| Canary | The execution Gate that validates a Crate before it is applied. | Canary is not a test runner or a syntax validator in isolation. It is the Gate that validates a complete Crate — as a package — before it is applied to the filesystem. A Crate that fails the Canary is not applied and the Proposal is marked failed. | `.specs/papers/CORE-Canary.md` | | Gate \| Crate \| IntentGuard |
| Component | A phase-bound execution unit invoked within a single phase of a command lifecycle. Components return a ComponentResult and operate within the phase boundaries declared in CORE-Phases-as-Governance-Boundaries.md. | A Component is not a Worker. Components are short-lived, phase-scoped, and invoked by orchestrators — not by the daemon. A Component does not claim Blackboard entries. | `.specs/papers/CORE-Adaptive-Workflow-Pattern.md` | Processor | Worker \| Phase |
| ConservationGate | The runtime Gate that ensures LLM-produced code preserves the logic it replaces. | ConservationGate is not a diff tool or a code formatter. It is the Gate that detects logic evaporation: syntactically valid code that silently deletes existing behavior. Syntactic validity does not imply behavioral preservation. | `.specs/papers/CORE-ConservationGate.md` | | Gate \| Logic evaporation \| IntentGuard |
| Constitution | The authority level immediately below Meta. A Rule or paper at constitution authority declares non-negotiable structural constraints that cannot be overridden by Policy or Code authority artifacts. Also used informally to refer to the full .intent/ governance layer. | Constitution is not a folder path and not a synonym for Rule. 'Constitutional rule' means a Rule with authority: constitution — not a rule located in a folder named constitution. | `.intent/constitution/CORE-CONSTITUTION.md` | | Authority \| Policy \| Rule |
| ConstitutionalEnvelope | The set of Rules injected into an LLM prompt to constrain its output. | ConstitutionalEnvelope is not a system prompt or a style guideline. It is the governed set of constitutional Rules injected into every LLM invocation that produces governed outputs. An LLM invoked without a ConstitutionalEnvelope produces ungoverned output regardless of its actual content. | `.specs/papers/CORE-ConstitutionalEnvelope.md` | | Rule \| IntentGuard |
| ConsumerWorker | An acting Worker that executes approved Proposals via ActionExecutor. | ConsumerWorker is not a Proposal author. It only executes Proposals that have already passed enforcement gates and been approved. ConsumerWorker has no Proposal creation authority; it executes, it does not propose. | `.specs/papers/CORE-ConsumerWorker.md` | | Acting Worker \| ProposalExecutor \| Proposal |
| ContextPacket | The minimal evidence set required to evaluate Rules at a specific Phase. | ContextPacket is not a cache or a configuration bundle. It is the scoped evidence set required for a specific Phase. Over-inclusion violates the Evidence-as-Input discipline by introducing untrusted evidence; under-inclusion produces evaluation failures. | `.specs/papers/CORE-Context-Packet-Doctrine.md` | | Evidence \| Phase \| Audit |
| Convergence | The state where Finding resolution exceeds Finding creation. The operational goal. | Convergence is not a state of zero violations. It is a dynamic rate condition: resolution must outpace creation. A system with violations that is resolving faster than it discovers new ones is converging. A system with no violations today but accelerating debt is diverging. | `.specs/papers/CORE-Remediation.md` | | Remediation \| Finding \| Audit |
| Crate | A staged, sandboxed package of changes. The unit of governed mutation. | Crate is not a file diff, a patch, or a commit. A Crate is staged before any file is written — it is validated by the Canary Gate and applied only if it passes. A mutation applied to the filesystem without a Crate is ungoverned. | `.specs/papers/CORE-Crate.md` | | Gate \| Canary \| AtomicAction |
| Document | A persisted artifact that CORE may load. Has no implicit meaning. | Document is not a synonym for Rule, Paper, or Policy. A Document is any loadable artifact — including Rules, schemas, worker declarations, and papers. Its meaning is determined by the system that reads it, not by its content alone. | `.intent/constitution/CORE-CONSTITUTION.md` | | Rule \| Authority |
| dry_run (evaluation_only) | An audit or rule evaluation that runs the check logic and records whether a violation would be found, but generates no fix and posts no actionable Finding. The rule is evaluated; the system is not changed. | evaluation_only dry-run does not produce a finding with dry_run=true. It produces no finding at all, or a finding explicitly tagged dry_run_scope: evaluation_only that must not enter the remediation pipeline. | `.specs/papers/CORE-Action.md` | | dry_run (fix_generated) \| dry_run (finding_suppressed) |
| dry_run (finding_suppressed) | A boolean field on a Blackboard Finding that marks it as produced in a dry-run context. A Finding with dry_run_scope: finding_suppressed must not be claimed by an Acting Worker for autonomous remediation. | finding_suppressed is a property of the Finding record, not a mode of execution. It is set by the Sensing Worker at post time and is distinct from the execution mode of any downstream action. | `.specs/papers/CORE-Finding.md` | | dry_run (evaluation_only) \| dry_run (fix_generated) \| Finding |
| dry_run (fix_generated) | An execution mode in which an AtomicAction or ViolationExecutor generates the full fix artifact (Crate) but does not apply it to the filesystem. The output is inspectable; the system is not changed. | fix_generated dry-run is not the same as evaluation_only. A fix has been computed. The distinction matters for consequence logging and audit reconstruction. | `.specs/papers/CORE-ViolationExecutor.md` | | dry_run (evaluation_only) \| dry_run (finding_suppressed) \| Crate |
| Evidence | The minimal set of inputs required to evaluate a Rule at a declared Phase. | Evidence is not context, metadata, or documentation in general. Evidence is the minimum declared inputs for a specific Rule at a specific Phase. Over-supplying evidence does not improve evaluation; missing evidence is an evaluation failure. | `.specs/papers/CORE-Evidence-as-Input.md` | | Rule \| Phase \| ContextPacket |
| FileHandler | The only governed write path for file system mutations in CORE. All writes pass through it and through IntentGuard. | FileHandler is not a file utility library or a wrapper around Python's open(). It is the sole constitutional write path. Any filesystem mutation that does not pass through FileHandler and IntentGuard is an ungoverned write — a constitutional violation regardless of the mutation's content. | `.specs/papers/CORE-IntentGuard.md` | | IntentGuard \| Gate \| Crate |
| Finding | An observation posted to the Blackboard by a sensing Worker. It names a specific rule violation: the rule ID, the file path, and the severity. It is the input to the remediation loop. | A Finding is not a Proposal and not a report. A Finding describes a detected problem; it does not prescribe a fix. | `.specs/papers/CORE-Finding.md` | | Blackboard \| Sensing Worker \| Proposal |
| Gate | A validation point that must pass before execution continues. | Gate is not a check, a warning, or an advisory. A Gate is a constitutional stop: failure halts execution. Gates do not produce warnings — they produce pass or fail. The three gates in order are: ConservationGate, IntentGuard, Canary. | `.specs/papers/CORE-Gate.md` | | ConservationGate \| IntentGuard \| Canary |
| GovernanceDecider | The Will-layer component that evaluates a proposed change against constitutional constraints and returns an authorization decision. | GovernanceDecider is not the auditor or the IntentGuard. It evaluates proposed changes — not file states — against constitutional constraints before execution. The audit evaluates the current codebase; GovernanceDecider evaluates a proposed future state. | `.specs/papers/CORE-Mind-Body-Will-Separation.md` | | IntentGuard \| Proposal \| Will |
| Indeterminate | An evaluation outcome where a Rule cannot be determined to hold or violate. Treated as blocking for blocking rules. | Indeterminate is not equivalent to Pass or to unknown. It is a distinct evaluation outcome: the available evidence was insufficient to evaluate the Rule. For blocking rules, Indeterminate is treated as a violation — it does not pass. | `.specs/papers/CORE-Rule-Evaluation-Semantics.md` | | Rule \| Audit \| Evidence |
| IntentGuard | The runtime Gate that evaluates every file write against constitutional Rules. | IntentGuard is not a linter, a style checker, or an advisory layer. It is a blocking Gate: every file write is evaluated against constitutional Rules before it is applied. Failure blocks the write unconditionally. IntentGuard does not warn — it passes or blocks. | `.specs/papers/CORE-IntentGuard.md` | | Gate \| FileHandler \| ConservationGate |
| IntentRepository | The runtime index of all constitutional documents, rules, and policies in `.intent/`. | IntentRepository is not a document store or a file reader. It is the trusted access path to `.intent/`: code that reads `.intent/` files directly — bypassing IntentRepository — is operating outside the governed access contract and in violation of the architecture rules. | `.specs/papers/CORE-IntentRepository.md` | | Rule \| Constitution \| Mind |
| Logic evaporation | LLM-produced code that is syntactically valid but silently deletes existing behavior. | Logic evaporation is not a syntax error, a test failure, or a runtime exception. It is a behavioral deletion: code that parses and executes without error but silently removes or corrupts existing logic. It is the primary failure mode ConservationGate exists to detect. | `.specs/papers/CORE-ConservationGate.md` | | ConservationGate \| Crate |
| Mind | `.intent/` and the governance machinery that reads it. | Mind is not the AI or the LLM. Mind is the governance layer: the constitutional rules, policies, and the machinery that reads and enforces them. AI operates as labor inside Body and Will — it has no constitutional authority. | `.specs/papers/CORE-Mind-Body-Will-Separation.md` | | Body \| Will \| IntentRepository |
| NorthStar | The reason CORE exists: use AI to write code in a controlled way. Law outranks intelligence. Defensibility outranks productivity. | NorthStar is not a strategy document or a feature roadmap. It is a governing law: the reference against which all CORE design decisions are evaluated. When a design decision conflicts with NorthStar, the decision changes, not the star. | `.specs/northstar/core_northstar.md` | | Constitution \| Authority |
| Octopus | Distributed intelligence, central law. Arms act locally. Brain governs intent. Nervous system is the only channel. | Octopus is not a metaphor for parallel execution or microservices. It is a governance metaphor: autonomous agents are constitutionally constrained by a central law they do not own. The arms are Workers; the nervous system is the Blackboard; the brain is `.intent/`. | `.specs/papers/CORE-The-Octopus-UNIX-Synthesis.md` | | UNIX \| Worker \| Blackboard |
| OptimizerWorker | An acting Worker. Observes repeated ViolationExecutor patterns and proposes AtomicAction codification for graduation to the constitutional path. Not yet designed. | OptimizerWorker is not a performance optimizer. Its job is governance progression: graduating ViolationExecutor patterns into constitutional AtomicActions, shrinking the fallback path toward zero. It does not optimize code — it optimizes the remediation pipeline. | `.specs/papers/CORE-OptimizerWorker.md` | | ViolationExecutor \| AtomicAction \| RemediationMap |
| Phase | When a Rule is evaluated. Every Rule belongs to exactly one Phase. | Phase is not a deployment environment, a pipeline stage, or an execution mode. Phase is the declared temporal context that determines which Rules apply to a given evaluation. A Rule evaluated outside its declared Phase produces an invalid result. | `.intent/constitution/CORE-CONSTITUTION.md` | | Rule \| Authority \| WorkflowStage |
| Policy | The authority level below Constitution. Rules at policy authority declare architectural standards and conventions that may be adjusted within the bounds set by constitution-authority rules. | Policy is not a folder path. The presence of a rule in .intent/rules/ does not determine its authority — the authority field in the rule document does. | `.specs/papers/CORE-Authority-Without-Registries.md` | | Authority \| Constitution \| Rule |
| Proposal | A declared, authorized intent to execute one or more Actions. | Proposal is not a suggestion or a request. A Proposal is a constitutional artifact declaring intent to execute specific Actions on specific files. It must pass enforcement gates before execution and is traceable from Finding through execution. | `.specs/papers/CORE-Proposal.md` | | ProposalAction \| ProposalExecutor \| Finding |
| Proposal Path | The constitutional remediation path: Finding → RemediationMap → Proposal → AtomicAction. No LLM in the remediation logic. Deterministic, traceable, and the target state for all rules. | The Proposal Path is not equivalent to the ViolationExecutor Path. They are not peers. The Proposal Path is the target architecture; the ViolationExecutor Path is a temporary fallback that must shrink to zero. | `.specs/papers/CORE-Remediation.md` | | ViolationExecutor Path \| RemediationMap \| AtomicAction |
| ProposalAction | A line item inside a Proposal that names an AtomicAction ID, its parameters, and its execution order. ProposalAction is a declaration of intent, not an execution. It is resolved to an AtomicAction at execution time by ConsumerWorker. | ProposalAction is not the same as AtomicAction. A ProposalAction references an AtomicAction by ID; it does not execute it. | `.specs/papers/CORE-Proposal.md` | | AtomicAction \| Proposal \| ConsumerWorker |
| ProposalExecutor | The Will-layer component that executes an approved Proposal by dispatching its actions via ActionExecutor. | ProposalExecutor is not ActionExecutor. ProposalExecutor coordinates the execution of a complete Proposal — dispatching each ProposalAction to ActionExecutor in declared order, managing the Crate lifecycle, and recording consequences. ActionExecutor resolves a single AtomicAction. | `.specs/papers/CORE-Proposal.md` | | ActionExecutor \| ConsumerWorker \| Proposal |
| ProposalScope | The declared files and domains a Proposal will touch. | ProposalScope is not a description of intent. It is a binding commitment: a Proposal may only touch files and domains it has declared in its scope. Touching out-of-scope files is a constitutional violation. An empty scope is a validation failure per ADR-026. | `.specs/papers/CORE-Proposal.md` | | Proposal \| FileHandler |
| Remediation | The governed process of resolving a Finding by applying a fix through the constitutional pipeline: Finding → RemediationMap lookup → Proposal → AtomicAction → Crate → Gates → Apply. Every step is declared, authorized, traced, and reversible. | Remediation is not repair. Repair is ad hoc. Remediation is governed. A fix applied outside the Proposal → AtomicAction path is repair, not remediation, regardless of whether it produces the correct result. | `.specs/papers/CORE-Remediation.md` | | Proposal Path \| ViolationExecutor Path \| AtomicAction |
| RemediationMap | The declared mapping from Rule to AtomicAction. Lives in `.intent/`. | RemediationMap is not a routing table or a registry. It is a constitutional declaration: a specific AtomicAction is authorized to remediate a specific Rule. Rules without a RemediationMap entry have no constitutional fixer and flow to the ViolationExecutor Path. | `.specs/papers/CORE-RemediationMap.md` | | Proposal Path \| AtomicAction \| Rule |
| RemediatorWorker | An acting Worker that claims Findings and creates Proposals via the RemediationMap. | RemediatorWorker is not ViolationExecutor. RemediatorWorker operates on the constitutional Proposal Path: it looks up a Finding's check_id in the RemediationMap and creates a Proposal deterministically. It does not invoke LLMs to discover fixes. | `.specs/papers/CORE-RemediatorWorker.md` | | Acting Worker \| Proposal Path \| RemediationMap |
| Rule | An atomic normative statement that evaluates to holds or violates. | Rule is not synonymous with Constitution or Policy. Constitution and Policy are authority levels that a Rule may carry. A Rule at constitution authority is a constitutional rule — but 'Rule' and 'Constitution' are not interchangeable terms. | `.intent/constitution/CORE-CONSTITUTION.md` | | Authority \| Constitution \| Policy |
| Sensing Worker | A Worker whose sole responsibility is perception: it reads the world (filesystem, database, auditor output) and posts Findings to the Blackboard. It makes no decisions and takes no actions. | A Sensing Worker must not write files, create Proposals, or invoke LLMs. It is read-only with respect to the governed system. | `.specs/papers/CORE-Workers-and-Governance-Model.md` | | Acting Worker \| Worker \| Finding |
| ShopManager | A Worker whose single job is supervising other Workers. | ShopManager is not a domain Worker. It does not perform remediation, propose fixes, or execute actions. Its only authority is to observe Worker health via the Blackboard and escalate. A ShopManager that performs domain work is in constitutional violation. | `.specs/papers/CORE-ShopManager.md` | | Worker \| Blackboard |
| UNIX | One component, one job. Composition is the only legitimate source of complexity. | UNIX is not a rule about file layout, process isolation, or OS primitives. It is an architectural discipline: a component that does two things is two components that have not yet been separated. | `.specs/papers/CORE-The-Octopus-UNIX-Synthesis.md` | | Octopus \| Worker |
| ViolationExecutor | An acting Worker. Discovers remediation patterns for unmapped rules via LLM reasoning. Surfaces AtomicAction candidates for codification. The goal is to reduce this path to zero. | ViolationExecutor is not the constitutional remediation path. It is a discovery fallback for rules with no registered AtomicAction. Its outputs are candidates, not authoritative fixes. Every rule it handles is a rule awaiting constitutional codification on the Proposal Path. | `.specs/papers/CORE-ViolationExecutor.md` | | ViolationExecutor Path \| Proposal Path \| RemediationMap |
| ViolationExecutor Path | The legacy remediation fallback: Finding → LLM invocation → Crate. Used only for rules that have no registered AtomicAction in the RemediationMap. Every rule handled by this path is a rule awaiting constitutional remediation. The goal is to reduce this path to zero. | The ViolationExecutor Path is not a peer of the Proposal Path. It is a fallback. It must not claim findings whose rules are mapped in the RemediationMap — those belong to the Proposal Path. | `.specs/papers/CORE-ViolationExecutor.md` | | Proposal Path \| RemediationMap \| ViolationExecutor |
| ViolationSensor | A sensing Worker that posts audit violations as Findings to the Blackboard. | ViolationSensor is not the audit engine. It is a Worker wrapper: it invokes the audit engine and posts the output as Findings. A ViolationSensor that creates Proposals or executes actions is in constitutional violation of its Sensing Worker mandate. | `.specs/papers/CORE-ViolationSensor.md` | | Sensing Worker \| Finding \| Blackboard |
| Will | The autonomous layer: workers, proposals, the remediation loop. | Will is not the scheduler or the event loop. Will is the autonomous governance layer: Workers, the Proposal system, and the remediation loop that drives the codebase toward constitutional compliance. | `.specs/papers/CORE-Mind-Body-Will-Separation.md` | | Mind \| Body \| Worker |
| Worker | A daemon-resident autonomous unit that runs continuously, claims Blackboard entries, and performs sensing or acting. Workers are declared in .intent/workers/ and loaded by the daemon at startup. | A Worker is not a Component. Workers are long-lived, daemon-resident, and claim work from the Blackboard. A Worker may contain or invoke Components, but is not itself phase-bound. | `.specs/papers/CORE-Workers-and-Governance-Model.md` | Processor | Component \| Sensing Worker \| Acting Worker |
| WorkflowStage | A bounded operational step inside a Phase that groups related Actions. | WorkflowStage is not a Phase. A Phase is when a Rule is evaluated; a WorkflowStage is an operational grouping of Actions within a Phase. Multiple WorkflowStages may exist within one Phase. Stages are execution structure; Phases are governance structure. | `.specs/papers/CORE-Workflow-Stages.md` | | Phase \| Action \| Component |

---

## Amendment

Terms are added here when a new concept is introduced to CORE.
Terms are removed here when a concept is retired.
Definitions in the canonical section are the authoritative index entries.
In case of conflict between the canonical section and an authoritative source paper, the paper wins.
