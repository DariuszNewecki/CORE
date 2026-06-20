---
kind: paper
id: CORE-BYOR
title: CORE-BYOR
status: draft
doctrine_tier: foundational
---

<!-- path: .specs/papers/CORE-BYOR.md -->

# CORE-BYOR — The Domain-General Adoption Surface

**Status:** Draft — proposed for ratification (2026-06-17)
**Authority:** Policy
**Scope:** What BYOR is, as the surface through which any external system adopts CORE governance; why it is parametrized by *Repository type*, not bound to code; and why the first paid instance is regulatory gap-analysis (GRC).
**Operationalizes:** UR-01 (Universal Input Acceptance) — primary; UR-04 (Constitution Before Artifact) — secondary.
**Provenance:** Drafted downstream of the 2026-06-17 northstar obligation-layer parametrization (commit `57379c9d`), which generalized the binding requirement from software to *any artifact*, code being the first instance. A governor↔Claude design review then set the commercial direction (GRC gap-analysis as the first paid wedge) and stress-tested the framing. This paper records both so the direction is reconciled-against, not re-derived.

---

## 1. Purpose

BYOR ("Bring Your Own Repository") is **CORE's adoption surface**: the boundary
at which an external system places itself under constitutional governance.

The historical reading was narrow — "onboard a *code* repository." UR-01 now
forbids that narrowing: CORE accepts *any artifact*, and a **Repository** is a
*domain-typed artifact corpus*, code being the first type. BYOR is therefore not
a code feature. It is the general front door; which *kind* of repository walks
through it is a parameter, not a fork.

This paper defines that surface, fixes its boundary against a sibling surface
(§4), states what varies by domain (§5), separates its two maturity axes (§6),
and names its first paid instance (§7). It decides *shape*; mechanisms are
deferred to the ADRs §9 grounds.

## 2. The invariant operation — establish, then maintain

Strip the domain away and one operation remains. CORE governs a pair:

- **Intent** — the prescriptive law: a constitution, a regulation, a
  requirements set. *What the system must obey.*
- **Artifact** — the descriptive corpus (the Repository): code, procedures,
  records. *What actually exists.*

CORE's job over that pair has two modes:

- **Establish** `Artifact ⊨ Intent` — bring the pair into conformance (author or
  induce the law; generate the artifact).
- **Maintain** `Artifact ⊨ Intent` — keep it conformant continuously: detect
  every drift with evidence, drive remediation under authority.

Adoption is **not a moment, it is an entry into a lifelong loop** (UR-06: no line
between build and maintain). A Repository moves between modes over its life — a
new feature is *established*, a legacy module's intent is *induced*, a new
regulation triggers re-*maintenance*. This is the same loop CORE already runs on
itself (`.intent/` is the Intent, `src/` is the Artifact); BYOR is that loop
pointed outward.

**Domain is orthogonal.** Code, business process, and regulated-industry
compliance are not three operations — three *artifact types* feeding one. Code is
the type CORE governs end-to-end today (§10); the rest are reachable because the
rules engine "makes no assumption about artifact type" (`CORE-Features.md`).

## 3. The Repository — the single parametrization seam

The one thing that varies by domain is the **Repository**, and the word marks the
seam: a software engineer hears *git source tree*; a governance librarian hears
*controlled library of records*. Both are native; neither is wrong. CORE treats a
Repository as:

> **Repository = an artifact corpus + the typed sensor that enumerates,
> reads, and classifies it.**

This is the open extension contract CORE already shipped:

- **F-41 (artifact-type registry)** — what kind of thing each artifact is. The
  Repository's *type system*.
- **F-42 (pluggable sensor)** — reads a corpus of that type. Its *reader*.
- **F-43 (pluggable action)** — produces/remediates artifacts of that type. Its
  *writer*.

A code Repository binds {git + AST sensors + code actions}. A governance
Repository binds {a records library + document sensors + control-drafting
actions}. Everything above the Repository is invariant. **Parametrize the
Repository and the rest is already general.**

## 4. Configurations, and the BYOR boundary

A would-be adopter arrives holding some of the (Intent, Artifact) pair. Which part
is present determines the entry:

| Path | Codename | Adopter brings | Lacks | Mode | Operation | Surface |
|---|---|---|---|---|---|---|
| 1 | **Scout** | Code repo | Intent | establish | Induction: LLM reads source → candidate rules → human ratifies → delivery | **BYOR** (`project onboard` + `project scout`) |
| 2 | **Guard** | Code repo + `.intent/` | — | maintain | Ongoing audit; gap-analysis of artifact against law | **BYOR** (`code audit --offline`) |
| 3 | **Generate** | Intent (URS, prose) | Artifact | establish | Generate the artifact; dialogue to close gaps | `project new` (sibling) |
| 4 | **Counsel** | Document corpus | Regulation-as-Intent | maintain | Gap-analysis of corpus against regulatory requirements | **BYOR** (T5b — forthcoming) |

