"""Load variables from TOML files.
"""

import os
import logging

import toml

from nsdu import loader_api
from nsdu import exceptions


logger = logging.getLogger(__name__)


def load_vars_from_file(path):
    """Load variables from a TOML file.

    Args:
        path (str): File path

    Raises:
        FileNotFoundError: [description]

    Returns:
        [type]: [description]
    """
    try:
        vars = toml.load(os.path.expanduser(path))
        logger.debug('Loaded var file "%s"', path)
        return vars
    except FileNotFoundError:
        logger.error('Could not find var file "{}"'.format(path))
        return None


def get_all_vars(paths):
    """Get variables from file(s).

    Args:
        paths (str|list): File path(s)

    Returns:
        dict: Variables
    """

    loaded_vars = {}

    if not paths or paths == '':
        logger.debug('No var file found')
    elif isinstance(paths, list):
        for path in paths:
            file_vars = load_vars_from_file(path)
            if file_vars is not None:
                loaded_vars.update(file_vars)
    else:
        loaded_vars = load_vars_from_file(paths)

    return loaded_vars


def add_personnel_info(vars, personnel_groups, personnel_info_groups):
    personnel_info = {}
    for group in personnel_info_groups:
        try:
            group_info = vars[group]
            for name in group_info.keys():
                group_info[name]['name'] = name
            personnel_info.update(group_info)
        except KeyError:
            raise exceptions.LoaderConfigError('Personnel info var group "{}" not found'.format(group))

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
    vars = get_all_vars(loader_config['var_paths'])
    return add_personnel_info(vars, loader_config['personnel_groups'], loader_config['personnel_info_groups'])
