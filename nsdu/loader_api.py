"""API for loader plugins.
"""

import datetime
from typing import Any, Mapping

import pluggy

from nsdu import info


dispatch_loader_specs = pluggy.HookspecMarker(info.DISPATCH_LOADER_PROJ)
dispatch_loader = pluggy.HookimplMarker(info.DISPATCH_LOADER_PROJ)

template_var_loader_specs = pluggy.HookspecMarker(info.TEMPLATE_VAR_LOADER_PROJ)
template_var_loader = pluggy.HookimplMarker(info.TEMPLATE_VAR_LOADER_PROJ)

simple_bb_loader_specs = pluggy.HookspecMarker(info.SIMPLE_BB_LOADER_PROJ)
simple_bb_loader = pluggy.HookimplMarker(info.SIMPLE_BB_LOADER_PROJ)

cred_loader_specs = pluggy.HookspecMarker(info.CRED_LOADER_PROJ)
cred_loader = pluggy.HookimplMarker(info.CRED_LOADER_PROJ)


@dispatch_loader_specs(firstresult=True)
def init_dispatch_loader(config: Mapping[str, dict]) -> object:
    """Create and return a loader object to persist.

    Args:
        config (Mapping[str, dict]): Loader's configuration

    Return:
        Loader object
    """


@dispatch_loader_specs(firstresult=True)
def get_dispatch_config(loader: object) -> dict[str, dict]:
    """Get configuration of dispatches as a dict.

    Args:
        loader: Loader

    Return:
        dict[str, dict]: Dispatch configuration
    """


@dispatch_loader_specs(firstresult=True)
def get_dispatch_template(loader: object, name: str) -> str:
    """Get template text of a dispatch.

    Args:
        loader: Loader

    Return:
        str: Dispatch content text
    """


@dispatch_loader_specs(firstresult=True)
def after_update(
    loader: object, name: str, action: str, result: str, result_time: datetime.datetime
):
    """Run after a dispatch has finished updating to report
    the result of an operation.

    Args:
        loader: Loader
        name (str): Dispatch name
        action (str): Finished action
        result (str): Result message
        result_time (datetime.datetime): Time of the update
    """


@dispatch_loader_specs(firstresult=True)
def add_dispatch_id(loader: object, name: str, dispatch_id: str):
    """Add or update dispatch ID when a new dispatch is made.

    Args:
        loader: Loader
        name (str): Dispatch name
        dispatch_id (str): Dispatch ID
    """


@dispatch_loader_specs(firstresult=True)
def cleanup_dispatch_loader(loader: object):
    """Run cleanup operations such as saving files
    on the loader when NSDU don't use it anymore.

    Args:
        loader: Loader
    """


@template_var_loader_specs
def get_template_vars(config: Mapping[str, dict]) -> dict[str, Any]:
    """Get variables for template placeholders.

    Args:
        config (Mapping[str, dict]): Loader's configuration

    Return:
        dict[str, Any]: Placeholder variables
    """


@simple_bb_loader_specs(firstresult=True)
def get_simple_bb_config(config: Mapping[str, dict]) -> dict[str, dict]:
    """Get configuration for simple BBCode formatters.

    Args:
        config (dict[str, dict]): Loader's configuration

    Return:
        dict[str, dict]: Config for simple BBCode formatters
    """


@cred_loader_specs(firstresult=True)
def init_cred_loader(config: Mapping[str, dict]) -> object:
    """Create and return a loader object to persist.

    Args:
        config (dict): Loader's configuration

    Return:
        Loader object
    """


@cred_loader_specs(firstresult=True)
def get_creds(loader: object) -> dict:
    """Get all login credentials.

    Args:
        loader: Loader

    Return:
        dict: Nations' credential
    """


@cred_loader_specs(firstresult=True)
def add_cred(loader: object, name: str, x_autologin: str):
    """Add a login credential.

    Args:
        loader: Loader
        name (str): Nation's name
        x_autologin (str): Nation's X-Autologin value.
    """


@cred_loader_specs(firstresult=True)
def remove_cred(loader: object, name: str):
    """Delete a login credential.

    Args:
        loader: Loader
        name (str): Nation's name
    """


@cred_loader_specs(firstresult=True)
def cleanup_cred_loader(loader: object):
    """Run cleanup operations such as saving files
    on the loader when NSDU don't use it anymore.

    Args:
        loader: Loader
    """
