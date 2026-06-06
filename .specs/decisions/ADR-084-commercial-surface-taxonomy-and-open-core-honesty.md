<!-- path: .specs/decisions/ADR-084-commercial-surface-taxonomy-and-open-core-honesty.md -->

> **Note (2026-06-06, per ADR-093 D3 + D6):** F-20, F-34, F-37, F-44, F-45, F-46 references in this ADR's body now point at E-20, E-34, E-37, E-44, E-45, E-46 (the Extension class, attaching via published interfaces). F-31/F-32/F-33/F-35/F-36 (runtime-fork engine-shape), F-38 (build overlay), F-39 (not software), F-47 (managed infrastructure) remain F-NN. Body text preserved verbatim per ADR-074 D13 + ADR-080 §D5 append-only discipline. The §D8 commercial-surface shape buckets still describe the correct architectural truth — only the namespace prefix on the bucket members has changed.

# ADR-084 — Commercial-surface taxonomy, add-on architecture, and the open-core honesty contract

**Date:** 2026-06-02
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-02 — drafted under Path A execute-verb authorization, "yes, draft ADR-084" after a multi-turn architectural discussion that surfaced the add-on framing)
**Grounding papers:** `papers/CORE-Features.md` §1 (the open/commercial line as constitutional commitment) and §3.11 (the extension interfaces F-41–F-43 as plugin APIs); `commercial/CORE-Products.md` §"Open-core boundary" (the descriptive line, including the explicit Enforceability note that "Structural boundary planned via separate repo for the commercial codebase"); `papers/CORE-Product-Tiers.md` §3 (the tier architecture this ADR translates into a structural shape).
**Related:** ADR-083 (the stamping ADR this one structurally generalizes — D6 of ADR-083 named the F-19/F-20 split as the canonical extension pattern; this ADR widens that to three shapes and adds the symmetry, honesty, and repo-topology consequences); ADR-052 (`core.llm_resources` per-resource provider model — the precedent for the sidecar shape); F-40 OEM API surface (which is the plugin-interface contract this ADR makes structurally load-bearing).
**Supersedes (partial):** The "Repo topology — overlay vs. separate `CORE-enterprise/` repo" item in `commercial/CORE-Products.md` §"GOVERNOR decisions still open." That decision is absorbed into D6 of this ADR and removed from the open-questions list.

---

## Context

### The architectural question behind "private repo or not"

ADR-083 stamped four commercial features (F-44–F-47) and codified the F-19/F-20 split as the canonical commercial-extension pattern. The natural follow-on question — *where does commercial code live and under what license* — is listed in Products.md §"GOVERNOR decisions still open" as the unresolved "Repo topology" item.

Approached directly, the question framings are all suboptimal:

- **Overlay (one mega-repo with private subdirectories)** breaks the MIT licensing of the open base.
- **Single private `CORE-enterprise/` repo** is the canonical open-core shape, but it answers "where does the code live" without answering "what shape does the code take." Without the shape decision, the repo becomes a junk drawer.
- **Doing nothing** lets the MIT license on the open repo silently absorb commercial code by accident — a permanent license-correctness problem (Products.md §Enforceability).

The right reframing came mid-session: *most* commercial features are already structurally add-ons because the open repo built F-41 / F-42 / F-43 (pluggable extension interfaces) and F-40 (OEM API surface) for exactly this purpose. The repo topology decision is therefore *downstream* of a more primary architectural decision: **what is the structural shape of a commercial feature on top of CORE?**

### Three shapes emerge from the registry

Cataloguing the eleven previously-stamped commercial features (F-20, F-31–F-40) plus the four new ones (F-44–F-47), three structural shapes recur:

**Shape 1 — Plugin.** Attaches to the open engine through an open extension interface. No private engine hook; the plugin uses only APIs a third party could use. Examples: F-44 (rule packs via `.intent/rules/` overlay loader F-04), F-46 (signed audit export via pluggable action interface F-43), F-37 (regulatory export, same shape as F-46 with richer formatting).

**Shape 2 — Sidecar service.** Standalone service that consumes the open repo's public APIs (F-40 OEM API surface) and renders, exports, or operates on the open state externally. Does not run inside the open daemon. Examples: F-20 (convergence dashboard reading the open Blackboard via API), F-34 (web dashboard, same), F-45 (hosted findings dashboard), F-47 (managed Qdrant — degenerate sidecar: managed infrastructure with no commercial code at all).

