# src/shared/exceptions.py
"""Exception hierarchy for CORE system."""

from __future__ import annotations


# ID: bbaf6baf-a332-4856-b43f-bac7b47639cc
class CoreException(Exception):
    """Base exception for all CORE errors."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


# ID: core-error-with-exit-code
# ID: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
class CoreError(CoreException):
    """
    Base exception for CORE operational errors with exit code support.

    Extends CoreException to add exit_code handling for CLI operations.
    All service-level exceptions should inherit from this class.

    Attributes:
        exit_code: Exit code for CLI operations (default: 1)

    Examples:
        >>> class MyServiceError(CoreError):
        ...     '''Custom error for my service.'''
        ...     pass
        >>> raise MyServiceError("Operation failed", exit_code=2)
    """

    def __init__(self, message: str, *, exit_code: int = 1):
        """
        Initialize CORE error with message and exit code.

        Args:
            message: Human-readable error description
            exit_code: Exit code for CLI operations (default: 1)
        """
        super().__init__(message)
        self.exit_code = exit_code


# ID: 129702f0-59e1-4fbe-b678-6573d871b0ba
class SecretsError(CoreException):
    """Base exception for secrets management errors."""

    pass


# ID: 19715775-1605-4127-be9f-1bb2c9e50572
class SecretNotFoundError(SecretsError):
    """Requested secret does not exist."""

    def __init__(self, key: str):
        super().__init__(f"Secret not found: {key}")
        self.key = key
