import asyncio

from body.services.service_registry import service_registry
from features.project_lifecycle.definition_service import (
    define_single_symbol,
    get_undefined_symbols,
)
from shared.config import settings
from shared.infrastructure.context.service import ContextService
from shared.infrastructure.database.session_manager import get_session


async def test():
    # 1) Get one symbol
    symbols = await get_undefined_symbols(limit=1)
    if not symbols:
        print("No symbols to test")
        return

    symbol = symbols[0]
    print(f"Testing symbol: {symbol['symbol_path']}")

    # 2) Get real dependencies (same pattern as conversational factory)
    cognitive_service = await service_registry.get_cognitive_service()

    qdrant_client = None
    try:
        qdrant_client = await service_registry.get_qdrant_service()
    except Exception as exc:
        print(f"Qdrant not available (continuing without it): {exc}")

    # 3) Build ContextService with correct root + real cognitive service
    ctx_service = ContextService(
        qdrant_client=qdrant_client,
        cognitive_service=cognitive_service,
        config={},
        project_root=str(settings.REPO_PATH),
        session_factory=get_session,
        service_registry=service_registry,  # if your ContextService supports it
    )  # :contentReference[oaicite:3]{index=3}

    # 4) Try to define it
    result = await define_single_symbol(symbol, ctx_service, set())
    print(f"Result: {result}")


asyncio.run(test())
