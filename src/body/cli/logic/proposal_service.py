# src/body/cli/logic/proposal_service.py
"""
Implements a service for proposal lifecycle management and the corresponding CLI commands.
"""

from __future__ import annotations

import asyncio
import base64
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from dotenv import load_dotenv

from mind.governance.auditor import ConstitutionalAuditor
from shared.config import settings
from shared.logger import getLogger
from shared.path_utils import copy_file, copy_tree
from shared.utils.crypto import generate_approval_token
from shared.utils.yaml_processor import YAMLProcessor

from .cli_utils import archive_rollback_plan


logger = getLogger(__name__)
yaml_processor = YAMLProcessor()


@dataclass
# ID: ba8240ee-f0ad-4c45-bb44-bf8f74db2ba1
class ProposalInfo:
    """Represents the status of a single proposal."""

    name: str
    justification: str
    target_path: str
    status: str
    is_critical: bool
    current_sigs: int
    required_sigs: int


# ID: 2613d1c7-08c8-486c-bdce-3e1580dfe4b5
class ProposalService:
    """Handles the business logic for constitutional proposals."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.proposals_dir = self.repo_root / ".intent" / "proposals"
        self.proposals_dir.mkdir(exist_ok=True)

        self.approvers_config = (
            yaml_processor.load(
                self.repo_root / ".intent/charter/constitution/approvers.yaml"
            )
            or {}
        )
        self.approver_keys = {
            a["identity"]: a["public_key"]
            for a in self.approvers_config.get("approvers", [])
        }
        critical_paths_source = self.approvers_config.get(
            "critical_paths_source", "charter/constitution/critical_paths.yaml"
        )
        critical_paths_file = self.repo_root / ".intent" / critical_paths_source
        critical_paths_data = yaml_processor.load(critical_paths_file) or {}
        self.critical_paths = critical_paths_data.get("paths", [])

    def _load_private_key(self) -> ed25519.Ed25519PrivateKey:
        """Loads the operator's private key from disk."""
        key_path = self.repo_root / settings.KEY_STORAGE_DIR / "private.key"
        if not key_path.exists():
            logger.error("Private key not found at %s.", key_path)
            raise FileNotFoundError("Private key not found.")
        return serialization.load_pem_private_key(key_path.read_bytes(), password=None)

    # ID: 95d5b788-eac0-4d3d-b065-f07625b26ad9
    def list(self) -> list[ProposalInfo]:
        """Returns structured info for all pending proposals."""
        proposals = []
        for prop_path in sorted(list(self.proposals_dir.glob("cr-*.yaml"))):
            config = yaml_processor.load(prop_path) or {}
            target_path = config.get("target_path", "")
            is_critical = any(target_path == p for p in self.critical_paths)
            current_sigs = len(config.get("signatures", []))

            quorum_config = self.approvers_config.get("quorum", {})
            current_mode = quorum_config.get("current_mode", "development")
            required_sigs = quorum_config.get(current_mode, {}).get(
                "critical" if is_critical else "standard", 1
            )

            status = (
                "✅ Ready"
                if current_sigs >= required_sigs
                else f"⏳ {current_sigs}/{required_sigs} sigs"
            )

            proposals.append(
                ProposalInfo(
                    name=prop_path.name,
                    justification=config.get(
                        "justification", "No justification provided."
                    ),
                    target_path=target_path,
                    status=status,
                    is_critical=is_critical,
                    current_sigs=current_sigs,
                    required_sigs=required_sigs,
                )
            )
        return proposals

    # ID: d255ea24-fed9-4881-bfd2-88e99efdaab4
    def sign(self, proposal_name: str, identity: str) -> None:
        """Adds a cryptographic signature to a proposal."""
        proposal_path = self.proposals_dir / proposal_name
        if not proposal_path.exists():
            raise FileNotFoundError(f"Proposal '{proposal_name}' not found.")

        proposal = yaml_processor.load(proposal_path) or {}
        private_key = self._load_private_key()
        token = generate_approval_token(proposal)
        signature = private_key.sign(token.encode("utf-8"))

        proposal.setdefault("signatures", [])
        proposal["signatures"] = [
            s for s in proposal["signatures"] if s.get("identity") != identity
        ]

        proposal["signatures"].append(
            {
                "identity": identity,
                "signature_b64": base64.b64encode(signature).decode("utf-8"),
                "token": token,
                "timestamp": datetime.now(UTC).isoformat() + "Z",
            }
        )

        yaml_processor.dump(proposal, proposal_path)

    def _verify_signatures(self, proposal: dict[str, Any]) -> int:
        """Verifies all signatures and returns the count of valid ones."""
        expected_token = generate_approval_token(proposal)
        valid = 0

        for sig in proposal.get("signatures", []):
            identity = sig.get("identity")
            if sig.get("token") != expected_token:
                logger.warning("Stale signature from '%s'.", identity)
                continue

            pem = self.approver_keys.get(identity)
            if not pem:
                logger.warning("No public key found for '%s'.", identity)
                continue

            try:
                pub_key: Ed25519PublicKey = serialization.load_pem_public_key(
                    pem.encode("utf-8")
                )
                pub_key.verify(
                    base64.b64decode(sig["signature_b64"]),
                    expected_token.encode("utf-8"),
                )
                logger.info("Valid signature from '%s'.", identity)
                valid += 1
            except Exception:
                logger.warning("Verification failed for '%s'.", identity)

        return valid

    async def _run_canary_audit(self, proposal: dict[str, Any]):
        """Creates a canary environment, applies the change, and runs the full audit."""
        target_rel_path = proposal["target_path"]

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            copy_tree(self.repo_root, tmp_path)

            env_file = self.repo_root / ".env"
            if env_file.exists():
                copy_file(env_file, tmp_path / ".env")

            canary_target_path = tmp_path / target_rel_path
            canary_target_path.parent.mkdir(parents=True, exist_ok=True)
            canary_target_path.write_text(proposal.get("content", ""), encoding="utf-8")

            if (tmp_path / ".env").exists():
                load_dotenv(dotenv_path=tmp_path / ".env", override=True)

            auditor = ConstitutionalAuditor(repo_root_override=tmp_path)
            success, findings, _ = await auditor.run_full_audit_async()

            return success, findings

    # ID: 92ce9218-fc89-4ee0-aba4-9956729c794c
    def approve(self, proposal_name: str) -> None:
        """Full approval workflow: verify, check quorum, audit, apply."""
        proposal_path = self.proposals_dir / proposal_name
        if not proposal_path.exists():
            raise FileNotFoundError(f"Proposal '{proposal_name}' not found.")

        proposal = yaml_processor.load(proposal_path) or {}
        target_rel_path = proposal.get("target_path")
        if not target_rel_path:
            raise ValueError("Proposal is invalid: missing 'target_path'.")

        valid_sigs = self._verify_signatures(proposal)

        is_critical = any(str(target_rel_path) == p for p in self.critical_paths)
        quorum_config = self.approvers_config.get("quorum", {})
        mode = quorum_config.get("current_mode", "development")
        required_sigs = quorum_config.get(mode, {}).get(
            "critical" if is_critical else "standard", 1
        )

        if valid_sigs < required_sigs:
            raise PermissionError(
                f"Approval failed: Quorum not met ({valid_sigs}/{required_sigs})."
            )

        success, findings = asyncio.run(self._run_canary_audit(proposal))

        if success:
            archive_rollback_plan(proposal_name, proposal)

            live_target_path = self.repo_root / target_rel_path
            live_target_path.parent.mkdir(parents=True, exist_ok=True)
            live_target_path.write_text(proposal.get("content", ""), encoding="utf-8")

            proposal_path.unlink()
            logger.info("Successfully approved and applied '%s'.", proposal_name)
        else:
            if findings:
                logger.error("Canary Audit Findings:")
                for finding in findings:
                    logger.error(finding)
            raise ChildProcessError("Canary audit failed.")


