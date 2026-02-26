# tests/governance/test_local_mode_governance.py
"""
Tests to ensure that CORE's governance principles are correctly
reflected in its configuration files.
"""

from shared.config_loader import load_yaml_file


def test_local_fallback_requires_git_checkpoint(tmp_path, monkeypatch):
    """
    Ensure local_mode.yaml correctly enforces Git validation.
    """
    # Create test structure
    config_dir = tmp_path / ".intent" / "mind" / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    config_path = config_dir / "local_mode.yaml"
    config_path.write_text(
        """
mode: local_fallback
apis:
  llm:
    enabled: false
    fallback: local_validator
  git:
    ignore_validation: false

dev_fastpath: true
"""
    )

    # Load and verify
    config = load_yaml_file(config_path)

    # This is a critical safety check: local mode must not bypass Git commits
    ignore_validation = config.get("apis", {}).get("git", {}).get("ignore_validation")
    assert ignore_validation is False, (
        "CRITICAL: local_mode.yaml is configured to ignore Git validation."
    )
