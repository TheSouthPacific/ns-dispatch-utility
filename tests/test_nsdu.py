from unittest import mock

import pytest

from nsdu import exceptions
from nsdu import __main__


def get_dispatch_info(dispatch_config):
    """Return dispatch information for use as context in the template renderer.

    Args:
        dispatch_config (dict): Dispatch configuration.
        id_store (IDStore): Dispatch ID store.

    Returns:
        dict: Dispatch information.
    """

    dispatch_info = {}
    for nation, dispatches in dispatch_config.items():
        for name, config in dispatches.items():
            config['owner_nation'] = nation
            dispatch_info[name] = config

    return dispatch_info


class TestNsduCred():
    def test_add_nation_cred(self):
        mock_cred_loader = mock.Mock(add_cred=mock.Mock())
        mock_dispatch_api = mock.Mock(login=mock.Mock(return_value='123456'))
        app = __main__.NsduCred(mock_cred_loader, mock_dispatch_api)

        app.add_nation_cred('nation1', '123456')
        app.close()

        mock_cred_loader.add_cred.assert_called_with('nation1', '123456')

    def test_remove_nation_cred(self):
        mock_cred_loader = mock.Mock(remove_cred=mock.Mock())
        app = __main__.NsduCred(mock_cred_loader, mock.Mock())

        app.remove_nation_cred('nation1')
        app.close()

        mock_cred_loader.remove_cred.assert_called_with('nation1')


