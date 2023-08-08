from datetime import datetime, timezone
from unittest import mock

import freezegun
import pytest

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
        result = api.get_data_from_range(range)

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

        ranges = [loader.SheetRange("1234abcd", "Foo!A1:F")]
        result = api.get_data_from_ranges(ranges)

        assert result == {ranges[0]: [["hello"]]}

    def test_get_cell_data_of_empty_range_returns_empty_list(self):
        resp = {
            "spreadsheetId": "1234abcd",
            "valueRanges": [{"range": "Foo!A1:F", "majorDimension": "ROWS"}],
        }
        request = mock.Mock(execute=mock.Mock(return_value=resp))
        google_api = mock.Mock(batchGet=mock.Mock(return_value=request))
        api = loader.GoogleSpreadsheetApiAdapter(google_api)

        range = loader.SheetRange("1234abcd", "Foo!A1:F")
        result = api.get_data_from_range(range)

        assert not result

    def test_get_cell_data_of_empty_ranges_returns_empty_list(self):
        resp = {
            "spreadsheetId": "1234abcd",
            "valueRanges": [{"range": "Foo!A1:F", "majorDimension": "ROWS"}],
        }
        request = mock.Mock(execute=mock.Mock(return_value=resp))
        google_api = mock.Mock(batchGet=mock.Mock(return_value=request))
        api = loader.GoogleSpreadsheetApiAdapter(google_api)

        ranges = [loader.SheetRange("1234abcd", "Foo!A1:F")]
        result = api.get_data_from_ranges(ranges)

        assert result == {ranges[0]: []}

    def test_update_cell_data_of_many_ranges(self):
        google_api = mock.Mock()
        api = loader.GoogleSpreadsheetApiAdapter(google_api)

        new_cell_data = {loader.SheetRange("1234abcd", "Foo!A1:F"): [["hello"]]}
        api.update_cells(new_cell_data)

        expected_body = {
            "valueInputOption": "USER_ENTERED",
            "data": [
                {"range": "Foo!A1:F", "majorDimension": "ROWS", "values": [["hello"]]}
            ],
        }
        google_api.batchUpdate.assert_called_with(
            spreadsheetId="1234abcd", body=expected_body
        )


class TestOperationResult:
    def test_get_success_result_message_returns_formatted_message(self):
        result = loader.SuccessOpResult(
            "name", loader.DispatchOperation.CREATE, datetime(2023, 1, 1)
        )

        assert (
            result.result_message == "Created successfully.\nTime: 2023/01/01 00:00:00 "
        )

    def test_get_failure_result_message_returns_formatted_message(self):
        result = loader.FailureOpResult(
            "name",
            loader.DispatchOperation.CREATE,
            datetime(2023, 1, 1),
            "Some details.",
        )

        assert (
            result.result_message
            == "Failed to create.\nDetails: Some details.\nTime: 2023/01/01 00:00:00 "
        )


class TestOperationResultStore:
    def test_report_success_adds_success_result(self):
        obj = loader.OperationResultStore()

        obj.report_success("n", loader.DispatchOperation.CREATE, datetime(2023, 1, 1))
        result = obj["n"]

        assert result == loader.SuccessOpResult(
            "n", loader.DispatchOperation.CREATE, datetime(2023, 1, 1)
        )

    @freezegun.freeze_time('2023-01-01')
    def test_report_success_with_no_result_time_uses_current_time_as_result_time(self):
        obj = loader.OperationResultStore()

        obj.report_success("n", loader.DispatchOperation.CREATE)
        result = obj["n"].result_time

        assert result == datetime(2023, 1, 1, tzinfo=timezone.utc)

    def test_report_failure_with_no_details_adds_no_details_failure_result(self):
        obj = loader.OperationResultStore()

        obj.report_failure(
            "n", loader.DispatchOperation.CREATE, None, datetime(2023, 1, 1)
        )
        result = obj["n"]

        assert isinstance(result, loader.FailureOpResult) and result.details is None

    def test_report_failure_with_str_details_adds_failure_result_with_str_details(
        self,
    ):
        obj = loader.OperationResultStore()

        obj.report_failure(
            "n", loader.DispatchOperation.CREATE, "d", datetime(2023, 1, 1)
        )
        result = obj["n"]

        assert isinstance(result, loader.FailureOpResult) and result.details == "d"

    def test_report_failure_with_exception_details_adds_failure_result_with_exception_msg_details(
        self,
    ):
        obj = loader.OperationResultStore()

        obj.report_failure(
            "n", loader.DispatchOperation.CREATE, Exception("d"), datetime(2023, 1, 1)
        )
        result = obj["n"]

        assert isinstance(result, loader.FailureOpResult) and result.details == "d"

    def test_report_failure_with_invalid_op_adds_failure_result_with_invalid_op_name(self):
        obj = loader.OperationResultStore()

        obj.report_failure("n", "a", details="d")
        result = obj['n'].operation

        assert result == "a"

    @freezegun.freeze_time('2023-01-01')
    def test_report_failure_with_no_result_time_uses_current_time_as_result_time(self):
        obj = loader.OperationResultStore()

        obj.report_failure("n", loader.DispatchOperation.CREATE, details="d")
        result = obj['n'].result_time

        assert result == datetime(2023, 1, 1, tzinfo=timezone.utc)


