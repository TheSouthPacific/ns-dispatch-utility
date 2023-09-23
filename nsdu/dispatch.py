"""Dispatch management."""

from __future__ import annotations

import logging
from argparse import Namespace
from datetime import datetime, timezone
from typing import Sequence

from nsdu import feature, loader_api, ns_api, updater_api, utils
from nsdu.config import Config
from nsdu.loader_api import DispatchesMetadata, DispatchOp, DispatchOpResult
from nsdu.loader_managers import (
    CredLoaderManager,
    DispatchLoaderManager,
    LoaderManagerBuilder,
    SimpleBbcLoaderManager,
    TemplateVarLoaderManager,
)

logger = logging.getLogger(__name__)


def group_dispatches_by_owner_nation(
    dispatches_metadata: DispatchesMetadata,
) -> dict[str, DispatchesMetadata]:
    """Group dispatch metadata objects by their owner nation.

    Args:
        dispatches_metadata (DispatchesMetadata): Metadata of dispatches

    Returns:
        dict[str, DispatchesMetadata]: Dispatch metadata objects keyed by owner nation
    """

    groups: dict[str, DispatchesMetadata] = {}
    for name, metadata in dispatches_metadata.items():
        nation = metadata.owner_nation
        if nation not in groups:
            groups[nation] = {}
        groups[nation][name] = metadata
    return groups


def get_dispatches_to_execute(
    dispatches_metadata: DispatchesMetadata, names: Sequence[str]
) -> DispatchesMetadata:
    """Get dispatches to execute by dispatch names.
    If no name is provided, use all dispatches.

    Args:
        dispatches_metadata (DispatchesMetadata): Metadata of dispatches
        names (Sequence[str]): Dispatch names

    Returns:
        DispatchesMetadata: Metadata of dispatches
    """

    if not names:
        return dispatches_metadata

    dispatches_to_execute = {
        name: metadata
        for name, metadata in dispatches_metadata.items()
        if name in names
    }

    not_found_names = list(
        filter(lambda name: name not in dispatches_to_execute.keys(), names)
    )
    if not_found_names:
        logger.error('Could not find dispatches "%s"', ", ".join(not_found_names))

    return dispatches_to_execute


class DispatchFeature(feature.Feature):
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

        plugin_opts = nsdu_config["plugins"]
        loaders_config = nsdu_config["loaders_config"]

        dispatch_loader_manager = DispatchLoaderManager(loaders_config)
        template_var_loader_manager = TemplateVarLoaderManager(loaders_config)
        simple_bbc_loader_manager = SimpleBbcLoaderManager(loaders_config)
        cred_loader_manager = CredLoaderManager(loaders_config)

        loader_manager_builder.build(
            dispatch_loader_manager, plugin_opts["dispatch_loader"]
        )
        loader_manager_builder.build(
            template_var_loader_manager, plugin_opts["template_var_loader"]
        )
        loader_manager_builder.build(cred_loader_manager, plugin_opts["cred_loader"])
        loader_manager_builder.build(
            simple_bbc_loader_manager, plugin_opts["simple_bbc_loader"]
        )

        cred_loader_manager.init_loader()

        dispatch_loader_manager.init_loader()
        dispatch_metadata = dispatch_loader_manager.get_dispatch_metadata()
        logger.debug("Loaded dispatch config: %r", dispatch_metadata)

        simple_fmts_config = simple_bbc_loader_manager.get_simple_bbc_config()

        template_vars = template_var_loader_manager.get_all_template_vars()
        template_vars["dispatch_info"] = dispatch_metadata

        rendering_config = nsdu_config.get("rendering", {})
        dispatch_updater = updater_api.DispatchUpdater(
            user_agent=nsdu_config["general"]["user_agent"],
            template_filter_paths=rendering_config.get("filter_paths", None),
            simple_fmts_config=simple_fmts_config,
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

    def execute_dispatch_operation(self, name: str) -> None:
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

        if dispatch_id is None and operation in [DispatchOp.EDIT, DispatchOp.DELETE]:
            raise updater_api.DispatchMetadataError(f'Dispatch "{name}" has no ID')

        try:
            if operation == DispatchOp.CREATE:
                logger.info('Creating dispatch "%s".', name)
                new_dispatch_id = self.dispatch_updater.create_dispatch(
                    name, title, category, subcategory
                )
                logger.debug('Got ID "%s" of new dispatch "%s".', new_dispatch_id, name)
                self.dispatch_loader_manager.add_dispatch_id(name, new_dispatch_id)

            if operation == DispatchOp.EDIT:
                logger.info('Editing dispatch "%s".', name)
                self.dispatch_updater.edit_dispatch(
                    name, dispatch_id, title, category, subcategory  # type: ignore
                )
            elif operation == DispatchOp.DELETE:
                logger.info('Deleting dispatch "%s".', name)
                self.dispatch_updater.delete_dispatch(dispatch_id)  # type: ignore

            result_time = datetime.now(tz=timezone.utc)
            self.dispatch_loader_manager.after_update(
                name, operation, DispatchOpResult.SUCCESS, result_time
            )
            logger.debug(f'Operation for dispatch "{name}" finished.')
        except ns_api.DispatchApiError as err:
            err_message = str(err)
            logger.error('Operation for dispatch "%s" failed: %s', name, err)

            result_time = datetime.now(tz=timezone.utc)
            self.dispatch_loader_manager.after_update(
                name, operation, DispatchOpResult.FAILURE, result_time, err_message
            )

    def execute_dispatch_operations(self, names: Sequence[str]) -> None:
        """Execute operations of dispatches with provided names.
        Empty list means all dispatches.

        Args:
            names (Sequence[str]): Dispatch names
        """

        dispatches_to_execute = get_dispatches_to_execute(
            self.dispatches_metadata, names
        )

        dispatch_groups = group_dispatches_by_owner_nation(dispatches_to_execute)

        for nation, dispatches_metadata in dispatch_groups.items():
            try:
                nation = utils.canonical_nation_name(nation)
                owner_nation_cred = self.cred_loader_manager.get_cred(nation)
                self.dispatch_updater.set_nation(nation, owner_nation_cred)
                logger.info('Begin to update dispatches of nation "%s".', nation)
            except ns_api.AuthApiError as err:
                logger.error(err)
                continue
            except loader_api.CredNotFound:
                logger.error('Nation "%s" has no login credential.', nation)
                continue

            for name in dispatches_metadata.keys():
                self.execute_dispatch_operation(name)

        logger.info("All dispatch operations finished")

    def cleanup(self) -> None:
        """Cleanup loaders (include saving dispatch metadata changes)."""

        self.dispatch_loader_manager.cleanup_loader()


class DispatchCliParser(feature.FeatureCliParser):
    def __init__(self, feature: DispatchFeature) -> None:
        self.feature = feature

    def parse(self, cli_args: Namespace) -> None:
        self.feature.execute_dispatch_operations(cli_args.dispatches)
