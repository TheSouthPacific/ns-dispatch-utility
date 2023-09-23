from unittest import mock
from unittest.mock import Mock

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


class TestCredCliParser:
    @pytest.fixture
    def parser(self):
        feature = mock.create_autospec(cred.CredFeature)
        return cred.CredCliParser(feature)

    @pytest.mark.parametrize(
        "args,expected",
        [
            [["nat1", "pass1", "nat2", "pass2"], {"nat1": "pass1", "nat2": "pass2"}],
            [[], {}],
        ],
    )
    def test_parse_add_password_creds_with_valid_args_uses_args(
        self, parser, args, expected
    ):
        parser.feature.add_password_creds = Mock()

        cli_args = Mock(add_password=args)
        parser.parse_add_password_creds(cli_args)

        parser.feature.add_password_creds.assert_called_with(expected)

    def test_parse_add_password_creds_with_missing_arg_raises_exception(self, parser):
        cli_args = Mock(add_password=["nat"])

        with pytest.raises(exceptions.UserError):
            parser.parse_add_password_creds(cli_args)

    @pytest.mark.parametrize(
        "args,expected",
        [
            [["nat1", "code1", "nat2", "code2"], {"nat1": "code1", "nat2": "code2"}],
            [[], {}],
        ],
    )
    def test_parse_add_autologin_creds_with_valid_args_uses_args(
        self, parser, args, expected
    ):
        parser.feature.add_autologin_creds = Mock()

        cli_args = Mock(add=args)
        parser.parse_add_autologin_creds(cli_args)

        parser.feature.add_autologin_creds.assert_called_with(expected)

    def test_parse_add_autologin_creds_with_missing_arg_raises_exception(self, parser):
        cli_args = Mock(add=["nat"])

        with pytest.raises(exceptions.UserError):
            parser.parse_add_autologin_creds(cli_args)

    @pytest.mark.parametrize(
        "args",
        [["nat1", "nat2"], []],
    )
    def test_parse_remove_creds_uses_input(self, parser, args):
        parser.feature.remove_creds = Mock()

        cli_args = Mock(remove=args)
        parser.parse_remove_creds(cli_args)

        parser.feature.remove_creds.assert_called_with(args)
