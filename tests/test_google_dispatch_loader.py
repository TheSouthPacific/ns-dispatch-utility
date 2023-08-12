from datetime import datetime, timezone
from unittest import mock
from unittest.mock import Mock

import freezegun
import pytest

from nsdu.loader_api import Dispatch, DispatchOperation
from nsdu.loaders import google_dispatch_loader as loader
from nsdu.loaders.google_dispatch_loader import (
    CategorySetup,
    DispatchRow,
    OwnerNation,
    SheetRange,
)


class TestGoogleSheetsApiAdapter:
    def test_get_values_of_a_range_returns_cell_values_of_that_range(self):
        api_resp = {
            "spreadsheetId": "s",
            "valueRanges": [
                {"range": "A!A1:F", "majorDimension": "ROWS", "values": [["v"]]}
            ],
        }
        request = Mock(execute=Mock(return_value=api_resp))
        google_api = Mock(batchGet=Mock(return_value=request))
        api = loader.GoogleSheetsApiAdapter(google_api)

        range = loader.SheetRange("s", "A!A1:F")
        result = api.get_values_of_range(range)

        assert result == [["v"]]

    def test_get_values_of_an_empty_range_returns_empty_list(self):
        api_resp = {
            "spreadsheetId": "s",
            "valueRanges": [{"range": "A!A1:F", "majorDimension": "ROWS"}],
        }
        request = Mock(execute=Mock(return_value=api_resp))
        google_api = Mock(batchGet=Mock(return_value=request))
        api = loader.GoogleSheetsApiAdapter(google_api)

        range = loader.SheetRange("s", "A!A1:F")
        result = api.get_values_of_range(range)

        assert result == []

    def test_get_values_of_many_ranges_returns_cell_values_of_those_ranges(self):
        api_resp = {
            "spreadsheetId": "s",
            "valueRanges": [
                {"range": "A!A1:F", "majorDimension": "ROWS", "values": [["v1"]]},
                {"range": "B!A1:F", "majorDimension": "ROWS", "values": [["v2"]]},
            ],
        }
        request = Mock(execute=Mock(return_value=api_resp))
        google_api = Mock(batchGet=Mock(return_value=request))
        api = loader.GoogleSheetsApiAdapter(google_api)

        ranges = [loader.SheetRange("s", "A!A1:F"), loader.SheetRange("s", "B!A1:F")]
        result = api.get_values_of_ranges(ranges)

        assert result == {ranges[0]: [["v1"]], ranges[1]: [["v2"]]}

    def test_get_values_of_empty_ranges_returns_empty_list(self):
        api_resp = {
            "spreadsheetId": "s",
            "valueRanges": [
                {"range": "A!A1:F", "majorDimension": "ROWS"},
                {"range": "B!A1:F", "majorDimension": "ROWS"},
            ],
        }
        request = Mock(execute=Mock(return_value=api_resp))
        google_api = Mock(batchGet=Mock(return_value=request))
        api = loader.GoogleSheetsApiAdapter(google_api)

        ranges = [loader.SheetRange("s", "A!A1:F"), loader.SheetRange("s", "B!A1:F")]
        result = api.get_values_of_ranges(ranges)

        assert result == {ranges[0]: [], ranges[1]: []}

    def test_update_values_of_many_ranges_makes_correct_api_client_call(self):
        google_api = Mock()
        api = loader.GoogleSheetsApiAdapter(google_api)

        new_values = {loader.SheetRange("s", "A!A1:F"): [["v"]]}
        api.update_values_of_ranges(new_values)

        expected_body = {
            "valueInputOption": "USER_ENTERED",
            "data": [{"range": "A!A1:F", "majorDimension": "ROWS", "values": [["v"]]}],
        }
        google_api.batchUpdate.assert_called_with(spreadsheetId="s", body=expected_body)


