#!/usr/bin/env python3
"""
Fixes malformed symbol keys in audit_ignore_policy.yaml.
Converts: core.actions.code_actions.CreateFileHandler
To:       src/core/actions/code_actions.py::CreateFileHandler
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from ruamel.yaml import YAML

console = Console()
yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)


def fix_symbol_key(key: str) -> str | None:
    """Convert module.path.ClassName to src/module/path.py::ClassName format."""

    # Pattern: module.submodule.ClassName (no file extension, no src/, no ::)
    if "::" in key or "/" in key or key.startswith("src"):
        return None  # Already correct format or different issue

    parts = key.split(".")
    if len(parts) < 2:
        return None  # Can't fix

    # Last part is the symbol name (class/function)
    symbol_name = parts[-1]

    # Everything else is the module path
    module_parts = parts[:-1]

    # Convert to file path: core.actions.code_actions -> src/core/actions/code_actions.py
    file_path = "src/" + "/".join(module_parts) + ".py"

    # Build correct format
    return f"{file_path}::{symbol_name}"


def main():
    console.print("[bold cyan]🔧 Symbol Key Format Fixer[/bold cyan]\n")

    # Locate policy file
    repo_root = Path.cwd()
    policy_path = (
        repo_root / ".intent/charter/policies/governance/audit_ignore_policy.yaml"
    )

    if not policy_path.exists():
        console.print(f"[red]❌ Policy file not found: {policy_path}[/red]")
        return 1

    # Load policy
    console.print("Loading policy file...")
    with policy_path.open("r", encoding="utf-8") as f:
        policy_data = yaml.load(f)

    symbol_ignores = policy_data.get("symbol_ignores", [])
    if not symbol_ignores:
        console.print("[yellow]No symbols to fix[/yellow]")
        return 0

    # Fix malformed entries
    fixed_count = 0
    for entry in symbol_ignores:
        original_key = entry.get("key", "")
        if not original_key:
            continue

        fixed_key = fix_symbol_key(original_key)
        if fixed_key:
            console.print(f"[yellow]Fixing:[/yellow] {original_key}")
            console.print(f"[green]    →[/green] {fixed_key}")
            entry["key"] = fixed_key
            fixed_count += 1

    if fixed_count == 0:
        console.print("[green]✅ No malformed keys found![/green]")
        return 0

    # Save updated policy
    console.print(f"\n[cyan]Writing {fixed_count} fixes to policy file...[/cyan]")
    with policy_path.open("w", encoding="utf-8") as f:
        yaml.dump(policy_data, f)

    console.print(f"[bold green]✅ Fixed {fixed_count} symbol keys![/bold green]")
    console.print(
        "\n[yellow]Next step:[/yellow] Re-run verify_legacy_symbols.py to confirm"
    )

    return 0


if __name__ == "__main__":
    exit(main())
