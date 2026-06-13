---
kind: paper
id: CORE-Vocabulary-Registers
title: CORE — Vocabulary Registers
status: canonical
doctrine_tier: constitution
---

<!-- path: .specs/papers/CORE-Vocabulary-Registers.md -->

# CORE — Vocabulary Registers

**Status:** Canonical
**Authority:** Constitution
**Scope:** All governed vocabulary in CORE — across `.specs/`, `.intent/`, `src/`, and the operational database

---

## 1. Purpose

CORE's governance vocabulary is read by two audiences:

- **Humans** — reading papers, ADRs, the Constitution, design discussions.
- **Machines** — loading rules, routing findings, validating schemas, executing actions.

These audiences read the same concepts under different conventions. A paper says *"a Rule with Policy authority"*. The corresponding YAML says `authority: policy`. The corresponding Python enum member is `Authority.POLICY`. The corresponding DB column value is `policy`. These are not drifted spellings of one canonical form. They are the same concept rendered in different **registers**, each appropriate to its surface.

This paper names the registers, declares which concept-families belong to which, and establishes the rule that **drift within a register is governance failure**, while **register-appropriate variation across surfaces is correct**.

The motivation is operational. A naive "normalize all casing" pass would corrupt the system: it would replace `ERROR` with `error` in severity fields, breaking every downstream consumer that expects the diagnostic convention; it would replace `Worker` with `worker` in paper prose, making the prose visually noisier and harder to parse; it would replace `policy` with `Policy` in YAML enum values, breaking every loader that expects the operational convention. Register awareness is the precondition for any drift-detection rule.

---

## 2. The three registers

CORE recognizes exactly three vocabulary registers. No fourth register may be introduced without amending this paper.

### 2.1 Conceptual register

**Form:** Title Case for single-word concepts; PascalCase for compound concepts.
**Examples:** `Worker`, `Phase`, `Authority`, `Rule`, `Finding`, `Proposal`, `AtomicAction`, `RemediationMap`, `Sensing Worker`, `ContextPacket`.
**Audience:** Human readers.
**Surfaces:** Papers under `.specs/papers/`, ADRs under `.specs/decisions/`, the Constitution under `.intent/constitution/`, narrative prose anywhere in the repository.
**Function:** The Conceptual register exists to make governance concepts visually distinct from ordinary words in running prose. *"Every Rule has exactly one Authority"* is unambiguous because `Rule` and `Authority` are flagged as concept references, not common nouns.

### 2.2 Operational register

**Form:** `snake_case` lowercase. Identifiers consist of `[a-z][a-z0-9_]*`.
**Examples:** `policy`, `interpret`, `parse`, `audit`, `active`, `paused`, `pending`, `approved`, `safe`, `moderate`, `blocking`, `reporting`.
**Audience:** Machine routing — loaders, schema validators, rule executors, the audit instrument.
**Surfaces:** Enum values in `.intent/META/enums.json`, `authority:` / `phase:` / `status:` / `severity:` field values in YAML and JSON declarations, DB enum values for status-family columns, action_id strings, rule_id strings, capability identifiers.
**Function:** Operational identifiers are routing keys. They are joined, indexed, compared, and dispatched on. The lowercase snake_case form is stable across Python, YAML, JSON, and SQL idioms; it requires no per-language transformation; it is the single form that can be safely used as a primary key.

### 2.3 Diagnostic register

**Form:** `UPPER_CASE`. Identifiers consist of `[A-Z][A-Z0-9_]*`.
**Examples:** `ERROR`, `WARNING`, `INFO`, `CRITICAL`, `DEGRADED`, `PASS`, `FAIL`.
**Audience:** Operators reading severity, verdict, and log-level signals.
**Surfaces:** The `AuditSeverity` enum and its consumers, severity fields on `AuditFinding`, verdict states in `audit_verdict.yaml` and `Final Verdict` panels, log levels in any logger configuration.
**Function:** The Diagnostic register signals **intensity or terminal state**. It exists distinct from the Operational register because severity and verdict states have a long-established cross-system convention (logging frameworks, monitoring systems, alert pipelines) of UPPER_CASE, and CORE inherits that convention rather than fighting it. Using lowercase here would force every downstream consumer — including external systems CORE may integrate with — to translate.

