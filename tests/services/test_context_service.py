# tests/services/test_context_service.py
"""Tests for ContextService integration."""

import pytest

from src.services.context.service import ContextService


class TestContextService:
    """Test ContextService end-to-end."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create ContextService with temp directory."""
        return ContextService(
            db_service=None,  # Mock for now
            qdrant_client=None,  # Mock for now
            config={"cache_dir": str(tmp_path / "cache")},
            project_root=str(tmp_path),
        )

    @pytest.mark.asyncio
    async def test_build_packet_creates_file(self, service, tmp_path):
        """Test that building a packet creates a file."""
        task_spec = {
            "task_id": "TEST_001",
            "task_type": "docstring.fix",
            "summary": "Test packet building",
            "roots": ["src/"],
            "max_items": 5,
        }

        # Build packet
        packet = await service.build_for_task(task_spec, use_cache=False)

        # Verify structure
        assert "header" in packet
        assert packet["header"]["task_id"] == "TEST_001"
        assert packet["header"]["privacy"] == "local_only"
        assert packet["policy"]["remote_allowed"] is False

        # Verify file created
        packet_file = (
            tmp_path / "work" / "context_packets" / "TEST_001" / "context.yaml"
        )
        assert packet_file.exists()

    @pytest.mark.asyncio
    async def test_validation_enforces_schema(self, service):
        """Test that validator enforces required fields."""
        invalid_packet = {"header": {"task_id": "TEST"}}
        is_valid, errors = service.validate_packet(invalid_packet)
        assert not is_valid
        assert len(errors) > 0

    @pytest.mark.asyncio
    async def test_load_packet(self, service, tmp_path):
        """Test loading a packet from disk."""
        task_spec = {
            "task_id": "TEST_002",
            "task_type": "test.generate",
            "summary": "Test loading",
            "roots": ["src/"],
        }

        original = await service.build_for_task(task_spec, use_cache=False)
        loaded = await service.load_packet("TEST_002")

        assert loaded is not None
        assert loaded["header"]["packet_id"] == original["header"]["packet_id"]

    @pytest.mark.asyncio
    async def test_cache_reuse(self, service):
        """Test that cache prevents rebuilding identical packets."""
        task_spec = {
            "task_id": "TEST_003",
            "task_type": "docstring.fix",
            "summary": "Test caching",
            "roots": ["src/"],
        }

        packet1 = await service.build_for_task(task_spec, use_cache=True)
        packet2 = await service.build_for_task(task_spec, use_cache=True)

        assert packet1["provenance"]["cache_key"] == packet2["provenance"]["cache_key"]

    # ————————————————————————————————————————————————————————————————————
    # FINAL FIXED TEST – works with corrected redactor (supports ** globs)
    # ————————————————————————————————————————————————————————————————————
    def test_privacy_enforcement(self, service):
        """Test that redactor removes .env files (even in subdirs) and blocks remote upload."""
        from src.services.context.redactor import ContextRedactor

        # Uses DEFAULT_FORBIDDEN_PATHS with **/.env → now works thanks to Path().match()
        redactor = ContextRedactor()

        packet = {
            "header": {"packet_id": "test", "privacy": {"remote_allowed": True}},
            "items": [
                {
                    "name": "secret",
                    "path": ".env",
                    "item_type": "snippet",
                    "source": "test",
                    "content": "API_KEY=abc123",
                },
                {
                    "path": "config/.env.local",
                    "item_type": "snippet",
                    "content": "DB=secret",
                },
                {"path": "safe/config.py", "content": "print('hello')"},
            ],
        }

        redacted = redactor.redact(packet)

        # Only safe file should remain
        assert len(redacted["items"]) == 1
        assert redacted["items"][0]["path"] == "safe/config.py"

        # At least 2 redactions (.env + .env.local)
        redactions = redacted["header"]["policy"]["redactions_applied"]
        assert len(redactions) >= 2
        assert any(r["path"] == ".env" for r in redactions)
        assert any(r["path"] == "config/.env.local" for r in redactions)

        # Remote upload blocked
        assert redacted["header"]["privacy"]["remote_allowed"] is False
