"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/analyzers/knowledge_graph_analyzer.py
- Symbol: KnowledgeGraphAnalyzer
- Status: 1 tests passed, some failed
- Passing tests: test_execute_with_non_python_files
- Generated: 2026-01-11 02:44:10
"""

import pytest
from pathlib import Path
from body.analyzers.knowledge_graph_analyzer import KnowledgeGraphAnalyzer

@pytest.mark.asyncio
async def test_execute_with_non_python_files(tmp_path):
    """Test execute with non-Python files (should be ignored)."""
    analyzer = KnowledgeGraphAnalyzer()
    (tmp_path / 'README.md').write_text('# Test Project')
    (tmp_path / 'config.json').write_text('{"key": "value"}')
    (tmp_path / 'data.txt').write_text('Some text data')
    result = await analyzer.execute(repo_root=tmp_path)
    assert result.ok == True
    assert isinstance(result.data, dict)
