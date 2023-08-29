"""Convert custom BBCode tags into NSCode tags.
"""

from abc import ABC, abstractmethod
from collections import namedtuple
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Type

import bbcode

from nsdu import config, utils
from nsdu.config import Config
from nsdu.types import RenderContext

logger = logging.getLogger(__name__)

SimpleFormattersConfig = dict[str, Config]


class ComplexFormatter(ABC):
    """Base class for a complex BBCode formatter."""

    @abstractmethod
    def format(
        self, tag_name: str, value: str, options: Config, parent: Any, context: Config
    ) -> str:
        """Format text between the tags and return it.

        Args:
            tag_name (str): Tag name
            value (str): Text to format
            options (Config): Tag options
            parent (Any): Parent tag object
            context (Config): Context variables

        Returns:
            str: Formatted text
        """


@dataclass(frozen=True)
class FormatterConfig:
    """Configuration of a BBCode formatter."""

    tag_name: str
    newline_closes: bool
    same_tag_closes: bool
    standalone: bool
    render_embedded: bool
    strip: bool
    swallow_trailing_newline: bool


ComplexFormatterTuple = namedtuple("ComplexFormatter", "cls config")
InitedComplexFormatterTuple = namedtuple("InitedComplexFormatter", "obj config")


class BBCRegistry:
    """A registry for complex BBCode formatters."""

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
    ):
        """Register a complex BBCode formatter class.

        Args:
            tag_name (str): Tag name
            newline_closes (bool, optional): Close tag on newline. Defaults to False.
            same_tag_closes (bool, optional): Use same new tag to close current tag.
            Defaults to False.
            standalone (bool, optional): No close tag needed. Defaults to False.
            render_embedded (bool, optional): Format nested tags. Defaults to False.
            strip (bool, optional): Strip trailing whitespaces. Defaults to False.
            swallow_trailing_newline (bool, optional): Swallow trailing newline.
            Defaults to False.
        """

        def decorator(fmt_class: Type[ComplexFormatter]):
            fmt_config = FormatterConfig(
                tag_name,
                newline_closes,
                same_tag_closes,
                standalone,
                render_embedded,
                strip,
                swallow_trailing_newline,
            )
            cls.complex_formatters.append(ComplexFormatterTuple(fmt_class, fmt_config))

        return decorator

    @classmethod
    def init_complex_formatters(cls) -> list[InitedComplexFormatterTuple]:
        """Initialize complex formatters.

        Raises:
            BBCFormatterLoadingError: Failed to load a formatter

        Returns:
            list[InitedComplexFormatterTuple]: Initialized formatters
        """

        inited_formatters: list[InitedComplexFormatterTuple] = []

        for fmt_cls, fmt_config in cls.complex_formatters:
            fmt_obj = fmt_cls()
            inited_formatters.append(InitedComplexFormatterTuple(fmt_obj, fmt_config))
            logger.debug('Initialized complex formatter "%s"', fmt_config.tag_name)

        cls.complex_formatters = []
        return inited_formatters


class BBCParserAdapter:
    """An adapter for the bbcode library."""

    def __init__(self) -> None:
        """An adapter for the bbcode library."""

        self.parser = bbcode.Parser(
            newline="\n",
            install_defaults=False,
            escape_html=False,
            replace_links=False,
            replace_cosmetic=False,
        )

    def add_simple_formatter(self, format_string: str, config: FormatterConfig) -> None:
        """Add a simple BBCode formatter.

        Args:
            format_string (str): Format template
            config (FormatterConfig): Formatter config
        """

        self.parser.add_simple_formatter(
            config.tag_name,
            format_string,
            newline_closes=config.newline_closes,
            same_tag_closes=config.same_tag_closes,
            standalone=config.standalone,
            render_embedded=config.render_embedded,
            strip=config.strip,
            swallow_trailing_newline=config.swallow_trailing_newline,
        )

    def add_complex_formatter(
        self, formatter_obj: ComplexFormatter, config: FormatterConfig
    ) -> None:
        """Add a complex BBCode formatter.

        Args:
            render_func (ComplexFormatter): Formatter object
            config (FormatterConfig): Formatter config
        """

        self.parser.add_formatter(
            config.tag_name,
            formatter_obj.format,
            newline_closes=config.newline_closes,
            same_tag_closes=config.same_tag_closes,
            standalone=config.standalone,
            render_embedded=config.render_embedded,
            strip=config.strip,
            swallow_trailing_newline=config.swallow_trailing_newline,
        )

    def format(self, text: str, context: RenderContext | None = None) -> str:
        """Format text with the added formatters.

        Args:
            text (str): Text to format
            context (RenderContext | None): Context values. Defaults to None

        Returns:
            str: Formatted text
        """

        return self.parser.format(text, **context or {})


