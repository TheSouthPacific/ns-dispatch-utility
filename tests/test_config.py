import pathlib
import pytest

from nsdu import config, exceptions, info


class TestGetConfigFromEnv:
    def test_with_env(self, toml_files):
        config_path = toml_files({"config.toml": {"a": "b"}})

        r = config.get_config_from_env(config_path)

        assert r == {"a": "b"}

    def test_with_env_and_non_existing_config_file(self):
        with pytest.raises(exceptions.ConfigError):
            config.get_config_from_env(pathlib.Path("abcd.toml"))


class TestGetConfigFromDefault:
    def test_with_existing_config_file(self, toml_files):
        config_path = toml_files({info.CONFIG_NAME: {"a": "b"}})

        r = config.get_config_from_default(
            config_path.parent, info.DEFAULT_CONFIG_PATH, info.CONFIG_NAME
        )

        assert r == {"a": "b"}

    def test_with_non_existing_config_file(self, tmp_path):
        with pytest.raises(exceptions.ConfigError):
            config.get_config_from_default(
                tmp_path, info.DEFAULT_CONFIG_PATH, info.CONFIG_NAME
            )

        config_path = tmp_path / info.CONFIG_NAME
        assert config_path.exists()
