---
kind: adr
id: ADR-121
title: 'ADR-121 — T5b: Document corpus Repository type — domain-agnostic governed document corpus'
status: accepted
---

<!-- path: .specs/decisions/ADR-121-t5b-grc-document-repository-type.md -->

# ADR-121 — T5b: Document corpus Repository type

**Status:** Accepted — 2026-08-24
**Date:** 2026-06-21 (proposed); accepted 2026-08-24
**Reconciliation (2026-08-24):** a governor-initiated D1–Dn implementation-conformance review
found this ADR's text diverged from what actually shipped on D2 (worker placement, config
location) and D4 (action ID). A second pass, prompted by the same review, corrected D3's
`catalog_names: []` semantics from fail-open (silently running everything when publication status
is unknown) to fail-closed (`CatalogPublicationUnknownError`) — a Governor-directed honesty
correction to the implementation itself, not just the text. D2, D3, and D4 below carry dated
reconciliation notes preserving the original (superseded) text rather than silently rewriting
over it. This reconciliation was itself a text/behavior correction, not the acceptance decision.
**Acceptance (2026-08-24):** with D1–D7 and the verification-criteria matrix confirmed conformant
to the reconciled implementation (65/65 applicable tests passing, ruff/mypy clean, constitutional
audit PASS), the Governor accepted this ADR as-is — status moves from Proposed to **Accepted**.
**Grounding papers:** `CORE-BYOR.md` §3 (Repository seam — artifact corpus + typed sensor), §7
  (GRC as first non-code Repository type; honesty guardrail), §9.3 (regulation→Intent representation
  — the GRC second domain, T5b).
**Builds on:** ADR-116 (GRC catalog residency, tiers, `catalog_resolver`), ADR-118 (RequirementVerdict
  as the verdict unit; applicability gate), ADR-120 (T5a — Repository adapter contract: D2 three-part
  declaration, D4 ADR-092-A trigger, D5 project-authored discovery, D6 ActionExecutor refusal gate).
**Closes:** BYOR backlog T5b (`.specs/planning/CORE-BYOR-Program-Backlog.md`).
**Triggers:** ADR-092-A obligation (recorded in ADR-120 D4 forward marker) — first non-Python atomic
  action ships in this change-set; the trigger fires here.
**Relates:** ADR-091 (F-42 pluggable sensor), ADR-092 (F-43 exit criterion), ADR-090 (F-41 registry),
  ADR-113 (per-finding evidence class).

---

## Context

### What T5b must deliver

ADR-120 D2 defined the Repository adapter as a **three-part declaration** (F-41 type + F-42 sensor +
F-43 action). T5b ships the first non-Python adapter: a governed document corpus. GRC gap-analysis
(CORE-BYOR §7) is the **first instance** of this adapter, not the only instance. The adapter itself
must be domain-agnostic.

Three design surfaces remain open after ADR-116:

1. **F-41 type** — no document corpus artifact type exists.
2. **F-42 sensor** — no worker reads a document corpus and posts gap findings.
3. **F-43 action + ADR-092-A trigger** — no non-Python atomic action; `supported_actions: []` is
   correct today (ADR-120 D4 forward marker); this ADR fires the trigger.

The `GRCGapAnalysisService` (Body service) and `catalog_resolver` (ADR-116 D4) are already
implemented. T5b wires them into the governed Repository adapter; it does not re-implement them.

### The domain-agnosticism observation

Examining what is actually GRC-specific in the existing service:

- **`GRCGapAnalysisService.run(corpus_root, catalog)`** — takes any `Path` and any
  `list[ExecutableRule]`. The class name is the only GRC-specific thing; the engine is generic.
- **`ExecutableRule`** — engine-agnostic (regex_gate, llm_gate, attestation_gate). No GRC coupling.
- **`RequirementVerdict`** (ADR-118) — one verdict per requirement over a corpus. The concept
  applies equally to legal contracts, medical records, financial statements, HR policies — any corpus
  evaluated against a set of requirements.
- **The catalog** — the YAML files in `grc-catalogs/` — is the only content that is domain-specific.

