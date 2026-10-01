from __future__ import annotations

from unittest.mock import MagicMock

from mind.logic.engines.attestation_gate import AttestationGateEngine


# ID: e63d4c62-f9f1-49ae-afed-9cf0358d7a05
async def test_AttestationGateEngine_verify_context() -> None:
    engine = MagicMock(spec=AttestationGateEngine)
    engine.engine_id = "attestation_gate"

    context = MagicMock()
    params = {"prompt": "Confirm the deployment is approved", "reference": "ADR-113"}

    findings = await AttestationGateEngine.verify_context(engine, context, params)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.check_id == "attestation_gate"
    assert "HUMAN ATTESTATION REQUIRED" in finding.message
    assert "Confirm the deployment is approved" in finding.message
    assert finding.context["finding_type"] == "REQUIRES_ATTESTATION"
    assert finding.context["attestation_prompt"] == "Confirm the deployment is approved"
    assert finding.context["reference"] == "ADR-113"


from pathlib import Path

import pytest


@pytest.mark.asyncio
# ID: a1d70697-b21c-432a-b970-ac662b26d23e
async def test_attestation_gate_engine_verify():
    engine = AttestationGateEngine()
    result = await engine.verify(Path("/tmp/nonexistent_file.py"), {})
    assert result.ok is True
    assert result.violations == []
    assert result.engine_id == engine.engine_id
