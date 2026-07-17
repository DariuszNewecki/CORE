"""Unit tests for circuit_breaker.canonical_signature and config loading.

Pure functions over strings — no DB, no I/O. Asserts that volatile
substrings (timestamps, UUIDs, durations, pids) are stripped before
truncation so two failures with the same root cause but different
incidental noise produce the same signature.
"""

from __future__ import annotations

import re

from will.autonomy.circuit_breaker import (
    CircuitBreakerConfig,
    canonical_signature,
)


def _config(window: int = 200) -> CircuitBreakerConfig:
    """Build a CircuitBreakerConfig with the production volatile patterns
    compiled in — exercises the same regex set the worker would see.
    """
    patterns = [
        re.compile(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?",
            re.IGNORECASE,
        ),
        re.compile(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            re.IGNORECASE,
        ),
        re.compile(r"\d+\.\d+s", re.IGNORECASE),
        re.compile(r"pid=\d+", re.IGNORECASE),
    ]
    return CircuitBreakerConfig(
        threshold_n=5,
        signature_window_chars=window,
        max_lookback=25,
        volatile_patterns=tuple(patterns),
    )


def test_canonical_signature_empty_inputs_collapse_to_empty() -> None:
    config = _config()
    assert canonical_signature(None, config) == ""
    assert canonical_signature("", config) == ""


def test_canonical_signature_strips_iso_timestamps() -> None:
    """Two failures differing only in timestamp produce the same signature."""
    config = _config()
    a = "Action failed at 2026-05-11T14:23:01.123456+00:00 — gate refused"
    b = "Action failed at 2026-05-11T14:24:55.998877+00:00 — gate refused"
    assert canonical_signature(a, config) == canonical_signature(b, config)


def test_canonical_signature_strips_uuids() -> None:
    """Different proposal_ids in error text do not change the signature."""
    config = _config()
    a = "Proposal 4a690b87-6016-4c12-8348-607c59cf2f15 rejected by IntentGuard"
    b = "Proposal d9270451-6f81-46b8-896e-6bb473dc820f rejected by IntentGuard"
    assert canonical_signature(a, config) == canonical_signature(b, config)


def test_canonical_signature_strips_durations() -> None:
    """Different elapsed durations do not change the signature."""
    config = _config()
    a = "CoderAgent timed out after 52.8s"
    b = "CoderAgent timed out after 119.04s"
    assert canonical_signature(a, config) == canonical_signature(b, config)


def test_canonical_signature_strips_pids() -> None:
    config = _config()
    a = "Worker pid=12345 crashed during build.tests"
    b = "Worker pid=98 crashed during build.tests"
    assert canonical_signature(a, config) == canonical_signature(b, config)


def test_canonical_signature_distinguishes_genuinely_different_errors() -> None:
    """Two failures with different root causes produce different signatures."""
    config = _config()
    a = "IntentGuard refused: scope leak in fix.placeholders"
    b = "ModularitySplitter refused: imported symbol in plan"
    assert canonical_signature(a, config) != canonical_signature(b, config)


def test_canonical_signature_truncates_to_window() -> None:
    """Signature length is bounded by signature_window_chars."""
    config = _config(window=20)
    long_err = "x" * 500
    sig = canonical_signature(long_err, config)
    assert len(sig) == 20


def test_canonical_signature_collapses_whitespace() -> None:
    """Runs of whitespace introduced by stripping are normalized to single
    spaces so the truncation window is not wasted on padding.
    """
    config = _config()
    a = "Failed   on   2026-05-11T14:23:01Z   — retry"
    sig = canonical_signature(a, config)
    assert "  " not in sig
    assert sig.startswith("Failed on")
