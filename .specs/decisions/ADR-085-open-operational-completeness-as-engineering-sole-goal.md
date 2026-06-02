<!-- path: .specs/decisions/ADR-085-open-operational-completeness-as-engineering-sole-goal.md -->

# ADR-085 — Open operational completeness as engineering's sole goal

**Date:** 2026-06-02
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-02 — drafted under Path A execute-verb authorization, "yes, that 5+3 list matches — let's lock it in" + answered scoping questions selecting "all three artifacts" and "exit criteria as proposed")
**Grounding papers:** `papers/CORE-Features.md` §1 (the open/commercial line as constitutional commitment); ADR-084 §D7 §1 (the *completeness* honesty commitment — "the open base ships every primitive required to reproduce the full thesis"); `papers/CORE-Product-Tiers.md` §2 (the adoption funnel that depends on a complete open base for entry).
**Related:** ADR-084 (the constitutional shape this ADR operationalises into a concrete sequencing constraint); ADR-083 (the four commercial stampings whose engineering work this ADR explicitly defers); the open-roadmap features this ADR makes load-bearing: F-10, F-27, F-40, F-41, F-42, F-43, F-48.

---

## Context

### The honesty commitment that needs operational teeth

ADR-084 D7 enumerates four constitutional commitments that keep the open-core architecture from drifting into the Elastic/MongoDB/HashiCorp relicensing failure mode. The first commitment — **completeness** — is the precondition for the other three: a base that is not complete on its own merit cannot be "symmetric with first-party plugins" or "library-grade open" in any meaningful sense, because the base itself is not the product.

ADR-084 expresses this as a *constitutional* commitment but does not translate it into an *operational* one. The risk is concrete: the four commercial features stamped in ADR-083 (F-44, F-45, F-46, F-47) and the eleven previously-stamped commercial features (F-20, F-31–F-40) are now visible, traceable, and tempting. Engineering capacity routed to commercial work before the open base is operationally complete is the exact failure mode ADR-084 forecloses constitutionally and therefore must also foreclose operationally.

### Why "open-first" is structural, not strategic

The dependency graph in `planning/CORE-Feature-Dependency-Graph.md` shows that every commercial feature has an open prerequisite. Specifically:

- Plugin-shape commercial features wait on F-41/F-42/F-43 (extension interfaces) or F-04 loader (F-44 only).
- Sidecar-shape commercial features wait on F-40 (OEM API surface).
- Runtime-fork-shape commercial features wait on F-48 (open library distribution).

The structural reality is: even if engineering capacity were directed at commercial work today, four-fifths of it would be blocked. The constraint codified in this ADR is therefore not making commercial work slower than it would have been — it is making the bottleneck explicit and committing to clearing it.

F-44 is the one exception: F-04 and F-05 ship, so F-44 has no hard blocker. The Consequences section addresses why F-44 is still deferred under this ADR.

### What "fully operational CORE-open" means

The phrase needs a concrete definition before it can be a sole engineering goal — otherwise it drifts into "everything is polished" which is never.

The definition this ADR adopts is a 5+3 list: five feature commitments (open-roadmap features whose status transitions to `shipping`) plus three quality goals (operational properties of the open distribution that the registry does not track). The list is exhaustive: when all eight items are satisfied, the constraint codified in D1 below relaxes.

| Group | Item | Type | What "done" looks like |
|---|---|---|---|
| Features (5, grouping the F-41/F-42/F-43 trio as one) | F-10 CI/CD gate | registry | `status: shipping`; PR annotations + merge-blocking demonstrated against a real external repo |
| | F-27 Local LLM | registry | promotes from `partial` to `shipping`; reliable local-LLM-only Solo run for ≥7 days |
| | F-40 OEM API surface | registry | `status: shipping`; documented public contract; sidecar-shape commercial features F-20/F-34/F-45/F-47 can attach against it without private hooks (ADR-084 D6) |
| | F-41 / F-42 / F-43 extension interfaces | registry | all three `status: shipping`; one first-party non-code instantiation exists as proof of the plugin-interface contract |
| | F-48 Open library distribution | registry | `status: shipping`; `pip install` works; semver tags; CI publishes on tag |
| Quality goals (3) | Docs polish | property | an outside developer installs + runs the full thesis (encounter → audit → remediate → verify) from public docs alone, without source-tree archaeology |
| | Demo reliability | property | the consequence-chain bootstrap demo (Tiers §3.2) runs cleanly on first attempt, three times in a row, from a clean repo clone on a freshly-provisioned machine |
| | Signal quality | property | the F-19 convergence metric reports resolution rate ≥ creation rate, sustained ≥ 30 days, on this repo — proving the open base is converging toward constitutional compliance under self-governance, not diverging |

