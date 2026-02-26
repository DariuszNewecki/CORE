#!/bin/bash
# Force the Coder role to use Anthropic
poetry run python3 -c "
import asyncio
from services.database.session_manager import get_session
from sqlalchemy import text

async def swap():
    async with get_session() as session:
        await session.execute(text(\"UPDATE core.cognitive_roles SET assigned_resource = 'anthropic_claude_sonnet' WHERE role = 'Coder'\"))
        await session.commit()
        print('🧠 Coder is now: Claude 3.5 Sonnet')

asyncio.run(swap())
"
