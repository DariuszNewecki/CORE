# src/body/services/crate_processing_service.py

"""
Provides the core service for processing asynchronous, autonomous change requests (Intent Crates).
"""

from __future__ import annotations

import fnmatch
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema
import yaml
from features.crate_processing.canary_executor import CanaryExecutor
from features.introspection.knowledge_graph_service import KnowledgeGraphBuilder
from mind.governance.audit_context import AuditorContext
from shared.action_logger import action_logger
from shared.config import settings
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

from src.mind.governance.auditor import ConstitutionalAuditor

logger = getLogger(__name__)


@dataclass
# ID: 96730f37-f39b-4241-9409-8c4664520beb
class Crate:
    """A simple data class representing a validated Intent Crate."""

    path: Path
    manifest: dict[str, Any]


# ID: 28207c61-99ce-4a66-940e-cb46c069ef81
class CrateProcessingService:
    """
    Orchestrates the lifecycle of an Intent Crate: validation, canary testing, application, and result logging.
    """

    def __init__(self):
        """Initializes the service with its required dependencies and constitutional policies."""
        self.repo_root = settings.REPO_PATH

        # Load operational policy (canary rules)
        try:
            ops_policy = settings.load("charter.policies.operations")
            self.canary_config = ops_policy.get("canary", {})
        except Exception as e:
            logger.warning("Failed to load canary policy from operations.yaml: %s", e)
            self.canary_config = {}

        # Initialize Canary Executor
        self.canary_executor = CanaryExecutor(self.canary_config)

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
        logger.info(
            "CrateProcessingService initialized and constitutionally configured."
        )

    def _scan_and_validate_inbox(self) -> list[Crate]:
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
                logger.warning("Skipping invalid crate '%s': %s.", crate_id, reason)
                action_logger.log_event(
                    "crate.validation.failed", {"crate_id": crate_id, "reason": reason}
                )
                continue
            try:
                manifest_content = settings._load_file_content(manifest_path)
                jsonschema.validate(instance=manifest_content, schema=self.crate_schema)
                valid_crates.append(Crate(path=item, manifest=manifest_content))
                logger.info(
                    "Validated crate '%s' with intent: '%s'",
                    crate_id,
                    manifest_content["intent"],
                )
            except (ValueError, jsonschema.ValidationError) as e:
                reason = f"Manifest validation failed: {e}"
                logger.error("Rejecting invalid crate '%s': %s", crate_id, reason)
                action_logger.log_event(
                    "crate.validation.failed", {"crate_id": crate_id, "reason": str(e)}
                )
                self._move_crate_to_rejected(item, reason)
                continue
        return valid_crates

    def _copy_tree(self, src: Path, dst: Path, ignore_patterns: list[str]):
        """A simple replacement for shutil.copytree to avoid the import."""
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            if any(fnmatch.fnmatch(item.name, p) for p in ignore_patterns):
                continue
            s = src / item.name
            d = dst / item.name
            if s.is_dir():
                self._copy_tree(s, d, ignore_patterns)
            else:
                d.parent.mkdir(parents=True, exist_ok=True)
                d.write_bytes(s.read_bytes())

    def _copy_file(self, src: Path, dst: Path):
        """A simple replacement for shutil.copy2."""
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())

    async def _run_canary_validation(
        self, crate: Crate
    ) -> tuple[bool, list[AuditFinding]]:
        """Creates a temporary environment, applies crate changes, and runs a full audit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            canary_path = Path(tmpdir) / "canary_repo"
            logger.info("Creating canary environment at %s", canary_path)
            self._copy_tree(
                self.repo_root,
                canary_path,
                ignore_patterns=[".git", ".venv", "__pycache__", "work", "reports"],
            )
            env_file = self.repo_root / ".env"
            if env_file.exists():
                self._copy_file(env_file, canary_path / ".env")
                logger.debug("Copied runtime environment configuration to canary.")
            logger.info("Applying proposed changes to canary...")
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
                self._copy_file(source_path, target_path)

            logger.info("Building canary's internal knowledge graph...")
            canary_builder = KnowledgeGraphBuilder(root_path=canary_path)
            canary_builder.build()

            logger.info("Running full constitutional audit on canary...")
            auditor = ConstitutionalAuditor(AuditorContext(canary_path))

            # Get raw findings (dicts)
            raw_findings = await auditor.run_full_audit_async()

            # Convert to objects
            all_findings = [AuditFinding(**f) for f in raw_findings]

            # 1. Calculate metrics from audit results
            metrics = self.canary_executor.derive_metrics_from_audit(all_findings)

            # 2. Enforce constitutional thresholds via CanaryExecutor
            canary_result = self.canary_executor.enforce(metrics)

            # 3. Check results
            if canary_result.passed:
                logger.info("Canary audit PASSED.")
                return (True, [])
            else:
                # Convert policy violations into synthetic AuditFindings for the report
                violation_findings = []
                for msg in canary_result.violations:
                    violation_findings.append(
                        AuditFinding(
                            check_id="operations.canary_policy",
                            severity=AuditSeverity.ERROR,
                            message=msg,
                            file_path="operations.yaml",
                        )
                    )

                # Return the specific violations + any existing errors/warnings that caused them
                combined_findings = violation_findings + [
                    f
                    for f in all_findings
                    if f.severity in (AuditSeverity.ERROR, AuditSeverity.WARNING)
                ]

                logger.error(
                    "Canary audit FAILED (%d policy violations).",
                    len(canary_result.violations),
                )
                for v in canary_result.violations:
                    logger.error("Violation: %s", v)

                return (False, combined_findings)

    def _apply_accepted_crate(self, crate: Crate):
        """Applies the payload of an accepted crate to the live repository."""
        logger.info(
            "Applying accepted crate '%s' to live system...",
            crate.path.name,
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
            self._copy_file(source_path, target_path)
            logger.debug("Applied '%s'", file_in_payload)

    def _write_result_manifest(self, crate_path: Path, status: str, details: Any):
        """Writes a result.yaml file into the processed crate directory."""
        result_content = {
            "status": status,
            "processed_at_utc": datetime.now(UTC).isoformat(),
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
        if final_path.exists():
            import time

            final_path = self.rejected_path / f"{crate_id}_{int(time.time())}"
        crate_path.rename(final_path)
        self._write_result_manifest(final_path, "rejected", details)
        reason_summary = (
            details
            if isinstance(details, str)
            else f"{len(details)} constitutional violations found."
        )
        logger.info("Moved to rejected. Reason: %s", reason_summary)
        log_details = {"crate_id": crate_id}
        if isinstance(details, str):
            log_details["reason"] = details
        else:
            log_details["violations"] = [finding.as_dict() for finding in details]
        action_logger.log_event("crate.processing.rejected", log_details)

    # ID: 0624a145-5cae-4e19-b80b-64173aa445d9
    async def process_pending_crates_async(self):
        """
        The main entry point for the service. It finds and processes all crates in the inbox.
        """
        logger.info("Starting new crate processing cycle...")
        valid_crates = self._scan_and_validate_inbox()
        if not valid_crates:
            logger.info("No valid crates found in the inbox. Cycle complete.")
            return
        logger.info("Found %d valid crate(s) to process.", len(valid_crates))
        for crate in valid_crates:
            crate_id = crate.path.name
            logger.info("Processing crate: %s", crate_id)
            try:
                processing_path = self.processing_path / crate_id
                crate.path.rename(processing_path)
                crate.path = processing_path
                logger.debug(
                    "Moved to processing: %s",
                    processing_path.relative_to(self.repo_root),
                )
                action_logger.log_event(
                    "crate.processing.started", {"crate_id": crate_id}
                )
                is_safe, findings = await self._run_canary_validation(crate)
                if is_safe:
                    self._apply_accepted_crate(crate)
                    final_path = self.accepted_path / crate.path.name
                    crate.path.rename(final_path)
                    self._write_result_manifest(
                        final_path,
                        "accepted",
                        "Canary audit passed and changes were applied.",
                    )
                    logger.info("Moved to accepted.")
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
                logger.error(
                    "Failed to process crate '%s': %s", crate_id, e, exc_info=True
                )
                self._move_crate_to_rejected(
                    crate.path, f"Internal processing error: {e}"
                )
                continue


# ID: a1c0b085-2426-4a2e-a637-c491f9c32dc1
async def process_crates():
    """High-level function to instantiate and run the service."""
    service = CrateProcessingService()
    await service.process_pending_crates_async()
