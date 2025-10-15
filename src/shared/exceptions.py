# src/shared/exceptions.py
"""Exception hierarchy for CORE system."""


# ID: bbaf6baf-a332-4856-b43f-bac7b47639cc
class CoreException(Exception):
    """Base exception for all CORE errors."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


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
