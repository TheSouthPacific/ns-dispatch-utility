import json
from pathlib import Path
from typing import Mapping, NamedTuple

import pytest
import toml


class Paths(NamedTuple):
    tmp_dir_path: Path
    file_paths: list[Path]


@pytest.fixture
def toml_files(tmp_path):
    """Generate TOML files for testing."""

    def gen_toml_files(files: Mapping[str, dict] | None = None) -> Paths:
        if files is None:
            files = {"test.toml": {"s": {"k": "v"}}}

        file_paths = []

        for name, config in files.items():
            file_path = tmp_path / name
            with open(file_path, "w") as f:
                toml.dump(config, f)
            file_paths.append(file_path)

        return Paths(tmp_path, file_paths)

    return gen_toml_files


@pytest.fixture
def text_files(tmp_path):
    """Create plain text files for testing."""

    def gen_text_files(files: Mapping[str, str] | None = None):
        if files is None:
            files = {"test.txt": "Hello World"}

        file_paths = []

        for name, text in files.items():
            file_path = tmp_path / name
            file_path.write_text(text)
            file_paths.append(file_path)

        return Paths(tmp_path, file_paths)

    return gen_text_files


@pytest.fixture
def json_files(tmp_path):
    """Create JSON files for testing."""

    def gen_json_files(files: Mapping[str, dict] | None = None):
        if files is None:
            files = {"test.json": {"key": "val"}}

        file_paths = []

        for name, config in files.items():
            file_path = tmp_path / name
            with open(file_path, "w") as f:
                json.dump(config, f)
            file_paths.append(file_path)

        return Paths(tmp_path, file_paths)

    return gen_json_files
