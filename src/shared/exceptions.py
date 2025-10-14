# src/shared/exceptions.py
"""Exception hierarchy for CORE system."""


class CoreException(Exception):
    """Base exception for all CORE errors."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class SecretsError(CoreException):
    """Base exception for secrets management errors."""

    pass


class SecretNotFoundError(SecretsError):
    """Requested secret does not exist."""

    def __init__(self, key: str):
        super().__init__(f"Secret not found: {key}")
        self.key = key
