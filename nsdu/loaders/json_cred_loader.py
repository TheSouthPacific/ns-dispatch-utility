"""Load nation login credentials from JSON file.
"""

import json
import logging
from pathlib import Path

from nsdu import info, loader_api
from nsdu.config import Config

CRED_FILENAME = "creds.json"


logger = logging.getLogger(__name__)


class JSONCredLoader:
    """Store nation login credentials in a JSON file."""

    def __init__(self, cred_file_path: Path) -> None:
        """Store nation login credentials in a JSON file.

        Args:
            cred_file_path (Path): Path to credential store file
        """

        self.creds: dict[str, str] = {}
        self.cred_file_path = cred_file_path
        self.changed = False

    def load_creds(self) -> None:
        """Load credentials from JSON file."""

        try:
            with open(self.cred_file_path) as f:
                self.creds = json.load(f)
        except FileNotFoundError:
            pass

    def get_cred(self, name: str) -> str:
        """Get credential (a.k.a autologin code) of a nation.

        Args:
            name (str): Nation name

        Raises:
            loader_api.LoaderError: Credential not found

        Returns:
            str: Autologin code
        """

        try:
            return self.creds[name]
        except KeyError as err:
            raise loader_api.CredNotFound from err

    def add_cred(self, name: str, autologin_code: str) -> None:
        """Add a credential.

        Args:
            name (str): Nation name
            autologin_code (str): Autologin code
        """

        self.creds[name] = autologin_code
        self.changed = True

    def remove_cred(self, name: str) -> None:
        """Remove a credential.

        Args:
            name (str): Nation name
        """

        if name not in self.creds:
            raise loader_api.CredNotFound
        del self.creds[name]
        self.changed = True

    def save(self) -> None:
        """Save creds to JSON file."""

        if self.changed:
            with open(self.cred_file_path, "w") as f:
                json.dump(self.creds, f)


@loader_api.cred_loader
def init_cred_loader(loaders_config: Config) -> JSONCredLoader:
    loader_config = loaders_config.get("json_cred_loader")
    if loader_config is None or "cred_path" not in loader_config:
        json_path = info.DATA_DIR / CRED_FILENAME
    else:
        json_path = Path(loader_config["cred_path"])

    loader = JSONCredLoader(json_path)
    loader.load_creds()

    return loader


@loader_api.cred_loader
def get_cred(loader: JSONCredLoader, name: str) -> str:
    return loader.get_cred(name)


@loader_api.cred_loader
def add_cred(loader: JSONCredLoader, name: str, x_autologin: str) -> None:
    loader.add_cred(name, x_autologin)


@loader_api.cred_loader
def remove_cred(loader: JSONCredLoader, name: str) -> None:
    loader.remove_cred(name)


@loader_api.cred_loader
def cleanup_cred_loader(loader: JSONCredLoader) -> None:
    loader.save()
