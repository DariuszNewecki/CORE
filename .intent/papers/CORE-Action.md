<!-- path: .intent/papers/CORE-Action.md -->

# CORE — The Action

**Status:** Canonical
**Authority:** Constitution
**Scope:** All executable units of work in CORE

---

## 1. Purpose

This paper defines the Action — the single-purpose unit of work — and
its implementation as an AtomicAction in CORE.

---

## 2. Definition

An Action is a single-purpose unit of work with a declared contract.

It takes defined inputs. It produces a defined output. It does not
produce side effects outside its declared scope. It does not make
decisions beyond its declared responsibility.

An Action succeeds or fails. It always reports which.

---

## 3. The AtomicAction Contract

Every AtomicAction in CORE must satisfy this contract:

**Signature:**
```python
async def action_*(
    write: bool = False,
    **kwargs
) → ActionResult
```

**Rules:**
- The function name must start with `action_`.
- `write: bool = False` is always the first parameter.
  When `write=False` the action runs in dry-run mode — it may read
  and validate but must not write anything.
- Additional parameters are passed via `**kwargs` from the Proposal.
- The return type is always `ActionResult`. No exceptions.
- Actions that need `CoreContext` receive it via `**kwargs` as
  `core_context`.

---

## 4. ActionResult

Every AtomicAction returns an `ActionResult` with exactly these fields:

| Field | Type | Description |
|-------|------|-------------|
| `action_id` | string | The registered ID of this action. e.g. `fix.imports` |
| `ok` | boolean | True if the action succeeded. False if it failed or found violations. |
| `data` | object | Action-specific structured results. |
| `duration_sec` | float | How long the action took. |
| `impact` | ActionImpact | Optional. The impact level of what was done. |

`ok=False` is not an exception. It is a valid outcome. An action that
finds violations returns `ok=False` with the violations in `data`.
An action that cannot complete returns `ok=False` with the error in `data`.

---

## 5. Registration

Every AtomicAction is registered with a single `@atomic_action` decorator.

| Field | Required | Description |
|-------|----------|-------------|
| `action_id` | Yes | Unique dot-notation identifier. e.g. `fix.imports` |
| `description` | Yes | One sentence describing what this action does. |
| `category` | Yes | `ActionCategory` enum value: `FIX`, `CHECK`, `SYNC`, `FILE`, `CRATE` |
| `impact` | Yes | `ActionImpact` enum value. See section 6. |
| `policies` | Yes | List of policy IDs this action is governed by. |
| `remediates` | No | List of rule IDs this action resolves. Used by RemediationMap. |

An action that is not registered does not exist constitutionally.
It cannot be referenced in a Proposal. It cannot appear in the
RemediationMap.

---

## 6. Impact Levels

The `impact` field uses the `ActionImpact` enum:

| Enum value | Meaning |
|------------|---------|
| `ActionImpact.READ_ONLY` | Reads data only. No writes. |
| `ActionImpact.WRITE_METADATA` | Writes only metadata: IDs, headers, comments. Never logic. |
| `ActionImpact.WRITE_CODE` | Writes or modifies functional code. |
| `ActionImpact.WRITE_DATA` | Writes to databases, files, or external systems. |

Impact level informs the risk assessment of any Proposal that uses
this action.

---

## 7. The `remediates` Field

The `remediates` field on a registered action declares which rule IDs
this action resolves.

This field is the technical basis of the RemediationMap. When the
RemediationMap declares that `style.import_order` is remediated by
`fix.imports`, it is because `fix.imports` declares
`remediates: ["style.import_order"]`.

The RemediationMap is the authoritative routing declaration.
The `remediates` field is the implementation declaration.
They must be consistent.

---

## 8. Dry-run Requirement

Every action must respect `write=False`.

When `write=False`:
- The action may read files, inspect state, compute results.
- The action must not write any file, database record, or external state.
- The action must return a result describing what would have happened.

An action that writes when `write=False` is a constitutional violation.

---

## 9. Migration Note

The codebase currently uses two stacked decorators: `@register_action`
and `@atomic_action`. This is a known duplication that predates this
paper. The two decorators have overlapping fields and in several cases
carry mismatched `action_id` values between them.

The target state is a single `@atomic_action` decorator matching the
contract defined in section 5. Migration is a code normalization task.
Until migration is complete, `@register_action` is the authoritative
source for `action_id` and `remediates`. `@atomic_action` is the
authoritative source for `impact`.

---

## 10. Non-Goals

This paper does not define:
- the ActionExecutor dispatch mechanism
- the atomic registry implementation
- specific action implementations
- error recovery strategies
