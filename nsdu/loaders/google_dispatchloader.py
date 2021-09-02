"""Load dispatches from Google spreadsheets.
"""

import collections
import copy
from datetime import datetime
from datetime import timezone
import re

from google.oauth2 import service_account
from googleapiclient import discovery
from googleapiclient.http import HttpError

from nsdu import exceptions
from nsdu import loader_api


SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
HYPERLINK_REGEX = r'=hyperlink\("https://www.nationstates.net/page=dispatch/id=(\d+)", "(\w+)"\)'
HYPERLINK = '=hyperlink("https://www.nationstates.net/page=dispatch/id={dispatch_id}", "{name}")'

SUCCESS_MESSAGES = {'create': 'Created on {time}',
                    'edit': 'Edited on {time}',
                    'remove': 'Removed on {time}'}
FAILURE_MESSAGES = {'create': 'Failed to create on {time}',
                    'edit': 'Failed to edit on {time}',
                    'remove': 'Failed to remove on {time}'}
FAILURE_DETAILS = '\nError: {details}'
RESULT_TIME_FORMAT = '%d/%m/%Y %H:%M:%S %Z'


class GoogleSpreadsheetApiAdapter():
    """Adapter for Google Spreadsheet API.

    Args:
        sheet_api: Google Spreadsheet API
    """

    def __init__(self, sheet_api):
        self.sheet_api = sheet_api

    def execute(self, request):
        """Execute request.

        Args:
            request: API request

        Raises:
            exceptions.LoaderError: API error

        Returns:
            dict: Response
        """

        try:
            return request.execute()
        except HttpError as e:
            raise exceptions.LoaderError('Google API Error {}: {}'.format(e.status_code, e.error_details))

    def get_rows_in_range(self, spreadsheet_id, sheet_range):
        """Get cell values of a range in a spreadsheet.

        Args:
            spreadsheet_id (str): Spreadsheet Id
            sheet_range (str): Range name
        Returns:
            List: Row values
        """

        req = self.sheet_api.get(spreadsheetId=spreadsheet_id,
                                 range=sheet_range,
                                 valueRenderOption='FORMULA')
        resp = self.execute(req)

        if 'values' not in resp:
            return []
        return resp['values']

    def get_rows_in_many_ranges(self, spreadsheet_id, sheet_ranges):
        """Get cell values of many ranges in a spreadsheet.

        Args:
            spreadsheet_id (str): Spreadsheet Id
            sheet_ranges (list): Range names

        Returns:
            dict: Row values keyed by range name
        """

        req = self.sheet_api.batchGet(spreadsheetId=spreadsheet_id,
                                      ranges=sheet_ranges,
                                      valueRenderOption='FORMULA')
        resp = self.execute(req)

        result = {}
        for value_range in resp['valueRanges']:
            sheet_range = value_range['range']
            if 'values' not in value_range:
                result[sheet_range] = []
            else:
                result[sheet_range] = value_range['values']

        return result

    def update_rows_in_many_ranges(self, spreadsheet_id, new_data):
        """Update cell values of many ranges in a spreadsheet.

        Args:
            spreadsheet_id (str): Spreadsheet Id
            new_data (dict): New row values
        """

        data = []
        for range_name, range_data in new_data.items():
            data.append({'range': range_name,
                         'majorDimension': 'ROWS',
                         'values': range_data})

        body = {'valueInputOption': 'USER_ENTERED',
                'data': data}
        req = self.sheet_api.batchUpdate(spreadsheetId=spreadsheet_id, body=body)
        self.execute(req)


SuccessResult = collections.namedtuple('SuccessResult', ['name', 'action'])
FailureResult = collections.namedtuple('SuccessResult', ['name', 'action', 'details'])
class ResultReporter():
    """Result report manager.
    """

    def __init__(self):
        self.results = {}

    def report_success(self, name, action):
        """Report a successful operation.

        Args:
            name (str): Dispatch name
            action (str): Action
        """

        self.results[name] = SuccessResult(name, action)

    def report_failure(self, name, action, details):
        """Report a failed operation.

        Args:
            name (str): Dispatch name
            action (str): Action
            details (str): Error details
        """

        if isinstance(details, Exception):
            details = str(details)
        self.results[name] = FailureResult(name, action, details)

    @staticmethod
    def format_success_message(action):
        """Format success messages.

        Args:
            action (str): Action

        Returns:
            str: Formatted message
        """

        current_time = datetime.now(tz=timezone.utc).strftime(RESULT_TIME_FORMAT)
        return SUCCESS_MESSAGES[action].format(time=current_time)

    @staticmethod
    def format_failure_message(action, details):
        """Format failure messages.

        Args:
            action (str): Action
            details (str): Error details

        Returns:
            str: Formatted message
        """

        current_time = datetime.now(tz=timezone.utc).strftime(RESULT_TIME_FORMAT)
        message = FAILURE_MESSAGES[action].format(time=current_time)
        message += FAILURE_DETAILS.format(details=details)
        return message

    def get_message(self, name):
        """Get user message for an operation result of a dispatch.

        Args:
            name (str): Dispatch name

        Returns:
            str: Message
        """

        if isinstance(self.results[name], SuccessResult):
            return ResultReporter.format_success_message(self.results[name].action)
        elif isinstance(self.results[name], FailureResult):
            return ResultReporter.format_failure_message(self.results[name].action,
                                                         self.results[name].details)


