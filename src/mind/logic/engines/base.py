# src/mind/logic/engines/base.py

"""Provides functionality for the base module."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
# ID: 5c3cb061-ea3e-46c9-b0a6-baf214a40b26
class EngineResult:
    ok: bool
    message: str
    violations: list[str]  # e.g., ["Line 42: use of eval()"]
    engine_id: str


# ID: 185ac493-d859-4a19-a7bd-e85fd2239af7
class BaseEngine(ABC):
    @abstractmethod
    # ID: db4c48d2-4ccc-4182-bb37-29973471b8bb
    def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        pass
