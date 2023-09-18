import logging
from datetime import datetime, timezone
from unittest import mock
from unittest.mock import Mock

import freezegun
import pytest

from nsdu.loader_api import DispatchMetadata, DispatchOp, DispatchOpResult
from nsdu.loaders import google_dispatch_loader as loader
from nsdu.loaders.google_dispatch_loader import (
    CategorySetup,
    Dispatch,
    DispatchRow,
    FailureOpResult,
    InvalidDispatchRowError,
    OwnerNation,
    SheetRange,
    SkipRow,
    SuccessOpResult,
    UtilityTemplateRow,
)


class TestGoogleSheetsApiAdapter:
    @pytest.mark.parametrize("range_cell_values", [[[["v"]]], [[]]])
    def test_get_values_of_a_range_returns_cell_values_of_range(
        self, range_cell_values
    ):
        api_resp = {
            "spreadsheetId": "s",
            "valueRanges": [
                {
                    "range": "A!A1:F",
                    "majorDimension": "ROWS",
                    "values": range_cell_values,
                }
            ],
        }
        request = Mock(execute=Mock(return_value=api_resp))
        google_api = Mock(batchGet=Mock(return_value=request))
        api = loader.GoogleSheetsApiAdapter(google_api)

        sheet_range = SheetRange("s", "A!A1:F")
        result = api.get_values_of_range(sheet_range)

        assert result == range_cell_values

    @pytest.mark.parametrize(
        "range_resp,expected",
        [
            [
                [
                    {"range": "A!A1:F", "majorDimension": "ROWS", "values": [["v1"]]},
                    {"range": "B!A1:F", "majorDimension": "ROWS", "values": [["v2"]]},
                ],
                {
                    SheetRange("s", "A!A1:F"): [["v1"]],
                    SheetRange("s", "B!A1:F"): [["v2"]],
                },
            ],
            [
                [
                    {"range": "A!A1:F", "majorDimension": "ROWS"},
                    {"range": "B!A1:F", "majorDimension": "ROWS"},
                ],
                {SheetRange("s", "A!A1:F"): [], SheetRange("s", "B!A1:F"): []},
            ],
        ],
    )
    def test_get_values_of_many_ranges_returns_cell_values_of_ranges(
        self, range_resp, expected
    ):
        api_resp = {"spreadsheetId": "s", "valueRanges": range_resp}
        request = Mock(execute=Mock(return_value=api_resp))
        google_api = Mock(batchGet=Mock(return_value=request))
        api = loader.GoogleSheetsApiAdapter(google_api)

        ranges = [SheetRange("s", "A!A1:F"), SheetRange("s", "B!A1:F")]
        result = api.get_values_of_ranges(ranges)

        assert result == expected

    def test_update_values_of_many_ranges_makes_correct_api_client_call(self):
        google_api = Mock()
        api = loader.GoogleSheetsApiAdapter(google_api)

        new_values = {SheetRange("s", "A!A1:F"): [["v"]]}
        api.update_values_of_ranges(new_values)

        expected_body = {
            "valueInputOption": "USER_ENTERED",
            "data": [{"range": "A!A1:F", "majorDimension": "ROWS", "values": [["v"]]}],
        }
        google_api.batchUpdate.assert_called_with(spreadsheetId="s", body=expected_body)


class TestOpResult:
    def test_get_success_result_message_returns_formatted_message(self):
        result = SuccessOpResult("name", DispatchOp.CREATE, datetime(2023, 1, 1))

        assert (
            result.result_message == "Created successfully.\nTime: 2023/01/01 00:00:00 "
        )

    def test_get_failure_result_message_returns_formatted_message(self):
        result = FailureOpResult(
            "name",
            DispatchOp.CREATE,
            datetime(2023, 1, 1),
            "Some details.",
        )

        assert (
            result.result_message
            == "Failed to create.\nDetails: Some details.\nTime: 2023/01/01 00:00:00 "
        )


