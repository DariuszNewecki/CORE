# src/system/admin/byor.py
"""
Intent: Implements the 'byor-init' command for the CORE Admin CLI.

This command is the entry point for the "Bring Your Own Repo" capability.
It analyzes an external repository and proposes a minimal `.intent/`
scaffold to begin governing it with CORE.
"""

from pathlib import Path

import typer
import yaml

from shared.logger import getLogger
from system.tools.codegraph_builder import KnowledgeGraphBuilder

log = getLogger("core_admin.byor")

# --- THIS IS THE FIX ---
# We now point to the 'starter_kits/default' directory as the single
# source of truth for all project scaffolding templates.
CORE_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = CORE_ROOT / "system" / "starter_kits" / "default"
# --- END OF FIX ---


def initialize_repository(
    path: Path = typer.Argument(
        ...,
        help="The path to the external repository to analyze.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--write",
        help="Show the proposed .intent/ scaffold without writing files. Use --write to apply.",
    ),
):
    """
    Analyzes an external repository and scaffolds a minimal `.intent/` constitution.
    """
    log.info(f"🚀 Starting analysis of repository at: {path}")

    # Step 1: Build the Knowledge Graph.
    log.info("   -> Step 1: Building Knowledge Graph of the target repository...")
    try:
        builder = KnowledgeGraphBuilder(root_path=path)
        graph = builder.build()
        total_symbols = len(graph.get("symbols", {}))
        log.info(
            f"   -> ✅ Knowledge Graph built successfully. Found {total_symbols} symbols."
        )
    except Exception as e:
        log.error(f"   -> ❌ Failed to build Knowledge Graph: {e}", exc_info=True)
        raise typer.Exit(code=1)

    # Step 2: Generate the content for the new constitutional files.
    log.info("   -> Step 2: Generating starter constitution from analysis...")

    # File 1: source_structure.yaml
    domains = builder.domain_map
    source_structure_content = {
        "structure": [
            {
                "domain": name,
                "path": path_str,
                "description": f"Domain for '{name}' inferred by CORE.",
                "allowed_imports": [name, "shared"],
            }
            for path_str, name in domains.items()
        ]
    }

    # File 2: project_manifest.yaml
    discovered_capabilities = sorted(
        list(
            set(
                s["capability"]
                for s in graph.get("symbols", {}).values()
                if s.get("capability") != "unassigned"
            )
        )
    )
    project_manifest_content = {
        "name": path.name,
        "version": "0.1.0-core-scaffold",
        "intent": "A high-level description of what this project is intended to do.",
        "required_capabilities": discovered_capabilities,
    }

    # File 3: capability_tags.yaml (dynamically populated)
    # The content is read from the now-consolidated template file.
    (TEMPLATES_DIR / "capability_tags.yaml.template").read_text()
    capability_tags_content = {
        "tags": [
            {
                "name": cap,
                "description": "A clear explanation of what this capability does.",
            }
            for cap in discovered_capabilities
        ]
    }

    # The files we will create and their content.
    files_to_generate = {
        ".intent/knowledge/source_structure.yaml": source_structure_content,
        ".intent/project_manifest.yaml": project_manifest_content,
        ".intent/knowledge/capability_tags.yaml": capability_tags_content,
        ".intent/mission/principles.yaml": (
            TEMPLATES_DIR / "principles.yaml"
        ).read_text(),
        ".intent/policies/safety_policies.yaml": (
            TEMPLATES_DIR / "safety_policies.yaml"
        ).read_text(),
    }

    # Step 3: Write the files or display the dry run.
    if dry_run:
        log.info("\n💧 Dry Run Mode: No files will be written.")
        for rel_path, content in files_to_generate.items():
            typer.secho(f"\n📄 Proposed `{rel_path}`:", fg=typer.colors.YELLOW)
            if isinstance(content, dict):
                typer.echo(yaml.dump(content, indent=2))
            else:
                typer.echo(content)
    else:
        log.info("\n💾 **Write Mode:** Applying changes to disk.")
        for rel_path, content in files_to_generate.items():
            target_path = path / rel_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, dict):
                target_path.write_text(yaml.dump(content, indent=2))
            else:
                target_path.write_text(content)
            typer.secho(
                f"   -> ✅ Wrote starter file to {target_path}", fg=typer.colors.GREEN
            )

    log.info("\n🎉 BYOR initialization complete.")


def register(app: typer.Typer) -> None:
    """Register BYOR commands (e.g., `byor-init`) under the admin CLI."""
    app.command("byor-init")(initialize_repository)
