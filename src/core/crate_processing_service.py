# src/core/crate_processing_service.py
"""
Provides the core service for processing asynchronous, autonomous change requests (Intent Crates).
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import jsonschema
import yaml
from rich.console import Console

from features.governance.constitutional_auditor import AuditScope, ConstitutionalAuditor
from features.introspection.knowledge_graph_service import (
    KnowledgeGraphBuilder,
)
from shared.action_logger import action_logger
from shared.config import settings
from shared.logger import getLogger
from shared.models import AuditFinding

log = getLogger("crate_processing_service")
console = Console()


@dataclass
# ID: a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d
class Crate:
    """A simple data class representing a validated Intent Crate."""

    path: Path
    manifest: Dict[str, Any]


# ID: 5d7a8b3e-1f2c-4d5e-6f7a-8b9c0d1e2f3a
class CrateProcessingService:
    """
    Orchestrates the lifecycle of an Intent Crate: validation, canary testing, application, and result logging.
    """

    def __init__(self):
        """Initializes the service with its required dependencies and constitutional policies."""
        self.repo_root = settings.REPO_PATH
        self.crate_policy = settings.load(
            "charter.policies.governance.intent_crate_policy"
        )
        self.crate_schema = settings.load(
            "charter.schemas.constitutional.intent_crate_schema"
        )

        self.inbox_path = self.repo_root / "work" / "crates" / "inbox"
        self.processing_path = self.repo_root / "work" / "crates" / "processing"
        self.accepted_path = self.repo_root / "work" / "crates" / "accepted"
        self.rejected_path = self.repo_root / "work" / "crates" / "rejected"

        for path in [
            self.inbox_path,
            self.processing_path,
            self.accepted_path,
            self.rejected_path,
        ]:
            path.mkdir(parents=True, exist_ok=True)

        log.info("CrateProcessingService initialized and constitutionally configured.")

    # ID: 4e3d2c1b-0a9b-8c7d-6e5f-4a3b2c1d0e9f
    def _scan_and_validate_inbox(self) -> List[Crate]:
        """Scans the inbox for crates and validates their manifests."""
        valid_crates = []
        if not self.inbox_path.exists():
            return []

        for item in self.inbox_path.iterdir():
            if not item.is_dir():
                continue

            crate_id = item.name
            action_logger.log_event("crate.validation.started", {"crate_id": crate_id})
            manifest_path = item / "manifest.yaml"
            if not manifest_path.exists():
                reason = "missing manifest.yaml"
                log.warning(f"Skipping invalid crate '{crate_id}': {reason}.")
                action_logger.log_event(
                    "crate.validation.failed", {"crate_id": crate_id, "reason": reason}
                )
                continue

            try:
                manifest_content = settings._load_file_content(manifest_path)
                jsonschema.validate(instance=manifest_content, schema=self.crate_schema)
                valid_crates.append(Crate(path=item, manifest=manifest_content))
                log.info(
                    f"Validated crate '{crate_id}' with intent: '{manifest_content['intent']}'"
                )
            except (ValueError, jsonschema.ValidationError) as e:
                reason = f"Manifest validation failed: {e}"
                log.error(f"Rejecting invalid crate '{crate_id}': {reason}")
                action_logger.log_event(
                    "crate.validation.failed", {"crate_id": crate_id, "reason": str(e)}
                )
                self._move_crate_to_rejected(item, reason)
                continue

        return valid_crates

    # ID: 1b2c3d4e-5f6a-7b8c-9d0e-1f2a3b4c5d6e
    async def _run_canary_validation(
        self, crate: Crate
    ) -> tuple[bool, List[AuditFinding]]:
        """Creates a temporary environment, applies crate changes, and runs a full audit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            canary_path = Path(tmpdir) / "canary_repo"
            console.print(f"   -> Creating canary environment at {canary_path}")

            shutil.copytree(
                self.repo_root,
                canary_path,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(
                    ".git", ".venv", "__pycache__", "work", "reports"
                ),
            )

            env_file = self.repo_root / ".env"
            if env_file.exists():
                shutil.copy(env_file, canary_path / ".env")
                console.print(
                    "   -> Copied runtime environment configuration to canary."
                )

            console.print("   -> Applying proposed changes to canary...")
            payload_files = crate.manifest.get("payload_files", [])
            for file_in_payload in payload_files:
                source_path = crate.path / file_in_payload
                if crate.manifest.get("type") == "CONSTITUTIONAL_AMENDMENT":
                    target_path = (
                        canary_path
                        / ".intent/charter/policies/governance"
                        / file_in_payload
                    )
                else:
                    target_path = canary_path / file_in_payload

                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target_path)

            console.print("   -> Building canary's internal knowledge graph...")
            canary_builder = KnowledgeGraphBuilder(root_path=canary_path)
            await canary_builder.build_and_sync()

            console.print("   -> 🔬 Running full constitutional audit on canary...")
            auditor = ConstitutionalAuditor(repo_root_override=canary_path)
            passed, findings, _ = await auditor.run_full_audit_async(
                scope=AuditScope.STATIC_ONLY
            )

            if passed:
                console.print("   -> [bold green]✅ Canary audit PASSED.[/bold green]")
                return True, []
            else:
                console.print("   -> [bold red]❌ Canary audit FAILED.[/bold red]")
                return False, findings

    def _apply_accepted_crate(self, crate: Crate):
        """Applies the payload of an accepted crate to the live repository."""
        console.print(
            f"   -> Applying accepted crate '{crate.path.name}' to live system..."
        )
        payload_files = crate.manifest.get("payload_files", [])
        for file_in_payload in payload_files:
            source_path = crate.path / file_in_payload

            if crate.manifest.get("type") == "CONSTITUTIONAL_AMENDMENT":
                target_path = (
                    self.repo_root
                    / ".intent/charter/policies/governance"
                    / file_in_payload
                )
            else:
                target_path = self.repo_root / file_in_payload

            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
            console.print(f"      -> Applied '{file_in_payload}'")

    def _write_result_manifest(self, crate_path: Path, status: str, details: Any):
        """Writes a result.yaml file into the processed crate directory."""
        result_content = {
            "status": status,
            "processed_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        if isinstance(details, str):
            result_content["justification"] = details
        elif isinstance(details, list):
            result_content["violations"] = [finding.as_dict() for finding in details]

        result_path = crate_path / "result.yaml"
        result_path.write_text(yaml.dump(result_content, indent=2), "utf-8")

    def _move_crate_to_rejected(self, crate_path: Path, details: Any):
        """Moves a crate to the rejected directory and writes a result manifest."""
        crate_id = crate_path.name
        final_path = self.rejected_path / crate_id
        shutil.move(str(crate_path), str(final_path))
        self._write_result_manifest(final_path, "rejected", details)

        reason_summary = (
            details
            if isinstance(details, str)
            else f"{len(details)} constitutional violations found."
        )
        console.print(f"   -> Moved to rejected. Reason: {reason_summary}")

        log_details = {"crate_id": crate_id}
        if isinstance(details, str):
            log_details["reason"] = details
        else:
            log_details["violations"] = [finding.as_dict() for finding in details]

        action_logger.log_event("crate.processing.rejected", log_details)

    # ID: 9a8b7c6d-5e4f-3a2b-1c0d-9e8f7a6b5c4d
    async def process_pending_crates_async(self):
        """
        The main entry point for the service. It finds and processes all crates in the inbox.
        """
        console.print(
            "[bold cyan]🚀 Starting new crate processing cycle...[/bold cyan]"
        )

        valid_crates = self._scan_and_validate_inbox()
        if not valid_crates:
            console.print("✅ No valid crates found in the inbox. Cycle complete.")
            return

        console.print(f"Found {len(valid_crates)} valid crate(s) to process.")

        for crate in valid_crates:
            crate_id = crate.path.name
            console.print(f"\n[bold]Processing crate: {crate_id}[/bold]")
            try:
                processing_path = self.processing_path / crate_id
                shutil.move(str(crate.path), str(processing_path))
                crate.path = processing_path
                console.print(
                    f"   -> Moved to processing: {processing_path.relative_to(self.repo_root)}"
                )
                action_logger.log_event(
                    "crate.processing.started", {"crate_id": crate_id}
                )

                is_safe, findings = await self._run_canary_validation(crate)

                if is_safe:
                    self._apply_accepted_crate(crate)
                    final_path = self.accepted_path / crate.path.name
                    shutil.move(str(crate.path), str(final_path))
                    self._write_result_manifest(
                        final_path,
                        "accepted",
                        "Canary audit passed and changes were applied.",
                    )
                    console.print("   -> Moved to accepted.")
                    action_logger.log_event(
                        "crate.processing.accepted",
                        {
                            "crate_id": crate_id,
                            "reason": "Canary audit passed and changes applied.",
                        },
                    )
                else:
                    self._move_crate_to_rejected(crate.path, findings)

            except Exception as e:
                log.error(f"Failed to process crate '{crate_id}': {e}", exc_info=True)
                self._move_crate_to_rejected(
                    crate.path, f"Internal processing error: {e}"
                )
                continue


# ID: 3e2d1c0b-9a8b-7c6d-5e4f-3a2b1c0d9e8f
async def process_crates():
    """High-level function to instantiate and run the service."""
    service = CrateProcessingService()
    await service.process_pending_crates_async()
