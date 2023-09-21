import os
import shutil
from pathlib import Path
from typing import Any

import toml

from nsdu import exceptions, info, utils

Config = dict[str, Any]


class ConfigError(exceptions.AppError):
    """NSDU config error."""


def get_config_from_toml(config_path: str | Path) -> Config:
    """Get configuration from a TOML file.

    Args:
        config_path (str | Path): Path to a TOML file.

    Returns:
        Config: Configuration
    """

    return toml.load(utils.expanded_path(config_path))


def get_config_from_env(config_path: Path) -> dict:
    """Get configuration from a TOML file provided via an environment variable.

    Args:
        config_path (Path): Path to a TOML file

    Raises:
        ConfigError: Could not find the TOML file

    Returns:
        Config: Configuration
    """

    try:
        return get_config_from_toml(config_path)
    except FileNotFoundError as err:
        raise ConfigError(f"Could not find general config file {config_path}") from err


def get_config_from_default(
    config_dir: Path | str, default_config_path: Path | str, config_name: Path | str
) -> dict:
    """Get configuration from file at default location.
    Create default config file if there is none.

    Args:
        config_dir (Path | str): Path to the default config directory
        default_config_path (Path | str): Path to sample config directory
        config_name (Path | str): Name of config file

    Raises:
        ConfigError: Could not find config file

    Returns:
        Config: Configuration
    """

    config_path = Path(config_dir) / Path(config_name)
    try:
        return get_config_from_toml(config_path)
    except FileNotFoundError as err:
        shutil.copyfile(default_config_path, config_path)
        raise ConfigError(
            (
                "Could not find config.toml. First time run? "
                "Created one in {}. Please edit it."
            ).format(config_path)
        ) from err


def get_general_config() -> Config:
    """Get general configuration from default path
    or path defined via environment variable.

    Returns:
        Config: Config
    """

    env_var = os.getenv(info.CONFIG_ENVVAR)
    if env_var is not None:
        return get_config_from_env(Path(env_var))

    info.CONFIG_DIR.mkdir(exist_ok=True)
    return get_config_from_default(
        info.CONFIG_DIR, info.DEFAULT_CONFIG_PATH, info.CONFIG_NAME
    )
