# tests/governance/test_local_mode_governance.py
"""
Tests to ensure that CORE's governance principles are correctly
reflected in its configuration files.
"""
from shared.config_loader import load_config
from shared.path_utils import get_repo_root


def test_local_fallback_requires_git_checkpoint():
    """Ensure local_mode.yaml correctly enforces Git validation."""
    repo_root = get_repo_root()
    config_path = repo_root / ".intent" / "config" / "local_mode.yaml"

    # Check that the file actually exists before testing its content
    assert config_path.exists(), "local_mode.yaml configuration file is missing."

    config = load_config(config_path)

    # This is a critical safety check: local mode must not bypass Git commits.
    ignore_validation = config.get("apis", {}).get("git", {}).get("ignore_validation")
    assert (
        ignore_validation is False
    ), "CRITICAL: local_mode.yaml is configured to ignore Git validation."
