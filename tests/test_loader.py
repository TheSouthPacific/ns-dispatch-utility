import pathlib
import importlib
from unittest import mock
from importlib.metadata import EntryPoint

import pytest

from nsdu import exceptions
from nsdu import loader


CUSTOM_LOADER_DIR_PATH = pathlib.Path('tests/resources')
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


class MockSingleLoaderManager():
    """Mock of a single loader manager.
    """

    def load_loader(self, module):
        """Load source from module.
        Store module in an attribute to check its file path later.

        Args:
            module (Python module): Module
        """

        self.module = module


class TestSingleLoaderManagerBuilder():
    @pytest.fixture
    def entry_points(self):
        entry_points = [mock.Mock(load=mock.Mock(return_value=mock.Mock()))]
        entry_points[0].name = 'simplebbloader-test1'

        yield entry_points

    def test_load_loader_from_default_source_dir(self, entry_points):
        manager = MockSingleLoaderManager()
        builder = loader.SingleLoaderManagerBuilder(DEFAULT_LOADER_DIR_PATH, CUSTOM_LOADER_DIR_PATH, entry_points)
        builder.set_loader_manager(manager)

        builder.load_from_default_dir('simplebbloader-test2')

        assert manager.module

    def test_load_non_existent_loader_from_default_dir_raises_exception(self, entry_points):
        builder = loader.SingleLoaderManagerBuilder(DEFAULT_LOADER_DIR_PATH, CUSTOM_LOADER_DIR_PATH, entry_points)
        builder.set_loader_manager(MockSingleLoaderManager())

        with pytest.raises(exceptions.LoaderNotFound):
            builder.load_from_default_dir('zoo')

    def test_load_loader_with_no_default_source_dir_raises_exception(self, entry_points):
        builder = loader.SingleLoaderManagerBuilder(None, CUSTOM_LOADER_DIR_PATH, entry_points)
        builder.set_loader_manager(MockSingleLoaderManager())

        with pytest.raises(ValueError):
            builder.load_from_default_dir('simplebbloader-test1')

    def test_load_loader_from_custom_source_dir(self, entry_points):
        manager = MockSingleLoaderManager()
        builder = loader.SingleLoaderManagerBuilder(DEFAULT_LOADER_DIR_PATH, CUSTOM_LOADER_DIR_PATH, entry_points)
        builder.set_loader_manager(manager)

        builder.load_from_custom_dir('simplebbloader-test1')

        assert manager.module

    def test_load_non_existent_loader_from_custom_dir_raises_exception(self, entry_points):
        builder = loader.SingleLoaderManagerBuilder(DEFAULT_LOADER_DIR_PATH, CUSTOM_LOADER_DIR_PATH, entry_points)
        builder.set_loader_manager(MockSingleLoaderManager())

        with pytest.raises(exceptions.LoaderNotFound):
            builder.load_from_custom_dir('zoo')

    
    def test_load_loader_with_no_custom_source_dir_raises_exception(self, entry_points):
        builder = loader.SingleLoaderManagerBuilder(DEFAULT_LOADER_DIR_PATH, None, entry_points)
        builder.set_loader_manager(MockSingleLoaderManager())

        with pytest.raises(ValueError):
            builder.load_from_custom_dir('simplebbloader-test1')

    def test_load_loader_from_entry_points(self, entry_points):
        manager = MockSingleLoaderManager()
        builder = loader.SingleLoaderManagerBuilder(DEFAULT_LOADER_DIR_PATH, CUSTOM_LOADER_DIR_PATH, entry_points)
        builder.set_loader_manager(manager)

        builder.load_from_entry_points('simplebbloader-test1')

        assert manager.module
    
    def test_load_non_existent_loader_from_entry_points_raises_exception(self, entry_points):
        builder = loader.SingleLoaderManagerBuilder(DEFAULT_LOADER_DIR_PATH, CUSTOM_LOADER_DIR_PATH, entry_points)
        builder.set_loader_manager(MockSingleLoaderManager())

        with pytest.raises(exceptions.LoaderNotFound):
            builder.load_from_entry_points('zoo')


