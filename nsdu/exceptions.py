"""Exceptions for NSDU-specific errors.
"""


class NSDUError(Exception):
    """NSDU general error."""


class LoaderError(NSDUError):
    """Error of loader plugins."""


class LoaderConfigError(LoaderError):
    """Loader's config error."""


class CredNotFound(LoaderError):
    """Login credential not found. For cred loader."""


class DispatchTemplateNotFound(LoaderError):
    """Loader could not find the requested dispatch template."""


class DispatchApiError(NSDUError):
    """Dispatch API error."""


class CredOperationError(NSDUError):
    """Error about a login credential operation (e.g. add, remove)."""


class UnknownDispatchError(DispatchApiError):
    """This dispatch does not exist."""


class NotOwnerDispatchError(DispatchApiError):
    """You do not own this dispatch."""


class NationLoginError(DispatchApiError):
    """Failed to log in to nation."""


class DispatchConfigError(NSDUError):
    """Dispatch config error."""


class NonexistentCategoryError(DispatchConfigError):
    """Category or subcategory doesn't exist."""

    def __init__(self, category_type, category_value):
        self.category_type = category_type
        self.category_value = category_value
        super().__init__()
