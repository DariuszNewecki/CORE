# CORE Autonomy Ladder

The CORE Autonomy Ladder defines how far the system can safely act on its own.
It is not a marketing concept — it is an engineering and governance model.

Each level represents a **quantifiable capability** that exists today or is planned, and every step is gated by constitutional controls.

The ladder ensures one principle:

> **CORE may become more autonomous, but never less governed.**

---

## Overview of the Ladder

| Level | Name                       | Description                                             | Status      |
| ----- | -------------------------- | ------------------------------------------------------- | ----------- |
| A0    | Static System              | Manual development only                                 | **Past**    |
| A1    | Governed Generation        | AI generates code in crates, audited before integration | **Current** |
| A2    | Intent-Aware Agents        | Agents reason using Mind rules during generation        | **Planned** |
| A3    | Governed Refactorer        | CORE proposes structural improvements through crates    | **Planned** |
| A4    | Self-Evolving Constitution | Agents propose constitutional changes, humans approve   | **Vision**  |

---

## A0 — Static System (Historical Baseline)

### What defines A0:

* No autonomous generation
* No agents
* No crate lifecycle
* No Knowledge Graph
* Minimal or no governance

A0 existed only in the earliest experimentation phase — before the Mind–Body–Will architecture.

---

## A1 — Governed Generation (Current Level)

A1 is **where CORE stands today**.
It supports safe, governed AI-assisted development.

### Capabilities:

* Crate creation from natural-language intent
* Autonomous coding and test generation inside crates
* Validation pipeline (Black, Ruff, Pytest, syntax checks)
* Full constitutional audits over generated changes
* Accept/reject workflow
* Introspection, knowledge sync, drift detection
* Self-healing (IDs, docstrings, headers, style, import rules)

### Guarantees:

* Agents cannot modify files directly — only through crates
* Mind audits everything before changes reach the codebase
* No changes merge unless compliant with `.intent/`
* Humans remain in full control of final integration

A1 forms the foundation for safe, incremental autonomy.

---

## A2 — Intent-Aware Agents (Planned)

In A2, CORE becomes significantly more intelligent — **not more dangerous**.

Agents still cannot bypass the Mind or modify code directly.
But they will:

### Capabilities to be added:

* Use `.intent/` rules as active constraints, not passive filters
* Read capability metadata from the Knowledge Graph
* Reason about architectural boundaries during generation
* Produce plans aligned with system domains
* Make more accurate and consistent code suggestions

### Guarantees:

* Constitutional Auditor still has veto power
* All changes still happen through crates
* No autonomous modification outside governed pathways

A2 is about **guided intelligence**.

---

## A3 — Governed Refactorer (Planned)

A3 introduces autonomous, *but governed*, refactoring.

### Future capabilities:

* Propose structural improvements via crates
* Identify drift or anti-patterns and recommend fixes
* Generate safe transforms for large or complex code areas
* Use semantic understanding from the Knowledge Graph
* Assist in organizing capabilities, domains, or symbols

### Guarantees:

* Refactors never bypass audits
* All changes are explicit, contextual, and inspectable
* Proposals remain small, bounded, reversible

A3 produces a system that can help maintain itself.

---

## A4 — Self-Evolving Constitution (Vision)

A4 is CORE’s **long-term North Star**.

The idea is not autonomy without limits — it is **governance with machine assistance**.

### Vision:

* Agents identify when constitutional rules need adaptation
* Propose amendments to `.intent/`
* Humans review, sign, and approve
* Canary validation ensures the new rules do not break CORE

### Guarantees:

* Mind always has human oversight
* Agents cannot self-ratify any constitutional change
* Evolution remains safe, traceable, and reversible

A4 is not the system governing itself — it is the system helping humans govern it.

---

## Why the Autonomy Ladder Matters

1. Prevents accidental overreach
2. Ensures transparency in capability growth
3. Gives developers a precise mental model
4. Makes limitations explicit
5. Aligns code, docs, and governance

CORE evolves only when the Mind allows it.
Autonomy never exceeds governance.

---

## Next Steps

Continue with:

* [Context & Comparisons](06-context-and-comparisons.md)
* [Worked Example](07-worked-example.md)
* [Governance](03_GOVERNANCE.md)

Or return to the root:
📘 [Home](../index.md)
