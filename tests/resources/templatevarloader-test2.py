"""A simple variable loader for testing.
"""


from nsdu import config, loader_api


@loader_api.template_var_loader
def get_template_vars(loader_configs: config.Config):
    return {"key2": loader_configs["templatevarloader-test2"]}
