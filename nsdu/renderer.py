"""Render dispatches from templates.
"""

import logging
from pathlib import Path
from typing import Callable, Mapping, Sequence

import jinja2

from nsdu import bbc_parser, exceptions, config, utils
from nsdu.bbc_parser import SimpleFormattersConfig
from nsdu.loader_api import TemplateVars
from nsdu.types import RenderContext

logger = logging.getLogger(__name__)


TemplateLoadFunc = Callable[[str], str]
FilterFunc = Callable[..., str]


class DispatchRenderError(exceptions.NSDUError):
    """Dispatch rendering error."""


class TemplateRenderError(DispatchRenderError):
    """Jinja template rendering errors."""


class JinjaTemplateLoader(jinja2.BaseLoader):
    """A Jinja template loader which uses a callback to get templates."""

    def __init__(self, template_load_func: TemplateLoadFunc):
        """A Jinja template loader which uses a callback to get templates.

        Args:
            template_load_func (TemplateLoadFunc): A callback which receives
            dispatch name and returns template text
        """

        self.template_load_func = template_load_func

    def get_source(self, _, template):
        text = self.template_load_func(template)

        return text, template, lambda: True


class TemplateRenderer:
    """Render a dispatch template using Jinja."""

    def __init__(self, template_load_func: TemplateLoadFunc) -> None:
        """Render a dispatch template using Jinja.

        Args:
            template_load_func (TemplateLoadFunc): A callback which receives
            dispatch name and returns template text
        """

        template_loader = JinjaTemplateLoader(template_load_func)
        # Make access to undefined context variables generate logs.
        undef = jinja2.make_logging_undefined(logger)
        self.env = jinja2.Environment(
            loader=template_loader, trim_blocks=True, undefined=undef
        )

    def load_filters(self, filters: Mapping[str, FilterFunc]) -> None:
        """Load custom filters into Jinja.

        Args:
            filters (Mapping[str, FilterFunc]): Filter functions keyed by name
        """

        self.env.filters.update(filters)

    def render(self, name: str, context: RenderContext) -> str:
        """Render a dispatch template.

        Args:
            name (str): Dispatch name
            context (RenderContext): Render context

        Returns:
            str: Rendered text
        """

        try:
            return self.env.get_template(name).render(context)
        except jinja2.TemplateError as err:
            raise TemplateRenderError(f"Dispatch template error: f{err}") from err


def load_filters_from_source(
    template_renderer: TemplateRenderer, filter_paths: Sequence[str]
) -> None:
    """Load custom Jinja filters from source files.

    Args:
        template_renderer (TemplateRenderer): Template renderer
        filter_paths (Sequence[str]): Paths to filter source files

    Raises:
        config.ConfigError: Filter file not found
    """

    loaded_filters: dict[str, FilterFunc] = {}

    for path in filter_paths:
        try:
            filters = utils.get_functions_from_module(path)
        except ModuleNotFoundError as err:
            raise config.ConfigError(f'Filter file not found at "{path}"') from err

        for filter_name, filter_func in filters:
            loaded_filters[filter_name] = filter_func
            logger.debug('Loaded custom Jinja filter "%s"', filter_name)

    template_renderer.load_filters(loaded_filters)
    logger.debug("Loaded all custom Jinja filters")


class DispatchRenderer:
    """Render dispatches from templates and process custom BBCode tags."""

    def __init__(
        self,
        template_load_func: TemplateLoadFunc,
        simple_fmts_config: SimpleFormattersConfig | None,
        complex_fmts_source_path: Path | None,
        template_filter_paths: Sequence[str] | None,
        template_vars: TemplateVars,
    ):
        """Render dispatches from templates and process custom BBCode tags.

        Args:
            template_load_func (TemplateLoadFunc): A callback which receives
            dispatch name and returns template text
            simple_fmts_config (SimpleFormattersConfig | None): Config for
            simple formatters
            complex_fmts_source_path (Path | None): Path to complex formatter
            source file
            template_filter_paths (Sequence[str] | None): Paths to custom Jinja filter
            source files
            template_vars (TemplateVars): Template variables
        """

        self.template_renderer = TemplateRenderer(template_load_func)
        if template_filter_paths is not None:
            load_filters_from_source(self.template_renderer, template_filter_paths)

        self.bbc_parser = bbc_parser.BbcParser(
            simple_fmts_config, complex_fmts_source_path
        )

        # Render context of all dispatches
        self.global_context = dict(template_vars)

    def render(self, name: str) -> str:
        """Render a dispatch template.

        Args:
            name (str): Dispatch name

        Returns:
            str: Rendered dispatch
        """

        context = self.global_context
        context["current_dispatch_name"] = name

        rendered = self.template_renderer.render(name, context)
        rendered = self.bbc_parser.format(rendered, context)
        logger.debug('Rendered dispatch "%s"', name)

        return rendered