class TestCategorySetupData:
    def test_get_category_subcategory_name_returns_name(self):
        categories = {"id1": "Meta"}
        subcategories = {"id1": "Gameplay"}
        setups = loader.CategorySetupData(categories, subcategories)

        category_name, subcategory_name = setups.get_category_subcategory_name("id1")

        assert category_name == "Meta" and subcategory_name == "Gameplay"

    def test_get_category_subcategory_of_non_existent_id_raises_exception(self):
        category_setups = loader.CategorySetupData({}, {})

        with pytest.raises(KeyError):
            category_setups.get_category_subcategory_name("id1")

    def test_load_category_setup_data_from_cell_data(self):
        cell_data = [["id1", "Meta", "Gameplay"]]

        category_setups = loader.CategorySetupData.load_from_range_cell_data(cell_data)

        assert category_setups.categories == {
            "id1": "Meta"
        } and category_setups.subcategories == {"id1": "Gameplay"}

    def test_load_category_setup_data_from_cell_data_uses_last_identical_setup_id(self):
        cell_data = [["id1", "Meta", "Gameplay"], ["id1", "Overview", "Factbook"]]

        category_setups = loader.CategorySetupData.load_from_range_cell_data(cell_data)

        assert category_setups.categories == {
            "id1": "Overview"
        } and category_setups.subcategories == {"id1": "Factbook"}


class TestOwnerNationData:
    def test_get_owner_nation_name_returns_name(self):
        owner_nation_names = {"id1": "nation1"}
        allowed_spreadsheet_ids = {"id1": ["s1"]}

        owner_nations = loader.OwnerNationData(
            owner_nation_names, allowed_spreadsheet_ids
        )

        assert owner_nations.get_owner_nation_name("id1") == "nation1"

    def test_get_non_existent_owner_nation_name_raises_exception(self):
        owner_nations = loader.OwnerNationData({}, {})

        with pytest.raises(KeyError):
            owner_nations.get_owner_nation_name("id1")

    def test_check_permission_on_allowed_spreadsheet_returns_true(self):
        owner_nation_names = {"id1": "nation1"}
        allowed_spreadsheet_ids = {"id1": ["s1"]}

        owner_nations = loader.OwnerNationData(
            owner_nation_names, allowed_spreadsheet_ids
        )

        assert owner_nations.check_spreadsheet_permission("id1", "s1")

    def test_check_permission_on_non_allowed_spreadsheet_returns_false(self):
        owner_nation_names = {"id1": "nation1"}
        allowed_spreadsheet_ids = {"id1": ["s1"]}

        owner_nations = loader.OwnerNationData(
            owner_nation_names, allowed_spreadsheet_ids
        )

        assert not owner_nations.check_spreadsheet_permission("id1", "s2")

    def test_check_permission_on_non_existent_owner_id_raises_exception(self):
        owner_nations = loader.OwnerNationData({}, {})

        with pytest.raises(KeyError):
            owner_nations.check_spreadsheet_permission("id1", "s1")

    def test_load_owner_nation_data_from_cell_data(self):
        cell_data = [["id1", "nation1", "s1,s2"]]

        owner_nations = loader.OwnerNationData.load_from_range_cell_data(cell_data)

        assert owner_nations.owner_nation_names == {
            "id1": "nation1"
        } and owner_nations.allowed_spreadsheet_ids == {"id1": ["s1", "s2"]}

    def test_load_owner_nation_data_from_cell_data_uses_last_identical_owner_id(self):
        cell_data = [["id1", "nation1", "s1,s2"], ["id1", "nation2", "s2,s3"]]

        owner_nations = loader.OwnerNationData.load_from_range_cell_data(cell_data)

        assert owner_nations.owner_nation_names == {
            "id1": "nation2"
        } and owner_nations.allowed_spreadsheet_ids == {"id1": ["s2", "s3"]}


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
    def test_returns_templates(self):
        range_data = [["layout1", "abcd"]]
        ranges = {loader.SheetRange("abcd1234", "Layout!A1:B"): range_data}

        result = loader.parse_utility_template_cell_ranges(ranges)

        assert result == {"layout1": "abcd"}

    def test_returns_last_identical_template(self):
        range_data = [["layout1", "abcd"], ["layout1", "xyzt"]]
        ranges = {loader.SheetRange("abcd1234", "Layout!A1:B"): range_data}

        result = loader.parse_utility_template_cell_ranges(ranges)

        assert result == {"layout1": "xyzt"}


