# src/features/test_generation_v2/artifacts.py

"""
Test Generation Artifact Store

Purpose:
- Centralize run artifact persistence (prompt/response/normalized/validation/sandbox/summary).
- Keep AdaptiveTestGenerator as an orchestrator rather than a file writer.

Artifacts live under: work/test_generation/<timestamp>/
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from shared.infrastructure.storage.file_handler import FileHandler


@dataclass(frozen=True)
# ID: 2a4ce96d-352e-4873-9e9b-2aa28d3e6c1a
class ArtifactPaths:
    session_dir: str


# ID: 2dbb6d78-468d-41cb-9a8f-4d1d3b839b5a
class TestGenArtifactStore:
    """Write session artifacts in a consistent, discoverable format."""

    def __init__(self, file_handler: FileHandler):
        self._fh = file_handler

    # ID: 5f574d0e-77ed-4315-9df5-be41652fcb15
    def start_session(self) -> ArtifactPaths:
        session_dir = f"work/test_generation/{int(time.time())}"
        self._fh.ensure_dir(session_dir)
        return ArtifactPaths(session_dir=session_dir)

    # ID: b7e7ee4f-051c-47a4-a4e0-5cc27f52435d
    def write_prompt(self, session_dir: str, symbol: str, prompt: str) -> str:
        path = f"{session_dir}/{symbol}_prompt.txt"
        self._fh.write_runtime_text(path, prompt)
        return path

    # ID: 84565676-b712-4233-b75e-a9e15440e302
    def write_response(self, session_dir: str, symbol: str, response: str) -> str:
        path = f"{session_dir}/{symbol}_response.txt"
        self._fh.write_runtime_text(path, response)
        return path

    # ID: 9eacbc1c-47de-4559-b019-36b6ad679793
    def write_normalized(
        self, session_dir: str, symbol: str, code: str, method: str
    ) -> str:
        path = f"{session_dir}/{symbol}_normalized.py"
        header = f"# Normalization: {method}\n"
        self._fh.write_runtime_text(path, header + code)
        return path

    # ID: 2b26fa57-3566-4bde-b9b5-661a95caf2d2
    def write_generated(self, session_dir: str, symbol: str, code: str) -> str:
        path = f"{session_dir}/{symbol}_generated.py"
        self._fh.write_runtime_text(path, code)
        return path

    # ID: 567ebd95-72f6-4109-8f6b-a4c45b1479ed
    def write_validation(
        self, session_dir: str, symbol: str, ok: bool, error: str, normalization: str
    ) -> str:
        path = f"{session_dir}/{symbol}_validation.json"
        payload = {
            "symbol": symbol,
            "validation_passed": ok,
            "error": error,
            "normalization": normalization,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._fh.write_runtime_text(path, json.dumps(payload, indent=2))
        return path

    # ID: 1320761a-226a-4029-ac11-e8adf3ca628e
    def write_sandbox(
        self, session_dir: str, symbol: str, passed: bool, error: str
    ) -> str:
        path = f"{session_dir}/{symbol}_sandbox.json"
        payload = {
            "symbol": symbol,
            "passed": passed,
            "error": error,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._fh.write_runtime_text(path, json.dumps(payload, indent=2))
        return path

    # ID: 537c3dc7-ed51-440f-ad35-9a199001d21a
    def write_summary(self, session_dir: str, summary: dict[str, Any]) -> str:
        path = f"{session_dir}/SUMMARY.json"
        self._fh.write_runtime_text(path, json.dumps(summary, indent=2))
        return path
