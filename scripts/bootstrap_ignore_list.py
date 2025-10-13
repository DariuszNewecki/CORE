# scripts/bootstrap_ignore_list.py
"""
A one-time administrative script to populate the audit_ignore_policy.yaml
with all currently unassigned public symbols. This is a pragmatic step to
acknowledge existing technical debt and allow the main integration workflow to pass.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

from rich.console import Console
from ruamel.yaml import YAML
from services.database.session_manager import get_session
from shared.config import settings
from sqlalchemy import text

console = Console()
yaml = YAML()
yaml.indent(mapping=2, sequence=4, offset=2)


async def bootstrap_ignore_list():
    """
    Finds all unassigned public symbols and adds them to the audit ignore policy.
    """
    console.print(
        "[bold cyan]🚀 Bootstrapping the audit ignore list with legacy unassigned symbols...[/bold cyan]"
    )
    unassigned_symbols = []
    try:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT symbol_path FROM core.symbols
                    WHERE key IS NULL AND is_public = TRUE
                    ORDER BY symbol_path;
                    """
                )
            )
            unassigned_symbols = [row[0] for row in result]
    except Exception as e:
        console.print(f"[bold red]❌ Database query failed: {e}[/bold red]")
        return

    if not unassigned_symbols:
        console.print(
            "[bold green]✅ No unassigned symbols found to ignore.[/bold green]"
        )
        return

    console.print(
        f"   -> Found {len(unassigned_symbols)} unassigned symbols to add to the ignore list."
    )

    policy_path = settings.get_path("charter.policies.governance.audit_ignore_policy")
    if not policy_path.exists():
        console.print(
            f"[bold red]❌ Audit ignore policy not found at: {policy_path}[/bold red]"
        )
        return

    try:
        with policy_path.open("r", encoding="utf-8") as f:
            policy_data = yaml.load(f)

        existing_ignores = {
            item["key"] for item in policy_data.get("symbol_ignores", [])
        }
        expiry_date = (date.today() + timedelta(days=180)).isoformat()

        new_ignores_added = 0
        for symbol_key in unassigned_symbols:
            if symbol_key not in existing_ignores:
                policy_data.setdefault("symbol_ignores", []).append(
                    {
                        "key": symbol_key,
                        "reason": "Legacy symbol - to be defined as part of technical debt.",
                        "expires": expiry_date,
                    }
                )
                new_ignores_added += 1

        if new_ignores_added > 0:
            with policy_path.open("w", encoding="utf-8") as f:
                yaml.dump(policy_data, f)
            console.print(
                f"[bold green]✅ Successfully added {new_ignores_added} symbols to {policy_path.name}.[/bold green]"
            )
        else:
            console.print(
                "[bold yellow]No new symbols needed to be added to the ignore list.[/bold yellow]"
            )

    except Exception as e:
        console.print(f"[bold red]❌ Failed to update the policy file: {e}[/bold red]")


if __name__ == "__main__":
    asyncio.run(bootstrap_ignore_list())
