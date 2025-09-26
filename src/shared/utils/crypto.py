# src/shared/utils/crypto.py
"""
Provides shared, constitutionally-governed cryptographic utilities for
tasks like signing and token generation.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from cryptography.hazmat.primitives import hashes


def _get_canonical_payload(proposal: Dict[str, Any]) -> str:
    """
    Creates a stable, sorted JSON string of the proposal's core intent,
    ignoring all other metadata like signatures. This is the single source
    of truth for what gets signed.
    """
    signable_data = {
        "target_path": proposal.get("target_path"),
        "action": proposal.get("action"),
        "justification": proposal.get("justification"),
        "content": proposal.get("content", ""),
    }
    return json.dumps(signable_data, sort_keys=True)


# ID: 38528901-21cb-4bbb-9f77-524beefdf990
def generate_approval_token(proposal: Dict[str, Any]) -> str:
    """
    Produces a deterministic token based on a canonical representation
    of the proposal's intent.
    """
    canonical_string = _get_canonical_payload(proposal)
    digest = hashes.Hash(hashes.SHA256())
    digest.update(canonical_string.encode("utf-8"))

    return f"core-proposal-v6:{digest.finalize().hex()}"