**Shape 3 — Runtime fork.** Separate distribution that depends on the open codebase as a published library and changes the runtime's authority/state model. Cannot fit as a plugin or sidecar because the change is structural — it touches every authority decision, not a discrete extension point. Examples: F-31 (shared consequence chain — single-user→multi-user state change), F-32 (RBAC — authority model), F-33 (multi-repo — daemon architecture), F-35 (federated constitution — constitution loader), F-36 (SSO — identity model).

A handful of features do not fit cleanly and are noted in Consequences: F-38 (air-gap guarantee — partly build/deployment, not really a plugin or service), F-39 (SLA support — not software at all), F-40 (the OEM API surface IS the plugin-shape interface by definition).

### Why this matters more than the repo question

The shape decision determines:

- **What license boundaries are needed.** Plugins and sidecars sit at API boundaries; runtime forks sit at library boundaries.
- **How many private repos exist.** One per shape (plugin-repo for atomic-action plugins and rule packs; sidecar-repo per service; fork-repo per runtime variant) is structurally cleaner than one private mega-repo.
- **What public APIs must be stable.** Plugin shape requires F-41/F-42/F-43 + atomic-action registry as published contracts. Sidecar shape requires F-40 OEM API surface. Runtime fork shape requires PyPI-published packages of the open codebase.
- **Whether the "open core" claim is honest.** Plugin and sidecar shapes are interchangeable with third-party plugins/sidecars built against the same APIs. Runtime fork shape is interchangeable with anyone else's runtime fork built against the same library. The open base is genuinely a substrate, not a teaser.

### The open-core honesty question

The user surfaced the question directly during the discussion: *if commercial parts are add-ons, does that not offend open-source spirit?*

The honest answer is: **no, IF the architecture encodes specific commitments that prevent the failure modes of open-core capture.** The failure modes are well-documented:

- Elastic (2021): relicensed core to SSPL/Elastic License when AWS-style hyperscalers competed with the open distribution. The open base stopped being open.
- MongoDB (2018): relicensed to SSPL for the same reason. Same shape.
- HashiCorp Terraform (2023): relicensed to BSL. Same shape.
- Various enterprise products throughout the 2010s: the open base atrophied while commercial features absorbed all engineering attention. The open base was nominally open but practically unmaintained.

The reference architectures that DO honor open-source spirit (Postgres + extensions / EnterpriseDB; VSCode + extensions / Cursor; Kubernetes + operators / commercial operators; ELK Stack pre-2021) share four properties:

1. **Open base is complete on its own merit.** A user runs it indefinitely without payment and gets the full thesis. The open base is the product, not a marketing funnel.
2. **Plugin interfaces are symmetric.** First-party commercial plugins use the same public APIs a third-party plugin would. No private surface area.
3. **License terms can't be retroactively tightened.** Existing contributions remain under their original license forever. License changes are forward-only and require contributor consent.
4. **Runtime forks build on the open library as published, versioned packages.** They depend on it the same way any third-party fork would.

CORE's existing architecture already establishes properties 1 and 3 constitutionally: Features §1 says weakening an `open` stamp is a governance amendment, and Products.md §Enforceability says MIT is the floor. Properties 2 and 4 are the new commitments this ADR adds.

---

## Decisions

### D1 — Three commercial-surface shapes, exhaustive

Every commercial feature in the registry takes exactly one of three structural shapes:

| Shape | What it is | Interface it uses | Examples (current registry) |
|---|---|---|---|
| **Plugin** | Code that runs inside the open daemon, attached via an open extension interface | F-41 (artifact type registry), F-42 (pluggable sensor), F-43 (pluggable action), atomic action registry, `.intent/rules/` loader | F-37, F-44, F-46 |
| **Sidecar** | Standalone service that reads/writes through the open public APIs | F-40 OEM API surface | F-20, F-34, F-45, F-47 |
| **Runtime fork** | Separate distribution depending on the open codebase as a published library, changing the runtime's authority/state model | PyPI-published open packages | F-31, F-32, F-33, F-35, F-36 |

A commercial feature that does not fit one of the three shapes is either (a) miscategorised — re-examine; (b) not actually software — F-39 SLA support is the canonical case; or (c) a build/deployment overlay rather than a feature — F-38 air-gap guarantee is the canonical case. In cases (b) and (c), the feature exists outside the taxonomy and is noted as such; the shape system is not stretched to accommodate it.

