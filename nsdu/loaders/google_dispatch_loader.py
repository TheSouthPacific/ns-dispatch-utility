"""A loader plugin to load dispatches from Google spreadsheets.
"""

from __future__ import annotations

import dataclasses
import itertools
import logging
import re
from abc import ABC, abstractmethod
from collections import UserDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from google.oauth2 import service_account
from googleapiclient import discovery
from googleapiclient.http import HttpError

from nsdu import exceptions, loader_api
from nsdu.config import Config
from nsdu.loader_api import DispatchOp, DispatchesMetadata

GOOGLE_API_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

HYPERLINK_PATTERN = (
    r'=hyperlink\("https://www.nationstates.net/page=dispatch/id=(\d+)",\s*"(.+)"\)'
)
HYPERLINK_FORMAT = (
    '=hyperlink("https://www.nationstates.net/page=dispatch/id={dispatch_id}","{name}")'
)


SUCCESS_RESULT_MESSAGE_FORMAT = "{message}\nTime: {result_time}"
SUCCESS_RESULT_MESSAGES = {
    DispatchOp.CREATE: "Created successfully.",
    DispatchOp.EDIT: "Edited successfully.",
    DispatchOp.DELETE: "Deleted successfully.",
}
FAILURE_RESULT_MESSAGE_FORMAT = (
    "{message}\nDetails: {failure_details}\nTime: {result_time}"
)
FAILURE_RESULT_MESSAGES = {
    DispatchOp.CREATE: "Failed to create.",
    DispatchOp.EDIT: "Failed to edit.",
    DispatchOp.DELETE: "Failed to remove.",
}
INVALID_OPERATION_MESSAGE = "Invalid operation {operation}"
RESULT_TIME_FORMAT = "%Y/%m/%d %H:%M:%S %Z"

logger = logging.getLogger(__name__)

CellValue = Any
RowCellValues = list[CellValue]
RangeCellValues = list[RowCellValues]


@dataclass(frozen=True)
class SheetRange:
    """Describes the spreadsheet ID and range value of a spreadsheet range."""

    spreadsheet_id: str
    range_value: str


MultiRangeCellValues = dict[SheetRange, RangeCellValues]


@dataclass(frozen=True)
class Dispatch(loader_api.DispatchMetadata):
    template: str


class GoogleDispatchLoaderError(exceptions.LoaderError):
    """Base class for exceptions from this loader."""


class GoogleApiError(GoogleDispatchLoaderError):
    """Exception for Google Sheets API errors."""

    def __init__(self, status_code: int, details: Any) -> None:
        """Exception for Google Sheets API errors.

        Args:
            status_code (int): HTTP status code
            details (str): Error details
        """
        message = f"Google API error {status_code}: {details}"
        super().__init__(message)

        self.status_code = status_code
        self.details = details


