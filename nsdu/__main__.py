"""NationStates Dispatch Utility."""


import argparse
import importlib.metadata as import_metadata
import logging
import logging.config
import signal
import sys
from argparse import Namespace
from importlib.metadata import EntryPoint
from typing import Sequence

from nsdu import config, cred, dispatch, exceptions, feature, info, loader_managers
from nsdu.config import Config

logger = logging.getLogger("NSDU")


def get_metadata_entry_points() -> Sequence[EntryPoint]:
    """Get all metadata entry points.

    Returns:
        Sequence[EntryPoint]: Entry points
    """

    try:
        return import_metadata.entry_points().select(group=info.LOADER_ENTRY_POINT_NAME)
    except KeyError:
        return []


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

    feature_obj: feature.Feature | None = None
    feature_cli_parser: feature.FeatureCliParser | None = None

    def interrupt_handler(sig, frame):
        logger.info("Exiting NSDU...")
        if feature_obj:
            feature_obj.cleanup()
        logger.info("Exited NSDU.")
        sys.exit()

    signal.signal(signal.SIGINT, interrupt_handler)

    if cli_args.subparser_name == "cred":
        feature_obj = cred.CredFeature.from_nsdu_config(
            nsdu_config, loader_manager_builder
        )
        feature_cli_parser = cred.CredCliParser(feature_obj)
    elif cli_args.subparser_name == "update":
        feature_obj = dispatch.DispatchFeature.from_nsdu_config(
            nsdu_config, loader_manager_builder
        )
        feature_cli_parser = dispatch.DispatchCliParser(feature_obj)

    if feature_obj and feature_cli_parser:
        feature_cli_parser.parse(cli_args)
        feature_obj.cleanup()


def get_cli_args() -> Namespace:
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
    except exceptions.UserError as err:
        print(err)
    except exceptions.AppError as err:
        logger.error(err)
    except Exception as err:
        logger.exception(err)
        raise err


if __name__ == "__main__":
    main()
