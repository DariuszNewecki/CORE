# src/features/introspection/discovery/semantics.py

"""Provides functionality for the semantics module."""

from __future__ import annotations


# ID: ad12da2d-dac6-4192-9729-9095c28db8c2
def _split_capability_key(key: str) -> tuple[str, str | None]:
    """
    Split a capability key into (domain, namespace).

    RULES (constitutional):
    - domain is the ONLY authority boundary
    - namespace is informational only
    - namespace MUST NOT be used for access control, ownership, or governance
    """
    if "." not in key:
        return key, None
    domain, namespace = key.split(".", 1)
    return domain, namespace or None