class GoogleSheetsApiAdapter:
    """Adapter for Google Sheets API client.

    Args:
        api (Any): Google Sheets API client object
    """

    def __init__(self, api: Any):
        self._api = api

    @staticmethod
    def execute(request: Any) -> Any:
        """Execute a request from the Google Sheets API client.

        Args:
            request (Any): Request from the Google Sheets API client

        Raises:
            GoogleApiError: API error

        Returns:
            Any: API response
        """

        try:
            return request.execute()
        except HttpError as err:
            raise GoogleApiError(err.status_code, err.error_details) from err

    def get_values_of_ranges(
        self, sheet_ranges: Sequence[SheetRange]
    ) -> dict[SheetRange, RangeCellValues]:
        """Get cell values of many spreadsheet ranges.

        Args:
            sheet_ranges (Sequence[SheetRange]): Ranges to get

        Returns:
            dict[SheetRange, SheetRangeValues]: Cell values
        """

        spreadsheets_cell_values: dict[SheetRange, RangeCellValues] = {}

        spreadsheets = itertools.groupby(
            sheet_ranges, lambda range: range.spreadsheet_id
        )
        for spreadsheet_id, spreadsheet_ranges in spreadsheets:
            range_values = list(
                map(lambda sheet_range: sheet_range.range_value, spreadsheet_ranges)
            )

            req = self._api.batchGet(
                spreadsheetId=spreadsheet_id,
                ranges=range_values,
                valueRenderOption="FORMULA",
            )
            resp = GoogleSheetsApiAdapter.execute(req)
            logger.debug(
                'Pulled cell values from ranges "%r" of spreadsheet "%s": "%r"',
                range_values,
                spreadsheet_id,
                resp,
            )

            cell_values = {
                SheetRange(spreadsheet_id, valueRange["range"]): valueRange.get(
                    "values", []
                )
                for valueRange in resp["valueRanges"]
            }
            spreadsheets_cell_values.update(cell_values)

        return spreadsheets_cell_values

    def get_values_of_range(self, sheet_range: SheetRange) -> RangeCellValues:
        """Get cell values of a spreadsheet range.

        Args:
            sheet_range (CellRange): Range to get

        Returns:
            RangeCellValues: Cell values
        """

        result = self.get_values_of_ranges([sheet_range])
        return next(iter(result.values()))

    def update_values_of_ranges(
        self, new_values: Mapping[SheetRange, RangeCellValues]
    ) -> None:
        """Update cell values of many spreadsheet ranges.

        Args:
            new_values (Mapping[SheetRange, RangeCellValues]): New cell values
        """

        spreadsheets = itertools.groupby(
            new_values.keys(), lambda range: range.spreadsheet_id
        )
        for spreadsheet_id, spreadsheet_ranges in spreadsheets:
            spreadsheet_new_values = list(
                map(
                    lambda range: {
                        "range": range.range_value,
                        "majorDimension": "ROWS",
                        "values": new_values[range],
                    },
                    spreadsheet_ranges,
                )
            )
            body = {"valueInputOption": "USER_ENTERED", "data": spreadsheet_new_values}
            req = self._api.batchUpdate(spreadsheetId=spreadsheet_id, body=body)
            resp = GoogleSheetsApiAdapter.execute(req)
            logger.debug(
                'Updated cell values of ranges "%r" from spreadsheet "%s": %r',
                spreadsheet_ranges,
                spreadsheet_id,
                resp,
            )


@dataclass(frozen=True)
class OpResult(ABC):
    """Describes the result of a dispatch operation."""

    dispatch_name: str
    operation: DispatchOp
    result_time: datetime

    @property
    @abstractmethod
    def result_message(self) -> str:
        """Get user-friendly result message.

        Returns:
            str: Message
        """


@dataclass(frozen=True)
class SuccessOpResult(OpResult):
    """Describes the result of a successful dispatch operation."""

    @property
    def result_message(self) -> str:
        result_message = SUCCESS_RESULT_MESSAGES[self.operation]
        result_time_str = self.result_time.strftime(RESULT_TIME_FORMAT)
        return SUCCESS_RESULT_MESSAGE_FORMAT.format(
            message=result_message, result_time=result_time_str
        )


@dataclass(frozen=True)
class FailureOpResult(OpResult):
    """Describes the result of a failed dispatch operation."""

    operation: DispatchOp | str
    details: str | None

    @property
    def result_message(self) -> str:
        result_message = (
            FAILURE_RESULT_MESSAGES[self.operation]
            if isinstance(self.operation, DispatchOp)
            else INVALID_OPERATION_MESSAGE.format(operation=self.operation)
        )
        result_time_str = self.result_time.strftime(RESULT_TIME_FORMAT)
        return FAILURE_RESULT_MESSAGE_FORMAT.format(
            message=result_message,
            failure_details=self.details,
            result_time=result_time_str,
        )


class OpResultStore(UserDict[str, OpResult]):
    """Stores the results of dispatch operations."""

    def report_success(
        self,
        dispatch_name: str,
        operation: DispatchOp,
        result_time: datetime | None = None,
    ) -> None:
        """Report a successful dispatch operation.

        Args:
            dispatch_name (str): Dispatch name
            operation (DispatchOperation): Dispatch operation
            result_time (datetime | None): Time the result happened.
            Use current time if None.
        """

        if result_time is None:
            result_time = datetime.now(tz=timezone.utc)
        self.data[dispatch_name] = SuccessOpResult(
            dispatch_name, operation, result_time
        )

    def report_failure(
        self,
        dispatch_name: str,
        operation: DispatchOp | str,
        details: str | Exception | None = None,
        result_time: datetime | None = None,
    ) -> None:
        """Report a failed dispatch operation.

        Args:
            dispatch_name (str): Dispatch name
            operation (DispatchOperation | str): Dispatch operation.
            Use a normal string for an invalid operation
            details (str | Exception | None): Error details. Defaults to None.
            result_time (datetime.datetime) Time the result happened.
            Use current time if None.
        """

        if result_time is None:
            result_time = datetime.now(tz=timezone.utc)

        details = str(details) if details is not None else None

        self.data[dispatch_name] = FailureOpResult(
            dispatch_name, operation, result_time, details
        )


