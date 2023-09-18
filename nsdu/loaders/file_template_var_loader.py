"""Load variables from TOML files.
"""

from __future__ import annotations

import copy
import logging
from collections import UserDict
from typing import Mapping, Sequence

from nsdu import config, loader_api
from nsdu.config import Config
from nsdu.loader_api import LoaderError, TemplateVars

logger = logging.getLogger(__name__)

PersonInfo = dict[str, str]


def load_template_vars_from_files(paths: Sequence[str]) -> TemplateVars:
    """Get all template variables from TOML files.

    Args:
        paths (Sequence[str]): File paths

    Returns:
        TemplateVars: Template variables
    """

    loaded_vars = {}

    for path in paths:
        try:
            file_vars = config.get_config_from_toml(path)
            logger.debug('Loaded variable file "%s"', path)
        except FileNotFoundError:
            raise LoaderError(f'Variable file "{path}" not found')

        if file_vars is not None:
            loaded_vars.update(file_vars)
        else:
            logger.warning('Variable file "%s" is empty', path)

    return loaded_vars


class PeopleInfoStore(UserDict[str, PersonInfo]):
    """Contains info such as name, nation name, Discord ID,... of people."""

    def __init__(self, people_info: Mapping[str, PersonInfo]):
        """Contains info such as name, nation name, Discord ID,... of people.

        Args:
            info_dict (Mapping[str, PersonInfo]): People info as dict
        """

        people_info = copy.deepcopy(people_info)
        for name, person_info in people_info.items():
            person_info["name"] = name
        super().__init__(people_info)

    @classmethod
    def from_people_info_var_groups(
        cls, template_vars: TemplateVars, group_names: Sequence[str]
    ) -> PeopleInfoStore:
        """Instantiate from people info variable groups.

        Args:
            template_vars (TemplateVars): Template variables
            group_names (Sequence[str]): Group names

        Raises:
            LoaderError: Group not found

        Returns:
            PeopleInfoStore
        """

        people_info: dict[str, PersonInfo] = {}
        for group in group_names:
            try:
                people_info.update(template_vars[group])
            except KeyError:
                raise LoaderError(f'People info variable group "{group}" not found')

        return cls(people_info)

    def __getitem__(self, name: str) -> PersonInfo:
        try:
            return super().__getitem__(name)
        except KeyError:
            raise LoaderError(f'Info for person "{name}" not found')


def replace_personnel_names_with_info(
    template_vars: TemplateVars,
    personnel_group_names: Sequence[str],
    people_info: PeopleInfoStore,
) -> None:
    """Replace values of variables in personnel variable groups with info dicts.

    Args:
        template_vars (TemplateVars): Template variables
        personnel_group_names (Sequence[str]): Personnel variable group names
        people_info (PeopleInfoStore): People info store

    Raises:
        LoaderError: Personnel variable group not found
    """

    for group in personnel_group_names:
        try:
            personnel = template_vars[group]
        except KeyError:
            raise LoaderError(f'Personnel variable group "{group}" not found')

        for position, names in personnel.items():
            if isinstance(names, list):
                person_info_list = list(map(lambda name: people_info[name], names))
                personnel[position] = person_info_list
            else:
                personnel[position] = people_info[names]


@loader_api.template_var_loader
def get_template_vars(loaders_config: Config) -> TemplateVars:
    loader_config = loaders_config["file_template_var_loader"]

    template_vars = load_template_vars_from_files(loader_config["template_var_paths"])

    people_info = PeopleInfoStore.from_people_info_var_groups(
        template_vars, loader_config["people_info_groups"]
    )

    replace_personnel_names_with_info(
        template_vars, loader_config["personnel_groups"], people_info
    )

    return template_vars
