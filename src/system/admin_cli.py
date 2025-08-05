# src/system/admin_cli.py
"""
The command-line interface for the CORE Human Operator.
Provides safe, governed commands for managing the system's constitution.
"""

import sys
import shutil
import tempfile
import json
import base64
import os
from pathlib import Path
from datetime import datetime

from shared.path_utils import get_repo_root
from shared.config_loader import load_config
from shared.logger import getLogger
from system.governance.constitutional_auditor import ConstitutionalAuditor

# Import cryptography components
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

log = getLogger("core_admin")

# --- Configuration ---
REPO_ROOT = get_repo_root()
INTENT_DIR = REPO_ROOT / ".intent"
SRC_DIR = REPO_ROOT / "src"
PROPOSALS_DIR = INTENT_DIR / "proposals"
CONSTITUTION_DIR = INTENT_DIR / "constitution"
ROLLBACKS_DIR = CONSTITUTION_DIR / "rollbacks"
KEY_STORAGE_DIR = Path.home() / ".config" / "core"

# --- Helper Functions ---

def _generate_approval_token(proposal_content: str) -> str:
    """Creates a unique, deterministic token for proposal content using a secure hash."""
    digest = hashes.Hash(hashes.SHA256())
    digest.update(proposal_content.encode('utf-8'))
    content_hash = digest.finalize().hex()
    return f"core-proposal-v1:{content_hash}"

def _load_private_key() -> ed25519.Ed25519PrivateKey:
    """Loads the user's private key from the secure storage location."""
    key_path = KEY_STORAGE_DIR / "private.key"
    if not key_path.exists():
        log.error("❌ Private key not found. Please run 'core-admin keygen' to create one.")
        sys.exit(1)
    
    with open(key_path, "rb") as key_file:
        return serialization.load_pem_private_key(
            key_file.read(),
            password=None
        )

# --- CLI Commands ---

def keygen(identity: str):
    """Generates a new cryptographic key pair for a user."""
    log.info(f"🔑 Generating new Ed25519 key pair for identity: {identity}")
    KEY_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    private_key_path = KEY_STORAGE_DIR / "private.key"

    if private_key_path.exists():
        log.warning("⚠️ A private key already exists. Overwriting it will invalidate your old identity.")
        if input("Are you sure you want to continue? (y/n): ").lower() != 'y':
            log.info("Aborted key generation.")
            return

    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Save private key securely
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    with open(private_key_path, "wb") as f:
        f.write(pem_private)
    os.chmod(private_key_path, 0o600)  # Set file permissions to user-only

    # Display public key for user
    pem_public = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    log.info("\n✅ Private key saved securely to: " + str(private_key_path))
    log.info("\n📋 Add the following JSON object to the 'approvers' list in '.intent/constitution/approvers.pub':")
    print(json.dumps({
        "identity": identity,
        "public_key": pem_public.decode('utf-8').strip(),
        "role": "contributor",
        "description": "Newly generated key"
    }, indent=2))

def sign_proposal(proposal_name: str):
    """Signs a proposal and adds the signature to the proposal file."""
    log.info(f"✍️ Signing proposal: {proposal_name}")
    proposal_path = PROPOSALS_DIR / proposal_name
    if not proposal_path.exists():
        log.error(f"❌ Proposal '{proposal_name}' not found.")
        return

    proposal = load_config(proposal_path, "yaml")
    private_key = _load_private_key()
    
    token = _generate_approval_token(proposal.get("content", ""))
    signature = private_key.sign(token.encode('utf-8'))
    
    # Get identity from user
    identity = input("Enter your identity (e.g., name@domain.com) to associate with this signature: ").strip()
    
    if 'signatures' not in proposal:
        proposal['signatures'] = []
    
    # Check if this identity has already signed
    if any(s['identity'] == identity for s in proposal['signatures']):
        log.warning(f"⚠️ Identity '{identity}' has already signed this proposal. Overwriting previous signature.")
        proposal['signatures'] = [s for s in proposal['signatures'] if s['identity'] != identity]

    proposal['signatures'].append({
        'identity': identity,
        'signature_b64': base64.b64encode(signature).decode('utf-8'),
        'token': token,
        'timestamp': datetime.utcnow().isoformat() + "Z"
    })
    
    with open(proposal_path, "w") as f:
        # Use json for consistency since YAML can have formatting quirks
        json.dump(proposal, f, indent=2)
        
    log.info("✅ Signature added to proposal file.")
    log.info(f"   Identity: {identity}")
    log.info(f"   Signature: {base64.b64encode(signature).decode('utf-8')[:30]}...")

def list_proposals():
    """Lists all pending constitutional amendment proposals."""
    log.info("🔍 Finding pending constitutional proposals...")
    PROPOSALS_DIR.mkdir(exist_ok=True)
    proposals = sorted(list(PROPOSALS_DIR.glob("cr-*.yaml")))
    
    if not proposals:
        log.info("✅ No pending proposals found.")
        return

    log.info(f"Found {len(proposals)} pending proposal(s):")
    # --- FIX: Load approvers.pub as YAML ---
    approvers_config = load_config(CONSTITUTION_DIR / "approvers.pub", "yaml")
    
    for prop_path in proposals:
        config = load_config(prop_path, "yaml")
        justification = config.get('justification', 'No justification provided.')
        
        is_critical = any(config.get("target_path", "").endswith(p) for p in approvers_config.get("critical_paths", []))
        required = approvers_config.get("quorum", {}).get("critical" if is_critical else "standard", 1)
        current = len(config.get('signatures', []))
        
        status = "✅ Ready for Approval" if current >= required else f"⏳ {current}/{required} signatures"
        
        log.info(f"\n  - {prop_path.name}: {justification}")
        log.info(f"    Target: {config.get('target_path')}")
        log.info(f"    Status: {status} ({'Critical' if is_critical else 'Standard'})")

