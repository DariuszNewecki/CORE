---
kind: adr
id: ADR-162
title: 'ADR-162 — Database upgrade remediation: the confirmed v2.9.1→v2.10.1 defect and the Governor ruling on its repair'
status: accepted
depends_on: ["ADR-086", "ADR-115", "ADR-159"]
---

<!-- path: .specs/decisions/ADR-162-database-upgrade-remediation-ruling.md -->

# ADR-162 — Database upgrade remediation: the confirmed v2.9.1→v2.10.1 defect and the Governor ruling on its repair

**Status:** Accepted — governor (D.Newecki), 2026-09-19.
**Date:** 2026-09-19
**Prompted by:** an executable evidence unit (2026-09-19, disposable clones of `v2.9.1` and
`v2.10.1` against a disposable Postgres) that proved the upgrade path between the two released
versions does not work, followed by a design/adjudication unit that produced the ruling
package this ADR records. Both reports live under `var/reports/` (ignored); this ADR is the
durable record — repository truth must not depend on chat or on an ignored file.
**Relates:** URS G11 (`.specs/requirements/URS-production-readiness.md#g11`) — the gate this
defect violates; ADR-159 D7 — which already classified G11 as pilot-blocking for third-party
installation and instructed its status be corrected to `not_met`; ADR-115 D1 — whose
"schema-as-truth, no migration framework" premise is stale (a ledger exists and is required);
ADR-161 (proposed) — which independently recorded the stale `infra/sql/db_schema_live.sql`
references and the ADR-115 corrigendum; ADR-086 D1/D7 — the published `core-engine` image
that runs the daemon from the wheel against an external database; `cli.command.dangerous_marking`
(`.intent/rules/infrastructure/cli_commands.json`) — mutating commands require an explicit flag.

---

## Context

### The confirmed defect (executed, not inferred)

A v2.9.1 installation created by `install-core.sh` and upgraded to v2.10.1 by the only
documented route (new checkout, re-run the installer) ends in this state:

- the installer exits 0 with "schema already present — skipping"; **no migration runs**.
  No API, daemon or installer path invokes `MigrationService` — the only callers are the
  `core-admin database migrate|status` commands.
- the API starts cleanly (`Application startup complete`, `/health` 200) on the stale
  v2.9.1 schema; `GET /v1/proposals` and `GET /v1/proposals/{id}` return **500**
  (`autonomous_proposals.consequence_recorded_at does not exist`); daemon workers fail every
  cycle (`proposal_consequences.consequence_source`, `blackboard_entries.last_seen_at`,
  `first_payload` missing). **Successful startup is not evidence of a successful upgrade.**
- `core-admin database status` reports 0 applied / 37 pending. The ledger
  (`core._migrations`) is never seeded by any install path: a **fresh** v2.9.1 install
  already reports 30 pending against its own schema.
- `core-admin database migrate` without `--apply` is a dry run (exit 0, nothing applied);
  `docs/cli-reference.md` called it "Run migrations".
- `--apply` on that un-seeded ledger replays the 30 historical migrations against a schema
  that already contains them and aborts at the second one.
- `--bootstrap`, run after switching to the v2.10.1 checkout, records **all 37** entries as
  applied without executing any SQL: `status` then reports 0 pending while the schema is still
  v2.9.1 and the API still fails. This is the most dangerous path because it looks healthy.
- the span `v2.9.1..v2.10.1` adds **nine** SQL files under `infra/scripts/migrations/` but
  only **seven** manifest entries: `20260722_active_finding_dedup.sql` and
  `20260722_active_finding_reconcile.sql` were applied to the single live database by hand
  (their rollout runbook) and never ledgered, yet the current `Worker.post_finding` upsert
  requires the columns and the partial unique index they create. Even the correct ledger
  sequence therefore leaves open-finding posting broken.
- the published wheel `core-runtime==2.10.1` contains no manifest, no migration SQL and no
  `schema.sql`; `load_policy()` raises on a wheel. The `core-engine` image (ADR-086) runs the
  daemon from that wheel and therefore cannot inspect or migrate its database at all.
- `apply_sql_file` executes one file in one transaction and `record_applied` opens a second;
  35 of 39 migration files carry their own `BEGIN;`/`COMMIT;`. A probe proved that with those
  statements kept, the file's `COMMIT` commits the DDL and a later ledger insert autocommits
  — nothing can be rolled back together; with transaction-control statements stripped, DDL and
  ledger row roll back as one, and `pg_advisory_xact_lock` plus a re-check inside the lock
  serialises concurrent appliers to exactly one application.
- a clean v2.10.1 installation is **not** affected: `schema.sql` at v2.10.1 carries the final
  schema, including the dedup index.

### Existing law and design this ruling sits on

- URS G11 requires a formal upgrade path from each released schema version to the next, no
  `DROP SCHEMA CASCADE`, preserved governance history, and rollback of a failed migration.
