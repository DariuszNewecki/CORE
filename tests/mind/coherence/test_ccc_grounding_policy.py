"""CCC structural checks after CCC run 6558a043 and proposal 0012.

- ROW3: a draft paper's MUSTs are proposals — not flagged.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar
from unittest.mock import MagicMock, patch

import pytest

import shared.infrastructure.intent.intent_repository as ir_module
from mind.coherence.checks.row3_citation import Row3CitationCheck
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
