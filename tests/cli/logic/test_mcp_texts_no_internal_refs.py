"""#1159 (proof run 3): what an outside assistant reads over MCP cited CORE's
own tracker and decision history -- "How a change lands (#1044)",
"(ADR-168 Amendment 2026-10-10 A1)", "on every pull request (#1043)". In an
adopter's repository those numbers resolve to nothing (decision_adr ADR-168
answers unknown there).

Scanned: the server instructions, every tool's description and input schema,
and every string each tool returns on the adopter-shaped repository. The
adopter's own decisions (the fixture's ADR-007) are its content, not a
dangling reference.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from cli.logic.assistant_tools import TOOLS, invoke
from cli.logic.mcp_server import _INSTRUCTIONS
from tests.cli.logic import test_assistant_tools as _shared


repo = _shared.repo
_INTERNAL_REF = re.compile(r"#\d+|\bADR-\d+")
_ADOPTER_OWN = {"ADR-007"}


def _refs(value: Any, where: str) -> Iterator[str]:
    if isinstance(value, str):
        for m in _INTERNAL_REF.finditer(value):
            if m.group() not in _ADOPTER_OWN:
                yield f"{where}: ...{value[max(0, m.start() - 50) : m.end() + 10]}"
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _refs(item, f"{where}.{key}")
    elif isinstance(value, list | tuple):
        for i, item in enumerate(value):
            yield from _refs(item, f"{where}[{i}]")


# ID: 678e5c1b-e292-4c9e-accf-051457569141
def test_instructions_and_tool_specs_cite_no_internal_refs() -> None:
    found = list(_refs(_INSTRUCTIONS, "instructions"))
    for name, tool in TOOLS.items():
        found += _refs(tool.description, f"{name}.description")
        found += _refs(tool.input_schema, f"{name}.input_schema")
    assert found == []


@pytest.mark.asyncio
# ID: a5fc22eb-905f-4d48-a1c5-1833e0fe51a2
async def test_tool_answers_cite_no_internal_refs(repo: Path) -> None:
    found: list[str] = []
    for name, arguments in _shared._CALLS.items():
        found += _refs(await invoke(name, arguments, repo), name)
    assert found == []


# ID: acf5423d-75dd-4075-a5ad-f3c9719908bd
def test_submit_change_says_what_it_answers() -> None:
    """#1178 (proof run 4): the description ended "and answers step 0"; no
    step 0 is defined anywhere an assistant can read."""
    text = TOOLS["submit_change"].description
    assert "step 0" not in text.lower()
    for field in ("proposal_id", "status", "scope_files", "step_zero"):
        assert field in text, field
