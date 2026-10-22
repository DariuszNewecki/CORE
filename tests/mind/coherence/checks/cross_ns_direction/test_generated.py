from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


# ID: d52f7733-2089-457c-a53b-55879dd38e04
async def test_CrossNsDirectionCheck_run(tmp_path: Path) -> None:
    from mind.coherence.checks.cross_ns_direction import CrossNsDirectionCheck

    check = CrossNsDirectionCheck(tmp_path)

    manifest_dir = tmp_path / "governance"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "namespace_manifest.yaml"

    manifest_content = (
        "classifications:\n"
        "  - path: '.specs/foo/ADR-001.md'\n"
        "    governance_namespace: 'framework'\n"
        "  - path: 'src/project/thing.py'\n"
        "    governance_namespace: 'project::core'\n"
    )
    manifest_path.write_text(manifest_content, encoding="utf-8")

    fw_dir = tmp_path / ".specs" / "foo"
    fw_dir.mkdir(parents=True, exist_ok=True)
    fw_file = fw_dir / "ADR-001.md"
    fw_file.write_text(
        "**Status:** Accepted\n\nSee src/project/thing.py for details.\n",
        encoding="utf-8",
    )

    candidate = MagicMock()

    with (
        patch(
            "mind.coherence.checks.cross_ns_direction.intent_root_for",
            return_value=tmp_path,
        ),
        patch(
            "mind.coherence.checks.cross_ns_direction._extract_project_path_refs",
            return_value=["src/project/thing.py"],
        ),
        patch(
            "mind.coherence.checks.cross_ns_direction.CoherenceCandidate",
            return_value=candidate,
        ) as mock_candidate_cls,
    ):
        result = await check.run()

    assert result == [candidate]
    mock_candidate_cls.assert_called_once()
    kwargs = mock_candidate_cls.call_args.kwargs
    assert kwargs["documents"] == [".specs/foo/ADR-001.md", "src/project/thing.py"]


import asyncio

from mind.coherence.checks.cross_ns_direction import CrossNsDirectionCheck


# ID: e1eccdeb-f3eb-4159-8115-9cd78676d01a
def test_CrossNsDirectionCheck(tmp_path: Path) -> None:
    # Prepare a fake repo root with a namespace manifest and a framework spec.
    repo_root = tmp_path / "repo"
    intent_root = repo_root / "intent"
    governance_dir = intent_root / "governance"
    governance_dir.mkdir(parents=True)

    manifest_path = governance_dir / "namespace_manifest.yaml"
    manifest_path.write_text(
        "classifications:\n"
        "  - path: .specs/features/foo/spec.md\n"
        "    governance_namespace: framework\n"
        "  - path: src/project/core/thing.py\n"
        "    governance_namespace: project::core\n",
        encoding="utf-8",
    )

    fw_spec_path = repo_root / ".specs" / "features" / "foo" / "spec.md"
    fw_spec_path.parent.mkdir(parents=True)
    fw_spec_path.write_text(
        "This references src/project/core/thing.py directly.",
        encoding="utf-8",
    )

    check = CrossNsDirectionCheck(repo_root)

    with (
        patch(
            "mind.coherence.checks.cross_ns_direction.intent_root_for",
            return_value=intent_root,
        ),
        patch(
            "mind.coherence.checks.cross_ns_direction._extract_project_path_refs",
            return_value=["src/project/core/thing.py"],
        ),
    ):
        candidates = asyncio.run(check.run())

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.relation == "CROSS_NS_DIRECTION"
    assert candidate.documents == [
        ".specs/features/foo/spec.md",
        "src/project/core/thing.py",
    ]
