# src/features/introspection/vectorization/delta_analyzer.py
# ID: d21e52f0-954a-46b3-aa1b-b199972bb718
"""Delta Analyzer - Identifies symbols requiring re-vectorization."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from shared.utils.embedding_utils import normalize_text

from .code_processor import extract_symbol_source


# ID: aa83d2ae-cd22-4eb5-b930-cd2f7c224abb
class DeltaAnalyzer:
    """Compares current filesystem state against stored vector hashes."""

    def __init__(self, repo_path: Path, stored_hashes: dict[str, str]):
        self.repo_path = repo_path
        self.stored_hashes = stored_hashes

    # ID: 434e51eb-ef0f-4220-acd3-972fa51b1359
    def identify_changes(
        self,
        all_symbols: list[dict],
        existing_links: dict[str, str],
        force: bool,
    ) -> list[dict[str, Any]]:
        """Determine which symbols are 'dirty' and need new embeddings."""
        tasks: list[dict[str, Any]] = []

        for sym in all_symbols:
            # Construct file path: module 'shared.utils' -> 'src/shared/utils.py'
            rel_path = f"src/{sym['module'].replace('.', '/')}.py"

            source = extract_symbol_source(
                self.repo_path / rel_path,
                sym["symbol_path"],
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

            # If forced, or new, or content changed -> add to task list
            if force or (existing_vec_id is None) or (code_hash != existing_hash):
                tasks.append(
                    {
                        "id": sym["id"],
                        "path": sym["symbol_path"],
                        "source": norm_code,
                        "hash": code_hash,
                        "file": rel_path,
                        "is_public": sym.get("is_public", True),
                    }
                )

        return tasks
