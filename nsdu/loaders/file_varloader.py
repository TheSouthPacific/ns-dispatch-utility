"""Load variables from TOML files.
"""

import copy
import os
import logging
import pathlib

import toml

from nsdu import loader_api
from nsdu import exceptions
from nsdu import utils


logger = logging.getLogger(__name__)


def load_vars_from_files(paths):
    """Get all variables from file(s).

    Args:
        paths (list): File paths

    Returns:
        dict: Variables
    """

    loaded_vars = {}

    for path in paths:
        try:
            file_vars = utils.get_config_from_toml(pathlib.Path(path))
            logger.debug('Loaded var file "%s"', path)
        except FileNotFoundError:
            raise exceptions.LoaderConfigError('Var file "{}" not found'.format(path))

        if file_vars is not None:
            loaded_vars.update(file_vars)
        else:
            logger.warning('Var file "%s" is empty', path)

    return loaded_vars


def add_personnel_info(vars, personnel_groups, personnel_info_groups):
    personnel_info = {}
    for group in personnel_info_groups:
        try:
            personnel_info.update(copy.deepcopy(vars[group]))
        except KeyError:
            raise exceptions.LoaderConfigError('Personnel info var group "{}" not found'.format(group))
    
    for name, info in personnel_info.items():
        info['name'] = name

    for group in personnel_groups:
        try:
            personnel = vars[group]
            for position in personnel.keys():
                try:
                    personnel_name = personnel[position]
                    vars[group][position] = personnel_info[personnel_name]
                except KeyError:
                    raise exceptions.LoaderConfigError('Info for personnel "{}" not found'.format(personnel_name))
        except KeyError:
            raise exceptions.LoaderConfigError('Personnel var group "{}" not found'.format(group))


@loader_api.var_loader
def get_vars(config):
    loader_config = config['file_varloader']

    vars = load_vars_from_files(loader_config['var_paths'])
    add_personnel_info(vars, loader_config['personnel_groups'], loader_config['personnel_info_groups'])

    return vars
