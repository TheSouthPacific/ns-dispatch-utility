import os
import shutil
import logging
from unittest import mock

import pytest
import toml

from nsdu import info
from nsdu import exceptions
from nsdu import renderer


class TestDispatchTemplateLoader():
    def test_with_existent_template(self):
        template_load_func = mock.Mock(return_value='Test text')
        loader = renderer.JinjaTemplateLoader(template_load_func)

        r = loader.get_source(mock.Mock(), 'Test')
        assert r[0] == 'Test text'

    def test_with_non_existent_template(self):
        template_load_func = mock.Mock(return_value=None)
        loader = renderer.JinjaTemplateLoader(template_load_func)

        r = loader.get_source(mock.Mock(), 'Test')
        assert r[0] == info.DEFAULT_TEMPLATE


class TestTemplateRenderer():
    def test_render_with_non_existent_template(self):
        template_load_func = mock.Mock(return_value=None)
        ins = renderer.TemplateRenderer(template_load_func)

        assert ins.render('foo', {}) == info.DEFAULT_TEMPLATE

    def test_render_with_existent_template(self):
        template = '{% for i in j %}{{ i }}{% endfor %}'
        template_load_func = mock.Mock(return_value=template)
        ins = renderer.TemplateRenderer(template_load_func)

        r = ins.render('foo', {'j': [1, 2]})

        assert r == '12'

    def test_load_filters_and_render(self):
        template = '{% for i in j %}{{ i|foo_filter }}{% endfor %}'
        template_load_func = mock.Mock(return_value=template)
        ins = renderer.TemplateRenderer(template_load_func)
        def foo_filter(a):
            return '[{}]'.format(a)

        ins.load_filters({'foo_filter': foo_filter})
        r = ins.render('foo', {'j': [1, 2]})

        assert r == '[1][2]'


class TestLoadFiltersFromSource():
    def test_with_existent_files(self):
        template = '{% for i in j %}{{ i|filter1 }}{{ i|filter2(0)}}{{ i|filter3 }}{% endfor %}'
        template_load_func = mock.Mock(return_value=template)
        ins = renderer.TemplateRenderer(template_load_func)

        renderer.load_filters_from_source(ins, ['tests/resources/filters-1.py', 'tests/resources/filters-2.py'])
        r = ins.render('foo', {'j': [1,2 ]})

        assert r == '[1]1and0<1>[2]2and0<2>'

    def test_with_a_non_existent_file(self):
        ins = renderer.TemplateRenderer(mock.Mock())

        with pytest.raises(exceptions.ConfigError):
            renderer.load_filters_from_source(ins, ['tests/resources/filter-1.py', 'non-existent.py'])


class TestDispatchRenderer():
    def test_render(self):
        template = ('{% for i in j %}[complex]{{ i|filter1 }}[/complex]'
                    '[complexctx][complex]{{ i|filter2(0)}}[/complex][/complexctx]'
                    '[complexopt opt=1]{{ i|filter3 }}[/complexopt]{% endfor %}')
        template_load_func = mock.Mock(return_value=template)
        simple_bb_config = {'simple1': {'format_string': '[simple1r]%(value)s[/simple1r]'}}
        complex_formatter_source_path = 'tests/resources/bb_complex_formatters.py'
        template_filter_paths = ['tests/resources/filters-1.py', 'tests/resources/filters-2.py']
        vars = {'j': [1, 2], 'example': {'foo': 'cool'}}
        ins = renderer.DispatchRenderer(template_load_func, simple_bb_config,
                                        complex_formatter_source_path, template_filter_paths, vars)

        expected = ('[simple1r][1][/simple1r][complexctxr=cool][complex]1and0[/complex][/complexctxr][complexoptr=1]<1>[/complexoptr]'
                    '[simple1r][2][/simple1r][complexctxr=cool][complex]2and0[/complex][/complexctxr][complexoptr=1]<2>[/complexoptr]')
        assert ins.render('test1') == expected