class CategorySetups():
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


class OwnerNations():
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
            permitted_spreadsheets[owner_id] = row[2].split(',')

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

    r = re.search(HYPERLINK_REGEX, cell_value, flags=re.IGNORECASE)
    if r is None:
        return None

    return r.group(1)


def extract_name_from_hyperlink(cell_value):
    """Get dispatch name from HYPERLINK function in the cell value of the name column.

    Args:
        cell_value (str): Cell value of name column

    Returns:
        str: Dispatch name
    """

    r = re.search(HYPERLINK_REGEX, cell_value, flags=re.IGNORECASE)
    if r is None:
        return cell_value

    return r.group(2)


class DispatchDataSpreadsheetConverter():
    """Converting spreadsheets into dispatch data and backward.

    Args:
        spreadsheets (str): Spreadsheet data
        result_reporter (ResultReporter): Result reporter instance
    """

    def __init__(self, spreadsheets, result_reporter):
        self.spreadsheets = spreadsheets
        self.result_reporter = result_reporter

    def extract_dispatch_data(self, owner_nations, category_setups):
        """Extract dispatch data from spreadsheets.

        Args:
            owner_nations (OwnerNations): Owner nations
            category_setups (CategorySetups): Category setups

        Returns:
            dict: Dispatch data keyed by dispatch name
        """

        dispatch_data = {}
        for spreadsheet_id, spreadsheet_values in self.spreadsheets.items():
            for range_data in spreadsheet_values.values():
                for row in range_data:
                    name = extract_name_from_hyperlink(row[0])

                    # Skip row with empty action cell
                    action = row[1]
                    if not action:
                        continue
                    if action not in ('create', 'edit', 'remove'):
                        self.result_reporter.report_failure(name, action, 'Invalid action')
                        continue

                    try:
                        owner_nation = owner_nations.get_owner_nation_name(row[2], spreadsheet_id)
                    except KeyError:
                        self.result_reporter.report_failure(name, action, 'This owner nation does not exist.')
                        continue
                    except ValueError:
                        self.result_reporter.report_failure(name, action, 'This spreadsheet does not allow this owner nation.')
                        continue

                    try:
                        category, subcategory = category_setups.get_category_subcategory_name(row[3])
                    except KeyError:
                        self.result_reporter.report_failure(name, action, 'This category setup does not exist.')
                        continue

                    data = {'action': action,
                            'owner_nation': owner_nation,
                            'category': category,
                            'subcategory': subcategory,
                            'title': row[4],
                            'template': row[5]}

                    dispatch_id = extract_dispatch_id_from_hyperlink(row[0])
                    if dispatch_id:
                        data['ns_id'] = dispatch_id

                    dispatch_data[name] = data
                    row[0] = name

        return dispatch_data

    def generate_new_spreadsheets(self, new_dispatch_data):
        """Generate new spreadsheets with new data.

        Args:
            new_dispatch_data (dict): New dispatch data, keyed by dispatch name

        Returns:
            dict: New spreadsheets keyed by spreadsheet id
        """

        new_spreadsheet_data = copy.deepcopy(self.spreadsheets)
        for spreadsheet_values in new_spreadsheet_data.values():
            for range_data in spreadsheet_values.values():
                for row in range_data:
                    name = row[0]
                    if name not in new_dispatch_data:
                        continue

                    if new_dispatch_data[name]['action'] == 'create':
                        row[1] = 'edit'
                    if new_dispatch_data[name]['action'] == 'remove':
                        row[1] = ''

                    row[0] = HYPERLINK.format(name=name, dispatch_id=new_dispatch_data[name]['ns_id'])
                    row[6] = self.result_reporter.get_message(name)

        return new_spreadsheet_data


