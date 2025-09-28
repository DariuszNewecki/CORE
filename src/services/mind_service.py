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
from shared.config_loader import load_yaml_file


# ID: d8390520-9c5b-4af3-881f-78f79601c7ff
class MindService:
    """A read-only API for accessing constitutional files from the .intent directory."""

    # ID: dda66271-6df0-4f6e-9a24-fe4ece6bafeb
    def load_policy(self, logical_path: str) -> dict[str, Any]:
        """
        Loads and parses a policy file using its logical path from meta.yaml.

        Args:
            logical_path: The dot-notation logical path (e.g., "charter.policies.safety_policy").

        Returns:
            The parsed content of the YAML policy file.

        Raises:
            FileNotFoundError: If the policy file cannot be found.
        """
        policy_path = settings.get_path(logical_path)
        return load_yaml_file(policy_path)


# ID: 8fd3d8eb-f721-4628-8263-94c6dd6d5171
def get_mind_service() -> MindService:
    """Factory function to get an instance of the MindService."""
    return MindService()
