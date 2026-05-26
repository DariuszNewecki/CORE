import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from collections.abc import Sequence
from body.services.governance_claims_service import GovernanceClaimsService, ClaimVector, SearchHit, _point_id
from body.services.governance_claims_service import Claim


@pytest.fixture
def mock_qdrant():
    """Fixture providing a mocked QdrantService instance."""
    mock = MagicMock()
    mock.ensure_collection = AsyncMock()
    mock.scroll_all_points = AsyncMock()
    mock.client = MagicMock()
    return mock


@pytest.fixture
def service(mock_qdrant):
    """Fixture providing a GovernanceClaimsService instance with mocked Qdrant."""
    svc = GovernanceClaimsService(qdrant=mock_qdrant, vector_size=768)
    return svc


class TestGovernanceClaimsService:
    """Test suite for GovernanceClaimsService."""

    @pytest.mark.asyncio
    async def test_init_sets_qdrant_and_vector_size(self, mock_qdrant):
        """__init__ should store qdrant and vector_size."""
        svc = GovernanceClaimsService(qdrant=mock_qdrant, vector_size=512)
        assert svc._qdrant is mock_qdrant
        assert svc._vector_size == 512

    @pytest.mark.asyncio
    async def test_init_uses_default_vector_size(self, mock_qdrant):
        """__init__ should default vector_size to 768."""
        svc = GovernanceClaimsService(qdrant=mock_qdrant)
        assert svc._vector_size == 768

    def test_collection_name_returns_constant(self, service):
        """collection_name property should return the collection name constant."""
        assert service.collection_name == "governance_claims"

    @pytest.mark.asyncio
    async def test_ensure_collection_delegates_to_qdrant(self, service, mock_qdrant):
        """ensure_collection should call qdrant.ensure_collection with collection name and vector size."""
        await service.ensure_collection()
        mock_qdrant.ensure_collection.assert_awaited_once_with(
            collection_name="governance_claims",
            vector_size=768,
        )

    @pytest.mark.asyncio
    async def test_is_seeded_returns_true_when_collection_exists_and_has_points(self, service, mock_qdrant):
        """is_seeded should return True when collection exists and has at least 1 point."""
        mock_qdrant.client.get_collections = AsyncMock(return_value=MagicMock(collections=[MagicMock(name="governance_claims")]))
        mock_qdrant.client.count = AsyncMock(return_value=MagicMock(count=5))
        result = await service.is_seeded()
        assert result is True

    @pytest.mark.asyncio
    async def test_is_seeded_returns_false_when_collection_missing(self, service, mock_qdrant):
        """is_seeded should return False when collection does not exist."""
        mock_qdrant.client.get_collections = AsyncMock(return_value=MagicMock(collections=[]))
        result = await service.is_seeded()
        assert result is False

    @pytest.mark.asyncio
    async def test_is_seeded_returns_false_when_count_is_zero(self, service, mock_qdrant):
        """is_seeded should return False when collection exists but has 0 points."""
        mock_qdrant.client.get_collections = AsyncMock(return_value=MagicMock(collections=[MagicMock(name="governance_claims")]))
        mock_qdrant.client.count = AsyncMock(return_value=MagicMock(count=0))
        result = await service.is_seeded()
        assert result is False

    @pytest.mark.asyncio
    async def test_is_seeded_returns_false_on_exception(self, service, mock_qdrant):
        """is_seeded should return False when get_collections raises an exception."""
        mock_qdrant.client.get_collections = AsyncMock(side_effect=Exception("Qdrant error"))
        result = await service.is_seeded()
        assert result is False

    @pytest.mark.asyncio
    async def test_current_keys_returns_set_of_tuples(self, service, mock_qdrant):
        """current_keys should return a set of (source_path, content_sha) tuples from scroll_all_points."""
        mock_qdrant.scroll_all_points.return_value = [
            MagicMock(payload={"source_path": "/path/a", "content_sha": "sha1"}),
            MagicMock(payload={"source_path": "/path/b", "content_sha": "sha2"}),
        ]
        result = await service.current_keys()
        assert result == {("/path/a", "sha1"), ("/path/b", "sha2")}

    @pytest.mark.asyncio
    async def test_current_keys_returns_empty_set_when_no_points(self, service, mock_qdrant):
        """current_keys should return an empty set when scroll_all_points returns empty list."""
        mock_qdrant.scroll_all_points.return_value = []
        result = await service.current_keys()
        assert result == set()

    @pytest.mark.asyncio
    async def test_delete_by_keys_with_empty_keys_returns_zero(self, service, mock_qdrant):
        """delete_by_keys should return 0 when keys is empty."""
        result = await service.delete_by_keys([])
        assert result == 0
        mock_qdrant.client.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_by_keys_deletes_points_and_returns_count(self, service, mock_qdrant):
        """delete_by_keys should delete points by point_id and return the count."""
        with patch("body.services.governance_claims_service._point_id", return_value="mock-point-id"):
            mock_qdrant.client.delete = AsyncMock()
            result = await service.delete_by_keys([("/path/a", "sha1"), ("/path/b", "sha2")])
            assert result == 2
            mock_qdrant.client.delete.assert_awaited_once_with(
                collection_name="governance_claims",
                points_selector=MagicMock(),
                wait=True,
            )

    @pytest.mark.asyncio
    async def test_delete_by_source_path_deletes_with_filter(self, service, mock_qdrant):
        """delete_by_source_path should call delete with a filter on source_path."""
        mock_qdrant.client.delete = AsyncMock()
        await service.delete_by_source_path("/path/to/file.md")
        mock_qdrant.client.delete.assert_awaited_once()
        call_args = mock_qdrant.client.delete.await_args
        assert call_args is not None
        assert call_args["collection_name"] == "governance_claims"
        # Verify filter is a FilterSelector with must condition on source_path
        filter_selector = call_args["points_selector"]
        assert hasattr(filter_selector, "filter")
        assert hasattr(filter_selector.filter, "must")

    @pytest.mark.asyncio
    async def test_upsert_claims_with_empty_items_returns_zero(self, service, mock_qdrant):
        """upsert_claims should return 0 when items is empty."""
        result = await service.upsert_claims([])
        assert result == 0
        mock_qdrant.client.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_upsert_claims_creates_point_structs_and_returns_count(self, service, mock_qdrant, mock_qdrant):
        """upsert_claims should create PointStructs and return the count written."""
        mock_qdrant.client.upsert = AsyncMock()
        claims = [
            ClaimVector(
                claim=MagicMock(source_path="/path/a", content_sha="sha1", paragraph_index=0, text="text1", category="cat1"),
                vector=[0.1, 0.2, 0.3],
            ),
            ClaimVector(
                claim=MagicMock(source_path="/path/b", content_sha="sha2", paragraph_index=1, text="text2", category="cat2"),
                vector=[0.4, 0.5, 0.6],
            ),
        ]
        with patch("body.services.governance_claims_service._point_id", side_effect=["id1", "id2"]):
            result = await service.upsert_claims(claims)
            assert result == 2
            mock_qdrant.client.upsert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_search_returns_list_of_search_hits(self, service, mock_qdrant):
        """search should return a list of SearchHit objects from Qdrant response."""
        mock_qdrant.client.search = AsyncMock(return_value=[
            MagicMock(
                id="point-id",
                version=1,
                score=0.85,
                payload={
                    "source_path": "/path/a",
                    "paragraph_index": 0,
                    "text": "claim text",
                    "content_sha": "sha1",
                    "category": "normative",
                },
            ),
        ])
        result = await service.search(query_vector=[0.1, 0.2, 0.3], limit=5)
        assert len(result) == 1
        hit = result[0]
        assert isinstance(hit, SearchHit)
        assert hit.cosine == 0.85
        assert hit.source_path == "/path/a"
        assert hit.paragraph_index == 0
        assert hit.text == "claim text"
        assert hit.content_sha == "sha1"
        assert hit.category == "normative"

    @pytest.mark.asyncio
    async def test_search_applies_source_path_filter(self, service, mock_qdrant):
        """search should pass filter when source_path_in is provided."""
        mock_qdrant.client.search = AsyncMock(return_value=[])
        with patch("body.services.governance_claims_service.qm") as mock_qm:
            result = await service.search(query_vector=[0.1], limit=3, source_path_in=["/path/a", "/path/b"])
            mock_qdrant.client.search.assert_awaited_once()
            assert result == []

    @pytest.mark.asyncio
    async def test_search_with_score_threshold(self, service, mock_qdrant):
        """search should pass score_threshold to Qdrant query."""
        mock_qdrant.client.search = AsyncMock(return_value=[
            MagicMock(score=0.9, payload={}),
        ])
        result = await service.search(query_vector=[0.1], limit=3, score_threshold=0.5)
        assert len(result) == 1
        assert result[0].cosine == 0.9

    def test_point_id_returns_deterministic_uuid(self):
        """_point_id should return a deterministic UUID5 string."""
        point_id_1 = _point_id("/path/a", "sha1")
        point_id_2 = _point_id("/path/a", "sha1")
        point_id_3 = _point_id("/path/b", "sha1")
        assert point_id_1 == point_id_2
        assert point_id_1 != point_id_3

    def test_search_hit_is_dataclass_with_expected_fields(self):
        """SearchHit should be instantiable with all fields."""
        hit = SearchHit(
            cosine=0.95,
            source_path="/path/to/file.md",
            paragraph_index=2,
            text="Some claim text",
            content_sha="abcdef123",
            category="obligation",
        )
        assert hit.cosine == 0.95
        assert hit.source_path == "/path/to/file.md"
        assert hit.paragraph_index == 2
        assert hit.text == "Some claim text"
        assert hit.content_sha == "abcdef123"
        assert hit.category == "obligation"

    def test_claim_vector_is_dataclass_with_expected_fields(self):
        """ClaimVector should be instantiable with claim and vector."""
        claim = MagicMock(source_path="/path", content_sha="sha", paragraph_index=0, text="text", category="cat")
        cv = ClaimVector(claim=claim, vector=[0.1, 0.2])
        assert cv.claim is claim
        assert cv.vector == [0.1, 0.2]