def build_simple_parser_from_config(
    formatters_config: SimpleFormattersConfig,
) -> BBCParserAdapter:
    """Build a BBCode parser with simple formatters defined in config.

    Args:
        formatters_config (SimpleFormattersConfig): Simple formatters' config

    Returns:
        BBCParserAdapter: Parser with loaded formatters
    """

    parser = BBCParserAdapter()
    for tag_name, config_dict in formatters_config.items():
        fmt_config = FormatterConfig(
            tag_name,
            config_dict.get("newline_closes", False),
            config_dict.get("same_tag_closes", False),
            config_dict.get("standalone", False),
            config_dict.get("render_embedded", True),
            config_dict.get("strip", False),
            config_dict.get("swallow_trailing_newline", False),
        )
        parser.add_simple_formatter(config_dict["format_string"], fmt_config)
        logger.debug('Loaded simple formatter "%s"', tag_name)
    return parser


def build_complex_parser_from_source(source_path: Path) -> BBCParserAdapter:
    """Build a BBCode parser with complex formatters loaded from source file.

    Args:
        source_path (Path): Path to source file

    Raises:
        FormatterLoadingError: Source file not found

    Returns:
        BBCParserAdapter: Parser with loaded formatters
    """

    try:
        utils.load_module(source_path)
        formatters = BBCRegistry.init_complex_formatters()
        logger.debug('Loaded complex formatter source file at "%s"', source_path)
    except ModuleNotFoundError as err:
        raise config.ConfigError(
            f'Complex formatter source file not found at "{source_path}"'
        ) from err

    parser = BBCParserAdapter()
    for fmt_obj, fmt_config in formatters:
        parser.add_complex_formatter(fmt_obj, fmt_config)
        logger.debug('Loaded complex formatter "%s"', fmt_config.tag_name)
    return parser


class BBCParser:
    """A parser to convert custom BBCode tags into NSCode tags."""

    def __init__(
        self,
        simple_fmts_config: SimpleFormattersConfig | None,
        complex_fmts_source_path: Path | None,
    ) -> None:
        """A parser to convert custom BBCode tags into NSCode tags.

        Args:
            simple_fmts_config (SimpleFormattersConfig | None): Config for
            simple formatters
            complex_fmts_source_path (Path | None): Path to source file of
            complex formatters
        """

        self.simple_parser = None
        if simple_fmts_config is not None:
            self.simple_parser = build_simple_parser_from_config(simple_fmts_config)

        self.complex_parser = None
        if complex_fmts_source_path is not None:
            self.complex_parser = build_complex_parser_from_source(
                complex_fmts_source_path
            )

    def format(self, text: str, context: RenderContext | None = None) -> str:
        """Convert custom BBCode tags in the provided text into NSCode tags.

        Args:
            text (str): Text with BBCode tags
            context (RenderContext | None): Context values. Defaults to None.

        Returns:
            str: Text with NSCode tags
        """

        formatted_text = text

        # Complex tags are evaluated first
        if self.complex_parser is not None:
            formatted_text = self.complex_parser.format(formatted_text, context)

        if self.simple_parser is not None:
            formatted_text = self.simple_parser.format(formatted_text, context)

        return formatted_text
