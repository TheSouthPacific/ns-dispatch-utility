"""Load nation login credentials from JSON file.
"""

import collections
import json
import logging

from nsdu import exceptions
from nsdu import info
from nsdu import loader_api


CRED_FILENAME = 'creds.json'


logger = logging.getLogger(__name__)


class JSONCredLoader(collections.UserDict):
    """JSON Credential Loader.

    Args:
        config (dict): Configuration
        json_path (str): Path to JSON file
    """

    def __init__(self, json_path):
        super().__init__()
        self.json_path = json_path
        self.saved = True

    def load_creds(self):
        """Get all login credentials

        Returns:
            dict: Nation name and autologin code
        """

        try:
            with open(self.json_path) as f:
                self.data = json.load(f)
        except FileNotFoundError:
            pass

    def __setitem__(self, name, x_autologin):
        """Add a new credential into file.

        Args:
            name (str): Nation name
            x_autologin (str): X-Autologin code
        """

        self.data[name] = x_autologin
        self.saved = False

    def __delitem__(self, name):
        """Remove a credential from file.

        Args:
            name (str): Nation name
        """

        if name not in self.data:
            raise exceptions.CredNotFound('Credential of nation "{}" not found.'.format(name))
        del self.data[name]
        self.saved = False

    def save(self):
        """Save creds to JSON file.
        """

        if not self.saved:
            with open(self.json_path, 'w') as f:
                json.dump(self.data, f)


@loader_api.cred_loader
def init_cred_loader(config):
    config = config.get('json_credloader')
    if config is None or not 'cred_path' in config:
        json_path = info.DATA_DIR / CRED_FILENAME
    else:
        json_path = config['cred_path']

    loader = JSONCredLoader(json_path)
    loader.load_creds()

    return loader


@loader_api.cred_loader
def get_creds(loader):
    return loader.data


@loader_api.cred_loader
def add_cred(loader, name, x_autologin):
    loader[name] = x_autologin


@loader_api.cred_loader
def remove_cred(loader, name):
    del loader[name]


@loader_api.cred_loader
def cleanup_cred_loader(loader):
    loader.save()