class TestOpResultStore:
    @pytest.mark.parametrize(
        "result_time,expected",
        [
            [datetime(2022, 1, 1), datetime(2022, 1, 1)],
            [None, datetime(2023, 1, 1, tzinfo=timezone.utc)],
        ],
    )
    @freezegun.freeze_time("2023-01-01")
    def test_report_success_adds_success_result(self, result_time, expected):
        obj = loader.OpResultStore()

        obj.report_success("n", DispatchOp.CREATE, result_time)
        result = obj["n"]

        assert result == SuccessOpResult("n", DispatchOp.CREATE, expected)

    @pytest.mark.parametrize(
        "err_details,result_time,expected_err_details,expected_result_time",
        [
            [
                Exception("e"),
                datetime(2023, 1, 1),
                "e",
                datetime(2023, 1, 1),
            ],
            ["d", datetime(2023, 1, 1), "d", datetime(2023, 1, 1)],
            [None, datetime(2022, 1, 1), None, datetime(2022, 1, 1)],
            [None, None, None, datetime(2023, 1, 1, tzinfo=timezone.utc)],
        ],
    )
    @freezegun.freeze_time("2023-01-01")
    def test_report_failure_adds_failure_result(
        self, err_details, result_time, expected_err_details, expected_result_time
    ):
        obj = loader.OpResultStore()

        obj.report_failure("n", DispatchOp.CREATE, err_details, result_time)
        result = obj["n"]

        assert result == FailureOpResult(
            "n", DispatchOp.CREATE, expected_result_time, expected_err_details
        )


class TestCategorySetupStore:
    def test_get_setup_returns_setup(self):
        setups = {"1": loader.CategorySetup("meta", "gameplay")}
        obj = loader.CategorySetupStore(setups)

        result = obj["1"]

        assert result == CategorySetup("meta", "gameplay")

    def test_get_setup_of_non_existent_id_raises_exception(self):
        category_setups = loader.CategorySetupStore({})

        with pytest.raises(KeyError):
            category_setups["1"]

    @pytest.mark.parametrize(
        "cell_values,expected",
        [
            [
                [[1, "meta", "gameplay"], [2, "meta", "reference"]],
                {
                    "1": CategorySetup("meta", "gameplay"),
                    "2": CategorySetup("meta", "reference"),
                },
            ],
            [[[1, "Meta", "Gameplay"]], {"1": CategorySetup("meta", "gameplay")}],
            [
                [[1, "meta", "gameplay"], [1, "overview", "factbook"]],
                {"1": CategorySetup("overview", "factbook")},
            ],
            [
                [[1, "", ""], [2, "meta", "reference"]],
                {"2": CategorySetup("meta", "reference")},
            ],
            [[], {}],
        ],
    )
    def test_load_from_range_cell_values_returns_obj(self, cell_values, expected):
        result = loader.CategorySetupStore.load_from_range_cell_values(cell_values)

        assert result == expected


class TestOwnerNationData:
    def test_get_owner_nation_returns_nation(self):
        owner_nations = {"1": loader.OwnerNation("n", [])}
        obj = loader.OwnerNationStore(owner_nations)

        result = obj["1"]

        assert result == OwnerNation("n", [])

    def test_get_non_existent_owner_nation_raises_exception(self):
        obj = loader.OwnerNationStore({})

        with pytest.raises(KeyError):
            obj["1"]

    @pytest.mark.parametrize("spreadsheet,expected", [["s", True], ["ss", False]])
    def test_check_spreadsheet_permission_returns_permission(
        self, spreadsheet, expected
    ):
        owner_nations = {"1": loader.OwnerNation("n", ["s"])}
        obj = loader.OwnerNationStore(owner_nations)

        result = obj.check_spreadsheet_permission("1", spreadsheet)

        assert result == expected

    def test_check_permission_of_non_existent_owner_raises_exception(self):
        obj = loader.OwnerNationStore({})

        with pytest.raises(KeyError):
            obj.check_spreadsheet_permission("1", "s")

    @pytest.mark.parametrize(
        "cell_values,expected",
        [
            [
                [["1", "n1", "s1,s2"], ["2", "n2", "s1"]],
                {"1": OwnerNation("n1", ["s1", "s2"]), "2": OwnerNation("n2", ["s1"])},
            ],
            [
                [["1", "n1", "s1"], ["1", "n2", "s2"]],
                {"1": OwnerNation("n2", ["s2"])},
            ],
            [[["1", "n", ""]], {"1": OwnerNation("n", [])}],
            [[["1", "", ""], ["2", "n2", "s1"]], {"2": OwnerNation("n2", ["s1"])}],
            [[], {}],
        ],
    )
    def test_load_from_range_cell_values_returns_obj(self, cell_values, expected):
        obj = loader.OwnerNationStore.load_from_range_cell_values(cell_values)

        assert obj == expected


