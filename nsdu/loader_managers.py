"""Load loader plugins and expose interfaces to use them.
"""
from __future__ import annotations
import collections
from abc import ABC, abstractmethod
from datetime import datetime
from importlib.metadata import EntryPoint
from pathlib import Path
from types import ModuleType
from typing import Sequence

import pluggy

from nsdu import exceptions, info, loader_api, utils
from nsdu.config import Config


class LoaderLoadError(exceptions.NSDUError):
    """Loader source file not found."""


class LoaderManager(ABC):
    """Expose interface to manage and interact with loader plugin(s)."""

    def __init__(self, proj_name: str, loaders_config: Config) -> None:
        """Expose interface to manage and interact with loader plugin(s).

        Args:
            proj_name (str): Pluggy project name for this loader plugin type
            loaders_config (Config): Config of loaders
        """

        self.manager = pluggy.PluginManager(proj_name)
        self.manager.add_hookspecs(loader_api)
        self._loaders_config = loaders_config

    def load_loader(self, module: ModuleType) -> None:
        """Register a loader by its Python module.

        Args:
            module (ModuleType): Python module
        """

        self.manager.register(module)

    def get_loaders(self) -> set[ModuleType]:
        """Get the Python modules of all registered loaders.

        Returns:
            set: Loaded loaders
        """

        return self.manager.get_plugins()


class PersistentLoaderManager(LoaderManager):
    """Expose interface to manage and interact with loader plugin(s)
    that hold states through many hook calls."""

    def __init__(self, proj_name: str, loaders_config: Config) -> None:
        """Manages loader(s) that hold states through many hook calls.

        Args:
            proj_name (str): Pluggy project name for this loader plugin type
            loaders_config (Config): Config of loaders
        """

        super().__init__(proj_name, loaders_config)
        self.loader = None

    @abstractmethod
    def init_loader(self) -> None:
        """Initialize loader(s)."""

        raise NotImplementedError

    @abstractmethod
    def cleanup_loader(self) -> None:
        """Cleanup loader(s)."""

        raise NotImplementedError


# pylint: disable=maybe-no-member
class TemplateVarLoaderManager(LoaderManager):
    """Expose interface to manage and interact with template variable
    loader plugin(s)."""

    def __init__(self, loaders_config: Config) -> None:
        """Expose interface to manage and interact with template variable
        loader plugin(s).

        Args:
            loaders_config (Config): Config of loaders
        """

        super().__init__(info.TEMPLATE_VAR_LOADER_PROJ, loaders_config)

    def get_all_template_vars(self):
        template_vars = self.manager.hook.get_template_vars(
            loaders_config=self._loaders_config
        )
        merged_template_vars = dict(collections.ChainMap(*template_vars))
        return merged_template_vars


class DispatchLoaderManager(PersistentLoaderManager):
    """Expose interface to manage and interact with a dispatch loader plugin."""

    def __init__(self, loaders_config: Config) -> None:
        """Expose interface to manage and interact with a dispatch loader plugin.

        Args:
            loaders_config (Config): Config of loaders
        """

        super().__init__(info.DISPATCH_LOADER_PROJ, loaders_config)

    def init_loader(self):
        self.loader = self.manager.hook.init_dispatch_loader(
            loaders_config=self._loaders_config
        )

    def cleanup_loader(self):
        self.manager.hook.cleanup_dispatch_loader(loader=self.loader)

    def get_dispatch_metadata(self) -> loader_api.DispatchesMetadata:
        return self.manager.hook.get_dispatch_metadata(loader=self.loader)

    def get_dispatch_template(self, name: str) -> str:
        return self.manager.hook.get_dispatch_template(loader=self.loader, name=name)

    def after_update(
        self,
        name: str,
        op: loader_api.DispatchOp,
        result: loader_api.DispatchOpResult,
        result_time: datetime,
        result_details: str | None,
    ) -> None:
        self.manager.hook.after_update(
            loader=self.loader,
            name=name,
            op=op,
            result=result,
            result_time=result_time,
            result_details=result_details,
        )

    def add_dispatch_id(self, name: str, dispatch_id: str) -> None:
        self.manager.hook.add_dispatch_id(
            loader=self.loader, name=name, dispatch_id=dispatch_id
        )


class SimpleBbcLoaderManager(LoaderManager):
    """Expose interface to manage and interact with a loader plugin
    which loads simple BBCode formatters."""

    def __init__(self, loaders_config: Config) -> None:
        """Expose interface to manage and interact with a loader plugin
        which loads simple BBCode formatters.

            Args:
                loaders_config (Config): Config of loaders
        """

        super().__init__(info.SIMPLE_BB_LOADER_PROJ, loaders_config)

    def get_simple_bbc_config(self) -> loader_api.BbcConfig:
        return self.manager.hook.get_simple_bbc_config(
            loaders_config=self._loaders_config
        )


