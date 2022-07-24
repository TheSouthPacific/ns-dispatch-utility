from unittest import mock

import nationstates
import pytest

from nsdu import dispatch_api
from nsdu import exceptions


class TestRaiseNsduException:
    def test_unknown_dispatch_raises_specific_nsdu_exception(self):
        exception = nationstates.exceptions.APIUsageError("Unknown dispatch.")
        with pytest.raises(exceptions.UnknownDispatchError):
            dispatch_api.raise_nsdu_exception(exception)

    def test_not_owner_dispatch_raises_specific_nsdu_exception(self):
        exception = nationstates.exceptions.APIUsageError(
            "You are not the author of this dispatch."
        )
        with pytest.raises(exceptions.NotOwnerDispatchError):
            dispatch_api.raise_nsdu_exception(exception)

    def test_forbidden_raises_specific_nsdu_exception(self):
        exception = nationstates.exceptions.Forbidden
        with pytest.raises(exceptions.NationLoginError):
            dispatch_api.raise_nsdu_exception(exception)

    def test_other_exception_raises_general_api_error_nsdu_exception(self):
        exception = nationstates.exceptions.APIUsageError
        with pytest.raises(exceptions.DispatchApiError):
            dispatch_api.raise_nsdu_exception(exception)


class TestLoginApi:
    def test_get_autologin_code_from_correct_password_returns_autologin_code(self):
        response = {"headers": {"X-Autologin": "123456"}}
        ns_api = mock.create_autospec(nationstates.Nationstates)
        ns_api.nation.return_value = mock.Mock(
            get_shards=mock.Mock(return_value=response)
        )
        api = dispatch_api.LoginApi("")
        api.orig_api = ns_api

        autologin = api.get_autologin_code("my_nation", password="hunterprime123")

        assert autologin == "123456"

    def test_get_autologin_code_from_incorrect_password_raises_exception(self):
        ns_api = mock.create_autospec(nationstates.Nationstates)
        ns_api.nation.return_value = mock.Mock(
            get_shards=mock.Mock(side_effect=nationstates.exceptions.Forbidden)
        )
        api = dispatch_api.LoginApi("")
        api.orig_api = ns_api

        with pytest.raises(exceptions.NationLoginError):
            api.get_autologin_code("my_nation", "something wrong")

    def test_verify_correct_autologin_code_returns_true(self):
        ns_api = mock.create_autospec(nationstates.Nationstates)
        api = dispatch_api.LoginApi("")
        api.orig_api = ns_api

        assert api.verify_autologin_code("my_nation", "123456")

    def test_verify_incorrect_autologin_code_returns_false(self):
        ns_api = mock.create_autospec(nationstates.Nationstates)
        ns_api.nation.return_value = mock.Mock(
            get_shards=mock.Mock(side_effect=nationstates.exceptions.Forbidden)
        )
        api = dispatch_api.LoginApi("")
        api.orig_api = ns_api

        assert not api.verify_autologin_code("my_nation", "123456")


class TestDispatchApi:
    def test_create_dispatch(self):
        resp = 'New factbook posted! <a href="/nation=test/detail=factbook/id=1234567">View Your Factbook</a>'
        api = dispatch_api.DispatchApi("")
        create_dispatch = mock.Mock(return_value={"success": resp})
        api.owner_nation = mock.Mock(create_dispatch=create_dispatch)

        r = api.create_dispatch(
            title="test", text="hello world —", category="1", subcategory="100"
        )

        assert r == "1234567"
        create_dispatch.assert_called_with(
            title="test", text=b"hello world &#8212;", category="1", subcategory="100"
        )

    def test_edit_dispatch(self):
        resp = 'New factbook edited! <a href="/nation=test/detail=factbook/id=1234567">View Your Factbook</a>'
        api = dispatch_api.DispatchApi("")
        edit_dispatch = mock.Mock(return_value={"success": resp})
        api.owner_nation = mock.Mock(edit_dispatch=edit_dispatch)

        api.edit_dispatch(
            dispatch_id="1234567",
            title="test",
            text="hello world —",
            category="1",
            subcategory="100",
        )

        edit_dispatch.assert_called_with(
            dispatch_id="1234567",
            title="test",
            text=b"hello world &#8212;",
            category="1",
            subcategory="100",
        )

    def test_remove_dispatch(self):
        resp = 'Remove dispatch "test."'
        api = dispatch_api.DispatchApi("")
        api.owner_nation = mock.Mock(
            remove_dispatch=mock.Mock(return_value={"success": resp})
        )

        api.remove_dispatch(dispatch_id="1234567")

        assert True
