from pathlib import Path
from unittest.mock import Mock

import pytest

from nsdu import BBCode
from nsdu import bbc_parser
from nsdu import exceptions
from nsdu.config import Config


class TestBBCRegistry:
    def test_init_complex_formatters_returns_inited_formatters(self):
        @BBCode.register("a")
        class FormatterA(bbc_parser.ComplexFormatter):
            def format(
                self,
                tag_name: str,
                value: str,
                options: Config,
                parent,
                context: Config,
            ) -> str:
                return "ar"

        @BBCode.register("b")
        class FormatterB(bbc_parser.ComplexFormatter):
            def format(
                self,
                tag_name: str,
                value: str,
                options: Config,
                parent,
                context: Config,
            ) -> str:
                return "br"

        formatters = bbc_parser.BBCRegistry.init_complex_formatters()
        result1 = formatters[0][0].format("a", "v", {}, Mock, {})
        result2 = formatters[1][0].format("b", "v", {}, Mock, {})

        assert result1 == "ar" and result2 == "br"

    def test_init_complex_formatters_with_no_format_method_class_raises_exception(self):
        @BBCode.register("a")
        class FormatterA:
            pass

        with pytest.raises(bbc_parser.BBCFormatterLoadingError):
            bbc_parser.BBCRegistry.init_complex_formatters()


@pytest.mark.parametrize(
    "config,result",
    [
        [
            {
                "t1": {"format_string": "[r1]%(value)s[/r1]"},
                "t2": {"format_string": "[r2]%(value)s[/r2]", "same_tag_closes": True},
            },
            "[r1]a[/r1][r2]b[/r2]",
        ],
        [
            {},
            "[t1]a[/t1][t2]b",
        ],
    ],
)
def test_build_simple_parser_from_config(config, result):
    parser = bbc_parser.build_simple_parser_from_config(config)
    r = parser.format("[t1]a[/t1][t2]b")

    assert r == result


class TestBuildComplexParserFromSource:
    def test_source_file_not_exist_raises_exception(self):
        with pytest.raises(exceptions.ConfigError):
            bbc_parser.build_complex_parser_from_source(Path(""))

    def test_source_file_exists_returns_loaded_parser(self):
        obj = bbc_parser.build_complex_parser_from_source(
            "tests/resources/bb_complex_formatters.py"
        )

        r = obj.format("[c1]a[/c1][c2]B[/c2]")

        assert r == "[cr1]a[/cr1][cr2=]B[/cr2]"


class TestBBCParser:
    def test_format_with_both_formatter_types_returns_formatted_text(self):
        simple_formatter_config = {
            "s1": {"format_string": "[sr1]%(value)s[/sr1]"},
            "s2": {"format_string": "[sr2]%(value)s[/sr2]"},
        }
        complex_formatter_source_path = "tests/resources/bb_complex_formatters.py"
        obj = bbc_parser.BBCParser(
            simple_formatter_config, complex_formatter_source_path
        )

        text = "[s1]a[/s1][s2]b[/s2][c1]complex[/c1][c2]context[/c2][c3]options[/c3]"
        result = obj.format(text, foo="bar")

        assert result == (
            "[sr1]a[/sr1][sr2]b[/sr2]"
            "[cr1]complex[/cr1][cr2=bar]context[/cr2][cr3=]options[/cr3]"
        )

    def test_format_with_only_simple_formatters_returns_formatted_text(self):
        simple_formatter_config = {
            "s1": {"format_string": "[sr1]%(value)s[/sr1]"},
            "s2": {"format_string": "[sr2]%(value)s[/sr2]"},
        }
        complex_formatter_source_path = None
        obj = bbc_parser.BBCParser(
            simple_formatter_config, complex_formatter_source_path
        )

        text = "[s1]a[/s1][s2]b[/s2]"
        result = obj.format(text)

        assert result == "[sr1]a[/sr1][sr2]b[/sr2]"

    def test_format_with_only_complex_formatters_returns_formatted_text(self):
        simple_formatter_config = None
        complex_formatter_source_path = "tests/resources/bb_complex_formatters.py"
        obj = bbc_parser.BBCParser(
            simple_formatter_config, complex_formatter_source_path
        )

        text = "[c1]complex[/c1][c2]context[/c2][c3]options[/c3]"
        result = obj.format(text, foo="bar")

        assert result == ("[cr1]complex[/cr1][cr2=bar]context[/cr2][cr3=]options[/cr3]")
