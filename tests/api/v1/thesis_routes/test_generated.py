from __future__ import annotations

import asyncio

from api.v1.thesis_routes import get_thesis


# ID: 26ababaa-c384-44d9-80cc-fad71875a09b
def test_get_thesis():
    latest = {"thesis": "measured", "date": "2024-01-01"}
    result = asyncio.run(get_thesis(latest))
    assert result == latest
    assert result is latest