# ---------------------------------------------------------------------------
# CLI COMMAND FUNCTIONS (renamed to *_cmd)
# ---------------------------------------------------------------------------


# ID: ac0fafee-585f-4ece-8675-269b5a8168c1
def proposals_list_cmd() -> None:
    """CLI command: list all pending proposals."""
    logger.info("Finding pending constitutional proposals...")
    service = ProposalService(settings.REPO_PATH)
    proposals = service.list()

    if not proposals:
        logger.info("No pending proposals found.")
        return

    logger.info(f"Found {len(proposals)} pending proposal(s):")
    for prop in proposals:
        logger.info(f"  - **{prop.name}**: {prop.justification.strip()}")
        logger.info(f"    Target: {prop.target_path}")
        logger.info(
            f"    Status: {prop.status} ({'Critical' if prop.is_critical else 'Standard'})"
        )


def _safe_proposal_action(action_desc: str, action_func: Callable) -> None:
    """
    Wraps proposal actions with standard error handling to reduce duplication.
    """
    logger.info(action_desc)
    try:
        action_func()
    except (FileNotFoundError, ValueError, PermissionError, ChildProcessError) as e:
        logger.error("%s", e)
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        raise typer.Exit(code=1)


# ID: 9247acde-c437-4eab-88ee-4b5c3da85cae
def proposals_sign_cmd(
    proposal_name: str = typer.Argument(..., help="Filename of the proposal to sign."),
) -> None:
    """CLI command: sign a proposal."""

    def _action():
        service = ProposalService(settings.REPO_PATH)
        identity = typer.prompt(
            "Enter your identity (e.g., name@domain.com) for this signature"
        )
        service.sign(proposal_name, identity)
        logger.info("Signature added to proposal file.")

    _safe_proposal_action(f"Signing proposal: {proposal_name}", _action)


# ID: 9f252083-c262-4251-b5d0-2c6661528db6
def proposals_approve_cmd(
    proposal_name: str = typer.Argument(
        ..., help="Filename of the proposal to approve."
    ),
) -> None:
    """CLI command: approve and apply a proposal."""

    def _action():
        service = ProposalService(settings.REPO_PATH)
        service.approve(proposal_name)

    _safe_proposal_action(f"Attempting to approve proposal: {proposal_name}", _action)


# ---------------------------------------------------------------------------
# BACKWARD-COMPATIBLE ALIASES
# ---------------------------------------------------------------------------

proposals_list = proposals_list_cmd
proposals_sign = proposals_sign_cmd
proposals_approve = proposals_approve_cmd