@dataclass(frozen=True)
class CategorySetup:
    """Describes a dispatch category/subcategory setup."""

    category_name: str
    subcategory_name: str


class CategorySetupStore(UserDict[str, CategorySetup]):
    """Contains dispatch category/subcategory setups."""

    @classmethod
    def load_from_range_cell_values(cls, range_cell_values: RangeCellValues):
        """Load category setups from cell values of a spreadsheet range.

        Args:
            range_cell_values (RangeCellValues): Cell values of a range

        Returns:
            CategorySetupStore
        """

        setups: dict[str, CategorySetup] = {}
        # In case of similar IDs, the latest one is used
        for row in range_cell_values:
            setup_id = str(row[0])
            category_name = str(row[1]).lower()
            subcategory_name = str(row[2]).lower()

            if not category_name or not subcategory_name:
                continue

            setups[setup_id] = CategorySetup(category_name, subcategory_name)

        return cls(setups)

    def __getitem__(self, setup_id: str) -> CategorySetup:
        try:
            return super().__getitem__(setup_id)
        except KeyError as err:
            raise KeyError(f"Could not find category setup ID {setup_id}") from err


@dataclass(frozen=True)
class OwnerNation:
    """Describes a dispatch owner nation and its allowed spreadsheets."""

    nation_name: str
    allowed_spreadsheet_ids: list[str]


class OwnerNationStore(UserDict[str, OwnerNation]):
    """Contains dispatch owner nations' config."""

    @classmethod
    def load_from_range_cell_values(cls, range_cell_values: RangeCellValues):
        """Load owner nations from cell values of a spreadsheet range.

        Args:
            range_cell_values (RangeCellValues): Cell values

        Returns:
            OwnerNationStore
        """

        owner_nations: dict[str, OwnerNation] = {}
        # If there are similar IDs, the latest one is used
        for row in range_cell_values:
            owner_id = str(row[0])

            owner_nation_name = str(row[1])
            if not owner_nation_name:
                continue

            allowed_spreadsheets_cell = str(row[2])
            if not allowed_spreadsheets_cell:
                allowed_spreadsheets = []
            else:
                allowed_spreadsheets = str(row[2]).split(",")

            owner_nations[owner_id] = OwnerNation(
                owner_nation_name, allowed_spreadsheets
            )

        return cls(owner_nations)

    def __getitem__(self, owner_id: str) -> OwnerNation:
        try:
            return super().__getitem__(owner_id)
        except KeyError as err:
            raise KeyError(
                f'Could not find any nation with owner ID "{owner_id}"'
            ) from err

    def check_spreadsheet_permission(self, owner_id: str, spreadsheet_id: str) -> bool:
        """Check if the provided owner ID can be used with the provided spreadsheet ID.

        Args:
            owner_id (str): Owner ID
            spreadsheet_id (str): Spreadsheet ID

        Returns:
            bool: True if allowed
        """

        if owner_id not in self.data:
            raise KeyError(f'Could not find any nation with owner ID "{owner_id}"')

        return spreadsheet_id in self.data[owner_id].allowed_spreadsheet_ids


