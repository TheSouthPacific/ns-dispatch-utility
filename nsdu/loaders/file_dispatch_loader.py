"""Load dispatch content from plain text files and
dispatch configuration from TOML files.
"""

import copy
import logging
from pathlib import Path
from typing import Sequence

import toml

import nsdu
from nsdu import loader_api
from nsdu.config import Config

DEFAULT_ID_STORE_FILENAME = "dispatch_id.json"
DEFAULT_EXT = ".txt"

logger = logging.getLogger(__name__)


class DispatchConfigManager:
    """Load and save dispatch configuration in TOML files."""

    def __init__(self):
        # Dispatch config of all loaded files
        self.all_dispatch_config = {}
        self.new_dispatch_id = {}
        self.saved = True

    def load_from_files(self, dispatch_config_paths: Sequence[str]) -> None:
        """Load dispatch configuration files from provided paths.

        Args:
            dispatch_config_paths (Sequence[str]): Dispatch config file paths
        """

        for dispatch_config_path in dispatch_config_paths:
            try:
                self.all_dispatch_config[
                    dispatch_config_path
                ] = nsdu.get_config_from_toml(dispatch_config_path)
            except FileNotFoundError:
                raise loader_api.LoaderError(
                    f"Dispatch config file {dispatch_config_path} not found."
                )

        logger.debug('Loaded all dispatch config files: "%r"', self.all_dispatch_config)

    def get_canonical_dispatch_config(self) -> dict[str, dict]:
        """Get dispatch configuration in NSDU's standard format.

        Returns:
            dict[str, dict]: Canonical dispatch configuration
        """

        canonical_dispatch_config = {}

        for dispatch_config in self.all_dispatch_config.values():
            for owner_nation, owner_dispatches in dispatch_config.items():
                if owner_nation not in canonical_dispatch_config:
                    canonical_dispatch_config[owner_nation] = {}
                for name, conf in owner_dispatches.items():
                    canonical_config = copy.deepcopy(conf)
                    if "ns_id" not in conf and "action" not in conf:
                        canonical_config["action"] = "create"
                    elif "action" not in conf:
                        canonical_config["action"] = "edit"
                    elif canonical_config["action"] == "remove":
                        canonical_config["action"] = "remove"
                    else:
                        canonical_config["action"] = "skip"
                    canonical_dispatch_config[owner_nation][name] = canonical_config

        return canonical_dispatch_config

    def add_new_dispatch_id(self, name: str, dispatch_id: str) -> None:
        """Add NationStates-provided ID of a new dispatch.

        Args:
            name (str): Dispatch name
            dispatch_id (str): NationStates-provided ID
        """

        self.new_dispatch_id[name] = dispatch_id
        self.saved = False

    def save(self) -> None:
        """Save new dispatch IDs into the dispatch configuration file(s)."""

        if not self.new_dispatch_id:
            return

        for dispatch_config_path, dispatch_config in self.all_dispatch_config.items():
            for owner_nation, owner_dispatches in dispatch_config.items():
                for name, conf in owner_dispatches.items():
                    if "ns_id" not in conf and name in self.new_dispatch_id:
                        self.all_dispatch_config[dispatch_config_path][owner_nation][
                            name
                        ]["ns_id"] = self.new_dispatch_id.pop(name)

        for dispatch_config_path, dispatch_config in self.all_dispatch_config.items():
            with open(Path(dispatch_config_path).expanduser(), "w") as f:
                toml.dump(dispatch_config, f)

        self.saved = True
        logger.debug("Saved modified dispatch config: %r", self.all_dispatch_config)


class FileDispatchLoader:
    """Wrapper to persist state and expose standard operations."""

    def __init__(
        self,
        dispatch_config_manager: DispatchConfigManager,
        template_path: Path,
        file_ext: str,
    ) -> None:
        """Wrapper to persist state and expose standard operations.

        Args:
            dispatch_config_manager (DispatchConfigManager): Dispatch config manager
            template_path (Path): Dispatch template folder path
            file_ext (str): Dispatch file extension
        """

        self.dispatch_config_manager = dispatch_config_manager
        self.template_path = template_path
        self.file_ext = file_ext

    def get_dispatch_config(self) -> dict[str, dict]:
        """Get dispatch configuration in NSDU's standard format.

        Returns:
            dict: Dispatch configuration
        """

        return self.dispatch_config_manager.get_canonical_dispatch_config()

    def get_dispatch_template(self, name: str) -> str:
        """Get the template text of a dispatch.

        Args:
            name (str): Dispatch name

        Raises:
            exceptions.LoaderError: Could not find dispatch file

        Returns:
            str | None: Template text
        """

        file_path = Path(self.template_path, name).with_suffix(self.file_ext)
        try:
            return file_path.read_text()
        except FileNotFoundError:
            raise ValueError("Dispatch template not found")

    def add_new_dispatch_id(self, name, dispatch_id) -> None:
        """Add NationStates-provided ID of a new dispatch.

        Args:
            name (str): Dispatch name
            dispatch_id (str): NationStates-provided ID
        """

        self.dispatch_config_manager.add_new_dispatch_id(name, dispatch_id)

    def save_dispatch_config(self) -> None:
        """Save new dispatch IDs into dispatch configuration file(s)."""

        self.dispatch_config_manager.save()


@loader_api.dispatch_loader
def init_dispatch_loader(loaders_config: Config):
    try:
        loader_config = loaders_config["file_dispatch_loader"]
    except KeyError:
        raise loader_api.LoaderError("File dispatch loader does not have config.")

    try:
        dispatch_config_paths = loader_config["dispatch_config_paths"]
    except KeyError:
        raise loader_api.LoaderError("There is no dispatch config path!")

    dispatch_config_manager = DispatchConfigManager()
    dispatch_config_manager.load_from_files(dispatch_config_paths)

    try:
        dispatch_template_path = Path(
            loader_config["dispatch_template_path"]
        ).expanduser()
    except KeyError:
        raise loader_api.LoaderError("There is no dispatch template path!")

    loader = FileDispatchLoader(
        dispatch_config_manager,
        dispatch_template_path,
        loader_config.get("file_ext", DEFAULT_EXT),
    )

    return loader


@loader_api.dispatch_loader
def get_dispatch_metadata(loader: FileDispatchLoader):
    return loader.get_dispatch_config()


@loader_api.dispatch_loader
def get_dispatch_template(loader: FileDispatchLoader, name: str) -> str:
    return loader.get_dispatch_template(name)


@loader_api.dispatch_loader
def add_dispatch_id(loader: FileDispatchLoader, name: str, dispatch_id: str) -> None:
    loader.add_new_dispatch_id(name, dispatch_id)


@loader_api.dispatch_loader
def cleanup_dispatch_loader(loader: FileDispatchLoader) -> None:
    loader.save_dispatch_config()