### D2 — Plugin shape: symmetric interfaces, no private hooks

A commercial plugin MUST attach to the open engine via the same public interfaces a third-party plugin would use. Specifically:

- A commercial rule pack MUST load through the same `.intent/rules/` loader that loads the default rule library (F-05). No private rule-loader path.
- A commercial sensor MUST register through F-42's pluggable sensor model. No private sensor registration.
- A commercial atomic action MUST register through F-43's pluggable action model AND F-12's atomic action registry conventions. No private action dispatch.
- A commercial artifact-type extension MUST register through F-41's artifact type registry. No private artifact-type routing.

The negative is constitutionally load-bearing: there is **no commercial-only plugin slot, hook, or API surface in the open repo.** If a commercial plugin needs a capability the open repo does not expose, the path is to expose it as a public interface (open) and then build the plugin against it — never to add a private surface for commercial-only use.

### D3 — Sidecar shape: F-40 OEM API as the only access path

A commercial sidecar service MUST consume the open repo's state exclusively through the F-40 OEM API surface. Direct database access, direct Blackboard manipulation, or any other path that bypasses the public API is forbidden.

The OEM API surface is therefore not just the integration story for third-party OEM partners (Tiers paper §3.5); it is the integration story for CORE's own commercial sidecars. This is what makes property 2 (interface symmetry) verifiable: if first-party sidecars use only the public API, third-party sidecars can do the same and reach feature parity.

F-40 is currently `roadmap`. Sidecar-shape commercial features are blocked on F-40 reaching shipping status. This is a constraint on commercial sequencing, not a flaw — it forces the public API to ship before commercial features that depend on it can ship.

### D4 — Runtime fork shape: open library dependency, no closed branches

A commercial runtime fork MUST depend on the open codebase as a versioned, published package — PyPI for Python packages, Docker registry for images — using the same dependency mechanism any third party would. Specifically:

- The fork repo MUST NOT vendor or copy the open codebase. It imports.
- The fork repo MUST track open releases by semantic version. Pinning to a SHA is permitted for development; release builds pin to a published version.
- Changes that the fork needs in the open codebase MUST be contributed upstream as open contributions, not held as closed patches. If upstream rejects the contribution, the fork lives with the rejection — it does not maintain a closed parallel implementation of the rejected change.
- The fork's own value-add (multi-user state model, RBAC authority model, federated constitution loader, SSO bindings) lives entirely in the fork repo. The open library exposes the extension points the fork attaches to.

This is what makes property 4 (forks build on the published library) verifiable: if first-party forks must use the published packages, third-party forks can do the same and produce competing distributions on equal terms.

### D5 — Repo topology: one repo per shape, not one mega-repo

The "Repo topology" question in Products.md §"GOVERNOR decisions still open" resolves to:

- **`CORE/`** — the existing open repo, MIT licensed. Hosts the engine, the default rule library, the public APIs (F-40), and the extension interfaces (F-41–F-43).
- **`CORE-rules-commercial/`** — private repo, commercial license. Hosts plugin-shape rule packs (F-44). Compliance domain experts review and approve content here; no engine code.
- **`CORE-plugins-commercial/`** — private repo, commercial license. Hosts plugin-shape atomic actions and sensors (F-37 regulatory export, F-46 cloud audit export). Engineering review here; depends on the open packages.
- **`CORE-sidecars-commercial/`** — private repo, commercial license. Hosts sidecar-shape services (F-20 convergence dashboard, F-34 web dashboard, F-45 hosted findings dashboard). One service may be split into its own repo if its release cadence diverges; sub-repos are an implementation detail not a structural commitment.
- **`CORE-runtime-fork/`** — private repo, commercial license. Hosts the runtime fork distribution: multi-user (F-31), RBAC (F-32), multi-repo (F-33), federated constitution (F-35), SSO (F-36). Depends on the open packages by version pin.
- **`CORE-managed-infra/`** — private operational repo (Terraform/Ansible/etc.) for managed-service offerings (F-47 managed Qdrant). No application code; infrastructure-as-code only.

