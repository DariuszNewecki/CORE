# ADR-049 — Restore parity between architectural doctrine and enforced rules

**Status:** Accepted
**Date:** 2026-05-15
**Authors:** Darek (Dariusz Newecki)
**Closes:** none directly
**Relates to:** CORE-Mind-Body-Will-Separation paper (§5.4, §6, §7.2),
ADR-047 (precedent for retiring/tightening enforcement-engine mismatches),
2026-05-15 static architecture review (initial), 2026-05-15 full
architecture audit (verification pass)

---

## Context

CORE's constitution exists on two surfaces:

- **`.specs/papers/`** — architectural reasoning. Human-authored, normative
  in tone, stated with categorical language ("no exceptions", "MUST NOT",
  "constitutionally prohibited").
- **`.intent/enforcement/mappings/`** — enforced rules. Machine-readable,
  scoped, with explicit `forbidden:` and `excludes:` lists. These are what
  the audit pipeline actually checks.

A 2026-05-15 static architecture review found that the code violates the
paper in several places, and on inspection every "violation" passes audit
because the corresponding enforced rule is narrower than the paper claims.
A subsequent full architecture audit (same date) verified all findings
against live file and rule state.

The code is compliant with the *rules*. The *rules* are not faithful to
the *paper*. CORE governs what it was told to govern; the doctrine that
sits above the rules is decorative unless the rules enforce it.

### Engine constraint (verified 2026-05-15)

`ast_gate import_boundary` (`import_boundary.py:233–261`, `_matches_pattern`)
supports three match modes only — **no wildcard or glob support**:

1. Exact match: `import_path == pattern`
2. Pattern-is-prefix: `import_path.startswith(pattern + ".")`
3. Import-is-prefix-of-pattern: `pattern.startswith(import_path + ".")`

A `forbidden:` entry of `will` therefore matches `will.autonomy`,
`will.tools`, `will.agents`, and every other `will.*` descendant via
Mode 2. Entries like `will.*` are taken literally and will never match.
All rule entries in this ADR use the bare-prefix form accordingly.

`TYPE_CHECKING` imports are skipped by the engine. Inline and
function-body imports are walked.

### Evidence (verified 2026-05-15)

**Paper §7.2 — "Shared imports nothing from `src/mind/`, `src/body/`, or
`src/will/`. There are no exceptions to this test."**

Rule `architecture.shared.no_layer_imports` exists in
`layer_separation.yaml` as `ast_gate import_boundary` and forbids
`src.mind`, `mind`, `src.body`, `body`, `src.will`, `will`. The rule
is correctly structured. However it carries 8 `excludes:` entries,
labelled in the YAML as "TEMPORARY — violations pending remediation":

- `src/shared/infrastructure/storage/file_handler.py` — imports
  `body.governance.intent_guard` and `mind.governance.violation_report`
  at runtime (lines 17–18).
- `src/shared/infrastructure/context/service.py` — lazy-imports
  `body.services.service_registry` inline at line 79.
- `src/shared/infrastructure/repositories/refusal_repository.py` —
  re-export shim importing `body.infrastructure.repositories.refusal_repository`
  (line 20).
- `src/shared/infrastructure/repositories/decision_trace_repository.py` —
  re-export shim importing `body.infrastructure.repositories.decision_trace_repository`
  (line 20).
- `src/shared/infrastructure/vector/cognitive_adapter.py` — imports
  `will.orchestration.cognitive_service` inside `TYPE_CHECKING` (line 21;
  engine skips this; paper §7.2 has no TYPE_CHECKING carve-out).
- `src/shared/infrastructure/service_registry.py` — excluded.
- `src/shared/infrastructure/bootstrap_registry.py` — excluded.
- `src/shared/workers/base.py` — excluded.

The rule structure is correct. The gap is the excludes list: the paper
admits no exceptions; the rule grants eight. Each exclude is a named
paper violation currently given rule-level amnesty without a closure plan.

