import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock
from importlib.metadata import EntryPoint
from importlib import util as import_util

import pytest

from nsdu import loader_managers
from nsdu.loader_api import DispatchMetadata, DispatchOperation


TEST_LOADER_DIR_PATH = Path("tests/resources")


def load_module(path: Path | str) -> ModuleType:
    """Load Python module at the provided path.

    Args:
        path (Path | str): Path to the module file

    Raises:
        ModuleNotFoundError: Could not find the module file

    Returns:
        ModuleType: Loaded module
    """

    path = Path(path)
    module_name = path.name

    spec = import_util.spec_from_file_location(module_name, path.expanduser())

    if spec is None or spec.loader is None:
        raise ModuleNotFoundError

    module = import_util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    return module


def create_mock_entry_point(name: str) -> tuple[EntryPoint, object]:
    module = Mock(__name__=f"{name}.py")
    entry_point = Mock(load=Mock(return_value=module))
    entry_point.name = name
    return entry_point, module


class TestLoadAllModulesFromEntryPoint:
    def test_with_existing_names_returns_modules(self):
        entry_point_1, module_1 = create_mock_entry_point("m1")
        entry_point_2, module_2 = create_mock_entry_point("m2")
        entry_points = [entry_point_1, entry_point_2]

        result = loader_managers.load_modules_from_entry_points(
            entry_points, ["m1", "m2"]
        )

        assert result["m1"] == module_1 and result["m2"] == module_2

    def test_with_non_existent_names_skips_them(self):
        entry_point_1, module_1 = create_mock_entry_point("m1")
        entry_points = [entry_point_1]

        result = loader_managers.load_modules_from_entry_points(
            entry_points, ["m1", "m2"]
        )

        assert result["m1"] == module_1


@pytest.mark.parametrize(
    "names,expected",
    [
        [
            ["cred_loader", "dispatch_loader"],
            ["cred_loader", "dispatch_loader"],
        ],
        [
            ["cred_loader", "a"],
            ["cred_loader"],
        ],
        [
            [],
            [],
        ],
    ],
)
def test_load_modules_from_dir_returns_modules(names, expected):
    dir_path = Path("tests/resources")
    result = loader_managers.load_modules_from_dir(dir_path, names)

    assert list(result.keys()) == expected


class TestLoadCustomLoadersIntoManager:
    @pytest.mark.parametrize(
        "names,entry_points,custom_dir,expected",
        [
            [
                ["cred_loader", "m1"],
                [create_mock_entry_point("m1")[0], create_mock_entry_point("m2")[0]],
                Path("tests/resources"),
                ["m1.py", "cred_loader.py"],
            ],
            [
                ["cred_loader"],
                [create_mock_entry_point("cred_loader")[0]],
                Path("tests/resources"),
                ["cred_loader.py"],
            ],
            [
                ["a"],
                [create_mock_entry_point("a")[0]],
                None,
                ["a.py"],
            ],
            [
                ["cred_loader"],
                [],
                Path("tests/resources"),
                ["cred_loader.py"],
            ],
            [[], [], [], []],
        ],
    )
    def test_with_existing_names_returns_loaded_manager(
        self, names, entry_points, custom_dir, expected
    ):
        result = loader_managers.load_user_loaders(names, entry_points, custom_dir)

        assert list(map(lambda i: i.__name__, result)) == expected

    def test_with_non_existent_names_raises_exception(self):
        with pytest.raises(loader_managers.LoaderLoadError):
            loader_managers.load_user_loaders(["a"], [], None)