@pytest.mark.parametrize(
    "hyperlink,expected",
    [
        [
            '=hyperlink("https://www.nationstates.net/page=dispatch/id=1234","abc")',
            "abc",
        ],
        ["xyz", "xyz"],
        ["", ""],
    ],
)
def test_extract_name_from_hyperlink_returns_name(hyperlink, expected):
    result = loader.extract_name_from_hyperlink(hyperlink)

    assert result == expected


@pytest.mark.parametrize(
    "hyperlink,expected",
    [
        [
            '=hyperlink("https://www.nationstates.net/page=dispatch/id=1","abc")',
            "1",
        ],
        ["xyz", None],
        ["", None],
    ],
)
def test_extract_dispatch_id_from_hyperlink_returns_dispatch_id(hyperlink, expected):
    result = loader.extract_dispatch_id_from_hyperlink(hyperlink)

    assert result == expected


class TestUtilityTemplateRow:
    @pytest.mark.parametrize(
        "row,expected",
        [
            [["u", "utp"], UtilityTemplateRow("u", "utp")],
            [["u"], UtilityTemplateRow("u", "")],
            [[], UtilityTemplateRow("", "")],
        ],
    )
    def test_create_from_api_row_returns_obj(self, row, expected):
        result = UtilityTemplateRow.from_api_row(row)

        assert result == expected

    @pytest.mark.parametrize(
        "row,expected",
        [
            [
                {
                    SheetRange("s", "a"): [["u1", "utp1"], ["u2", "utp2"]],
                    SheetRange("s", "b"): [["u3", "utp3"]],
                },
                [
                    UtilityTemplateRow("u1", "utp1"),
                    UtilityTemplateRow("u2", "utp2"),
                    UtilityTemplateRow("u3", "utp3"),
                ],
            ],
            [{}, []],
        ],
    )
    def test_get_rows_from_api_returns_objs(self, row, expected):
        sheets_api = Mock(get_values_of_ranges=Mock(return_value=row))

        result = UtilityTemplateRow.get_many_from_api(sheets_api, [])

        assert result == expected


@pytest.mark.parametrize(
    "rows,expected",
    [
        [
            [
                UtilityTemplateRow("u1", "utp1"),
                UtilityTemplateRow("u2", "utp2"),
            ],
            {"u1": "utp1", "u2": "utp2"},
        ],
        [
            [
                UtilityTemplateRow("u1", "utp1"),
                UtilityTemplateRow("u1", "utp2"),
            ],
            {"u1": "utp2"},
        ],
        [[], {}],
    ],
)
def test_parse_utility_template_sheet_rows_returns_utility_templates(rows, expected):
    result = loader.parse_utility_template_sheet_rows(rows)

    assert result == expected


