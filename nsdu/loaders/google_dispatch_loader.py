"""Load dispatches from Google spreadsheets.
"""

from dataclasses import dataclass
import collections
import copy
from datetime import datetime
from datetime import timezone
import itertools
import re
import logging
from typing import Mapping, Sequence

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

CellData = list[list[str]]


@dataclass(frozen=True)
class SheetRange:
    spreadsheet_id: str
    range_value: str


class GoogleSpreadsheetApiAdapter:
    """Adapter for Google Spreadsheet API.

    Args:
        sheet_api: Google Spreadsheet API
    """

    def __init__(self, sheet_api):
        self.sheet_api = sheet_api

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
        self, range: Sequence[SheetRange] | SheetRange
    ) -> dict[SheetRange, CellData] | CellData:
        """Get call data from spreadsheet ranges.

        Args:
            range (Sequence[SheetRange] | SheetRange): Range(s) to get

        Returns:
            dict[SheetRange, CellData]: Cell data
        """

        cell_data: dict[SheetRange, CellData] = {}

        if isinstance(range, SheetRange):
            ranges = [range]
        else:
            ranges = range

        spreadsheets = itertools.groupby(ranges, lambda range: range.spreadsheet_id)
        for spreadsheet_id, ranges in spreadsheets:
            range_values = list(map(lambda range: range.range_value, ranges))

            req = self.sheet_api.batchGet(
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
                SheetRange(spreadsheet_id, range["range"]): range.get("values", [])
                for range in resp["valueRanges"]
            }

            cell_data.update(range_data)

        if isinstance(range, SheetRange):
            return cell_data[range]
        return cell_data

    def update_cell_data(self, new_cell_data: Mapping[SheetRange, CellData]) -> None:
        """Update cell values of many ranges in a spreadsheet.

        Args:
            spreadsheet_id (str): Spreadsheet Id
            new_data (dict): New row values
        """

        spreadsheets = itertools.groupby(
            new_cell_data.keys(), lambda range: range.spreadsheet_id
        )
        for spreadsheet_id, ranges in spreadsheets:
            new_data = list(map(
                lambda range: {
                    "range": range.range_value,
                    "majorDimension": "ROWS",
                    "values": new_cell_data[range],
                },
                ranges,
            ))
            body = {"valueInputOption": "USER_ENTERED", "data": new_data}
            req = self.sheet_api.batchUpdate(spreadsheetId=spreadsheet_id, body=body)
            GoogleSpreadsheetApiAdapter.execute(req)
            logger.debug(
                'Updated cell data of spreadsheet "%s": %r', spreadsheet_id, body
            )


SuccessResult = collections.namedtuple(
    "SuccessResult", ["name", "action", "result_time"]
)
FailureResult = collections.namedtuple(
    "FailureResult", ["name", "action", "details", "result_time"]
)
Message = collections.namedtuple("Message", ["is_failure", "text"])


class ResultReporter:
    """Manages the results of spreadsheet and dispatch update operations."""

    def __init__(self):
        self.results = {}

    def report_success(self, name, action, result_time=None):
        """Report a successful operation.

        Args:
            name (str): Dispatch name
            action (str): Action
            result_time (datetime.datetime) Time the operation happened. Use current time if this is None.
        """

        if result_time is None:
            result_time = datetime.now(tz=timezone.utc)
        self.results[name] = SuccessResult(name, action, result_time)

    def report_failure(self, name, action, details, result_time=None):
        """Report a failed operation.

        Args:
            name (str): Dispatch name
            action (str): Action
            details (str): Error details
            result_time (datetime.datetime) Time the operation happened. Use current time if this is None.
        """

        if isinstance(details, Exception):
            details = str(details)
        if result_time is None:
            result_time = datetime.now(tz=timezone.utc)
        self.results[name] = FailureResult(name, action, details, result_time)

    @staticmethod
    def format_success_message(action, result_time):
        """Format success messages.

        Args:
            action (str): Action
            result_time (datetime.datetime): Time the operation happened

        Returns:
            str: Formatted message
        """

        current_time = result_time.strftime(RESULT_TIME_FORMAT)
        return SUCCESS_MESSAGE_FORMATS[action].format(time=current_time)

    @staticmethod
    def format_failure_message(action, details, result_time=None):
        """Format failure messages.

        Args:
            action (str): Action
            details (str): Error details
            result_time (datetime.datetime): Time the operation happened

        Returns:
            str: Formatted message
        """

        current_time = result_time.strftime(RESULT_TIME_FORMAT)
        message = FAILURE_MESSAGE_FORMATS[action].format(time=current_time)
        message += FAILURE_DETAILS_FORMAT.format(details=details)
        return message

    def get_message(self, name):
        """Get user message for an operation result of a dispatch.

        Args:
            name (str): Dispatch name

        Returns:
            str: Message
        """

        result = self.results[name]
        if isinstance(result, SuccessResult):
            message_text = ResultReporter.format_success_message(
                result.action, result.result_time
            )
            return Message(is_failure=False, text=message_text)
        message_text = ResultReporter.format_failure_message(
            result.action, result.details, result.result_time
        )
        return Message(is_failure=True, text=message_text)


