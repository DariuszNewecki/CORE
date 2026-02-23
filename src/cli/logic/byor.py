# src/body/cli/logic/byor.py

"""
Implements the 'byor-init' command to analyze external repositories and scaffold minimal CORE governance structures.

CONSTITUTIONAL FIX:
- Aligned with 'governance.artifact_mutation.traceable'.
- Replaced direct Path writes with governed FileHandler mutations.
- Centralizes mutation logic via the Body layer for auditability.
"""

from __future__ import annotations

from pathlib import Path

import typer
import yaml

from body.introspection.knowledge_graph_service import KnowledgeGraphBuilder
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger


logger = getLogger(__name__)
CORE_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = (
    CORE_ROOT / "src" / "features" / "project_lifecycle" / "starter_kits" / "default"
)


# ID: 8b2ee927-9c35-4125-b291-22669733e531
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
    logger.info("🚀 Starting analysis of repository at: %s", path)
    logger.info("   -> Step 1: Building Knowledge Graph of the target repository...")
    try:
        builder = KnowledgeGraphBuilder(root_path=path)
        graph = builder.build()
        total_symbols = len(graph.get("symbols", {}))
        logger.info(
            "   -> ✅ Knowledge Graph built successfully. Found %s symbols.",
            total_symbols,
        )
    except Exception as e:
        logger.error("   -> ❌ Failed to build Knowledge Graph: %s", e, exc_info=True)
        raise typer.Exit(code=1)

    logger.info("   -> Step 2: Generating starter constitution from analysis...")
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

    # Pre-flight check on template availability
    tag_template_path = TEMPLATES_DIR / "capability_tags.yaml.template"
    if not tag_template_path.exists():
        logger.warning("Template missing: %s", tag_template_path)

    capability_tags_content = {
        "tags": [
            {
                "name": cap,
                "description": "A clear explanation of what this capability does.",
            }
            for cap in discovered_capabilities
        ]
    }

    files_to_generate = {
        ".intent/knowledge/source_structure.yaml": source_structure_content,
        ".intent/project_manifest.yaml": project_manifest_content,
        ".intent/knowledge/capability_tags.yaml": capability_tags_content,
        ".intent/mission/principles.yaml": (
            TEMPLATES_DIR / "principles.yaml"
        ).read_text(encoding="utf-8"),
        ".intent/policies/safety_policies.yaml": (
            TEMPLATES_DIR / "safety_policies.yaml"
        ).read_text(encoding="utf-8"),
    }

    if dry_run:
        logger.info("\n💧 Dry Run Mode: No files will be written.")
        for rel_path, content in files_to_generate.items():
            typer.secho(f"\n📄 Proposed `{rel_path}`:", fg=typer.colors.YELLOW)
            if isinstance(content, dict):
                typer.echo(yaml.dump(content, indent=2, sort_keys=False))
            else:
                typer.echo(content)
    else:
        logger.info("\n💾 **Write Mode:** Applying changes to disk.")

        # CONSTITUTIONAL FIX: Initialize FileHandler for the target path.
        # This ensures all writes are traceable and governed by IntentGuard.
        # NOTE: BYOR is allowed to write to .intent in the NEW repo because
        # the FileHandler is rooted at the external 'path'.
        fh = FileHandler(str(path))

        for rel_path, content in files_to_generate.items():
            if isinstance(content, dict):
                output_content = yaml.dump(content, indent=2, sort_keys=False)
            else:
                output_content = content

            try:
                # Use governed mutation surface instead of Path.write_text
                fh.write_runtime_text(rel_path, output_content)
                typer.secho(
                    f"   -> ✅ Wrote starter file: {rel_path}", fg=typer.colors.GREEN
                )
            except Exception as e:
                logger.error("   -> ❌ Failed to write %s: %s", rel_path, e)

    logger.info("\n🎉 BYOR initialization complete.")
