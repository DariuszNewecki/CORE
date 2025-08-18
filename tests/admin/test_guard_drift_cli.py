# tests/admin/test_guard_drift_cli.py
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from system.admin import app  # uses core-admin entrypoint

runner = CliRunner()


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def domain_manifest_yaml(domain: str, capabilities: list[str]):
    """Helper to create a domain-specific manifest file content."""
    return yaml.safe_dump(
        {"domain": domain, "capabilities": capabilities}, sort_keys=False
    )


@pytest.fixture
def drift_test_repo(tmp_path: Path) -> Path:
    """Creates a temporary repository with the basic constitutional files needed for drift tests."""
    # Create the source_structure.yaml to map files to domains
    write(
        tmp_path / ".intent/knowledge/source_structure.yaml",
        yaml.safe_dump(
            {
                "structure": [
                    {"domain": "domain_alpha", "path": "src/domain_alpha"},
                    {"domain": "domain_beta", "path": "src/domain_beta"},
                ]
            }
        ),
    )
    # Boilerplate files for correct KGB initialization
    write(tmp_path / ".intent/knowledge/entry_point_patterns.yaml", "patterns: []")
    write(tmp_path / "pyproject.toml", "[tool.poetry]\nname = 'test-project'")
    return tmp_path


def test_guard_drift_clean_repo(drift_test_repo: Path):
    """Tests that a clean repository with modular manifests passes the drift check."""
    tmp_path = drift_test_repo
    out = tmp_path / "reports" / "drift_report.json"

    write(
        tmp_path / "src" / "domain_alpha" / "mod.py",
        "# CAPABILITY: alpha.cap\ndef alpha_func(): pass",
    )
    write(
        tmp_path / "src" / "domain_beta" / "mod.py",
        "# CAPABILITY: beta.cap\ndef beta_func(): pass",
    )
    write(
        tmp_path / "src" / "domain_alpha" / "manifest.yaml",
        domain_manifest_yaml("domain_alpha", ["alpha.cap"]),
    )
    write(
        tmp_path / "src" / "domain_beta" / "manifest.yaml",
        domain_manifest_yaml("domain_beta", ["beta.cap"]),
    )

    result = runner.invoke(
        app,
        [
            "guard",
            "drift",
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    report = json.loads(out.read_text(encoding="utf-8"))
    assert not report["missing_in_code"]
    assert not report["undeclared_in_manifest"]
    assert not report["mismatched_mappings"]


def test_guard_drift_detects_undeclared(drift_test_repo: Path):
    """Tests that a capability in code but not in any manifest is detected."""
    tmp_path = drift_test_repo
    write(
        tmp_path / "src" / "domain_alpha" / "manifest.yaml",
        domain_manifest_yaml("domain_alpha", ["alpha.cap"]),
    )
    write(
        tmp_path / "src" / "domain_alpha" / "mod.py",
        "# CAPABILITY: alpha.cap\ndef alpha_func(): pass\n\n# CAPABILITY: ghost.cap\ndef ghost_func(): pass",
    )
    out = tmp_path / "reports" / "drift_report.json"

    result = runner.invoke(
        app,
        [
            "guard",
            "drift",
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--fail-on",
            "any",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 2, result.output
    report = json.loads(out.read_text(encoding="utf-8"))
    assert "ghost.cap" in report["undeclared_in_manifest"]
    assert len(report["mismatched_mappings"]) == 0


def test_guard_drift_detects_mismatched_domain(drift_test_repo: Path):
    """Tests that a capability in the wrong domain is detected as a mismatch."""
    tmp_path = drift_test_repo
    write(
        tmp_path / "src" / "domain_alpha" / "manifest.yaml",
        domain_manifest_yaml("domain_alpha", ["beta.cap"]),
    )
    write(
        tmp_path / "src" / "domain_beta" / "mod.py",
        "# CAPABILITY: beta.cap\ndef beta_func(): pass",
    )
    out = tmp_path / "reports" / "drift_report.json"

    result = runner.invoke(
        app,
        [
            "guard",
            "drift",
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--fail-on",
            "any",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 2, result.output
    report = json.loads(out.read_text(encoding="utf-8"))
    assert not report["missing_in_code"]
    assert not report["undeclared_in_manifest"]
    assert any(m.get("capability") == "beta.cap" for m in report["mismatched_mappings"])
