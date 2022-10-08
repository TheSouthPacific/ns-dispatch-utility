from unittest import mock

import pytest

from nsdu import exceptions, ns_api
from nsdu import __main__


def get_dispatch_info(dispatch_config):
    """Return dispatch information for use as context in the template renderer.

    Args:
        dispatch_config (dict): Dispatch configuration.
        id_store (IDStore): Dispatch ID store.

    Returns:
        dict: Dispatch information.
    """

    dispatch_info = {}
    for nation, dispatches in dispatch_config.items():
        for name, config in dispatches.items():
            config["owner_nation"] = nation
            dispatch_info[name] = config

    return dispatch_info


class TestNsduCred:
    def test_add_correct_password_cred_calls_cred_loader_with_autologin_code(self):
        mock_cred_loader = mock.Mock(add_cred=mock.Mock())
        login_api = mock.create_autospec(ns_api.LoginApi)
        login_api.get_autologin_code.return_value = "123456"
        operations = __main__.CredOperations(mock_cred_loader, login_api)

        operations.add_password_cred("nation1", "password")
        operations.cleanup()

        mock_cred_loader.add_cred.assert_called_with("nation1", "123456")

    def test_add_incorrect_password_raises_exception(self):
        mock_cred_loader = mock.Mock(add_cred=mock.Mock())
        login_api = mock.create_autospec(ns_api.LoginApi)
        login_api.get_autologin_code.side_effect = exceptions.NationLoginError
        operations = __main__.CredOperations(mock_cred_loader, login_api)

        with pytest.raises(exceptions.CredOperationError):
            operations.add_password_cred("nation1", "password")

        operations.cleanup()

    def test_add_correct_autologin_cred_calls_cred_loader_with_autologin_code(self):
        mock_cred_loader = mock.Mock(add_cred=mock.Mock())
        login_api = mock.create_autospec(ns_api.LoginApi)
        login_api.verify_autologin_code.return_value = True
        operations = __main__.CredOperations(mock_cred_loader, login_api)

        operations.add_autologin_cred("nation1", "123456")
        operations.cleanup()

        mock_cred_loader.add_cred.assert_called_with("nation1", "123456")

    def test_add_incorrect_autologin_code_raises_exception(self):
        mock_cred_loader = mock.Mock(add_cred=mock.Mock())
        login_api = mock.create_autospec(ns_api.LoginApi)
        login_api.verify_autologin_code.return_value = False
        operations = __main__.CredOperations(mock_cred_loader, login_api)

        with pytest.raises(exceptions.CredOperationError):
            operations.add_autologin_cred("nation1", "123456")

        operations.cleanup()

    def test_remove_nation_cred_calls_cred_loader(self):
        mock_cred_loader = mock.Mock(remove_cred=mock.Mock())
        app = __main__.CredOperations(mock_cred_loader, mock.Mock())

        app.remove_cred("nation1")
        app.cleanup()

        mock_cred_loader.remove_cred.assert_called_with("nation1")


