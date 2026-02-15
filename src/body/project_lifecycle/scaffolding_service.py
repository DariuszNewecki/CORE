# src/body/project_lifecycle/scaffolding_service.py
# ID: b2a71e87-f72f-4868-8e63-9538096af12e

"""
Service to scaffold a new CORE-governed project with templates and structure.
MOVED: From features/project_lifecycle to body/project_lifecycle (Wave 1 Rebirth).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import yaml

from body.atomic.executor import ActionExecutor
from shared.config import settings
from shared.logger import getLogger
from shared.path_utils import get_repo_root


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: defb2539-73fe-43dd-9bb1-506a3f076570
class Scaffolder:
    """
    Orchestrates the creation of a new CORE project via governed Atomic Actions.
    """

    def __init__(
        self, context: CoreContext, project_name: str, profile: str = "default"
    ):
        self.context = context
        self.executor = ActionExecutor(context)
        self.name = project_name
        self.profile = profile

        # Scaffolding target is typically a sibling to the current REPO_PATH
        self.workspace = settings.REPO_PATH.parent
        self.project_root = self.workspace / project_name

        # Source of truth for templates
        repo_root = get_repo_root()
        self.starter_kit_path = (
            repo_root / "starter_kits" / "project_profiles" / profile
        )

        if not self.starter_kit_path.exists():
            raise FileNotFoundError(
                f"Starter kit profile '{profile}' not found at {self.starter_kit_path}"
            )

    # ID: 882f22a6-a1f3-4a31-8967-09f8b9d763ab
    async def scaffold_base_structure(self, write: bool = False) -> None:
        """
        Creates the base project structure via governed Atomic Actions.
        """
        logger.info("💾 Planning project structure at %s...", self.project_root)

        if self.project_root.exists() and write:
            raise FileExistsError(f"Directory '{self.project_root}' already exists.")

        # 1. Define required directory structure
        dirs_to_create = [
            "",  # Root
            "src",
            "tests",
            ".github/workflows",
            "reports",
            ".intent",
        ]

        # Use the FileHandler via the Gateway to ensure directories exist
        for d in dirs_to_create:
            rel_dir = f"../{self.name}/{d}".strip("/")
            if write:
                self.context.file_handler.ensure_dir(rel_dir)
            else:
                logger.info("   -> [DRY RUN] Would create directory: %s", rel_dir)

        # 2. Copy Constitutional Files
        constitutional_files = [
            "principles.yaml",
            "project_manifest.yaml",
            "safety_policies.yaml",
            "source_structure.yaml",
            "README.md",
        ]

        for filename in constitutional_files:
            source_path = self.starter_kit_path / filename
            if not source_path.exists():
                continue

            content = source_path.read_text(encoding="utf-8")
            target_rel_path = f"../{self.name}/.intent/{filename}"

            await self.executor.execute(
                action_id="file.create",
                write=write,
                file_path=target_rel_path,
                code=content,
            )

        # 3. Process Templates (.template files)
        for template_path in self.starter_kit_path.glob("*.template"):
            content = template_path.read_text(encoding="utf-8").format(
                project_name=self.name
            )

            target_base = (
                ".gitignore"
                if template_path.name == "gitignore.template"
                else template_path.name.replace(".template", "")
            )
            target_rel_path = f"../{self.name}/{target_base}"

            await self.executor.execute(
                action_id="file.create",
                write=write,
                file_path=target_rel_path,
                code=content,
            )

        # 4. Finalize Manifest
        manifest_rel = f"../{self.name}/.intent/project_manifest.yaml"
        manifest_abs = self.project_root / ".intent" / "project_manifest.yaml"
        if manifest_abs.exists():
            manifest_data = (
                yaml.safe_load(manifest_abs.read_text(encoding="utf-8")) or {}
            )
            manifest_data["name"] = self.name

            await self.executor.execute(
                action_id="file.edit",
                write=write,
                file_path=manifest_rel,
                code=yaml.dump(manifest_data, indent=2),
            )

        logger.info(
            "   -> ✅ Base structure for '%s' orchestrated successfully.", self.name
        )

    # ID: badd73be-d36f-44a8-a4f9-6c3d9b025b80
    async def write_file(
        self, relative_path: str, content: str, write: bool = False
    ) -> None:
        """Writes content to a file within the new project via the Gateway."""
        target_rel = f"../{self.name}/{relative_path}"

        await self.executor.execute(
            action_id="file.create", write=write, file_path=target_rel, code=content
        )


async def _create_new_project(
    context: CoreContext, name: str, profile: str = "default", write: bool = False
) -> None:
    """
    Domain-level operation to scaffold a new CORE project.
    """
    scaffolder = Scaffolder(context, project_name=name, profile=profile)

    mode_str = "WRITE" if write else "DRY RUN"
    logger.info("🚀 Scaffolding new CORE application: '%s' [%s]", name, mode_str)

    try:
        await scaffolder.scaffold_base_structure(write=write)

        readme_template_path = scaffolder.starter_kit_path / "README.md.template"
        if readme_template_path.exists():
            readme_content = readme_template_path.read_text(encoding="utf-8").format(
                project_name=name
            )
            await scaffolder.write_file("README.md", readme_content, write=write)

    except Exception as e:
        logger.error("❌ Scaffolding failed for '%s': %s", name, e, exc_info=True)
        raise


# Alias for backward compatibility
create_new_project = _create_new_project
