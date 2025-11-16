# tests/body/cli/logic/test_proposal_service.py
# CORRECTED: Import Generator for proper type hinting of fixtures that use yield.
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from body.cli.logic.proposal_service import ProposalService
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from shared.utils.yaml_processor import YAMLProcessor

yaml_processor = YAMLProcessor()

# --- Test Data ---
TEST_IDENTITY = "test.user@core.ai"
APPROVERS_CONFIG = {
    "approvers": [{"identity": TEST_IDENTITY, "public_key": "", "role": "maintainer"}],
    "quorum": {
        "current_mode": "development",
        "development": {"standard": 1, "critical": 1},
    },
    "critical_paths_source": "charter/constitution/critical_paths.yaml",
}
CRITICAL_PATHS_CONFIG = {"paths": ["charter/policies/safety_framework.yaml"]}
STANDARD_PROPOSAL = {
    "justification": "A standard change.",
    "target_path": "charter/policies/operations.yaml",
    "content": "new_content: standard",
}

# --- Fixtures ---


@pytest.fixture
def private_key() -> ed25519.Ed25519PrivateKey:
    return ed25519.Ed25519PrivateKey.generate()


@pytest.fixture
# CORRECTED: The return type is a Generator that yields a Path.
def mock_repo(
    tmp_path: Path, private_key: ed25519.Ed25519PrivateKey
) -> Generator[Path, None, None]:
    """
    Creates a mock repo with a private key and necessary config files.
    """
    intent_dir = tmp_path / ".intent"
    constitution_dir = intent_dir / "charter" / "constitution"
    keys_dir = intent_dir / "keys"

    constitution_dir.mkdir(parents=True)
    keys_dir.mkdir(parents=True)

    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    (keys_dir / "private.key").write_bytes(pem_private)

    public_key = private_key.public_key()
    pem_public = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    approvers_with_key = APPROVERS_CONFIG.copy()
    approvers_with_key["approvers"][0]["public_key"] = pem_public.decode("utf-8")

    yaml_processor.dump(approvers_with_key, constitution_dir / "approvers.yaml")
    yaml_processor.dump(CRITICAL_PATHS_CONFIG, constitution_dir / "critical_paths.yaml")

    # Patch the global settings for KEY_STORAGE_DIR as it's used by the service
    with patch(
        "body.cli.logic.proposal_service.settings.KEY_STORAGE_DIR", Path(".intent/keys")
    ):
        yield tmp_path


@pytest.fixture
def service(mock_repo: Path) -> ProposalService:
    # mock_repo fixture yields a Path, which pytest passes here.
    return ProposalService(repo_root=mock_repo)


# --- Test Classes ---


class TestProposalServiceList:
    def test_list_with_no_proposals(self, service: ProposalService):
        assert service.list() == []

    def test_list_with_one_standard_proposal(self, service: ProposalService):
        yaml_processor.dump(
            STANDARD_PROPOSAL, service.proposals_dir / "cr-standard.yaml"
        )
        proposals = service.list()
        assert len(proposals) == 1
        assert not proposals[0].is_critical


class TestProposalServiceSign:
    def test_sign_proposal_successfully(self, service: ProposalService):
        proposal_name = "cr-sign-me.yaml"
        yaml_processor.dump(STANDARD_PROPOSAL, service.proposals_dir / proposal_name)
        service.sign(proposal_name, TEST_IDENTITY)
        updated_proposal = yaml_processor.load(service.proposals_dir / proposal_name)
        assert len(updated_proposal["signatures"]) == 1
        assert updated_proposal["signatures"][0]["identity"] == TEST_IDENTITY

    def test_sign_replaces_existing_signature(self, service: ProposalService):
        proposal_name = "cr-resign.yaml"
        yaml_processor.dump(STANDARD_PROPOSAL, service.proposals_dir / proposal_name)
        service.sign(proposal_name, TEST_IDENTITY)
        service.sign(proposal_name, TEST_IDENTITY)
        updated_proposal = yaml_processor.load(service.proposals_dir / proposal_name)
        assert len(updated_proposal["signatures"]) == 1


class TestProposalServiceApprove:
    @patch("body.cli.logic.proposal_service.archive_rollback_plan")
    @patch(
        "body.cli.logic.proposal_service.ProposalService._run_canary_audit",
        new_callable=AsyncMock,
    )
    def test_approve_happy_path(
        self, mock_canary: AsyncMock, mock_archive: MagicMock, service: ProposalService
    ):
        mock_canary.return_value = (True, [])
        proposal_name = "cr-approve-me.yaml"
        yaml_processor.dump(STANDARD_PROPOSAL, service.proposals_dir / proposal_name)
        service.sign(proposal_name, TEST_IDENTITY)

        service.approve(proposal_name)

        target_path = service.repo_root / STANDARD_PROPOSAL["target_path"]
        assert target_path.exists()
        assert not (service.proposals_dir / proposal_name).exists()
        mock_archive.assert_called_once()
        mock_canary.assert_awaited_once()

    def test_approve_fails_on_quorum(self, service: ProposalService):
        proposal_name = "cr-no-quorum.yaml"
        yaml_processor.dump(STANDARD_PROPOSAL, service.proposals_dir / proposal_name)
        with pytest.raises(PermissionError, match="Quorum not met"):
            service.approve(proposal_name)

    @patch(
        "body.cli.logic.proposal_service.ProposalService._run_canary_audit",
        new_callable=AsyncMock,
    )
    def test_approve_fails_on_canary_audit(
        self, mock_canary: AsyncMock, service: ProposalService
    ):
        mock_canary.return_value = (False, [MagicMock()])
        proposal_name = "cr-canary-fail.yaml"
        yaml_processor.dump(STANDARD_PROPOSAL, service.proposals_dir / proposal_name)
        service.sign(proposal_name, TEST_IDENTITY)
        with pytest.raises(ChildProcessError, match="Canary audit failed"):
            service.approve(proposal_name)