@dataclass(frozen=True)
class UtilityTemplateRow:
    """Contains cell values of a utility template sheet row."""

    name: str
    template: str

    @classmethod
    def from_api_row(cls, resp: RowCellValues) -> UtilityTemplateRow:
        """Create a utility template row object from
        row cell values in Sheets API format.

        Args:
            resp (RowCellValues): Row cell values in Sheets API format

        Returns:
            UtilityTemplateRow: Utility template row object
        """

        name = template = ""
        try:
            name = str(resp[0])
            template = str(resp[1])
        except IndexError:
            pass
        return cls(name, template)

    @staticmethod
    def get_many_from_api(
        api: GoogleSheetsApiAdapter, sheet_ranges: Sequence[SheetRange]
    ) -> list[UtilityTemplateRow]:
        """Get utility template row objects from many spreadsheet ranges
        using the Sheets API.

        Args:
            api (GoogleSheetsApiAdapter): Sheets API client
            sheet_ranges (Sequence[SheetRange]): Ranges to load

        Returns:
            list[UtilityTemplateRow]: Utility template row objects
        """

        values = api.get_values_of_ranges(sheet_ranges).values()
        return [
            UtilityTemplateRow.from_api_row(row) for range in values for row in range
        ]


def parse_utility_template_sheet_rows(
    rows: Sequence[UtilityTemplateRow],
) -> dict[str, str]:
    """Get utility templates from utility template sheet rows.

    Args:
        rows: Sequence[UtilityTemplateRow]: Utility template sheet rows

    Returns:
        dict[str, str]: Utility templates keyed by name
    """

    return {row.name: row.template for row in rows if row.name and row.template}


def extract_dispatch_id_from_hyperlink(cell_value: str) -> str | None:
    """Extract dispatch ID from the HYPERLINK function in the dispatch name cell.

    Args:
        cell_value (str): Dispatch name cell value

    Returns:
        str | None: Dispatch ID
    """

    result = re.search(HYPERLINK_PATTERN, cell_value, flags=re.IGNORECASE)
    if result is None:
        return None

    return result.group(1)


def extract_name_from_hyperlink(cell_value: str) -> str:
    """Extract dispatch name from the HYPERLINK function in the dispatch name cell.

    Args:
        cell_value (str): Dispatch name cell value

    Returns:
        str: Dispatch name
    """

    result = re.search(HYPERLINK_PATTERN, cell_value, flags=re.IGNORECASE)
    if result is None:
        return cell_value

    return result.group(2)


def create_hyperlink(name: str, dispatch_id: str) -> str:
    """Create a hyperlink sheet function from dispatch name and ID.

    Args:
        name (str): Dispatch name
        dispatch_id (str): Dispatch id

    Returns:
        str: Hyperlink function
    """

    return HYPERLINK_FORMAT.format(name=name, dispatch_id=dispatch_id)


class InvalidDispatchRowError(GoogleDispatchLoaderError):
    """Exception for invalid values on dispatch sheet rows."""

    def __init__(self, operation: DispatchOp | str, *args: object) -> None:
        super().__init__(*args)
        self.operation = operation


class SkipRow(GoogleDispatchLoaderError):
    """Exception for dispatch sheet rows to skip when processing."""


@dataclass(frozen=True)
class DispatchRow:
    """Contains cell values of a dispatch sheet row."""

    hyperlink: str
    operation: str
    owner_id: str
    category_setup_id: str
    title: str
    template: str
    status: str

    @classmethod
    def from_api_row(cls, resp: RowCellValues) -> DispatchRow:
        """Create a dispatch row object from row cell values in Sheets API format.

        Args:
            resp (RowCellValues): Row cell values in Sheets API format

        Returns:
            DispatchRow: Dispatch row object
        """

        dispatch_name = (
            operation
        ) = owner_nation = category_setup = title = template = status = ""
        try:
            dispatch_name = str(resp[0])
            operation = str(resp[1])
            owner_nation = str(resp[2])
            category_setup = str(resp[3])
            title = str(resp[4])
            template = str(resp[5])
            status = str(resp[6])
        except IndexError:
            pass
        return cls(
            dispatch_name,
            operation,
            owner_nation,
            category_setup,
            title,
            template,
            status,
        )

    @staticmethod
    def get_many_from_api(
        api: GoogleSheetsApiAdapter, sheet_ranges: Sequence[SheetRange]
    ) -> dict[SheetRange, DispatchRows]:
        """Get dispatch row objects from many spreadsheet ranges using the Sheets API.

        Args:
            api (GoogleSheetsApiAdapter): Sheets API
            sheet_ranges (Sequence[SheetRange]): Ranges to get

        Returns:
            dict[SheetRange, DispatchRows]: Dispatch row objects
        """

        resp = api.get_values_of_ranges(sheet_ranges)
        return {
            range: [DispatchRow.from_api_row(row) for row in rows]
            for range, rows in resp.items()
        }

    def to_cell_values(self) -> RowCellValues:
        """Get cell values of this row in Sheets API format.

        Returns:
            RowCellValues: Row cell values in Sheets API format
        """

        return [
            self.hyperlink,
            self.operation,
            self.owner_id,
            self.category_setup_id,
            self.title,
            self.template,
            self.status,
        ]