class CategorySetups:
    """Convert category setup sheet data to dict.

    Args:
        categories (dict): Category names and setup id
        subcategories (dict): Subcategory names and setup id
    """

    def __init__(self, categories, subcategories):
        self.categories = categories
        self.subcategories = subcategories

    @classmethod
    def load_from_rows(cls, rows):
        """Create an instance from sheet's row data

        Args:
            rows (list): Row data

        Returns:
            CategorySetups instance
        """

        categories = {}
        subcategories = {}
        # In case of similar IDs, the latest one is used
        for row in rows:
            setup_id = row[0]
            categories[setup_id] = row[1]
            subcategories[setup_id] = row[2]

        return cls(categories, subcategories)

    def get_category_subcategory_name(self, setup_id):
        """Get category and subcategory name from setup id.

        Args:
            setup_id (str): Setup id

        Raises:
            KeyError: Setup id does not exist

        Returns:
            (str, str): Category and subcategory name
        """

        if setup_id not in self.categories:
            raise KeyError
        return self.categories[setup_id], self.subcategories[setup_id]


class OwnerNations:
    """Information about owner nations.

    Args:
        owner_nation_names (dict): Owner nation names
        permitted_spreadsheets (dict): Permitted spreadsheets of an owner
    """

    def __init__(self, owner_nation_names, permitted_spreadsheets):
        self.owner_nation_names = owner_nation_names
        self.permitted_spreadsheets = permitted_spreadsheets

    @classmethod
    def load_from_rows(cls, rows):
        """Load owner nations from sheet.

        Args:
            rows (list): Sheet rows

        Returns:
            OwnerNations: An instance
        """

        owner_nation_names = {}
        permitted_spreadsheets = {}
        # In case of similar IDs, the latest one is used
        for row in rows:
            owner_id = row[0]
            owner_nation_names[owner_id] = row[1]
            permitted_spreadsheets[owner_id] = row[2].split(",")

        return cls(owner_nation_names, permitted_spreadsheets)

    def get_owner_nation_name(self, owner_id, spreadsheet_id):
        """Get owner nation name from owner id.

        Args:
            owner_id (str): Owner nation id
            spreadsheet_id (str): Spreadsheet id

        Raises:
            KeyError: Owner nation does not exist
            ValueError: Owner nation is not allowed for this spreadsheet

        Returns:
            str: Owner nation name
        """

        if owner_id not in self.owner_nation_names:
            raise KeyError

        if spreadsheet_id not in self.permitted_spreadsheets[owner_id]:
            raise ValueError

        return self.owner_nation_names[owner_id]


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


def extract_dispatch_id_from_hyperlink(cell_value):
    """Get dispatch id from HYPERLINK function in the cell value of the name column.

    Args:
        cell_value (str): Cell value of name column

    Returns:
        tuple: Dispatch id
        None: No dispatch id
    """

    result = re.search(HYPERLINK_REGEX, cell_value, flags=re.IGNORECASE)
    if result is None:
        return None

    return result.group(1)


def extract_name_from_hyperlink(cell_value):
    """Get dispatch name from HYPERLINK function in the cell value of the name column.

    Args:
        cell_value (str): Cell value of name column

    Returns:
        str: Dispatch name
    """

    result = re.search(HYPERLINK_REGEX, cell_value, flags=re.IGNORECASE)
    if result is None:
        return cell_value

    return result.group(2)


def get_hyperlink(name, dispatch_id):
    """Get a hyperlink sheet function based on dispatch name and id.

    Args:
        name (str): Dispatch name
        dispatch_id (str): Dispatch id

    Returns:
        str: Hyperlink function
    """
    return HYPERLINK_BUILD_FORMAT.format(name=name, dispatch_id=dispatch_id)


