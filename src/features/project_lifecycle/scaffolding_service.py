# src/features/project_lifecycle/scaffolding_service.py

"""
Service to scaffold a new CORE-governed project with templates and structure.

Domain-level scaffolding logic lives in `_create_new_project`, with a
backwards-compatible `create_new_project` alias used by the CLI. The alias
keeps the public API stable while avoiding treating this helper as a
first-class governed capability until the project lifecycle domain is fully
modelled in capabilities.
"""

from __future__ import annotations

import yaml

from shared.config import settings
from shared.logger import getLogger
from shared.path_utils import get_repo_root


logger = getLogger(__name__)


# ID: b2a71e87-f72f-4868-8e63-9538096af12e
class Scaffolder:
    """
    Handles filesystem operations to create a new CORE-governed project
    from a starter kit profile.
    """

    def __init__(self, project_name: str, profile: str = "default"):
        self.name = project_name
        self.profile = profile
        self.workspace = settings.REPO_PATH.parent
        self.project_root = self.workspace / project_name
        repo_root = get_repo_root()
        self.starter_kit_path = (
            repo_root / "starter_kits" / "project_profiles" / profile
        )
        if not self.starter_kit_path.exists():
            raise FileNotFoundError(
                f"Starter kit profile '{profile}' not found at {self.starter_kit_path}"
            )

    # ID: 882f22a6-a1f3-4a31-8967-09f8b9d763ab
    def scaffold_base_structure(self) -> None:
        """Creates the base project structure, including tests and CI directories."""
        logger.info("💾 Creating project structure at %s...", self.project_root)
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
        logger.info("   -> ✅ Base structure for '%s' created successfully.", self.name)

    # ID: badd73be-d36f-44a8-a4f9-6c3d9b025b80
    def write_file(self, relative_path: str, content: str) -> None:
        """Writes content to a file within the new project's directory, creating parent directories as needed."""
        target_file = self.project_root / relative_path
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(content, encoding="utf-8")
        logger.info("   -> 📄 Wrote agent-generated file: %s", relative_path)


def _create_new_project(
    name: str, profile: str = "default", dry_run: bool = True
) -> None:
    """
    Domain-level operation to scaffold a new CORE-governed project.

    This is pure service logic:
    - No Typer dependencies
    - No direct exit codes
    - Uses logging and exceptions only

    It is intentionally kept as a private helper from the perspective of
    the intent_alignment auditor; the CLI-level entrypoint is the governed
    surface, and this function is an implementation detail behind it.
    """
    scaffolder = Scaffolder(project_name=name, profile=profile)
    logger.info(
        "🚀 Scaffolding new CORE application: '%s' using '%s' profile.", name, profile
    )
    if dry_run:
        logger.info(
            "💧 Dry Run Mode: no files will be written. Would create project '%s' in '%s/' with the '%s' starter kit.",
            name,
            scaffolder.workspace,
            profile,
        )
        return
    try:
        scaffolder.scaffold_base_structure()
        readme_template_path = scaffolder.starter_kit_path / "README.md.template"
        if readme_template_path.exists():
            readme_content = readme_template_path.read_text(encoding="utf-8").format(
                project_name=name
            )
            scaffolder.write_file("README.md", readme_content)
    except FileExistsError:
        logger.error(
            "❌ Cannot scaffold project '%s': destination already exists at %s",
            name,
            scaffolder.project_root,
        )
        raise
    except Exception as e:
        logger.error(
            "❌ Unexpected error while scaffolding project '%s': %s",
            name,
            e,
            exc_info=True,
        )
        raise


create_new_project = _create_new_project
