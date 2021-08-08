"""Load dispatches from plain text files with TOML dispatch configuration.
"""

import copy
import pathlib
import collections
import json
import logging
import toml

from nsdu import info
from nsdu import exceptions
from nsdu import loader_api
from nsdu import utils

DEFAULT_ID_STORE_FILENAME = 'dispatch_id.json'
DEFAULT_EXT = '.txt'

logger = logging.getLogger(__name__)


class DispatchConfigManager():
    def __init__(self):
        # Dispatch config of all loaded files
        self.all_dispatch_config = {}
        self.new_dispatch_id = {}

    def load_from_files(self, dispatch_config_paths):
        """Load dispatch configuration from paths.

        Args:
            dispatch_config_paths (list): Dispatch config file paths
        """

        for dispatch_config_path in dispatch_config_paths:
            self.all_dispatch_config[dispatch_config_path] = utils.get_config_from_toml(dispatch_config_path)

        logger.debug('Loaded all dispatch config files: "%r"', self.all_dispatch_config)

    def get_canonical_dispatch_config(self):
        """Get canonicalized dispatch config

        Returns:
            dict: Canonicalized dispatch configuration
        """

        canonical_dispatch_config = {}

        for dispatch_config in self.all_dispatch_config.values():
            for owner_nation, owner_dispatches in dispatch_config.items():
                if owner_nation not in canonical_dispatch_config:
                    canonical_dispatch_config[owner_nation] = {}
                for name, config in owner_dispatches.items():
                    canonical_config = copy.deepcopy(config)
                    if 'ns_id' not in config and 'action' not in config:
                        canonical_config['action'] = 'create'
                    elif 'action' not in config:
                        canonical_config['action'] = 'edit'
                    elif canonical_config['action'] == 'remove':
                        canonical_config['action'] = 'remove'
                    else:
                        canonical_config['action'] = 'skip'
                    canonical_dispatch_config[owner_nation][name] = canonical_config

        return canonical_dispatch_config

    def add_new_dispatch_id(self, name, dispatch_id):
        """Add id of new dispatch.

        Args:
            name (str): Dispatch name
            dispatch_id (str): Dispatch id
        """

        self.new_dispatch_id[name] = dispatch_id
        self.saved = False

    def save(self):
        """Update dispatch config with new id (if there is) and save it into appropriate files
        """

        if not self.new_dispatch_id:
            return

        for dispatch_config_path, dispatch_config in self.all_dispatch_config.items():
            for owner_nation, owner_dispatches in dispatch_config.items():
                for name, config in owner_dispatches.items():
                    if 'ns_id' not in config and name in self.new_dispatch_id:
                        self.all_dispatch_config[dispatch_config_path][owner_nation][name]['ns_id'] = self.new_dispatch_id.pop(name)

        for dispatch_config_path, dispatch_config in self.all_dispatch_config.items():
            with open(pathlib.Path(dispatch_config_path).expanduser(), 'w') as f:
                toml.dump(dispatch_config, f)

        self.saved = True
        logger.debug('Saved modified dispatch config: %r', self.all_dispatch_config)


class FileDispatchLoader():
    """Load dispatches from plain text files.

    Args:
        dispatch_config_manager (DispatchConfigManager): Dispatch config manager
        template_path (str): Dispatch template folder path
        file_ext (str): Dispatch file extension
    """

    def __init__(self, dispatch_config_manager, template_path, file_ext):
        self.dispatch_config_manager = dispatch_config_manager
        self.template_path = template_path
        self.file_ext = file_ext

    def get_dispatch_config(self):
        """Get dispatch configuration for NSDU's usage

        Returns:
            dict: Dispatch configuration
        """

        return self.dispatch_config_manager.get_canonical_dispatch_config()

    def get_dispatch_template(self, name):
        """Get the template text of a dispatch.

        Args:
            name (str): Dispatch name

        Raises:
            exceptions.LoaderError: Could not find dispatch file

        Returns:
            str: Text
        """

        file_path = pathlib.Path(self.template_path, name).with_suffix(self.file_ext)
        try:
            return file_path.read_text()
        except FileNotFoundError:
            logger.error('Could not find dispatch template file "%s".', file_path)
            return None

    def add_new_dispatch_id(self, name, dispatch_id):
        """Add id of new dispatch into id store.

        Args:
            name (str): Dispatch name
            dispatch_id (str): Dispatch id
        """

        self.dispatch_config_manager.add_new_dispatch_id(name, dispatch_id)

    def save_dispatch_config(self):
        """Save all changes to id store.
        """

        self.dispatch_config_manager.save()


@loader_api.dispatch_loader
def init_dispatch_loader(config):
    try:
        this_config = config['file_dispatchloader']
    except KeyError:
        raise exceptions.ConfigError('File dispatch loader does not have config.')

    try:
        dispatch_config_paths = this_config['dispatch_config_paths']
    except KeyError:
        raise exceptions.ConfigError('There is no dispatch config path!')

    dispatch_config_manager = DispatchConfigManager()
    try:
        dispatch_config_manager.load_from_files(dispatch_config_paths)
    except FileNotFoundError as e:
        raise exceptions.ConfigError('Dispatch config file(s) not found: {}'.format(str(e)))

    try:
        dispatch_template_path = pathlib.Path(this_config['dispatch_template_path']).expanduser()
    except KeyError:
        raise exceptions.ConfigError('There is no dispatch template path!')

    loader = FileDispatchLoader(dispatch_config_manager, dispatch_template_path,
                                this_config.get('file_ext', DEFAULT_EXT))

    return loader


@loader_api.dispatch_loader
def get_dispatch_config(loader):
    return loader.get_dispatch_config()


@loader_api.dispatch_loader
def get_dispatch_template(loader, name):
    return loader.get_dispatch_template(name)


@loader_api.dispatch_loader
def add_dispatch_id(loader, name, dispatch_id):
    loader.add_new_dispatch_id(name, dispatch_id)


@loader_api.dispatch_loader
def cleanup_dispatch_loader(loader):
    loader.save_dispatch_config()
