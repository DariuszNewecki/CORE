# src/will/phases/code_generation/artifact_saver.py

"""
Saves generated code artifacts and reports.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.models.execution_models import DetailedPlanStep


logger = getLogger(__name__)


# ID: 065f8542-cdf1-466f-aa69-b0b2e5b1e4a6
class ArtifactSaver:
    """Saves generated code artifacts and metadata reports."""

    def __init__(self, file_handler: FileHandler):
        self.file_handler = file_handler

    # ID: 60ccdf98-685d-4b9e-b3c1-f7364515255a
    def save_generation_artifacts(
        self, steps: list[DetailedPlanStep], work_dir_rel: str, goal: str
    ) -> None:
        """
        Save all generated code to work directory for review and debugging.

        Args:
            steps: List of detailed plan steps with generated code
            work_dir_rel: Relative path to work directory
            goal: Original refactoring goal

        Constitutional Compliance:
            - governance.artifact_mutation.traceable: Uses FileHandler for all writes
            - Creates both code files and metadata report
        """
        report_data = self._build_report_data(steps, goal)

        # Save individual code artifacts
        for i, step in enumerate(steps, 1):
            if step.params.get("code"):
                self._save_code_artifact(
                    step, i, work_dir_rel, report_data["steps"][i - 1]
                )

        # Save generation report
        self._save_report(report_data, work_dir_rel)

        # Log summary
        self._log_summary(report_data, work_dir_rel)

    def _build_report_data(self, steps: list[DetailedPlanStep], goal: str) -> dict:
        """Build metadata report for generation session."""
        return {
            "goal": goal,
            "timestamp": datetime.now().isoformat(),
            "total_steps": len(steps),
            "successful": sum(
                1 for s in steps if not s.metadata.get("generation_failed")
            ),
            "failed": sum(1 for s in steps if s.metadata.get("generation_failed")),
            "steps": [self._build_step_info(s, i) for i, s in enumerate(steps, 1)],
        }

    @staticmethod
    def _build_step_info(step: DetailedPlanStep, step_number: int) -> dict:
        """Build metadata for a single step."""
        return {
            "number": step_number,
            "action": step.action,
            "description": step.description,
            "success": not step.metadata.get("generation_failed"),
        }

    def _save_code_artifact(
        self,
        step: DetailedPlanStep,
        step_number: int,
        work_dir_rel: str,
        step_info: dict,
    ) -> None:
        """Save a single code artifact."""
        code = step.params["code"]

        # Generate safe filename
        artifact_filename = self._generate_artifact_filename(step, step_number)
        artifact_rel_path = f"{work_dir_rel}/{artifact_filename}"

        # CONSTITUTIONAL: Use FileHandler for write
        self.file_handler.write_runtime_text(artifact_rel_path, code)

        # Update step info
        target_path = step.params.get("file_path", f"unknown_{step_number}")
        step_info["target_file"] = target_path
        step_info["artifact_file"] = artifact_filename
        step_info["code_size_bytes"] = len(code)

        # Log result
        if not step.metadata.get("generation_failed"):
            logger.info("   → Saved: %s", artifact_filename)
        else:
            step_info["error"] = step.metadata.get("error", "Unknown error")
            logger.warning("   → Saved (FAILED): %s", artifact_filename)

    @staticmethod
    def _generate_artifact_filename(step: DetailedPlanStep, step_number: int) -> str:
        """Generate safe filename for artifact."""
        action_slug = step.action.replace(".", "_")
        target_path = step.params.get("file_path", f"unknown_{step_number}")
        target_filename = Path(target_path).name

        return f"step_{step_number:02d}_{action_slug}_{target_filename}"

    def _save_report(self, report_data: dict, work_dir_rel: str) -> None:
        """Save generation report JSON."""
        report_rel_path = f"{work_dir_rel}/generation_report.json"
        report_json = json.dumps(report_data, indent=2, ensure_ascii=False)

        # CONSTITUTIONAL: Use FileHandler for report write
        self.file_handler.write_runtime_text(report_rel_path, report_json)

    @staticmethod
    def _log_summary(report_data: dict, work_dir_rel: str) -> None:
        """Log summary of generation session."""
        logger.info(
            "📊 Code Generation Summary: %d/%d steps successful",
            report_data["successful"],
            report_data["total_steps"],
        )
        logger.info("📁 Review generated code at: %s", work_dir_rel)
        logger.info("💡 TIP: Inspect artifacts before using --write to apply changes")
