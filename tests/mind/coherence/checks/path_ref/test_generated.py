from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch


# ID: 87b8f524-965f-4618-92a0-18101b3b3359
def test_PathRefCheck_run():
    from mind.coherence.checks.path_ref import PathRefCheck

    repo_root = Path("/repo")
    content = "See `./src/missing.py` for details."

    check = PathRefCheck(repo_root)

    fake_doc = MagicMock(spec=Path)
    fake_doc.read_text.return_value = content

    # ID: 7815ffeb-d110-40a9-908a-6c52a431748d
    def fake_resolves(ref: str) -> bool:
        return False

    with (
        patch.object(check, "_governance_docs", return_value=[fake_doc]),
        patch("mind.coherence.checks.path_ref.document_status", return_value="active"),
        patch(
            "mind.coherence.checks.path_ref.law_relpath", return_value=".specs/doc.md"
        ),
        patch("mind.coherence.checks.path_ref._normalize_ref", side_effect=lambda r: r),
        patch.object(check, "_resolves", side_effect=fake_resolves),
    ):
        candidates = asyncio.run(check.run())

    # If construction left relation unset, ensure it is a valid value.
    assert isinstance(candidates, list)


from mind.coherence.checks.path_ref import PathRefCheck


# ID: f2237200-c4b3-495c-86e7-2f1029dd1474
async def test_PathRefCheck(tmp_path: Path) -> None:
    repo_root = tmp_path
    doc = repo_root / ".specs" / "governance" / "doc.md"
    doc.parent.mkdir(parents=True)
    doc.write_text(
        "See `.src/missing_module.py` for details.\n",
        encoding="utf-8",
    )

    check = PathRefCheck(repo_root)
    check._governance_docs = MagicMock(return_value=[doc])

    candidates = await check.run()

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.relation == "PATH_REF"
    assert len(candidate.documents) == 1
    assert ".specs/governance/doc.md" in candidate.documents[0]
    assert ".src/missing_module.py" in candidate.claim
    assert "does not exist" in candidate.claim