class TestNsduDispatch():
    def test_update_a_dispatch_with_create_action(self):
        dispatch_loader_manager = mock.Mock()
        dispatch_updater = mock.Mock(create_dispatch=mock.Mock(return_value='12345'))
        dispatch_info = {'foo': {'action': 'create',
                                 'title': 'Test title',
                                 'category': '1',
                                 'subcategory': '100'}}
        app = __main__.NsduDispatch(dispatch_updater, dispatch_loader_manager, {}, dispatch_info, {})

        app.update_a_dispatch('foo')

        dispatch_loader_manager.add_dispatch_id.assert_called_with('foo', '12345')

    def test_update_a_dispatch_with_edit_action(self):
        dispatch_loader_manager = mock.Mock()
        dispatch_updater = mock.Mock()
        dispatch_info = {'foo': {'action': 'edit',
                                 'ns_id': '12345',
                                 'title': 'Test title',
                                 'category': '1',
                                 'subcategory': '100'}}
        app = __main__.NsduDispatch(dispatch_updater, dispatch_loader_manager, {}, dispatch_info, {})

        app.update_a_dispatch('foo')

        dispatch_updater.edit_dispatch.assert_called_with('foo', '12345', 'Test title', '1', '100')

    def test_update_a_dispatch_with_remove_action(self):
        dispatch_loader_manager = mock.Mock()
        dispatch_updater = mock.Mock()
        dispatch_info = {'foo': {'action': 'remove',
                                 'ns_id': '12345',
                                 'title': 'Test title',
                                 'category': '1',
                                 'subcategory': '100'}}
        app = __main__.NsduDispatch(dispatch_updater, dispatch_loader_manager, {}, dispatch_info, {})

        app.update_a_dispatch('foo')

        dispatch_updater.remove_dispatch.assert_called_with('12345')

    def test_update_a_dispatch_with_invalid_action(self):
        dispatch_loader_manager = mock.Mock()
        dispatch_updater = mock.Mock()
        dispatch_info = {'foo': {'action': 'abcd',
                                 'ns_id': '12345',
                                 'title': 'Test title',
                                 'category': '1',
                                 'subcategory': '100'}}
        app = __main__.NsduDispatch(dispatch_updater, dispatch_loader_manager, {}, dispatch_info, {})

        with pytest.raises(exceptions.DispatchConfigError):
            app.update_a_dispatch('foo')

    @pytest.mark.parametrize("api_exceptions, result",
                             [(exceptions.UnknownDispatchError, 'unknown-dispatch-error'),
                              (exceptions.NotOwnerDispatchError, 'not-owner-dispatch-error'),
                              (exceptions.NonexistentCategoryError('',''), 'invalid-category-options')])
    def test_update_a_dispatch_with_api_exceptions(self, api_exceptions, result, caplog):
        dispatch_loader_manager = mock.Mock()
        dispatch_updater = mock.Mock(edit_dispatch=mock.Mock(side_effect=api_exceptions))
        dispatch_info = {'foo': {'action': 'edit',
                                 'ns_id': '12345',
                                 'title': 'Test title',
                                 'category': '1',
                                 'subcategory': '100'}}
        app = __main__.NsduDispatch(dispatch_updater, dispatch_loader_manager, {}, dispatch_info, {})

        app.update_a_dispatch('foo')

        assert caplog.records[-1].levelname == 'ERROR'
        dispatch_loader_manager.after_update.assert_called_with('foo', 'edit', result)

    def test_update_dispatches_with_all_dispatches_and_existent_dispatches(self):
        dispatch_loader_manager = mock.Mock()
        dispatch_updater = mock.Mock()
        dispatch_config = {'nation1' : {'foo': {'action': 'create',
                                                'ns_id': '12345',
                                                'title': 'Test title 1',
                                                'category': '1',
                                                'subcategory': '100'},
                                        'bar': {'action': 'edit',
                                                'ns_id': '54321',
                                                'title': 'Test title 2',
                                                'category': '1',
                                                'subcategory': '200'}},
                           'nation2': {'zoo': {'action': 'remove',
                                               'ns_id': '98765',
                                               'title': 'Test title 1',
                                               'category': '1',
                                               'subcategory': '100'}}}
        dispatch_info = get_dispatch_info(dispatch_config)
        creds = {'nation1': 'abcd1234', 'nation2': '4321bcda'}
        app = __main__.NsduDispatch(dispatch_updater, dispatch_loader_manager, dispatch_config, dispatch_info, creds)

        app.update_dispatches([])

        dispatch_updater.create_dispatch.assert_called()
        dispatch_updater.edit_dispatch.assert_called()
        dispatch_updater.remove_dispatch.assert_called()

    def test_update_dispatches_with_some_dispatches_and_existent_dispatches(self):
        dispatch_loader_manager = mock.Mock()
        dispatch_updater = mock.Mock()
        dispatch_config = {'nation1' : {'foo': {'action': 'create',
                                                'ns_id': '12345',
                                                'title': 'Test title 1',
                                                'category': '1',
                                                'subcategory': '100'},
                                        'bar': {'action': 'edit',
                                                'ns_id': '54321',
                                                'title': 'Test title 2',
                                                'category': '1',
                                                'subcategory': '200'}},
                           'nation2': {'zoo': {'action': 'remove',
                                               'ns_id': '98765',
                                               'title': 'Test title 1',
                                               'category': '1',
                                               'subcategory': '100'}}}
        dispatch_info = get_dispatch_info(dispatch_config)
        creds = {'nation1': 'abcd1234', 'nation2': '4321bcda'}
        app = __main__.NsduDispatch(dispatch_updater, dispatch_loader_manager, dispatch_config, dispatch_info, creds)

        app.update_dispatches(['foo', 'zoo'])

        dispatch_updater.create_dispatch.assert_called()
        dispatch_updater.edit_dispatch.assert_not_called()
        dispatch_updater.remove_dispatch.assert_called()

    def test_update_dispatches_with_all_non_existent_dispatches(self, caplog):
        dispatch_loader_manager = mock.Mock()
        dispatch_updater = mock.Mock()
        dispatch_config = {'nation1' : {'foo': {'action': 'create',
                                                'ns_id': '12345',
                                                'title': 'Test title 1',
                                                'category': '1',
                                                'subcategory': '100'},
                                        'bar': {'action': 'edit',
                                                'ns_id': '54321',
                                                'title': 'Test title 2',
                                                'category': '1',
                                                'subcategory': '200'}},
                           'nation2': {'zoo': {'action': 'remove',
                                               'ns_id': '98765',
                                               'title': 'Test title 1',
                                               'category': '1',
                                               'subcategory': '100'}}}
        dispatch_info = get_dispatch_info(dispatch_config)
        creds = {'nation1': 'abcd1234', 'nation2': '4321bcda'}
        app = __main__.NsduDispatch(dispatch_updater, dispatch_loader_manager, dispatch_config, dispatch_info, creds)

        app.update_dispatches(['voo', 'doo'])

        assert caplog.records[-1].levelname == 'ERROR'