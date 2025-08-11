# src/system/admin/scaffolder.py
"""
Intent: Implements the 'new' command for scaffolding new CORE-native projects.

This command is the entry point for the "CORE-fication" pipeline, responsible
for creating new Mind/Body applications from scratch, complete with a starter
constitution and CI/CD wiring.
"""

import shutil
from pathlib import Path
import typer
import yaml
from shared.logger import getLogger

log = getLogger("core_admin.scaffolder")
CORE_ROOT = Path(__file__).resolve().parents[2]
STARTER_KITS_DIR = CORE_ROOT / "system" / "starter_kits"


# --- Minimal templates for a new project ---

GITIGNORE_TEMPLATE = """
# Python
__pycache__/
*.py[cod]
.venv/
.env

# CORE-specific
.intent/knowledge/knowledge_graph.json
reports/
logs/
"""

PYPROJECT_TEMPLATE = """
[tool.poetry]
name = "{project_name}"
version = "0.1.0"
description = "A new project governed by CORE."
authors = ["Your Name <you@example.com>"]
readme = "README.md"

[tool.poetry.dependencies]
python = ">=3.9"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
"""

def new_project(
    name: str = typer.Argument(
        ...,
        help="The name of the new CORE-governed application to create.",
    ),
    profile: str = typer.Option(
        "default",
        "--profile",
        help="The starter kit profile to use for the new project's constitution.",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--write",
        help="Show what will be created without writing files. Use --write to apply.",
    ),
):
    """
    Scaffolds a new, constitutionally-governed "Mind/Body" application.
    """
    log.info(f"🚀 Scaffolding new CORE application: '{name}' using '{profile}' profile.")
    project_root = Path.cwd() / name
    starter_kit_path = STARTER_KITS_DIR / profile

    if not starter_kit_path.is_dir():
        log.error(f"❌ Starter kit profile '{profile}' not found at {starter_kit_path}.")
        raise typer.Exit(code=1)

    # Define the core directory structure and basic files
    scaffold_plan = {
        "src/main": None,
        "src/shared": None,
        ".gitignore": GITIGNORE_TEMPLATE,
        "pyproject.toml": PYPROJECT_TEMPLATE.format(project_name=name),
        "README.md": f"# {name}\n\nA new project governed by CORE.",
    }

    if dry_run:
        log.info("\n💧 Dry Run Mode: No files will be written.")
        typer.secho(f"Would create the following structure inside ./{name}/:", fg=typer.colors.YELLOW)
        for rel_path, content in scaffold_plan.items():
            typer.secho(f"  - {'[Dir]' if content is None else '[File]'} {rel_path}", fg=typer.colors.CYAN)
        typer.secho("  - [Dir] .intent/ (populated from starter kit)", fg=typer.colors.CYAN)

    else:
        log.info("\n💾 **Write Mode:** Creating project structure...")
        if project_root.exists():
            log.error(f"❌ Directory '{name}' already exists. Aborting.")
            raise typer.Exit(code=1)
        project_root.mkdir()

        # Create basic files and directories
        for rel_path, content in scaffold_plan.items():
            target_path = project_root / rel_path
            if content is None:
                target_path.mkdir(parents=True, exist_ok=True)
                typer.secho(f"   -> ✅ Created directory: {target_path}", fg=typer.colors.GREEN)
            else:
                target_path.write_text(content)
                typer.secho(f"   -> ✅ Created file:      {target_path}", fg=typer.colors.GREEN)

        # Copy and customize the starter kit
        intent_dir = project_root / ".intent"
        shutil.copytree(starter_kit_path, intent_dir)
        typer.secho(f"   -> ✅ Populated .intent/ from '{profile}' starter kit", fg=typer.colors.GREEN)

        # Dynamically update the project name in the new manifest
        manifest_path = intent_dir / "project_manifest.yaml"
        if manifest_path.exists():
            manifest_data = yaml.safe_load(manifest_path.read_text())
            manifest_data["name"] = name
            manifest_path.write_text(yaml.dump(manifest_data, indent=2))
            typer.secho(f"   -> ✅ Customized project name in manifest", fg=typer.colors.GREEN)

    log.info(f"\n🎉 Scaffolding for '{name}' complete.")
    typer.secho("\nNext Steps:", bold=True)
    typer.echo(f"1. Navigate into your new project: `cd {name}`")
    typer.echo("2. Run `poetry install` to set up the environment.")
    typer.echo("3. Run `core-admin byor-init .` to perform the first audit.")

def register(app: typer.Typer) -> None:
    """Intent: Register scaffolding commands under the admin CLI."""
    app.command("new")(new_project)