class TestDispatchRow:
    @pytest.mark.parametrize(
        "row,expected",
        [
            [
                ["n", "edit", "1", "1", "t", "tp", "stat"],
                DispatchRow("n", "edit", "1", "1", "t", "tp", "stat"),
            ],
            [
                ["n", "create", "1", "1", "t", "tp"],
                DispatchRow("n", "create", "1", "1", "t", "tp", ""),
            ],
            [["n"], DispatchRow("n", "", "", "", "", "", "")],
            [[], DispatchRow("", "", "", "", "", "", "")],
        ],
    )
    def test_create_from_api_row_returns_obj(self, row, expected):
        result = DispatchRow.from_api_row(row)

        assert result == expected

    @pytest.mark.parametrize(
        "row,expected",
        [
            [
                {
                    SheetRange("s", "a"): [
                        ["n1", "edit", "1", "1", "t1", "tp1", "stat1"],
                        ["n2", "edit", "1", "1", "t2", "tp2", "stat2"],
                    ],
                    SheetRange("s", "b"): [
                        ["n3", "edit", "1", "1", "t3", "tp3", "stat3"]
                    ],
                },
                {
                    SheetRange("s", "a"): [
                        DispatchRow("n1", "edit", "1", "1", "t1", "tp1", "stat1"),
                        DispatchRow("n2", "edit", "1", "1", "t2", "tp2", "stat2"),
                    ],
                    SheetRange("s", "b"): [
                        DispatchRow("n3", "edit", "1", "1", "t3", "tp3", "stat3"),
                    ],
                },
            ],
            [
                {SheetRange("s", "a"): []},
                {SheetRange("s", "a"): []},
            ],
            [{}, {}],
        ],
    )
    def test_get_rows_from_api_returns_many_objs(self, row, expected):
        sheets_api = Mock(get_values_of_ranges=Mock(return_value=row))

        result = DispatchRow.get_many_from_api(sheets_api, [])

        assert result == expected


@pytest.fixture(scope="module")
def owner_nations():
    return loader.OwnerNationStore({"1": loader.OwnerNation("nat", ["s"])})


@pytest.fixture(scope="module")
def category_setups():
    return loader.CategorySetupStore({"1": loader.CategorySetup("meta", "gameplay")})


class TestParseDispatchCellValuesOfRow:
    @pytest.mark.parametrize(
        "row,expected",
        [
            [
                DispatchRow(
                    '=hyperlink("https://www.nationstates.net/page=dispatch/id=1","n")',
                    "edit",
                    "1",
                    "1",
                    "t",
                    "tp",
                    "",
                ),
                Dispatch(
                    "1",
                    DispatchOp.EDIT,
                    "nat",
                    "t",
                    "meta",
                    "gameplay",
                    "tp",
                ),
            ],
            [
                DispatchRow("n", "create", "1", "1", "t", "tp", ""),
                Dispatch(None, DispatchOp.CREATE, "nat", "t", "meta", "gameplay", "tp"),
            ],
            [
                DispatchRow("n", "create", "1", "1", "t", "", ""),
                Dispatch(None, DispatchOp.CREATE, "nat", "t", "meta", "gameplay", ""),
            ],
        ],
    )
    def test_with_valid_row_returns_dispatch_obj(
        self, row, expected, owner_nations, category_setups
    ):
        spreadsheet_id = "s"

        result = loader.parse_dispatch_cell_values_of_row(
            row, spreadsheet_id, owner_nations, category_setups
        )

        assert result == expected

    @pytest.mark.parametrize(
        "row,spreadsheet_id,expected",
        [
            [DispatchRow("", "create", "1", "1", "t", "tp", ""), "s", SkipRow],
            [DispatchRow("n", "", "1", "1", "t", "tp", ""), "s", SkipRow],
            [
                DispatchRow("n", "a", "1", "1", "t", "tp", ""),
                "s",
                InvalidDispatchRowError,
            ],
            [
                DispatchRow("n", "create", "1", "1", "", "tp", ""),
                "s",
                InvalidDispatchRowError,
            ],
            [
                DispatchRow("n", "create", "invalid", "1", "t", "tp", ""),
                "s",
                InvalidDispatchRowError,
            ],
            [
                DispatchRow("n", "create", "1", "invalid", "t", "tp", ""),
                "s",
                InvalidDispatchRowError,
            ],
            [
                DispatchRow("n", "create", "1", "invalid", "t", "tp", ""),
                "s2",
                InvalidDispatchRowError,
            ],
        ],
    )
    def test_with_invalid_row_raises_exception(
        self, row, spreadsheet_id, expected, owner_nations, category_setups
    ):
        with pytest.raises(expected):
            loader.parse_dispatch_cell_values_of_row(
                row, spreadsheet_id, owner_nations, category_setups
            )


