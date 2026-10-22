from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch


# ID: 106df5c8-3a8d-4f8d-84d1-c525e120abd9
def test_Row3CitationCheck_run():
    import mind.coherence.checks.row3_citation as mod

    # Build a fake paper file under a temporary repo root.
    tmp = tempfile.mkdtemp()
    repo_root = Path(tmp)
    papers_dir = repo_root / "specs" / "papers"
    papers_dir.mkdir(parents=True)
    paper_file = papers_dir / "paper.md"
    section_text = (
        "# Some Title\n\n"
        "## Enforcement\n\n"
        "This MUST be enforced somehow but cites nothing.\n"
    )
    paper_file.write_text(section_text, encoding="utf-8")

    # Mock register with a marker-pattern and no aspirational markers.
    register = MagicMock()
    register.marker_pattern = mod.re.compile(r"\bMUST\b")
    register.aspirational_markers = []

    check = mod.Row3CitationCheck(repo_root, register)
    check.relation = MagicMock()

    # Fake intent repository returning a spec_markdown artifact type.
    fake_repo = MagicMock()
    artifact = MagicMock()
    artifact.content = {"discovery": ["specs/papers/**/*.md"]}
    fake_repo.get_artifact_type.return_value = artifact

    with (
        patch(
            "shared.infrastructure.intent.intent_repository.get_intent_repository",
            return_value=fake_repo,
        ),
        patch.object(mod, "specs_root_for", return_value=repo_root / "specs"),
        patch.object(mod, "law_glob", return_value=[paper_file]),
        patch.object(
            mod, "law_relpath", side_effect=lambda root, p: str(p.relative_to(root))
        ),
        patch.object(mod, "document_status", return_value="accepted"),
        patch.object(
            mod, "_iter_sections", return_value=[("Enforcement", section_text)]
        ),
        patch.object(mod, "GitService") as mock_git_cls,
    ):
        mock_git = MagicMock()
        mock_git.first_seen_date.return_value = date(2026, 6, 1)
        mock_git_cls.return_value = mock_git

        import asyncio

        candidates = asyncio.get_event_loop().run_until_complete(check.run())

    assert isinstance(candidates, list)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.relation is check.relation
    assert "Enforcement" in cand.claim
