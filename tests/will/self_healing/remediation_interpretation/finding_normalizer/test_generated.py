from __future__ import annotations

from unittest.mock import MagicMock

from will.self_healing.remediation_interpretation.finding_normalizer import (
    FindingNormalizer,
)


# ID: 7ff5a7c5-be93-40b3-8439-33658e2f9090
def test_FindingNormalizer_normalize() -> None:
    normalizer = FindingNormalizer()

    normalized_a = MagicMock(name="normalized_a")
    normalized_b = MagicMock(name="normalized_b")
    normalized_c = MagicMock(name="normalized_c")

    normalizer.normalize_one = MagicMock(
        side_effect=[normalized_b, normalized_a, normalized_c]
    )
    normalizer._sort_key = MagicMock(
        side_effect=lambda item: {
            normalized_a: 1,
            normalized_b: 2,
            normalized_c: 3,
        }[item]
    )

    findings = [{"raw": "b"}, {"raw": "a"}, {"raw": "c"}]
    result = normalizer.normalize(findings)

    assert result == [normalized_a, normalized_b, normalized_c]
    assert normalizer.normalize_one.call_count == 3
    assert [
        call.args[0] for call in normalizer.normalize_one.call_args_list
    ] == findings
