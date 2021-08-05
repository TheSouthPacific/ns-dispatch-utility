from unittest import mock

import nationstates
import pytest

from nsdu import api_adapter
from nsdu import exceptions


class TestReraiseException():
    def test_unknown_dispatch(self):
        exception = nationstates.exceptions.APIUsageError('Unknown dispatch.')
        with pytest.raises(exceptions.UnknownDispatchError):
            api_adapter.reraise_exception(exception)

    def test_not_owner_dispatch(self):
        exception = nationstates.exceptions.APIUsageError('You are not the author of this dispatch.')
        with pytest.raises(exceptions.NotOwnerDispatchError):
            api_adapter.reraise_exception(exception)


class TestDispatchApi():
    def test_login_with_password_and_get_autologin(self):
        response = {'headers': {'X-Autologin': '123456'}}
        nation = mock.Mock(get_shards=mock.Mock(return_value=response))
        ns_api = mock.Mock(nation=mock.Mock(return_value=nation))
        dispatch_api = api_adapter.DispatchApi('Maxtopia')
        dispatch_api.api = ns_api

        autologin = dispatch_api.login('my_nation', password='hunterprime123')

        assert autologin == '123456'

    def test_login_with_autologin(self):
        response = {'headers': {'XYZ': '123'}}
        nation = mock.Mock(get_shards=mock.Mock(return_value=response))
        ns_api = mock.Mock(nation=mock.Mock(return_value=nation))
        dispatch_api = api_adapter.DispatchApi('Maxtopia')
        dispatch_api.api = ns_api

        dispatch_api.login('my_nation', autologin='123456')

        ns_api.nation.assert_called_with('my_nation', autologin='123456')

    def test_login_forbidden_exception(self):
        nation =  mock.Mock(get_shards=mock.Mock(side_effect=nationstates.exceptions.Forbidden))
        ns_api = mock.Mock(nation=mock.Mock(return_value=nation))
        dispatch_api = api_adapter.DispatchApi('Maxtopia')
        dispatch_api.api = ns_api

        with pytest.raises(exceptions.DispatchApiError):
            dispatch_api.login('my_nation', 'hunterprime123')

    def test_create_dispatch(self):
        resp = 'New factbook posted! <a href="/nation=test/detail=factbook/id=1234567">View Your Factbook</a>'
        dispatch_api = api_adapter.DispatchApi('Maxtopia')
        create_dispatch = mock.Mock(return_value={'success': resp})
        dispatch_api.owner_nation = mock.Mock(create_dispatch=create_dispatch)

        r = dispatch_api.create_dispatch(title='test', text='hello world —',
                                         category='1', subcategory='100')

        assert r == '1234567'
        create_dispatch.assert_called_with(title='test', text=b'hello world &#8212;',
                                           category='1', subcategory='100')

    def test_edit_dispatch(self):
        resp = 'New factbook edited! <a href="/nation=test/detail=factbook/id=1234567">View Your Factbook</a>'
        dispatch_api = api_adapter.DispatchApi('Maxtopia')
        edit_dispatch = mock.Mock(return_value={'success': resp})
        dispatch_api.owner_nation = mock.Mock(edit_dispatch=edit_dispatch)

        dispatch_api.edit_dispatch(dispatch_id='1234567', title='test',
                                   text='hello world —', category='1', subcategory='100')

        edit_dispatch.assert_called_with(dispatch_id='1234567', title='test',
                                         text=b'hello world &#8212;', category='1', subcategory='100')

    def test_remove_dispatch(self):
        resp = 'Remove dispatch "test."'
        dispatch_api = api_adapter.DispatchApi('Maxtopia')
        dispatch_api.owner_nation = mock.Mock(remove_dispatch=mock.Mock(return_value={'success': resp}))

        dispatch_api.remove_dispatch(dispatch_id='1234567')

        assert True


