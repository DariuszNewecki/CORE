# src/body/cli/logic/proposals/service.py

"""Refactored logic for src/body/cli/logic/proposals/service.py."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives import serialization

from body.cli.logic.cli_utils import archive_rollback_plan
from shared.context import CoreContext
from shared.infrastructure.storage.file_handler import FileHandler
from shared.processors.yaml_processor import YAMLProcessor
from shared.utils.crypto import generate_approval_token

from .canary import run_canary_audit
from .crypto import verify_signatures
from .models import ProposalInfo, _to_repo_rel, _yaml_dump


yaml_processor = YAMLProcessor()


# ID: 99bcd929-7853-4e6f-bd14-e7e8c3e60252
class ProposalService:
    def __init__(self, repo_root: Path, core_context: CoreContext | None = None):
        self.repo_root = repo_root.resolve()
        self.fs = FileHandler(str(self.repo_root))
        from shared.path_resolver import PathResolver

        path_resolver = PathResolver.from_repo(
            repo_root=self.repo_root,
            intent_root=self.repo_root / ".intent",
        )

        self.proposals_dir = path_resolver.proposals_dir
        self.fs.ensure_dir(_to_repo_rel(self.repo_root, self.proposals_dir))

        app_cfg = (
            yaml_processor.load(
                path_resolver.intent_root / "constitution" / "approvers.yaml"
            )
            or {}
        )
        self.approver_keys = {
            a["identity"]: a["public_key"] for a in app_cfg.get("approvers", [])
        }
        self.quorum_config = app_cfg.get("quorum", {})

        crit_path = path_resolver.intent_root / app_cfg.get(
            "critical_paths_source", "charter/constitution/critical_paths.json"
        )
        self.critical_paths = (yaml_processor.load(crit_path) or {}).get("paths", [])

    # ID: 7cf17c56-adf6-47a7-a70d-7342e2064c16
    def list(self) -> list[ProposalInfo]:
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
        path = self.proposals_dir / proposal_name
        if not path.exists():
            raise FileNotFoundError(f"Proposal '{proposal_name}' not found.")

        proposal = yaml_processor.load(path) or {}
        key_path = self.repo_root / ".intent" / "keys" / "private.key"
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
        path = self.proposals_dir / proposal_name
        if not path.exists():
            raise FileNotFoundError(f"Proposal '{proposal_name}' not found.")
        proposal = yaml_processor.load(path) or {}
        target = proposal.get("target_path")
        if not target:
            raise ValueError("Proposal is invalid: missing 'target_path'.")

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

        success, _findings = await run_canary_audit(
            self.repo_root, self.fs, proposal, proposal_name
        )
        if not success:
            raise ChildProcessError("Canary audit failed.")

        archive_rollback_plan(proposal_name, proposal, self.fs)
        self.fs.write_runtime_text(
            str(target).lstrip("./"), proposal.get("content", "")
        )
        self.fs.remove_file(_to_repo_rel(self.repo_root, path))
