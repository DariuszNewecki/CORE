<!-- path: .specs/papers/CORE-ConstitutionalCoherenceChecker.md -->

# CORE — Constitutional Coherence Checker

**Status:** Canonical
**Authority:** Constitution-level
**Scope:** Coherence of constitutional documents — ADRs, rule domains, northstar
**Operationalizes:** UR-07 (Defensibility is Non-Negotiable) — primary; UR-06 (Continuous Constitutional Governance) — secondary

---

## 1. Purpose

This paper defines the Constitutional Coherence Checker (CCC): an instrument
that evaluates the internal soundness of CORE's governing documents.

CORE audits `src/` against `.intent/`. Nothing audits `.intent/` against itself
or against `.specs/northstar/`. The constitution is currently trusted by
assumption, not by proof. This paper closes that gap.

### 1.1 Grounding in northstar

The CCC operationalizes **UR-07 (Defensibility is Non-Negotiable)** as primary
grounding. UR-07 requires that every output CORE produces be traceable to a
stated requirement. Traceability terminates in contradiction when the
constitution itself is incoherent — UR-X says one thing, paper says another,
rule says a third. Defensibility is broken at the constitutional layer before
any source-code output is even produced. The CCC is the instrument that
prevents that breakage by checking the constitutional layer against itself.

Secondary grounding is **UR-06 (Continuous Constitutional Governance)**:
governance applies from the first commit, every commit thereafter, and to
every artifact in the governance graph — including the governance graph itself.
There is no exempt layer where coherence may drift. The CCC is the
operational mechanism by which UR-06 reaches the constitutional layer.

UR-03 (Gap and Contradiction Reporting) is intentionally **not** cited as
grounding. UR-03's scope is gaps and contradictions in stated user intent —
input the system is asked to act on. The CCC's scope is gaps and
contradictions in CORE's own governing documents. Related discipline, distinct
operationalization.

---

## 2. Problem Statement

Constitutional debt accumulates silently. Examples of the failure modes this
instrument targets:

- Two ADRs declare incompatible requirements without referencing each other.
- A rule's enforcement behaviour has drifted from its governing ADR's
  specification.
- A northstar requirement has no corresponding rule enforcement.
- A rule exists with no traceable connection to any northstar requirement.
- A new ADR was authored after an older paper was written and invalidates
  one of that paper's assumptions without declaring it.
- Two ADRs address the same governance concern from different angles and have
  never been reconciled.

None of these defects are visible to `core-admin code audit`, which evaluates
`src/` against declared rules. They require a separate instrument that reads
the constitutional layer against itself.

---

## 3. Instrument Design

The CCC evaluates four coherence relations across three input domains.

### 3.1 Input Domains

| Domain | Source |
|---|---|
| ADRs | `.specs/decisions/ADR-*.md` |
| Rule domains | `.intent/rules/` (all rule declaration files) |
| Northstar documents | `.specs/northstar/` |

Papers in `.specs/papers/` are secondary inputs: consulted as context when
evaluating ADR or rule coherence, not enumerated as primary targets. Any paper
explicitly referenced by an ADR is included in the evaluation of that ADR.

### 3.2 Coherence Relations Evaluated

**R1 — ADR-vs-ADR**
Does ADR-X declare a requirement incompatible with ADR-Y? Does ADR-X amend
or supersede ADR-Y implicitly without declaring it? Do two ADRs address the
same governance concern without cross-referencing?

**R2 — Rule-vs-northstar**
Is every rule domain traceable to at least one northstar requirement? Does any
northstar requirement have no corresponding rule enforcement?

**R3 — Rule-vs-ADR**
Does every rule domain have a governing ADR? Does every architectural decision
recorded in an ADR have a corresponding rule enforcement? Has a rule's
enforcement behaviour drifted from its ADR's specification?

**R4 — Cross-document drift**
Has a document authored before a given ADR had its assumptions invalidated by
that ADR? Is any named concept, component, or principle referenced in one
document absent, renamed, or retired in the documents it depends on?

---

## 4. LLM Posture