**Naming boundary (resolved).** "Bring Your Own *Repository*" presupposes a
corpus exists. So BYOR proper is the three configurations where the adopter brings
an existing Repository — **Scout** (code, no constitution), **Guard** (code +
constitution), and **Counsel** (document corpus + regulatory law). The **Generate**
configuration has no corpus yet; CORE *creates* it. That is the adjacent
greenfield surface (`project new`) — the *same conformance engine*, not BYOR.
Keeping them distinct avoids the category error of calling a from-scratch build
"bring your own." One engine, four configurations, two named entry surfaces
(BYOR and `project new`). The GRC path (Counsel) is confirmed as BYOR Path 4 —
it shares the same Repository abstraction (F-41/F-42/F-43); the artifact type
changes from code to document corpus, the governance loop is structurally
identical (ADR-119 D1).

## 5. Domain parameters (the genuine asymmetries)

"No difference between code and compliance" holds at the *operation* level. The
real differences are **parameters of the one engine**, not different engines —
which is itself the proof of generality. Three must be configured per Repository
type:

1. **Intent provenance.** For code, the constitution may be *authored* or
   *induced-then-ratified*. For regulation, Intent is **retrieved from an
   authoritative external corpus and never induced** — you do not derive a
   regulation from someone's procedures; that inverts authority. (This is exactly
   why legacy `byor.py`'s "analyze the code, generate the law" model is wrong,
   §8.)

2. **Verification trust model — and where CORE's value actually sits.** Code
   conformance is largely *deterministic* (AST/glob/runtime gates) — CORE's
   high-assurance core. Moving to process/regulatory domains, conformance splits:
   the **traceability/completeness skeleton** (every requirement mapped to a
   control, every record present, every approval signed) *stays deterministic* —
   and that skeleton is most of what compliance is. But requirement-*satisfaction*
   ("does this control actually meet this clause?") is irreducibly **semantic** →
   `llm_gate` + human attestation. So CORE's transferable edge in non-code domains
   is **not** the deterministic verdict — it is the **defensible, attested
   evidence trail**: every finding labelled *proven*, *judged*, or *attested*
   (`CORE-Instrument-Attestation`). Selling a deterministic verdict CORE cannot
   produce would violate the Final Invariant in the very market it courts.

