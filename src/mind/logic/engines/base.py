# src/mind/logic/engines/base.py

"""
Provides the base contract for all constitutional enforcement engines.

CONSTITUTIONAL ALIGNMENT:
- Aligned with 'async.no_manual_loop_run'.
- Promoted to async-first verification to prevent event-loop hijacking
  in I/O-bound engines (Database/Network).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
# ID: 5c3cb061-ea3e-46c9-b0a6-baf214a40b26
class EngineResult:
    """The result of a constitutional engine verification run."""

    ok: bool
    message: str
    violations: list[str]  # e.g., ["Line 42: use of eval()"]
    engine_id: str


# ID: 185ac493-d859-4a19-a7bd-e85fd2239af7
class BaseEngine(ABC):
    """
    Abstract base class for all Governance Engines.

    Now natively async to support the Database-as-SSOT principle
    without violating loop-hijacking rules.
    """

    @abstractmethod
    # ID: db4c48d2-4ccc-4182-bb37-29973471b8bb
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """
        Verify a file or context against constitutional rules.

        Args:
            file_path: Absolute path to the file being audited.
            params: Rule-specific parameters from the Mind.

        Returns:
            EngineResult indicating compliance status.
        """
        pass