class TestNsduDispatch:
    def test_create_dispatch_calls_add_dispatch_id_on_loader(self):
        dispatch_loader_manager = mock.Mock()
        dispatch_updater = mock.Mock(create_dispatch=mock.Mock(return_value="12345"))
        dispatch_info = {
            "foo": {
                "action": "create",
                "title": "Test title",
                "category": "1",
                "subcategory": "100",
            }
        }
        app = __main__.DispatchOperations(
            dispatch_updater, dispatch_loader_manager, {}, dispatch_info, {}
        )

        app.update_a_dispatch("foo")

        dispatch_loader_manager.add_dispatch_id.assert_called_with("foo", "12345")

    def test_edit_dispatch_calls_dispatch_updater(self):
        dispatch_loader_manager = mock.Mock()
        dispatch_updater = mock.Mock()
        dispatch_info = {
            "foo": {
                "action": "edit",
                "ns_id": "12345",
                "title": "Test title",
                "category": "1",
                "subcategory": "100",
            }
        }
        app = __main__.DispatchOperations(
            dispatch_updater, dispatch_loader_manager, {}, dispatch_info, {}
        )

        app.update_a_dispatch("foo")

        dispatch_updater.edit_dispatch.assert_called_with(
            "foo", "12345", "Test title", "1", "100"
        )

    def test_remove_dispatch_calls_dispatch_updater(self):
        dispatch_loader_manager = mock.Mock()
        dispatch_updater = mock.Mock()
        dispatch_info = {
            "foo": {
                "action": "remove",
                "ns_id": "12345",
                "title": "Test title",
                "category": "1",
                "subcategory": "100",
            }
        }
        app = __main__.DispatchOperations(
            dispatch_updater, dispatch_loader_manager, {}, dispatch_info, {}
        )

        app.update_a_dispatch("foo")

        dispatch_updater.remove_dispatch.assert_called_with("12345")

    def test_update_a_dispatch_with_invalid_action(self):
        dispatch_loader_manager = mock.Mock()
        dispatch_updater = mock.Mock()
        dispatch_info = {
            "foo": {
                "action": "abcd",
                "ns_id": "12345",
                "title": "Test title",
                "category": "1",
                "subcategory": "100",
            }
        }
        app = __main__.DispatchOperations(
            dispatch_updater, dispatch_loader_manager, {}, dispatch_info, {}
        )

        with pytest.raises(exceptions.DispatchConfigError):
            app.update_a_dispatch("foo")

    def test_update_a_dispatch_with_no_exception_reports_success(self, caplog):
        dispatch_loader_manager = mock.Mock()
        dispatch_updater = mock.Mock()
        dispatch_info = {
            "foo": {
                "action": "edit",
                "ns_id": "12345",
                "title": "Test title",
                "category": "1",
                "subcategory": "100",
            }
        }
        app = __main__.DispatchOperations(
            dispatch_updater, dispatch_loader_manager, {}, dispatch_info, {}
        )

        app.update_a_dispatch("foo")

        result = dispatch_loader_manager.after_update.call_args[0][2]
        assert result == "success"

    @pytest.mark.parametrize(
        "api_exceptions,expected_result",
        [
            (exceptions.UnknownDispatchError, "unknown-dispatch-error"),
            (exceptions.NotOwnerDispatchError, "not-owner-dispatch-error"),
            (exceptions.NonexistentCategoryError("", ""), "invalid-category-options"),
        ],
    )
    def test_update_a_dispatch_with_exceptions_reports_failure(
        self, api_exceptions, expected_result, caplog
    ):
        dispatch_loader_manager = mock.Mock()
        dispatch_updater = mock.Mock(
            edit_dispatch=mock.Mock(side_effect=api_exceptions)
        )
        dispatch_info = {
            "foo": {
                "action": "edit",
                "ns_id": "12345",
                "title": "Test title",
                "category": "1",
                "subcategory": "100",
            }
        }
        app = __main__.DispatchOperations(
            dispatch_updater, dispatch_loader_manager, {}, dispatch_info, {}
        )

        app.update_a_dispatch("foo")

        result = dispatch_loader_manager.after_update.call_args[0][2]
        assert result == expected_result

    def test_update_existing_dispatches_calls_dispatch_updater(self):
        dispatch_loader_manager = mock.Mock()
        dispatch_updater = mock.Mock()
        dispatch_config = {
            "nation1": {
                "foo": {
                    "action": "create",
                    "title": "Test title 1",
                    "category": "1",
                    "subcategory": "100",
                }
            }
        }
        dispatch_info = get_dispatch_info(dispatch_config)
        creds = {"nation1": "abcd1234"}
        app = __main__.DispatchOperations(
            dispatch_updater,
            dispatch_loader_manager,
            dispatch_config,
            dispatch_info,
            creds,
        )

        app.update_dispatches([])

        dispatch_updater.create_dispatch.assert_called()

    def test_uppercase_owner_nation_name_canonicalized(self):
        dispatch_loader_manager = mock.Mock()
        dispatch_updater = mock.Mock()
        dispatch_config = {"Nation1": {}}
        dispatch_info = get_dispatch_info(dispatch_config)
        creds = {"nation1": "abcd1234"}
        app = __main__.DispatchOperations(
            dispatch_updater,
            dispatch_loader_manager,
            dispatch_config,
            dispatch_info,
            creds,
        )

        app.update_dispatches([])

        dispatch_updater.set_owner_nation.assert_called_with("nation1", "abcd1234")

    def test_update_some_existing_dispatches_calls_dispatch_updater(self):
        dispatch_loader_manager = mock.Mock()
        dispatch_updater = mock.Mock()
        dispatch_config = {
            "nation1": {
                "foo": {
                    "action": "create",
                    "title": "Test title 1",
                    "category": "1",
                    "subcategory": "100",
                }
            }
        }
        dispatch_info = get_dispatch_info(dispatch_config)
        creds = {"nation1": "abcd1234"}
        app = __main__.DispatchOperations(
            dispatch_updater,
            dispatch_loader_manager,
            dispatch_config,
            dispatch_info,
            creds,
        )

        app.update_dispatches(["foo"])

        dispatch_updater.create_dispatch.assert_called()

    def test_update_non_existent_dispatches_logs_error(self, caplog):
        dispatch_loader_manager = mock.Mock()
        dispatch_updater = mock.Mock()
        dispatch_config = {
            "nation1": {
                "foo": {
                    "action": "create",
                    "ns_id": "12345",
                    "title": "Test title 1",
                    "category": "1",
                    "subcategory": "100",
                }
            }
        }
        dispatch_info = get_dispatch_info(dispatch_config)
        creds = {"nation1": "abcd1234"}
        app = __main__.DispatchOperations(
            dispatch_updater,
            dispatch_loader_manager,
            dispatch_config,
            dispatch_info,
            creds,
        )

        app.update_dispatches(["voo"])

        assert caplog.records[-1].levelname == "ERROR"