Using an LLM to produce verdicts on the constitution would invert the trust
hierarchy: the governed would be judging the governor. This is prohibited.

The CCC assigns the LLM exactly one role: **candidate-finder**.

The LLM:

- receives a structured prompt containing two or more constitutional documents,
- produces a list of candidate contradictions, gaps, or drift observations,
- assigns a brief rationale to each candidate,
- does NOT assign enforcement verdicts,
- does NOT propose constitutional amendments,
- does NOT score or rank candidates as real vs. false.

Each candidate is a claim of the form:

> "ADR-031 and ADR-008 may conflict on the scope of path enforcement — ADR-031
> applies the regex to all runtime dir references, while ADR-008 scopes impact
> enforcement to declared action metadata only."

The claim is a question for the human, not an answer. The LLM's output has no
enforcement power.

The human (governor):

- reviews every candidate produced in a run,
- marks each as: **confirmed**, **dismissed**, or **deferred**,
- authors constitutional amendment proposals for confirmed findings,
- closes the run only when every candidate carries a triage status.

A run with untriaged candidates is not complete.

---

## 5. Coverage Model

Completeness is a first-class property of the CCC. A coherence run that
evaluated only some ADRs is not a coherence run — it is a partial scan with
unknown residual risk.

Every CCC run MUST produce a **coverage manifest**: an enumeration of every
input item evaluated, with a status of `checked` or `skipped`. A `skipped`
item requires an explicit rationale. Items skipped without rationale constitute
a coverage gap and MUST be surfaced as findings in the run report.

Coverage obligations per domain:

| Domain | Coverage requirement |
|---|---|
| ADRs | Every file matching `.specs/decisions/ADR-*.md` |
| Rule domains | Every file in `.intent/rules/` |
| Northstar documents | Every file in `.specs/northstar/` |

The coverage manifest is part of the Constitutional Coherence Report and is
not separable from it.

---

## 6. Human Approval Posture

The CCC produces candidates. Only the governor decides which candidates are
real findings.

The triage workflow:

1. A CCC run completes and produces a Constitutional Coherence Report (CCR).
2. The governor reviews the CCR in full.
3. For each candidate, the governor records a triage decision:
   - **Confirmed** — a real constitutional defect; triggers an amendment proposal.
   - **Dismissed** — a false positive; governor records the rationale.
   - **Deferred** — real enough to track but not immediately actionable;
     becomes a parked issue.
4. Confirmed findings are addressed through the existing constitutional amendment
   mechanism. The governor authors the amendment; CORE does not.
5. The run is closed when every candidate has a triage decision.

No autonomous proposal may be created directly from a CCC candidate. The
governance pathway from candidate to resolved defect runs through the governor.

---

## 7. Output: Constitutional Coherence Report

Each CCC run produces one CCR. The CCR is persistent and queryable, separate
from the standard audit verdict.

### 7.1 CCR Structure

| Field | Content |
|---|---|
| `run_id` | UUID assigned at run start |
| `run_at` | ISO 8601 timestamp |
| `input_manifest` | Enumeration of every input item with `checked`/`skipped` status |
| `candidates` | Ordered list of LLM-produced candidate findings |
| `triage_status` | Per-candidate governor decision (unreviewed/confirmed/dismissed/deferred) |
| `run_status` | `open` (untriaged candidates remain) or `closed` (all triaged) |

### 7.2 Candidate Record Structure

| Field | Content |
|---|---|
| `candidate_id` | UUID |
| `relation` | One of R1/R2/R3/R4 (coherence relation violated) |
| `documents` | List of document paths implicated |
| `claim` | LLM-produced natural-language candidate claim |
| `rationale` | LLM-produced supporting observation |
| `triage_decision` | Governor-assigned: unreviewed / confirmed / dismissed / deferred |
| `triage_note` | Governor-authored rationale (required for dismissed) |

### 7.3 Storage

The CCR is stored persistently in the CORE database. The run is also emitted
as a machine-readable report file alongside existing audit reports. The CCR
does not appear in the standard `core-admin code audit` output; it is
accessible via a dedicated command (`core-admin coherence report`).