The 5+3 framing collapses F-41/F-42/F-43 into one "extension interfaces" item because the three are interlocked: F-42 and F-43 both depend on F-41, and the contract symmetry that ADR-084 D6 requires is satisfied only when all three ship together. Operationally these are three separate registry transitions; strategically they are one gate.

### Why the three quality goals are NOT in the registry

The five features have F-IDs. The three quality goals do not. They are excluded from the registry deliberately:

- **Docs polish** is an output of all engineering work, not a discrete feature. Adding "F-49: docs polish" would create a never-closing tracking issue because documentation work continues forever.
- **Demo reliability** is a verification property of the system as a whole, not a feature delivered in one place. The demo's reliability depends on the engine, the CLI, the rule library, the LLM integration, and the docs — every change affects it.
- **Signal quality** is a derived metric over time, not a built artifact. The metric (F-19) ships; the quality of what it reports is an emergent property of how well the engine, sensors, and remediators behave together.

These three properties belong in this ADR and in the operational-completeness planning doc, not in the feature registry. The registry tracks *what gets built*; this ADR tracks *what "complete" means as a system property*.

---

## Decisions

### D1 — Engineering capacity routes only to the 5+3 list until exit criteria are met

From the date of this ADR until all eight items in §Context's table are satisfied, engineering capacity is allocated only to (a) the five features in the list and (b) work that materially advances the three quality goals.

**Engineering capacity in scope:**
- Implementation work on F-10, F-27, F-40, F-41, F-42, F-43, F-48
- Documentation work that closes the "docs polish" gap
- Engine, CLI, rule library, or LLM-integration work that advances the demo or convergence-metric quality

**Engineering capacity NOT in scope (deferred):**
- Implementation work on any commercial feature: F-20, F-31, F-32, F-33, F-34, F-35, F-36, F-37, F-44, F-45, F-46, F-47
- Implementation work on F-38 (air-gap guarantee — depends on F-48 and is a deployment/build concern, not an engineering capacity question)
- Speculative refactoring or platform work not visibly on the 5+3 path

Bug fixes, security patches, dependency updates, and constitutional-debt remediation continue as ordinary engineering hygiene — they are not "new work" in the sense this constraint governs.

### D2 — Governance-frame work continues unconstrained

Authoring and amending ADRs, papers, the feature registry, planning docs, GitHub issues for tracking purposes, label/milestone administration, and other artifacts under `.specs/` continue without restriction. This work has zero overlap with engineering capacity and is exactly what enables the constraint in D1 to be enforced.

Specifically: the four commercial stampings in ADR-083 (F-44–F-47) and the shape taxonomy in ADR-084 are *governance work*, not engineering work. They consumed no engineering capacity. They anchor the commercial line constitutionally and enable honest commercial conversations with potential partners or investors without requiring commercial *engineering* work to start. This ADR codifies that asymmetry rather than reversing it.

### D3 — Sales, positioning, and partnership work continues unconstrained

Conversations with potential customers, OEM partners, regulatory consultants, or investors are out of scope for this ADR. They consume strategic and relational capacity, not engineering capacity. The four commercial stampings exist precisely to make those conversations honest without requiring commercial features to be built first.

If a sales conversation produces a customer who is willing to pre-commit to a commercial SKU before the open base is operationally complete, that is a *different* decision than the one this ADR governs — it would require an amendment specifically authorizing engineering capacity for that SKU as a customer-driven exception. The constraint in D1 governs *speculative* commercial work, not *customer-pulled* commercial work.

### D4 — Domain-expert content authoring is allowed in parallel

F-44 (premium rule libraries) is plugin-shape pure content: `.intent/rules/` overlays authored by compliance domain experts (GxP, IEC 62304, EU AI Act Article 9, PCI-DSS, SOC 2). This work has zero engineering capacity overlap with the 5+3 list. If a compliance consultant is engaged to author a pack while engineering ships F-10 or F-40, that engagement is allowed under this ADR.

