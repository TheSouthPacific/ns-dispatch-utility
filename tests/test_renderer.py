import os
import shutil
import logging
from unittest import mock

import pytest
import toml

from nsdu import exceptions
from nsdu import renderer


@pytest.fixture
def get_mock_dispatch_loader():
    def dispatch_loader(text="Test"):
        return mock.Mock(get_dispatch_text=mock.Mock(return_value=text))

    return dispatch_loader


class TestDispatchTemplateLoader():
    def test_load_text(self):
        get_dispatch_text = mock.Mock(return_value='Test text')
        loader_plugin = mock.Mock(get_dispatch_text=get_dispatch_text)
        loader = renderer.DispatchJinjaLoader(loader_plugin)

        r = loader.get_source(mock.Mock(), 'Test')
        assert r[0] == 'Test text'
        assert r[2]()

    def test_load_text_with_loader_error(self):
        get_dispatch_text = mock.Mock(side_effect=exceptions.DispatchTextNotFound(suppress_nsdu_error=False))
        loader_plugin = mock.Mock(get_dispatch_text=get_dispatch_text)
        loader = renderer.DispatchJinjaLoader(loader_plugin)

        with pytest.raises(exceptions.DispatchRenderingError):
            loader.get_source(mock.Mock(), 'Test')


class TestTemplateRenderer():
    def test_load_filters(self, get_mock_dispatch_loader):
        dispatch_loader = get_mock_dispatch_loader()
        ins = renderer.TemplateRenderer(dispatch_loader)

        ins.load_filters('tests/resources/filters.py')

        assert ins.env.filters['filter1']

    def test_load_filters_with_non_existent_filter_file(self, get_mock_dispatch_loader):
        dispatch_loader = get_mock_dispatch_loader()
        ins = renderer.TemplateRenderer(dispatch_loader)

        with pytest.raises(exceptions.ConfigError):
            ins.load_filters('non_existent.py')

    def test_render_with_filters(self, get_mock_dispatch_loader):
        template_text = '{% for i in j %}{{ i|filter1(2) }} {{ i|filter2(3) }} {% endfor %}'
        dispatch_loader = get_mock_dispatch_loader(template_text)
        ins = renderer.TemplateRenderer(dispatch_loader)
        ins.load_filters('tests/resources/filters.py')

        r = ins.render('template', context={'j': [1, 2]})

        assert r == '1 2 1and3 2 2 2and3 '


class TestDispatchRenderer():
    def test_render(self, get_mock_dispatch_loader):
        template_text = ('{% for i in j %}[simple1]{{ i|filter2(1) }}[/simple1]{% endfor %}'
                         '[complex]{{ john.dave }}{{ current_dispatch }}[/complex][complexcfg]'
                         '{{ key1 }}[/complexcfg]')
        dispatch_loader = get_mock_dispatch_loader(template_text)
        simple_bb_config = {'simple1': {'format_string': '[simple1r]%(value)s[/simple1r]'},
                            'simple2': {'format_string': '[simple2r]%(value)s[/simple2r]'},
                            'simple3': {'format_string': '[simple3r]%(value)s[/simple3r]',
                                        'render_embedded': False}}
        complex_bb_config = {'complex_formatter_source_path': 'tests/resources/bb_complex_formatters.py',
                             'complex_formatter_config_path': 'tests/resources/bb_complex_formatter_config.toml'}
        template_config = {'filter_path': 'tests/resources/filters.py'}
        vars = {'j': [1, 2, 3],
                'john': {'dave': 'marry'},
                'key1': 'val1'}
        dispatch_config = {'nation1': {'test1': {'ns_id': 1234567, 'title': 'ABC'},
                                       'test2': {'ns_id': 7890123, 'title': 'DEF'}}}
        ins = renderer.DispatchRenderer(dispatch_loader)
        ins.load(simple_bb_config, complex_bb_config, template_config, vars, dispatch_config)

        expected = ('[simple1r]1and1[/simple1r][simple1r]2and1[/simple1r][simple1r]3and1[/simple1r]'
                    '[simple1r]marrytest1[/simple1r][complexcfgr=testcfgval]val1[/complexcfgr]')
        assert ins.render('test1') == expected

