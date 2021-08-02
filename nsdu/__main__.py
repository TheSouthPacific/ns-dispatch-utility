"""NationStates Dispatch Utility."""

import os
import argparse
import importlib.metadata as import_metadata
import logging
import logging.config

import nationstates

from nsdu import info
from nsdu import exceptions
from nsdu import api_adapter
from nsdu import loader
from nsdu import renderer
from nsdu import updater
from nsdu import utils


logger = logging.getLogger(__name__)


class NSDU():
    """NSDU Application.

    Args:
        config (dict): General configuration
    """

    def __init__(self, config):
        self.config = config

        ns_api = nationstates.Nationstates(user_agent=config['general']['user_agent'])
        dispatch_api = api_adapter.DispatchAPI(ns_api)

        self.custom_loader_dir_path = self.config['general'].get('custom_loader_dir_path', None)
        loader_config = self.config['loader_config']

        self.dispatch_loader_handle = loader.DispatchLoaderHandle(loader_config)
        self.var_loader_handle = loader.VarLoaderHandle(loader_config)
        self.simple_bb_loader_handle = loader.SimpleBBLoaderHandle(loader_config)

        self.dispatch_config = None

        self.renderer = renderer.DispatchRenderer(self.dispatch_loader_handle)

        self.cred_loader_handle = loader.CredLoaderHandle(loader_config)
        self.creds = utils.CredManager(self.cred_loader_handle, dispatch_api)

        self.updater = updater.DispatchUpdater(dispatch_api, self.creds,
                                               self.renderer, self.dispatch_loader_handle)

    def load(self, only_cred=False):
        """Load all loaders and the renderer.

        Args:
            only_cred (bool): Only load credential loader
        """

        plugin_opt = self.config['plugins']

        entry_points = import_metadata.entry_points()[info.LOADER_ENTRY_POINT_NAME]
        single_loader_builder = loader.SingleLoaderHandleBuilder(info.LOADER_DIR_PATH,
                                                                 self.custom_loader_dir_path,
                                                                 entry_points)
        multiple_loaders_builder = loader.MultiLoadersHandleBuilder(info.LOADER_DIR_PATH,
                                                                    self.custom_loader_dir_path,
                                                                    entry_points)

        single_loader_builder.load_loader(self.cred_loader_handle, plugin_opt['cred_loader'])
        if only_cred:
            return
        self.creds.load_creds()

        single_loader_builder.load_loader(self.dispatch_loader_handle, plugin_opt['dispatch_loader'])
        self.dispatch_config = self.dispatch_loader_handle.get_dispatch_config()

        single_loader_builder.load_loader(self.simple_bb_loader_handle, plugin_opt['simple_bb_loader'])
        simple_bb_config = self.simple_bb_loader_handle.get_simple_bb_config()

        multiple_loaders_builder.load_loader(self.var_loader_handle, plugin_opt['var_loader'])
        vars = self.var_loader_handle.get_all_vars()

        self.renderer.load(simple_bb_config, self.config['complex_bb_parser'],
                           self.config['template_renderer'], vars, self.dispatch_config)

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

        self.dispatch_loader_handle.cleanup_loader()
        self.creds.save()
        self.cred_loader_handle.cleanup_loader()


def cli():
    """Process command line arguments."""

    parser = argparse.ArgumentParser(description=info.DESCRIPTION)
    subparsers = parser.add_subparsers(help='Sub-command help')

    cred_command = subparsers.add_parser('cred', help='Nation login credential management')
    cred_command.add_argument('--add', nargs='*', metavar=('NAME', 'PASSWORD'),
                              help='Add new login credential')
    cred_command.add_argument('--remove', nargs='*', metavar='NAME',
                              help='Remove login credential')

    update_command = subparsers.add_parser('update', help='Update dispatches')
    update_command.add_argument('dispatches', nargs='*', metavar='N',
                                help='Names of dispatches to update (Leave blank means all)')

    return parser.parse_args()


def run(app, inputs):
    """Run app.

    Args:
        app: NSDU
        inputs: CLI arguments
    """

    if hasattr(inputs, 'add') and inputs.add is not None:
        app.load(only_cred=True)
        if len(inputs.add) % 2 != 0:
            print('There is no password for the last name.')
            return
        for i in range(0, len(inputs.add), 2):
            app.add_nation_cred(inputs.add[i], inputs.add[i+1])
    elif hasattr(inputs, 'remove') and inputs.remove is not None:
        app.load(only_cred=True)
        for nation_name in inputs.remove:
            app.remove_nation_cred(nation_name)
    else:
        app.load()
        app.update_dispatches(inputs.dispatches)


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
        app = NSDU(config)
        run(app, inputs)
        app.close()
    except Exception as err:
        logger.exception(err)
        raise err


if __name__ == "__main__":
    main()
