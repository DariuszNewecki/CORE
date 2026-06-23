# ADR-105 Stage 2b Completion Plan

**Status:** Ready for dedicated session
**Created:** 2026-06-23
**Scope:** Fix 10 failing `.specs/` documents, wire `SpecsDocValidator`, protect the orphan

---

## 0. Context

ADR-105 D6 defined two validation hooks for `.specs/` documents:

- **Hook 1 — Load-time (Stage 2a):** Build `SpecsDocValidator` to validate YAML frontmatter
  headers against per-class schemas. **Done** — `src/mind/governance/specs_doc_validator.py`,
  commit `66a1d622` (2026-06-13). Deliberately left unwired: at commit time 181 docs lacked
  frontmatter, so wiring would have false-alarmed immediately.

- **Stage 2b — Frontmatter migration + wiring:** Backfill frontmatter across all modeled docs,
  then wire the validator into `constitution validate`. The Stage 2a commit message:
  *"Wiring lands with the frontmatter migration (Stage 2b)."*

Stage 2b is **95% complete.** The migration happened between June 13 and now. As of
2026-06-23, running `SpecsDocValidator.validate_all_documents()` against the repo produces:

```
Checked: 204  Valid: 194  Invalid: 10
```

The 10 failures have three distinct root causes. All are mechanical. No governor judgment
required except one enum-value call on ADR-112.

---

## 1. Root-cause map

### Root cause A — Unquoted YAML title containing `: ` (7 ADRs)

**Symptom:** `schema_violation` — `'kind' is a required property` (and id/title/status).

**Why:** The YAML parser treats `title: ADR-NNN — Foo bar: baz quux` as a nested mapping
when it encounters `bar: ` (colon-space) inside the scalar. `yaml.safe_load` raises
`mapping values are not allowed here`. `parse_frontmatter` catches the `YAMLError` and
returns `{}`. Schema validation then sees an empty dict — all required fields "missing."

**Confirmed via:** direct `yaml.safe_load` on the captured frontmatter block.

**Fix:** Wrap the `title:` value in single quotes. Any internal single quotes escaped as `''`.

**Affected files and their colon-space trigger:**

| ADR | Trigger in title |
|---|---|
| ADR-116 | `residency: law-as-data` |
| ADR-117 | `no janitor: a bounded` |
| ADR-119 | `Scout: BYOR Path 1` |
| ADR-120 | `T5a: Repository` |
| ADR-121 | `T5b: Document` |
| ADR-122 | `T5d: Internal` |
| ADR-123 | `T4: \`project onboard\`` — note: also contains backticks; use double quotes |

**Template fix (single-quote):**
```yaml
---
kind: adr
id: ADR-NNN
title: 'ADR-NNN — original title here'
status: accepted
---
```

---

### Root cause B — Status value `withdrawn` not in the closed enum (1 ADR)

**Symptom:** `schema_violation` — `'withdrawn' is not one of ['proposed', 'accepted',
'superseded', 'retired']`.

**Affected:** ADR-112 (`status: withdrawn`).

**Context:** ADR-112 was deliberately withdrawn after being proposed — never accepted.
Its body reads: *"Withdrawn — 2026-06-18. Superseded by the Scenario 1+4 scoping
decision... The BYOR onboard / starter-floor work this ADR addressed (Scenario 2) is
parked."* No other ADR holds a `supersedes: ADR-112` pointer.

**Governor call required:** `withdrawn` is not in the enum. Two options:

- Map to `retired` — the ADR was never accepted and its work area is parked. Semantically
  honest: `retired` covers "no longer in play," regardless of whether it was once accepted.
- Map to `superseded` — the body says "superseded by the Scenario 1+4 scoping decision,"
  but that's a strategic pivot, not a specific ADR. No `supersedes:` chain to wire up.

Recommendation: **`retired`** — the ADR was withdrawn before acceptance; it did not enter
the governance lifecycle the way a superseded ADR does.

Do NOT extend the enum to add `withdrawn`. The `adr_status` vocabulary is closed
(`enums.json`, constitutional core). An extension requires a governor act at that level.
The existing `retired` value covers this case.

---

### Root cause C — Missing frontmatter entirely (2 ADRs)

**Symptom:** `missing_header` — `No YAML frontmatter header (kind=adr)`.

