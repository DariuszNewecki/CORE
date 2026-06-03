# CORE: Roadmap

**Document type:** Strategic paper — sequencing surface
**Location:** `.specs/papers/CORE-Roadmap.md`
**Status:** Authoritative (replaces prior shape 2026-06-03)
**Audience:** Internal — governance, engineering sequencing, commercial planning, investor conversation
**Authority floor:** This document owns sequencing + the single product milestone. Substance (feature definitions, tier definitions, decisions) lives in the canonical surfaces this doc references. When this doc disagrees with the registry, the registry wins.

---

## 1. Purpose

CORE has one named, achievable, definable milestone:

> **Open Base Fully Operational** — the open distribution ships every primitive required to reproduce the full thesis (constitutionally-governed AI code generation with autonomous remediation and full consequence chain), and the three system-quality goals that gate adoption are demonstrably met.

Everything else on the roadmap is sequenced relative to this milestone. Commercial features ship after it — using only the open surfaces it makes load-bearing. Versioning evolves alongside it but is not gated by it (see §5).

This roadmap is **structurally stable** by design: the milestone definition, the commercial-after-milestone ordering, the tier mapping — none of these change as features ship. Only the *status* of items inside changes. When a new feature is added to the registry (constitutional act per `Features.md §1`), the roadmap absorbs it without restructure.

When this doc disagrees with `CORE-Features.md` on feature status, the registry wins. When it disagrees with `CORE-Product-Tiers.md` on tier definitions, Tiers wins. This doc is the navigation surface; substance is canonical elsewhere.

---

## 2. The milestone: Open Base Fully Operational

### 2.1 Definition

The milestone is constitutionally declared by **ADR-085 D5** (mechanical-check exit criteria). When all eight items below show satisfied state, the open base is "fully operational" per the open-core honesty contract (ADR-084 D7 §1).

| Group | Item | Type | "Done" criterion | Status today |
|---|---|---|---|---|
| Feature commitments (5) | F-10 CI/CD gate | registry | `Status: shipping`; PR annotations + merge-blocking demonstrated against external repo | ✅ shipped 2026-06-02 |
| | F-27 Local LLM | registry | `Status: shipping`; capability demonstration per ADR-089 D1 | ✅ shipped 2026-06-03 |
| | F-40 OEM API surface | registry | `Status: shipping`; documented public contract; sidecar attachability proven | ✅ shipped 2026-06-02 |
| | F-41 + F-42 + F-43 extension interfaces | registry | All three `Status: shipping`; one first-party non-code instantiation as plugin-contract proof | ⬜ roadmap |
| | F-48 Open library distribution | registry | `Status: shipping`; `pip install core-runtime` works; semver tags; CI publishes on tag | ✅ shipped 2026-06-02 |
| Quality goals (3) | Docs polish | system property | Outside developer installs + runs the full thesis from public docs alone, without source-tree archaeology | ⬜ not started |
| | Demo reliability | system property | Consequence-chain bootstrap demo runs cleanly on first attempt, three times in a row, from a clean repo clone on a freshly-provisioned machine | ⬜ not started |
| | Signal quality | derived metric | F-19 convergence metric reports resolution rate ≥ creation rate, sustained ≥ 30 days, on this repo | ⬜ not started (F-19 query honesty verification not yet executed) |

**Progress as of 2026-06-03:** 4 of 5 feature commitments closed; 0 of 3 quality goals met. The remaining feature work is the F-41 / F-42 / F-43 extension-interfaces trio (F-41 first, F-42 + F-43 in parallel afterward).

### 2.2 What this milestone is NOT

- **Not "all 33 open-stamped features at shipping."** F-48 closed when the parent gate criterion (pip install + tag + CI publish) was met; F-48 sub-items (F-48.3 Docker/GHCR, F-48.4 public Python surface, F-48.5 semver policy doc) continue as post-milestone polish per the Operational-Completeness tracker §2.4. The milestone is the constitutional definition, not the all-shipping-features definition.
- **Not the v3.0.0 trigger.** Version bumps are governed by public-surface contract change per ADR-088 D5, independent of milestone status. The milestone may land in 2.x; v3.0 ships when public-surface contract changes break, not when the milestone achieves.
- **Not a commercial readiness signal.** Customer signal sequences commercial features (§3); the milestone unblocks them constitutionally but does not predict adoption velocity.

