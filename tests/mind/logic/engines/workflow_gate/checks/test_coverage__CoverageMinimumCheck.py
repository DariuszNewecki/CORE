"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/logic/engines/workflow_gate/checks/coverage.py
- Symbol: CoverageMinimumCheck
- Generated: 2026-01-11 02:39:56
- 2026-06-07 (#572 Cat B batch 9):
    * CoverageMinimumCheck.__init__ now takes path_resolver. Added a
      path_resolver fixture used by all tests.
    * Config-loading boundary moved: source reads via
      ``self._paths.policy("operations")``, not ``settings.paths.policy(...)``.
      The autogen vintage's patches against
      ``mind.logic.engines.workflow_gate.checks.coverage.settings`` are
      no-ops because the module no longer imports ``settings``. Each test
      now controls the resolved Path via path_resolver.policy.return_value
      and patches Path.exists / Path.read_text where needed.
    * Default-fallback value: source falls through to
      ``_CFG.gap_threshold_pct`` (module-level constant from
      ``load_operational_config().coverage``), which resolves to 75.0 in
      this repo — preserving the autogen literal but for a different
      reason than the autogen assumed.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mind.logic.engines.workflow_gate.checks.coverage import CoverageMinimumCheck


@pytest.fixture
def path_resolver():
    """MagicMock satisfying the PathResolver attribute surface the check
    consumes: a ``.policy(policy_id)`` method returning a Path. Each test
    sets ``path_resolver.policy.return_value`` to the Path it wants the
    config-load logic to see."""
    return MagicMock()


class TestCoverageMinimumCheck:
    def test_init(self, path_resolver):
        """Basic initialization."""
        check = CoverageMinimumCheck(path_resolver=path_resolver)
        assert check.check_type == "coverage_minimum"

    def test_load_coverage_threshold_default(self, path_resolver):
        """Default threshold (75.0) — assertion preserved through the
        method-mock indirection from the autogen vintage; the substantive
        behavior is covered by test_load_coverage_threshold_config_file_not_exists
        below."""
        check = CoverageMinimumCheck(path_resolver=path_resolver)
        with patch.object(check, "_load_coverage_threshold") as mock_load:
            mock_load.return_value = 75.0
            result = check._load_coverage_threshold()
            assert result == 75.0

    def test_load_coverage_threshold_from_config(self, path_resolver):
        """Threshold loaded from the operations policy file when it exists
        and parses cleanly to the expected schema."""
        check = CoverageMinimumCheck(path_resolver=path_resolver)
        path_resolver.policy.return_value = Path("/fake/path")
        mock_config_data = {
            "quality_assurance": {"coverage_requirements": {"minimum_threshold": 90.5}}
        }
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=json.dumps(mock_config_data)),
        ):
            assert check._load_coverage_threshold() == 90.5

    def test_load_coverage_threshold_config_missing_keys(self, path_resolver):
        """When the loaded JSON lacks the expected schema keys, source's
        chained .get(...) defaults take over and the value resolves to 75."""
        check = CoverageMinimumCheck(path_resolver=path_resolver)
        path_resolver.policy.return_value = Path("/fake/path")
        mock_config_data = {"quality_assurance": {"other_setting": "value"}}
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=json.dumps(mock_config_data)),
        ):
            assert check._load_coverage_threshold() == 75.0

    def test_load_coverage_threshold_config_file_not_exists(self, path_resolver):
        """When the operations policy file doesn't exist, source falls
        through to ``_CFG.gap_threshold_pct`` which resolves to 75.0 in
        this repo."""
        check = CoverageMinimumCheck(path_resolver=path_resolver)
        path_resolver.policy.return_value = Path("/fake/path")
        with patch("pathlib.Path.exists", return_value=False):
            assert check._load_coverage_threshold() == 75.0

    def test_load_coverage_threshold_config_corrupted(self, path_resolver):
        """When the policy file exists but read_text raises (e.g. corrupted
        bytes / IOError), source's broad except suppresses and the
        ``_CFG.gap_threshold_pct`` fallback resolves to 75.0."""
        check = CoverageMinimumCheck(path_resolver=path_resolver)
        path_resolver.policy.return_value = Path("/fake/path")
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", side_effect=Exception("Corrupted JSON")),
        ):
            assert check._load_coverage_threshold() == 75.0


@pytest.mark.asyncio
async def test_async_verify_with_explicit_coverage(path_resolver):
    """Async verify with explicit coverage parameter at or above threshold
    returns an empty violations list."""
    check = CoverageMinimumCheck(path_resolver=path_resolver)
    with patch.object(check, "_load_coverage_threshold", return_value=75.0):
        params = {"current_coverage": 80.0}
        result = await check.verify(None, params)
        assert result == []
