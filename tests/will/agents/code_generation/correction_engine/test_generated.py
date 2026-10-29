from __future__ import annotations

from unittest.mock import MagicMock

from will.agents.code_generation.correction_engine import CorrectionEngine


# ID: 1be9adc3-7c65-4c75-bcd0-b8418421e0ed
def test_CorrectionEngine():
    cognitive_service = MagicMock()
    auditor_context = MagicMock()
    tracer = MagicMock()

    engine = CorrectionEngine(
        cognitive_service=cognitive_service,
        auditor_context=auditor_context,
        tracer=tracer,
    )

    assert engine.cognitive_service is cognitive_service
    assert engine.auditor_context is auditor_context
    assert engine.tracer is tracer
