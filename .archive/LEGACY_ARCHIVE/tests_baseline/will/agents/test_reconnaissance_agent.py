# tests/will/agents/test_reconnaissance_agent.py


import pytest


pytestmark = pytest.mark.legacy

from unittest.mock import AsyncMock

from will.agents.reconnaissance_agent import ReconnaissanceAgent


def _make_knowledge_graph() -> dict:
    """
    Minimal knowledge graph fixture with one target symbol and one caller.

    symbols:
      - "module.target": the symbol we find via semantic search
      - "module.caller": a symbol that calls `target`
    """
    target_symbol = {
        "key": "module.target",
        "name": "target",
        "type": "function",
        "file": "src/module.py",
        "intent": "Does something important.",
        "calls": [],
    }
    caller_symbol = {
        "key": "module.caller",
        "name": "caller",
        "type": "function",
        "file": "src/caller.py",
        "intent": "Uses target.",
        "calls": ["target"],
    }
    return {
        "symbols": {
            "module.target": target_symbol,
            "module.caller": caller_symbol,
        }
    }


@pytest.mark.anyio
async def test_find_relevant_symbols_and_files_happy_path() -> None:
    """_find_relevant_symbols_and_files should return symbols and files from semantic search hits."""
    graph = _make_knowledge_graph()
    cognitive_service = AsyncMock()
    # Simulate a single hit pointing at our target symbol
    cognitive_service.search_capabilities = AsyncMock(
        return_value=[{"payload": {"symbol": "module.target"}}]
    )

    agent = ReconnaissanceAgent(graph, cognitive_service)

    symbols, files = await agent._find_relevant_symbols_and_files("add feature X")

    assert len(symbols) == 1
    assert symbols[0]["key"] == "module.target"
    # Files are returned as a sorted list, derived from symbol["file"]
    assert files == ["src/module.py"]
    cognitive_service.search_capabilities.assert_awaited_once()


@pytest.mark.anyio
async def test_find_relevant_symbols_and_files_handles_exception() -> None:
    """If semantic search fails, the agent should degrade gracefully and return empty results."""
    graph = _make_knowledge_graph()
    cognitive_service = AsyncMock()
    cognitive_service.search_capabilities = AsyncMock(side_effect=RuntimeError("boom"))

    agent = ReconnaissanceAgent(graph, cognitive_service)

    symbols, files = await agent._find_relevant_symbols_and_files("any goal")

    assert symbols == []
    assert files == []


def test_find_callers_finds_symbols_calling_target() -> None:
    """_find_callers returns all symbols whose 'calls' list references the given name."""
    graph = _make_knowledge_graph()
    cognitive_service = AsyncMock()  # not used in this test
    agent = ReconnaissanceAgent(graph, cognitive_service)

    callers = agent._find_callers("target")
    assert len(callers) == 1
    assert callers[0]["key"] == "module.caller"

    # None / empty symbol name should return an empty list
    assert agent._find_callers(None) == []


@pytest.mark.anyio
async def test_generate_report_with_results_includes_files_and_symbols() -> None:
    """generate_report should include relevant files and symbols with caller info."""
    graph = _make_knowledge_graph()
    cognitive_service = AsyncMock()
    agent = ReconnaissanceAgent(graph, cognitive_service)

    # Avoid hitting the real cognitive_service logic here:
    # directly stub the internal search helper.
    target_symbol = graph["symbols"]["module.target"]
    agent._find_relevant_symbols_and_files = AsyncMock(  # type: ignore[assignment]
        return_value=([target_symbol], ["src/module.py"])
    )

    report = await agent.generate_report("implement feature Y")

    # Basic structure
    assert "# Reconnaissance Report" in report
    assert "## Relevant Files Identified by Semantic Search" in report
    assert "- `src/module.py`" in report

    # Symbol section with metadata
    assert "## Relevant Symbols Identified by Semantic Search" in report
    assert "### Symbol: `module.target`" in report
    assert "- **Type:** function" in report
    assert "- **Location:** `src/module.py`" in report
    assert "- **Intent:** Does something important." in report

    # Caller info (since module.caller calls 'target')
    assert "- **Referenced By:**" in report
    assert "  - `module.caller`" in report

    # Conclusion present (markdown-formatted)
    assert (
        "The analysis is complete. Use this information to form a precise plan."
        in report
    )


@pytest.mark.anyio
async def test_generate_report_no_results_has_fallback_messages() -> None:
    """When no files or symbols are found, the report should include the 'no results' text."""
    graph = _make_knowledge_graph()
    cognitive_service = AsyncMock()
    agent = ReconnaissanceAgent(graph, cognitive_service)

    agent._find_relevant_symbols_and_files = AsyncMock(  # type: ignore[assignment]
        return_value=([], [])
    )

    report = await agent.generate_report("goal with no context")

    assert "- No specific relevant files were identified via semantic search." in report
    assert "- No specific code symbols were identified via semantic search." in report