def _archive_rollback_plan(proposal_name: str, proposal: dict):
    """Saves the rollback plan to a dedicated archive."""
    rollback_plan = proposal.get("rollback_plan")
    if not rollback_plan:
        return
    
    ROLLBACKS_DIR.mkdir(exist_ok=True)
    archive_path = ROLLBACKS_DIR / f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{proposal_name}.json"
    with open(archive_path, "w") as f:
        json.dump({
            "proposal_name": proposal_name,
            "target_path": proposal.get("target_path"),
            "justification": proposal.get("justification"),
            "rollback_plan": rollback_plan
        }, f, indent=2)
    log.info(f"📖 Rollback plan archived to {archive_path}")

def approve_proposal(proposal_name: str):
    """Approves and applies a proposal after successful canary check and signature verification."""
    log.info(f"🚀 Attempting to approve proposal: {proposal_name}")
    proposal_path = PROPOSALS_DIR / proposal_name
    if not proposal_path.exists():
        log.error(f"❌ Proposal '{proposal_name}' not found.")
        return

    proposal = load_config(proposal_path, "yaml")
    target_rel_path = proposal.get("target_path")
    if not target_rel_path:
        log.error("❌ Proposal is invalid: missing 'target_path'.")
        return

    # --- SIGNATURE VERIFICATION ---
    log.info("🔐 Verifying cryptographic signatures...")
    # --- FIX: Load approvers.pub as YAML ---
    approvers_config = load_config(CONSTITUTION_DIR / "approvers.pub", "yaml")
    approver_keys = {app['identity']: app['public_key'] for app in approvers_config.get("approvers", [])}
    
    valid_signatures = 0
    for sig_data in proposal.get('signatures', []):
        identity = sig_data.get('identity')
        public_key_pem = approver_keys.get(identity)
        if not public_key_pem:
            log.warning(f"⚠️ Signature from unknown identity '{identity}' skipped.")
            continue

        try:
            pub_key = serialization.load_pem_public_key(public_key_pem.encode('utf-8'))
            pub_key.verify(
                base64.b64decode(sig_data.get('signature_b64', '')),
                sig_data.get('token', '').encode('utf-8')
            )
            # Crucially, verify the token in the signature matches the current proposal content
            expected_token = _generate_approval_token(proposal.get("content", ""))
            if sig_data.get('token') == expected_token:
                log.info(f"   ✅ Valid signature found for '{identity}'.")
                valid_signatures += 1
            else:
                log.warning(f"   ⚠️ Signature from '{identity}' is for outdated proposal content. Ignoring.")
        except (InvalidSignature, ValueError, TypeError) as e:
            log.warning(f"   ⚠️ Invalid signature for '{identity}': {e}")

    is_critical = any(target_rel_path.endswith(p) for p in approvers_config.get("critical_paths", []))
    required = approvers_config.get("quorum", {}).get("critical" if is_critical else "standard", 1)
    
    if valid_signatures < required:
        log.error(f"❌ Approval failed: Quorum not met. Have {valid_signatures}/{required} valid signatures.")
        return

    # --- THE CANARY CHECK ---
    log.info("\n🐦 Spinning up temporary 'canary' environment for validation...")
    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        shutil.copytree(INTENT_DIR, temp_dir / ".intent")
        shutil.copytree(SRC_DIR, temp_dir / "src")
        
        canary_target_path = temp_dir / target_rel_path
        canary_target_path.parent.mkdir(parents=True, exist_ok=True)
        canary_target_path.write_text(proposal.get("content", ""), encoding="utf-8")
        
        log.info("🔬 Commanding canary to perform a self-audit...")
        auditor = ConstitutionalAuditor(repo_root_override=temp_dir)
        success = auditor.run_full_audit()

        if success:
            log.info("✅ Canary audit PASSED. The proposed change is constitutionally valid.")
            log.info("Applying change to the live .intent/ directory...")
            
            _archive_rollback_plan(proposal_name, proposal)
            
            live_target_path = REPO_ROOT / target_rel_path
            live_target_path.parent.mkdir(parents=True, exist_ok=True)
            live_target_path.write_text(proposal.get("content", ""), encoding="utf-8")
            
            proposal_path.unlink()
            log.info(f"✅ Successfully approved and applied '{proposal_name}'.")
        else:
            log.error("❌ Canary audit FAILED. The proposed change would create an inconsistent state.")
            log.error("Proposal has been rejected. The live system remains untouched.")

def main():
    """Main entry point for the admin CLI."""
    if len(sys.argv) < 2:
        print("Usage: core-admin <command> [args]")
        print("Commands:")
        print("  keygen <identity>        - Generate a new key pair (e.g., keygen name@domain.com)")
        print("  proposals-list           - List all pending constitutional proposals")
        print("  proposals-sign <name>    - Add your signature to a proposal")
        print("  proposals-approve <name> - Verify signatures and apply an approved proposal")
        sys.exit(1)
        
    command = sys.argv[1]
    
    if command == "keygen":
        if len(sys.argv) < 3: log.error("Usage: core-admin keygen <your-identity>"); sys.exit(1)
        keygen(sys.argv[2])
    elif command == "proposals-list":
        list_proposals()
    elif command == "proposals-sign":
        if len(sys.argv) < 3: log.error("Usage: core-admin proposals-sign <proposal-filename>"); sys.exit(1)
        sign_proposal(sys.argv[2])
    elif command == "proposals-approve":
        if len(sys.argv) < 3: log.error("Usage: core-admin proposals-approve <proposal-filename>"); sys.exit(1)
        approve_proposal(sys.argv[2])
    else:
        log.error(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()