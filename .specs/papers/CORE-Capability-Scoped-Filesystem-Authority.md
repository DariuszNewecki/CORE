---
kind: paper
id: CORE-Capability-Scoped-Filesystem-Authority
title: CORE — Capability-Scoped Filesystem Authority
status: canonical
doctrine_tier: constitution
---

<!-- path: .specs/papers/CORE-Capability-Scoped-Filesystem-Authority.md -->

# CORE — Capability-Scoped Filesystem Authority

**Status:** Canonical
**Authority:** Constitution
**Scope:** All filesystem writes in CORE

---

## 1. Purpose

This paper defines how filesystem write authority is granted, scoped, and
enforced in CORE. It establishes three load-bearing principles: a single
chokepoint for every write; capability-scoped least authority over that
chokepoint; and a mode dimension that distinguishes development from live
operation. Together they answer the question *may this code, at this moment,
write this file?* without delegating it to convention, code review, or grep.

---

## 2. Definition

Three principles operate together. A write is permitted only when all three
hold.

**Single chokepoint.** Every filesystem mutation in CORE — content, structure,
or metadata — passes through exactly one interface. Raw `pathlib.Path.write_text`,
`os.replace`, `shutil.move`, `open(w)`, and their kin do not appear in CORE's
source. The chokepoint is structural, not advisory: there is one door, and the
door is the only way out.

**Capability-scoped authority.** The chokepoint's authorization decision is
keyed on the calling *operational capability*, not on the calling module,
layer, or file path. Each capability — `self_healing`,
`audit_report_generation`, `governance_amend_rule`, and so on — declares its
filesystem profile in `.intent/`: which operations on which paths, in which
modes. Anything not declared is forbidden by default.

**Mode dimension.** The chokepoint reads a process-level mode flag —
*development* or *live* — and consults the per-capability profile keyed on
that mode. A capability permitted to write `.intent/` in development may be
flatly denied in live. The same code, the same call site, the same capability
— two modes, two answers.

A write reaches disk only when it traverses the chokepoint, the calling
capability declares the operation, and the current mode permits it.

---

## 3. Constitutional Basis

CORE develops CORE. The governor uses CORE to evolve CORE's own constitution
and specifications. In development this requires write paths into `.intent/`
and `.specs/` — otherwise the system cannot amend itself through itself, and
constitutional change happens by hand outside any audit. In live operation
the same paths must be closed absolutely, because there is no governor in the
loop to authorize them. The same code, in two modes, must obey two different
policies. A static block forbidding `.intent/` writes is too strong for
development; an advisory rule is too weak for live. The mode dimension is
constitutional, not operational convenience.

The failure mode this prevents is sharper in live than in development. A live
deployment of CORE that retains constitutional self-modification authority
allows an LLM-generated proposal to alter the rules that govern it — the
system becomes self-amending without the human in the loop the model assumes.
Denying that authority structurally, at the door, is the only defense that
does not depend on every future capability remembering not to use it.

The choice to scope authority by *capability* rather than by module or layer
follows from the same self-development pressure. CORE's structure changes —
files move, layers reorganize, sanctioned-caller lists drift. A capability is
the stable invariant: `self_healing` means the same thing across refactors;
`src/will/self_healing/handler.py` may not. Authorization tied to capability
identity survives the refactor. Authorization tied to module paths requires
the kind of `scope.excludes` curation that has already produced
silent-incompleteness defects elsewhere in the system, per
CORE-Enforcement-Completeness.md.

---

## 4. The Chokepoint

The chokepoint is the only surface through which writes leave CORE's address
space and become disk state. Its singular character is what makes the rest of
the model meaningful: a policy on the door has no force if the door is not the
only way out. Enforcement of that property — the absence of bypasses — is a
write-perimeter problem, governed by CORE-Enforcement-Completeness.md. Both
the runtime block and the audit-time verification are required.

The chokepoint's job at runtime is exactly the policy decision: given the
inputs *(calling capability, operation, target path, current mode)*, is the
write permitted? It performs no path-rewriting, no implicit buffering, no
content rewriting. It admits or it raises.

---

## 5. Capability-Scoped Least Authority

Authorization is keyed on the *operational capability* under which the write
is happening. An operational capability is a declared, named unit of what
CORE-as-a-system does — distinct from a *cognitive* capability per
CORE-Capability-Taxonomy.md, which describes what an LLM model can do. The
two taxonomies coexist; they answer different questions and live in
different files.