- ADR-159 D7: G11 is pilot-blocking for third-party installation; its attestation status
  should read `not_met`; the ledger is never seeded, ~a third of files are unguarded DDL, and
  apply/record are not atomic. This ADR does not re-decide any of that; it acts on it.
- ADR-115 D1's grounding sentence ("no migration framework") and its `db_schema_live.sql`
  path are stale; ADR-161 already lists the corrigendum. This ADR relies on ADR-161's note
  rather than amending ADR-115 itself.
- `cli.command.dangerous_marking`: state-mutating commands carry `dangerous=True` and require
  an explicit `--write`. `database migrate` uses `--apply`, so that gate is inert today.

## Decisions

The Governor approved the ruling package as **R1-A, R2-A, R3-A, R4-A, R5-A, R6-A, R7-A,
R8-A, R9-A, R10-A, R11-A**, with the binding amendments in D12.

### D1 — R1-A: migrations are explicitly operator-run
Only `core-admin database migrate --write` mutates the schema (`--apply` may survive one
release as a deprecated alias). Inspection (`status`, dry run), approval (the operator's
decision) and execution stay separate. Neither the installer nor API/daemon startup applies
migrations automatically. An explicit `install-core.sh --upgrade` convenience that prints the
plan, confirms, and calls the same command is permitted later; it is not part of this ruling.

### D2 — R2-A: API and daemon refuse a non-current schema
`core_lifespan`, the daemon entry point and the `core-engine` entrypoint run a **read-only**
schema gate before serving or starting workers. Known pending migrations, an empty ledger on a
populated schema, a ledger row whose verification probe fails, or unreadable migration
assets → **refuse**, exit 78 (`EX_CONFIG`, the code the `core-engine` entrypoint already
uses), naming the exact remedy command. `CORE_STRICT_MODE` does not relax this. Database
unreachable keeps today's `CORE_STRICT_MODE` behaviour; the gate reports it as unavailable.
The gate never calls `ensure_ledger()` — `database status` must likewise become read-only.

### D3 — R3-A: unrestricted `--bootstrap` is retired; baseline adoption is verified
`--bootstrap` is removed. `core-admin database migrate --adopt-baseline <tag>` records
manifest entries up to a declared baseline **only after every declared probe for that
baseline passes**; it refuses naming the first failing probe and never records entries beyond
the baseline. Naming a version is never sufficient on its own. `status` may *suggest* a
baseline from the catalog, read-only; it never records one.

### D4 — R4-A: supported upgrade range
Every tagged release from **v2.9.1** onward is a declared baseline with a supported upgrade
path to the current release by chained hops; each hop is tested when it is current (D5).
Manifest entries are never deleted or reordered. Pre-v2.9.1 databases are outside the promise.

### D5 — R5-A: `schema.sql` is authoritative for fresh installs, the manifest for upgrades
Fresh installation loads `schema.sql`; upgrades replay manifest entries through the ledger
engine; the ledger is checked against per-migration probes. CI proves equivalence:
`schema.sql` at the previous release plus the entries added since must produce the current
`schema.sql` (normalised `pg_dump` comparison).

### D6 — R6-A: every executable migration is ledgered
Both `20260722_active_finding_*.sql` files enter the manifest in date position between
`20260717…` and `20260727…`. CI proves both directions: every manifest entry exists on disk,
and every `.sql` file in the migrations directory appears **exactly once** in the manifest
(see D12 amendment 3 — there is no exclusion list).

### D7 — R7-A: per-migration atomic execution, concurrency-locked
The engine strips in-file transaction control (`BEGIN`, `START TRANSACTION`, `COMMIT`, `END`,
`ROLLBACK`; a CI lint permits only a leading `BEGIN;` and a trailing `COMMIT;` in migration
files) and runs each migration's statements **and** its ledger row in one transaction, under a
fixed-key `pg_advisory_xact_lock` with the applied set re-read inside the lock. Failure at
migration N leaves 1..N-1 recorded and N fully rolled back; retry is safe by construction.
Migrations needing non-transactional statements are refused until designed. The ledger gains
a `reconciled` marker (D12 amendment 2).

### D8 — R8-A: migration assets ship inside installed runtime artifacts
The manifest, the migration SQL and `schema.sql` are bundled as package data (a byte-parity
mirror under `src/shared/`, the pattern `shared/_prompts/` already uses, with the same kind of
parity and installed-wheel tests). On a wheel the bundled set is authoritative — the migration
set must match the installed code. The `core-engine` entrypoint gains `status`/`migrate`
wrappers. Relocating the canonical files instead of mirroring them is deferred to ADR-161.

### D9 — R9-A: a fresh schema contains its exact ledger baseline
`schema.sql` carries the `core._migrations` seed rows for the manifest at that release,
generated by the existing dump step and checked by a test (`seed ids == manifest order`).
Every path that loads `schema.sql` — installer, compose init, CI, demo fixtures — therefore
starts with a complete ledger; an empty ledger on a populated schema becomes a refusal (D2),
never a silent state.

