import functools
import json
from pathlib import Path
from typing import Callable, Mapping, NamedTuple, TypeVar

import pytest
import toml


class Paths(NamedTuple):
    tmp_dir_path: Path
    file_paths: list[Path]


T = TypeVar("T")


def gen_files(
    gen_func: Callable[[Path, T], None],
    tmp_path: Path,
    default_files: Mapping[str, T],
    files: Mapping[str, T],
) -> Paths:
    if files is None:
        files = default_files

    file_paths = []

    for name, content in files.items():
        file_path = tmp_path / name
        gen_func(file_path, content)
        file_paths.append(file_path)

    return Paths(tmp_path, file_paths)


def gen_toml_file(file_path: Path, content: dict):
    with open(file_path, "w") as file:
        toml.dump(content, file)


@pytest.fixture
def toml_files(tmp_path):
    """Generate TOML files for testing."""

    default = {"test.toml": {"s": {"k": "v"}}}
    return functools.partial(gen_files, gen_toml_file, tmp_path, default)


def gen_text_file(file_path: Path, content: str):
    file_path.write_text(content)


@pytest.fixture
def text_files(tmp_path):
    """Create plain text files for testing."""

    default = {"test.txt": "Hello World"}
    return functools.partial(gen_files, gen_text_file, tmp_path, default)


def gen_json_file(file_path: Path, content: dict):
    with open(file_path, "w") as f:
        json.dump(content, f)


@pytest.fixture
def json_files(tmp_path):
    """Create JSON files for testing."""

    default = {"test.json": {"k": "v"}}
    return functools.partial(gen_files, gen_json_file, tmp_path, default)
