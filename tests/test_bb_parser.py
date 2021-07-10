import os
import logging
import pathlib
from unittest import mock

import pytest
import toml

from nsdu import BBCode
from nsdu import bb_parser
from nsdu import exceptions


class TestBBParserCore():
    def test_add_simple_formatter(self):
        ins = bb_parser.BBParserAdapter()
        add_simple_formatter = mock.Mock()
        ins.parser.add_simple_formatter = add_simple_formatter

        ins.add_simple_formatter('test', 'test', escape_html=True)

        add_simple_formatter.assert_called_with(tag_name='test', format_string='test',
                                                escape_html=True)

    def test_add_complex_formatter(self):
        ins = bb_parser.BBParserAdapter()
        mock_func = mock.Mock()
        add_formatter = mock.Mock()
        ins.parser.add_formatter = add_formatter

        ins.add_complex_formatter('test', mock_func, escape_html=True)

        add_formatter.assert_called_with(tag_name='test', render_func=mock_func,
                                         escape_html=True)

    def test_format(self):
        ins = bb_parser.BBParserAdapter()
        mock_format = mock.Mock(return_value='Test')
        ins.parser = mock.Mock(format=mock_format)

        assert ins.format(text='abc', example='123') == 'Test'
        mock_format.assert_called_with('abc', example='123')


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
        config = {'test1': {'foo': 'bar', 'loo': 'var'},
                  'test2': {'foo2': 'bar2', 'loo2': 'var2'}}

        r = ins.init_complex_formatters('test.py', config)

        assert r[0]['obj'].config == {'foo': 'bar', 'loo': 'var'}
        assert r[1]['obj'].config == {'foo2': 'bar2', 'loo2': 'var2'}

    @mock.patch('nsdu.utils.load_module')
    def test_init_complex_formatters_with_non_existent_config(self, mock):
        ins = bb_parser.BBRegistry

        class Formatter1():
            pass

        class Formatter2():
            pass

        ins.complex_formatters = [{'tag_name': 'test1', 'obj': Formatter1, 'john': True},
                                  {'tag_name': 'test2', 'obj': Formatter2, 'john': False}]

        r = ins.init_complex_formatters('test.py', {})

        assert not hasattr(r[0]['obj'], 'config')
        assert not hasattr(r[1]['obj'], 'config')

    @mock.patch('nsdu.utils.load_module', side_effect=FileNotFoundError)
    def test_init_complex_formatters_with_non_existent_file(self, mock):
        ins = bb_parser.BBRegistry()

        with pytest.raises(FileNotFoundError):
            ins.init_complex_formatters('test.py', {})


class TestBBSimpelFormatters():
    @pytest.mark.usefixtures('toml_files')
    def test_load_simple_formatters_with_simple_formatter_file_exists(self, toml_files):
        formatters = {'tag1': {'template': 'test1',
                               'render_embedded': True,
                               'newline_closes': False},
                      'tag2': {'template': 'test2',
                               'render_embedded': True,
                               'newline_closes': False,
                               'same_tag_closes': True}}
        formatter_path = toml_files({'simple_formatters.toml': formatters})
        ins = bb_parser.BBSimpleFormatters()

        ins.load_formatters(formatter_path)

        r = [{'tag_name': 'tag1', 'template': 'test1',
              'render_embedded': True, 'newline_closes': False},
             {'tag_name': 'tag2', 'template': 'test2',
              'render_embedded': True, 'newline_closes': False, 'same_tag_closes': True}]

        assert ins.formatters == r

    def test_load_simple_formatters_with_non_existent_simple_formatter_file(self, caplog):
        """There is no error message.
        """

        ins = bb_parser.BBSimpleFormatters()

        with pytest.raises(exceptions.ConfigError):
            ins.load_formatters(pathlib.Path('non_existent.toml'))