class TestDispatchData:
    def test_get_canonical_dispatch_config_id_exists_returns_canonical_config(self):
        dispatch_data = {
            "name1": loader.Dispatch(
                ns_id="12345",
                owner_nation="testopia",
                operation=loader.DispatchOperation.EDIT,
                title="Hello Title",
                content="Hello World",
                category="meta",
                subcategory="gameplay",
            )
        }
        obj = loader.DispatchData(dispatch_data)

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
            "name1": loader.Dispatch(
                ns_id=None,
                owner_nation="testopia",
                operation=loader.DispatchOperation.CREATE,
                title="Hello Title",
                content="Hello World",
                category="meta",
                subcategory="gameplay",
            )
        }
        obj = loader.DispatchData(dispatch_data)

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
            "name1": loader.Dispatch(
                ns_id="12345",
                owner_nation="testopia",
                operation=loader.DispatchOperation.EDIT,
                title="Hello Title",
                content="Hello World",
                category="meta",
                subcategory="gameplay",
            )
        }
        obj = loader.DispatchData(dispatch_data)

        assert obj.get_dispatch_template("name1") == "Hello World"

    def test_get_non_existent_dispatch_template_raises_exception(self):
        obj = loader.DispatchData({})

        with pytest.raises(KeyError):
            obj.get_dispatch_template("something non existent")

    def test_add_dispatch_id_adds_id_into_new_dispatch(self):
        dispatch_data = {
            "name1": loader.Dispatch(
                ns_id=None,
                owner_nation="testopia",
                operation=loader.DispatchOperation.CREATE,
                title="Hello Title",
                content="Hello World",
                category="meta",
                subcategory="gameplay",
            )
        }
        obj = loader.DispatchData(dispatch_data)

        obj.add_dispatch_id("name1", "54321")

        assert obj["name1"].ns_id == "54321"

    def test_add_dispatch_id_overrides_old_id(self):
        dispatch_data = {
            "name1": loader.Dispatch(
                ns_id="12345",
                owner_nation="testopia",
                operation=loader.DispatchOperation.EDIT,
                title="Hello Title",
                content="Hello World",
                category="meta",
                subcategory="gameplay",
            )
        }
        obj = loader.DispatchData(dispatch_data)

        obj.add_dispatch_id("name1", "54321")

        assert obj["name1"].ns_id == "54321"


@pytest.fixture
def owner_nations():
    return loader.OwnerNationData({"1": "nation1"}, {"1": ["s1"]})


@pytest.fixture
def category_setups():
    return loader.CategorySetupData({"1": "meta"}, {"1": "gameplay"})


