"""Render dispatches from templates.
"""

import logging
import pathlib

import jinja2

from nsdu import exceptions
from nsdu import bb_parser
from nsdu import utils


logger = logging.getLogger(__name__)


class DispatchJinjaLoader(jinja2.BaseLoader):
    """Wrapper around dispatch loader for Jinja environment.
    """

    def __init__(self, dispatch_loader):
        self.dispatch_loader = dispatch_loader

    def get_source(self, environment, template):
        try:
            text = self.dispatch_loader.get_dispatch_text(template)
        except exceptions.DispatchTextNotFound as err:
            if not err.suppress_nsdu_error:
                logger.error('Text %s "%s" of dispatch "%s" not found.')
            raise exceptions.DispatchRenderingError from err

        return text, template, lambda: True


class TemplateRenderer():
    """Render a dispatch template.

    Args:
        dispatch_loader (str): Dispatch loader plugin.
    """

    def __init__(self, dispatch_loader):
        template_loader = DispatchJinjaLoader(dispatch_loader)
        # Make access to undefined context variables generate logs.
        undef = jinja2.make_logging_undefined(logger=logger)
        self.env = jinja2.Environment(loader=template_loader, trim_blocks=True, undefined=undef)

    def load_filters(self, filter_path):
        """Load all filters if filter path is set.

        Args:
            filter_path (str): Path to filters file.
        """

        if filter_path is not None:
            try:
                filters = utils.get_functions_from_module(pathlib.Path(filter_path))
            except FileNotFoundError:
                raise exceptions.ConfigError('Filter file not found at "{}"'.format(filter_path))
            else:
                loaded_filters = {}
                for jinja_filter in filters:
                    loaded_filters[jinja_filter[0]] = jinja_filter[1]
                    logger.debug('Loaded filter "%s"', jinja_filter[0])
                self.env.filters.update(loaded_filters)
                logger.debug('Loaded all custom filters')

    def render(self, name, context):
        """Render a dispatch template.

        Args:
            name (str): Dispatch template name.
            context (dict): Context for the template.

        Returns:
            str: Rendered template.
        """

        return self.env.get_template(name).render(context)


class DispatchRenderer():
    """Render dispatches from templates and process custom BBCode tags.

    Args:
        dispatch_loader: Dispatch loader
    """

    def __init__(self, dispatch_loader):
        self.template_renderer = TemplateRenderer(dispatch_loader)
        self.bb_parser = bb_parser.BBParser()

        # Context all dispatches will have
        self.global_context = {}

    def load(self, simple_bb_config, complex_bb_config, template_config, vars, dispatch_config):
        """Load template renderer filters, BBCode formatters, and setup context.
        Args:
            simple_bb_config (dict): Simple BBCode formatter config
            complex_bb_config (dict): Complex BBCode formatter config
            template_config (dict): Template renderer config
            vars (dict): Variables for placeholders
            dispatch_config (dict): Dispatch config
        """

        self.template_renderer.load_filters(template_config.get('filter_path', None))
        self.bb_parser.load_formatters(simple_bb_config,
                                       complex_bb_config.get('complex_formatter_source_path', None),
                                       complex_bb_config.get('complex_formatter_config_path', None))

        self.global_context = vars
        self.global_context['dispatch_info'] = utils.get_dispatch_info(dispatch_config)

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
