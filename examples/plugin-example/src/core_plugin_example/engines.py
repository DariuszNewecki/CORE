"""An example engine: flags lines that contain a TODO marker.

It imports only from ``mind.engine_api``, the one public import path for
engines outside CORE (ADR-177 D6).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mind.engine_api import BaseEngine, EngineResult, EvidenceClass


class NoTodoGate(BaseEngine):
    """Fails a file that still contains a TODO marker."""

    engine_id = "example_no_todo_gate"
    evidence_class = EvidenceClass.PROVEN

    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        marker = str(params.get("marker", "TODO"))
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            return EngineResult(
                ok=False,
                message=f"cannot read {file_path.name}: {exc}",
                violations=[f"unreadable file: {exc}"],
                engine_id=self.engine_id,
            )
        hits = [f"line {n}: {marker} marker" for n, line in enumerate(lines, 1) if marker in line]
        return EngineResult(
            ok=not hits,
            message=f"{len(hits)} {marker} marker(s)" if hits else "no markers",
            violations=hits,
            engine_id=self.engine_id,
        )
