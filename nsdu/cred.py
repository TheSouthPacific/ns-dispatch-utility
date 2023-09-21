"""Nation login credential management."""

from __future__ import annotations

from argparse import Namespace

from nsdu import loader_api, loader_managers, ns_api
from nsdu.config import Config
from nsdu.exceptions import UserError
from nsdu.loader_managers import CredLoaderManager, LoaderManagerBuilder
from nsdu.types import Feature


class CredFeature(Feature):
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
        loader_name = nsdu_config["loaders"]["cred_loader"]
        loader_manager_builder.build(cred_loader_manager, loader_name)
        cred_loader_manager.init_loader()

        auth_api = ns_api.AuthApi(nsdu_config["general"]["user_agent"])

        return cls(cred_loader_manager, auth_api)

    def add_password_cred(self, nation_name: str, password: str) -> None:
        """Add a new credential that uses password.

        Args:
            nation_name (str): Nation name
            password (str): Password
        """

        try:
            autologin_code = self.auth_api.get_autologin_code(nation_name, password)
            self.cred_loader_manager.add_cred(nation_name, autologin_code)
        except ns_api.AuthApiError as err:
            raise UserError(
                f'Could not log in to the nation "{nation_name}" with that password.'
            ) from err

    def add_autologin_cred(self, nation_name: str, autologin_code: str) -> None:
        """Add a new credential that uses autologin code.

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

    def remove_cred(self, nation_name: str) -> None:
        """Remove a login credential.

        Args:
            nation_name (str): Nation name
        """

        self.cred_loader_manager.remove_cred(nation_name)

    def cleanup(self) -> None:
        """Cleanup loader (include saving credential changes)."""

        self.cred_loader_manager.cleanup_loader()


def run_add_password_creds(feature: CredFeature, cli_args: Namespace) -> None:
    """Run password credential add operation.

    Args:
        feature (CredFeature): Credential feature
        cli_args (Namespace): CLI argument values
    """

    if len(cli_args.add_password) % 2 != 0:
        print("There is no password for the last name.")
        return

    try:
        for i in range(0, len(cli_args.add_password), 2):
            feature.add_password_cred(
                cli_args.add_password[i], cli_args.add_password[i + 1]
            )
    except UserError as err:
        print(err)
        return

    print("Successfully added all login credentials")


def run_add_autologin_creds(feature: CredFeature, cli_args: Namespace) -> None:
    """Run autologin credential add operation.

    Args:
        feature (CredFeature): Credential feature
        cli_args (Namespace): CLI argument values
    """

    if len(cli_args.add) % 2 != 0:
        print("There is no password for the last name.")
        return

    try:
        for i in range(0, len(cli_args.add), 2):
            feature.add_autologin_cred(cli_args.add[i], cli_args.add[i + 1])
    except UserError as err:
        print(err)
        return

    print("Successfully added all login credentials")


def run_remove_cred(feature: CredFeature, cli_args: Namespace) -> None:
    """Run credential remove operation.

    Args:
        feature (CredFeature): Credential feature
        cli_args (Namespace): CLI argument values
    """

    for nation_name in cli_args.remove:
        try:
            feature.remove_cred(nation_name)
            print(f'Removed login credential of "{nation_name}"')
        except loader_api.CredNotFound:
            print(f'Nation "{nation_name}" not found.')
            break
