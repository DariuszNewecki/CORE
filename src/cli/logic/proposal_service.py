# src/cli/logic/proposal_service.py
"""
Implements the command-line interface for proposal lifecycle management.
This module now serves as the main entry point for ALL proposal types.
"""

from __future__ import annotations

import asyncio
import base64
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from cryptography.hazmat.primitives import serialization
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from features.governance.constitutional_auditor import ConstitutionalAuditor
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger
from shared.utils.crypto import generate_approval_token

from .cli_utils import (
    archive_rollback_plan,
    load_private_key,
    load_yaml_file,
    save_yaml_file,
)

log = getLogger("core_admin.proposals")
console = Console()

# Global variable to store context
_context: Optional[CoreContext] = None


# ID: 7dcb045e-19c9-4d84-91fd-70c4de7e8dfe
def proposals_list() -> None:
    """List pending constitutional proposals and display their status."""
    log.info("🔍 Finding pending constitutional proposals...")
    proposals_dir = settings.REPO_PATH / ".intent" / "proposals"
    proposals_dir.mkdir(exist_ok=True)
    proposals = sorted(list(proposals_dir.glob("cr-*.yaml")))

    if not proposals:
        log.info("✅ No pending proposals found.")
        return

    log.info(f"Found {len(proposals)} pending proposal(s):")
    approvers_config = load_yaml_file(
        settings.REPO_PATH / ".intent" / "charter" / "constitution" / "approvers.yaml"
    )

    for prop_path in proposals:
        config = load_yaml_file(prop_path)
        justification = config.get("justification", "No justification provided.")
        target_path = config.get("target_path", "")
        quorum_config = approvers_config.get("quorum", {})
        current_mode = quorum_config.get("current_mode", "development")

        critical_paths_source = approvers_config.get(
            "critical_paths_source", "charter/constitution/critical_paths.yaml"
        )
        critical_paths_file = settings.REPO_PATH / ".intent" / critical_paths_source
        critical_paths_config = load_yaml_file(critical_paths_file)
        critical_paths = critical_paths_config.get("paths", [])

        is_critical = any(target_path == p for p in critical_paths)
        required_sigs = quorum_config.get(current_mode, {}).get(
            "critical" if is_critical else "standard", 1
        )
        current_sigs = len(config.get("signatures", []))
        status = (
            "✅ Ready"
            if current_sigs >= required_sigs
            else f"⏳ {current_sigs}/{required_sigs} sigs"
        )

        log.info(f"\n  - **{prop_path.name}**: {justification.strip()}")
        log.info(f"    Target: {target_path}")
        log.info(f"    Status: {status} ({'Critical' if is_critical else 'Standard'})")


