"""NationStates Dispatch Utility."""

from __future__ import annotations

import abc
import argparse
import importlib.metadata as import_metadata
import logging
import logging.config
import signal
import sys
from argparse import Namespace
from datetime import datetime, timezone
from typing import Sequence

from nsdu import (
    config,
    exceptions,
    info,
    loader_api,
    loader_managers,
    ns_api,
    updater_api,
    utils,
)
from nsdu.config import Config
from nsdu.loader_api import DispatchesMetadata, DispatchOp, DispatchOpResult
from nsdu.loader_managers import (
    CredLoaderManager,
    DispatchLoaderManager,
    LoaderManagerBuilder,
    SimpleBbcLoaderManager,
    TemplateVarLoaderManager,
)

logger = logging.getLogger("NSDU")


class CredOperationError(exceptions.NSDUError):
    """Error about a login credential operation (e.g. add, remove)."""


class Feature(abc.ABC):
    """Base class for a facade class which handles a feature."""

    @abc.abstractmethod
    def cleanup(self) -> None:
        """Perform saves and cleanup before exiting."""


class DispatchFeature(Feature):
    """Handles the dispatch feature."""

    def __init__(
        self,
        dispatch_updater: updater_api.DispatchUpdater,
        dispatch_loader_manager: DispatchLoaderManager,
        cred_loader_manager: CredLoaderManager,
        dispatches_metadata: DispatchesMetadata,
    ) -> None:
        """Handles the dispatch features.

        Args:
            dispatch_updater (updater_api.DispatchUpdater): Dispatch updater
            dispatch_loader_manager (DispatchLoaderManager): Dispatch loader manager
            cred_loader_manager (CredLoaderManager): Credential loader manager
            dispatch_metadata (DispatchesMetadata): Metadata of dispatches
        """

        self.dispatch_updater = dispatch_updater
        self.dispatch_loader_manager = dispatch_loader_manager
        self.dispatches_metadata = dispatches_metadata
        self.cred_loader_manager = cred_loader_manager

    @classmethod
    def from_nsdu_config(
        cls, nsdu_config: Config, loader_manager_builder: LoaderManagerBuilder
    ) -> DispatchFeature:
        """Setup this feature with NSDU's config.

        Args:
            nsdu_config (Config): NSDU's config
            loader_manager_builder (LoaderManagerBuilder): Loader manager builder

        Returns:
            DispatchFeature
        """

        loader_opts = nsdu_config["loaders"]
        loaders_config = nsdu_config["loaders_config"]

        dispatch_loader_manager = DispatchLoaderManager(loaders_config)
        template_var_loader_manager = TemplateVarLoaderManager(loaders_config)
        simple_bbc_loader_manager = SimpleBbcLoaderManager(loaders_config)
        cred_loader_manager = CredLoaderManager(loaders_config)

        loader_manager_builder.build(
            dispatch_loader_manager, loader_opts["dispatch_loader"]
        )
        loader_manager_builder.build(
            template_var_loader_manager, loader_opts["template_var_loader"]
        )
        loader_manager_builder.build(cred_loader_manager, loader_opts["cred_loader"])
        loader_manager_builder.build(
            simple_bbc_loader_manager, loader_opts["simple_bb_loader"]
        )

        cred_loader_manager.init_loader()

        dispatch_loader_manager.init_loader()
        dispatch_metadata = dispatch_loader_manager.get_dispatch_metadata()
        logger.debug("Loaded dispatch config: %r", dispatch_metadata)

        simple_bb_config = simple_bbc_loader_manager.get_simple_bbc_config()

        template_vars = template_var_loader_manager.get_all_template_vars()
        template_vars["dispatch_info"] = dispatch_metadata

        rendering_config = nsdu_config.get("rendering", {})
        dispatch_updater = updater_api.DispatchUpdater(
            user_agent=nsdu_config["general"]["user_agent"],
            template_filter_paths=rendering_config.get("filter_paths", None),
            simple_fmts_config=simple_bb_config,
            complex_fmts_source_path=rendering_config.get(
                "complex_formatter_source_path", None
            ),
            template_load_func=dispatch_loader_manager.get_dispatch_template,
            template_vars=template_vars,
        )

        return cls(
            dispatch_updater,
            dispatch_loader_manager,
            cred_loader_manager,
            dispatch_metadata,
        )

    def execute_dispatch_op(self, name: str) -> None:
        """Execute a dispatch operation.

        Args:
            name (str): Dispatch name
        """

        metadata = self.dispatches_metadata[name]
        dispatch_id = metadata.ns_id
        title = metadata.title
        operation = metadata.operation
        category = metadata.category
        subcategory = metadata.subcategory

        result_time = datetime.now(tz=timezone.utc)

        try:
            if operation == DispatchOp.CREATE:
                new_dispatch_id = self.dispatch_updater.create_dispatch(
                    name, title, category, subcategory
                )
                self.dispatch_loader_manager.add_dispatch_id(name, new_dispatch_id)
            elif operation == DispatchOp.EDIT:
                if dispatch_id is None:
                    raise ValueError
                self.dispatch_updater.edit_dispatch(
                    name, dispatch_id, title, category, subcategory
                )
            elif operation == DispatchOp.DELETE:
                if dispatch_id is None:
                    raise ValueError
                self.dispatch_updater.remove_dispatch(name, dispatch_id)

            self.dispatch_loader_manager.after_update(
                name, operation, DispatchOpResult.SUCCESS, result_time
            )
        except ns_api.DispatchApiError as err:
            err_message = str(err)
            logger.error(err_message)
            self.dispatch_loader_manager.after_update(
                name, operation, DispatchOpResult.FAILURE, result_time, err_message
            )

    def execute_dispatch_ops(self, names: Sequence[str]) -> None:
        """Execute operations of dispatches with provided names.
        Empty list means all dispatches.

        Args:
            names (Sequence[str]): Dispatch names
        """

        names = list(names)
        while names and names[-1] not in self.dispatches_metadata:
            logger.error('Could not find dispatch "%s"', names[-1])
            names.pop()

        dispatch_groups: dict[str, DispatchesMetadata] = {}
        for name, metadata in self.dispatches_metadata.items():
            owner_nation = metadata.owner_nation
            if owner_nation not in dispatch_groups:
                dispatch_groups[owner_nation] = {}
            dispatch_groups[owner_nation][name] = metadata

        for owner_nation, dispatches_metadata in dispatch_groups.items():
            try:
                owner_nation = utils.canonical_nation_name(owner_nation)
                owner_nation_cred = self.cred_loader_manager.get_cred(owner_nation)
                self.dispatch_updater.set_owner_nation(owner_nation, owner_nation_cred)
                logger.info('Begin to update dispatches of nation "%s".', owner_nation)
            except ns_api.NationLoginError:
                logger.error('Could not log in to nation "%s".', owner_nation)
                continue
            except KeyError:
                logger.error('Nation "%s" has no login credential.', owner_nation)
                continue

            for name in dispatches_metadata.keys():
                if not names or name in names:
                    self.execute_dispatch_op(name)

    def cleanup(self) -> None:
        """Save dispatch config changes and close dispatch loader."""

        self.dispatch_loader_manager.cleanup_loader()


