<!-- path: .intent/papers/CORE-Proposal.md -->

# CORE — The Proposal

**Status:** Canonical
**Authority:** Constitution
**Scope:** All authorized action in CORE

---

## 1. Purpose

This paper defines the Proposal — the declared, authorized intent to
execute one or more Actions.

---

## 2. Definition

A Proposal is the unit of authorized action in CORE.

Nothing executes in CORE without a Proposal. A Worker that executes
directly — without creating a Proposal — is in constitutional violation.

A Proposal is created by an acting Worker. It is authorized by the
constitutional approval model. It is executed by the ConsumerWorker.

---

## 3. Required Fields

Every Proposal must declare:

| Field | Type | Description |
|-------|------|-------------|
| `proposal_id` | UUID | Permanent identity. Never reused. |
| `goal` | string | Human-readable statement of intent. What this Proposal will achieve. |
| `actions` | list | One or more ProposalActions. See section 5. |
| `scope` | ProposalScope | Files and domains this Proposal will touch. See section 6. |
| `status` | string | Current lifecycle status. See section 4. |
| `created_by` | string | Identity of the Worker that created this Proposal. |
| `constitutional_constraints` | object | Evidence of the constitutional basis for this Proposal. |
| `approval_required` | boolean | Whether human approval is required before execution. |
| `risk` | object | Risk assessment: overall_risk, action_risks, risk_factors, mitigation. |

---

## 4. Status Lifecycle

draft → approved → executing → completed
↘ failed

| Status | Meaning |
|--------|---------|
| `draft` | Created. Not yet authorized. Human review required. |
| `approved` | Authorized. Ready for execution by ConsumerWorker. |
| `executing` | ConsumerWorker has begun execution. |
| `completed` | All actions executed successfully. |
| `failed` | One or more actions failed. `failure_reason` is populated. |

**Auto-approval:** Proposals where `approval_required = false` are
created directly in `approved` status. The ConsumerWorker picks them
up immediately without human intervention.

**Human approval:** Proposals where `approval_required = true` are
created in `draft` status. They wait until a human promotes them to
`approved`.

---

## 5. ProposalAction

Each action in a Proposal declares:

| Field | Type | Description |
|-------|------|-------------|
| `action_id` | string | The registered AtomicAction to execute. e.g. `fix.imports` |
| `parameters` | object | Parameters passed to the action. Must include `write: true`. |
| `order` | integer | Execution order within the Proposal. Zero-indexed. |

A Proposal with multiple actions executes them in `order` sequence.
If any action fails, execution halts and the Proposal moves to `failed`.

---

## 6. ProposalScope

The scope declares what the Proposal will touch:

| Field | Type | Description |
|-------|------|-------------|
| `files` | list | Repo-relative file paths this Proposal may modify. |
| `domains` | list | Logical domains this Proposal operates in. |

The scope is a declaration of intent, not a technical constraint.
IntentGuard enforces actual write boundaries independently.

---

## 7. Risk Assessment

Every Proposal carries a risk assessment computed at creation time.

| Field | Values | Meaning |
|-------|--------|---------|
| `overall_risk` | `safe`, `moderate`, `high` | Aggregate risk level. |
| `action_risks` | object | Per-action risk levels. |
| `risk_factors` | list | Human-readable risk explanations. |
| `mitigation` | list | Declared mitigations. |

Risk level determines `approval_required`:
- `safe` → `approval_required = false` → auto-approved
- `moderate` or `high` → `approval_required = true` → human review

---

## 8. Execution Results

After execution, the Proposal carries:

| Field | Type | Description |
|-------|------|-------------|
| `execution_results` | object | Per-action results keyed by action_id. |
| `failure_reason` | string | Populated when status is `failed`. |
| `execution_started_at` | timestamp | When execution began. |
| `execution_completed_at` | timestamp | When execution ended. |

Each action result contains: `ok`, `data`, `order`, `duration_sec`.

---

## 9. Deduplication

Before creating a Proposal, the acting Worker checks whether an active
Proposal already exists for the same action group. An active Proposal
has status `draft`, `approved`, or `executing`.

If an active Proposal exists for the same `action_id`: no new Proposal
is created. The existing one is left to complete.

This prevents infinite spin loops where a Worker repeatedly creates
Proposals for violations it cannot resolve.

---

## 10. Non-Goals

This paper does not define:
- the human approval interface
- the ConsumerWorker's execution strategy
- consequence logging
- rollback procedures
