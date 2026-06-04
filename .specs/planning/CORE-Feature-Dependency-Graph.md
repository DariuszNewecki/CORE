# CORE — Feature Dependency Graph

**Status:** Authoritative (visualization of `CORE-Features.md` + ADR-084 D8)
**Location:** `.specs/planning/CORE-Feature-Dependency-Graph.md`
**Audience:** Internal — sequencing, commercial planning, sprint scoping
**Last updated:** 2026-06-04 (post-F-10/F-40/F-48 ship coherence pass; Track column drops ship-state per §5)

---

## 1. Purpose

This document is the picture-form of the roadmap. The structured data lives in `.specs/papers/CORE-Features.md` (the registry) and in GitHub Project #6 ("CORE Roadmap", queryable by Tier / Scope / Shape / Status). What this file adds is the *shape* — which open prerequisites unblock which commercial features, and how the three commercial-surface shapes (ADR-084 D1) cluster.

When the Mermaid graph here disagrees with the registry, the registry wins. This is a derived artifact; the registry is authoritative.

---

## 2. The dependency picture

```mermaid
graph TD
  classDef shipping fill:#90ee90,stroke:#2e7d32,color:#000
  classDef openRoadmap fill:#ffd966,stroke:#bf9000,color:#000
  classDef pluginIface fill:#a4c2f4,stroke:#1c4587,color:#000
  classDef plugin fill:#9fc5e8,stroke:#0b5394,color:#000
  classDef sidecar fill:#b4a7d6,stroke:#351c75,color:#000
  classDef fork fill:#ea9999,stroke:#990000,color:#000
  classDef overlay fill:#d9d9d9,stroke:#666666,color:#000

  subgraph shipping ["Open base — shipping"]
    F01["F-01 Rule engine #375"]
    F04["F-04 .intent loader #378"]
    F05["F-05 Default rules #379"]
    F09["F-09 Finding persistence #383"]
    F10["F-10 CI/CD gate #384"]
    F19["F-19 Convergence metric #393"]
    F25["F-25 Vector indexing #399"]
    F40["F-40 OEM API surface #414"]
    F48["F-48 Open library<br/>distribution #527"]
  end

  subgraph openRoadmap ["Open roadmap — prerequisites for commercial"]
    F41["F-41 Artifact registry #415"]
    F42["F-42 Pluggable sensor #416"]
    F43["F-43 Pluggable action #417"]
  end

  subgraph plugins ["Commercial — Plugin shape (ADR-084 D2)"]
    F37["F-37 Regulatory export #411"]
    F44["F-44 Premium rule packs #523<br/><b>unblocked — first SKU</b>"]
    F46["F-46 Cloud audit export #525"]
  end

  subgraph sidecars ["Commercial — Sidecar shape (ADR-084 D3)"]
    F20["F-20 Convergence dashboard #394"]
    F34["F-34 Web dashboard #408"]
    F45["F-45 Hosted findings #524"]
    F47["F-47 Managed Qdrant #526"]
  end

  subgraph forks ["Commercial — Runtime fork shape (ADR-084 D4)"]
    F31["F-31 Shared chain #405"]
    F32["F-32 RBAC #406"]
    F33["F-33 Multi-repo #407"]
    F35["F-35 Federated constitution #409"]
    F36["F-36 SSO #410"]
  end

  subgraph carveouts ["Outside three-shape taxonomy"]
    F38["F-38 Air-gap guarantee #412<br/>(build overlay)"]
    F39["F-39 SLA support #413<br/>(not software)"]
  end

  F09 --> F10
  F09 --> F40
  F01 --> F41
  F41 --> F42
  F41 --> F43

  F04 --> F44
  F05 --> F44
  F43 --> F37
  F43 --> F46

  F40 --> F20
  F40 --> F34
  F40 --> F45
  F25 --> F47
  F10 --> F45
  F19 --> F20

  F48 --> F31
  F48 --> F32
  F48 --> F33
  F48 --> F35
  F48 --> F36
  F31 -.-> F32
  F32 -.-> F36

  class F01,F04,F05,F09,F10,F19,F25,F40,F48 shipping
  class F41,F42,F43 pluginIface
  class F37,F44,F46 plugin
  class F20,F34,F45,F47 sidecar
  class F31,F32,F33,F35,F36 fork
  class F38,F39 overlay
```

Edge legend: solid arrow = hard dependency (`blocked by`); dashed arrow = soft dependency (likely sequencing but not architecturally required).

---

## 3. Sequencing implications

The graph makes the open/commercial sequencing constraint structural rather than aspirational. Four observations follow directly from the picture:

**A. Most commercial features now have all-shipping open dependencies.** With F-10, F-40, and F-48 all shipped (2026-06-02), the commercial features F-20, F-34, F-44, F-45, F-47, and the F-31–F-36 runtime-fork cluster are no longer dependency-blocked. Only F-37 and F-46 (both blocked by F-43) still wait on a roadmap item. ADR-083 designated F-44 as the first-SKU candidate when F-44 was uniquely unblocked; that uniqueness no longer holds, but ADR-083's strategic argument for sequencing the rule-pack SKU first remains.

