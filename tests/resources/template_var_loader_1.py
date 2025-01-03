"""A simple template variable loader for tests.
"""


from nsdu import loader_api
from nsdu.config import Config
from nsdu.loader_api import TemplateVars


@loader_api.template_var_loader
def get_template_vars(loaders_config: Config) -> TemplateVars:
    return loaders_config["template_var_loader_1"]
