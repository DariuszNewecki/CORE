# src/body/services/file_service.py
"""
Body layer file operations service.

Thin Body-layer wrapper around the single FileHandler write channel
(ADR-097). Will-tier and other Body consumers delegate through this
service so they do not have to import FileHandler directly
(`[[will-tier-file-ops-use-fileservice]]`); Mind never reaches here at all.

Per ADR-097 D4, the surface is narrowed to a unified `write` entry
that delegates straight through to `FileHandler.write`, with a
`write_json` convenience for dict payloads. The leak-through wrappers
(`write_runtime_text/_bytes/_json`, `write_file`) and the
`get_file_handler` escape hatch are gone — they re-exposed FileHandler's
pre-ADR-097 surface and have no remaining callers after the step-7
mechanical migration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from body.infrastructure.storage.file_handler import FileHandler, FileOpResult
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 54b51df1-b3c5-4169-9c69-d76b08f77e2b
class FileService:
    """Body-layer thin wrapper over `FileHandler.write` (ADR-097 D4).

    The surface is intentionally minimal: one write entry, one JSON
    convenience, directory ensure, and the staged pending-write path.
    Target-class dispatch, source-shape transforms, and IntentGuard
    routing all live in FileHandler — this layer adds no policy.
    """

    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path).resolve()
        self._file_handler = FileHandler(str(self.repo_path))
        logger.debug("FileService initialized for %s", self.repo_path)

    # ID: 2e4a3653-7c9b-47e1-bd87-818468bfee40
    def write(self, rel_path: str, content: str | bytes) -> FileOpResult:
        """Single-channel write. Delegates to `FileHandler.write` (ADR-097 D4)."""
        return self._file_handler.write(rel_path, content)

    # ID: 437ab543-980e-4315-8ae9-c6d39c99d376
    def write_json(self, rel_path: str, payload: Any) -> FileOpResult:
        """Serialize `payload` with `indent=2` and write through `write`.

        Single-purpose convenience over the unified channel — standardizes
        JSON output shape across the codebase. Not a parallel write path
        (ADR-097 D4).
        """
        return self._file_handler.write(rel_path, json.dumps(payload, indent=2))

    # ID: d05b941e-2c2a-4f0c-849d-80206f4ec140
    def ensure_dir(self, rel_dir: str) -> FileOpResult:
        return self._file_handler.ensure_dir(rel_dir)

    # ID: c746644c-35d6-4b59-9caa-1c921e8a6b07
    def add_pending_write(self, prompt: str, suggested_path: str, code: str) -> str:
        return self._file_handler.add_pending_write(prompt, suggested_path, code)
