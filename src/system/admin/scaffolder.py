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
WORKSPACE_DIR = CORE_ROOT / "work"

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
    
    project_root = WORKSPACE_DIR / name
    starter_kit_path = STARTER_KITS_DIR / profile

    if not starter_kit_path.is_dir():
        log.error(f"❌ Starter kit profile '{profile}' not found at {starter_kit_path}.")
        raise typer.Exit(code=1)

    # --- THIS IS THE NEW, CLEAN LOGIC ---
    # The scaffolder no longer contains hardcoded templates. It only reads files.
    if dry_run:
        log.info("\n💧 Dry Run Mode: No files will be written.")
        typer.secho(f"Would create project '{name}' in '{WORKSPACE_DIR}/' with the '{profile}' starter kit.", fg=typer.colors.YELLOW)
    else:
        log.info(f"\n💾 **Write Mode:** Creating project structure at {project_root}...")
        if project_root.exists():
            log.error(f"❌ Directory '{project_root}' already exists. Aborting.")
            raise typer.Exit(code=1)
        
        # Create the basic structure
        project_root.mkdir(parents=True, exist_ok=True)
        (project_root / "src").mkdir()
        (project_root / "reports").mkdir()

        # Copy and process all template files from the starter kit
        for template_path in starter_kit_path.glob("*.template"):
            content = template_path.read_text().format(project_name=name)
            
            # Remove '.template' and handle special case for '.gitignore'
            if template_path.name == "gitignore.template":
                target_name = ".gitignore"
            else:
                target_name = template_path.name.replace(".template", "")
                
            target_path = project_root / target_name
            target_path.write_text(content)
            typer.secho(f"   -> ✅ Created file:      {target_path}", fg=typer.colors.GREEN)
            
        # Copy constitutional files into the .intent directory
        intent_dir = project_root / ".intent"
        intent_dir.mkdir()
        
        constitutional_files = [
            "principles.yaml", "project_manifest.yaml", "safety_policies.yaml", "source_structure.yaml"
        ]
        # Also copy the intent README
        shutil.copy(starter_kit_path / "intent_README.md.template", intent_dir / "README.md")

        for f in constitutional_files:
             shutil.copy(starter_kit_path / f, intent_dir / f)

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
    typer.echo(f"1. Navigate into your new project: `cd work/{name}`")
    typer.echo("2. Run `poetry install` to set up the environment.")
    typer.echo(f"3. From the CORE directory, run `core-admin byor-init work/{name}` to perform the first audit.")

def register(app: typer.Typer) -> None:
    """Intent: Register scaffolding commands under the admin CLI."""
    app.command("new")(new_project)
