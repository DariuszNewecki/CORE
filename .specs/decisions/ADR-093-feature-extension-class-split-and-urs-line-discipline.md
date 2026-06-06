<!-- path: .specs/decisions/ADR-093-feature-extension-class-split-and-urs-line-discipline.md -->

# ADR-093 — Feature / Extension class split + URS-line governance discipline

**Date:** 2026-06-06
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-06 — drafted under explicit "go" authorization at the close of an exploratory thread on CORE's intake architecture. The naming question — Plug-in vs Extension — was the only sub-decision where the governor flagged unease; the unease was taken as signal and landed on Extension, the term already canonical in the planning doc.)
**Grounding decisions:** ADR-083 (commercial add-on stamping for F-44–F-47, directly affected by the migration in D3). ADR-084 (commercial decomposition + the canonical commercial-extension `shape: plugin` vocabulary that this ADR lifts to a top-level class). ADR-085 §Context (the 5+3 list whose members all stay F-NN). ADR-074 D13 + ADR-080 §D5 (append-only ADR precedent applied to D6's redirect markers). ADR-091 D6 (F-43 registry-coupling enforcement — the architectural anchor that makes "attaches via published interface" a verifiable property).
**Related:** `.specs/requirements/URS-requirement-fulfillment-verification.md` (the URS whose discipline this ADR extends to E-NN with an analogous Extension Manifest shape). `.specs/concepts/CORE-URS-Intake-Concept.md` (the frozen pre-URS thinking + §11 Reception that opened the URS-line conversation). `.specs/papers/CORE-Features.md` (the registry this ADR restructures).

---

## Context

### The conflation this ADR resolves

`CORE-Features.md` currently holds 48 F-NN entries with mixed `sourcing` (open vs commercial). The single namespace conflates four architecturally different classes of artifact:

1. **Interface contracts** baked into the open-source engine — F-04 (rule pack loader), F-41/F-42/F-43 (the extension interfaces we shipped this session).
2. **Engine capabilities** baked into the open-source distribution — F-10, F-19, F-27, F-48, etc.
3. **Engine capabilities** that ship as part of a commercial runtime fork or as managed infrastructure — F-37 (autonomous developer), F-47 (managed Qdrant).
4. **Implementations** that attach to the open-source engine via the published interface contracts at runtime — F-44 (premium rule libraries), F-45 (hosted findings dashboard), F-46 (cloud audit export signed).

Classes (1)–(3) are *architecturally features* — they live inside an engine binary, regardless of how the engine is distributed. Class (4) is *architecturally an extension* — it sits outside the engine, attaches via a published contract, and could be authored by a third party.

The single F-NN namespace pretends these are peers. They are not. ADR-084 D2 already names "plugin" as the canonical commercial-extension *shape*; this ADR lifts that vocabulary from a per-row attribute to a top-level class, and chooses the term Extension over Plug-in to avoid the peripheral connotation.

### The URS-line discipline this ADR codifies

The session that produced this ADR included a CONCEPT freeze (`.specs/concepts/CORE-URS-Intake-Concept.md`), four external reviews, and a v0.1 URS (`.specs/requirements/URS-requirement-fulfillment-verification.md`). The CONCEPT's §11 Reception recorded the convergence that the Verifier must be sensor-shaped and that classification is declared per criterion.

A separate thread in the same session surfaced that **CORE is not URS-based** — 92 ADRs and 73 papers exist; only 5 URSs predate this session. The "papers keep their honor" reframe was: don't retrocover historical work with URSs; instead, draw a URS-line at this ADR's acceptance date and require URSs (or Extension Manifests) for new work going forward.

This ADR is the URS-line act. It codifies what each class requires at the intent layer for net-new authoring, what gets grandfathered, and what migrates immediately.

### Why the classifier is architectural shape, not commercial sourcing

An earlier framing of the split used `sourcing: open|commercial` as the discriminator. Recon broke that framing on two cases:

- **F-37 (Autonomous Developer)** is commercial but engine-shape (built into a commercial runtime fork — same architectural class as F-19 or F-27, different distribution).
- **F-47 (Managed Qdrant)** is commercial but managed-infrastructure shape (per the F-40.4 verification, F-47 doesn't consume the FastAPI OEM API at all; its "API" is the Qdrant wire protocol).

Both are commercial. Neither is an Extension. The honest classifier is *architectural shape* — built-into-engine vs attached-via-interface — with `sourcing:` carrying the open/commercial distinction *within each class*.

---

## Decisions

### D1 — Two top-level artifact classes in `CORE-Features.md`: F-NN (Features) and E-NN (Extensions)

The registry shall, from the date of this ADR forward, distinguish two artifact classes:

- **F-NN (Features)** — capabilities built into an engine binary. Includes engine primitives (F-10, F-19, F-27, F-48), interface contracts (F-04, F-41, F-42, F-43), commercial-engine-features (F-37, F-47), and any other built-into-the-engine work regardless of sourcing.
- **E-NN (Extensions)** — implementations that attach to an engine at runtime via a published interface contract (F-41 artifact_type registry, F-42 pluggable sensor model, F-43 pluggable action model, or F-04 rule pack loader). Authorable by first parties or third parties; typically commercial but the class is sourcing-agnostic.

The discriminator is **architectural shape**, not commercial sourcing. The `sourcing: open|commercial` field on each entry continues to differentiate distribution model within each class.

### D2 — Commercial-engine-shape and not-software entries stay F-NN

The following commercial entries **remain F-NN with `sourcing: commercial`** because their architectural shape is not "attaches via published interface":

- **F-31** (Shared consequence chain), **F-32** (RBAC), **F-33** (Multi-repository support), **F-35** (Federated constitution), **F-36** (SSO / SAML / OIDC) — all `Shape: runtime fork` per ADR-084 D1. These are engine-shape features of a commercial runtime fork; different distribution model, same architectural class as open engine features.
- **F-39** (SLA support) — `Shape: not software` per ADR-084 D1. A commercial and operational commitment, not a software artifact. Outside the three-shape software taxonomy but still a registry entry; F-NN by default since the registry has no third class.
- **F-47** (Managed Qdrant) — `Shape: sidecar (managed infrastructure)` per ADR-084 D3, but per F-40.4's verification it does not consume CORE's FastAPI surface — its "API" is the Qdrant wire protocol. Managed-infrastructure shape, not interface-attaching shape. F-NN.

Any future commercial-engine-shape feature (e.g., a Team-tier capability built into a commercial runtime fork) follows the same pattern: F-NN with `sourcing: commercial`. The E-NN namespace is reserved exclusively for the attached-via-published-interface shape.

### D3 — Six entries migrate to E-NN: F-20, F-34, F-37, F-44, F-45, F-46

A registry shape review (recon during implementation of this ADR) found six entries whose declared `Shape:` is interface-attaching:

- **F-20** (Convergence graph dashboard) → **E-20** — `Shape: sidecar`, consumes F-40 OEM API.
- **F-34** (Web dashboard) → **E-34** — `Shape: sidecar`, consumes F-40 OEM API.
- **F-37** (Regulatory export, GxP / EU AI Act) → **E-37** — `Shape: plugin (atomic action)`, attaches via F-43 atomic action interface.
- **F-44** (Premium rule libraries / industry packs) → **E-44** — `Shape: plugin`, attaches via F-04 rule pack loader.
- **F-45** (Hosted findings dashboard) → **E-45** — `Shape: sidecar`, consumes F-40 OEM API.
- **F-46** (Cloud audit export, signed) → **E-46** — `Shape: plugin (atomic action)`, attaches via F-43 atomic action interface.

The migration is mechanical. `CORE-Features.md`'s entry headers and table rows are updated; the summary count (currently 34 shipping / 0 partial / 14 roadmap) is restructured to report F-NN and E-NN separately. Per-entry attachment points are preserved in each renamed body's prose.

**Historical scoping note:** the draft of this ADR initially scoped the migration to F-44/F-45/F-46 only, based on a stale memory association that put a different feature in the F-37 slot ("Autonomous Developer"). The actual registry shape review surfaced three additional entries (F-20, F-34, F-37) whose `Shape:` field unambiguously placed them on the attached-via-interface side of D1's classifier. The expansion is the honest outcome of verification per memory `feedback_recheck_state_before_public_assertion`.

### D4 — URS-line governance shape, differentiated by class

From the acceptance date of this ADR forward (the URS-line):

- A new F-NN entry in `CORE-Features.md` shall require a URS in `.specs/requirements/` referencing the F-NN, with a criterion manifest per R-001 of `URS-requirement-fulfillment-verification.md`, before the registry row lands.
- A new E-NN entry in `CORE-Features.md` shall require an Extension Manifest, before the registry row lands. The Manifest declares at minimum: which F-NN interface contract the extension attaches through, conformance evidence, and the ADR-084 D2 vocabulary attributes (`shape`, `sourcing`).

Both gates are intent-layer artifacts at the URS-line. They diverge in form because the work diverges in kind: F-NN is engine capability declaration; E-NN is attachment-shape declaration against an existing contract.

### D5 — Extension Manifest details are paper-scope

The exact shape of an Extension Manifest (storage format — embedded YAML? Markdown table? separate `.intent/extensions/<id>.yaml`? — mandatory fields beyond the minimum in D4, lifecycle handling) is **paper-scope**. This ADR does not pre-judge the form. The Manifest paper is authored when the first new E-NN entry needs to land after the URS-line.

Suggested minimum-shape inputs the paper author should consider:

- `target_interface` — which F-NN contract this extension attaches through (closed enum: F-04 | F-41 | F-42 | F-43 | future interfaces)
- `conformance` — pointer to evidence that the extension honors the interface contract
- `shape` — per ADR-084 D2 vocabulary (`plugin`, `source-code-instantiation`, etc.)
- `sourcing` — `open` | `commercial`
- `commercial_tier` — when sourcing is commercial, the tier mapping per ADR-084 / Tiers paper

The paper may add fields and lifecycle states; this ADR does not constrain those decisions.

### D6 — Historical references preserved by append-only redirect markers, not rewrites

ADR-083 (commercial add-on stamping for F-44–F-47) and ADR-084 (commercial decomposition + commercial-shape taxonomy) reference the migrated F-NN entries by their original names throughout. **Their bodies shall not be rewritten.** Per ADR-074 D13 + ADR-080 §D5 append-only discipline, the rename is recorded as an additive marker at the top of each ADR:

> "Note (2026-06-06, per ADR-093): F-20, F-34, F-37, F-44, F-45, F-46 references in this ADR's body now point at E-20, E-34, E-37, E-44, E-45, E-46. Body text preserved verbatim; the rename is governed by ADR-093 D1 + D3."

Historical references in older ADRs, accepted GH issues, memory artifacts, and shipping commit messages remain as-is. The cost of rewriting history outweighs the readability cost of a stable redirect pointer at two well-known ADR locations.

### D7 — The URS-line cutover date is this ADR's acceptance date

When this ADR is accepted, the URS-line discipline (D4) takes effect for new authoring. Existing entries (48 pre-rename F-NN, becoming 42 F-NN + 6 freshly-renamed E-NN after D3) are **grandfathered**. The discipline does not require retroactive URS or Extension Manifest authoring for entries that predate the URS-line.

Optional retroactive coverage of historical entries is permitted under `feedback_park_cleanup_when_boundary_works`: visible-but-stable governance debt defers. If a governor later authors a URS for a historical F-NN, it lands as forward-coverage; it does not retroactively gate the historical entry.

### D8 — Recursive cleanup: `URS-requirement-fulfillment-verification.md` retrofits its own criterion manifest

The URS authored earlier in this same session (`.specs/requirements/URS-requirement-fulfillment-verification.md`) carries 12 functional requirements but no per-criterion `verification_class` metadata. Under its own R-001 + R-011 discipline, the URS would reject itself on first invocation as malformed.

This recursive defect is closed as part of this ADR's implementation phase: the URS shall be retrofitted with a criterion manifest covering R-001 through R-012, each with declared `verification_class` and `verifier_hint`. The retrofit ships in the same change-set as the F→E migration.

The four other pre-URS-line URSs (`CORE-Ask-URS.md`, `CORE-Governor-Ask-URS.md`, `CORE-Governor-Dashboard-URS.md`, `URS-consequence-chain.md`, `URS-mechanism-coherence.md`) are grandfathered per D7. Their retrofit is optional follow-on work, not gated by this ADR.

---

## Consequences

### Registry shape changes from one namespace to two

`CORE-Features.md` restructures from "48 F-NN entries" to "42 F-NN + 6 E-NN entries." The summary count migrates from "34 shipping / 0 partial / 14 roadmap" to a class-split version reporting both namespaces independently. The "Of the N shipping features..." narrative line is recomputed against the new totals.

### ADR-083 and ADR-084 carry append-only redirect markers

Both ADRs receive a one-line "Note (2026-06-06, per ADR-093)..." marker at the top. Bodies are not edited. This is the same pattern ADR-089 used for F-27 and ADR-092 used for F-43 — append-only amendments under acceptance.

### URS-line discipline becomes the new authoring gate

After this ADR's acceptance, any pull request that adds a new F-NN or E-NN entry to `CORE-Features.md` shall include the corresponding URS or Extension Manifest in the same change-set. The Verifier (when shipped per `URS-requirement-fulfillment-verification.md`) will report registry-shape findings when this discipline is violated.

For the implementation phase of this ADR, no Verifier exists yet, so the discipline is enforced by governor + reviewer attention only. The Verifier's eventual ship makes the discipline mechanically enforceable.

### Conversation history preserved; memory artifacts not amended

Memory artifacts that reference F-44/F-45/F-46 (per the user's MEMORY.md index) are **not** updated as part of this ADR. The rename moves forward; the historical record stays as it was. Future memory entries reference E-NN; past entries reference F-NN. The redirect markers on ADR-083/ADR-084 provide the canonical pointer for readers who need to bridge.

### The URS we just shipped becomes internally consistent

D8 closes the recursive embarrassment surfaced last turn — the URS that requires criterion manifests gets one of its own. This is the first concrete exercise of the criterion-manifest pattern; the retrofit doubles as the proof-of-concept for the Manifest format the future paper will codify.

### Architectural-shape classifier is now visible at the registry layer

Today, distinguishing "is this baked into the engine?" from "does this attach via a contract?" requires reading per-row `Shape:` attributes. After D1, the discrimination is in the artifact ID. F-NN means engine; E-NN means extension. Reviewers, future ADRs, and the future Verifier can rely on the namespace as a sufficient signal.

### Extension Manifest paper is now committed forward work

D5 defers Extension Manifest details but commits that the paper will be authored when the first new E-NN entry needs to land. This sequences the work: paper precedes the first net-new E-NN; no E-NN can be added under D4 until the paper specifies the Manifest's form. Implementing E-NN governance is therefore a two-step sequence: ADR-093 acceptance + Manifest paper.

For the F-44/F-45/F-46 → E-44/E-45/E-46 migration in D3, no Manifest is required — these are existing entries being renamed, not new entries being added. The migration commit documents this exception.

---

## Verification

- This ADR exists at `.specs/decisions/ADR-093-feature-extension-class-split-and-urs-line-discipline.md`.
- `.specs/papers/CORE-Features.md` is updated:
  - F-44 entry renamed to E-44 (body, table row, summary count).
  - F-45 entry renamed to E-45 (body, table row, summary count).
  - F-46 entry renamed to E-46 (body, table row, summary count).
  - Summary line restructured to report F-NN and E-NN counts independently.
  - Header table (if present) or registry section reflects the new class split.
- `.specs/decisions/ADR-083` carries an append-only redirect marker per D6 at the top of its body.
- `.specs/decisions/ADR-084` carries an append-only redirect marker per D6 at the top of its body.
- `.specs/requirements/URS-requirement-fulfillment-verification.md` carries a criterion manifest per D8, with `verification_class` declared on each of R-001 through R-012.
- `.specs/planning/CORE-Operational-Completeness.md` is searched for references to F-44/F-45/F-46; any references found are updated to E-44/E-45/E-46 with a parenthetical "(formerly F-NN per ADR-093)" annotation.
- After this ADR's acceptance, new F-NN entries in `CORE-Features.md` shall ship with a URS in the same change-set; new E-NN entries shall ship with an Extension Manifest. The discipline is reviewer-enforced until the Verifier ships.
- Historical references (older ADRs not specifically called out in D6, accepted GH issues, memory artifacts, commit messages) are **not** updated. The redirect markers on ADR-083 and ADR-084 are the canonical pointers.

---

## References

- ADR-083 — commercial add-on stamping for F-44–F-47. Receives redirect marker per D6.
- ADR-084 — commercial decomposition + the canonical `Shape: plugin` vocabulary. Receives redirect marker per D6. The vocabulary stays valid as a per-row attribute even after this ADR lifts "Extension" to a top-level class.
- ADR-085 — the 5+3 list. All five feature commitments (F-10, F-27, F-40, F-41/F-42/F-43, F-48) stay F-NN; none of them migrate.
- ADR-091 D6 — F-43 registry-coupling enforcement. The architectural anchor that makes "attaches via published interface" a verifiable property; without that enforcement, the F-NN/E-NN distinction would be a label without a runtime gate.
- ADR-074 D13 + ADR-080 §D5 — append-only ADR-amendment precedent applied to D6's redirect markers and D8's URS retrofit pattern.
- ADR-089 — direct precedent for "amendment via new ADR on equal footing"; D6's redirect markers follow the same shape ADR-089 used for F-27.
- ADR-092 — direct precedent for the planning-doc-update + GH-issue-comment + verification-bullet pattern this ADR's implementation will follow.
- `URS-requirement-fulfillment-verification.md` — the URS this ADR extends with the Extension Manifest analog and whose own criterion-manifest retrofit closes D8.
- `.specs/concepts/CORE-URS-Intake-Concept.md` — the frozen pre-URS thinking + §11 Reception that opened the URS-line conversation this ADR codifies.
- `papers/CORE-Features.md` — the registry this ADR restructures.
- Memory `feedback_phase_goal_absorbs_design` — interrogating the goal (the right namespace structure) rather than the mechanism (which artifacts get renamed) is what surfaced the architectural-shape classifier over the commercial-sourcing classifier.
- Memory `feedback_conviction_signal` — the user delegated the call ("you decide") and a hedge-free decision was the honest response.
- Memory `feedback_park_cleanup_when_boundary_works` — D7's grandfather discipline and the optional-not-required posture on retroactive URS authoring.
- Memory `feedback_external_review_value_triage` — the four external reviews on the CONCEPT shaped the URS, which shaped the URS-line discipline this ADR formalizes.
- Memory `feedback_append_only_amendments_under_review` — the D6 redirect-marker pattern.
- Memory `feedback_no_tooling_for_retiring_artifacts` — informed the choice to bite the bounded migration cost in D3 + D6 rather than defer indefinitely.
