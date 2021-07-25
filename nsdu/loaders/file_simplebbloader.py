"""Load simple BBCode formatter config from a TOML file.
"""

import os
import logging

import toml

from nsdu import exceptions
from nsdu import loader_api
from nsdu import utils


logger = logging.getLogger(__name__)


@loader_api.simple_bb_loader
def get_simple_bb_config(config):
    try:
        file_path = config['file_simplebbloader']['file_path']
    except KeyError:
        return None

    try:
        return utils.get_config_from_toml(file_path)
    except FileNotFoundError:
        raise exceptions.LoaderConfigError('Simple BBCode formatter config file not found at {}'.format(file_path))
