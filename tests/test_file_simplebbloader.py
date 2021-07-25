import pytest

from nsdu import exceptions
from nsdu.loaders import file_simplebbloader


class TestFileVarLoader():
    def test_get_simple_bb_config_with_existent_path(self, toml_files):
        bb_config = {'tag1': {'format_string': 'test1'},
                     'tag2': {'format_string': 'test2', 'render_embedded': False}}
        path = toml_files({'simple_bb_config.toml': bb_config})
        loader_config = {'file_simplebbloader': {'file_path': path}}

        r = file_simplebbloader.get_simple_bb_config(loader_config)

        assert r == bb_config

    def test_get_simple_bb_config_with_non_existent_path(self):
        loader_config = {'file_simplebbloader': {'file_path': 'non_existent.toml'}}

        with pytest.raises(exceptions.LoaderConfigError):
            file_simplebbloader.get_simple_bb_config(loader_config)

    def test_get_simple_bb_config_with_no_path(self):
        loader_config = {'file_simplebbloader': {}}

        r = file_simplebbloader.get_simple_bb_config(loader_config)

        assert r is None
