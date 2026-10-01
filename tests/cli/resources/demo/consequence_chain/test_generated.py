from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer

from cli.resources.demo.consequence_chain import consequence_chain_cmd


# ID: a18b4fd4-8636-4c18-8e70-9fa9913fa725
def test_consequence_chain_cmd():
    core_context = SimpleNamespace(
        git_service=SimpleNamespace(repo_path="/tmp/repo"),
    )
    ctx = MagicMock()
    ctx.obj = core_context

    result = SimpleNamespace(ok=True)

    run_chain = AsyncMock(return_value=result)

    with (
        patch(
            "cli.resources.demo.consequence_chain.shutil.which",
            return_value="/usr/bin/docker",
        ),
        patch(
            "cli.resources.demo.consequence_chain.run_consequence_chain",
            run_chain,
        ),
        patch(
            "cli.resources.demo.consequence_chain.render_summary",
        ) as mock_render_summary,
    ):
        with pytest.raises(typer.Exit) as exc_info:
            asyncio.run(
                consequence_chain_cmd(
                    ctx=ctx,
                    output=None,
                    keep_workspace=False,
                    simulate_confirmation=True,
                    timeout_seconds=None,
                )
            )

    assert exc_info.value.exit_code == 0
    run_chain.assert_awaited_once()
    mock_render_summary.assert_called_once()
