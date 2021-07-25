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

    @mock.patch('nsdu.utils.load_module')
    def test_init_complex_formatters(self, mock):
        ins = bb_parser.BBRegistry

        class Formatter1():
            pass

        class Formatter2():
            pass

        ins.complex_formatters = [{'tag_name': 'test1', 'obj': Formatter1, 'john': True},
                                  {'tag_name': 'test2', 'obj': Formatter2, 'john': False}]
        config = {'test1': {'foo': 'bar', 'loo': 'var'}}

        r = ins.init_complex_formatters('test.py', config)

        assert r[0]['obj'].config == {'foo': 'bar', 'loo': 'var'}
        assert r[1]['obj'].config == None

    @mock.patch('nsdu.utils.load_module')
    def test_init_complex_formatters_with_non_existent_config(self, mock):
        ins = bb_parser.BBRegistry

        class Formatter1():
            pass

        class Formatter2():
            pass

        ins.complex_formatters = [{'tag_name': 'test1', 'obj': Formatter1, 'john': True},
                                  {'tag_name': 'test2', 'obj': Formatter2, 'john': False}]

        r = ins.init_complex_formatters('test.py', None)

        assert r[0]['obj'].config == None
        assert r[1]['obj'].config == None

    @mock.patch('nsdu.utils.load_module', side_effect=FileNotFoundError)
    def test_init_complex_formatters_with_non_existent_file(self, mock):
        ins = bb_parser.BBRegistry()

        with pytest.raises(FileNotFoundError):
            ins.init_complex_formatters('test.py', {})


class TestBBSimpleParser():
    def test_load_formatters(self):
        formatter_config = {'tag1': {'format_string': '[r1]%(value)s[/r1]',
                                     'same_tag_closes': True},
                            'tag2': {'format_string': '[r2]%(value)s[/r2]'}}
        parser = bb_parser.BBSimpleParser()

        parser.load_formatters(formatter_config)
        r = parser.format('[tag1][tag2]madoka[/tag2][tag1]homura')

        assert r == '[r1][r2]madoka[/r2][/r1][r1]homura[/r1]'

class TestBBComplexParser():
    @pytest.fixture
    def mock_bb_registry(self):
        @BBCode.register('tag1')
        class Tag1():
            def format(self, tag_name, value, options, parent, context):
                return '[r1]{}[/r1]'.format(value)

        @BBCode.register('tag2')
        class Tag2():
            def format(self, tag_name, value, options, parent, context):
                if self.config is None:
                    return '[r2]{}no_config[/r2]'.format(value)
                return '[r2]{}{}[/r2]'.format(value, self.config)

    def test_load_complex_formatters_with_non_existent_formatter_file(self):
        parser = bb_parser.BBComplexParser()

        mock_bb_registry = mock.Mock(init_complex_formatters=mock.Mock(side_effect=FileNotFoundError))
        with pytest.raises(exceptions.ConfigError):
            parser.load_formatters(mock_bb_registry, pathlib.Path('non_existent.py'), None)

    def test_load_formatters_with_no_config(self, mock_bb_registry):
        parser = bb_parser.BBComplexParser()

        parser.load_formatters(bb_parser.BBRegistry(), pathlib.Path('tests/test_bb_parser.py'), None)
        r = parser.format('[tag1]sayaka[/tag1][tag2]mami[/tag2]')

        assert r == '[r1]sayaka[/r1][r2]mamino_config[/r2]'

    def test_load_formatters_with_non_existent_config(self, mock_bb_registry):
        parser = bb_parser.BBComplexParser()

        with pytest.raises(exceptions.ConfigError):
            parser.load_formatters(bb_parser.BBRegistry(), pathlib.Path('tests/test_bb_parser.py'),
                                   pathlib.Path('non_existent.toml'))

    @pytest.mark.usefixtures('toml_files')
    def test_load_formatters_with_config(self, mock_bb_registry, toml_files):
        formatter_config = {'tag2': 'fun'}
        formatter_config_path = toml_files({'formatter_config.toml': formatter_config})
        parser = bb_parser.BBComplexParser()

        parser.load_formatters(bb_parser.BBRegistry(), pathlib.Path('tests/test_bb_parser.py'),
                               formatter_config_path)
        r = parser.format('[tag1]sayaka[/tag1][tag2]mami[/tag2]')

        assert r == '[r1]sayaka[/r1][r2]mamifun[/r2]'


