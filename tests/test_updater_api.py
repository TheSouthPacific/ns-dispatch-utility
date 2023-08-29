from unittest import mock


from nsdu import updater_api


class TestGetCategoryNumber:
    def test_all_alpha_inputs_returns_correct_numbers(self):
        cat_num, subcat_num = updater_api.get_category_number("factbook", "overview")

        assert cat_num == "1" and subcat_num == "100"

    def test_all_alpha_inputs_with_uppercase_letters_returns_correct_numbers(self):
        cat_num, subcat_num = updater_api.get_category_number("Factbook", "Overview")

        assert cat_num == "1" and subcat_num == "100"

    def test_no_alpha_inputs_returns_inputs(self):
        cat_num, subcat_num = updater_api.get_category_number("1", "100")

        assert cat_num == "1" and subcat_num == "100"


class TestDispatchUpdater:
    def test_login_owner_nation_calls_dispatch_api_with_autologin_code(self):
        updater = updater_api.DispatchUpdater(
            user_agent="foo",
            template_filter_paths=[],
            simple_fmts_config=None,
            complex_fmts_source_path=None,
            template_load_func=mock.Mock(),
            template_vars={},
        )
        dispatch_api = mock.Mock()
        updater.dispatch_api = dispatch_api

        updater.set_owner_nation("testopia", "123456")

        dispatch_api.set_owner_nation.assert_called_with("testopia", "123456")

    def test_create_dispatch_calls_dispatch_api(self):
        updater = updater_api.DispatchUpdater(
            user_agent="foo",
            template_filter_paths=[],
            simple_fmts_config=None,
            complex_fmts_source_path=None,
            template_load_func=mock.Mock(return_value="Test template"),
            template_vars={},
        )
        dispatch_api = mock.Mock(create_dispatch=mock.Mock(return_value="12345"))
        updater.dispatch_api = dispatch_api

        new_dispatch_id = updater.create_dispatch("foo", "Title", "meta", "gameplay")

        dispatch_api.create_dispatch.assert_called_with(
            title="Title", text="Test template", category="8", subcategory="835"
        )
        assert new_dispatch_id == "12345"

    def test_edit_dispatch_calls_dispatch_api(self):
        updater = updater_api.DispatchUpdater(
            user_agent="foo",
            template_filter_paths=[],
            simple_fmts_config=None,
            complex_fmts_source_path=None,
            template_load_func=mock.Mock(return_value="Test template"),
            template_vars={},
        )
        dispatch_api = mock.Mock()
        updater.dispatch_api = dispatch_api

        updater.edit_dispatch("foo", "12345", "Title", "meta", "gameplay")

        dispatch_api.edit_dispatch.assert_called_with(
            dispatch_id="12345",
            title="Title",
            text="Test template",
            category="8",
            subcategory="835",
        )

    def test_remove_dispatch_calls_dispatch_api(self):
        updater = updater_api.DispatchUpdater(
            user_agent="foo",
            template_filter_paths=[],
            simple_fmts_config=None,
            complex_fmts_source_path=None,
            template_load_func=mock.Mock(return_value="Test template"),
            template_vars={},
        )
        dispatch_api = mock.Mock()
        updater.dispatch_api = dispatch_api

        updater.remove_dispatch("12345")

        dispatch_api.remove_dispatch.assert_called_with("12345")