The implication: if T5b ships `grc_document` + `GrcCorpusSensor` + `grc.run.gap_analysis`, adding a
second document domain (legal contract review, clinical protocol compliance, financial audit) would
require a new artifact type, a new sensor, and a new action — even though the runtime behaviour is
identical. The domain lives in the catalog, not in the adapter.

**T5b therefore ships a domain-agnostic adapter.** The GRC domain is expressed through catalog
content and `catalog_root` configuration; the infrastructure is reusable by any document corpus
domain without new Python or new F-41/F-42/F-43 declarations.

### Two distinct document surfaces in GRC

**The catalog (Intent side):** CORE-authored requirements derived from regulation — the product
asset (ADR-116). Already governed by the catalog residency model. T5b does NOT touch catalog
authorship or residency.

**The customer corpus (Artifact side):** the customer's compliance evidence documents — policies,
procedures, records, audit logs. This is the *Repository* CORE governs. T5b introduces the
domain-agnostic artifact type, sensor, and action for this surface; catalog selection makes it GRC.

---

## Decision

### D1 — `document_corpus` artifact type (F-41 declaration)

The artifact type ID is **`document_corpus`**. It is the governed unit for any collection of
documents evaluated against a requirements catalog — GRC, legal, financial, or otherwise.

```yaml
# .intent/artifact_types/document_corpus.yaml
$schema: "META/artifact_type.schema.json"
kind: artifact_type

id: document_corpus
title: Governed document corpus
description: >
  A collection of documents (policies, procedures, records, contracts, or any
  structured artifact set) evaluated against a requirements catalog. The Artifact
  side of CORE's corpus governance model (CORE-BYOR §3): CORE supplies the Intent
  (a catalog of checkable requirements); the project brings the Artifact (their
  document library). Domain is expressed through catalog selection — no new
  artifact type is needed when adding a new domain; a new catalog suffices.
  Discovery is project-authored (ADR-120 D5, ADR-121 D3): the framework ships
  the sensor; the project configures the corpus path.

discovery: []                # project-authored (ADR-120 D5)
identity_key: path
schema_ref: null
change_record: text_diff
vector_collection: document-corpus
crawler_indexed: false       # DocumentCorpusSensor handles enumeration; repo_crawler does not

supported_sensors:
  - document_corpus_sensor
supported_actions: []        # populated when document.gap_analysis ships (D4/D5 below)
```

**`crawler_indexed: false`** — the repo crawler walks project source trees. A customer's document
library may live at an OS-level path, a mounted volume, or outside the project tree entirely. The
sensor handles enumeration from the configured `corpus_root`.

**`vector_collection: document-corpus`** — separate from `core-code` / `core-tests` / `core-docs`.
Documents from different domains may co-exist in this collection; catalog-name metadata on each
vector record enables domain-scoped retrieval when needed.

### D2 — `DocumentCorpusSensor` Worker design (F-42 binding)

**Reconciliation note (2026-08-24 — Governor decision, ADR-121 D1–Dn conformance review).**
As originally written (2026-06-21), D2 below specified Body placement: *"A new `Worker`
subclass, `DocumentCorpusSensor`, in `src/body/workers/document_corpus_sensor.py`."* That text
was a governance-authoring error, not implementation drift — `DocumentCorpusSensor` shipped at
`src/will/workers/document_corpus_sensor.py` from the initial implementation commit (`a9b19264`,
2026-06-21) onward, whose own commit message already states "Will layer." This is consistent
with 37 of 39 worker declarations in the fleet and with the constitutional rule
`architecture.layers.no_body_to_will`, which names `will.workers` as a recognized Will sub-path.
The Governor confirmed Will as the approved architecture; D2's text below is corrected to match
the shipped implementation. Similarly, the worker declaration's `corpus_root`/`catalog_root`/
`catalog_names` fields below now show the `config:` block they actually live in — moved there
from `mandate.scope` in commit `5aa900e4` (2026-06-23) because `mandate.scope`'s JSON schema
carries `additionalProperties: false` and rejected them; `config:` is ratified here as the
correct, narrow home for this worker's settings, not a fleet-wide convention change. At the time
this note was written, **ADR-121 remained `status: proposed`** — this note recorded a text
correction reconciling the ADR with what was already shipped and governor-approved, distinct from
acceptance. Acceptance followed separately, once all reconciliation was complete — see the
Acceptance note at the top of this document.

