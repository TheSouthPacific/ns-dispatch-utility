"""Load dispatch content from plain text files and
dispatch configuration from TOML files.
"""

import logging
from pathlib import Path
from typing import Mapping, Sequence

import toml

import nsdu
from nsdu import loader_api
from nsdu.config import Config
from nsdu.loader_api import DispatchesMetadata, DispatchMetadata, DispatchOp

DEFAULT_EXT = ".txt"

logger = logging.getLogger(__name__)


def parse_dispatch_metadata_dict(raw: dict, owner_nation: str) -> DispatchMetadata:
    """Parse a dispatch metadata dict and return the metadata
    as a DispatchMetadata instance.

    Args:
        raw (dict): Raw dict
        owner_nation (str): Owner nation name

    Raises:
        ValueError: Failed to parse

    Returns:
        DispatchMetadata: Dispatch metadata
    """

    try:
        title = raw["title"]
        category = raw["category"]
        subcategory = raw["subcategory"]
    except KeyError as err:
        raise ValueError(f"{err.args[0]} is missing")

    ns_id = raw.get("ns_id")
    operation = raw.get("op")

    match operation:
        case "create":
            operation = DispatchOp.CREATE
        case "edit":
            operation = DispatchOp.EDIT
        case "delete":
            operation = DispatchOp.DELETE
        case _:
            raise ValueError(f'Invalid operation "{operation}"')

    if operation in [DispatchOp.EDIT, DispatchOp.DELETE] and ns_id is None:
        raise ValueError("Needs ID for edit or deletion")

    return DispatchMetadata(
        ns_id, operation, owner_nation, title, category, subcategory
    )


def parse_dispatch_metadata_file(content: dict) -> DispatchesMetadata:
    """Parse content of a dispatch metadata file and return
    the dispatches' metadata as a DispatchesMetadata instance.

    Args:
        content (dict): File content

    Returns:
        DispatchesMetadata: Metadata of dispatches
    """

    dispatches_metadata: DispatchesMetadata = {}
    for owner_nation, metadata_dicts in content.items():
        for name, metadata_dict in metadata_dicts.items():
            dispatches_metadata[name] = parse_dispatch_metadata_dict(
                metadata_dict, owner_nation
            )
    return dispatches_metadata


def parse_dispatch_metadata_files(
    files_content: Sequence[dict],
) -> DispatchesMetadata:
    """Parse content of many dispatch metadata files and return
    the dispatches' metadata as a DispatchesMetadata instance.

    Args:
        files_content (Sequence[dict]): Files' content

    Returns:
        DispatchesMetadata: Metadata of dispatches
    """

    files_dispatches_metadata: DispatchesMetadata = {}
    for file_content in files_content:
        dispatches_metadata = parse_dispatch_metadata_file(file_content)
        files_dispatches_metadata.update(dispatches_metadata)
    return files_dispatches_metadata


def load_files_content(file_paths: Sequence[str]) -> dict[Path, dict]:
    """Load TOML files as dicts.

    Args:
        file_paths (Sequence[str]): File paths

    Raises:
        loader_api.LoaderError: File not found

    Returns:
        dict[Path, dict]: Files' content
    """

    files_content: dict[Path, dict] = {}
    for path in file_paths:
        try:
            content = nsdu.get_config_from_toml(path)
        except FileNotFoundError as err:
            raise loader_api.LoaderError(
                f'Dispatch metadata file "{path}"" not found.'
            ) from err

        file_path = Path(path)
        files_content[file_path] = content
    return files_content


def get_new_metadata_dict(old_dict: dict, new_dispatch_id: str | None) -> dict:
    """Get a dispatch metadata dict with new data from an old one.

    Args:
        old_dict (dict): Old metadata dict
        new_dispatch_id (str | None): ID of new dispatch

    Returns:
        dict: Metadata dict with new data
    """

    if new_dispatch_id is None:
        return old_dict

    new_dict = old_dict.copy()
    new_dict["ns_id"] = new_dispatch_id
    new_dict["op"] = "edit"
    return new_dict