DispatchRows = Sequence[DispatchRow]


def parse_dispatch_cell_values_of_row(
    row: DispatchRow,
    spreadsheet_id: str,
    owner_nations: OwnerNationStore,
    category_setups: CategorySetupStore,
) -> Dispatch:
    """Parse a dispatch sheet row's cell values
    and return a Dispatch object.

    Args:
        rows (RowData): Dispatch row data
        spreadsheet_id (str): Spreadsheet ID
        owner_nations (OwnerNationData): Owner nation data
        category_setups (CategorySetupData): Category setup data

    Raises:
        SkipRow: This row must be skipped
        InvalidDispatchDataError: This row has invalid values

    Returns:
        Dispatch: Dispatch object
    """

    if not row.hyperlink:
        raise SkipRow
    dispatch_id = extract_dispatch_id_from_hyperlink(str(row.hyperlink))

    if not row.operation:
        raise SkipRow

    operation_cell_value = row.operation.lower()
    try:
        operation = DispatchOp[operation_cell_value.upper()]
    except KeyError as err:
        raise InvalidDispatchRowError(
            operation_cell_value, "Invalid operation."
        ) from err

    if not row.owner_id:
        raise InvalidDispatchRowError(operation, "Owner nation cell cannot be empty.")
    try:
        owner_nation = owner_nations[row.owner_id].nation_name
    except KeyError as err:
        raise InvalidDispatchRowError(
            operation, f"Invalid owner nation ID {row.owner_id}"
        ) from err
    if not owner_nations.check_spreadsheet_permission(row.owner_id, spreadsheet_id):
        raise InvalidDispatchRowError(
            operation,
            f"Owner nation {row.owner_id} cannot be used on this spreadsheet.",
        )

    if not row.category_setup_id:
        raise InvalidDispatchRowError(operation, "Category setup cell cannot be empty.")
    try:
        category_setup = category_setups[row.category_setup_id]
        category = category_setup.category_name
        subcategory = category_setup.subcategory_name
    except KeyError as err:
        raise InvalidDispatchRowError(
            operation, f"Invalid category setup ID {row.category_setup_id}"
        ) from err

    if not row.title:
        raise InvalidDispatchRowError(operation, "Title column cannot be empty")

    return Dispatch(
        dispatch_id,
        operation,
        owner_nation,
        row.title,
        category,
        subcategory,
        row.template,
    )


ReportFailureCb = Callable[[str, DispatchOp | str, InvalidDispatchRowError], None]


def parse_dispatch_cell_values_of_rows(
    rows: DispatchRows,
    spreadsheet_id: str,
    owner_nations: OwnerNationStore,
    category_setups: CategorySetupStore,
    report_failure: ReportFailureCb,
) -> dict[str, Dispatch]:
    """Parse dispatch sheet rows' cell values and return Dispatch objects.

    Args:
        rows (DispatchRows): Dispatch data rows
        spreadsheet_id (str): Spreadsheet ID
        owner_nations (OwnerNationStore): Owner nation data
        category_setups (CategorySetupStore): Category setup data
        report_failure (ReportFailureCb): Failure report callback

    Returns:
        dict[str, Dispatch]: Dispatch objects
    """

    dispatches: dict[str, Dispatch] = {}

    for row in rows:
        dispatch_name = extract_name_from_hyperlink(row.hyperlink)

        try:
            dispatch = parse_dispatch_cell_values_of_row(
                row, spreadsheet_id, owner_nations, category_setups
            )
            dispatches[dispatch_name] = dispatch
        except SkipRow:
            logger.debug('Skipped spreadsheet row of dispatch "%s"', dispatch_name)
        except InvalidDispatchRowError as err:
            logger.error(
                'Spreadsheet row of dispatch "%s" is invalid: %s', dispatch_name, err
            )
            report_failure(dispatch_name, err.operation, err)

    return dispatches


