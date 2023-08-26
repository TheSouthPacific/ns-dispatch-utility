"""Convert custom BBCode tags into NSCode tags.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Callable, Mapping, Type

import bbcode

from nsdu import exceptions
from nsdu import utils
from nsdu.config import Config

logger = logging.getLogger(__name__)


SimpleFormatterConfig = Mapping[str, str]
SimpleFormatterConfigs = Mapping[str, SimpleFormatterConfig]


class BBCFormatterLoadingError(exceptions.NSDUError):
    pass


class ComplexFormatter(ABC):
    @abstractmethod
    def format(
        self, tag_name: str, value: str, options: Config, parent, context: Config
    ) -> str:
        pass


@dataclass
class ComplexFormatterConfig:
    tag_name: str
    newline_closes: bool
    same_tag_closes: bool
    standalone: bool
    render_embedded: bool
    strip: bool
    swallow_trailing_newline: bool


InitedComplexFormatterTuple = tuple[ComplexFormatter, ComplexFormatterConfig]


class BBCRegistry:
    """A registry for complex BBCode formatters."""

    ComplexFormatterTuple = tuple[Type[ComplexFormatter], ComplexFormatterConfig]
    complex_formatters: list[ComplexFormatterTuple] = []

    @classmethod
    def register(
        cls,
        tag_name: str,
        newline_closes=False,
        same_tag_closes=False,
        standalone=False,
        render_embedded=False,
        strip=False,
        swallow_trailing_newline=False,
    ) -> Callable:
        """A decorator to register a complex formatter.

        Args:
            tag_name (str): Tag name.
        """

        def decorator(formatter_class: Type[ComplexFormatter]):
            formatter_config = ComplexFormatterConfig(
                tag_name,
                newline_closes,
                same_tag_closes,
                standalone,
                render_embedded,
                strip,
                swallow_trailing_newline,
            )
            cls.complex_formatters.append((formatter_class, formatter_config))

        return decorator

    @classmethod
    def init_complex_formatters(cls) -> list[InitedComplexFormatterTuple]:
        """Initialize complex formatters."""

        inited_formatters: list[InitedComplexFormatterTuple] = []
        for formatter_cls, config in cls.complex_formatters:
            try:
                formatter_cls.format
            except AttributeError as err:
                cls.complex_formatters = []
                raise BBCFormatterLoadingError(
                    f"Could not find format method in "
                    f'complex formatter class "{formatter_cls.__name__}"'
                ) from err

            formatter_obj = formatter_cls()
            inited_formatters.append((formatter_obj, config))
            logger.debug('Initialized complex formatter "%s"', config.tag_name)

        cls.complex_formatters = []
        return inited_formatters


class BBCParserAdapter:
    """An adapter for the bbcode library's API."""

    def __init__(self) -> None:
        """An adapter for the bbcode library's API."""

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
            tag_name (str): BBCode tag name
            format_string (str): Template for the formatted string
        """

        self.parser.add_simple_formatter(tag_name, format_string, **kwargs)

    def add_complex_formatter(
        self, tag_name: str, render_func: Callable[..., str], **kwargs
    ):
        """Add a complex formatter.

        Args:
            tag_name (str): BBCode tag name
            render_func (Callable): A callable that returns the formatted string
        """

        self.parser.add_formatter(tag_name, render_func, **kwargs)

    def format(self, text: str, **kwargs):
        """Format text with the added formatters."""

        return self.parser.format(text, **kwargs)


def build_simple_parser_from_config(config: SimpleFormatterConfigs) -> BBCParserAdapter:
    """Build a BBCode parser with simple formatters loaded from config.

    Args:
        config (SimpleFormatterConfigs): Simple formatter config

    Returns:
        BBCParserAdapter: Parser with loaded formatters
    """

    parser = BBCParserAdapter()
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


def build_complex_parser_from_source(source_path: Path | str) -> BBCParserAdapter:
    """Build a BBCode parser with complex formatters loaded source file.

    Args:
        source_path (Path | str): Path to source file

    Raises:
        exceptions.ConfigError: Source file not found

    Returns:
        BBParserCore: Parser with loaded formatters
    """

    try:
        utils.load_module(source_path)
        formatters = BBCRegistry.init_complex_formatters()
        logger.debug('Loaded complex formatter source file at "%s"', source_path)
    except FileNotFoundError:
        raise exceptions.ConfigError(
            'Complex formatter source file not found at "{}"'.format(source_path)
        )

    parser = BBCParserAdapter()

    for obj, config in formatters:
        parser.add_complex_formatter(
            tag_name=config.tag_name,
            render_func=obj.format,
            escape_html=False,
            replace_links=False,
            replace_cosmetic=False,
            newline_closes=config.newline_closes,
            same_tag_closes=config.same_tag_closes,
            standalone=config.standalone,
            render_embedded=config.render_embedded,
            strip=config.strip,
            swallow_trailing_newline=config.swallow_trailing_newline,
        )
        logger.debug('Loaded complex formatter "%s"', obj, config.tag_name)

    return parser


class BBCParser:
    """A parser to convert custom BBCode tags into NSCode tags."""

    def __init__(
        self,
        simple_formatter_config: SimpleFormatterConfigs | None,
        complex_formatter_source_path: Path | str | None,
    ) -> None:
        """A parser to convert custom BBCode tags into NSCode tags.

        Args:
            simple_formatter_config (SimpleFormatterConfigs | None): Config for
            simple formatters
            complex_formatter_source_path (Path | str | None): Path to complex formatter
            source file
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

        # Complex formatters take precedence over simple formatters
        if self.complex_formatter_source_path is not None:
            formatted_text = self.complex_parser.format(text=formatted_text, **kwargs)

        if self.simple_formatter_config is not None:
            formatted_text = self.simple_parser.format(text=formatted_text, **kwargs)

        return formatted_text
