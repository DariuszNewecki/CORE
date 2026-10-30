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


from types import SimpleNamespace

from will.self_healing.remediation_interpretation.reasoning_brief_builder import (
    ReasoningBriefBuilder,
)


# ID: 91b9b34e-9ea1-4655-a0a6-c3614c46abc8
def test_ReasoningBriefBuilder():
    builder = ReasoningBriefBuilder()

    file_role = SimpleNamespace(layer="runtime", role_id="worker.sensor")
    finding = SimpleNamespace(rule_id="RULE-1")
    cluster = SimpleNamespace(name="cluster-a")
    strategy = SimpleNamespace(
        strategy_id="S1",
        summary="Split responsibilities",
        preserves_contract=True,
        evidence=["evidence-1", "evidence-2"],
    )

    file_context = {
        "role_constraints": ["Constraint from role context"],
        "file_metrics": {"line_count": 120, "distinct_rule_count": 2},
        "violation_summary": {"rules": {"RULE-1": 3, "RULE-2": 1}},
        "structural_signals": ["signal-a", "signal-b"],
    }

    brief = builder.build(
        file_path="src/foo.py",
        file_role=file_role,
        normalized_findings=[finding],
        file_context=file_context,
        responsibility_clusters=[cluster],
        candidate_strategies=[strategy],
        recommended_strategy=strategy,
    )

    assert brief.file_path == "src/foo.py"
    assert brief.file_role is file_role
    assert brief.findings == [finding]
    assert brief.responsibility_clusters == [cluster]
    assert brief.candidate_strategies == [strategy]
    assert brief.recommended_strategy is strategy

    # Constraints include context-provided, layer, role, contract, and worker.sensor notes.
    assert "Constraint from role context" in brief.constraints
    assert any("'runtime' constitutional layer" in c for c in brief.constraints)
    assert any("'worker.sensor'" in c for c in brief.constraints)
    assert any("Preserve externally visible behavior" in c for c in brief.constraints)
    assert any("mutation" in c for c in brief.constraints)

    # Architectural notes include role, size, scope, dominant rule, clusters, signals, strategy.
    assert any(
        "src/foo.py" in n and "worker.sensor" in n for n in brief.architectural_notes
    )
    assert any("120 lines" in n for n in brief.architectural_notes)
    assert any("1 finding(s)" in n for n in brief.architectural_notes)
    assert any("RULE-1" in n and "Dominant" in n for n in brief.architectural_notes)
    assert any("cluster-a" in n for n in brief.architectural_notes)
    assert "signal-a" in brief.architectural_notes
    assert "signal-b" in brief.architectural_notes
    assert any(
        "S1" in n and "Split responsibilities" in n for n in brief.architectural_notes
    )
    assert any("evidence-1" in n for n in brief.architectural_notes)
    assert any("evidence-2" in n for n in brief.architectural_notes)

    # Dedupe preserved: no duplicate entries.
    assert len(brief.constraints) == len(set(brief.constraints))
    assert len(brief.architectural_notes) == len(set(brief.architectural_notes))
