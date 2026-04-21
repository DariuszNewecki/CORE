# Daemon reactivation reconnaissance — 2026-04-20

**Status:** Recon / read-only. No daemon started, no `.intent/` or
`src/` writes.
**Scope:** Is it safe to start `core-daemon.service`, or does something
need fixing first?
**Method:** Live evidence only. Commands and queries are recorded in
the section they inform. Items marked UNVERIFIED were not confirmed.

---

## 1. Why did the daemon stop?

**Classification: clean shutdown (systemctl stop).** Exit code 0/SUCCESS.
No stack trace, no kill signal, no hang.

The session opener stated "inactive since 2026-04-18 14:26." **That is
off by two hours.** `systemctl --user status core-daemon` and the
journal agree on the actual shutdown:

> Active: inactive (dead) since Sat 2026-04-18 **16:26:35** CEST; 2 days ago
> Duration: 10min 21.202s
> Main PID: 3642332 (code=exited, status=0/SUCCESS)
> CPU: 31.773s

Between 14:26 and 16:26 the daemon was still running normally — worker
heartbeats, `WorkerAuditor: cycle complete — checked=14 flagged=0`,
`BlackboardAuditor` cycles, and filtered-audit executions all logged
without interruption. The last 14-heartbeat cycle arrived at 16:26:08
and the shutdown began 26 seconds later.

Last 20 log lines verbatim (from `journalctl --user -u core-daemon
--since "2026-04-18 16:25" --until "2026-04-18 16:27" --no-pager`):

```
Apr 18 16:26:34 lira core-daemon[3642332]:            INFO     INFO:mind.governance.filtered_audit:Filtered audit complete:
Apr 18 16:26:34 lira core-daemon[3642332]:                     3/3 rules executed, 0 findings
Apr 18 16:26:34 lira core-daemon[3642332]:            INFO     INFO:will.workers.audit_violation_sensor:AuditViolationSenso
Apr 18 16:26:34 lira core-daemon[3642332]:                     r[layout]: no actionable violations found.
Apr 18 16:26:34 lira core-daemon[3642332]:            INFO     INFO:will.workers.audit_violation_sensor:AuditViolationSenso
Apr 18 16:26:34 lira core-daemon[3642332]:                     r[logic]: no actionable violations found.
Apr 18 16:26:34 lira core-daemon[3642332]:            INFO     INFO:will.workers.audit_violation_sensor:AuditViolationSenso
Apr 18 16:26:34 lira core-daemon[3642332]:                     r[architecture]: no actionable violations found.
Apr 18 16:26:34 lira core-daemon[3642332]:            INFO     INFO:will.workers.audit_violation_sensor:AuditViolationSenso
Apr 18 16:26:34 lira core-daemon[3642332]:                     r[linkage]: no actionable violations found.
Apr 18 16:26:34 lira systemd[1055]: Stopping core-daemon.service - CORE Background Worker Daemon...
Apr 18 16:26:34 lira core-daemon[3642332]:            INFO     INFO:cli.commands.daemon:CORE daemon: shutdown signal
Apr 18 16:26:34 lira core-daemon[3642332]:                     received.
Apr 18 16:26:34 lira core-daemon[3642332]:            INFO     INFO:cli.commands.daemon:CORE daemon: cancelling workers...
Apr 18 16:26:34 lira core-daemon[3642332]:            INFO     INFO:cli.commands.daemon:CORE daemon: stopped cleanly.
Apr 18 16:26:35 lira systemd[1055]: Stopped core-daemon.service - CORE Background Worker Daemon.
Apr 18 16:26:35 lira systemd[1055]: core-daemon.service: Consumed 31.773s CPU time.
```

No blocker from §1. The daemon was healthy at shutdown.

## 2. Blackboard state as left

**Status counts:**

| status             | count  |
|---                 |---     |
| abandoned          | 3      |
| claimed            | 55     |
| dry_run_complete   | 2      |
| open               | 70     |
| resolved           | 10,771 |

**`claimed` older than 24h: all 55.** The oldest `updated_at` is
`2026-04-17 11:22:43+00:00`; the newest is older than the required 24h
threshold (NOW() − 24h). Every `claimed` row is orphaned by this
definition.

