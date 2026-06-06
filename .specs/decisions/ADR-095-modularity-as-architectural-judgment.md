<!-- path: .specs/decisions/ADR-095-modularity-as-architectural-judgment.md -->

# ADR-095 — Modularity family as architectural-judgment, role-declared sanctuary

**Date:** 2026-06-06
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-06 — drafted under explicit "write that ADR" confirmation at the close of a triage thread that surfaced the modularity mess as a coherent family problem rather than per-finding noise. The governor explicitly asked for the full rule inventory before drafting; the decisions below are scoped against that inventory, not against the single triage case (`3703c54a`) that opened the thread.)
**Grounding decisions:** ADR-006 (alignment of `needs_split` with its statement). ADR-007 (class-too-large lives inside the class, not in the file split). ADR-042 D3/D4 (per-file exemption register pattern + the `unix_philosophy` retirement promise this ADR amends). ADR-068 (principal role taxonomy — `resolution_authority: principal.governor` lands as a first-class finding-payload field per D4 below). ADR-093 D7 (sanctuary posture: visible-but-stable governance debt defers; this ADR generalizes the posture for modularity findings). ADR-094 D6 (URS-line precedent: deterministic-judgment instruments are governor-routed, not autonomous).
**Related:** #306 (the `modularity.unix_philosophy` LLM gate path, dormant; D5 below formally amends ADR-042 D4's retirement commitment). #579 (BlackboardPublisher extraction — Worker's modularity sanctuary entry from earlier this session; D3's migration applies). #580 (`fix.modularity.remediates` coherence gap — D4 below closes the ghost-rule half; #580 remains open for the cross-surface schema discipline question). The triage thread that opened this work: proposal `3703c54a-3141-43d5-afd0-8adc19a9e951` (rejected 2026-06-06).

---

## Context

A single triage case (`fix.modularity` proposal on `coherence_service.py`) opened into a family audit that surfaced multiple stacked problems in the modularity rule cluster:

