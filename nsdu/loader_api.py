"""API for loaders.
"""

import datetime

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
def init_dispatch_loader(config: dict) -> object:
    """Initiate a loader.

    Args:
        config (dict): Loader's configuration

    Return:
        Loader object
    """


@dispatch_loader_specs(firstresult=True)
def get_dispatch_config(loader: object) -> dict:
    """Get a dict of dispatch parameters.

    Args:
        loader: Loader

    Return:
        dict: Dispatch configuration
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
def after_update(loader: object, name: str, action: str, result: str, result_time: datetime.datetime):
    """Run after a dispatch is updated to report
    result of an operation.

    Args:
        loader: Loader
        name (str): Dispatch name
        action (str): Action
        result (str): Result message
        result_time (datetime.datetime): Update time
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
    """Cleanup loader and close it.

    Args:
        loader: Loader
    """


@template_var_loader_specs
def get_template_vars(config: dict) -> dict:
    """Get variables for placeholders.

    Args:
        config (dict): Loader's configuration

    Return:
        dict: Placeholder variables
    """


@simple_bb_loader_specs(firstresult=True)
def get_simple_bb_config(config: dict) -> dict:
    """Get simple BBCode formatter config.

    Args:
        config (dict): Loader's configuration
    Return:
        dict: Config for simple BBCode formatters
    """


@cred_loader_specs(firstresult=True)
def init_cred_loader(config: dict) -> object:
    """Initiate a loader.

    Args:
        config (dict): Loader's configuration

    Return:
        Loader object
    """


@cred_loader_specs(firstresult=True)
def get_creds(loader: object) -> dict:
    """Get all nations' credential.

    Args:
        config (dict): Loader's configuration

    Return:
        dict: Nations' credential
    """


@cred_loader_specs(firstresult=True)
def add_cred(loader: object, name: str, x_autologin: str):
    """Add a nation's credential.

    Args:
        config (dict): Loader's configuration
        name (str): Nation name
        x_autologin (str): Nation's X-Autologin.
    """


@cred_loader_specs(firstresult=True)
def remove_cred(loader: object, name: str):
    """Delete a nation's credential.

    Args:
        config (dict): Loader's configuration
        name (str): Nation name
    """


@cred_loader_specs(firstresult=True)
def cleanup_cred_loader(loader: object):
    """Cleanup loader and close it.

    Args:
        loader: Loader
    """