Top 10 oldest `claimed` rows (by `updated_at ASC`) are all
`audit.violation::workflow.ruff_format_check::…` finding subjects,
claimed by worker UUID `c9d4e5f6-a7b8-4c0d-9e1f-2a3b4c5d6e7f`
(ViolationExecutorWorker per log cross-reference). Files in the stale
claim set include `cli/resources/admin/self_check.py`,
`cli/commands/fix/atomic_actions.py`, `shared/self_healing/
remediation_interpretation/file_context_assembler.py`,
`will/agents/conversational/agent.py`, and ten others.

Distinct subjects among the 55 orphans (ARRAY_AGG DISTINCT): 13
subjects, 12 of them `audit.violation::workflow.ruff_format_check::*`
plus one `test.missing::src/will/workers/blackboard_auditor.py`.

**This is the §1 operational trace.** The session-opener's "14:26
inactive" is almost certainly pattern-matching against the fact that
**blackboard writes stopped around 14:26** even though the daemon
process kept running until 16:26. That is consistent with
ViolationExecutorWorker acquiring claims and then something upstream
of its report path going silent — but whether that silence was a
logical no-op or an actual stall is UNVERIFIED here; the daemon
process's own cycles (WorkerAuditor, BlackboardAuditor) kept ticking
to shutdown.

On daemon start, BlackboardAuditor will flag all 55 as stale (its
SLA=3600s, per the 14:58:08 log line that already flagged one at
3668s). Flagging is non-fatal; the daemon continues. But these 55
claims held by a UUID that will not re-register are a persistent
false signal in every subsequent cycle.

## 3. Worker registry state

**Status counts:** `abandoned` = 20, `active` = 15.

**The session-opener's "20 abandoned" matches exactly.** No growth
since the daemon went inactive:

```
SELECT COUNT(*) FROM core.worker_registry
  WHERE status='abandoned' AND last_heartbeat > '2026-04-18 16:26:35';
→ 0
```

Newest abandoned row has `last_heartbeat = 2026-04-07 16:03:06` —
11 days before the shutdown, let alone after it. The abandoned set is
stable historical residue (oldest: 2026-03-13 Audit Violation Sensor;
newest: 2026-04-07 Documentation Writer / Self-Healing Agent). None
of the abandoned UUIDs match the `c9d4e5f6-…` UUID holding the 55
orphan claims from §2; the ViolationExecutorWorker is in the `active`
set (or has no registry row — UNVERIFIED which).

Schema note: the session-opener's query used `worker_id`; the live
schema column is `worker_uuid` (uuid) plus `worker_name` (text). No
`declaration_name` column exists. Reporting here uses the real schema.

## 4. Daemon startup path integrity

Three of the six import commands in the brief target paths that **do
not exist in the current codebase.** They fail not because the code
is broken but because the paths are stale.

Brief's commands, as given:

| Command (verbatim) | Result |
|---|---|
| `from will.daemon.main import main` | **FAIL** — `ModuleNotFoundError: No module named 'will.daemon'`. No `src/will/daemon/` directory exists. The daemon is launched via `core-admin daemon start` (systemd ExecStart: `/opt/dev/CORE/.venv/bin/core-admin daemon start`); the entry point is `src/cli/commands/daemon.py::start()`. |
| `from will.workers.violation_remediator import ViolationRemediator` | **FAIL** — `ImportError: cannot import name 'ViolationRemediator'`. Actual class name is `ViolationRemediatorWorker`. |
| `from will.workers.proposal_consumer import ProposalConsumer` | **FAIL** — `ModuleNotFoundError: No module named 'will.workers.proposal_consumer'`. Actual module is `will.workers.proposal_consumer_worker`, class `ProposalConsumerWorker`. |
| `from will.workers.audit_violation_sensor import AuditViolationSensor` | **OK** |
| `from shared.infrastructure.intent.audit_verdict import load_audit_verdict_policy; print(load_audit_verdict_policy())` | **OK** — returns `{'fail_severities': ['ERROR'], 'ignored_finding_types': ['ENFORCEMENT_FAILURE'], 'degraded_on': ['any_crashed_rules']}` |
| `from mind.logic.engines.ast_gate.checks.modularity_checks import ModularityChecker; print('ok')` | **OK** — prints `ok` |

Re-running the three failures with the real names:

