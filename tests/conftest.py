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
    """Generate TOML config files for testing."""

    def gen_toml_files(files: Mapping[str, dict] | None = None) -> Paths:
        if files is None:
            files = {"test.toml": {"sec": {"key": "val"}}}

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
    """Create text files for testing."""

    def gen_text_files(files={"test.txt": "Foo Bar"}):
        f_path = None
        for name, text in files.items():
            f_path = tmp_path / name
            f_path.write_text(text)

        if len(files) == 1:
            return f_path
        return tmp_path

    return gen_text_files


@pytest.fixture
def json_files(tmp_path):
    """Create JSON files for testing."""

    def gen_json_files(files={"test.json": {"key": "value"}}):
        f_path = None
        for name, content in files.items():
            f_path = tmp_path / name
            with open(f_path, "w") as f:
                json.dump(content, f)

        if len(files) == 1:
            return f_path
        return tmp_path

    return gen_json_files
