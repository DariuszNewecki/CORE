<!-- path: .intent/papers/CORE-ConstitutionalEnvelope.md -->

# CORE — The Constitutional Envelope

**Status:** Canonical
**Authority:** Constitution
**Scope:** All LLM invocations within CORE

---

## 1. Purpose

This paper defines the Constitutional Envelope — the mechanism by which
constitutional law reaches the LLM before it produces output.

---

## 2. The Problem

An LLM operating without constitutional constraints is operating without law.

It may produce syntactically valid code that:
- violates layer separation
- bypasses governance surfaces
- contradicts CLI structure rules
- introduces ungoverned file writes

The LLM does not know CORE's rules unless they are explicitly provided.
Hoping the LLM will infer constitutional compliance is not governance.

---

## 3. Definition

A Constitutional Envelope is the set of Rules injected into an LLM prompt
to constrain its output to constitutional compliance before it is produced.

It is not a suggestion. It is not guidance. It is law declared to the LLM
in the same terms CORE declares law everywhere: explicit, phase-bound,
authority-attributed.

---

## 4. How It Works

Before invoking an LLM for code generation or modification, the caller
constructs a Constitutional Envelope for the target files:

1. The target file paths are resolved to their architectural layers.
2. The IntentRepository is queried for all active rules applicable to
   those layers.
3. The rules are formatted as a constraints block and injected into the
   system prompt.
4. The LLM receives the constraints as part of its constitutional context.

The LLM's obligation is to satisfy the rules. It is not asked to understand
them. It is not asked to agree with them. It must satisfy them.

## 4a. Technical Construction

A ConstitutionalEnvelope is built by `ConstitutionalEnvelope.build(target_files)`:

**Step 1 — Resolve layers**
The target file paths are mapped to their architectural layers using
path prefix matching (`src/will/`, `src/body/`, `src/mind/`, etc.).

**Step 2 — Query rules**
The IntentRepository is queried for all active rules via
`list_policy_rules()`. Rules are filtered to those applicable to the
resolved layers.

**Step 3 — Deduplicate and sort**
Duplicate rules are removed. Rules are sorted by authority precedence:
Constitution before Policy before Code.

**Step 4 — Format**
The filtered rules are formatted as a constraints block — a structured
text representation suitable for injection into a system prompt.

**Step 5 — Return**
The result is a `ConstitutionalEnvelope` with:
- `text` — the formatted constraints block, ready for prompt injection
- `rule_count` — number of rules injected (may be zero for ungoverned layers)
- `layers` — the architectural layers resolved from the target files

## 4b. IntentRepository Unavailability vs Empty Envelope

These two conditions are distinct and handled differently:

**IntentRepository unreachable (fail-closed):**
If the IntentRepository cannot be reached at build time, the envelope
MUST NOT allow the LLM invocation to proceed ungoverned. The correct
behaviour is fail-closed:

- `ConstitutionalEnvelope.build()` raises a `GovernanceError` when the
  IntentRepository cannot be reached.
- The calling Worker catches `GovernanceError`, marks the in-flight
  Finding as `abandoned`, posts a `report` entry with subject
  `governance.envelope_failure::{worker_uuid}` recording the error,
  and halts processing for the current run cycle.
- No LLM invocation proceeds when the law is unreadable.

The rationale: an ungoverned LLM mutation is constitutionally worse than
no mutation. If the law cannot be read, the action must not proceed.

**IntentRepository reachable but returns zero rules (fail-open):**
If the IntentRepository is reachable but returns no applicable rules for
the resolved layers, this is a valid constitutional state — the layer
has no declared constraints yet. The envelope is returned with
`rule_count=0` and an empty `text`. The LLM invocation proceeds without
injected constraints. A `governance.envelope_empty::{worker_uuid}` advisory
entry is posted to the Blackboard for observability, but processing
continues.

The rationale: new layers and layers under active development may
legitimately have no rules yet. Blocking writes until a rule exists
inverts the intended workflow — rules follow code, not the other way around.

## 4c. Injection

The `envelope.text` is injected into the LLM system prompt as a
dedicated section, typically labeled "Constitutional constraints" or
"Governance requirements."

The LLM is instructed that these constraints are not guidelines —
they are requirements the produced code must satisfy.

If `envelope.rule_count` is zero, the constraints section is omitted
from the prompt entirely. The LLM is not told the envelope is empty.

---

## 5. Relationship to Gates

The Constitutional Envelope is upstream of the Gates. It constrains the
LLM's output before any Gate evaluates it.

Gates are the enforcement surface for what the LLM produces despite the
Envelope. The Envelope reduces Gate failures. It does not replace them.

The correct order is:

Constitutional Envelope (constrain before generation)
→ LLM generates output
→ ConservationGate (verify logic preserved)
→ IntentGuard (verify constitutional compliance)
→ Canary (verify system health)

An LLM invocation without a Constitutional Envelope is a governance gap.
Every such invocation is a candidate for having an Envelope added.

---

## 6. Current State

Not all LLM invocations in CORE currently use a Constitutional Envelope.
The ViolationExecutor's prompt template includes partial constitutional
guidance hardcoded in the system prompt. This is not equivalent to a
Constitutional Envelope — it does not derive rules dynamically from
`.intent/` and does not update when rules change.

The gap between hardcoded guidance and a governed Constitutional Envelope
is the difference between advisory context and constitutional constraint.

---

## 7. Non-Goals

This paper does not define:
- the formatting of the constraints block in prompts
- which LLM provider or model receives the envelope
- the IntentRepository query implementation

Those are implementation concerns.
