"""Updates dispatches based on dispatch config from dispatch loader.
"""

import logging
from pathlib import Path
from typing import Sequence, Tuple

from nsdu import exceptions, info, ns_api, renderer
from nsdu.bbc_parser import SimpleFormattersConfig
from nsdu.renderer import TemplateLoadFunc, TemplateVars

logger = logging.getLogger(__name__)


class DispatchMetadataError(exceptions.NSDUError):
    """Dispatch config error."""


class NonExistentCategoryError(DispatchMetadataError):
    """Category or subcategory doesn't exist."""

    def __init__(self, category_type, category_value):
        self.category_type = category_type
        self.category_value = category_value
        super().__init__()


def get_category_number(category: str, subcategory: str) -> Tuple[str, str]:
    """Get the number of a dispatch category or subcategory name.
    If the provided names are numbers, just return the numbers as is.

    Args:
        category (str): Category name or number
        subcategory (str): Subcategory name or number

    Raises:
        exceptions.DispatchUpdatingError: Could not find (sub)category number
        from provided name

    Returns:
        Tuple[str, str]: Category and subcategory number
    """

    if category.isalpha() and subcategory.isalpha():
        try:
            category_info = info.CATEGORIES[category.lower()]
            category_num = category_info["num"]
        except KeyError as err:
            raise NonExistentCategoryError("category", category) from err

        try:
            subcategory_num = category_info["subcategories"][subcategory.lower()]
        except KeyError as err:
            raise NonExistentCategoryError("subcategory", subcategory) from err
    else:
        category_num = category
        subcategory_num = subcategory

    return category_num, subcategory_num


class DispatchUpdater:
    """Render dispatches from templates and uploads them to NationStates."""

    def __init__(
        self,
        user_agent: str,
        template_filter_paths: Sequence[str],
        simple_fmts_config: SimpleFormattersConfig | None,
        complex_fmts_source_path: Path | None,
        template_load_func: TemplateLoadFunc,
        template_vars: TemplateVars,
    ) -> None:
        """Renders dispatches from templates and uploads them to NationStates.

        Args:
            user_agent (str): User agent for NationStates API calls
            template_filter_paths (Sequence[str]): List of paths to template filter
            source files
            simple_formatter_config (SimpleFormattersConfig | None): Simple BBCode
            formatter config
            complex_formatter_source_path (Path | None): Path to complex BBCode
            formatter
            source file
            template_load_func (TemplateLoadFunc): A callable that receives a
            dispatch name and returns its template
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

    def set_owner_nation(self, nation_name: str, autologin: str) -> None:
        """Set the nation to do dispatch operations on.

        Args:
            nation_name (str): Nation name
            autologin (str): Nation's autologin code
        """

        self.dispatch_api.set_owner_nation(nation_name, autologin)

    def get_rendered_dispatch_text(self, name: str) -> str:
        """Get rendered text of a dispatch.

        Args:
            name (str): Dispatch name

        Returns:
            str: Rendered text
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
            str: Id of new dispatch
        """

        logger.info('Creating dispatch "%s".', name)
        text = self.get_rendered_dispatch_text(name)
        category_num, subcategory_num = get_category_number(category, subcategory)

        new_dispatch_id = self.dispatch_api.create_dispatch(
            title=title, text=text, category=category_num, subcategory=subcategory_num
        )
        logger.debug('Got ID "%s" of new dispatch "%s".', new_dispatch_id, name)
        logger.debug('Created dispatch "%s"', name)
        return new_dispatch_id

    def edit_dispatch(
        self, name: str, dispatch_id: str, title: str, category: str, subcategory: str
    ) -> None:
        """Edit a dispatch.

        Args:
            name (str): Name
            dispatch_id (str): Id
            title (str): Title
            category (str): Category name or number
            subcategory (str): Subcategory name or number
        """

        logger.info('Editing dispatch "%s".', name)

        text = self.get_rendered_dispatch_text(name)
        category_num, subcategory_num = get_category_number(category, subcategory)

        self.dispatch_api.edit_dispatch(
            dispatch_id=dispatch_id,
            title=title,
            text=text,
            category=category_num,
            subcategory=subcategory_num,
        )
        logger.debug('Edited dispatch "%s"', name)

    def remove_dispatch(self, name: str, dispatch_id: str) -> None:
        """Delete a dispatch.

        Args:
            dispatch_id (str):  Id
        """

        logger.info('Deleting dispatch "%s".', name)
        self.dispatch_api.remove_dispatch(dispatch_id)
        logger.debug('Deleted dispatch "%s".', name)