class TestBBComplexFormatters():
    @pytest.fixture
    def mock_bb_registry(self):
        class Test1():
            def format(self):
                pass

        class Test2():
            def format(self):
                pass

        f = [{'tag_name': 'test1', 'obj': Test1(), 'newline_closes': True},
             {'tag_name': 'test2', 'obj': Test2(), 'same_tag_closes': True}]

        ins = mock.Mock(init_complex_formatters=mock.Mock(return_value=f))

        return ins

    def test_load_complex_formatters_with_non_existent_formatter_file(self):
        ins = bb_parser.BBComplexFormatters()

        mock_bb_registry = mock.Mock(init_complex_formatters=mock.Mock(side_effect=FileNotFoundError))
        with pytest.raises(exceptions.ConfigError):
            ins.load_formatters(mock_bb_registry, pathlib.Path('non_existent.py'), None)

    def test_load_complex_formatters_with_no_config(self, mock_bb_registry):
        ins = bb_parser.BBComplexFormatters()

        ins.load_formatters(mock_bb_registry, pathlib.Path('test.py'), None)

        mock_bb_registry.init_complex_formatters.assert_called_with(pathlib.Path('test.py'), {})

    def test_load_complex_formatters_with_non_existent_config(self, mock_bb_registry):
        ins = bb_parser.BBComplexFormatters()

        with pytest.raises(exceptions.ConfigError):
            ins.load_formatters(mock_bb_registry, pathlib.Path('test.py'), pathlib.Path('non_existent.toml'))

    @pytest.mark.usefixtures('toml_files')
    def test_load_complex_formatters_with_config(self, mock_bb_registry, toml_files):
        formatter_config = {'test1': {'key1': 'val1'}}
        formatter_config_path = toml_files({'formatter_config.toml': formatter_config})
        ins = bb_parser.BBComplexFormatters()

        ins.load_formatters(mock_bb_registry, pathlib.Path('test.py'), formatter_config_path)

        mock_bb_registry.init_complex_formatters.assert_called_with(pathlib.Path('test.py'), formatter_config)


class TestBBParserLoader():
    def test_load_simple_formatters_with_template_configured(self):
        mock_parser = mock.Mock(add_simple_formatter=mock.Mock())
        simple_formatters = [{'tag_name': 'tag1', 'template': 'test1', 'newline_closes': True},
                             {'tag_name': 'tag2', 'template': 'test2', 'render_embedded': False}]
        mock_simple_formatters = mock.Mock(get_formatters=mock.Mock(return_value=simple_formatters))
        ins = bb_parser.BBParserLoader(mock_parser)

        ins.load_simple_formatters(mock_simple_formatters)

        mock_parser.add_simple_formatter.assert_called_with(
            tag_name='tag2',
            template='test2',
            escape_html=False,
            replace_links=False,
            replace_cosmetic=False,
            newline_closes=False,
            same_tag_closes=False,
            standalone=False,
            render_embedded=False,
            strip=False,
            swallow_trailing_newline=False
        )

    def test_load_simple_formatters_with_template_not_configured(self):
        """Simple formatter should not be loaded.
        """

        mock_parser = mock.Mock(add_simple_formatter=mock.Mock())
        simple_formatters = [{'tag_name': 'tag1', 'newline_closes': True},
                             {'tag_name': 'tag2', 'template': 'test2', 'render_embedded': False}]
        mock_simple_formatters = mock.Mock(get_formatters=mock.Mock(return_value=simple_formatters))
        ins = bb_parser.BBParserLoader(mock_parser)

        ins.load_simple_formatters(mock_simple_formatters)

        mock_parser.add_simple_formatter.assert_called_once_with(
            tag_name='tag2',
            template='test2',
            escape_html=False,
            replace_links=False,
            replace_cosmetic=False,
            newline_closes=False,
            same_tag_closes=False,
            standalone=False,
            render_embedded=False,
            strip=False,
            swallow_trailing_newline=False
        )

    def test_load_complex_formatters(self):
        mock_parser = mock.Mock(add_complex_formatter=mock.Mock())
        mock_render_func_1 = mock.Mock()
        mock_render_func_2 = mock.Mock()
        complex_formatters = [{'tag_name': 'tag1', 'func': mock_render_func_1},
                              {'tag_name': 'tag2', 'func': mock_render_func_2, 'render_embedded': False}]
        mock_complex_formatters = mock.Mock(get_formatters=mock.Mock(return_value=complex_formatters))
        ins = bb_parser.BBParserLoader(mock_parser)

        ins.load_complex_formatters(mock_complex_formatters)

        mock_parser.add_complex_formatter.assert_called_with(
            tag_name='tag2',
            render_func=mock_render_func_2,
            escape_html=False,
            replace_links=False,
            replace_cosmetic=False,
            newline_closes=False,
            same_tag_closes=False,
            standalone=False,
            render_embedded=False,
            strip=False,
            swallow_trailing_newline=False
        )


