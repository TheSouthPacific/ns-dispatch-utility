import os

import pytest
import toml

from nsdu.loaders import file_varloader


@pytest.fixture(scope='module')
def setup_vars_files():
    vars_1 = {'foo1': {'bar1': 'john1'}}
    with open('test1.toml', 'w') as f:
        toml.dump(vars_1, f)

    vars_2 = {'foo2': {'bar2': 'john2'}}
    with open('test2.toml', 'w') as f:
        toml.dump(vars_2, f)

    yield 0

    os.remove('test1.toml')
    os.remove('test2.toml')


class TestFileVarLoader():
    def test_load_vars_with_one_file(self, setup_vars_files):
        r = file_varloader.get_all_vars('test1.toml')

        assert r['foo1']['bar1'] == 'john1'

    def test_load_vars_with_many_files(self, setup_vars_files):
        r = file_varloader.get_all_vars(['test1.toml', 'test2.toml'])

        assert r['foo1']['bar1'] == 'john1' and r['foo2']['bar2'] == 'john2'

    def test_load_vars_with_non_existent_file(self, caplog):
        file_varloader.get_all_vars('meguminbestgirl.toml')

        assert caplog.records[-1].levelname == 'ERROR'

    def test_load_vars_with_non_existent_file_in_list(self, setup_vars_files, caplog):
        file_varloader.get_all_vars(['meguminbestgirl.toml', 'meguminworstgirl.toml', 'test1.toml'])

        assert caplog.records[-1].levelname == 'ERROR'
        assert caplog.records[-2].levelname == 'ERROR'

    def test_load_vars_with_empty_filename(self):
        """Load custom vars if no file is provided.
        Nothing should happen.
        """

        file_varloader.get_all_vars('')

    def test_load_vars_with_empty_file_list(self):
        """Load custom vars if no file is provided.
        Nothing should happen.
        """

        file_varloader.get_all_vars([])