def parse_dispatch_cell_values_of_ranges(
    sheet_ranges: Mapping[SheetRange, DispatchRows],
    owner_nations: OwnerNationStore,
    category_setups: CategorySetupStore,
    report_failure: ReportFailureCb,
) -> dict[str, Dispatch]:
    """Parse dispatch cell values from many spreadsheet ranges
    and return Dispatch objects.

    Args:
        sheet_ranges (Mapping[SheetRange, DispatchRows]): Cell values of sheet ranges
        owner_nations (OwnerNationStore): Owner nation data
        category_setups (CategorySetupStore): Category setup data
        report_failure (ReportFailureCb): Failure report callback

    Returns:
        dict[str, Dispatch]: Dispatch objects keyed by dispatch name
    """

    dispatches: dict[str, Dispatch] = {}
    for sheet_range, rows in sheet_ranges.items():
        row_dispatches = parse_dispatch_cell_values_of_rows(
            rows,
            sheet_range.spreadsheet_id,
            owner_nations,
            category_setups,
            report_failure,
        )
        dispatches.update(row_dispatches)
    return dispatches


def generate_new_dispatch_cell_values_of_range(
    old_rows: DispatchRows,
    dispatch_config: Mapping[str, Dispatch],
    op_results: Mapping[str, OpResult],
) -> RangeCellValues:
    """Generate new dispatch cell values for a spreadsheet range
    with updated values such as dispatch IDs, status messages,...

    Args:
        old_rows (DispatchRows): Old cell data of a dispatch sheet range
        dispatch_config (Mapping[str, Dispatch]): New dispatch config
        op_results (Mapping[str, OpResult]): Dispatch operation results

    Returns:
        RangeCellData: New dispatch cell data
    """

    new_row_values: RangeCellValues = []
    for row in old_rows:
        dispatch_name = extract_name_from_hyperlink(row.hyperlink)

        if dispatch_name not in dispatch_config:
            new_row_values.append(row.to_cell_values())
            continue

        # This case arises when the dispatch was loaded but
        # the program exits before it is updated
        try:
            result = op_results[dispatch_name]
        except KeyError:
            new_row_values.append(row.to_cell_values())
            continue

        new_status = result.result_message
        if isinstance(result, FailureOpResult):
            new_dispatch_row = dataclasses.replace(row, status=new_status)
            new_row_values.append(new_dispatch_row.to_cell_values())
            continue

        dispatch = dispatch_config[dispatch_name]

        new_dispatch_name = row.hyperlink
        new_operation = row.operation
        if dispatch.operation == DispatchOp.CREATE and dispatch.ns_id is not None:
            new_dispatch_name = create_hyperlink(dispatch_name, dispatch.ns_id)
            new_operation = "edit"
        elif dispatch.operation == DispatchOp.DELETE:
            new_operation = ""

        new_dispatch_row = DispatchRow(
            new_dispatch_name,
            new_operation,
            row.owner_id,
            row.category_setup_id,
            row.title,
            row.template,
            new_status,
        )
        new_row_values.append(new_dispatch_row.to_cell_values())

    return new_row_values


def generate_new_dispatch_cell_values_for_ranges(
    old_spreadsheet_cell_values: Mapping[SheetRange, DispatchRows],
    dispatch_config: Mapping[str, Dispatch],
    op_results: Mapping[str, OpResult],
) -> MultiRangeCellValues:
    """Generate new dispatch cell values for many spreadsheet ranges
    with updated values such as dispatch IDs, status messages,...

    Args:
        old_spreadsheet_values (Mapping[SheetRange, DispatchRows]): Old cell values
        dispatch_config (Mapping[str, Dispatch]): New dispatch config
        operation_results (Mapping[str, OpResult]): Dispatch operation results

    Returns:
        MultiRangeCellValues: New spreadsheet cell values
    """

    new_spreadsheet_cell_values: Mapping[SheetRange, RangeCellValues] = {}
    for sheet_range, cell_values in old_spreadsheet_cell_values.items():
        new_range_cell_values = generate_new_dispatch_cell_values_of_range(
            cell_values, dispatch_config, op_results
        )
        new_spreadsheet_cell_values[sheet_range] = new_range_cell_values
    return new_spreadsheet_cell_values


