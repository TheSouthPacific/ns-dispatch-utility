import pathlib
import importlib
from unittest import mock

import pytest

from nsdu import exceptions
from nsdu import loader
from nsdu import info


LOADER_DIR_PATH = pathlib.Path('tests/resources')
DEFAULT_LOADER_DIR_PATH = pathlib.Path('tests/resources/default')


def load_module(path):
    """Load module from a file.

    Args:
        path (pathlib.Path): Directory containing module file
        name (str): Name of module file
    """

    spec = importlib.util.spec_from_file_location(path.name, path.expanduser().with_suffix('.py'))
    if spec is not None:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    raise FileNotFoundError


class TestLoadModuleFromEntryPoint():
    def test_with_existing_name(self):
        module_1 = mock.Mock()
        module_2 = mock.Mock()
        entry_points = [mock.Mock(load=mock.Mock(return_value=module_1)),
                        mock.Mock(load=mock.Mock(return_value=module_2))]
        entry_points[0].name = 'foo'
        entry_points[1].name = 'bar'

        r = loader.load_module_from_entry_points(entry_points, 'foo')

        assert r == module_1

    def test_with_non_existing_name(self):
        module_1 = mock.Mock()
        module_2 = mock.Mock()
        entry_points = [mock.Mock(load=mock.Mock(return_value=module_1)),
                        mock.Mock(load=mock.Mock(return_value=module_2))]
        entry_points[0].name = 'foo'
        entry_points[1].name = 'bar'

        r = loader.load_module_from_entry_points(entry_points, 'zoo')

        assert r == None


class TestLoadAllModulesFromEntryPoint():
    def test_with_all_names_existing(self):
        module_1 = module_2 = module_3 = mock.Mock()
        entry_points = [mock.Mock(load=mock.Mock(return_value=module_1)),
                        mock.Mock(load=mock.Mock(return_value=module_2)),
                        mock.Mock(load=mock.Mock(return_value=module_3))]
        entry_points[0].name = 'foo'
        entry_points[1].name = 'bar'
        entry_points[2].name = 'eoo'

        r = loader.load_all_modules_from_entry_points(entry_points, ['foo', 'bar'])

        assert r == {'foo': module_1, 'bar': module_2}

    def test_with_some_non_existent_names(self):
        module_1 = mock.Mock()
        module_2 = mock.Mock()
        entry_points = [mock.Mock(load=mock.Mock(return_value=module_1)),
                        mock.Mock(load=mock.Mock(return_value=module_2))]
        entry_points[0].name = 'foo'
        entry_points[1].name = 'bar'

        r = loader.load_all_modules_from_entry_points(entry_points, ['foo', 'zoo'])

        assert r == {'foo': module_1}


def mock_load_module(path):
    """A mock of utils.load_module for testing.

    Args:
        path (pathlib.Path): Path to module's source file

    Returns:
        mock.Mock: Mock of a Python module object
    """

    if path == pathlib.Path('default_folder/foo.py'):
        return mock.Mock()
    return None


class MockSingleLoaderHandle():
    """Mock of a single loader handle.
    """

    def load_loader(self, module):
        """Load source from module.
        Store module in an attribute to check its file path later.

        Args:
            module (Python module): Module
        """

        self.module = module


