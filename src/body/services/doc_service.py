# src/body/services/doc_service.py
"""
DocService - Data-access layer for core.symbols (documentation).

Covers:
  - DocWorker._fetch_undocumented_symbols
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 775dc52c-2cbf-4a87-929e-ea677f872685
class DocService:
    """
    Body layer service. Exposes named methods for core.symbols
    queries used by DocWorker.
    """
