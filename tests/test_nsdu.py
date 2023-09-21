from datetime import datetime, timezone
from unittest import mock
from unittest.mock import Mock, call

import freezegun
import pytest

from nsdu import __main__, loader_managers, ns_api, updater_api
from nsdu.__main__ import UserError
from nsdu.loader_api import DispatchMetadata, DispatchOp, DispatchOpResult


class TestNsduCred:
    @pytest.fixture
    def feature(self):
        cred_loader_manager = mock.create_autospec(loader_managers.CredLoaderManager)
        auth_api = mock.create_autospec(ns_api.AuthApi)
        return __main__.CredFeature(cred_loader_manager, auth_api)

    def test_add_correct_password_cred_calls_cred_loader_with_autologin_code(
        self, feature
    ):
        feature.auth_api.get_autologin_code.return_value = "1234"

        feature.add_password_cred("nat", "12345678")
        feature.cleanup()

        feature.cred_loader_manager.add_cred.assert_called_with("nat", "1234")

    def test_add_wrong_password_raises_exception(self, feature):
        feature.auth_api.get_autologin_code.side_effect = ns_api.AuthApiError

        with pytest.raises(UserError):
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

        with pytest.raises(UserError):
            feature.add_autologin_cred("nat", "")

    def test_remove_nation_cred_calls_cred_loader(self, feature):
        feature.remove_cred("nat")
        feature.cleanup()

        feature.cred_loader_manager.remove_cred.assert_called_with("nat")


class TestNsduDispatch:
    @pytest.fixture
    def feature(self):
        dispatch_loader_manager = mock.create_autospec(
            loader_managers.DispatchLoaderManager
        )
        cred_loader_manager = mock.create_autospec(loader_managers.CredLoaderManager)
        dispatch_updater = mock.create_autospec(updater_api.DispatchUpdater)

        return __main__.DispatchFeature(
            dispatch_updater,
            dispatch_loader_manager,
            cred_loader_manager,
            {},
        )

    def test_create_dispatch_adds_new_dispatch_id_to_loader(self, feature):
        feature.dispatches_metadata = {
            "n": DispatchMetadata(
                None, DispatchOp.CREATE, "nat", "t", "meta", "gameplay"
            )
        }
        feature.dispatch_updater.create_dispatch.return_value = "1234"

        feature.execute_dispatch_operation("n")

        feature.dispatch_loader_manager.add_dispatch_id.assert_called_with("n", "1234")

    def test_edit_dispatch_calls_dispatch_updater(self, feature):
        feature.dispatches_metadata = {
            "n": DispatchMetadata("1", DispatchOp.EDIT, "nat", "t", "meta", "gameplay")
        }

        feature.execute_dispatch_operation("n")

        feature.dispatch_updater.edit_dispatch.assert_called()

    def test_remove_dispatch_calls_dispatch_updater(self, feature):
        feature.dispatches_metadata = {
            "n": DispatchMetadata(
                "1", DispatchOp.DELETE, "nat", "t", "meta", "gameplay"
            )
        }

        feature.execute_dispatch_operation("n")

        feature.dispatch_updater.delete_dispatch.assert_called()

    @pytest.mark.parametrize("operation", [DispatchOp.EDIT, DispatchOp.DELETE])
    def test_execute_dispatch_op_that_require_id_with_no_id_raises_exception(
        self, feature, operation
    ):
        feature.dispatches_metadata = {
            "n": DispatchMetadata(None, operation, "nat", "t", "meta", "gameplay")
        }

        with pytest.raises(updater_api.DispatchMetadataError):
            feature.execute_dispatch_operation("n")

    @freezegun.freeze_time("2023-01-01")
    def test_execute_dispatch_op_with_no_exception_reports_success(self, feature):
        feature.dispatches_metadata = {
            "n": DispatchMetadata(
                None, DispatchOp.CREATE, "nat", "t", "meta", "gameplay"
            )
        }

        feature.execute_dispatch_operation("n")

        feature.dispatch_loader_manager.after_update.assert_called_with(
            "n",
            DispatchOp.CREATE,
            DispatchOpResult.SUCCESS,
            datetime(2023, 1, 1, tzinfo=timezone.utc),
        )

    @freezegun.freeze_time("2023-01-01")
    def test_execute_dispatch_op_with_api_exception_reports_failure(self, feature):
        feature.dispatches_metadata = {
            "n": DispatchMetadata(
                None, DispatchOp.CREATE, "nat", "t", "meta", "gameplay"
            )
        }
        feature.dispatch_updater.create_dispatch.side_effect = ns_api.DispatchApiError(
            "a"
        )

        feature.execute_dispatch_operation("n")

        feature.dispatch_loader_manager.after_update.assert_called_with(
            "n",
            DispatchOp.CREATE,
            DispatchOpResult.FAILURE,
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            "a",
        )

    def test_execute_dispatch_ops_with_names_uses_dispatches_with_those_names(
        self, feature
    ):
        feature.dispatches_metadata = {
            "n1": DispatchMetadata(
                None, DispatchOp.CREATE, "nat", "t1", "meta", "gameplay"
            ),
            "n2": DispatchMetadata(
                None, DispatchOp.CREATE, "nat", "t2", "meta", "gameplay"
            ),
        }
        feature.cred_loader_manager.get_cred.return_value = "1234"
        feature.execute_dispatch_operation = Mock()

        feature.execute_dispatch_operations(["n1"])

        feature.execute_dispatch_operation.assert_has_calls([call("n1")])

    def test_execute_dispatch_ops_with_no_name_uses_all_dispatches(self, feature):
        feature.dispatches_metadata = {
            "n1": DispatchMetadata(
                None, DispatchOp.CREATE, "nat", "t1", "meta", "gameplay"
            ),
            "n2": DispatchMetadata(
                None, DispatchOp.CREATE, "nat", "t2", "meta", "gameplay"
            ),
        }
        feature.cred_loader_manager.get_cred.return_value = "1234"
        feature.execute_dispatch_operation = Mock()

        feature.execute_dispatch_operations([])

        feature.execute_dispatch_operation.assert_has_calls([call("n1"), call("n2")])

    def test_execute_dispatch_ops_with_many_owner_nations_logins_to_those_nations(
        self, feature
    ):
        feature.dispatches_metadata = {
            "n1": DispatchMetadata(
                None, DispatchOp.CREATE, "nat1", "t1", "meta", "gameplay"
            ),
            "n2": DispatchMetadata(
                None, DispatchOp.CREATE, "nat2", "t2", "meta", "gameplay"
            ),
        }
        feature.cred_loader_manager.get_cred.return_value = "1234"
        feature.execute_dispatch_operation = Mock()

        feature.execute_dispatch_operations([])

        feature.dispatch_updater.set_nation.assert_has_calls(
            [call("nat1", "1234"), call("nat2", "1234")]
        )

    def test_execute_dispatch_ops_with_non_existent_name_logs_error(
        self, caplog, feature
    ):
        feature.execute_dispatch_operations(["n"])

        assert caplog.records[-1].levelname == "ERROR"
