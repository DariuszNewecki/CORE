# src/system/admin/proposals.py
"""
Intent: Proposal lifecycle commands (list, sign, approve) for constitution-governed changes.
Integrates with the ConstitutionalAuditor via a canary workspace before applying changes.
"""

from __future__ import annotations

import base64
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import typer
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from shared.config import settings
from shared.logger import getLogger
from system.admin.utils import (
    archive_rollback_plan,
    generate_approval_token,
    load_private_key,
    load_yaml_file,
    save_yaml_file,
)
from system.governance.constitutional_auditor import ConstitutionalAuditor

log = getLogger("core_admin")

# Create a Typer app for the "proposals" subcommand group
proposals_app = typer.Typer(help="Work with constitutional proposals")


@proposals_app.command("list")
def proposals_list() -> None:
    """List pending constitutional proposals and display their justification, target path, and signature/quorum status."""
    log.info("🔍 Finding pending constitutional proposals...")
    proposals_dir = settings.MIND / "proposals"
    proposals_dir.mkdir(exist_ok=True)
    proposals = sorted(proposals_dir.glob("cr-*.yaml"))

    if not proposals:
        log.info("✅ No pending proposals found.")
        return

    log.info(f"Found {len(proposals)} pending proposal(s):")
    approvers_config = load_yaml_file(settings.MIND / "constitution" / "approvers.yaml")

    for prop_path in proposals:
        config = load_yaml_file(prop_path)
        justification = config.get("justification", "No justification provided.")
        is_critical = any(
            config.get("target_path", "").endswith(p)
            for p in approvers_config.get("critical_paths", [])
        )
        required = approvers_config.get("quorum", {}).get(
            "critical" if is_critical else "standard", 1
        )
        current = len(config.get("signatures", []))
        status = "✅ Ready" if current >= required else f"⏳ {current}/{required} sigs"

        log.info(f"\n  - **{prop_path.name}**: {justification.strip()}")
        log.info(f"    Target: {config.get('target_path')}")
        log.info(f"    Status: {status} ({'Critical' if is_critical else 'Standard'})")


@proposals_app.command("sign")
def proposals_sign(
    proposal_name: str = typer.Argument(
        ...,  # The '...' makes this argument required
        help="Filename of the proposal to sign (e.g., 'cr-new-policy.yaml').",
    ),
) -> None:
    """Sign a proposal with the operator's private key (content-bound token)."""
    log.info(f"✍️ Signing proposal: {proposal_name}")
    proposal_path = settings.MIND / "proposals" / proposal_name
    if not proposal_path.exists():
        log.error(f"❌ Proposal '{proposal_name}' not found.")
        raise typer.Exit(code=1)

    proposal = load_yaml_file(proposal_path)
    private_key = load_private_key()

    token = generate_approval_token(proposal)
    signature = private_key.sign(token.encode("utf-8"))

    identity = typer.prompt(
        "Enter your identity (e.g., name@domain.com) to associate with this signature"
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


@proposals_app.command("approve")
def proposals_approve(
    proposal_name: str = typer.Argument(
        ...,  # The '...' makes this argument required
        help="Filename of the proposal to approve.",
    ),
) -> None:
    """Verify signatures/quorum, run a canary constitutional audit, then apply the proposal if valid."""
    log.info(f"🚀 Attempting to approve proposal: {proposal_name}")
    proposal_path = settings.MIND / "proposals" / proposal_name
    if not proposal_path.exists():
        log.error(f"❌ Proposal '{proposal_name}' not found.")
        raise typer.Exit(code=1)

    proposal = load_yaml_file(proposal_path)
    target_rel_path = proposal.get("target_path")
    if not target_rel_path:
        log.error("❌ Proposal is invalid: missing 'target_path'.")
        raise typer.Exit(code=1)

    log.info("🔐 Verifying cryptographic signatures...")
    approvers_config = load_yaml_file(settings.MIND / "constitution" / "approvers.yaml")
    approver_keys = {
        a["identity"]: a["public_key"] for a in approvers_config.get("approvers", [])
    }

    valid_signatures = 0
    for sig in proposal.get("signatures", []):
        identity = sig.get("identity")
        pem = approver_keys.get(identity)
        if not pem:
            continue
        try:
            pub_key = serialization.load_pem_public_key(pem.encode("utf-8"))
            if not isinstance(pub_key, ed25519.Ed25519PublicKey):
                log.warning(
                    f"   ⚠️ Key for '{identity}' is not a valid Ed25519 signing key. Skipping."
                )
                continue

            pub_key.verify(
                base64.b64decode(sig["signature_b64"]), sig["token"].encode("utf-8")
            )
            if sig["token"] == generate_approval_token(proposal):
                log.info(f"   ✅ Valid signature from '{identity}'.")
                valid_signatures += 1
            else:
                log.warning(
                    f"   ⚠️ Signature from '{identity}' is for outdated content."
                )
        except (InvalidSignature, ValueError, TypeError):
            log.warning(f"   ⚠️ Invalid signature for '{identity}'.")

    is_critical = any(
        str(target_rel_path).endswith(p)
        for p in approvers_config.get("critical_paths", [])
    )
    required = approvers_config.get("quorum", {}).get(
        "critical" if is_critical else "standard", 1
    )

    if valid_signatures < required:
        log.error(
            f"❌ Approval failed: Quorum not met. Have {valid_signatures}/{required} valid signatures."
        )
        raise typer.Exit(code=1)

    log.info("\n🧠 Generating fresh Knowledge Graph before canary validation...")
    try:
        subprocess.run(
            [sys.executable, "-m", "src.system.tools.codegraph_builder"],
            cwd=settings.REPO_PATH,
            check=True,
            capture_output=True,
        )
        log.info("   -> Knowledge Graph regenerated successfully.")
    except subprocess.CalledProcessError as e:
        log.error(
            f"❌ Failed to regenerate Knowledge Graph. Aborting. Stderr: {e.stderr.decode()}"
        )
        raise typer.Exit(code=1)

    log.info("\n🐦 Spinning up canary environment for validation...")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        log.info(f"   -> Creating a clean clone of the repository at {tmp_path}...")
        try:
            subprocess.run(
                ["git", "clone", str(settings.REPO_PATH), "."],
                cwd=tmp_path,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            log.error(
                f"❌ Failed to create clean git clone for canary. Aborting. Stderr: {e.stderr.decode()}"
            )
            raise typer.Exit(code=1)

        env_file = settings.REPO_PATH / ".env"
        if env_file.exists():
            shutil.copy(env_file, tmp_path / ".env")
            log.info("   -> Copied environment configuration to canary.")

        canary_target_path = tmp_path / target_rel_path
        canary_target_path.parent.mkdir(parents=True, exist_ok=True)
        canary_target_path.write_text(proposal.get("content", ""), encoding="utf-8")

        log.info("🔬 Commanding canary to perform a self-audit...")
        auditor = ConstitutionalAuditor(repo_root_override=tmp_path)
        success = auditor.run_full_audit()

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
            raise typer.Exit(code=1)


# This function will now be simplified to just register the app
def register(app: typer.Typer) -> None:
    """Register proposal lifecycle commands under the admin CLI."""
    app.add_typer(proposals_app, name="proposals")
