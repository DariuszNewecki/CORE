# CLI Reference

CORE has two command-line tools (ADR-146). Every command, option and default is listed in
the generated reference for each one; this page explains which tool does what, the
conventions they share, and the commands whose operational behaviour needs more than help
text.

| Binary | Package | Audience | Reference |
|---|---|---|---|
| `core-admin` | `pip install core-runtime` | Operators of a CORE installation, and anyone auditing or starting a governed repository locally | [`core-admin` reference](reference/core-admin.md) |
| `core` | `pip install core-cli` | Consumers of a running CORE: proposals, secrets, BYOR onboarding, assisted remediation. Most commands talk to a running CORE API | [`core` reference](reference/core.md) |

Both reference pages are generated from the live command trees by
`core-admin docs generate --write`, so they list exactly what the installed CLIs accept.
Every command also answers `--help`. In a development checkout, prefix commands with
`poetry run`.

---

## Command conventions

**`--write`**: required for any command that modifies files or data. Without it, commands
run in dry-run mode.

**Dry-run by default**: CORE never makes changes unless explicitly instructed.

**Interactive confirmation**: `dev sync --write` and destructive operations require
interactive confirmation and cannot be piped. When stdin is closed, they exit with code 2
and say how to proceed.

**Deprecated names**: a renamed command can keep its old name as a hidden, deprecated
alias. Hidden aliases are not listed in the generated reference.

---

## Command notes

### `project new` and `project adopt-pack`

`project new` is the bootstrap stage of Generate (ADR-119, amended 2026-10-02). It creates
the repository substrate and the machinery that can host project law, and **no
project-specific law**. Until rules are authored or ratified, or a governance pack is
explicitly adopted with `project adopt-pack`, `code audit` on the new project fails closed.
That is intended: CORE does not choose a project's law. It never overwrites: a non-empty
target, or a target inside CORE's own repository, is refused. Without `--write` it previews
the files.

`project onboard`, `project scout`, `project promote` and `project docs` belong to `core`
and talk to a running CORE API (ADR-146 D2). See [byor-quickstart.md](byor-quickstart.md).

### `demo consequence-chain`

**Prerequisites:** Docker (Compose v2). No LLM key required.

**What it proves.** `consequence-chain` seeds a real `linkage.assign_ids` violation into a
**disposable clone** and runs it through the **real** sensor → remediator → proposal route →
executor → consequence service → re-audit. It never touches the invoking checkout, its git
index, your database, Qdrant, API, or daemon; it stands up its own loopback-only, dynamically
ported Postgres + Qdrant, and tears everything down when done. Every displayed fact (finding,
proposal, approval authority, execution, pre/post SHA, changed files, resolved finding) belongs
to the **same** proposal; nothing is selected by "latest". The `fix.ids` proposal is
auto-approved as **policy-safe** (`risk_classification.safe_auto_approval`); the interactive
prompt is your consent to continue the demonstration, **not** a proposal-approval event.

**Fails closed.** The command exits non-zero unless every isolation, chain, evidence, and cleanup
assertion holds. Warnings never substitute for an assertion.

**Output.** By default it writes **no** file into your checkout. With `--output PATH` it writes a
Markdown report and a matching JSON companion (`PATH` with a `.json` suffix) inside the repository
boundary.

**Exit codes:**

| Exit | Meaning |
|---|---|
| `0` | Every scenario and cleanup assertion passed. |
| `2` | Pre-flight/configuration failure (e.g. Docker missing, bad `--output` path); the scenario did not start. |
| `64` | Scenario, evidence, isolation, or cleanup failure. |
| `130` | Operator interruption (Ctrl-C); infrastructure cleanup attempted and the retained workspace path reported. |

**Cleanup.** On success the disposable clone is removed (unless `--keep-workspace`). On failure or
interruption, disposable infrastructure is still torn down but the clone is **retained** for
diagnosis; the command prints its path and the `demo cleanup <run_id>` command to remove it. Cleanup
is marker-checked: it removes only a directory whose basename equals the run id and that carries the
matching run-id marker file.

> `scripts/demo.sh` is a thin compatibility wrapper that delegates to `demo consequence-chain`; it
> contains no scenario logic of its own.

