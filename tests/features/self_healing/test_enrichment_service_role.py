from typing import ClassVar

import pytest

from src.features.self_healing import enrichment_service


class _FakeAgent:
    async def make_request_async(self, prompt: str, user_id: str):
        # Return JSON in text so extract_json_from_response can parse
        return '{"description": "Dummy description for testing."}'


class _FakeCognitiveService:
    def __init__(self):
        self.requested_roles = []

    async def aget_client_for_role(self, role: str):
        self.requested_roles.append(role)
        return _FakeAgent()


class _FakeQdrantService:
    async def search_code(self, symbol_path: str, limit: int = 1):
        # Provide a payload in the shape the service expects
        class _Point:
            payload: ClassVar[dict[str, str]] = {"code": "def x():\n    return 1\n"}

        return [_Point()]


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeAsyncSession:
    def __init__(self, rows):
        self._rows = rows
        self.executed = []
        self.committed = False

    async def execute(self, stmt, params=None):
        # Track calls; first execute() is the SELECT, second is UPDATE
        self.executed.append((stmt, params))
        # For SELECT: return fake rows with keys uuid and symbol_path
        if len(self.executed) == 1:
            return _FakeResult(self._rows)
        # For UPDATE: return any object; caller doesn't use it
        return _FakeResult([])

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_enrich_symbols_requests_localcoder_role_and_updates_db_when_not_dry_run():
    session = _FakeAsyncSession(
        rows=[
            {
                "uuid": "00000000-0000-0000-0000-000000000001",
                "symbol_path": "src/x.py::x",
            }
        ]
    )
    cognitive = _FakeCognitiveService()
    qdrant = _FakeQdrantService()

    await enrichment_service.enrich_symbols(
        session=session,
        cognitive_service=cognitive,
        qdrant_service=qdrant,
        dry_run=False,
    )

    assert enrichment_service.ENRICH_SYMBOLS_ROLE == "LocalCoder"
    assert cognitive.requested_roles == ["LocalCoder"]

    # Should have run SELECT + UPDATE and committed
    assert len(session.executed) >= 2
    assert session.committed is True


@pytest.mark.asyncio
async def test_enrich_symbols_dry_run_does_not_commit():
    session = _FakeAsyncSession(
        rows=[
            {
                "uuid": "00000000-0000-0000-0000-000000000001",
                "symbol_path": "src/x.py::x",
            }
        ]
    )
    cognitive = _FakeCognitiveService()
    qdrant = _FakeQdrantService()

    await enrichment_service.enrich_symbols(
        session=session,
        cognitive_service=cognitive,
        qdrant_service=qdrant,
        dry_run=True,
    )

    assert cognitive.requested_roles == ["LocalCoder"]
    assert session.committed is False
