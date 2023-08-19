"""NationStates Dispatch Utility."""

import abc
import argparse
from datetime import datetime
from datetime import timezone
import importlib.metadata as import_metadata
import logging
import logging.config
import signal
import sys
from typing import Any, Mapping, Sequence

from nsdu import info
from nsdu import exceptions
from nsdu import ns_api
from nsdu import loader
from nsdu import updater_api
from nsdu import utils


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
        dispatch_loader_manager: loader.DispatchLoaderManager,
        dispatch_config: dict,
        dispatch_info: dict,
        creds: Mapping[str, str],
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
        self.creds = creds

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
                    owner_nation, self.creds[owner_nation]
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
    config: Mapping[str, Any],
    single_loader_builder: loader.SingleLoaderManagerBuilder,
    multi_loaders_builder: loader.MultiLoadersManagerBuilder,
) -> DispatchOperations:
    """Setup and return dispatch operation wrapper.

    Args:
        config (Mapping[str, Any]): User configuration
        single_loader_builder (loader.SingleLoaderManagerBuilder): Single-loader
        manager builder
        multi_loaders_builder (loader.MultiLoadersManagerBuilder): Multi-loaders
        manager builder

    Returns:
        DispatchOperations: Dispatch operation wrapper
    """

    loader_config = config["loader_config"]
    plugin_opt = config["plugins"]

    dispatch_loader_manager = loader.DispatchLoaderManager(loader_config)
    template_var_loader_manager = loader.TemplateVarLoaderManager(loader_config)
    simple_bb_loader_manager = loader.SimpleBBLoaderManager(loader_config)
    cred_loader_manager = loader.CredLoaderManager(loader_config)

    single_loader_builder.set_loader_manager(cred_loader_manager)
    single_loader_builder.load_loader(plugin_opt["cred_loader"])
    single_loader_builder.set_loader_manager(dispatch_loader_manager)
    single_loader_builder.load_loader(plugin_opt["dispatch_loader"])
    single_loader_builder.set_loader_manager(simple_bb_loader_manager)
    single_loader_builder.load_loader(plugin_opt["simple_bb_loader"])
    multi_loaders_builder.set_loader_manager(template_var_loader_manager)
    multi_loaders_builder.load_loaders(plugin_opt["template_var_loader"])

    cred_loader_manager.init_loader()
    creds = cred_loader_manager.get_creds()

    dispatch_loader_manager.init_loader()
    dispatch_config = dispatch_loader_manager.get_dispatch_config()
    logger.debug("Loaded dispatch config: %r", dispatch_config)

    simple_bb_config = simple_bb_loader_manager.get_simple_bb_config()

    template_vars = template_var_loader_manager.get_all_template_vars()
    dispatch_info = utils.get_dispatch_info(dispatch_config)
    template_vars["dispatch_info"] = dispatch_info

    rendering_config = config.get("rendering", {})
    dispatch_updater = updater_api.DispatchUpdater(
        user_agent=config["general"]["user_agent"],
        template_filter_paths=rendering_config.get("filter_paths", None),
        simple_formatter_config=simple_bb_config,
        complex_formatter_source_path=rendering_config.get(
            "complex_formatter_source_path", None
        ),
        template_load_func=dispatch_loader_manager.get_dispatch_template,
        template_vars=template_vars,
    )

    return DispatchOperations(
        dispatch_updater, dispatch_loader_manager, dispatch_config, dispatch_info, creds
    )


class CredOperations(OperationWrapper):
    """A wrapper for credential operations such as adding credential."""

    def __init__(
        self,
        cred_loader_manager: loader.CredLoaderManager,
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
    config: Mapping[str, Any], single_loader_builder: loader.SingleLoaderManagerBuilder
) -> CredOperations:
    """Setup and return credential operation wrapper.

    Args:
        config (Mapping[str, Any]): User configuration
        single_loader_builder (loader.SingleLoaderManagerBuilder): Single loader
        manager builder

    Returns:
        CredOperations: Cred operation wrapper
    """

    cred_loader_manager = loader.CredLoaderManager(config["loader_config"])
    single_loader_builder.set_loader_manager(cred_loader_manager)
    single_loader_builder.load_loader(config["plugins"]["cred_loader"])
    cred_loader_manager.init_loader()

    login_api = ns_api.AuthApi(config["general"]["user_agent"])

    return CredOperations(cred_loader_manager, login_api)


def setup_operations(
    config: Mapping[str, Any], cli_args: argparse.Namespace
) -> OperationWrapper:
    """Setup and return operation wrapper.

    Args:
        config (Mapping[str, Any]): User configuration
        cli_args (argparse.Namespace): CLI argument values

    Returns:
        OperationWrapper: Operation wrapper
    """

    custom_loader_dir_path = config["general"].get("custom_loader_dir_path", None)
    entry_points = get_metadata_entry_points()
    single_loader_builder = loader.SingleLoaderManagerBuilder(
        info.LOADER_DIR_PATH, custom_loader_dir_path, entry_points
    )
    multi_loaders_builder = loader.MultiLoadersManagerBuilder(
        info.LOADER_DIR_PATH, custom_loader_dir_path, entry_points
    )

    if cli_args.subparser_name == "update":
        return setup_dispatch_operations(
            config, single_loader_builder, multi_loaders_builder
        )
    return setup_cred_operations(config, single_loader_builder)


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


def run(config: Mapping[str, Any], cli_args: argparse.Namespace) -> None:
    """Run the app with user configuration and CLI argument values.

    Args:
        config (Mapping[str, Any]): Configuration
        cli_args (argparse.Namespace): CLI argument values
    """

    custom_loader_dir_path = config["general"].get("custom_loader_dir_path", None)
    entry_points = get_metadata_entry_points()
    single_loader_builder = loader.SingleLoaderManagerBuilder(
        info.LOADER_DIR_PATH, custom_loader_dir_path, entry_points
    )
    multi_loaders_builder = loader.MultiLoadersManagerBuilder(
        info.LOADER_DIR_PATH, custom_loader_dir_path, entry_points
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
        operations = setup_cred_operations(config, single_loader_builder)
        if hasattr(cli_args, "add") and cli_args.add is not None:
            run_add_autologin_creds(operations, cli_args)
        elif hasattr(cli_args, "add_password") and cli_args.add_password is not None:
            run_add_password_creds(operations, cli_args)
        elif hasattr(cli_args, "remove") and cli_args.remove is not None:
            run_remove_cred(operations, cli_args)
    elif cli_args.subparser_name == "update":
        operations = setup_dispatch_operations(
            config, single_loader_builder, multi_loaders_builder
        )
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
        config = utils.get_general_config()
        logger.debug("Loaded general configuration.")
    except exceptions.ConfigError as err:
        print(err)
        return

    logger.info("NSDU %s started.", info.APP_VERSION)

    try:
        run(config, cli_args)
    except exceptions.NSDUError as err:
        logger.error(err)
    except Exception as err:
        logger.exception(err)
        raise err


if __name__ == "__main__":
    main()
