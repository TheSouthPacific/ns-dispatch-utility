from unittest import mock
from unittest.mock import Mock

import nationstates
import pytest
from nationstates import exceptions as ns_exceptions

from nsdu import ns_api


def test_convert_to_html_entities_returns_text_with_html_entities():
    result = ns_api.convert_to_html_entities("—")

    assert result == b"&#8212;"


class TestParseRespForNewDispatchId:
    def test_with_dispatch_id_exists_returns_dispatch_id(self):
        resp_text = (
            "New factbook posted!"
            '<a href="/nation=test/detail=factbook/id=123456">View Your Factbook</a>'
        )
        result = ns_api.parse_resp_for_new_dispatch_id(resp_text)

        assert result == "123456"

    def test_with_dispatch_id_not_exist_raises_exception(self):
        with pytest.raises(ns_api.DispatchApiError):
            ns_api.parse_resp_for_new_dispatch_id("")


def mock_orig_api(
    return_value: dict | None = None, side_effect: Exception | None = None
) -> nationstates.Nationstates:
    original_api = mock.create_autospec(nationstates.Nationstates)
    original_api.nation.return_value = Mock(
        get_shards=Mock(return_value=return_value, side_effect=side_effect)
    )
    return original_api


class TestAuthApi:
    @pytest.fixture
    def auth_api(self):
        def create_auth_api(
            return_value: dict | None = None, side_effect: Exception | None = None
        ):
            api = ns_api.AuthApi("")
            api.original_api = mock_orig_api(return_value, side_effect)
            return api

        return create_auth_api

    def test_get_autologin_code_with_correct_password_returns_autologin_code(
        self, auth_api
    ):
        resp_headers = {"headers": {"X-Autologin": "123456"}}
        api = auth_api(resp_headers)

        autologin = api.get_autologin_code("nat", password="1234")

        assert autologin == "123456"

    def test_get_autologin_code_with_wrong_password_raises_exception(self, auth_api):
        api = auth_api(side_effect=ns_exceptions.Forbidden)

        with pytest.raises(ns_api.AuthApiError):
            api.get_autologin_code("", "")

    def test_verify_correct_autologin_code_returns_true(self, auth_api):
        api = auth_api()

        result = api.verify_autologin_code("nat", "12345678")

        assert result

    def test_verify_wrong_autologin_code_returns_false(self, auth_api):
        api = auth_api(side_effect=ns_exceptions.Forbidden)

        result = api.verify_autologin_code("nat", "12345678")

        assert not result


class TestDispatchApi:
    def test_create_dispatch_calls_original_api_and_returns_new_dispatch_id(self):
        resp = (
            "New factbook posted!"
            '<a href="/nation=test/detail=factbook/id=1234">View Your Factbook</a>'
        )
        create_dispatch = Mock(return_value={"success": resp})
        api = ns_api.DispatchApi("")
        api.nation = Mock(create_dispatch=create_dispatch)

        result = api.create_dispatch(
            title="t", text="te", category="1", subcategory="100"
        )

        assert result == "1234"
        create_dispatch.assert_called_with(
            title="t", text=b"te", category="1", subcategory="100"
        )

    def test_edit_dispatch_calls_original_api(self):
        resp = (
            "New factbook posted!"
            '<a href="/nation=test/detail=factbook/id=1234567">View Your Factbook</a>'
        )
        edit_dispatch = Mock(return_value={"success": resp})
        api = ns_api.DispatchApi("")
        api.nation = Mock(edit_dispatch=edit_dispatch)

        api.edit_dispatch(
            dispatch_id="1234",
            title="t",
            text="te",
            category="1",
            subcategory="100",
        )

        edit_dispatch.assert_called_with(
            dispatch_id="1234",
            title="t",
            text=b"te",
            category="1",
            subcategory="100",
        )

    def test_remove_dispatch_calls_original_api(self):
        resp = 'Remove dispatch "test".'
        api = ns_api.DispatchApi("")
        remove_dispatch = Mock(return_value={"success": resp})
        api.nation = Mock(remove_dispatch=remove_dispatch)

        api.delete_dispatch(dispatch_id="1234")

        remove_dispatch.assert_called_with(dispatch_id="1234")
