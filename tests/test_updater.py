import os
import logging
import json
from unittest import mock

import pytest
import toml


from nsdu import exceptions
from nsdu import updater


class TestGetCategoryNumber():
    def test_get_category_number_with_all_alpha_params(self):
        cat_num, subcat_num = updater.get_category_number('factbook', 'overview')

        assert cat_num == '1' and subcat_num == '100'

    def test_get_category_number_with_no_alpha_param(self):
        cat_num, subcat_num = updater.get_category_number('1', '100')

        assert cat_num == '1' and subcat_num == '100'


class TestDispatchUpdater():
    def test_login_owner_nations(self):
        login = mock.Mock()
        dispatch_api = mock.Mock(login=login)
        creds = {'test_nation': '12345'}
        mock_obj = mock.Mock()
        ins = updater.DispatchUpdater(dispatch_api, creds, mock_obj, mock_obj)
        dispatch_config = {'test_name': {'title': 'test_title',
                                         'category': '1',
                                         'subcategory': '100',
                                         'ns_id': '12345',
                                         'action': 'remove'}}

        ins.login_owner_nation('test_nation', dispatch_config)

        login.assert_called_with('test_nation', autologin='12345')
        assert ins.dispatch_config == dispatch_config

    def test_create_dispatch(self):
        create_dispatch = mock.Mock(return_value='12345')
        dispatch_api = mock.Mock(create_dispatch=create_dispatch)
        dispatch_loader = mock.Mock(add_dispatch_id=mock.Mock())
        mock_obj = mock.Mock()
        ins = updater.DispatchUpdater(dispatch_api, mock_obj, mock_obj, dispatch_loader)
        params = {'title': 'test_title',
                  'text': 'test_text',
                  'category': '1',
                  'subcategory': '100'}

        ins.create_dispatch('test_name', params)

        dispatch_loader.add_dispatch_id.assert_called_with('test_name', '12345')

    def test_create_or_edit_dispatch_with_create_action(self):
        mock_obj = mock.Mock()
        ins = updater.DispatchUpdater(mock_obj, mock_obj, mock_obj, mock_obj)
        ins.create_dispatch = mock.Mock()
        ins.get_dispatch_template = mock.Mock(return_value='test_text')
        this_dispatch_config = {'title': 'test_title',
                                'category': '1',
                                'subcategory': '100',
                                'ns_id': '12345'}

        ins.create_or_edit_dispatch('test_name', 'create', this_dispatch_config)

        ins.create_dispatch.assert_called_with('test_name',
                                               {'title': 'test_title',
                                                'text': 'test_text',
                                                'category': '1',
                                                'subcategory': '100'})

    def test_create_or_edit_dispatch_with_edit_action(self):
        mock_obj = mock.Mock()
        ins = updater.DispatchUpdater(mock_obj, mock_obj, mock_obj, mock_obj)
        ins.edit_dispatch = mock.Mock()
        ins.get_dispatch_template = mock.Mock(return_value='test_text')
        this_dispatch_config = {'title': 'test_title',
                                'category': '1',
                                'subcategory': '100',
                                'ns_id': '12345'}

        ins.create_or_edit_dispatch('test_name', 'edit', this_dispatch_config)

        ins.edit_dispatch.assert_called_with('12345',
                                             {'title': 'test_title',
                                              'text': 'test_text',
                                              'category': '1',
                                              'subcategory': '100'})

    def test_create_or_edit_dispatch_with_fail_to_get_text(self, caplog):
        mock_obj = mock.Mock()
        ins = updater.DispatchUpdater(mock_obj, mock_obj, mock_obj, mock_obj)
        ins.edit_dispatch = mock.Mock()
        ins.get_dispatch_template = mock.Mock(side_effect=exceptions.DispatchRenderingError)
        this_dispatch_config = {'title': 'test_title',
                                'category': '1',
                                'subcategory': '100',
                                'ns_id': '12345'}

        ins.create_or_edit_dispatch('test_name', 'edit', this_dispatch_config)

    def test_update_dispatch_with_remove_action(self):
        mock_obj = mock.Mock()
        ins = updater.DispatchUpdater(mock_obj, mock_obj, mock_obj, mock_obj)
        ins.dispatch_config = {'test_name': {'title': 'test_title',
                                             'category': '1',
                                             'subcategory': '100',
                                             'ns_id': '12345',
                                             'action': 'remove'}}
        ins.remove_dispatch = mock.Mock()

        ins.update_dispatch('test_name')

        ins.remove_dispatch.assert_called_with('12345')

    def test_update_dispatch_with_no_remove_action(self):
        mock_obj = mock.Mock()
        ins = updater.DispatchUpdater(mock_obj, mock_obj, mock_obj, mock_obj)
        ins.dispatch_config = {'test_name': {'title': 'test_title',
                                             'category': '1',
                                             'subcategory': '100',
                                             'ns_id': '12345',
                                             'action': 'create'}}
        ins.create_or_edit_dispatch = mock.Mock()

        ins.update_dispatch('test_name')

        ins.create_or_edit_dispatch.assert_called_with('test_name', 'create',
                                                       {'title': 'test_title',
                                                        'category': '1',
                                                        'subcategory': '100',
                                                        'ns_id': '12345'})
