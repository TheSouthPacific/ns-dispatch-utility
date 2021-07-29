import os
import shutil
import json
import toml
import logging
import pathlib
from unittest import mock

import pytest

from nsdu import info
from nsdu import exceptions
from nsdu import utils


class TestCredManager():
    def test_load_creds(self):
        mock_creds = {'nation1': '123456', 'nation2': '567890'}
        mock_cred_loader = mock.Mock(get_creds=mock.Mock(return_value=mock_creds))
        creds = utils.CredManager(mock_cred_loader, mock.Mock())

        creds.load_creds()

        assert creds['nation1'] == '123456'

    def test_add_cred(self):
        mock_cred_loader = mock.Mock(add_cred=mock.Mock())
        mock_dispatch_api = mock.Mock(login=mock.Mock(return_value='123456'))
        creds = utils.CredManager(mock_cred_loader, mock_dispatch_api)

        creds['nation1'] = 'hunterprime1'
        creds['nation2'] = 'hunterprime2'
        creds.save()

        mock_cred_loader.add_cred.assert_has_calls([mock.call('nation1', '123456'), 
                                                    mock.call('nation2', '123456')])
        mock_dispatch_api.login.assert_has_calls([mock.call('nation1', password='hunterprime1'), 
                                                  mock.call('nation2', password='hunterprime2')])

    def test_remove_cred(self):
        mock_cred_loader = mock.Mock(remove_cred=mock.Mock())
        creds = utils.CredManager(mock_cred_loader, mock.Mock())

        del creds['nation1']
        del creds['nation2']
        creds.save()

        mock_cred_loader.remove_cred.assert_has_calls([mock.call('nation1'), 
                                                       mock.call('nation2')])


class TestGetDispatchInfo():
    def test_get_dispatch_info(self):
        dispatch_config = {'nation1': {'dispatch1': {'title': 'Test Title 1',
                                                     'ns_id': '1234567',
                                                     'category': '1',
                                                     'subcategory': '100'},
                                      'dispatch2': {'title': 'Test Title 2',
                                                     'ns_id': '7654321',
                                                     'category': '2',
                                                     'subcategory': '120'}},
                           'nation2': {'dispatch3': {'title': 'Test Title 1',
                                                    'ns_id': '1234567',
                                                    'category': '1',
                                                    'subcategory': '100'}}}

        r = utils.get_dispatch_info(dispatch_config)
        assert r == {'dispatch1': {'title': 'Test Title 1',
                                   'ns_id': '1234567',
                                   'category': '1',
                                   'subcategory': '100',
                                   'owner_nation': 'nation1'},
                    'dispatch2': {'title': 'Test Title 2',
                                   'ns_id': '7654321',
                                   'category': '2',
                                   'subcategory': '120',
                                   'owner_nation': 'nation1'},
                    'dispatch3': {'title': 'Test Title 1',
                                   'ns_id': '1234567',
                                   'category': '1',
                                   'subcategory': '100',
                                   'owner_nation': 'nation2'}}


class TestGetConfigFromEnv():
    def test_with_env(self, toml_files):
        config_path = toml_files({'test_config.toml': {'testkey': 'testval'}})

        r = utils.get_config_from_env(config_path)

        assert r == {'testkey': 'testval'}

    def test_with_env_and_non_existing_config_file(self):
        with pytest.raises(exceptions.ConfigError):
            utils.get_config_from_env(pathlib.Path('abcd.toml'))


class TestGetConfigFromDefault():
    def test_with_existing_config_file(self, toml_files):
        config_path = toml_files({info.CONFIG_NAME: {'testkey': 'testval'}})

        r = utils.get_config_from_default(config_path.parent, info.DEFAULT_CONFIG_PATH, info.CONFIG_NAME)

        assert r == {'testkey': 'testval'}

    def test_with_non_existing_config_file(self, tmp_path):
        with pytest.raises(exceptions.ConfigError):
            utils.get_config_from_default(tmp_path, info.DEFAULT_CONFIG_PATH, info.CONFIG_NAME)

        config_path = tmp_path / info.CONFIG_NAME
        assert config_path.exists()