class TestOperationResult:
    def test_get_success_result_message_returns_formatted_message(self):
        result = loader.SuccessOpResult(
            "name", DispatchOperation.CREATE, datetime(2023, 1, 1)
        )

        assert (
            result.result_message == "Created successfully.\nTime: 2023/01/01 00:00:00 "
        )

    def test_get_failure_result_message_returns_formatted_message(self):
        result = loader.FailureOpResult(
            "name",
            DispatchOperation.CREATE,
            datetime(2023, 1, 1),
            "Some details.",
        )

        assert (
            result.result_message
            == "Failed to create.\nDetails: Some details.\nTime: 2023/01/01 00:00:00 "
        )


class TestOperationResultStore:
    def test_report_success_adds_success_result(self):
        obj = loader.OpResultStore()

        obj.report_success("n", DispatchOperation.CREATE, datetime(2023, 1, 1))
        result = obj["n"]

        assert result == loader.SuccessOpResult(
            "n", DispatchOperation.CREATE, datetime(2023, 1, 1)
        )

    @freezegun.freeze_time("2023-01-01")
    def test_report_success_with_no_result_time_uses_current_time_as_result_time(self):
        obj = loader.OpResultStore()

        obj.report_success("n", DispatchOperation.CREATE)
        result = obj["n"].result_time

        assert result == datetime(2023, 1, 1, tzinfo=timezone.utc)

    def test_report_failure_with_no_details_adds_no_details_failure_result(self):
        obj = loader.OpResultStore()

        obj.report_failure("n", DispatchOperation.CREATE, None, datetime(2023, 1, 1))
        result = obj["n"]

        assert isinstance(result, loader.FailureOpResult) and result.details is None

    def test_report_failure_with_str_details_adds_failure_result_with_str_details(
        self,
    ):
        obj = loader.OpResultStore()

        obj.report_failure("n", DispatchOperation.CREATE, "d", datetime(2023, 1, 1))
        result = obj["n"]

        assert isinstance(result, loader.FailureOpResult) and result.details == "d"

    def test_report_failure_with_exception_details_adds_failure_result_with_exception_msg_details(
        self,
    ):
        obj = loader.OpResultStore()

        obj.report_failure(
            "n", DispatchOperation.CREATE, Exception("d"), datetime(2023, 1, 1)
        )
        result = obj["n"]

        assert isinstance(result, loader.FailureOpResult) and result.details == "d"

    def test_report_failure_with_invalid_op_adds_failure_result_with_invalid_op_name(
        self,
    ):
        obj = loader.OpResultStore()

        obj.report_failure("n", "a", details="d")
        result = obj["n"].operation

        assert result == "a"

    @freezegun.freeze_time("2023-01-01")
    def test_report_failure_with_no_result_time_uses_current_time_as_result_time(self):
        obj = loader.OpResultStore()

        obj.report_failure("n", DispatchOperation.CREATE, details="d")
        result = obj["n"].result_time

        assert result == datetime(2023, 1, 1, tzinfo=timezone.utc)


class TestCategorySetupStore:
    def test_get_setup_returns_correct_setup(self):
        setups = {"1": loader.CategorySetup("meta", "gameplay")}
        obj = loader.CategorySetupStore(setups)

        result = obj["1"]

        assert result == loader.CategorySetup("meta", "gameplay")

    def test_get_setup_of_non_existent_id_raises_exception(self):
        category_setups = loader.CategorySetupStore({})

        with pytest.raises(KeyError):
            category_setups["1"]

    def test_load_from_range_cell_values_gets_correct_setups(self):
        cell_values = [[1, "meta", "gameplay"]]

        obj = loader.CategorySetupStore.load_from_range_cell_values(cell_values)

        assert obj["1"] == loader.CategorySetup("meta", "gameplay")

    def test_load_from_range_cell_values_uses_last_conflicting_setup_id(self):
        cell_values = [["1", "Meta", "Gameplay"], ["1", "overview", "factbook"]]

        obj = loader.CategorySetupStore.load_from_range_cell_values(cell_values)

        assert obj["1"] == loader.CategorySetup("overview", "factbook")

    def test_load_from_range_cell_values_converts_category_subcategory_names_to_lower_case(
        self,
    ):
        cell_values = [[1, "meta", "gameplay"]]

        obj = loader.CategorySetupStore.load_from_range_cell_values(cell_values)

        assert obj["1"] == loader.CategorySetup("meta", "gameplay")


