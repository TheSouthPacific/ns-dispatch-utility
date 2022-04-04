from unittest import mock

import nationstates
import pytest

from nsdu import dispatch_api
from nsdu import exceptions


class TestReraiseException():
    def test_unknown_dispatch(self):
        exception = nationstates.exceptions.APIUsageError('Unknown dispatch.')
        with pytest.raises(exceptions.UnknownDispatchError):
            dispatch_api.reraise_exception(exception)

    def test_not_owner_dispatch(self):
        exception = nationstates.exceptions.APIUsageError('You are not the author of this dispatch.')
        with pytest.raises(exceptions.NotOwnerDispatchError):
            dispatch_api.reraise_exception(exception)


class TestDispatchApi():
    def test_login_with_password_and_get_autologin(self):
        response = {'headers': {'X-Autologin': '123456'}}
        ns_api = mock.create_autospec(nationstates.Nationstates)
        ns_api.nation.return_value = mock.Mock(get_shards=mock.Mock(return_value=response))
        api = dispatch_api.DispatchApi('Maxtopia')
        api.api = ns_api

        autologin = api.login('my_nation', password='hunterprime123')

        assert autologin == '123456'

    def test_login_with_autologin(self):
        response = {'headers': {'XYZ': '123'}}
        ns_api = mock.create_autospec(nationstates.Nationstates)
        ns_api.nation.return_value = mock.Mock(get_shards=mock.Mock(return_value=response))
        api = dispatch_api.DispatchApi('Maxtopia')
        api.api = ns_api

        api.login('my_nation', autologin='123456')

        ns_api.nation.assert_called_with('my_nation', autologin='123456')

    def test_login_forbidden_exception(self):
        ns_api = mock.create_autospec(nationstates.Nationstates)
        ns_api.nation.return_value = mock.Mock(get_shards=mock.Mock(side_effect=nationstates.exceptions.Forbidden))
        api = dispatch_api.DispatchApi('Maxtopia')
        api.api = ns_api

        with pytest.raises(exceptions.DispatchApiError):
            api.login('my_nation', 'hunterprime123')

    def test_create_dispatch(self):
        resp = 'New factbook posted! <a href="/nation=test/detail=factbook/id=1234567">View Your Factbook</a>'
        api = dispatch_api.DispatchApi('Maxtopia')
        create_dispatch = mock.Mock(return_value={'success': resp})
        api.owner_nation = mock.Mock(create_dispatch=create_dispatch)

        r = api.create_dispatch(title='test', text='hello world —', category='1', subcategory='100')

        assert r == '1234567'
        create_dispatch.assert_called_with(title='test', text=b'hello world &#8212;',
                                           category='1', subcategory='100')

    def test_edit_dispatch(self):
        resp = 'New factbook edited! <a href="/nation=test/detail=factbook/id=1234567">View Your Factbook</a>'
        api = dispatch_api.DispatchApi('Maxtopia')
        edit_dispatch = mock.Mock(return_value={'success': resp})
        api.owner_nation = mock.Mock(edit_dispatch=edit_dispatch)

        api.edit_dispatch(dispatch_id='1234567', title='test',
                          text='hello world —', category='1', subcategory='100')

        edit_dispatch.assert_called_with(dispatch_id='1234567', title='test',
                                         text=b'hello world &#8212;', category='1', subcategory='100')

    def test_remove_dispatch(self):
        resp = 'Remove dispatch "test."'
        api = dispatch_api.DispatchApi('Maxtopia')
        api.owner_nation = mock.Mock(remove_dispatch=mock.Mock(return_value={'success': resp}))

        api.remove_dispatch(dispatch_id='1234567')

        assert True
