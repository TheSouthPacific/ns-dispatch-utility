"""Load template variables from JSON files."""

from typing import Any, Mapping
import json

from nsdu import loader_api
from nsdu import exceptions


@loader_api.template_var_loader
def get_template_vars(config: Mapping[str, Any]) -> dict:
    var_json_paths: list = config["json_templatevarloader"]["template_var_paths"]

    template_vars = {}
    for path in var_json_paths:
        try:
            with open(path, encoding="utf-8") as file:
                template_vars.update(json.load(file))
        except FileNotFoundError as err:
            raise exceptions.LoaderConfigError(f'JSON var file "{path}" not found') from err
        except json.JSONDecodeError as err:
            raise exceptions.LoaderConfigError(
                f"JSON var file {path} is invalid: {err}"
            ) from err

    return template_vars