class TestOwnerNationData:
    def test_get_owner_nation_returns_correct_nation(self):
        owner_nations = {"1": loader.OwnerNation("n", [])}
        obj = loader.OwnerNationStore(owner_nations)

        result = obj["1"]

        assert result == loader.OwnerNation("n", [])

    def test_get_non_existent_owner_nation_raises_exception(self):
        obj = loader.OwnerNationStore({})

        with pytest.raises(KeyError):
            obj["1"]

    def test_check_permission_on_allowed_spreadsheet_returns_true(self):
        owner_nations = {"1": loader.OwnerNation("n", ["s"])}
        obj = loader.OwnerNationStore(owner_nations)

        result = obj.check_spreadsheet_permission("1", "s")

        assert result

    def test_check_permission_on_non_allowed_spreadsheet_returns_false(self):
        owner_nations = {"1": loader.OwnerNation("n", ["s"])}
        obj = loader.OwnerNationStore(owner_nations)

        result = obj.check_spreadsheet_permission("1", "s1")

        assert not result

    def test_check_permission_of_non_existent_owner_raises_exception(self):
        obj = loader.OwnerNationStore({})

        with pytest.raises(KeyError):
            obj.check_spreadsheet_permission("1", "s")

    def test_load_from_range_cell_values_gets_correct_owner_nations(self):
        cell_data = [["1", "n", "s1,s2"]]
        obj = loader.OwnerNationStore.load_from_range_cell_values(cell_data)

        assert obj["1"] == loader.OwnerNation("n", ["s1", "s2"])

    def test_load_from_range_cell_values_uses_last_conflicting_owner_id(self):
        cell_data = [["1", "n1", "s1"], ["1", "n2", "s2"]]

        obj = loader.OwnerNationStore.load_from_range_cell_values(cell_data)

        assert obj["1"] == loader.OwnerNation("n2", ["s2"])


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


class TestParseUtilityTemplateCellRanges:
    def test_parse_many_templates_returns_correct_templates(self):
        rows = [
            loader.UtilityTemplateRow("l1", "a"),
            loader.UtilityTemplateRow("l2", "b"),
        ]

        result = loader.parse_utility_template_sheet_rows(rows)

        assert result == {"l1": "a", "l2": "b"}

    def test_parse_uses_last_conflicting_template(self):
        rows = [
            loader.UtilityTemplateRow("l", "a"),
            loader.UtilityTemplateRow("l", "b"),
        ]

        result = loader.parse_utility_template_sheet_rows(rows)

        assert result == {"l": "b"}