A `Worker` subclass, `DocumentCorpusSensor`, in `src/will/workers/document_corpus_sensor.py`:

```
declaration_name = "document_corpus_sensor"
class: sensing
mandate.scope.artifact_type: [document_corpus]
```

**What it does per run:**

1. Reads `corpus_root` from the declaration's `config.corpus_root`. If absent or empty, logs a
   warning and posts `post_heartbeat()` — the sensor is declared but unconfigured. Does **not**
   raise or fail the daemon; other sensors continue.
2. Reads `catalog_root` from `config.catalog_root`. If absent, falls back to
   `settings.paths.grc_catalogs_dir` (backward-compatible default for the GRC first instance).
   Any domain pointing its own catalog tree sets this field explicitly.
3. Reads `catalog_names` from `config.catalog_names` (list of strings). If
   empty, resolves all frameworks with `status == "published"` from `<catalog_root>/inventory.yaml`
   via `catalog_resolver.discover_published_catalogs()` — automatic coverage of every catalog
   available at the configured root that has actually been published, not merely authored.
   An explicit `catalog_names` list bypasses this gate (the project's own opt-in).
4. For each active catalog: loads it via `load_catalog(name, catalog_root=...)`, instantiates
   `DocumentCorpusAnalysisService` (renamed from `GRCGapAnalysisService`, D7), calls
   `await service.run(corpus_root, catalog)`, receives `list[RequirementVerdict]`.
5. For each `RequirementVerdict` with a gap status posts a finding via
   `self.post_artifact_finding(artifact_type=..., sub_namespace=..., identity_key_value=...,
   payload=...)` — subject format per D6.
6. Posts `self.post_heartbeat()` once per run after all catalogs.

**The sensor never modifies documents.** Read-only throughout (CORE-BYOR §5 parameter 3).

**LLM availability:** sensor instantiates `DocumentCorpusAnalysisService` without an LLM client
by default. Without a wired client, `judged` requirements degrade to `RequirementStatus.UNAVAILABLE`
— the honest degradation path (ADR-118 D4). T5d wires the LLM substrate.

**Worker declaration** (`.intent/workers/document_corpus_sensor.yaml`):

```yaml
kind: worker
id: document_corpus_sensor
class: sensing
description: >
  Reads a document corpus against one or more requirements catalogs and posts
  gap findings to the blackboard. Domain is expressed through catalog selection.
  Project-authored configuration required (ADR-121 D3).

implementation:
  class: DocumentCorpusSensor
  module: will.workers.document_corpus_sensor

mandate:
  scope:
    artifact_type: [document_corpus]
  schedule:
    max_interval: 3600

config:
  corpus_root: ""          # REQUIRED: project configures path to document library
  catalog_root: ""         # optional: overrides default (grc-catalogs/); set for non-GRC domains
  catalog_names: []        # optional: empty = all published catalogs at catalog_root
```

### D3 — Project-authored corpus configuration convention

`corpus_root`, `catalog_root`, and `catalog_names` are the project author's configuration surface.
CORE ships the declaration with empty defaults; the project fills them in:

```yaml
# GRC project — .intent/workers/document_corpus_sensor.yaml (project-authored)
mandate:
  scope:
    artifact_type: [document_corpus]
  schedule:
    max_interval: 7200
config:
  corpus_root: "compliance/"               # relative to repo root
  catalog_root: ""                         # uses grc-catalogs/ default
  catalog_names: [nist_800_171, cfr_part_11]

# Legal domain project (future) — same sensor, different configuration
mandate:
  scope:
    artifact_type: [document_corpus]
  schedule:
    max_interval: 3600
config:
  corpus_root: "/mnt/contracts"
  catalog_root: "/mnt/legal-catalogs"      # domain-specific catalog root
  catalog_names: [contract_review_standard]
```

(`corpus_root`/`catalog_root`/`catalog_names` live in a top-level `config:` block, not
`mandate.scope` — see the D2 reconciliation note above for why.)

**`corpus_root` resolution:** relative paths resolve from `repo_root`. Absolute paths are used
as-is. This lets a project store its evidence corpus under a project-controlled path (`compliance/`)
without requiring an absolute mount.

**`catalog_root` fallback:** when empty/absent, the sensor uses `settings.paths.grc_catalogs_dir`
(backward-compatible default). GRC projects require no change; non-GRC domains set the field.

**`catalog_names: []` semantics:** run all catalogs with `status: published` found at
`catalog_root/inventory.yaml`, via `catalog_resolver.discover_published_catalogs()`. New
published catalogs are automatically included. A project that wants to restrict which catalogs
run lists only the ones it accepts (bypassing the publish gate — an explicit list is the
project's own opt-in).

**Reconciliation note (2026-08-24 — Governor decision, ADR-121 D1–Dn conformance review, second
pass).** As originally written and as first implemented, this paragraph continued: *"When
`inventory.yaml` is absent (a non-GRC domain has no framework-registry concept), no filter
applies and every discovered catalog runs."* That was fail-open: treating an absent or unreadable
inventory as "everything discovered is implicitly published" cannot be reconciled with the
honesty posture GRC gap-analysis exists to enforce (ADR-113, ADR-118 D4) — CORE must never infer
publication where it cannot establish it. The Governor corrected this. The publication-selection
semantics, as implemented and now normative, are:

- **Explicit `catalog_names`** is authoritative project selection and bypasses automatic
  publication discovery entirely — the project has already vouched for these catalogs by name.
- **Empty `catalog_names`, `inventory.yaml` present and readable** — run only frameworks with
  `status: published` in it.
- **Empty `catalog_names`, but catalogs are discovered on disk and `inventory.yaml` is missing or
  unreadable** — publication status cannot be established. Automatic discovery **fails closed**:
  `catalog_resolver.discover_published_catalogs()` raises `CatalogPublicationUnknownError` rather
  than running anything; both call sites (`DocumentCorpusSensor.run()`, `document.gap_analysis`)
  catch it and surface a specific, non-silent diagnostic — a distinct logged skip for the sensor,
  `ActionResult(ok=False, data={"error": ...})` for the action — never a silent empty run and
  never "run everything."
- **No catalogs discovered on disk at all** — an unambiguous empty result (nothing to be uncertain
  about), returned without error, exactly as before.

This is a narrow correction to D3's publication-selection semantics, not new catalog doctrine:
it does not change what "published" means, does not touch `inventory.yaml`'s schema (ADR-116
D7), and does not extend the publish gate to any surface beyond `catalog_names: []` resolution.

**Reconciliation note (2026-08-24 — Governor decision, `config:` approval).** The D2 reconciliation
note above already recorded *why* `corpus_root`/`catalog_root`/`catalog_names` moved from
`mandate.scope` to a top-level `config:` block (commit `5aa900e4`: `mandate.scope`'s schema
carries `additionalProperties: false` and rejected them). This note is the Governor's explicit
approval of that placement, not merely an acknowledgment that it was schema-forced:

`config:` is approved for `document_corpus_sensor` because `corpus_root`, `catalog_root`, and
`catalog_names` are **worker-specific operational configuration** — parameters this worker needs
to execute its mandate — not part of the worker's *governed* mandate/scope (which declares
responsibility, authority, artifact-type scope, and scheduling; ADR-121 D2's `mandate.scope`
carries only `artifact_type` today).