```
from cli.commands.daemon import start          → ok
from will.workers.violation_remediator import ViolationRemediatorWorker        → ok
from will.workers.proposal_consumer_worker import ProposalConsumerWorker       → ok
```

**All actual daemon code paths compile and import cleanly.** The two
retrofits from this session (ADR-005 verdict policy loader, ADR-006
modularity classifier swap) both import and initialise without error.
No blocker from §4.

## 5. Dry-run daemon sanity

`core-admin workers blackboard` — **OK.** Prints the 50-row tabular
snapshot of `core.blackboard_entries` ordered by `created_at DESC`.
Exercises the same session_manager and ORM path the daemon will use.
DB access works.

`core-admin workers registry` — **FAILS:** `Error: No such command
'registry'`. The `workers` Typer app exposes only `run`, `blackboard`,
`purge`, `remediate`. There is no `registry` subcommand. This is a
brief artefact, not a daemon blocker — the registry surface the
brief imagined does not exist, but the registry table was queried
directly in §3 with no error.

Nearest equivalents for registry-style introspection:
`core-admin runtime health`, `core-admin runtime dashboard` (both
live-read-only dashboards; not invoked here because they render Rich
UI and the brief asked for output capture).

No blocker from §5.

## 6. fix.modularity risk surface for the 11 remaining findings

Extracted from `reports/audit_findings.json` (mtime
`2026-04-20 22:05`); 11 `modularity.needs_split` entries, each
classified by running `ast.parse` on the current file to count
top-level `ClassDef` and compute `dominant_class_lines / loc`.

| # | file | loc | class_count | dominant_class_lines | ratio | >0.70 |
|---|---|---|---|---|---|---|
|  1 | `src/body/evaluators/atomic_actions_evaluator.py` | 428 | 2 | 349 | 0.815 | ✓ |
|  2 | `src/body/services/blackboard_service.py` | 658 | 1 | 620 | 0.942 | ✓ |
|  3 | `src/body/services/constitutional_validator.py` | 426 | 4 | 288 | 0.676 | ✗ |
|  4 | `src/shared/path_resolver.py` | 403 | 1 | 367 | 0.911 | ✓ |
|  5 | `src/will/agents/strategic_auditor/agent.py` | 417 | 1 | 355 | 0.851 | ✓ |
|  6 | `src/will/interpreters/request_interpreter.py` | 441 | 5 | 235 | 0.533 | ✗ |
|  7 | `src/will/self_healing/remediation_interpretation/responsibility_extractor.py` | 421 | 1 | 411 | 0.976 | ✓ |
|  8 | `src/will/strategists/fix_strategist.py` | 467 | 1 | 430 | 0.921 | ✓ |
|  9 | `src/will/workers/audit_violation_sensor.py` | 434 | 1 | 361 | 0.832 | ✓ |
| 10 | `src/will/workers/test_remediator.py` | 412 | 1 | 337 | 0.818 | ✓ |
| 11 | `src/will/workers/violation_remediator.py` | 503 | 1 | 434 | 0.863 | ✓ |

**DOMINANT-CLASS count by the brief's `ratio > 0.70` criterion: 9,
not 6.** The nine are rows 1, 2, 4, 5, 7, 8, 9, 10, 11.

ADR-006 §4 said "6 of the 11 are DOMINANT-CLASS." That figure comes
from the 2026-04-20 modularity diagnostic's taxonomy, where files with
`responsibilities ≤ 2` AND a dominant class were classified
`DOMINANT-CLASS` *only if* they weren't already captured by an earlier
first-match category (`INTERNAL-MODULE-NO-SIGNAL` caught 4 of the
workers/services with dominant classes because their external signal
was one responsibility or less). The diagnostic also used a softer
dominant-class threshold than `>0.70` — `constitutional_validator.py`
at ratio 0.676 was labelled DOMINANT-CLASS there.

Under the brief's stated criterion, the autonomy-mismatch risk surface
for `fix.modularity` is **9 of 11 findings**, not 6. The two files
that would not trip the gate are:
- `src/body/services/constitutional_validator.py` (4 classes, dominant
  ratio 0.676)
- `src/will/interpreters/request_interpreter.py` (5 classes, dominant
  ratio 0.533)

ADR-006 §4's critique — file-level splitting of a dominant-class file
crosses a discipline boundary the rule's rationale explicitly
disclaims — applies to all nine.

