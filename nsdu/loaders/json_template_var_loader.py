"""Load template variables from JSON files."""

import json
import pathlib

from nsdu import loader_api
from nsdu.config import Config
from nsdu.loader_api import TemplateVars


@loader_api.template_var_loader
def get_template_vars(loaders_config: Config) -> TemplateVars:
    var_json_paths: list = loaders_config["json_template_var_loader"][
        "template_var_paths"
    ]

    template_vars = {}
    for path in var_json_paths:
        try:
            file_content = pathlib.Path(path).expanduser().read_text()
            template_vars.update(json.loads(file_content))
        except FileNotFoundError as err:
            raise loader_api.LoaderError(f'JSON var file "{path}" not found') from err
        except json.JSONDecodeError as err:
            raise loader_api.LoaderError(
                f'JSON var file "{path}" is invalid: {err}'
            ) from err

    return template_vars
