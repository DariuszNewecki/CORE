# URS-001: Governed Interrogation Command

Document:  URS-001-ASK
Authority: governor
Status:    draft
Version:   0.1.0

## 1. Purpose

The governor currently reconstitutes context manually at the start of every
architectural reasoning session with an external LLM: constitutional
principles, specification retrieval, the role contract (governor not
programmer), and the requirement that answers be architectural rather than
fragmentary. This manual reconstitution is forgetful by construction. Any
omission causes the model's output to drift from the governance model, and
the governor must detect and correct drift in real time. This is work CORE
was built to eliminate.

This document specifies what the governor requires of a CORE command that
absorbs this work: a governed interrogation surface that assembles context,
enforces the role contract, verifies the output, and returns cited answers
grounded in current state.

## 2. Scope

This document specifies governor-facing requirements for architectural and
strategic interrogation of CORE. It does not specify implementation,
component decomposition, or internal worker structure. It does not specify
requirements for software CORE builds for target repositories (URS-2,
separate document).

## 3. User Role

Primary user: the governor (architect, intent author, non-programmer).
Interaction medium: command line, at autonomy level A3.

## 4. Functional Requirements

### R-001. Automatic context assembly
The governor requires that every interrogation session automatically load
the constitutional core (Mind/Body/Will separation, trust model, convergence
principle, applicable policies) without manual invocation. Forgetfulness
must not be possible.

### R-002. Policy-enforced role contract
The governor requires that the role contract (governor as non-programmer;
architectural reasoning not fragments; whole files when code is produced,
not diffs) be enforced by policy in .intent/, not re-typed per session. The
contract is amendable only by editing the policy.

### R-003. Relevant specification retrieval
The governor requires that each question trigger retrieval of relevant
.specs/ documents (papers, ADRs, northstar) via semantic search over
question content. The governor does not select what to retrieve; CORE does.

### R-004. State-grounded retrieval
The governor requires retrieval of relevant runtime state (current findings,
applicable rules, cited source files, recent consequence log entries) so
that answers reflect CORE's actual state, not an imagined one.

### R-005. Cited answers
The governor requires that every substantive claim in an answer carry a
citation to the artifact that grounds it: rule ID, finding ID, specification
reference, or source file with line range. Uncited claims are invalid
output.

### R-006. Grounded vs inferred distinction
The governor requires that each claim be labeled as grounded (traced to
verified artifact) or inferred (produced by the model's reasoning without
direct evidence). Undifferentiated prose mixing the two is invalid output.

### R-007. Honest unanswerability
The governor requires that when a question cannot be answered from current
state or retrievable specifications, CORE say so explicitly, naming what
state or specification would be required to answer it. Improvisation or
answers "from general knowledge" are failures, not fallbacks.

### R-008. Contradictions as findings
The governor requires that when retrieval surfaces a contradiction (between
constitutional rules, between specifications, or between specification and
current state) the contradiction be logged as a finding. Interrogation is
also a sensor.

### R-009. Session state and correction
The governor requires that interrogation accumulate state within a session.
Governor correction of a prior answer is a first-class input that
re-triggers retrieval and reasoning with the correction weighted, not a new
unrelated question. The remediation loop applies to dialogue.

### R-010. Structured output
The governor requires that answers be returned in a structured form
(claim, provenance, grounding) and optionally rendered as prose for reading.
The structure is primary; the prose is derivative.

### R-011. Traceable invocation
The governor requires that every interrogation session produce an entry in
the consequence log: question, retrieved context identifiers, answer,
corrections applied, findings raised. Interrogation is subject to the same
auditability as any other governed action.

### R-012. Command-invoked at A3
The governor requires that interrogation be invoked on demand via the
command line, not as an automatic workflow phase. Promotion to an automatic
pre-decision phase is a later governance decision, not in scope for this
URS.

## 5. Constraints

### C-001. Trust model
The command operates within CORE's existing trust model. The LLM is an
untrusted component; its output is verified by CORE before being returned
to the governor.

### C-002. Layer separation
Interrogation logic belongs to Will. Retrieval belongs to Body. Role
contract and citation rules belong to Mind (.intent/).

### C-003. Backend agnostic
The command must function regardless of which LLM backend is configured
(Anthropic, DeepSeek, local Ollama). The role contract and citation
requirements are backend-agnostic.

## 6. Out of Scope

- Implementation architecture (worker structure, module layout, class names)
- LLM backend selection logic (already exists)
- Vector collection schema (already exists)
- Automatic pre-decision interrogation as a workflow phase (deferred)
- URS-2 requirements for software CORE produces for target repositories

## 7. Traceability

This URS derives from lived governor friction using external LLM interfaces
for architectural reasoning, and from the convergence principle (reducing
ungoverned loops in the trust model). Downstream artifacts (the
interrogation contract policy, the worker implementation, the validation
tests) must trace to this document.

## 8. Validation

This URS is validated when:
- The interrogation contract policy (.intent/policies/interrogation_contract.yaml)
  enforces every functional requirement that is enforceable by policy.
- The worker implementation produces structured, cited, verified output
  that satisfies R-005 through R-010 on a representative question set.
- The consequence log contains complete entries satisfying R-011 for every
  session in the representative set.
- Unanswerable questions produce explicit unanswerability (R-007) rather
  than confabulation, verified on an adversarial question set.