class TestParseDispatchCellValuesOfRows:
    @pytest.mark.parametrize(
        "rows,expected",
        [
            [
                [
                    DispatchRow("n1", "create", "1", "1", "t1", "tp1", ""),
                    DispatchRow("n2", "create", "1", "1", "t2", "tp2", ""),
                ],
                {
                    "n1": Dispatch(
                        None,
                        DispatchOp.CREATE,
                        "nat",
                        "t1",
                        "meta",
                        "gameplay",
                        "tp1",
                    ),
                    "n2": Dispatch(
                        None,
                        DispatchOp.CREATE,
                        "nat",
                        "t2",
                        "meta",
                        "gameplay",
                        "tp2",
                    ),
                },
            ],
            [
                [
                    DispatchRow("n1", "create", "1", "1", "t1", "tp1", ""),
                    DispatchRow("", "", "", "", "", "", ""),
                ],
                {
                    "n1": Dispatch(
                        None,
                        DispatchOp.CREATE,
                        "nat",
                        "t1",
                        "meta",
                        "gameplay",
                        "tp1",
                    ),
                },
            ],
            [
                [
                    DispatchRow("n1", "create", "1", "1", "t1", "tp1", ""),
                    DispatchRow("n2", "create", "", "", "", "", ""),
                ],
                {
                    "n1": Dispatch(
                        None,
                        DispatchOp.CREATE,
                        "nat",
                        "t1",
                        "meta",
                        "gameplay",
                        "tp1",
                    ),
                },
            ],
            [[], {}],
        ],
    )
    def test_with_rows_returns_dispatches(
        self, rows, expected, owner_nations, category_setups
    ):
        result = loader.parse_dispatch_cell_values_of_rows(
            rows, "s", owner_nations, category_setups, Mock()
        )

        assert result == expected

    def test_skip_row_logs_message(
        self, owner_nations, category_setups, caplog: pytest.LogCaptureFixture
    ):
        rows = [DispatchRow("n", "", "1", "1", "t", "tp", "")]

        with caplog.at_level(logging.DEBUG):
            loader.parse_dispatch_cell_values_of_rows(
                rows, "s", owner_nations, category_setups, Mock()
            )

    def test_with_invalid_row_logs_message(
        self, owner_nations, category_setups, caplog: pytest.LogCaptureFixture
    ):
        rows = [DispatchRow("n", "create", "", "", "", "", "")]

        with caplog.at_level(logging.ERROR):
            loader.parse_dispatch_cell_values_of_rows(
                rows, "s", owner_nations, category_setups, Mock()
            )

    def test_with_invalid_row_calls_report_failure_cb(
        self, owner_nations, category_setups
    ):
        rows = [DispatchRow("n", "create", "", "", "", "", "")]
        report_failure_cb = Mock()

        loader.parse_dispatch_cell_values_of_rows(
            rows, "s", owner_nations, category_setups, report_failure_cb
        )

        report_failure_cb.assert_called()


