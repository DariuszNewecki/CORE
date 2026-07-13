# src/body/services/crate_processing_service.py

"""
CrateProcessingService - The Constitutional Judge

Orchestrates the lifecycle of an Intent Crate: validation, canary testing,
and final reporting. This service ensures that proposed changes are
proven safe in a sandbox before being accepted into the Body.

A3 Methodology:
- Supports surgical validation by Crate ID for iterative retry loops.
- Enforces Canary thresholds defined in operations.json.
- Headless execution for background automation.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from body.crate_processing.canary_executor import CanaryExecutor, CanaryResult
from body.infrastructure.storage.file_handler import FileHandler
from body.introspection.knowledge_graph_service import KnowledgeGraphBuilder
from mind.governance.audit_context import AuditorContext
from mind.governance.auditor import ConstitutionalAuditor
from shared.action_logger import action_logger
from shared.context import CoreContext
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity
from shared.path_resolver import PathResolver


logger = getLogger(__name__)


@dataclass
# ID: 96730f37-f39b-4241-9409-8c4664520beb
class Crate:
    """A simple data class representing a validated Intent Crate."""

    path: Path
    manifest: dict[str, Any]


# ID: 26ed379a-875e-4df0-9596-f053baadca66
class CrateProcessingService:
    """
    Validates and processes Intent Crates via Canary sandboxing.
    """

    def __init__(self, core_context: CoreContext):
        """Initializes service using PathResolver (SSOT)."""
        self.core_context = core_context
        self.repo_root = core_context.git_service.repo_path.resolve()
        self._fh = core_context.file_handler or FileHandler(str(self.repo_root))
        self._paths = PathResolver.from_repo(
            repo_root=self.repo_root, intent_root=self.repo_root / ".intent"
        )

        # Use canonical paths from PathResolver
        self.inbox_path = self._paths.workflows_dir / "crates" / "inbox"
        self.processing_path = self._paths.workflows_dir / "crates" / "processing"
        self.accepted_path = self._paths.workflows_dir / "crates" / "accepted"
        self.rejected_path = self._paths.workflows_dir / "crates" / "rejected"

        # Initialize Logic components
        try:
            from shared.infrastructure.intent.intent_repository import (
                get_intent_repository,
            )

            intent_repo = get_intent_repository()
            ops_policy = intent_repo.load_policy("policies/operations")
            self.canary_config = ops_policy.get("canary", {"enabled": True})
        except Exception:
            self.canary_config = {"enabled": True}

        self.canary_executor = CanaryExecutor(self.canary_config)

        try:
            from shared.infrastructure.intent.intent_repository import (
                get_intent_repository,
            )

            intent_repo = get_intent_repository()
            self.crate_schema = intent_repo.load_document(
                self._paths.intent_root
                / "schemas"
                / "constitutional"
                / "intent_crate.schema.json"
            )
        except Exception:
            # Fallback to minimal schema
            self.crate_schema = {"type": "object"}

    # ID: 154f8a2c-9a4d-4cb0-8172-3334d7bd05b8
    async def validate_crate_by_id(
        self, crate_id: str
    ) -> tuple[bool, list[AuditFinding]]:
        """
        Surgical validation for a specific crate.
        Used by the Orchestrator to drive the A3 retry loop.
        """
        crate_path = self.inbox_path / crate_id
        if not crate_path.exists():
            logger.error("Crate %s not found in inbox.", crate_id)
            return False, [
                AuditFinding(
                    check_id="infra.crate_missing",
                    severity=AuditSeverity.BLOCK,
                    message=f"Crate {crate_id} missing from inbox",
                    file_path="none",
                )
            ]

        try:
            # 1. Load and validate manifest structure
            manifest_path = crate_path / "manifest.yaml"
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            jsonschema.validate(instance=manifest, schema=self.crate_schema)

            crate_obj = Crate(path=crate_path, manifest=manifest)

            # 2. Run the Sandbox Trial
            return await self._run_canary_validation(crate_obj)

        except Exception as e:
            logger.error("Crate %s failed structural validation: %s", crate_id, e)
            return False, [
                AuditFinding(
                    check_id="infra.crate_invalid",
                    severity=AuditSeverity.BLOCK,
                    message=str(e),
                    file_path="manifest.yaml",
                )
            ]

    async def _run_canary_validation(
        self, crate: Crate
    ) -> tuple[bool, list[AuditFinding]]:
        """
        Creates a temporary environment, applies crate changes, and runs a full audit.
        """
        # Create canary sandbox in work/ directory (within REPO_PATH)
        canary_id = f"sandbox_{crate.manifest.get('crate_id')}"
        canary_repo_path = self.repo_root / "work" / "canary" / canary_id

        try:
            # Clean any previous sandbox with same ID
            if canary_repo_path.exists():
                shutil.rmtree(canary_repo_path, ignore_errors=True)

            canary_repo_path.mkdir(parents=True, exist_ok=True)

            logger.info("Created Canary Sandbox at %s", canary_repo_path)

            # A) Snapshot the system (exclude runtime noise)
            exclude_dirs = {"var", ".git", "__pycache__", ".venv", "work", "reports"}

            for item in self.repo_root.iterdir():
                if item.name in exclude_dirs:
                    continue

                dst = canary_repo_path / item.name
                try:
                    if item.is_symlink():
                        # copytree's symlinks=True only preserves symlinks it
                        # encounters *inside* a copied tree — passed as `src`
                        # itself, a symlinked dir is scanned via os.scandir()
                        # and still fully dereferenced. Recreate it directly.
                        dst.symlink_to(item.readlink())
                    elif item.is_dir():
                        shutil.copytree(
                            item, dst, symlinks=True, ignore_dangling_symlinks=True
                        )
                    else:
                        shutil.copy2(item, dst)
                except Exception as e:
                    logger.warning("Failed to copy %s: %s", item.name, e)

            # B) Apply the "Blueprint" (Payload)
            payload_files = crate.manifest.get("payload_files", [])
            for rel_file in payload_files:
                src = crate.path / rel_file
                dst = canary_repo_path / rel_file
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

            # C) The Trial: Canary is under repo_root, so path-relative tooling works

            # Build knowledge graph in sandbox
            kg_builder = KnowledgeGraphBuilder(canary_repo_path)
            kg_builder.build()

            # Create auditor context - canary is within repo_root
            auditor_ctx = AuditorContext(canary_repo_path)
            auditor = ConstitutionalAuditor(auditor_ctx)

            # Run audit
            audit_result = await auditor.run_full_audit_async()
            raw_findings = (
                audit_result.get("findings", [])
                if isinstance(audit_result, dict)
                else audit_result
            )
            all_findings = [
                AuditFinding(**f) if isinstance(f, dict) else f for f in raw_findings
            ]

            # D) The Verdict
            metrics = self.canary_executor.derive_metrics_from_audit(all_findings)
            canary_result: CanaryResult = self.canary_executor.enforce(metrics)

            if canary_result.passed:
                logger.info(
                    "✅ Canary Trial PASSED for %s", crate.manifest.get("crate_id")
                )
                return True, []

            logger.warning(
                "❌ Canary Trial FAILED for %s", crate.manifest.get("crate_id")
            )
            return False, all_findings

        except Exception as e:
            logger.error("Canary trial crashed: %s", e, exc_info=True)
            return False, [
                AuditFinding(
                    check_id="infra.canary_crash",
                    severity=AuditSeverity.BLOCK,
                    message=f"Canary trial infrastructure error: {e}",
                    file_path="canary_sandbox",
                )
            ]
        finally:
            # Clean up sandbox
            if canary_repo_path.exists():
                shutil.rmtree(canary_repo_path, ignore_errors=True)

    # ID: 729b80a5-bc1b-484d-aa22-d27356481cbc
    async def apply_and_finalize_crate(self, crate_id: str) -> None:
        """Apply crate payload to production code and delete it from inbox.

        Inbox is a transit zone, not an archive. After the governed writes
        succeed the crate directory is removed — callers should not re-run
        this method on the same crate_id.
        """
        crate_path = self.inbox_path / crate_id
        manifest_path = crate_path / "manifest.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

        logger.info("Applying accepted crate '%s' to production code...", crate_id)

        for rel_file in manifest.get("payload_files", []):
            source = crate_path / rel_file
            self._fh.write_runtime_text(rel_file, source.read_text(encoding="utf-8"))

        self._fh.remove_tree(self._to_repo_rel(crate_path))
        action_logger.log_event("crate.accepted", {"crate_id": crate_id})

    # ID: b2c2ffe3-5df4-406e-9003-435f10abb134
    def purge_stale_inbox_crates(self, ttl_days: int = 7) -> list[str]:
        """Delete inbox crate directories older than ttl_days.

        Age is measured against manifest.yaml mtime; falls back to the
        directory mtime when the manifest is absent. Returns the list of
        purged crate ids.
        """
        if not self.inbox_path.exists():
            return []

        now = datetime.now(UTC).timestamp()
        purged: list[str] = []
        for crate_dir in self.inbox_path.iterdir():
            if not crate_dir.is_dir():
                continue
            manifest = crate_dir / "manifest.yaml"
            ref = manifest if manifest.exists() else crate_dir
            age_days = (now - ref.stat().st_mtime) / 86400
            if age_days >= ttl_days:
                self._fh.remove_tree(self._to_repo_rel(crate_dir))
                purged.append(crate_dir.name)
                logger.info(
                    "Purged stale inbox crate %s (age %.1f days)",
                    crate_dir.name,
                    age_days,
                )
        return purged

    def _to_repo_rel(self, p: Path) -> str:
        """Helper to ensure paths are FileHandler compatible."""
        try:
            return str(p.relative_to(self.repo_root))
        except ValueError:
            return str(p)
