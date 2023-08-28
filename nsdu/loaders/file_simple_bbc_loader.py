"""Load simple BBCode formatter config from a TOML file.
"""

import logging

from nsdu import config, exceptions, loader_api

logger = logging.getLogger(__name__)


@loader_api.simple_bb_loader
def get_simple_bb_config(loader_config: config.Config):
    try:
        file_path = loader_config["file_simple_bbc_loader"]["file_path"]
    except KeyError:
        return None

    try:
        return config.get_config_from_toml(file_path)
    except FileNotFoundError:
        raise exceptions.LoaderConfigError(
            "Simple BBCode formatter config file not found at {}".format(file_path)
        )
