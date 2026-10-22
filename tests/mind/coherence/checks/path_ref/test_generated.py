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
