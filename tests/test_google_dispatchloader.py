from datetime import datetime
from unittest import mock

import pytest
from googleapiclient.http import HttpError

from nsdu.loaders import google_dispatch_loader as loader


class TestGoogleSpreadsheetApiAdapter:
    def test_get_cell_data_of_a_range_returns_cell_data_of_one_range(self):
        resp = {
            "spreadsheetId": "1234abcd",
            "valueRanges": [
                {"range": "Foo!A1:F", "majorDimension": "ROWS", "values": [["hello"]]}
            ],
        }
        request = mock.Mock(execute=mock.Mock(return_value=resp))
        google_api = mock.Mock(batchGet=mock.Mock(return_value=request))
        api = loader.GoogleSpreadsheetApiAdapter(google_api)

        range = loader.SheetRange("1234abcd", "Foo!A1:F")

        result = api.get_cell_data(range)

        assert result == [["hello"]]

    def test_get_cell_data_of_many_ranges_returns_cell_data_of_many_ranges(self):
        resp = {
            "spreadsheetId": "1234abcd",
            "valueRanges": [
                {"range": "Foo!A1:F", "majorDimension": "ROWS", "values": [["hello"]]}
            ],
        }
        request = mock.Mock(execute=mock.Mock(return_value=resp))
        google_api = mock.Mock(batchGet=mock.Mock(return_value=request))
        api = loader.GoogleSpreadsheetApiAdapter(google_api)

        range = [loader.SheetRange("1234abcd", "Foo!A1:F")]

        result = api.get_cell_data(range)

        assert result == {range[0]: [["hello"]]}

    def test_get_cell_data_of_empty_range_returns_empty_list(self):
        resp = {
            "spreadsheetId": "1234abcd",
            "valueRanges": [{"range": "Foo!A1:F", "majorDimension": "ROWS"}],
        }
        request = mock.Mock(execute=mock.Mock(return_value=resp))
        google_api = mock.Mock(batchGet=mock.Mock(return_value=request))
        api = loader.GoogleSpreadsheetApiAdapter(google_api)

        range = loader.SheetRange("1234abcd", "Foo!A1:F")

        result = api.get_cell_data(range)

        assert not result

    def test_update_cell_data_of_many_ranges(self):
        google_api = mock.Mock()
        api = loader.GoogleSpreadsheetApiAdapter(google_api)

        new_cell_data = {loader.SheetRange("1234abcd", "Foo!A1:F"): [["hello"]]}

        api.update_cell_data(new_cell_data)

        expected_body = {
            "valueInputOption": "USER_ENTERED",
            "data": [
                {"range": "Foo!A1:F", "majorDimension": "ROWS", "values": [["hello"]]}
            ],
        }
        google_api.batchUpdate.assert_called_with(
            spreadsheetId="1234abcd", body=expected_body
        )


class TestResultReporter:
    def test_format_success_message_returns_formatted_messages(self):
        result_time = datetime.fromisoformat("2021-01-01T00:00:00")
        r = loader.ResultReporter.format_success_message("create", result_time)

        assert r == "Created on 2021/01/01 00:00:00 "

    def test_format_failure_message_returns_formatted_messages(self):
        result_time = datetime.fromisoformat("2021-01-01T00:00:00")
        r = loader.ResultReporter.format_failure_message(
            "create", "Some details", result_time
        )

        assert r == "Failed to create on 2021/01/01 00:00:00 \nError: Some details"

    def test_report_success_adds_success_report(self):
        reporter = loader.ResultReporter()

        reporter.report_success("foo", "create", datetime.now())

        assert reporter.results["foo"].action == "create"

    def test_report_success_uses_current_time_if_no_result_time_is_provided(self):
        reporter = loader.ResultReporter()

        reporter.report_success("foo", "create")

        assert isinstance(reporter.results["foo"].result_time, datetime)

    def test_report_failure_adds_failure_report(self):
        reporter = loader.ResultReporter()

        reporter.report_failure("foo", "create", "Some details", datetime.now())
        r = reporter.results["foo"]

        assert r.action == "create" and r.details == "Some details"

    def test_report_failure_uses_current_time_if_no_result_time_is_provided(self):
        reporter = loader.ResultReporter()

        reporter.report_failure("foo", "create", "Some details")
        r = reporter.results["foo"]

        assert r.action == "create" and r.details == "Some details"
        assert isinstance(reporter.results["foo"].result_time, datetime)

    def test_get_message_of_successful_result_returns_formatted_message(self):
        reporter = loader.ResultReporter()
        result_time = datetime.fromisoformat("2021-01-01T00:00:00")
        reporter.report_success("foo", "create", result_time)

        r1 = reporter.get_message("foo")

        assert "Created on 2021/01/01 00:00:00 " in r1.text
        assert not r1.is_failure

    def test_get_message_of_failure_result_returns_formatted_message(self):
        reporter = loader.ResultReporter()
        result_time = datetime.fromisoformat("2021-01-01T00:00:00")
        reporter.report_failure("foo", "edit", "Some details", result_time)

        r1 = reporter.get_message("foo")

        assert r1.text == "Failed to edit on 2021/01/01 00:00:00 \nError: Some details"
        assert r1.is_failure


