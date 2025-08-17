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
    # Arrange: Create a realistic temporary project structure
    out = tmp_path / "reports" / "drift_report.json"

    # Create valid Python files with symbols for the KGB to find.
    write(
        tmp_path / "src" / "domain_alpha" / "mod.py",
        "# CAPABILITY: alpha.cap\ndef alpha_func(): pass",
    )
    write(
        tmp_path / "src" / "domain_beta" / "mod.py",
        "# CAPABILITY: beta.cap\ndef beta_func(): pass",
    )

    # Create the corresponding domain manifests
    write(
        tmp_path / "src" / "domain_alpha" / "manifest.yaml",
        domain_manifest_yaml("domain_alpha", ["alpha.cap"]),
    )
    write(
        tmp_path / "src" / "domain_beta" / "manifest.yaml",
        domain_manifest_yaml("domain_beta", ["beta.cap"]),
    )

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

    # Boilerplate files for correct initialization
    write(tmp_path / ".intent/knowledge/entry_point_patterns.yaml", "patterns: []")
    write(tmp_path / "pyproject.toml", "[tool.poetry]\nname = 'test-project'")

    # Act: Run the drift command on our temporary project
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

    # --- THIS IS THE DIAGNOSTIC PART ---
    # We print the raw output from the command runner.
    # The `assert False` guarantees the test fails and this output is shown in the CI logs.
    print("\n--- RAW CLI OUTPUT FOR DIAGNOSIS ---")
    print(result.output)
    print("--- END RAW CLI OUTPUT ---")
    assert result.exit_code == 0, result.output
    # --- END DIAGNOSTIC PART ---
    
    report = json.loads(out.read_text(encoding="utf-8"))
    assert not report["missing_in_code"]
    assert not report["undeclared_in_manifest"]
    assert not report["mismatched_mappings"]

# ... (the rest of the file remains the same) ...
# ... I'm omitting the other two tests for brevity, they should not be changed ...

def test_guard_drift_detects_undeclared(tmp_path: Path):
    """Tests that a capability in code but not in any manifest is detected."""
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

    assert result.exit_code == 2
    report = json.loads(out.read_text(encoding="utf-8"))
    assert "ghost.cap" in report["undeclared_in_manifest"]


def test_guard_drift_detects_mismatched_domain(tmp_path: Path):
    """Tests that a capability in the wrong domain is detected as a mismatch."""
    write(
        tmp_path / "src" / "domain_alpha" / "manifest.yaml",
        domain_manifest_yaml("domain_alpha", ["beta.cap"]),
    )
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
    write(
        tmp_path / "src" / "domain_beta" / "mod.py",
        "# CAPABILITY: beta.cap\ndef beta_func(): pass",
    )
    write(tmp_path / ".intent/knowledge/entry_point_patterns.yaml", "patterns: []")
    write(tmp_path / "pyproject.toml", "[tool.poetry]\nname = 'test-project'")
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
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 2
    report = json.loads(out.read_text(encoding="utf-8"))
    assert not report["missing_in_code"]
    assert not report["undeclared_in_manifest"]
    assert any(m.get("capability") == "beta.cap" for m in report["mismatched_mappings"])