---

## 3. The same-concept invariant

The same governance concept appears in multiple registers. Its form within each register is fixed, and there is a deterministic transformation between forms.

For a concept that exists in all three registers, the canonical forms are:

| Concept | Conceptual | Operational | Diagnostic |
|---|---|---|---|
| Authority level "Policy" | `Policy` | `policy` | — (not a diagnostic concept) |
| Phase "Audit" | `Audit` | `audit` | — |
| Severity "Error" | `Error` (when discussed in prose) | — (severity is not an enum value in `authority:`/`phase:`-style fields) | `ERROR` |
| Verdict "Pass" | `Pass` (in prose) | — | `PASS` |

Not every concept appears in every register. Many concepts appear in only one or two:

- `AtomicAction` appears in the Conceptual register only — it is a concept name, not an enum value or a diagnostic state.
- `safe`, `moderate`, `dangerous` (impact levels) appear in the Operational register only — they are routing keys with no general prose convention or diagnostic counterpart.
- `INFO`, `WARNING` appear in the Diagnostic register only as signals; their Conceptual counterparts (when papers discuss "informational findings") are not capitalized as concepts because "informational" is a common adjective, not a flagged concept name.

The principle: **a concept's presence in a register is a deliberate decision, not automatic.** The decision lives in the canonical store for that register-family.

---

## 4. Drift within a register is governance failure

The same concept may legitimately have different forms across registers. The same concept **may not** have different forms **within** a register. Both rules are enforceable.

### 4.1 Operational drift

A YAML file declaring `authority: Policy` (Title Case) is operational drift — it has imported a Conceptual-register form into an Operational-register field. The downstream loader either crashes (strict matching), silently fails (case-sensitive comparison missing the value), or accepts it under a tolerant comparison and propagates the casing inconsistency further.

A JSON rule declaring `"phase": "AUDIT"` is operational drift — Diagnostic-register form in an Operational-register field.

The rule `vocabulary.register.must_match_family` (declared in `.intent/rules/governance/`) fails the audit when an operational field's value does not match the Operational register's grammar `^[a-z][a-z0-9_]*$`.

### 4.2 Diagnostic drift

A finding declared with `severity: error` (lowercase) is diagnostic drift. The `AuditSeverity` enum's canonical form is UPPER_CASE; the value as written cannot be matched against the enum without a transformation that itself becomes a drift surface.

The same rule applies in the diagnostic direction: severity fields must match `^[A-Z][A-Z0-9_]*$`.

### 4.3 Conceptual drift

A paper writing `"a rule with policy authority"` (lowercase concept names in prose) loses the visual distinctness that Conceptual register exists to provide. This is **soft drift** — the prose remains parseable; only the readability convention is violated.

The Conceptual register is not enforced by a runtime rule. There is no machine-checkable definition of "ordinary noun vs concept reference" without a parser that understands governance semantics. Conceptual register is enforced by review, by the canonical-section grammar of `CORE-Vocabulary.md` (which lists the concepts that belong to the register), and by the convention that ADR templates and paper templates use the Conceptual form.

---

## 5. Register assignments by concept-family

The following table assigns concept-families to their canonical operational register. This is the table the meta-rule reads.

