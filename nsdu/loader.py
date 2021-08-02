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
    for entry_point in entry_points:
        if entry_point.name == name:
            return entry_point.load()
    return None


def load_all_modules_from_entry_points(entry_points, names):
    modules = {}
    for entry_point in entry_points:
        if entry_point.name in names:
            modules[entry_point.name] = entry_point.load()
    return modules


class LoaderHandleBuilder():
    def __init__(self, default_dir_path, custom_dir_path, entry_points):
        self.default_dir_path = default_dir_path
        self.custom_dir_path = custom_dir_path
        self.entry_points = entry_points


class SingleLoaderHandleBuilder(LoaderHandleBuilder):
    def __init__(self, default_dir_path, custom_dir_path, entry_points):
        super().__init__(default_dir_path, custom_dir_path, entry_points)

    def load_loader(self, loader_obj, name):
        if self.custom_dir_path is not None:
            try:
                loaded_module = utils.load_module((self.custom_dir_path / name).with_suffix('.py'))
                loader_obj.load_loader(loaded_module)
                return
            except FileNotFoundError:
                pass

        loaded_module = load_module_from_entry_points(self.entry_points, name)
        if loaded_module is not None:
            loader_obj.load_loader(loaded_module)
            return

        try:
            loaded_module = utils.load_module((self.default_dir_path / name).with_suffix('.py'))
            loader_obj.load_loader(loaded_module)
            return
        except FileNotFoundError:
            raise exceptions.LoaderNotFound('Loader "{}" not found.'.format(name))


class MultiLoadersHandleBuilder(LoaderHandleBuilder):
    def __init__(self, default_dir_path, custom_dir_path, entry_points):
        super().__init__(default_dir_path, custom_dir_path, entry_points)

    def load_loader(self, loader_obj, names):
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
                    loaded_modules[name] = utils.load_module((self.custom_dir_path / name).with_suffix('.py'))
                except FileNotFoundError:
                    pass

        for name in names:
            if name in loaded_modules:
                loader_obj.load_loader(loaded_modules[name])
            else:
                raise exceptions.LoaderNotFound('Loader "{}" not found.'.format(name))


class LoaderHandle():
    """Handle for loaded loaders.

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


class PersistentLoaderHandle(LoaderHandle):
    """Handle for loaders that maintain state for the entire duration of the app.

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
        reusing file handlers/database connections.
        """

        super().load_loader(module)
        self.init_loader()

    def init_loader(self):
        raise NotImplementedError

    def cleanup_loader(self):
        raise NotImplementedError


# pylint: disable=maybe-no-member
class VarLoaderHandle(LoaderHandle):
    """Handle for variable loaders.
    """

    def __init__(self, loader_config):
        super().__init__(info.VAR_LOADER_PROJ, loader_config)

    def get_all_vars(self):
        vars_list = self.manager.hook.get_vars(config=self.loader_config)
        merged_vars_dict = dict(collections.ChainMap(*vars_list))
        return merged_vars_dict


class DispatchLoaderHandle(PersistentLoaderHandle):
    """Handle for a dispatch loader.
    """

    def __init__(self, loader_config):
        super().__init__(info.DISPATCH_LOADER_PROJ, loader_config)

    def init_loader(self):
        self._loader = self.manager.hook.init_dispatch_loader(config=self.loader_config)

    def cleanup_loader(self):
        self.manager.hook.cleanup_dispatch_loader(loader=self._loader)

    def get_dispatch_config(self):
        return self.manager.hook.get_dispatch_config(loader=self._loader)

    def get_dispatch_text(self, name):
        return self.manager.hook.get_dispatch_text(loader=self._loader, name=name)

    def add_dispatch_id(self, name, dispatch_id):
        return self.manager.hook.add_dispatch_id(loader=self._loader,
                                                 name=name,
                                                 dispatch_id=dispatch_id)


class SimpleBBLoaderHandle(LoaderHandle):
    """Handle for a simple BBCode formatter loader.
    """

    def __init__(self, loader_config):
        super().__init__(info.SIMPLE_BB_LOADER_PROJ, loader_config)

    def get_simple_bb_config(self):
        return self.manager.hook.get_simple_bb_config(config=self.loader_config)


class CredLoaderHandle(PersistentLoaderHandle):
    """Handle for a login credential loader.
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
