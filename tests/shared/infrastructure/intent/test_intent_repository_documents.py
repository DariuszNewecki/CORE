"""IntentRepository document reads: parse failures and scoped walks."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.infrastructure.intent.errors import GovernanceError
from shared.infrastructure.intent.intent_repository import IntentRepository


def _repo(tmp_path: Path) -> IntentRepository:
    root = tmp_path / ".intent"
    mappings = root / "enforcement" / "mappings" / "x"
    mappings.mkdir(parents=True)
    (mappings / "good.yaml").write_text("mappings:\n  a.b:\n    engine: x\n")
    (mappings / "bad.yaml").write_text("mappings: [unclosed\n")
    (root / "META").mkdir()
    (root / "META" / "s.json").write_text('{"k": 1}')
    return IntentRepository(root=root, strict=False)


def test_malformed_yaml_raises_governance_error(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    with pytest.raises(GovernanceError):
        repo.load_document(repo.resolve_rel("enforcement/mappings/x/bad.yaml"))


def test_iter_documents_skips_a_malformed_file(tmp_path: Path) -> None:
    """Regression (2026-10-02): a YAML parse error escaped as ValueError, so the
    documented "log and skip" did not hold and the walk aborted."""
    names = [p.name for p, _ in _repo(tmp_path).iter_documents()]
    assert "good.yaml" in names
    assert "bad.yaml" not in names


def test_iter_documents_under_limits_the_walk(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    names = [p.name for p, _ in repo.iter_documents(under="enforcement/mappings")]
    assert names == ["good.yaml"]
    assert list(repo.iter_documents(under="does/not/exist")) == []
