from __future__ import annotations

from unittest.mock import MagicMock, patch

from will.self_healing.remediation_pattern_matcher import RemediationPatternMatcher


# ID: 1517cbf4-0ed2-44b1-ab92-0d03ff8cb774
def test_RemediationPatternMatcher_match():
    with patch.object(RemediationPatternMatcher, "_load_fix_patterns", return_value={}):
        matcher = RemediationPatternMatcher()

    finding = MagicMock()
    finding.check_id = "CHECK_001"

    pattern = MagicMock()
    pattern.confidence = 0.95
    pattern.risk_level = "low"

    mode = MagicMock()

    with (
        patch.object(
            matcher, "_find_matching_pattern", return_value=pattern
        ) as mock_find,
        patch.object(matcher, "_is_allowed", return_value=True) as mock_allowed,
    ):
        matched, unmatched = matcher.match([finding], mode, target_pattern="PAT_1")

    mock_find.assert_called_once_with("CHECK_001", "PAT_1")
    mock_allowed.assert_called_once_with(pattern, mode)

    assert len(matched) == 1
    assert unmatched == []
    result = matched[0]
    assert result.finding is finding
    assert result.pattern is pattern
    assert result.confidence == 0.95
    assert result.risk_level == "low"




# ID: 8c74454b-ce62-47d3-a666-c9839bb53e14
def test_RemediationPatternMatcher():
    from will.self_healing.remediation_pattern_matcher import (
        RemediationMode,
        RemediationPatternMatcher,
    )

    matcher = RemediationPatternMatcher()
    assert len(matcher.patterns) >= 1

    finding = MagicMock()
    finding.check_id = "style.import_order"

    matched, unmatched = matcher.match([finding], RemediationMode.SAFE_ONLY)

    assert len(matched) == 1
    assert len(unmatched) == 0
    assert matched[0].finding is finding
    assert matched[0].pattern.check_id_pattern == "style.import_order"
    assert matched[0].confidence == matched[0].pattern.confidence
