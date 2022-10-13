"""Utility functions.
"""

import os
import shutil
import inspect
import logging
import importlib
from pathlib import Path
from types import ModuleType
from typing import Callable, Mapping, Union

import toml

from nsdu import info
from nsdu import exceptions


logger = logging.getLogger(__name__)


def get_config_from_toml(config_path: Union[str, Path]) -> dict:
    """Get configuration from a TOML file as a dictionary.

    Args:
        config_path (Union[str, Path]): Path to a TOML file. The user symbol will be expanded

    Returns:
        dict: Configuration
    """

    return toml.load(Path(config_path).expanduser())


def get_config_from_env(config_path: Path) -> dict:
    """Get configuration from a TOML file provided via an environment variable.

    Args:
        config_path (Path): Path to a TOML file

    Raises:
        exceptions.ConfigError: Could not find the TOML file

    Returns:
        dict: Configuration
    """

    try:
        return get_config_from_toml(config_path)
    except FileNotFoundError as err:
        raise exceptions.ConfigError(
            "Could not find general config file {}".format(config_path)
        ) from err


def get_config_from_default(
    config_dir: Path, default_config_path: Path, config_name: Path
) -> dict:
    """Get configuration from file at default location.
    Create default config file if there is none.

    Args:
        config_dir (Path): Path to the default config directory
        default_config_path (Path): Path to sample config directory
        config_name (Path): Name of config file

    Raises:
        exceptions.ConfigError: Could not find config file

    Returns:
        dict: Configuration
    """

    config_path = config_dir / config_name
    try:
        return get_config_from_toml(config_path)
    except FileNotFoundError as err:
        shutil.copyfile(default_config_path, config_path)
        raise exceptions.ConfigError(
            (
                "Could not find config.toml. First time run? "
                "Created one in {}. Please edit it."
            ).format(config_path)
        ) from err


def get_general_config() -> dict:
    """Get general configuration from default path
    or path defined via environment variable.

    Returns:
        dict: Config
    """

    env_var = os.getenv(info.CONFIG_ENVVAR)
    if env_var is not None:
        return get_config_from_env(Path(env_var))

    info.CONFIG_DIR.mkdir(exist_ok=True)
    return get_config_from_default(
        info.CONFIG_DIR, info.DEFAULT_CONFIG_PATH, info.CONFIG_NAME
    )


def get_dispatch_info(dispatch_config: Mapping) -> dict:
    """Return dispatch information for use as context in the template renderer.

    Args:
        dispatch_config (Mapping): Dispatch configuration.

    Returns:
        dict: Dispatch information.
    """

    dispatch_info = {}
    for nation, dispatches in dispatch_config.items():
        for name, config in dispatches.items():
            config["owner_nation"] = nation
            dispatch_info[name] = config

    return dispatch_info


def get_functions_from_module(path: str) -> list[Callable]:
    """Get all functions from a Python module file.

    Args:
        path (str): Path to the module file

    Returns:
        list[Callable]: Functions
    """

    module = load_module(path)
    return inspect.getmembers(module, inspect.isfunction)


def load_module(path: Path) -> ModuleType:
    """Load Python module at the provided path.

    Args:
        path (Path): Path to the module file

    Raises:
        FileNotFoundError: Could not find the module file

    Returns:
        ModuleType: Loaded module
    """

    spec = importlib.util.spec_from_file_location(path.name, path.expanduser())
    if spec is not None:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    raise FileNotFoundError


def canonical_nation_name(name: str) -> str:
    """Canonicalize nation name into lower case form with no underscore.

    Args:
        name (str): Name

    Returns:
        str: Canonical nation name
    """

    return name.lower().replace("_", " ")
