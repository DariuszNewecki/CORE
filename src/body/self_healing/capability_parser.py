# src/features/self_healing/capability_parser.py

"""
Capability Parser - Extract Capability Tags from Code

CONSTITUTIONAL ALIGNMENT:
- Single Responsibility: Parse capability tags
- Stateless utility
- No side effects

Extracted from complexity_service.py to separate parsing concerns.
"""

from __future__ import annotations

import re

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 2d14352d-e585-47db-b0bf-bcbf5f8f1eec
# ID: 1a2b3c4d-5e6f-7890-abcd-ef1234567890
class CapabilityParser:
    """
    Parses capability tags from code.

    Capabilities are declared with # CAPABILITY: tag_name
    """

    # ID: 36fa2c9b-0897-4c0b-95c9-3d153fe1b24f
    # ID: 2b3c4d5e-6f7a-8901-bcde-f12345678901
    @staticmethod
    # ID: 6188e431-7097-4e73-a523-2edfed57231c
    def extract_capabilities(code: str) -> list[str]:
        """
        Extract # CAPABILITY tags from code.

        Args:
            code: Source code to parse

        Returns:
            List of capability tag names

        Example:
            # CAPABILITY: file_operations
            # CAPABILITY: database_access
            -> ["file_operations", "database_access"]
        """
        return re.findall(r"#\s*CAPABILITY:\s*(\S+)", code)

    # ID: 95b2a7ec-fdda-48b5-b048-2f43e9314aa5
    # ID: 3c4d5e6f-7a8b-9012-cdef-123456789012
    @staticmethod
    # ID: ac4ff8e2-924e-4d81-a744-55c6ce91b08e
    def has_capability(code: str, capability: str) -> bool:
        """
        Check if code declares a specific capability.

        Args:
            code: Source code to check
            capability: Capability name to search for

        Returns:
            True if capability is declared
        """
        capabilities = CapabilityParser.extract_capabilities(code)
        return capability in capabilities
