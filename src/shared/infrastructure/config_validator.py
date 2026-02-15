# src/shared/infrastructure/config_validator.py
# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567896

"""
Config Validator - Phase 4 Hardening.
Enforces that the environment matches the required schema.
"""

from __future__ import annotations

import re
from typing import ClassVar

from shared.config import settings
from shared.logger import getLogger
from shared.models.validation_result import ValidationResult


logger = getLogger(__name__)


# ID: dd5d8e9d-d0ba-4fc9-9a8b-4020d367c564
class ConfigValidator:
    """
    Validates environment configuration against a strict schema.
    """

    # Schema definition: key -> (is_required, regex_pattern, hint)
    # RUF012 FIX: Annotated with ClassVar as required by Ruff
    SCHEMA: ClassVar[dict[str, tuple[bool, str, str]]] = {
        "DATABASE_URL": (
            True,
            r"^postgresql\+asyncpg://",
            "Must be a valid PostgreSQL asyncpg URL",
        ),
        "QDRANT_URL": (True, r"^http", "Must be a valid URL for Qdrant API"),
        "LLM_API_KEY": (True, r".+", "Cannot be empty"),
        "CORE_MASTER_KEY": (
            True,
            r".{32,}",
            "Must be a Fernet-compatible Base64 key (32+ chars)",
        ),
        "LOG_LEVEL": (
            False,
            r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
            "Must be a standard Python log level",
        ),
    }

    # ID: 4b841f90-bde6-4d87-bc23-7f9d70cb5c9e
    def validate_env(self) -> ValidationResult:
        """
        Validates the current settings against the hardcoded schema.
        """
        errors = []

        for key, (required, pattern, hint) in self.SCHEMA.items():
            value = getattr(settings, key, None)

            # 1. Presence Check
            if not value:
                if required:
                    errors.append(f"MISSING: {key} - {hint}")
                continue

            # 2. Format Check (Regex)
            if not re.search(pattern, str(value)):
                errors.append(f"INVALID FORMAT: {key} - {hint}")

        is_ok = len(errors) == 0
        return ValidationResult(ok=is_ok, errors=errors, metadata={"source": ".env"})
