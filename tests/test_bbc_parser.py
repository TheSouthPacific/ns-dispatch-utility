from pathlib import Path

import pytest

from nsdu import BBCode, bbc_parser, config


class TestBBCRegistry:
    def test_init_complex_formatters_returns_inited_formatters(self):
        @BBCode.register("a")
        class FormatterA(bbc_parser.ComplexFormatter):
            def format(self, tag_name, value, options, parent, context) -> str:
                return "ar"

        @BBCode.register("b")
        class FormatterB(bbc_parser.ComplexFormatter):
            def format(self, tag_name, value, options, parent, context) -> str:
                return "br"

        formatters = bbc_parser.BBCRegistry.init_complex_formatters()
        result1 = formatters[0][0].format("a", "v", {}, None, {})
        result2 = formatters[1][0].format("b", "v", {}, None, {})

        assert result1 == "ar" and result2 == "br"

    def test_init_complex_formatters_returns_correct_formatter_config(self):
        @BBCode.register("a", render_embedded=True)
        class FormatterA(bbc_parser.ComplexFormatter):
            def format(self, tag_name, value, options, parent, context) -> str:
                return "ar"

        formatters = bbc_parser.BBCRegistry.init_complex_formatters()
        result = formatters[0][1].render_embedded

        assert result


@pytest.mark.parametrize(
    "config,expected",
    [
        [
            {
                "t1": {"format_string": "[r1]%(value)s[/r1]"},
                "t2": {"format_string": "[r2]%(value)s[/r2]"},
            },
            "[r1]a[r2]b[/r2][/r1]",
        ],
        [
            {
                "t1": {"format_string": "[r1]%(value)s[/r1]", "render_embedded": False},
                "t2": {"format_string": "[r2]%(value)s[/r2]"},
            },
            "[r1]a[t2]b[/t2][/r1]",
        ],
        [
            {},
            "[t1]a[t2]b[/t2][/t1]",
        ],
    ],
)
def test_build_simple_parser_from_config_returns_loaded_parser(config, expected):
    parser = bbc_parser.build_simple_parser_from_config(config)
    result = parser.format("[t1]a[t2]b[/t2][/t1]")

    assert result == expected


class TestBuildComplexParserFromSource:
    def test_source_file_not_exist_raises_exception(self):
        with pytest.raises(config.ConfigError):
            bbc_parser.build_complex_parser_from_source(Path(""))

    def test_source_file_exists_returns_loaded_parser(self):
        obj = bbc_parser.build_complex_parser_from_source(
            Path("tests/resources/bbc_complex_formatters.py")
        )

        result = obj.format("[c1]a[/c1][c2]b[/c2][c3]c[/c3]")

        assert result == "[cr1]a[/cr1][cr2]ctx= b[/cr2][cr3]opt= c[/cr3]"

    def test_formatter_config_is_used(self):
        obj = bbc_parser.build_complex_parser_from_source(
            Path("tests/resources/bbc_complex_formatters.py")
        )

        result = obj.format("[c2][c1]dont format nested tag[/c1][/c2]")

        assert result == "[cr2]ctx= [c1]dont format nested tag[/c1][/cr2]"


class TestBBCParser:
    def test_format_with_both_formatter_types_returns_formatted_text(self):
        simple_formatter_config = {
            "s1": {"format_string": "[sr1]%(value)s[/sr1]"},
            "s2": {"format_string": "[sr2]%(value)s[/sr2]"},
        }
        complex_formatter_source_path = Path(
            "tests/resources/bbc_complex_formatters.py"
        )
        obj = bbc_parser.BBCParser(
            simple_formatter_config, complex_formatter_source_path
        )

        text = "[s1]a[/s1] [s2]b[/s2] [c1]c[/c1] [c2]d[/c2]"
        result = obj.format(text)

        assert result == "[sr1]a[/sr1] [sr2]b[/sr2] [cr1]c[/cr1] [cr2]ctx= d[/cr2]"

    def test_format_with_only_simple_formatters_returns_formatted_text(self):
        simple_formatter_config = {
            "s1": {"format_string": "[sr1]%(value)s[/sr1]"},
            "s2": {"format_string": "[sr2]%(value)s[/sr2]"},
        }
        complex_formatter_source_path = None
        obj = bbc_parser.BBCParser(
            simple_formatter_config, complex_formatter_source_path
        )

        text = "[s1]a[/s1] [s2]b[/s2]"
        result = obj.format(text)

        assert result == "[sr1]a[/sr1] [sr2]b[/sr2]"

    def test_format_with_only_complex_formatters_returns_formatted_text(self):
        simple_formatter_config = None
        complex_formatter_source_path = Path(
            "tests/resources/bbc_complex_formatters.py"
        )
        obj = bbc_parser.BBCParser(
            simple_formatter_config, complex_formatter_source_path
        )

        text = "[c1]c[/c1] [c2]d[/c2]"
        result = obj.format(text)

        assert result == "[cr1]c[/cr1] [cr2]ctx= d[/cr2]"

    def test_format_with_context_uses_context_in_complex_formatters(self):
        simple_formatter_config = None
        complex_formatter_source_path = Path(
            "tests/resources/bbc_complex_formatters.py"
        )
        obj = bbc_parser.BBCParser(
            simple_formatter_config, complex_formatter_source_path
        )

        context_vars = {"foo": "bar"}
        text = "[c2]context[/c2]"
        result = obj.format(text, context_vars)

        assert result == "[cr2]ctx=bar context[/cr2]"

    def test_format_with_tag_options_uses_options_in_complex_formatters(self):
        simple_formatter_config = None
        complex_formatter_source_path = Path(
            "tests/resources/bbc_complex_formatters.py"
        )
        obj = bbc_parser.BBCParser(
            simple_formatter_config, complex_formatter_source_path
        )

        context_vars = {"foo": "bar"}
        text = "[c3 foo=bar]context[/c3]"
        result = obj.format(text, context_vars)

        assert result == "[cr3]opt=bar context[/cr3]"

    def test_format_with_non_existent_tag_returns_original(self):
        obj = bbc_parser.BBCParser(None, None)

        text = "[s]a[/s]"
        result = obj.format(text)

        assert result == "[s]a[/s]"
