"""Load and run plugins.
"""

import collections
import os
import pathlib

import pluggy

from nsdu import exceptions
from nsdu import info
from nsdu import loader_api
from nsdu import utils


def load_module_from_entry_points(entry_points, name):
    """Load module found via metadata entry points.

    Args:
        entry_points (list): List of entry points
        name (str): Entry point's name

    Returns:
        Loaded Python module
    """

    for entry_point in entry_points:
        if entry_point.name == name:
            return entry_point.load()
    return None


def load_all_modules_from_entry_points(entry_points, names):
    """Load all modules with name in names via metadata entry points.

    Args:
        entry_points (list): List of entry points
        names (list): List of entry points' names

    Returns:
        Loaded Python module
    """

    modules = {}
    for entry_point in entry_points:
        if entry_point.name in names:
            modules[entry_point.name] = entry_point.load()
    return modules


class LoaderManagerBuilder():
    """Abstract class for loader manager builders.

    Args:
        default_dir_path (pathlib.Path): Default loader directory
        custom_dir_path (pathlib.Path): User-confiured loader directory
        entry_points (list): List of entry points
    """

    def __init__(self, default_dir_path, custom_dir_path, entry_points):
        self.default_dir_path = default_dir_path
        self.custom_dir_path = custom_dir_path
        self.entry_points = entry_points


class SingleLoaderManagerBuilder(LoaderManagerBuilder):
    """Build loader manager that managers one loader only.
    """

    def __init__(self, default_dir_path, custom_dir_path, entry_points):
        super().__init__(default_dir_path, custom_dir_path, entry_points)

    def load_loader(self, manager, name):
        """Load loader into manager.

        Args:
            manager (loader.LoaderManager): Single loader manager object
            name (str): Loader name

        Raises:
            exceptions.LoaderNotFound: Failed to find loader
        """

        if self.custom_dir_path is not None:
            try:
                loaded_module = utils.load_module(pathlib.Path(self.custom_dir_path / name).with_suffix('.py'))
                manager.load_loader(loaded_module)
                return
            except FileNotFoundError:
                pass

        loaded_module = load_module_from_entry_points(self.entry_points, name)
        if loaded_module is not None:
            manager.load_loader(loaded_module)
            return

        try:
            loaded_module = utils.load_module((self.default_dir_path / name).with_suffix('.py'))
            manager.load_loader(loaded_module)
            return
        except FileNotFoundError:
            raise exceptions.LoaderNotFound('Loader "{}" not found.'.format(name))


class MultiLoadersManagerBuilder(LoaderManagerBuilder):
    """Build loader manager that managers many loaders
    """
    def __init__(self, default_dir_path, custom_dir_path, entry_points):
        super().__init__(default_dir_path, custom_dir_path, entry_points)

    def load_loader(self, manager, names):
        """Load loaders into manager.

        Args:
            manager (loader.LoaderManager): Multi-loaders manager object
            names (list): Loader names

        Raises:
            exceptions.LoaderNotFound: Failed to find loader
        """

        loaded_modules = {}
        for name in names:
            try:
                loaded_modules[name] = utils.load_module((self.default_dir_path / name).with_suffix('.py'))
            except FileNotFoundError:
                pass

        loaded_modules.update(load_all_modules_from_entry_points(self.entry_points, names))

        if self.custom_dir_path is not None:
            for name in names:
                try:
                    loaded_modules[name] = utils.load_module(pathlib.Path(self.custom_dir_path / name).with_suffix('.py'))
                except FileNotFoundError:
                    pass

        for name in names:
            if name in loaded_modules:
                manager.load_loader(loaded_modules[name])
            else:
                raise exceptions.LoaderNotFound('Loader "{}" not found.'.format(name))


class LoaderManager():
    """Manager for loaded loaders.

    Args:
        proj_name (str): Pluggy project name for this plugin type
        loader_config (dict): Loaders' configuration
    """

    def __init__(self, proj_name, loader_config):
        self.manager = pluggy.PluginManager(proj_name)
        self.manager.add_hookspecs(loader_api)
        self.loader_config = loader_config

    def load_loader(self, module):
        """Load source of loader.

        Args:
            module: Module that contains the source
        """

        self.manager.register(module)


class PersistentLoaderManager(LoaderManager):
    """Manager for loaders that maintain state for the entire duration of the app.

    Args:
        Same as Loader class
    """

    def __init__(self, proj_name, loader_config):
        super().__init__(proj_name, loader_config)
        # Loader instance to reuse the same database connection
        # across hook calls.
        self._loader = None

    def load_loader(self, module):
        """Load a loader and return its instance for
        reusing file managerrs/database connections.
        """

        super().load_loader(module)
        self.init_loader()

    def init_loader(self):
        raise NotImplementedError

    def cleanup_loader(self):
        raise NotImplementedError


# pylint: disable=maybe-no-member
class TemplateVarLoaderManager(LoaderManager):
    """Manager for template variable loaders.
    """

    def __init__(self, loader_config):
        super().__init__(info.TEMPLATE_VAR_LOADER_PROJ, loader_config)

    def get_all_template_vars(self):
        template_vars = self.manager.hook.get_template_vars(config=self.loader_config)
        merged_template_vars = dict(collections.ChainMap(*template_vars))
        return merged_template_vars


class DispatchLoaderManager(PersistentLoaderManager):
    """Manager for a dispatch loader.
    """

    def __init__(self, loader_config):
        super().__init__(info.DISPATCH_LOADER_PROJ, loader_config)

    def init_loader(self):
        self._loader = self.manager.hook.init_dispatch_loader(config=self.loader_config)

    def cleanup_loader(self):
        self.manager.hook.cleanup_dispatch_loader(loader=self._loader)

    def get_dispatch_config(self):
        return self.manager.hook.get_dispatch_config(loader=self._loader)

    def get_dispatch_template(self, name):
        return self.manager.hook.get_dispatch_template(loader=self._loader, name=name)

    def add_dispatch_id(self, name, dispatch_id):
        return self.manager.hook.add_dispatch_id(loader=self._loader,
                                                 name=name,
                                                 dispatch_id=dispatch_id)


class SimpleBBLoaderManager(LoaderManager):
    """Manager for a simple BBCode formatter loader.
    """

    def __init__(self, loader_config):
        super().__init__(info.SIMPLE_BB_LOADER_PROJ, loader_config)

    def get_simple_bb_config(self):
        return self.manager.hook.get_simple_bb_config(config=self.loader_config)


class CredLoaderManager(PersistentLoaderManager):
    """Manager for a login credential loader.
    """

    def __init__(self, loader_config):
        super().__init__(info.CRED_LOADER_PROJ, loader_config)

    def init_loader(self):
        self._loader = self.manager.hook.init_cred_loader(config=self.loader_config)

    def cleanup_loader(self):
        self.manager.hook.cleanup_cred_loader(loader=self._loader)

    def get_creds(self):
        return self.manager.hook.get_creds(loader=self._loader)

    def add_cred(self, name, x_autologin):
        return self.manager.hook.add_cred(loader=self._loader,
                                          name=name, x_autologin=x_autologin)

    def remove_cred(self, name):
        return self.manager.hook.remove_cred(loader=self._loader, name=name)
