"""artifact_gate on a model.yaml whose top level is not a mapping: a finding,
not a crash (found by the ADR-177 D7 run check, #1339 PR J)."""

from __future__ import annotations

from pathlib import Path

from mind.logic.engines.artifact_gate import ArtifactGateEngine


async def test_a_non_mapping_manifest_is_a_violation(tmp_path: Path) -> None:
    manifest = tmp_path / "model.yaml"
    manifest.write_text("just a string\n")
    result = await ArtifactGateEngine().verify(manifest, {})
    assert result.ok is False
    assert result.message == "model.yaml is not a mapping"
    assert result.violations == [f"{manifest}: top level is str, not a mapping"]
