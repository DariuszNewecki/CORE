# src/features/self_healing/single_file_remediation.py
# ID: 0c2cfe25-2da0-4aaa-8927-f1312c7a3825

"""
Enhanced single-file test generation with comprehensive context analysis.

This service uses the V2 Adaptive infrastructure to gather deep context
before generating tests, preventing misunderstandings and improving quality.

LEGACY ELIMINATION: Removed SingleFileRemediationService (V1) per Roadmap.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from body.self_healing.coverage_analyzer import CoverageAnalyzer
from body.self_healing.test_generator import EnhancedTestGenerator
from mind.governance.audit_context import AuditorContext
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)


# ID: 840acb0f-7ec4-4f61-bc69-62c9b2fda26d
class EnhancedSingleFileRemediationService:
    """
    Generates tests for a single file using comprehensive V2 context analysis.
    """

    def __init__(
        self,
        cognitive_service: CognitiveService,
        auditor_context: AuditorContext,
        file_path: Path,
        file_handler: FileHandler,
        repo_root: Path,
        max_complexity: str = "SIMPLE",
    ):
        self.cognitive = cognitive_service
        self.auditor = auditor_context
        self.target_file = file_path
        self.file_handler = file_handler
        self.repo_root = repo_root
        self.analyzer = CoverageAnalyzer(repo_path=self.repo_root)

        # This generator owns the V2 adaptive retry logic
        self.generator = EnhancedTestGenerator(
            cognitive_service,
            auditor_context,
            file_handler,
            repo_root,
            use_iterative_fixing=True,  # Enabled for V2 alignment
            max_complexity=max_complexity,
        )

    # ID: b4e19ec3-a8b4-40d8-ae9d-2c8972f5199c
    async def remediate(self) -> dict[str, Any]:
        """
        Generate comprehensive tests for the target file using V2 patterns.
        """
        logger.info("V2 Single-File Remediation: %s", self.target_file)

        # Path normalization
        if str(self.target_file).startswith(str(self.repo_root)):
            relative_path = self.target_file.relative_to(self.repo_root)
        else:
            relative_path = self.target_file

        target_str = str(relative_path)

        # Derive module path for imports
        if "src/" in target_str:
            module_part = target_str.split("src/", 1)[1]
        else:
            module_part = target_str

        module_name = module_part.replace("/", ".").replace(".py", "")

        # Calculate test destination
        module_parts = module_name.split(".")
        if len(module_parts) > 1:
            test_dir = Path("tests") / module_parts[0]
        else:
            test_dir = Path("tests")

        test_filename = f"test_{Path(module_part).stem}.py"
        test_file = test_dir / test_filename

        goal = (
            f"Create comprehensive unit tests for {module_name} with V2 Adaptive loop."
        )

        try:
            # Execute V2 Adaptive Generation
            result = await self.generator.generate_test(
                module_path=str(relative_path),
                test_file=str(test_file),
                goal=goal,
                target_coverage=75.0,
                file_handler=self.file_handler,
                repo_root=self.repo_root,
            )

            if result.get("status") == "success":
                final_coverage = self._measure_final_coverage(str(relative_path))
                return {
                    "status": "completed",
                    "file": str(self.target_file),
                    "test_file": str(test_file),
                    "final_coverage": final_coverage,
                    "metrics": result.get("metrics", {}),
                }

            return {
                "status": "failed",
                "file": str(self.target_file),
                "error": result.get("error", "Generation failed"),
                "violations": result.get("violations", []),
            }

        except Exception as exc:
            logger.error("V2 Remediation crashed for %s: %s", self.target_file, exc)
            return {"status": "error", "error": str(exc)}

    def _measure_final_coverage(self, module_rel_path: str) -> float | None:
        try:
            coverage_data = self.analyzer.get_module_coverage()
            return coverage_data.get(module_rel_path) if coverage_data else None
        except Exception:
            return None
