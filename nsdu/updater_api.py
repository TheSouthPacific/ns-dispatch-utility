"""Updates dispatches based on dispatch config from dispatch loader.
"""

import logging
from typing import Any, Callable, Mapping, Sequence, Tuple, Union

from nsdu import ns_api
from nsdu import renderer
from nsdu import info
from nsdu import exceptions


logger = logging.getLogger(__name__)


def get_category_number(category: str, subcategory: str) -> Tuple[str, str]:
    """Get category and subcategory number if they are descriptive name.

    Args:
        category (str): Category
        subcategory (str): Subcategory

    Raises:
        exceptions.DispatchUpdatingError: Could not find (sub)category number from name

    Returns:
        str, str: Category and subcategory number
    """

    if category.isalpha() and subcategory.isalpha():
        try:
            category_info = info.CATEGORIES[category.lower()]
            category_num = category_info["num"]
        except KeyError as err:
            raise exceptions.NonexistentCategoryError("category", category) from err

        try:
            subcategory_num = category_info["subcategories"][subcategory.lower()]
        except KeyError as err:
            raise exceptions.NonexistentCategoryError(
                "subcategory", subcategory
            ) from err
    else:
        category_num = category
        subcategory_num = subcategory

    return category_num, subcategory_num


class DispatchUpdater:
    """Renders dispatches from templates and uploads them to NationStates."""

    def __init__(
        self,
        user_agent: str,
        template_filter_paths: Sequence[str],
        simple_formatter_config: Mapping[str, Mapping[str, str]],
        complex_formatter_source_path: str,
        template_load_func: Callable[[str], str],
        template_vars: Mapping[str, Any],
    ) -> None:
        """Renders dispatches from templates and uploads them to NationStates.

        Args:
            user_agent (str): User agent for NationStates API calls
            template_filter_paths (Sequence[str]): List of paths to template filter source files
            simple_formatter_config (Mapping[str, Mapping[str, str]]): Simple BBCode formatter config
            complex_formatter_source_path (str): Path to complex BBCode formatter source file
            template_load_func (Callable[[str], str]): A callable that receives a dispatch name and returns its template
            template_vars (Mapping[str, Any]): Template variables
        """

        self.dispatch_api = ns_api.DispatchApi(user_agent=user_agent)
        self.renderer = renderer.DispatchRenderer(
            template_load_func,
            simple_formatter_config,
            complex_formatter_source_path,
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
    ) -> None:
        """Create a dispatch.

        Args:
            name (str): Name
            title (str): Title
            category (str): Category
            subcategory (str): Subcategory

        Returns:
            str: Id of new dispatch
        """

        text = self.get_rendered_dispatch_text(name)
        category_num, subcategory_num = get_category_number(category, subcategory)
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
            dispatch_id (str): Id
            title (str): Title
            category (str): Category
            subcategory (str): Subcategory
        """

        text = self.get_rendered_dispatch_text(name)
        category_num, subcategory_num = get_category_number(category, subcategory)
        self.dispatch_api.edit_dispatch(
            dispatch_id=dispatch_id,
            title=title,
            text=text,
            category=category_num,
            subcategory=subcategory_num,
        )

    def remove_dispatch(self, dispatch_id: str) -> None:
        """Delete a dispatch.

        Args:
            dispatch_id (str):  Id
        """

        self.dispatch_api.remove_dispatch(dispatch_id)
