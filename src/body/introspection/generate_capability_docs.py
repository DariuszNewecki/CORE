# src/features/introspection/generate_capability_docs.py
"""
Generates the canonical capability reference documentation from the database.

ARCHITECTURE: Pure feature - no standalone execution.
Use via: core-admin build capability-docs

CONSTITUTIONAL FIX:
- Aligned with 'governance.artifact_mutation.traceable'.
- Replaced direct Path writes with governed FileHandler mutations.
- Enforces IntentGuard and audit logging for documentation exports.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger


logger = getLogger(__name__)

# --- Configuration ---
# Internal logic uses repo-relative path for FileHandler compatibility
REL_OUTPUT_PATH = "docs/10_CAPABILITY_REFERENCE.md"
GITHUB_URL_BASE = "https://github.com/DariuszNewecki/CORE/blob/main/"

HEADER = """
# 10. Capability Reference

This document is the canonical, auto-generated reference for all capabilities recognized by the CORE constitution.
It is generated from the `core.knowledge_graph` database view and should not be edited manually.
"""


async def _fetch_capabilities(session: AsyncSession) -> list[dict]:
    """
    Fetches all public capabilities from the database knowledge graph view.

    Args:
        session: Injected database session
    """
    logger.info("Fetching capabilities from the database...")
    stmt = text(
        """
            SELECT
                capability,
                intent,
                file_path as file
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
        # Infer domain from the key
        domain_key = ".".join(key.split(".")[:-1]) if "." in key else "general"
        if domain_key not in domains:
            domains[domain_key] = []
        domains[domain_key].append(cap)
    return domains


# ID: 2ea63de3-081d-40b3-9386-0d372487aabd
async def main(session: AsyncSession):
    """
    The main entry point for the documentation generation script.
    """
    try:
        capabilities = await _fetch_capabilities(session)
    except Exception as e:
        logger.error("Error fetching capabilities: %s", e)
        return

    if not capabilities:
        logger.warning(
            "No capabilities found in the database. Documentation will be empty."
        )
        return

    domains = _group_by_domain(capabilities)

    logger.info(
        "Generating documentation for %d capabilities across %d domains...",
        len(capabilities),
        len(domains),
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
            line_number = 1
            github_link = f"{GITHUB_URL_BASE}{file_path}#L{line_number}"
            md_content.append(f"  - **Source:** [{file_path}]({github_link})")
        md_content.append("")

    final_text = "\n".join(md_content)

    # CONSTITUTIONAL FIX: Use the governed mutation surface
    # FileHandler handles directory creation and path validation automatically.
    file_handler = FileHandler(str(settings.REPO_PATH))

    try:
        file_handler.write_runtime_text(REL_OUTPUT_PATH, final_text)
        logger.info(
            "Capability reference documentation successfully written to %s via FileHandler",
            REL_OUTPUT_PATH,
        )
    except Exception as e:
        logger.error("Failed to write documentation: %s", e)
