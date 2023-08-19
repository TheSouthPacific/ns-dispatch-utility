from unittest import mock
import json

import pytest

from nsdu import exceptions
from nsdu.loaders import json_credloader


@pytest.fixture
def creds(json_files):
    return json_files(
        {"cred.json": {"nation1": "hunterprime1", "nation2": "hunterprime2"}}
    )


class TestJSONLoader:
    def test_get_creds(self, creds):
        config = {"json_credloader": {"cred_path": creds}}
        loader = json_credloader.init_cred_loader(config)

        r = json_credloader.get_creds(loader)

        json_credloader.cleanup_cred_loader(loader)

        assert r["nation2"] == "hunterprime2"

    def test_add_cred_with_existing_file(self, creds):
        config = {"json_credloader": {"cred_path": creds}}
        loader = json_credloader.init_cred_loader(config)

        json_credloader.add_cred(loader, "nation3", "hunterprime3")

        json_credloader.cleanup_cred_loader(loader)

        with open(creds) as f:
            r = json.load(f)

        assert r["nation3"] == "hunterprime3"

    def test_add_cred_with_cred_path_and_non_existing_file(self, tmp_path):
        cred_path = tmp_path / "id_store.json"
        config = {"json_credloader": {"cred_path": cred_path}}
        loader = json_credloader.init_cred_loader(config)

        json_credloader.add_cred(loader, "nation1", "hunterprime1")

        json_credloader.cleanup_cred_loader(loader)

        with open(cred_path) as f:
            r = json.load(f)

        assert r["nation1"] == "hunterprime1"

    def test_add_cred_with_no_cred_path_and_non_existing_file(self, tmp_path):
        with mock.patch("nsdu.info.DATA_DIR", tmp_path):
            loader = json_credloader.init_cred_loader({})

            json_credloader.add_cred(loader, "nation1", "hunterprime1")

            json_credloader.cleanup_cred_loader(loader)

        json_path = tmp_path / json_credloader.CRED_FILENAME
        with open(json_path) as f:
            r = json.load(f)

        assert r["nation1"] == "hunterprime1"

    def test_remove_cred(self, creds):
        config = {"json_credloader": {"cred_path": creds}}
        loader = json_credloader.init_cred_loader(config)

        json_credloader.remove_cred(loader, "nation2")

        json_credloader.cleanup_cred_loader(loader)

        with open(creds) as f:
            r = json.load(f)

        assert "nation2" not in r

    def test_remove_non_existent_cred(self, creds):
        config = {"json_credloader": {"cred_path": creds}}
        loader = json_credloader.init_cred_loader(config)

        with pytest.raises(exceptions.CredNotFound):
            json_credloader.remove_cred(loader, "garbage")
