# src/body/cli/logic/diagnostics.py

"""
Aggregates deep diagnostic checks from specialized modules.
Acts as the wiring center for the 'diagnostics' command group.
"""

from __future__ import annotations

import asyncio

import typer

from features.introspection.audit_unassigned_capabilities import get_unassigned_symbols
from features.introspection.graph_analysis_service import find_semantic_clusters
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger
from shared.utils.constitutional_parser import get_all_constitutional_paths

from .diagnostics_policy import policy_coverage
from .diagnostics_registry import check_legacy_tags, cli_registry, manifest_hygiene


logger = getLogger(__name__)
diagnostics_app = typer.Typer(help="Deep diagnostic and integrity checks.")


async def _async_find_clusters(context: CoreContext, n_clusters: int):
    """Async helper that contains the core logic for the command."""
    logger.info("Finding semantic clusters with n_clusters=%s...", n_clusters)
    if context.qdrant_service is None and context.registry:
        try:
            context.qdrant_service = await context.registry.get_qdrant_service()
        except Exception as e:
            logger.error("Failed to initialize QdrantService: %s", e)
            return
    clusters = await find_semantic_clusters(
        qdrant_service=context.qdrant_service, n_clusters=n_clusters
    )
    if not clusters:
        logger.warning("No clusters found.")
        return
    logger.info("Found %s clusters.", len(clusters))
    return clusters


@diagnostics_app.command(
    "find-clusters",
    help="Finds and displays all semantic capability clusters, sorted by size.",
)
# ID: 91856850-423f-4c27-90c3-e06f56a3841a
def find_clusters_command_sync(
    ctx: typer.Context,
    n_clusters: int = typer.Option(
        25, "--n-clusters", "-n", help="The number of clusters to find."
    ),
):
    """Synchronous Typer wrapper for the async clustering logic."""
    core_context: CoreContext = ctx.obj
    asyncio.run(_async_find_clusters(core_context, n_clusters))


def _add_cli_nodes(cli_app: typer.Typer):
    """Build CLI structure without UI dependencies."""
    structure = []
    for cmd_info in sorted(cli_app.registered_commands, key=lambda c: c.name or ""):
        if not cmd_info.name:
            continue
        help_text = cmd_info.help.split("\n")[0] if cmd_info.help else ""
        structure.append({"type": "command", "name": cmd_info.name, "help": help_text})
    for group_info in sorted(cli_app.registered_groups, key=lambda g: g.name or ""):
        if not group_info.name:
            continue
        help_text = (
            group_info.typer_instance.info.help.split("\n")[0]
            if group_info.typer_instance.info.help
            else ""
        )
        structure.append(
            {
                "type": "group",
                "name": group_info.name,
                "help": help_text,
                "children": _add_cli_nodes(group_info.typer_instance),
            }
        )
    return structure


@diagnostics_app.command(
    "cli-tree", help="Displays a hierarchical tree view of all available CLI commands."
)
# ID: dd914ffc-2b27-43e5-a6a6-20695cb7e778
def cli_tree():
    """Builds and returns the CLI command tree structure."""
    from body.cli.admin_cli import app as main_app

    logger.info("Building CLI Command Tree...")
    return _add_cli_nodes(main_app)


@diagnostics_app.command(
    "debug-meta", help="Prints the auditor's view of all required constitutional files."
)
# ID: 59eb1e73-3e51-470c-8f1c-1c7c2142013d
def debug_meta_paths():
    """A diagnostic tool that returns all file paths indexed in meta.yaml."""
    logger.info("Getting auditor's interpretation of meta.yaml...")
    required_paths = get_all_constitutional_paths(settings._meta_config, settings.MIND)
    return sorted(list(required_paths))


@diagnostics_app.command(
    "unassigned-symbols", help="Finds symbols without a universal # ID tag."
)
# ID: b39297a7-26db-47a6-a2d0-f2780cca9bb1
def unassigned_symbols():
    unassigned = get_unassigned_symbols()
    if not unassigned:
        logger.info("Success! All governable symbols have an assigned ID tag.")
        return []
    logger.warning("Found %s symbols with no assigned ID", len(unassigned))
    return unassigned


diagnostics_app.command(
    "policy-coverage", help="Audits the constitution for policy coverage and integrity."
)(policy_coverage)
diagnostics_app.command(
    "manifest-hygiene",
    help="Checks for capabilities declared in the wrong domain manifest file.",
)(manifest_hygiene)
diagnostics_app.command(
    "cli-registry", help="Validates the CLI registry against its constitutional schema."
)(cli_registry)
diagnostics_app.command("legacy-tags", help="Scans the codebase for obsolete tags.")(
    check_legacy_tags
)
