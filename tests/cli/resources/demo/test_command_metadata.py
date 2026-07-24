# tests/cli/resources/demo/test_command_metadata.py
"""Regression: the demo commands satisfy `cli.dangerous_explicit` (ADR-155 Phase 4).

The repo-scope audit exposed that `demo.consequence-chain` and `demo.cleanup` were
declared `behavior=MUTATE` without `dangerous=True` + a `write` param, tripping the
blocking `cli.dangerous_explicit` gate. That gate is context-level and is skipped
under `--files`, so a scoped audit could not see it. This test runs the *actual*
gate check against the *actual* introspected demo app, so the regression cannot
silently return.
"""

from __future__ import annotations

import inspect

from cli.resources.demo import app as demo_app
from cli.resources.demo.cleanup import cleanup_cmd
from cli.resources.demo.consequence_chain import consequence_chain_cmd
from mind.logic.engines.cli_gate.checks.dangerous_explicit import DangerousExplicitCheck
from shared.cli.app_introspection import walk_typer_app
from shared.cli.command_meta import CommandBehavior, get_command_meta


# ── The exact gate that failed the repo-scope audit now returns no findings ────


# ID: a93f239c-056c-4260-9d65-b12d77a18e81
def test_demo_commands_pass_dangerous_explicit_gate() -> None:
    commands = walk_typer_app(demo_app, prefix="demo.")
    findings = DangerousExplicitCheck().verify(commands, {})
    assert findings == [], [f.message for f in findings]


# ── Consequence-chain is VALIDATE (governor-approved reclassification) ─────────


# ID: 3a5a73ad-9337-48fc-8bb9-f61c70b1be30
def test_consequence_chain_is_validate() -> None:
    meta = get_command_meta(consequence_chain_cmd)
    assert meta is not None
    assert meta.behavior == CommandBehavior.VALIDATE


# ── Cleanup stays MUTATE, marked dangerous, with a write parameter ────────────


# ID: 8aeddb68-e81a-48bc-b731-d762fbbd0975
def test_cleanup_is_mutate_dangerous_with_write_param() -> None:
    meta = get_command_meta(cleanup_cmd)
    assert meta is not None
    assert meta.behavior == CommandBehavior.MUTATE
    assert meta.dangerous is True
    assert "write" in inspect.signature(cleanup_cmd).parameters