# ID: e0b15fef-d8d5-4f39-98b3-18d4eedd8bb5
def proposals_sign(
    proposal_name: str = typer.Argument(
        ..., help="Filename of the proposal to sign (e.g., 'cr-new-policy.yaml')."
    ),
) -> None:
    """Sign a proposal with the operator's private key."""
    log.info(f"✍️ Signing proposal: {proposal_name}")
    proposal_path = settings.REPO_PATH / ".intent" / "proposals" / proposal_name
    if not proposal_path.exists():
        log.error(f"❌ Proposal '{proposal_name}' not found.")
        raise typer.Exit(code=1)

    proposal = load_yaml_file(proposal_path)
    private_key = load_private_key()
    token = generate_approval_token(proposal)
    signature = private_key.sign(token.encode("utf-8"))
    identity = typer.prompt(
        "Enter your identity (e.g., name@domain.com) for this signature"
    )

    proposal.setdefault("signatures", [])
    proposal["signatures"] = [
        s for s in proposal["signatures"] if s.get("identity") != identity
    ]
    proposal["signatures"].append(
        {
            "identity": identity,
            "signature_b64": base64.b64encode(signature).decode("utf-8"),
            "token": token,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )

    save_yaml_file(proposal_path, proposal)
    log.info("✅ Signature added to proposal file.")


# ID: 9848504e-60ef-44c1-a57c-b7e14edb5809
def proposals_approve(
    proposal_name: str = typer.Argument(
        ..., help="Filename of the proposal to approve."
    ),
) -> None:
    """Verify signatures, run a canary audit, and apply a valid proposal."""
    if _context is None:
        console.print("[bold red]Error: Context not initialized for approve[/bold red]")
        raise typer.Exit(code=1)

    log.info(f"🚀 Attempting to approve proposal: {proposal_name}")
    proposal_path = settings.REPO_PATH / ".intent" / "proposals" / proposal_name
    if not proposal_path.exists():
        log.error(f"❌ Proposal '{proposal_name}' not found.")
        raise typer.Exit(code=1)

    proposal = load_yaml_file(proposal_path)
    target_rel_path = proposal.get("target_path")
    if not target_rel_path:
        log.error("❌ Proposal is invalid: missing 'target_path'.")
        raise typer.Exit(code=1)

    log.info("🔐 Verifying cryptographic signatures...")
    approvers_config = load_yaml_file(
        settings.REPO_PATH / ".intent" / "charter" / "constitution" / "approvers.yaml"
    )
    approver_keys = {
        a["identity"]: a["public_key"] for a in approvers_config.get("approvers", [])
    }

    expected_token = generate_approval_token(proposal)
    valid_signatures = 0
    for sig in proposal.get("signatures", []):
        identity = sig.get("identity")
        if sig.get("token") != expected_token:
            log.warning(f"   ⚠️ Stale signature from '{identity}'.")
            continue
        pem = approver_keys.get(identity)
        if not pem:
            log.warning(f"   ⚠️ No public key found for signatory '{identity}'.")
            continue
        try:
            pub_key = serialization.load_pem_public_key(pem.encode("utf-8"))
            pub_key.verify(
                base64.b64decode(sig["signature_b64"]), expected_token.encode("utf-8")
            )
            log.info(f"   ✅ Valid signature from '{identity}'.")
            valid_signatures += 1
        except Exception:
            log.warning(f"   ⚠️ Verification failed for signature from '{identity}'.")
            continue

    quorum_config = approvers_config.get("quorum", {})
    mode = quorum_config.get("current_mode", "development")

    critical_paths_source = approvers_config.get(
        "critical_paths_source", "charter/constitution/critical_paths.yaml"
    )
    critical_paths_file = settings.REPO_PATH / ".intent" / critical_paths_source
    critical_paths_config = load_yaml_file(critical_paths_file)
    critical_paths = critical_paths_config.get("paths", [])

    is_critical = any(str(target_rel_path) == p for p in critical_paths)
    required_sigs = quorum_config.get(mode, {}).get(
        "critical" if is_critical else "standard", 1
    )

    if valid_signatures < required_sigs:
        log.error(
            f"❌ Approval failed: Quorum not met ({valid_signatures}/{required_sigs})."
        )
        raise typer.Exit(code=1)

    log.info("\n🐦 Spinning up canary environment for validation...")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        log.info(f"   -> Creating a clean copy of the repository at {tmp_path}...")

        shutil.copytree(
            settings.REPO_PATH,
            tmp_path,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", ".venv", "venv", "__pycache__"),
        )

        canary_env_path = tmp_path / ".env"
        env_file = settings.REPO_PATH / ".env"
        if env_file.exists():
            shutil.copy(env_file, canary_env_path)
            log.info("   -> Copied environment configuration to canary.")

        canary_target_path = tmp_path / target_rel_path
        canary_target_path.parent.mkdir(parents=True, exist_ok=True)
        canary_target_path.write_text(proposal.get("content", ""), encoding="utf-8")

        if canary_env_path.exists():
            log.info(f"   -> Loading canary environment from {canary_env_path}...")
            load_dotenv(dotenv_path=canary_env_path, override=True)

        log.info("🔬 Commanding canary to perform a self-audit...")
        auditor = ConstitutionalAuditor(repo_root_override=tmp_path)
        success, findings, unassigned_count = asyncio.run(
            auditor.run_full_audit_async()
        )

        if success:
            log.info("✅ Canary audit PASSED. Change is constitutionally valid.")
            archive_rollback_plan(proposal_name, proposal)
            live_target_path = settings.REPO_PATH / target_rel_path
            live_target_path.parent.mkdir(parents=True, exist_ok=True)
            live_target_path.write_text(proposal.get("content", ""), encoding="utf-8")
            proposal_path.unlink()
            log.info(f"✅ Successfully approved and applied '{proposal_name}'.")
        else:
            log.error(
                "❌ Canary audit FAILED. Proposal rejected; live system untouched."
            )
            if findings:
                console.print("\n[bold red]Canary Audit Findings:[/bold red]")
                table = Table()
                table.add_column("Severity")
                table.add_column("Check ID")
                table.add_column("Message")
                table.add_column("File:Line")
                for f in findings:
                    loc = (
                        f"{f.file_path}:{f.line_number}"
                        if f.line_number
                        else f.file_path
                    )
                    table.add_row(str(f.severity), f.check_id, f.message, loc)
                console.print(table)
            raise typer.Exit(code=1)
