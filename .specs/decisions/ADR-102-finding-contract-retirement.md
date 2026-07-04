---
kind: adr
id: ADR-102
title: 'ADR-102 — Finding.json retirement: class-shape was the wrong enforcement site
  for the constitutional Finding nucleus'
status: accepted
---

<!-- path: .specs/decisions/ADR-102-finding-contract-retirement.md -->

# ADR-102 — Finding.json retirement: class-shape was the wrong enforcement site for the constitutional Finding nucleus

**Date:** 2026-06-09
**Governing paper:** `.specs/papers/CORE-Finding.md`
**Status:** Accepted (2026-06-09)
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-09, ADR-099 implementation pass — step 3's worker_registry seed surfaced a schema mismatch which triggered a step-back review of the whole migration's purpose. The investigation found that CheckResult and AuditFinding are local data carriers, not blackboard-persisted Findings; the bind that produced the 16 findings on `data.contracts.finding_nucleus_conforms` was a category error in ADR-056 D3.)
**Grounding paper:** ADR-056 D3 — *"Layer-specific extensions are permitted; nucleus fields are not optional."* The nucleus commitment is preserved; what changes is its enforcement site. The class-shape binding to CheckResult and AuditFinding was wrong; nucleus enforcement belongs at the blackboard-write boundary, not at Pydantic class declaration.
**Related:**
- ADR-056 D3 (the binding being narrowed; the 5-field nucleus commitment itself remains constitutional)
- ADR-099 (most decisions superseded by this ADR; see ADR-099 Revision C for the formal supersession ledger)
- `.intent/enforcement/contracts/Finding.json` v1.1.0 (deleted by this ADR)
- `.intent/enforcement/contracts/CheckResult.json` v1.0.0 (preserved, unchanged — already governs CheckResult against its own field shape; produces zero findings)
- `.intent/enforcement/contracts/AuditFinding.json` v1.0.0 (preserved, unchanged — already governs AuditFinding's persistence shape; produces zero findings)
- `.intent/enforcement/contracts/BlackboardEntry.json` (preserved, unchanged — already governs the blackboard entry shape; the actual constitutional Finding surface)
- `src/will/workers/audit_ingest_worker.py` — the bridge from Mind-layer evaluation to blackboard post. Demonstrates that worker-attribution at the write boundary already works correctly without sentinel infrastructure.
- Memory: `[[feedback_two_surface_requires_two_structures]]` — directly relevant. The 16 findings are exactly the case where forcing two distinct shapes (Mind evaluator return type, blackboard payload) through a single contract creates drift visibility that screams "the unification was the bug."
- Memory: `[[feedback_count_from_source_not_narrative]]` — the investigation was the disciplined version of this rule. The ADR-099 trajectory was reading from the narrative (ADR-056 D3 says these classes are Findings; build the infrastructure to make them conform). The step-back was the re-read: grep where the classes are actually instantiated, who consumes them, whether they cross the persistence boundary.

---

## Context

### What ADR-099 was doing and why we stopped

ADR-099 was a ten-step migration to reconcile CheckResult and AuditFinding with the Finding nucleus declared in `.intent/enforcement/contracts/Finding.json`. The migration produced two revisions (A, B) in a single session — each correcting a load-bearing mechanism error the previous draft made (Pydantic-on-non-Pydantic dataclass; UUID collision with the live ADR-017 D4 claimer). Implementation reached step 2; step 3's worker_registry seed surfaced a third issue (the seed columns specified in the ADR don't match the actual schema — no `status` column exists; `last_heartbeat` is NOT NULL with default).

Three correction passes in one session is a pattern. Each correction found another gap; none of them changed the fundamental approach. The step-back question — *what are we actually trying to accomplish, and is this approach earning its weight?* — produced this ADR.

### The investigation

The load-bearing fact ADR-099 inherited from ADR-056 D3 was: CheckResult and AuditFinding are constitutional Findings; they must conform to the 5-field nucleus (`rule_id, severity, subject, evidence, worker_uuid`). The investigation grep'd what these classes actually do:

**AuditFinding** is instantiated in 23 sites, **all under `src/mind/`**:
- `mind/governance/rule_executor.py` (5 sites)
- `mind/governance/constitutional_auditor_dynamic.py` (2 sites)
- `mind/logic/engines/*.py` — knowledge_gate, artifact_gate, taxonomy_gate, runtime_gate, _knowledge_gate_duplication (16 sites)

Plus 4 sites in `src/body/services/crate_processing_service.py` for crate validation results.

