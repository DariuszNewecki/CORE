---
kind: adr
id: ADR-131
title: ADR-131 — Governance Application Data Model
status: accepted
---

# ADR-131 — Governance Application Data Model

**Date:** 2026-06-28
**Governing paper:** `.specs/papers/CORE-Governance-Topology.md`
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Closes:** #479 (governance-application data model, unblocked by ADR-075 + namespace manifest)
**Grounding papers:** `papers/CORE-Governance-Topology.md` §2–§3; `papers/CORE-Governance-Topology.md` §8
**Related:** ADR-075 (framework/project namespace split), ADR-068 (principal role taxonomy), ADR-130 (constitutional artifact staging), ADR-053 (API domain model)

---

## Context

ADR-075 established the framework/project namespace split and the namespace
manifest. Both close-conditions of #457 are now satisfied. The follow-on issue
#479, filed as ADR-075 close-condition 3, requires a data-model design for the
governance application: the DB-backed web authoring surface for `.intent/` and
`.specs/` artifacts.

The governance application exists because the current authoring model has one
primary friction point: **validation only fires at audit time**. A governor
editing a rule YAML today has no feedback until the next audit cycle. The
application closes this gap by providing inline validation during authoring.

Three constraints shape the design space before any decision is made:

1. **Filesystem authority is settled law.** Every piece of work done to date
   treats `.intent/` and `.specs/` as the canonical, runtime-read source of
   truth. IntentRepository reads from disk. ADR-130 D1 hardened this into an
   unconditional invariant: no code path may write to `.intent/`; the governor
   is the write path. Replacing the filesystem with a DB as ground truth would
   reverse the most foundational constraint in the system — that is out of scope
   for this ADR and any near-term work.

2. **The namespace split (ADR-075) gives the schema a scoped problem.** Every
   artifact is classified as `framework` or `project::<name>`. The schema can
   model this natively. Without ADR-075, the data model would conflate artifacts
   with different ownership, lifecycle, and deployment semantics.

3. **The principal role taxonomy (ADR-068) exists.** `principal.governor`,
   `principal.operator`, `principal.auditor`, `principal.system` are declared.
   Access control can reference them without defining them here.

---

## Decisions

### D1 — Filesystem authority is unchanged; the application is an authoring layer

`.intent/` and `.specs/` remain the canonical source of truth that the runtime
reads. The governance application is a web authoring layer above the filesystem,
not a replacement for it.

The DB stores **draft state** and **authoring history** only. The filesystem
holds **applied state** — the constitution that `IntentRepository` reads at
runtime. This extends ADR-130's staging pattern (vocabulary.json draft in
`var/drafts/`) to the full governance surface: the application automates and
web-exposes the same staged-draft pathway.

A DB-native model (DB replaces `.intent/` as ground truth) is explicitly
deferred. No existing law motivates it; the cost of reversing the filesystem-
authority invariant is high; the governance application's design benefit does
not require it.

### D2 — Three-state draft lifecycle

Every governance artifact in the application has exactly one of three states:

| State | Location | Meaning |
|-------|----------|---------|
| `draft` | DB only | In-progress authoring, not yet validated |
| `staged` | DB only | Validated against schema; pending governor apply |
| `applied` | Filesystem (canonical) + DB record | Written to `.intent/`/`.specs/` and committed |

Transitions:

- `draft → staged`: requires schema validation to pass (D4). Any principal with
  write permission for that artifact's layer (D6) may trigger this.
- `staged → applied`: governor-role only (D5). Writes to filesystem, commits.
- `applied → archived` (DB record): when the applied artifact is deleted from
  the filesystem, the DB record is marked archived rather than deleted. Audit
  trail is preserved.

There is no direct `draft → applied` path. Staged is a mandatory checkpoint.

### D3 — Schema: governance_artifacts_draft table

The primary table for the authoring layer:

```sql
CREATE TABLE core.governance_artifacts_draft (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind            VARCHAR(64)  NOT NULL,   -- rule | worker | mapping | adr | paper |
                                             -- taxonomy | workflow | policy | contract |
                                             -- config | meta
    path            TEXT         NOT NULL,   -- canonical repo-relative path,
                                             -- e.g. .intent/rules/architecture/x.json
    governance_namespace  VARCHAR(128) NOT NULL,  -- 'framework' or 'project::<name>'
                                                   -- (ADR-075 D3 vocabulary)
    project_id      UUID         REFERENCES core.projects(id) ON DELETE RESTRICT,
                                             -- NULL for framework artifacts;
                                             -- project UUID for project:: artifacts
    content         JSONB        NOT NULL,
    schema_version  VARCHAR(32),             -- version of the .intent/META/ schema
                                             -- used for validation
    status          VARCHAR(16)  NOT NULL DEFAULT 'draft'
                                 CHECK (status IN ('draft', 'staged', 'applied', 'archived')),
    content_hash    TEXT,                    -- SHA-256 of content at staging time;
                                             -- revalidated at apply to detect tampering
    validation_errors  JSONB,               -- last validation result (null = not yet run)
    principal_id    UUID         NOT NULL REFERENCES core.principals(id),
    applied_at      TIMESTAMPTZ,
    applied_by      UUID         REFERENCES core.principals(id),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT governance_artifacts_draft_namespace_project_consistency CHECK (
        (governance_namespace = 'framework' AND project_id IS NULL)
        OR (governance_namespace <> 'framework' AND project_id IS NOT NULL)
    )
);
```

The consistency constraint closes the gap between the string classification
(governance_namespace) and the FK partitioning (project_id): a `framework`
artifact must have no project owner, and a `project::` artifact must have one.

