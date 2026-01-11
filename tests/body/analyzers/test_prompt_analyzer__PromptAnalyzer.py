"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/analyzers/prompt_analyzer.py
- Symbol: PromptAnalyzer
- Status: 1 tests passed, some failed
- Passing tests: test_prompt_analyzer_template_not_found
- Generated: 2026-01-11 02:45:26
"""

import pytest
from body.analyzers.prompt_analyzer import PromptAnalyzer
import tempfile
import os

@pytest.mark.asyncio
async def test_prompt_analyzer_template_not_found():
    """Test behavior when template file doesn't exist."""
    analyzer = PromptAnalyzer()
    context = {'source_code': "print('hello')"}
    result = await analyzer.execute('non_existent_template', context)
    assert result.ok == False
    assert result.confidence == 0.0
    assert 'error' in result.data
    assert 'Template not found' in result.data['error']
