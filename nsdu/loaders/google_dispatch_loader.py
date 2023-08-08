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
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

from google.oauth2 import service_account
from googleapiclient import discovery
from googleapiclient.http import HttpError

from nsdu import exceptions, loader_api

GOOGLE_API_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

HYPERLINK_PATTERN = (
    r'=hyperlink\("https://www.nationstates.net/page=dispatch/id=(\d+)",\s*"(.+)"\)'
)
HYPERLINK_FORMAT = (
    '=hyperlink("https://www.nationstates.net/page=dispatch/id={dispatch_id}","{name}")'
)


class DispatchOperation(Enum):
    """Dispatch operation type."""

    CREATE = 1
    EDIT = 2
    DELETE = 3


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

RowCellData = list[Any]
RangeCellData = list[RowCellData]


@dataclass(frozen=True)
class SheetRange:
    """Describe the spreadsheet ID and range name of a range."""

    spreadsheet_id: str
    range_name: str


MultiRangeCellData = Mapping[SheetRange, RangeCellData]


class GoogleSpreadsheetApiAdapter:
    """Adapter for Google Spreadsheet API.

    Args:
        api: Google Spreadsheet API
    """

    def __init__(self, api):
        self._api = api

    @staticmethod
    def execute(request) -> dict:
        """Execute API request.

        Args:
            request: API request

        Raises:
            exceptions.LoaderError: API error

        Returns:
            dict: API response
        """

        try:
            return request.execute()
        except HttpError as err:
            raise exceptions.LoaderError(
                "Google API error {}: {}".format(err.status_code, err.error_details)
            )

    def get_data_from_ranges(
        self, ranges: Sequence[SheetRange]
    ) -> dict[SheetRange, RangeCellData]:
        """Get cell data from many spreadsheet ranges.

        Args:
            ranges (Sequence[CellRange]): Ranges to get

        Returns:
            dict[CellRange, RangeData]: Cell data
        """

        multi_range_cell_data: dict[SheetRange, RangeCellData] = {}

        spreadsheets = itertools.groupby(ranges, lambda range: range.spreadsheet_id)
        for spreadsheet_id, cell_ranges in spreadsheets:
            cell_ranges = list(
                map(lambda cell_range: cell_range.range_name, cell_ranges)
            )

            req = self._api.batchGet(
                spreadsheetId=spreadsheet_id,
                ranges=cell_ranges,
                valueRenderOption="FORMULA",
            )
            resp = GoogleSpreadsheetApiAdapter.execute(req)
            logger.debug(
                'Pulled values from ranges "%r" of spreadsheet "%s": "%r"',
                cell_ranges,
                spreadsheet_id,
                resp,
            )

            range_cell_data = {
                SheetRange(spreadsheet_id, range["range"]): range.get("values", [])
                for range in resp["valueRanges"]
            }

            multi_range_cell_data.update(range_cell_data)

        return multi_range_cell_data

    def get_data_from_range(self, range: SheetRange) -> RangeCellData:
        """Get cell data from a spreadsheet range.

        Args:
            ranges (CellRange): Range to get

        Returns:
            RangeData: Cell data
        """
        result = self.get_data_from_ranges([range])
        return next(iter(result.values()))

    def update_cells(
        self, new_range_cell_data: Mapping[SheetRange, RangeCellData]
    ) -> None:
        """Update cell data of spreadsheet ranges.

        Args:
            new_range_cell_data (Mapping[CellRange, RangeData]): New cell data
        """

        spreadsheets = itertools.groupby(
            new_range_cell_data.keys(), lambda range: range.spreadsheet_id
        )
        for spreadsheet_id, ranges in spreadsheets:
            new_data = list(
                map(
                    lambda range: {
                        "range": range.range_name,
                        "majorDimension": "ROWS",
                        "values": new_range_cell_data[range],
                    },
                    ranges,
                )
            )
            body = {"valueInputOption": "USER_ENTERED", "data": new_data}
            req = self._api.batchUpdate(spreadsheetId=spreadsheet_id, body=body)
            GoogleSpreadsheetApiAdapter.execute(req)
            logger.debug(
                'Updated cell data of spreadsheet "%s": %r', spreadsheet_id, body
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


class OperationResultStore(UserDict[str, OpResult]):
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


class CategorySetupData:
    """Contains information about dispatch category setup.

    Args:
        categories (Mapping[str, str]): Category names of setup IDs
        subcategories (Mapping[str, str]): Subcategory names of setup IDs
    """

    def __init__(self, categories: Mapping[str, str], subcategories: Mapping[str, str]):
        self.categories = categories
        self.subcategories = subcategories

    @classmethod
    def load_from_range_cell_data(cls, range_cell_data: RangeCellData):
        """Load category setup data from spreadsheet cell data.

        Args:
            range_cell_data (RangeData): Cell data

        Returns:
            CategorySetupData
        """

        categories: dict[str, str] = {}
        subcategories: dict[str, str] = {}
        # In case of similar IDs, the latest one is used
        for row in range_cell_data:
            setup_id = str(row[0])
            category_name = str(row[1])
            subcategory_name = str(row[2])

            categories[setup_id] = category_name
            subcategories[setup_id] = subcategory_name

        return cls(categories, subcategories)

    def get_category_subcategory_name(self, setup_id: str) -> tuple[str, str]:
        """Get the category and subcategory name of a setup ID.

        Args:
            setup_id (str): Setup ID

        Raises:
            KeyError: Setup ID does not exist

        Returns:
            tuple[str, str]: Category and subcategory name
        """

        if setup_id not in self.categories:
            raise KeyError(f"Could not find category setup ID {setup_id}")
        return self.categories[setup_id], self.subcategories[setup_id]


SpreadsheetIds = Sequence[str]


class OwnerNationData:
    """Contains information about dispatch owner nations.

    Args:
        owner_nation_names (Mapping[str, str]): Owner nation names
        allowed_spreadsheet_ids (Mapping[str, SpreadsheetIds])  : Allowed spreadsheets of each owner
    """

    def __init__(
        self,
        owner_nation_names: Mapping[str, str],
        allowed_spreadsheet_ids: Mapping[str, SpreadsheetIds],
    ) -> None:
        self.owner_nation_names = owner_nation_names
        self.allowed_spreadsheet_ids = allowed_spreadsheet_ids

    @classmethod
    def load_from_range_cell_data(cls, range_cell_data: RangeCellData):
        """Load owner nation data from spreadsheet cell data.

        Args:
            range_cell_data (RangeData): Cell data

        Returns:
            OwnerNationData
        """

        owner_nation_names: dict[str, str] = {}
        allowed_spreadsheet_ids: dict[str, SpreadsheetIds] = {}
        # If there are similar IDs, the latest one is used
        for row in range_cell_data:
            owner_id = str(row[0])
            owner_nation_name = str(row[1])
            allowed_spreadsheets = str(row[2])

            owner_nation_names[owner_id] = owner_nation_name
            allowed_spreadsheet_ids[owner_id] = allowed_spreadsheets.split(",")

        return cls(owner_nation_names, allowed_spreadsheet_ids)

    def get_owner_nation_name(self, owner_id: str) -> str:
        """Get owner nation name from owner ID.

        Args:
            owner_id (int): Owner nation ID

        Raises:
            KeyError: Owner nation does not exist

        Returns:
            str: Owner nation name
        """

        if owner_id not in self.owner_nation_names:
            raise KeyError(f'Could not find any nation with owner ID "{owner_id}"')

        return self.owner_nation_names[owner_id]

    def check_spreadsheet_permission(self, owner_id: str, spreadsheet_id: str) -> bool:
        """Check if the provided owner ID can be used with the provided spreadsheet ID.

        Args:
            owner_id (str): Owner ID
            spreadsheet_id (str): Spreadsheet ID

        Returns:
            bool: True if allowed
        """

        if owner_id not in self.allowed_spreadsheet_ids:
            raise KeyError(f'Could not find any nation with owner ID "{owner_id}"')

        return spreadsheet_id in self.allowed_spreadsheet_ids[owner_id]


def parse_utility_template_cell_ranges(
    cell_data: Mapping[SheetRange, RangeCellData]
) -> dict[str, str]:
    """Get utility template content from cell data of many sheet ranges.

    Args:
        cell_data (Mapping[SheetRange, RangeCellData]): Cell data of many sheet ranges

    Returns:
        dict: Utility templates keyed by name
    """

    utility_templates: dict[str, str] = {}
    for range in cell_data.values():
        for row in range:
            utility_templates[row[0]] = row[1]

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


@dataclass(frozen=True)
class Dispatch:
    """Contains the metadata and content of a dispatch."""

    ns_id: str | None
    operation: DispatchOperation
    owner_nation: str
    title: str
    category: str
    subcategory: str
    content: str


class InvalidDispatchDataError(Exception):
    """Exception for invalid values on dispatch sheet rows."""

    def __init__(self, operation: DispatchOperation | str, *args: object) -> None:
        super().__init__(*args)
        self.operation = operation


class SkipRow(Exception):
    """Exception for dispatch sheet rows to skip when processing."""

    pass


def parse_dispatch_data_row(
    row_data: RowCellData,
    spreadsheet_id: str,
    owner_nations: OwnerNationData,
    category_setups: CategorySetupData,
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
        owner_nation = owner_nations.get_owner_nation_name(owner_id)
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
        category, subcategory = category_setups.get_category_subcategory_name(
            category_setup_id
        )
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
    rows: RangeCellData,
    spreadsheet_id: str,
    owner_nations: OwnerNationData,
    category_setups: CategorySetupData,
    report_failure: ReportFailureCallback,
) -> dict[str, Dispatch]:
    """Parse dispatch sheet rows' data into Dispatch objects.

    Args:
        rows (RangeData): Dispatch data rows
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
    cell_data: MultiRangeCellData,
    owner_nations: OwnerNationData,
    category_setups: CategorySetupData,
    report_failure: ReportFailureCallback,
) -> dict[str, Dispatch]:
    """Parse dispatch data from many sheet ranges into Dispatch objects.

    Args:
        cell_data (SpreadsheetData): Cell data of many sheet ranges
        owner_nations (OwnerNationData): Owner nation data
        category_setups (CategorySetupData): Category setup data
        report_failure (ReportFailureFunc): Failure report callback

    Returns:
        dict[str, Dispatch]: Dispatch objects keyed by dispatch name
    """

    dispatches: dict[str, Dispatch] = {}
    for range, range_cell_data in cell_data.items():
        row_dispatches = parse_dispatch_data_rows(
            range_cell_data,
            range.spreadsheet_id,
            owner_nations,
            category_setups,
            report_failure,
        )
        dispatches.update(row_dispatches)
    return dispatches


def generate_new_dispatch_data_rows(
    old_cell_data: RangeCellData,
    dispatch_data: Mapping[str, Dispatch],
    operation_results: Mapping[str, OpResult],
) -> RangeCellData:
    """Generate new dispatch data row values for a sheet range
    with updated dispatch IDs and status messages.

    Args:
        old_cell_data (RangeCellData): Old cell data of a dispatch sheet range
        dispatch_data (Mapping[str, Dispatch]): New dispatch data
        operation_results (Mapping[str, OperationResult]): Dispatch operation results

    Returns:
        RangeCellData: New dispatch cell data
    """

    new_row_data = copy.deepcopy(old_cell_data)
    for row in new_row_data:
        # Skip rows with empty id, operation or are not long enough
        if (not (row[0] and row[1])) or len(row) < 6:
            continue

        name = extract_name_from_hyperlink(row[0])

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


def generate_new_dispatch_cell_data(
    old_cell_data: MultiRangeCellData,
    dispatch_data: Mapping[str, Dispatch],
    operation_results: Mapping[str, OpResult],
) -> MultiRangeCellData:
    """_summary_

    Args:
        spreadsheet_data (MultiRangeCellData): Old cell data of dispatch sheet ranges
        dispatch_data (Mapping[str, Dispatch]): New dispatch data
        operation_results (Mapping[str, OperationResult]): Dispatch operation results

    Returns:
        MultiRangeCellData: New dispatch cell data
    """

    new_spreadsheet_data: Mapping[SheetRange, RangeCellData] = {}
    for range, range_cell_data in old_cell_data.items():
        new_range_cell_data = generate_new_dispatch_data_rows(
            range_cell_data, dispatch_data, operation_results
        )
        new_spreadsheet_data[range] = new_range_cell_data
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
        dispatch_cell_data (dict[CellRange, RangeData]): Dispatch spreadsheet values
        utility_template_cell_data (dict[CellRange, RangeData]): Utility template spreadsheet values
        owner_nation_spreadsheet_data (RangeData): Owner nation spreadsheet values
        category_setup_spreadsheet_data (RangeData): Category setup spreadsheet values
    """

    def __init__(
        self,
        spreadsheet_api: GoogleSpreadsheetApiAdapter,
        dispatch_cell_data: Mapping[SheetRange, RangeCellData],
        utility_template_cell_data: Mapping[SheetRange, RangeCellData],
        owner_nation_spreadsheet_data: RangeCellData,
        category_setup_spreadsheet_data: RangeCellData,
    ) -> None:
        self.spreadsheet_api = spreadsheet_api
        self.operation_result_recorder = OperationResultStore()

        self.dispatch_cell_data = dispatch_cell_data

        self.owner_nations = OwnerNationData.load_from_range_cell_data(
            owner_nation_spreadsheet_data
        )

        self.category_setups = CategorySetupData.load_from_range_cell_data(
            category_setup_spreadsheet_data
        )

        self.utility_templates = parse_utility_template_cell_ranges(
            utility_template_cell_data
        )

        self.dispatch_data = DispatchData(
            parse_dispatch_data_cell_ranges(
                self.dispatch_cell_data,
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

        new_dispatch_cell_data = generate_new_dispatch_cell_data(
            self.dispatch_cell_data,
            self.dispatch_data,
            self.operation_result_recorder,
        )
        self.spreadsheet_api.update_cells(new_dispatch_cell_data)
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
    spreadsheet_api = GoogleSpreadsheetApiAdapter(google_api)

    owner_nation_range_cell_data = spreadsheet_api.get_data_from_range(
        SheetRange(
            config["owner_nation_sheet"]["spreadsheet_id"],
            config["owner_nation_sheet"]["range"],
        )
    )
    category_setup_range_cell_data = spreadsheet_api.get_data_from_range(
        SheetRange(
            config["category_setup_sheet"]["spreadsheet_id"],
            config["category_setup_sheet"]["range"],
        )
    )
    utility_template_range_cell_data = spreadsheet_api.get_data_from_ranges(
        flatten_spreadsheet_config(config["utility_template_spreadsheets"])
    )
    dispatch_spreadsheets = spreadsheet_api.get_data_from_ranges(
        flatten_spreadsheet_config(config["dispatch_spreadsheets"])
    )

    return GoogleDispatchLoader(
        spreadsheet_api,
        dispatch_spreadsheets,
        utility_template_range_cell_data,
        owner_nation_range_cell_data,
        category_setup_range_cell_data,
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
