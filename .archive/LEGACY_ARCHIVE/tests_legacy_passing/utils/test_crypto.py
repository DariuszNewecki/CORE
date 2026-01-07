# tests/shared/utils/test_crypto.py
import json
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives import hashes

from src.shared.utils.crypto import _get_canonical_payload, generate_approval_token


class TestGetCanonicalPayload:
    """Tests for _get_canonical_payload internal function."""

    def test_get_canonical_payload_basic_proposal(self):
        """Test canonical payload with basic proposal data."""
        proposal = {
            "target_path": "/some/path",
            "action": "create_file",
            "justification": "Test justification",
            "content": "file content",
        }
        result = _get_canonical_payload(proposal)

        # Should be a JSON string with sorted keys
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed == {
            "action": "create_file",
            "content": "file content",
            "justification": "Test justification",
            "target_path": "/some/path",
        }
        # Verify keys are sorted
        keys = list(json.loads(result).keys())
        assert keys == sorted(keys)

    def test_get_canonical_payload_missing_optional_fields(self):
        """Test canonical payload when optional fields are missing."""
        proposal = {
            "target_path": "/some/path",
            "action": "create_file",
            # missing justification and content
        }
        result = _get_canonical_payload(proposal)
        parsed = json.loads(result)
        assert parsed == {
            "action": "create_file",
            "content": "",  # default empty string
            "justification": None,  # missing becomes None
            "target_path": "/some/path",
        }

    def test_get_canonical_payload_ignores_extra_fields(self):
        """Test that extra fields are ignored in canonical payload."""
        proposal = {
            "target_path": "/some/path",
            "action": "create_file",
            "justification": "test",
            "content": "content",
            "signature": "should-be-ignored",
            "timestamp": "should-be-ignored",
            "author": "should-be-ignored",
        }
        result = _get_canonical_payload(proposal)
        parsed = json.loads(result)
        # Only the core fields should be included
        assert set(parsed.keys()) == {
            "target_path",
            "action",
            "justification",
            "content",
        }
        assert "signature" not in parsed
        assert "timestamp" not in parsed
        assert "author" not in parsed

    def test_get_canonical_payload_empty_content(self):
        """Test canonical payload with empty content."""
        proposal = {
            "target_path": "/some/path",
            "action": "create_file",
            "justification": "test",
            "content": "",  # explicitly empty
        }
        result = _get_canonical_payload(proposal)
        parsed = json.loads(result)
        assert parsed["content"] == ""


class TestGenerateApprovalToken:
    """Tests for generate_approval_token function."""

    def test_generate_approval_token_basic(self):
        """Test generating approval token with basic proposal."""
        proposal = {
            "target_path": "/test/path",
            "action": "create_file",
            "justification": "Test justification",
            "content": "Test content",
        }

        result = generate_approval_token(proposal)

        # Should start with the expected prefix
        assert result.startswith("core-proposal-v6:")
        # Should be a hex string after the prefix
        hex_part = result.split(":")[1]
        assert len(hex_part) == 64  # SHA256 produces 64-character hex
        assert all(c in "0123456789abcdef" for c in hex_part)

    def test_generate_approval_token_deterministic(self):
        """Test that the same proposal produces the same token."""
        proposal = {
            "target_path": "/test/path",
            "action": "create_file",
            "justification": "Test",
            "content": "Content",
        }

        token1 = generate_approval_token(proposal)
        token2 = generate_approval_token(proposal)

        assert token1 == token2

    def test_generate_approval_token_different_content_different_tokens(self):
        """Test that different content produces different tokens."""
        proposal1 = {
            "target_path": "/test/path",
            "action": "create_file",
            "justification": "Test",
            "content": "Content1",
        }
        proposal2 = {
            "target_path": "/test/path",
            "action": "create_file",
            "justification": "Test",
            "content": "Content2",  # Different content
        }

        token1 = generate_approval_token(proposal1)
        token2 = generate_approval_token(proposal2)

        assert token1 != token2

    def test_generate_approval_token_different_action_different_tokens(self):
        """Test that different actions produce different tokens."""
        proposal1 = {
            "target_path": "/test/path",
            "action": "create_file",  # Different action
            "justification": "Test",
            "content": "Content",
        }
        proposal2 = {
            "target_path": "/test/path",
            "action": "edit_file",  # Different action
            "justification": "Test",
            "content": "Content",
        }

        token1 = generate_approval_token(proposal1)
        token2 = generate_approval_token(proposal2)

        assert token1 != token2

    def test_generate_approval_token_minimal_proposal(self):
        """Test generating token with minimal proposal data."""
        proposal = {"target_path": "/path", "action": "action"}

        result = generate_approval_token(proposal)

        assert result.startswith("core-proposal-v6:")
        hex_part = result.split(":")[1]
        assert len(hex_part) == 64

    def test_generate_approval_token_with_none_fields(self):
        """Test generating token when some fields are None."""
        proposal = {
            "target_path": "/path",
            "action": "action",
            "justification": None,
            "content": None,
        }

        result = generate_approval_token(proposal)
        assert result.startswith("core-proposal-v6:")

    @patch("src.shared.utils.crypto.hashes.Hash")
    def test_generate_approval_token_hash_usage(self, mock_hash_class):
        """Test that the hash function is called correctly."""
        mock_hash_instance = MagicMock()
        mock_hash_class.return_value = mock_hash_instance
        mock_hash_instance.finalize.return_value = b"\xaa" * 32  # Fake hash

        proposal = {
            "target_path": "/test",
            "action": "test",
            "justification": "test",
            "content": "test",
        }

        result = generate_approval_token(proposal)

        # Verify hash was created - check it was called with any SHA256 instance
        mock_hash_class.assert_called_once()
        call_arg = mock_hash_class.call_args[0][0]
        assert isinstance(call_arg, hashes.SHA256)

        # Verify update was called with canonical string
        mock_hash_instance.update.assert_called_once()
        call_args = mock_hash_instance.update.call_args[0][0]
        assert isinstance(call_args, bytes)

        # Verify finalize was called
        mock_hash_instance.finalize.assert_called_once()

        # Verify result format
        assert result == "core-proposal-v6:" + "aa" * 32
