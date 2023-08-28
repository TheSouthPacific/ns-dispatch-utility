"""A basic simple BBCode formatter config loader for testing.
"""


from nsdu import config, loader_api


@loader_api.simple_bb_loader
def get_simple_bb_config(loader_configs: config.Config):
    return {"key1": loader_configs["simplebbloader-test1"]}
