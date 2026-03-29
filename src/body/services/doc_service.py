# src/body/services/doc_service.py
"""
DocService - Data-access layer for core.symbols (documentation).

Covers:
  - DocWorker._fetch_undocumented_symbols
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 775dc52c-2cbf-4a87-929e-ea677f872685
class DocService:
    """
    Body layer service. Exposes named methods for core.symbols
    queries used by DocWorker.
    """

    # ID: d68e8d4c-7382-4530-a715-3aa852b9eac8
    async def fetch_undocumented_symbols(self) -> list[dict[str, Any]]:
        """
        Return public symbols with missing or empty intent,
        ordered by module and qualname.

        Covers:
          - DocWorker._fetch_undocumented_symbols
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    select
                        symbol_path,
                        module,
                        qualname,
                        kind,
                        file_path
                    from core.symbols
                    where
                        is_public = true
                        and (intent is null or trim(intent) = '')
                    order by module, qualname
                    """
                )
            )
            return [dict(row._mapping) for row in result]
