# src/shared/self_healing/remediation_interpretation/service.py

from __future__ import annotations

from typing import Any

from shared.self_healing.remediation_interpretation.file_context_assembler import (
    FileContextAssembler,
)
from shared.self_healing.remediation_interpretation.file_role_detector import (
    FileRoleDetector,
)
from shared.self_healing.remediation_interpretation.finding_normalizer import (
    FindingNormalizer,
)
from shared.self_healing.remediation_interpretation.models import ReasoningBrief
from shared.self_healing.remediation_interpretation.reasoning_brief_builder import (
    ReasoningBriefBuilder,
)
from shared.self_healing.remediation_interpretation.responsibility_extractor import (
    ResponsibilityExtractor,
)
from shared.self_healing.remediation_interpretation.strategy_catalog import (
    StrategyCatalog,
)
from shared.self_healing.remediation_interpretation.strategy_selector import (
    StrategySelector,
)


# ID: bd0d2b1f-692d-4693-801e-aba8a4c5f514
class RemediationInterpretationError(Exception):
    """
    Raised when the interpretation pipeline cannot produce a valid brief.

    Callers MUST treat this as an indeterminate outcome and halt any
    execution-phase actions. Do not catch and continue with a fallback —
    CORE-Evidence-as-Input §6: indeterminate outcomes block progression.
    """


# ID: 5d3c9f29-5d7a-43b7-92a2-5d3f2fd0f6a1
class RemediationInterpretationService:
    """
    Deterministic-first remediation architectural context builder.

    This service wires the bounded interpretation steps into a single
    entrypoint that the remediator calls during the RUNTIME planning phase,
    before any execution-phase actions occur.

    Output is evidence: a deterministic description of the file's detected
    role, responsibility clusters, and candidate strategies. This is NOT
    authority. It does not define what must be done. It informs planning.

    Flow:
    1. normalize findings
    2. detect file role
    3. assemble file context
    4. extract responsibility clusters
    5. rank strategies
    6. choose recommended strategy (may be None if confidence is low)
    7. build ReasoningBrief

    Design constraints:
    - deterministic only
    - no LLM
    - no file I/O beyond the already-provided source_code input
    - no blackboard/database access
    - no repo traversal

    Failure contract:
    - Raises RemediationInterpretationError on any internal failure.
    - Never silently degrades or returns partial output.
    - Callers are responsible for handling indeterminate outcomes.
    """

    def __init__(
        self,
        finding_normalizer: FindingNormalizer | None = None,
        file_role_detector: FileRoleDetector | None = None,
        file_context_assembler: FileContextAssembler | None = None,
        responsibility_extractor: ResponsibilityExtractor | None = None,
        strategy_catalog: StrategyCatalog | None = None,
        strategy_selector: StrategySelector | None = None,
        reasoning_brief_builder: ReasoningBriefBuilder | None = None,
    ) -> None:
        self._finding_normalizer = finding_normalizer or FindingNormalizer()
        self._file_role_detector = file_role_detector or FileRoleDetector()
        self._file_context_assembler = file_context_assembler or FileContextAssembler()
        self._responsibility_extractor = (
            responsibility_extractor or ResponsibilityExtractor()
        )
        self._strategy_catalog = strategy_catalog or StrategyCatalog()
        self._strategy_selector = strategy_selector or StrategySelector(
            strategy_catalog=self._strategy_catalog
        )
        self._reasoning_brief_builder = (
            reasoning_brief_builder or ReasoningBriefBuilder()
        )

    # ID: 2b4a7e90-7b0a-40db-a4e4-6f8eb78d5b9c
    def build_reasoning_brief(
        self,
        file_path: str,
        source_code: str,
        findings: list[dict[str, Any]],
    ) -> ReasoningBrief:
        """
        Build a complete ReasoningBrief from claimed blackboard findings and
        current source code for one file.

        Raises:
            RemediationInterpretationError: if any pipeline step fails.
                The caller must treat this as an indeterminate outcome.
        """
        try:
            normalized_findings = self._finding_normalizer.normalize(findings)
        except Exception as exc:
            raise RemediationInterpretationError(
                f"FindingNormalizer failed for '{file_path}': {exc}"
            ) from exc

        try:
            file_role = self._file_role_detector.detect(
                file_path=file_path,
                source_code=source_code,
                findings=normalized_findings,
            )
        except Exception as exc:
            raise RemediationInterpretationError(
                f"FileRoleDetector failed for '{file_path}': {exc}"
            ) from exc

        try:
            file_context = self._file_context_assembler.assemble(
                file_path=file_path,
                source_code=source_code,
                findings=normalized_findings,
                file_role=file_role,
            )
        except Exception as exc:
            raise RemediationInterpretationError(
                f"FileContextAssembler failed for '{file_path}': {exc}"
            ) from exc

        try:
            responsibility_clusters = self._responsibility_extractor.extract(
                file_context
            )
        except Exception as exc:
            raise RemediationInterpretationError(
                f"ResponsibilityExtractor failed for '{file_path}': {exc}"
            ) from exc

        try:
            candidate_strategies = self._strategy_selector.select(
                file_role=file_role,
                file_context=file_context,
                responsibility_clusters=responsibility_clusters,
            )
            recommended_strategy = self._strategy_selector.choose_recommended(
                candidate_strategies
            )
        except Exception as exc:
            raise RemediationInterpretationError(
                f"StrategySelector failed for '{file_path}': {exc}"
            ) from exc

        try:
            return self._reasoning_brief_builder.build(
                file_path=file_path,
                file_role=file_role,
                normalized_findings=normalized_findings,
                file_context=file_context,
                responsibility_clusters=responsibility_clusters,
                candidate_strategies=candidate_strategies,
                recommended_strategy=recommended_strategy,
            )
        except Exception as exc:
            raise RemediationInterpretationError(
                f"ReasoningBriefBuilder failed for '{file_path}': {exc}"
            ) from exc

    # ID: 7aa9cfde-e8ac-4e14-bd33-e6df31d5b2d1
    def build_reasoning_brief_dict(
        self,
        file_path: str,
        source_code: str,
        findings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Convenience wrapper returning a JSON-serializable brief.

        Raises:
            RemediationInterpretationError: propagated from build_reasoning_brief.
        """
        brief = self.build_reasoning_brief(
            file_path=file_path,
            source_code=source_code,
            findings=findings,
        )
        return brief.to_dict()
