# tests/body/cli/logic/test_knowledge.py

from __future__ import annotations

from unittest.mock import patch

import pytest

try:
    from body.cli.logic.knowledge import find_common_knowledge

    _KNOWLEDGE_AVAILABLE = True
except ImportError:  # pragma: no cover
    find_common_knowledge = None
    _KNOWLEDGE_AVAILABLE = False


@pytest.mark.skipif(not _KNOWLEDGE_AVAILABLE, reason="knowledge module not available")
def test_find_common_knowledge():
    """Test that find_common_knowledge runs async workflow and prints results."""
    if not _KNOWLEDGE_AVAILABLE:
        pytest.skip("knowledge module not available")

    with (
        patch("body.cli.logic.knowledge.asyncio") as mock_asyncio,
        patch("body.cli.logic.knowledge.console") as mock_console,
    ):
        # Mock async result
        mock_result = {"hash1": [("file1.py", 10), ("file2.py", 20)]}
        mock_asyncio.run.return_value = mock_result

        # Call command
        find_common_knowledge(min_occurrences=3, max_lines=10)

        # === ASSERTIONS ===
        # 1. Async workflow was executed
        mock_asyncio.run.assert_called_once()

        # 2. Something was printed (at least once)
        mock_console.print.assert_called()
        assert mock_console.print.call_count >= 1  # or == 4 if you want strict

        # Optional: verify key message was printed
        printed_args = [call[0][0] for call in mock_console.print.call_args_list]
        assert any("Next Step" in arg for arg in printed_args if isinstance(arg, str))
