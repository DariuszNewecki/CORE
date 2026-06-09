<!-- path: .specs/decisions/ADR-099-finding-nucleus-migration.md -->

# ADR-099 — Finding-nucleus migration: alias-bridged reconciliation of CheckResult and AuditFinding to the canonical contract

**Date:** 2026-06-09
**Status:** Proposed
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
