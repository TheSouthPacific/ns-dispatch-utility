"""Nation login credential management."""

from __future__ import annotations

from argparse import Namespace
from typing import Mapping, Sequence

from nsdu import feature, loader_api, loader_managers, ns_api
from nsdu.config import Config
from nsdu.exceptions import UserError
from nsdu.loader_managers import CredLoaderManager, LoaderManagerBuilder


class CredFeature(feature.Feature):
    """Handles the nation login credential feature."""

    def __init__(
        self,
        cred_loader_manager: CredLoaderManager,
        auth_api: ns_api.AuthApi,
    ) -> None:
        """Handles the nation login credential feature.

        Args:
            cred_loader_manager (CredLoaderManager): Cred loader manager
            auth_api (api_adapter.AuthApi): Login API wrapper
        """

        self.auth_api = auth_api
        self.cred_loader_manager = cred_loader_manager

    @classmethod
    def from_nsdu_config(
        cls, nsdu_config: Config, loader_manager_builder: LoaderManagerBuilder
    ) -> CredFeature:
        """Setup this feature with NSDU's config

        Args:
            nsdu_config (Config): NSDU's config
            loader_manager_builder (LoaderManagerBuilder): Loader manager builder

        Returns:
            CredFeature
        """

        cred_loader_manager = loader_managers.CredLoaderManager(
            nsdu_config["loaders_config"]
        )
        cred_loader_name = nsdu_config["plugins"]["cred_loader"]
        loader_manager_builder.build(cred_loader_manager, cred_loader_name)
        cred_loader_manager.init_loader()

        auth_api = ns_api.AuthApi(nsdu_config["general"]["user_agent"])

        return cls(cred_loader_manager, auth_api)

    def add_password_cred(self, nation_name: str, password: str) -> None:
        """Add a password credential.

        Args:
            nation_name (str): Nation name
            password (str): Password

        Raises:
            UserError: Failed to login
        """

        try:
            autologin_code = self.auth_api.get_autologin_code(nation_name, password)
            self.cred_loader_manager.add_cred(nation_name, autologin_code)
        except ns_api.AuthApiError as err:
            raise UserError(err) from err

    def add_password_creds(self, creds: Mapping[str, str]) -> None:
        """Add password credentials.

        Args:
            creds (Mapping[str, str]): Passwords keyed by nation name
        """

        for nation_name, password in creds.items():
            self.add_password_cred(nation_name, password)

    def add_autologin_cred(self, nation_name: str, autologin_code: str) -> None:
        """Add an autologin code credential.

        Args:
            nation_name (str): Nation name
            autologin (str): Autologin code
        """

        is_correct = self.auth_api.verify_autologin_code(nation_name, autologin_code)
        if is_correct:
            self.cred_loader_manager.add_cred(nation_name, autologin_code)
        else:
            raise UserError(
                f'Could not log in to the nation "{nation_name}" with that '
                f"autologin code (use --add-password if you are adding passwords)."
            )

    def add_autologin_creds(self, creds: Mapping[str, str]) -> None:
        """Add autologin code credentials.

        Args:
            creds (Mapping[str, str]): Autologin code keyed by nation name
        """

        for nation_name, password in creds.items():
            self.add_password_cred(nation_name, password)

    def remove_cred(self, nation_name: str) -> None:
        """Remove a login credential.

        Args:
            nation_name (str): Nation name
        """

        try:
            self.cred_loader_manager.remove_cred(nation_name)
        except loader_api.CredNotFound:
            raise UserError(f'Login credential for nation "{nation_name}" not found.')

    def remove_creds(self, nation_names: Sequence[str]) -> None:
        for name in nation_names:
            self.remove_cred(name)

    def cleanup(self) -> None:
        """Cleanup loader (include saving credential changes)."""

        self.cred_loader_manager.cleanup_loader()


class CredCliParser(feature.FeatureCliParser):
    """Parse CLI arguments for CredFeature."""

    def __init__(self, feature: CredFeature) -> None:
        self.feature = feature

    def parse_add_password_creds(self, cli_args: Namespace) -> None:
        """Parse password credential add CLI arguments.

        Args:
            cli_args (Namespace): CLI argument values
        """

        if len(cli_args.add_password) % 2 != 0:
            raise UserError("There is no password for the last nation.")

        creds: dict[str, str] = {}
        for i in range(0, len(cli_args.add_password), 2):
            inputs = cli_args.add_password
            creds[inputs[i]] = inputs[i + 1]
        self.feature.add_password_creds(creds)

        print("Successfully added all login credentials")

    def parse_add_autologin_creds(self, cli_args: Namespace) -> None:
        """Parse autologin credential add CLI arguments.

        Args:
            cli_args (Namespace): CLI argument values
        """

        if len(cli_args.add) % 2 != 0:
            raise UserError("There is no autologin code for the last nation.")

        creds: dict[str, str] = {}
        for i in range(0, len(cli_args.add), 2):
            inputs = cli_args.add
            creds[inputs[i]] = inputs[i + 1]
        self.feature.add_autologin_creds(creds)

        print("Successfully added all login credentials")

    def parse_remove_creds(self, cli_args: Namespace) -> None:
        """Parse credential remove CLI arguments.

        Args:
            cli_args (Namespace): CLI argument values
        """

        self.feature.remove_creds(cli_args.remove)
        nation_names_str = ", ".join(cli_args.remove)
        print(f'Removed login credentials of "{nation_names_str}"')

    def parse(self, cli_args: Namespace) -> None:
        """Parse CLI arguments.

        Args:
            cli_args (Namespace): CLI arguments
        """

        if cli_args.add is not None:
            self.parse_add_autologin_creds(cli_args)
        elif cli_args.add_password is not None:
            self.parse_add_password_creds(cli_args)
        elif cli_args.remove is not None:
            self.parse_remove_creds(cli_args)
