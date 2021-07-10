"""API for loaders.
"""

import pluggy

from nsdu import info


dispatch_loader_specs = pluggy.HookspecMarker(info.DISPATCH_LOADER_PROJ)
dispatch_loader = pluggy.HookimplMarker(info.DISPATCH_LOADER_PROJ)

var_loader_specs = pluggy.HookspecMarker(info.VAR_LOADER_PROJ)
var_loader = pluggy.HookimplMarker(info.VAR_LOADER_PROJ)

cred_loader_specs = pluggy.HookspecMarker(info.CRED_LOADER_PROJ)
cred_loader = pluggy.HookimplMarker(info.CRED_LOADER_PROJ)


@dispatch_loader_specs(firstresult=True)
def init_dispatch_loader(config):
    """Initiate a loader.

    Args:
        config (dict): Loaders' configuration

    Return:
        Loader object
    """


@dispatch_loader_specs(firstresult=True)
def get_dispatch_config(loader):
    """Get a dict of dispatch parameters.

    Args:
        loader: Loader

    Return:
        dict: Dispatch configuration
    """


@dispatch_loader_specs(firstresult=True)
def get_dispatch_text(loader, name):
    """Get content text of a dispatch.

    Args:
        loader: Loader

    Return:
        str: Dispatch content text
    """


@dispatch_loader_specs(firstresult=True)
def add_dispatch_id(loader, name, dispatch_id):
    """Add or update dispatch ID when a new dispatch is made.

    Args:
        loader: Loader
        name (str): Dispatch name
        dispatch_id (str): Dispatch ID
    """


@dispatch_loader_specs(firstresult=True)
def cleanup_dispatch_loader(loader):
    """Cleanup loader and close it.

    Args:
        loader: Loader
    """


@var_loader_specs
def get_vars(config):
    """Get all variables as a dict.

    Args:
        config (dict): Loaders' configuration

    Return:
        dict: Variables
    """


@cred_loader_specs(firstresult=True)
def init_cred_loader(config):
    """Initiate a loader.

    Args:
        config (dict): Loaders' configuration

    Return:
        Loader object
    """


@cred_loader_specs(firstresult=True)
def get_creds(loader):
    """Get all nations' credential.

    Args:
        config (dict): Loaders' configuration

    Return:
        dict: Nations' credential
    """


@cred_loader_specs(firstresult=True)
def add_cred(loader, name, x_autologin):
    """Add a nation's credential.

    Args:
        config (dict): Loaders' configuration
        name (str): Nation name
        x_autologin (str): Nation's X-Autologin.
    """


@cred_loader_specs(firstresult=True)
def remove_cred(loader, name):
    """Delete a nation's credential.

    Args:
        config (dict): Loaders' configuration
        name (str): Nation name
    """


@cred_loader_specs(firstresult=True)
def cleanup_cred_loader(loader):
    """Cleanup loader and close it.

    Args:
        loader: Loader
    """
