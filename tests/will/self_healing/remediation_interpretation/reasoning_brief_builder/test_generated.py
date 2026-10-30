from __future__ import annotations

from unittest.mock import MagicMock, patch


# ID: dd824dc4-a652-4e0e-b24f-8653dfbb387a
def test_ReasoningBriefBuilder_build():
    from will.self_healing.remediation_interpretation.reasoning_brief_builder import (
        ReasoningBriefBuilder,
    )

    builder = ReasoningBriefBuilder()

    file_path = "src/foo/bar.py"
    file_role = MagicMock(name="file_role")
    normalized_findings = [MagicMock(name="finding1"), MagicMock(name="finding2")]
    file_context = {"some": "context"}
    responsibility_clusters = [MagicMock(name="cluster1")]
    candidate_strategies = [MagicMock(name="strat1"), MagicMock(name="strat2")]
    recommended_strategy = MagicMock(name="recommended")

    mock_constraints = MagicMock(name="constraints")
    mock_notes = MagicMock(name="architectural_notes")

    with (
        patch.object(
            ReasoningBriefBuilder, "_build_constraints", return_value=mock_constraints
        ) as m_constraints,
        patch.object(
            ReasoningBriefBuilder,
            "_build_architectural_notes",
            return_value=mock_notes,
        ) as m_notes,
        patch(
            "will.self_healing.remediation_interpretation.reasoning_brief_builder.ReasoningBrief"
        ) as m_brief_cls,
    ):
        result = builder.build(
            file_path=file_path,
            file_role=file_role,
            normalized_findings=normalized_findings,
            file_context=file_context,
            responsibility_clusters=responsibility_clusters,
            candidate_strategies=candidate_strategies,
            recommended_strategy=recommended_strategy,
        )

    m_constraints.assert_called_once_with(
        file_role=file_role,
        file_context=file_context,
        recommended_strategy=recommended_strategy,
    )
    m_notes.assert_called_once_with(
        file_path=file_path,
        file_role=file_role,
        normalized_findings=normalized_findings,
        file_context=file_context,
        responsibility_clusters=responsibility_clusters,
        recommended_strategy=recommended_strategy,
    )
    m_brief_cls.assert_called_once_with(
        file_path=file_path,
        file_role=file_role,
        findings=list(normalized_findings),
        responsibility_clusters=list(responsibility_clusters),
        candidate_strategies=list(candidate_strategies),
        recommended_strategy=recommended_strategy,
        constraints=mock_constraints,
        architectural_notes=mock_notes,
    )
    assert result is m_brief_cls.return_value
