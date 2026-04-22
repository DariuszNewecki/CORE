# Parking Note — Constitutionalize `impact_level`

**Status:** Parked. Not session-scale. Save this wherever your
parked-governance notes live (e.g. `.specs/decisions/` or
`.intent/governance/backlog/` — path is your call).

**Surfaced:** 2026-04-22, during Decision 1 of Option C (reclassifying
`fix.placeholders` from `moderate` to `safe`).

---

## Problem

`impact_level` — the field that determines whether a Proposal requires
human approval or auto-approves — is declared in Python code, inside
`@register_action(...)` decorators across ~40 action registrations in
`src/body/atomic/*.py`.

Example (`src/body/atomic/fix_actions.py`):

```python
@register_action(
    action_id="fix.placeholders",
    ...
    impact_level="safe",
    ...
)
```

This is a governance decision — "which actions execute autonomously
versus which require human oversight" — and it is carried in source
code, not in `.intent/` constitutional law.

## Why this is a problem

Per the established principle: **no governance in `src/`**. All
governance mappings, remediation configurations, and enforcement
decisions must live in `.intent/`, never hardcoded in Python.

`impact_level` violates this directly. A policy change — say,
"promote `fix.placeholders` from moderate to safe" — today requires a
Python code edit, a commit, and a redeploy. It should be an `.intent/`
edit: constitutional, not behavioral.

Scope: this is structural, not a one-off. Every action registration
carries its own `impact_level` literal. Changing the pattern means
changing all of them plus the loader.

## Evidence that the current pattern is fragile

Decision 1 (2026-04-22) surfaced `fix.placeholders` as miscategorized
`moderate` when it has the same risk profile as `safe`-classified
`fix.format`. The miscategorization went unnoticed for some time and
produced DRAFT-proposal accumulation every sensor cycle. Under a
constitutional model, the classification would be subject to
`.intent/` review and audit, not buried in a decorator literal.

## Target state

- Action registrations in `src/body/atomic/*.py` declare only
  behavioral metadata (action_id, description, handler).
- `impact_level` lives in `.intent/enforcement/config/action_risk.yaml`
  (or similar), keyed by `action_id`.
- A loader reads the mapping at runtime; `register_action` consults
  the loader rather than taking the value as a literal.
- Auditable: changes to the mapping go through the same review path
  as any other `.intent/` edit.

## Why not today

Three reasons this isn't a today-sized fix:

1. **Schema design.** The risk model today is one-axis (impact
   severity). Before externalizing it, it's worth deciding whether the
   schema should already admit the future second axis (confidence,
   reversibility, scope size — Decision 3 in Option C's framing) or
   whether that's a later migration.
2. **Loader wiring.** `register_action` is imported and invoked at
   module-load time. The `.intent/` loader has to be ready before any
   action module imports. Ordering matters.
3. **Migration surface.** ~40 action registrations. Mechanical but not
   trivial; each needs a corresponding `.intent/` entry and verification
   that the runtime classification matches the removed literal.

## Relationship to Decision 3

The open question "should the risk model have a second axis?" from the
2026-04-21 evening handoff interacts with this work. If the answer is
yes, the externalized schema should be designed with it. If no, the
single-axis externalization is straightforward.

## Action

Park. Surface when the Decision 3 policy conversation is being had
anyway, or when the DRAFT-accumulation pattern recurs under a
differently-miscategorized action.
