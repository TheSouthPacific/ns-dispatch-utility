import os
import logging
import pathlib
from unittest import mock

import pytest
import toml

from nsdu import BBCode
from nsdu import bb_parser
from nsdu import exceptions


class TestBBRegistry():
    def test_register_formatter_class(self):
        @BBCode.register('test', john=True)
        class Test():
            a = 1

        r = bb_parser.BBRegistry().complex_formatters[0]

        assert r['tag_name'] == 'test' and r['john'] == True
        assert r['obj'].a == 1

    def test_init_complex_formatters(self):
        ins = bb_parser.BBRegistry

        class Formatter1():
            pass

        class Formatter2():
            pass

        ins.complex_formatters = [{'tag_name': 'test1', 'obj': Formatter1, 'john': True},
                                  {'tag_name': 'test2', 'obj': Formatter2, 'john': False}]

        r = ins.init_complex_formatters()

        assert r[0]['obj'].__class__ == Formatter1
        assert r[1]['obj'].__class__ == Formatter2


class TestBuildSimpleParserFromConfig():
    def test(self):
        config = {'tag1': {'format_string': '[r1]%(value)s[/r1]',
                           'same_tag_closes': True},
                  'tag2': {'format_string': '[r2]%(value)s[/r2]'}}

        parser = bb_parser.build_simple_parser_from_config(config)
        r = parser.format('[tag1][tag2]madoka[/tag2][tag1]homura')

        assert r == '[r1][r2]madoka[/r2][/r1][r1]homura[/r1]'


class TestBuildComplexParserFromSource():
    @pytest.fixture
    def mock_bb_registry(self):
        @BBCode.register('tag1')
        class Tag1():
            def format(self, tag_name, value, options, parent, context):
                return '[r1]{}[/r1]'.format(value)

        @BBCode.register('tag2')
        class Tag2():
            def format(self, tag_name, value, options, parent, context):
                return '[r2]{}[/r2]'.format(value)

    def test_with_non_existent_source_file(self):
        with pytest.raises(exceptions.ConfigError):
            bb_parser.build_complex_parser_from_source(pathlib.Path('non_existent.py'))

    def test_with_existent_source_file(self, mock_bb_registry):
        parser = bb_parser.build_complex_parser_from_source(pathlib.Path('tests/test_bb_parser.py'))
        r = parser.format('[tag1]sayaka[/tag1][tag2]mami[/tag2]')

        assert r == '[r1]sayaka[/r1][r2]mami[/r2]'


class TestBBParserIntegration():
    def test_format_with_simple_and_complex_formatters(self):
        simple_formatter_config = {'simple1': {'format_string': '[simple1r]%(value)s[/simple1r]'},
                                   'simple2': {'format_string': '[simple2r]%(value)s[/simple2r]'},
                                   'simple3': {'format_string': '[simple3r]%(value)s[/simple3r]',
                                               'render_embedded': False}}
        complex_formatter_source_path = 'tests/resources/bb_complex_formatters.py'
        ins = bb_parser.BBParser(simple_formatter_config, complex_formatter_source_path)
        text = ('[simple1]Simple[/simple1][simple2]Simple [simple3]nested[/simple3][/simple2]'
                '[complex]Complex[/complex][complexctx]Complex context[/complexctx]'
                '[complexopt opt=test]option[/complexopt]')

        r = ins.format(text, example={'foo': 'bar'})

        assert r == ('[simple1r]Simple[/simple1r][simple2r]Simple [simple3r]nested[/simple3r][/simple2r]'
                     '[simple1r]Complex[/simple1r][complexctxr=bar]Complex context[/complexctxr]'
                     '[complexoptr=test]option[/complexoptr]')

    def test_format_with_simple_formatters_and_no_complex_formatters(self):
        simple_formatter_config = {'simple1': {'format_string': '[simple1r]%(value)s[/simple1r]'},
                                   'simple2': {'format_string': '[simple2r]%(value)s[/simple2r]'},
                                   'simple3': {'format_string': '[simple3r]%(value)s[/simple3r]',
                                               'render_embedded': False}}
        ins = bb_parser.BBParser(simple_formatter_config, None)
        text = ('[simple1]Simple[/simple1][simple2]Simple [simple3]nested[/simple3][/simple2]'
                '[complex]Complex[/complex][complexctx]Complex context[/complexctx]'
                '[complexopt opt=test]option[/complexopt]')

        r = ins.format(text, example={'foo': 'bar'})

        assert r == ('[simple1r]Simple[/simple1r][simple2r]Simple [simple3r]nested[/simple3r][/simple2r]'
                     '[complex]Complex[/complex][complexctx]Complex context[/complexctx]'
                     '[complexopt opt=test]option[/complexopt]')

    def test_format_with_complex_formatters_and_no_simple_formatters(self):
        complex_formatter_source_path = 'tests/resources/bb_complex_formatters.py'
        ins = bb_parser.BBParser(None, complex_formatter_source_path)
        text = ('[simple1]Simple[/simple1][simple2]Simple [simple3]nested[/simple3][/simple2]'
                '[complex]Complex[/complex][complexctx]Complex context[/complexctx]'
                '[complexopt opt=test]option[/complexopt]')

        r = ins.format(text, example={'foo': 'bar'})

        assert r == ('[simple1]Simple[/simple1][simple2]Simple [simple3]nested[/simple3][/simple2]'
                     '[simple1]Complex[/simple1][complexctxr=bar]Complex context[/complexctxr]'
                     '[complexoptr=test]option[/complexoptr]')