# src/features/introspection/generate_capability_docs.py
"""
Generates the canonical capability reference documentation from the database.
"""

from __future__ import annotations

import asyncio

from rich.console import Console
from services.repositories.db.engine import get_session
from shared.config import settings
from sqlalchemy import text

console = Console()

# --- Configuration ---
OUTPUT_PATH = settings.REPO_PATH / "docs" / "10_CAPABILITY_REFERENCE.md"
GITHUB_URL_BASE = "https://github.com/DariuszNewecki/CORE/blob/main/"

HEADER = """
# 10. Capability Reference

This document is the canonical, auto-generated reference for all capabilities recognized by the CORE constitution.
It is generated from the `core.knowledge_graph` database view and should not be edited manually.
"""


async def _fetch_capabilities() -> list[dict]:
    """Fetches all public capabilities from the database knowledge graph view."""
    console.print("[cyan]Fetching capabilities from the database...[/cyan]")
    async with get_session() as session:
        stmt = text(
            """
            SELECT capability, intent, file, line_number
            FROM core.knowledge_graph
            WHERE is_public = TRUE AND capability IS NOT NULL
            ORDER BY capability;
            """
        )
        result = await session.execute(stmt)
        return [dict(row._mapping) for row in result]


def _group_by_domain(capabilities: list[dict]) -> dict[str, list[dict]]:
    """Groups capabilities by their domain prefix."""
    domains = {}
    for cap in capabilities:
        key = cap["capability"]
        # Infer domain from the key, e.g., 'autonomy.self_healing.fix_headers' -> 'autonomy.self_healing'
        domain_key = ".".join(key.split(".")[:-1]) if "." in key else "general"
        if domain_key not in domains:
            domains[domain_key] = []
        domains[domain_key].append(cap)
    return domains


# ID: 2ea63de3-081d-40b3-9386-0d372487aabd
def main():
    """The main entry point for the documentation generation script."""

    async def _async_main():
        capabilities = await _fetch_capabilities()
        if not capabilities:
            console.print(
                "[yellow]Warning: No capabilities found in the database. Documentation will be empty.[/yellow]"
            )
            return

        domains = _group_by_domain(capabilities)

        console.print(
            f"[cyan]Generating documentation for {len(capabilities)} capabilities across {len(domains)} domains...[/cyan]"
        )

        md_content = [HEADER.strip(), ""]

        for domain_name in sorted(domains.keys()):
            md_content.append(f"## Domain: `{domain_name}`")
            md_content.append("")

            for cap in sorted(domains[domain_name], key=lambda x: x["capability"]):
                md_content.append(f"- **`{cap['capability']}`**")

                description = cap.get("intent") or "No description provided."
                md_content.append(f"  - **Description:** {description.strip()}")

                file_path = cap.get("file")
                # Use a default line number if it's missing to avoid errors
                line_number = cap.get("line_number") or 0
                github_link = f"{GITHUB_URL_BASE}{file_path}#L{line_number + 1}"
                md_content.append(f"  - **Source:** [{file_path}]({github_link})")
            md_content.append("")

        final_text = "\n".join(md_content)

        OUTPUT_PATH.write_text(final_text, encoding="utf-8")
        console.print(
            f"[bold green]✅ Capability reference documentation successfully written to {OUTPUT_PATH}[/bold green]"
        )

    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
