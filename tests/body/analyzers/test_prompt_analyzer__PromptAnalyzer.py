"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/analyzers/prompt_analyzer.py
- Symbol: PromptAnalyzer
- Status: 1 tests passed, some failed
- Passing tests: test_prompt_analyzer_template_not_found
- Generated: 2026-01-11 02:45:26
"""

from pathlib import Path

import pytest

from body.analyzers.prompt_analyzer import PromptAnalyzer


@pytest.mark.asyncio
async def test_prompt_analyzer_template_not_found(tmp_path: Path):
    """Test behavior when template file doesn't exist.

    2026-06-07 (#572 Cat B batch 18): execute() now requires an explicit
    ``prompt_root`` parameter (same DI shape as FileAnalyzer from batch 12;
    source returns 'PromptAnalyzer requires prompt_root parameter'
    otherwise). Pass an empty tmp_path as prompt_root so the template
    lookup misses cleanly and we hit the not-found branch."""
    analyzer = PromptAnalyzer()
    context = {"source_code": "print('hello')"}
    result = await analyzer.execute(
        "non_existent_template", context, prompt_root=tmp_path
    )
    assert not result.ok
    assert result.confidence == 0.0
    assert "error" in result.data
    assert "Template not found" in result.data["error"]
