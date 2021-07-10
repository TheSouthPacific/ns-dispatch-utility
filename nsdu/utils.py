""" Utilities.
"""

import os
import collections
import shutil
import inspect
import logging
import importlib
import pathlib

import toml

from nsdu import info
from nsdu import exceptions


logger = logging.getLogger(__name__)


class CredManager(collections.UserDict):
    """Nation login credential manager object.

    Args:
        cred_loader: Credential loader
        dispatch_api: Dispatch API
    """

    def __init__(self, cred_loader, dispatch_api):
        super().__init__()
        self.cred_loader = cred_loader
        self.dispatch_api = dispatch_api

    def load_creds(self):
        """Load all credentials from loader.
        """

        self.data = self.cred_loader.get_creds()

    def __setitem__(self, nation_name, password):
        """Add a new credential with X-Autologin.

        Args:
            nation_name (str): Nation name
            password (str): Password
        """

        x_autologin = self.dispatch_api.login(nation_name, password=password)
        self.cred_loader.add_cred(nation_name, x_autologin)

    def __delitem__(self, nation_name):
        """Delete a credential

        Args:
            nation_name (str): Nation name
        """

        self.cred_loader.remove_cred(nation_name)


def get_config_from_toml(config_path):
    """Get configuration from TOML file.

    Args:
        config_path (pathlib.Path|str): Path to config file (user expanded)

    Returns:
        dict: Config
    """

    return toml.load(pathlib.Path(config_path).expanduser())


def get_config_from_env(config_path):
    """Get configuration from environment variable.

    Args:
        config_path (pathlib.Path): Path to config file

    Raises:
        exceptions.ConfigError: Could not find config file

    Returns:
        dict: Config
    """

    try:
        return get_config_from_toml(config_path)
    except FileNotFoundError as err:
        raise exceptions.ConfigError('Could not find general config file {}'.format(config_path)) from err


def get_config_from_default(config_dir, default_config_path, config_name):
    """Get config from default location.
    Create default config file if there is none.

    Args:
        config_dir (pathlib.Path): [description]
        default_config_path (pathlib.Path): [description]
        config_name (pathlib.Path): [description]

    Raises:
        exceptions.ConfigError: Could not find config file

    Returns:
        dict: Config
    """

    config_path = config_dir / config_name
    try:
        return get_config_from_toml(config_path)
    except FileNotFoundError as err:
        shutil.copyfile(default_config_path , config_path)
        raise exceptions.ConfigError(('Could not find config.toml. First time run? '
                                      'Created one in {}. Please edit it.').format(config_path)) from err


def get_general_config():
    """Get general configuration from default path
    or path defined via environment variable.

    Returns:
        dict: Config
    """

    env_var = os.getenv(info.CONFIG_ENVVAR)
    if env_var is not None:
        return get_config_from_env(pathlib.Path(env_var))

    info.CONFIG_DIR.mkdir(exist_ok=True)
    return get_config_from_default(info.CONFIG_DIR,
                                   info.DEFAULT_CONFIG_PATH,
                                   info.CONFIG_NAME)


def get_dispatch_info(dispatch_config):
    """Compose and return dispatch information
    for use as context in the template renderer.

    Args:
        dispatch_config (dict): Dispatch configuration.
        id_store (IDStore): Dispatch ID store.

    Returns:
        dict: Dispatch information.
    """

    dispatch_info = {}
    for nation, dispatches in dispatch_config.items():
        for name, config in dispatches.items():
            config['owner_nation'] = nation
            dispatch_info[name] = config

    return dispatch_info


def get_funcs(path):
    """Get functions from a module file (.py).

    Args:
        path (str): Path to module file (.py).
    """

    module = load_module(path)
    return inspect.getmembers(module, inspect.isfunction)


def load_module(path, name='module'):
    """Load module from a path.

    Args:
        path (pathlib.Path): Path to module file (.py)
        name (str): Name of module for reference needs. Defaults to 'module'
    """

    spec = importlib.util.spec_from_file_location(name, path)
    if spec is not None:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    raise FileNotFoundError


def add_extension(name):
    """Get file name with .py extension.

    Args:
        name (str): Name

    Returns:
        str
    """

    return '{}.py'.format(name)
