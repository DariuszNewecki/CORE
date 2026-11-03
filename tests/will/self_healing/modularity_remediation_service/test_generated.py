from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from will.self_healing.modularity_remediation_service import (
    ModularityRemediationService,
)


# ID: 0f2d8435-cf71-4d7f-96bd-dc2131f110d8
def test_ModularityRemediationService_remediate_batch():
    # --- context / dependencies ---
    repo_root = Path("/tmp/repo")
    context = MagicMock()
    context.git_service.repo_path = repo_root
    context.file_handler = MagicMock()

    # Construct the service with mocked dependencies patched at module level.
    with (
        patch("will.self_healing.modularity_remediation_service.ModularityChecker"),
        patch(
            "will.self_healing.modularity_remediation_service.EnforcementMappingLoader"
        ),
        patch("will.self_healing.modularity_remediation_service.intent_root_for"),
        patch.object(
            ModularityRemediationService,
            "_get_constitutional_threshold",
            return_value=10.0,
        ),
    ):
        service = ModularityRemediationService(context)

    file_path = repo_root / "pkg" / "module.py"
    service._get_source_files = MagicMock(return_value=[file_path])
    service.threshold = 10.0

    # Checker returns one violation with score above threshold.
    finding = {"details": {"total_score": 42.0}}
    service.checker = MagicMock()
    service.checker.check_refactor_score.return_value = [finding]

    # file reads
    file_mock = MagicMock()
    file_mock.read_text.return_value = "original code"
    file_mock.name = "module.py"

    # relative_to should work on real Path; use a fake path wrapper.
    rel_path_str = "pkg/module.py"

    # Patch Path.read_text and relative_to behavior via a fake path object.
    fake_path = MagicMock(spec=Path)
    fake_path.read_text.return_value = "original code"
    fake_path.name = "module.py"
    fake_path.relative_to.return_value = Path(rel_path_str)
    service._get_source_files.return_value = [fake_path]

    # develop_from_goal is imported locally in the method; patch at defining module.
    develop_mock = AsyncMock(return_value=(True, "refactor applied"))

    conservation_verdict = MagicMock()
    conservation_verdict.ok = True
    conservation_verdict.data = {"ratio": 1.0}
    validator_mock = MagicMock()
    validator_mock.evaluate = AsyncMock(return_value=conservation_verdict)

    with (
        patch(
            "will.self_healing.modularity_remediation_service.develop_from_goal",
            develop_mock,
        ),
        patch(
            "will.self_healing.modularity_remediation_service.LogicConservationValidator",
            return_value=validator_mock,
        ),
    ):
        import asyncio

        results = asyncio.run(service.remediate_batch(limit=5, write=False))

    assert len(results) == 1
    assert results[0]["file"] == rel_path_str
    assert results[0]["original_score"] == 42.0
    assert results[0]["success"] is True
    assert results[0]["message"] == "refactor applied"

    service.checker.check_refactor_score.assert_called_once()
    develop_mock.assert_awaited_once()
    # write=False => conservation gate not evaluated.
    validator_mock.evaluate.assert_not_awaited()