class TestCategorySetups:
    def test_get_category_subcategory_names_returns_name(self):
        rows = [[1, "Meta", "Gameplay"]]
        category_setups = loader.CategorySetups.load_from_rows(rows)

        category_name, subcategory_name = category_setups.get_category_subcategory_name(
            1
        )
        assert category_name == "Meta" and subcategory_name == "Gameplay"

    def test_get_category_subcategory_names_returns_name_of_last_idential_id(self):
        rows = [[1, "Meta", "Gameplay"], [1, "Meta", "Reference"]]
        category_setups = loader.CategorySetups.load_from_rows(rows)

        category_name, subcategory_name = category_setups.get_category_subcategory_name(
            1
        )
        assert category_name == "Meta" and subcategory_name == "Reference"

    def test_get_category_subcategory_non_existent_names_raises_exception(self):
        rows = [[1, "Meta", "Gameplay"]]
        category_setups = loader.CategorySetups.load_from_rows(rows)

        with pytest.raises(KeyError):
            category_setups.get_category_subcategory_name(100)


class TestOwnerNations:
    def test_get_owner_nation_name_returns_name(self):
        rows = [[1, "Testopia", "foofoo,barbar,coocoo"], [2, "Monopia", "zoo"]]
        owner_nations = loader.OwnerNations.load_from_rows(rows)

        assert owner_nations.get_owner_nation_name(1, "barbar") == "Testopia"

    def test_get_non_existent_owner_nation_name_raises_exception(self):
        rows = [[1, "Testopia", "foofoo,barbar,coocoo"], [2, "Monopia", "zoo"]]
        owner_nations = loader.OwnerNations.load_from_rows(rows)

        with pytest.raises(KeyError):
            owner_nations.get_owner_nation_name(100, "barbar")

    def test_get_unpermitted_owner_nation_name_raises_exception(self):
        rows = [[1, "Testopia", "foofoo,barbar,coocoo"], [2, "Monopia", "zoo"]]
        owner_nations = loader.OwnerNations.load_from_rows(rows)

        with pytest.raises(ValueError):
            owner_nations.get_owner_nation_name(1, "illegalsheet")

    def test_get_owner_nation_name_returns_name_of_last_identical_id(self):
        rows = [[1, "Testopia", "foofoo,barbar,coocoo"], [1, "Monopia", "zoo"]]
        owner_nations = loader.OwnerNations.load_from_rows(rows)

        assert owner_nations.get_owner_nation_name(1, "zoo") == "Monopia"


class TestExtractNameFromHyperlink:
    def test_valid_hyperlink_returns_name(self):
        cell_value = (
            '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","foobar")'
        )

        assert loader.extract_name_from_hyperlink(cell_value) == "foobar"

    def test_invalid_hyperlink_returns_input(self):
        cell_value = "foobar"

        assert loader.extract_name_from_hyperlink(cell_value) == "foobar"


class TestExtractDispatchIdFromHyperlink:
    def test_valid_hyperlink_returns_id_num(self):
        cell_value = (
            '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","foobar")'
        )

        assert loader.extract_dispatch_id_from_hyperlink(cell_value) == "1234"

    def test_invalid_hyperlink_returns_none(self):
        cell_value = "foobar"

        assert loader.extract_dispatch_id_from_hyperlink(cell_value) == None


