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
        ins = renderer.TemplateRenderer(dispatch_loader, 'tests/resources/filters.py')

        ins.load_filters()

        assert ins.env.filters['filter1']

    def test_load_filters_with_non_existent_filter_file(self, get_mock_dispatch_loader):
        dispatch_loader = get_mock_dispatch_loader()
        ins = renderer.TemplateRenderer(dispatch_loader, 'non_existent.py')

        with pytest.raises(exceptions.ConfigError):
            ins.load_filters()

    def test_render_with_filters(self, get_mock_dispatch_loader):
        template_text = '{% for i in j %}{{ i|filter1(2) }} {{ i|filter2(3) }} {% endfor %}'
        dispatch_loader = get_mock_dispatch_loader(template_text)
        ins = renderer.TemplateRenderer(dispatch_loader, 'tests/resources/filters.py')
        ins.load_filters()

        r = ins.render('template', context={'j': [1, 2]})

        assert r == '1 2 1and3 2 2 2and3 '


class TestDispatchRenderer():
    def test_render(self, get_mock_dispatch_loader):
        template_text = ('{% for i in j %}[simple1]{{ i|filter2(1) }}[/simple1]{% endfor %}'
                         '[complex]{{ john.dave }}{{ current_dispatch }}[/complex][complexcfg]'
                         '{{ key1 }}[/complexcfg]')
        dispatch_loader = get_mock_dispatch_loader(template_text)
        vars = {'j': [1, 2, 3],
                'john': {'dave': 'marry'},
                'key1': 'val1'}
        var_loader = mock.Mock(get_all_vars=mock.Mock(return_value=vars))
        dispatch_config = {'nation1': {'test1': {'ns_id': 1234567, 'title': 'ABC'},
                                       'test2': {'ns_id': 7890123, 'title': 'DEF'}}}
        template_config = {'filter_path': 'tests/resources/filters.py'}
        bb_config = {'simple_formatter_path': 'tests/resources/bb_simple_formatters.toml',
                     'complex_formatter_path': 'tests/resources/bb_complex_formatters.py',
                      'complex_formatter_config_path': 'tests/resources/bb_complex_formatter_config.toml'}
        ins = renderer.DispatchRenderer(dispatch_loader, var_loader, bb_config, template_config)
        ins.load(dispatch_config)

        expected = ('[simple1r]1and1[/simple1r][simple1r]2and1[/simple1r][simple1r]3and1[/simple1r]'
                    '[complexr]marrytest1[/complexr][complexcfgr=testcfgval]val1[/complexcfgr]')
        assert ins.render('test1') == expected