`document_corpus_sensor` is recorded here as evidence for a possible general separation between
**mandate** and **configuration** in the worker model:

- `mandate` expresses governed responsibility, authority, scope, and scheduling;
- `config` expresses worker-specific operational parameters needed to execute that mandate.

**This decision approves that separation for `document_corpus_sensor` only.** It is explicitly
*not* a CORE-wide worker-model convention — 38 of the fleet's other 39 worker declarations carry
no `config:` block at all, and this ADR does not ask them to change. A general convention is
deferred until additional worker cases provide enough evidence to justify one.

### D4 — First non-Python atomic action: `document.gap_analysis` (F-43 binding)

**Reconciliation note (2026-08-24 — Governor decision).** As originally written this action was
named `document.run.gap_analysis`. It shipped, and remains registered everywhere in code and in
`action_risk.yaml`, as **`document.gap_analysis`**. This naming mismatch left
`document_corpus.yaml`'s `supported_actions` (D5b) declaring an action ID (`document.run.gap_analysis`)
that was never actually registered — an asymmetry `governance.taxonomy.action_supported_by_declaration`
(D5a) is designed to catch, and did: it was live and unresolved until this reconciliation, which
corrects `document_corpus.yaml` to the canonical `document.gap_analysis` (see D5). D5 itself —
the taxonomy rule and its `taxonomy_gate` branch — is unchanged; it worked as designed.

