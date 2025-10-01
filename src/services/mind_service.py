# src/services/mind_service.py
"""
Provides a constitutionally-governed, read-only interface to the Mind (.intent).
This service is the single, authoritative broker for accessing constitutional
knowledge, ensuring that the Body does not have arbitrary access to the filesystem
of the Mind, thus upholding the `separation_of_concerns` principle.
"""
from __future__ import annotations

from typing import Any

from shared.config import settings
from shared.utils.yaml_processor import strict_yaml_processor


# ID: d8390520-9c5b-4af3-881f-78f79601c7ff
class MindService:
    """A read-only API for accessing constitutional files from the .intent directory."""

    # ID: dda66271-6df0-4f6e-9a24-fe4ece6bafeb
    def load_policy(self, logical_path: str) -> dict[str, Any]:
        """
        Loads and parses a policy file using its logical path from meta.yaml.
        """
        policy_path = settings.get_path(logical_path)
        # DELEGATE to the canonical processor
        return strict_yaml_processor.load_strict(policy_path)


# ID: 8fd3d8eb-f721-4628-8263-94c6dd6d5171
def get_mind_service() -> MindService:
    """Factory function to get an instance of the MindService."""
    return MindService()
