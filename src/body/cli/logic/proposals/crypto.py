# src/body/cli/logic/proposals/crypto.py

"""Refactored logic for src/body/cli/logic/proposals/crypto.py."""

from __future__ import annotations

import base64
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from shared.logger import getLogger
from shared.utils.crypto import generate_approval_token


logger = getLogger(__name__)


# ID: c9b3551a-acde-4630-ac38-5257434fc951
def verify_signatures(proposal: dict[str, Any], approver_keys: dict[str, str]) -> int:
    """Verifies all signatures and returns the count of valid ones."""
    expected_token = generate_approval_token(proposal)
    valid = 0
    for sig in proposal.get("signatures", []):
        identity = sig.get("identity")
        if sig.get("token") != expected_token:
            logger.warning("Stale signature from '%s'.", identity)
            continue
        pem = approver_keys.get(identity)
        if not pem:
            logger.warning("No public key found for '%s'.", identity)
            continue
        try:
            pub_key: Ed25519PublicKey = serialization.load_pem_public_key(
                pem.encode("utf-8")
            )
            pub_key.verify(
                base64.b64decode(sig["signature_b64"]), expected_token.encode("utf-8")
            )
            logger.info("Valid signature from '%s'.", identity)
            valid += 1
        except Exception:
            logger.warning("Verification failed for '%s'.", identity)
    return valid
