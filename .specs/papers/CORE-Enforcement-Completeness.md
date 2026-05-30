<!-- path: .specs/papers/CORE-Enforcement-Completeness.md -->

# CORE — Enforcement Completeness

**Status:** Canonical
**Authority:** Constitution
**Scope:** All blocking enforcement in CORE

---

## 1. Purpose

This paper defines the relationship between CORE's two enforcement times —
runtime Gates and audit-time checks — and the completeness obligation that
binds them. A Gate blocks a forbidden effect at the point it guards. A check
verifies that the Gate's guarantee actually holds across the whole codebase.
Neither is sufficient alone.

---

## 2. Definition

Enforcement in CORE happens at two times.

**Runtime enforcement** is a Gate (see CORE-Gate.md). It evaluates a single
operation at a single invocation point and blocks it if a rule is violated.
Its guarantee is local: the operation that passed through it complied.

**Audit-time enforcement** is a check. It observes the codebase statically and
reports any construct that could reach a forbidden effect — including constructs
that never pass through the runtime Gate. Its guarantee is global: no such
construct exists, or every one that does has been surfaced as a finding.

A Gate blocks what reaches it. A check finds what would not.

---

## 3. Constitutional Basis

A Gate guards an invocation point, not an effect. Its guarantee extends only to
operations that pass through that point.

This is an assumption, not a property. The Gate is complete *if and only if*
every path to the guarded effect routes through the guarded point. That
condition is not self-enforcing. Code can reach the same effect by a path the
Gate never sees, and the Gate will report nothing — because nothing reached it.

The condition must therefore be established elsewhere. It is established at audit
time, by a check that searches for the paths the Gate cannot see. The Gate
enforces compliance; the check enforces the Gate's reach.

---

## 4. The Reach Gap

IntentGuard is the canonical case. It guards `FileHandler.write_runtime_text()`
and blocks any write to a forbidden path. Its guarantee was once stated as
total: every write goes through `FileHandler`, so no write escapes the Gate.

That statement was a reachability assumption, and it was false. A raw
`pathlib.Path(".intent/x").write_text(...)` reaches the filesystem without
calling `FileHandler`, and IntentGuard never runs. The Gate was not wrong about
what it evaluated. It was wrong about what reached it.

The reach gap is invisible from inside the Gate. A Gate cannot report on traffic
it never receives. Only a check that inspects the codebase for unguarded paths
to the same effect can close it — and that check is the necessary complement to
every Gate whose effect is reachable by more than one code path.

---

## 5. Completeness Against Runtime Reality

An audit-time check recognizes a forbidden operation through a **vocabulary** —
the set of call-shapes it matches. The check is only as complete as that
vocabulary. An operation the runtime offers but the vocabulary omits is an
unguarded path the check cannot see — the same reach gap, moved one level in.

This is the defect class CORE treats as constitutionally unacceptable: **silent
incompleteness**. A vocabulary missing an entry does not fail loudly. It passes,
and the gap it leaves is invisible precisely to the instrument that would
otherwise find it.

Silent incompleteness is the only failure a governance system cannot audit its
way out of by inspection alone, because the missing entry removes the finding
that would announce it. The defense cannot be vigilance. It must be structural.

A check's vocabulary must therefore be verified complete **against runtime
reality**, and the verification must be derived from that reality, not curated
against it:

- Where the operation surface can be introspected — the methods a runtime type
  actually exposes — the vocabulary is checked against the live surface. An
  operation present at runtime but absent from the vocabulary is itself a
  finding. The set cannot silently fall behind what it governs.
- Where the surface cannot be cleanly introspected, the vocabulary names a
  watched set, and the check verifies each entry still resolves — but the
  residual that introspection cannot reach is *declared*, not hidden.

A curated list of what to enforce is itself a thing that can be silently
incomplete. A completeness check that is also curated reproduces the defect it
exists to remove. Completeness is guaranteed only when discovery is mechanical.

---

## 6. The Recurring Shape

The reach gap and silent incompleteness are one shape, seen wherever a declared
set must stay complete against a moving runtime reality and incompleteness is
silent:

- a rule with no remediation — abandoned without notice
- a file with no classification — ungoverned without notice
- a queue subject with no drainer — accumulating without notice
- a filesystem operation with no enforcement entry — bypassing without notice

In each, the declared set is the governing instrument, the runtime reality is
what it must cover, and the gap between them is invisible until something
external compares the two. The comparison is the check. The requirement that the
comparison be exhaustive is enforcement completeness.

---

## 7. Relationship to Gates

This paper is the check-side complement to CORE-Gate.md.

A Gate and a check are not redundant; they cover orthogonal failure modes. The
Gate covers *the operation was attempted through the guarded path*. The check
covers *an operation exists that reaches the effect through an unguarded path,
or the vocabulary that would catch it is incomplete*.

A Gate guards a door. A check verifies there is only one door — and keeps
verifying as the building changes.

Enforcement is complete only when both hold: every guarded path blocks, and no
unguarded path survives audit.

---

## 8. Non-Goals

This paper does not define:
- the specific Gates (see CORE-Gate.md) or the rules they evaluate
- the ast_gate engine or any individual check's implementation
- the taxonomy format or loader for any specific operation vocabulary
- the remediation behavior of completeness findings