This is a maximum of five private repos. The split is by shape because shape determines (a) the public-API surface the repo depends on, (b) the license boundary, (c) the review cadence (rule packs reviewed by domain experts; sidecars by engineering; forks by senior engineering). A single mega-repo would conflate these and obscure the structural intent the rest of this ADR establishes.

Initial setup is the rule-packs repo + the plugins repo only — these match the two lowest-friction first-SKU candidates from ADR-083 §Consequences (F-44 and F-46). The other three repos materialise when their first feature is authored.

### D6 — Interface symmetry is constitutionally load-bearing

The open repo MUST NOT expose any API, hook, or extension point that is documented or accessible only to first-party commercial code. Every interface a commercial plugin, sidecar, or runtime fork uses MUST be a documented public interface available to any third party.

Verification path: any commercial F-NN entry's "Extension of" reference (in Features.md §3.12 and equivalents) MUST point to an open F-NN entry whose interface is publicly documented in the open repo. If no such open feature exists, the commercial feature cannot ship — the open public interface MUST ship first.

This is what makes property 2 enforceable rather than aspirational. It is also the constraint that operationalises the existing Features §3.11 prose ("Anyone may write a sensor or action against the public interface").

### D7 — The four constitutional open-core honesty commitments

These four commitments, taken together, define what "open core" honestly means for CORE:

1. **Completeness.** The open base, as distributed, ships every primitive required to reproduce the full thesis (constitutionally-governed AI code generation with autonomous remediation and full consequence chain). Already constitutional via Features §1; reaffirmed here. A new open feature does not need permission from this ADR to ship; a reclassification of an open feature to commercial does, and is foreclosed by Features §1.

2. **Symmetry.** Commercial plugins, sidecars, and runtime forks use only public interfaces a third party could use. Constitutional via D6. No commercial-only API surface in the open repo, ever.

3. **License floor.** MIT is the floor for the open repo. License tightening is forward-only and requires contributor consent. Constitutional via Products.md §Enforceability; reaffirmed here. The Elastic / MongoDB / HashiCorp relicensing pattern is explicitly named and foreclosed: if competitive pressure on the open base eventually arrives, the response is to compete on quality of commercial polish (plugins, sidecars, support), not to relicense the open base.

4. **Library-grade openness.** The open codebase is published as semantic-versioned packages (PyPI for Python, Docker registry for images) so that runtime forks — first-party and third-party — can depend on it as a library on equal terms. Constitutional via D4. The open repo cannot become "open source code that only we know how to build."

A future change to any of these four commitments is a constitutional amendment, on the same footing as a reclassification of an `open` stamp. They are not product decisions.

### D8 — Reclassification of stamped features into shape buckets

The fifteen currently-stamped commercial features (the eleven previously stamped + the four added by ADR-083) bucket as follows. This bucketing is a registry property and will be added to `papers/CORE-Features.md` §3.12 and §4 as a downstream documentation update.

| F-ID | Name | Shape |
|---|---|---|
| F-20 | Convergence graph dashboard | Sidecar |
| F-31 | Shared consequence chain (multi-user) | Runtime fork |
| F-32 | RBAC | Runtime fork |
| F-33 | Multi-repository support | Runtime fork |
| F-34 | Web dashboard | Sidecar |
| F-35 | Federated constitution | Runtime fork |
| F-36 | SSO / SAML / OIDC | Runtime fork |
| F-37 | Regulatory export (GxP / EU AI Act) | Plugin (atomic action) |
| F-38 | Air-gapped deployment (guaranteed) | Build overlay (outside taxonomy) |
| F-39 | SLA support | Not software (outside taxonomy) |
| F-40 | OEM API surface | The plugin-interface contract itself |
| F-44 | Premium rule libraries | Plugin (rule overlay) |
| F-45 | Hosted findings dashboard | Sidecar |
| F-46 | Cloud audit export (signed) | Plugin (atomic action) |
| F-47 | Managed Qdrant | Sidecar (degenerate — managed infrastructure) |

Plugins: 4 (F-37, F-44, F-46, F-47-style infrastructure not counted as code).
Sidecars: 4 (F-20, F-34, F-45, F-47).
Runtime forks: 5 (F-31, F-32, F-33, F-35, F-36).
Outside taxonomy: 2 (F-38, F-39).
F-40: the plugin-interface contract.

