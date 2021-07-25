"""Load and run plugins.
"""

import collections
import os
import pathlib

import pluggy

from nsdu import info
from nsdu import loader_api
from nsdu import utils


class Loader():
    """Handling loader plugins.

    Args:
        proj_name (str): Pluggy project name for this plugin type
        name (str|list): Name(s) of loader's source file(s)
        loader_config (dict): Loaders' configuration
    """

    def __init__(self, proj_name, name, loader_config):
        self.manager = pluggy.PluginManager(proj_name)
        self.manager.add_hookspecs(loader_api)
        self.loader_config = loader_config
        self.name = name

    def load_a_loader(self, name):
        """Load a loader's module and register it.

        Args:
            name (str): Name of loader's source file
        """

        path = (info.LOADER_DIR_PATH / name).with_suffix('.py')
        module = utils.load_module(path, name)
        self.manager.register(module)

    def load_loader(self):
        """Load loader(s).
        """

        if isinstance(self.name, list):
            for name in self.name:
                self.load_a_loader(name)
        else:
            self.load_a_loader(self.name)


class PersistentLoader(Loader):
    """Handling plugins that maintain state for the entire duration of the app.

    Args:
        Same as Loader class
    """

    def __init__(self, proj_name, name, loader_config):
        super().__init__(proj_name, name, loader_config)
        # Loader instance to reuse the same database connection
        # across hook calls.
        self._loader = None

    def load_loader(self):
        """Load a loader and return its instance for
        reusing file handlers/database connections.
        """

        super().load_loader()
        self.init_loader()

    def init_loader(self):
        raise NotImplementedError

    def cleanup_loader(self):
        raise NotImplementedError


# pylint: disable=maybe-no-member
class VarLoader(Loader):
    """Load variables from multiple loaders.

    Args:
        names (list): Names of loaders' source file
    """

    def __init__(self, names, loader_config):
        super().__init__(info.VAR_LOADER_PROJ, names, loader_config)

    def get_all_vars(self):
        vars_list = self.manager.hook.get_vars(config=self.loader_config)
        merged_vars_dict = dict(collections.ChainMap(*vars_list))
        return merged_vars_dict


class DispatchLoader(PersistentLoader):
    """Load dispatch information and content.

    Args:
        name (str): Name of loader's source file
    """

    def __init__(self, name, loader_config):
        super().__init__(info.DISPATCH_LOADER_PROJ, name, loader_config)

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


class SimpleBBLoader(Loader):
    """Load simple BBCode formatter config.

    Args:
        name (str): Name of loader's source file
    """

    def __init__(self, name, loader_config):
        super().__init__(info.SIMPLE_BB_LOADER_PROJ, name, loader_config)

    def get_simple_bb_config(self):
        return self.manager.hook.get_simple_bb_config(config=self.loader_config)


class CredLoader(PersistentLoader):
    """Load nation login credentials.

    Args:
        name (str): Name of loader's source file
    """

    def __init__(self, name, loader_config):
        super().__init__(info.CRED_LOADER_PROJ, name, loader_config)

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
