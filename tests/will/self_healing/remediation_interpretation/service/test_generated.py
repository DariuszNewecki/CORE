from __future__ import annotations

from unittest.mock import MagicMock

from will.self_healing.remediation_interpretation.service import (
    RemediationInterpretationService,
)


# ID: 097db9d1-c8bf-4e6c-96e7-bcb12763db17
def test_RemediationInterpretationService_build_reasoning_brief_dict() -> None:
    service = RemediationInterpretationService()

    expected_dict = {"brief": "value", "nested": {"k": 1}}
    mock_brief = MagicMock()
    mock_brief.to_dict.return_value = expected_dict

    service.build_reasoning_brief = MagicMock(return_value=mock_brief)

    file_path = "src/example.py"
    source_code = "def foo():\n    return 1\n"
    findings = [{"code": "E001", "message": "issue"}]

    result = service.build_reasoning_brief_dict(
        file_path=file_path,
        source_code=source_code,
        findings=findings,
    )

    service.build_reasoning_brief.assert_called_once_with(
        file_path=file_path,
        source_code=source_code,
        findings=findings,
    )
    mock_brief.to_dict.assert_called_once_with()
    assert result == expected_dict





# ID: d52c592b-7084-4066-aec3-5ce10a812440
def test_RemediationInterpretationService_build_reasoning_brief():
    normalized_findings = [{"id": "f1"}]
    file_role = MagicMock(name="file_role")
    file_context = MagicMock(name="file_context")
    responsibility_clusters = MagicMock(name="responsibility_clusters")
    candidate_strategies = MagicMock(name="candidate_strategies")
    recommended_strategy = MagicMock(name="recommended_strategy")
    reasoning_brief = MagicMock(name="reasoning_brief")

    finding_normalizer = MagicMock()
    finding_normalizer.normalize.return_value = normalized_findings

    file_role_detector = MagicMock()
    file_role_detector.detect.return_value = file_role

    file_context_assembler = MagicMock()
    file_context_assembler.assemble.return_value = file_context

    responsibility_extractor = MagicMock()
    responsibility_extractor.extract.return_value = responsibility_clusters

    strategy_catalog = MagicMock()
    strategy_selector = MagicMock()
    strategy_selector.select.return_value = candidate_strategies
    strategy_selector.choose_recommended.return_value = recommended_strategy

    reasoning_brief_builder = MagicMock()
    reasoning_brief_builder.build.return_value = reasoning_brief

    service = RemediationInterpretationService(
        finding_normalizer=finding_normalizer,
        file_role_detector=file_role_detector,
        file_context_assembler=file_context_assembler,
        responsibility_extractor=responsibility_extractor,
        strategy_catalog=strategy_catalog,
        strategy_selector=strategy_selector,
        reasoning_brief_builder=reasoning_brief_builder,
    )

    file_path = "src/example.py"
    source_code = "def foo():\n    return 1\n"
    findings = [{"id": "f1"}]

    result = service.build_reasoning_brief(
        file_path=file_path,
        source_code=source_code,
        findings=findings,
    )

    assert result is reasoning_brief

    finding_normalizer.normalize.assert_called_once_with(findings)
    file_role_detector.detect.assert_called_once_with(
        file_path=file_path,
        source_code=source_code,
        findings=normalized_findings,
    )
    file_context_assembler.assemble.assert_called_once_with(
        file_path=file_path,
        source_code=source_code,
        findings=normalized_findings,
        file_role=file_role,
    )
    responsibility_extractor.extract.assert_called_once_with(file_context)
    strategy_selector.select.assert_called_once_with(
        file_role=file_role,
        file_context=file_context,
        responsibility_clusters=responsibility_clusters,
    )
    strategy_selector.choose_recommended.assert_called_once_with(candidate_strategies)
    reasoning_brief_builder.build.assert_called_once_with(
        file_path=file_path,
        file_role=file_role,
        normalized_findings=normalized_findings,
        file_context=file_context,
        responsibility_clusters=responsibility_clusters,
        candidate_strategies=candidate_strategies,
        recommended_strategy=recommended_strategy,
    )