### `database status` and `database migrate`

`database status` is read-only: exit 0 when the schema is current, 2 when migrations are
pending or the ledger contradicts the schema, 1 when the check itself failed.
`database migrate` without `--write` lists pending migrations and mutates nothing.

CORE never migrates a database on its own. Upgrading an existing database is an operator-run
step — the procedure for each released baseline is in
[Upgrading an existing CORE database](getting-started.md#upgrading-an-existing-core-database).

```bash
core-admin database status                          # read-only; exit 0 current, 2 pending/contradictory
core-admin database status --format json            # adds ledger_present, probe_failures, baseline_suggestion, current
core-admin database migrate                         # dry run: lists pending, mutates nothing
core-admin database migrate --write                 # applies pending, one transaction per migration
core-admin database migrate --adopt-baseline v2.9.1          # verifies the baseline's probes only
core-admin database migrate --adopt-baseline v2.9.1 --write  # records the ledger through that baseline
```

- `--write` is the only mutation flag (`--apply` remains one release as a deprecated alias).
  `--bootstrap` is removed: it recorded every manifest entry without verifying anything.
- Each migration executes together with its `core._migrations` row in **one** transaction
  under an advisory lock; a failure leaves that migration rolled back and unrecorded, earlier
  ones recorded, and re-running is safe. Concurrent invocations apply each migration once.
- `status` never creates anything. It reports pending migrations, **probe failures** (recorded
  migrations whose verification probe fails — the ledger claims a change the schema lacks) and,
  for an empty ledger on a populated schema, the declared baseline that matches.
- `--adopt-baseline <tag>` records manifest entries up to a declared baseline only after every
  probe of that baseline holds and no later baseline also holds; it never records beyond the
  baseline. Naming a version is never sufficient on its own.
- `--write` refuses an empty ledger on a populated schema (adopt a baseline first) and any
  ledger/schema contradiction.
- A fresh `schema.sql` load seeds the ledger completely; a fresh install never has an empty ledger.
- **Installer.** `install-core.sh` runs `database status` read-only: it loads `schema.sql` only
  into a database with no CORE schema (one transaction, no drop-and-retry), continues on a current
  database, and refuses — before any service starts, without migrating — on any other state.
- **Startup gate.** `core-admin daemon start` and the API lifespan evaluate the same read-only
  check as `database status` before starting workers / serving and refuse (daemon and
  `core-engine` exit 78; the API's startup fails under uvicorn with exit 3 — ADR-162 Governor
  clarification 2026-09-19) when migrations are pending, the ledger is empty on a
  populated schema, a recorded migration's probe fails, no CORE schema exists, or the manifest
  is unreadable — naming the remedy. `CORE_STRICT_MODE` does not relax it; an unreachable
  database keeps the existing connectivity behaviour, so a service that starts is proof of a
  matching schema when the database is reachable.
- The wheel bundles the manifest, the migration SQL and `schema.sql` (`src/shared/_migrations/`, a
  byte-parity mirror): `database status|migrate` work from a `pip install core-runtime` with no
  checkout (`status --format json` reports `"assets": "bundled"`), and the `core-engine` image
  exposes them as `entrypoint.sh status …` / `entrypoint.sh migrate …` (only `DATABASE_URL` needed).

### `runtime dashboard`

The governor dashboard answers five questions with color signals:

1. **Convergence Direction** — is the codebase healing or accumulating debt?
2. **Governor Inbox** — are there items requiring human judgment?
3. **Loop Running** — are all workers alive and cycling?
4. **Pipeline Moving** — are proposals flowing through to execution?
5. **Autonomous Reach** — can the daemon self-heal without intervention?

```bash
watch -n 30 core-admin runtime dashboard --plain  # Live monitoring
```

### `daemon`

Use `core-admin daemon up | down | restart | status` to control the CORE services; they
drive the systemd user units. `daemon start` is the systemd entry point, not a command to run
by hand.

---

## Governance note

All CLI operations that modify files are subject to constitutional governance. A command that
would produce a blocking violation halts before applying changes. The CLI is not an escape
hatch from the constitution.