### 2.3 Achieving the milestone

Per ADR-085 D5, achievement is mechanical: each item's "Done" cell evaluates true. The governor authors a follow-on ADR (or amends ADR-085) declaring the constraint relaxed and authorizing commercial engineering work to begin. Until that authoring step, the constraint stays active even if all items appear satisfied — the relaxation is an explicit governance act, not an automatic state transition.

---

## 3. After the milestone — commercial sequencing

Commercial features sit on this roadmap explicitly. They are not omitted, not flattened into "later," and not dated. Each entry below carries one of two structural conditions:

- **Structural-readiness condition:** can ship once the open prerequisites are present (the post-milestone authorized state).
- **Customer-signal condition:** depends on a buyer commitment beyond engineering effort — first regulated customer, first OEM partner, first hosted-tier subscriber.

The first-SKU candidate is **F-44 (Premium rule libraries)** per ADR-083 §Consequences and ADR-084 §Consequences (structural-readiness from independent arguments). The decision belongs to the governor and is not closed; the candidate set is no longer ambiguous.

Sequencing is also constrained by the three commercial-surface shapes (ADR-084 D8). Each shape attaches via a different open contract:

- **Plugin shape** attaches via F-04 loader + F-41/F-42/F-43 extension interfaces + atomic action registry
- **Sidecar shape** attaches via F-40 OEM API surface (open, already shipping)
- **Runtime fork shape** attaches via F-48 published library (open, already shipping)
- **Outside taxonomy:** F-38 (build overlay), F-39 (not software)

### 3.1 Plugin-shape commercial features (3)

| F-ID | Name | Tier | Shape | Ships when |
|---|---|---|---|---|
| F-44 | Premium rule libraries (industry packs) | Audit + | Plugin (rule overlay via F-04 + F-05) | **Structural-ready today** (only commercial feature with all open prerequisites shipping). Lowest-friction first-SKU candidate per ADR-083 / ADR-084. Customer signal: any regulated industry buyer commits to one of GxP / IEC 62304 / EU AI Act / PCI-DSS / SOC 2 pack. |
| F-46 | Cloud audit export (signed) | Solo + | Plugin (atomic action via registry) | Structurally ready (registry shipping); customer signal: any non-regulated buyer wants signed export. |
| F-37 | Regulatory export (GxP / EU AI Act) | Enterprise + | Plugin (atomic action via registry) | Customer signal required: regulated customer signing on (GxP, EU AI Act Article 9, IEC 62304 evidence). Distinct from F-46 — this is the regulator-facing variant. |

### 3.2 Sidecar-shape commercial features (4)

| F-ID | Name | Tier | Shape | Ships when |
|---|---|---|---|---|
| F-45 | Hosted findings dashboard | Audit + | Sidecar (read-side via F-40) | Structurally ready (F-40 shipping); customer signal: any Audit-tier customer wants hosted UI without their own web tier. |
| F-20 | Convergence graph dashboard | Team + | Sidecar (via F-40) | Structurally ready (F-40 shipping, F-19 metric shipping); part of Team-tier package. Ships with first Team customer. |
| F-34 | Web dashboard | Team + | Sidecar (via F-40) | Same as F-20 — Team-tier package. Ships with first Team customer. |
| F-47 | Managed Qdrant | Solo + | Sidecar (degenerate — managed infrastructure, no FastAPI consumption) | Operational: managed-infra repo + hosting commitment. Customer signal: customer wants to skip local Qdrant operation. |

### 3.3 Runtime-fork-shape commercial features (5)

All depend on F-48 published library (shipping) and on Team-tier infrastructure decisions. Ships as one bundle per ADR-084 D4 / D5 (one private repo per shape; runtime-fork repo materialises with first feature).

