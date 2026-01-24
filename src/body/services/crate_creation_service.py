# src/body/services/crate_creation_service.py
# ID: b9ee3781-7db1-4445-a5f6-19eb7d658315

"""
Service for creating Intent Crates from generated code.

Packages code, tests, and metadata into constitutionally-compliant crates
that can be processed by CrateProcessingService with canary validation.

UNIX-Compliant Methodology:
- This is a "Body" component: it executes the packaging but makes no decisions.
- It is the "Staging Area" between the SpecificationAgent and ExecutionAgent.

Policy Alignment:
- Headless: Uses standard logging only.
- Safe-by-Default: Validates all paths before touching the disk.
- Governed: All mutations route through FileHandler (IntentGuard enforced).
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action

# REMOVED: from shared.config import settings
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: 8051b110-89d6-44f9-b787-21a3d58519b5
class CrateCreationService:
    """
    Creates Intent Crates from generated code.
    Acts as the bridge between Engineering (Will) and Construction (Body).
    """

    def __init__(self, core_context: CoreContext) -> None:
        """
        Initialize service with the system context.

        Args:
            core_context: The central container for system services.
        """
        self.context = core_context

        # REFACTOR: Access repo_path via context -> git_service
        self.repo_path = core_context.git_service.repo_path

        # REFACTOR: Construct canonical inbox path manually (var/workflows/crates/inbox)
        # This avoids depending on 'settings.paths'
        self.inbox_path = self.repo_path / "var" / "workflows" / "crates" / "inbox"

        self.fs = core_context.file_handler

    @atomic_action(
        action_id="crate.create",
        intent="Package generated code into an Intent Crate for canary validation",
        impact=ActionImpact.WRITE_DATA,
        policies=["body_contracts", "intent_crate_schema"],
        category="orchestration",
    )
    # ID: dc96d08d-72ec-407e-b087-349423ed66ef
    async def create_intent_crate(
        self,
        intent: str,
        payload_files: dict[str, str],
        crate_type: str = "STANDARD",
        metadata: dict[str, Any] | None = None,
    ) -> ActionResult:
        """
        The core logic to build a Crate. Returns an ActionResult for the Orchestrator.
        """
        start_time = time.time()
        crate_id = self._generate_crate_id()
        crate_path = self.inbox_path / crate_id

        # Convert to repo-relative path for FileHandler
        crate_rel = self._to_repo_rel(crate_path)

        try:
            # 1. Path Safety Check (Constitutional Guard)
            path_errors = self.validate_payload_paths(payload_files)
            if path_errors:
                return ActionResult(
                    action_id="crate.create",
                    ok=False,
                    data={
                        "error": "Forbidden paths in payload",
                        "details": path_errors,
                    },
                    duration_sec=time.time() - start_time,
                )

            # 2. Create directory (Governed Mutation)
            self.fs.ensure_dir(crate_rel)

            # 3. Create Manifest
            # REFACTOR: Use standard datetime formatting instead of settings helper
            timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

            manifest = {
                "crate_id": crate_id,
                "author": "CoderAgent",
                "intent": intent,
                "type": "CODE_MODIFICATION" if crate_type == "STANDARD" else crate_type,
                "created_at": timestamp,
                "metadata": metadata or {},
                "payload_files": list(payload_files.keys()),
            }

            # 4. Write Manifest & Payload (IntentGuard Enforced)
            self.fs.write_runtime_text(
                f"{crate_rel}/manifest.yaml", yaml.dump(manifest, sort_keys=False)
            )

            for rel_path, content in payload_files.items():
                # Ensure we don't allow traversal or absolute paths
                safe_file_rel = f"{crate_rel}/{rel_path.lstrip('/')}"
                self.fs.write_runtime_text(safe_file_rel, content)

            logger.info("Successfully created Crate: %s", crate_id)

            return ActionResult(
                action_id="crate.create",
                ok=True,
                data={
                    "crate_id": crate_id,
                    "path": crate_rel,
                    "file_count": len(payload_files),
                },
                duration_sec=time.time() - start_time,
                impact=ActionImpact.WRITE_DATA,
            )

        except Exception as e:
            logger.error("Crate creation failed: %s", e, exc_info=True)
            # Cleanup on failure via governed surface
            self.fs.remove_tree(crate_rel)

            return ActionResult(
                action_id="crate.create",
                ok=False,
                data={"error": str(e)},
                duration_sec=time.time() - start_time,
            )

    def _generate_crate_id(self) -> str:
        """Generate a deterministic, stable ID for the transaction."""
        return f"fix_{uuid.uuid4().hex[:8]}"

    # ID: 356375c5-8d95-441f-90ec-967f38794f35
    def validate_payload_paths(self, payload_files: dict[str, str]) -> list[str]:
        """
        Enforce Constitutional path boundaries.
        CORE must never write to .intent/** or keys/**.
        """
        errors: list[str] = []
        forbidden_roots = [".intent", "var/keys", "var/cache"]

        for path_str in payload_files.keys():
            p = Path(path_str)
            if p.is_absolute():
                errors.append(f"Absolute path forbidden: {path_str}")
                continue

            normalized = p.as_posix()
            if any(normalized.startswith(root) for root in forbidden_roots):
                errors.append(f"Constitutional boundary violation: {path_str}")

            if ".." in normalized:
                errors.append(f"Path traversal detected: {path_str}")

        return errors

    def _to_repo_rel(self, p: Path) -> str:
        """Internal helper to ensure paths are compatible with FileHandler."""
        try:
            return str(p.relative_to(self.repo_path))
        except ValueError:
            # If it's already relative, just return it
            return str(p)


# ID: a858d9e4-1fbe-4fcb-8af7-92d74a852024
@atomic_action(
    action_id="create.crate",
    intent="Atomic action for create_crate_from_spec",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: d7ec3f85-f7ba-4b08-8389-bd76082f9606
async def create_crate_from_spec(
    context: CoreContext,
    intent: str,
    files_generated: dict[str, str],
    metadata: dict[str, Any] | None = None,
) -> ActionResult:
    """
    Convenience wrapper for SpecificationAgent.
    """
    service = CrateCreationService(context)
    return await service.create_intent_crate(
        intent=intent, payload_files=files_generated, metadata=metadata
    )