**B. F-40 unblocked four commercial features at once.** Shipping F-40 (2026-06-02) released F-20, F-34, F-45, and F-47 simultaneously to commercial work. ADR-084 D3 codified the elevation from "Embedded tier preparation" (Tiers paper §3.5 pre-ADR-084) to single-largest commercial unblocker.

**C. F-43 unblocks two commercial features.** Plus the plugin shape becomes available to third-party authors at the same moment, which is the F-41/F-42/F-43 trio's stated purpose. The trio is now the last remaining open-side dependency gate for any commercial feature.

**D. F-48 shipped (2026-06-02) — runtime-fork cluster no longer gated.** Open library distribution (PyPI + Docker registry, issue #527) was the shared open-infrastructure prerequisite for all five runtime-fork commercial features (F-31, F-32, F-33, F-35, F-36); that gate is now lifted. *Previously this was a planning gap (the graph had to invent a "PYPI" pseudo-node); ADR-084 §Consequences flagged it for filing.*

---

## 4. Per-feature dependency table

The structured version of the graph. Use this for filtering and for generating the GitHub Project #6 `Blocked by` field.

Track is sourcing (open vs commercial), not ship-state — current ship-state lives in `CORE-Operational-Completeness.md` §1 and on GitHub Project #6 per §5.

| F-ID | Issue | Shape | Track | Hard `blocked by` | Notes |
|---|---|---|---|---|---|
| F-10 | #384 | engine | open | none | top-of-funnel, ships independently |
| F-20 | #394 | sidecar | commercial | F-40, F-19 (F-19 ships) | dashboard rendering the convergence metric |
| F-31 | #405 | runtime fork | commercial | F-48 | multi-user state model |
| F-32 | #406 | runtime fork | commercial | F-48; soft on F-31 | authority model change |
| F-33 | #407 | runtime fork | commercial | F-48 | daemon architecture change |
| F-34 | #408 | sidecar | commercial | F-40 | full web governance UI |
| F-35 | #409 | runtime fork | commercial | F-48 | constitution loader change |
| F-36 | #410 | runtime fork | commercial | F-48; soft on F-32 | identity model change |
| F-37 | #411 | plugin | commercial | F-43 | regulatory export atomic action |
| F-38 | #412 | build overlay | commercial (outside taxonomy) | signed image infra | not really a "feature" |
| F-39 | #413 | not software | commercial (outside taxonomy) | n/a | support contract |
| F-40 | #414 | sidecar-interface | open | F-09 (ships) | OEM API surface — unblocks 4 commercial sidecars |
| F-41 | #415 | plugin-interface | open | F-01 (ships) | artifact type registry |
| F-42 | #416 | plugin-interface | open | F-41 | pluggable sensor model |
| F-43 | #417 | plugin-interface | open | F-41 | pluggable action model |
| F-44 | #523 | plugin | commercial | none (F-04, F-05 ship) | **unblocked — first-SKU candidate** |
| F-45 | #524 | sidecar | commercial | F-40, F-10 | Audit-tier polish surface |
| F-46 | #525 | plugin | commercial | F-43 | non-regulated audit export |
| F-47 | #526 | sidecar | commercial | none materially (F-25 ships) | managed infrastructure, not application code |
| F-48 | #527 | engine | open | none | unblocks all 5 runtime-fork commercial features |

---

## 5. What this document is NOT

- **Not a project tracker.** Status, priority, and assignee live on the GitHub issues and Project #6. This document carries the dependency *structure*, which changes slowly (shape buckets are constitutional per ADR-084 D7) and benefits from being plain text in the repo.
- **Not the canonical feature definition.** Each F-ID's authoritative definition lives in `papers/CORE-Features.md` §3. The notes here are abbreviations.
- **Not commercial strategy.** The commercial sequencing (which SKU ships first, pricing, GTM) lives in `commercial/CORE-Products.md` and is private. This file contains the *dependency facts*, not the commercial decisions.

When a new commercial feature is stamped (per the ADR-083 pattern), update this graph in the same change-set so the picture stays current. ADR-084 D6 (interface symmetry) means every new commercial feature has a well-defined `blocked by` open prerequisite — the new edge is always derivable from the stamping ADR.

---

## 6. References

- `papers/CORE-Features.md` §3 (feature definitions) and §4.1 (shape buckets per ADR-084 D8)
- `papers/CORE-Product-Tiers.md` §3 (tier-to-feature mapping) and §3.5 (F-40's elevated structural role)
- ADR-083 — stamps F-44–F-47
- ADR-084 — three-shape taxonomy + open-core honesty contract
- GitHub Project #6 "CORE Roadmap" — queryable surface (Tier, Scope, Shape, Status custom fields)
- `planning/CORE-GitHub-Project-Management.md` — operational governance of the Project board
- `planning/CORE-A3-plan.md` — band-level milestone planning
