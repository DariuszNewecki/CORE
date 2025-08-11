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

def initialize_repository(
    path: Path = typer.Argument(
        ...,  # ... means the argument is required
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

    # Step 1: Build the Knowledge Graph. This is the core analysis.
    log.info("   -> Step 1: Building Knowledge Graph of the target repository...")
    try:
        # We tell the builder to use the *external* repo as its root.
        builder = KnowledgeGraphBuilder(root_path=path)
        graph = builder.build()
        total_symbols = len(graph.get("symbols", {}))
        log.info(f"   -> ✅ Knowledge Graph built successfully. Found {total_symbols} symbols.")
    except Exception as e:
        log.error(f"   -> ❌ Failed to build Knowledge Graph: {e}", exc_info=True)
        raise typer.Exit(code=1)

    # Step 2: Generate the content for the new constitutional files from the graph.
    log.info("   -> Step 2: Generating starter constitution from analysis...")
    
    # Infer domains from the graph's `domain_map`. This uses our new heuristic.
    domains = builder.domain_map
    source_structure_content = {
        "structure": [
            {
                "domain": name,
                "path": path_str,
                "description": f"Domain for '{name}' inferred by CORE.",
                "allowed_imports": [name, "shared"], # A sensible default
            }
            for path_str, name in domains.items()
        ]
    }
    
    # Discover all capabilities found in the code.
    discovered_capabilities = sorted(list(set(
        s["capability"] for s in graph.get("symbols", {}).values() if s.get("capability") != "unassigned"
    )))
    project_manifest_content = {
        "name": path.name,
        "version": "0.1.0-core-scaffold",
        "intent": "A high-level description of what this project is intended to do.",
        "required_capabilities": discovered_capabilities,
    }

    # Step 3: Write the files or display the dry run.
    if dry_run:
        log.info("\n💧 Dry Run Mode: No files will be written.")
        typer.secho("\n📄 Proposed `.intent/knowledge/source_structure.yaml`:", fg=typer.colors.YELLOW)
        typer.echo(yaml.dump(source_structure_content, indent=2))
        typer.secho("\n📄 Proposed `.intent/project_manifest.yaml`:", fg=typer.colors.YELLOW)
        typer.echo(yaml.dump(project_manifest_content, indent=2))
    else:
        log.info("\n💾 **Write Mode:** Applying changes to disk.")
        intent_dir = path / ".intent"
        knowledge_dir = intent_dir / "knowledge"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        
        ss_path = knowledge_dir / "source_structure.yaml"
        ss_path.write_text(yaml.dump(source_structure_content, indent=2))
        typer.secho(f"   -> ✅ Wrote starter constitution to {ss_path}", fg=typer.colors.GREEN)
        
        pm_path = intent_dir / "project_manifest.yaml"
        pm_path.write_text(yaml.dump(project_manifest_content, indent=2))
        typer.secho(f"   -> ✅ Wrote starter manifest to {pm_path}", fg=typer.colors.GREEN)

    log.info("\n🎉 BYOR initialization complete.")


def register(app: typer.Typer) -> None:
    """Intent: Register BYOR commands under the admin CLI."""
    app.command("byor-init")(initialize_repository)