| F-ID | Name | Tier | Shape | Ships when |
|---|---|---|---|---|
| F-32 | RBAC | Team + | Runtime fork | Structurally ready. Foundation for F-31 (shared consequence chain depends on identity). Ships first within the Team bundle. |
| F-31 | Shared consequence chain (multi-user) | Team + | Runtime fork | Depends on F-32. |
| F-33 | Multi-repository support | Team + | Runtime fork | Independent of F-31/F-32 within the bundle. |
| F-35 | Federated constitution | Enterprise + | Runtime fork | Enterprise-tier requirement (org root + team extensions, no override). |
| F-36 | SSO / SAML / OIDC | Enterprise + | Runtime fork | Enterprise-tier requirement; regulated-industry procurement gate. |

### 3.4 Outside-taxonomy commercial commitments (2)

| F-ID | Name | Tier | Shape | Ships when |
|---|---|---|---|---|
| F-38 | Air-gapped deployment (guaranteed) | Enterprise + | Build overlay (signed image + configuration) | Depends on F-27 (capability — shipping) + F-48.3 (Docker/GHCR). Customer signal: regulated customer requires contractual air-gap guarantee. |
| F-39 | SLA support | Enterprise + | Not software (operational commitment) | Operational commitment; customer signal: any Enterprise contract requiring response-time SLA. |

### 3.5 Open distribution finishing items (post-milestone, not commercial)

F-48 closed at the milestone-gate level; sub-items continue as open distribution polish, not commercial work. Per `CORE-Operational-Completeness.md` §2.4:

| Sub-item | Name | Status | Sequencing |
|---|---|---|---|
| F-48.3 | Docker `core-engine` image + GHCR release workflow | open | Solo install-path enabler; needed before F-38. |
| F-48.4 | Public Python API surface declaration (`__all__`) | recently shipped — **verify status** | Gates F-31/F-32/F-33/F-35/F-36 commercial sidecars per ADR-084 D4; also gates ADR-088 D2 PyPI `Production/Stable` classifier promotion. |
| F-48.5 | Semver policy doc | open | Inherits ADR-088 D5 baseline; documents what `core-runtime` users can rely on. |

(F-48.4 status reconciliation is a known open item — see recon `var/recon-product-state-2026-06-03.md` §C2.)

---

## 4. Tier × feature mapping

The canonical tier x feature mapping is `CORE-Features.md` §5 (registry-authoritative). The canonical tier definitions are `CORE-Product-Tiers.md` §4. This roadmap does not re-declare either.

The relevant view this roadmap adds is: **for each tier, what's available today vs. what's gated behind §2 or §3.**

| Tier | Available today | Adds after milestone | Customer-signal-gated |
|---|---|---|---|
| **Audit** | Stateless audit; default rule library; CI/CD gate (F-10); pre-commit-hooks distribution (F-10.5, bonus) | Premium rule packs (F-44); hosted findings dashboard (F-45) | F-44 with first regulated buyer; F-45 with first Audit-tier hosting customer |
| **Solo** | Full daemon; autonomous remediation; consequence chain; local + external LLM routing; CLI | Cloud audit export (F-46); managed Qdrant (F-47) | F-46 with first non-regulated buyer; F-47 with operational hosting commitment |
| **Team** | None of Team-tier features ship today | F-20 + F-31 + F-32 + F-33 + F-34 (the Team bundle) | First Team customer signing on |
| **Enterprise** | None of Enterprise-tier features ship today | F-35 + F-36 + F-37 + F-38 + F-39 (the Enterprise bundle) | First regulated customer; SLA commitment |
| **Embedded** | F-40 OEM API surface shipping (the contract); OpenAPI spec published | F-40 Phase B (auth, host binding, rate limiting per ADR-087 D8); commercial Embedded engagement | First OEM partner; auth model decided per ADR-087 D8 |

Each tier has a complete and honest answer today. Audit + Solo are deployable as fully open distributions. Team + Enterprise + Embedded are honest pre-commitments — the contract surfaces (F-40, F-48, F-41–F-43) that make them load-bearing exist or are nearing completion.