Each operational capability declares, in the operational-capability taxonomy,
its filesystem profile:

- the set of *reads* it requires
- the set of *creates*
- the set of *modifies*
- the set of *deletes*

— each as a list of path patterns, each pattern qualified by the modes in
which it is permitted. Operations absent from the declaration are forbidden
by default. Least authority is therefore a structural property, not a
discipline: a capability has exactly the authority its declaration grants,
and no more.

The capability registry becomes the source of truth for filesystem authority.
Two consequences follow directly:

- *Who can write to path X* is a lookup against capability declarations, not a
  grep across `src/`. The answer is enumerable and attributable.
- Removing a capability automatically revokes its filesystem authority.
  Authorization cannot outlive the feature that justified it.

A capability that needs new authority must declare it. The declaration is a
governance change — visible, reviewable, attributable — not a code change a
review might miss.

---

## 6. The Mode Dimension

The process-level mode flag is set at startup from the environment and is
immutable for the lifetime of the process. There are exactly two values.

**Development.** The governor is in the loop. Capabilities whose profile
permits writes to `.intent/` or `.specs/` in development mode may invoke
them. These writes are mediated — they pass through atomic actions whose
authorization carries a governor token — but they exist. This is the path by
which CORE amends itself through itself.

**Live.** No governor is in the loop. Capabilities permitted to mutate
protected namespaces have their profiles read with development-only entries
elided. A capability whose profile carries no live-mode entry for an
operation is denied by the chokepoint at policy-decision time, with no
override, no emergency bypass, and no per-action exception.

Mode is not a debug flag. It is a constitutional declaration of *who is in
the loop*. A process that cannot prove its mode honestly cannot be
authorized for any privileged write — the default on uncertainty is *live*.

---

## 7. Capability Identity at the Chokepoint

The chokepoint's policy decision requires that it know, with certainty,
which operational capability the write is being made under. Capability
identity is propagated from the entry point to the chokepoint via a
process-scoped context; the atomic-action decorator is the natural place to
set it, because every authorized mutation in CORE already passes through
an atomic action.

A write reaching the chokepoint with no capability context is not a benign
edge case. It is structurally indistinguishable from an unauthorized bypass
that lost provenance along the way. The chokepoint denies it.

---

## 8. Relationship to Other Papers

This paper sits on top of three existing ones. It supersedes none in full,
but it amends CORE-IntentGuard.md §4 in one respect (the `.intent/` floor
block), called out below. Without that amendment the self-amendment path in
§6 is unreachable.

- **CORE-Gate.md** defines Gates as blocking validation points. The
  chokepoint is itself a Gate — the runtime Gate for filesystem authority.
  Its singular nature is what allows it to function as one.
- **CORE-IntentGuard.md** defines the runtime path-and-rule validation
  performed at the chokepoint today. The chokepoint inherits most of its
  constitutional invariants — `var/keys/`, `var/cache/`, absolute paths,
  traversal — as floor-level blocks that hold regardless of capability or
  mode. The `.intent/` entry changes shape: it remains a floor-level block
  in *live* mode, but in *development* mode the block is layered over by
  capability-mediated permissions for governor-approved self-amendment.
  This is a constitutional amendment to IntentGuard.md §4; the dated Note
  marker is placed in IntentGuard.md §4 in the same change-set as this
  paper. `.specs/` enters the chokepoint's scope here for the first time;
  that is an extension, not an amendment.
- **CORE-Enforcement-Completeness.md** governs the write-perimeter property:
  that the chokepoint *is* the perimeter, with no unguarded paths.
  Capability-scoped authority requires that property to hold; its
  enforcement assumes the chokepoint is reachable from no bypass.

This paper deliberately distinguishes itself from **CORE-Capability-Taxonomy.md**,
which defines cognitive capabilities (model abilities for routing). The
operational-capability taxonomy is a separate vocabulary, answering a
different question, written for a different audience.

---

## 9. Non-Goals

This paper does not define:

- the specific operational capabilities CORE has (the inventory grounded in
  this paper)
- the data-model schema for the operational-capability taxonomy YAML
- the mode-flag startup mechanism and its provenance guarantees
- the governor-token machinery that authorizes development-mode privileged
  writes
- the chokepoint's identity-propagation implementation
- the migration path from today's `scope.excludes`-based perimeter to
  capability-keyed authorization

Each of those is the subject of a separate ADR or follow-on paper.
