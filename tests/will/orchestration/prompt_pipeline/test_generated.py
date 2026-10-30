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





# ID: 5944f0ce-f3fd-46bd-8bfa-451de59f315d
def test_PromptPipeline(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "notes.txt"
    target.write_text("hello world", encoding="utf-8")

    pipeline = PromptPipeline(repo)

    is_safe, abs_path, error = pipeline._is_safe_path("notes.txt")
    assert is_safe is True
    assert error == ""
    assert abs_path == target.resolve()

    content, success = pipeline._read_file_safe("notes.txt")
    assert success is True
    assert content == "hello world"

    result = pipeline.process("Dir: [[context:notes.txt]]")
    assert "--- CONTEXT: notes.txt ---" in result
    assert "hello world" in result
    assert "--- END CONTEXT ---" in result

    assert pipeline.context_pattern.pattern == r"\[\[context:(.+?)\]\]"