3. **Remediation autonomy ceiling.** In code, remediation writes a file. In a
   process/regulatory domain it can only *draft a control or SOP revision for
   human adoption* — CORE cannot change what an organization actually does
   (`CORE-Features.md`: "for other artifact types, the execution edge would
   produce a different change"). Higher artifact types carry a lower autonomy
   ceiling and a mandatory human-in-the-loop.

**The hard part, named.** Parameter 1's "retrieve and represent the Intent" is
not a small config knob — turning prose regulation into checkable Intent is the
core RegTech problem and is likely the gating effort for the first non-code
Repository. This paper names it as such rather than burying it.

## 6. Two maturity axes — why code and GRC do not compete

CORE matures along two *independent* axes, and conflating them is the source of
the "finish the engine vs. get customers" false dilemma:

- **Autonomy** — how much of the loop runs without human hands. Proven first on
  the code Repository (A1→A5; the self-build "final exam"). This is the axis
  that is *not yet finished*.
- **Reach** — how many Repository types the one engine governs. Code is type #1,
  end-to-end. New domains arrive as new artifact-type/sensor/action triples
  against the open F-41/F-42/F-43 contract — a new *Reach* point, not a new
  engine.

The key consequence: **a non-code domain can be served at the *low* end of the
Autonomy axis** (assisted gap-analysis + evidence, human-ratified) using the
*mature* part of the engine — while the code Repository continues climbing
Autonomy on its own track. The unfinished half (full autonomy) is exactly the
half a regulated customer neither needs nor wants. The two axes do not contend
for the same maturity.

## 7. The first paid instance — GRC gap-analysis

The first commercial Repository type is a **governance/records library**, and the
first configuration sold is **Gap-analysis** (§4) — the lowest-effort,
highest-credibility wedge:

- It needs no generation, no induction, no autonomy: retrieve the cited
  requirements → map them to the customer's SOPs/controls → emit a traceability
  matrix + gap report + defensible evidence trail. It stresses the engine least
  and shows the value most.
- It is chosen deliberately over "another programming language" because it
  **forces all three §5 parameters to be honoured** — retrieved-not-induced
  Intent, semantic+attestation verification, human-ratified remediation. If the
  engine survives that, generality is demonstrated, not asserted.

**Honesty guardrail (binding).** CORE-for-GRC is sold as an *assisted,
evidence-trailed gap-analysis engine with honest per-finding attestation* —
**never** as autonomous or deterministic compliance. In a regulated market the
attestation honesty *is* the product: auditors distrust black-box AI; "here is
exactly what I proved versus what needs your sign-off" is the moat. Overstating
it fails the Final Invariant precisely where it matters most.

**Residual build (honest scope).** The engine is reused; the domain layer is
net-new: a *document/records Repository adapter* (F-41/F-42 for documents, not
code AST) and *regulation→checkable-Intent representation* (§5, the hard part).
This is a domain adapter on a mature core — a far smaller bet than building a
governance engine — but it is not "point and sell."

**Commercial center of gravity (governor decision, recorded here).** The
near-term commercial focus is GRC; code self-development drops to a maintenance
track (autonomous upkeep + governor-directed feature work, including building the
GRC adapter). This is permitted by the northstar (regulated environments; "any
artifact-producing system") and does not require a law change; it is recorded as
the deliberate direction.

## 8. Relationship to existing decisions

- **ADR-108 + ADR-119 (Scout — Path 1).** The Scout configuration induces a fitted
  constitution: first `project onboard` delivers the machinery floor; then
  `project scout` runs LLM analysis of the target's source, proposes candidate
  rules in CORE's enforcement vocabulary, and requires human ratification before
  delivery. `examples/starter-intent/` is the illustrative reference and
  LLM-unavailable fallback — its four-rule set is the menu when no LLM is
  available, not the default output. ADR-119 D3 is the canonical form of what
  ADR-111 D2 anticipated as "explicitly-labelled, non-authoritative suggestion
  for the human to consider" — with mandatory ratification making it law.
- **ADR-075 (framework/project namespace).** A BYOR deployment is `framework`
  (CORE's machinery floor) + `project::<external>` (the adopter's authored law).
  The Repository carries the project layer; the floor is shared.
- **ADR-090 (F-41 as unified contract).** Its "commercial BYOR **multi-language**"
  framing widens to **multi-domain**. A regulatory corpus is a Repository *type*,
  not merely another language.
- **`byor.py` / #640.** The *code × Induce* cell. Frozen, not patched: broken
  (dead template path; crashes even in `--dry-run`), heuristically hollow on real
  repos, and philosophically inverted (generates law from the artifact). Its
  correct form is "deliver the ADR-108 starter into a code Repository," to be
  built once this shape is ratified.

## 9. What this paper decides, and what it grounds

**Decides (the shape):** BYOR is the existing-corpus adoption surface over a typed
Repository; the Repository is the single parametrization seam; the operation is
invariant across domains; the three §5 parameters are how a domain is *configured*
rather than re-engineered; code climbs Autonomy while GRC monetizes Reach at low
autonomy; GRC gap-analysis is the first paid cell, sold under the honesty
guardrail.

**Grounds (future ADRs, separate change-sets):**
1. The **Repository adapter interface** — the concrete F-41/F-42/F-43 binding.
2. **Scout — the code × Induce cell (ADR-119, ratified 2026-06-20).** Machinery
   floor delivery (`project onboard`) + LLM-assisted rule induction with mandatory
   human ratification (`project scout`). Closes #640 step 1; defines the two-phase
   model and the reference grammar constraint (CORE's `.intent/` is vocabulary, not
   template).
3. The **document/records Repository type** + **regulation→Intent representation**
   — the GRC second domain (Counsel / Path 4).
4. **Per-finding attestation** (proven / judged / attested) as a first-class
   evidence-trail field — the honesty guardrail made mechanical.

## 10. Non-goals and honesty

- **Code is the only artifact type CORE governs end-to-end today.** Non-code
  Repository types are roadmap. Nothing here licenses claiming, in user-facing
  surfaces, that CORE governs SOPs or regulations before that cell is built and
  verified (UR-07).
- BYOR is **not** multi-repository governance (F-33, shared state across many
  repos) — an orthogonal commercial axis. BYOR onboards one Repository.
- BYOR is **not** the commercial rule packs (E-44); those layer curated law on
  top of an already-adopted Repository.

## 11. References

- `CORE-USER-REQUIREMENTS.md` — UR-01 (Repository defined domain-typed), UR-04,
  UR-03, UR-05, UR-07.
- `CORE-Features.md` — "law over any artifact-producing process"; code as the
  first artifact type; F-41/F-42/F-43 as the extension seam.
- ADR-108 — external adoption ships a minimal authored starter, not a copy.
- ADR-075 — framework/project namespace split (`project::<external>`).
- ADR-090 — F-41 artifact-type registry as the unified governance contract.
- `CORE-Instrument-Attestation.md` — proven/judged/attested honesty of the
  evidence trail (load-bearing for §5 parameter 2 and §7's guardrail).
- #640 — the code × Induce first cell (frozen pending this reframe).
