# src/body/cli/commands/check/__init__.py
"""
Check command group - Constitutional compliance and system health validation.
"""

from __future__ import annotations

import typer


# Create command group
check_app = typer.Typer(
    help="Read-only validation and health checks.", no_args_is_help=True
)


def _register_rule_commands():
    """Register rule commands with debugging."""
    import body.cli.commands.check.rule as rule_module

    print("DEBUG: Checking rule module...")
    print(
        f"DEBUG: Module attributes: {[x for x in dir(rule_module) if not x.startswith('_')]}"
    )

    found = False
    for attr_name in dir(rule_module):
        attr = getattr(rule_module, attr_name)
        if callable(attr) and hasattr(attr, "__name__"):
            print(
                f"DEBUG: Found callable '{attr_name}' with __name__ = '{attr.__name__}'"
            )
            if attr.__name__ == "rule_cmd":
                print("DEBUG: ✓ Registering rule_cmd!")
                check_app.command("rule")(attr)
                found = True
                break

    if not found:
        print("DEBUG: ✗ rule_cmd not found in module!")


def _register_audit_commands():
    """Register audit commands."""
    import body.cli.commands.check.audit as audit_module

    for attr_name in dir(audit_module):
        attr = getattr(audit_module, attr_name)
        if callable(attr) and hasattr(attr, "__name__"):
            if attr.__name__ == "audit_cmd":
                check_app.command("audit")(attr)
            elif attr.__name__ == "audit_v2_cmd":
                check_app.command("audit-v2")(attr)
            elif attr.__name__ == "audit_hybrid_cmd":
                check_app.command("audit-hybrid")(attr)


def _register_quality_commands():
    """Register quality commands."""
    import body.cli.commands.check.quality as quality_module

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
    """Register diagnostic commands."""
    import body.cli.commands.check.diagnostics_commands as diag_module

    for attr_name in dir(diag_module):
        attr = getattr(diag_module, attr_name)
        if callable(attr) and hasattr(attr, "__name__"):
            if attr.__name__ == "diagnostics_cmd":
                check_app.command("diagnostics")(attr)
            elif attr.__name__ == "check_body_ui_cmd":
                check_app.command("body-ui")(attr)


# Register all commands
_register_audit_commands()
_register_rule_commands()
_register_quality_commands()
_register_diagnostic_commands()


__all__ = ["check_app"]
