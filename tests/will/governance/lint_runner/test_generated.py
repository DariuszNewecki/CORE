from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.governance.lint_runner import run_lint


# ID: 77004eaa-5331-484b-98e7-f32d4642e497
async def test_run_lint():
    # ID: 536449e8-f52c-45d1-bd43-3bc8ca84e066
    async def fake_run_tool(path, args):
        if path.name == "black":
            return {"returncode": 0, "stdout": "", "stderr": ""}
        return {"returncode": 0, "stdout": "all good", "stderr": ""}

    fake_path = MagicMock()
    fake_path.exists.return_value = True
    fake_path.__truediv__.side_effect = lambda name: MagicMock(
        name=name, exists=lambda: True
    )
    fake_path.__truediv__.return_value.name = "black"

    with (
        patch("will.governance.lint_runner._VENV_BIN", new=fake_path),
        patch(
            "will.governance.lint_runner._run_tool",
            new=AsyncMock(side_effect=fake_run_tool),
        ),
    ):
        result = await run_lint()

    assert result["ok"] is True
    assert result["error"] is None
    assert set(result["tools"].keys()) == {"black", "ruff"}
    assert result["tools"]["black"]["returncode"] == 0
    assert result["tools"]["ruff"]["returncode"] == 0