def get_metadata_entry_points() -> Sequence[import_metadata.EntryPoint]:
    """Get all metadata entry points.

    Returns:
        Sequence[import_metadata.EntryPoint]: Entry points
    """

    try:
        return import_metadata.entry_points()[info.LOADER_ENTRY_POINT_NAME]
    except KeyError:
        return []


class CredFeature(Feature):
    """Handles the nation login credential feature."""

    def __init__(
        self,
        cred_loader_manager: CredLoaderManager,
        login_api: ns_api.AuthApi,
    ) -> None:
        """Handles the nation login credential feature.

        Args:
            cred_loader_manager (CredLoaderManager): Cred loader manager
            login_api (api_adapter.LoginApi): Login API wrapper
        """

        self.login_api = login_api
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

        login_api = ns_api.AuthApi(nsdu_config["general"]["user_agent"])

        return cls(cred_loader_manager, login_api)

    def add_password_cred(self, nation_name: str, password: str) -> None:
        """Add a new credential that uses password.

        Args:
            nation_name (str): Nation name
            password (str): Password
        """

        try:
            autologin_code = self.login_api.get_autologin_code(nation_name, password)
            self.cred_loader_manager.add_cred(nation_name, autologin_code)
        except ns_api.NationLoginError:
            raise CredOperationError(
                f'Could not log in to the nation "{nation_name}" with that password.'
            )

    def add_autologin_cred(self, nation_name: str, autologin_code: str) -> None:
        """Add a new credential that uses autologin code.

        Args:
            nation_name (str): Nation name
            autologin (str): Autologin code
        """

        is_correct = self.login_api.verify_autologin_code(nation_name, autologin_code)
        if is_correct:
            self.cred_loader_manager.add_cred(nation_name, autologin_code)
        else:
            raise CredOperationError(
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
        """Save cred changes and close."""

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
    except CredOperationError as err:
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
    except CredOperationError as err:
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


def run(nsdu_config: Config, cli_args: Namespace) -> None:
    """Run the app with user configuration and CLI argument values.

    Args:
        nsdu_config (Config): Configuration
        cli_args (Namespace): CLI argument values
    """

    custom_loader_dir_path = nsdu_config["general"].get("custom_loader_dir_path", None)
    entry_points = get_metadata_entry_points()
    loader_manager_builder = loader_managers.LoaderManagerBuilder(
        entry_points, custom_loader_dir_path
    )

    feature: Feature | None = None

    def interrupt_handler(sig, frame):
        logger.info("Exiting NSDU...")
        if feature:
            feature.cleanup()
        logger.info("Exited NSDU.")
        sys.exit()

    signal.signal(signal.SIGINT, interrupt_handler)

    if cli_args.subparser_name == "cred":
        feature = CredFeature.from_nsdu_config(nsdu_config, loader_manager_builder)
        if hasattr(cli_args, "add") and cli_args.add is not None:
            run_add_autologin_creds(feature, cli_args)
        elif hasattr(cli_args, "add_password") and cli_args.add_password is not None:
            run_add_password_creds(feature, cli_args)
        elif hasattr(cli_args, "remove") and cli_args.remove is not None:
            run_remove_cred(feature, cli_args)
    elif cli_args.subparser_name == "update":
        feature = DispatchFeature.from_nsdu_config(nsdu_config, loader_manager_builder)
        feature.execute_dispatch_ops(cli_args.dispatches)

    if feature:
        feature.cleanup()


def get_cli_args() -> argparse.Namespace:
    """Process command line arguments."""

    parser = argparse.ArgumentParser(description=info.DESCRIPTION)
    subparsers = parser.add_subparsers(help="Sub-command help", dest="subparser_name")

    cred_command = subparsers.add_parser(
        "cred", help="Nation login credential management"
    )
    cred_command.add_argument(
        "--add",
        nargs="*",
        metavar=("NAME", "AUTOLOGIN-CODE"),
        help="Add autologin code for a nation",
    )
    cred_command.add_argument(
        "--add-password",
        nargs="*",
        metavar=("NAME", "PASSWORD"),
        help="Add password for a nation",
    )
    cred_command.add_argument(
        "--remove", nargs="*", metavar="NAME", help="Remove login credential"
    )

    update_command = subparsers.add_parser("update", help="Update dispatches")
    update_command.add_argument(
        "dispatches",
        nargs="*",
        metavar="N",
        help="Names of dispatches to update (Leave blank means all)",
    )

    return parser.parse_args()


def main():
    """Starting point."""

    cli_args = get_cli_args()

    info.DATA_DIR.mkdir(exist_ok=True)

    info.LOGGING_DIR.parent.mkdir(exist_ok=True)
    info.LOGGING_DIR.mkdir(exist_ok=True)
    logging.config.dictConfig(info.LOGGING_CONFIG)

    try:
        nsdu_config = config.get_general_config()
        logger.debug("Loaded general configuration.")
    except config.ConfigError as err:
        print(err)
        return

    logger.info("NSDU %s started.", info.APP_VERSION)

    try:
        run(nsdu_config, cli_args)
    except exceptions.NSDUError as err:
        logger.error(err)
    except Exception as err:
        logger.exception(err)
        raise err


if __name__ == "__main__":
    main()
