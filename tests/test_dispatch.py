from datetime import datetime, timezone
from unittest import mock
from unittest.mock import Mock, call

import freezegun
import pytest

from nsdu import dispatch, loader_api, loader_managers, ns_api, updater_api
from nsdu.loader_api import DispatchMetadata, DispatchOp, DispatchOpResult


def test_group_dispatches_by_owner_nation_returns_grouped_metadata_objs():
    dispatches_metadata = {
        "n1": DispatchMetadata(
            None, DispatchOp.CREATE, "nat1", "t1", "meta", "gameplay"
        ),
        "n2": DispatchMetadata(
            None, DispatchOp.CREATE, "nat1", "t2", "meta", "gameplay"
        ),
        "n3": DispatchMetadata(
            None, DispatchOp.CREATE, "nat2", "t3", "meta", "gameplay"
        ),
    }

    result = dispatch.group_dispatches_by_owner_nation(dispatches_metadata)

    expected = {
        "nat1": {"n1": dispatches_metadata["n1"], "n2": dispatches_metadata["n2"]},
        "nat2": {"n3": dispatches_metadata["n3"]},
    }
    assert result == expected


class TestGetDispatchesToExecute:
    @pytest.mark.parametrize(
        "names,expected",
        [
            [
                ["n1"],
                {
                    "n1": DispatchMetadata(
                        None, DispatchOp.CREATE, "nat", "t1", "meta", "gameplay"
                    ),
                },
            ],
            [
                [],
                {
                    "n1": DispatchMetadata(
                        None, DispatchOp.CREATE, "nat", "t1", "meta", "gameplay"
                    ),
                    "n2": DispatchMetadata(
                        None, DispatchOp.CREATE, "nat", "t2", "meta", "gameplay"
                    ),
                },
            ],
        ],
    )
    def test_with_existing_names_returns_dispatch_metadata_objs(self, names, expected):
        dispatches_metadata = {
            "n1": DispatchMetadata(
                None, DispatchOp.CREATE, "nat", "t1", "meta", "gameplay"
            ),
            "n2": DispatchMetadata(
                None, DispatchOp.CREATE, "nat", "t2", "meta", "gameplay"
            ),
        }

        result = dispatch.get_dispatches_to_execute(dispatches_metadata, names)

        assert result == expected

    def test_with_non_existent_name_skips_name(self):
        dispatches_metadata = {
            "n1": DispatchMetadata(
                None, DispatchOp.CREATE, "nat", "t1", "meta", "gameplay"
            ),
        }
        names = ["n1", "n"]

        result = dispatch.get_dispatches_to_execute(dispatches_metadata, names)

        assert result == {"n1": dispatches_metadata["n1"]}

    def test_with_non_existent_name_logs_error(self, caplog):
        dispatches_metadata = {}
        names = ["n"]

        dispatch.get_dispatches_to_execute(dispatches_metadata, names)

        assert caplog.records[-1].levelname == "ERROR"


class TestNsduDispatch:
    @pytest.fixture
    def feature(self):
        dispatch_loader_manager = mock.create_autospec(
            loader_managers.DispatchLoaderManager
        )
        cred_loader_manager = mock.create_autospec(loader_managers.CredLoaderManager)
        dispatch_updater = mock.create_autospec(updater_api.DispatchUpdater)

        return dispatch.DispatchFeature(
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

    def test_execute_dispatch_ops_with_owner_nations_logins_to_those_nations(
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

        feature.execute_dispatch_operations([])

        feature.dispatch_updater.set_nation.assert_has_calls(
            [call("nat1", "1234"), call("nat2", "1234")]
        )

    def test_execute_dispatch_ops_with_non_existent_cred_logs_error(
        self, caplog, feature
    ):
        feature.dispatches_metadata = {
            "n": DispatchMetadata(
                None, DispatchOp.CREATE, "nat", "t1", "meta", "gameplay"
            )
        }
        feature.cred_loader_manager.get_cred.side_effect = loader_api.CredNotFound

        feature.execute_dispatch_operations(["n"])

        assert caplog.records[-1].levelname == "ERROR"

    def test_execute_dispatch_ops_with_auth_error_logs_error(self, caplog, feature):
        feature.dispatches_metadata = {
            "n": DispatchMetadata(
                None, DispatchOp.CREATE, "nat", "t1", "meta", "gameplay"
            )
        }
        feature.dispatch_updater.set_nation.side_effect = ns_api.AuthApiError

        feature.execute_dispatch_operations(["n"])

        assert caplog.records[-1].levelname == "ERROR"

    def test_execute_dispatch_ops_with_non_existent_name_logs_error(
        self, caplog, feature
    ):
        feature.execute_dispatch_operations(["n"])

        assert caplog.records[-1].levelname == "ERROR"