class TestBBParserIntegration():
    def test_format_with_simple_and_complex_formatters(self):
        simple_formatter_path = 'tests/resources/bb_simple_formatters.toml'
        complex_formatter_path = 'tests/resources/bb_complex_formatters.py'
        complex_formatter_config_path = 'tests/resources/bb_complex_formatter_config.toml'
        ins = bb_parser.BBParser(simple_formatter_path, complex_formatter_path,
                                 complex_formatter_config_path)
        ins.load_formatters()
        text = ('[simple1]Simple[/simple1][simple2]Simple [simple3]nested[/simple3][/simple2]'
                '[complex]Complex[/complex][complexctx]Complex context[/complexctx]'
                '[complexcfg]Complex config [complexopt opt=test]option[/complexopt][/complexcfg]')

        r = ins.format(text, example={'foo': 'bar'})

        assert r == ('[simple1r]Simple[/simple1r][simple2r]Simple [simple3]nested[/simple3][/simple2r]'
                     '[complexr]Complex[/complexr][complexctxr=bar]Complex context[/complexctxr]'
                     '[complexcfgr=testcfgval]Complex config [complexoptr=test]option[/complexoptr][/complexcfgr]')

    def test_format_with_simple_formatters_and_no_complex_formatters(self):
        simple_formatter_path = 'tests/resources/bb_simple_formatters.toml'
        complex_formatter_path = None
        complex_formatter_config_path = None
        ins = bb_parser.BBParser(simple_formatter_path, complex_formatter_path,
                                 complex_formatter_config_path)
        ins.load_formatters()
        text = ('[simple1]Simple[/simple1][simple2]Simple [simple3]nested[/simple3][/simple2]'
                '[complex]Complex[/complex][complexctx]Complex context[/complexctx]'
                '[complexcfg]Complex config [complexopt opt=test]option[/complexopt][/complexcfg]')

        r = ins.format(text, example={'foo': 'bar'})

        assert r == ('[simple1r]Simple[/simple1r][simple2r]Simple [simple3]nested[/simple3][/simple2r]'
                     '[complex]Complex[/complex][complexctx]Complex context[/complexctx]'
                     '[complexcfg]Complex config [complexopt opt=test]option[/complexopt][/complexcfg]')

    def test_format_with_complex_formatters_and_no_simple_formatters(self):
        simple_formatter_path = None
        complex_formatter_path = 'tests/resources/bb_complex_formatters.py'
        complex_formatter_config_path = 'tests/resources/bb_complex_formatter_config.toml'
        ins = bb_parser.BBParser(simple_formatter_path, complex_formatter_path,
                                 complex_formatter_config_path)
        ins.load_formatters()
        text = ('[simple1]Simple[/simple1][simple2]Simple [simple3]nested[/simple3][/simple2]'
                '[complex]Complex[/complex][complexctx]Complex context[/complexctx]'
                '[complexcfg]Complex config [complexopt opt=test]option[/complexopt][/complexcfg]')

        r = ins.format(text, example={'foo': 'bar'})

        assert r == ('[simple1]Simple[/simple1][simple2]Simple [simple3]nested[/simple3][/simple2]'
                     '[complexr]Complex[/complexr][complexctxr=bar]Complex context[/complexctxr]'
                     '[complexcfgr=testcfgval]Complex config [complexoptr=test]option[/complexoptr][/complexcfgr]')