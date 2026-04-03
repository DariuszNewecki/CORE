# src/cli/logic/proposals/service.py

"""
Refactored logic for proposal lifecycle management.

CONSTITUTIONAL COMPLIANCE:
- Uses FileHandler for all mutations (IntentGuard enforced)
- Uses PathResolver for path resolution
- Verifies signatures cryptographically
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives import serialization

from cli.logic.cli_utils import archive_rollback_plan
from shared.context import CoreContext
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.processors.yaml_processor import YAMLProcessor
from shared.utils.crypto import generate_approval_token

from .canary import run_canary_audit
from .crypto import verify_signatures
from .models import ProposalInfo, _to_repo_rel, _yaml_dump


logger = getLogger(__name__)
yaml_processor = YAMLProcessor()


# ID: 99bcd929-7853-4e6f-bd14-e7e8c3e60252
class ProposalService:
    """
    Manages proposal lifecycle: list, sign, approve.

    CONSTITUTIONAL COMPLIANCE:
    - Uses FileHandler for mutations
    - Uses PathResolver for paths
    - Verifies cryptographic signatures
    - Enforces quorum requirements
    """

    def __init__(self, repo_root: Path, core_context: CoreContext | None = None):
        """
        Initialize proposal service.

        Args:
            repo_root: Repository root path
            core_context: Optional CoreContext
        """
        self.repo_root = repo_root.resolve()
        self.fs = FileHandler(str(self.repo_root))
        from shared.path_resolver import PathResolver

        path_resolver = PathResolver.from_repo(
            repo_root=self.repo_root,
            intent_root=self.repo_root / ".intent",
        )

        self.proposals_dir = path_resolver.proposals_dir
        self.fs.ensure_dir(_to_repo_rel(self.repo_root, self.proposals_dir))

        # Approver configuration — not yet provisioned.
        # Populate var/governance/approvers.yaml to enable quorum enforcement.
        self.approver_keys: dict[str, str] = {}
        self.quorum_config: dict = {}

        # Critical paths configuration — not yet provisioned.
        # Populate var/governance/critical_paths.yaml to enable path classification.
        self.critical_paths: list = []

    # ID: 7cf17c56-adf6-47a7-a70d-7342e2064c16
    def list(self) -> list[ProposalInfo]:
        """
        List all pending proposals.

        Returns:
            List of ProposalInfo objects
        """
        proposals = []
        for prop_path in sorted(list(self.proposals_dir.glob("cr-*.yaml"))):
            cfg = yaml_processor.load(prop_path) or {}
            target = cfg.get("target_path", "")
            is_crit = any(target == p for p in self.critical_paths)
            cur_sigs = len(cfg.get("signatures", []))
            mode = self.quorum_config.get("current_mode", "development")
            req_sigs = self.quorum_config.get(mode, {}).get(
                "critical" if is_crit else "standard", 1
            )
            status = (
                "✅ Ready" if cur_sigs >= req_sigs else f"⏳ {cur_sigs}/{req_sigs} sigs"
            )
            proposals.append(
                ProposalInfo(
                    prop_path.name,
                    cfg.get("justification", "No justification provided."),
                    target,
                    status,
                    is_crit,
                    cur_sigs,
                    req_sigs,
                )
            )
        return proposals

    # ID: 0d0219b7-c66c-447f-870f-c0cb834768fd
    def sign(self, proposal_name: str, identity: str) -> None:
        """
        Sign a proposal with cryptographic signature.

        Args:
            proposal_name: Name of the proposal file
            identity: Identity of the signer

        Raises:
            FileNotFoundError: If proposal or private key doesn't exist
        """
        path = self.proposals_dir / proposal_name
        if not path.exists():
            raise FileNotFoundError(f"Proposal '{proposal_name}' not found.")

        proposal = yaml_processor.load(path) or {}
        key_path = self.repo_root / "var" / "keys" / "private.key"
        if not key_path.exists():
            raise FileNotFoundError(
                f"Private key not found at {key_path}. "
                "Run 'core-admin manage keys generate' to create one."
            )
        private_key = serialization.load_pem_private_key(
            key_path.read_bytes(), password=None
        )

        token = generate_approval_token(proposal)
        sig_b64 = base64.b64encode(private_key.sign(token.encode("utf-8"))).decode(
            "utf-8"
        )

        proposal.setdefault("signatures", [])
        proposal["signatures"] = [
            s for s in proposal["signatures"] if s.get("identity") != identity
        ]
        proposal["signatures"].append(
            {
                "identity": identity,
                "signature_b64": sig_b64,
                "token": token,
                "timestamp": datetime.now(UTC).isoformat() + "Z",
            }
        )
        self.fs.write_runtime_text(
            _to_repo_rel(self.repo_root, path), _yaml_dump(proposal)
        )

    # ID: 02c38ef1-bd0a-4610-89b5-bd8169dcfd1c
    async def approve(self, proposal_name: str) -> None:
        """
        Approve and execute a proposal after signature verification.

        Args:
            proposal_name: Name of the proposal file

        Raises:
            FileNotFoundError: If proposal doesn't exist
            ValueError: If proposal is invalid
            PermissionError: If quorum not met
            ChildProcessError: If canary audit fails
        """
        path = self.proposals_dir / proposal_name
        if not path.exists():
            raise FileNotFoundError(f"Proposal '{proposal_name}' not found.")

        proposal = yaml_processor.load(path) or {}
        target = proposal.get("target_path")
        if not target:
            raise ValueError("Proposal is invalid: missing 'target_path'.")

        # Verify cryptographic signatures
        valid_sigs = verify_signatures(proposal, self.approver_keys)
        mode = self.quorum_config.get("current_mode", "development")
        req = self.quorum_config.get(mode, {}).get(
            (
                "critical"
                if any(str(target) == p for p in self.critical_paths)
                else "standard"
            ),
            1,
        )

        if valid_sigs < req:
            raise PermissionError(
                f"Approval failed: Quorum not met ({valid_sigs}/{req})."
            )

        # Run canary audit before applying
        success, _findings = await run_canary_audit(
            self.repo_root, self.fs, proposal, proposal_name
        )
        if not success:
            raise ChildProcessError("Canary audit failed.")

        # Archive for rollback capability
        archive_rollback_plan(proposal_name, proposal, self.fs)

        # Apply the proposal
        self.fs.write_runtime_text(
            str(target).lstrip("./"), proposal.get("content", "")
        )

        # Remove the proposal file
        self.fs.remove_file(_to_repo_rel(self.repo_root, path))
