# src/features/project_lifecycle/scaffolding_service.py

"""
Provides a reusable service for scaffolding new CORE-governed projects with constitutional compliance.
"""

from __future__ import annotations

from pathlib import Path

import typer
import yaml
from shared.config import settings
from shared.logger import getLogger
from shared.path_utils import get_repo_root

logger = getLogger(__name__)
CORE_ROOT = get_repo_root()
STARTER_KITS_DIR = CORE_ROOT / "src" / "features" / "project_lifecycle" / "starter_kits"


# ID: b7d1b0a0-e1f3-4936-a61c-e6c05ab1b001
class Scaffolder:
    """A reusable service for creating new, constitutionally-governed projects."""

    def __init__(
        self,
        project_name: str,
        profile: str = "default",
        workspace_dir: Path | None = None,
    ):
        """Initializes the Scaffolder with project name, profile, and workspace directory."""
        self.name = project_name
        self.profile = profile
        source_structure = settings.load("mind.knowledge.source_structure")
        workspace_path_str = source_structure.get("paths", {}).get("workspace", "work")
        self.workspace = workspace_dir or CORE_ROOT / workspace_path_str
        self.project_root = self.workspace / self.name
        self.starter_kit_path = STARTER_KITS_DIR / self.profile
        if not self.starter_kit_path.is_dir():
            raise FileNotFoundError(
                f"Starter kit profile '{self.profile}' not found at {self.starter_kit_path}."
            )

    # ID: 5bb9dca0-ebfc-420f-ab6b-88f8b03831a5
    def scaffold_base_structure(self):
        """Creates the base project structure, including tests and CI directories."""
        logger.info(f"💾 Creating project structure at {self.project_root}...")
        if self.project_root.exists():
            raise FileExistsError(f"Directory '{self.project_root}' already exists.")
        self.project_root.mkdir(parents=True, exist_ok=True)
        (self.project_root / "src").mkdir()
        (self.project_root / "tests").mkdir()
        (self.project_root / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
        (self.project_root / "reports").mkdir()
        intent_dir = self.project_root / ".intent"
        intent_dir.mkdir()
        constitutional_files_to_copy = [
            "principles.yaml",
            "project_manifest.yaml",
            "safety_policies.yaml",
            "source_structure.yaml",
        ]
        for filename in constitutional_files_to_copy:
            source_path = self.starter_kit_path / filename
            if source_path.exists():
                target_path = intent_dir / filename
                target_path.write_bytes(source_path.read_bytes())
        readme_template = self.starter_kit_path / "README.md"
        if readme_template.exists():
            target_path = intent_dir / "README.md"
            target_path.write_bytes(readme_template.read_bytes())
        for template_path in self.starter_kit_path.glob("*.template"):
            content = template_path.read_text(encoding="utf-8").format(
                project_name=self.name
            )
            target_name = (
                ".gitignore"
                if template_path.name == "gitignore.template"
                else template_path.name.replace(".template", "")
            )
            (self.project_root / target_name).write_text(content, encoding="utf-8")
        manifest_path = intent_dir / "project_manifest.yaml"
        if manifest_path.exists():
            manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            if manifest_data:
                manifest_data["name"] = self.name
                manifest_path.write_text(
                    yaml.dump(manifest_data, indent=2), encoding="utf-8"
                )
        logger.info(f"   -> ✅ Base structure for '{self.name}' created successfully.")

    # ID: 7a9df125-ef0b-4c81-b150-82594b288bdc
    def write_file(self, relative_path: str, content: str):
        """Writes content to a file within the new project's directory, creating parent directories as needed."""
        target_file = self.project_root / relative_path
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(content, encoding="utf-8")
        logger.info(f"   -> 📄 Wrote agent-generated file: {relative_path}")


# ID: cbb1b4bb-e21a-4cac-bbe2-d288fa0400ac
def new_project(
    name: str = typer.Argument(
        ..., help="The name of the new CORE-governed application to create."
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
    """Scaffolds a new CORE-governed application with the given name, profile, and dry-run option, including base structure and README generation."""
    scaffolder = Scaffolder(project_name=name, profile=profile)
    logger.info(
        f"🚀 Scaffolding new CORE application: '{name}' using '{profile}' profile."
    )
    if dry_run:
        logger.info("\n💧 Dry Run Mode: No files will be written.")
        typer.secho(
            f"Would create project '{name}' in '{scaffolder.workspace}/' with the '{profile}' starter kit.",
            fg=typer.colors.YELLOW,
        )
    else:
        try:
            scaffolder.scaffold_base_structure()
            readme_template_path = scaffolder.starter_kit_path / "README.md.template"
            if readme_template_path.exists():
                readme_content = readme_template_path.read_text(
                    encoding="utf-8"
                ).format(project_name=name)
                scaffolder.write_file("README.md", readme_content)
        except FileExistsError as e:
            logger.error(f"❌ {e}")
            raise typer.Exit(code=1)
        except Exception as e:
            logger.error(f"❌ An unexpected error occurred: {e}", exc_info=True)
            raise typer.Exit(code=1)
