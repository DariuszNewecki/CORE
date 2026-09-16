# tests/mind/logic/engines/ast_gate/test_orphan_ids_check.py

"""linkage.no_orphan_ids via ast_gate check_type ``orphan_ids``.

The inverse of id_anchor: an anchor that annotates no def/class. Covers the
population id_anchor never inspects -- anchors on private symbols (the
9e9067eb defect) and file-level strays -- and pins that the violation names
line and ID so the fix is a re-attach, not a regeneration."""

from __future__ import annotations

from pathlib import Path

import pytest

from mind.logic.engines.ast_gate.checks.purity_checks import PurityChecks
from mind.logic.engines.ast_gate.engine import ASTGateEngine
from shared.path_resolver import PathResolver


_UID = "a1fb17c6-a4a7-4503-9103-491b28305c2d"

# The class itself is correctly anchored; the only defect is the anchor on
# the private method, split from its def by a blank line (9e9067eb).
SPLIT_ABOVE_PRIVATE = (
    "# ID: 5f1c2a6e-3f1c-4b0a-9c8d-2e7f1a3b4c5d\n"
    "class Worker:\n"
    f"    # ID: {_UID}\n"
    "\n"
    "    async def _run(self):\n"
    "        pass\n"
)


def test_check_reports_line_and_id() -> None:
    violations = PurityChecks.check_orphan_id_anchors(SPLIT_ABOVE_PRIVATE)
    assert len(violations) == 1
    assert "line 3" in violations[0]
    assert _UID in violations[0]
    assert "re-attach" in violations[0]


def test_check_is_silent_on_attached_anchors() -> None:
    source = f"# ID: {_UID}\ndef f():\n    pass\n"
    assert PurityChecks.check_orphan_id_anchors(source) == []


def test_id_anchor_check_is_blind_to_this_defect() -> None:
    """Documents why the rule exists: the public-only check passes the
    9e9067eb file shape, the orphan check does not."""
    assert PurityChecks.check_stable_id_anchor(SPLIT_ABOVE_PRIVATE) == []
    assert PurityChecks.check_orphan_id_anchors(SPLIT_ABOVE_PRIVATE) != []


@pytest.fixture
def engine(tmp_path: Path) -> ASTGateEngine:
    # The engine reads .intent_root only inside protected_namespace_access,
    # which this file never exercises; any root will do.
    return ASTGateEngine(path_resolver=PathResolver(repo_root=tmp_path))


async def test_engine_dispatches_orphan_ids(
    engine: ASTGateEngine, tmp_path: Path
) -> None:
    assert "orphan_ids" in ASTGateEngine._SUPPORTED_CHECK_TYPES
    assert "orphan_ids" not in ASTGateEngine._context_check_types

    bad = tmp_path / "bad.py"
    bad.write_text(SPLIT_ABOVE_PRIVATE, encoding="utf-8")
    result = await engine.verify(bad, {"check_type": "orphan_ids"})
    assert not result.ok
    assert result.engine_id == "ast_gate"
    assert len(result.violations) == 1
    assert _UID in str(result.violations[0])

    good = tmp_path / "good.py"
    good.write_text(f"# ID: {_UID}\ndef f():\n    pass\n", encoding="utf-8")
    result = await engine.verify(good, {"check_type": "orphan_ids"})
    assert result.ok
    assert result.violations == []
