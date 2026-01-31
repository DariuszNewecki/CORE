# src/features/introspection/vectorization/delta_analyzer.py

"""
Delta Analyzer - Identifies symbols requiring re-vectorization.
Pure 'Parse/Audit' logic for the vectorization pipeline.
"""

from __future__ import annotations

import hashlib
from typing import Any

from shared.config import settings
from shared.utils.embedding_utils import normalize_text

from .code_processor import extract_symbol_source


# ID: vectorization_delta_analyzer
# ID: d21e52f0-954a-46b3-aa1b-b199972bb718
class DeltaAnalyzer:
    """Compares current filesystem state against stored vector hashes."""

    def __init__(self, repo_path: Any, stored_hashes: dict[str, str]):
        self.repo_path = repo_path
        self.stored_hashes = stored_hashes

    # ID: 434e51eb-ef0f-4220-acd3-972fa51b1359
    def identify_changes(
        self, all_symbols: list[dict], existing_links: dict, force: bool
    ) -> list[dict[str, Any]]:
        """Determines which symbols are 'dirty' and need new embeddings."""
        tasks = []
        for sym in all_symbols:
            rel_path = f"src/{sym['module'].replace('.', '/')}.py"
            source = extract_symbol_source(
                self.repo_root_path() / rel_path, sym["symbol_path"]
            )

            if not source:
                continue

            norm_code = normalize_text(source)
            code_hash = hashlib.sha256(norm_code.encode("utf-8")).hexdigest()

            symbol_id_str = str(sym["id"])
            existing_vec_id = existing_links.get(symbol_id_str)
            existing_hash = (
                self.stored_hashes.get(existing_vec_id) if existing_vec_id else None
            )

            if force or (existing_vec_id is None) or (code_hash != existing_hash):
                tasks.append(
                    {
                        "id": sym["id"],
                        "path": sym["symbol_path"],
                        "source": norm_code,
                        "hash": code_hash,
                        "file": rel_path,
                    }
                )
        return tasks

    # ID: 2eac143d-1ade-408e-b5f5-f98efbd63948
    def repo_root_path(self):
        return settings.REPO_PATH
