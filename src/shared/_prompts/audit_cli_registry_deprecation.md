# audit_cli_registry deprecation — next-session brief

Drafted 2026-05-29 at the close of the cli_gate landing session (commit
a40ce0a4). Closes the architecture-debt half of #483 by collapsing two
implementations of the 5 shared CLI checks into one home.

Paste the block below into a fresh session.

---

```
TASK: Deprecate audit_cli_registry in favor of cli_gate. Refactor
self_check.py (the sole caller) to consume cli_gate directly so the
manual self-check and the autonomous audit share one implementation.
This closes the architecture-debt half of #483.

Working dir: /opt/dev/CORE. Pause the daemon first: `systemctl --user
stop core-daemon`. Do NOT restart at end — governor's call.

Pinned from prior session (commit a40ce0a4, do not re-derive):
- Engine: CliGateEngine at src/mind/logic/engines/cli_gate/engine.py
- Resolves via: EngineRegistry.get("cli_gate")
- Checks: 8 CliCheck subclasses at src/mind/logic/engines/cli_gate/checks/
  exposed by checks/__init__.py; verify(commands, params) -> list[AuditFinding]
  is SYNC. DiscoveryStrictCheck takes path_resolver in __init__; others don't.
- Walker: shared.cli.app_introspection.walk_typer_app(app, include_missing_handlers=True);
  returns list[dict] with raw `callback` field.
- audit_cli_registry sole call site (recon): src/cli/resources/admin/self_check.py:53
- mind→cli boundary already crossed by cli_gate's lazy import — precedent set.

────────────────────────────────────────────────────────────────────
PHASE 0 — VERIFY (read-only). STOP gates.

0.1 Sole caller still sole. grep audit_cli_registry across src/ and confirm
    self_check.py is still the only consumer. If a second caller appeared
    since commit a40ce0a4, STOP and report.

0.2 Self-check shape. Read src/cli/resources/admin/self_check.py and report:
    how it renders audit_cli_registry's output dict today (Rich? plain
    print? what fields does it surface?). The refactor must preserve the
    user-visible output contract or explicitly upgrade it.

0.3 Shim consumers. _introspect_typer_app in command_sync_service.py was
    kept as a back-compat shim for audit_cli_registry. grep its call sites.
    If audit_cli_registry was the only consumer, the shim goes with it.
    If anything else still imports it, STOP and report.

0.4 Consumption pattern — pick ONE and document why before building:
    (a) Engine path: instantiate CliGateEngine via EngineRegistry.get and
        loop over the 8 check_types calling verify_context for each. Same
        path the audit pipeline uses; output is list[AuditFinding] per
        check; you re-discover all mappings' params from the live policies.
    (b) Check-direct path: walk the Typer app once via walk_typer_app,
        instantiate each CliCheck subclass directly, call verify(commands,
        params) per check. Bypasses the rule_executor and the enforcement-
        severity mapping; lighter and self-contained; you hardcode the
        params dicts in self_check.py.
    Recommendation lean: (b) for a fast manual preflight, but (a) gives
    output parity with the autonomous audit. Whichever you pick, write
    one paragraph of why before Phase 1.

────────────────────────────────────────────────────────────────────
PHASE 1 — BUILD (only after 0 gates pass).

1.1 Refactor self_check.py per the 0.4 decision. The command renders to
    console via Rich (per CLAUDE.md: console.print for Rich objects, never
    logger). Preserve the existing UX shape — duplicate detection,
    missing-handler counts, violations grouped by rule — unless the
    upgrade is explicitly documented.

1.2 Delete audit_cli_registry from command_sync_service.py. If 0.3
    confirmed no other consumers of _introspect_typer_app, delete that
    shim too. The _sync_commands_to_db function stays as is (it already
    consumes walk_typer_app directly post-commit a40ce0a4).

1.3 If self_check.py used path (a), the cli→mind import goes via
    EngineRegistry.get; if (b), via direct CliCheck class imports. Both
    are layer-clean per the cli_gate precedent. Use lazy import inside
    the command callback if eager import bloats CLI startup.

────────────────────────────────────────────────────────────────────
PHASE 2 — SELF-TEST (daemon still stopped).

2.1 Run `core-admin admin self-check` end-to-end. Confirm:
    - Exits non-zero when findings present (preserve prior contract)
    - Output is readable (Rich-rendered)
    - Findings match what cli_gate produced in the a40ce0a4 self-test
      (3 resource_first + 21 standard_verbs + 2 dangerous_explicit +
      1 async_execution + 2 no_duplicates = 29 total against current
      main; numbers may differ if #484 was resolved or remediation
      landed)

2.2 Import smoke for command_sync_service after deletion — no broken
    imports anywhere in src/.

2.3 Ruff check on every file touched.

────────────────────────────────────────────────────────────────────
PHASE 3 — REPORT (ordered):
A. Files changed (src/ only this session — .intent/ untouched).
B. 0.4 decision and rationale.
C. Self-check output sample (first 10 lines or a screenshot if available).
D. Drift surfaces eliminated: 5 check implementations previously
   duplicated between audit_cli_registry and cli_gate now have one
   home. Explicitly confirm the deletion is clean (no dead imports,
   no orphan helpers).

STOP. Do not restart the daemon. Do not edit .intent/. If 0.1 or 0.3
surfaces a new caller, STOP at that gate.
```

---

## Open items at hand-off (not part of next session's scope)

- **#484** — `coherence.seed.*` depth-3 design call (refactor / grow rule
  with `subgroup_resources` / downgrade to reporting). Until decided, the
  autonomous remediator will propose fixes against possibly-legitimate
  commands on next ramp.
- **Daemon restart** — whenever the governor chooses. The 8 cli_gate
  rules will start firing on the next audit cycle; expect ~29 findings as
  the first-enforcement baseline, not a regression.
