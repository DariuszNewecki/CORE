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

**This document carries structure. GitHub carries status.** Every item in the milestone (§2.1) and every commercial / post-MVP item (§3) carries a GH issue link. Live state — what's shipped, what's in flight, what's blocked on what — lives in the issues, the labels, and Project #6. The doc does not need an edit when a feature ships; the issue closes and the milestone-progress query reflects it (see §6 Maintenance discipline).

This roadmap is **structurally stable** by design: the milestone definition, the commercial-after-milestone ordering, the tier mapping — none of these change as features ship. Only the *status* of items inside changes, and that lives on GH. When a new feature is added to the registry (constitutional act per `Features.md §1`), the roadmap absorbs it as a structural update (see §6).

When this doc disagrees with `CORE-Features.md` on feature definitions, the registry wins. When it disagrees with `CORE-Product-Tiers.md` on tier definitions, Tiers wins. When it disagrees with GH issue state on what's shipping, GH wins. This doc is the navigation surface; substance is canonical elsewhere.

---

## 2. The milestone: Open Base Fully Operational

### 2.1 Definition

The milestone is constitutionally declared by **ADR-085 D5** (mechanical-check exit criteria). When all eight items below show satisfied state, the open base is "fully operational" per the open-core honesty contract (ADR-084 D7 §1).

