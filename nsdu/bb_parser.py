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
    def init_complex_formatters(cls, source_path, config):
        """Initialize complex formatters and give them config.

        Args:
            source_path (pathlib.Path): Path to complex formatter source file
            config (dict|None): Complex formatter config
        """

        utils.load_module(source_path)
        logger.debug('Loaded complex formatter source file at "%s"', source_path)

        inited_formatters = []
        for formatter_info in cls.complex_formatters:
            tag_name = formatter_info['tag_name']
            formatter_info['obj'].config = None
            if config is not None and tag_name in config:
                formatter_info['obj'].config = config[tag_name]
            formatter_info['obj'] = formatter_info['obj']()
            inited_formatters.append(formatter_info)
            logger.debug('Initialized complex formatter "%s"', tag_name)

        cls.complex_formatters = []
        return inited_formatters


class BBGenericParser():
    """Adapter of library's BBCode parser
    """

    def __init__(self):
        self.parser = bbcode.Parser(newline='\n',
                                    install_defaults=False,
                                    escape_html=False,
                                    replace_links=False,
                                    replace_cosmetic=False)

    def format(self, text, **kwargs):
        """Format text with loaded formatters.
        """

        return self.parser.format(text, **kwargs)


class BBSimpleParser(BBGenericParser):
    """Parser for formatting with simple formatters
    """

    def load_formatters(self, config):
        """Load simple formatters defined in config.

        Args:
            config (dict): Simple formatter config
        """

        for tag_name, format_config in config.items():
            self.parser.add_simple_formatter(
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


class BBComplexParser(BBGenericParser):
    """Parser for formatting with complex formatters
    """

    def load_formatters(self, bb_registry, source_path, config_path):
        """Load complex formatters from Python source file.

        Args:
            bb_registry (BBRegistry): Complex formatter registry
            source_path (pathlib.Path): Complex formatter source file path
            config_path (pathlib.Path|None): Complex formatter config file path

        Raises:
            exceptions.ConfigError: Failed to find source or config file
        """

        config = {}
        if config_path is not None:
            try:
                config = utils.get_config_from_toml(config_path)
            except FileNotFoundError:
                raise exceptions.ConfigError('Complex formatter config file not found at "{}"'.format(config_path))

        try:
            formatters = bb_registry.init_complex_formatters(source_path, config)
        except FileNotFoundError:
            raise exceptions.ConfigError('Complex formatter source file not found at "{}"'.format(source_path))

        for formatter_info in formatters:
            self.parser.add_formatter(
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


class BBParser():
    """Render NSCode tags from custom BBCode tags.

    Args:
        simple_formatter_config (dict|None): Simple formatter config
        complex_formatter_source_path (str|None): Complex formatter file path
        complex_formatter_config_path (str|None): Complex formatter config file path
    """

    def __init__(self):

        self.simple_parser = BBSimpleParser()
        self.registry = BBRegistry()
        self.complex_parser = BBComplexParser()

    def load_formatters(self, simple_formatter_config,
                        complex_formatter_source_path,
                        complex_formatter_config_path):
        """Load all formatters from their files.

        Args:
            simple_formatter_config (dict|None): Simple formatter config
            complex_formatter_source_path (str|None): Complex formatter file path
            complex_formatter_config_path (str|None): Complex formatter config file path
        """

        if simple_formatter_config is None:
            logger.debug('There is no simple formatter config')
        else:
            self.simple_parser.load_formatters(simple_formatter_config)

        if complex_formatter_config_path is None:
            logger.debug('There is no complex formatter config path')

        if complex_formatter_source_path is None:
            logger.debug('There is no complex formatter file path')
        elif complex_formatter_config_path is None:
            self.complex_parser.load_formatters(self.registry, pathlib.Path(complex_formatter_source_path), None)
        else:
            self.complex_parser.load_formatters(self.registry, pathlib.Path(complex_formatter_source_path),
                                                pathlib.Path(complex_formatter_config_path))

    def format(self, text, **kwargs):
        """Format BBCode text.

        Args:
            text (str): Text
        """

        complex_formatted_text = self.complex_parser.format(text=text, **kwargs)
        return self.simple_parser.format(text=complex_formatted_text, **kwargs)
