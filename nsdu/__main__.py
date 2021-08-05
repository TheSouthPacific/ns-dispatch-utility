"""NationStates Dispatch Utility."""

import os
import argparse
import importlib.metadata as import_metadata
import logging
import logging.config

from nsdu import info
from nsdu import exceptions
from nsdu import api_adapter
from nsdu import loader
from nsdu import updater_api
from nsdu import utils


logger = logging.getLogger('NSDU')


class NsduDispatch():
    def __init__(self, dispatch_updater, dispatch_loader_manager, dispatch_config, dispatch_info, creds):
        self.dispatch_updater = dispatch_updater
        self.dispatch_loader_manager = dispatch_loader_manager
        self.dispatch_config = dispatch_config
        self.dispatch_info = dispatch_info
        self.creds = creds

    def update_a_dispatch(self, name):
        config = self.dispatch_info[name]
        category = config['category']
        subcategory = config['subcategory']
        title = config['title']
        action = config['action']

        if action not in ('create', 'edit', 'remove'):
            raise exceptions.DispatchConfigError('Invalid action "{}" on dispatch "{}".'.format(action, name))

        try:
            if action == 'create':
                logger.debug('Creating dispatch "%s" with params: %r', name, config)
                new_dispatch_id = self.dispatch_updater.create_dispatch(name, title, category, subcategory)
                logger.debug('Got id "%s" of new dispatch "%s".', new_dispatch_id, name)
                self.dispatch_loader_manager.add_dispatch_id(name, new_dispatch_id)
                logger.info('Created dispatch "%s".', name)
            elif action == 'edit':
                dispatch_id = config['ns_id']
                logger.debug('Editing dispatch "%s" with id "%s" and with params: %r',
                             name, dispatch_id, config)
                self.dispatch_updater.edit_dispatch(name, dispatch_id, title, category, subcategory)
                logger.info('Edited dispatch "%s".', name)
            elif action == 'remove':
                dispatch_id = config['ns_id']
                logger.debug('Removing dispatch "%s" with id "%s".', name, dispatch_id)
                self.dispatch_updater.remove_dispatch(dispatch_id)
                logger.info('Removed dispatch "%s".', name)
        except exceptions.UnknownDispatchError:
            logger.error('Could not find dispatch "%s" with id "%s".', name, dispatch_id)
        except exceptions.NotOwnerDispatchError:
            logger.error('Dispatch "%s" is not owned by this nation.', name)
        except exceptions.NonexistentCategoryError as err:
            logger.error('%s "%s" of dispatch "%s" is invalid.', err.category_type, err.category_value, name)

    def update_dispatches(self, names):
        """Update dispatches. Empty list means update all.

        Args:
            names (list): Dispatch names
        """

        if names:
            while (names[-1] not in self.dispatch_info):
                logger.error('Could not find dispatch "%s"', names[-1])
                names.pop()
                if not names:
                    return

        for owner_nation, dispatch_config in self.dispatch_config.items():
            try:
                self.dispatch_updater.login_owner_nation(owner_nation, autologin=self.creds[owner_nation])
                logger.info('Logged in nation "%s".', owner_nation)
            except exceptions.NationLoginError:
                logger.error('Could not log into nation "%s".', owner_nation)
                continue

            if not names:
                [self.update_a_dispatch(name) for name in dispatch_config.keys()]
            else:
                [self.update_a_dispatch(name) for name in dispatch_config.keys() if name in names]

    def close(self):
        self.dispatch_loader_manager.cleanup_loader()


class NsduCred():
    """NSDU credential management utility.

    Args:
        dispatch_api (nsdu.api_adapter.DispatchApi): Dispatch API
        cred_loader_manager (nsdu.loader.CredLoaderManager): Cred loader manager
    """

    def __init__(self, cred_loader_manager, dispatch_api):
        self.dispatch_api = dispatch_api
        self.cred_loader_manager = cred_loader_manager

    def add_nation_cred(self, nation_name, password):
        """Add new credentials.

        Args:
            nation_name (str): Nation name
            password (str): Password
        """

        x_autologin = self.dispatch_api.login(nation_name, password=password)
        self.cred_loader_manager.add_cred(nation_name, x_autologin)

    def remove_nation_cred(self, nation_name):
        """Remove credentials.

        Args:
            nation_name (str): Nation name
        """

        self.cred_loader_manager.remove_cred(nation_name)

    def close(self):
        """Save changes to creds and close.
        """

        self.cred_loader_manager.cleanup_loader()


