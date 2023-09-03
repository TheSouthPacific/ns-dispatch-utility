from pathlib import Path
from unittest.mock import Mock

import pytest

from nsdu import config, exceptions, renderer


class TestDispatchTemplateLoader:
    def test_with_template_exists_returns_template_text(self):
        template_load_func = Mock(return_value="r")
        obj = renderer.JinjaTemplateLoader(template_load_func)

        result = obj.get_source(Mock(), "t")

        assert result[0] == "r"

    def test_with_template_not_exist_raises_exception(self):
        template_load_func = Mock(side_effect=exceptions.DispatchTemplateNotFound)
        obj = renderer.JinjaTemplateLoader(template_load_func)

        with pytest.raises(exceptions.DispatchTemplateNotFound):
            obj.get_source(Mock(), "")


class TestTemplateRenderer:
    @pytest.mark.parametrize("context,expected", [[{"i": "1"}, "1"], [{}, ""]])
    def test_render_existing_template_returns_rendered_text(self, context, expected):
        template = "{{ i }}"
        template_load_func = Mock(return_value=template)
        obj = renderer.TemplateRenderer(template_load_func)

        result = obj.render("t", context)

        assert result == expected

    def test_render_non_existent_template_raises_exception(self):
        template_load_func = Mock(side_effect=exceptions.DispatchTemplateNotFound)
        obj = renderer.TemplateRenderer(template_load_func)

        with pytest.raises(exceptions.DispatchTemplateNotFound):
            obj.render("t", {})

    def test_load_filters_then_render_uses_filters_when_rendering(self):
        template = "{{ i|foo }}"
        template_load_func = Mock(return_value=template)
        obj = renderer.TemplateRenderer(template_load_func)

        def foo(a):
            return "f-{}".format(a)

        obj.load_filters({"foo": foo})
        result = obj.render("t", {"i": "1"})

        assert result == "f-1"

    def test_render_with_non_existent_filters_raises_exception(self):
        template = "{{ i|foo }}"
        template_load_func = Mock(return_value=template)
        obj = renderer.TemplateRenderer(template_load_func)

        with pytest.raises(renderer.TemplateRenderError):
            obj.render("t", {"i": "1"})


class TestLoadFiltersFromSource:
    @pytest.mark.parametrize(
        "paths,template,expected",
        [
            [
                ["tests/resources/filters-1.py", "tests/resources/filters-2.py"],
                "{{ i|filterA }} {{ i|filterC }}",
                "fA-1 fC-1",
            ],
            [
                [],
                "{{ i }}",
                "1",
            ],
        ],
    )
    def test_with_files_exist_loads_filters(self, paths, template, expected):
        template_load_func = Mock(return_value=template)
        obj = renderer.TemplateRenderer(template_load_func)

        renderer.load_filters_from_source(obj, paths)
        result = obj.render("t", {"i": 1})

        assert result == expected

    def test_with_non_existent_files_raises_exception(self):
        obj = renderer.TemplateRenderer(Mock())

        with pytest.raises(config.ConfigError):
            renderer.load_filters_from_source(obj, [""])


class TestDispatchRenderer:
    @pytest.mark.parametrize(
        "template,simple_fmts_config,complex_fmts_path,filter_paths,expected",
        [
            [
                "[s]{{ i|filterA }}[/s][c1]{{ i|filterC }}[/c1]",
                {"s": {"format_string": "[sr]%(value)s[/sr]"}},
                Path("tests/resources/bbc_complex_formatters.py"),
                ["tests/resources/filters-1.py", "tests/resources/filters-2.py"],
                "[sr]fA-1[/sr][cr1]fC-1[/cr1]",
            ],
            [
                "[s]{{ i }}[/s][c1]{{ i }}[/c1]",
                {"s": {"format_string": "[sr]%(value)s[/sr]"}},
                Path("tests/resources/bbc_complex_formatters.py"),
                None,
                "[sr]1[/sr][cr1]1[/cr1]",
            ],
            [
                "{{ i|filterA }}{{ i|filterC }}",
                None,
                None,
                ["tests/resources/filters-1.py", "tests/resources/filters-2.py"],
                "fA-1fC-1",
            ],
            [
                "{{ i }}",
                None,
                None,
                None,
                "1",
            ],
        ],
    )
    def test_render_returns_rendered_text(
        self, template, simple_fmts_config, complex_fmts_path, filter_paths, expected
    ):
        template_load_func = Mock(return_value=template)
        template_vars = {"i": 1}
        obj = renderer.DispatchRenderer(
            template_load_func,
            simple_fmts_config,
            complex_fmts_path,
            filter_paths,
            template_vars,
        )

        result = obj.render("t")

        assert result == expected

    def test_render_with_bbc_uses_template_vars_as_bbc_format_context(self):
        template = "[c2]{{ i|filterA }}[/c2]"
        template_load_func = Mock(return_value=template)
        simple_formatter_config = None
        complex_formatter_source_path = Path(
            "tests/resources/bbc_complex_formatters.py"
        )
        template_filter_paths = ["tests/resources/filters-1.py"]
        template_vars = {"i": 1, "foo": "bar"}
        obj = renderer.DispatchRenderer(
            template_load_func,
            simple_formatter_config,
            complex_formatter_source_path,
            template_filter_paths,
            template_vars,
        )

        result = obj.render("t")

        assert result == "[cr2]ctx=bar fA-1[/cr2]"