| Concept-family | Operational register form | Surfaces where this register is canonical |
|---|---|---|
| Authority levels (`meta`, `constitution`, `policy`, `code`) | Operational | `authority:` field in any YAML/JSON declaration |
| Phase names (`interpret`, `parse`, `load`, `audit`, `runtime`, `execution`) | Operational | `phase:` field in any YAML/JSON declaration |
| Enforcement strength (`blocking`, `reporting`, `advisory`) | Operational | `strength:` / `enforcement:` field |
| Artifact status (`experimental`, `active`, `deprecated`) | Operational | `status:` field on artifacts under `.intent/` |
| Worker status (`active`, `paused`, `deprecated`) | Operational | `status:` field on worker declarations |
| Proposal status (`draft`, `pending`, `approved`, `executing`, `completed`, `failed`) | Operational | `core.autonomous_proposals.status` DB column |
| Blackboard entry status (`open`, `claimed`, `resolved`, `abandoned`, `deferred_to_proposal`, `dry_run_complete`, `indeterminate`) | Operational | `core.blackboard_entries.status` DB column |
| Worker class (`sensing`, `acting`) | Operational | `class:` field on worker declarations |
| Workflow ordering mode (`single`, `sequential`, `parallel`) | Operational | `ordering:` field on workflow definitions |
| Severity (`ERROR`, `WARNING`, `INFO`) | **Diagnostic** | `severity:` field on findings; `AuditSeverity` enum; logging configurations |
| Audit verdict (`PASS`, `FAIL`, `DEGRADED`) | **Diagnostic** | Verdict panels; `audit_verdict.yaml`; verdict-deciding rule outputs |

When a new concept-family is introduced (a new ADR establishing a new enum-typed value, a new status, a new severity-like signal), the ADR's responsibility is to assign the family to the appropriate register and add a row to this table. A new concept-family lacking a register assignment is itself governance debt.

---

## 6. Relationship to the canonical vocabulary store

This paper governs **how** vocabulary is rendered across surfaces. It does not govern **which terms exist**. That is the job of the canonical stores established under ADR-023 and its companions:

- `.specs/papers/CORE-Vocabulary.md` (canonical section) for governance-ontology terms.
- `.intent/taxonomies/capability_taxonomy.yaml` for capability terms.
- `.intent/META/enums.json` for enum-typed value vocabularies.
- `.intent/enforcement/config/audit_verdict.yaml` for audit verdict vocabulary.

Each canonical store declares its terms in the register appropriate to its surface. `enums.json` declares operational-register values (lowercase). `audit_verdict.yaml` declares diagnostic-register values (UPPER_CASE for severity, UPPER_CASE for verdict states). `CORE-Vocabulary.md` declares conceptual-register names (Title Case / PascalCase). Each store is internally consistent; this paper governs the consistency *between* stores.

A future drift-detection rule that checks "every canonical-store entry uses its register's grammar" can be added under `.intent/rules/governance/` once this paper is in place. It is not part of this paper.

---

## 7. Non-goals

This paper does **not**:

- Mandate a fourth register. The three are sufficient for current governance surfaces. Future additions go through ADR.
- Govern non-vocabulary text (paper section headers, code comments, log message prose). Those are not vocabulary; they are explanation.
- Force renaming of existing free-form prose. Conceptual drift in prose is soft; the rule is reviewer-enforced, not machine-enforced.
- Substitute for the canonical-store mechanism. Knowing the register doesn't tell you whether a term exists; that's still the canonical store's job.

---

## 8. References

- `.intent/constitution/CORE-CONSTITUTION.md` Article I §5 (introduces this paper as the doctrinal source for register discipline)
- `.intent/META/enums.json` (operational-register canonical store for enum-typed values)
- `.intent/enforcement/config/audit_verdict.yaml` (diagnostic-register canonical store for verdict semantics)
- `.specs/papers/CORE-Vocabulary.md` (conceptual-register canonical store for governance-ontology terms)
- `.specs/decisions/ADR-023-vocabulary-canonical-store.md` (the broader pattern this paper extends)

---

## 9. Amendment

Changes to the three-register definition or to the register-assignment table in §5 require an ADR. Changes to non-substantive prose (clarifications, examples) may be made by direct commit with a clear commit message.
