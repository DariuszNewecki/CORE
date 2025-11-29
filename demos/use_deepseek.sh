#!/bin/bash
# Force the Coder role to use DeepSeek
poetry run python3 -c "
import asyncio
from services.database.session_manager import get_session
from sqlalchemy import text

async def swap():
    async with get_session() as session:
        await session.execute(text(\"UPDATE core.cognitive_roles SET assigned_resource = 'deepseek_coder' WHERE role = 'Coder'\"))
        await session.commit()
        print('🤖 Coder is now: DeepSeek V2.5')

asyncio.run(swap())
"
