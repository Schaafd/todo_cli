"""Centralized application error taxonomy."""


class TodoCliError(Exception):
    """Base error for all Todo CLI domain/application failures."""


class ValidationError(TodoCliError):
    """Raised when input or entity validation fails."""


class ConfigurationError(TodoCliError):
    """Raised when configuration is invalid or unavailable."""


class StorageError(TodoCliError):
    """Raised for persistence and serialization errors."""


class ProviderError(TodoCliError):
    """Raised for external provider/network failures."""
