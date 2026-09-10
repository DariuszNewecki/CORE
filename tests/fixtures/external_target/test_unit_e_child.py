"""Focused tests for unit_e_child.py's own wiring.

unit_e_child.py deliberately carries almost no logic of its own -- it
reuses unit_d_child.py's real _run() unmodified except for the Proposal's
goal string (see that module's docstring). These tests exercise this
module's own thin surface (the goal string it passes, its main()'s
result-writing contract) via a stub _run, without provisioning a database
or running the full governed scenario -- that remains the live run,
executed once, against real components (see the Unit E final report).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent))

import unit_e_child


class TestGoalString:
    def test_goal_identifies_unit_e(self) -> None:
        assert "Unit E" in unit_e_child._GOAL

    def test_goal_cites_the_governing_adrs(self) -> None:
        assert "ADR-129 D1" in unit_e_child._GOAL
        assert "ADR-101 D3" in unit_e_child._GOAL

    def test_goal_differs_from_unit_d(self) -> None:
        from unit_d_child import _GOAL as unit_d_goal

        assert unit_e_child._GOAL != unit_d_goal


class TestMainWiring:
    def test_main_passes_this_modules_goal_to_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        async def _fake_run(target: Path, *, goal: str) -> dict:
            captured["target"] = target
            captured["goal"] = goal
            return {"ok": True, "proposal_id": "p-1"}

        monkeypatch.setattr(unit_e_child, "_run", _fake_run)
        result_path = tmp_path / "result.json"
        monkeypatch.setattr(
            sys, "argv", ["unit_e_child.py", str(tmp_path / "target"), str(result_path)]
        )

        rc = unit_e_child.main()

        assert rc == 0
        assert captured["goal"] == unit_e_child._GOAL
        assert captured["target"] == tmp_path / "target"
        written = json.loads(result_path.read_text("utf-8"))
        assert written == {"ok": True, "proposal_id": "p-1"}

    def test_main_writes_structured_failure_on_exception(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _raising_run(target: Path, *, goal: str) -> dict:
            raise RuntimeError("boom")

        monkeypatch.setattr(unit_e_child, "_run", _raising_run)
        result_path = tmp_path / "result.json"
        monkeypatch.setattr(
            sys, "argv", ["unit_e_child.py", str(tmp_path / "target"), str(result_path)]
        )

        rc = unit_e_child.main()

        assert rc == 1
        written = json.loads(result_path.read_text("utf-8"))
        assert written["ok"] is False
        assert written["stage"] == "unhandled_exception"
        assert "boom" in written["error"]