class TestLoadUtilityTemplatesFromSpreadsheets:
    def test_returns_templates(self):
        spreadsheets = {"abcd1234": {"Layout!A1:B": [["layout1", "abcd"]]}}

        r = loader.load_utility_templates_from_spreadsheets(spreadsheets)

        assert r == {"layout1": "abcd"}

    def test_returns_last_identical_template(self):
        spreadsheets = {
            "abcd1234": {"Layout!A1:B": [["layout1", "abcd"], ["layout1", "xyzt"]]}
        }

        r = loader.load_utility_templates_from_spreadsheets(spreadsheets)

        assert r == {"layout1": "xyzt"}


class TestDispatchData:
    def test_get_canonical_dispatch_config_id_exists_returns_canonical_config(self):
        dispatch_data = {
            "name1": {
                "owner_nation": "testopia",
                "action": "edit",
                "ns_id": "12345",
                "title": "Test 1",
                "template": "Text 1",
                "category": "meta",
                "subcategory": "gameplay",
            }
        }
        obj = loader.Dispatches(dispatch_data)

        r = obj.get_canonical_dispatch_config()

        assert r == {
            "testopia": {
                "name1": {
                    "action": "edit",
                    "ns_id": "12345",
                    "title": "Test 1",
                    "category": "meta",
                    "subcategory": "gameplay",
                }
            }
        }

    def test_get_canonical_dispatch_config_id_not_exist_returns_canonical_config(self):
        dispatch_data = {
            "name1": {
                "owner_nation": "testopia",
                "action": "create",
                "title": "Test 1",
                "template": "Text 1",
                "category": "meta",
                "subcategory": "gameplay",
            }
        }
        obj = loader.Dispatches(dispatch_data)

        r = obj.get_canonical_dispatch_config()

        assert r == {
            "testopia": {
                "name1": {
                    "action": "create",
                    "title": "Test 1",
                    "category": "meta",
                    "subcategory": "gameplay",
                }
            }
        }

    def test_get_dispatch_template_returns_template_text(self):
        dispatch_data = {
            "name1": {
                "owner_nation": "testopia",
                "action": "edit",
                "ns_id": "12345",
                "title": "Test 1",
                "template": "Text 1",
                "category": "meta",
                "subcategory": "gameplay",
            }
        }
        obj = loader.Dispatches(dispatch_data)

        assert obj.get_dispatch_template("name1") == "Text 1"

    def test_get_non_existent_dispatch_template_raises_exception(self):
        obj = loader.Dispatches({})

        with pytest.raises(KeyError):
            obj.get_dispatch_template("something non existent")

    def test_add_dispatch_id_adds_id_into_new_dispatch(self):
        dispatch_data = {
            "name1": {
                "owner_nation": "testopia",
                "action": "edit",
                "title": "Test 1",
                "template": "Text 1",
                "category": "meta",
                "subcategory": "gameplay",
            }
        }
        obj = loader.Dispatches(dispatch_data)

        obj.add_dispatch_id("name1", "54321")

        assert obj.dispatch_data["name1"]["ns_id"] == "54321"

    def test_add_dispatch_id_overrides_old_id(self):
        dispatch_data = {
            "name1": {
                "owner_nation": "testopia",
                "action": "edit",
                "ns_id": "12345",
                "title": "Test 1",
                "template": "Text 1",
                "category": "meta",
                "subcategory": "gameplay",
            }
        }
        obj = loader.Dispatches(dispatch_data)

        obj.add_dispatch_id("name1", "54321")

        assert obj.dispatch_data["name1"]["ns_id"] == "54321"


@pytest.fixture
def owner_nations():
    return loader.OwnerNations({1: "testopia"}, {1: ["abcd1234", "xyzt1234"]})


@pytest.fixture
def category_setups():
    return loader.CategorySetups({1: "meta"}, {1: "reference"})


