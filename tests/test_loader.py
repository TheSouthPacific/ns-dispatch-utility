from nsdu import loader
from nsdu import info


info.LOADER_DIR_PATH = 'tests/resources'


DISPATCH_LOADER_NAME = 'dispatchloader-test1'
DISPATCH_LOADER_CONFIG = {'dispatchloader-test1': {'key1': 'val1'}}


class TestDispatchLoader():
    def test_get_dispatch_config(self):
        obj = loader.DispatchLoader(DISPATCH_LOADER_NAME,
                                    DISPATCH_LOADER_CONFIG)
        obj.load_loader()
        r = obj.get_dispatch_config()
        obj.cleanup_loader()

        assert r == {'foo1': 'bar1', 'foo2': 'bar2'}

    def test_get_dispatch_text(self):
        obj = loader.DispatchLoader(DISPATCH_LOADER_NAME,
                                    DISPATCH_LOADER_CONFIG)
        obj.load_loader()
        r = obj.get_dispatch_text('test')
        obj.cleanup_loader()

        assert r == 'Dispatch content of test'

    def test_add_dispatch_id(self):
        obj = loader.DispatchLoader(DISPATCH_LOADER_NAME,
                                    DISPATCH_LOADER_CONFIG)
        obj.load_loader()
        r = obj.add_dispatch_id('test', '123456')
        obj.cleanup_loader()

        assert r


VAR_LOADER_NAMES = ['varloader-test1', 'varloader-test2']
VAR_LOADER_CONFIG = {'varloader-test1': {'key1': 'val1'},
                     'varloader-test2': {'key2': 'val2'}}


class TestVarLoader():
    def test_get_all_vars(self):
        obj = loader.VarLoader(VAR_LOADER_NAMES, VAR_LOADER_CONFIG)
        obj.load_loader()
        r = obj.get_all_vars()

        assert r == {'key1': {'key1': 'val1'}, 'key2': {'key2': 'val2'}}


CRED_LOADER_NAME = 'credloader-test1'
CRED_LOADER_CONFIG = {'credloader-test1': {'key1': 'val1'}}


class TestCredLoader():
    def test_get_all_creds(self):
        obj = loader.CredLoader(CRED_LOADER_NAME, CRED_LOADER_CONFIG)
        obj.load_loader()
        r = obj.get_creds()
        obj.cleanup_loader()

        assert r == {'nation1': '123456'}

    def test_add_cred(self):
        obj = loader.CredLoader(CRED_LOADER_NAME, CRED_LOADER_CONFIG)
        obj.load_loader()
        r = obj.add_cred('nation1', '123456')
        obj.cleanup_loader()

        assert r

    def test_remove_cred(self):
        obj = loader.CredLoader(CRED_LOADER_NAME, CRED_LOADER_CONFIG)
        obj.load_loader()
        r = obj.remove_cred('nation1')
        obj.cleanup_loader()

        assert r