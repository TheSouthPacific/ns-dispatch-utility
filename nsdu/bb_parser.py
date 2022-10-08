"""Convert custom BBCode tags into NSCode tags.
"""

import logging
from pathlib import Path
from typing import Callable, Mapping, Type, Union

import bbcode

from nsdu import exceptions
from nsdu import utils


logger = logging.getLogger(__name__)


class BBRegistry:
    """Complex formatter registry."""

    complex_formatters = []

    @classmethod
    def register(cls, tag_name: str, **kwargs) -> Callable:
        """A decorator to register a complex formatter.

        Args:
            tag_name (str): Tag name.
        """

        def decorator(formatter_class: Type):
            formatter_info = kwargs
            formatter_info["obj"] = formatter_class
            formatter_info["tag_name"] = tag_name
            cls.complex_formatters.append(formatter_info)

            # Return the formatter class to make tests on them possible.
            return formatter_class

        return decorator

    @classmethod
    def init_complex_formatters(cls):
        """Initialize complex formatters and give them config.
        """

        inited_formatters = []
        for formatter_info in cls.complex_formatters:
            tag_name = formatter_info["tag_name"]
            formatter_info["obj"].config = None
            formatter_info["obj"] = formatter_info["obj"]()
            inited_formatters.append(formatter_info)
            logger.debug('Initialized complex formatter "%s"', tag_name)

        cls.complex_formatters = []
        return inited_formatters


class BBParserCore:
    """A wrapper around bbcode library's parser."""

    def __init__(self) -> None:
        """A wrapper around bbcode library's parser."""

        self.parser = bbcode.Parser(
            newline="\n",
            install_defaults=False,
            escape_html=False,
            replace_links=False,
            replace_cosmetic=False,
        )

    def add_simple_formatter(self, tag_name: str, format_string: str, **kwargs):
        """Add a simple formatter.

        Args:
            tag_name (str): Tag name
            format_string (str): Template of the formatted string
        """

        self.parser.add_simple_formatter(tag_name, format_string, **kwargs)

    def add_complex_formatter(self, tag_name: str, render_func: Callable[..., str], **kwargs):
        """Add a complex formatter.

        Args:
            tag_name (str): Tag name
            render_func (Callable): A callable that returns formatted string
        """

        self.parser.add_formatter(tag_name, render_func, **kwargs)

    def format(self, text: str, **kwargs):
        """Format text with loaded formatters."""

        return self.parser.format(text, **kwargs)


def build_simple_parser_from_config(config: Mapping[str, Mapping[str, str]]) -> BBParserCore:
    """Build a BBCode parser with simple formatters loaded from config.

    Args:
        config (Mapping[str, Mapping[str, str]]): Simple formatter config

    Returns:
        BBParserCore: Parser with loaded formatters
    """

    parser = BBParserCore()
    for tag_name, format_config in config.items():
        parser.add_simple_formatter(
            tag_name=tag_name,
            format_string=format_config["format_string"],
            escape_html=False,
            replace_links=False,
            replace_cosmetic=False,
            newline_closes=format_config.get("newline_closes", False),
            same_tag_closes=format_config.get("same_tag_closes", False),
            standalone=format_config.get("standalone", False),
            render_embedded=format_config.get("render_embedded", True),
            strip=format_config.get("strip", False),
            swallow_trailing_newline=format_config.get(
                "swallow_trailing_newline", False
            ),
        )
    return parser


def build_complex_parser_from_source(source_path: Path) -> BBParserCore:
    """Build a BBCode parser with complex formatters loaded source file.

    Args:
        source_path (Path): Path to source file

    Raises:
        exceptions.ConfigError: Source file not found

    Returns:
        BBParserCore: Parser with loaded formatters
    """

    try:
        utils.load_module(source_path)
        formatters = BBRegistry.init_complex_formatters()
        logger.debug('Loaded complex formatter source file at "%s"', source_path)
    except FileNotFoundError:
        raise exceptions.ConfigError(
            'Complex formatter source file not found at "{}"'.format(source_path)
        )

    parser = BBParserCore()

    for formatter_info in formatters:
        parser.add_complex_formatter(
            tag_name=formatter_info["tag_name"],
            render_func=formatter_info.pop("obj").format,
            escape_html=False,
            replace_links=False,
            replace_cosmetic=False,
            newline_closes=formatter_info.get("newline_closes", False),
            same_tag_closes=formatter_info.get("same_tag_closes", False),
            standalone=formatter_info.get("standalone", False),
            render_embedded=formatter_info.get("render_embedded", True),
            strip=formatter_info.get("strip", False),
            swallow_trailing_newline=formatter_info.get(
                "swallow_trailing_newline", False
            ),
        )
        logger.debug('Loaded complex formatter "%s"', formatter_info["tag_name"])

    return parser


class BBParser:
    """Convert custom BBCode tags into NSCode tags."""

    def __init__(self, simple_formatter_config: Union[dict, None], complex_formatter_source_path: Union[str, None]) -> None:
        """Convert custom BBCode tags into NSCode tags.

        Args:
            simple_formatter_config (Union[dict, None]): Config for simple formatters
            complex_formatter_source_path (Union[str, None]): Path to complex formatter source file
        """

        self.simple_formatter_config = simple_formatter_config
        self.complex_formatter_source_path = complex_formatter_source_path

        if self.simple_formatter_config is not None:
            self.simple_parser = build_simple_parser_from_config(
                self.simple_formatter_config
            )

        if self.complex_formatter_source_path is not None:
            self.complex_parser = build_complex_parser_from_source(
                Path(self.complex_formatter_source_path)
            )

    def format(self, text: str, **kwargs) -> str:
        """Convert custom BBCode tags in provided text into NSCode tags.

        Args:
            text (str): Text

        Returns:
            str: Text with NSCode tags
        """

        formatted_text = text

        if self.complex_formatter_source_path is not None:
            formatted_text = self.complex_parser.format(text=formatted_text, **kwargs)

        if self.simple_formatter_config is not None:
            formatted_text = self.simple_parser.format(text=formatted_text, **kwargs)

        return formatted_text
