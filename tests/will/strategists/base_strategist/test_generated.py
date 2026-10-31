from __future__ import annotations

from will.strategists.base_strategist import BaseStrategist


# ID: e4d8cd49-f52b-4bad-8d1a-2512effc83bf
def test_BaseStrategist_phase():
    from will.strategists.base_strategist import ComponentPhase

    strategist = BaseStrategist.__new__(BaseStrategist)

    result = strategist.phase

    assert result is ComponentPhase.RUNTIME




# ID: ead8792d-95cd-4788-b6ad-b7e711342481
def test_BaseStrategist():
    strategist = BaseStrategist()

    phase = strategist.phase

    assert phase is not None
    assert phase.name == "RUNTIME"
