<!-- path: .specs/decisions/ADR-083-commercial-add-on-stamping-f44-f47.md -->

> **Note (2026-06-06, per ADR-093 D3 + D6):** F-44, F-45, F-46 references in this ADR's body now point at E-44, E-45, E-46 (the Extension class, attaching via published interfaces). F-47 remains F-NN (managed-infrastructure shape, does not attach via published API per F-40.4 verification). Body text preserved verbatim per ADR-074 D13 + ADR-080 §D5 append-only discipline. The filename, title, and historical commit references retain their original "F-44–F-47" form for archaeological continuity.

# ADR-083 — Stamping Tier 1/2 commercial add-ons as F-44–F-47

**Date:** 2026-06-02
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-02 — drafted under Path A execute-verb authorization, "can you help me with implementing your suggestions" + answered scoping questions selecting "ADR first, then docs" and "the four Tiers.md names")
**Grounding papers:** `papers/CORE-Product-Tiers.md` §3.1 and §3.2 (which name these four add-ons informally as "future commercial add-ons not yet enumerated as features"); `papers/CORE-Features.md` §1 (constitutional commitment that open/commercial line is amendment-only) and §4 (canonical sourcing tally).
**Related:** ADR-052 (`core.llm_resources` per-resource provider model — sets the precedent for "infrastructure-as-service" commercial wrapping that F-47 follows); Tiers paper §5 (tier × feature matrix this ADR's stampings join); Products doc §"Open-core boundary" (descriptive recital of the 32/11 split this ADR moves to 32/15).

---

## Context

### The hedge that Tiers.md leaves open

`CORE-Product-Tiers.md` §3.1 and §3.2 contain two parallel passages of identical structure:

> *Revenue model: Open-source core. Future commercial add-ons (not yet enumerated as features in `CORE-Features.md`): premium rule libraries; hosted findings dashboard. These are monetisation mechanics under consideration; they will get F-IDs and `Sourcing: commercial` stamps when they crystallise into committed roadmap.*

And for Solo:

> *Revenue model: Open-source. Future commercial add-ons (not yet enumerated as features in `CORE-Features.md`): cloud audit export; managed Qdrant. These are monetisation mechanics under consideration; they will get F-IDs and `Sourcing: commercial` stamps when they crystallise into committed roadmap.*

Four named candidates, no F-IDs, no commitment. The hedge is honest but is now creating drag: the Products doc carries an open "GOVERNOR decisions still open" line asking which commercial unit ships first, and no answer is possible against a list of unstamped candidates. Stamping is the gate between strategic intent and committed roadmap.

### Why now, and why these four specifically

The four were derived from the tier architecture, not from market signal — they exist because the Audit and Solo tiers each surface a natural commercial polish surface that does not weaken the open base:

- **Audit tier surface 1 — rule library.** F-05 (default rule library) is the constitutional content shipped open. Industry-specific rule packs (GxP, IEC 62304, EU AI Act Article 9, PCI-DSS, etc.) are domain expertise, not engine code. Selling domain expertise is the simplest commercial form available — no software boundary required, no UI investment, monetises authorship rather than execution.
- **Audit tier surface 2 — findings rendering.** F-09 (audit finding persistence) ships open as DB rows. A hosted UI rendering those findings (for customers who installed the Audit CI gate but do not want to host a web tier themselves) is pure polish: the value is the rendering and hosting, not the data.
- **Solo tier surface 1 — audit export.** Distinct from F-37 (Regulatory export, Enterprise-tier, full consequence chain formatted for GxP / EU AI Act submission). F-46 is the simpler thing: cryptographically signed audit-findings export for non-regulated buyers who want a portable artifact without provisioning the full consequence-chain pipeline.
- **Solo tier surface 2 — managed Qdrant.** Solo's open distribution requires the operator to run Postgres and Qdrant locally via Docker Compose. The Postgres burden is unavoidable (the Blackboard is the system of record); the Qdrant burden is lighter (vector store, not authority), and a managed-service version removes the largest friction in the Solo demo without removing the demo.

The fifth candidate (worker-health-monitoring polish surface, splitting F-24 the way F-19/F-20 split convergence) was offered in scoping and explicitly deferred — Tiers.md does not name it. Stamping discipline says: ship what the strategic paper already names, do not infer beyond it.

### The F-19/F-20 split is the structural precedent

F-19 (Convergence metric, open, primitive) and F-20 (Convergence graph dashboard, commercial, primitive) are the same data viewed two ways. The data is constitutionally open; the polished surface is commercial. This is the only existing instance of the split in the registry, and it is the model the four new stampings replicate:

- F-05 (open rule library) ↔ F-44 (commercial premium rule packs) — same shape, content tier vs free tier.
- F-09 (open finding persistence) ↔ F-45 (commercial hosted dashboard) — same shape, data vs polished surface. Same shape as F-19/F-20 at a different granularity.
- F-09 (open finding persistence) ↔ F-46 (commercial signed audit export) — same shape, raw vs delivery format.
- F-25 (open vector indexing) ↔ F-47 (commercial managed Qdrant) — infrastructure variant, same data semantics.

In each pair the open primitive is untouched. This is structurally important: the commercial line grows by addition, never by reclassification. Features §1's constitutional commitment ("weakening any `open` stamp is a governance amendment, not a product decision") is honored by construction.

### What this ADR does NOT decide

- It does not decide the order of commercial delivery. The Products doc question "which SKU first" remains open and is a separate decision — though the Consequences section below records the structural reasoning that points at F-44 as the lowest-friction first deliverable.
- It does not stamp the Worker-health-monitoring polish candidate. Tiers.md does not name it; stamping it would be the kind of "infer beyond what the strategic paper says" pattern this ADR exists to avoid.
- It does not change the tier × feature assignment philosophy. F-44 attaches at Audit+; F-45 attaches at Audit+; F-46 attaches at Solo+; F-47 attaches at Solo+ — each at the tier where the underlying primitive first exists.

---

## Decisions

### D1 — Stamp F-44, F-45, F-46, F-47 with `Sourcing: commercial`, `Status: roadmap`

The four features named in Tiers.md §3.1 and §3.2 enter the registry as committed commercial roadmap. Definitions follow.

| ID | Name | Scope | Tier attachment | Extension of |
|---|---|---|---|---|
| F-44 | Premium rule libraries (industry packs) | source-code instantiation | Audit+ | F-05 |
| F-45 | Hosted findings dashboard | source-code instantiation | Audit+ | F-09 |
| F-46 | Cloud audit export (signed) | source-code instantiation | Solo+ | F-09 |
| F-47 | Managed Qdrant | primitive | Solo+ | F-25 |

F-47 is `primitive` because vector-store hosting is artifact-agnostic; F-44/F-45/F-46 are `source-code instantiation` because the rule packs and finding renderings they extend are scoped to source code today (and will inherit non-code extensions when F-41–F-43 land).

### D2 — F-44 definition: Premium rule libraries (industry packs)

Curated rule packs targeting regulated-industry compliance domains. Initial candidates: GxP, IEC 62304 (medical device software), EU AI Act Article 9 (risk management), PCI-DSS, SOC 2. Each pack is a complete `.intent/rules/` overlay that drops alongside the default library (F-05) and adds domain-specific constitutional checks. Distributed under commercial license, not MIT. Versioned and supported.

The pack content is not part of the open distribution; the engine that loads it (F-01) is. A customer can author their own equivalent packs against the open engine — this feature monetises authorship, not capability.

### D3 — F-45 definition: Hosted findings dashboard

A cloud-hosted web UI rendering audit findings (F-09) for Audit-tier customers who installed the CI gate (F-10) but do not run a daemon, database, or web tier locally. Read-only view: rule, file, severity, message, history across PR runs. Per-organisation deployment with SSO.

Distinct from F-20 (Convergence graph dashboard, Team+, full convergence metric over time). F-45 renders point-in-time findings from stateless audit runs; F-20 renders the full convergence trajectory from a stateful Blackboard. They are not the same surface and do not overlap.

### D4 — F-46 definition: Cloud audit export (signed)

Structured, cryptographically signed export of audit findings (and, where Solo+ stateful operation is in use, the surrounding proposal context) for customers who need a portable evidence artifact but do not need the full Enterprise-grade regulatory submission package.

Distinct from F-37 (Regulatory export, Enterprise+, full consequence chain formatted for GxP / EU AI Act submission). F-46 is a simpler artifact aimed at non-regulated buyers: it is *evidence of audit*, not *evidence of governed change*. The two coexist; F-46 is the cheaper deliverable and the path to first commercial revenue from Solo-tier installations.

### D5 — F-47 definition: Managed Qdrant

Managed hosting of the vector store layer (F-25 collections — `core-code`, `core-docs`, etc.) on infrastructure operated by the commercial product line. Solo customers point their daemon at the managed endpoint via a configuration switch; all governance semantics remain identical.

Provided primarily to remove infrastructure friction from the Solo demo for non-regulated customers. Regulated and air-gapped deployments (F-38) cannot use this and continue to self-host; that's explicit, not a gap.

### D6 — The F-19/F-20 split is the canonical commercial-extension pattern

Future commercial features that extend a shipping open primitive MUST take the same shape: the primitive stays open, the polished/hosted/curated surface is a new feature stamped `commercial`. Reclassifying an existing `open` stamp is foreclosed by Features §1 and reaffirmed here. The four stampings in D1 each satisfy this constraint.

Operationally: when a future Tiers.md addition or Products.md proposal names a commercial surface, the ADR that stamps it MUST identify which shipping open primitive(s) it extends and confirm the primitive is unchanged. An ADR that cannot point to that primitive is proposing a standalone commercial feature — also valid (F-20 itself is roadmap-only, not an extension of a shipping open feature) — but the open/commercial relationship must be explicit either way.

### D7 — Open-stamp claw-back remains constitutionally prohibited

This ADR adds four `commercial` stamps. It does not touch any existing `open` stamp. Features §1 is reaffirmed verbatim: weakening an `open` stamp is a governance amendment, not a product decision, and the MIT-licensed open distribution forecloses retroactive claw-back regardless. The tally moves from 32 open / 11 commercial to 32 open / 15 commercial.

---

## Consequences

### Tally update and document touch-list

Three documents carry the 32/11 tally and must update to 32/15:

1. `papers/CORE-Features.md` §4 ("Sourcing split") and §4 status table (new rows for F-44–F-47).
2. `papers/CORE-Features.md` §5 (tier × feature mapping table — new rows).
3. `commercial/CORE-Products.md` §"Open-core boundary" (paragraph recites the tally verbatim).

`papers/CORE-Product-Tiers.md` §3.1 and §3.2 are updated to replace the "not yet enumerated as features" hedge with F-ID references and removed-hedge language. §5 of Tiers is unchanged because it tracks only the headline capabilities; the four new add-ons are tier-decoration features, not headline tier capabilities.

The Products doc §"GOVERNOR decisions still open" list remains accurate — this ADR stamps the commercial line items but does not decide which one ships first.

### First-SKU implication (structural reasoning, not a decision)

Of the four, F-44 (Premium rule libraries) has the lowest delivery cost: no UI work, no hosted infrastructure, no signing pipeline. It monetises domain expertise (which CORE's governance positioning already implicitly markets) rather than software (which would require either a hosted runtime or a paid binary). It is also the most defensible against open-source forking — a competitor can fork the engine, but cannot reproduce industry-specific rule authorship without doing the regulatory research themselves.

This is the structural argument for F-44 as the first commercial deliverable. It is not the decision; the decision belongs in a separate ADR or in the Products doc once the governor closes the open question.

### What this changes about future commercial extensions

D6 sets the rule: new commercial features that extend a shipping open primitive get stamped without touching the primitive. This makes future stamping ADRs structurally short — the question shrinks to "which primitive does this extend, and what is the polished surface."

The fifth candidate from scoping (Worker-health-monitoring-pro splitting F-24) would fit this template cleanly when and if Tiers.md adds it. The ADR for that addition would cite this one as the pattern precedent and the same four-section structure would apply.

### No backward-compatibility risk

Stamping new commercial features does not affect any shipping open feature, any existing customer (there are no commercial customers yet), or any code path. The audit engine, daemon, CLI, and consequence chain operate identically. The only observable change is in three strategic documents.

### Open question this ADR does NOT close

Products doc §"GOVERNOR decisions still open" asks:

> *Whether the first commercial unit is hosted (Team-tier dashboard SaaS), a license (Enterprise on-prem), or a service (regulated onboarding + governance authoring).*

With the four stampings in D1, that question now has concrete candidates to pick from rather than a list of categories. The decision itself — which of F-20 / F-37 / F-44 / F-45 / F-46 / F-47 is the first commercial SKU — remains the governor's, and is not in scope for this ADR.

---

## Verification

- `papers/CORE-Features.md` §4 carries new rows F-44 through F-47 with `Sourcing: commercial`, `Status: roadmap`. Sourcing tally line reads "Open: 32 | Commercial: 15".
- `papers/CORE-Features.md` §5 tier × feature mapping includes rows for F-44 (Audit/Solo/Team/Enterprise/Embedded all marked), F-45 (same), F-46 (Solo+), F-47 (Solo+).
- `papers/CORE-Product-Tiers.md` §3.1 and §3.2 no longer carry "not yet enumerated as features" language; the four references are replaced by F-ID citations.
- `commercial/CORE-Products.md` §"Open-core boundary" paragraph reads "32 open / 15 commercial" (or equivalent restatement).
- `grep -c 'Sourcing: commercial' .specs/papers/CORE-Features.md` returns 15.
- `grep -c 'Sourcing: open' .specs/papers/CORE-Features.md` returns 32.
- No `Sourcing: open` line was removed in this change; verified by diff of `papers/CORE-Features.md` against the prior commit.

---

## References

- `papers/CORE-Product-Tiers.md` §3.1 and §3.2 — the two parallel passages naming the four add-ons as "future commercial add-ons not yet enumerated."
- `papers/CORE-Features.md` §1 — constitutional commitment that the open/commercial line is amendment-only; the foundation for D7.
- `papers/CORE-Features.md` §4 — the sourcing tally line this ADR updates; F-19/F-20 split visible here as the precedent for D6.
- `commercial/CORE-Products.md` §"Open-core boundary" — descriptive recital of the 32/11 split.
- ADR-052 — `core.llm_resources` per-resource model; the precedent for "infrastructure-as-service" commercial wrapping that F-47 follows in shape.
- Memory `feedback_two_surface_requires_two_structures` — why F-44 (rule pack content) and F-45 (hosted UI surface) are two features, not one "commercial Audit add-on."
- Memory `feedback_deferred_scope_must_be_filed_before_authoring` — the fifth candidate (Worker-health-monitoring-pro) was explicitly deferred during scoping rather than silently dropped.