class DispatchConfigStore(UserDict[str, Dispatch]):
    """Manage configurations of dispatches
    (e.g. ID, title, category, template,...)."""

    def get_canonical_dispatch_config(self):
        """Get dispatch config in NSDU format.

        Returns:
            dict: Canonical dispatch config
        """

        result = {}
        for name, dispatch in self.data.items():
            match dispatch.operation:
                case DispatchOp.CREATE:
                    canonical_operation = "create"
                case DispatchOp.EDIT:
                    canonical_operation = "edit"
                case DispatchOp.DELETE:
                    canonical_operation = "remove"

            canonical_config = {
                "action": canonical_operation,
                "title": dispatch.title,
                "category": dispatch.category,
                "subcategory": dispatch.subcategory,
            }
            if dispatch.ns_id is not None:
                canonical_config["ns_id"] = dispatch.ns_id
            owner_nation = dispatch.owner_nation
            if owner_nation not in result:
                result[owner_nation] = {}
            result[owner_nation][name] = canonical_config
        return result

    def get_dispatch_template(self, name: str) -> str:
        """Get dispatch template text.

        Args:
            name (str): Dispatch name

        Returns:
            str: Template text
        """

        return self.data[name].template

    def add_dispatch_id(self, name: str, dispatch_id: str) -> None:
        """Add id of new dispatch.

        Args:
            name (str): Dispatch name
            dispatch_id (str): Dispatch id
        """

        dispatch = self.data[name]
        self.data[name] = dataclasses.replace(dispatch, ns_id=dispatch_id)


class GoogleDispatchLoader:
    """Google spreadsheet dispatch loader.

    Args:
        spreadsheet_api (GoogleSheetsApiAdapter): Spreadsheet API adapter
        dispatch_rows (Mapping[SheetRange, DispatchRows]): Dispatch spreadsheet values
        utility_templates (Mapping[str, str]): Utility template spreadsheet values
        owner_nations (OwnerNationStore): Owner nation spreadsheet values
        category_setups (CategorySetupStore): Category setup spreadsheet values
    """

    def __init__(
        self,
        api: GoogleSheetsApiAdapter,
        dispatch_rows: Mapping[SheetRange, DispatchRows],
        dispatches: DispatchConfigStore,
        utility_templates: Mapping[str, str],
        owner_nations: OwnerNationStore,
        category_setups: CategorySetupStore,
        op_result_store: OpResultStore,
    ) -> None:
        self.spreadsheet_api = api
        self.op_result_store = op_result_store

        self.dispatch_rows = dispatch_rows

        self.owner_nations = owner_nations
        self.category_setups = category_setups
        self.utility_templates = utility_templates
        self.dispatches = dispatches

    def get_dispatch_config(self) -> dict:
        """Get dispatch config.

        Returns:
            dict: Dispatch config
        """

        return self.dispatches.get_canonical_dispatch_config()

    def get_dispatch_template(self, name: str) -> str:
        """Get dispatch template text.

        Args:
            name (str): Dispatch name

        Returns:
            str: Template text
        """

        if name in self.utility_templates:
            return self.utility_templates[name]
        return self.dispatches.get_dispatch_template(name)

    def add_dispatch_id(self, name: str, dispatch_id: str) -> None:
        """Add id of new dispatch.

        Args:
            name (str): Dispatch name
            dispatch_id (str): Dispatch id
        """

        self.dispatches.add_dispatch_id(name, dispatch_id)

    def report_result(
        self,
        name: str,
        operation: DispatchOp,
        result: str,
        result_time: datetime,
    ) -> None:
        """Report operation result from NSDU.

        Args:
            name (str): Dispatch name
            operation (str): Dispatch operation
            result (str): Result
            result_time (datetime): Time update operation happened
        """

        if result == "success":
            self.op_result_store.report_success(name, operation, result_time)
        else:
            self.op_result_store.report_failure(name, operation, result, result_time)

    def update_spreadsheets(self) -> None:
        """Update spreadsheets."""

        new_dispatch_values = generate_new_dispatch_cell_values_for_ranges(
            self.dispatch_rows,
            self.dispatches,
            self.op_result_store,
        )
        self.spreadsheet_api.update_values_of_ranges(new_dispatch_values)
        logger.info("Updated Google spreadsheets.")


