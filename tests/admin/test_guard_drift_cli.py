# tests/admin/test_guard_drift_cli.py
from __future__ import annotations

import json
from pathlib import Path

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


def test_guard_drift_clean_repo(tmp_path: Path):
    """Tests that a clean repository with modular manifests passes the drift check."""
    # Arrange: Create domain-specific manifests that match the code
    write(
        tmp_path / "src" / "domain_alpha" / "manifest.yaml",
        domain_manifest_yaml("domain_alpha", ["alpha.cap"]),
    )
    write(
        tmp_path / "src" / "domain_beta" / "manifest.yaml",
        domain_manifest_yaml("domain_beta", ["beta.cap"]),
    )
    write(
        tmp_path / "src" / "domain_alpha" / "mod.py", "# CAPABILITY: alpha.cap"
    )
    write(
        tmp_path / "src" / "domain_beta" / "mod.py", "# CAPABILITY: beta.cap"
    )
    out = tmp_path / "reports" / "drift_report.json"

    result = runner.invoke(
        app,
        [
            "guard", "drift", "--root", str(tmp_path), "--format", "json", "--output", str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    report = json.loads(out.read_text(encoding="utf-8"))
    assert not report["missing_in_code"]
    assert not report["undeclared_in_manifest"]
    assert not report["mismatched_mappings"]


def test_guard_drift_detects_undeclared(tmp_path: Path):
    """Tests that a capability in code but not in any manifest is detected."""
    write(
        tmp_path / "src" / "domain_alpha" / "manifest.yaml",
        domain_manifest_yaml("domain_alpha", ["alpha.cap"]),
    )
    write(
        tmp_path / "src" / "domain_alpha" / "mod.py",
        "# CAPABILITY: alpha.cap\n# CAPABILITY: ghost.cap\n",
    )
    out = tmp_path / "reports" / "drift_report.json"

    result = runner.invoke(
        app,
        [
            "guard", "drift", "--root", str(tmp_path), "--format", "json", "--fail-on", "any", "--output", str(out),
        ],
    )

    assert result.exit_code == 2
    report = json.loads(out.read_text(encoding="utf-8"))
    assert "ghost.cap" in report["undeclared_in_manifest"]


def test_guard_drift_detects_mismatched_domain(tmp_path: Path):
    """Tests that a capability in the wrong domain is detected as a mismatch."""
    # Arrange: beta.cap is declared in domain_alpha's manifest...
    write(
        tmp_path / "src" / "domain_alpha" / "manifest.yaml",
        domain_manifest_yaml("domain_alpha", ["beta.cap"]),
    )
    # ...but it is implemented in a file belonging to domain_beta.
    # The KnowledgeGraphBuilder should associate it with domain_beta.
    write(
        tmp_path / ".intent/knowledge/source_structure.yaml",
        yaml.safe_dump({
            "structure": [
                {"domain": "domain_alpha", "path": "src/domain_alpha"},
                {"domain": "domain_beta", "path": "src/domain_beta"},
            ]
        })
    )
    write(
        tmp_path / "src" / "domain_beta" / "mod.py",
        "# CAPABILITY: beta.cap",
    )
    out = tmp_path / "reports" / "drift_report.json"

    result = runner.invoke(
        app,
        [
            "guard", "drift", "--root", str(tmp_path), "--format", "json", "--output", str(out),
        ],
    )

    assert result.exit_code == 2
    report = json.loads(out.read_text(encoding="utf-8"))
    assert not report["missing_in_code"]
    assert not report["undeclared_in_manifest"]
    assert any(m.get("capability") == "beta.cap" for m in report["mismatched_mappings"])
