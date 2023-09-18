import json

import pytest
import toml


@pytest.fixture
def toml_files(tmp_path):
    """Generate TOML config files for testing."""

    def gen_toml_files(files={"test.toml": {"sec": {"key": "val"}}}):
        f_path = None
        for name, config in files.items():
            f_path = tmp_path / name
            with open(f_path, "w") as f:
                toml.dump(config, f)

        if len(files) == 1:
            return f_path
        return tmp_path

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