class TestDispatchSheetRange:
    def test_extract_dispatch_data_valid_action_returns_data(
        self, owner_nations, category_setups
    ):
        result_reporter = mock.Mock()
        row_values = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                "edit",
                1,
                1,
                "Title 1",
                "Text 1",
                "",
            ]
        ]
        obj = loader.DispatchSheetRange(row_values, result_reporter)

        r = obj.get_dispatches_as_dict(owner_nations, category_setups, "abcd1234")

        assert r == {
            "name1": {
                "owner_nation": "testopia",
                "ns_id": "1234",
                "action": "edit",
                "title": "Title 1",
                "template": "Text 1",
                "category": "meta",
                "subcategory": "reference",
            }
        }

    def test_extract_dispatch_data_returns_data_of_no_id_rows(
        self, owner_nations, category_setups
    ):
        result_reporter = mock.Mock()
        row_values = [["name1", "create", 1, 1, "Title 1", "Text 1", ""]]
        obj = loader.DispatchSheetRange(row_values, result_reporter)

        r = obj.get_dispatches_as_dict(owner_nations, category_setups, "abcd1234")

        assert r == {
            "name1": {
                "owner_nation": "testopia",
                "action": "create",
                "title": "Title 1",
                "template": "Text 1",
                "category": "meta",
                "subcategory": "reference",
            }
        }

    def test_extract_dispatch_data_skips_rows_with_not_enough_cells(
        self, owner_nations, category_setups
    ):
        result_reporter = mock.Mock()
        row_values = [["name1", "create", 1, 1, "Title 1"]]
        obj = loader.DispatchSheetRange(row_values, result_reporter)

        r = obj.get_dispatches_as_dict(owner_nations, category_setups, "abcd1234")

        assert r == {}

    def test_extract_dispatch_data_skips_rows_with_empty_name(
        self, owner_nations, category_setups
    ):
        result_reporter = mock.Mock()
        row_values = [["name1", "create", 1, 1, "Title 1"]]
        obj = loader.DispatchSheetRange(row_values, result_reporter)

        r = obj.get_dispatches_as_dict(owner_nations, category_setups, "abcd1234")

        assert r == {}

    def test_extract_dispatch_data_skips_over_invalid_action_dispatch(
        self, owner_nations, category_setups
    ):
        result_reporter = mock.Mock()
        row_values = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                "invalid action",
                1,
                1,
                "Title 1",
                "Text 1",
                "",
            ]
        ]
        obj = loader.DispatchSheetRange(row_values, result_reporter)

        r = obj.get_dispatches_as_dict(owner_nations, category_setups, "abcd1234")

        assert r == {}
        result_reporter.report_failure.assert_called()

    def test_extract_dispatch_data_skips_over_empty_action_dispatch(
        self, owner_nations, category_setups
    ):
        result_reporter = mock.Mock()
        row_values = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                "",
                1,
                1,
                "Title 1",
                "Text 1",
                "",
            ]
        ]
        obj = loader.DispatchSheetRange(row_values, result_reporter)

        r = obj.get_dispatches_as_dict(owner_nations, category_setups, "abcd1234")

        assert r == {}

    def test_extract_dispatch_data_skips_over_non_existent_owner_dispatch(
        self, owner_nations, category_setups
    ):
        result_reporter = mock.Mock()
        row_values = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                "edit",
                20,
                1,
                "Title 1",
                "Text 1",
                "",
            ]
        ]
        obj = loader.DispatchSheetRange(row_values, result_reporter)

        r = obj.get_dispatches_as_dict(owner_nations, category_setups, "abcd1234")

        assert r == {}
        result_reporter.report_failure.assert_called()

    def test_extract_dispatch_data_skips_over_unpermitted_owner_dispatch(
        self, owner_nations, category_setups
    ):
        result_reporter = mock.Mock()
        row_values = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                "edit",
                1,
                1,
                "Title 1",
                "Text 1",
                "",
            ]
        ]
        obj = loader.DispatchSheetRange(row_values, result_reporter)

        r = obj.get_dispatches_as_dict(owner_nations, category_setups, "ijkl1234")

        assert r == {}
        result_reporter.report_failure.assert_called()

    def test_extract_dispatch_data_skips_over_non_existent_category_setup_dispatch(
        self, owner_nations, category_setups
    ):
        result_reporter = mock.Mock()
        row_values = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                "edit",
                1,
                20,
                "Title 1",
                "Text 1",
                "",
            ]
        ]
        obj = loader.DispatchSheetRange(row_values, result_reporter)

        r = obj.get_dispatches_as_dict(owner_nations, category_setups, "abcd1234")

        assert r == {}
        result_reporter.report_failure.assert_called()

    def test_extract_dispatch_data_should_not_stop_on_skipped_rows(
        self, owner_nations, category_setups
    ):
        result_reporter = mock.Mock()
        row_values = [
            ["", "", 1, 1, "Title 1", "Text 1", ""],
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name2")',
                "edit",
                1,
                1,
                "Title 2",
                "Text 2",
                "",
            ],
        ]
        obj = loader.DispatchSheetRange(row_values, result_reporter)

        r = obj.get_dispatches_as_dict(owner_nations, category_setups, "abcd1234")

        assert r == {
            "name2": {
                "owner_nation": "testopia",
                "ns_id": "1234",
                "action": "edit",
                "title": "Title 2",
                "template": "Text 2",
                "category": "meta",
                "subcategory": "reference",
            }
        }

    def test_get_new_values_of_edited_dispatch(self):
        message = loader.Message(is_failure=False, text="Test message")
        result_reporter = mock.Mock(get_message=mock.Mock(return_value=message))
        row_values = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                "edit",
                1,
                1,
                "Title 1",
                "Text 1",
                "Old message",
            ]
        ]
        obj = loader.DispatchSheetRange(row_values, result_reporter)
        new_dispatch_data = {
            "name1": {
                "owner_nation": "testopia",
                "ns_id": "1234",
                "action": "edit",
                "title": "Title 1",
                "template": "Text 1",
                "category": "meta",
                "subcategory": "reference",
            }
        }

        r = obj.get_new_values(new_dispatch_data)

        expected = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                "edit",
                1,
                1,
                "Title 1",
                "Text 1",
                "Test message",
            ]
        ]
        assert r == expected

    def test_get_new_values_of_created_dispatch_changes_action_to_edit(self):
        message = loader.Message(is_failure=False, text="Test message")
        result_reporter = mock.Mock(get_message=mock.Mock(return_value=message))
        row_values = [["name1", "create", 1, 1, "Title 1", "Text 1", "Old message"]]
        obj = loader.DispatchSheetRange(row_values, result_reporter)
        new_dispatch_data = {
            "name1": {
                "owner_nation": "testopia",
                "ns_id": "1234",
                "action": "create",
                "title": "Title 1",
                "template": "Text 1",
                "category": "meta",
                "subcategory": "reference",
            }
        }

        r = obj.get_new_values(new_dispatch_data)

        expected = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                "edit",
                1,
                1,
                "Title 1",
                "Text 1",
                "Test message",
            ]
        ]
        assert r == expected

    def test_get_new_values_of_removed_dispatch_changes_action_to_empty_removes_hyperlink(
        self,
    ):
        message = loader.Message(is_failure=False, text="Test message")
        result_reporter = mock.Mock(get_message=mock.Mock(return_value=message))
        row_values = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                "create",
                1,
                1,
                "Title 1",
                "Text 1",
                "Old message",
            ]
        ]
        obj = loader.DispatchSheetRange(row_values, result_reporter)
        new_dispatch_data = {
            "name1": {
                "owner_nation": "testopia",
                "ns_id": "1234",
                "action": "remove",
                "title": "Title 1",
                "template": "Text 1",
                "category": "meta",
                "subcategory": "reference",
            }
        }

        r = obj.get_new_values(new_dispatch_data)

        expected = [["name1", "", 1, 1, "Title 1", "Text 1", "Test message"]]
        assert r == expected

    def test_get_new_values_keeps_empty_action_rows_same(self):
        result_reporter = mock.Mock()
        row_values = [["name1", "", 1, 1, "Title 1", "Text 1", "Old message"]]
        new_dispatch_data = {}
        obj = loader.DispatchSheetRange(row_values, result_reporter)

        r = obj.get_new_values(new_dispatch_data)

        expected = [["name1", "", 1, 1, "Title 1", "Text 1", "Old message"]]
        assert r == expected

    def test_get_new_values_failure_result_message_adds_message(self):
        message = loader.Message(is_failure=True, text="Error message")
        result_reporter = mock.Mock(get_message=mock.Mock(return_value=message))
        row_values = [["name1", "create", 1, 1, "Title 1", "Text 1", "Old message"]]
        new_dispatch_data = {}
        obj = loader.DispatchSheetRange(row_values, result_reporter)

        r = obj.get_new_values(new_dispatch_data)

        expected = [["name1", "create", 1, 1, "Title 1", "Text 1", "Error message"]]
        assert r == expected

    def test_get_new_values_skips_row_on_non_existent_result_message(self):
        result_reporter = mock.Mock(get_message=mock.Mock(side_effect=KeyError))
        row_values = [["name1", "create", 1, 1, "Title 1", "Text 1", "Old message"]]
        new_dispatch_data = {}
        obj = loader.DispatchSheetRange(row_values, result_reporter)

        r = obj.get_new_values(new_dispatch_data)

        expected = [["name1", "create", 1, 1, "Title 1", "Text 1", "Old message"]]
        assert r == expected

    def test_get_new_values_keeps_rows_with_not_enough_cells_same(self):
        result_reporter = mock.Mock()
        row_values = [["name1", "create", 1, 1, "Title 1"]]
        new_dispatch_data = {}
        obj = loader.DispatchSheetRange(row_values, result_reporter)

        r = obj.get_new_values(new_dispatch_data)

        expected = [["name1", "create", 1, 1, "Title 1"]]
        assert r == expected

    def test_get_new_values_adds_missing_result_message_cell(self):
        message = loader.Message(is_failure=False, text="Test message")
        result_reporter = mock.Mock(get_message=mock.Mock(return_value=message))
        row_values = [["name1", "create", 1, 1, "Title 1", "Text 1"]]
        new_dispatch_data = {
            "name1": {
                "owner_nation": "testopia",
                "ns_id": "1234",
                "action": "create",
                "title": "Title 1",
                "template": "Text 1",
                "category": "meta",
                "subcategory": "reference",
            }
        }
        obj = loader.DispatchSheetRange(row_values, result_reporter)

        r = obj.get_new_values(new_dispatch_data)

        expected = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                "edit",
                1,
                1,
                "Title 1",
                "Text 1",
                "Test message",
            ]
        ]
        assert r == expected

    def test_get_new_values_should_not_stop_on_skipped_rows(self):
        message = loader.Message(is_failure=False, text="Test message")
        result_reporter = mock.Mock(get_message=mock.Mock(return_value=message))
        row_values = [
            ["", "", 1, 1, "Title 1", "Text 1"],
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name2")',
                "edit",
                1,
                1,
                "Title 2",
                "Text 2",
            ],
        ]
        new_dispatch_data = {
            "name2": {
                "owner_nation": "testopia",
                "ns_id": "1234",
                "action": "create",
                "title": "Title 1",
                "template": "Text 1",
                "category": "meta",
                "subcategory": "reference",
            }
        }
        obj = loader.DispatchSheetRange(row_values, result_reporter)

        r = obj.get_new_values(new_dispatch_data)

        expected = [
            ["", "", 1, 1, "Title 1", "Text 1"],
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name2")',
                "edit",
                1,
                1,
                "Title 2",
                "Text 2",
                "Test message",
            ],
        ]
        assert r == expected


