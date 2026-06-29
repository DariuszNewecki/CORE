"""Tests for ADR-134 D1: adr_anchor field on PromptModelManifest.

Verifies that:
- adr_anchor parses from model.yaml as a string, list, or None
- A manifest without adr_anchor returns None (D2 rule: governed prompts MUST declare it)
- _parse_manifest wires the value into the returned dataclass
"""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.ai.prompt_model import PromptModel, PromptModelManifest


def _write_minimal_model_yaml(
    tmp_path: Path, extra_fields: dict | None = None
) -> Path:
    """Write a valid minimal model.yaml for testing."""
    content: dict = {
        "id": "test_prompt",
        "version": "1.0.0",
        "role": "Coder",
        "description": "Test prompt",
        "input": {"required": ["code"]},
        "output": {"format": "raw_text"},
        "success_criteria": "Returns code.",
    }
    if extra_fields:
        content.update(extra_fields)
    model_path = tmp_path / "model.yaml"
    model_path.write_text(yaml.dump(content))
    return model_path


def test_adr_anchor_absent_returns_none(tmp_path: Path) -> None:
    """A model.yaml without adr_anchor yields adr_anchor=None."""
    model_yaml = _write_minimal_model_yaml(tmp_path)
    raw = yaml.safe_load(model_yaml.read_text())
    # Access parse via PromptModel._parse_manifest (internal but deterministic)
    manifest = PromptModel._parse_manifest(raw, "test_prompt")
    assert manifest.adr_anchor is None


def test_adr_anchor_string_parsed(tmp_path: Path) -> None:
    """A scalar adr_anchor in model.yaml is returned as str."""
    model_yaml = _write_minimal_model_yaml(tmp_path, {"adr_anchor": "ADR-134"})
    raw = yaml.safe_load(model_yaml.read_text())
    manifest = PromptModel._parse_manifest(raw, "test_prompt")
    assert manifest.adr_anchor == "ADR-134"
    assert isinstance(manifest.adr_anchor, str)


def test_adr_anchor_list_parsed(tmp_path: Path) -> None:
    """A list adr_anchor in model.yaml is returned as list[str]."""
    model_yaml = _write_minimal_model_yaml(
        tmp_path, {"adr_anchor": ["ADR-003", "ADR-134:D1"]}
    )
    raw = yaml.safe_load(model_yaml.read_text())
    manifest = PromptModel._parse_manifest(raw, "test_prompt")
    assert manifest.adr_anchor == ["ADR-003", "ADR-134:D1"]
    assert isinstance(manifest.adr_anchor, list)


def test_adr_anchor_field_on_dataclass() -> None:
    """PromptModelManifest accepts adr_anchor and exposes it."""
    m = PromptModelManifest(
        id="x",
        version="1.0.0",
        role="Coder",
        description="",
        required_inputs=[],
        optional_inputs=[],
        output_format="raw_text",
        output_max_length=0,
        output_must_contain=[],
        output_must_not_contain=[],
        output_json_schema=None,
        model_preference="",
        model_max_tokens=1024,
        temperature=None,
        success_criteria="",
        scope_layers=[],
        adr_anchor="ADR-025",
    )
    assert m.adr_anchor == "ADR-025"


def test_adr_anchor_none_in_dataclass() -> None:
    """PromptModelManifest defaults adr_anchor to None."""
    m = PromptModelManifest(
        id="x",
        version="1.0.0",
        role="Coder",
        description="",
        required_inputs=[],
        optional_inputs=[],
        output_format="raw_text",
        output_max_length=0,
        output_must_contain=[],
        output_must_not_contain=[],
        output_json_schema=None,
        model_preference="",
        model_max_tokens=1024,
        temperature=None,
        success_criteria="",
        scope_layers=[],
    )
    assert m.adr_anchor is None
