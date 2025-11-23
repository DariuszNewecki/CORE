#!/usr/bin/env python3
"""
Script to verify if symbols in audit_ignore_policy.yaml are truly unused.
Reports SAFE_TO_DELETE, IN_USE, or UNCLEAR for each symbol.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Literal

from rich.console import Console
from rich.table import Table
from ruamel.yaml import YAML

console = Console()
yaml = YAML()

SymbolStatus = Literal["SAFE_TO_DELETE", "IN_USE", "UNCLEAR"]


class UsageAnalyzer:
    """Analyzes Python files to find symbol usage."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.src_files = list((repo_root / "src").rglob("*.py"))

    def parse_symbol_key(self, key: str) -> tuple[str, str, str]:
        """Parse 'path/file.py::Class.method' into components."""
        match = re.match(r"^(.+)::(.+?)(?:\.(.+))?$", key)
        if not match:
            return "", "", ""
        file_path, class_or_func, method = match.groups()
        return file_path, class_or_func, method or ""

    def find_direct_imports(self, symbol_name: str) -> list[tuple[Path, int]]:
        """Find files that directly import this symbol."""
        matches = []
        for py_file in self.src_files:
            try:
                content = py_file.read_text(encoding="utf-8")
                for line_num, line in enumerate(content.splitlines(), 1):
                    if re.search(rf"\bfrom\b.*\bimport\b.*\b{symbol_name}\b", line):
                        matches.append((py_file, line_num))
                    elif re.search(rf"\bimport\b.*\b{symbol_name}\b", line):
                        matches.append((py_file, line_num))
            except Exception:
                continue
        return matches

    def find_usage_in_code(self, symbol_name: str) -> list[tuple[Path, int]]:
        """Find files that call or reference this symbol."""
        matches = []
        for py_file in self.src_files:
            try:
                content = py_file.read_text(encoding="utf-8")
                for line_num, line in enumerate(content.splitlines(), 1):
                    # Skip comments and docstrings
                    if line.strip().startswith("#"):
                        continue
                    # Look for function calls, class instantiation, or attribute access
                    if re.search(rf"\b{symbol_name}\b\s*\(", line):  # function call
                        matches.append((py_file, line_num))
                    elif re.search(rf"\b{symbol_name}\b\.", line):  # attribute access
                        matches.append((py_file, line_num))
            except Exception:
                continue
        return matches

    def analyze_symbol(self, key: str) -> tuple[SymbolStatus, str]:
        """Determine if a symbol is truly unused."""
        file_path, class_or_func, method = self.parse_symbol_key(key)

        if not file_path:
            return "UNCLEAR", "Could not parse symbol key"

        # Check if the source file still exists
        full_path = self.repo_root / file_path
        if not full_path.exists():
            return "SAFE_TO_DELETE", "Source file no longer exists"

        # Extract the symbol name to search for
        symbol_name = method if method else class_or_func

        # Search for imports
        imports = self.find_direct_imports(symbol_name)
        if imports:
            locations = ", ".join([f"{p.name}:{ln}" for p, ln in imports[:3]])
            return "IN_USE", f"Imported in: {locations}"

        # Search for usage in code
        usages = self.find_usage_in_code(symbol_name)
        if usages:
            locations = ", ".join([f"{p.name}:{ln}" for p, ln in usages[:3]])
            return "IN_USE", f"Used in: {locations}"

        # Check if it's a test file - these might be intentionally unused
        if "/tests/" in file_path or file_path.endswith("_test.py"):
            return "UNCLEAR", "Test file - manual review recommended"

        # No usage found
        return "SAFE_TO_DELETE", "No imports or usages found"


def main():
    console.print("[bold cyan]🔍 Legacy Symbol Verification Tool[/bold cyan]\n")

    # Locate repository root and policy file
    repo_root = Path.cwd()
    policy_path = (
        repo_root / ".intent/charter/policies/governance/audit_ignore_policy.yaml"
    )

    if not policy_path.exists():
        console.print(f"[red]❌ Policy file not found: {policy_path}[/red]")
        sys.exit(1)

    # Load policy
    with policy_path.open("r", encoding="utf-8") as f:
        policy_data = yaml.load(f)

    symbol_ignores = policy_data.get("symbol_ignores", [])
    if not symbol_ignores:
        console.print("[green]✅ No symbols in ignore list[/green]")
        return

    console.print(f"Found {len(symbol_ignores)} symbols to analyze...\n")

    # Analyze each symbol
    analyzer = UsageAnalyzer(repo_root)
    results: dict[SymbolStatus, list[tuple[str, str]]] = {
        "SAFE_TO_DELETE": [],
        "IN_USE": [],
        "UNCLEAR": [],
    }

    for entry in symbol_ignores:
        key = entry.get("key", "")
        if not key:
            continue

        status, reason = analyzer.analyze_symbol(key)
        results[status].append((key, reason))

    # Display results
    for status, items in results.items():
        if not items:
            continue

        color = {
            "SAFE_TO_DELETE": "green",
            "IN_USE": "yellow",
            "UNCLEAR": "cyan",
        }[status]

        console.print(f"\n[bold {color}]{status}: {len(items)} symbols[/bold {color}]")
        table = Table(show_header=True)
        table.add_column("Symbol", style=color, no_wrap=False)
        table.add_column("Reason", style="white")

        for key, reason in items[:20]:  # Show first 20
            table.add_row(key, reason)

        console.print(table)

        if len(items) > 20:
            console.print(f"... and {len(items) - 20} more")

    # Summary
    console.print("\n[bold cyan]📊 Summary:[/bold cyan]")
    console.print(f"  SAFE_TO_DELETE: {len(results['SAFE_TO_DELETE'])}")
    console.print(f"  IN_USE: {len(results['IN_USE'])}")
    console.print(f"  UNCLEAR: {len(results['UNCLEAR'])}")

    # Generate deletion script
    if results["SAFE_TO_DELETE"]:
        console.print(
            "\n[yellow]⚠️  Review SAFE_TO_DELETE symbols above carefully![/yellow]"
        )
        console.print(
            "[yellow]If you're confident, I can generate a cleanup script.[/yellow]"
        )


if __name__ == "__main__":
    main()