It's consumed as `list[AuditFinding]` return values from rule evaluation functions. **Zero grep hits for AuditFinding near `post_finding` or `blackboard_entries`.** Mind layer is constitutionally forbidden from DB access (`architecture.mind.no_database_access`). AuditFinding does not cross the persistence boundary.

**CheckResult** is instantiated in 3 sites:
- `body/autonomy/micro_proposal_executor.py` (7 sites) — internal to `validate_proposal()` return path
- `body/services/cim/policy.py` (6 sites) — CIM policy evaluation
- `body/services/cim/models.py` (1 site — the class definition)

It is consumed via `list[CheckResult]` returns from `validate_proposal()` and similar evaluation methods. **Zero persistence path.** CheckResult never leaves the proposal-validation function.

**The bridge to the blackboard is `audit_ingest_worker`** (Will layer):
- Calls Mind's `_run_audit()` and receives a list of finding-dicts
- For each, calls `self.post_artifact_finding(...)` with a payload constructed inline (`rule`, `file_path`, `line_number`, `message`, `severity`, `status`)
- `worker_uuid` populated automatically by the Worker base class with `audit_ingest_worker`'s own UUID
- The blackboard payload is JSONB, not a Pydantic class

### What this means

The constitutional Finding — the thing whose attribution and shape matters across the system — is the **blackboard JSONB payload**, not CheckResult or AuditFinding. The blackboard payload:
- Already conforms structurally (workers carry UUIDs, payloads carry rule_id and subject and severity semantically)
- Is enforced at the **write boundary** via `Worker.post_finding()` and the `worker_uuid` FK on `blackboard_entries`
- Has its own contract (`BlackboardEntry.json`) which governs the entry shape

CheckResult and AuditFinding are **data carriers between layers** — Mind evaluator return types, proposal-validation result types. They are not the constitutional Finding surface. They never cross the persistence boundary. Binding them to a class-shape contract that demands `worker_uuid` is asking a data carrier to wear an attribution that belongs to a different category of object.

Both classes are *also already governed* by their own per-class contracts:
- `CheckResult.json` — required `[id, severity, rule, evidence, recommendation]`. CheckResult has all of these. Zero findings.
- `AuditFinding.json` — required `[check_id, severity, message]`. AuditFinding has all of these. Zero findings.

Finding.json's binding of these two classes is **duplicative and wrong-shape**. It overlays a nucleus contract on classes that are already correctly governed by their own contracts. The 16 findings are not signal that the classes are wrong — they are signal that **Finding.json's binding is wrong.**

### The category error

ADR-056 D3 conflated two distinct concerns when it specified the Finding nucleus:

1. **The "what's wrong" shape** — `rule_id, severity, subject, evidence`. These genuinely cross-cut every violation-like emission in CORE. The nucleus is right about this.
2. **Attribution** — `worker_uuid`. Makes sense for blackboard-persisted findings (workers post them, FK-enforced, liveness-tracked). Does not make sense for transient evaluator return types whose lifecycle ends at the function return.

ADR-099 D1 tried to solve the second-concern problem (non-worker emitters of class instances tagged with worker_uuid) by inventing synthetic workers. The synthetic workers are a category-blurring workaround: registering "operator-run" and "ci-run" in worker_registry to pretend they are workers, so the nucleus's `worker_uuid` requirement can be satisfied.

But the category error is upstream. CheckResult and AuditFinding don't need attribution at the class-declaration level because they are not the thing being attributed. The thing being attributed is the blackboard entry. The blackboard entry already has a worker behind it (the worker that called `post_finding`). The Mind-layer evaluation return path produces *information about violations*, not *attributed findings*; the attribution happens at the bridge when the Will-layer worker decides to persist some of that information.

---

## Decisions

### D1 — Finding.json is retired

Delete `.intent/enforcement/contracts/Finding.json`. The contract's binding of CheckResult and AuditFinding to a 5-field nucleus including `worker_uuid` was a category error. The 16 findings on `data.contracts.finding_nucleus_conforms` clear immediately upon retirement — they exist exclusively because of this contract's `governed_classes` declaration.

The contract's title ("Finding — canonical constitutional nucleus") and intent ("the minimum-required field set that any object claiming to be a constitutional Finding must declare") remain valid conceptually, but the **enforcement site moves from class-shape to blackboard-write boundary** per D2 below.

### D2 — ADR-056 D3's nucleus commitment narrows in scope

The 5-field nucleus (`rule_id, severity, subject, evidence, worker_uuid`) remains the constitutional shape of a Finding. What changes is its **enforcement site**:

- **Before:** Finding.json's data_contract declaration, evaluated by the AST gate against Pydantic class field shapes.
- **After:** the blackboard-write boundary — i.e., enforced at `Worker.post_finding()` against payload dicts being inserted into `core.blackboard_entries`.

`Worker.post_finding()` already carries `worker_uuid` automatically (from the worker's identity). `worker_uuid` is FK-enforced by the `blackboard_entries_worker_uuid_fkey` constraint. The remaining four nucleus fields (`rule_id, severity, subject, evidence`) are operationally present in current `post_finding` usage but not currently structurally validated at the call site.

Structural validation of the remaining four fields at `post_finding` time is **out of scope for this ADR** — filed as follow-up. The architectural decision (nucleus is enforced at write, not at class) is what this ADR commits to; the validator implementation lands in a separate change-set when prioritized.

### D3 — CheckResult and AuditFinding continue under their existing per-class contracts

- `.intent/enforcement/contracts/CheckResult.json` continues to govern CheckResult against `[id, severity, rule, evidence, recommendation]`. Zero findings (the class conforms).
- `.intent/enforcement/contracts/AuditFinding.json` continues to govern AuditFinding against `[check_id, severity, message]`. Zero findings (the class conforms).

Neither requires nucleus-field conformance. The nucleus is for blackboard payloads, not for class declarations. The per-class contracts govern the persistence and serialization shapes these classes actually have.

### D4 — ADR-099 is retired except for its D3 (the `permitted_extensions` META schema clause) and step 1's implementation

ADR-099 D3 introduced the concept of `permitted_extensions` — a per-class allowlist of refinement fields beyond the nucleus. The structural concept is independently useful for future contracts that need to distinguish refinements from drift. The clause we landed on `.intent/META/data_contract.schema.json` in step 1 stays.

ADR-099's other decisions — D1 (synthetic workers), D2 (alias-bridged class rename), D4 (CheckResult-first sequencing), D5 (smoke test + audit-pipeline diff) — are retired. The class migrations they sequenced are unnecessary because the classes don't need to migrate to a nucleus they shouldn't be bound to.

See ADR-099 Revision C for the formal supersession ledger and the reverts that follow (synthetic_workers loader deletion; proposals_routes.py restoration; surface for `.intent/META/synthetic_workers.json` deletion).

---

## Verification

- **Contract-conformance check:** delete Finding.json. Re-run the audit. The 16 findings on `data.contracts.finding_nucleus_conforms` clear (the rule's contract is gone). CheckResult.json and AuditFinding.json continue to produce zero findings (existing per-class contracts already conform).
- **No-regression check:** no Pydantic class changes; no emitter changes; no DB schema changes. The blast radius of this ADR is one deleted contract file and a handful of reverts (documented in ADR-099 Revision C).
- **Blackboard surface intact:** `BlackboardEntry.json` continues to govern the blackboard entry shape. `Worker.post_finding()` and the `worker_uuid` FK continue to enforce attribution at the write boundary. The architectural shape of constitutional Finding enforcement does not change — only the misplaced class-shape overlay is removed.

## Out of scope

- **Write-boundary validation of the four non-`worker_uuid` nucleus fields at `Worker.post_finding`.** D2 commits to the architectural decision; the validator implementation is a separate change-set. The `worker_uuid` half is already enforced by the FK constraint.
- **Reintroducing a class-shape Finding contract.** Defer until a single unified Pydantic class for blackboard payloads emerges (and there is no current pressure for that). When/if it does, that class is the appropriate `governed_classes` entry — not data carriers like CheckResult or AuditFinding.
- **Revisiting BlackboardEntry.json's shape.** Out of scope. The existing contract already governs the blackboard entry; whether its required fields fully cover the nucleus is a separate question for a separate ADR.
- **Revisiting ADR-017 D4's claimer-UUID pattern.** The pattern remains valid for its own scope (proposal claim attribution). ADR-099 Revision B's framing of "consolidating ADR-017 D4 into a synthetic-worker ledger" is dropped along with the rest of ADR-099 D1; ADR-017 D4 stays as it was.
- **CheckResult / AuditFinding internal field shapes.** The per-class contracts (CheckResult.json, AuditFinding.json) govern these and are appropriate. Changes to those shapes are governed by those contracts, not by this ADR.

## References

- ADR-056 D3 — The constitutional nucleus commitment (narrowed in enforcement-site, not in field-shape).
- ADR-099 (all revisions) — Retired except D3 (kept) and step 1 (kept). See ADR-099 Revision C.
- ADR-099 #598 (originating issue) — Resolved by this ADR through retirement rather than migration.
- `.intent/enforcement/contracts/Finding.json` — Deleted.
- `.intent/enforcement/contracts/CheckResult.json` — Preserved.
- `.intent/enforcement/contracts/AuditFinding.json` — Preserved.
- `.intent/enforcement/contracts/BlackboardEntry.json` — Preserved; remains the contract for the actual constitutional Finding surface.
- `.intent/META/data_contract.schema.json` — `permitted_extensions` clause from ADR-099 D3 step 1 retained.
- `src/shared/models/audit_models.py` — `AuditFinding` definition; unchanged.
- `src/body/services/cim/models.py` — `CheckResult` definition; unchanged.
- `src/will/workers/audit_ingest_worker.py` — The bridge from Mind evaluation to blackboard post. The architectural site where attribution actually happens.
- `src/shared/workers/base.py` — `Worker.post_finding()`; the future site of D2's write-boundary nucleus validation.
- Memory: `[[feedback_two_surface_requires_two_structures]]`
- Memory: `[[feedback_count_from_source_not_narrative]]`
- Memory: `[[feedback_layered_authority_three_way_check]]`

---

## Investigation record

The disciplined version of the investigation — for the audit trail of how this ADR was reached — is captured in the session transcript that produced it. Key beats:

1. **Step 3 schema mismatch.** Pre-write check for the worker_registry seed found that the ADR-099 D1 spec ("status active, no heartbeat") referenced columns that don't exist (`status`) and a state that the schema doesn't allow (`last_heartbeat` is NOT NULL DEFAULT now()).
2. **Helicopter pause.** Two correction passes (Revision A, Revision B) in one session, plus a third pending, was the signal to step back rather than push through.
3. **Category check.** Asking "why do we even have these 16 findings, and why do we need constitutional infrastructure for non-worker attribution" reframed the problem.
4. **Grep.** Confirmed AuditFinding (23 sites) lives exclusively in Mind layer; CheckResult (3 sites) lives in CIM/proposal-validation; neither crosses the persistence boundary; the bridge worker (audit_ingest_worker) does the attribution correctly.
5. **Contract inventory.** Confirmed CheckResult.json and AuditFinding.json already exist and already govern their respective classes with zero findings each. Finding.json is the duplicative binding.

The category error in ADR-056 D3 was inheritable: the bind was made when the three-surface analysis was nascent and CheckResult/AuditFinding looked like reasonable proxies for the "constitutional Finding" concept. The Mind/Body/Will discipline that's matured since (Mind cannot persist; Body and Will run the bridge) makes the distinction sharper than it was when ADR-056 was written. ADR-102 is the corrective.

---

## 2026-06-09 addendum — layer-distribution claim refinement

While implementing the audit rule that prevents this class of error (#612), verification surfaced that **AuditFinding's instantiation distribution is actually `{body, cli, mind, will}` — not "exclusively in `src/mind/`"** as the Context section above stated. The error was conflating "Mind-instantiated as a data-evaluation return type" (true for the majority of sites) with "Mind-only" (false; AuditFinding is also constructed in body crate-processing, will workers, and cli-layer adapters as a return-shape data carrier).

**The categorical conclusion is unchanged.** The load-bearing fact ADR-102 leans on is the *persistence-reach* claim, not the *layer-distribution* claim: no AuditFinding instance is ever passed to `Worker.post_finding()` or inserted into `core.blackboard_entries`. The blackboard payload posted by `audit_ingest_worker` is constructed as a dict inline, not as an AuditFinding instance. The grep evidence for that persistence-reach claim is unchanged. AuditFinding is still a transient data carrier; it still doesn't cross the persistence boundary; it still doesn't need to conform to a nucleus that requires blackboard attribution.

**What this refinement means for the audit rule (#612).** The implemented rule (`data.contracts.layer_scope_coherence`, in `src/mind/logic/engines/contracts_gate.py`) uses the *narrower* heuristic — classes whose instantiation sites are exclusively in a forbidding layer — because that's what static analysis without dataflow can determine. AuditFinding doesn't trip this narrower rule. The broader version (dataflow-based detection of "class is never reached by a worker-attribution write site") is filed as #619 follow-up.

The narrower rule still has standalone value: it would prevent a future case where a developer added a contract requiring `worker_uuid` and bound a pure-Mind class (an evaluator-internal data carrier) to it. The ADR-099 specific case (AuditFinding spanning 4 layers as a return-shape) needs the broader rule. Both rules together close the category-error gate.

This addendum is a transparency note, not a substantive revision of the ADR's decisions — D1 through D4 stand as written, anchored on the persistence-reach claim that the implementation-pass verification did not falsify.
