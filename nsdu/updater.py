"""Updates dispatches based on dispatch config from dispatch loader.
"""

import logging

from nsdu import api_adapter
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
            category_info = info.CATEGORIES[category]
            category_num = category_info['num']
        except KeyError as err:
            raise exceptions.NonexistentCategoryError('category', category) from err

        try:
            subcategory_num = category_info['subcategories'][subcategory]
        except KeyError as err:
            raise exceptions.NonexistentCategoryError('subcategory', subcategory) from err
    else:
        category_num = category
        subcategory_num = subcategory

    return category_num, subcategory_num


class DispatchUpdater():
    """Update a dispatch.

    Args:
        dispatch_api (nsdu.api_adapter.DispatchAPI): Dispatch API adapter
        creds (dict): Nation login credentials
        renderer (nsdu.renderer.Renderer): Renderer
        dispatch_loader (nsdu.loader.DispatchLoader): Dispatch loader
    """

    def __init__(self, dispatch_api, creds, renderer, dispatch_loader):
        self.dispatch_api = dispatch_api
        self.renderer = renderer
        self.dispatch_loader = dispatch_loader
        self.dispatch_config = None
        self.creds = creds

    def login_owner_nation(self, owner_nation, dispatch_config):
        """Log into dispatch owner nation and set its dispatches' info.

        Args:
            owner_nation (str): Nation name
            dispatch_config (dict): Nation's dispatch config
        """

        self.dispatch_api.login(owner_nation, autologin=self.creds[owner_nation])
        self.dispatch_config = dispatch_config

    def update_dispatch(self, name):
        """Update a dispatch.

        Args:
            name (str): Dispatch name
        """

        this_dispatch_config = self.dispatch_config[name]
        try:
            action = this_dispatch_config.pop('action')
        except KeyError as err:
            logger.error('Dispatch "%s" does not have %s.', name, err)

        try:
            if action == 'remove':
                dispatch_id = this_dispatch_config['ns_id']
                logger.debug('Remove dispatch "%s" with id "%s".', name, dispatch_id)
                self.remove_dispatch(dispatch_id)
                logger.info('Removed dispatch "%s".', name)
            elif action in ('edit', 'create'):
                self.create_or_edit_dispatch(name, action, this_dispatch_config)
            else:
                logger.error('Invalid action "%s" on dispatch "%s".', action, name)
        except exceptions.UnknownDispatchError:
            logger.error('Could not find dispatch "%s" with id "%s".', name, dispatch_id)
        except exceptions.NotOwnerDispatchError:
            logger.error('Dispatch "%s" is not owned by this nation.', name)
        except exceptions.DispatchAPIError:
            logger.exception('Dispatch API error')

    def get_dispatch_text(self, name):
        """Get rendered text for a dispatch.

        Args:
            name (str): Dispatch name

        Returns:
            str: Rendered text
        """

        return self.renderer.render(name)

    def create_or_edit_dispatch(self, name, action, this_dispatch_config):
        """Create or edit a dispatch based on action.

        Args:
            name (str): Dispatch name
            action (str): Action to perform
            this_dispatch_config (dict): This dispatch's info
        """

        try:
            category = this_dispatch_config['category']
            subcategory = this_dispatch_config['subcategory']
            title = this_dispatch_config['title']
        except KeyError as err:
            logger.error('Dispatch "%s" does not have %s.', name, err)
            return

        try:
            category_num, subcategory_num = get_category_number(category, subcategory)
        except exceptions.NonexistentCategoryError as err:
            logger.error('Text %s "%s" of dispatch "%s" not found.',
                         err.category_type, err.category_value, name)
            return

        try:
            text = self.get_dispatch_text(name)
        except exceptions.DispatchRenderingError as err:
            return

        params = {'title': title,
                  'text': text,
                  'category': category_num,
                  'subcategory': subcategory_num}

        if action == 'create':
            logger.debug('Create dispatch "%s" with params: %r', name, params)
            self.create_dispatch(name, params)
            logger.info('Created dispatch "%s".', name)
        elif action == 'edit':
            dispatch_id = this_dispatch_config['ns_id']
            logger.debug('Edit dispatch "%s" with id "%s" and with params: %r',
                         name, dispatch_id, params)
            self.edit_dispatch(dispatch_id, params)
            logger.info('Edited dispatch "%s".', name)

    def create_dispatch(self, name, params):
        """Create a dispatch.

        Args:
            name (str): Dispatch name
            params (dict): Dispatch parameters
        """

        new_dispatch_id = self.dispatch_api.create_dispatch(title=params['title'],
                                                            text=params['text'],
                                                            category=params['category'],
                                                            subcategory=params['subcategory'])
        logger.debug('Got id "%s" of new dispatch "%s".', new_dispatch_id, name)
        self.dispatch_loader.add_dispatch_id(name, new_dispatch_id)

    def edit_dispatch(self, dispatch_id, params):
        """Edit a dispatch.

        Args:
            dispatch_id (str): Dispatch ID
            params (dict): Dispatch parameters
        """

        self.dispatch_api.edit_dispatch(dispatch_id=dispatch_id,
                                        title=params['title'],
                                        text=params['text'],
                                        category=params['category'],
                                        subcategory=params['subcategory'])

    def remove_dispatch(self, dispatch_id):
        """Delete a dispatch.

        Args:
            dispatch_id (str): Dispatch ID
        """

        self.dispatch_api.remove_dispatch(dispatch_id)
