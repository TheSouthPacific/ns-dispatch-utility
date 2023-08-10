"""Load dispatches from Google spreadsheets.
"""

import copy
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
from nsdu.loader_api import Dispatch, DispatchOperation

GOOGLE_API_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

HYPERLINK_PATTERN = (
    r'=hyperlink\("https://www.nationstates.net/page=dispatch/id=(\d+)",\s*"(.+)"\)'
)
HYPERLINK_FORMAT = (
    '=hyperlink("https://www.nationstates.net/page=dispatch/id={dispatch_id}","{name}")'
)


SUCCESS_RESULT_MESSAGE_FORMAT = "{message}\nTime: {result_time}"
SUCCESS_RESULT_MESSAGES = {
    DispatchOperation.CREATE: "Created successfully.",
    DispatchOperation.EDIT: "Edited successfully.",
    DispatchOperation.DELETE: "Deleted successfully.",
}
FAILURE_RESULT_MESSAGE_FORMAT = (
    "{message}\nDetails: {failure_details}\nTime: {result_time}"
)
FAILURE_RESULT_MESSAGES = {
    DispatchOperation.CREATE: "Failed to create.",
    DispatchOperation.EDIT: "Failed to edit.",
    DispatchOperation.DELETE: "Failed to remove.",
}
INVALID_OPERATION_MESSAGE = "Invalid operation {operation}"
RESULT_TIME_FORMAT = "%Y/%m/%d %H:%M:%S %Z"

logger = logging.getLogger(__name__)

CellValue = Any
RowCellValues = list[CellValue]
RangeCellValues = list[RowCellValues]
SpreadsheetIds = Sequence[str]


@dataclass(frozen=True)
class SheetRange:
    """Describes the spreadsheet ID and range value of a spreadsheet range."""

    spreadsheet_id: str
    range_value: str


MultiRangeCellValues = Mapping[SheetRange, RangeCellValues]


class GoogleDispatchLoaderError(exceptions.LoaderError):
    """Base class for exceptions from this loader."""

    pass


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
            raise GoogleApiError(err.status_code, err.error_details)

    def get_values_of_ranges(
        self, ranges: Sequence[SheetRange]
    ) -> dict[SheetRange, RangeCellValues]:
        """Get cell values of many spreadsheet ranges.

        Args:
            ranges (Sequence[SheetRange]): Ranges to get

        Returns:
            dict[SheetRange, SheetRangeValues]: Cell values
        """

        all_spreadsheets_cell_values: dict[SheetRange, RangeCellValues] = {}

        spreadsheets = itertools.groupby(ranges, lambda range: range.spreadsheet_id)
        for spreadsheet_id, spreadsheet_ranges in spreadsheets:
            range_cell_values = list(
                map(lambda cell_range: cell_range.range_value, spreadsheet_ranges)
            )
            req = self._api.batchGet(
                spreadsheetId=spreadsheet_id,
                ranges=range_cell_values,
                valueRenderOption="FORMULA",
            )
            resp = GoogleSheetsApiAdapter.execute(req)
            logger.debug(
                'API response for pulling cell values from ranges "%r" of spreadsheet "%s": "%r"',
                range_cell_values,
                spreadsheet_id,
                resp,
            )

            sheet_cell_values = {
                SheetRange(spreadsheet_id, valueRange["range"]): valueRange.get(
                    "values", []
                )
                for valueRange in resp["valueRanges"]
            }
            all_spreadsheets_cell_values.update(sheet_cell_values)

        return all_spreadsheets_cell_values

    def get_values_of_range(self, range: SheetRange) -> RangeCellValues:
        """Get cell values of a spreadsheet range.

        Args:
            range (CellRange): Range to get

        Returns:
            RangeCellValues: Cell values
        """

        result = self.get_values_of_ranges([range])
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
                'API response for updating cell values of ranges "%r" from spreadsheet "%s": %r',
                spreadsheet_ranges,
                spreadsheet_id,
                resp,
            )


