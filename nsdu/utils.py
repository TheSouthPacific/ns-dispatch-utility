"""Utility functions.
"""

import inspect
import logging
import sys
from importlib import util as import_util
from pathlib import Path
from types import ModuleType

logger = logging.getLogger(__name__)


def expanded_path(path: Path | str) -> Path:
    """Get user-expanded path.

    Args:
        path (Path | str): Path

    Returns:
        Path: User-expanded path
    """

    return Path(path).expanduser()


def get_functions_from_module(path: Path | str):
    """Get all functions in a Python module file.

    Args:
        path (Path | str): Path to the module file

    Returns:
        Functions
    """

    module = load_module(path)
    return inspect.getmembers(module, inspect.isfunction)


def load_module(path: Path | str) -> ModuleType:
    """Load Python module at the provided path.

    Args:
        path (Path | str): Path to the module file

    Raises:
        ModuleNotFoundError: Could not find the module file

    Returns:
        ModuleType: Loaded module
    """

    path = expanded_path(path)
    module_name = path.name

    spec = import_util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError

    module = import_util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except FileNotFoundError as err:
        raise ModuleNotFoundError from err

    return module


def canonical_nation_name(name: str) -> str:
    """Convert nation name into canonical form (lower case with no underscore).

    Args:
        name (str): Name

    Returns:
        str: Canonical nation name
    """

    return name.lower().replace("_", " ")