class TestParseDispatchCellValuesOfRanges:
    @pytest.mark.parametrize(
        "sheet_ranges,expected",
        [
            [
                {
                    SheetRange("s", "A!A1:F"): [
                        DispatchRow("n1", "create", "1", "1", "t1", "tp1", ""),
                        DispatchRow("n2", "create", "1", "1", "t2", "tp2", ""),
                    ],
                    SheetRange("s", "B!A1:F"): [
                        DispatchRow("n3", "create", "1", "1", "t3", "tp3", ""),
                    ],
                },
                {
                    "n1": Dispatch(
                        None,
                        DispatchOp.CREATE,
                        "nat",
                        "t1",
                        "meta",
                        "gameplay",
                        "tp1",
                    ),
                    "n2": Dispatch(
                        None,
                        DispatchOp.CREATE,
                        "nat",
                        "t2",
                        "meta",
                        "gameplay",
                        "tp2",
                    ),
                    "n3": Dispatch(
                        None,
                        DispatchOp.CREATE,
                        "nat",
                        "t3",
                        "meta",
                        "gameplay",
                        "tp3",
                    ),
                },
            ],
            [
                {
                    SheetRange("s", "A!A1:F"): [
                        DispatchRow("n1", "create", "1", "1", "t1", "tp1", ""),
                    ],
                    SheetRange("s", "B!A1:F"): [
                        DispatchRow("n2", "create", "", "", "", "", ""),
                    ],
                },
                {
                    "n1": Dispatch(
                        None,
                        DispatchOp.CREATE,
                        "nat",
                        "t1",
                        "meta",
                        "gameplay",
                        "tp1",
                    ),
                },
            ],
            [
                {
                    SheetRange("s", "A!A1:F"): [],
                },
                {},
            ],
            [{}, {}],
        ],
    )
    def test_with_valid_rows_returns_dispatches(
        self, sheet_ranges, expected, owner_nations, category_setups
    ):
        result = loader.parse_dispatch_cell_values_of_ranges(
            sheet_ranges, owner_nations, category_setups, Mock()
        )

        assert result == expected

    def test_with_invalid_rows_reports_failure_cb(self, owner_nations, category_setups):
        sheet_ranges = {
            SheetRange("s", "A!A1:F"): [
                DispatchRow("n", "create", "", "", "t", "tp", ""),
            ],
        }
        report_failure_cb = Mock()

        loader.parse_dispatch_cell_values_of_ranges(
            sheet_ranges, owner_nations, category_setups, report_failure_cb
        )

        report_failure_cb.assert_called()


class TestGenerateNewDispatchRangeCellValues:
    @pytest.mark.parametrize(
        "hyperlink, op, op_enum, expected_hyperlink, expected_op, expected_status",
        [
            [
                "n",
                "create",
                DispatchOp.CREATE,
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1","n")',
                "edit",
                "Created successfully.\nTime: 2023/01/01 00:00:00 ",
            ],
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1","n")',
                "edit",
                DispatchOp.EDIT,
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1","n")',
                "edit",
                "Edited successfully.\nTime: 2023/01/01 00:00:00 ",
            ],
            [
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1","n")',
                "delete",
                DispatchOp.DELETE,
                '=hyperlink("https://www.nationstates.net/page=dispatch/id=1","n")',
                "",
                "Deleted successfully.\nTime: 2023/01/01 00:00:00 ",
            ],
        ],
    )
    def test_with_succeed_ops_returns_updated_row_cell_values(
        self, hyperlink, op, op_enum, expected_hyperlink, expected_op, expected_status
    ):
        old_rows = [DispatchRow(hyperlink, op, "1", "1", "t", "tp", "")]
        dispatch_config = {
            "n": Dispatch("1", op_enum, "nat", "t", "meta", "gameplay", "tp")
        }
        op_results = {"n": SuccessOpResult("n", op_enum, datetime(2023, 1, 1))}

        result = loader.generate_new_dispatch_cell_values_of_range(
            old_rows, dispatch_config, op_results
        )

        assert result == [
            [expected_hyperlink, expected_op, "1", "1", "t", "tp", expected_status]
        ]

    @pytest.mark.parametrize(
        "hyperlink,dispatch_config,op_results",
        [
            ["", {}, {}],
            [
                "n",
                {},
                {"n": SuccessOpResult("n", DispatchOp.CREATE, datetime(2023, 1, 1))},
            ],
            [
                "n",
                {
                    "n": Dispatch(
                        "1",
                        DispatchOp.CREATE,
                        "nat",
                        "t",
                        "meta",
                        "gameplay",
                        "tp",
                    )
                },
                {},
            ],
        ],
    )
    def test_with_no_op_cases_returns_identical_row_cell_values(
        self, hyperlink, dispatch_config, op_results
    ):
        old_rows = [DispatchRow(hyperlink, "create", "1", "1", "t", "tp", "")]

        result = loader.generate_new_dispatch_cell_values_of_range(
            old_rows, dispatch_config, op_results
        )

        assert result == [
            [
                hyperlink,
                "create",
                "1",
                "1",
                "t",
                "tp",
                "",
            ]
        ]

    def test_with_failed_op_returns_identical_row_cell_values_with_failed_status(self):
        old_rows = [DispatchRow("n", "create", "1", "1", "t", "tp", "")]
        dispatch_config = {
            "n": Dispatch("1", DispatchOp.CREATE, "nat", "t", "meta", "gameplay", "tp")
        }
        op_results = {
            "n": FailureOpResult("n", DispatchOp.CREATE, datetime(2023, 1, 1), "d")
        }

        result = loader.generate_new_dispatch_cell_values_of_range(
            old_rows, dispatch_config, op_results
        )

        assert result == [
            [
                "n",
                "create",
                "1",
                "1",
                "t",
                "tp",
                "Failed to create.\nDetails: d\nTime: 2023/01/01 00:00:00 ",
            ]
        ]


