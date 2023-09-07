"""A basic simple BBCode formatter config loader for tests.
"""


from nsdu import loader_api
from nsdu.config import Config


@loader_api.simple_bbc_loader
def get_simple_bbc_config(loaders_config: Config) -> Config:
    return loaders_config["simple_bbc_loader"]
