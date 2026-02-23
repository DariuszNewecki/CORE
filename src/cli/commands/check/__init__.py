# src/body/cli/commands/check/__init__.py
"""
Check command group - Constitutional compliance verification.

This module orchestrates the registration of all read-only validation
and health checks. It has been cleaned to remove transitional V1/V2
hybrid audit commands.
"""

from __future__ import annotations

import typer


# Create the main command group
check_app = typer.Typer(
    help="Read-only validation and health checks.", no_args_is_help=True
)


def _register_rule_commands():
    """Register specific rule-based audit commands."""
    import cli.commands.check.rule as rule_module

    for attr_name in dir(rule_module):
        attr = getattr(rule_module, attr_name)
        if callable(attr) and hasattr(attr, "__name__") and attr.__name__ == "rule_cmd":
            check_app.command("rule")(attr)
            break


def _register_audit_commands():
    """
    Register core audit commands.

    V2 ALIGNMENT: Removed 'audit-v2' and 'audit-hybrid' as the
    primary 'audit' command is now fully unified.
    """
    import cli.commands.check.audit as audit_module

    for attr_name in dir(audit_module):
        attr = getattr(audit_module, attr_name)
        if callable(attr) and hasattr(attr, "__name__"):
            if attr.__name__ == "audit_cmd":
                check_app.command("audit")(attr)
                break


def _register_quality_commands():
    """Register general code quality and system health commands."""
    import cli.commands.check.quality as quality_module

    for attr_name in dir(quality_module):
        attr = getattr(quality_module, attr_name)
        if callable(attr) and hasattr(attr, "__name__"):
            if attr.__name__ == "lint_cmd":
                check_app.command("lint")(attr)
            elif attr.__name__ == "tests_cmd":
                check_app.command("tests")(attr)
            elif attr.__name__ == "system_cmd":
                check_app.command("system")(attr)


def _register_diagnostic_commands():
    """Register deep diagnostic and contract verification commands."""
    import cli.commands.check.diagnostics_commands as diag_module

    for attr_name in dir(diag_module):
        attr = getattr(diag_module, attr_name)
        if callable(attr) and hasattr(attr, "__name__"):
            if attr.__name__ == "diagnostics_cmd":
                check_app.command("diagnostics")(attr)
            elif attr.__name__ == "check_body_ui_cmd":
                check_app.command("body-ui")(attr)


def _register_quality_gates_commands():
    """Register automated industry-standard quality gates."""
    import cli.commands.check.quality_gates as qg_module

    for attr_name in dir(qg_module):
        attr = getattr(qg_module, attr_name)
        if (
            callable(attr)
            and hasattr(attr, "__name__")
            and attr.__name__ == "quality_gates_cmd"
        ):
            check_app.command("quality-gates")(attr)
            break


# Trigger all registrations
_register_audit_commands()
_register_rule_commands()
_register_quality_commands()
_register_diagnostic_commands()
_register_quality_gates_commands()

__all__ = ["check_app"]