---

## 5. Versioning relationship

Per ADR-088, `core-runtime` PyPI sits at v2.x and tracks the constitutional repo's narrative release history. Version bumps are governed by **public-surface contract change**, not by milestone or feature status:

- **Patch** (`2.6.0 → 2.6.1`): bug fixes, internal-only refactors, documentation — no surface change.
- **Minor** (`2.6 → 2.7`): additive features, new public symbols, new public routes, new optional response fields.
- **Major** (`2.x → 3.x`): breaking change to the Python public surface (per F-48.4 when defined) **OR** wire-surface major bump per ADR-087 D6 (`/v1/` → `/v2/`).

The milestone (§2) and the version track (this section) evolve independently. Achieving the milestone in 2.x is normal. Crossing to 3.0 requires a breaking-surface trigger, which may happen before, during, or after the milestone. PyPI `Development Status` classifier promotion to `Production/Stable` is gated on F-40 (shipping) + F-48.4 (status pending verification) per ADR-088 D2.

---

## 6. Maintenance discipline

This roadmap is updated under two distinct disciplines:

**Status updates (operational, no ADR required):**
- A feature ships → its "Status today" cell in §2.1 or §3 flips to ✅, with date.
- A quality goal reaches met state → §2.1's "Status today" cell records the date.
- A customer signal arrives that re-orders §3 commercial sequencing → reorder freely; the structural conditions stay.

**Structural updates (constitutional, ADR required):**
- A new F-ID is added to the registry → this roadmap's relevant section absorbs it.
- The milestone definition changes (e.g., ADR-085 D5 amended) → §2.1 follows the amendment.
- A feature's `Sourcing` changes (open ↔ commercial) → governance amendment per Features.md §1; this roadmap reflects the new section placement.
- The three commercial-surface shapes change (ADR-084 D8 amended) → §3 reorganization follows.

The structural stability of the document is itself a discipline: avoid restructure when status updates suffice. The prior `CORE-Roadmap.md` shape drifted because per-tier "what to build next" prose decayed against the registry by ~8 ships in three weeks; this version delegates that prose to the registry to prevent recurrence.

---

## 7. References

- `CORE-Features.md` §3 (feature definitions), §4 (status counts + shape buckets), §5 (tier mapping) — authoritative for feature status, sourcing, and tier inclusion
- `CORE-Product-Tiers.md` §2 (adoption funnel), §3 (non-goals), §4 (tier definitions), §5 (tier comparison) — authoritative for tier-level claims and positioning
- `commercial/CORE-Products.md` — operational view of the open/commercial line; first-SKU candidate set
- `planning/CORE-Operational-Completeness.md` — operational tracker for milestone progress; per-item status + closure verification log
- `planning/CORE-Feature-Dependency-Graph.md` — picture-form of the prerequisite graph; supports §3 structural-readiness conditions
- ADR-083 — stamps F-44/F-45/F-46/F-47 as commercial; first-SKU structural argument for F-44
- ADR-084 — three commercial-surface shapes (D1); interface symmetry (D6); four open-core honesty commitments (D7); shape-bucket reclassification (D8)
- ADR-085 — open-base completeness as engineering's sole goal (D1); exit criteria (D5); the milestone in §2 is this ADR's own framing
- ADR-086 — installation architecture; three distribution channels; tier-install profile mapping
- ADR-087 — OEM API versioning and stability policy; Phase B scope (D8) referenced in §3.2 / §4
- ADR-088 — PyPI version alignment; semver bump rules (D5) referenced in §5
- ADR-089 — F-27 exit criterion amendment; precedent for milestone exit criteria refinement
- `var/recon-product-state-2026-06-03.md` — recon audit that surfaced the drifts this roadmap reshape addresses (B7: prior `CORE-Roadmap.md` stale by 8+ ships)

---

*This roadmap supersedes the prior shape of `CORE-Roadmap.md` (preserved in git history). The reshape is operational, not constitutional: no ADR required because no decision changed. The structural-stability discipline in §6 is the safeguard against the drift that motivated the reshape.*
