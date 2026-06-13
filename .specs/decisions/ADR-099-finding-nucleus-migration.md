---
kind: adr
id: ADR-099
title: 'ADR-099 — Finding-nucleus migration: alias-bridged reconciliation of CheckResult
  and AuditFinding to the canonical contract'
status: superseded
---

<!-- path: .specs/decisions/ADR-099-finding-nucleus-migration.md -->

# ADR-099 — Finding-nucleus migration: alias-bridged reconciliation of CheckResult and AuditFinding to the canonical contract

**Date:** 2026-06-09
**Status:** Retired (2026-06-09) — superseded by **ADR-102**. Only D3 (the `permitted_extensions` clause on the META schema) and migration step 1 (the META schema extension that landed it) survive; everything else — D1 synthetic-worker apparatus, D2 alias bridge, D4 sequencing, D5 verification gates, and migration steps 2–10 — is retired. See Revision C below for the supersession ledger and the reverts that followed. The original draft, Revision A, and Revision B are preserved in place with their existing `> SUPERSEDED` markers per `[[feedback_append_only_amendments_under_review]]`; the audit trail (original draft → Revision A → Revision B → Revision C retirement) stays readable inside the file.
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-09, after #598 triage. ADR-056 D3 committed CheckResult and AuditFinding to the canonical Finding nucleus (`rule_id, severity, subject, evidence, worker_uuid`); implementation has been on incompatible names since the contract bind landed. The contract author left a deliberate dual-contract structure — Finding.json governs CheckResult+AuditFinding for *visibility* of the gap, AuditFinding.json governs AuditFinding for the *actual persistence shape*. The 16 audit findings against `data.contracts.finding_nucleus_conforms` are the gap visible. The five open design questions in #598 — worker_uuid attribution, renames vs aliases, extension allowlist, migration sequencing, pre-migration instrumentation — needed an integrated decision, not piecemeal answers.)
**Grounding paper:** ADR-056 D3 — *"Layer-specific extensions are permitted; nucleus fields are not optional."* The ADR-056 bind is the constitutional commitment this migration honors.
**Related:**
- #598 (the originating issue; this ADR is its requested resolution).
- ADR-056 D3 (the contract bind being reconciled).
- ADR-056 D6 (`SchemaConformanceChecks` is the AST gate that fires the 16 findings being addressed; the rule `data.contracts.finding_nucleus_conforms` lives at `.intent/rules/data/governance.json`).
- ADR-059 D2 (severity vocabulary — `audit_severity` enum already shared across `AuditFinding` and `CheckResult` per AuditFinding.json's note; this ADR does not touch severity).
- ADR-098 D2 (this session's prior ADR — `AuditFinding.context` extensions for aggregate quality gates; D3 of this ADR co-ordinates the `permitted_extensions` clause to include `context` so the two ADRs compose).
- `.intent/enforcement/contracts/Finding.json` v1.1.0 (governs CheckResult + AuditFinding against the nucleus).
- `.intent/enforcement/contracts/AuditFinding.json` v1.0.0 (governs AuditFinding's actual persistence shape; intentionally divergent from Finding.json to make the gap visible).
- `src/shared/models/audit_models.py:43-107` (`AuditFinding` definition; 23 emitter files reference it).
- `src/body/services/cim/models.py:279-293` (`CheckResult` definition; 3 emitter files reference it).
- Memory: `[[feedback_two_surface_requires_two_structures]]` — when one structure is read with semantically different meanings, the unification was the bug. The dual-contract here is the precise opposite move: keep two structures (Finding.json nucleus vs AuditFinding.json persistence) deliberately, bridge them via aliases.
- Memory: `[[feedback_enum_subset_canonicalize_and_fail_closed]]` — the spirit applied to fields: alias for migration, never inline the divergence.

---

## Context

The Finding nucleus contract at `.intent/enforcement/contracts/Finding.json` (v1.1.0) requires five fields on any class claiming to be a constitutional Finding: `rule_id`, `severity`, `subject`, `evidence`, `worker_uuid`. Two classes are governed:

| Class | File | Current fields | Nucleus fields present | Nucleus fields missing | Extension fields |
|---|---|---|---|---|---|
| `CheckResult` | `src/body/services/cim/models.py:279` | `id, severity, rule, evidence, recommendation, links` | `severity`, `evidence` (2/5) | `rule_id`, `subject`, `worker_uuid` (3) | `id, rule, recommendation, links` (4) |
| `AuditFinding` | `src/shared/models/audit_models.py:43` | `check_id, severity, message, file_path, line_number, context` | `severity` (1/5) | `rule_id`, `subject`, `evidence`, `worker_uuid` (4) | `check_id, message, file_path, line_number, context` (5) |

The audit rule `data.contracts.finding_nucleus_conforms` (engine: `ast_gate` per ADR-056 D6's `SchemaConformanceChecks`) fires 16 findings: 7 missing-required (3 + 4), 9 extension-visible (4 + 5). The contract's description language is explicit about the latter: *"extensions to a closed nucleus are drift to be made visible, not silently absorbed."*

The contract author also left a deliberate second contract — `AuditFinding.json` v1.0.0 — governing AuditFinding's actual persistence shape (`check_id, severity, message`) with its own description acknowledging the gap: *"A separate governance entry will govern AuditFinding against the canonical Finding nucleus (Finding.json), which will produce drift findings for missing nucleus fields (rule_id, subject, worker_uuid absent; check_id/message serve analogous roles under different names)."*

The dual-contract structure is the constitutional posture: persistence shape gets its own governance contract; the nucleus-conformance is the visible gap. **This ADR does not retire the dual-contract structure.** It reconciles the *implementation* with the Finding nucleus, preserving the dual contracts as the after-state.

### The structural problems the gap creates

The 16 findings aren't just visible drift. Three concrete failures land downstream of the unreconciled state:

1. **Cross-surface consumer code branches on field names.** Code reading findings has to know whether it's reading a `CheckResult` (`.rule`), an `AuditFinding` (`.check_id`), or a `BlackboardEntry.payload['rule_id']` (the third surface, BlackboardEntry, isn't governed yet but exists as a real persistence target). Three names for the same conceptual identity. Memory `[[feedback_three_layer_intent_alignment]]` is the precise shape of this drift.

2. **Worker attribution is structurally absent on operator-run audits.** `core-admin code audit` (the governor's command-line invocation) produces AuditFinding instances with no worker context. The nucleus requires `worker_uuid`. The operator-run path doesn't have one. ADR-056 D3's bind committed to the nucleus without specifying the non-worker case; this ADR's D1 resolves it.

3. **Extension fields that are conceptually refinements get rendered as drift.** `AuditFinding.file_path` is a refinement of `subject` (subject names the artifact; file_path is its concrete location). `AuditFinding.context` is a refinement of `evidence` (evidence is the prose; context is the structured payload). Rendering them as "drift to be made visible" treats refinements as noise. The contract's `permitted_extensions` clause exists in spirit (in the description) but not as a structural field; this ADR's D3 makes it structural.

### Constraints inherited

- **ADR-056 D3.** Nucleus fields are not optional. This ADR honors that — the after-state has all five nucleus fields present on both governed classes.
- **ADR-056 D6.** AST gate is the enforcement site. This ADR does not change engines; it changes class shapes and contract clauses the engine reads.
- **ADR-059 D2.** Severity vocabulary already shared (`audit_severity` enum). No severity changes in this ADR.
- **ADR-098 D2.** `AuditFinding.context` extensions for aggregate quality gates. D3 below registers `context` as a permitted extension so this ADR's reconciliation does not collide with ADR-098's per-tool payload shape.
- **23 + 3 emitter blast radius.** AuditFinding has 23 referencing files (`grep -rl "AuditFinding(" src/`); CheckResult has 3. The migration strategy in D2 below is sized to the AuditFinding number — the CheckResult migration is mechanical.

---

## Decisions

### D1 — Non-worker findings use a reserved sentinel `worker_uuid`; operator-run is a constitutional officer

> **SUPERSEDED by Revision A — D1 prose only, mechanism unchanged.** Revision A keeps the sentinel mechanism, the `worker_registry` officer registration, and the closed-vocabulary `synthetic_workers.json` declaration. What changes is the framing: the claim that the sentinel "is queryable as data, not a special case in code" was self-contradicted by the Out-of-scope note that liveness consumers must exclude synthetic UUIDs (which IS a special case in code, just localized to liveness). Revision A acknowledges the trade honestly instead of overselling it. Text below preserved as the original framing.

The Finding nucleus's `worker_uuid` field is **mandatory and never optional**. Non-worker emitters use a reserved sentinel UUID identifying the source. The initial sentinels:

| Source | Reserved UUID | Registered as |
|---|---|---|
| Operator-run (`core-admin code audit`) | `00000000-0000-0000-0000-000000000001` | Constitutional officer in `worker_registry` with name `"operator-run"`, status `"active"`, no heartbeat (the operator is the heartbeat) |
| CI-run (F-10 stateless audit, GH Actions) | `00000000-0000-0000-0000-000000000002` | Constitutional officer in `worker_registry` with name `"ci-run"`, status `"active"`, no heartbeat |

The operator-run sentinel is **not** a workaround. It is a constitutional declaration: the operator's CLI invocation is a recognized audit-emitting authority, equivalent to a sensor worker for governance-attribution purposes. The `worker_registry` entry makes the attribution queryable (e.g., "show all operator-attributed findings in the last 24h" is a SQL filter, not a special case in code) and keeps the type discipline intact (`worker_uuid` is always a UUID, never None).

**Why this beats the alternatives.**

- *Optional `worker_uuid`* (#598's Q1 option (b)) breaks the type discipline — every consumer needs an Optional[UUID] check; the nucleus's "5 mandatory fields" property erodes.
- *Discriminator field `source`* (#598's Q1 option (c)) introduces a parallel attribution axis. Two ways to say "who emitted this" is one too many; the dual surface invites drift.
- *Reserved sentinel* (option (a)) preserves the type discipline, generalizes to future synthetic emitters (e.g., a future remediation-evidence-writer, a future audit-snapshot replay), and is queryable as data.

The sentinel UUIDs are declared in `.intent/META/synthetic_workers.json` (new artifact, follows the data-driven-vocab pattern of `enums.json`). The list is closed — adding a new sentinel requires governor approval, same as any other constitutional vocabulary expansion. This forecloses ad-hoc sentinel proliferation.

### D2 — Aliases bridge the rename, with a fixed deprecation horizon

> **SUPERSEDED by Revision A — load-bearing mechanism error.** This original D2 specified Pydantic `Field(alias=...)` as the bridge mechanism for both classes. That's correct for `CheckResult` (which is `class CheckResult(BaseModel)` — Pydantic) but **mechanically broken for `AuditFinding`**, which is actually `@dataclass(init=False)`. The misreading came from the `audit_models.py` module docstring ("Defines the Pydantic models…"), which is itself stale and lies about the class type. `Field(alias=...)` is a Pydantic-only feature; on a `@dataclass` it either errors or silently no-ops. The original D2 below is preserved as record of the misreading; Revision A specifies the correct bridge mechanism per class. Discovered by an external review during the Proposed→Acceptance gate (see External Review Record at end of file).

The Finding-nucleus field names (`rule_id`, `subject`, `evidence`) replace the current implementation names (`check_id`, [no current equivalent], `message`) on `AuditFinding`; (`rule`, [no current equivalent], `evidence` — `evidence` already matches) on `CheckResult`. The migration uses **Pydantic field aliases with a one-release deprecation horizon**, not a hard rename:

**For `AuditFinding`** (`src/shared/models/audit_models.py`):

```python
class AuditFinding:
    rule_id: str = Field(alias="check_id")     # canonical name; old name accepted as alias on input
    severity: AuditSeverity
    subject: str                                # NEW field; replaces the implicit role of file_path/check_id
    evidence: str = Field(alias="message")     # canonical name; old name accepted as alias on input
    worker_uuid: UUID                           # NEW field; populated by emitter, sentinel for operator-run
    # Extension fields (permitted per D3):
    file_path: str | None = None
    line_number: int | None = None
    context: dict[str, Any] = field(default_factory=dict)
```

**For `CheckResult`** (`src/body/services/cim/models.py`):

```python
class CheckResult(BaseModel):
    rule_id: str = Field(alias="rule")         # canonical name; old name accepted as alias
    severity: Literal["block", "high", "medium", "low", "info"]
    subject: str                                # NEW field; CIM's per-policy target identifier
    evidence: str                               # already the canonical name; no change
    worker_uuid: UUID                           # NEW field; sentinel for operator-run
    # Extension fields (permitted per D3):
    id: str
    recommendation: str
    links: list[str] = Field(default_factory=list)
```

**Deprecation horizon: one full audit-coherence cycle from D2 landing.** The horizon is dated in `.intent/CHANGELOG.md` at the time the alias-bridged classes ship. When the cycle completes with zero emitter-side use of the old name (verifiable via grep + audit), the aliases are removed.

**Why aliases with a horizon, not hard rename or permanent aliases.**

- *Hard rename in one PR* touches 23 emitter files at once. The blast radius produces a forcing function — one mistake and the autonomous audit loop breaks until the rename completes everywhere. The risk is operational, not technical.
- *Permanent aliases* lock in the divergence as a feature. The contract description's reconciliation intent doesn't survive that choice — "check_id" forever-accepted means "rule_id is just a synonym," and the next session reads `check_id` in code and stops noticing it isn't the canonical name.
- *Aliases with a horizon* let emitters migrate incrementally (a single emitter at a time, verified by smoke), then the alias removal is the forcing function that completes the reconciliation. The horizon makes the temporary state visible and non-permanent.

The horizon's mechanism is the `.intent/CHANGELOG.md` dated entry plus a `# DEPRECATED: alias removed YYYY-MM-DD` comment on each aliased Field. Memory `[[feedback_append_only_adr_closure_marker]]` informs the comment shape — append-only, dated, traceable.

### D3 — `permitted_extensions` clause makes refinement-of-nucleus fields structurally allowlisted

The Finding.json contract gains a new optional clause `permitted_extensions` — a per-class map of extension-field names to their structural justification:

```json
{
  "governed_classes": ["CheckResult", "AuditFinding"],
  "required": ["rule_id", "severity", "subject", "evidence", "worker_uuid"],
  "permitted_extensions": {
    "AuditFinding": {
      "file_path": "Refinement of subject: subject names the artifact (file/symbol), file_path locates it as a repo-relative path",
      "line_number": "Refinement of subject: locates the violation within file_path",
      "context": "Refinement of evidence: evidence is the prose description, context is the structured payload (per ADR-098 D2 for aggregate quality gates)"
    },
    "CheckResult": {
      "id": "Pydantic identity field — required by the CIM persistence surface",
      "recommendation": "CIM's per-policy actionable suggestion; conceptually distinct from evidence",
      "links": "References to source / rule documentation; conceptually distinct from evidence"
    }
  }
}
```

The `SchemaConformanceChecks` engine reads `permitted_extensions` and:
- Suppresses findings on any field listed in the per-class extension map.
- **Continues to flag** fields not listed in either `required` or `permitted_extensions` — these are unannounced drift, exactly what the contract description's "made visible, not silently absorbed" requires.

**Why structural allowlist rather than blanket permission.**

The contract's "extensions are drift to be made visible" language is correct *for unannounced extensions*. A field whose role in the class is non-obvious — added by an evolving emitter without governor review — should be visible. A field whose role is the structural refinement of a nucleus field is not drift; it's the nucleus mapped to the layer's concrete surface. The clause distinguishes the two. Future additions to either class either join `permitted_extensions` (governor approves the refinement) or fire as drift (governor sees it and decides).

The clause's schema lives in `.intent/META/data_contract.schema.json` (extended in this ADR's migration step 1).

### D4 — Sequencing: CheckResult first (smaller blast radius, proof-of-pattern), AuditFinding second; BlackboardEntry deferred

CheckResult migrates first because:
- Smaller blast radius (3 emitter files vs 23).
- Lower visibility impact (CIM is internal vs AuditFinding's user-facing audit dashboard).
- Proves the alias-bridged migration pattern on the lower-risk surface before applying it to the high-blast-radius one.

AuditFinding migrates second once the CheckResult pattern is validated by one full audit cycle. Both follow the same D2 alias-bridge mechanism; the second migration is a copy of the first with a different field map.

**BlackboardEntry payload (the third Finding surface named in Finding.json's description) is out of scope for this ADR.** Per Finding.json v1.1.0's description: *"BlackboardEntry payload family to be added in Wave 1 Session 3."* The blackboard payload has a different blast radius and a different reconciliation question (it's JSONB, not a Pydantic class — the contract's enforcement mechanism is different). A future ADR — call it ADR-100 — extends Finding.json's governed_classes to include the payload family once the pattern from this ADR is proven.

The change-sets land in this sequence:

1. **CheckResult migration change-set.** Aliases + `subject` + `worker_uuid` on CheckResult; CIM emitters (3 files) updated to pass the new fields. Smoke tests per D5. CheckResult-shaped findings on `data.contracts.finding_nucleus_conforms` clear.
2. **One audit cycle of bake time.** No drift findings appear on CheckResult; consumers exercising CIM (rare today) keep working through the alias.
3. **AuditFinding migration change-set.** Same pattern, 23 emitter files. Smoke tests per D5. AuditFinding-shaped findings on the same rule clear.
4. **One audit cycle of bake time.**
5. **Alias removal change-set.** Both classes drop their aliases; only canonical names accepted. The deprecation horizon completes. Any emitter still using the old name fails fast at instantiation (the canonical signal that the migration is done).

### D5 — Pre-migration verification: synthetic-emitter smoke test + audit-pipeline diff

The risk D2's alias bridge is meant to mitigate is *catastrophic* — if AuditFinding instantiation breaks mid-flight, every audit emitter in `src/` raises on every cycle, the autonomous loop halts, the dashboard goes silent. The bridge alone is not enough; the migration needs a verification gate before the alias-bridged class ships.

**Synthetic-emitter smoke test** (lives at `tests/governance/test_finding_migration_smoke.py`, authored as part of step 1):

For each emitter pattern in the codebase (enumerated by `grep -rln "AuditFinding(" src/`), the smoke constructs an instance using:
- The pre-rename name set (old names).
- The post-rename name set (canonical names).
- A mixed set (some old, some canonical).

All three forms must instantiate cleanly and serialize via `as_dict()` to the same payload. The smoke is part of the migration PR; the PR cannot merge if any of the three forms fails on any emitter pattern.

**Audit-pipeline diff** (run as a verification gate at the end of each migration change-set):

Run `core-admin code audit --offline --format json` against the commit immediately before the change-set and immediately after. The two finding sets must be **identical modulo the `data.contracts.finding_nucleus_conforms` findings themselves** — i.e., the only delta is the seven (or sixteen, when AuditFinding also migrates) findings that the migration is meant to clear. Any other delta is a regression introduced by the rename and must be diagnosed before the change-set lands.

**Why these two gates and no others.** The smoke verifies the rename mechanics (consumers + emitters under the alias bridge); the pipeline diff verifies the runtime semantics (the audit produces the same findings on the same code, modulo the targeted clearing). Together they bound the risk to "exactly the change you authorized," which is the property the ADR-056 D3 contract assumes when it requires nucleus reconciliation without specifying how.

---

## Migration

Steps land in this order; each is verifiable independently before the next begins.

1. **Extend `.intent/META/data_contract.schema.json`** to define the `permitted_extensions` clause (per-class map of field name → string justification). Schema-only change; no consumer yet. **Verification:** `core-admin code audit --offline` runs clean; `permitted_extensions` clause validates per the META schema on a synthetic test fixture.

2. **Land `.intent/META/synthetic_workers.json`** with the operator-run and ci-run sentinels (per D1). Plus loader at `src/shared/infrastructure/intent/synthetic_workers.py` exposing `OPERATOR_RUN_UUID`, `CI_RUN_UUID` constants. **Verification:** unit test asserts loader returns the declared sentinels; AST gate confirms the constants are read only from this loader (no scattered literals).

3. **Land `.intent/META/synthetic_workers.json`'s worker_registry seed** (the operator-run and ci-run rows registered as constitutional officers; status active, no heartbeat). One-time SQL insert via `infra/sql/db_schema_live.sql` augmentation per `[[feedback_schema_as_truth_no_migration_framework]]`. **Verification:** SQL probe on `worker_registry` shows both rows present after schema sync.

4. **Update Finding.json (contract v1.2.0):** add the `permitted_extensions` clause per D3. CheckResult and AuditFinding entries listed; specific fields enumerated. **Verification:** `data.contracts.finding_nucleus_conforms` finding count drops from 16 (= 7 missing + 9 extension) to 7 (only the missing-required remain visible).

5. **Author the synthetic-emitter smoke test** per D5. **Verification:** test runs against the unmodified codebase; the "current names" form passes, the "canonical names" form fails (the canonical names don't exist yet), the "mixed" form fails. This is the *pre-condition* shape the migration steps below flip.

6. **CheckResult migration change-set.** Add `rule_id` (alias `rule`), `subject`, `worker_uuid` to CheckResult. Update the 3 emitters in `src/body/services/cim/*` and `src/body/autonomy/micro_proposal_executor.py` to pass the new fields. Smoke test pass; audit-pipeline diff shows CheckResult findings cleared (3 missing-required → 0). **Verification:** D5 gates both pass; `data.contracts.finding_nucleus_conforms` finding count drops to 4 (only AuditFinding's missing-required remain).

7. **One audit cycle bake.** ~24h. CheckResult-attributed findings produced in normal operation match the new shape; no consumer regressions reported.

8. **AuditFinding migration change-set.** Add `rule_id` (alias `check_id`), `subject`, `evidence` (alias `message`), `worker_uuid` to AuditFinding. Update the 23 emitter files in `src/mind/`, `src/body/`, `src/will/`, `src/api/`, `src/cli/`. Operator-run emitters (e.g., the `core-admin code audit` path) populate `worker_uuid` with `OPERATOR_RUN_UUID`; worker-attributed emitters populate it from the worker's own UUID. Smoke test pass; audit-pipeline diff shows AuditFinding findings cleared (4 missing-required → 0). **Verification:** D5 gates both pass; `data.contracts.finding_nucleus_conforms` finding count = 0.

9. **One audit cycle bake.** AuditFinding-attributed findings produced in normal operation match the new shape.

10. **Alias removal change-set.** Drop `Field(alias="check_id")`, `Field(alias="message")`, `Field(alias="rule")` from both classes. Any emitter still using old names raises at instantiation; this is the forcing function that confirms the deprecation horizon completed. **Verification:** `grep -rn "check_id=\|message=\|rule=" src/` (excluding test fixtures) returns zero hits in emitter files before this change-set merges.

Steps 1–4 are landing-order-coupled. Steps 5–7 land independently (CheckResult arc). Steps 8–9 land after step 7's bake completes (AuditFinding arc). Step 10 lands after both arcs' deprecation horizons close.

## Verification

- **Contract-conformance check:** post-step-4, the 9 extension-visible findings on `data.contracts.finding_nucleus_conforms` clear (the permitted-extensions clause structurally absorbs them). Post-step-6, 3 of the remaining 7 missing-required findings clear (CheckResult). Post-step-8, the final 4 clear (AuditFinding). Post-step-10, no aliased fields remain in either class.
- **Smoke-test check:** the D5 smoke test passes the "mixed" form during the alias period (any combination of old and new names instantiates cleanly) and the "old names only" form fails after step 10 (the canonical-only state is enforced).
- **Audit-pipeline diff check:** at each step 6/8 change-set, the pre/post audit-pipeline diff is bounded — only the targeted `data.contracts.finding_nucleus_conforms` findings clear; no other finding count changes. Any other delta is investigated before the change-set merges.
- **Synthetic-emitter attribution check:** post-step-3, every `core-admin code audit` run produces AuditFinding instances with `worker_uuid = OPERATOR_RUN_UUID`; every CI gate run produces AuditFinding instances with `worker_uuid = CI_RUN_UUID`. Verifiable by SQL probe: `SELECT DISTINCT worker_uuid FROM core.audit_runs ... ` shows the sentinels alongside real-worker UUIDs.
- **No-regression-on-third-surface check:** BlackboardEntry payload is out of scope for this ADR, but the audit's existing rule fires on it as the third Finding surface. The migration must not cause new findings to appear on `BlackboardEntry.payload` shapes — verified by the audit-pipeline diff at each step.

## Out of scope

- **BlackboardEntry payload Finding-nucleus reconciliation.** Deferred to a future ADR (the contract's v1.1.0 description names this as Wave 1 Session 3). The reconciliation mechanism for JSONB is different from the Pydantic class case; copying this ADR's pattern wholesale would be premature.
- **Severity vocabulary changes.** ADR-059 D2 governs severity; AuditFinding.json's note already documents the IntEnum/string reconciliation. This ADR makes no changes to severity-related fields.
- **AuditFinding.json contract retirement.** The dual-contract structure (Finding.json governs nucleus-conformance, AuditFinding.json governs persistence shape) is a deliberate design per ADR-056's posture. This ADR reconciles the implementation with both contracts; it does not retire either.
- **Operator-run heartbeat mechanism.** The operator-run sentinel is registered as a constitutional officer in `worker_registry` with no heartbeat. The liveness-check engines (e.g., `worker_max_interval` per #604) must skip synthetic-worker UUIDs. Implementation note: the existing `active_uuids` filter in `worker_shop_manager` will need to exclude the sentinels; this is mechanical, lives in the migration's step 3 change-set, and does not warrant its own ADR.
- **CI-run worker_uuid sentinel rollout.** The CI_RUN_UUID is declared in step 2 of the migration but is not consumed by any emitter until the F-10 CI gate's emitter path is migrated (separate from `src/`'s emitter migration). That migration is sequenced after step 9 of this ADR and tracked separately.
- **Renaming `data.contracts.finding_nucleus_conforms` to reflect post-migration shape.** The rule's name and rationale describe a transitional state. Once this ADR's migration completes, the rationale needs an editorial pass — but the rule itself stays as the conformance enforcer for any future class added to Finding.json's governed_classes.

## References

- #598 — Originating issue (ADR-056 D3 implementation drift).
- ADR-056 D3 — The constitutional bind being reconciled.
- ADR-056 D6 — `SchemaConformanceChecks` is the enforcement site this ADR's migration steps interact with.
- ADR-059 D2 — Severity vocabulary (unchanged by this ADR).
- ADR-098 D2 — `AuditFinding.context` extensions for aggregate quality gates (composes with D3's `permitted_extensions` clause).
- `.intent/enforcement/contracts/Finding.json` v1.1.0 — The nucleus contract being honored.
- `.intent/enforcement/contracts/AuditFinding.json` v1.0.0 — The persistence-shape contract being honored.
- `.intent/rules/data/governance.json` — The `data.contracts.finding_nucleus_conforms` rule (the 16 findings live here).
- `src/shared/models/audit_models.py:43-107` — `AuditFinding` definition (migrated in steps 8–10).
- `src/body/services/cim/models.py:279-293` — `CheckResult` definition (migrated in steps 6–10).
- `src/mind/logic/engines/ast_gate/checks/` — `SchemaConformanceChecks` lives here (reads the `permitted_extensions` clause introduced by D3 / step 4).
- `src/will/workers/worker_shop_manager.py` — The liveness-check site that needs the synthetic-worker exclusion noted in Out of scope.
- Memory: `[[feedback_two_surface_requires_two_structures]]` — informed the dual-contract preservation; AuditFinding.json + Finding.json are kept as two structures because they serve materially different jobs.
- Memory: `[[feedback_three_layer_intent_alignment]]` — the precise pathology this ADR addresses (engine / rule / convention disagreement; here it's nucleus / persistence / actual-class).
- Memory: `[[feedback_append_only_adr_closure_marker]]` — informs the deprecation comment shape on D2's aliased Field declarations.
- Memory: `[[feedback_schema_as_truth_no_migration_framework]]` — step 3's worker_registry seed lives in `infra/sql/db_schema_live.sql`, not in a migration framework that doesn't exist.

---

## Revision A — 2026-06-09 (authoritative for D2–D5; D1 superseded by Revision B)

### Why this revision

A pre-acceptance external review verified the ADR's decisions against current source rather than against the ADR's code blocks. Two findings:

1. **Load-bearing mechanism error in D2.** The original D2 specified Pydantic `Field(alias=...)` as the bridge mechanism for both `CheckResult` and `AuditFinding`. Verification against `src/shared/models/audit_models.py` showed `AuditFinding` is `@dataclass(init=False)` — not Pydantic — despite a stale module docstring claiming "Defines the Pydantic models." `Field(alias=...)` is Pydantic-only. The 23-emitter migration arc (the largest blast radius in the ADR, and the entire reason D4's careful sequencing exists) specified a mechanism that doesn't work on the target class. Implementing the original D2 would either fail at step 8 instantiation or force the implementer to silently improvise — exactly the implementation-drift failure mode ADRs exist to prevent.

2. **D1 framing oversold the sentinel mechanism.** D1 claimed the sentinel approach "is queryable as data, not a special case in code." The Out-of-scope section in the same ADR notes that liveness consumers (`worker_max_interval` per #604, `active_uuids` filter in `worker_shop_manager`) must skip synthetic-worker UUIDs. That IS a special case in code — localized to liveness, but still code. The mechanism remains the correct choice (the alternatives have worse trade-offs); the framing should acknowledge the trade rather than oversell it.

The third claim the review surfaced — that the severity vocabulary referenced in the Context section was on a "stale" three-value scale — was investigated against live `main` (HEAD `b366e480` at investigation time) via the reviewer's own specified four-check protocol after they flagged that the first response to their critique had asserted "verified" without showing the work. The reviewer's index was stale relative to live; live shows the five-value reconciliation landed.

**Four-check verification log:**

1. `AuditSeverity` IntEnum members at `src/shared/models/audit_models.py:14-28`: `INFO=1, LOW=2, MEDIUM=3, HIGH=4, BLOCK=5` — five-value.
2. `severity_from_string` lives at `src/cli/commands/check/converters.py:42` (not in `audit_models.py` as the reviewer's index suggested). Default: `AuditSeverity.BLOCK`. Lookup: `AuditSeverity[v.upper()]` against canonical five-value names. No `WARNING`/`ERROR` mapping anywhere.
3. `grep -rn 'AuditSeverity.WARNING\|AuditSeverity.ERROR' src/` (excluding `tests/`) returns zero hits — ADR-059 D2's stated verification criterion is satisfied.
4. `.intent/META/enums.json` `audit_severity.enum`: `["info", "low", "medium", "high", "block"]` (type `string`, enum field present).

The migration commit is identifiable in git log as `9551e972 ADR-059 D2: replace AuditSeverity 3-value scale with 5-value finding scale`. ADR-099's "severity already shared, no changes" precondition holds against live source. No revision needed on this claim — but the *epistemic* point the reviewer made (don't assert "verified" without showing the work) is recorded in the External Review Record as a methodology lesson alongside the substantive findings.

Revision A keeps everything else from the original draft unchanged — D3 (`permitted_extensions` as structural allowlist), D4 (CheckResult-first sequencing), D5 (smoke test + audit-pipeline diff gates), the 10-step migration order, the BlackboardEntry deferral. Those held under verification.

### D1 (Revision A) — Non-worker findings use a reserved sentinel `worker_uuid`; operator-run is a constitutional officer

> **SUPERSEDED by Revision B — D1 only.** Revision B keeps Revision A's sentinel mechanism, closed-vocabulary discipline, `worker_registry` officer registration, and honest-trade-off framing. What changes: the implementation-pass duplicate sweep before step 2 found that `...0002` was already live as `API_CLAIMER_UUID` (ADR-017 D4 pattern) and that `...0001` had a stale `CLI_CLAIMER_UUID` comment. Revision B consolidates the audit-emitter sentinels (operator-run, ci-run) with the ADR-017 D4 claimer sentinel (api-claimer) into a single authoritative ledger, adds an `axis` field to distinguish the two patterns, and renumbers `ci-run` to `...0003`. The mechanism is identical; the ledger is wider.

The Finding nucleus's `worker_uuid` field is **mandatory and never optional**. Non-worker emitters use a reserved sentinel UUID identifying the source. The initial sentinels:

| Source | Reserved UUID | Registered as |
|---|---|---|
| Operator-run (`core-admin code audit`) | `00000000-0000-0000-0000-000000000001` | Constitutional officer in `worker_registry` with name `"operator-run"`, status `"active"`, no heartbeat (the operator is the heartbeat) |
| CI-run (F-10 stateless audit, GH Actions) | `00000000-0000-0000-0000-000000000002` | Constitutional officer in `worker_registry` with name `"ci-run"`, status `"active"`, no heartbeat |

The operator-run sentinel is a constitutional declaration: the operator's CLI invocation is a recognized audit-emitting authority, equivalent to a sensor worker for governance-attribution purposes. The `worker_registry` entry makes the attribution queryable (e.g., "show all operator-attributed findings in the last 24h" is a SQL filter, not a branch in code) and keeps the type discipline intact (`worker_uuid` is always a UUID, never None).

The sentinel UUIDs are declared in `.intent/META/synthetic_workers.json` (new artifact, follows the data-driven-vocab pattern of `enums.json`). The list is closed — adding a new sentinel requires governor approval, same as any other constitutional vocabulary expansion.

**The trade-off, stated honestly:** the sentinel approach localizes "is this synthetic?" branching to liveness consumers — `worker_max_interval` and `worker_shop_manager.active_uuids`. The original D1 framing claimed this was "not a special case in code"; that overstated the position. The accurate framing: synthetic-UUID exclusion in liveness is a small, named, localized branch — preferred over the alternatives because the branch lives at a small, well-defined surface rather than at every Finding consumer.

**Why this beats the alternatives.**

- *Optional `worker_uuid`* (#598's Q1 option (b)) leaks `Optional[UUID]` into every Finding consumer. Liveness consumers would still need to special-case the None branch — the "no special case in code" property the original D1 implicitly claimed never held. Optional erodes the nucleus's "5 mandatory fields" property at every reader, not just at liveness.
- *Discriminator field `source`* (#598's Q1 option (c)) introduces a parallel attribution axis. Two ways to say "who emitted this" (sentinel + discriminator) invites drift between the two; consumers that join on one don't see the other.
- *Reserved sentinel* (option (a)) keeps `worker_uuid: UUID` as a non-optional type, localizes the synthetic-vs-real distinction to liveness consumers (a small, well-defined set), and generalizes to future synthetic emitters (audit-snapshot replay, remediation-evidence writer) without further vocabulary expansion at the consumer surface.

### D2 (Revision A) — Bridge mechanism split by class type

The Finding-nucleus field names (`rule_id`, `subject`, `evidence`) replace the current implementation names on both classes. The migration uses **two different bridge mechanisms appropriate to each class's type discipline**, with a single shared deprecation horizon.

**For `CheckResult`** (`src/body/services/cim/models.py:279` — `class CheckResult(BaseModel)`, Pydantic):

Pydantic field aliases. `Field(alias="rule")` accepts the old name on input while the canonical name is the attribute. Standard Pydantic pattern.

```python
class CheckResult(BaseModel):
    rule_id: str = Field(alias="rule")          # canonical; old name accepted as alias
    severity: Literal["block", "high", "medium", "low", "info"]
    subject: str                                 # NEW field; CIM's per-policy target identifier
    evidence: str                                # already canonical; no change
    worker_uuid: UUID                            # NEW field; sentinel for operator-run
    # Extension fields (permitted per D3):
    id: str
    recommendation: str
    links: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}    # accept both `rule` and `rule_id` on input
```

**For `AuditFinding`** (`src/shared/models/audit_models.py:41` — `@dataclass(init=False)`, NOT Pydantic):

Custom `__init__` kwarg-aliasing. This is the codebase's established dataclass rename-bridge pattern — already present in the same class file for the `details=` → `context` legacy alias. The hand-written `__init__` accepts both legacy and canonical kwargs and folds them onto the canonical field. No Pydantic involvement.

```python
@dataclass(init=False)
class AuditFinding:
    rule_id: str                                 # canonical; replaces check_id
    severity: AuditSeverity
    subject: str                                 # NEW field; the artifact identity
    evidence: str                                # canonical; replaces message
    worker_uuid: UUID                            # NEW field; sentinel for operator-run
    # Extension fields (permitted per D3):
    file_path: str | None = None
    line_number: int | None = None
    context: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        *,
        # Canonical kwargs — preferred for new code:
        rule_id: str | None = None,
        severity: AuditSeverity,
        subject: str | None = None,
        evidence: str | None = None,
        worker_uuid: UUID,
        # Legacy kwargs — accepted during deprecation horizon, fold onto canonical:
        check_id: str | None = None,
        message: str | None = None,
        # Extensions:
        file_path: str | None = None,
        line_number: int | None = None,
        context: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,    # existing legacy → context (pre-existing)
    ) -> None:
        # rule_id resolution: prefer canonical, fall back to legacy, raise if both absent
        if rule_id is None and check_id is None:
            raise TypeError("AuditFinding requires rule_id (or legacy check_id)")
        if rule_id is not None and check_id is not None and rule_id != check_id:
            raise TypeError("AuditFinding: rule_id and check_id given with different values")
        self.rule_id = rule_id if rule_id is not None else check_id

        # evidence resolution: same pattern
        if evidence is None and message is None:
            raise TypeError("AuditFinding requires evidence (or legacy message)")
        if evidence is not None and message is not None and evidence != message:
            raise TypeError("AuditFinding: evidence and message given with different values")
        self.evidence = evidence if evidence is not None else message

        # subject is new; required canonical
        if subject is None:
            raise TypeError("AuditFinding requires subject")
        self.subject = subject

        self.severity = severity
        self.worker_uuid = worker_uuid
        self.file_path = file_path
        self.line_number = line_number

        # context resolution: existing pattern (preserved from current code)
        base_context: dict[str, Any] = dict(context or {})
        if details:
            base_context.update(details)
        self.context = base_context
```

The `details=` → `context` fold is preserved unchanged — that legacy alias predates this migration and lives on its own lifecycle.

**Both bridges share the same one-cycle deprecation horizon** dated in `.intent/CHANGELOG.md` at the time the bridges ship. The horizon's mechanism per class:

- **CheckResult:** at step 10, the `Field(alias="rule")` is removed; `populate_by_name = True` is removed. Any consumer still passing `rule=` raises a Pydantic `ValidationError`.
- **AuditFinding:** at step 10, the `check_id` and `message` kwargs are removed from the `__init__` signature. Any caller still passing them raises `TypeError: unexpected keyword argument`. The `details=` legacy kwarg is NOT removed at step 10 — it's on a separate lifecycle and its retirement (if any) is a future ADR.

**D5's smoke test must now exercise both bridge shapes** (Revision A amendment to D5): the test fixture for AuditFinding constructs instances using `(check_id=..., message=...)`, `(rule_id=..., evidence=...)`, and `(check_id=..., evidence=...)` mixed; the test fixture for CheckResult does the same with `rule=` and `rule_id=`. Each form must instantiate cleanly during the alias period and `as_dict()` to the same canonical payload. Post-step-10, the legacy-only forms must fail — that failure is the verification that the deprecation horizon closed cleanly.

**Why the split by class type rather than converting `AuditFinding` to Pydantic.**

Converting `AuditFinding` to a Pydantic `BaseModel` would unify the bridge mechanism — but it's a much larger blast radius than this ADR is sized to absorb. The dataclass has a hand-written `__init__`, a `details` property + setter, a custom `as_dict()`, and `@dataclass(init=False)` semantics that consumers may rely on. Migrating to Pydantic would change instantiation semantics, attribute-access semantics (Pydantic does extra validation), serialization (custom `as_dict()` vs `model_dump()`), and likely break some of the 23 emitters in ways the alias bridge alone wouldn't. That's a different ADR. Splitting the bridge by class type lets this ADR achieve its objective (nucleus reconciliation) without paying that cost.

### Sequencing impact (D4 unchanged; clarification only)

D4's CheckResult-first ordering remains correct. The bridge-mechanism split doesn't alter the sequencing argument — CheckResult is still the smaller blast radius (3 emitters vs 23) and the right proof-of-pattern surface. What changes is that step 6 (CheckResult migration) and step 8 (AuditFinding migration) now exercise *different* bridge mechanisms, so the proof-of-pattern from step 6 doesn't carry directly to step 8's mechanics — but the surrounding migration discipline (smoke, audit-pipeline diff, bake cycle) does. Step 8's risk profile is comparable to step 6's; the bridge-mechanism delta is the localized variable.

### What this revision does NOT change

- D3's `permitted_extensions` clause and the META schema extension at step 1 — unchanged.
- D4's CheckResult-first → AuditFinding-second sequencing — unchanged.
- D5's two verification gates (synthetic-emitter smoke test, audit-pipeline diff) — unchanged in intent; D5's smoke test fixture content amended above to cover both bridge shapes.
- The 10-step migration order — unchanged.
- BlackboardEntry deferral to a future ADR (ADR-100) — unchanged.
- D1's sentinel mechanism, the `synthetic_workers.json` declaration, the `worker_registry` officer registration, and the closed-vocabulary discipline — unchanged. Only D1's framing prose is amended (above) to acknowledge the localized liveness branch instead of overselling the sentinel as branch-free.

---

## External Review Record

| Date | Reviewer | Surface reviewed | Contribution |
|---|---|---|---|
| 2026-06-09 | Pre-acceptance external review (via the governor's session) | Original D1 + D2 verified against `src/shared/models/audit_models.py` and `src/body/services/cim/models.py` rather than against ADR code blocks. | (1) Caught that `AuditFinding` is `@dataclass(init=False)`, not Pydantic (the module docstring lies). Original D2's `Field(alias=...)` mechanism is Pydantic-only and would either error or no-op on the 23-emitter target class. Triggered Revision A's bridge-mechanism split. (2) Surfaced D1's framing inconsistency (sentinel framed as "not a special case in code" while the Out-of-scope section requires liveness-side branching). Triggered Revision A's honest-trade-off reframe of D1. (3) Raised a third claim — severity vocab on a stale three-value scale. Investigated via four-check protocol against live `main` (see "Why this revision" section above); index was stale, live source is the five-value reconciliation ADR-099 references. No substantive revision; ADR's precondition holds. |
| 2026-06-09 | Same reviewer, second pass on the first draft of Revision A | Revision A's "Why this revision" subsection + External Review Record's framing of the severity claim. | Flagged that the first draft of Revision A asserted the severity claim was "verified incorrect" without showing the four-check evidence — the same kind of bald assertion the first round's verification discipline was meant to correct. Forced the four-check log to be recorded inline (above) and the ERR row's wording to be amended from "verified incorrect" to "investigated via four-check protocol; reviewer's index was stale; live shows reconciliation landed." Epistemic discipline preserved into the permanent record. |

The pattern this ADR followed: verify the ADR's load-bearing decisions against live source before flipping Status from Proposed → Accepted, and verify the verification before stamping it into the append-only record. The original D2's miss came from accepting the ADR's code blocks and the file's module docstring at face value (memory `[[feedback_verify_docstring_against_impl]]`); the Revision A "verified incorrect" miss came from re-asserting from memory after writing the lesson down (memory `[[feedback_recheck_state_before_public_assertion]]`). Both lessons reinforced.

---

## Revision B — 2026-06-09 (current authoritative proposal; D1 only)

### Why this revision

Implementation-pass duplicate sweep before drafting `.intent/META/synthetic_workers.json` (migration step 2) surfaced two collisions on the reserved UUID range Revision A's D1 specified:

1. **`...0002` is live as `API_CLAIMER_UUID`** at `src/api/v1/proposals_routes.py:51` — a proposal-claimer sentinel established by the ADR-017 D4 pattern (*"governor-direct execution paths get a stable sentinel so claimed_by lineage is queryable per surface"*). Different DB column (`proposals.claimed_by` vs `worker_uuid` on findings) but the same `worker_registry` key space: registering `...0002` as "ci-run" would mean future SQL queries joining `claimed_by → worker_registry.id` yield a misleading "ci-run" label on actual API claims.
2. **`...0001` had a stale comment** at `proposals_routes.py:47-50` referencing a `CLI_CLAIMER_UUID` constant at `src/cli/resources/proposals/manage.py`. Grep finds no such constant — the CLI now calls the API via `CoreApiClient` and the literal UUID was removed. Slot is functionally free; the comment is documentation rot, cleaned up in this revision's step 2 work.

The bigger pattern the sweep surfaced: the "synthetic UUID for non-worker action" convention already exists under ADR-017 D4. Revision A's D1 formalized the convention for the audit-emitter axis without acknowledging the existing claimer-axis instances — a split ledger waiting to drift. Revision B consolidates.

### D1 (Revision B) — Single authoritative ledger; consolidated with the ADR-017 D4 claimer pattern

`.intent/META/synthetic_workers.json` is the authoritative ledger of ALL reserved synthetic UUIDs in CORE. Both axes — audit-emitter and claimer — declare here:

| Name | UUID | Axis | Authority |
|---|---|---|---|
| operator-run | `00000000-0000-0000-0000-000000000001` | audit-emitter (`worker_uuid`) | ADR-099 D1 |
| api-claimer | `00000000-0000-0000-0000-000000000002` | claimer (`proposals.claimed_by`) | ADR-017 D4 (preserved, consolidated) |
| ci-run | `00000000-0000-0000-0000-000000000003` | audit-emitter (`worker_uuid`) | ADR-099 D1 (renumbered from ...0002 per this revision) |

The closed-vocabulary discipline still applies — adding a new entry requires governor approval (the file is in `.intent/META/`, constitutional core). The `axis` field distinguishes the two patterns so consumers don't conflate them; the `worker_registry` officer-registration in migration step 3 still covers only the audit-emitter entries (api-claimer follows ADR-017 D4's existing attribution model, which doesn't require a worker_registry row).

### Migration step 2 — expanded scope under Revision B

Step 2 now lands four artifacts together (in the same change-set):

1. `.intent/META/synthetic_workers.json` — the ledger above.
2. `src/shared/infrastructure/intent/synthetic_workers.py` — the loader exposing `OPERATOR_RUN_UUID`, `API_CLAIMER_UUID`, `CI_RUN_UUID` constants and a `SYNTHETIC_WORKERS` dict.
3. `src/api/v1/proposals_routes.py` migration — imports `API_CLAIMER_UUID` from the loader (line 51's local literal removed; lines 47-50's stale `CLI_CLAIMER_UUID` comment removed; unused `from typing import Final` and `from uuid import UUID` imports removed).
4. This Revision B section.

The Revision A step-2 verification gates apply unchanged: unit test asserts loader returns the declared sentinels; AST gate confirms the constants are read only from this loader (no scattered literals — `API_CLAIMER_UUID` is no longer a scattered literal as of this revision).

### What this revision does NOT change

- D1's sentinel mechanism, closed-vocabulary discipline, and `worker_registry` officer registration for audit-emitter sentinels — unchanged from Revision A.
- D2 (Revision A) bridge-mechanism split — unchanged.
- D3 (`permitted_extensions` clause) — unchanged.
- D4 sequencing (CheckResult first, AuditFinding second, BlackboardEntry deferred) — unchanged.
- D5 verification gates (synthetic-emitter smoke test, audit-pipeline diff) — unchanged.
- The 10-step migration order — unchanged in sequence; step 2's scope expands as above.

### External Review Record amendment

| Date | Reviewer | Surface reviewed | Contribution |
|---|---|---|---|
| 2026-06-09 | Implementation-pass duplicate sweep (in-session) | Pre-write grep of UUID literals in `src/` before drafting `synthetic_workers.json` | Surfaced ADR-017 D4 collision on `...0002` (live `API_CLAIMER_UUID` in `proposals_routes.py:51`) and stale `CLI_CLAIMER_UUID` comment at lines 47-50. Triggered Revision B's consolidation into a single ledger with an `axis` field; renumbered ci-run to `...0003`; migrated `API_CLAIMER_UUID` to load from the loader. The pattern the sweep enforces: duplicate-check BEFORE writing reserved identifiers, not after — the comment in `proposals_routes.py` even referenced the ADR-017 D4 pattern in passing, but Revision A drafted around the existing convention without acknowledging it. |

---

## Revision C — 2026-06-09 (retirement; superseded by ADR-102)

### Why this revision

Step 3's worker_registry seed pre-write check surfaced a third mechanism error in two sessions: the ADR's `status: "active"` framing references a column that doesn't exist (`worker_registry` has no status column per `worker_registry_service.py:30-31`), and the `no heartbeat` framing conflicts with the schema (`last_heartbeat` is NOT NULL DEFAULT now()). That was the third correction needed in one session — after Revision A's Pydantic-on-dataclass error and Revision B's UUID collision. A third correction pass on a migration plan is a pattern, not noise.

The step-back question — *what are we actually trying to accomplish, and is this approach earning its weight?* — surfaced the load-bearing fact ADR-099 inherited but never verified:

**AuditFinding and CheckResult are not constitutional Findings.** Grep confirmed:
- **AuditFinding** (23 instantiation sites) lives **exclusively in `src/mind/`**. Mind layer is constitutionally forbidden from DB access (`architecture.mind.no_database_access`). Zero grep hits for AuditFinding near `post_finding` or `blackboard_entries`. AuditFinding never crosses the persistence boundary; it's a return shape from rule evaluators.
- **CheckResult** (3 instantiation sites) is internal to `body/autonomy/micro_proposal_executor.py`'s `validate_proposal()` and `body/services/cim/policy.py`'s CIM evaluation. Returned as `list[CheckResult]`; never persisted.
- The bridge to the blackboard is **`audit_ingest_worker`** (Will layer): it calls Mind's `_run_audit()`, receives dicts, then calls `post_artifact_finding()` with a payload constructed inline. The worker's OWN `worker_uuid` populates `blackboard_entries.worker_uuid`. The blackboard payload is JSONB, not a Pydantic class.

So **neither class is the constitutional Finding surface**. The constitutional Finding is the blackboard JSONB payload, which already conforms (worker-attributed via FK, structurally correct). Each class is *also already governed* by its own appropriate per-class contract (CheckResult.json, AuditFinding.json) with zero findings against either.

**Finding.json's binding of these two classes was a category error in ADR-056 D3** — overlaying a nucleus contract on data carriers that don't cross the persistence boundary. The 16 findings on `data.contracts.finding_nucleus_conforms` are exclusively that contract firing on classes it shouldn't be governing.

**ADR-102 supersedes this ADR.** Finding.json is retired. The nucleus enforcement site moves from class-shape (the wrong site) to blackboard-write boundary (the right site). Most of ADR-099 is retired with Finding.json — there's no migration to do because there are no classes to migrate.

### What this revision retires

- **D1 (all variants — original, Revision A, Revision B).** Synthetic-worker sentinel mechanism is unnecessary. Operator CLI runs and CI gates are read-only evaluator invocations; they emit data carriers, not blackboard-persisted Findings. No attribution is needed because nothing crosses the boundary needing it.
- **D2 (all variants — original, Revision A).** Alias-bridged class rename is unnecessary. The 23 AuditFinding emitter sites and 3 CheckResult emitter sites remain unchanged. Their classes are already correctly governed by CheckResult.json and AuditFinding.json with zero findings.
- **D4 — CheckResult-first sequencing.** No migration to sequence.
- **D5 — synthetic-emitter smoke test + audit-pipeline diff verification.** No migration to verify.
- **Migration steps 2–10.** All retired.

### What this revision keeps

- **D3 — `permitted_extensions` clause on the META schema.** The structural concept (refinement-of-nucleus fields are allowlisted extensions, structurally distinguished from drift) remains independently useful even with no current consumer. ADR-102 keeps it for future contracts.
- **Migration step 1.** The `permitted_extensions` clause added to `.intent/META/data_contract.schema.json` stays in place.

### What gets reverted (alongside this revision, in the same change-set as ADR-102)

- **`.intent/enforcement/contracts/Finding.json` — deleted.** This is the load-bearing fix per ADR-102 D1; it's the action that clears the 16 findings.
- **`src/shared/infrastructure/intent/synthetic_workers.py` — deleted.** Loader has no consumers after the proposals_routes.py revert.
- **`src/api/v1/proposals_routes.py` — restored to local `API_CLAIMER_UUID` declaration.** The "consolidate into single ledger" rationale from Revision B was downstream of the synthetic-worker apparatus; without that apparatus the centralization has no benefit. The stale `CLI_CLAIMER_UUID` comment cleanup is preserved as a legitimate small fix.
- **`.intent/META/synthetic_workers.json` — surfaced for governor deletion** (constitutional core requires specific file-naming for deletion; cannot delete unilaterally).

### What remains as a forward-looking commitment from ADR-102 D2

The 5-field nucleus (`rule_id, severity, subject, evidence, worker_uuid`) remains the constitutional shape of a Finding. Its enforcement site moves from class-shape to blackboard-write boundary — i.e., enforced at `Worker.post_finding()` against payload dicts being inserted into `core.blackboard_entries`. The `worker_uuid` half is already enforced by the `blackboard_entries_worker_uuid_fkey` constraint. Structural validation of the other four fields at `post_finding` time is **out of scope** for this ADR and for ADR-102; it's filed as a follow-up for when prioritized.

### References

- **ADR-102** — Primary driver of this retirement. Read that for the full reframing.
- ADR-056 D3 — Narrowed in scope per ADR-102 D2 (nucleus commitment preserved; enforcement site moved).
- `[[feedback_two_surface_requires_two_structures]]` — The lesson this ADR (and its retirement) embodies: when forcing two distinct shapes through one contract creates persistent drift visibility, the unification was the bug.
- `[[feedback_count_from_source_not_narrative]]` — The discipline that produced the retirement. Three sessions of correction passes were the narrative reading. The grep-from-source produced the categorical answer.
- `[[feedback_layered_authority_three_way_check]]` — ADR > paper > code; here ADR-056 D3's bind held authority through ADR-099's three revision passes until the grep-from-code surfaced the category error.
