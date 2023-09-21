from unittest import mock

import pytest

from nsdu import cred, exceptions, loader_managers, ns_api


class TestNsduCred:
    @pytest.fixture
    def feature(self):
        cred_loader_manager = mock.create_autospec(loader_managers.CredLoaderManager)
        auth_api = mock.create_autospec(ns_api.AuthApi)
        return cred.CredFeature(cred_loader_manager, auth_api)

    def test_add_correct_password_cred_calls_cred_loader_with_autologin_code(
        self, feature
    ):
        feature.auth_api.get_autologin_code.return_value = "1234"

        feature.add_password_cred("nat", "12345678")
        feature.cleanup()

        feature.cred_loader_manager.add_cred.assert_called_with("nat", "1234")

    def test_add_wrong_password_raises_exception(self, feature):
        feature.auth_api.get_autologin_code.side_effect = ns_api.AuthApiError

        with pytest.raises(exceptions.UserError):
            feature.add_password_cred("nation1", "password")

    def test_add_correct_autologin_cred_calls_cred_loader_with_autologin_code(
        self, feature
    ):
        feature.auth_api.verify_autologin_code.return_value = True

        feature.add_autologin_cred("nat", "1234")
        feature.cleanup()

        feature.cred_loader_manager.add_cred.assert_called_with("nat", "1234")

    def test_add_wrong_autologin_code_raises_exception(self, feature):
        feature.auth_api.verify_autologin_code.return_value = False

        with pytest.raises(exceptions.UserError):
            feature.add_autologin_cred("nat", "")

    def test_remove_nation_cred_calls_cred_loader(self, feature):
        feature.remove_cred("nat")
        feature.cleanup()

        feature.cred_loader_manager.remove_cred.assert_called_with("nat")
