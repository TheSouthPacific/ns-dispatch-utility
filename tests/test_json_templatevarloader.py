import pytest

from nsdu import exceptions
from nsdu.loaders import json_templatevarloader


class TestJsonTemplateVarLoader:
    def test_load_valid_json_file_returns_dict_of_json_content(self, json_files):
        json_path = json_files({"foobar.json": {"key1": "value1"}})
        loader_config = {"json_templatevarloader": {"template_var_paths": [json_path]}}

        result = json_templatevarloader.get_template_vars(loader_config)

        assert result == {"key1": "value1"}

    def test_load_two_json_files_with_same_root_keys_returns_last_matching_key(
        self, json_files
    ):
        json_dir = json_files(
            {"foobar1.json": {"key1": "value1"}, "foobar2.json": {"key1": "value2"}}
        )
        json_path_1 = str(json_dir / "foobar1.json")
        json_path_2 = str(json_dir / "foobar2.json")
        loader_config = {
            "json_templatevarloader": {"template_var_paths": [json_path_1, json_path_2]}
        }

        result = json_templatevarloader.get_template_vars(loader_config)

        assert result == {"key1": "value2"}

    def test_load_invalid_json_file_raises_exception(self, text_files):
        json_path = text_files({"foobar.json": "{something wrong}"})
        loader_config = {"json_templatevarloader": {"template_var_paths": [json_path]}}

        with pytest.raises(exceptions.LoaderConfigError):
            json_templatevarloader.get_template_vars(loader_config)

    def test_load_non_existent_json_file_raises_exception(self):
        loader_config = {"json_templatevarloader": {"template_var_paths": ["abcd"]}}

        with pytest.raises(exceptions.LoaderConfigError):
            json_templatevarloader.get_template_vars(loader_config)

    def test_no_template_var_path_provided_returns_empty_dict(self):
        loader_config = {"json_templatevarloader": {"template_var_paths": []}}

        result = json_templatevarloader.get_template_vars(loader_config)

        assert result == {}
