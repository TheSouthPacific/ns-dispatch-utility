"""Render dispatches from templates.
"""

import logging
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import jinja2

from nsdu import bbc_parser, config, utils
from nsdu.bbc_parser import SimpleFormattersConfig
from nsdu.types import RenderContext

logger = logging.getLogger(__name__)


TemplateLoadFunc = Callable[[str], str]
FilterFunc = Callable[..., str]
TemplateVars = Mapping[str, Any]


class JinjaTemplateLoader(jinja2.BaseLoader):
    """Load dispatch templates into Jinja from a callback function."""

    def __init__(self, template_load_func: TemplateLoadFunc):
        self.template_load_func = template_load_func

    def get_source(self, _, template: str):
        text = self.template_load_func(template)

        return text, template, lambda: True


class TemplateRenderer:
    """Render a dispatch from its template using Jinja."""

    def __init__(self, template_load_func: TemplateLoadFunc) -> None:
        """Render a dispatch from its template using Jinja.

        Args:
            template_load_func (TemplateLoadFunc): A callable that receives a
            dispatch name and returns its template
        """

        template_loader = JinjaTemplateLoader(template_load_func)
        # Make access to undefined context variables generate logs.
        undef = jinja2.make_logging_undefined(logger)
        self.env = jinja2.Environment(
            loader=template_loader, trim_blocks=True, undefined=undef
        )

    def load_filters(self, filters: Mapping[str, FilterFunc]) -> None:
        """Load template filters into Jinja.

        Args:
            filters (Mapping[str, FilterFunc]): Filter functions keyed by name
        """

        self.env.filters.update(filters)

    def render(self, name: str, context: RenderContext) -> str:
        """Render a dispatch from its template.

        Args:
            name (str): Dispatch name
            context (RenderContext): Context values

        Returns:
            str: Rendered text
        """

        return self.env.get_template(name).render(context)


def load_filters_from_source(
    template_renderer: TemplateRenderer, filter_paths: Sequence[str]
) -> None:
    """Load Jinja filters from source files.

    Args:
        template_renderer (TemplateRenderer): Template renderer
        filter_paths (Sequence[str]): Paths to filter source files

    Raises:
        exceptions.ConfigError: Filter file not found
    """

    loaded_filters = {}

    for path in filter_paths:
        try:
            filters = utils.get_functions_from_module(path)
        except ModuleNotFoundError as err:
            raise config.ConfigError(f'Filter file not found at "{path}"') from err

        for jinja_filter in filters:
            filter_name = jinja_filter[0]
            loaded_filters[filter_name] = jinja_filter[1]
            logger.debug('Loaded filter "%s"', jinja_filter[0])

    template_renderer.load_filters(loaded_filters)
    logger.debug("Loaded all custom filters")


class DispatchRenderer:
    """Render dispatches from templates and process custom BBCode tags."""

    def __init__(
        self,
        template_load_func: TemplateLoadFunc,
        simple_fmts_config: SimpleFormattersConfig | None,
        complex_fmts_source_path: Path | None,
        template_filter_paths: Sequence[str],
        template_vars: TemplateVars,
    ):
        """Render dispatches from templates and process custom BBCode tags.

        Args:
            template_load_func (TemplateLoadFunc): A callable that receives
            a dispatch name and returns its template
            simple_fmts_config (SimpleFormattersConfig | None): Config for
            simple formatters
            complex_fmts_source_path (Path | None): Path to complex formatter
            source file
            template_filter_paths (Sequence[str]): Paths to filter source files
            template_vars (TemplateVars): Template variables
        """

        self.template_renderer = TemplateRenderer(template_load_func)
        if template_filter_paths is not None:
            load_filters_from_source(self.template_renderer, template_filter_paths)

        self.bbc_parser = bbc_parser.BBCParser(
            simple_fmts_config, complex_fmts_source_path
        )

        # Render context all dispatches will have
        self.global_context = dict(template_vars)

    def render(self, name: str) -> str:
        """Render a dispatch.

        Args:
            name (str): Dispatch name.

        Returns:
            str: Rendered dispatch.
        """

        context = self.global_context
        context["current_dispatch_name"] = name

        rendered = self.template_renderer.render(name, context)
        rendered = self.bbc_parser.format(rendered, context)
        logger.debug('Rendered dispatch "%s"', name)

        return rendered
