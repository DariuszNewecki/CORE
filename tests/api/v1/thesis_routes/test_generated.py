from __future__ import annotations

import asyncio

from api.v1.thesis_routes import get_thesis


# ID: 26ababaa-c384-44d9-80cc-fad71875a09b
def test_get_thesis():
    latest = {"thesis": "measured", "date": "2024-01-01"}
    result = asyncio.run(get_thesis(latest))
    assert result == latest
    assert result is latest


from api.v1.thesis_routes import ThesisResponse


# ID: 839961c4-def6-468f-adf3-5687a40ce7a2
def test_ThesisResponse():
    response = ThesisResponse(
        day="2024-01-15",
        line="line-42",
        unverified_writes=3,
        ai_share=0.75,
        waste_per_change=0.12,
        convergence=0.98,
        breaches=[{"rule": "r1", "detail": "overflow"}],
        unavailable=["ai_share"],
    )

    assert response.day == "2024-01-15"
    assert response.line == "line-42"
    assert response.unverified_writes == 3
    assert response.ai_share == 0.75
    assert response.waste_per_change == 0.12
    assert response.convergence == 0.98
    assert response.breaches == [{"rule": "r1", "detail": "overflow"}]
    assert response.unavailable == ["ai_share"]

    minimal = ThesisResponse(day="2024-01-16", line="line-43")
    assert minimal.unverified_writes is None
    assert minimal.ai_share is None
    assert minimal.waste_per_change is None
    assert minimal.convergence is None
    assert minimal.breaches == []
    assert minimal.unavailable == []
