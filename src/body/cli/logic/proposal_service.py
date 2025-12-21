# src/body/cli/logic/proposal_service.py

"""
Implements a service for proposal lifecycle management and the corresponding CLI commands.
"""

from __future__ import annotations

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

from mind.governance.audit_context import AuditorContext
from mind.governance.auditor import ConstitutionalAuditor
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger
from shared.path_utils import copy_file, copy_tree
from shared.utils.crypto import generate_approval_token
from shared.utils.yaml_processor import YAMLProcessor

from .cli_utils import archive_rollback_plan


logger = getLogger(__name__)
yaml_processor = YAMLProcessor()


@dataclass
# ID: 5cc2a437-a17b-421c-b074-5eeacefdba80
class ProposalInfo:
    """Represents the status of a single proposal."""

    name: str
    justification: str
    target_path: str
    status: str
    is_critical: bool
    current_sigs: int
    required_sigs: int


# ID: 69f8c9d1-a0c3-426a-a68c-471cba429b9d
class ProposalService:
    """Handles the business logic for constitutional proposals."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.proposals_dir = settings.paths.proposals_dir
        self.proposals_dir.mkdir(parents=True, exist_ok=True)
        self.approvers_config = (
            yaml_processor.load(settings.paths.constitution_dir / "approvers.yaml")
            or {}
        )
        self.approver_keys = {
            a["identity"]: a["public_key"]
            for a in self.approvers_config.get("approvers", [])
        }
        critical_paths_source = self.approvers_config.get(
            "critical_paths_source", "charter/constitution/critical_paths.json"
        )
        critical_paths_file = settings.paths.intent_root / critical_paths_source
        critical_paths_data = yaml_processor.load(critical_paths_file) or {}
        self.critical_paths = critical_paths_data.get("paths", [])

    def _load_private_key(self) -> ed25519.Ed25519PrivateKey:
        """Loads the operator's private key from disk."""
        key_dir = settings.KEY_STORAGE_DIR
        key_path = key_dir / "private.key"
        if not key_path.exists():
            logger.error("Private key not found at %s.", key_path)
            raise FileNotFoundError("Private key not found.")
        return serialization.load_pem_private_key(key_path.read_bytes(), password=None)

    # ID: 5055d32c-5ed1-4e46-947f-07f6416f8f95
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

    # ID: e6086478-190e-43a2-a862-797daf0c0c75
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

    async def _run_canary_audit(
        self, proposal: dict[str, Any]
    ) -> tuple[bool, list[Any]]:
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
            auditor_context = AuditorContext(tmp_path)
            auditor = ConstitutionalAuditor(auditor_context)
            findings = await auditor.run_full_audit_async()

            def _is_blocking(finding: Any) -> bool:
                severity = getattr(finding, "severity", None)
                if hasattr(severity, "is_blocking"):
                    return bool(severity.is_blocking)
                if isinstance(severity, str):
                    return severity.lower() == "error"
                if isinstance(finding, dict):
                    sev = finding.get("severity")
                    if isinstance(sev, str):
                        return sev.lower() == "error"
                return False

            success = not any(_is_blocking(f) for f in findings)
            return (success, findings)

    # ID: 4fceca37-1e93-4f82-b676-b9e6ed5d866d
    async def approve(self, proposal_name: str) -> None:
        """Full approval workflow: verify, check quorum, audit, apply."""
        proposal_path = self.proposals_dir / proposal_name
        if not proposal_path.exists():
            raise FileNotFoundError(f"Proposal '{proposal_name}' not found.")
        proposal = yaml_processor.load(proposal_path) or {}

        # Constitutional requirement: Log IntentBundle ID before write operations
        # Each proposal file name serves as the intent_bundle_id for audit traceability
        intent_bundle_id = proposal_name
        logger.info("Processing proposal with intent_bundle_id: %s", intent_bundle_id)

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
        success, findings = await self._run_canary_audit(proposal)
        if success:
            archive_rollback_plan(proposal_name, proposal)
            live_target_path = self.repo_root / target_rel_path
            live_target_path.parent.mkdir(parents=True, exist_ok=True)

            # Log before write: Constitutional safety requirement (safety.change_must_be_logged)
            logger.info(
                "Applying changes for intent_bundle_id: %s to %s",
                intent_bundle_id,
                target_rel_path,
            )
            live_target_path.write_text(proposal.get("content", ""), encoding="utf-8")

            proposal_path.unlink()
            logger.info("Successfully approved and applied '%s'.", proposal_name)
        else:
            if findings:
                logger.error("Canary Audit Findings:")
                for finding in findings:
                    logger.error(finding)
            raise ChildProcessError("Canary audit failed.")


# ID: afb5a8de-836f-4788-8fe0-f3cd86b463c6
def proposals_list_cmd() -> None:
    """CLI command: list all pending proposals."""
    logger.info("Finding pending constitutional proposals...")
    service = ProposalService(settings.REPO_PATH)
    proposals = service.list()
    if not proposals:
        logger.info("No pending proposals found.")
        return
    logger.info("Found %s pending proposal(s):", len(proposals))
    for prop in proposals:
        logger.info("  - **%s**: %s", prop.name, prop.justification.strip())
        logger.info("    Target: %s", prop.target_path)
        logger.info(
            "    Status: %s (%s)",
            prop.status,
            "Critical" if prop.is_critical else "Standard",
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


# ID: a0f3d16d-4c7e-47b6-b8b6-3cc0ebb3e803
def proposals_sign_cmd(
    proposal_name: str = typer.Argument(..., help="Filename of the proposal to sign.")
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


# ID: dbbc5fd7-a43d-40bd-bb5d-821c043652c1
async def proposals_approve_cmd(
    proposal_name: str = typer.Argument(
        ..., help="Filename of the proposal to approve."
    ),
    context: CoreContext | None = None,
) -> None:
    """CLI command: approve and apply a proposal."""
    repo_root = (
        context.git_service.repo_path
        if context and context.git_service
        else settings.REPO_PATH
    )

    async def _action() -> None:
        service = ProposalService(repo_root)
        await service.approve(proposal_name)

    logger.info("Attempting to approve proposal: %s", proposal_name)
    try:
        await _action()
    except (FileNotFoundError, ValueError, PermissionError, ChildProcessError) as e:
        logger.error("%s", e)
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        raise typer.Exit(code=1)


proposals_list = proposals_list_cmd
proposals_sign = proposals_sign_cmd
proposals_approve = proposals_approve_cmd