@pytest.mark.parametrize(
    "old_rows,expected_result",
    [
        [
            {
                SheetRange("s1", "A!A1:F"): [
                    DispatchRow("n1", "create", "1", "1", "t1", "tp1", "")
                ],
                SheetRange("s2", "A!A1:F"): [
                    DispatchRow("n2", "create", "1", "1", "t2", "tp2", "")
                ],
            },
            {
                SheetRange("s1", "A!A1:F"): [
                    [
                        '=hyperlink("https://www.nationstates.net/page=dispatch/id=1","n1")',
                        "edit",
                        "1",
                        "1",
                        "t1",
                        "tp1",
                        "Created successfully.\nTime: 2023/01/01 00:00:00 ",
                    ]
                ],
                SheetRange("s2", "A!A1:F"): [
                    [
                        '=hyperlink("https://www.nationstates.net/page=dispatch/id=2","n2")',
                        "edit",
                        "1",
                        "1",
                        "t2",
                        "tp2",
                        "Created successfully.\nTime: 2023/01/01 00:00:00 ",
                    ]
                ],
            },
        ],
        [{SheetRange("s1", "A!A1:F"): []}, {SheetRange("s1", "A!A1:F"): []}],
        [{}, {}],
    ],
)
def test_generate_new_dispatch_cell_values_for_ranges_returns_updated_cell_values(
    old_rows, expected_result
):
    dispatch_config = {
        "n1": Dispatch("1", DispatchOp.CREATE, "nat", "t1", "meta", "gameplay", "tp1"),
        "n2": Dispatch("2", DispatchOp.CREATE, "nat", "t2", "meta", "gameplay", "tp2"),
    }
    op_results = {
        "n1": SuccessOpResult("n1", DispatchOp.CREATE, datetime(2023, 1, 1)),
        "n2": SuccessOpResult("n2", DispatchOp.CREATE, datetime(2023, 1, 1)),
    }

    result = loader.generate_new_dispatch_cell_values_for_ranges(
        old_rows, dispatch_config, op_results
    )

    assert result == expected_result