The first commercial SKU candidates remain those identified in ADR-083 §Consequences (F-44 as lowest-friction). With this bucketing, the path is unambiguous: ship the `CORE-rules-commercial/` repo first, populate it with F-44, validate the plugin shape against real domain content, and let the second SKU be either another plugin (F-46) or the first sidecar (F-45) depending on which signal the market sends.

---

## Consequences

### Closes the "Repo topology" governance question

`commercial/CORE-Products.md` §"GOVERNOR decisions still open" lists "Repo topology — overlay vs. separate `CORE-enterprise/` repo" as an open item. D5 of this ADR resolves it. The Products doc should be updated to remove that item and reference this ADR as the place the decision was made. This is a downstream doc edit, not part of the ADR text.

### Establishes the open-core honesty contract as constitutional

D7 turns four properties of honest open-core architecture into constitutional commitments on equal footing with Features §1's open-stamp commitment. Future ADRs that propose changing them face the same bar as ADRs proposing to reclassify an `open` feature: a governance amendment, not a product decision.

The four commitments together foreclose the Elastic / MongoDB / HashiCorp relicensing pattern. They do not prevent the commercial line from competing — they require the commercial line to compete on the merits of plugin quality, sidecar operations, runtime-fork value-add, and support, not on artificial scarcity of the open base.

### Reframes the commercial-feature authoring process

A new commercial feature F-NN is no longer authored as "what commercial code shall we write." It is authored as a four-question scope decision:

1. **What shape is this?** Plugin, sidecar, or runtime fork (D1).
2. **What open public interface does it extend or consume?** Must exist and be public (D6).
3. **Which private repo does it live in?** Determined by shape (D5).
4. **Does the open base need a new public interface to support this?** If yes, that open feature ships first.

This is the four-question filter that should accompany any future commercial-stamping ADR (the way ADR-083 stamped four features, future stamping ADRs are expected to also classify by shape per D8).

### Sequencing constraints become explicit

Because D2/D3/D6 require commercial features to attach via public open interfaces, the sequencing constraint becomes:

- Plugin-shape commercial features (F-44 rule packs, F-46 signed export, F-37 regulatory export) ship after the open extension interfaces they depend on. F-44 depends on F-04 (`.intent/` loader, shipping); ready. F-46 depends on F-43 (pluggable action model, roadmap); blocked. F-37 depends on F-43 + signing infrastructure; blocked.
- Sidecar-shape commercial features (F-20, F-34, F-45, F-47) ship after F-40 (OEM API surface, roadmap). All blocked on F-40.
- Runtime-fork-shape commercial features (F-31–F-36) ship after the open codebase is published as semantic-versioned packages. Partial state — the codebase exists but is not yet a PyPI artifact.

The first commercial SKU is therefore F-44, structurally — it is the only commercial feature whose open dependencies are already shipping. This is consistent with ADR-083 §Consequences' independent argument from first-deliverable cost.

### Bumps F-10 / F-40 / F-41–F-43 priority

The previous answer to the user's original question (what open features to prioritise) ordered F-10, F-27, then F-41/F-42/F-43. With D2/D3/D6 making these the structural prerequisites for commercial shipping, the priority logic compounds:

- **F-10 (CI/CD gate)** — top-of-funnel, gates customer encounter with CORE. Priority unchanged.
- **F-40 (OEM API surface)** — was deferred to Embedded tier in Tiers paper §3.5. After this ADR, it is the structural gate for FOUR commercial sidecar SKUs. Priority materially elevated.
- **F-41 / F-42 / F-43 (extension interfaces)** — were positioning-claim work. After this ADR, they are the structural gate for FOUR commercial plugin SKUs. Priority materially elevated.

The investor framing of the open roadmap also tightens: the open features that need to ship are precisely the ones that unblock commercial revenue. There is no longer a tension between "open work" and "commercial work" — the open work is the precondition for commercial work, by structural design.

### Public-API discipline becomes the central engineering practice

D6 makes interface symmetry constitutional. The practical implication: every new open feature that exposes an extension point ships with documented public-API status. "Internal" APIs in the open repo are permitted only when no commercial feature would attach to them. The moment a commercial feature wants to attach, the API ships as public — there is no path where the commercial feature attaches privately.

This is a discipline change. Engineering work that previously could be deferred ("we'll document the API later") is now blocked on commercial sequencing — the API ships with documentation as part of the open release that enables the commercial feature.

