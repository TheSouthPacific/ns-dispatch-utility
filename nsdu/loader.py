"""Load loader plugins and expose interfaces to use them.
"""

from abc import ABC
from typing import Union
import importlib.metadata as import_metadata
from types import ModuleType
from typing import Any, Mapping, Sequence
import collections
from pathlib import Path

import pluggy

from nsdu import exceptions
from nsdu import info
from nsdu import loader_api
from nsdu import utils


class LoaderManager:
    """Manager for loaded loaders."""

    def __init__(self, proj_name: str, loader_config: Mapping[str, Any]) -> None:
        """Manager for loaded loaders.

        Args:
            proj_name (str): Pluggy project name for this loader plugin type
            loader_config (Mapping[str, Any]): Loaders' configuration
        """

        self.manager = pluggy.PluginManager(proj_name)
        self.manager.add_hookspecs(loader_api)
        self.loader_config = loader_config

    def load_loader(self, module) -> None:
        """Load the Python module of a loader.

        Args:
            module: Python module of the loader
        """

        self.manager.register(module)

    def get_loaded_loaders(self) -> set:
        """Get all loaded loaders.

        Returns:
            set: Loaded loaders
        """

        return self.manager.get_plugins()


class PersistentLoaderManager(LoaderManager):
    """Manager for loaders that live for the entire run of the app."""

    def __init__(self, proj_name: str, loader_config: Mapping[str, Any]) -> None:
        """Manager for loaders that live for the entire run of the app.

        Args:
            proj_name (str): Pluggy project name for this loader plugin type
            loader_config (Mapping[str, Any]): Loaders' configuration
        """

        super().__init__(proj_name, loader_config)
        # The instance of the loader class is stored here after
        # it is loaded for access throughout the app's run time.
        self._loader = None

    def init_loader(self):
        raise NotImplementedError

    def cleanup_loader(self):
        raise NotImplementedError


# pylint: disable=maybe-no-member
class TemplateVarLoaderManager(LoaderManager):
    """Manager for template variable loaders."""

    def __init__(self, loader_config):
        super().__init__(info.TEMPLATE_VAR_LOADER_PROJ, loader_config)

    def get_all_template_vars(self):
        template_vars = self.manager.hook.get_template_vars(config=self.loader_config)
        merged_template_vars = dict(collections.ChainMap(*template_vars))
        return merged_template_vars


class DispatchLoaderManager(PersistentLoaderManager):
    """Manager for a dispatch loader."""

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

    def after_update(self, name, action, result, result_time):
        self.manager.hook.after_update(
            loader=self._loader,
            name=name,
            action=action,
            result=result,
            result_time=result_time,
        )

    def add_dispatch_id(self, name, dispatch_id):
        self.manager.hook.add_dispatch_id(
            loader=self._loader, name=name, dispatch_id=dispatch_id
        )


class SimpleBBLoaderManager(LoaderManager):
    """Manager for a simple BBCode formatter loader."""

    def __init__(self, loader_config):
        super().__init__(info.SIMPLE_BB_LOADER_PROJ, loader_config)

    def get_simple_bb_config(self):
        return self.manager.hook.get_simple_bb_config(config=self.loader_config)


class CredLoaderManager(PersistentLoaderManager):
    """Manager for a login credential loader."""

    def __init__(self, loader_config):
        super().__init__(info.CRED_LOADER_PROJ, loader_config)

    def init_loader(self):
        self._loader = self.manager.hook.init_cred_loader(config=self.loader_config)

    def cleanup_loader(self):
        self.manager.hook.cleanup_cred_loader(loader=self._loader)

    def get_creds(self):
        return self.manager.hook.get_creds(loader=self._loader)

    def add_cred(self, name, x_autologin):
        self.manager.hook.add_cred(
            loader=self._loader,
            name=utils.canonical_nation_name(name),
            x_autologin=x_autologin,
        )

    def remove_cred(self, name):
        self.manager.hook.remove_cred(
            loader=self._loader, name=utils.canonical_nation_name(name)
        )


def load_module_from_entry_points(
    entry_points: Sequence[import_metadata.EntryPoint], name: Sequence[str]
) -> Union[ModuleType, None]:
    """Load a module found via package metadata entry points.

    Args:
        entry_points (Sequence[import_metadata.EntryPoint]): Package entry points
        name (str): Entry point's name

    Returns:
        Union[Any, None]: Loaded Python module or None if fails
    """

    for entry_point in entry_points:
        if entry_point.name == name:
            return entry_point.load()
    return None


def load_all_modules_from_entry_points(
    entry_points: Sequence[import_metadata.EntryPoint], names: Sequence[str]
) -> list[ModuleType]:
    """Load all modules with provided names via package entry points.

    Args:
        entry_points (Sequence[import_metadata.EntryPoint]): Package entry points
        names (Sequence[str]): Entry point names

    Returns:
        list[Any]: Loaded Python modules
    """

    modules = {}
    for entry_point in entry_points:
        if entry_point.name in names:
            modules[entry_point.name] = entry_point.load()
    return modules


class LoaderManagerBuilder(ABC):
    """Base class for loader manager builders."""

    def __init__(
        self,
        default_dir_path: Path,
        custom_dir_path: Path,
        entry_points: Sequence[import_metadata.EntryPoint],
    ) -> None:
        """Base class for loader manager builders.

        Args:
            default_dir_path (Path): Path to default loader directory
            custom_dir_path (Path): Path to custom loader directory
            entry_points (Sequence[import_metadata.EntryPoint]): Package entry points
        """

        self.default_dir_path = default_dir_path
        self.custom_dir_path = custom_dir_path
        self.entry_points = entry_points
        self.loader_manager = None

    def set_loader_manager(self, loader_manager: LoaderManager) -> None:
        """Set loader manager to build.

        Args:
            loader_manager (LoaderManager): Loader manager instance
        """

        self.loader_manager = loader_manager