Authoring a rule pack is *content engineering* in the same sense legal drafting is content engineering: it requires expertise, but not the same expertise as the open-base feature work. The exclusion in D1 governs *software-engineering* capacity on commercial features.

D4 carves out content authoring; it does NOT carve out software work to support pack distribution (e.g., a CLI subcommand to manage pack overlays). Such software work, if needed, falls under D1 and is deferred.

### D5 — Exit criteria are checked against §Context's table, not interpreted

The constraint in D1 relaxes when all eight items in the §Context "5+3 list" table are satisfied per their stated "what done looks like" column. The check is mechanical:

- For the five feature items: the F-NN entry in `papers/CORE-Features.md` carries `status: shipping`. For F-40 and F-41/F-42/F-43, the additional "non-code instantiation exists" / "sidecars can attach without private hooks" sub-criteria are also satisfied and documented in the planning doc.
- For the three quality items: the planning doc `CORE-Operational-Completeness.md` records the date the criterion was first met and the date sustained satisfaction was confirmed (for criteria with a sustained-window requirement).

When all eight items show satisfied state in the planning doc, the governor authors a follow-on ADR (or amends this one) declaring the constraint relaxed and authorizing commercial engineering work to begin. The relaxation is an explicit governance act, not an automatic state transition — the governor confirms before commercial work starts.

### D6 — Sequencing inside the 5+3 list

This ADR does not prescribe ordering inside the list, but the dependency graph constrains it:

- F-41 ships first (F-42 and F-43 depend on it).
- F-42 and F-43 can land in parallel after F-41.
- F-10, F-27, F-40, F-48 are independent of the F-41 trio and each other (per the graph). They can ship in any order driven by leverage and engineering velocity.
- The three quality goals are advanced by every shipping feature; they cannot be sequenced independently.

The planning doc carries the current best estimate of internal ordering and is updated as engineering signal arrives. The internal ordering is operational, not constitutional.

### D7 — The constraint is durable; constitutional relaxation is forward-only

D1's constraint is not interim. It is the operational expression of ADR-084 D7 §1 ("completeness as constitutional commitment") and persists until exit criteria in D5 are met. The governor may amend this ADR (per D3 customer-pulled exception, or any other compelling reason), but amendment requires written justification on the ADR's footing, not a verbal redirection.

The reverse — relaxing the constraint after exit criteria are met, then re-tightening it later — is not foreclosed; if the open base regresses (e.g., a feature transitions back from `shipping` to `partial`), the governor may re-impose this constraint. The point is that *relaxation is constitutional*, on the same footing as the original imposition.

---

## Consequences

### Closes the strategic-priority drift risk

Without this ADR, the most likely failure mode after ADR-083/084 was: the four commercial stampings get treated as new engineering work, F-44 gets prioritised because it's "lowest friction," and incremental commercial work absorbs capacity that should have gone to F-10/F-40/F-48. This ADR makes that drift explicitly out-of-policy, with a constitutional bar to crossing.

The drift risk is real because the four commercial features are concrete, the open-roadmap features (F-10, F-40, F-41–F-43, F-48) are larger and more architectural. Concrete-and-fast usually beats large-and-architectural in operator attention; the constraint here is designed to override that attention bias.

### Re-prioritises the open roadmap explicitly

