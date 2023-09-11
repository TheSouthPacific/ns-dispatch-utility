"""NationStates Dispatch Utility."""

import abc
import argparse
import importlib.metadata as import_metadata
import logging
import logging.config
import signal
import sys
from datetime import datetime, timezone
from typing import Sequence

from nsdu import config, exceptions, info, loader_managers, ns_api, updater_api, utils
from nsdu.loader_managers import (
    DispatchLoaderManager,
    LoaderManagerBuilder,
    TemplateVarLoaderManager,
    CredLoaderManager,
    SimpleBbcLoaderManager,
)
from nsdu.config import Config

logger = logging.getLogger("NSDU")


class OperationWrapper(abc.ABC):
    """Interface for classes that wrap related NSDU's operations."""

    @abc.abstractmethod
    def cleanup(self) -> None:
        """Perform final save and cleanup."""


class DispatchOperations(OperationWrapper):
    """A wrapper for dispatch operations such as update."""

    def __init__(
        self,
        dispatch_updater: updater_api.DispatchUpdater,
        dispatch_loader_manager: DispatchLoaderManager,
        cred_loader_manager: CredLoaderManager,
        dispatch_config: dict,
        dispatch_info: dict,
    ) -> None:
        """A wrapper for dispatch operations such as update.

        Args:
            dispatch_updater (updater_api.DispatchUpdater): Dispatch updater
            dispatch_loader_manager (loader.DispatchLoaderManager): Dispatch loader
            manager
            dispatch_config (dict): Dispatch config
            dispatch_info (dict): Dispatch info
            creds (Mapping[str, str]): Nation login credentials
        """

        self.dispatch_updater = dispatch_updater
        self.dispatch_loader_manager = dispatch_loader_manager
        self.dispatch_config = dispatch_config
        self.dispatch_info = dispatch_info
        self.cred_loader_manager = cred_loader_manager

    def update_a_dispatch(self, name: str) -> None:
        """Update a dispatch.

        Args:
            name (str): Dispatch name
        """

        config = self.dispatch_info[name]
        category = config["category"]
        subcategory = config["subcategory"]
        title = config["title"]
        action = config["action"]

        if action not in ("create", "edit", "remove"):
            raise exceptions.DispatchConfigError(
                f'Invalid action "{action}" on dispatch "{name}".'
            )
        dispatch_id = config.get("ns_id")
        result_time = datetime.now(tz=timezone.utc)

        try:
            if action == "create":
                logger.debug('Creating dispatch "%s" with params: %r', name, config)
                new_dispatch_id = self.dispatch_updater.create_dispatch(
                    name, title, category, subcategory
                )
                logger.debug('Got id "%s" of new dispatch "%s".', new_dispatch_id, name)
                self.dispatch_loader_manager.add_dispatch_id(name, new_dispatch_id)
                logger.info('Created dispatch "%s".', name)
            elif action == "edit":
                logger.debug(
                    'Editing dispatch "%s" with id "%s" and with params: %r',
                    name,
                    dispatch_id,
                    config,
                )
                self.dispatch_updater.edit_dispatch(
                    name, dispatch_id, title, category, subcategory
                )
                logger.info('Edited dispatch "%s".', name)
            elif action == "remove":
                logger.debug('Removing dispatch "%s" with id "%s".', name, dispatch_id)
                self.dispatch_updater.remove_dispatch(dispatch_id)
                logger.info('Removed dispatch "%s".', name)
            result_time = datetime.now(tz=timezone.utc)
            self.dispatch_loader_manager.after_update(
                name, action, "success", result_time
            )
        except exceptions.UnknownDispatchError:
            logger.error(
                'Could not find dispatch "%s" with id "%s".', name, dispatch_id
            )
            self.dispatch_loader_manager.after_update(
                name, action, "unknown-dispatch-error", result_time
            )
        except exceptions.NotOwnerDispatchError:
            logger.error('Dispatch "%s" is not owned by this nation.', name)
            self.dispatch_loader_manager.after_update(
                name, action, "not-owner-dispatch-error", result_time
            )
        except exceptions.NonexistentCategoryError as err:
            logger.error(
                '%s "%s" of dispatch "%s" is invalid.',
                err.category_type,
                err.category_value,
                name,
            )
            self.dispatch_loader_manager.after_update(
                name, action, "invalid-category-options", result_time
            )

    def update_dispatches(self, names: Sequence[str]) -> None:
        """Update dispatches. Empty list means update all.

        Args:
            names (Sequence[str]): Dispatch names
        """

        names = list(names)
        if names:
            while names[-1] not in self.dispatch_info:
                logger.error('Could not find dispatch "%s"', names[-1])
                names.pop()
                if not names:
                    return

        for owner_nation, dispatch_config in self.dispatch_config.items():
            try:
                owner_nation = utils.canonical_nation_name(owner_nation)
                self.dispatch_updater.set_owner_nation(
                    owner_nation, self.cred_loader_manager.get_cred(owner_nation)
                )
                logger.info('Begin to update dispatches of nation "%s".', owner_nation)
            except exceptions.NationLoginError:
                logger.error('Could not log in to nation "%s".', owner_nation)
                continue
            except KeyError:
                logger.error('Nation "%s" has no login credential.', owner_nation)
                continue

            if not names:
                for name in dispatch_config.keys():
                    self.update_a_dispatch(name)
            else:
                for name in dispatch_config.keys():
                    if name in names:
                        self.update_a_dispatch(name)

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