`document.gap_analysis` is the first atomic action carrying
`artifact_types: [document_corpus]` in `action_risk.yaml`. This fires the ADR-092-A trigger.

**Action contract:**

```python
@atomic_action(
    action_id="document.gap_analysis",
    intent="Evaluate a document corpus against requirements catalogs; report coverage gaps",
    impact=ActionImpact.READ_ONLY,
    policies=["document.policy.analysis_scope"],
)
@register_action(
    action_id="document.gap_analysis",
    description="Evaluate a document corpus against one or more requirements catalogs",
    category=ActionCategory.CHECK,
    policies=["document.policy.analysis_scope"],
    requires_db=False,
    requires_vectors=False,
)
async def action_run_gap_analysis(
    corpus_root: str,
    catalog_names: list[str] | None = None,
    catalog_root: str | None = None,   # None → grc-catalogs/ default
    write: bool = False,
    core_context: Any = None,
    **kwargs: Any,
) -> ActionResult:
```

`action_risk.yaml` entry:
```yaml
document.gap_analysis:
  impact_level: safe
  artifact_types: [document_corpus]
```

**`write` flag semantics:** governs whether a report artifact is written to
`var/reports/corpus/<corpus_slug>_<catalog>_<timestamp>.yaml`. The corpus itself is never
mutated (`impact_level: safe` is unconditional).

**`ActionResult.data` summary:**
```python
data = {
    "corpus_root": str(corpus_root),
    "catalog_root": str(resolved_catalog_root),
    "catalogs_run": [...names...],
    "total_requirements": N,
    "covered": C,
    "not_covered": NC,
    "unavailable": U,
    "covered_unauthoritatively": CA,
}
```

Full `RequirementVerdict` records go to the report file (when `write=True`); the summary alone
fits `ActionResult.data`.

### D5 — ADR-092-A execution (obligated by ADR-120 D4 forward marker)

Same change-set as D4. The obligation fires because `document.gap_analysis` is the first
non-Python atomic action carrying a non-empty `artifact_types`.

**D5a — Author `governance.taxonomy.action_supported_by_declaration`**

New rule file `.intent/rules/governance/action_taxonomy.json`:

```json
{
  "$schema": "META/rule_document.schema.json",
  "kind": "rule_document",
  "metadata": {
    "id": "rules.governance.action_taxonomy",
    "title": "Action-to-Artifact-Type Coherence",
    "version": "1.0.0",
    "authority": "constitution",
    "phase": "audit",
    "status": "active"
  },
  "rules": [
    {
      "id": "governance.taxonomy.action_supported_by_declaration",
      "statement": "Every atomic action declaring `artifact_types: [X]` in action_risk.yaml MUST appear in artifact_type X's `supported_actions` array, and every entry in an artifact_type's `supported_actions` MUST correspond to a registered atomic action whose action_risk.yaml entry declares `artifact_types: [X]`. The two sets — authored (artifact_type `supported_actions`) and registered (action_risk.yaml `artifact_types`) — MUST be equal for each type.",
      "enforcement": "reporting",
      "authority": "constitution",
      "phase": "audit",
      "rationale": "ADR-092-A (triggered by ADR-121 T5b). F-43 cognate of `sensor_supported_by_declaration` (F-42, sensor_taxonomy.json). Ships at `reporting`; promotes to `blocking` at Phase 7 alongside the sensor rule. Completes the F-41 ↔ F-42 ↔ F-43 coherence triad."
    }
  ]
}
```

Enforcement mapping `.intent/enforcement/mappings/governance/action_taxonomy.yaml`:

```yaml
mappings:
  governance.taxonomy.action_supported_by_declaration:
    engine: taxonomy_gate
    params:
      check_type: action_supported_by_declaration
    scope:
      applies_to:
        - ".intent/enforcement/config/action_risk.yaml"
```

**D5b — Populate `supported_actions` on `document_corpus.yaml`**

```yaml
supported_actions:
  - document.gap_analysis
```

**D5c — Populate `supported_actions` on `python.yaml`** (and `test.yaml` if any Python-typed
actions declare `artifact_types: [test]` — verify at implementation against action_risk.yaml).

The 21 Python-specific actions with `artifact_types: [python]` in `action_risk.yaml`:

```yaml
supported_actions:
  - build.tests
  - check.body_contracts
  - check.imports
  - fix.atomic_actions
  - fix.body_ui
  - fix.capability_tagging
  - fix.docstrings
  - fix.duplicate_ids
  - fix.format
  - fix.headers
  - fix.ids
  - fix.imports
  - fix.logging
  - fix.modularity
  - fix.path_resolver
  - fix.placeholders
  - fix.purge_legacy_tags
  - fix.settings_access
  - fix.vulture_heal
  - test.execute
  - test.sandbox_validate
```

Derive this list at implementation time from `action_risk.yaml` entries — the ADR list above is
verified against current state; it is the authoritative reference but the implementation cross-check
is canonical.

**D5d — `taxonomy_gate` extension for `action_supported_by_declaration`**

The `taxonomy_gate` engine gains an `action_supported_by_declaration` check_type branch in its
`verify_context` method. Substrate: `action_risk.yaml` (action entries with `artifact_types`) cross-
validated against `.intent/artifact_types/*.yaml` (`supported_actions` arrays). Implementation scope:
one new branch in the existing gate; no new engine.

### D6 — Subject format for document corpus findings

Canonical format (ADR-091): `<artifact_type>::<sub_namespace>::<identity_key_value>`

| Finding type | Subject | Example |
|---|---|---|
| Per-requirement gap | `document_corpus::requirement::<requirement_id>` | `document_corpus::requirement::nist_800_171.doc_finalized` |
| Per-document finding | `document_corpus::document::<rel_path>` | `document_corpus::document::policies/access_control.md` |
| Corpus-level | `document_corpus::corpus::<catalog_name>` | `document_corpus::corpus::nist_800_171` |

**Primary subject:** `document_corpus::requirement::<requirement_id>` — one finding per non-covered
requirement per ADR-118's verdict unit. The requirement_id is authored in the catalog and stable
across runs (not a synthetic SHA).

**Payload structure:**
```python
{
    "requirement_id": verdict.requirement_id,
    "catalog": catalog_name,
    "catalog_root": str(resolved_catalog_root),
    "status": verdict.status.value,
    "evidence_class": verdict.evidence_class.value,
    "corpus_root": str(corpus_root),
    "evidence_count": len(verdict.evidence or []),
    "rationale": verdict.rationale or "",
}
```

### D7 — `GRCGapAnalysisService` renamed to `DocumentCorpusAnalysisService`

The service is the only caller in `src/cli/resources/grc/gap_analysis.py` and
`src/body/services/grc/__init__.py`. The rename is in-scope for this change-set:

- `src/body/services/grc/gap_analysis_service.py` — class renamed; public API unchanged
- `src/body/services/grc/__init__.py` — re-export updated; backward-compat alias
  `GRCGapAnalysisService = DocumentCorpusAnalysisService` added to avoid breaking any
  external callers (BYOR users who may import it directly)
- `src/cli/resources/grc/gap_analysis.py` — import updated (this call site actually kept
  importing `GRCGapAnalysisService` via the alias until the 2026-08-24 reconciliation pass
  — see the D2 note — corrected then, not in the original change-set)

The module file stays at `gap_analysis_service.py` (no file rename needed). The service's internal
logic, public method signatures, and test coverage are unchanged.

---

## Implementation change-set