class TestParseDispatchDataRow:
    def test_ns_id_exists_returns_dispatch_obj_with_ns_id(
        self, owner_nations, category_setups
    ):
        spreadsheet_id = "s1"
        row_data = [
            '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
            "edit",
            1,
            1,
            "Title",
            "Text",
        ]

        dispatch = loader.parse_dispatch_data_row(
            row_data, spreadsheet_id, owner_nations, category_setups
        )

        assert dispatch == loader.Dispatch(
            "1234",
            loader.DispatchOperation.EDIT,
            "nation1",
            "Title",
            "meta",
            "gameplay",
            "Text",
        )

    def test_no_ns_id_returns_dispatch_obj_with_no_ns_id(
        self, owner_nations, category_setups
    ):
        spreadsheet_id = "s1"
        row_data = ["name1", "edit", 1, 1, "Title", "Text"]

        dispatch = loader.parse_dispatch_data_row(
            row_data, spreadsheet_id, owner_nations, category_setups
        )

        assert not dispatch.ns_id

    def test_empty_dispatch_name_raises_skip_exception(
        self, owner_nations, category_setups
    ):
        spreadsheet_id = "s1"
        row_data = ["", "edit", 1, 1, "Title", "Text"]

        with pytest.raises(loader.SkipRow):
            loader.parse_dispatch_data_row(
                row_data, spreadsheet_id, owner_nations, category_setups
            )

    def test_empty_action_raises_skip_exception(self, owner_nations, category_setups):
        spreadsheet_id = "s1"
        row_data = [
            '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
            "",
            1,
            1,
            "Title",
            "Text",
        ]

        with pytest.raises(loader.SkipRow):
            loader.parse_dispatch_data_row(
                row_data, spreadsheet_id, owner_nations, category_setups
            )

    def test_invalid_action_raises_invalid_data_exception(
        self, owner_nations, category_setups
    ):
        spreadsheet_id = "s1"
        row_data = [
            '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
            "something invalid",
            1,
            1,
            "Title",
            "Text",
        ]

        with pytest.raises(loader.InvalidDispatchDataError):
            loader.parse_dispatch_data_row(
                row_data, spreadsheet_id, owner_nations, category_setups
            )

    def test_not_enough_filled_cells_with_valid_action_and_name_raises_invalid_exception(
        self, owner_nations, category_setups
    ):
        spreadsheet_id = "s1"
        row_data = [
            '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
            "edit",
            1,
            1,
        ]

        with pytest.raises(loader.InvalidDispatchDataError):
            loader.parse_dispatch_data_row(
                row_data, spreadsheet_id, owner_nations, category_setups
            )

    def test_empty_owner_id_raises_invalid_data_exception(
        self, owner_nations, category_setups
    ):
        spreadsheet_id = "s1"
        row_data = [
            '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
            "edit",
            "",
            1,
            "Title",
            "Text",
        ]

        with pytest.raises(loader.InvalidDispatchDataError):
            loader.parse_dispatch_data_row(
                row_data, spreadsheet_id, owner_nations, category_setups
            )

    def test_owner_id_not_found_raises_invalid_data_exception(
        self, owner_nations, category_setups
    ):
        spreadsheet_id = "s1"
        row_data = [
            '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
            "edit",
            2,
            1,
            "Title",
            "Text",
        ]

        with pytest.raises(loader.InvalidDispatchDataError):
            loader.parse_dispatch_data_row(
                row_data, spreadsheet_id, owner_nations, category_setups
            )

    def test_owner_id_not_permitted_raises_invalid_data_exception(
        self, owner_nations, category_setups
    ):
        spreadsheet_id = "s2"
        row_data = [
            '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
            "edit",
            1,
            1,
            "Title",
            "Text",
        ]

        with pytest.raises(loader.InvalidDispatchDataError):
            loader.parse_dispatch_data_row(
                row_data, spreadsheet_id, owner_nations, category_setups
            )

    def test_empty_category_setup_id_raises_invalid_data_exception(
        self, owner_nations, category_setups
    ):
        spreadsheet_id = "s1"
        row_data = [
            '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
            "edit",
            1,
            "",
            "Title",
            "Text",
        ]

        with pytest.raises(loader.InvalidDispatchDataError):
            loader.parse_dispatch_data_row(
                row_data, spreadsheet_id, owner_nations, category_setups
            )

    def test_category_setup_id_not_found_raises_invalid_data_exception(
        self, owner_nations, category_setups
    ):
        spreadsheet_id = "s1"
        row_data = [
            '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
            "edit",
            1,
            2,
            "Title",
            "Text",
        ]

        with pytest.raises(loader.InvalidDispatchDataError):
            loader.parse_dispatch_data_row(
                row_data, spreadsheet_id, owner_nations, category_setups
            )

    def test_title_not_found_raises_invalid_data_exception(
        self, owner_nations, category_setups
    ):
        spreadsheet_id = "s1"
        row_data = [
            '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
            "edit",
            1,
            1,
            "",
            "Text",
        ]

        with pytest.raises(loader.InvalidDispatchDataError):
            loader.parse_dispatch_data_row(
                row_data, spreadsheet_id, owner_nations, category_setups
            )

    def test_content_not_found_uses_empty_string_on_content_field(
        self, owner_nations, category_setups
    ):
        spreadsheet_id = "s1"
        row_data = [
            '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
            "edit",
            1,
            1,
            "Title",
        ]

        dispatch = loader.parse_dispatch_data_row(
            row_data, spreadsheet_id, owner_nations, category_setups
        )

        assert dispatch.content == ""

    def test_can_parse_extra_useless_cells(self, owner_nations, category_setups):
        spreadsheet_id = "s1"
        row_data = [
            '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
            "edit",
            1,
            1,
            "Title",
            "Text",
            "something",
            "else",
        ]

        dispatch = loader.parse_dispatch_data_row(
            row_data, spreadsheet_id, owner_nations, category_setups
        )

        assert dispatch == loader.Dispatch(
            "1234",
            loader.DispatchOperation.EDIT,
            "nation1",
            "Title",
            "meta",
            "gameplay",
            "Text",
        )