`kind` is an open vocabulary at the DB level — the closed vocabulary is
enforced by the validation layer (D4) via the schema registry in `.intent/META/`.

### D4 — Write-time validation fires at draft → staged transition

Schema validation against the `.intent/META/` schema for the artifact's `kind`
runs at the `draft → staged` transition. It does not run at save (too expensive,
interrupts flow) and does not defer to audit time (too late, this is the gap
being closed).

Validation failure blocks the transition. The `validation_errors` column on
`governance_artifacts_draft` is updated with structured errors. The artifact
stays in `draft` state. The authoring UI renders these errors inline.

Validation runs against the same schemas that `IntentRepository` validates
against at runtime — there is one schema registry, and the application consumes
it rather than maintaining a parallel one. This ensures that a staged artifact
that passes the application's validation will also pass runtime loading.

### D5 — Apply is a governor-role action; it routes through FileHandler + commit_paths

The `staged → applied` transition is restricted to `principal.governor`
(ADR-068). The application executes the apply as:

1. Re-validate content hash (detect tampering since staging).
2. Write staged content to target path via `FileHandler.write_runtime_text()`.
3. Call `git_service.commit_paths([path], message)` with principal attribution
   in the commit message (`gov({principal_id[:8]}): apply {kind} {path}`).
4. Mark the DB record `applied`; set `applied_at`, `applied_by`.

Step 2 is the same FileHandler pathway that all production writes use. Step 3
is the same `commit_paths` call that the proposal execution pipeline uses for
code changes. No new mechanism is introduced; the governance application
composes existing governed surfaces.

This makes the application's "apply" button the web-equivalent of running:
```
cp var/drafts/... .intent/...
git add .intent/... && git commit -m "..."
```
from the CLI as governor. The hard invariant of ADR-130 D1 is not violated —
the governor IS the governed write path.

### D6 — Access control by governance layer

| Layer | Stage permission | Apply permission |
|-------|-----------------|-----------------|
| `framework` | `principal.governor` only | `principal.governor` only |
| `project::<name>` | `principal.operator` or above | `principal.governor` only |

Framework artifacts affect every governed project and every future BYOR
deployment. Only the governor may author them. Project artifacts affect only
the named project; operators may draft and stage but governors apply.

Apply is governor-only for both layers. This is the constitutional invariant:
the filesystem is always a governor-applied surface. Operators cannot bypass
this by clicking a button in the application.

### D7 — BYOR multi-tenancy via project_id null / non-null

`project_id IS NULL` identifies framework artifacts — shared across all
deployments, owned by CORE. `project_id = <uuid>` identifies project artifacts,
partitioned by project.

A BYOR deployment running against a shared CORE instance:
- Reads framework artifacts (project_id IS NULL) as the constitutional floor.
- Reads and writes its own project artifacts (project_id = its project UUID).
- Cannot stage or apply framework artifacts (D6: governor-only).

One DB instance, namespace-isolated by column. Multi-project governance is
supported by extension: each governed repo has its own project UUID; framework
artifacts are shared without duplication.

### D8 — Pre-flight validation exposed as a governed API endpoint

The application exposes a `POST /governance/validate` endpoint accepting:
```json
{ "kind": "rule", "path": ".intent/rules/...", "content": { ... } }
```
and returning structured validation results. This endpoint:

- Validates against the `.intent/META/` schema for the given `kind`.
- Returns errors in the same format as the `draft → staged` validation (D4).
- Requires `principal.operator` authentication minimum.
- Does not write to DB or filesystem.

Use cases: inline validation in authoring UI (before triggering the stage
transition), CI gates on governance artifact pull requests in external repos,
and programmatic pre-flight checks in BYOR scaffolding workflows.

---

## Consequences

- **Audit-time-only gap is closed.** Governors and operators see schema errors
  during authoring, not on the next audit cycle.
- **BYOR multi-tenancy is modelled.** The `project_id` column gives the schema
  first-class support for multiple governed repos against one CORE instance.
- **No new bypass of the filesystem invariant.** The application composes
  `FileHandler` + `commit_paths()`; it does not introduce a new write path.
- **One schema registry.** The application validates against `.intent/META/`
  schemas, the same registry `IntentRepository` uses. Schema drift between
  authoring-time and runtime validation is structurally impossible.
- **Implementation is deferred.** This ADR accepts the data model; the
  application implementation (web UI, API routes, migration) is a follow-on
  tracked separately. The `governance_artifacts_draft` migration and the
  `/governance/validate` endpoint are the first implementation deliverables.

---

## Verification

This ADR closes #479 when:

- `governance_artifacts_draft` migration authored and applied.
- `POST /governance/validate` endpoint implemented and returning structured
  schema validation results.
- A follow-on issue filed for the web authoring UI implementation.

---

## References

- `papers/CORE-Governance-Topology.md` §2–§3 — governance surface definitions
  and directional relation graph; §8 — framework/project principle.
- ADR-075 — Framework / Project Namespace Split; D3 (`governance_namespace`
  vocabulary), D6 (per-layer manifest), D7 (completeness enforcement).
- ADR-068 — Principal Role Taxonomy; declares `principal.governor`,
  `principal.operator`, `principal.auditor`, `principal.system`.
- ADR-130 — Constitutional Artifact Staging; D1 (filesystem hard invariant),
  D2 (staged-draft pathway). This ADR extends that pattern to the full
  governance surface.
- ADR-053 — API Domain Model; D7 (`requested_by` attribution field).
- Issue #479 — Governance application data model (this ADR's target issue).
- Issue #457 — Constitutional layer reorganization; ADR-075 close-condition 3
  filed this issue.