def load_nsdu_dispatch_utility_from_config(config):
    custom_loader_dir_path = config['general'].get('custom_loader_dir_path', None)
    loader_config = config['loader_config']

    dispatch_loader_manager = loader.DispatchLoaderManager(loader_config)
    template_var_loader_manager = loader.TemplateVarLoaderManager(loader_config)
    simple_bb_loader_manager = loader.SimpleBBLoaderManager(loader_config)
    cred_loader_manager = loader.CredLoaderManager(loader_config)

    plugin_opt = config['plugins']
    try:
        entry_points = import_metadata.entry_points()[info.LOADER_ENTRY_POINT_NAME]
    except KeyError:
        entry_points = []
    singleloader_builder = loader.SingleLoaderManagerBuilder(info.LOADER_DIR_PATH,
                                                             custom_loader_dir_path,
                                                             entry_points)
    multiloaders_builder = loader.MultiLoadersManagerBuilder(info.LOADER_DIR_PATH,
                                                             custom_loader_dir_path,
                                                             entry_points)

    singleloader_builder.load_loader(cred_loader_manager, plugin_opt['cred_loader'])
    creds = cred_loader_manager.get_creds()

    singleloader_builder.load_loader(dispatch_loader_manager, plugin_opt['dispatch_loader'])
    dispatch_config = dispatch_loader_manager.get_dispatch_config()

    singleloader_builder.load_loader(simple_bb_loader_manager, plugin_opt['simple_bb_loader'])
    simple_bb_config = simple_bb_loader_manager.get_simple_bb_config()

    multiloaders_builder.load_loader(template_var_loader_manager, plugin_opt['template_var_loader'])
    template_vars = template_var_loader_manager.get_all_template_vars()
    dispatch_info = utils.get_dispatch_info(dispatch_config)
    template_vars['dispatch_info'] = dispatch_info

    rendering_config = config.get('rendering', {})
    dispatch_updater = updater_api.DispatchUpdater(user_agent=config['general']['user_agent'],
                                                   template_filter_paths=rendering_config.get('filter_paths', None),
                                                   simple_formatter_config=simple_bb_config,
                                                   complex_formatter_source_path=rendering_config.get('complex_formatter_source_path', None),
                                                   template_load_func=dispatch_loader_manager.get_dispatch_template,
                                                   template_vars=template_vars)

    return NsduDispatch(dispatch_updater, dispatch_loader_manager, dispatch_config, dispatch_info, creds)


def load_nsdu_cred_utility_from_config(config):
    dispatch_api = api_adapter.DispatchApi(config['general']['user_agent'])
    cred_loader_manager = loader.CredLoaderManager(config['loader_config'])
    return NsduCred(dispatch_api, cred_loader_manager)


def run(config, inputs):
    """Run app.

    Args:
        app: NSDU
        inputs: CLI arguments
    """

    if inputs.subparser_name == 'cred':
        app = load_nsdu_cred_utility_from_config(config)
        if hasattr(inputs, 'add') and inputs.add is not None:
            if len(inputs.add) % 2 != 0:
                print('There is no password for the last name.')
                return
            for i in range(0, len(inputs.add), 2):
                app.add_nation_cred(inputs.add[i], inputs.add[i+1])
        elif hasattr(inputs, 'remove') and inputs.remove is not None:
            for nation_name in inputs.remove:
                app.remove_nation_cred(nation_name)
    elif inputs.subparser_name == 'update':
        app = load_nsdu_dispatch_utility_from_config(config)
        app.update_dispatches(inputs.dispatches)

    app.close()


def cli():
    """Process command line arguments."""

    parser = argparse.ArgumentParser(description=info.DESCRIPTION)
    subparsers = parser.add_subparsers(help='Sub-command help', dest='subparser_name')

    cred_command = subparsers.add_parser('cred', help='Nation login credential management')
    cred_command.add_argument('--add', nargs='*', metavar=('NAME', 'PASSWORD'),
                              help='Add new login credential')
    cred_command.add_argument('--remove', nargs='*', metavar='NAME',
                              help='Remove login credential')

    update_command = subparsers.add_parser('update', help='Update dispatches')
    update_command.add_argument('dispatches', nargs='*', metavar='N',
                                help='Names of dispatches to update (Leave blank means all)')

    return parser.parse_args()


def main():
    """Starting point."""

    inputs = cli()

    info.DATA_DIR.mkdir(exist_ok=True)

    info.LOGGING_DIR.parent.mkdir(exist_ok=True)
    info.LOGGING_DIR.mkdir(exist_ok=True)
    logging.config.dictConfig(info.LOGGING_CONFIG)

    try:
        config = utils.get_general_config()
        logger.info('Loaded general config.')
    except exceptions.ConfigError as err:
        print(err)
        return

    try:
        run(config, inputs)
    except exceptions.NSDUError as err:
        logger.error(err)
    except Exception as err:
        logger.exception(err)


if __name__ == "__main__":
    main()
