import json
from unittest import mock

import pytest

from nsdu import loader_api
from nsdu.loaders import json_cred_loader as loader


@pytest.fixture
def cred_file(json_files):
    result = json_files({"cred.json": {"nat1": "a1", "nat2": "a2"}})
    return result.file_paths[0]


class TestJSONLoader:
    def test_get_existing_cred_returns_cred(self, cred_file):
        config = {"json_cred_loader": {"cred_path": cred_file}}
        obj = loader.init_cred_loader(config)

        result = loader.get_cred(obj, "nat1")
        loader.cleanup_cred_loader(obj)

        assert result == "a1"

    def test_get_non_existent_cred_raises_exception(self, cred_file):
        config = {"json_cred_loader": {"cred_path": cred_file}}
        obj = loader.init_cred_loader(config)

        with pytest.raises(loader_api.CredNotFound):
            loader.get_cred(obj, "n")

    def test_add_cred_with_existing_file_saves_to_file(self, cred_file):
        config = {"json_cred_loader": {"cred_path": cred_file}}
        obj = loader.init_cred_loader(config)

        loader.add_cred(obj, "nat3", "a3")
        loader.cleanup_cred_loader(obj)

        with open(cred_file) as f:
            result = json.load(f)
        assert result["nat3"] == "a3"

    def test_add_cred_with_non_existent_custom_file_creates_file(self, tmp_path):
        cred_file_path = tmp_path / "cred.json"
        config = {"json_cred_loader": {"cred_path": cred_file_path}}
        obj = loader.init_cred_loader(config)

        loader.add_cred(obj, "nat", "a")
        loader.cleanup_cred_loader(obj)

        with open(cred_file_path) as f:
            result = json.load(f)
        assert result["nat"] == "a"

    def test_add_cred_with_non_existent_default_file_creates_file(self, tmp_path):
        with mock.patch("nsdu.info.DATA_DIR", tmp_path):
            obj = loader.init_cred_loader({})

            loader.add_cred(obj, "nat", "a")
            loader.cleanup_cred_loader(obj)

        json_path = tmp_path / loader.CRED_FILENAME
        with open(json_path) as f:
            result = json.load(f)
        assert result["nat"] == "a"

    def test_remove_existing_cred_removes_cred_from_file(self, cred_file):
        config = {"json_cred_loader": {"cred_path": cred_file}}
        obj = loader.init_cred_loader(config)

        loader.remove_cred(obj, "nat2")
        loader.cleanup_cred_loader(obj)

        with open(cred_file) as f:
            result = json.load(f)
        assert "nat2" not in result

    def test_remove_non_existent_cred_raises_exception(self, cred_file):
        config = {"json_cred_loader": {"cred_path": cred_file}}
        obj = loader.init_cred_loader(config)

        with pytest.raises(loader_api.CredNotFound):
            loader.remove_cred(obj, "a")
