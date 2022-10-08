"""Updates dispatches based on dispatch config from dispatch loader.
"""

import logging

from nsdu import ns_api
from nsdu import renderer
from nsdu import info
from nsdu import exceptions


logger = logging.getLogger(__name__)


def get_category_number(category, subcategory):
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
    """API for rendering and updating dispatches.

    Args:
        user_agent (str): User agent
        template_filter_paths (list): Paths to template filter source files
        simple_formatter_config (dict): Simple BBCode formatter config
        complex_formatter_source_path (str): Path to complex BBCode formatter source file
        template_load_func (Function): A callback that accepts dispatch name and returns its template
        template_vars (dict): Variables for templates
    """

    def __init__(
        self,
        user_agent,
        template_filter_paths,
        simple_formatter_config,
        complex_formatter_source_path,
        template_load_func,
        template_vars,
    ):
        self.dispatch_api = ns_api.DispatchApi(user_agent=user_agent)
        self.renderer = renderer.DispatchRenderer(
            template_load_func,
            simple_formatter_config,
            complex_formatter_source_path,
            template_filter_paths,
            template_vars,
        )

    def set_owner_nation(self, nation_name, autologin):
        """Set the nation to do dispatch operations on.

        Args:
            nation_name (str): Nation name
            autologin (str): Nation's autologin code
        """

        self.dispatch_api.set_owner_nation(nation_name, autologin)

    def get_rendered_dispatch_text(self, name):
        """Get rendered text of a dispatch.

        Args:
            name (str): Dispatch name

        Returns:
            str: Rendered text
        """

        return self.renderer.render(name)

    def create_dispatch(self, name, title, category, subcategory):
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

    def edit_dispatch(self, name, dispatch_id, title, category, subcategory):
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

    def remove_dispatch(self, dispatch_id):
        """Delete a dispatch.

        Args:
            dispatch_id (str):  Id
        """

        self.dispatch_api.remove_dispatch(dispatch_id)
