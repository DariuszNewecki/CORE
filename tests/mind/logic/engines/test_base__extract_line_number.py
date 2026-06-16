"""Tests for ``mind.logic.engines.base.extract_line_number`` (#548).

The helper centralizes line-number extraction so AuditFindings carry the
correct ``line_number`` field for GitHub inline annotations, regardless
of whether the originating engine emitted a structured dict with a
``line``/``line_number`` key or a bare string with ``"Line N:"`` embedded
in the message.
"""

from __future__ import annotations

import pytest

from mind.logic.engines.base import extract_line_number


# ID: d681458a-e34f-43b8-898f-093a6aedc279
def test_structured_line_number_key_preferred() -> None:
    """``details["line_number"]`` (canonical) takes priority over message
    text — structured signal is always more reliable than regex."""
    out = extract_line_number(
        message="Line 99: some violation", details={"line_number": 42}
    )
    assert out == 42


# ID: e16821f8-229b-4095-b5a1-a298f7705031
def test_structured_line_alias_when_no_canonical() -> None:
    """``details["line"]`` is recognized as a sensor alias for older
    detail-emitting engines that pre-date the canonical key.
    """
    out = extract_line_number(message="anything", details={"line": 17})
    assert out == 17


# ID: 5eba1552-f00c-4378-a4df-271354e06423
def test_message_regex_fallback_capital_line() -> None:
    """``"Line N: ..."`` is the dominant pattern in legacy engine messages;
    extracted when no structured detail is present.
    """
    out = extract_line_number(
        message="Line 229: Forbidden primitive 'subprocess.run' used.", details=None
    )
    assert out == 229


# ID: 71d54445-eb87-4c22-8832-16b0df600476
def test_message_regex_fallback_lowercase_line() -> None:
    """Tail-form ``"(line N)"`` and other lowercase variants — common in
    some engines — are also picked up by the same regex.
    """
    out = extract_line_number(
        message="Forbidden primitive 'subprocess.run' used (line 229).",
        details={},
    )
    assert out == 229


# ID: 07baa021-8814-4960-af00-d44d15dd0745
def test_no_line_info_returns_none() -> None:
    """Message has no embedded line and details carries no key → None.
    Consumers pass that through to ``AuditFinding.line_number=None``
    (the documented "no info available" sentinel — the field's existing
    default behaviour).
    """
    out = extract_line_number(
        message="Module-level violation; no specific line.", details={}
    )
    assert out is None


# ID: 2e866e99-2201-4c93-80eb-624778bdad3b
def test_string_typed_structured_key_accepted() -> None:
    """Some sensors stringify the line number in their details dict.
    The helper accepts numeric strings ('229') to avoid forcing every
    sensor to int-cast at emit time.
    """
    out = extract_line_number(message="anything", details={"line_number": "229"})
    assert out == 229


def test_first_line_match_wins_when_multiple_in_message() -> None:
    """If the message text mentions multiple lines (e.g. cross-reference
    'Line 12 conflicts with the definition at Line 7'), the first match
    is treated as the violation's primary anchor.
    """
    out = extract_line_number(
        message="Line 12 conflicts with the definition at Line 7.", details=None
    )
    assert out == 12


def test_invalid_structured_value_falls_through_to_regex() -> None:
    """``details["line_number"]`` is the canonical key, but a malformed
    value (zero, negative, non-numeric string) must NOT shadow a valid
    embedded line in the message — fall through to the regex.
    """
    out = extract_line_number(
        message="Line 88: violation", details={"line_number": "not-a-number"}
    )
    assert out == 88
    out = extract_line_number(message="Line 88: violation", details={"line_number": 0})
    assert out == 88


def test_zero_in_message_is_ignored() -> None:
    """A literal ``"Line 0"`` in a message is treated as no-info — line
    numbers are 1-indexed in editor surfaces.
    """
    out = extract_line_number(message="Line 0: ambiguous", details=None)
    assert out is None


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