### D10 — R10-A: unrelated defects stay separate
- The installer's `postgresql://` URL form (written verbatim into `.env`; the async engine
  then fails on a missing `psycopg2`) is its own tiny unit (U1).
- The unmounted `src/cli/logic/db.py` migrate command and `db_manage.py` are dead code for
  the ADR-161 layout drain, not this remediation.
- Stale command names and schema paths in active documentation and Python docstrings are
  corrected in U0; stale comments inside **released** migration files are not — released
  migration bytes are immutable (see Known documentation defects below).
- Remediation ships as `2.10.2` or later (D11).

### D11 — R11-A: the public warning ships first
Public and operator-facing surfaces state now that upgrading an existing database to v2.10.1
is unsupported (U0, this ADR's implementing commit), before any runtime change.

### D12 — Binding amendments to the approved package
1. **No public interim repair recipe.** The source-derived sequence that reaches a working
   v2.10.1 database from v2.9.1 is not published anywhere operator-facing. Documentation says
   the upgrade is unsupported and must wait for the corrected release.
2. **Reconciliation is exceptional, not generic.** A migration may be recorded without being
   executed only when its manifest entry is explicitly marked `reconcilable` **and** its probe
   proves the complete postcondition, including any required data state. Otherwise the engine
   executes it or refuses. Reconcile-by-probe is not a default behaviour of `--write`.
3. **No unmanaged SQL escape hatch.** Every `.sql` file in the migrations directory appears
   exactly once in the manifest. Non-migration SQL lives outside that directory. There is no
   `unmanaged:` list.
4. **Implementation order:** `U0 → U1 → U2 → U3 → U4 → U5 → U7 → U6 → U8` — packaging (U7)
   lands before the startup gate (U6), and the gate lands after baseline adoption (U4), so no
   supported installation form is ever refused without a remedy it can run.
5. **`2.10.2` is the intended remediation target, not a release authorisation.** A release
   requires completed U2–U7 evidence and a separate Governor decision.

### D13 — Scope of this ruling
This ADR authorises **design direction only**. Runtime behaviour is unchanged by its
acceptance and remains broken until the units below land and are certified. Nothing in this
ruling authorises a write to `.intent/`; any rule, schema or manifest change that a later unit
needs is drafted for the Governor under the CLAUDE.md confirmation gate. (The one
classification entry this ADR itself requires in `.intent/governance/namespace_manifest.yaml`,
per the blocking rule `governance.namespace.classification_complete`, was confirmed separately
by the Governor as a Path A write in the implementing turn — it is not a consequence of the ruling.)

## Implementation units (summary — scope is decided, sequencing is D12 §4)

| Unit | Scope | Ruling |
|---|---|---|
| U0 | this ADR; public warning in `README.md`, `docs/getting-started.md`, `docs/cli-reference.md`, `CHANGELOG.md`; active docstring/manifest-header drift; G11 → `not_met` | D11 |
| U1 | installer URL normalisation | D10 |
| U2 | atomic ledger engine, advisory lock, `reconciled` marker, transaction-control lint; real-Postgres tests | D7 |
| U3 | manifest probes, `reconcilable` marker, both `20260722` entries, bidirectional manifest↔disk test | D6, D12 §2–3 |
| U4 | `--adopt-baseline`, retire `--bootstrap`, `--write`, read-only `status`, `schema.sql` ledger seed + test | D1, D3, D4, D9 |
| U5 | CI hop-equivalence job | D5 |
| U7 | bundled assets, parity + installed-wheel tests, `core-engine` wrappers | D8 |
| U6 | startup gate in API, daemon and entrypoint, tests per state | D2 |
| U8 | installer upgrade behaviour, final docs, `2.10.2` release decision, G11 evidence | D10, D12 §5 |

## Known documentation defects deferred (not corrected in U0)

- Released migration comments cite `core-admin db migrate` / `db_schema_live.sql`:
  `20260914_885_retire_draft_proposal_status.sql`, `20260713_repo_artifacts_type_check_registry_sync.sql`,
  `20260602b_drop_lira_user_default_privileges_core.sql`. Released migration bytes are
  immutable; the correct command name is recorded here and in the manifest header.
- `tests/will/autonomy/test_proposal_lifecycle_no_draft.py` docstring cites `core-admin db migrate` (U3/U4).
- `src/cli/logic/db.py` prints the stale path and the "framework is dormant" message; dead code, ADR-161 drain.
- Historical ADRs (016, 055, 057, 058, 086, 090, 099, 115, 129) name `infra/sql/db_schema_live.sql`; historical records, corrected only through ADR-115's corrigendum (ADR-161).

## Consequences

- Operators are told the truth now: a clean v2.10.1 install works; an upgrade does not, and
  must wait. G11 reads `not_met` in the attestation and the generated README section.
- The remediation has a fixed shape and order; every later unit cites the decision it
  implements and cannot re-open R1–R11 without a new ruling.
- Until U6 lands, a stale schema still boots; until U8 lands, the installer still skips.
  This ADR changes none of that.