class DispatchSheetRange:
    """A sheet range that contains dispatches.

    Args:
        row_values (list): Row values
        result_reporter (ResultReporter): Result reporter instance
    """

    def __init__(self, row_values, result_reporter):
        self.row_values = row_values
        self.result_reporter = result_reporter

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
        for row in self.row_values:
            if len(row) < 6:
                continue

            if not row[0]:
                continue
            name = extract_name_from_hyperlink(row[0])

            action = row[1]
            if not action:
                continue
            if action not in ("create", "edit", "remove"):
                self.result_reporter.report_failure(name, action, "Invalid action")
                continue

            try:
                owner_nation = owner_nations.get_owner_nation_name(
                    row[2], spreadsheet_id
                )
            except KeyError:
                self.result_reporter.report_failure(
                    name, action, "This owner nation does not exist."
                )
                continue
            except ValueError:
                self.result_reporter.report_failure(
                    name, action, "This spreadsheet does not allow this owner nation."
                )
                continue

            try:
                category, subcategory = category_setups.get_category_subcategory_name(
                    row[3]
                )
            except KeyError:
                self.result_reporter.report_failure(
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

        new_row_values = copy.deepcopy(self.row_values)
        for row in new_row_values:
            # SKip rows with empty title or template cell
            if len(row) < 6:
                continue

            # Skip row with empty action
            if not row[0] or not row[1]:
                continue

            name = extract_name_from_hyperlink(row[0])

            try:
                user_message = self.result_reporter.get_message(name)
                try:
                    row[6] = user_message.text
                except IndexError:
                    row.append(user_message.text)
                if user_message.is_failure:
                    continue
            except KeyError:
                continue

            if new_dispatch_data[name]["action"] == "remove":
                row[0] = name
                row[1] = ""
            elif new_dispatch_data[name]["action"] == "create":
                row[0] = get_hyperlink(name, new_dispatch_data[name]["ns_id"])
                row[1] = "edit"

        return new_row_values


class DispatchSpreadsheet:
    """A spreadsheet that contains dispatches.

    Args:
        sheet_ranges (list): Ranges of this spreadsheet
        result_reporter (ResultReporter): Result reporter instance
    """

    def __init__(self, sheet_ranges, result_reporter):
        self.values_of_ranges = {}
        for sheet_range, range_values in sheet_ranges.items():
            self.values_of_ranges[sheet_range] = DispatchSheetRange(
                range_values, result_reporter
            )
        self.result_reporter = result_reporter

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
        result_reporter (ResultReporter): Result reporter instance
    """

    def __init__(self, spreadsheets, result_reporter):
        self.spreadsheets = {}
        for spreadsheet_id, sheet_ranges in spreadsheets.items():
            self.spreadsheets[spreadsheet_id] = DispatchSpreadsheet(
                sheet_ranges, result_reporter
            )

        self.result_reporter = result_reporter

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

        owner_nations = OwnerNations.load_from_rows(owner_nation_rows)
        category_setups = CategorySetups.load_from_rows(category_setup_rows)

        self.utility_templates = load_utility_templates_from_spreadsheets(
            utility_template_spreadsheets
        )

        self.result_reporter = ResultReporter()

        self.converter = DispatchSpreadsheets(
            dispatch_spreadsheets, self.result_reporter
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
            self.result_reporter.report_success(name, action, result_time)
        else:
            self.result_reporter.report_failure(name, action, result, result_time)

    def update_spreadsheets(self):
        """Update spreadsheets."""

        new_spreadsheet_values = self.converter.get_new_values(
            self.dispatch_data.dispatch_data
        )
        self.spreadsheet_api.update_rows_in_many_spreadsheets(new_spreadsheet_values)
        logger.info("Updated Google spreadsheets.")


@loader_api.dispatch_loader
def init_dispatch_loader(config):
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

    owner_nation_rows = spreadsheet_api.get_cell_values_of_range(
        config["owner_nation_sheet"]["spreadsheet_id"],
        config["owner_nation_sheet"]["range"],
    )
    category_setup_rows = spreadsheet_api.get_cell_values_of_range(
        config["category_setup_sheet"]["spreadsheet_id"],
        config["category_setup_sheet"]["range"],
    )
    utility_template_spreadsheets = spreadsheet_api.get_rows_in_many_spreadsheets(
        config["utility_template_spreadsheets"]
    )
    dispatch_spreadsheets = spreadsheet_api.get_rows_in_many_spreadsheets(
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
def get_dispatch_config(loader):
    return loader.get_dispatch_config()


@loader_api.dispatch_loader
def get_dispatch_template(loader, name):
    return loader.get_dispatch_template(name)


@loader_api.dispatch_loader
def after_update(loader, name, action, result, result_time):
    loader.report_result(name, action, result, result_time)


@loader_api.dispatch_loader
def add_dispatch_id(loader, name, dispatch_id):
    loader.add_dispatch_id(name, dispatch_id)


@loader_api.dispatch_loader
def cleanup_dispatch_loader(loader):
    loader.update_spreadsheets()