class TestSingleLoaderHandleBuilder():
    @pytest.fixture
    def entry_points(self):
        module_1 = mock.Mock()
        module_1.__file__ = 'someplaces/simplebbloader-test1.py'
        module_2 = mock.Mock()
        module_2.__file__ = 'someplaces/someloader.py'
        entry_points = [mock.Mock(load=mock.Mock(return_value=module_1)),
                        mock.Mock(load=mock.Mock(return_value=module_2))]
        entry_points[0].name = 'simplebbloader-test1'
        entry_points[1].name = 'someloader'

        yield entry_points

    def test_load_loader_in_custom_source_dir(self, entry_points):
        handle = MockSingleLoaderHandle()
        builder = loader.SingleLoaderHandleBuilder(DEFAULT_LOADER_DIR_PATH, LOADER_DIR_PATH, entry_points)

        builder.load_loader(handle, 'simplebbloader-test1')
        assert handle.module.__file__ == str(LOADER_DIR_PATH / 'simplebbloader-test1.py')

    def test_load_loader_found_via_entry_points(self, entry_points):
        handle = MockSingleLoaderHandle()
        builder = loader.SingleLoaderHandleBuilder(DEFAULT_LOADER_DIR_PATH, LOADER_DIR_PATH, entry_points)

        builder.load_loader(handle, 'someloader')

        assert handle.module.__file__ == 'someplaces/someloader.py'

    def test_load_loader_in_default_source_dir(self, entry_points):
        handle = MockSingleLoaderHandle()
        builder = loader.SingleLoaderHandleBuilder(DEFAULT_LOADER_DIR_PATH, LOADER_DIR_PATH, entry_points)

        builder.load_loader(handle, 'simplebbloader-test2')

        assert handle.module.__file__ == str(DEFAULT_LOADER_DIR_PATH / 'simplebbloader-test2.py')

    def test_load_loader_with_no_custom_source_dir(self, entry_points):
        handle = MockSingleLoaderHandle()
        builder = loader.SingleLoaderHandleBuilder(DEFAULT_LOADER_DIR_PATH, None, entry_points)

        builder.load_loader(handle, 'simplebbloader-test1')
        assert handle.module.__file__ == 'someplaces/simplebbloader-test1.py'

    def test_load_loader_with_non_existent_loader(self, entry_points):
        handle = MockSingleLoaderHandle()
        builder = loader.SingleLoaderHandleBuilder(DEFAULT_LOADER_DIR_PATH, LOADER_DIR_PATH, entry_points)

        with pytest.raises(exceptions.LoaderNotFound):
            builder.load_loader(handle, 'zoo')


class MockMultiLoadersHandle():
    """Mock of a multi-loaders handle.
    """

    def __init__(self):
        self.modules = []

    def load_loader(self, module):
        """Load source from module.
        Store modules in an attribute to check their file path later.

        Args:
            module (Python module): Module
        """

        self.modules.append(module)


class TestMultiLoadersHandleBuilder():
    @pytest.fixture
    def entry_points(self):
        module_1 = mock.Mock()
        module_1.__file__ = 'someplaces/varloader-test2'
        module_2 = mock.Mock()
        module_2.__file__ = 'someplaces/varloader-test4'
        entry_points = [mock.Mock(load=mock.Mock(return_value=module_1)),
                        mock.Mock(load=mock.Mock(return_value=module_2))]
        entry_points[0].name = 'varloader-test2'
        entry_points[1].name = 'varloader-test4'

        yield entry_points

    def test_load_loader_in_everywhere(self, entry_points):
        handle = MockMultiLoadersHandle()
        builder = loader.MultiLoadersHandleBuilder(DEFAULT_LOADER_DIR_PATH, LOADER_DIR_PATH, entry_points)

        builder.load_loader(handle, ['varloader-test1', 'varloader-test2', 'varloader-test3', 'varloader-test4'])

        assert handle.modules[0].__file__ == str(LOADER_DIR_PATH / 'varloader-test1.py')
        assert handle.modules[1].__file__ == str(LOADER_DIR_PATH / 'varloader-test2.py')
        assert handle.modules[2].__file__ == str(DEFAULT_LOADER_DIR_PATH / 'varloader-test3.py')
        assert handle.modules[3].__file__ == 'someplaces/varloader-test4'

    def test_load_loader_with_no_custom_source_dir(self, entry_points):
        handle = MockMultiLoadersHandle()
        builder = loader.MultiLoadersHandleBuilder(DEFAULT_LOADER_DIR_PATH, None, entry_points)

        builder.load_loader(handle, ['varloader-test1', 'varloader-test2'])
        assert handle.modules[0].__file__ == str(DEFAULT_LOADER_DIR_PATH / 'varloader-test1.py')
        assert handle.modules[1].__file__ == 'someplaces/varloader-test2'

    def test_load_loader_with_a_non_existent_loader(self, entry_points):
        handle = MockMultiLoadersHandle()
        builder = loader.MultiLoadersHandleBuilder(DEFAULT_LOADER_DIR_PATH, LOADER_DIR_PATH, entry_points)

        with pytest.raises(exceptions.LoaderNotFound):
            builder.load_loader(handle, ['varloader-test1', 'varloader-test3', 'nonexistentloader'])


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