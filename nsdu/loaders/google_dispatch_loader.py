"""Load dispatches from Google spreadsheets.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import copy
from datetime import datetime
from datetime import timezone
import itertools
import re
import logging
from typing import Mapping, Optional, Sequence

from google.oauth2 import service_account
from googleapiclient import discovery
from googleapiclient.http import HttpError

from nsdu import exceptions
from nsdu import loader_api


GOOGLE_API_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
HYPERLINK_REGEX = (
    r'=hyperlink\("https://www.nationstates.net/page=dispatch/id=(\d+)",\s*"(.+)"\)'
)
HYPERLINK_BUILD_FORMAT = (
    '=hyperlink("https://www.nationstates.net/page=dispatch/id={dispatch_id}","{name}")'
)

SUCCESS_MESSAGE_FORMATS = {
    "create": "Created on {time}",
    "edit": "Edited on {time}",
    "remove": "Removed on {time}",
}
FAILURE_MESSAGE_FORMATS = {
    "create": "Failed to create on {time}",
    "edit": "Failed to edit on {time}",
    "remove": "Failed to remove on {time}",
}
FAILURE_DETAILS_FORMAT = "\nError: {details}"
RESULT_TIME_FORMAT = "%Y/%m/%d %H:%M:%S %Z"


logger = logging.getLogger(__name__)

CellValue = str | int | float

CellData = list[list[CellValue]]


@dataclass(frozen=True)
class CellRange:
    """Describe the spreadsheet ID and range name of a range."""

    spreadsheet_id: str
    range_name: str


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

    def get_cell_data(
        self, range: Sequence[CellRange] | CellRange
    ) -> dict[CellRange, CellData] | CellData:
        """Get call data from spreadsheet range(s).

        Args:
            range (Sequence[CellRange] | CellRange): Range(s) to get

        Returns:
            dict[CellRange, CellData]: Cell data
        """

        cell_data: dict[CellRange, CellData] = {}

        if isinstance(range, CellRange):
            ranges = [range]
        else:
            ranges = range

        spreadsheets = itertools.groupby(ranges, lambda range: range.spreadsheet_id)
        for spreadsheet_id, ranges in spreadsheets:
            range_values = list(map(lambda range: range.range_name, ranges))

            req = self._api.batchGet(
                spreadsheetId=spreadsheet_id,
                ranges=range_values,
                valueRenderOption="FORMULA",
            )
            resp = GoogleSpreadsheetApiAdapter.execute(req)
            logger.debug(
                'Pulled values from ranges "%r" of spreadsheet "%s": "%r"',
                range,
                spreadsheet_id,
                resp,
            )

            range_data = {
                CellRange(spreadsheet_id, range["range"]): range.get("values", [])
                for range in resp["valueRanges"]
            }

            cell_data.update(range_data)

        if isinstance(range, CellRange):
            return cell_data[range]
        return cell_data

    def update_cell_data(self, new_cell_data: Mapping[CellRange, CellData]) -> None:
        """Update cell data of spreadsheet range(s).

        Args:
            new_cell_data (Mapping[CellRange, CellData]): New cell data
        """

        spreadsheets = itertools.groupby(
            new_cell_data.keys(), lambda range: range.spreadsheet_id
        )
        for spreadsheet_id, ranges in spreadsheets:
            new_data = list(
                map(
                    lambda range: {
                        "range": range.range_name,
                        "majorDimension": "ROWS",
                        "values": new_cell_data[range],
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
class Result(ABC):
    """Describes an operation result."""

    dispatch_name: str
    action: str
    result_time: datetime

    @property
    @abstractmethod
    def user_message(self) -> str:
        pass


@dataclass(frozen=True)
class SuccessResult(Result):
    """Describes a successful operation result."""

    @property
    def user_message(self) -> str:
        time_string = self.result_time.strftime(RESULT_TIME_FORMAT)
        return SUCCESS_MESSAGE_FORMATS[self.action].format(time=time_string)


@dataclass(frozen=True)
class FailureResult(Result):
    """Describes a failure operation result."""

    details: str | None

    @property
    def user_message(self) -> str:
        time_string = self.result_time.strftime(RESULT_TIME_FORMAT)
        message = FAILURE_MESSAGE_FORMATS[self.action].format(time=time_string)
        message += FAILURE_DETAILS_FORMAT.format(details=self.details)
        return message


class ResultRecorder:
    """Records the results of spreadsheet and dispatch update operations."""

    def __init__(self):
        self.results: dict[str, SuccessResult | FailureResult] = {}

    def get_result(self, dispatch_name: str) -> SuccessResult | FailureResult:
        return self.results[dispatch_name]

    def report_success(
        self, dispatch_name: str, action: str, result_time: datetime | None = None
    ) -> None:
        """Report a successful operation.

        Args:
            dispatch_name (str): Dispatch name
            action (str): Dispatch action
            result_time (datetime | None) The time the operation happened. Use current time if None.
        """

        if result_time is None:
            result_time = datetime.now(tz=timezone.utc)
        self.results[dispatch_name] = SuccessResult(dispatch_name, action, result_time)

    def report_failure(
        self,
        dispatch_name: str,
        action: str,
        details: str | Exception | None = None,
        result_time: datetime | None = None,
    ) -> None:
        """Report a failed operation.

        Args:
            dispatch_name (str): Dispatch name
            action (str): Dispatch action
            details (str | Exception | None): Error details
            result_time (datetime.datetime) Time the operation happened. Use current time if None.
        """

        if isinstance(details, Exception):
            details = str(details)

        if result_time is None:
            result_time = datetime.now(tz=timezone.utc)

        self.results[dispatch_name] = FailureResult(
            dispatch_name, action, result_time, details
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
    def load_from_cell_data(cls, cell_data: CellData):
        """Load category setup data from spreadsheet cell data.

        Args:
            cell_data (CellData): Cell data

        Returns:
            CategorySetupData
        """

        categories: dict[str, str] = {}
        subcategories: dict[str, str] = {}
        # In case of similar IDs, the latest one is used
        for row in cell_data:
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
    def load_from_cell_data(cls, cell_data: CellData):
        """Load owner nation data from spreadsheet cell data.

        Args:
            cell_data (CellData): Cell data

        Returns:
            OwnerNationData
        """

        owner_nation_names: dict[str, str] = {}
        allowed_spreadsheet_ids: dict[str, SpreadsheetIds] = {}
        # If there are similar IDs, the latest one is used
        for row in cell_data:
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


def load_utility_templates_from_spreadsheets(spreadsheets):
    """Load utility templates from spreadsheets.

    Args:
        spreadsheets (list): Spreadsheet data

    Returns:
        dict: Layouts keyed by name
    """

    utility_templates = {}
    for spreadsheet in spreadsheets.values():
        for rows in spreadsheet.values():
            for row in rows:
                utility_templates[row[0]] = row[1]

    return utility_templates


def extract_dispatch_id_from_hyperlink(cell_value: str) -> str | None:
    """Extract dispatch ID from the HYPERLINK function in the dispatch name cell.

    Args:
        cell_value (str): Dispatch name cell value

    Returns:
        str | None: Dispatch ID
    """

    result = re.search(HYPERLINK_REGEX, cell_value, flags=re.IGNORECASE)
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

    result = re.search(HYPERLINK_REGEX, cell_value, flags=re.IGNORECASE)
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
    return HYPERLINK_BUILD_FORMAT.format(name=name, dispatch_id=dispatch_id)


class RangeDispatchData:
    """Dispatch data of a spreadsheet range.

    Args:
        row_values (list): Row values
        result_recorder (ResultReporter): Result reporter
    """

    def __init__(self, cell_data: CellData, result_recorder: ResultRecorder):
        self.cell_data = cell_data
        self.result_recorder = result_recorder

    def get_dispatches_as_dict(self, owner_nations, category_setups, spreadsheet_id):
        """Get dispatches in this range as a dict of dispatch config
        and content keyed by dispatch name.

        Args:
            owner_nations (OwnerNations): Owner nation instance
            category_setups (CategorySetups): Category setup instance
            spreadsheet_id (str): Spreadsheet Id of this range

        Returns:
            dict: Dispatch information keyed by dispatch name
        """

        dispatch_data = {}
        for row in self.cell_data:
            if len(row) < 6:
                continue

            if not row[0]:
                continue
            name = extract_name_from_hyperlink(row[0])

            action = row[1]
            if not action:
                continue
            if action not in ("create", "edit", "remove"):
                self.result_recorder.report_failure(name, action, "Invalid action")
                continue

            try:
                owner_nation = owner_nations.get_owner_nation_name(
                    row[2], spreadsheet_id
                )
            except KeyError:
                self.result_recorder.report_failure(
                    name, action, "This owner nation does not exist."
                )
                continue
            except ValueError:
                self.result_recorder.report_failure(
                    name, action, "This spreadsheet does not allow this owner nation."
                )
                continue

            try:
                category, subcategory = category_setups.get_category_subcategory_name(
                    row[3]
                )
            except KeyError:
                self.result_recorder.report_failure(
                    name, action, "This category setup does not exist."
                )
                continue

            data = {
                "action": action,
                "owner_nation": owner_nation,
                "category": category,
                "subcategory": subcategory,
                "title": row[4],
                "template": row[5],
            }

            dispatch_id = extract_dispatch_id_from_hyperlink(row[0])
            if dispatch_id:
                data["ns_id"] = dispatch_id

            dispatch_data[name] = data

        return dispatch_data

    def get_new_values(self, new_dispatch_data):
        """Get new row values from new dispatch data.

        Args:
            new_dispatch_data (dict): New dispatch data

        Returns:
            list: New row values.
        """

        new_row_values = copy.deepcopy(self.cell_data)
        for row in new_row_values:
            # SKip rows with empty title or template cell
            if len(row) < 6:
                continue

            # Skip row with empty action
            if not row[0] or not row[1]:
                continue

            name = extract_name_from_hyperlink(row[0])

            try:
                result = self.result_recorder.get_result(name)
                try:
                    row[6] = result.user_message
                except IndexError:
                    row.append(result.user_message)
                if isinstance(result, FailureResult):
                    continue
            except KeyError:
                continue

            if new_dispatch_data[name]["action"] == "remove":
                row[0] = name
                row[1] = ""
            elif new_dispatch_data[name]["action"] == "create":
                row[0] = create_hyperlink(name, new_dispatch_data[name]["ns_id"])
                row[1] = "edit"

        return new_row_values


class DispatchSpreadsheet:
    """A spreadsheet that contains dispatches.

    Args:
        sheet_ranges (list): Ranges of this spreadsheet
        result_recorder (ResultReporter): Result reporter instance
    """

    def __init__(self, sheet_ranges, result_recorder):
        self.values_of_ranges = {}
        for sheet_range, range_values in sheet_ranges.items():
            self.values_of_ranges[sheet_range] = RangeDispatchData(
                range_values, result_recorder
            )
        self.result_recorder = result_recorder

    def get_dispatches_as_dict(self, owner_nations, category_setups, spreadsheet_id):
        """Extract dispatch data from configured ranges in this spreadsheet.

        Args:
            owner_nations (OwnerNations): Owner nation instance
            category_setups (CategorySetups): Category setup instance
            spreadsheet_id (str): Id of this spreadsheet

        Returns:
            dict: Extracted dispatch data keyed by dispatch name
        """

        all_dispatch_data = {}
        for range_data_values in self.values_of_ranges.values():
            dispatch_data = range_data_values.get_dispatches_as_dict(
                owner_nations, category_setups, spreadsheet_id
            )
            all_dispatch_data.update(dispatch_data)

        return all_dispatch_data

    def get_new_values(self, new_dispatch_data):
        """Get new spreadsheet values from new dispatch data.

        Args:
            new_dispatch_data (dict): New dispatch data

        Returns:
            dict: New spreadsheet values
        """

        new_spreadsheet_values = {}
        for sheet_range, range_data_values in self.values_of_ranges.items():
            new_spreadsheet_values[sheet_range] = range_data_values.get_new_values(
                new_dispatch_data
            )

        return new_spreadsheet_values


class DispatchSpreadsheets:
    """Spreadsheets that contain dispatches.

    Args:
        spreadsheets (str): Spreadsheet data
        result_recorder (ResultReporter): Result reporter instance
    """

    def __init__(self, spreadsheets, result_recorder):
        self.spreadsheets = {}
        for spreadsheet_id, sheet_ranges in spreadsheets.items():
            self.spreadsheets[spreadsheet_id] = DispatchSpreadsheet(
                sheet_ranges, result_recorder
            )

        self.result_recorder = result_recorder

    def get_dispatches_as_dict(self, owner_nations, category_setups):
        """Extract dispatch data from spreadsheets.

        Args:
            owner_nations (OwnerNations): Owner nations
            category_setups (CategorySetups): Category setups

        Returns:
            dict: Dispatch data keyed by dispatch name
        """

        all_dispatch_data = {}
        for spreadsheet_id, spreadsheet_data in self.spreadsheets.items():
            dispatch_data = spreadsheet_data.get_dispatches_as_dict(
                owner_nations, category_setups, spreadsheet_id
            )
            all_dispatch_data.update(dispatch_data)

        return all_dispatch_data

    def get_new_values(self, new_dispatch_data):
        """Get new values of spreadsheets from new data.

        Args:
            new_dispatch_data (dict): New dispatch data, keyed by dispatch name

        Returns:
            dict: New spreadsheets keyed by spreadsheet id
        """

        new_spreadsheets = {}
        for spreadsheet_id, spreadsheet_data in self.spreadsheets.items():
            new_spreadsheets[spreadsheet_id] = spreadsheet_data.get_new_values(
                new_dispatch_data
            )

        return new_spreadsheets


class Dispatches:
    """Manage dispatch data.

    Args:
        dispatch_data (dict): Canonical dispatch data
    """

    def __init__(self, dispatch_data):
        self.dispatch_data = dispatch_data

    def get_canonical_dispatch_config(self):
        """Get dispatch config in NSDU format.

        Returns:
            dict: Canonicalized dispatch config
        """

        result = {}
        for name, config in self.dispatch_data.items():
            canonical_config = {
                "action": config["action"],
                "title": config["title"],
                "category": config["category"],
                "subcategory": config["subcategory"],
            }
            if "ns_id" in config:
                canonical_config["ns_id"] = config["ns_id"]
            owner_nation = config["owner_nation"]
            if owner_nation not in result:
                result[owner_nation] = {}
            result[owner_nation][name] = canonical_config
        return result

    def get_dispatch_template(self, name):
        """Get dispatch template text.

        Args:
            name (str): Dispatch name

        Returns:
            str: Template text
        """

        return self.dispatch_data[name]["template"]

    def add_dispatch_id(self, name, dispatch_id):
        """Add id of new dispatch.

        Args:
            name (str): Dispatch name
            dispatch_id (str): Dispatch id
        """

        self.dispatch_data[name]["ns_id"] = dispatch_id


class GoogleDispatchLoader:
    """Google spreadsheet dispatch loader.

    Args:
        spreadsheet_api (googleapiclients): Google Spreadsheet Api
        dispatch_spreadsheets (dict): Dispatch spreadsheet values
        utility_template_spreadsheets (dict): Utility template spreadsheet values
        owner_nation_rows (dict): Owner nation spreadsheet values
        category_setup_rows (dict): Category setup spreadsheet values
    """

    def __init__(
        self,
        spreadsheet_api,
        dispatch_spreadsheets,
        utility_template_spreadsheets,
        owner_nation_rows,
        category_setup_rows,
    ):
        self.spreadsheet_api = spreadsheet_api

        owner_nations = OwnerNationData.load_from_cell_data(owner_nation_rows)
        category_setups = CategorySetupData.load_from_cell_data(category_setup_rows)

        self.utility_templates = load_utility_templates_from_spreadsheets(
            utility_template_spreadsheets
        )

        self.result_recorder = ResultRecorder()

        self.converter = DispatchSpreadsheets(
            dispatch_spreadsheets, self.result_recorder
        )
        extracted_data = self.converter.get_dispatches_as_dict(
            owner_nations, category_setups
        )
        self.dispatch_data = Dispatches(extracted_data)
        logger.info("Pulled dispatch data from Google spreadsheets.")

    def get_dispatch_config(self):
        """Get dispatch config.

        Returns:
            dict: Dispatch config
        """

        return self.dispatch_data.get_canonical_dispatch_config()

    def get_dispatch_template(self, name):
        """Get dispatch template text.

        Args:
            name (str): Dispatch name

        Returns:
            str: Template text
        """

        if name in self.utility_templates:
            return self.utility_templates[name]
        return self.dispatch_data.get_dispatch_template(name)

    def add_dispatch_id(self, name, dispatch_id):
        """Add id of new dispatch.

        Args:
            name (str): Dispatch name
            dispatch_id (str): Dispatch id
        """

        self.dispatch_data.add_dispatch_id(name, dispatch_id)

    def report_result(self, name, action, result, result_time):
        """Report operation result from NSDU.

        Args:
            name (str): Dispatch name
            action (str): Action
            result (str): Result
            result_time (datetime.Datetime): Time update operation happened
        """

        if result == "success":
            self.result_recorder.report_success(name, action, result_time)
        else:
            self.result_recorder.report_failure(name, action, result, result_time)

    def update_spreadsheets(self):
        """Update spreadsheets."""

        new_spreadsheet_values = self.converter.get_new_values(
            self.dispatch_data.dispatch_data
        )
        self.spreadsheet_api.update_rows_in_many_spreadsheets(new_spreadsheet_values)
        logger.info("Updated Google spreadsheets.")


@loader_api.dispatch_loader
def init_dispatch_loader(config: Mapping):
    config = config["google_dispatchloader"]

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

    owner_nation_rows = spreadsheet_api.get_cell_data(
        CellRange(
            config["owner_nation_sheet"]["spreadsheet_id"],
            config["owner_nation_sheet"]["range"],
        )
    )
    category_setup_rows = spreadsheet_api.get_cell_data(
        CellRange(
            config["category_setup_sheet"]["spreadsheet_id"],
            config["category_setup_sheet"]["range"],
        )
    )
    utility_template_spreadsheets = spreadsheet_api.get_cell_data(
        config["utility_template_spreadsheets"]
    )
    dispatch_spreadsheets = spreadsheet_api.get_cell_data(
        config["dispatch_spreadsheets"]
    )

    return GoogleDispatchLoader(
        spreadsheet_api,
        dispatch_spreadsheets,
        utility_template_spreadsheets,
        owner_nation_rows,
        category_setup_rows,
    )


@loader_api.dispatch_loader
def get_dispatch_config(loader: GoogleDispatchLoader):
    return loader.get_dispatch_config()


@loader_api.dispatch_loader
def get_dispatch_template(loader: GoogleDispatchLoader, dispatch_name: str):
    return loader.get_dispatch_template(dispatch_name)


@loader_api.dispatch_loader
def after_update(loader: GoogleDispatchLoader, name, action, result, result_time):
    loader.report_result(name, action, result, result_time)


@loader_api.dispatch_loader
def add_dispatch_id(loader: GoogleDispatchLoader, dispatch_name: str, dispatch_id: str):
    loader.add_dispatch_id(dispatch_name, dispatch_id)


@loader_api.dispatch_loader
def cleanup_dispatch_loader(loader: GoogleDispatchLoader):
    loader.update_spreadsheets()