**Live status:** `gh issue list --label goal:operational-completeness --state all` (or [GitHub UI query](https://github.com/DariuszNewecki/CORE/issues?q=label%3Agoal%3Aoperational-completeness)). This document carries the *definition* of each milestone item; the linked issues carry their *state*.

| Group | Item | GH issue | "Done" criterion |
|---|---|---|---|
| Feature commitments (5) | F-10 CI/CD gate | [#384](https://github.com/DariuszNewecki/CORE/issues/384) | `Status: shipping`; PR annotations + merge-blocking demonstrated against external repo |
| | F-27 Local LLM | [#401](https://github.com/DariuszNewecki/CORE/issues/401) | `Status: shipping`; capability demonstration per ADR-089 D1 |
| | F-40 OEM API surface | [#414](https://github.com/DariuszNewecki/CORE/issues/414) | `Status: shipping`; documented public contract; sidecar attachability proven |
| | F-41 + F-42 + F-43 extension interfaces | [#415](https://github.com/DariuszNewecki/CORE/issues/415) [#416](https://github.com/DariuszNewecki/CORE/issues/416) [#417](https://github.com/DariuszNewecki/CORE/issues/417) | All three `Status: shipping`; one first-party non-code instantiation as plugin-contract proof |
| | F-48 Open library distribution | [#527](https://github.com/DariuszNewecki/CORE/issues/527) | `Status: shipping`; `pip install core-runtime` works; semver tags; CI publishes on tag |
| Quality goals (3) | Docs polish | [#561](https://github.com/DariuszNewecki/CORE/issues/561) | Outside developer installs + runs the full thesis from public docs alone, without source-tree archaeology |
| | Demo reliability | [#562](https://github.com/DariuszNewecki/CORE/issues/562) | Consequence-chain bootstrap demo runs cleanly on first attempt, three times in a row, from a clean repo clone on a freshly-provisioned machine |
| | Signal quality | [#563](https://github.com/DariuszNewecki/CORE/issues/563) | F-19 convergence metric reports resolution rate ≥ creation rate, sustained ≥ 30 days, on this repo |

Closing each issue records the per-item closure evidence. Constitutional closure of the milestone is a governance act (ADR amendment per ADR-085 D5), not auto-derived from issue state.

### 2.2 What this milestone is NOT

- **Not "all 33 open-stamped features at shipping."** F-48 closure is the parent gate criterion (pip install + tag + CI publish), not the sum of its sub-items. F-48 sub-items (F-48.3 Docker/GHCR, F-48.4 public Python surface, F-48.5 semver policy doc) carry their own GH issues (#539, #540, #541) and ship on their own track per the Operational-Completeness tracker §2.4. The milestone is the constitutional definition, not the all-shipping-features definition.
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

**Live status:** each F-NN has a GH issue; check state via the issue link or `gh issue view <NN>`. This document carries each feature's *structural prerequisites* and *customer-signal condition*; the issue carries the state.

### 3.1 Plugin-shape commercial features (3)

| F-ID | GH | Name | Tier | Structural prerequisites | Customer signal |
|---|---|---|---|---|---|
| F-44 | [#523](https://github.com/DariuszNewecki/CORE/issues/523) | Premium rule libraries (industry packs) | Audit + | F-04 + F-05 (rule overlay attachment surface) | Any regulated industry buyer commits to one of GxP / IEC 62304 / EU AI Act / PCI-DSS / SOC 2 pack. First-SKU candidate per ADR-083 / ADR-084. |
| F-46 | [#525](https://github.com/DariuszNewecki/CORE/issues/525) | Cloud audit export (signed) | Solo + | Atomic action registry | Any non-regulated buyer wants signed audit export |
| F-37 | [#411](https://github.com/DariuszNewecki/CORE/issues/411) | Regulatory export (GxP / EU AI Act) | Enterprise + | Atomic action registry | Regulated customer signing on (GxP, EU AI Act Article 9, IEC 62304 evidence). Distinct from F-46 — regulator-facing variant. |

### 3.2 Sidecar-shape commercial features (4)

| F-ID | GH | Name | Tier | Structural prerequisites | Customer signal |
|---|---|---|---|---|---|
| F-45 | [#524](https://github.com/DariuszNewecki/CORE/issues/524) | Hosted findings dashboard | Audit + | F-40 OEM API surface (read-side) | Audit-tier customer wants hosted UI without their own web tier |
| F-20 | [#394](https://github.com/DariuszNewecki/CORE/issues/394) | Convergence graph dashboard | Team + | F-40 + F-19 convergence metric | First Team customer (part of Team bundle) |
| F-34 | [#408](https://github.com/DariuszNewecki/CORE/issues/408) | Web dashboard | Team + | F-40 OEM API surface | First Team customer (part of Team bundle) |
| F-47 | [#526](https://github.com/DariuszNewecki/CORE/issues/526) | Managed Qdrant | Solo + | Managed-infra repo + hosting commitment (no FastAPI consumption — degenerate sidecar) | Customer wants to skip local Qdrant operation |

### 3.3 Runtime-fork-shape commercial features (5)

All depend on F-48 published library and on Team-tier infrastructure decisions. Ships as one bundle per ADR-084 D4 / D5 (one private repo per shape; runtime-fork repo materialises with first feature).

| F-ID | GH | Name | Tier | Internal sequence | Customer signal |
|---|---|---|---|---|---|
| F-32 | [#406](https://github.com/DariuszNewecki/CORE/issues/406) | RBAC | Team + | First in bundle — identity foundation for F-31 | First Team customer |
| F-31 | [#405](https://github.com/DariuszNewecki/CORE/issues/405) | Shared consequence chain (multi-user) | Team + | After F-32 | First Team customer |
| F-33 | [#407](https://github.com/DariuszNewecki/CORE/issues/407) | Multi-repository support | Team + | Independent within bundle | First Team customer |
| F-35 | [#409](https://github.com/DariuszNewecki/CORE/issues/409) | Federated constitution | Enterprise + | Within Enterprise bundle | First Enterprise customer (org root + team extensions) |
| F-36 | [#410](https://github.com/DariuszNewecki/CORE/issues/410) | SSO / SAML / OIDC | Enterprise + | Within Enterprise bundle | Regulated-industry procurement gate |

### 3.4 Outside-taxonomy commercial commitments (2)

| F-ID | GH | Name | Tier | Structural prerequisites | Customer signal |
|---|---|---|---|---|---|
| F-38 | [#412](https://github.com/DariuszNewecki/CORE/issues/412) | Air-gapped deployment (guaranteed) | Enterprise + | F-27 (capability) + F-48.3 (Docker/GHCR) | Regulated customer requires contractual air-gap guarantee |
| F-39 | [#413](https://github.com/DariuszNewecki/CORE/issues/413) | SLA support | Enterprise + | Operational commitment, not software | Any Enterprise contract requiring response-time SLA |

### 3.5 Open distribution finishing items (post-milestone, not commercial)

F-48 closure is parent-level; sub-items ship on their own track. Per `CORE-Operational-Completeness.md` §2.4:

| Sub-item | GH | Name | Sequencing role |
|---|---|---|---|
| F-48.3 | [#539](https://github.com/DariuszNewecki/CORE/issues/539) | Docker `core-engine` image + GHCR release workflow | Solo install-path enabler; needed before F-38 |
| F-48.4 | [#540](https://github.com/DariuszNewecki/CORE/issues/540) | Public Python API surface declaration (`__all__`) | Closes the gate for F-31/F-32/F-33/F-35/F-36 commercial runtime forks per ADR-084 D4; satisfies ADR-088 D2's gate for PyPI `Production/Stable` classifier promotion (governor decision per the linked ADR — not automatic) |
| F-48.5 | [#541](https://github.com/DariuszNewecki/CORE/issues/541) | Semver policy doc | Inherits ADR-088 D5 baseline; documents what `core-runtime` users can rely on |

---

## 4. Tier × feature mapping

The canonical tier × feature mapping is `CORE-Features.md` §5 (registry-authoritative). The canonical tier definitions are `CORE-Product-Tiers.md` §4. The structural view this roadmap adds is **which feature group belongs to each tier under the milestone frame** (open base vs. commercial extension), not which features happen to be shipping today.

| Tier | Open base (in milestone §2.1) | Commercial extension (in §3) | Phase B / post-MVP |
|---|---|---|---|
| **Audit** | Stateless audit + default rule library + CI/CD gate (F-10) | F-44 premium rule packs (§3.1) + F-45 hosted findings dashboard (§3.2) | F-10.5 pre-commit-hooks (bonus distribution channel) |
| **Solo** | Full daemon + autonomous remediation + consequence chain + LLM routing + CLI | F-46 cloud audit export (§3.1) + F-47 managed Qdrant (§3.2) | F-48.3 Docker/GHCR (§3.5); F-48.5 semver policy doc (§3.5) |
| **Team** | (no open-base-only features at this tier — Team requires shared state) | F-20 + F-31 + F-32 + F-33 + F-34 (Team bundle, §3.2 + §3.3) | — |
| **Enterprise** | (no open-base-only features at this tier) | F-35 + F-36 + F-37 + F-38 + F-39 (Enterprise bundle, §3.1 + §3.3 + §3.4) | — |
| **Embedded** | F-40 OEM API surface + OpenAPI spec + ADR-087 stability policy | (no per-tier commercial features — Embedded is the integration path) | F-40 Phase B per ADR-087 D8 (#554 auth, #555 host binding + rate limiting); commercial Embedded engagement model |

For *live availability* per tier (what's shipping right now), filter the registry: `gh issue list --search "in:title F- label:type:feature is:closed" --limit 100` or read `CORE-Features.md` §5. The doc above carries the *structural* shape of each tier — open base + commercial extension + post-MVP — which is stable as features ship.

---

## 5. Versioning relationship

Per ADR-088, `core-runtime` PyPI sits at v2.x and tracks the constitutional repo's narrative release history. Version bumps are governed by **public-surface contract change**, not by milestone or feature status:

- **Patch** (`2.6.0 → 2.6.1`): bug fixes, internal-only refactors, documentation — no surface change.
- **Minor** (`2.6 → 2.7`): additive features, new public symbols, new public routes, new optional response fields.
- **Major** (`2.x → 3.x`): breaking change to the Python public surface (per F-48.4 when defined) **OR** wire-surface major bump per ADR-087 D6 (`/v1/` → `/v2/`).

The milestone (§2) and the version track (this section) evolve independently. Achieving the milestone in 2.x is normal. Crossing to 3.0 requires a breaking-surface trigger, which may happen before, during, or after the milestone. PyPI `Development Status` classifier promotion to `Production/Stable` is gated on F-40 + F-48.4 closure per ADR-088 D2. Whether both gates are currently met is a live state — check F-40 #414 and F-48.4 #540. When both are closed, the promotion is a governor decision per ADR-088 D2 (not automatic).

---

## 6. Maintenance discipline

This roadmap separates two surfaces by design:

**Status lives on GitHub (no doc edit on ship).**

- A feature ships → its GH issue closes; the `gh issue list --label goal:operational-completeness` query reflects new state automatically.
- A quality goal reaches met state → its GH issue (#561 / #562 / #563) closes with evidence in the closure comment.
- A customer signal arrives → relevant commercial F-NN issue's discussion or labels reflect the signal; no doc edit needed.

**Structure lives in this document (ADR-required updates).**

- A new F-ID is added to the registry → §2.1 (if open-base feature) or §3 (if commercial) absorbs the new row.
- The milestone definition changes (ADR-085 D5 amended) → §2.1 follows the amendment.
- A feature's `Sourcing` changes (open ↔ commercial) → governance amendment per Features.md §1; this roadmap reflects the new section placement.
- The three commercial-surface shapes change (ADR-084 D8 amended) → §3 reorganization follows.

The structural stability of this document is the safeguard against recurrence of the drift that motivated the 2026-06-03 reshape — the prior `CORE-Roadmap.md` carried per-tier "what to build next" prose that decayed against the registry by ~8 ships in three weeks. By delegating status to GH and keeping only structural framing here, the doc no longer needs an edit when a feature ships.

---

## 7. References

- **GitHub queries for live state:**
  - `gh issue list --label goal:operational-completeness --state all` — full milestone item set, open + closed
  - `gh issue list --label goal:operational-completeness --state open` — what remains
  - GH Project #6 ("CORE Roadmap") — kanban view, filterable by Tier / Scope / Shape / Status
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
