from unittest import mock
from unittest.mock import Mock

import pytest

from nsdu import updater_api
from nsdu.ns_api import DispatchApi


class TestGetCategoryNumber:
    @pytest.mark.parametrize(
        "category,subcategory,expected",
        [
            ["factbook", "overview", ("1", "100")],
            ["Factbook", "Overview", ("1", "100")],
            ["1", "100", ("1", "100")],
        ],
    )
    def test_with_valid_names_returns_numbers(self, category, subcategory, expected):
        result = updater_api.get_category_numbers(category, subcategory)

        assert result == expected

    @pytest.mark.parametrize(
        "category,subcategory",
        [
            ["factbook", "a"],
            ["a", "overview"],
            ["a", "a"],
        ],
    )
    def test_with_invalid_names_raises_exception(self, category, subcategory):
        with pytest.raises(updater_api.DispatchMetadataError):
            updater_api.get_category_numbers(category, subcategory)


class TestDispatchUpdater:
    @pytest.fixture
    def updater(self):
        updater = updater_api.DispatchUpdater(
            user_agent="",
            template_filter_paths=[],
            simple_fmts_config=None,
            complex_fmts_source_path=None,
            template_load_func=Mock(return_value="tp"),
            template_vars={},
        )
        updater.dispatch_api = mock.create_autospec(DispatchApi)
        return updater

    def test_set_nation_calls_dispatch_api(self, updater):
        updater.set_nation("nat", "1234")

        updater.dispatch_api.set_nation.assert_called_with("nat", "1234")

    def test_create_dispatch_calls_dispatch_api(self, updater):
        updater.dispatch_api.create_dispatch = Mock(return_value="1234")

        result = updater.create_dispatch("n", "t", "meta", "gameplay")

        updater.dispatch_api.create_dispatch.assert_called_with(
            title="t", text="tp", category="8", subcategory="835"
        )
        assert result == "1234"

    def test_edit_dispatch_calls_dispatch_api(self, updater):
        updater.edit_dispatch("n", "1234", "t", "meta", "gameplay")

        updater.dispatch_api.edit_dispatch.assert_called_with(
            dispatch_id="1234",
            title="t",
            text="tp",
            category="8",
            subcategory="835",
        )

    def test_remove_dispatch_calls_dispatch_api(self, updater):
        updater.delete_dispatch("1234")

        updater.dispatch_api.delete_dispatch.assert_called_with("1234")
