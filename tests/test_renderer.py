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
    def test_exising_template_returns_template_text(self):
        template_load_func = mock.Mock(return_value='Test text')
        obj = renderer.JinjaTemplateLoader(template_load_func)

        r = obj.get_source(mock.Mock(), 'Test')
        assert r[0] == 'Test text'

    def test_non_existent_template_raises_exception(self):
        template_load_func = mock.Mock(side_effect=exceptions.DispatchTemplateNotFound)
        obj = renderer.JinjaTemplateLoader(template_load_func)

        with pytest.raises(exceptions.DispatchTemplateNotFound):
            obj.get_source(mock.Mock(), 'Test')


class TestTemplateRenderer():
    def test_render_non_existent_template_raises_exception(self):
        template_load_func = mock.Mock(side_effect=exceptions.DispatchTemplateNotFound)
        obj = renderer.TemplateRenderer(template_load_func)

        with pytest.raises(exceptions.DispatchTemplateNotFound):
            obj.render('foo', {})

    def test_render_existent_template_returns_rendered_text(self):
        template = '{{ i }}'
        template_load_func = mock.Mock(return_value=template)
        obj = renderer.TemplateRenderer(template_load_func)

        r = obj.render('foo', {'i': '1'})

        assert r == '1'

    def test_load_filters_filters_are_loaded(self):
        template = '{{ i|foo_filter }}'
        template_load_func = mock.Mock(return_value=template)
        obj = renderer.TemplateRenderer(template_load_func)
        def foo_filter(a):
            return '[{}]'.format(a)

        obj.load_filters({'foo_filter': foo_filter})
        r = obj.render('foo', {'i': '1'})

        assert r == '[1]'


class TestLoadFiltersFromSource():
    def test_files_exist_filters_are_loaded(self):
        template = '{{ i|filter1 }}'
        template_load_func = mock.Mock(return_value=template)
        obj = renderer.TemplateRenderer(template_load_func)

        renderer.load_filters_from_source(obj, ['tests/resources/filters-1.py'])
        r = obj.render('foo', {'i': 1})

        assert r == '[1]'

    def test_files_not_exist_raises_exception(self):
        obj = renderer.TemplateRenderer(mock.Mock())

        with pytest.raises(exceptions.ConfigError):
            renderer.load_filters_from_source(obj, ['non-existent.py'])


class TestIntegrationDispatchRenderer():
    def test_render(self):
        template = ('{% for i in j %}[complex]{{ i|filter1 }}[/complex]'
                    '[complexctx][complex]{{ i|filter2(0)}}[/complex][/complexctx]'
                    '[complexopt opt=1]{{ i|filter3 }}[/complexopt]{% endfor %}')
        template_load_func = mock.Mock(return_value=template)
        simple_bb_config = {'simple1': {'format_string': '[simple1r]%(value)s[/simple1r]'}}
        complex_formatter_source_path = 'tests/resources/bb_complex_formatters.py'
        template_filter_paths = ['tests/resources/filters-1.py', 'tests/resources/filters-2.py']
        template_vars = {'j': [1, 2], 'example': {'foo': 'cool'}}
        ins = renderer.DispatchRenderer(template_load_func, simple_bb_config,
                                        complex_formatter_source_path, template_filter_paths, template_vars)

        expected = ('[simple1r][1][/simple1r][complexctxr=cool][complex]1and0[/complex][/complexctxr][complexoptr=1]<1>[/complexoptr]'
                    '[simple1r][2][/simple1r][complexctxr=cool][complex]2and0[/complex][/complexctxr][complexoptr=1]<2>[/complexoptr]')
        assert ins.render('test1') == expected