def setup_dispatch_operations(
    nsdu_config: Config, loader_manager_builder: LoaderManagerBuilder
) -> DispatchOperations:
    """Setup and return dispatch operation wrapper.

    Args:
        nsdu_config (Config): User configuration
        loader_manager_builder (loader_managers.LoaderManagerBuilder): Loader manager
        builder object

    Returns:
        DispatchOperations: Dispatch operation wrapper
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
    dispatch_config = dispatch_loader_manager.get_dispatch_metadata()
    logger.debug("Loaded dispatch config: %r", dispatch_config)

    simple_bb_config = simple_bbc_loader_manager.get_simple_bbc_config()

    template_vars = template_var_loader_manager.get_all_template_vars()
    dispatch_info = utils.get_dispatch_info(dispatch_config)
    template_vars["dispatch_info"] = dispatch_info

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

    return DispatchOperations(
        dispatch_updater,
        dispatch_loader_manager,
        cred_loader_manager,
        dispatch_config,
        dispatch_info,
    )


class CredOperations(OperationWrapper):
    """A wrapper for credential operations such as adding credential."""

    def __init__(
        self,
        cred_loader_manager: CredLoaderManager,
        login_api: ns_api.AuthApi,
    ) -> None:
        """A wrapper for credential operations such as adding credential.

        Args:
            login_api (api_adapter.LoginApi): Login API wrapper
            cred_loader_manager (loader.CredLoaderManager): Cred loader manager
        """

        self.login_api = login_api
        self.cred_loader_manager = cred_loader_manager

    def add_password_cred(self, nation_name: str, password: str) -> None:
        """Add a new credential that uses password.

        Args:
            nation_name (str): Nation name
            password (str): Password
        """

        try:
            autologin_code = self.login_api.get_autologin_code(nation_name, password)
            self.cred_loader_manager.add_cred(nation_name, autologin_code)
        except exceptions.NationLoginError:
            raise exceptions.CredOperationError(
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
            raise exceptions.CredOperationError(
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


def setup_cred_operations(
    nsdu_config: Config, loader_manager_builder: LoaderManagerBuilder
) -> CredOperations:
    """Setup and return credential operation wrapper.

    Args:
        nsdu_config (Config): User configuration
        single_loader_builder (loader.SingleLoaderManagerBuilder): Single loader
        manager builder

    Returns:
        CredOperations: Cred operation wrapper
    """

    cred_loader_manager = loader_managers.CredLoaderManager(
        nsdu_config["loaders_config"]
    )
    loader_name = nsdu_config["loaders"]["cred_loader"]
    loader_manager_builder.build(cred_loader_manager, loader_name)
    cred_loader_manager.init_loader()

    login_api = ns_api.AuthApi(nsdu_config["general"]["user_agent"])

    return CredOperations(cred_loader_manager, login_api)


def run_add_password_creds(
    operations: CredOperations, cli_args: argparse.Namespace
) -> None:
    """Run password credential add operation.

    Args:
        operations (CredOperations): Credential operation wrapper
        cli_args (argparse.Namespace): CLI argument values
    """

    if len(cli_args.add_password) % 2 != 0:
        print("There is no password for the last name.")
        return

    try:
        for i in range(0, len(cli_args.add_password), 2):
            operations.add_password_cred(
                cli_args.add_password[i], cli_args.add_password[i + 1]
            )
    except exceptions.CredOperationError as err:
        print(err)
        return

    print("Successfully added all login credentials")


def run_add_autologin_creds(
    operations: CredOperations, cli_args: argparse.Namespace
) -> None:
    """Run autologin credential add operation.

    Args:
        operations (CredOperations): Credential operation wrapper
        cli_args (argparse.Namespace): CLI argument values
    """

    if len(cli_args.add) % 2 != 0:
        print("There is no password for the last name.")
        return

    try:
        for i in range(0, len(cli_args.add), 2):
            operations.add_autologin_cred(cli_args.add[i], cli_args.add[i + 1])
    except exceptions.CredOperationError as err:
        print(err)
        return

    print("Successfully added all login credentials")


def run_remove_cred(operations: CredOperations, cli_args: argparse.Namespace) -> None:
    """Run credential remove operation.

    Args:
        operations (CredOperations): Credential operation wrapper
        cli_args (argparse.Namespace): CLI argument values
    """

    for nation_name in cli_args.remove:
        try:
            operations.remove_cred(nation_name)
            print(f'Removed login credential of "{nation_name}"')
        except exceptions.CredNotFound:
            print(f'Nation "{nation_name}" not found.')
            break


def run(nsdu_config: Config, cli_args: argparse.Namespace) -> None:
    """Run the app with user configuration and CLI argument values.

    Args:
        nsdu_config (Config): Configuration
        cli_args (argparse.Namespace): CLI argument values
    """

    custom_loader_dir_path = nsdu_config["general"].get("custom_loader_dir_path", None)
    entry_points = get_metadata_entry_points()
    loader_manager_builder = loader_managers.LoaderManagerBuilder(
        entry_points, custom_loader_dir_path
    )

    operations: OperationWrapper | None = None

    def interrupt_handler(sig, frame):
        logger.info("Exiting NSDU...")
        if operations:
            operations.cleanup()
        logger.info("Exited NSDU.")
        sys.exit()

    signal.signal(signal.SIGINT, interrupt_handler)

    if cli_args.subparser_name == "cred":
        operations = setup_cred_operations(nsdu_config, loader_manager_builder)
        if hasattr(cli_args, "add") and cli_args.add is not None:
            run_add_autologin_creds(operations, cli_args)
        elif hasattr(cli_args, "add_password") and cli_args.add_password is not None:
            run_add_password_creds(operations, cli_args)
        elif hasattr(cli_args, "remove") and cli_args.remove is not None:
            run_remove_cred(operations, cli_args)
    elif cli_args.subparser_name == "update":
        operations = setup_dispatch_operations(nsdu_config, loader_manager_builder)
        operations.update_dispatches(cli_args.dispatches)

    if operations:
        operations.cleanup()


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