@pytest.fixture
def dispatch_data():
    return {
        "name1": {
            "owner_nation": "testopia",
            "ns_id": "1234",
            "action": "edit",
            "title": "Title 1",
            "template": "Text 1",
            "category": "meta",
            "subcategory": "reference",
        },
        "name2": {
            "owner_nation": "testopia",
            "ns_id": "4321",
            "action": "remove",
            "title": "Title 2",
            "template": "Text 2",
            "category": "meta",
            "subcategory": "reference",
        },
    }


class TestDispatchSpreadsheet:
    def test_extract_dispatch_data_returns_data(
        self, owner_nations, category_setups, dispatch_data
    ):
        result_reporter = mock.Mock()
        sheet_ranges = {
            "Sheet1!A3:F": [
                [
                    '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                    "edit",
                    1,
                    1,
                    "Title 1",
                    "Text 1",
                    "Old message",
                ]
            ],
            "Sheet2!A3:F": [
                [
                    '=hyperlink("https://www.nationstates.net/page=dispatch/id=4321","name2")',
                    "remove",
                    1,
                    1,
                    "Title 2",
                    "Text 2",
                    "Old message",
                ]
            ],
        }
        obj = loader.DispatchSpreadsheet(sheet_ranges, result_reporter)

        r = obj.get_dispatches_as_dict(owner_nations, category_setups, "abcd1234")

        assert r == dispatch_data

    def test_get_new_values_returns_new_values(self, dispatch_data):
        message = loader.Message(is_failure=False, text="Test message")
        result_reporter = mock.Mock(get_message=mock.Mock(return_value=message))
        sheet_ranges = {
            "Sheet1!A3:F": [
                [
                    '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                    "edit",
                    1,
                    1,
                    "Title 1",
                    "Text 1",
                    "Old message",
                ]
            ],
            "Sheet2!A3:F": [
                [
                    '=hyperlink("https://www.nationstates.net/page=dispatch/id=4321","name2")',
                    "remove",
                    1,
                    1,
                    "Title 2",
                    "Text 2",
                    "Old message",
                ]
            ],
        }

        obj = loader.DispatchSpreadsheet(sheet_ranges, result_reporter)

        r = obj.get_new_values(dispatch_data)

        assert r == {
            "Sheet1!A3:F": [
                [
                    '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                    "edit",
                    1,
                    1,
                    "Title 1",
                    "Text 1",
                    "Test message",
                ]
            ],
            "Sheet2!A3:F": [["name2", "", 1, 1, "Title 2", "Text 2", "Test message"]],
        }


