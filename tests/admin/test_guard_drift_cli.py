# tests/admin/test_guard_drift_cli.py
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from system.admin import app  # uses core-admin entrypoint

runner = CliRunner()


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def manifest_yaml(capabilities):
    import yaml  # already a project dep

    # Prefer a top-level 'capabilities' key; adjust if your manifest uses a different key.
    data = {"capabilities": []}
    for c in capabilities:
        data["capabilities"].append(c)
    return yaml.safe_dump(data, sort_keys=False)


def test_guard_drift_clean_repo(tmp_path: Path):
    # Arrange: manifest and code agree (no meta mismatch)
    write(
        tmp_path / ".intent" / "project_manifest.yaml",
        manifest_yaml(["alpha.cap", "beta.cap"]),
    )
    write(
        tmp_path / "src" / "mod.py", "# CAPABILITY: alpha.cap\n# CAPABILITY: beta.cap\n"
    )
    out = tmp_path / "reports" / "drift_report.json"

    # Act
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

    # Assert
    assert result.exit_code == 0, result.output
    assert out.exists()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["missing_in_code"] == []
    assert report["undeclared_in_manifest"] == []
    assert report["mismatched_mappings"] == []


def test_guard_drift_detects_undeclared(tmp_path: Path):
    # Arrange: code has extra capability not in manifest
    write(tmp_path / ".intent" / "project_manifest.yaml", manifest_yaml(["alpha.cap"]))
    write(
        tmp_path / "src" / "mod.py",
        "# CAPABILITY: alpha.cap\n# CAPABILITY: ghost.cap\n",
    )
    out = tmp_path / "reports" / "drift_report.json"

    # Act
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

    # Assert
    assert result.exit_code == 2  # drift should fail the command
    assert out.exists()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert "ghost.cap" in report["undeclared_in_manifest"]


def test_guard_drift_strict_requires_kg(tmp_path: Path):
    # Arrange: no KG present; strict should fail fast instead of grepping
    write(tmp_path / ".intent" / "project_manifest.yaml", manifest_yaml([]))

    # Act
    result = runner.invoke(
        app,
        [
            "guard",
            "drift",
            "--root",
            str(tmp_path),
            "--strict-intent",
            "--format",
            "json",
        ],
    )

    # Assert
    assert result.exit_code != 0
    # Typer doesn't print the exception to stdout; check the exception message instead.
    assert result.exception is not None
    assert "Strict intent mode" in str(result.exception)


def test_guard_drift_mismatched_mappings(tmp_path: Path):
    # Arrange: same capability both sides, but code has meta that manifest does not -> mismatch
    write(tmp_path / ".intent" / "project_manifest.yaml", manifest_yaml(["beta.cap"]))
    write(
        tmp_path / "src" / "mod.py",
        "# CAPABILITY: beta.cap [domain=governance owner=ops]\n",
    )
    out = tmp_path / "reports" / "drift_report.json"

    # Act
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

    # Assert: default --fail-on any -> should fail due to mismatched_mappings
    assert result.exit_code == 2
    assert out.exists()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["missing_in_code"] == []
    assert report["undeclared_in_manifest"] == []
    assert any(m.get("capability") == "beta.cap" for m in report["mismatched_mappings"])
