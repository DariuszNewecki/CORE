# tests/shared/test_pagination.py

"""Unit tests for shared.pagination cursor encode/decode helpers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from shared.pagination import decode_cursor, encode_cursor


class TestEncodeCursor:
    def test_encodes_timestamp_and_key(self) -> None:
        ts = datetime(2026, 6, 28, 12, 0, 0, tzinfo=UTC)
        cursor = encode_cursor(ts, "abc-123")
        assert isinstance(cursor, str)
        assert len(cursor) > 0
        # Must be URL-safe base64 — no +, /
        assert "+" not in cursor
        assert "/" not in cursor

    def test_encodes_key_only_when_ts_is_none(self) -> None:
        cursor = encode_cursor(None, "only-key")
        assert isinstance(cursor, str)
        ts, key = decode_cursor(cursor)
        assert ts is None
        assert key == "only-key"

    def test_roundtrip_with_timestamp(self) -> None:
        ts = datetime(2026, 1, 15, 8, 30, 45, tzinfo=UTC)
        original_key = "proposal-uuid-value"
        cursor = encode_cursor(ts, original_key)
        decoded_ts, decoded_key = decode_cursor(cursor)
        assert decoded_key == original_key
        # isoformat roundtrip preserves the datetime
        assert decoded_ts is not None
        assert decoded_ts.isoformat() == ts.isoformat()

    def test_roundtrip_with_microseconds(self) -> None:
        ts = datetime(2026, 6, 28, 12, 0, 0, 123456, tzinfo=UTC)
        cursor = encode_cursor(ts, "key")
        decoded_ts, decoded_key = decode_cursor(cursor)
        assert decoded_ts is not None
        assert decoded_ts.microsecond == 123456
        assert decoded_key == "key"

    def test_different_keys_produce_different_cursors(self) -> None:
        ts = datetime(2026, 6, 28, tzinfo=UTC)
        c1 = encode_cursor(ts, "key-a")
        c2 = encode_cursor(ts, "key-b")
        assert c1 != c2

    def test_different_timestamps_produce_different_cursors(self) -> None:
        ts1 = datetime(2026, 6, 28, tzinfo=UTC)
        ts2 = datetime(2026, 6, 27, tzinfo=UTC)
        c1 = encode_cursor(ts1, "same-key")
        c2 = encode_cursor(ts2, "same-key")
        assert c1 != c2


class TestDecodeCursor:
    def test_raises_on_invalid_base64(self) -> None:
        with pytest.raises(ValueError, match="Invalid pagination cursor"):
            decode_cursor("not-valid-base64!!!")

    def test_raises_on_missing_key_field(self) -> None:
        import base64
        import json

        # Valid base64 JSON but missing "k"
        payload = base64.urlsafe_b64encode(json.dumps({"t": "2026-01-01"}).encode()).decode()
        with pytest.raises(ValueError, match="Invalid pagination cursor"):
            decode_cursor(payload)

    def test_raises_on_invalid_timestamp_format(self) -> None:
        import base64
        import json

        payload = base64.urlsafe_b64encode(
            json.dumps({"k": "x", "t": "not-a-date"}).encode()
        ).decode()
        with pytest.raises(ValueError, match="Invalid pagination cursor"):
            decode_cursor(payload)

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid pagination cursor"):
            decode_cursor("")