class MockMultiLoadersManager():
    """Mock of a multi-loaders manager.
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


class TestMultiLoadersManagerBuilder():
    @pytest.fixture
    def entry_points(self):
        entry_point = mock.create_autospec(EntryPoint)
        entry_point.name = 'templatevarloader-test1'

        yield [entry_point]

    def test_load_loader_from_default_source_dir(self, entry_points):
        manager = MockMultiLoadersManager()
        builder = loader.MultiLoadersManagerBuilder(DEFAULT_LOADER_DIR_PATH, CUSTOM_LOADER_DIR_PATH, entry_points)
        builder.set_loader_manager(manager)

        builder.load_from_default_dir(['templatevarloader-test1'])

        assert manager.modules[0]

    def test_load_non_existent_loaders_from_default_source_dir_returns_non_existent_loader_names(self, entry_points):
        manager = MockMultiLoadersManager()
        builder = loader.MultiLoadersManagerBuilder(DEFAULT_LOADER_DIR_PATH, CUSTOM_LOADER_DIR_PATH, entry_points)
        builder.set_loader_manager(manager)

        non_existent_loader_names = builder.load_from_default_dir(['foo'])

        assert non_existent_loader_names == ['foo']

    def test_load_loader_from_custom_source_dir(self, entry_points):
        manager = MockMultiLoadersManager()
        builder = loader.MultiLoadersManagerBuilder(DEFAULT_LOADER_DIR_PATH, CUSTOM_LOADER_DIR_PATH, entry_points)
        builder.set_loader_manager(manager)

        builder.load_from_custom_dir(['templatevarloader-test1'])

        assert manager.modules[0]

    def test_load_non_existent_loaders_from_custom_source_dir_returns_non_existent_loader_names(self, entry_points):
        manager = MockMultiLoadersManager()
        builder = loader.MultiLoadersManagerBuilder(DEFAULT_LOADER_DIR_PATH, CUSTOM_LOADER_DIR_PATH, entry_points)
        builder.set_loader_manager(manager)

        non_existent_loader_names = builder.load_from_custom_dir(['foo'])

        assert non_existent_loader_names == ['foo']

    def test_load_loader_from_entry_points(self, entry_points):
        manager = MockMultiLoadersManager()
        builder = loader.MultiLoadersManagerBuilder(DEFAULT_LOADER_DIR_PATH, CUSTOM_LOADER_DIR_PATH, entry_points)
        builder.set_loader_manager(manager)

        builder.load_from_entry_points(['templatevarloader-test1'])

        assert manager.modules[0]

    def test_load_non_existent_loaders_from_entry_points_returns_non_existent_loader_names(self, entry_points):
        manager = MockMultiLoadersManager()
        builder = loader.MultiLoadersManagerBuilder(DEFAULT_LOADER_DIR_PATH, CUSTOM_LOADER_DIR_PATH, entry_points)
        builder.set_loader_manager(manager)

        non_existent_loader_names = builder.load_from_entry_points(['foo'])

        assert non_existent_loader_names == ['foo']


DISPATCH_LOADER_NAME = 'dispatchloader-test1.py'
DISPATCH_LOADER_CONFIG = {'dispatchloader-test1': {'key1': 'val1'}}


class TestDispatchLoaderManager():
    def test_get_dispatch_config(self):
        manager = loader.DispatchLoaderManager(DISPATCH_LOADER_CONFIG)
        manager.load_loader(load_module(CUSTOM_LOADER_DIR_PATH / DISPATCH_LOADER_NAME))

        r = manager.get_dispatch_config()
        manager.cleanup_loader()

        assert r == {'foo1': 'bar1', 'foo2': 'bar2'}

    def test_get_dispatch_template(self):
        manager = loader.DispatchLoaderManager(DISPATCH_LOADER_CONFIG)
        manager.load_loader(load_module(CUSTOM_LOADER_DIR_PATH / DISPATCH_LOADER_NAME))

        r = manager.get_dispatch_template('test')
        manager.cleanup_loader()

        assert r == 'Dispatch content of test'

    def test_after_update(self):
        manager = loader.DispatchLoaderManager(DISPATCH_LOADER_CONFIG)
        manager.load_loader(load_module(CUSTOM_LOADER_DIR_PATH / DISPATCH_LOADER_NAME))

        result_time = mock.Mock()
        manager.after_update('test', 'edit', 'success', result_time)
        manager.cleanup_loader()

        assert manager._loader.result == {'name': 'test', 'action': 'edit',
                                          'result': 'success', 'result_time': result_time}

    def test_add_dispatch_id(self):
        manager = loader.DispatchLoaderManager(DISPATCH_LOADER_CONFIG)
        manager.load_loader(load_module(CUSTOM_LOADER_DIR_PATH / DISPATCH_LOADER_NAME))

        manager.add_dispatch_id('test', '123456')
        manager.cleanup_loader()

        assert manager._loader.dispatch_id == {'test': '123456'}


VAR_LOADER_NAMES = ['templatevarloader-test1.py', 'templatevarloader-test2.py']
VAR_LOADER_CONFIG = {'templatevarloader-test1': {'key1': 'val1'},
                     'templatevarloader-test2': {'key2': 'val2'}}


class TestTemplateVarLoaderManager():
    def test_get_all_template_vars(self):
        manager = loader.TemplateVarLoaderManager(VAR_LOADER_CONFIG)
        for name in VAR_LOADER_NAMES:
            manager.load_loader(load_module(CUSTOM_LOADER_DIR_PATH / name))

        r = manager.get_all_template_vars()

        assert r == {'key1': {'key1': 'val1'}, 'key2': {'key2': 'val2'}}


SIMPLE_BB_LOADER_NAME = 'simplebbloader-test1.py'
SIMPLE_BB_LOADER_CONFIG = {'simplebbloader-test1': {'key1': 'val1'}}


class TestSimpleBBLoaderManager():
    def test_get_simple_bb_config(self):
        manager = loader.SimpleBBLoaderManager(SIMPLE_BB_LOADER_CONFIG)
        manager.load_loader(load_module(CUSTOM_LOADER_DIR_PATH / SIMPLE_BB_LOADER_NAME))

        r = manager.get_simple_bb_config()

        assert r == {'key1': {'key1': 'val1'}}


CRED_LOADER_NAME = 'credloader-test1.py'
CRED_LOADER_CONFIG = {'credloader-test1': {'key1': 'val1'}}


class TestCredLoaderManager():
    def test_get_all_creds(self):
        manager = loader.CredLoaderManager(CRED_LOADER_CONFIG)
        manager.load_loader(load_module(CUSTOM_LOADER_DIR_PATH / CRED_LOADER_NAME))

        r = manager.get_creds()
        manager.cleanup_loader()

        assert r == {}

    def test_add_cred(self):
        manager = loader.CredLoaderManager(CRED_LOADER_CONFIG)
        manager.load_loader(load_module(CUSTOM_LOADER_DIR_PATH / CRED_LOADER_NAME))
        manager.add_cred('Nation1', '123456')
        manager.cleanup_loader()

        assert manager.get_creds() == {'nation1': '123456'}

    def test_remove_cred(self):
        manager = loader.CredLoaderManager(CRED_LOADER_CONFIG)
        manager.load_loader(load_module(CUSTOM_LOADER_DIR_PATH / CRED_LOADER_NAME))
        manager.add_cred('Nation1', '123456')

        manager.remove_cred('nation1')
        manager.cleanup_loader()

        assert manager.get_creds() == {}