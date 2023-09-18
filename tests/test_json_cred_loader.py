import json
from unittest import mock

import pytest

from nsdu import loader_api
from nsdu.loaders import json_cred_loader


@pytest.fixture
def creds(json_files):
    return json_files({"cred.json": {"nat1": "p1", "nat2": "p2"}})


class TestJSONLoader:
    def test_get_creds(self, creds):
        config = {"json_cred_loader": {"cred_path": creds}}
        loader = json_cred_loader.init_cred_loader(config)

        result = json_cred_loader.get_cred(loader, "nat1")
        json_cred_loader.cleanup_cred_loader(loader)

        assert result == "p1"

    def test_add_cred_with_existing_file(self, creds):
        config = {"json_cred_loader": {"cred_path": creds}}
        loader = json_cred_loader.init_cred_loader(config)

        json_cred_loader.add_cred(loader, "nat3", "p3")
        json_cred_loader.cleanup_cred_loader(loader)

        with open(creds) as f:
            result = json.load(f)
        assert result["nat3"] == "p3"

    def test_add_cred_with_cred_path_and_non_existing_file(self, tmp_path):
        cred_path = tmp_path / "id_store.json"
        config = {"json_cred_loader": {"cred_path": cred_path}}
        loader = json_cred_loader.init_cred_loader(config)

        json_cred_loader.add_cred(loader, "nat1", "p1")
        json_cred_loader.cleanup_cred_loader(loader)

        with open(cred_path) as f:
            result = json.load(f)
        assert result["nat1"] == "p1"

    def test_add_cred_with_no_cred_path_and_non_existing_file(self, tmp_path):
        with mock.patch("nsdu.info.DATA_DIR", tmp_path):
            loader = json_cred_loader.init_cred_loader({})

            json_cred_loader.add_cred(loader, "nat1", "p1")
            json_cred_loader.cleanup_cred_loader(loader)

        json_path = tmp_path / json_cred_loader.CRED_FILENAME
        with open(json_path) as f:
            result = json.load(f)
        assert result["nat1"] == "p1"

    def test_remove_cred(self, creds):
        config = {"json_cred_loader": {"cred_path": creds}}
        loader = json_cred_loader.init_cred_loader(config)

        json_cred_loader.remove_cred(loader, "nat2")
        json_cred_loader.cleanup_cred_loader(loader)

        with open(creds) as f:
            result = json.load(f)
        assert "nat2" not in result

    def test_remove_non_existent_cred(self, creds):
        config = {"json_cred_loader": {"cred_path": creds}}
        loader = json_cred_loader.init_cred_loader(config)

        with pytest.raises(loader_api.CredNotFound):
            json_cred_loader.remove_cred(loader, "a")
