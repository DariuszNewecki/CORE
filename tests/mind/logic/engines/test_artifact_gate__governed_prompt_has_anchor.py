"""Tests for the governed_prompt_has_anchor check in artifact_gate.

Verifies that:
  - A governed prompt with adr_anchor passes.
  - A governed prompt without adr_anchor produces a violation.
  - A non-governed prompt silently passes (anchor not required).
  - A missing governed_prompts.yaml produces an error result.
"""

from __future__ import annotations

from pathlib import Path

from mind.logic.engines.artifact_gate import ArtifactGateEngine


_GOVERNED_PROMPTS_YAML = """\
governed_prompts:
  - name: governed_test_prompt
    anchors: ["ADR-134:D1"]
    rationale: Test fixture for governed_prompt_has_anchor check.
"""

_MANIFEST_WITH_ANCHOR = {
    "role": "coder",
    "adr_anchor": "ADR-134:D1",
}

_MANIFEST_WITHOUT_ANCHOR = {
    "role": "coder",
}


def _scaffold_repo(tmp_path: Path, *, with_governed_yaml: bool = True) -> Path:
    """Build the minimal tree the check function needs.

    Layout::

        <tmp_path>/
          .intent/enforcement/config/governed_prompts.yaml   (optional)
          .specs/                                             (existence marker)
          var/prompts/<prompt_name>/model.yaml                (caller writes)
    """
    (tmp_path / ".intent" / "enforcement" / "config").mkdir(parents=True)
    (tmp_path / ".specs").mkdir()

    if with_governed_yaml:
        governed = (
            tmp_path / ".intent" / "enforcement" / "config" / "governed_prompts.yaml"
        )
        governed.write_text(_GOVERNED_PROMPTS_YAML, encoding="utf-8")

    return tmp_path


def _prompt_model_yaml(repo_root: Path, prompt_name: str) -> Path:
    """Return the path for a prompt's model.yaml (does not create the file)."""
    path = repo_root / "var" / "prompts" / prompt_name / "model.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


# ID: 91b8cb03-a86f-4fb0-a98c-72efc0a7f890
def test_governed_prompt_with_anchor_passes(tmp_path: Path) -> None:
    """Governed prompt whose model.yaml carries adr_anchor is compliant."""
    repo = _scaffold_repo(tmp_path)
    model_yaml = _prompt_model_yaml(repo, "governed_test_prompt")
    model_yaml.write_text("role: coder\nadr_anchor: 'ADR-134:D1'\n", encoding="utf-8")

    import yaml

    manifest = yaml.safe_load(model_yaml.read_text())

    engine = ArtifactGateEngine()
    result = engine._check_governed_prompt_has_anchor(model_yaml, manifest)

    assert result.ok is True
    assert result.violations == []


# ID: 1cb31379-ea00-4f4d-a7f3-9e03722de4c0
def test_governed_prompt_without_anchor_violates(tmp_path: Path) -> None:
    """Governed prompt missing adr_anchor produces a violation."""
    repo = _scaffold_repo(tmp_path)
    model_yaml = _prompt_model_yaml(repo, "governed_test_prompt")
    model_yaml.write_text("role: coder\n", encoding="utf-8")

    import yaml

    manifest = yaml.safe_load(model_yaml.read_text())

    engine = ArtifactGateEngine()
    result = engine._check_governed_prompt_has_anchor(model_yaml, manifest)

    assert result.ok is False
    assert len(result.violations) == 1
    assert "governed_test_prompt" in result.violations[0]
    assert "adr_anchor" in result.violations[0]


# ID: 64065009-b28b-41ec-862a-735f25f5d1cc
def test_ungoverned_prompt_silently_passes(tmp_path: Path) -> None:
    """Prompt not listed in governed_prompts.yaml passes without adr_anchor."""
    repo = _scaffold_repo(tmp_path)
    model_yaml = _prompt_model_yaml(repo, "some_ungoverned_prompt")
    model_yaml.write_text("role: coder\n", encoding="utf-8")

    import yaml

    manifest = yaml.safe_load(model_yaml.read_text())

    engine = ArtifactGateEngine()
    result = engine._check_governed_prompt_has_anchor(model_yaml, manifest)

    assert result.ok is True
    assert result.violations == []


# ID: f1286c47-1ce4-48c9-bd6d-0fafcf5e7381
def test_missing_governed_prompts_yaml_returns_error(tmp_path: Path) -> None:
    """Absent governed_prompts.yaml produces an error (ok=False) result."""
    repo = _scaffold_repo(tmp_path, with_governed_yaml=False)
    model_yaml = _prompt_model_yaml(repo, "governed_test_prompt")
    model_yaml.write_text("role: coder\n", encoding="utf-8")

    import yaml

    manifest = yaml.safe_load(model_yaml.read_text())

    engine = ArtifactGateEngine()
    result = engine._check_governed_prompt_has_anchor(model_yaml, manifest)

    assert result.ok is False
    assert any("governed_prompts.yaml" in v for v in result.violations)


# ID: dbe122d5-7ef5-4179-9eee-9969c2c08e81
def test_verify_dispatches_governed_prompt_has_anchor(tmp_path: Path) -> None:
    """ArtifactGateEngine.verify() dispatches governed_prompt_has_anchor correctly."""
    import asyncio

    repo = _scaffold_repo(tmp_path)
    model_yaml = _prompt_model_yaml(repo, "governed_test_prompt")
    model_yaml.write_text("role: coder\nadr_anchor: 'ADR-134:D1'\n", encoding="utf-8")

    engine = ArtifactGateEngine()
    result = asyncio.run(
        engine.verify(model_yaml, {"check_type": "governed_prompt_has_anchor"})
    )

    assert result.ok is True
