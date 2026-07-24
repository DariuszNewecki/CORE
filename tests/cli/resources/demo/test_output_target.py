# tests/cli/resources/demo/test_output_target.py
"""`--output` path resolution stays inside the repo boundary (ADR-155 D12/U14)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cli.resources.demo.consequence_chain import _resolve_output_target


# ID: 99fa03ad-14a7-420e-b88f-f27337262650
def test_relative_output_resolves_with_json_companion(tmp_path: Path):
    md_rel, json_rel = _resolve_output_target(tmp_path.resolve(), "reports/demo.md")
    assert md_rel == "reports/demo.md"
    assert json_rel == "reports/demo.json"


# ID: ea364d8f-4b59-4d42-b759-d6229f4954cf
def test_absolute_inside_repo_ok(tmp_path: Path):
    root = tmp_path.resolve()
    target = root / "out" / "r.md"
    md_rel, json_rel = _resolve_output_target(root, str(target))
    assert md_rel == "out/r.md"
    assert json_rel == "out/r.json"


# ID: 139fd048-bf30-4e2e-99d1-c71641c807a5
def test_escape_outside_repo_rejected(tmp_path: Path):
    root = (tmp_path / "repo").resolve()
    root.mkdir()
    with pytest.raises(ValueError, match="outside repository boundary"):
        _resolve_output_target(root, "../escape.md")
    with pytest.raises(ValueError, match="outside repository boundary"):
        _resolve_output_target(root, "/etc/passwd.md")
