"""A simple API to render dispatches from templates
and upload them to NationStates.
"""

import logging
from pathlib import Path
from typing import Sequence

from nsdu import exceptions, info, ns_api, renderer
from nsdu.bbc_parser import SimpleFormattersConfig
from nsdu.renderer import TemplateLoadFunc, TemplateVars

logger = logging.getLogger(__name__)


class DispatchMetadataError(exceptions.NSDUError):
    """Dispatch metadata error."""


def get_category_numbers(category: str, subcategory: str) -> tuple[str, str]:
    """Get category and subcategory number from their names.
    If the provided names are numbers, return the numbers as is.

    Args:
        category (str): Category name
        subcategory (str): Subcategory name

    Raises:
        DispatchMetadataError: Invalid name

    Returns:
        tuple[str, str]: Category, subcategory number
    """

    if category.isnumeric() and subcategory.isnumeric():
        return category, subcategory

    try:
        category_info = info.CATEGORIES[category.lower()]
        category_num = category_info["num"]
    except KeyError as err:
        raise DispatchMetadataError(f"Category {category} is invalid") from err

    try:
        subcategory_num = category_info["subcategories"][subcategory.lower()]
    except KeyError as err:
        raise DispatchMetadataError(f"Subcategory {subcategory} is invalid") from err

    return category_num, subcategory_num


class DispatchUpdater:
    """Render dispatches from templates and upload them to NationStates."""

    def __init__(
        self,
        user_agent: str,
        template_filter_paths: Sequence[str],
        simple_fmts_config: SimpleFormattersConfig | None,
        complex_fmts_source_path: Path | None,
        template_load_func: TemplateLoadFunc,
        template_vars: TemplateVars,
    ) -> None:
        """Renders and uploads dispatches to NationStates.

        Args:
            user_agent (str): User agent for NationStates API
            template_filter_paths (Sequence[str]): Paths to template filter source files
            simple_formatter_config (SimpleFormattersConfig | None): Config for
            simple BBCode formatters
            complex_formatter_source_path (Path | None): Path to source file of
            complex BBCode formatters
            template_load_func (TemplateLoadFunc): A callback which receives
            dispatch name and returns template text
            template_vars (TemplateVars): Template variables
        """

        self.dispatch_api = ns_api.DispatchApi(user_agent=user_agent)
        self.renderer = renderer.DispatchRenderer(
            template_load_func,
            simple_fmts_config,
            complex_fmts_source_path,
            template_filter_paths,
            template_vars,
        )

    def set_nation(self, nation_name: str, autologin: str) -> None:
        """Set the nation to do dispatch operations on.

        Args:
            nation_name (str): Nation name
            autologin (str): Autologin code
        """

        self.dispatch_api.set_nation(nation_name, autologin)

    def render_dispatch(self, name: str) -> str:
        """Render a dispatch.

        Args:
            name (str): Dispatch name

        Returns:
            str: Text of rendered dispatch
        """

        return self.renderer.render(name)

    def create_dispatch(
        self, name: str, title: str, category: str, subcategory: str
    ) -> str:
        """Create a dispatch.

        Args:
            name (str): Name
            title (str): Title
            category (str): Category name or number
            subcategory (str): Subcategory name or number

        Returns:
            str: ID of new dispatch
        """

        text = self.render_dispatch(name)
        category_num, subcategory_num = get_category_numbers(category, subcategory)

        new_dispatch_id = self.dispatch_api.create_dispatch(
            title=title, text=text, category=category_num, subcategory=subcategory_num
        )

        return new_dispatch_id

    def edit_dispatch(
        self, name: str, dispatch_id: str, title: str, category: str, subcategory: str
    ) -> None:
        """Edit a dispatch.

        Args:
            name (str): Name
            dispatch_id (str): ID
            title (str): Title
            category (str): Category name or number
            subcategory (str): Subcategory name or number
        """

        text = self.render_dispatch(name)
        category_num, subcategory_num = get_category_numbers(category, subcategory)

        self.dispatch_api.edit_dispatch(
            dispatch_id=dispatch_id,
            title=title,
            text=text,
            category=category_num,
            subcategory=subcategory_num,
        )

    def delete_dispatch(self, dispatch_id: str) -> None:
        """Delete a dispatch.

        Args:
            dispatch_id (str): ID
        """

        self.dispatch_api.delete_dispatch(dispatch_id)
