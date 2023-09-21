"""API for loader plugins.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import pluggy

from nsdu import exceptions, info
from nsdu.config import Config

TemplateVars = dict[str, Any]
BbcConfig = Config


class DispatchOpResult(Enum):
    """Operation result type."""

    SUCCESS = 1
    FAILURE = 2


class DispatchOp(Enum):
    """Dispatch operation type."""

    CREATE = 1
    EDIT = 2
    DELETE = 3


@dataclass(frozen=True)
class DispatchMetadata:
    """Contains the metadata of a dispatch."""

    ns_id: str | None
    operation: DispatchOp
    owner_nation: str
    title: str
    category: str
    subcategory: str


class LoaderError(exceptions.AppError):
    """Error from loader plugins."""


class CredNotFound(LoaderError):
    """Login credential not found. This exception is for credential loaders."""


class DispatchTemplateNotFound(LoaderError):
    """Dispatch template not found. This exception is for dispatch loaders."""


DispatchesMetadata = dict[str, DispatchMetadata]
LoginCreds = dict[str, str]

dispatch_loader_specs = pluggy.HookspecMarker(info.DISPATCH_LOADER_PROJ)
dispatch_loader = pluggy.HookimplMarker(info.DISPATCH_LOADER_PROJ)

template_var_loader_specs = pluggy.HookspecMarker(info.TEMPLATE_VAR_LOADER_PROJ)
template_var_loader = pluggy.HookimplMarker(info.TEMPLATE_VAR_LOADER_PROJ)

simple_bbc_loader_specs = pluggy.HookspecMarker(info.SIMPLE_BBC_LOADER_PROJ)
simple_bbc_loader = pluggy.HookimplMarker(info.SIMPLE_BBC_LOADER_PROJ)

cred_loader_specs = pluggy.HookspecMarker(info.CRED_LOADER_PROJ)
cred_loader = pluggy.HookimplMarker(info.CRED_LOADER_PROJ)


@dispatch_loader_specs(firstresult=True)
def init_dispatch_loader(loaders_config: Config) -> object:
    """Return a dispatch loader object which holds any state
    this loader should keep while NSDU is running.

    Args:
        loaders_config (Config): Loaders' config

    Return:
        object: Loader object
    """


@dispatch_loader_specs(firstresult=True)
def get_dispatch_metadata(loader: object) -> DispatchesMetadata:
    """Return metadata of dispatches to work on.

    Args:
        loader (object): Loader object

    Return:
        DispatchesMetadata: Metadata keyed by dispatch name
    """

    raise NotImplementedError


@dispatch_loader_specs(firstresult=True)
def get_dispatch_template(loader: object, name: str) -> str:
    """Return template text of a dispatch.

    Args:
        loader (object): Loader object
        name (str): Dispatch name

    Return:
        str: Dispatch template text
    """

    raise NotImplementedError


@dispatch_loader_specs(firstresult=True)
def after_update(
    loader: object,
    name: str,
    op: DispatchOp,
    result: DispatchOpResult,
    result_time: datetime,
    result_details: str | None,
) -> None:
    """Run after a dispatch operation has finished to get its result.

    Args:
        loader (object): Loader object
        name (str): Dispatch name
        op (DispatchOperation): Operation type
        result (DispatchOpResult): Result type
        result_time (datetime): Time the operation finished
        result_details (str | None): Result details
    """

    raise NotImplementedError


@dispatch_loader_specs(firstresult=True)
def add_dispatch_id(loader: object, name: str, dispatch_id: str) -> None:
    """Add or update dispatch ID when a new dispatch is made.

    Args:
        loader (object): Loader object
        name (str): Dispatch name
        dispatch_id (str): Dispatch ID
    """

    raise NotImplementedError


@dispatch_loader_specs(firstresult=True)
def cleanup_dispatch_loader(loader: object) -> None:
    """Run cleanup operations on the loader such as saving files
    when NSDU doesn't use it anymore.

    Args:
        loader (object): Loader object
    """

    raise NotImplementedError


@template_var_loader_specs
def get_template_vars(loaders_config: Config) -> TemplateVars:
    """Return template variable values.

    Args:
        loaders_config (Config): Loaders' configuration

    Return:
        TemplateVars: Variable values
    """

    raise NotImplementedError


@simple_bbc_loader_specs(firstresult=True)
def get_simple_bbc_config(loaders_config: Config) -> BbcConfig:
    """Return a credential loader object which holds any state
    this loader should keep while NSDU is running.

    Args:
        loaders_config (Config): Loaders' configuration

    Return:
        BbcConfig: Configuration
    """

    raise NotImplementedError


@cred_loader_specs(firstresult=True)
def init_cred_loader(loaders_config: Config) -> object:
    """Create and return a loader object to persist.

    Args:
        loaders_config (Config): Loaders' configuration

    Return:
        object: Loader object
    """

    raise NotImplementedError


@cred_loader_specs(firstresult=True)
def get_cred(loader: object, name: str) -> str:
    """Get the autologin code of a nation.

    Args:
        loader (object): Loader object
        name (str): Nation name

    Return:
        str: Autologin code
    """

    raise NotImplementedError


@cred_loader_specs(firstresult=True)
def add_cred(loader: object, name: str, x_autologin: str) -> None:
    """Add a nation login credential.

    Args:
        loader (object): Loader object
        name (str): Nation name
        x_autologin (str): Autologin code.
    """

    raise NotImplementedError


@cred_loader_specs(firstresult=True)
def remove_cred(loader: object, name: str) -> None:
    """Delete a nation login credential.

    Args:
        loader (object): Loader object
        name (str): Nation name
    """

    raise NotImplementedError


@cred_loader_specs(firstresult=True)
def cleanup_cred_loader(loader: object) -> None:
    """Run cleanup operations on the loader such as saving files
    when NSDU doesn't use it anymore.

    Args:
        loader (object): Loader object
    """

    raise NotImplementedError
