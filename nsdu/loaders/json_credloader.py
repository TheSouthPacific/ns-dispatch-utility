"""Load nation login credentials from JSON file.
"""

import json
import logging
from typing import Any

from nsdu import exceptions
from nsdu import info
from nsdu import loader_api


CRED_FILENAME = "creds.json"


logger = logging.getLogger(__name__)


class JSONCredLoader:
    """JSON Credential Loader.

    Args:
        config (dict): Configuration
        json_path (str): Path to JSON file
    """

    def __init__(self, json_path: str):
        super().__init__()
        self.creds = {}
        self.json_path = json_path
        self.saved = True

    def load_creds(self) -> None:
        """Get all login credentials

        Returns:
            dict: Nation name and autologin code
        """

        try:
            with open(self.json_path) as f:
                self.creds = json.load(f)
        except FileNotFoundError:
            pass

    def add_cred(self, name: str, x_autologin: str) -> None:
        """Add a new credential into file.

        Args:
            name (str): Nation name
            x_autologin (str): X-Autologin code
        """

        self.creds[name] = x_autologin
        self.saved = False

    def remove_cred(self, name: str) -> None:
        """Remove a credential from file.

        Args:
            name (str): Nation name
        """

        if name not in self.creds:
            raise exceptions.CredNotFound(
                'Credential of nation "{}" not found.'.format(name)
            )
        del self.creds[name]
        self.saved = False

    def save(self) -> None:
        """Save creds to JSON file."""

        if not self.saved:
            with open(self.json_path, "w") as f:
                json.dump(self.creds, f)


@loader_api.cred_loader
def init_cred_loader(config: dict[str, Any]) -> JSONCredLoader:
    config = config.get("json_credloader")
    if config is None or not "cred_path" in config:
        json_path = info.DATA_DIR / CRED_FILENAME
    else:
        json_path = config["cred_path"]

    loader = JSONCredLoader(json_path)
    loader.load_creds()

    return loader


@loader_api.cred_loader
def get_creds(loader: JSONCredLoader) -> dict[str, str]:
    return loader.creds


@loader_api.cred_loader
def add_cred(loader: JSONCredLoader, name: str, x_autologin: str) -> None:
    loader.add_cred(name, x_autologin)


@loader_api.cred_loader
def remove_cred(loader: JSONCredLoader, name: str) -> None:
    loader.remove_cred(name)


@loader_api.cred_loader
def cleanup_cred_loader(loader: JSONCredLoader) -> None:
    loader.save()
