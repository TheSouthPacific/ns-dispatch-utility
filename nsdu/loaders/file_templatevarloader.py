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


def load_template_vars_from_files(paths):
    """Get all template variables from TOML file(s).

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


def replace_name_with_personnel_info(name, personnel_info):
    try:
        name = personnel_info[name]
    except KeyError:
        raise exceptions.LoaderConfigError('Info for personnel "{}" not found'.format(name))

    return name


def replace_name_list_with_personnel_info(name_list, personnel_info):
    for i, name in enumerate(name_list):
        name_list[i] = replace_name_with_personnel_info(name, personnel_info)

    return name_list


def merge_personnel_info_groups(template_vars, personnel_info_groups):
    personnel_info = {}
    for group in personnel_info_groups:
        try:
            personnel_info.update(copy.deepcopy(template_vars[group]))
        except KeyError:
            raise exceptions.LoaderConfigError('Personnel info var group "{}" not found'.format(group))

    for name, info in personnel_info.items():
        info['name'] = name

    return personnel_info


def add_personnel_info(template_vars, personnel_groups, personnel_info_groups):
    personnel_info = merge_personnel_info_groups(template_vars, personnel_info_groups)

    for group in personnel_groups:
        try:
            personnel = template_vars[group]
            for position, names in personnel.items():
                if isinstance(names, list):
                    personnel[position] = replace_name_list_with_personnel_info(names, personnel_info)
                else:
                    personnel[position] = replace_name_with_personnel_info(names, personnel_info)
        except KeyError:
            raise exceptions.LoaderConfigError('Personnel var group "{}" not found'.format(group))


@loader_api.template_var_loader
def get_template_vars(config):
    loader_config = config['file_templatevarloader']

    template_vars = load_template_vars_from_files(loader_config['template_var_paths'])
    add_personnel_info(template_vars, loader_config['personnel_groups'], loader_config['personnel_info_groups'])

    return template_vars
