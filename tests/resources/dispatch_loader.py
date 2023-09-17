"""A simple dispatch loader for tests.
"""


from datetime import datetime

from nsdu import loader_api
from nsdu.config import Config
from nsdu.loader_api import (
    DispatchOpResult,
    DispatchesMetadata,
    DispatchOp,
    DispatchMetadata,
)


class DispatchLoader:
    def __init__(self, loader_config: Config) -> None:
        self.loader_config = loader_config
        self.dispatch_ids: dict[str, str] = {}
        self.result: dict | None = None

    def get_dispatch_metadata(self) -> DispatchesMetadata:
        return {
            "n": DispatchMetadata(None, DispatchOp.CREATE, "nat", "t", "cat", "sub")
        }

    def get_dispatch_template(self, name: str) -> str:
        return name

    def add_dispatch_id(self, name: str, dispatch_id: str) -> None:
        self.dispatch_ids[name] = dispatch_id

    def after_update(
        self,
        name: str,
        action: DispatchOp,
        result: DispatchOpResult,
        result_time: datetime,
        result_details: str,
    ) -> None:
        self.result = {
            "name": name,
            "op": action,
            "result": result,
            "result_details": result_details,
            "result_time": result_time,
        }

    def cleanup_loader(self) -> None:
        pass


@loader_api.dispatch_loader
def init_dispatch_loader(loaders_config: Config) -> DispatchLoader:
    return DispatchLoader(loaders_config["dispatch_loader"])


@loader_api.dispatch_loader
def get_dispatch_metadata(loader: DispatchLoader) -> DispatchesMetadata:
    return loader.get_dispatch_metadata()


@loader_api.dispatch_loader
def get_dispatch_template(loader: DispatchLoader, name: str) -> str:
    return loader.get_dispatch_template(name)


@loader_api.dispatch_loader
def after_update(
    loader: DispatchLoader,
    name: str,
    op: DispatchOp,
    result: DispatchOpResult,
    result_details: str,
    result_time: datetime,
) -> None:
    loader.after_update(name, op, result, result_time, result_details)


@loader_api.dispatch_loader
def add_dispatch_id(loader: DispatchLoader, name: str, dispatch_id: str) -> None:
    loader.add_dispatch_id(name, dispatch_id)


@loader_api.dispatch_loader
def cleanup_dispatch_loader(loader: DispatchLoader) -> None:
    return loader.cleanup_loader()
