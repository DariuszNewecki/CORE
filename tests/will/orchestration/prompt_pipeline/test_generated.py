from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from will.orchestration.prompt_pipeline import PromptPipeline


# ID: 652ef418-804a-4cfd-b8c8-803d7585945f
def test_PromptPipeline_process(tmp_path: Path) -> None:
    pipeline = PromptPipeline(repo_path=tmp_path)

    pipeline._inject_context = MagicMock(
        side_effect=lambda p: p.replace("[[context:x]]", "CTX")
    )
    pipeline._inject_includes = MagicMock(
        side_effect=lambda p: p.replace("[[include:y]]", "INC")
    )
    pipeline._inject_analysis = MagicMock(
        side_effect=lambda p: p.replace("[[analysis:z]]", "ANALYSIS")
    )

    result = pipeline.process("[[context:x]] [[include:y]] [[analysis:z]]")

    assert result == "CTX INC ANALYSIS"
    pipeline._inject_context.assert_called_once()
    pipeline._inject_includes.assert_called_once()
    pipeline._inject_analysis.assert_called_once()
