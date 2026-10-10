"""CCC structural checks after CCC run 6558a043 and proposal 0012.

- ROW2: an ADR is grounded by a paper (path or file name), the northstar or
  charter, or another accepted ADR; a Supersedes-only reference is still an
  inherited bind, verified separately.
- ROW3: a draft paper's MUSTs are proposals — not flagged.
- ROW4: a law file is named when its introducing commit cites an accepted
  ADR whose text names the file's folder.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar
from unittest.mock import MagicMock, patch

import pytest

import shared.infrastructure.intent.intent_repository as ir_module
from mind.coherence.checks.row2_grounding import Row2GroundingCheck
from mind.coherence.checks.row3_citation import Row3CitationCheck
from mind.coherence.checks.row4_naming import Row4NamingCheck
from shared.governance.coherence_harvester import NormativeMarkerRegister


def _fake_repo(glob: str) -> object:
    class _Type:
        content: ClassVar[dict] = {"discovery": [glob]}

    class _Repo:
        def get_artifact_type(self, _name: str) -> _Type:
            return _Type()

    return _Repo()


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


async def _row2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list:
    monkeypatch.setattr(
        ir_module, "get_intent_repository", lambda: _fake_repo(".specs/decisions/*.md")
    )
    return await Row2GroundingCheck(repo_root=tmp_path).run()


_ACCEPTED = "**Status:** Accepted\n"


# ID: 0a7ff582-ed47-47a6-ac1f-94a3cf4837d1
async def test_row2_paper_named_by_file_name_grounds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, ".specs/papers/CORE-Topic.md", "# Topic")
    _write(tmp_path, ".specs/decisions/ADR-010-x.md", _ACCEPTED + "See CORE-Topic.md.")
    assert await _row2(tmp_path, monkeypatch) == []


# ID: af43ed4a-bbc5-4c30-872b-aa1d3be05079
async def test_row2_northstar_or_accepted_adr_grounds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(
        tmp_path, ".specs/decisions/ADR-010-a.md", _ACCEPTED + "Grounds: the northstar."
    )
    _write(
        tmp_path, ".specs/decisions/ADR-011-b.md", _ACCEPTED + "Grounds: ADR-010 D2."
    )
    assert await _row2(tmp_path, monkeypatch) == []


# ID: 1743b999-1a5c-4b7c-aa55-e4df4723bda2
async def test_row2_citing_only_a_proposed_adr_is_not_grounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, ".specs/decisions/ADR-010-a.md", "**Status:** Proposed\n# Body")
    _write(tmp_path, ".specs/decisions/ADR-011-b.md", _ACCEPTED + "Relates: ADR-010.")
    candidates = await _row2(tmp_path, monkeypatch)
    assert [c.documents for c in candidates] == [[".specs/decisions/ADR-011-b.md"]]


# ID: e978177c-9b85-4ee3-ad24-c4df611d65c3
async def test_row3_draft_paper_is_not_flagged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    section = "## 2. Rule\n\nThe executor MUST record every consequence.\n"
    _write(
        tmp_path, ".specs/papers/CORE-Draft.md", "---\nstatus: draft\n---\n" + section
    )
    _write(
        tmp_path,
        ".specs/papers/CORE-Live.md",
        "---\nstatus: canonical\n---\n" + section,
    )
    monkeypatch.setattr(
        ir_module, "get_intent_repository", lambda: _fake_repo(".specs/papers/*.md")
    )
    register = NormativeMarkerRegister._from_data({"markers": ["MUST"]}, source="t")
    with patch(
        "mind.coherence.checks.row3_citation.GitService",
        return_value=MagicMock(first_seen_date=MagicMock(return_value=None)),
    ):
        candidates = await Row3CitationCheck(tmp_path, register).run()
    assert {c.documents[0] for c in candidates} == {".specs/papers/CORE-Live.md"}


# ID: 540d5830-f99a-4297-982c-e479c445b20e
def test_row4_named_when_introducing_commit_cites_an_accepted_adr(
    tmp_path: Path,
) -> None:
    check = Row4NamingCheck(tmp_path)
    accepted = {"56": "Contracts, one per model.", "167": "docs/CLI rules."}
    git = MagicMock()
    with patch("mind.coherence.checks.row4_naming.GitService", return_value=git):
        git.introducing_commit_subject.return_value = "feat(intent): ADR-056 Wave 1"
        assert check._named_by_introducing_decision(".intent/x/a.json", accepted)
        git.introducing_commit_subject.return_value = "feat(cli_gate): ADR-167 rules"
        assert check._named_by_introducing_decision(
            ".intent/rules/cli/d.json", accepted
        )
        git.introducing_commit_subject.return_value = "feat: close #617"
        assert not check._named_by_introducing_decision(".intent/x/a.json", accepted)
        git.introducing_commit_subject.return_value = "feat: ADR-117 janitor"
        assert not check._named_by_introducing_decision(".intent/x/a.json", accepted)