class SingleLoaderManagerBuilder(LoaderManagerBuilder):
    """Load a loader into a loader manager."""

    def load_from_default_dir(self, name: str) -> None:
        """Load a loader into loader manager from default loader directory.

        Args:
            name (str): Loader name

        Raises:
            exceptions.LoaderNotFound: Failed to find loader
        """

        if self.default_dir_path is None:
            raise ValueError("Default loader directory path is None")

        try:
            loader_module = utils.load_module(
                (self.default_dir_path / name).with_suffix(".py")
            )
        except FileNotFoundError:
            raise exceptions.LoaderNotFound
        self.loader_manager.load_loader(loader_module)

    def load_from_custom_dir(self, name: str) -> None:
        """Load a loader into loader manager from custom loader directory.

        Args:
            name (str): Loader name

        Raises:
            exceptions.LoaderNotFound: Failed to find loader
        """

        if self.custom_dir_path is None:
            raise ValueError("Custom loader directory path is None")

        try:
            loader_module = utils.load_module(
                Path(self.custom_dir_path / name).with_suffix(".py")
            )
        except FileNotFoundError:
            raise exceptions.LoaderNotFound
        self.loader_manager.load_loader(loader_module)

    def load_from_entry_points(self, name: str) -> None:
        """Load a loader into loader manager from package entry points.

        Args:
            name (str): Loader name

        Raises:
            exceptions.LoaderNotFound: Failed to find loader
        """

        loader_module = load_module_from_entry_points(self.entry_points, name)
        if loader_module is None:
            raise exceptions.LoaderNotFound
        self.loader_manager.load_loader(loader_module)

    def load_loader(self, loader_name: str) -> None:
        """Load one loader into loader manager.

        Args:
            loader_name (str): Name of loader to load

        Raises:
            exceptions.LoaderNotFound: No builder could find this loader
        """

        methods = [
            self.load_from_custom_dir,
            self.load_from_entry_points,
            self.load_from_default_dir,
        ]

        for method in methods:
            try:
                method(loader_name)
                break
            except exceptions.LoaderNotFound:
                if method == methods[-1]:
                    raise exceptions.LoaderNotFound(f"Loader {loader_name} not found.")
            except ValueError:
                pass


class MultiLoadersManagerBuilder(LoaderManagerBuilder):
    """Load many loaders into a loader manager."""

    def load_into_manager(self, loader_modules: Mapping[str, ModuleType]) -> None:
        """Load loader modules into loader manager.

        Args:
            loader_modules (Mapping[str, ModuleType]): Loader modules
        """

        for module in loader_modules.values():
            self.loader_manager.load_loader(module)

    def load_from_default_dir(self, names: Sequence[str]) -> Sequence[str]:
        """Load loaders into loader manager from default loader directory.

        Args:
            names (Sequence[str]): Names of loaders to load

        Raises:
            ValueError: Custom loader directory path is None

        Returns:
            Sequence[str]: Names of non-existent loaders
        """

        if self.default_dir_path is None:
            raise ValueError("Default loader directory path is None")

        loader_modules = {}
        failed_loader_module_names = []

        for name in names:
            try:
                loader_modules[name] = utils.load_module(
                    (self.default_dir_path / name).with_suffix(".py")
                )
            except FileNotFoundError:
                failed_loader_module_names.append(name)

        self.load_into_manager(loader_modules)
        return failed_loader_module_names

    def load_from_custom_dir(self, names: Sequence[str]) -> Sequence[str]:
        """Load loaders into loader manager from custom loader directory.

        Args:
            names (Sequence[str]): Names of loaders to load

        Raises:
            ValueError: Custom loader directory path is None

        Returns:
            Sequence[str]: Names of non-existent loaders
        """

        if self.custom_dir_path is None:
            raise ValueError("Custom loader directory path is None")

        loader_modules = {}
        failed_loader_module_names = []

        for name in names:
            try:
                loader_modules[name] = utils.load_module(
                    (self.custom_dir_path / name).with_suffix(".py")
                )
            except FileNotFoundError:
                failed_loader_module_names.append(name)

        self.load_into_manager(loader_modules)
        return failed_loader_module_names

    def load_from_entry_points(self, names: Sequence[str]) -> Sequence[str]:
        """Load loaders into loader manager from package metadata entry points.

        Args:
            names (list): Names of loaders to load

        Returns:
            Sequence[str]: Names of non-existent loaders
        """

        loader_modules = load_all_modules_from_entry_points(self.entry_points, names)
        self.load_into_manager(loader_modules)

        failed_loader_module_names = [
            name for name in names if name not in loader_modules
        ]
        return failed_loader_module_names

    def load_loaders(self, loader_names: Sequence[str]) -> None:
        """Load all provided loaders into loader manager.

        Args:
            loader_names (Sequence[str]): Names of loaders to load

        Raises:
            exceptions.LoaderNotFound: Some loaders could not be found
        """

        methods = [
            self.load_from_custom_dir,
            self.load_from_entry_points,
            self.load_from_default_dir,
        ]

        for method in methods:
            try:
                loader_names = method(loader_names)
            except ValueError:
                pass

        if loader_names:
            raise exceptions.LoaderNotFound(
                f'Loaders {", ".join(loader_names)} not found.'
            )
