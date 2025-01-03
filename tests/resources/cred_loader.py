"""A simple credential loader for testing.
"""


from nsdu import loader_api
from nsdu.config import Config


class CredLoader:
    def __init__(self, loader_config: Config):
        self.loader_config = loader_config
        self.creds: dict[str, str] = loader_config

    def get_cred(self, name: str) -> str:
        return self.creds[name]

    def add_cred(self, name: str, x_autologin: str) -> None:
        self.creds[name] = x_autologin

    def remove_cred(self, name: str) -> None:
        del self.creds[name]

    def cleanup(self) -> None:
        pass


@loader_api.cred_loader
def init_cred_loader(loaders_config: Config) -> CredLoader:
    return CredLoader(loaders_config["cred_loader"])


@loader_api.cred_loader
def get_cred(loader: CredLoader, name: str) -> str:
    return loader.get_cred(name)


@loader_api.cred_loader
def add_cred(loader: CredLoader, name: str, x_autologin: str) -> None:
    return loader.add_cred(name, x_autologin)


@loader_api.cred_loader
def remove_cred(loader: CredLoader, name: str) -> None:
    return loader.remove_cred(name)


@loader_api.cred_loader
def cleanup_cred_loader(loader: CredLoader) -> None:
    loader.cleanup()
