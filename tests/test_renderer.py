from pathlib import Path
from unittest.mock import Mock

import pytest

from nsdu import config, exceptions, renderer


class TestDispatchTemplateLoader:
    def test_with_template_exists_returns_template_text(self):
        template_load_func = Mock(return_value="r")
        obj = renderer.JinjaTemplateLoader(template_load_func)

        r = obj.get_source(Mock(), "t")
        assert r[0] == "r"

    def test_with_template_not_exist_raises_exception(self):
        template_load_func = Mock(side_effect=exceptions.DispatchTemplateNotFound)
        obj = renderer.JinjaTemplateLoader(template_load_func)

        with pytest.raises(exceptions.DispatchTemplateNotFound):
            obj.get_source(Mock(), "")


class TestTemplateRenderer:
    def test_render_existing_template_returns_rendered_text(self):
        template = "{{ i }}"
        template_load_func = Mock(return_value=template)
        obj = renderer.TemplateRenderer(template_load_func)

        r = obj.render("t", {"i": "1"})

        assert r == "1"

    def test_render_non_existent_template_raises_exception(self):
        template_load_func = Mock(side_effect=exceptions.DispatchTemplateNotFound)
        obj = renderer.TemplateRenderer(template_load_func)

        with pytest.raises(exceptions.DispatchTemplateNotFound):
            obj.render("t", {})

    def test_load_filters_loads_the_filters(self):
        template = "{{ i|foo_filter }}"
        template_load_func = Mock(return_value=template)
        obj = renderer.TemplateRenderer(template_load_func)

        def foo_filter(a):
            return "f-{}".format(a)

        obj.load_filters({"foo_filter": foo_filter})
        result = obj.render("t", {"i": "1"})

        assert result == "f-1"


class TestLoadFiltersFromSource:
    def test_with_files_exist_loads_filters(self):
        template = "{{ i|filterA }}"
        template_load_func = Mock(return_value=template)
        obj = renderer.TemplateRenderer(template_load_func)

        renderer.load_filters_from_source(obj, ["tests/resources/filters-1.py"])
        result = obj.render("t", {"i": 1})

        assert result == "fA-1"

    def test_with_empty_list_does_not_load(self):
        template = "a"
        template_load_func = Mock(return_value=template)
        obj = renderer.TemplateRenderer(template_load_func)

        renderer.load_filters_from_source(obj, [])
        result = obj.render("t", {})

        assert result == "a"

    def test_with_non_existent_files_raises_exception(self):
        obj = renderer.TemplateRenderer(Mock())

        with pytest.raises(config.ConfigError):
            renderer.load_filters_from_source(obj, [""])


class TestDispatchRenderer:
    def test_render_with_many_filters_and_formatters_returns_formatted_texts(self):
        template = (
            "{% for i in j %}"
            "[s]{{ i|filterA }}[/s]"
            "[c2]{{ i|filterC }}[/c2]"
            "{% endfor %}"
        )
        template_load_func = Mock(return_value=template)
        simple_formatter_config = {"s": {"format_string": "[sr]%(value)s[/sr]"}}
        complex_formatter_source_path = Path(
            "tests/resources/bbc_complex_formatters.py"
        )
        template_filter_paths = [
            "tests/resources/filters-1.py",
            "tests/resources/filters-2.py",
        ]
        template_vars = {"j": [1, 2], "foo": "bar"}
        obj = renderer.DispatchRenderer(
            template_load_func,
            simple_formatter_config,
            complex_formatter_source_path,
            template_filter_paths,
            template_vars,
        )

        expected = (
            "[sr]fA-1[/sr][cr2]ctx=bar fC-1[/cr2][sr]fA-2[/sr][cr2]ctx=bar fC-2[/cr2]"
        )
        assert obj.render("t") == expected