class TestDispatchSpreadsheets:
    def test_extract_dispatch_data_returns_data(
        self, owner_nations, category_setups, dispatch_data
    ):
        result_reporter = mock.Mock()
        range1 = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                "edit",
                1,
                1,
                "Title 1",
                "Text 1",
                "Old message",
            ]
        ]
        range2 = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=4321","name2")',
                "remove",
                1,
                1,
                "Title 2",
                "Text 2",
                "Old message",
            ]
        ]
        spreadsheets = {
            "abcd1234": {"Sheet1!A3:F": range1},
            "xyzt1234": {"Sheet2!A3:F": range2},
        }
        obj = loader.DispatchSpreadsheets(spreadsheets, result_reporter)

        r = obj.get_dispatches_as_dict(owner_nations, category_setups)

        assert r == dispatch_data

    def test_get_new_values_returns_new_values(self, dispatch_data):
        message = loader.Message(is_failure=False, text="Test message")
        result_reporter = mock.Mock(get_message=mock.Mock(return_value=message))
        range1 = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                "edit",
                1,
                1,
                "Title 1",
                "Text 1",
                "Old message",
            ]
        ]
        range2 = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=4321","name2")',
                "remove",
                1,
                1,
                "Title 2",
                "Text 2",
                "Old message",
            ]
        ]
        spreadsheets = {
            "abcd1234": {"Sheet1!A3:F": range1},
            "xyzt1234": {"Sheet2!A3:F": range2},
        }
        obj = loader.DispatchSpreadsheets(spreadsheets, result_reporter)

        r = obj.get_new_values(dispatch_data)

        range1_expected = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                "edit",
                1,
                1,
                "Title 1",
                "Text 1",
                "Test message",
            ]
        ]
        range2_expected = [["name2", "", 1, 1, "Title 2", "Text 2", "Test message"]]
        assert r == {
            "abcd1234": {"Sheet1!A3:F": range1_expected},
            "xyzt1234": {"Sheet2!A3:F": range2_expected},
        }