class CredLoaderManager(PersistentLoaderManager):
    """Expose interface to manage and interact with a nation login
    credential loader."""

    def __init__(self, loaders_config: Config) -> None:
        """Expose interface to manage and interact with a nation login
        credential loader.

        Args:
            loaders_config (Config): Config of loaders
        """

        super().__init__(info.CRED_LOADER_PROJ, loaders_config)

    def init_loader(self):
        self._loader = self.manager.hook.init_cred_loader(
            loaders_config=self._loaders_config
        )

    def cleanup_loader(self):
        self.manager.hook.cleanup_cred_loader(loader=self._loader)

    def get_cred(self, name: str) -> str:
        return self.manager.hook.get_cred(loader=self._loader, name=name)

    def add_cred(self, name: str, x_autologin: str) -> None:
        self.manager.hook.add_cred(
            loader=self._loader,
            name=utils.canonical_nation_name(name),
            x_autologin=x_autologin,
        )

    def remove_cred(self, name: str) -> None:
        self.manager.hook.remove_cred(
            loader=self._loader, name=utils.canonical_nation_name(name)
        )


def load_modules_from_entry_points(
    entry_points: Sequence[EntryPoint], names: Sequence[str]
) -> dict[str, ModuleType]:
    """Load many modules from package entry points.

    Args:
        entry_points (Sequence[EntryPoint]): Package entry points
        names (Sequence[str]): Entry point names

    Returns:
        dict[str, ModuleType]: Modules keyed by entry point name
    """

    modules: dict[str, ModuleType] = {}
    for entry_point in entry_points:
        if entry_point.name in names:
            modules[entry_point.name] = entry_point.load()
    return modules


def load_modules_from_dir(
    dir_path: Path, names: Sequence[str]
) -> dict[str, ModuleType]:
    """Load modules with provided names from a directory.
    Missing/failed to load modules are ignored.

    Args:
        dir_path (Path): Directory to find modules
        names (Sequence[str]): Module names

    Returns:
        dict[str, ModuleType]: Modules keyed by name
    """

    modules: dict[str, ModuleType] = {}
    for name in names:
        try:
            module_file_path = (dir_path / name).with_suffix(".py")
            modules[name] = utils.load_module(module_file_path)
        except ModuleNotFoundError:
            pass
    return modules


def load_loader_modules(
    names: Sequence[str],
    entry_points: Sequence[EntryPoint],
    custom_dir_path: Path | None,
) -> list[ModuleType]:
    """Load loader plugin modules from default directory,
    package entry points, and custom directory.

    Args:
        names (Sequence[str]): Loader names
        entry_points (Sequence[EntryPoint]): Package entry points
        custom_dir_path (Path | None): Custom loader directory

    Raises:
        LoaderLoadError: Failed to load a loader

    Returns:
        list[ModuleType]: Modules of loaders
    """

    modules = load_modules_from_dir(info.LOADER_DIR_PATH, names)
    modules.update(load_modules_from_entry_points(entry_points, names))
    if custom_dir_path is not None:
        modules.update(load_modules_from_dir(custom_dir_path, names))

    failed_to_load = set(names) - set(modules.keys())
    if failed_to_load:
        raise LoaderLoadError(f"Loaders {list(failed_to_load)} not found")

    return list(modules.values())


class LoaderManagerBuilder(ABC):
    def __init__(
        self,
        entry_points: Sequence[EntryPoint],
        custom_dir_path: Path | None,
    ) -> None:
        """Build a loader manager with loader modules from, default directory,
        package entry points, and custom directory

        Args:
            entry_points (Sequence[EntryPoint]): Package entry points
            custom_dir_path (Path | None): Custom loader directory
        """

        self.entry_points = entry_points
        self.custom_dir_path = custom_dir_path

    def build(self, manager: LoaderManager, names: str | Sequence[str]):
        """Build a loader manager using loaders with provided names.

        Args:
            manager (LoaderManager): Loader manager object
            names (str | Sequence[str]): Loader name(s)
        """

        if isinstance(names, str):
            loader_modules = load_loader_modules(
                [names], self.entry_points, self.custom_dir_path
            )
            manager.load_loader(loader_modules[0])
        else:
            loader_modules = load_loader_modules(
                names, self.entry_points, self.custom_dir_path
            )
            for module in loader_modules:
                manager.load_loader(module)