class TestGoogleDispatchLoader:
    def test_get_dispatch_config(self):
        range_data_1 = [
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
        range_data_2 = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=4321","name3")',
                "delete",
                2,
                1,
                "Title 3",
                "Text 3",
                "Edited on 2021/01/01 01:00:00 UTC",
            ]
        ]
        dispatch_spreadsheets = {
            loader.SheetRange("abcd1234", "Sheet1!A3:F"): range_data_1,
            loader.SheetRange("xyzt1234", "Sheet2!A3:F"): range_data_2,
        }

        owner_nation_rows = [[1, "Testopia", "abcd1234"], [2, "Cooltopia", "xyzt1234"]]
        category_rows = [[1, "Meta", "Gameplay"], [2, "Meta", "Reference"]]

        obj = loader.GoogleDispatchLoader(
            mock.Mock(),
            dispatch_spreadsheets,
            {},
            owner_nation_rows,
            category_rows,
        )

        result = obj.get_dispatch_config()

        assert result == {
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
        range_data = [["layout1", "abcd"]]
        utility_template_ranges = {
            loader.SheetRange("abcd1234", "Layout!A1:B"): range_data
        }

        obj = loader.GoogleDispatchLoader(
            mock.Mock(), {}, utility_template_ranges, [], []
        )

        result = obj.get_dispatch_template("layout1")

        assert result == "abcd"

    def test_get_dispatch_template_of_normal_dispatch(self):
        range1 = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                "edit",
                1,
                1,
                "Hello Title",
                "Hello World",
                "Edited on 2021/01/01 01:00:00 UTC",
            ]
        ]
        dispatch_spreadsheets = {loader.SheetRange("abcd1234", "Sheet1!A3:F"): range1}

        owner_nation_rows = [[1, "Testopia", "abcd1234"]]
        category_rows = [[1, "Meta", "Gameplay"]]
        obj = loader.GoogleDispatchLoader(
            mock.Mock(),
            dispatch_spreadsheets,
            {},
            owner_nation_rows,
            category_rows,
        )

        result = obj.get_dispatch_template("name1")

        assert result == "Hello World"

    def test_update_spreadsheets_after_new_dispatch_created(self):
        range1 = [["name1", "create", 1, 1, "Hello Title", "Hello World"]]
        dispatch_spreadsheets = {loader.SheetRange("abcd1234", "Sheet1!A3:F"): range1}
        owner_nation_rows = [[1, "Testopia", "abcd1234"]]
        category_rows = [[1, "Meta", "Gameplay"]]
        spreadsheet_api = mock.Mock(spec=loader.GoogleSpreadsheetApiAdapter)
        obj = loader.GoogleDispatchLoader(
            spreadsheet_api,
            dispatch_spreadsheets,
            {},
            owner_nation_rows,
            category_rows,
        )

        obj.add_dispatch_id("name1", "1234")
        obj.report_result(
            "name1",
            loader.DispatchOperation.CREATE,
            "success",
            datetime(2023, 1, 1),
        )
        obj.update_spreadsheets()

        new_range = [
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","name1")',
                "edit",
                1,
                1,
                "Hello Title",
                "Hello World",
                "Created successfully.\nTime: 2023/01/01 00:00:00 ",
            ]
        ]
        new_spreadsheets = {loader.SheetRange("abcd1234", "Sheet1!A3:F"): new_range}
        spreadsheet_api.update_cells.assert_called_with(new_spreadsheets)


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
