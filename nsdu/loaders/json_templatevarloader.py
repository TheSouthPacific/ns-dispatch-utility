"""Load template variables from JSON files."""

import pathlib
from typing import Any, Mapping
import json

from nsdu import exceptions
from nsdu import loader_api


@loader_api.template_var_loader
def get_template_vars(config: Mapping[str, Any]) -> dict:
    var_json_paths: list = config["json_templatevarloader"]["template_var_paths"]

    template_vars = {}
    for path in var_json_paths:
        try:
            file_content = pathlib.Path(path).expanduser().read_text()
            template_vars.update(json.loads(file_content))
        except FileNotFoundError as err:
            raise exceptions.LoaderConfigError(
                f'JSON var file "{path}" not found'
            ) from err
        except json.JSONDecodeError as err:
            raise exceptions.LoaderConfigError(
                f'JSON var file "{path}" is invalid: {err}'
            ) from err

    return template_vars