class TestDispatchConfig:
    def test_get_canonical_dispatch_config_id_exists_returns_canonical_config(self):
        dispatch_data = {
            "name1": Dispatch(
                ns_id="12345",
                owner_nation="testopia",
                operation=DispatchOperation.EDIT,
                title="Hello Title",
                content="Hello World",
                category="meta",
                subcategory="gameplay",
            )
        }
        obj = loader.DispatchConfigStore(dispatch_data)

        result = obj.get_canonical_dispatch_config()

        assert result == {
            "testopia": {
                "name1": {
                    "action": "edit",
                    "ns_id": "12345",
                    "title": "Hello Title",
                    "category": "meta",
                    "subcategory": "gameplay",
                }
            }
        }

    def test_get_canonical_dispatch_config_id_not_exist_returns_canonical_config(self):
        dispatch_data = {
            "name1": Dispatch(
                ns_id=None,
                owner_nation="testopia",
                operation=DispatchOperation.CREATE,
                title="Hello Title",
                content="Hello World",
                category="meta",
                subcategory="gameplay",
            )
        }
        obj = loader.DispatchConfigStore(dispatch_data)

        result = obj.get_canonical_dispatch_config()

        assert result == {
            "testopia": {
                "name1": {
                    "action": "create",
                    "title": "Hello Title",
                    "category": "meta",
                    "subcategory": "gameplay",
                }
            }
        }

    def test_get_dispatch_template_returns_template_text(self):
        dispatch_data = {
            "name1": Dispatch(
                ns_id="12345",
                owner_nation="testopia",
                operation=DispatchOperation.EDIT,
                title="Hello Title",
                content="Hello World",
                category="meta",
                subcategory="gameplay",
            )
        }
        obj = loader.DispatchConfigStore(dispatch_data)

        assert obj.get_dispatch_template("name1") == "Hello World"

    def test_get_non_existent_dispatch_template_raises_exception(self):
        obj = loader.DispatchConfigStore({})

        with pytest.raises(KeyError):
            obj.get_dispatch_template("something non existent")

    def test_add_dispatch_id_adds_id_into_new_dispatch(self):
        dispatch_data = {
            "name1": Dispatch(
                ns_id=None,
                owner_nation="testopia",
                operation=DispatchOperation.CREATE,
                title="Hello Title",
                content="Hello World",
                category="meta",
                subcategory="gameplay",
            )
        }
        obj = loader.DispatchConfigStore(dispatch_data)

        obj.add_dispatch_id("name1", "54321")

        assert obj["name1"].ns_id == "54321"

    def test_add_dispatch_id_overrides_old_id(self):
        dispatch_data = {
            "name1": Dispatch(
                ns_id="12345",
                owner_nation="testopia",
                operation=DispatchOperation.EDIT,
                title="Hello Title",
                content="Hello World",
                category="meta",
                subcategory="gameplay",
            )
        }
        obj = loader.DispatchConfigStore(dispatch_data)

        obj.add_dispatch_id("name1", "54321")

        assert obj["name1"].ns_id == "54321"


