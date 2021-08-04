"""Parse BBCode tags.
"""

import os
import logging
import pathlib

import toml
import bbcode

from nsdu import exceptions
from nsdu import utils


logger = logging.getLogger(__name__)


class BBRegistry():
    """Complex formatter registry.
    """

    complex_formatters = []

    @classmethod
    def register(cls, tag_name, **kwargs):
        """Register a complex formatter.

        Args:
            tag_name (str): Tag name.
        """

        def decorator(class_obj):
            formatter_info = kwargs
            formatter_info['obj'] = class_obj
            formatter_info['tag_name'] = tag_name
            cls.complex_formatters.append(formatter_info)

            # Return original class object to make tests on them possible.
            return class_obj

        return decorator

    @classmethod
    def init_complex_formatters(cls):
        """Initialize complex formatters and give them config.

        Args:
            source_path (pathlib.Path): Path to complex formatter source file
            config (dict|None): Complex formatter config
        """

        inited_formatters = []
        for formatter_info in cls.complex_formatters:
            tag_name = formatter_info['tag_name']
            formatter_info['obj'].config = None
            formatter_info['obj'] = formatter_info['obj']()
            inited_formatters.append(formatter_info)
            logger.debug('Initialized complex formatter "%s"', tag_name)

        cls.complex_formatters = []
        return inited_formatters


class BBParserCore():
    """Adapter of library's BBCode parser
    """

    def __init__(self):
        self.parser = bbcode.Parser(newline='\n',
                                    install_defaults=False,
                                    escape_html=False,
                                    replace_links=False,
                                    replace_cosmetic=False)

    def add_simple_formatter(self, tag_name, format_string, **kwargs):
        self.parser.add_simple_formatter(tag_name, format_string, **kwargs)

    def add_complex_formatter(self, tag_name, render_func, **kwargs):
        self.parser.add_formatter(tag_name, render_func, **kwargs)

    def format(self, text, **kwargs):
        """Format text with loaded formatters.
        """

        return self.parser.format(text, **kwargs)


def build_simple_parser_from_config(config):
    parser = BBParserCore()

    for tag_name, format_config in config.items():
        parser.add_simple_formatter(
            tag_name=tag_name,
            format_string=format_config['format_string'],
            escape_html=False,
            replace_links=False,
            replace_cosmetic=False,
            newline_closes=format_config.get('newline_closes', False),
            same_tag_closes=format_config.get('same_tag_closes', False),
            standalone=format_config.get('standalone', False),
            render_embedded=format_config.get('render_embedded', True),
            strip=format_config.get('strip', False),
            swallow_trailing_newline=format_config.get('swallow_trailing_newline', False))

    return parser


def build_complex_parser_from_source(source_path):
    try:
        utils.load_module(source_path)
        formatters = BBRegistry.init_complex_formatters()
        logger.debug('Loaded complex formatter source file at "%s"', source_path)
    except FileNotFoundError:
        raise exceptions.ConfigError('Complex formatter source file not found at "{}"'.format(source_path))

    parser = BBParserCore()

    for formatter_info in formatters:
        parser.add_complex_formatter(
            tag_name=formatter_info['tag_name'],
            render_func=formatter_info.pop('obj').format,
            escape_html=False,
            replace_links=False,
            replace_cosmetic=False,
            newline_closes=formatter_info.get('newline_closes', False),
            same_tag_closes=formatter_info.get('same_tag_closes', False),
            standalone=formatter_info.get('standalone', False),
            render_embedded=formatter_info.get('render_embedded', True),
            strip=formatter_info.get('strip', False),
            swallow_trailing_newline=formatter_info.get('swallow_trailing_newline', False))
        logger.debug('Loaded complex formatter "%s"', formatter_info['tag_name'])

    return parser


class BBParser():
    """Render NSCode tags from custom BBCode tags.

    Args:
        simple_formatter_config (dict|None): Simple formatter config
        complex_formatter_source_path (str|None): Complex formatter file path
    """

    def __init__(self, simple_formatter_config, complex_formatter_source_path):
        self.simple_formatter_config = simple_formatter_config
        self.complex_formatter_source_path = complex_formatter_source_path

        if self.simple_formatter_config is not None:
            self.simple_parser = build_simple_parser_from_config(self.simple_formatter_config)

        if self.complex_formatter_source_path is not None:
            self.complex_parser = build_complex_parser_from_source(pathlib.Path(self.complex_formatter_source_path))

    def format(self, text, **kwargs):
        """Format BBCode text.

        Args:
            text (str): Text
        """

        formatted_text = text

        if self.complex_formatter_source_path is not None:
            formatted_text = self.complex_parser.format(text=formatted_text, **kwargs)

        if self.simple_formatter_config is not None:
            formatted_text = self.simple_parser.format(text=formatted_text, **kwargs)

        return formatted_text
