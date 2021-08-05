"""Render dispatches from templates.
"""

import logging
import pathlib

import jinja2

from nsdu import info
from nsdu import exceptions
from nsdu import info
from nsdu import bb_parser
from nsdu import utils


logger = logging.getLogger(__name__)


class JinjaTemplateLoader(jinja2.BaseLoader):
    """Load Jinja templates using a function.
    """

    def __init__(self, template_load_func):
        self.template_load_func = template_load_func

    def get_source(self, environment, template):
        text = self.template_load_func(template)
        if text is None:
            text = info.DEFAULT_TEMPLATE

        return text, template, lambda: True


class TemplateRenderer():
    """Render a dispatch template.

    Args:
        template_load_func (str): Function to load a template by name
    """

    def __init__(self, template_load_func):
        template_loader = JinjaTemplateLoader(template_load_func)
        # Make access to undefined context variables generate logs.
        undef = jinja2.make_logging_undefined(logger=logger)
        self.env = jinja2.Environment(loader=template_loader, trim_blocks=True, undefined=undef)

    def load_filters(self, filters):
        """Load filters.

        Args:
            filters (dict): Name and function of filters
        """

        self.env.filters.update(filters)

    def render(self, name, context):
        """Render a dispatch template.

        Args:
            name (str): Dispatch template name.
            context (dict): Context for the template.

        Returns:
            str: Rendered template.
        """

        return self.env.get_template(name).render(context)


def load_filters_from_source(template_renderer, filter_paths):
    """Load Jinja filters from source files.

    Args:
        template_renderer (nsdu.renderer.TemplateRenderer): Template renderer
        filter_paths (list): Paths to filter source files

    Raises:
        exceptions.ConfigError: Filter file not found
    """

    loaded_filters = {}

    for path in filter_paths:
        try:
            filters = utils.get_functions_from_module(pathlib.Path(path))
        except FileNotFoundError:
            raise exceptions.ConfigError('Filter file not found at "{}"'.format(path))

        for jinja_filter in filters:
            loaded_filters[jinja_filter[0]] = jinja_filter[1]
            logger.debug('Loaded filter "%s"', jinja_filter[0])

    template_renderer.load_filters(loaded_filters)
    logger.debug('Loaded all custom filters')


class DispatchRenderer():
    """Render dispatches from templates and process custom BBCode tags.

    Args:
        dispatch_loader: Dispatch loader
    """

    def __init__(self, template_load_func, simple_formatter_config,
                 complex_formatter_source_path, template_filter_paths, vars):
        self.template_renderer = TemplateRenderer(template_load_func)
        if template_filter_paths is not None:
            load_filters_from_source(self.template_renderer, template_filter_paths)

        self.bb_parser = bb_parser.BBParser(simple_formatter_config, complex_formatter_source_path)

        # Context all dispatches will have
        self.global_context = vars

    def render(self, name):
        """Render a dispatch.

        Args:
            name (str): Dispatch name.

        Returns:
            str: Rendered dispatch.
        """

        context = self.global_context
        context['current_dispatch'] = name

        rendered = self.template_renderer.render(name, context)
        rendered = self.bb_parser.format(rendered, **context)

        logger.debug('Rendered dispatch "%s"', name)

        return rendered
