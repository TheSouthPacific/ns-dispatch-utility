"""Load simple BBCode formatter config from a TOML file.
"""

import logging

from nsdu import config, loader_api
from nsdu.config import Config
from nsdu.loader_api import BbcConfig

logger = logging.getLogger(__name__)


@loader_api.simple_bbc_loader
def get_simple_bbc_config(loaders_config: Config) -> BbcConfig:
    try:
        file_path = loaders_config["file_simple_bbc_loader"]["file_path"]
    except KeyError:
        raise loader_api.LoaderError(
            "Simple BBCode formatter config file path is not set"
        )

    try:
        return config.get_config_from_toml(file_path)
    except FileNotFoundError:
        raise loader_api.LoaderError(
            "Simple BBCode formatter config file not found at {}".format(file_path)
        )