**Paper §5.4 — "Body → Will is constitutionally prohibited."**

Rule `architecture.layers.no_body_to_will` (`layer_separation.yaml:244–259`)
forbids exactly four sub-paths: `will.agents`, `will.orchestration`,
`will.workers`, `will.self_healing` (and `src.` variants). The rest of
`will/` is silently permitted. Verified violations not caught by the rule:

- `src/body/atomic/proposal_lifecycle_actions.py:25` — imports
  `will.autonomy.proposal.ProposalStatus`. `will.autonomy` not in
  forbidden list.
- `src/body/infrastructure/bootstrap.py:60` — imports
  `will.tools.architectural_context_builder`. `will.tools` not in list.
- `src/body/infrastructure/bootstrap.py:63` — imports
  `will.tools.module_anchor_generator`. Same gap.
- `src/body/infrastructure/bootstrap.py:64` — imports
  `will.tools.policy_vectorizer`. Same gap.

(`src/body/services/service_registry.py:42` imports
`will.orchestration.cognitive_service` which IS forbidden, but the
import is inside `TYPE_CHECKING` — engine skips it. Out of scope here.)

**Paper §6 — "API components MUST NOT access infrastructure directly."**

Rule `architecture.api.no_direct_database_access` forbids only
`shared.infrastructure.database.session_manager.get_session` and
`get_db_session`. Other `shared.infrastructure.*` imports are unguarded.
The full audit confirmed no additional `shared.infrastructure` violations
in `src/api/` beyond what was already known — the boundary holds in
practice for repositories and services via `api/dependencies.py`. The
paper's categorical claim ("MUST NOT access infrastructure directly")
overstates what is enforced and what is architecturally intended.

### Why this matters

When the paper is stricter than the rules:

- Code drifts toward the rules' actual line, not the paper's stated line.
- New code is written against the paper, then silently passes audit
  because the rule permits what the paper forbids.
- The next architecture review finds the same gap in different files
  because the rules have not changed.

This is **doctrine-rule drift** — the meta-loop failure. CORE enforces
what its rules say; the rules are not in lockstep with the doctrine that
motivates them.

---

## Options considered

**Option A — Tighten the rules to match the papers.** Rewrite every
`ast_gate` rule to enforce the full paper statement, with `excludes:`
entries for currently-violating files pending refactor.

**Option B — Soften the papers to match the rules.** §7.2's "no
exceptions" becomes "no exceptions except those listed in
`excludes:`." §5.4 and §6 receive the same treatment.

**Option C — Mixed: tighten where the refactor is bounded, soften where
it is not.** Decide per boundary based on violation count and refactor
cost.

**Option D — Status quo.** The next review finds the same gap.

---

## Decision

### D1 — Adopt Option C per boundary

| Boundary | Current state | This ADR's verdict |
|---|---|---|
| §7.2 Shared layer independence | Rule exists (`architecture.shared.no_layer_imports`). 8 files in `excludes:` with no closure plan. | **Close the excludes list.** The rule structure is correct. Each of the 8 excluded files requires a closure ADR per D3. No new `excludes:` entries may be added without a simultaneous closure ADR. |
| §5.4 Body → Will | `no_body_to_will` covers only 4 `will.*` sub-paths. 4 violations pass undetected. | **Tighten.** Expand `forbidden:` to bare prefixes `will` and `src.will` (Mode 2 prefix match covers all descendants). Add `excludes:` for the 4 known violating files, each with a closure ADR per D3. |
| §6 API infrastructure access | `no_direct_database_access` covers DB sessions only. Paper claims broader prohibition. | **Soften paper, keep rule.** Amend §6 to replace "MUST NOT access infrastructure directly" with "MUST NOT access database sessions directly; MAY use sanctioned shared repositories and services through `api/dependencies.py` and named providers." Route-via-Will use-case layer recorded as architectural debt requiring its own ADR before it can become enforceable. |