def update_dispatch_metadata_files(
    files_content: Mapping[Path, dict], new_dispatch_ids: Mapping[str, str]
) -> None:
    """Save new metadata of dispatches into TOML files.

    Args:
        files_content (Mapping[Path, dict]): Files' content
    """

    for path, content in files_content.items():
        new_content = {
            owner: {
                name: get_new_metadata_dict(metadata, new_dispatch_ids.get(name))
                for name, metadata in dispatches_metadata
            }
            for owner, dispatches_metadata in content
        }
        with open(path, "w") as f:
            toml.dump(new_content, f)


class FileDispatchLoader:
    """Wrapper for operations of this loader."""

    def __init__(
        self,
        metadata_files: dict[Path, dict],
        template_path: Path,
        file_ext: str,
    ) -> None:
        """Wrapper for operations of this loader.

        Args:
            metadata_files (dict[Path, dict]): Paths and content of
            dispatch metadata files
            template_path (Path): Dispatch template directory path
            file_ext (str): Dispatch template extension
        """

        self.template_path = template_path
        self.file_ext = file_ext

        self.metadata_files = metadata_files
        self.new_dispatch_ids: dict[str, str] = {}
        self.changed = False

    def get_canonical_dispatch_metadata(self) -> DispatchesMetadata:
        """Get dispatch metadata as a DispatchesMetadata instance.

        Returns:
            DispatchesMetadata: Metadata of dispatches
        """

        files_content = list(self.metadata_files.values())
        return parse_dispatch_metadata_files(files_content)

    def get_dispatch_template(self, name: str) -> str:
        """Get a dispatch template from a text file with the same name.

        Args:
            name (str): Dispatch name

        Raises:
            exceptions.LoaderError: Dispatch file not found

        Returns:
            str: Template text
        """

        file_path = Path(self.template_path, name).with_suffix(self.file_ext)
        try:
            return file_path.read_text()
        except FileNotFoundError:
            raise loader_api.DispatchTemplateNotFound

    def add_new_dispatch_id(self, name: str, dispatch_id: str) -> None:
        """Add ID of a new dispatch.

        Args:
            name (str): Dispatch name
            dispatch_id (str): Dispatch ID
        """

        self.new_dispatch_ids[name] = dispatch_id

    def save_updated_dispatch_metadata(self) -> None:
        """Save new dispatch IDs into dispatch configuration file(s)."""

        if not self.changed:
            return
        update_dispatch_metadata_files(self.metadata_files, self.new_dispatch_ids)
        self.changed = False
        logger.debug("Saved modified dispatch config: %r", self.metadata_files)


@loader_api.dispatch_loader
def init_dispatch_loader(loaders_config: Config):
    try:
        loader_config = loaders_config["file_dispatch_loader"]
    except KeyError:
        raise loader_api.LoaderError(
            "file_dispatch_loader is not configured. "
            "Please set file_dispatch_loader in loaders_config."
        )

    try:
        dispatch_metadata_paths = loader_config["metadata_paths"]
    except KeyError:
        raise loader_api.LoaderError(
            "No dispatch metadata path configured. "
            "Please set metadata_paths in this loader's config."
        )
    metadata_files_content = load_files_content(dispatch_metadata_paths)

    try:
        dispatch_template_path = Path(loader_config["template_path"]).expanduser()
    except KeyError:
        raise loader_api.LoaderError(
            "No dispatch template path configured. "
            "Please set template_path in this loader's config."
        )

    template_file_extension = loader_config.get("file_ext", DEFAULT_EXT)

    loader = FileDispatchLoader(
        metadata_files_content,
        dispatch_template_path,
        template_file_extension,
    )
    return loader


@loader_api.dispatch_loader
def get_dispatch_metadata(loader: FileDispatchLoader):
    return loader.get_canonical_dispatch_metadata()


@loader_api.dispatch_loader
def get_dispatch_template(loader: FileDispatchLoader, name: str) -> str:
    return loader.get_dispatch_template(name)


@loader_api.dispatch_loader
def add_dispatch_id(loader: FileDispatchLoader, name: str, dispatch_id: str) -> None:
    loader.add_new_dispatch_id(name, dispatch_id)


@loader_api.dispatch_loader
def cleanup_dispatch_loader(loader: FileDispatchLoader) -> None:
    loader.save_updated_dispatch_metadata()
