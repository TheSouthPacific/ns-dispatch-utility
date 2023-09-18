import pytest

from nsdu import loader_api
from nsdu.loaders import file_simple_bbc_loader


class TestFileVarLoader:
    def test_get_simple_bb_config_with_existent_path(self, toml_files):
        bb_config = {
            "tag1": {"format_string": "test1"},
            "tag2": {"format_string": "test2", "render_embedded": False},
        }
        path = toml_files({"simple_bb_config.toml": bb_config}).file_paths[0]
        loader_config = {"file_simple_bbc_loader": {"file_path": path}}

        r = file_simple_bbc_loader.get_simple_bb_config(loader_config)

        assert r == bb_config

    def test_get_simple_bb_config_with_non_existent_path(self):
        loader_config = {"file_simple_bbc_loader": {"file_path": "a"}}

        with pytest.raises(loader_api.LoaderError):
            file_simple_bbc_loader.get_simple_bb_config(loader_config)

    def test_get_simple_bb_config_with_no_path(self):
        loader_config = {"file_simple_bbc_loader": {}}

        with pytest.raises(loader_api.LoaderError):
            file_simple_bbc_loader.get_simple_bb_config(loader_config)