class TestParseDispatchDataRow:
    @pytest.fixture(scope="class")
    def owner_nations(self):
        return loader.OwnerNationStore({"1": loader.OwnerNation("n", ["s"])})

    @pytest.fixture(scope="class")
    def category_setups(self):
        return loader.CategorySetupStore(
            {"1": loader.CategorySetup("meta", "gameplay")}
        )

    def test_ns_id_exists_returns_dispatch_obj_with_ns_id(
        self, owner_nations, category_setups
    ):
        spreadsheet_id = "s"
        row = DispatchRow(
            '=hyperlink("https://www.nationstates.net/page=dispatch/id=1","n")',
            "edit",
            "1",
            "1",
            "t",
            "c",
            "",
        )

        result = loader.parse_dispatch_sheet_row(
            row, spreadsheet_id, owner_nations, category_setups
        )

        assert result == Dispatch(
            "1",
            DispatchOperation.EDIT,
            "n",
            "t",
            "meta",
            "gameplay",
            "c",
        )

    def test_no_ns_id_returns_dispatch_obj_with_no_ns_id(
        self, owner_nations, category_setups
    ):
        spreadsheet_id = "s"
        row = DispatchRow("n", "edit", "1", "1", "t", "c", "")

        result = loader.parse_dispatch_sheet_row(
            row, spreadsheet_id, owner_nations, category_setups
        )

        assert result.ns_id is None

    def test_empty_dispatch_name_raises_skip_exception(
        self, owner_nations, category_setups
    ):
        spreadsheet_id = "s"
        row = DispatchRow("", "edit", "1", "1", "t", "c", "")

        with pytest.raises(loader.SkipRow):
            loader.parse_dispatch_sheet_row(
                row, spreadsheet_id, owner_nations, category_setups
            )

    def test_empty_action_raises_skip_exception(self, owner_nations, category_setups):
        spreadsheet_id = "s"
        row = DispatchRow("n", "", "1", "1", "t", "c", "")

        with pytest.raises(loader.SkipRow):
            loader.parse_dispatch_sheet_row(
                row, spreadsheet_id, owner_nations, category_setups
            )

    def test_invalid_action_raises_invalid_data_exception(
        self, owner_nations, category_setups
    ):
        spreadsheet_id = "s"
        row = DispatchRow("n", "a", "1", "1", "t", "c", "")

        with pytest.raises(loader.InvalidDispatchDataError):
            loader.parse_dispatch_sheet_row(
                row, spreadsheet_id, owner_nations, category_setups
            )

    def test_empty_title_raises_invalid_exception(self, owner_nations, category_setups):
        spreadsheet_id = "s"
        row = DispatchRow("n", "create", "1", "1", "", "c", "")

        with pytest.raises(loader.InvalidDispatchDataError):
            loader.parse_dispatch_sheet_row(
                row, spreadsheet_id, owner_nations, category_setups
            )

    def test_owner_id_not_found_raises_invalid_data_exception(
        self, owner_nations, category_setups
    ):
        spreadsheet_id = "s"
        row = DispatchRow("n", "create", "0", "1", "t", "c", "")

        with pytest.raises(loader.InvalidDispatchDataError):
            loader.parse_dispatch_sheet_row(
                row, spreadsheet_id, owner_nations, category_setups
            )

    def test_owner_id_not_permitted_raises_invalid_data_exception(
        self, owner_nations, category_setups
    ):
        spreadsheet_id = "s2"
        row = DispatchRow("n", "create", "1", "1", "t", "c", "")

        with pytest.raises(loader.InvalidDispatchDataError):
            loader.parse_dispatch_sheet_row(
                row, spreadsheet_id, owner_nations, category_setups
            )

    def test_category_setup_id_not_found_raises_invalid_data_exception(
        self, owner_nations, category_setups
    ):
        spreadsheet_id = "s"
        row = DispatchRow("n", "create", "1", "0", "t", "c", "")

        with pytest.raises(loader.InvalidDispatchDataError):
            loader.parse_dispatch_sheet_row(
                row, spreadsheet_id, owner_nations, category_setups
            )

    def test_empty_content_uses_empty_string_on_content_field(
        self, owner_nations, category_setups
    ):
        spreadsheet_id = "s"
        row = DispatchRow("n", "create", "1", "1", "t", "", "")

        result = loader.parse_dispatch_sheet_row(
            row, spreadsheet_id, owner_nations, category_setups
        )

        assert result.content == ""


class TestFlattenDispatchSheetConfig:
    def test_empty_config_returns_empty_list(self):
        config = []

        result = loader.flatten_spreadsheet_config(config)

        assert result == []

    def test_many_spreadsheets_with_empty_range_returns_empty_list(self):
        config = [
            {"spreadsheet_id": "s1", "ranges": []},
            {"spreadsheet_id": "s2", "ranges": []},
        ]

        result = loader.flatten_spreadsheet_config(config)

        assert result == []

    def test_many_spreadsheets_with_many_ranges_returns_flatten_list(self):
        config = [
            {"spreadsheet_id": "s1", "ranges": ["r1", "r2"]},
            {"spreadsheet_id": "s2", "ranges": ["r3", "r4"]},
        ]

        result = loader.flatten_spreadsheet_config(config)

        assert result == [
            loader.SheetRange("s1", "r1"),
            loader.SheetRange("s1", "r2"),
            loader.SheetRange("s2", "r3"),
            loader.SheetRange("s2", "r4"),
        ]