class TestBBParserIntegration():
    def test_format_with_simple_and_complex_formatters(self):
        simple_formatter_config = {'simple1': {'format_string': '[simple1r]%(value)s[/simple1r]'},
                                   'simple2': {'format_string': '[simple2r]%(value)s[/simple2r]'},
                                   'simple3': {'format_string': '[simple3r]%(value)s[/simple3r]',
                                               'render_embedded': False}}
        complex_formatter_path = 'tests/resources/bb_complex_formatters.py'
        complex_formatter_config_path = 'tests/resources/bb_complex_formatter_config.toml'
        ins = bb_parser.BBParser()
        ins.load_formatters(simple_formatter_config, complex_formatter_path,
                            complex_formatter_config_path)
        text = ('[simple1]Simple[/simple1][simple2]Simple [simple3]nested[/simple3][/simple2]'
                '[complex]Complex[/complex][complexctx]Complex context[/complexctx]'
                '[complexcfg]Complex config [complexopt opt=test]option[/complexopt][/complexcfg]')

        r = ins.format(text, example={'foo': 'bar'})

        assert r == ('[simple1r]Simple[/simple1r][simple2r]Simple [simple3r]nested[/simple3r][/simple2r]'
                     '[simple1r]Complex[/simple1r][complexctxr=bar]Complex context[/complexctxr]'
                     '[complexcfgr=testcfgval]Complex config [complexoptr=test]option[/complexoptr][/complexcfgr]')

    def test_format_with_simple_formatters_and_no_complex_formatters(self):
        simple_formatter_config = {'simple1': {'format_string': '[simple1r]%(value)s[/simple1r]'},
                                   'simple2': {'format_string': '[simple2r]%(value)s[/simple2r]'},
                                   'simple3': {'format_string': '[simple3r]%(value)s[/simple3r]',
                                               'render_embedded': False}}
        complex_formatter_path = None
        complex_formatter_config_path = None
        ins = bb_parser.BBParser()
        ins.load_formatters(simple_formatter_config, complex_formatter_path,
                            complex_formatter_config_path)
        text = ('[simple1]Simple[/simple1][simple2]Simple [simple3]nested[/simple3][/simple2]'
                '[complex]Complex[/complex][complexctx]Complex context[/complexctx]'
                '[complexcfg]Complex config [complexopt opt=test]option[/complexopt][/complexcfg]')

        r = ins.format(text, example={'foo': 'bar'})

        assert r == ('[simple1r]Simple[/simple1r][simple2r]Simple [simple3r]nested[/simple3r][/simple2r]'
                     '[complex]Complex[/complex][complexctx]Complex context[/complexctx]'
                     '[complexcfg]Complex config [complexopt opt=test]option[/complexopt][/complexcfg]')

    def test_format_with_complex_formatters_and_no_simple_formatters(self):
        simple_formatter_config = None
        complex_formatter_path = 'tests/resources/bb_complex_formatters.py'
        complex_formatter_config_path = 'tests/resources/bb_complex_formatter_config.toml'
        ins = bb_parser.BBParser()
        ins.load_formatters(simple_formatter_config, complex_formatter_path,
                            complex_formatter_config_path)
        text = ('[simple1]Simple[/simple1][simple2]Simple [simple3]nested[/simple3][/simple2]'
                '[complex]Complex[/complex][complexctx]Complex context[/complexctx]'
                '[complexcfg]Complex config [complexopt opt=test]option[/complexopt][/complexcfg]')

        r = ins.format(text, example={'foo': 'bar'})

        assert r == ('[simple1]Simple[/simple1][simple2]Simple [simple3]nested[/simple3][/simple2]'
                     '[simple1]Complex[/simple1][complexctxr=bar]Complex context[/complexctxr]'
                     '[complexcfgr=testcfgval]Complex config [complexoptr=test]option[/complexoptr][/complexcfgr]')