def flatten_spreadsheet_config(config: Any) -> Sequence[SheetRange]:
    """Flatten spreadsheet configuration dict.

    Args:
        config (Any): Configuration dict

    Returns:
        Sequence[SheetRange]: Flatten dict
    """

    return [
        SheetRange(spreadsheet["spreadsheet_id"], range)
        for spreadsheet in config
        for range in spreadsheet["ranges"]
    ]


@loader_api.dispatch_loader
def init_dispatch_loader(loaders_config: Config):
    loader_config = loaders_config["google_dispatch_loader"]

    google_api_creds = service_account.Credentials.from_service_account_file(
        loader_config["google_cred_path"], scopes=GOOGLE_API_SCOPES
    )
    # pylint: disable=maybe-no-member
    google_api = (
        discovery.build(
            "sheets", "v4", credentials=google_api_creds, cache_discovery=False
        )
        .spreadsheets()
        .values()
    )
    sheets_api = GoogleSheetsApiAdapter(google_api)
    op_result_store = OpResultStore()

    owner_nation_rows = sheets_api.get_values_of_range(
        SheetRange(
            loader_config["owner_nation_sheet"]["spreadsheet_id"],
            loader_config["owner_nation_sheet"]["range"],
        )
    )
    owner_nations = OwnerNationStore.load_from_range_cell_values(owner_nation_rows)

    category_setup_rows = sheets_api.get_values_of_range(
        SheetRange(
            loader_config["category_setup_sheet"]["spreadsheet_id"],
            loader_config["category_setup_sheet"]["range"],
        )
    )
    category_setups = CategorySetupStore.load_from_range_cell_values(
        category_setup_rows
    )

    utility_template_rows = UtilityTemplateRow.get_many_from_api(
        sheets_api,
        flatten_spreadsheet_config(loader_config["utility_template_spreadsheets"]),
    )
    utility_templates = parse_utility_template_sheet_rows(utility_template_rows)

    dispatch_rows = DispatchRow.get_many_from_api(
        sheets_api,
        flatten_spreadsheet_config(loader_config["dispatch_spreadsheets"]),
    )
    dispatches = DispatchConfigStore(
        parse_dispatch_cell_values_of_ranges(
            dispatch_rows,
            owner_nations,
            category_setups,
            op_result_store.report_failure,
        )
    )

    logger.info("Pulled data from Google spreadsheets.")

    return GoogleDispatchLoader(
        sheets_api,
        dispatch_rows,
        dispatches,
        utility_templates,
        owner_nations,
        category_setups,
        op_result_store,
    )


@loader_api.dispatch_loader
def get_dispatch_metadata(loader: GoogleDispatchLoader) -> DispatchesMetadata:
    return loader.get_dispatch_config()


@loader_api.dispatch_loader
def get_dispatch_template(loader: GoogleDispatchLoader, name: str) -> str:
    return loader.get_dispatch_template(name)


@loader_api.dispatch_loader
def after_update(
    loader: GoogleDispatchLoader,
    name: str,
    op: DispatchOp,
    result: str,
    result_time: datetime,
) -> None:
    match op:
        case "create":
            operation = DispatchOp.CREATE
        case "edit":
            operation = DispatchOp.EDIT
        case "remove":
            operation = DispatchOp.DELETE
        case _:
            raise ValueError("Invalid dispatch action")

    loader.report_result(name, operation, result, result_time)


@loader_api.dispatch_loader
def add_dispatch_id(loader: GoogleDispatchLoader, name: str, dispatch_id: str) -> None:
    loader.add_dispatch_id(name, dispatch_id)


@loader_api.dispatch_loader
def cleanup_dispatch_loader(loader: GoogleDispatchLoader) -> None:
    loader.update_spreadsheets()
