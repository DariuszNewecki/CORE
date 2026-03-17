<!-- path: .intent/papers/CORE-Context-Packet-Doctrine.md -->

# CORE: Context Packet Doctrine

**Status:** Draft
**Authority:** Constitution

---

## 1. Purpose

A Context Packet is the **minimal evidence set required to evaluate Rules at a specific Phase**.

Context packets exist so that agents, workflows, and CLI operations can act **without introducing implicit assumptions**.

---

## 2. Constitutional Basis

This doctrine derives from the CORE primitives:

* **Document** – persisted artifact CORE may load
* **Rule** – atomic normative statement
* **Phase** – moment of rule evaluation
* **Authority** – source of decision legitimacy

A Context Packet must therefore expose the **documents, rules, phase, and evidence** required for deterministic rule evaluation.

---

## 3. Definition

A **Context Packet** is a structured document representing the **legally sufficient situation model** required for action inside CORE.

It contains:

* the governing rules
* the relevant documents
* the current phase
* the evidence required to evaluate rules

---

## 4. Context Packet Structure

A valid Context Packet contains the following sections:

```
ContextPacket
├── header
├── phase
├── constitution
├── policy
├── constraints
├── evidence
├── runtime
└── provenance
```

### header

Metadata describing the packet.

### phase

The CORE Phase in which rule evaluation occurs.

### constitution

Rules with **Authority = Constitution**.

### policy

Rules with **Authority = Policy**.

### constraints

Subset of rules relevant to the current action.

### evidence

Documents and data required for rule evaluation.

### runtime

Current system state relevant to the phase.

### provenance

Trace describing how the packet was constructed.

---

## 5. Evidence Sources

Evidence may originate from multiple providers, including:

* source code analysis
* database state
* semantic search
* runtime inspection

Providers are **implementation details** and are not constitutional primitives.

---

## 6. Determinism Requirement

A Context Packet is valid only if all included Rules can be **deterministically evaluated at the declared Phase**.

If a rule cannot be evaluated with the provided evidence, the packet is incomplete.

---

## 7. Non-Goals

Context packets must **not introduce new primitives**.

Specifically they must not define:

* taxonomies
* registries
* indexes
* implicit rule interpretation

These violate the CORE constitutional model.

---

## 8. Summary

A Context Packet is **not an information bundle**.

It is the **evaluation input required for lawful action within CORE**.

Agents operating under CORE must reason from Context Packets rather than from implicit assumptions.
