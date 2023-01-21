import os
import logging
import pathlib
from unittest import mock

import pytest
import toml

from nsdu import BBCode
from nsdu import bb_parser
from nsdu import exceptions


class TestBBRegistry:
    def test_formatter_class_is_registered(self):
        @BBCode.register("test", same_tag_closes=True)
        class Test:
            a = 1

        r = bb_parser.BBRegistry().complex_formatters[0]

        assert r["tag_name"] == "test" and r["same_tag_closes"] == True
        assert r["obj"].a == 1

    def test_init_complex_formatters_instances_exist(self):
        ins = bb_parser.BBRegistry

        class Formatter1:
            pass

        ins.complex_formatters = [
            {"tag_name": "test1", "obj": Formatter1, "same_tag_closes": True}
        ]

        r = ins.init_complex_formatters()

        assert r[0]["obj"].__class__ == Formatter1


class TestBuildSimpleParserFromConfig:
    def test_formatters_loaded(self):
        config = {
            "tag1": {"format_string": "[r1]%(value)s[/r1]", "same_tag_closes": True}
        }

        parser = bb_parser.build_simple_parser_from_config(config)
        r = parser.format("[tag1]madoka")

        assert r == "[r1]madoka[/r1]"


class TestBuildComplexParserFromSource:
    @pytest.fixture
    def mock_bb_registry(self):
        @BBCode.register("tag1")
        class Tag1:
            def format(self, tag_name, value, options, parent, context):
                return "[r1]{}[/r1]".format(value)

        @BBCode.register("tag2")
        class Tag2:
            def format(self, tag_name, value, options, parent, context):
                return "[r2]{}[/r2]".format(value)

    def test_source_file_not_exists_raises_exception(self):
        with pytest.raises(exceptions.ConfigError):
            bb_parser.build_complex_parser_from_source(pathlib.Path("non_existent.py"))

    def test_source_file_exists_formatters_loaded(self, mock_bb_registry):
        parser = bb_parser.build_complex_parser_from_source(
            pathlib.Path("tests/test_bb_parser.py")
        )
        r = parser.format("[tag1]sayaka[/tag1]")

        assert r == "[r1]sayaka[/r1]"


class TestIntegrationBBParser:
    def test_simple_and_complex_formatters_returns_formatted_text(self):
        simple_formatter_config = {
            "simple1": {"format_string": "[simple1r]%(value)s[/simple1r]"},
            "simple2": {"format_string": "[simple2r]%(value)s[/simple2r]"},
            "simple3": {
                "format_string": "[simple3r]%(value)s[/simple3r]",
                "render_embedded": False,
            },
        }
        complex_formatter_source_path = "tests/resources/bb_complex_formatters.py"
        ins = bb_parser.BBParser(simple_formatter_config, complex_formatter_source_path)
        text = (
            "[simple1]Simple[/simple1][simple2]Simple [simple3]nested[/simple3][/simple2]"
            "[complex]Complex[/complex][complexctx][complex]Complex context[/complex][/complexctx]"
            "[complexopt opt=test]option[/complexopt]"
        )

        r = ins.format(text, example={"foo": "bar"})

        assert r == (
            "[simple1r]Simple[/simple1r][simple2r]Simple [simple3r]nested[/simple3r][/simple2r]"
            "[simple1r]Complex[/simple1r][complexctxr=bar][complex]Complex context[/complex][/complexctxr]"
            "[complexoptr=test]option[/complexoptr]"
        )

    def test_simple_formatters_and_no_complex_formatters_returns_formatted_text(self):
        simple_formatter_config = {
            "simple1": {"format_string": "[simple1r]%(value)s[/simple1r]"},
            "simple2": {"format_string": "[simple2r]%(value)s[/simple2r]"},
            "simple3": {
                "format_string": "[simple3r]%(value)s[/simple3r]",
                "render_embedded": False,
            },
        }
        ins = bb_parser.BBParser(simple_formatter_config, None)
        text = (
            "[simple1]Simple[/simple1][simple2]Simple [simple3]nested[/simple3][/simple2]"
            "[complex]Complex[/complex][complexctx][complex]Complex context[/complex][/complexctx]"
            "[complexopt opt=test]option[/complexopt]"
        )

        r = ins.format(text, example={"foo": "bar"})

        assert r == (
            "[simple1r]Simple[/simple1r][simple2r]Simple [simple3r]nested[/simple3r][/simple2r]"
            "[complex]Complex[/complex][complexctx][complex]Complex context[/complex][/complexctx]"
            "[complexopt opt=test]option[/complexopt]"
        )

    def test_complex_formatters_and_no_simple_formatters_returns_formatted_text(self):
        complex_formatter_source_path = "tests/resources/bb_complex_formatters.py"
        ins = bb_parser.BBParser(None, complex_formatter_source_path)
        text = (
            "[simple1]Simple[/simple1][simple2]Simple [simple3]nested[/simple3][/simple2]"
            "[complex]Complex[/complex][complexctx][complex]Complex context[/complex][/complexctx]"
            "[complexopt opt=test]option[/complexopt]"
        )

        r = ins.format(text, example={"foo": "bar"})

        assert r == (
            "[simple1]Simple[/simple1][simple2]Simple [simple3]nested[/simple3][/simple2]"
            "[simple1]Complex[/simple1][complexctxr=bar][complex]Complex context[/complex][/complexctxr]"
            "[complexoptr=test]option[/complexoptr]"
        )