---

## 8. Relationship to Existing Instruments

### 8.1 CoherenceSensorWorker (ADR-027)

`CoherenceSensorWorker` detects sensor-fixer incoherence in the autonomous
remediation loop: a proposal executed successfully but the violation persists.
Its scope is runtime execution coherence.

The CCC's scope is constitutional document coherence. These instruments share
a name component but are entirely separate in purpose, input, schedule,
storage, and trust posture.

### 8.2 Standard Audit (`core-admin code audit`)

The standard audit evaluates `src/` against `.intent/` rules. It does not read
`.intent/` rules against each other, against ADRs, or against the northstar.
The CCC is the instrument for that evaluation.

The standard audit verdict and the CCR run status are independent. A system
may hold a clean audit verdict while carrying unresolved constitutional
candidates, and vice versa.

### 8.3 CORE-Constitution-Read-Only-Contract

The CCC is a read-only instrument. It reads constitutional documents; it writes
no constitutional documents. The governor authors any amendments that confirmed
findings require. This paper is a direct implementation of the read-only
contract.

### 8.4 CORE-Rule-Conflict-Semantics

When the CCC identifies a candidate ADR-vs-ADR or rule-vs-rule conflict (R1,
R3), that candidate is evaluated against the conflict semantics defined in
CORE-Rule-Conflict-Semantics.md if and when the governor confirms it. A
confirmed rule conflict is a governance error per that paper and must be
resolved at the source, not through runtime compensation.

### 8.5 URS Verifier (`.specs/papers/CORE-URS-Verifier.md`, ADR-094)

The URS Verifier is the fourth coherence-family instrument, verifying whether
CORE's runtime state honors the claims its URSs make. The instrument is
sensor-shaped, deterministic, and uses no LLM in its verdict path.

CCC and the URS Verifier are complementary. CCC asks "do constitutional
documents agree with each other?" — its candidate generation is LLM-assisted
and confirmation is governor-driven. The URS Verifier asks "do URSs'
acceptance claims hold against current runtime state?" — its verdicts are
deterministic per criterion. Both surface findings to the governor; neither
acts autonomously. (Amendment added per `CORE-URS-Verifier.md` §12.1.)

---

## 9. Scheduling and Trigger Conditions

The CCC is not a continuously-running worker. It is invoked:

- manually by the governor (`core-admin coherence check`),
- automatically when the ADR count increases (a new ADR was authored),
- automatically when any file in `.specs/northstar/` changes.

A CCC run triggered by a new ADR evaluates the new ADR against all existing
ADRs (R1) and against all rule domains (R3) at minimum. Full-corpus re-runs
are at governor discretion.

The instrument does not run on every audit cycle. Constitutional documents
change infrequently; the cost of a full LLM-assisted scan is not justified at
the frequency of `src/` audits.

---

## 10. Non-Goals

This paper does not define:

- the schema for CCR database tables (ADR scope),
- the LLM prompt templates used for candidate generation (ADR scope),
- the remediation strategy for confirmed constitutional defects (governed by
  the existing amendment mechanism),
- scoring or ranking of candidate severity (the governor triages; no
  automated scoring is permitted),
- any automatic enforcement action derived from a CCR candidate.

---

## 11. ADR Requirement

No implementation of the Constitutional Coherence Checker may begin before an
ADR is authored and accepted that specifies:

- the storage schema for CCR records and candidate records,
- the CLI surface (`core-admin coherence`),
- the LLM invocation model (prompt structure, batching strategy, failure
  handling),
- the scheduling triggers and their integration with the daemon,
- the relationship between CCR run status and any governance dashboard signal.

This paper defines the instrument. The ADR codifies the implementation
decisions.

---

## 12. Amendment Discipline

This paper may be amended only by explicit constitutional replacement, in
accordance with the CORE amendment mechanism.

---

## 13. Closing Statement

CORE enforces what is declared. If what is declared is unsound, enforcement
is unsound.

The Constitutional Coherence Checker exists so that the constitution is
verified, not merely assumed.
