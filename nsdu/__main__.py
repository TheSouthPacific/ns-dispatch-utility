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
from nsdu import renderer
from nsdu import updater
from nsdu import utils


logger = logging.getLogger(__name__)


class NsduDispatch():
    """NSDU dispatch update utility.

    Args:
        config (dict): General configuration
    """

    def __init__(self, config):
        self.config = config

        dispatch_api = api_adapter.DispatchAPI(self.config['general']['user_agent'])

        self.custom_loader_dir_path = self.config['general'].get('custom_loader_dir_path', None)
        loader_config = self.config['loader_config']

        self.dispatch_loader_manager = loader.DispatchLoaderManager(loader_config)
        self.var_loader_manager = loader.VarLoaderManager(loader_config)
        self.simple_bb_loader_manager = loader.SimpleBBLoaderManager(loader_config)
        self.cred_loader_manager = loader.CredLoaderManager(loader_config)

        plugin_opt = self.config['plugins']
        try:
            entry_points = import_metadata.entry_points()[info.LOADER_ENTRY_POINT_NAME]
        except KeyError:
            entry_points = []
        singleloader_builder = loader.SingleLoaderManagerBuilder(info.LOADER_DIR_PATH,
                                                                self.custom_loader_dir_path,
                                                                entry_points)
        multiloaders_builder = loader.MultiLoadersManagerBuilder(info.LOADER_DIR_PATH,
                                                                self.custom_loader_dir_path,
                                                                entry_points)

        singleloader_builder.load_loader(self.cred_loader_manager, plugin_opt['cred_loader'])
        self.creds = utils.CredManager(self.cred_loader_manager, dispatch_api)
        self.creds.load_creds()

        singleloader_builder.load_loader(self.dispatch_loader_manager, plugin_opt['dispatch_loader'])
        self.dispatch_config = self.dispatch_loader_manager.get_dispatch_config()

        singleloader_builder.load_loader(self.simple_bb_loader_manager, plugin_opt['simple_bb_loader'])
        simple_bb_config = self.simple_bb_loader_manager.get_simple_bb_config()

        multiloaders_builder.load_loader(self.var_loader_manager, plugin_opt['var_loader'])
        template_vars = self.var_loader_manager.get_all_vars()
        self.dispatch_info = utils.get_dispatch_info(self.dispatch_config)
        template_vars['dispatch_info'] = self.dispatch_info

        rendering_config = self.config.get('rendering', {})
        self.renderer = renderer.DispatchRenderer(self.dispatch_loader_manager.get_dispatch_text, simple_bb_config,
                                                  rendering_config.get('complex_formatter_source_path', None),
                                                  rendering_config.get('filter_paths', None), template_vars)

        self.updater = updater.DispatchUpdater(dispatch_api, self.creds,
                                               self.renderer, self.dispatch_loader_manager)

    def update_dispatches(self, dispatches):
        """Update dispatches. Empty list means update all.

        Args:
            dispatches (list): Dispatch names
        """

        for owner_nation, dispatch_config in self.dispatch_config.items():
            try:
                self.updater.login_owner_nation(owner_nation, dispatch_config)
                logger.info('Logged in nation "%s".', owner_nation)
            except exceptions.NationLoginError:
                logger.error('Could not log into nation "%s".', owner_nation)
                continue

            if not dispatches:
                [self.updater.update_dispatch(name) for name in dispatch_config.keys()]
            else:
                remaining_dispatches = set(dispatches)
                for name in dispatch_config.keys():
                    if name in remaining_dispatches:
                        self.updater.update_dispatch(name)
                        remaining_dispatches.discard(name)
                if remaining_dispatches:
                    [logger.error('Could not find dispatch "%s".', name) for name in remaining_dispatches]

    def add_nation_cred(self, nation_name, password):
        """Add new credentials.

        Args:
            nation_name (str): Nation name
            password (str): Password
        """

        self.creds[nation_name] = password

    def remove_nation_cred(self, nation_name):
        """Remove credentials.

        Args:
            nation_name (str): Nation name
        """

        del self.creds[nation_name]

    def close(self):
        """Cleanup.
        """

        self.dispatch_loader_manager.cleanup_loader()
        self.creds.save()
        self.cred_loader_manager.cleanup_loader()


class NsduCred():
    """NSDU credential management utility.

    Args:
        config (dict): General configuration
     """

    def __init__(self, config):
        dispatch_api = api_adapter.DispatchAPI(config['general']['user_agent'])

        self.cred_loader_manager = loader.CredLoaderManager(config['loader_config'])
        self.creds = utils.CredManager(self.cred_loader_manager, dispatch_api)
        self.creds.load_creds()

    def add_nation_cred(self, nation_name, password):
        """Add new credentials.

        Args:
            nation_name (str): Nation name
            password (str): Password
        """

        self.creds[nation_name] = password

    def remove_nation_cred(self, nation_name):
        """Remove credentials.

        Args:
            nation_name (str): Nation name
        """

        del self.creds[nation_name]

    def close(self):
        """Save changes to creds and close.
        """

        self.creds.save()
        self.cred_loader_manager.cleanup_loader()


def run(config, inputs):
    """Run app.

    Args:
        app: NSDU
        inputs: CLI arguments
    """

    if inputs.subparser_name == 'cred':
        app = NsduCred(config)
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
        app = NsduDispatch(config)
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