1. **Over-routing.** `fix.modularity` (a file-splitter action) is the dispatch target for six rules across two namespaces: `modularity.needs_split`, `modularity.class_too_large`, `modularity.needs_refactor`, `purity.no_ast_duplication`, `purity.no_semantic_duplication`, `purity.no_orphan_files`. Three of these (the modularity trio's non-split members + the purity trio) cannot be honestly handled by a file-splitter.
2. **Rule-statement-vs-dispatch contradiction.** `modularity.class_too_large`'s own rule statement says *"Autonomous mechanical redistribution is not permitted for this class of finding"*, yet `auto_remediation.yaml` routes it to autonomous mechanical redistribution. `modularity.needs_refactor` says *"cannot be resolved by mechanical splitting alone"*, yet routes to mechanical splitting.
3. **Ghost `remediates` declaration.** `fix.modularity` self-declares `remediates=[architecture.max_file_size, modularity.refactor_score_threshold, modularity.single_responsibility, modularity.import_coupling, modularity.semantic_cohesion]` — all five rules are absent from `.intent/rules/`. The action's self-declared scope is fictional.
4. **Two parallel sanctuary registers requiring hand-sync.** `modularity.needs_split.scope.excludes` (inline path list) and `modularity.class_too_large.governed_exclusions` (structured register). Files that need sanctuary against both must be registered in both. The rule_extractor merges `governed_exclusions` only into the rule it's declared under. The 11-entry register works today partly by accident of `check_needs_split`'s defensive filter (`responsibility_count ≤ 2 AND dominant_class ≤ limit`); when the filter changes, sanctuary breaks silently.
5. **LOC measures shape, not intent.** The family enforces "is this file/class doing too much?" through LOC thresholds. LOC is a shape proxy for a cohesion-of-responsibility property. The proxy fails on legitimate cross-cutting facades (`IntentRepository`, `BlackboardService`, `CoherenceService`, `Worker` — all sanctuary entries). The growing sanctuary register IS the failure signal.
6. **Stubbed LLM gate.** `modularity.unix_philosophy` (the LLM gate that ADR-042 D4 named as the eventual replacement for the LOC stack) is stubbed per #306. The "comes online" commitment has held the family in a transitional posture longer than planned.

The cumulative shape: a rule family that pretends to have mechanical fixes, contradicts its own rule statements at the dispatch layer, declares fictional rules in action metadata, grows a parallel sanctuary list every time a legitimate facade is flagged, and waits on an LLM gate that hasn't shipped. **Each piece can be patched in isolation; the family as a whole needs to be honest about what it is.**

The honest framing: **modularity is architectural judgment, not mechanical fix.** The rules surface candidates for governor review. They do not have autonomous remediation paths. Sanctuary is declared on the artifact (where the role lives), not in parallel YAML lists.

---

## Decisions

### D1 — Modularity rules are architectural-judgment; no autonomous remediation

The four `modularity.*` rules (`needs_split`, `class_too_large`, `needs_refactor`, `unix_philosophy`) shall be classified as architectural-judgment findings. Their findings carry `resolution_authority: principal.governor` (per D4 below) and are routed to the governor dashboard for triage. **None** of them route to `fix.*` actions via the autonomous remediation pipeline.

This includes `modularity.needs_split` — despite its rule statement claiming "mechanical redistribution." The triage that opened this ADR demonstrated that even `needs_split`'s defensive filter cannot reliably distinguish a split-candidate from a legitimate facade (CoherenceService slipped through). The honest posture is that LOC-derived findings always need human judgment about whether the flagged file is a problem at all.

`fix.modularity` itself is not deleted. It is retained as a **governor-invoked CLI tool** (`core-admin tools fix-modularity <file>`) for cases where the governor decides splitting is the right move. The action keeps its two-phase LLM analysis + Logic Conservation Gate. It just stops being the autonomous remediator's target.

### D2 — Drop the six modularity / purity routings from `auto_remediation.yaml`

The following six routings are removed from `.intent/enforcement/remediation/auto_remediation.yaml`:

- `modularity.needs_split → fix.modularity`
- `modularity.class_too_large → fix.modularity`
- `modularity.needs_refactor → fix.modularity`
- `purity.no_ast_duplication → fix.modularity`
- `purity.no_semantic_duplication → fix.modularity`
- `purity.no_orphan_files → fix.modularity`

The first three are the modularity rules covered by D1. The latter three are cross-namespace misroutings — purity findings (duplication, orphans) cannot be honestly resolved by a file-splitter. They are reclassified as architectural-judgment in the same posture: governor-routed, no autonomous fix. (`purity.no_dead_code → fix.vulture_heal` remains; that routing is coherent.)

The two purity duplication rules and `purity.no_orphan_files` were named in the carry-forward thread as dispatch gaps. This ADR resolves them by **acknowledging there is no autonomous fix** rather than building one. If a future ADR ships a real dedup or orphan-resolver action, those routings may re-land — but as honest declarations, not as a "point everything at `fix.modularity`" default.

### D3 — File-level `CORE_ROLE` declaration replaces both sanctuary registers

Files whose architectural role legitimately exempts them from LOC-derived modularity rules shall declare that role as a **module-level constant** at file head:

```python
CORE_ROLE = "facade"  # or "algorithm" | "catalog"
```

The constant lives near the file's `__all__` (top of module body, after imports). It is AST-readable (`ast.Assign` node, target name `CORE_ROLE`, value a `Constant[str]`).

The closed role vocabulary at first ship is:

- **`facade`** — cross-cutting single gateway for one consumer's set of operations (IntentRepository, BlackboardService, CoherenceService, CrawlService, SystemContextGatherer, Worker, IntentInspector, FileRoleDetector).
- **`algorithm`** — cohesive multi-stage algorithm whose stages share intermediate state and have one consumer (ContextBuilder).
- **`catalog`** — declarative catalog of homogeneous entries, one responsibility (PathResolver, OperationalConfig).

The modularity rule engines (`check_needs_split`, `check_class_too_large`, future `check_unix_philosophy`) skip files declaring `CORE_ROLE` ∈ `{facade, algorithm, catalog}`. The role itself is the declaration of why the LOC rule does not apply.

**Role choice is governor-authorized.** A file declaring `CORE_ROLE` for the first time, or changing its declared role, requires the same review surface as any other governance-shaping change. The role is not a hide-the-finding switch the autonomous loop can apply.

Rationale for role declaration over the existing register:

- **Single source of truth.** The role lives on the artifact. No parallel YAML list to keep synchronized with the file.
- **Role is load-bearing where it's declared.** The maintainer touching `CoherenceService` sees `CORE_ROLE = "facade"` at the top of the file. The register required a parallel lookup.
- **Drift is impossible.** A file with `CORE_ROLE` declared is exempt; without it, not. There is no "in one register but not the other" failure mode.
- **Discoverable via introspection.** Tooling can ask "what are CORE's facades?" by AST-walking `src/`. The register required loading governance YAML.

The two existing registers — `modularity.needs_split.scope.excludes` (inline) and `modularity.class_too_large.governed_exclusions` (structured) — are emptied (paths only; `tests/**` / `scripts/**` / `**/__init__.py` patterns stay) and slated for full retirement after migration (D5 below tracks the cleanup).

### D4 — Modularity findings carry `resolution_authority: principal.governor`

Per ADR-068's principal role taxonomy, every modularity-family finding (the four rules in D1, plus the three purity rules reclassified in D2) shall carry `resolution_authority: principal.governor` in its payload. This makes the routing explicit at the **data layer** — the autonomous remediator filters findings by `resolution_authority` and never picks up architectural-judgment subjects.

This is the codification half of D1. D1 says "no autonomous remediation"; D4 says "the data declares this so the routing is mechanical, not by hope." If a future autonomous remediator config drops the `resolution_authority` filter, the routing breaks loudly (data carries it) rather than silently (only YAML carries it).

### D5 — Ghost `remediates` corrected; `fix.modularity.remediates` resets to empty; #580 narrows to schema discipline

`fix.modularity`'s `@register_action(... remediates=[...])` declaration shall be updated in the same change-set to:

```python
remediates=[]  # Governor-invoked CLI tool only (ADR-095 D1).
```

The five ghost rule IDs are removed. The empty list reflects D1's truth: the action no longer claims any rule as autonomous-fix target.

This closes one half of #580 (the action's self-declaration is no longer fictional). The remaining half — the cross-surface discipline ensuring `auto_remediation.yaml` and action `remediates` cannot drift in the future — stays in #580's scope as a schema/audit question separable from this ADR.

### D6 — `modularity.unix_philosophy` LLM gate (#306) formally deferred; successor path is agentic invocation, not the gate

ADR-042 D4 named the `unix_philosophy` LLM gate as the eventual replacement for the LOC stack. That commitment is amended.

The LLM gate (yes/no single-shot prompt/response verdict, the shape #306 named) is not the right mechanism for architectural judgment. A yes/no gate cannot distinguish a facade from a God Object any more reliably than the LOC heuristic it was meant to retire — the verdict surface is too narrow for the question. The real successor capability is **agentic invocation**: CORE invokes an external reasoning model (the agent reads the finding, the file, the surrounding architectural context, and produces a decision among `split | sanctuary | refactor | refuse`, either acting or escalating). That capability is separate from #306's gate; it is the shape this family's autonomous-judgment story re-enters under.

This ADR does not ship that capability. It commits the family to architectural-judgment posture (D1 + D4) until that capability is real. #306 remains open with its scope shifted from "ship the LLM gate" to "the gate's design was the wrong mechanism for architectural judgment; the right successor is agentic invocation, scoped separately." A future ADR for the agentic path is a sibling of this one.

---

## Phasing

The migration is small and linear. One change-set:

1. **Edit `auto_remediation.yaml`** — remove the 6 routings per D2.
2. **Edit `modularity_fix.py`** — `remediates=[]` per D5.
3. **Migrate 11 files** — add `CORE_ROLE = "facade" | "algorithm" | "catalog"` per D3, mirroring the existing register's `category` field. Path mapping per the verification section below: 6 `facade`, 3 `algorithm`, 2 `catalog`.
4. **Edit modularity check engines** — `check_needs_split` and `check_class_too_large` skip files where `CORE_ROLE` is declared in the closed vocabulary.
5. **Empty the two sanctuary registers** — `modularity.needs_split.scope.excludes` drops the 3 facade paths (`tests/**` / `scripts/**` / `**/__init__.py` stay); `modularity.class_too_large.governed_exclusions` empties to `[]` (the per-file entries migrate to `CORE_ROLE` declarations; the register's schema stays in case it's needed for non-`CORE_ROLE` carve-outs).
6. **Add finding-emission `resolution_authority: principal.governor`** to the modularity rule engines per D4.

Steps 1–6 ship as one PR. No multi-phase rollout. The change is bounded (11 files + 2 engines + 1 action + 1 YAML).

---

## Consequences

### The autonomous-remediation pile for modularity stops growing

Today's dashboard shows 175 indeterminate inbox items, several of which are modularity proposals like `3703c54a`. After this ADR ships, modularity findings stop reaching the autonomous remediator entirely. The 175 figure decreases proportionally. The carry-forward "175 indeterminate" thread narrows.

### Two parallel sanctuary registers die; one in-file declaration replaces both

The brittleness named in the post-triage debt observation (the convention requiring hand-sync between `needs_split.scope.excludes` and `class_too_large.governed_exclusions`) is structurally resolved by D3. Future facades self-declare via `CORE_ROLE`; the registers no longer accumulate entries.

### `fix.modularity` becomes a governor tool

The action survives. Its surface narrows: callable from CLI under governor authority, not from the autonomous loop. The two-phase LLM analysis + Logic Conservation Gate remain. The action's `remediates=[]` declaration honestly reflects its new posture.

### Three purity rules become architectural-judgment

`purity.no_ast_duplication`, `purity.no_semantic_duplication`, `purity.no_orphan_files` move from "autonomous-fix-attempted-by-misrouting" to "governor-routed architectural judgment." Their findings appear on the dashboard for triage. If a real dedup or orphan-resolver action ships later, those routings can re-land honestly.

### #580 narrows but stays open

The ghost-rules half of #580 closes with D5. The schema-discipline question (how do `auto_remediation.yaml` and action `remediates` declarations stay in sync going forward) remains open as a separable governance-hygiene issue. #580's body gets a forward-pointer to this ADR for the closed half.

### #579 (BlackboardPublisher) is unaffected by this ADR

The Worker extraction tracked in #579 is still real architectural debt. Adding `CORE_ROLE = "facade"` to `workers/base.py` declares the role honestly but doesn't retire the extraction question. Both can land in either order; this ADR doesn't gate #579.

### ADR-042 D4's "retired when unix_philosophy comes online" commitment is amended

The LOC stack is no longer transitional infrastructure waiting for the LLM gate. It is the architectural-judgment-surfacing stack, at rest, with the LLM gate deferred. Future amendments to the LOC stack don't carry the retirement-pending stigma; they are amendments to a stable family.

### The 11 affected files carry visible architectural roles

Reading `coherence_service.py` after this ADR ships, a maintainer sees `CORE_ROLE = "facade"` near the top. The role is documentation that travels with the code. The register required reading governance YAML to discover the same fact.

### Findings carry routing in their data, not just in their YAML

D4's `resolution_authority: principal.governor` makes the architectural-judgment routing a property of the finding itself. The autonomous remediator's filter becomes mechanical (skip findings carrying `principal.governor`); no YAML config edit can accidentally re-route architectural judgment back to autonomous fix.

### D1's "no autonomous" posture is provisional, not permanent

D1 reflects what CORE can honestly do today: mechanical splitters can't tell facades from God Objects, and the LLM-gate shape (#306) was designed for yes/no verdicts that misfit architectural judgment. When CORE gains agentic-invocation capability — an external reasoning model with full conversational context, not a single-shot prompt/response gate — architectural-judgment findings become candidates for autonomous adjudication on a different mechanism per D6. The agent reads the finding, the file, and the surrounding context; produces a judgment among `split | sanctuary | refactor | refuse`; and either acts or escalates. D1 holds the line until that capability ships, then a sibling ADR re-opens autonomous remediation on the agentic path. The `CORE_ROLE` qualifiers (D3) survive that transition — the agent reads them as one input to its judgment, same as a governor does today.

---

## Verification

- This ADR exists at `.specs/decisions/ADR-095-modularity-as-architectural-judgment.md`.
- `.intent/enforcement/remediation/auto_remediation.yaml` no longer contains routings for: `modularity.needs_split`, `modularity.class_too_large`, `modularity.needs_refactor`, `purity.no_ast_duplication`, `purity.no_semantic_duplication`, `purity.no_orphan_files`.
- `src/body/atomic/modularity_fix.py` declares `remediates=[]`.
- 11 files carry `CORE_ROLE = "<facade | algorithm | catalog>"` at module top:
    - `facade`: intent_repository.py, context_gatherer.py, crawl_service/main_module.py, blackboard_service.py, coherence_service.py, workers/base.py.
    - `algorithm`: intent_inspector.py, builder.py, file_role_detector.py.
    - `catalog`: path_resolver.py, operational_config.py.
- `src/mind/logic/engines/ast_gate/checks/modularity_checks.py`'s `check_needs_split` and `check_class_too_large` short-circuit when the target file's AST contains a `CORE_ROLE = "<facade | algorithm | catalog>"` assignment.
- `.intent/enforcement/mappings/code/modularity.yaml` `modularity.class_too_large.governed_exclusions` empties of per-file entries; `modularity.needs_split.scope.excludes` retains only `tests/**`, `scripts/**`, `**/__init__.py`.
- Modularity rule-engine finding emission stamps `resolution_authority: principal.governor` in payload.
- ADR-042 D4 carries an append-only marker per the precedent set in ADR-093 D6: "Note (2026-06-06, per ADR-095): the 'retired when modularity.unix_philosophy comes online' commitment is amended. See ADR-095 D6 for the deferred posture."
- #580 receives a comment noting the ghost-rules half is closed by ADR-095 D5; the schema-discipline half remains in scope.
- #306 receives a comment noting the LLM gate's path shifts from "autonomous adjudication" to "deferred governor-advisory channel" per ADR-095 D6.
- After ship + daemon restart, the next audit cycle produces zero new modularity proposals; existing abandoned modularity findings age out of the dashboard windows normally.

---

## Note — D4 scope extension to `architecture.mind.no_execution_semantics` (2026-06-06, same day as acceptance)

Inbox triage surfaced a sibling case the original D4 scope did not name: `architecture.mind.no_execution_semantics`. Same structural shape as `modularity.unix_philosophy`:

- **`llm_gate` engine** — produces yes/no verdicts at scale on Mind layer files.
- **Pre-selector + LLM gate split** — `architecture.mind.execution_signal` (regex pre-selector) gates the LLM via `requires_findings_from`, identical pattern to `class_too_large` → `unix_philosophy`.
- **Mixed precision in practice** — true positives on real LLM invocations (`assumption_extractor.py`); false positives on `field(default_factory=list)` dataclass declarations and type names matching the pre-selector's `AllowList`/`DenyList` patterns.
- **34 distinct subjects sitting indeterminate at audit-time of this Note** — the third-largest inbox contributor after this ADR's covered rules begin draining.

The D4 architectural-judgment routing applies cleanly. Rule added to `_ARCHITECTURAL_JUDGMENT_RULES` in `audit_violation_sensor.py` (now 8 rules); `auto_remediation.yaml` description updated to reference D6's deferral posture. No new decisions; this is operational scope extension of the existing D4 + D6 frame to a sibling case the original draft missed.

The pre-selector itself (`architecture.mind.execution_signal`) is deterministic regex and remains unchanged — same posture as `modularity.class_too_large` keeping its LOC pre-selector.

If further `llm_gate`-engine rules surface in future triage, they belong in the same set under the same posture. The `llm_gate` engine itself is the marker for "this rule's verdict surface is structurally wrong for autonomous adjudication" until agentic invocation ships.

---

## Note — D2 implementation correction (2026-06-06, same day as acceptance)

D2's wording "remove these routings from `auto_remediation.yaml`" was imprecise — implemented literally, it would violate ADR-066's `governance.remediation.all_rules_mapped` invariant (every active rule must have an entry). The implemented form is functionally equivalent and ADR-066-coherent:

- `modularity.needs_split`: status flipped `ACTIVE → DELEGATE`, confidence dropped `0.85 → 0.40`. This kills the proposal-creation pathway (the ACTIVE status was the harm — it was the routing that created `3703c54a`).
- The other five entries (`modularity.class_too_large`, `modularity.needs_refactor`, `purity.no_ast_duplication`, `purity.no_semantic_duplication`, `purity.no_orphan_files`) were already at `DELEGATE` or `PENDING` status — already governor-routed, not autonomous. Their descriptions were updated to reference ADR-095 D1/D2 so future readers see the architectural-judgment posture by inspection.

The `action: fix.modularity` field remains on the DELEGATE entries as a placeholder satisfying ADR-066's mapping invariant. It is dead documentation in the DELEGATE context (no action runs) but its presence keeps the loader honest. The `fix.modularity.remediates=[]` reset (D5) closes the loop on the action's side.

The verification bullet "no longer contains routings for [the 6 rules]" should be read as "no longer contains ACTIVE routings or routings whose descriptions imply autonomous remediation."

---

## References

- ADR-006 — alignment of `needs_split` with its statement.
- ADR-007 — class-too-large lives inside the class, not in the file split.
- ADR-042 D3/D4 — per-file exemption register + the retirement commitment amended by D6.
- ADR-068 — principal role taxonomy; `resolution_authority` field consumed by D4.
- ADR-093 D6 — append-only amendment precedent applied to ADR-042 D4's marker.
- ADR-093 D7 — sanctuary-vs-retrofit posture (visible-but-stable debt defers); D3 generalizes the posture as in-file declaration.
- ADR-094 D6 — URS-line precedent that deterministic-judgment instruments ship governor-routed, not autonomous; D1 follows the same pattern for LOC-derived findings.
- #306 — `modularity.unix_philosophy` LLM gate (scope amended by D6).
- #579 — BlackboardPublisher extraction (unaffected by this ADR; Worker's `CORE_ROLE = "facade"` is the in-file declaration of the sanctuary posture that issue's scope-deferral relies on).
- #580 — `fix.modularity` `remediates` coherence gap (ghost half closed by D5; schema-discipline half remains).
- Triage case: proposal `3703c54a-3141-43d5-afd0-8adc19a9e951` (rejected 2026-06-06 — the entry point to this ADR's scope).
- Memory `feedback_two_surface_requires_two_structures` — informed D3's in-file declaration over parallel registers.
- Memory `feedback_park_cleanup_when_boundary_works` — informed D6's deferral over recommitting to LLM-gate ship.
- Memory `feedback_layered_authority_three_way_check` — surfaced the rule-statement-vs-dispatch-table contradiction in Context point 2.
- Memory `feedback_hardening_over_coverage` — informed the decision to ship the family-level resolution rather than continue patching per-finding into sanctuary.
- Memory `feedback_audit_findings_feed_remediation` — informed D4's data-layer routing (loop dynamics: stale-finding revival mode breaks when only YAML carries routing).
- Memory `feedback_conviction_signal` — the inventory exercise made conviction available; this ADR commits to the family-level shift rather than another patch.
