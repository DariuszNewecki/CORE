# src/features/test_generation_v2/llm_output.py

"""
LLM Output Normalization

Purpose:
- Convert "assistant-style" LLM responses into parseable Python source code.
- Strip Markdown fences and remove leading prose when possible.

This module is intentionally pure and unit-testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
# ID: 7bce2b7a-9b1e-4b34-a0b2-4c3b2f70b0d0
class NormalizedOutput:
    code: str
    method: str  # e.g., "fenced:python", "fenced:any", "sliced", "raw", "empty"


# ID: 2b77c7cc-0a1e-4f7f-8bb8-3f5c94a3b815
class PythonOutputNormalizer:
    """Normalize LLM output into parseable Python."""

    _FENCED_PY_RE = re.compile(
        r"```python\s*(.*?)\s*```", flags=re.DOTALL | re.IGNORECASE
    )
    _FENCED_ANY_RE = re.compile(r"```\s*(.*?)\s*```", flags=re.DOTALL)

    # ID: 6399b7f3-87a3-4cf8-946c-1ffbf52b8950
    def normalize(self, raw: str) -> NormalizedOutput:
        text = (raw or "").strip()
        if not text:
            return NormalizedOutput(code="", method="empty")

        # Prefer ```python ... ``` blocks (most common)
        m = self._FENCED_PY_RE.search(text)
        if m:
            return NormalizedOutput(code=m.group(1).strip(), method="fenced:python")

        # Fallback any fenced code block
        m = self._FENCED_ANY_RE.search(text)
        if m:
            return NormalizedOutput(code=m.group(1).strip(), method="fenced:any")

        # Slice away leading prose: start at first plausible code line
        lines = text.splitlines()
        starters = ("import ", "from ", "def ", "async def ", "class ", '"""', "#", "@")
        for idx, line in enumerate(lines):
            if line.lstrip().startswith(starters):
                if idx > 0:
                    return NormalizedOutput(
                        code="\n".join(lines[idx:]).strip(), method="sliced"
                    )
                break

        return NormalizedOutput(code=text, method="raw")