class TestDispatchLoaderManager:
    loader_config = {"dispatch_loader": {"c": "v"}}

    @pytest.fixture(scope="class")
    def loader_module(self):
        return load_module(TEST_LOADER_DIR_PATH / "dispatch_loader.py")

    def test_get_config_returns_config(self, loader_module):
        manager = loader_managers.DispatchLoaderManager(self.loader_config)
        manager.load_loader(loader_module)

        manager.init_loader()
        result = manager.loader.loader_config
        manager.cleanup_loader()

        assert result == {"c": "v"}

    def test_get_dispatch_metadata(self, loader_module):
        manager = loader_managers.DispatchLoaderManager(self.loader_config)
        manager.load_loader(loader_module)

        manager.init_loader()
        result = manager.get_dispatch_metadata()
        manager.cleanup_loader()

        assert result == {
            "n": DispatchMetadata(
                None, DispatchOperation.CREATE, "nat", "t", "cat", "sub"
            )
        }

    def test_get_dispatch_template(self, loader_module):
        manager = loader_managers.DispatchLoaderManager(self.loader_config)
        manager.load_loader(loader_module)

        manager.init_loader()
        result = manager.get_dispatch_template("n")
        manager.cleanup_loader()

        assert result == "n"

    def test_after_update(self, loader_module):
        manager = loader_managers.DispatchLoaderManager(self.loader_config)
        result_time = Mock()
        manager.load_loader(loader_module)

        manager.init_loader()
        manager.after_update("n", DispatchOperation.EDIT, "r", result_time)
        manager.cleanup_loader()

        assert manager.loader.result == {
            "name": "n",
            "op": DispatchOperation.EDIT,
            "result": "r",
            "result_time": result_time,
        }

    def test_add_dispatch_id(self, loader_module):
        manager = loader_managers.DispatchLoaderManager(self.loader_config)
        manager.load_loader(loader_module)

        manager.init_loader()
        manager.add_dispatch_id("n", "1")
        manager.cleanup_loader()

        assert manager.loader.dispatch_ids == {"n": "1"}


class TestTemplateVarLoaderManager:
    @pytest.fixture(scope="class")
    def loader_modules(self):
        return [
            load_module(TEST_LOADER_DIR_PATH / "template_var_loader_1.py"),
            load_module(TEST_LOADER_DIR_PATH / "template_var_loader_2.py"),
        ]

    @pytest.mark.parametrize(
        "loaders_config,expected",
        [
            [
                {
                    "template_var_loader_1": {"c1": "v1"},
                    "template_var_loader_2": {"c2": "v2"},
                },
                {"c1": "v1", "c2": "v2"},
            ],
            [
                {
                    "template_var_loader_1": {"c1": "v1"},
                    "template_var_loader_2": {"c1": "v2"},
                },
                {"c1": "v2"},
            ],
        ],
    )
    def test_get_all_template_vars_returns_template_vars(
        self, loader_modules, loaders_config, expected
    ):
        manager = loader_managers.TemplateVarLoaderManager(loaders_config)
        manager.load_loaders(loader_modules)

        result = manager.get_all_template_vars()

        assert result == expected


class TestSimpleBBCLoaderManager:
    def test_get_simple_bbc_config_returns_simple_bbc_config(self):
        loaders_config = {"simple_bbc_loader": {"c": "v"}}
        loader_module = load_module(TEST_LOADER_DIR_PATH / "simple_bbc_loader.py")
        manager = loader_managers.SimpleBbcLoaderManager(loaders_config)
        manager.load_loader(loader_module)

        result = manager.get_simple_bbc_config()

        assert result == {"c": "v"}


class TestCredLoaderManager:
    loaders_config = {"cred_loader": {"nat": "c"}}

    @pytest.fixture(scope="class")
    def loader_module(self):
        return load_module(TEST_LOADER_DIR_PATH / "cred_loader.py")

    def test_get_cred_returns_cred(self, loader_module):
        manager = loader_managers.CredLoaderManager(self.loaders_config)
        manager.load_loader(loader_module)

        manager.init_loader()
        result = manager.get_cred("nat")
        manager.cleanup_loader()

        assert result == "c"

    def test_add_cred_adds_cred(self, loader_module):
        manager = loader_managers.CredLoaderManager(self.loaders_config)
        manager.load_loader(loader_module)

        manager.init_loader()
        manager.add_cred("nat1", "c1")
        result = manager.get_cred("nat1")
        manager.cleanup_loader()

        assert result == "c1"

    def test_remove_cred_removes_cred(self, loader_module):
        manager = loader_managers.CredLoaderManager(self.loaders_config)
        manager.load_loader(loader_module)
        manager.init_loader()

        manager.remove_cred("nat")

        with pytest.raises(KeyError):
            manager.get_cred("nat")
