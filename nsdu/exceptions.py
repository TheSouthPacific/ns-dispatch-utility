"""Exceptions for NSDU-specific errors.
"""


class AppError(Exception):
    """NSDU general error."""


class UserError(AppError):
    """User error."""