@dataclass(frozen=True)
class OpResult(ABC):
    """Describes the result of a dispatch operation."""

    dispatch_name: str
    operation: DispatchOperation
    result_time: datetime

    @property
    @abstractmethod
    def result_message(self) -> str:
        pass


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

    operation: DispatchOperation | str
    details: str | None

    @property
    def result_message(self) -> str:
        result_message = (
            FAILURE_RESULT_MESSAGES[self.operation]
            if isinstance(self.operation, DispatchOperation)
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
        operation: DispatchOperation,
        result_time: datetime | None = None,
    ) -> None:
        """Report a successful dispatch operation.

        Args:
            dispatch_name (str): Dispatch name
            operation (DispatchOperation): Dispatch operation
            result_time (datetime | None): Time the result happened. Use current time if None.
        """

        if result_time is None:
            result_time = datetime.now(tz=timezone.utc)
        self.data[dispatch_name] = SuccessOpResult(
            dispatch_name, operation, result_time
        )

    def report_failure(
        self,
        dispatch_name: str,
        operation: DispatchOperation | str,
        details: str | Exception | None = None,
        result_time: datetime | None = None,
    ) -> None:
        """Report a failed dispatch operation.

        Args:
            dispatch_name (str): Dispatch name
            operation (DispatchOperation | str): Dispatch operation. Use a normal string for an invalid operation
            details (str | Exception | None): Error details. Defaults to None.
            result_time (datetime.datetime) Time the result happened. Use current time if None.
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

    def __init__(self, setups: Mapping[str, CategorySetup]):
        """Contains dispatch category/subcategory setups.

        Args:
            setups (Mapping[str, CategorySetup]): Setups
        """

        self.data = dict(setups)

    @classmethod
    def load_from_range_cell_values(cls, range_cell_values: RangeCellValues):
        """Load category setups from cell values of a spreadsheet range.

        Args:
            range_cell_values (RangeCellValues): Cell values of a range

        Returns:
            CategorySetups
        """

        setups: dict[str, CategorySetup] = {}
        # In case of similar IDs, the latest one is used
        for row in range_cell_values:
            setup_id = str(row[0])
            category_name = str(row[1]).lower()
            subcategory_name = str(row[2]).lower()
            setups[setup_id] = CategorySetup(category_name, subcategory_name)

        return cls(setups)

    def __getitem__(self, setup_id: str) -> CategorySetup:
        try:
            return super().__getitem__(setup_id)
        except KeyError:
            raise KeyError(f"Could not find category setup ID {setup_id}")


@dataclass(frozen=True)
class OwnerNation:
    """Describes a dispatch owner nation and its allowed spreadsheets."""

    nation_name: str
    allowed_spreadsheet_ids: SpreadsheetIds


class OwnerNationStore(UserDict[str, OwnerNation]):
    """Contains dispatch owner nations' config.

    Args:
        owner_nations (Mapping[str, OwnerNation]): Owner nations
    """

    def __init__(
        self,
        owner_nations: Mapping[str, OwnerNation],
    ) -> None:
        self.data = dict(owner_nations)

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
            allowed_spreadsheets = str(row[2]).split(",")

            owner_nations[owner_id] = OwnerNation(
                owner_nation_name, allowed_spreadsheets
            )

        return cls(owner_nations)

    def __getitem__(self, owner_id: str) -> OwnerNation:
        try:
            return super().__getitem__(owner_id)
        except KeyError:
            raise KeyError(f'Could not find any nation with owner ID "{owner_id}"')

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


def parse_utility_template_cell_ranges(
    values: Mapping[SheetRange, RangeCellValues]
) -> dict[str, str]:
    """Get utility template content from cell data of many sheet ranges.

    Args:
        values (Mapping[SheetRange, RangeCellData]): Cell data of many sheet ranges

    Returns:
        dict: Utility templates keyed by name
    """

    utility_templates: dict[str, str] = {}
    for range in values.values():
        for row in range:
            utility_templates[str(row[0])] = row[1]

    return utility_templates


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
    """Create a hyperlink sheet function based on dispatch name and ID.

    Args:
        name (str): Dispatch name
        dispatch_id (str): Dispatch id

    Returns:
        str: Hyperlink function
    """
    return HYPERLINK_FORMAT.format(name=name, dispatch_id=dispatch_id)


class InvalidDispatchDataError(GoogleDispatchLoaderError):
    """Exception for invalid values on dispatch sheet rows."""

    def __init__(self, operation: DispatchOperation | str, *args: object) -> None:
        super().__init__(*args)
        self.operation = operation


class SkipRow(GoogleDispatchLoaderError):
    """Exception for dispatch sheet rows to skip when processing."""

    pass


def parse_dispatch_data_row(
    row_data: RowCellValues,
    spreadsheet_id: str,
    owner_nations: OwnerNationStore,
    category_setups: CategorySetupStore,
) -> Dispatch:
    """Parse a dispatch sheet row's data into a Dispatch object.

    Args:
        row_data (RowData): Dispatch row data
        spreadsheet_id (str): Spreadsheet ID
        owner_nations (OwnerNationData): Owner nation data
        category_setups (CategorySetupData): Category setup data

    Raises:
        SkipRow: This row must be skipped
        InvalidDispatchDataError: This row has invalid values

    Returns:
        Dispatch: Dispatch object
    """

    if not row_data[0]:
        raise SkipRow
    dispatch_id = extract_dispatch_id_from_hyperlink(str(row_data[0]))

    operation = str(row_data[1]).lower()
    if not operation:
        raise SkipRow
    try:
        operation = DispatchOperation[operation.upper()]
    except KeyError:
        raise InvalidDispatchDataError(operation, "Invalid operation.")

    if len(row_data) < 5:
        raise InvalidDispatchDataError(operation, "Not enough cells are filled.")

    owner_id = str(row_data[2])
    if not owner_id:
        raise InvalidDispatchDataError(operation, "Owner nation cell cannot be empty.")
    try:
        owner_nation = owner_nations[owner_id].nation_name
    except KeyError as err:
        raise InvalidDispatchDataError(operation, err)
    if not owner_nations.check_spreadsheet_permission(owner_id, spreadsheet_id):
        raise InvalidDispatchDataError(
            operation, f"Owner nation {owner_id} cannot be used on this spreadsheet."
        )

    category_setup_id = str(row_data[3])
    if not category_setup_id:
        raise InvalidDispatchDataError(
            operation, "Category setup cell cannot be empty."
        )
    try:
        category_setup = category_setups[category_setup_id]
        category = category_setup.category_name
        subcategory = category_setup.subcategory_name
    except KeyError as err:
        raise InvalidDispatchDataError(operation, err)

    title = str(row_data[4])
    if not title:
        raise InvalidDispatchDataError(operation, "Title cell cannot be empty")

    try:
        content = str(row_data[5])
    except IndexError:
        content = ""

    return Dispatch(
        dispatch_id, operation, owner_nation, title, category, subcategory, content
    )


ReportFailureCallback = Callable[
    [str, DispatchOperation | str, InvalidDispatchDataError], None
]


def parse_dispatch_data_rows(
    rows: RangeCellValues,
    spreadsheet_id: str,
    owner_nations: OwnerNationStore,
    category_setups: CategorySetupStore,
    report_failure: ReportFailureCallback,
) -> dict[str, Dispatch]:
    """Parse dispatch sheet rows' data into Dispatch objects.

    Args:
        rows (RangeCellValues): Dispatch data rows
        spreadsheet_id (str): Spreadsheet ID
        owner_nations (OwnerNationData): Owner nation data
        category_setups (CategorySetupData): Category setup data
        report_failure (ReportFailureFunc): Failure report callback

    Returns:
        dict[str, Dispatch]: Dispatch objects keyed by dispatch name
    """

    dispatches: dict[str, Dispatch] = {}

    for row in rows:
        dispatch_name = extract_name_from_hyperlink(str(row[0]))

        try:
            dispatch = parse_dispatch_data_row(
                row, spreadsheet_id, owner_nations, category_setups
            )
            dispatches[dispatch_name] = dispatch
        except SkipRow:
            logger.info(f'Skipped spreadsheet row of dispatch "{dispatch_name}"')
            continue
        except InvalidDispatchDataError as err:
            logger.error(
                f'Spreadsheet row of dispatch "{dispatch_name}" is invalid: {err}'
            )
            report_failure(dispatch_name, err.operation, err)

    return dispatches


def parse_dispatch_data_cell_ranges(
    values: MultiRangeCellValues,
    owner_nations: OwnerNationStore,
    category_setups: CategorySetupStore,
    report_failure: ReportFailureCallback,
) -> dict[str, Dispatch]:
    """Parse dispatch data from many sheet ranges into Dispatch objects.

    Args:
        values (SpreadsheetData): Cell data of many sheet ranges
        owner_nations (OwnerNationData): Owner nation data
        category_setups (CategorySetupData): Category setup data
        report_failure (ReportFailureFunc): Failure report callback

    Returns:
        dict[str, Dispatch]: Dispatch objects keyed by dispatch name
    """

    dispatches: dict[str, Dispatch] = {}
    for range, range_cell_values in values.items():
        row_dispatches = parse_dispatch_data_rows(
            range_cell_values,
            range.spreadsheet_id,
            owner_nations,
            category_setups,
            report_failure,
        )
        dispatches.update(row_dispatches)
    return dispatches


def generate_new_dispatch_data_rows(
    old_values: RangeCellValues,
    dispatch_data: Mapping[str, Dispatch],
    operation_results: Mapping[str, OpResult],
) -> RangeCellValues:
    """Generate new dispatch data row values for a sheet range
    with updated dispatch IDs and status messages.

    Args:
        old_values (RangeCellData): Old cell data of a dispatch sheet range
        dispatch_data (Mapping[str, Dispatch]): New dispatch data
        operation_results (Mapping[str, OperationResult]): Dispatch operation results

    Returns:
        RangeCellData: New dispatch cell data
    """

    new_row_data = copy.deepcopy(old_values)
    for row in new_row_data:
        # Skip rows with empty id, operation or are not long enough
        if (not (row[0] and row[1])) or len(row) < 6:
            continue

        name = extract_name_from_hyperlink(str(row[0]))

        try:
            result = operation_results[name]
        except KeyError:
            continue

        try:
            row[6] = result.result_message
        except IndexError:
            row.append(result.result_message)

        if isinstance(result, FailureOpResult):
            continue

        dispatch = dispatch_data[name]

        if (
            dispatch.operation == DispatchOperation.CREATE
            and dispatch.ns_id is not None
        ):
            row[0] = create_hyperlink(name, dispatch.ns_id)
            row[1] = "edit"
        elif dispatch.operation == DispatchOperation.DELETE:
            row[0] = name
            row[1] = ""

    return new_row_data


def generate_new_dispatch_values(
    old_values: MultiRangeCellValues,
    dispatch_data: Mapping[str, Dispatch],
    operation_results: Mapping[str, OpResult],
) -> MultiRangeCellValues:
    """_summary_

    Args:
        spreadsheet_data (MultiRangeCellData): Old cell data of dispatch sheet ranges
        dispatch_data (Mapping[str, Dispatch]): New dispatch data
        operation_results (Mapping[str, OperationResult]): Dispatch operation results

    Returns:
        MultiRangeCellData: New dispatch cell data
    """

    new_spreadsheet_data: Mapping[SheetRange, RangeCellValues] = {}
    for range, range_cell_values in old_values.items():
        new_range_cell_values = generate_new_dispatch_data_rows(
            range_cell_values, dispatch_data, operation_results
        )
        new_spreadsheet_data[range] = new_range_cell_values
    return new_spreadsheet_data


class DispatchData(UserDict[str, Dispatch]):
    """Manage dispatch data.

    Args:
        dispatches (Mapping[str, Dispatch]): Dispatch data
    """

    def __init__(self, dispatches: Mapping[str, Dispatch]):
        super().__init__(dispatches)

    def get_canonical_dispatch_config(self):
        """Get dispatch config in NSDU format.

        Returns:
            dict: Canonical dispatch config
        """

        result = {}
        for name, dispatch in self.data.items():
            match dispatch.operation:
                case DispatchOperation.CREATE:
                    canonical_operation = "create"
                case DispatchOperation.EDIT:
                    canonical_operation = "edit"
                case DispatchOperation.DELETE:
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

        return self.data[name].content

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
        spreadsheet_api (GoogleSpreadsheetApiAdapter): Spreadsheet API adapter
        dispatch_values (dict[CellRange, RangeCellValues]): Dispatch spreadsheet values
        utility_template_values (dict[CellRange, RangeCellValues]): Utility template spreadsheet values
        owner_nation_spreadsheet_data (RangeCellValues): Owner nation spreadsheet values
        category_setup_spreadsheet_data (RangeCellValues): Category setup spreadsheet values
    """

    def __init__(
        self,
        spreadsheet_api: GoogleSheetsApiAdapter,
        dispatch_values: Mapping[SheetRange, RangeCellValues],
        utility_template_values: Mapping[SheetRange, RangeCellValues],
        owner_nation_spreadsheet_data: RangeCellValues,
        category_setup_spreadsheet_data: RangeCellValues,
    ) -> None:
        self.spreadsheet_api = spreadsheet_api
        self.operation_result_recorder = OpResultStore()

        self.dispatch_values = dispatch_values

        self.owner_nations = OwnerNationStore.load_from_range_cell_values(
            owner_nation_spreadsheet_data
        )

        self.category_setups = CategorySetupStore.load_from_range_cell_values(
            category_setup_spreadsheet_data
        )

        self.utility_templates = parse_utility_template_cell_ranges(
            utility_template_values
        )

        self.dispatch_data = DispatchData(
            parse_dispatch_data_cell_ranges(
                self.dispatch_values,
                self.owner_nations,
                self.category_setups,
                self.operation_result_recorder.report_failure,
            )
        )

        logger.info("Pulled dispatch data from Google spreadsheets.")

    def get_dispatch_config(self) -> dict:
        """Get dispatch config.

        Returns:
            dict: Dispatch config
        """

        return self.dispatch_data.get_canonical_dispatch_config()

    def get_dispatch_template(self, name: str) -> str:
        """Get dispatch template text.

        Args:
            name (str): Dispatch name

        Returns:
            str: Template text
        """

        if name in self.utility_templates:
            return self.utility_templates[name]
        return self.dispatch_data.get_dispatch_template(name)

    def add_dispatch_id(self, name: str, dispatch_id: str) -> None:
        """Add id of new dispatch.

        Args:
            name (str): Dispatch name
            dispatch_id (str): Dispatch id
        """

        self.dispatch_data.add_dispatch_id(name, dispatch_id)

    def report_result(
        self,
        name: str,
        operation: DispatchOperation,
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
            self.operation_result_recorder.report_success(name, operation, result_time)
        else:
            self.operation_result_recorder.report_failure(
                name, operation, result, result_time
            )

    def update_spreadsheets(self) -> None:
        """Update spreadsheets."""

        new_dispatch_values = generate_new_dispatch_values(
            self.dispatch_values,
            self.dispatch_data,
            self.operation_result_recorder,
        )
        self.spreadsheet_api.update_values_of_ranges(new_dispatch_values)
        logger.info("Updated Google spreadsheets.")


def flatten_spreadsheet_config(config: Sequence[Any]) -> Sequence[SheetRange]:
    return [
        SheetRange(spreadsheet["spreadsheet_id"], range)
        for spreadsheet in config
        for range in spreadsheet["ranges"]
    ]


@loader_api.dispatch_loader
def init_dispatch_loader(config: Mapping):
    config = config["google_dispatch_loader"]

    google_api_creds = service_account.Credentials.from_service_account_file(
        config["google_cred_path"], scopes=GOOGLE_API_SCOPES
    )
    # pylint: disable=maybe-no-member
    google_api = (
        discovery.build(
            "sheets", "v4", credentials=google_api_creds, cache_discovery=False
        )
        .spreadsheets()
        .values()
    )
    spreadsheet_api = GoogleSheetsApiAdapter(google_api)

    owner_nation_range_cell_values = spreadsheet_api.get_values_of_range(
        SheetRange(
            config["owner_nation_sheet"]["spreadsheet_id"],
            config["owner_nation_sheet"]["range"],
        )
    )
    category_setup_range_cell_values = spreadsheet_api.get_values_of_range(
        SheetRange(
            config["category_setup_sheet"]["spreadsheet_id"],
            config["category_setup_sheet"]["range"],
        )
    )
    utility_template_range_cell_values = spreadsheet_api.get_values_of_ranges(
        flatten_spreadsheet_config(config["utility_template_spreadsheets"])
    )
    dispatch_spreadsheets = spreadsheet_api.get_values_of_ranges(
        flatten_spreadsheet_config(config["dispatch_spreadsheets"])
    )

    return GoogleDispatchLoader(
        spreadsheet_api,
        dispatch_spreadsheets,
        utility_template_range_cell_values,
        owner_nation_range_cell_values,
        category_setup_range_cell_values,
    )


@loader_api.dispatch_loader
def get_dispatch_config(loader: GoogleDispatchLoader):
    return loader.get_dispatch_config()


@loader_api.dispatch_loader
def get_dispatch_template(loader: GoogleDispatchLoader, name: str):
    return loader.get_dispatch_template(name)


@loader_api.dispatch_loader
def after_update(loader: GoogleDispatchLoader, name, action, result, result_time):
    match action:
        case "create":
            operation = DispatchOperation.CREATE
        case "edit":
            operation = DispatchOperation.EDIT
        case "remove":
            operation = DispatchOperation.DELETE
        case _:
            raise ValueError("Invalid dispatch action")

    loader.report_result(name, operation, result, result_time)


@loader_api.dispatch_loader
def add_dispatch_id(loader: GoogleDispatchLoader, name: str, dispatch_id: str):
    loader.add_dispatch_id(name, dispatch_id)


@loader_api.dispatch_loader
def cleanup_dispatch_loader(loader: GoogleDispatchLoader):
    loader.update_spreadsheets()