class TestGoogleDispatchLoader:
    @pytest.fixture(scope="class")
    def prepared_loader(self):
        owner_nations = loader.OwnerNationStore(
            {"1": OwnerNation("nation1", ["s"]), "2": OwnerNation("nation2", ["s"])}
        )
        category_setups = loader.CategorySetupStore(
            {"1": CategorySetup("meta", "gameplay")}
        )

        range_1_rows = [
            DispatchRow("n1", "create", "1", "1", "t1", "tp1", ""),
            DispatchRow(
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=2","n2")',
                "edit",
                "1",
                "1",
                "t2",
                "tp2",
                "stat2",
            ),
        ]
        range_2_rows = [
            DispatchRow(
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=3","n3")',
                "edit",
                "2",
                "1",
                "t3",
                "tp3",
                "stat3",
            ),
        ]
        dispatch_ranges = {
            SheetRange("s", "A!A1:F"): range_1_rows,
            SheetRange("s", "B!A1:F"): range_2_rows,
        }
        dispatches = loader.DispatchConfigStore(
            loader.parse_dispatch_sheet_ranges(
                dispatch_ranges, owner_nations, category_setups, Mock()
            )
        )

        utility_templates = {"u": "utp"}

        return loader.GoogleDispatchLoader(
            Mock(),
            dispatch_ranges,
            dispatches,
            utility_templates,
            owner_nations,
            category_setups,
            Mock(),
        )

    def test_get_dispatch_config_with_many_dispatches_returns_correct_dict_structure(
        self, prepared_loader
    ):
        result = prepared_loader.get_dispatch_config()

        assert result == {
            "nation1": {
                "n1": {
                    "action": "create",
                    "title": "t1",
                    "category": "meta",
                    "subcategory": "gameplay",
                },
                "n2": {
                    "action": "edit",
                    "ns_id": "2",
                    "title": "t2",
                    "category": "meta",
                    "subcategory": "gameplay",
                },
            },
            "nation2": {
                "n3": {
                    "action": "edit",
                    "ns_id": "3",
                    "title": "t3",
                    "category": "meta",
                    "subcategory": "gameplay",
                }
            },
        }

    def test_get_utility_dispatch_template_returns_correct_template(
        self, prepared_loader
    ):
        result = prepared_loader.get_dispatch_template("u")

        assert result == "utp"

    def test_get_normal_dispatch_template_returns_correct_template(
        self, prepared_loader
    ):
        result = prepared_loader.get_dispatch_template("n1")

        assert result == "tp1"

    def test_update_spreadsheets_after_new_dispatch_created_changes_its_operation_to_edit(
        self,
    ):
        owner_nations = loader.OwnerNationStore({"1": OwnerNation("nation1", ["s"])})
        category_setups = loader.CategorySetupStore(
            {"1": CategorySetup("meta", "gameplay")}
        )
        utility_templates = {}
        range_1_rows = [DispatchRow("n", "create", "1", "1", "t", "tp", "")]
        dispatch_ranges = {
            SheetRange("s", "A!A1:F"): range_1_rows,
        }
        dispatches = loader.DispatchConfigStore(
            loader.parse_dispatch_sheet_ranges(
                dispatch_ranges, owner_nations, category_setups, Mock()
            )
        )
        sheets_api = mock.create_autospec(loader.GoogleSheetsApiAdapter)
        op_result_store = loader.OpResultStore()
        obj = loader.GoogleDispatchLoader(
            sheets_api,
            dispatch_ranges,
            dispatches,
            utility_templates,
            owner_nations,
            category_setups,
            op_result_store,
        )

        obj.add_dispatch_id("n", "1")
        obj.report_result(
            "n",
            DispatchOperation.CREATE,
            "success",
            datetime(2023, 1, 1),
        )
        obj.update_spreadsheets()

        new_range = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1","n")',
                "edit",
                "1",
                "1",
                "t",
                "tp",
                "Created successfully.\nTime: 2023/01/01 00:00:00 ",
            ]
        ]
        new_spreadsheets = {loader.SheetRange("s", "A!A1:F"): new_range}
        sheets_api.update_values_of_ranges.assert_called_with(new_spreadsheets)
