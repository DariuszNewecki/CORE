# Upgrade a CORE Database

CORE never migrates a database on its own. `install-core.sh` and every service start (`core-admin
daemon start`, the API, the `core-engine` container) check the schema state **read-only** and refuse
to run against a database that is not current. Migration is a deliberate, operator-run step.

**Fresh installation** — `./install-core.sh` (or `./install-core.sh --bare --db-url … --qdrant-url …`)
loads `schema.sql` into a database that has no CORE schema, in one transaction, and then shows
`core-admin database status` reporting the ledger current. Nothing else is needed. A failed load
leaves nothing behind (there is no drop-and-retry); the installer refuses and names `var/logs/schema-apply.log`.

**Before any upgrade** — stop CORE so nothing writes during migration, using the commands your
installation already has:

| Installation | Stop | Start again (only after `status` exits 0) |
|---|---|---|
| systemd units (unit files in `infra/systemd/`; `core-admin daemon up` starts them, it does not install them) | `core-admin daemon down` | `core-admin daemon up` |
| bare (`install-core.sh --bare`) | `./stop.sh` | `./start.sh` |
| installer Docker path (API started by the installer, daemon by `make daemon-start`) | `make daemon-stop` and `make stop` | `./install-core.sh` (re-verifies status, starts the API) and `make daemon-start` |

Take your normal database backup. Then check what you have:

```bash
poetry run core-admin database status          # exit 0 current · 2 not current · 1 the check itself failed
```

**Upgrading a database created by v2.9.1** — `status` reports an empty ledger on a populated
schema and suggests baseline `v2.9.1`:

```bash
poetry run core-admin database migrate --adopt-baseline v2.9.1          # dry run: verifies the baseline's probes, records nothing
poetry run core-admin database migrate --adopt-baseline v2.9.1 --write  # records the ledger through v2.9.1
poetry run core-admin database migrate --write                          # applies the 14 pending migrations, one transaction each
poetry run core-admin database status                                   # must exit 0: current
```

**Upgrading a database created by v2.10.1** — `status` suggests baseline `v2.10.1`:

```bash
poetry run core-admin database migrate --adopt-baseline v2.10.1 --write
poetry run core-admin database migrate --write      # 1 applied, 4 reconciled: structure the schema already carries is recorded, not re-run
poetry run core-admin database status               # must exit 0
```

From an installed wheel (`pip install core-runtime`) the same commands work with only `DATABASE_URL`
set (the manifest, SQL and `schema.sql` ship inside the wheel); the `core-engine` container exposes
them as `status` and `migrate`.

**Already current** — `status` exits 0; `migrate --write` reports nothing pending; re-running the
installer continues. Nothing is changed.

**Pending migrations on a ledgered database** — `status` lists them; run `database migrate --write`,
then `status`.

**Contradiction** — `status` names a recorded migration whose verification probe fails: the ledger
claims a change the schema lacks. `migrate --write` refuses. Do not adopt a baseline over it and do
not hand-edit `core._migrations`; restore the database from backup, or report the status output.

**Unrecognised schema** — a `core` namespace that no declared baseline matches: `status` reports an
empty ledger with no matching baseline and the installer refuses. The database was not created by a
released CORE version. Nothing is changed; do not force a baseline.

**What a refusal means** — each migration runs together with its ledger row in one transaction
under a lock. A failure leaves that migration rolled back and unrecorded, earlier ones recorded, and
re-running `migrate --write` is safe once the cause is fixed (the message names it — for example a
`runtime_settings` key not yet recorded as migrated in `config_migration_log`). Concurrent
invocations apply each migration once. Governance history (`blackboard_entries`,
`autonomous_proposals`, `proposal_consequences`) is preserved: rows, identities, content and
relationships survive; a v2.9.1 upgrade updates `updated_at` on existing blackboard rows and turns
retired `draft` proposals `pending`, as those migrations declare.

**Restart only after `status` exits 0.** A service that starts is proof of a matching schema when
the database is reachable; one that refuses names the remedy in its log (daemon and `core-engine`
exit 78; the API's startup fails under uvicorn, exit 3).
