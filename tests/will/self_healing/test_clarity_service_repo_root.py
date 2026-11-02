"""fix clarity reads the target from the context's repository (#1390 F13).

It asked ConfigService for REPO_PATH, which no table supplies since the
ADR-052 cutover, so every run ended in KeyError before generating anything.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.self_healing import clarity_service


class _Reached(Exception):
    """Raised once the service has read the source file."""


async def test_source_is_read_from_the_context_repository(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    context = MagicMock()
    context.git_service.repo_path = tmp_path

    task = MagicMock(targets=["pkg/mod.py"])
    ok = MagicMock(ok=True, data={"task": task, "strategy": "s"}, metadata={})

    def _stop(name: str) -> None:
        raise _Reached(name)

    with (
        patch.object(clarity_service, "CLIArgsInterpreter") as interp,
        patch.object(clarity_service, "FileAnalyzer") as analyzer,
        patch.object(clarity_service, "ClarityStrategist") as strategist,
        patch.object(clarity_service.PromptModel, "load", side_effect=_stop),
    ):
        interp.return_value.execute = AsyncMock(return_value=ok)
        analyzer.return_value.execute = AsyncMock(return_value=ok)
        strategist.return_value.execute = AsyncMock(return_value=ok)
        with pytest.raises(_Reached):
            await clarity_service.remediate_clarity_v2(context, Path("pkg/mod.py"))