### Does not change ADR-083

ADR-083 stamped F-44–F-47 and named the F-19/F-20 split pattern. This ADR extends that — the F-19/F-20 split becomes the plugin and sidecar shapes specifically. ADR-083 stands; no supersession.

### Does change downstream documentation

The following downstream doc edits are implied by this ADR but not performed inside it (per CLAUDE.md §"Reconnaissance before editing" and the multi-file-edit pause). They are noted here as the implementation plan:

- `papers/CORE-Features.md` §3.12 — annotate each of F-44–F-47 with its shape (plugin/sidecar) per D8.
- `papers/CORE-Features.md` §4 — add a "Shape" column to the status table.
- `papers/CORE-Features.md` §5 — possibly add a "Shape" annotation to the tier-mapping table.
- `commercial/CORE-Products.md` §"Open-core boundary" — embed the three-shape model and the four D7 commitments.
- `commercial/CORE-Products.md` §"GOVERNOR decisions still open" — remove "Repo topology" item and the "first SKU" item is enriched (F-44 emerges as the structurally unblocked candidate).
- `papers/CORE-Product-Tiers.md` §3.5 (Embedded) — F-40's elevated structural role should be acknowledged.

These edits will land as a separate change-set after this ADR is reviewed and accepted.

---

## Verification

- ADR file exists at `.specs/decisions/ADR-084-commercial-surface-taxonomy-and-open-core-honesty.md`.
- ADR explicitly resolves the "Repo topology" item from Products.md §"GOVERNOR decisions still open" (D5).
- ADR establishes four named constitutional commitments (D7) on equal footing with Features §1.
- D1 taxonomy is exhaustive across the 15 commercial F-IDs (D8 bucketing covers all of F-20, F-31–F-40, F-44–F-47).
- D6 interface symmetry is a verifiable property: any commercial F-NN's "Extension of" reference points to an open F-NN whose interface is publicly documented. F-44 → F-04/F-05 (✓ shipping, public). F-46 → F-43 (✓ public roadmap interface). F-45 / F-47 → F-40 (✓ public roadmap interface).
- No `open` stamp was modified or reclassified by this ADR (consistent with D7 §1 and Features §1).
- `grep -c 'open-core' .specs/decisions/ADR-084*` returns >= 3 (the term is used as a marker of the architectural pattern being committed to).

---

## References

- ADR-083 — stamps F-44–F-47 and names the F-19/F-20 split. This ADR widens that split into the three-shape taxonomy and adds the symmetry, honesty, and repo-topology consequences.
- ADR-052 — `core.llm_resources` per-resource model. The precedent for the sidecar shape: managed infrastructure consumed through a documented configuration interface.
- `papers/CORE-Features.md` §1 — the constitutional commitment on the open/commercial line. D7 §1 reaffirms verbatim.
- `papers/CORE-Features.md` §3.11 — the F-41/F-42/F-43 extension interfaces. D2 and D6 make their plugin-API status structurally load-bearing.
- `papers/CORE-Product-Tiers.md` §3.5 — F-40 OEM API surface as Embedded tier feature. After this ADR, F-40 also structurally underpins every sidecar-shape SKU.
- `commercial/CORE-Products.md` §"Open-core boundary" §Enforceability — the MIT floor commitment. D7 §3 reaffirms verbatim.
- `commercial/CORE-Products.md` §"GOVERNOR decisions still open" — the "Repo topology" item D5 closes.
- Memory `feedback_two_surface_requires_two_structures` — why three shapes rather than collapsing plugins and sidecars into one bucket: the material difference between "code running inside the open daemon" and "service consuming open APIs externally" is the kind that does not survive unification.
- Memory `feedback_governance_debt_share_inversion` — the open-core honesty commitments in D7 are the equivalent governance metric at the commercial-line level: ratio of "open base completeness" to "commercial-only feature reliance" is the long-run signal of whether the open-core claim stays honest.
- External reference (named for foreclosure, not as model): Elastic 2021 SSPL/Elastic License relicensing, MongoDB 2018 SSPL relicensing, HashiCorp 2023 BSL relicensing — all are the failure mode D7 §3 explicitly forecloses.
- External reference (named as model): Postgres + extensions, VSCode + extensions, Kubernetes + operators — three-shape add-on architectures that have honored open-source spirit at scale over long time horizons.
