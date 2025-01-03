import pytest

from nsdu import loader_api
from nsdu.loaders import json_template_var_loader


class TestGetTemplateVars:
    @pytest.mark.parametrize(
        "vars,expected",
        [
            [{"t.json": {"k": "v"}}, {"k": "v"}],
            [{"t1.json": {"k": "v1"}, "t2.json": {"k": "v2"}}, {"k": "v2"}],
        ],
    )
    def test_with_valid_json_files_returns_json_content_dict(
        self, json_files, vars, expected
    ):
        paths = json_files(vars).file_paths
        config = {"json_template_var_loader": {"template_var_paths": paths}}

        result = json_template_var_loader.get_template_vars(config)

        assert result == expected

    def test_with_no_json_file_returns_empty_dict(self):
        config = {"json_template_var_loader": {"template_var_paths": []}}

        result = json_template_var_loader.get_template_vars(config)

        assert result == {}

    def test_with_invalid_json_file_raises_exception(self, text_files):
        path = text_files({"t.json": "{"}).file_paths[0]
        config = {"json_template_var_loader": {"template_var_paths": [path]}}

        with pytest.raises(loader_api.LoaderError):
            json_template_var_loader.get_template_vars(config)

    def test_with_non_existent_file_raises_exception(self):
        config = {"json_template_var_loader": {"template_var_paths": ["a"]}}

        with pytest.raises(loader_api.LoaderError):
            json_template_var_loader.get_template_vars(config)