class TestDispatchConfigStore:
    @pytest.mark.parametrize(
        "dispatch_config,expected",
        [
            [
                {
                    "n": Dispatch(
                        ns_id="1",
                        owner_nation="nat",
                        operation=DispatchOp.EDIT,
                        title="t",
                        template="tp",
                        category="meta",
                        subcategory="gameplay",
                    )
                },
                {
                    "n": DispatchMetadata(
                        "1", DispatchOp.EDIT, "nat", "t", "meta", "gameplay"
                    )
                },
            ],
            [
                {
                    "n": Dispatch(
                        ns_id=None,
                        owner_nation="nat",
                        operation=DispatchOp.CREATE,
                        title="t",
                        template="tp",
                        category="meta",
                        subcategory="gameplay",
                    )
                },
                {
                    "n": DispatchMetadata(
                        None, DispatchOp.CREATE, "nat", "t", "meta", "gameplay"
                    )
                },
            ],
            [{}, {}],
        ],
    )
    def test_get_canonical_dispatch_config_returns_canonical_format(
        self, dispatch_config, expected
    ):
        obj = loader.DispatchStore(dispatch_config)

        result = obj.get_dispatches_metadata()

        assert result == expected

    def test_get_dispatch_template_returns_template_text(self):
        dispatch_data = {
            "n": Dispatch(
                ns_id="1",
                owner_nation="nat",
                operation=DispatchOp.EDIT,
                title="t",
                template="tp",
                category="meta",
                subcategory="gameplay",
            )
        }
        obj = loader.DispatchStore(dispatch_data)

        assert obj.get_dispatch_template("n") == "tp"

    def test_get_non_existent_dispatch_template_raises_exception(self):
        obj = loader.DispatchStore({})

        with pytest.raises(KeyError):
            obj.get_dispatch_template("something non existent")

    @pytest.mark.parametrize("old_dispatch_id,expected", [[None, "1"], ["0", "1"]])
    def test_add_dispatch_id_adds_id_into_dispatch(self, old_dispatch_id, expected):
        dispatch_data = {
            "n": Dispatch(
                ns_id=old_dispatch_id,
                owner_nation="nat",
                operation=DispatchOp.CREATE,
                title="t",
                template="tp",
                category="meta",
                subcategory="gameplay",
            )
        }
        obj = loader.DispatchStore(dispatch_data)

        obj.add_dispatch_id("n", "1")
        result = obj["n"].ns_id

        assert result == expected


@pytest.mark.parametrize(
    "config,expected",
    [
        [[], []],
        [
            [
                {"spreadsheet_id": "s1", "ranges": []},
                {"spreadsheet_id": "s2", "ranges": []},
            ],
            [],
        ],
        [
            [
                {"spreadsheet_id": "s1", "ranges": ["r1", "r2"]},
                {"spreadsheet_id": "s2", "ranges": ["r3"]},
            ],
            [
                SheetRange("s1", "r1"),
                SheetRange("s1", "r2"),
                SheetRange("s2", "r3"),
            ],
        ],
    ],
)
def test_flatten_dispatch_sheet_config_returns_flatten_list(config, expected):
    result = loader.flatten_spreadsheet_config(config)

    assert result == expected


class TestGoogleDispatchLoader:
    @pytest.fixture(scope="class")
    def loader_obj(self):
        owner_nations = loader.OwnerNationStore(
            {"1": OwnerNation("nat1", ["s"]), "2": OwnerNation("nat2", ["s"])}
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
        dispatches = loader.DispatchStore(
            loader.parse_dispatch_cell_values_of_ranges(
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

    def test_get_dispatches_metadata_returns_metadata(self, loader_obj):
        result = loader_obj.get_dispatches_metadata()

        assert result == {
            "n1": DispatchMetadata(
                None, DispatchOp.CREATE, "nat1", "t1", "meta", "gameplay"
            ),
            "n2": DispatchMetadata(
                "2", DispatchOp.EDIT, "nat1", "t2", "meta", "gameplay"
            ),
            "n3": DispatchMetadata(
                "3", DispatchOp.EDIT, "nat2", "t3", "meta", "gameplay"
            ),
        }

    def test_get_utility_dispatch_template_returns_correct_template(self, loader_obj):
        result = loader_obj.get_dispatch_template("u")

        assert result == "utp"

    def test_get_normal_dispatch_template_returns_correct_template(self, loader_obj):
        result = loader_obj.get_dispatch_template("n1")

        assert result == "tp1"

    def test_update_spreadsheets_after_new_dispatch_created_changes_op_to_edit(
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
        dispatches = loader.DispatchStore(
            loader.parse_dispatch_cell_values_of_ranges(
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
            DispatchOp.CREATE,
            DispatchOpResult.SUCCESS,
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
