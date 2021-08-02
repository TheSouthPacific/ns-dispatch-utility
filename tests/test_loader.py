import pathlib
import importlib
import mock

import pytest

from nsdu import exceptions
from nsdu import loader
from nsdu import info


LOADER_DIR_PATH = pathlib.Path('tests/resources')


DISPATCH_LOADER_NAME = 'dispatchloader-test1.py'
DISPATCH_LOADER_CONFIG = {'dispatchloader-test1': {'key1': 'val1'}}


class TestDispatchLoaderHandle():
    def test_get_dispatch_config(self):
        handle = loader.DispatchLoaderHandle(DISPATCH_LOADER_CONFIG)
        handle.load_loader(load_module(LOADER_DIR_PATH / DISPATCH_LOADER_NAME))

        r = handle.get_dispatch_config()

        handle.cleanup_loader()

        assert r == {'foo1': 'bar1', 'foo2': 'bar2'}

    def test_get_dispatch_text(self):
        handle = loader.DispatchLoaderHandle(DISPATCH_LOADER_CONFIG)
        handle.load_loader(load_module(LOADER_DIR_PATH / DISPATCH_LOADER_NAME))

        r = handle.get_dispatch_text('test')

        handle.cleanup_loader()

        assert r == 'Dispatch content of test'

    def test_add_dispatch_id(self):
        handle = loader.DispatchLoaderHandle(DISPATCH_LOADER_CONFIG)
        handle.load_loader(load_module(LOADER_DIR_PATH / DISPATCH_LOADER_NAME))

        r = handle.add_dispatch_id('test', '123456')

        handle.cleanup_loader()

        assert r


VAR_LOADER_NAMES = ['varloader-test1.py', 'varloader-test2.py']
VAR_LOADER_CONFIG = {'varloader-test1': {'key1': 'val1'},
                     'varloader-test2': {'key2': 'val2'}}


class TestVarLoaderHandle():
    def test_get_all_vars(self):
        handle = loader.VarLoaderHandle(VAR_LOADER_CONFIG)
        for name in VAR_LOADER_NAMES:
            handle.load_loader(load_module(LOADER_DIR_PATH / name))

        r = handle.get_all_vars()

        assert r == {'key1': {'key1': 'val1'}, 'key2': {'key2': 'val2'}}


SIMPLE_BB_LOADER_NAME = 'simplebbloader-test1.py'
SIMPLE_BB_LOADER_CONFIG = {'simplebbloader-test1': {'key1': 'val1'}}


class TestSimpleBBLoaderHandle():
    def test_get_simple_bb_config(self):
        handle = loader.SimpleBBLoaderHandle(SIMPLE_BB_LOADER_CONFIG)
        handle.load_loader(load_module(LOADER_DIR_PATH / SIMPLE_BB_LOADER_NAME))

        r = handle.get_simple_bb_config()

        assert r == {'key1': {'key1': 'val1'}}


CRED_LOADER_NAME = 'credloader-test1.py'
CRED_LOADER_CONFIG = {'credloader-test1': {'key1': 'val1'}}


class TestCredLoaderHandle():
    def test_get_all_creds(self):
        handle = loader.CredLoaderHandle(CRED_LOADER_CONFIG)
        handle.load_loader(load_module(LOADER_DIR_PATH / CRED_LOADER_NAME))

        r = handle.get_creds()

        handle.cleanup_loader()

        assert r == {'nation1': '123456'}

    def test_add_cred(self):
        handle = loader.CredLoaderHandle(CRED_LOADER_CONFIG)
        handle.load_loader(load_module(LOADER_DIR_PATH / CRED_LOADER_NAME))

        r = handle.add_cred('nation1', '123456')

        handle.cleanup_loader()

        assert r

    def test_remove_cred(self):
        handle = loader.CredLoaderHandle(CRED_LOADER_CONFIG)
        handle.load_loader(load_module(LOADER_DIR_PATH / CRED_LOADER_NAME))

        r = handle.remove_cred('nation1')

        handle.cleanup_loader()

        assert r