The previous answer to "what open features should we prioritise?" (the session that produced this ADR's chain) ordered F-10, F-27, then F-41/F-42/F-43. With ADR-084 elevating F-40 and ADR-085 locking the constraint, the operational priority becomes:

- **Tier-1 (any can ship next, choose by velocity):** F-10, F-40, F-48 (each unblocks a distinct downstream surface)
- **Tier-2 (F-41 first, then F-42 + F-43 in parallel):** the extension-interfaces cluster
- **Tier-3 (finishing touches alongside the above):** F-27 promotion, docs polish, demo reliability, signal-quality verification

This ordering lives in the planning doc and is updateable; the *constraint* in D1 is the constitutional part.

### Defers F-44 explicitly

F-44 is the only commercial feature with no hard blocker (F-04 and F-05 ship). ADR-083 §Consequences and ADR-084 §Consequences both pointed at F-44 as the first SKU candidate. This ADR explicitly defers the *software* work on F-44 (loader hooks, CLI subcommand for pack management, if needed) until exit criteria are met. D4 permits parallel *content* authoring by domain experts.

The deferral is not a reversal of the first-SKU argument; it is a recognition that "first SKU" means *first commercial engineering work after the open base is complete*, not *first work overall*. The deferral does not weaken the F-44 case — it strengthens it, because by the time F-44 software work starts, the open base will be operationally complete and the commercial conversation will be honest.

### Makes the GitHub surface declarative

A label (`goal:operational-completeness`) applied to the seven gate issues (F-10 #384, F-27 #401, F-40 #414, F-41 #415, F-42 #416, F-43 #417, F-48 #527) provides a single-filter view. The session-protocol surface in `planning/SESSION-PROTOCOL.md` should reference this label as the canonical "what to pick next" filter while the constraint is active.

The Project #6 Shape field (added in the prior session) is also informative: filtering Project #6 for `Sourcing: open` AND `Status != shipping` returns approximately the same set as the label filter, with F-27 as the only delta (F-27 is partial, not roadmap, so it shows up in Project #6 with `Feature Status: partial` rather than `roadmap`).

### Tracks the three quality goals where the registry doesn't

The three quality goals are tracked in `planning/CORE-Operational-Completeness.md` because the registry has no concept for "system properties that emerge from many features working together." The planning doc carries per-item status, the date the criterion was first met (if applicable), and the verification path. The planning doc is the operational surface; this ADR is the constitutional surface.

### Does not change ADR-083 or ADR-084

ADR-083 stamps four commercial features; that stamping stands. ADR-084 defines the three-shape taxonomy and four honesty commitments; those stand. This ADR adds the operational discipline that makes ADR-084 D7 §1 enforceable. No supersession; pure extension.

### Surfaces the F-19 verification question

D5's exit criterion for "signal quality" assumes the F-19 convergence metric is querying honest data. Before the constraint relaxes on this criterion, the metric query itself needs verification: is the resolution-rate / creation-rate calculation correct, are the time windows aligned, are abandoned findings handled coherently. This verification is part of advancing the signal-quality criterion and is in scope for engineering capacity under D1.

If verification reveals that F-19 reports unreliably, the criterion may need refinement before it can be a gate. That refinement is a planning-doc update, not an ADR amendment, as long as the *intent* (open base demonstrates self-convergence) remains constant.

---

## Verification

- This ADR exists at `.specs/decisions/ADR-085-open-operational-completeness-as-engineering-sole-goal.md`.
- `.specs/planning/CORE-Operational-Completeness.md` exists and carries the 5+3 list with per-item status.
- GitHub label `goal:operational-completeness` exists.
- The label is applied to issues #384 (F-10), #401 (F-27), #414 (F-40), #415 (F-41), #416 (F-42), #417 (F-43), #527 (F-48).
- A `gh issue list --label goal:operational-completeness --state open` query returns exactly those seven issues.
- This ADR is referenced from `papers/CORE-Features.md` §1 (or §3) as the operational binding of the constitutional commitment.
- A future change-set that touches commercial-feature engineering carries either (a) an ADR amendment to this one citing D3 customer-pulled exception, or (b) explicit declaration that the exit criteria in D5 are met. Absent either, the change is out-of-policy.

---

## References

- ADR-084 — three-shape taxonomy + four honesty commitments. This ADR makes D7 §1 (completeness) operationally enforceable.
- ADR-083 — stamps F-44–F-47. The engineering work on those features is explicitly deferred by D1.
- `papers/CORE-Features.md` §1 — the constitutional commitment on the open/commercial line. This ADR sits on equal footing for operational scope.
- `papers/CORE-Features.md` §3 entries for F-10, F-27, F-40, F-41, F-42, F-43, F-48 — the five feature commitments enumerated in §Context.
- `papers/CORE-Product-Tiers.md` §2 — the adoption funnel that depends on a complete open base.
- `planning/CORE-Feature-Dependency-Graph.md` — the dependency picture that makes the structural-vs-strategic distinction concrete.
- `planning/CORE-Operational-Completeness.md` — the per-item operational surface this ADR codifies the discipline for.
- Memory `feedback_hardening_over_coverage` — the existing project preference that maps onto this ADR: hardening live constitutional violations and operational completeness wins over authoring more contract surface or speculative commercial work.
- Memory `feedback_governance_debt_share_inversion` — the long-run metric this ADR's constraint helps preserve: the ratio of "open base completeness" to "commercial reliance" is the signal of whether open-core stays honest.
