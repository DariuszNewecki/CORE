# tests/features/governance/test_key_management_service.py

import pytest


pytestmark = pytest.mark.legacy

from pathlib import Path
from unittest.mock import MagicMock

from mind.governance.key_management_service import KeyManagementError, keygen


class TestKeyManagementService:
    """Test suite for key_management_service module."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up common mocks for all tests in this class."""
        self.mock_settings = mocker.patch(
            "mind.governance.key_management_service.settings"
        )
        self.mock_ed25519 = mocker.patch(
            "mind.governance.key_management_service.ed25519.Ed25519PrivateKey"
        )
        self.mock_chmod = mocker.patch(
            "mind.governance.key_management_service.os.chmod"
        )
        # CORRECTED: Patch 'logger' instead of 'log'
        self.mock_logger = mocker.patch("mind.governance.key_management_service.logger")
        self.mock_print = mocker.patch("builtins.print")
        self.mock_yaml_dump = mocker.patch(
            "mind.governance.key_management_service.yaml.dump"
        )
        self.mock_datetime = mocker.patch(
            "mind.governance.key_management_service.datetime"
        )

        # Configure default behaviors
        mock_key_storage = MagicMock(spec=Path)
        mock_private_key_path = MagicMock(spec=Path)

        self.mock_settings.REPO_PATH = MagicMock(spec=Path)
        self.mock_settings.KEY_STORAGE_DIR = "keys"
        self.mock_settings.REPO_PATH.__truediv__.return_value = mock_key_storage
        mock_key_storage.__truediv__.return_value = mock_private_key_path

        self.mock_key_storage = mock_key_storage
        self.mock_private_key_path = mock_private_key_path

        mock_private_key = MagicMock()
        mock_public_key = MagicMock()
        self.mock_ed25519.generate.return_value = mock_private_key
        # Note: public_key is a property, not a method to be called
        type(mock_private_key).public_key = mocker.PropertyMock(
            return_value=mock_public_key
        )
        mock_private_key.private_bytes.return_value = b"fake_private_key"
        mock_public_key.public_bytes.return_value = b"fake_public_key"

    def test_keygen_successful_generation(self):
        """Test successful key generation with a new key pair."""
        self.mock_private_key_path.exists.return_value = False

        keygen("test@example.com")

        self.mock_key_storage.mkdir.assert_called_with(parents=True, exist_ok=True)
        self.mock_private_key_path.write_bytes.assert_called_with(b"fake_private_key")
        self.mock_chmod.assert_called_with(
            self.mock_private_key_path, 384
        )  # 384 is the decimal for 0o600
        # CORRECTED: Assert against the correct mock object
        self.mock_logger.info.assert_called()

    def test_keygen_existing_key_abort(self):
        """Test key generation aborts when the user declines to overwrite."""
        self.mock_private_key_path.exists.return_value = True

        with pytest.raises(KeyManagementError):
            keygen("test@example.com")

    def test_keygen_yaml_output(self):
        """Test that YAML output is correctly formatted."""
        fake_datetime = MagicMock()
        fake_datetime.isoformat.return_value = "2023-01-01T00:00:00+00:00"
        self.mock_datetime.now.return_value = fake_datetime
        self.mock_yaml_dump.return_value = "fake_yaml_output"
        self.mock_private_key_path.exists.return_value = False

        identity = "test.user@example.com"
        keygen(identity)

        self.mock_yaml_dump.assert_called_once()
        call_args = self.mock_yaml_dump.call_args[0][0]
        assert len(call_args) == 1
        approver_data = call_args[0]
        assert approver_data["identity"] == identity

    def test_keygen_existing_key_overwrite(self):
        """Test key generation proceeds when the user confirms an overwrite."""
        self.mock_private_key_path.exists.return_value = True

        keygen("test@example.com", allow_overwrite=True)
        self.mock_private_key_path.write_bytes.assert_called_once()

    def test_keygen_function_signature(self):
        """Test that the keygen function has the correct signature."""
        import inspect

        sig = inspect.signature(keygen)
        assert "identity" in sig.parameters
        # Just verify parameter exists, don't check annotation details

    def test_keygen_directory_creation(self):
        """Test that the key storage directory is created if it doesn't exist."""
        self.mock_private_key_path.exists.return_value = False

        keygen("test@example.com")

        self.mock_key_storage.mkdir.assert_called_with(parents=True, exist_ok=True)
