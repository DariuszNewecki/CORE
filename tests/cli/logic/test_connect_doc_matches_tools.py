"""#1177 (proof run 4): *Connect your AI assistant* listed eight tools and said
"Six tools only read" while the MCP server offered nine; core_status was in
neither the table, the count, nor the --allowedTools list."""

from __future__ import annotations

import re
from pathlib import Path

from cli.logic.assistant_tools import TOOLS


DOC = Path(__file__).resolve().parents[3] / "docs" / "connect-an-assistant.md"
_SUBMIT = {"validate_change", "submit_change"}
_WORDS = {3: "Three", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten"}


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


# ID: b2ecd6e6-6adf-45a9-a38a-c1b321f43862
def test_tool_table_lists_exactly_the_servers_tools() -> None:
    listed = re.findall(r"^\| `([a-z_]+)` \|", _text(), flags=re.MULTILINE)
    assert sorted(listed) == sorted(TOOLS)


# ID: b56eb948-2904-420b-8162-718774c5ce89
def test_read_only_count_matches() -> None:
    reading = len(TOOLS) - len(_SUBMIT)
    assert f"{_WORDS[reading]} tools only read." in _text()


# ID: 4c8843b1-efaa-465a-8952-435f2162ac58
def test_allowed_tools_list_has_every_read_tool_and_no_submit_tool() -> None:
    (allowed,) = re.findall(r'--allowedTools "([^"]+)"', _text())
    names = {t.removeprefix("mcp__core__") for t in allowed.split(",")}
    assert names == set(TOOLS) - _SUBMIT