class DispatchData():
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
            canonical_config = {'action': config['action'],
                                'title': config['title'],
                                'category': config['category'],
                                'subcategory': config['subcategory']}
            if 'ns_id' in config:
                canonical_config['ns_id'] = config['ns_id']
            owner_nation = config['owner_nation']
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

        return self.dispatch_data[name]['template']

    def add_dispatch_id(self, name, dispatch_id):
        """Add id of new dispatch.

        Args:
            name (str): Dispatch name
            dispatch_id (str): Dispatch id
        """

        self.dispatch_data[name]['ns_id'] = dispatch_id


class GoogleDispatchLoader():
    """Google spreadsheet dispatch loader.

    Args:
        spreadsheet_api (googleapiclients): Google Spreadsheet Api
        dispatch_spreadsheet_config (dict): Dispatch spreadsheet config
        owner_nation_config (dict): Owner nation spreadsheet config
        category_setups_config (dict): Category setup spreadsheet config
    """

    def __init__(self, spreadsheet_api, dispatch_spreadsheet_config,
                 owner_nation_config, category_setups_config):
        self.spreadsheet_api = spreadsheet_api

        owner_nation_rows = self.spreadsheet_api.get_rows_in_range(owner_nation_config['spreadsheet_id'],
                                                                   owner_nation_config['range'])
        owner_nations = OwnerNations.load_from_rows(owner_nation_rows)

        category_setup_rows = self.spreadsheet_api.get_rows_in_range(category_setups_config['spreadsheet_id'],
                                                                     category_setups_config['range'])
        category_setups = CategorySetups.load_from_rows(category_setup_rows)

        dispatch_spreadsheets = {}
        for spreadsheet in dispatch_spreadsheet_config:
            dispatch_spreadsheet = self.spreadsheet_api.get_rows_in_many_ranges(dispatch_spreadsheet_config['spreadsheet_id'],
                                                                                dispatch_spreadsheet_config['ranges'])
            spreadsheet_id = spreadsheet['spreadsheet_id']
            dispatch_spreadsheets[spreadsheet_id] = dispatch_spreadsheet

        self.result_reporter = ResultReporter()

        self.converter = DispatchDataSpreadsheetConverter(dispatch_spreadsheets, self.result_reporter)
        extracted_data = self.converter.extract_dispatch_data(owner_nations, category_setups)

        self.dispatch_data = DispatchData(extracted_data)

    def get_dispatch_config(self):
        """Get dispatch config.

        Returns:
            dict: Dispatch config
        """

        return self.dispatch_data.get_canonical_dispatch_config()

    def add_dispatch_id(self, name, dispatch_id):
        """Add id of new dispatch.

        Args:
            name (str): Dispatch name
            dispatch_id (str): Dispatch id
        """

        self.dispatch_data.add_dispatch_id(name, dispatch_id)

    def get_dispatch_template(self, name):
        """Get dispatch template text.

        Args:
            name (str): Dispatch name

        Returns:
            str: Template text
        """

        self.dispatch_data.get_dispatch_template(name)

    def report_result(self, name, action, result):
        """Report operation result from NSDU.

        Args:
            name (str): Dispatch name
            action (str): Action
            result (str): Result
        """

        if result == 'success':
            self.result_reporter.report_success(name, action)
        else:
            self.result_reporter.report_failure(name, action, result)

    def update_spreadsheets(self):
        """Update spreadsheets.
        """

        new_spreadsheet_data = self.converter.generate_new_spreadsheets(self.dispatch_data.dispatch_data)
        for spreadsheet_id, spreadsheet_data in new_spreadsheet_data.items():
            self.spreadsheet_api.batch_update_data(spreadsheet_id, spreadsheet_data)


@loader_api.dispatch_loader
def init_dispatch_loader(loader_config):
    config = loader_config['google_dispatchloader']

    google_api_creds = service_account.Credentials.from_service_account_file(config['cred_path'], scopes=SCOPES)
    # pylint: disable=maybe-no-member
    google_api = discovery.build('sheets', 'v4', credentials=google_api_creds).spreadsheets().values()
    spreadsheet_api = GoogleSpreadsheetApiAdapter(google_api)

    return GoogleDispatchLoader(spreadsheet_api, config['dispatch_spreadsheets'],
                                config['owner_nation_spreadsheet'],
                                config['category_setup_spreadsheet'])


@loader_api.dispatch_loader
def get_dispatch_config(loader):
    return loader.get_dispatch_config()


@loader_api.dispatch_loader
def get_dispatch_template(loader, name):
    return loader.get_dispatch_template(name)


@loader_api.dispatch_loader
def after_update(loader, name, action, result):
    loader.report_result(name, action, result)


@loader_api.dispatch_loader
def add_dispatch_id(loader, name, dispatch_id):
    loader.add_new_dispatch_id(name, dispatch_id)


@loader_api.dispatch_loader
def cleanup_dispatch_loader(loader):
    loader.save_dispatch_config()