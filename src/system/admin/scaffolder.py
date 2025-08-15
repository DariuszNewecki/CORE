# src/system/admin/scaffolder.py
"""
Intent: Implements the 'new' command and provides a reusable Scaffolding service.
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


class Scaffolder:
    """A reusable service for creating new, constitutionally-governed projects."""

    def __init__(self, project_name: str, profile: str = "default"):
        self.name = project_name
        self.profile = profile
        self.project_root = WORKSPACE_DIR / self.name
        self.starter_kit_path = STARTER_KITS_DIR / self.profile

        if not self.starter_kit_path.is_dir():
            raise FileNotFoundError(
                f"Starter kit profile '{self.profile}' not found at {self.starter_kit_path}."
            )

    def scaffold_base_structure(self):
        """Creates the base directory structure and constitution from the starter kit."""
        log.info(f"💾 Creating project structure at {self.project_root}...")
        if self.project_root.exists():
            raise FileExistsError(f"Directory '{self.project_root}' already exists.")

        # Create the basic structure
        self.project_root.mkdir(parents=True, exist_ok=True)
        (self.project_root / "src").mkdir()
        (self.project_root / "reports").mkdir()

        # Copy and process template files
        for template_path in self.starter_kit_path.glob("*.template"):
            content = template_path.read_text().format(project_name=self.name)
            target_name = (
                ".gitignore"
                if template_path.name == "gitignore.template"
                else template_path.name.replace(".template", "")
            )
            (self.project_root / target_name).write_text(content)

        # Copy constitutional files
        intent_dir = self.project_root / ".intent"
        shutil.copytree(self.starter_kit_path, intent_dir, dirs_exist_ok=True)

        # Clean up non-constitutional files from the copied starter kit
        for f in intent_dir.glob("*.template"):
            f.unlink()
        (intent_dir / ".gitkeep").unlink(missing_ok=True)


        # Customize the new project's manifest
        manifest_path = intent_dir / "project_manifest.yaml"
        if manifest_path.exists():
            manifest_data = yaml.safe_load(manifest_path.read_text())
            manifest_data["name"] = self.name
            manifest_path.write_text(yaml.dump(manifest_data, indent=2))
        
        log.info(f"   -> ✅ Base structure for '{self.name}' created successfully.")

    def write_file(self, relative_path: str, content: str):
        """Writes a file into the newly scaffolded project."""
        target_file = self.project_root / relative_path
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(content, encoding="utf-8")
        log.info(f"   -> 📄 Wrote agent-generated file: {relative_path}")


# This remains the CLI command for manual scaffolding.
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
    log.info(
        f"🚀 Scaffolding new CORE application: '{name}' using '{profile}' profile."
    )
    if dry_run:
        log.info("\n💧 Dry Run Mode: No files will be written.")
        typer.secho(
            f"Would create project '{name}' in '{WORKSPACE_DIR}/' with the '{profile}' starter kit.",
            fg=typer.colors.YELLOW,
        )
    else:
        try:
            scaffolder = Scaffolder(project_name=name, profile=profile)
            scaffolder.scaffold_base_structure()
            # Add a basic README to the project root
            readme_content = (
                (scaffolder.starter_kit_path / "README.md.template")
                .read_text()
                .format(project_name=name)
            )
            scaffolder.write_file("README.md", readme_content)

        except FileExistsError as e:
            log.error(f"❌ {e}")
            raise typer.Exit(code=1)
        except Exception as e:
            log.error(f"❌ An unexpected error occurred: {e}", exc_info=True)
            raise typer.Exit(code=1)

    log.info(f"\n🎉 Scaffolding for '{name}' complete.")
    typer.secho("\nNext Steps:", bold=True)
    typer.echo(f"1. Navigate into your new project: `cd work/{name}`")
    typer.echo("2. Run `poetry install` to set up the environment.")
    typer.echo(
        f"3. From the CORE directory, run `core-admin byor-init work/{name}` to perform the first audit."
    )


def register(app: typer.Typer) -> None:
    """Intent: Register scaffolding commands under the admin CLI."""
    app.command("new")(new_project)