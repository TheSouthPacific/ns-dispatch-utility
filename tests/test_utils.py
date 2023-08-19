import pathlib

import pytest

from nsdu import info
from nsdu import exceptions
from nsdu import utils


class TestGetDispatchInfo:
    def test_get_dispatch_info(self):
        dispatch_config = {
            "nation1": {
                "dispatch1": {
                    "title": "Test Title 1",
                    "ns_id": "1234567",
                    "category": "1",
                    "subcategory": "100",
                },
                "dispatch2": {
                    "title": "Test Title 2",
                    "ns_id": "7654321",
                    "category": "2",
                    "subcategory": "120",
                },
            },
            "nation2": {
                "dispatch3": {
                    "title": "Test Title 1",
                    "ns_id": "1234567",
                    "category": "1",
                    "subcategory": "100",
                }
            },
        }

        r = utils.get_dispatch_info(dispatch_config)
        assert r == {
            "dispatch1": {
                "title": "Test Title 1",
                "ns_id": "1234567",
                "category": "1",
                "subcategory": "100",
                "owner_nation": "nation1",
            },
            "dispatch2": {
                "title": "Test Title 2",
                "ns_id": "7654321",
                "category": "2",
                "subcategory": "120",
                "owner_nation": "nation1",
            },
            "dispatch3": {
                "title": "Test Title 1",
                "ns_id": "1234567",
                "category": "1",
                "subcategory": "100",
                "owner_nation": "nation2",
            },
        }


class TestGetConfigFromEnv:
    def test_with_env(self, toml_files):
        config_path = toml_files({"test_config.toml": {"testkey": "testval"}})

        r = utils.get_config_from_env(config_path)

        assert r == {"testkey": "testval"}

    def test_with_env_and_non_existing_config_file(self):
        with pytest.raises(exceptions.ConfigError):
            utils.get_config_from_env(pathlib.Path("abcd.toml"))


class TestGetConfigFromDefault:
    def test_with_existing_config_file(self, toml_files):
        config_path = toml_files({info.CONFIG_NAME: {"testkey": "testval"}})

        r = utils.get_config_from_default(
            config_path.parent, info.DEFAULT_CONFIG_PATH, info.CONFIG_NAME
        )

        assert r == {"testkey": "testval"}

    def test_with_non_existing_config_file(self, tmp_path):
        with pytest.raises(exceptions.ConfigError):
            utils.get_config_from_default(
                tmp_path, info.DEFAULT_CONFIG_PATH, info.CONFIG_NAME
            )

        config_path = tmp_path / info.CONFIG_NAME
        assert config_path.exists()


class TestCanonicalNationName:
    def test_uppercase_letters_converts_to_all_lower_case_letters(self):
        assert utils.canonical_nation_name("Testopia opia") == "testopia opia"

    def test_underscores_removed(self):
        assert utils.canonical_nation_name("testopia_opia") == "testopia opia"
