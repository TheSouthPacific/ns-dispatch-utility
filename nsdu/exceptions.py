"""Exceptions for NSDU-specific errors.
"""

class NSDUError(Exception):
    """NSDU general error.
    """


class ConfigError(NSDUError):
    """NSDU general config error.
    """


class LoaderError(NSDUError):
    """Loader plugin error.
    """

    def __init__(self, suppress_nsdu_error=True):
        self.suppress_nsdu_error = suppress_nsdu_error
        super().__init__()


class DispatchTextNotFound(LoaderError):
    """Dispatch text not found error.
    """


class DispatchAPIError(NSDUError):
    """Dispatch API error.
    """


class UnknownDispatchError(DispatchAPIError):
    """This dispatch does not exist.
    """


class NotOwnerDispatchError(DispatchAPIError):
    """You do not own this dispatch.
    """


class NationLoginError(DispatchAPIError):
    """Failed to log in to nation.
    """


class DispatchUpdatingError(NSDUError):
    """Dispatch update error.
    """


class NonexistentCategoryError(DispatchUpdatingError):
    """Category or subcategory doesn't exist.
    """

    def __init__(self, category_type, category_value):
        self.category_type = category_type
        self.category_value = category_value
        super().__init__()


class DispatchRenderingError(NSDUError):
    """Dispatch rendering error.
    """


class BBParsingError(DispatchRenderingError):
    """BBCode parsing errors.
    """


class TemplateRendererError(DispatchRenderingError):
    """Jinja template rendering errors.
    """