## 7. Stale proposals

**Two proposal tables exist under `core`:** `proposals` (empty — zero
rows of any status) and `autonomous_proposals` (the A3 pipeline's
primary table). The brief's query targeted `core.proposals`. Using
both:

| table | status | count |
|---|---|---|
| `core.proposals` | (none) | 0 |
| `core.autonomous_proposals` | `completed` | 16 |
| `core.autonomous_proposals` | `failed` | 1 |
| `core.autonomous_proposals` | `rejected` | 1 |

**Zero rows in `pending_approval`, `approved`, or `executing` in
either table.** The query `WHERE status IN
('pending_approval','approved','executing') ORDER BY created_at ASC
LIMIT 20` returns no rows.

**Nothing would execute in the first minute of daemon uptime from the
proposal queue.** No blocker from §7.

## 8. Go / No-go recommendation

**GO WITH GATES.** Daemon can start, but two pre-start actions are
warranted:

### Gate 1 — purge or reset the 55 orphaned `claimed` blackboard entries before startup.

From §2: every `claimed` row is >24h old, all held by worker UUID
`c9d4e5f6-a7b8-4c0d-9e1f-2a3b4c5d6e7f`. On restart that UUID will
not re-register (worker UUIDs are process-scoped); the claims will
sit orphaned and be re-flagged by `BlackboardAuditor` on every
cycle. The surface `core-admin workers purge` exists and can target
status-filtered rows. The alternative (leave them, let the auditor
log 55 stale-claim warnings per cycle) is noisy but not fatal.

### Gate 2 — guard `fix.modularity` against DOMINANT-CLASS findings before enabling it.

From §6: 9 of 11 `modularity.needs_split` findings have
`dominant_class_lines / loc > 0.70`. ADR-006 §4 names this exact case
as an open follow-up ("DOMINANT-CLASS autonomy gate — either a
class-structure signal on `fix.modularity` or a confidence
downgrade"). Running the remediator against any of the nine without a
gate violates the rule's own rationale ("mechanical redistribution, no
discipline boundaries crossed"); splitting a dominant class across
files requires a type-identity decision that is a discipline boundary.

`fix.modularity` is currently Tier 2 ACTIVE at confidence 0.85 per
`.intent/enforcement/remediation/auto_remediation.yaml` (UNVERIFIED
post-retrofit — the YAML was not re-read in this recon; status at
ADR-006 acceptance time was as stated). Until the gate lands, a
conservative path is either: (a) mark `fix.modularity` Tier 3
(proposal-only, no execute) for `modularity.needs_split` findings
until the class-structure signal exists, or (b) leave the daemon's
ProposalConsumerWorker cycle running but keep the manual-approval
gate that already sits before execution and decline all nine.

### Non-blockers documented for completeness

- §1: clean shutdown, no crash to investigate.
- §3: 20 abandoned workers, zero growth since stop — stable residue.
- §4: all real code paths import; the three brief failures were
  stale paths, not breakage.
- §5: `workers blackboard` works; `workers registry` does not exist as
  a CLI surface — no live blocker.
- §7: no proposals pending/approved/executing; proposal queue is
  idle.

### Explicit unverifieds (do not build plans on these without checking)

1. Whether the 14:26-vs-16:26 discrepancy reflects a real
   report-path stall upstream of ViolationExecutorWorker. §1 and §2
   agree the daemon process ran to 16:26; §2 shows the last
   `claimed`-row update landed 2026-04-17 11:37. A worker that
   claimed rows on 04-17 and never updated them is consistent with
   either "nothing to report" or "silent failure." This recon did
   not open the ViolationExecutor's consumer-side log path.
2. Whether `auto_remediation.yaml` still maps `fix.modularity` at
   Tier 2 ACTIVE 0.85 after ADR-005 / ADR-006 landed. The YAML was
   not re-read in this session.
3. Whether the orphan-claiming worker UUID has a
   `core.worker_registry` row (active or abandoned). Cross-referencing
   §2 and §3 did not surface it explicitly; the query `SELECT … WHERE
   worker_uuid = 'c9d4e5f6-…'` was not run.

---

*End of recon. No follow-up edits to this file; if correction is
needed, write a new dated recon.*
