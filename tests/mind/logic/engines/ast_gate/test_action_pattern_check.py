"""Tests for PurityChecks.check_action_pattern (#820).

The rule — architecture.patterns.action_pattern, blocking — reads: "Action
commands MUST use @atomic_action and have a 'write' parameter defaulting to
False", scoped to src/body/atomic/** and src/cli/commands/**.

Until #820 the check_type had no dispatcher: ast_gate's unknown-check_type
guard returned ok=False with no violations, which rule_executor swallowed, so
the rule was reached on every CI audit and enforced nothing. These tests pin
both obligations, the layer split between them, and the two selection edges
that keep the check from over-firing (Typer-wrapped defaults, undecorated
helpers).
"""

from __future__ import annotations

import ast
from pathlib import Path

from mind.logic.engines.ast_gate.checks.purity_checks import PurityChecks


ATOMIC = "src/body/atomic/file_ops.py"
CLI = "src/cli/commands/fix/audit.py"


def _check(code: str, path: str) -> list[str]:
    """Parse code and run the check against the synthetic path."""
    return PurityChecks.check_action_pattern(ast.parse(code), file_path=Path(path))


# ID: 5f2a91c4-8b7e-4d03-9a6c-1e8f4b2d7305
def test_registered_action_without_atomic_action_flags() -> None:
    """The decorator obligation: @register_action alone is ungoverned."""
    code = (
        "@register_action('x')\n"
        "async def action_write_file(path, write=False):\n"
        "    return None\n"
    )
    findings = _check(code, ATOMIC)
    assert len(findings) == 1
    assert "@atomic_action" in findings[0]
    assert "action_write_file" in findings[0]


# ID: 9c4e7a15-2f8b-46d0-a3e9-5b1c8d0f6427
def test_registered_action_with_atomic_action_is_clean() -> None:
    """The compliant shape — both decorators, write defaulting to False."""
    code = (
        "@register_action('x')\n"
        "@atomic_action(action_id='x', intent='i')\n"
        "async def action_write_file(path, write=False):\n"
        "    return None\n"
    )
    assert _check(code, ATOMIC) == []


# ID: 3d8b0f62-7a41-4e59-b2c7-9f0a6e3d15b8
def test_decorator_obligation_does_not_reach_cli_layer() -> None:
    """CLI commands route mutations through ActionExecutor under @core_command.

    Requiring @atomic_action on a Typer command would contradict the
    documented CLI pattern, so the decorator half binds to the atomic layer
    only. The write-default half still applies — see the CLI tests below.
    """
    code = (
        "@app.command()\n"
        "@core_command(dangerous=True)\n"
        "async def fix_audit_command(ctx, write=False):\n"
        "    return None\n"
    )
    assert _check(code, CLI) == []


# ID: 59fac976-f7c9-4f3b-bad5-91c86aabf375
def test_write_defaulting_true_flags_in_atomic_layer() -> None:
    """The write obligation: mutation must be opt-in, not opt-out."""
    code = (
        "@atomic_action(action_id='x', intent='i')\n"
        "async def action_write_file(path, write=True):\n"
        "    return None\n"
    )
    findings = _check(code, ATOMIC)
    assert len(findings) == 1
    assert "does not default to False" in findings[0]
    assert "True" in findings[0]


# ID: c05a8e37-4b9d-41f6-8027-6a3e9c1b5d82
def test_typer_option_wrapping_false_is_clean() -> None:
    """`typer.Option(False, '--write')` IS a False default.

    The repo's 22 CLI write flags are all spelled this way. A check that
    read the wrapper literally would flag every one of them and put main
    red — the precision edge that makes this rule landable.
    """
    code = (
        "@app.command()\n"
        "@core_command(dangerous=True)\n"
        "def fix_cmd(ctx, write: bool = typer.Option(False, '--write', "
        "help='Apply changes.')):\n"
        "    return None\n"
    )
    assert _check(code, CLI) == []


# ID: 1e6d0b48-9f27-4c53-ae81-3b5f7a2c9d06
def test_typer_option_wrapping_true_flags() -> None:
    """Unwrapping must not become blanket trust of the wrapper."""
    code = (
        "@app.command()\n"
        "def fix_cmd(ctx, write: bool = typer.Option(True, '--write')):\n"
        "    return None\n"
    )
    findings = _check(code, CLI)
    assert len(findings) == 1
    assert "does not default to False" in findings[0]


# ID: 51850683-2abb-45ba-852c-d6ed037767ad
def test_write_parameter_without_default_flags() -> None:
    """A decorated command taking a required `write` has no default posture."""
    code = "@app.command()\ndef fix_cmd(ctx, write: bool):\n    return None\n"
    findings = _check(code, CLI)
    assert len(findings) == 1
    assert "no default" in findings[0]


# ID: 4f9e2a76-1c58-4b03-8d6a-9e0f3c7b5124
def test_undecorated_helper_with_required_write_is_clean() -> None:
    """The sandbox_lifecycle shape: not an action command, not flagged.

    `build_execution_context(self, definition, write: bool, ...)` forces an
    explicit argument at its call site — a legitimate contract that a
    path-based check would have mistaken for a violation.
    """
    code = (
        "class SandboxLifecycle:\n"
        "    def build_execution_context(self, definition, write: bool, sha):\n"
        "        return None\n"
    )
    assert _check(code, ATOMIC) == []


# ID: 6b0d8c24-3a9f-4157-92e6-8c4b1f7d0a35
def test_keyword_only_write_is_covered() -> None:
    """Keyword-only `write` carries the same obligation as positional."""
    bad = (
        "@atomic_action(action_id='x', intent='i')\n"
        "async def action_x(path, *, write=True):\n"
        "    return None\n"
    )
    good = (
        "@atomic_action(action_id='x', intent='i')\n"
        "async def action_x(path, *, write=False):\n"
        "    return None\n"
    )
    assert len(_check(bad, ATOMIC)) == 1
    assert _check(good, ATOMIC) == []


# ID: 86d9be03-51ef-4313-be0b-9d8c51b25f34
def test_private_and_undecorated_functions_are_skipped() -> None:
    """Selection is by decorator, and private symbols are exempt throughout."""
    code = (
        "def helper(write=True):\n"
        "    return None\n"
        "@atomic_action(action_id='x', intent='i')\n"
        "def _private(write=True):\n"
        "    return None\n"
    )
    assert _check(code, ATOMIC) == []


# ID: 0d5b3e89-7c14-42af-9106-4e8a2f6c1b70
def test_both_obligations_report_independently() -> None:
    """A function can fail the decorator and write checks at once."""
    code = (
        "@register_action('x')\n"
        "async def action_write_file(path, write=True):\n"
        "    return None\n"
    )
    findings = _check(code, ATOMIC)
    assert len(findings) == 2
    assert any("@atomic_action" in f for f in findings)
    assert any("does not default to False" in f for f in findings)