### D2 — Establish doctrine-rule parity as a standing discipline

Every paper that makes a normative statement about imports, layer
boundaries, or component responsibilities must name the rule that
enforces it, or explicitly mark itself as aspirational. Required form,
in the paper, immediately under each normative claim:

> *Enforced by `<rule_id>` (`<rule_path>`). See `excludes:` for
> documented exceptions.*

or

> *Aspirational. No rule currently enforces this; see ADR-XXX for the
> architectural debt and planned enforcement.*

This is documentation discipline enforced at governor sign-off, not
by tooling.

### D3 — Each excludes entry must reference a closure ADR and carry a deadline

Any addition to an `excludes:` list — whether existing or new — requires
a companion document in `.specs/decisions/` naming: the file, the rule
it bypasses, the reason the bypass is temporarily accepted, the planned
refactor that will remove the entry, and a **deadline date** by which
the entry must be closed.

The deadline is enforced in two stages:

- **Warning:** audit emits a warning for any `excludes:` entry whose
  deadline has passed but whose closure ADR is not marked accepted.
- **Blocking:** after a grace period of 30 days past deadline, the
  entry is treated as a rule violation — the file fails audit as if
  it were not excluded.

The excludes list is not a parking lot. "TEMPORARY" without a date is
not temporary; it is permanent with good intentions. A named deadline
converts intent into a governance commitment.

---

## Consequences

### Positive

- **Doctrine and law re-aligned per boundary.** The paper either states
  what the rule enforces, or names itself as aspirational with a tracked
  path to enforcement.
- **"Exception creep" becomes an explicit, named list.** Each `excludes:`
  entry is tied to a closure ADR. The list has a floor of zero and cannot
  grow without a recorded justification.
- **Future architecture reviews stop re-finding the same gap.** A diff
  against the rules surfaces drift; doctrine review is no longer the
  only detection mechanism.
- **Sets precedent for the meta-loop.** ADR-047 retired one rule by
  matching engine to question shape. This ADR retires a class of silent
  doctrine-rule mismatches by matching rule reach to paper claim.

### Negative

- **Refactor cost on the tightening side.** The Body→Will expansion and
  the shared excludes closure each require real refactor work or real
  closure ADRs. `file_handler.py` importing from both `body` and `mind`
  is not a one-line move.
- **Softening §6 is a doctrinal concession.** Recording "API → Will
  use-case layer" as debt rather than enforced law means the API surface
  remains a partial application service layer for some time. Honest
  framing is preferable to the current state, but it is a concession.
- **D2 is load-bearing documentation discipline.** There is no tool
  that catches a missing rule citation in a paper. This depends on
  governor sign-off at the point a normative paragraph is authored.

### Long-horizon direction

`shared/` as a substrate layer carries a known long-term risk: logic
creeps in because it is the path of least resistance, and the layer
becomes an informal composition root. The 8 excludes entries are the
current symptom. The direction this ADR points toward — but does not
enforce — is contraction of `shared/` to pure contracts: interfaces,
data types, constants, and nothing that depends on a layer. Any module
in `shared/` that currently contains logic or service calls belongs in a
layer; the re-export shims are the clearest examples. This is a
multi-ADR effort on a longer horizon than D1–D3; it is named here so
future architecture reviews treat it as a known trajectory, not a new
finding.

### Neutral

- The audit verdict changes the moment D1's Body→Will tightening lands.
  Files that were silently passing will fail until fixed or excluded.
  This is correct; it is also a one-time visible jump in findings count.
- The `architecture.shared.no_layer_imports` rule requires no structural
  change — only the closure ADR process (D3) applied to its existing
  8 excludes entries.

---

## Verification

This ADR is verified when, after D1 + D2 + D3 land:

1. **The `shared/` excludes list is closed or each entry has a closure
   ADR.** All 8 currently-excluded files either (a) no longer import
   across layer boundaries, or (b) have a D3-compliant closure ADR
   filed and linked from the `excludes:` entry in the YAML.

2. **`architecture.layers.no_body_to_will` covers all of `will/`.**
   The `forbidden:` block contains `will` and `src.will` (bare prefix
   form). `proposal_lifecycle_actions.py` and the three `bootstrap.py`
   imports are either refactored or in `excludes:` with closure ADRs.

3. **The Mind/Body/Will Separation paper §6 is amended** to replace
   the "MUST NOT access infrastructure directly" claim with the
   narrower DB-session statement, with a forward reference to the
   architectural debt ADR for the API → Will use-case layer.

4. **A full audit run reports the expanded `no_body_to_will` rule
   executing** (visible in audit log as `ast_gate.import_boundary`
   against the expanded forbidden list). Findings are either zero or
   match the `excludes:` list one-for-one.

A single full audit cycle after D1 changes land satisfies criterion 4.

---

## References

- `.specs/papers/CORE-Mind-Body-Will-Separation.md:§5.4` — Body → Will
  prohibition.
- `.specs/papers/CORE-Mind-Body-Will-Separation.md:§6` — API layer
  boundary (the claim this ADR proposes to soften).
- `.specs/papers/CORE-Mind-Body-Will-Separation.md:§7.2` — Shared
  admission test, "no exceptions."
- `.intent/enforcement/mappings/architecture/layer_separation.yaml:244–259` —
  `architecture.layers.no_body_to_will` (narrow 4-sub-path version).
- `.intent/enforcement/mappings/architecture/layer_separation.yaml` —
  `architecture.shared.no_layer_imports` (rule exists; 8 excludes
  pending closure).
- `src/mind/logic/engines/ast_gate/checks/import_boundary.py:233–261` —
  `_matches_pattern`: prefix-only matching, no wildcard support.
- `src/shared/infrastructure/storage/file_handler.py:17–18` — body +
  mind imports from shared (excluded, closure ADR required).
- `src/shared/infrastructure/context/service.py:79` — inline body
  import from shared (excluded, closure ADR required).
- `src/shared/infrastructure/repositories/refusal_repository.py:20` —
  body re-export shim (excluded, closure ADR required).
- `src/shared/infrastructure/repositories/decision_trace_repository.py:20` —
  body re-export shim (excluded, closure ADR required).
- `src/body/atomic/proposal_lifecycle_actions.py:25` — body imports
  `will.autonomy.proposal` (not caught by current rule).
- `src/body/infrastructure/bootstrap.py:60–64` — body imports
  `will.tools.*` (not caught by current rule).
- ADR-047 — precedent for engine/rule realignment.
- 2026-05-15 static architecture review — original surfacing.
- 2026-05-15 full architecture audit — verification of all findings
  against live state; source of engine constraint confirmation.

## Amendment — 2026-05-27 (CCC #463)

**Scope broadened by CORE-Governance-Topology Row 3 (2026-05-26).**

D2 as written required rule citation only for normative paper claims about
imports, layer boundaries, or component responsibilities. CORE-Governance-Topology
Row 3 (accepted 2026-05-26) operationalizes the same Paper → Rule constitutional
direction but applies it to ALL normative paper §s, using the normative-marker
detection at `.intent/enforcement/config/normative_markers.yaml`. The narrow
scope in D2 above is the original framing; the current constitutional bar is
the broader Topology Row 3 reading. Scanner gate: ROW3_CITATION per ADR-073 D6.

CCC SAMECONCERN candidate `d571a2d2-614b-45d0-9f21-805432cc61d8` surfaced this
scope gap. Topology Row 3's "(existing ADR-049 D2)" parenthetical was
accidental — it inherited the broader reading as if D2 already covered it.
Corrected in the companion edit to "(extends ADR-049 D2)."