Eight touch-points in one commit (ADR-092-A must land with D4's first action):

1. **`.intent/artifact_types/document_corpus.yaml`** — new F-41 declaration (D1). Must land with
   `document_corpus_sensor.yaml` — the two files together satisfy ADR-120 D3 cross-validation
   (P1–P4); neither is valid alone.

2. **`.intent/workers/document_corpus_sensor.yaml`** — new F-42 worker declaration (D2).
   `class: sensing`, `mandate.scope.artifact_type: [document_corpus]`, declaration name
   `document_corpus_sensor` matches `document_corpus.supported_sensors`.

3. **`src/body/workers/document_corpus_sensor.py`** — new `Worker` subclass (D2). Posts
   `document_corpus::requirement::<id>` findings for non-covered verdicts. Reads `corpus_root`,
   `catalog_root`, `catalog_names` from mandate. Calls `DocumentCorpusAnalysisService.run()`.

4. **`src/body/atomic/document/gap_analysis_action.py`** (new module) — atomic action
   `document.gap_analysis` (D4). `ActionCategory.CHECK`, `impact_level: safe`,
   `artifact_types: [document_corpus]`. Must be imported in `src/body/atomic/__init__.py`
   so `@register_action` fires at executor init.

5. **`.intent/enforcement/config/action_risk.yaml`** — add entry for `document.gap_analysis`
   (D4). Update `supported_actions` on `document_corpus.yaml` (D5b) and `python.yaml` (D5c).

6. **`.intent/rules/governance/action_taxonomy.json`** + **`.intent/enforcement/mappings/
   governance/action_taxonomy.yaml`** — new rule file and mapping (D5a).

7. **`taxonomy_gate` engine** — `action_supported_by_declaration` check_type branch (D5d).
   Confirm engine source path at implementation.

8. **`src/body/services/grc/gap_analysis_service.py`** + **`__init__.py`** + **`cli/resources/
   grc/gap_analysis.py`** — class rename `GRCGapAnalysisService` → `DocumentCorpusAnalysisService`
   with backward-compat alias (D7).

**Tests (minimum):**

- `test_document_corpus_sensor_no_corpus_root` — empty `corpus_root` → heartbeat only, no raise.
- `test_document_corpus_sensor_custom_catalog_root` — non-default `catalog_root` is passed to
  `load_catalog`; confirms non-GRC domains can point at a different catalog tree.
- `test_document_corpus_sensor_posts_gap_findings` — mock `DocumentCorpusAnalysisService.run()`
  returning two not-covered verdicts; assert two findings with correct subject format.
- `test_run_gap_analysis_action_summary` — mock service; assert `ActionResult.data` carries
  `covered`, `not_covered`, `total_requirements`, `catalog_root` keys.
- `test_action_supported_by_declaration_symmetric` — taxonomy_gate with symmetric
  `supported_actions` / `artifact_types`; assert no finding.
- `test_action_supported_by_declaration_asymmetric` — asymmetric; assert finding emitted.
- `test_document_corpus_cross_validation_symmetric` — `IntentRepository._validate_sensor_cross_
  references()` with `document_corpus` + `document_corpus_sensor` declarations; no error.

---

## Consequences

### Closes

- **BYOR backlog T5b** — `document_corpus` artifact type (F-41), `DocumentCorpusSensor` (F-42),
  `document.gap_analysis` (F-43). The three-part Repository adapter (ADR-120 D2) is complete
  for governed document corpora. GRC is the first configured instance.
- **ADR-092-A trigger** (ADR-120 D4 forward marker): `action_supported_by_declaration` rule
  authored; `supported_actions` populated; obligation closed.
- **Domain lock-in**: adding a new document corpus domain no longer requires new Python, new
  F-41/F-42/F-43 declarations, or a new change-set. A new domain = a new catalog.

### Opens / follow-on

- **New domain onboarding path (zero-code):** a legal-contract corpus, a clinical-protocol
  compliance corpus, or a financial-audit corpus uses `document_corpus` + `document_corpus_sensor`
  configured with their catalog root and catalog names. No new adapter; no new ADR needed unless
  the domain requires specialized pre-processing (e.g. OCR, DOCX parsing) — at which point a
  `DocumentCorpusSensor` subclass is the extension point.
- **T5c** (per-finding attestation) — `document_corpus::requirement::<id>` findings on the
  blackboard are the substrate. Unblocked.
- **T5d** (internal audit corpus) — `DocumentCorpusSensor` degrades to `UNAVAILABLE` without
  an LLM client today. T5d's Qdrant wiring + licence-gated corpus ingestion are the LLM
  substrate for judged verdicts at scale. Sensor LLM wiring is T5d scope, not T5b.
- **`action_supported_by_declaration` Phase 7 promotion** — `reporting` today; promotes to
  `blocking` at Phase 7 alongside `sensor_supported_by_declaration`.
- **`grc_catalogs_dir` in `PathResolver`** — remains named as-is (it is a concrete path for the
  GRC product asset, not the generic catalog root concept). The `catalog_root` mandate field is the
  generic override; `grc_catalogs_dir` remains the default for backward-compat.

### Does not change

- `DocumentCorpusAnalysisService` public API — rename only; method signatures unchanged.
- Catalog residency model (ADR-116) — `grc-catalogs/` layout unchanged.
- The eleven existing artifact_type declarations — unchanged except `python.yaml` gaining
  `supported_actions` (D5c).
- `Worker` base class and F-42 sensor contract — `DocumentCorpusSensor` is a new implementor.
- `catalog_resolver.py` — `discover_catalogs()` and `load_catalog()` are unchanged; the sensor
  passes `catalog_root` as the `catalog_root` override parameter already supported by the resolver.

---

## Alternatives considered

**`grc_document` + `GrcCorpusSensor` + `grc.run.gap_analysis` (original ADR-121 draft)**

Rejected on the helicopter-view principle: `GRCGapAnalysisService` is already a generic
document corpus engine — the GRC name is cosmetic. Making the artifact type, sensor, and action
domain-specific forces a new adapter change-set for every new document domain, even when the
runtime logic is identical. The domain lives in the catalog, not the adapter.

**Separate artifact types per domain (`grc_document`, `legal_document`, `medical_record`, …)**

Rejected: it conflates *document kind* (the type of artifact) with *evaluation domain* (which
catalog you run). A policy document that a GRC team uses for NIST 800-171 could simultaneously
be evaluated against a legal review catalog. The domain is a catalog selection concern; the
artifact type is a corpus structure concern. One type correctly models the artifact.

**Sub-typing via a `domain` field on the artifact type declaration**

Considered: `document_corpus` with a `domain: grc` field that the sensor reads to select default
catalog roots. Rejected: the mandate's `catalog_root` field is already the right locus for domain
scoping — it is project-configured, not framework-declared, which is the correct authority split.
A `domain` field on the type would re-introduce the coupling we are trying to avoid.

**Keep `GRCGapAnalysisService` name, skip rename (D7)**

Considered and rejected: the name misleads future implementors into believing the engine is
GRC-specific, which is the root cause of the original coupling. The rename has one caller; the
cost is trivial. The backward-compat alias ensures no external breakage.

---

## References

- `CORE-BYOR.md` §3 (Repository = artifact corpus + typed sensor; catalog drives domain), §5
  (autonomy ceiling — CORE reads, never modifies customer documents), §7 (first paid instance;
  honesty guardrail), §9.3 (T5b — regulation→Intent representation)
- ADR-116 D2/D3/D4 — catalog tiers, tier-agnostic resolution, `catalog_resolver`
- ADR-118 D1/D3/D4 — `RequirementVerdict` per requirement; non-covered = finding; silence ≠ gap
- ADR-120 D2/D4/D5/D6 — adapter contract; ADR-092-A forward marker; project-authored discovery;
  ActionExecutor refusal gate
- ADR-091 D4/D5 — `supported_sensors` cross-validation; sensor subject format; Phase 7 gate
- ADR-092 D1/D2 — F-43 exit criterion (refusal gate); `action_supported_by_declaration` parking
- ADR-113 — per-finding evidence class (proven/judged/attested); provenance chain
- `.specs/planning/CORE-BYOR-Program-Backlog.md` — T5b, T5c, T5d
- `.intent/rules/governance/sensor_taxonomy.json` — `sensor_supported_by_declaration` (F-42
  cognate of the `action_supported_by_declaration` rule authored in D5a)
- `src/body/services/grc/gap_analysis_service.py` — `DocumentCorpusAnalysisService.run()`
- `src/body/services/grc/catalog_resolver.py` — `discover_catalogs()`, `load_catalog()`