class TestGoogleDispatchLoader:
    def test_get_dispatch_config(self):
        range1 = [
            ["name1", "create", 1, 1, "Title 1", "Text 1"],
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name2")',
                "edit",
                1,
                2,
                "Title 2",
                "Text 2",
                "Edited on 2021/01/01 01:00:00 UTC",
            ],
        ]
        range2 = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=4321","name3")',
                "remove",
                2,
                1,
                "Title 3",
                "Text 3",
                "Edited on 2021/01/01 01:00:00 UTC",
            ]
        ]
        dispatch_spreadsheets = {
            "abcd1234": {"Sheet1!A3:F": range1},
            "xyzt1234": {"Sheet2!A3:F": range2},
        }
        utility_template_spreadsheets = {
            "abcd1234": {"Layout!A3:B": [["layout1", "abcd"]]}
        }
        owner_nation_rows = [[1, "Testopia", "abcd1234"], [2, "Cooltopia", "xyzt1234"]]
        category_rows = [[1, "Meta", "Gameplay"], [2, "Meta", "Reference"]]
        obj = loader.GoogleDispatchLoader(
            mock.Mock(),
            dispatch_spreadsheets,
            utility_template_spreadsheets,
            owner_nation_rows,
            category_rows,
        )

        r = obj.get_dispatch_config()

        assert r == {
            "Testopia": {
                "name1": {
                    "action": "create",
                    "title": "Title 1",
                    "category": "Meta",
                    "subcategory": "Gameplay",
                },
                "name2": {
                    "action": "edit",
                    "ns_id": "1234",
                    "title": "Title 2",
                    "category": "Meta",
                    "subcategory": "Reference",
                },
            },
            "Cooltopia": {
                "name3": {
                    "action": "remove",
                    "ns_id": "4321",
                    "title": "Title 3",
                    "category": "Meta",
                    "subcategory": "Gameplay",
                }
            },
        }

    def test_get_dispatch_template_of_utility_template(self):
        range1 = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                "edit",
                1,
                1,
                "Title 1",
                "Text 1",
                "Edited on 2021/01/01 01:00:00 UTC",
            ]
        ]
        dispatch_spreadsheets = {"abcd1234": {"Sheet1!A3:F": range1}}
        utility_template_spreadsheets = {
            "abcd1234": {"Layout!A3:B": [["layout1", "abcd"]]}
        }
        owner_nation_rows = [[1, "Testopia", "abcd1234"]]
        category_rows = [[1, "Meta", "Gameplay"]]
        obj = loader.GoogleDispatchLoader(
            mock.Mock(),
            dispatch_spreadsheets,
            utility_template_spreadsheets,
            owner_nation_rows,
            category_rows,
        )

        r = obj.get_dispatch_template("layout1")

        assert r == "abcd"

    def test_get_dispatch_template_of_normal_dispatch(self):
        range1 = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                "edit",
                1,
                1,
                "Title 1",
                "Text 1",
                "Edited on 2021/01/01 01:00:00 UTC",
            ]
        ]
        dispatch_spreadsheets = {"abcd1234": {"Sheet1!A3:F": range1}}
        utility_template_spreadsheets = {
            "abcd1234": {"Layout!A3:B": [["layout1", "abcd"]]}
        }
        owner_nation_rows = [[1, "Testopia", "abcd1234"]]
        category_rows = [[1, "Meta", "Gameplay"]]
        obj = loader.GoogleDispatchLoader(
            mock.Mock(),
            dispatch_spreadsheets,
            utility_template_spreadsheets,
            owner_nation_rows,
            category_rows,
        )

        r = obj.get_dispatch_template("name1")

        assert r == "Text 1"

    def test_update_spreadsheets_after_successfully_create_new_dispatch(self):
        range1 = [["name1", "create", 1, 1, "Title 1", "Text 1"]]
        dispatch_spreadsheets = {"abcd1234": {"Sheet1!A3:F": range1}}
        utility_template_spreadsheets = {}
        owner_nation_rows = [[1, "Testopia", "abcd1234"]]
        category_rows = [[1, "Meta", "Gameplay"]]
        spreadsheet_api = mock.Mock()
        obj = loader.GoogleDispatchLoader(
            spreadsheet_api,
            dispatch_spreadsheets,
            utility_template_spreadsheets,
            owner_nation_rows,
            category_rows,
        )

        obj.add_dispatch_id("name1", "1234")
        obj.report_result(
            "name1", "create", "success", datetime.fromisoformat("2021-01-01T00:00:00")
        )
        obj.update_spreadsheets()

        new_range = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                "edit",
                1,
                1,
                "Title 1",
                "Text 1",
                "Created on 2021/01/01 00:00:00 ",
            ]
        ]
        new_spreadsheets = {"abcd1234": {"Sheet1!A3:F": new_range}}
        spreadsheet_api.update_rows_in_many_spreadsheets.assert_called_with(
            new_spreadsheets
        )
