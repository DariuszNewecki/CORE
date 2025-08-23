# tests/admin/test_guard_drift_cli.py
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from system.admin import app

runner = CliRunner()


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_guard_drift_clean_repo(tmp_path: Path):
    """Tests a clean state where code and manifest are in sync."""
    write(
        tmp_path / ".intent/knowledge/source_structure.yaml",
        "structure:\n  - domain: main\n    path: src/main",
    )
    write(
        tmp_path / "src/main/manifest.yaml",
        "capabilities:\n  - alpha.cap\n  - beta.cap",
    )
    write(
        tmp_path / "src/main/mod.py",
        "# CAPABILITY: alpha.cap\n# CAPABILITY: beta.cap\n",
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
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    report = json.loads(out.read_text())
    assert not report["missing_in_code"]
    assert not report["undeclared_in_manifest"]


def test_guard_drift_detects_undeclared(tmp_path: Path):
    """Tests that a capability in code but not in a manifest is detected."""
    write(
        tmp_path / ".intent/knowledge/source_structure.yaml",
        "structure:\n  - domain: main\n    path: src/main",
    )
    write(tmp_path / "src/main/manifest.yaml", "capabilities:\n  - alpha.cap")
    (tmp_path / "src/main").mkdir(parents=True, exist_ok=True)
    write(
        tmp_path / "src/main/mod.py",
        "# CAPABILITY: alpha.cap\n# CAPABILITY: ghost.cap\n",
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
            "--fail-on",
            "any",
        ],
    )

    assert result.exit_code == 2
    report = json.loads(result.output)
    assert "ghost.cap" in report["undeclared_in_manifest"]


def test_guard_drift_strict_requires_kg(tmp_path: Path):
    """Tests that strict mode fails if the KnowledgeGraphBuilder is not available (simulated)."""
    write(
        tmp_path / ".intent/knowledge/source_structure.yaml",
        "structure:\n  - domain: main\n    path: src/main",
    )
    write(tmp_path / "src/main/manifest.yaml", "capabilities: []")

    result = runner.invoke(
        app,
        ["guard", "drift", "--root", str(tmp_path), "--strict-intent"],
    )

    assert result.exit_code != 0
    assert "Strict intent mode" in str(result.exception)


def test_guard_drift_detects_mismatched_mappings(tmp_path: Path):
    """
    Confirms that the system now correctly detects metadata mismatches.
    This test is the inverse of the old, obsolete one.
    """
    # Arrange
    write(
        tmp_path / ".intent/knowledge/source_structure.yaml",
        "structure:\n  - domain: main\n    path: src/main",
    )
    # The manifest declares a capability with specific metadata.
    write(
        tmp_path / "src/main/manifest.yaml",
        "capabilities:\n  beta.cap:\n    domain: main\n    owner: dev_team",
    )
    # The code has the same capability but with different or missing metadata.
    (tmp_path / "src/main").mkdir(parents=True, exist_ok=True)
    write(
        tmp_path / "src/main/mod.py",
        "# CAPABILITY: beta.cap [domain=governance]\n",
    )

    # Act
    result = runner.invoke(
        app, ["guard", "drift", "--root", str(tmp_path), "--format", "json"]
    )

    # Assert: This should now FAIL with exit code 2 because drift is detected.
    assert result.exit_code == 2
    report = json.loads(result.output)
    assert report["mismatched_mappings"]
    assert report["mismatched_mappings"][0]["capability"] == "beta.cap"
