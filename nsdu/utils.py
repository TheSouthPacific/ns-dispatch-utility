"""Utility functions.
"""

import inspect
import logging
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Mapping


from nsdu import exceptions


logger = logging.getLogger(__name__)


def get_dispatch_info(dispatch_config: Mapping) -> dict:
    """Return dispatch information for use as context in the template renderer.

    Args:
        dispatch_config (Mapping): Dispatch configuration.

    Returns:
        dict: Dispatch information.
    """

    dispatch_info = {}
    for nation, dispatches in dispatch_config.items():
        for name, config in dispatches.items():
            config["owner_nation"] = nation
            dispatch_info[name] = config

    return dispatch_info


def get_functions_from_module(path: Path | str) -> list[Any]:
    """Get all functions from a Python module file.

    Args:
        path (Path | str): Path to the module file

    Returns:
        list[Any]: Functions
    """

    module = load_module(Path(path))
    return inspect.getmembers(module, inspect.isfunction)


def load_module(path: Path | str) -> ModuleType:
    """Load Python module at the provided path.

    Args:
        path (Path | str): Path to the module file

    Raises:
        FileNotFoundError: Could not find the module file

    Returns:
        ModuleType: Loaded module
    """

    path = Path(path)
    module_name = path.name
    spec = importlib.util.spec_from_file_location(module_name, path.expanduser())
    if spec is not None:
        if not spec.loader:
            raise exceptions.NSDUError(f"Failed to load loader {module_name}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    raise FileNotFoundError


def canonical_nation_name(name: str) -> str:
    """Canonicalize nation name into lower case form with no underscore.

    Args:
        name (str): Name

    Returns:
        str: Canonical nation name
    """

    return name.lower().replace("_", " ")