**Affected:** ADR-124, ADR-125 — both authored 2026-06-21, after the migration was complete.
They were written using the older `**Status:** accepted` prose convention.

**Fix:** Add the standard 4-field header block at the top of each file.

**ADR-124** (`ADR-124-user-access-control.md`):
```yaml
---
kind: adr
id: ADR-124
title: 'ADR-124 — User Access Control (UAC)'
status: accepted
---
```

**ADR-125** (`ADR-125-web-frontend-architecture.md`):
```yaml
---
kind: adr
id: ADR-125
title: 'ADR-125 — Web Frontend Architecture'
status: accepted
---
```

---

## 2. Wiring step

`SpecsDocValidator.validate_all_documents()` has no caller in production. ADR-105 D6
says it belongs at **load-time** — called when the governance posture is validated. The
natural hook is `src/shared/infrastructure/intent/intent_validator.py`, which already
validates `.intent/` documents via `MetaValidator`. `SpecsDocValidator` is its sibling.

**Wiring location:** `intent_validator.py` — after `MetaValidator` runs, instantiate
`SpecsDocValidator(repo_root=repo_root)`, call `validate_all_documents()`, fold its
errors into the existing `ValidationReport`. This surfaces `.specs/` header violations
through the same `constitution validate` surface that `.intent/` violations use.

**Pre-condition:** All 10 failures must be fixed before wiring. Wiring with any invalid
docs produces errors on every validate run — the validator fails closed, and that's correct
behavior, but the session should start clean.

**Wire-in order:**
1. Fix the 10 docs (Roots A, B, C)
2. Re-run `SpecsDocValidator.validate_all_documents()` — confirm `Invalid: 0`
3. Wire into `intent_validator.py`
4. Run `core-admin intent validate` — confirm clean pass
5. Update test coverage: add a test that `validate_all_documents()` is called from
   `intent_validator.py` and that the 204-doc pass holds

---

## 3. Orphan protection for `specs_doc_validator.py`

`specs_doc_validator.py` is flagged `purity.no_orphan_files` because it has no production
caller — the `indeterminate/human` blackboard entry persists until Stage 2b wires it in.

**Two options:**

**Option A — Fix the orphan by completing the wiring (this session).**
Wire `SpecsDocValidator` into `intent_validator.py` as part of this plan. The file gets a
caller; the finding clears on the next audit cycle. Clean, no protection layer needed.

**Option B — Add a `planned_files:` param to the `no_orphan_files` enforcement mapping.**
Extend `purity.yaml` with a `planned_files:` list (alongside the existing `excludes:`).
The `_check_orphan_files` method in `knowledge_gate.py` reads it and skips those paths
with an advisory log, not a finding. The entry carries a `grounding:` field naming the
ADR. This is the general mechanism for any future planned-but-unwired file.

Both options are on the table; Option A is preferred if wiring lands in this session. If
the wiring is split into a separate session, implement Option B first so the orphan finding
does not continue polluting the governor inbox.

---

## 4. Session scope

This is a single session of work:

1. Fix Root A: quote 7 titles (mechanical string edits, `.specs/decisions/` files)
2. Fix Root B: change `status: withdrawn` → `status: retired` in ADR-112
3. Fix Root C: add frontmatter to ADR-124 and ADR-125
4. Verify: `SpecsDocValidator.validate_all_documents()` → `Invalid: 0`
5. Wire: `intent_validator.py` calls `SpecsDocValidator`
6. Verify: `core-admin intent validate` clean
7. Write / update tests
8. Resolve the `specs_doc_validator.py` blackboard orphan finding

**Out of scope for this session (ADR-105 D8 deferred):**
- Requirements/planning/charter/northstar status subsets and schemas
- The ADR-105 D6 Hook 2 (CCC check: draft-cited-by-accepted, ungrounded-accepted-ADR)
- The GLOBAL-schema sibling question

---

## 5. Pre-session checklist

Before starting, verify:
- [ ] Daemon is running (autonomy loop should not commit mid-fix)
- [ ] `SpecsDocValidator.validate_all_documents()` still shows `Invalid: 10` (baseline)
- [ ] `core-admin intent validate` passes on `.intent/` (no pre-existing schema drift)
- [ ] The 10 failing files are the exact set listed here (rerun the validator to confirm)
