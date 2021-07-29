import os

import pytest
import toml

from nsdu import exceptions
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


class TestAddPersonnelInfo():
    def test_with_existing_groups(self):
        personnel = {'personnel1': {'position1': 'Frodo', 'position2': 'Gandalf'},
                     'personnel2': {'position1': 'Sauron', 'position2': 'Theoden'}}
        personnel_info = {'info1': {'Frodo': {'nation': 'Frodonia', 'discord_handle': 'Frodo#1234'},
                                    'Gandalf': {'nation': 'Gandalf Republic', 'discord_handle': 'Gandalf#4321'},
                                    'Sauron': {'nation': 'Sauron', 'discord_handle': 'Sauron#5050'}},
                          'info2': {'Theoden': {'nation': 'Theoden Federation', 'discord_handle': 'Theoden#0974'}}}
        vars = {'foo1': 'bar1'}
        vars.update(personnel)
        vars.update(personnel_info)
    
        file_varloader.add_personnel_info(vars, ['personnel1', 'personnel2'], ['info1', 'info2'])
    
        expected_personnel = {'personnel1': {'position1': {'name': 'Frodo', 'nation': 'Frodonia', 'discord_handle': 'Frodo#1234'},
                                             'position2': {'name': 'Gandalf', 'nation': 'Gandalf Republic', 'discord_handle': 'Gandalf#4321'}},
                              'personnel2': {'position1': {'name': 'Sauron', 'nation': 'Sauron', 'discord_handle': 'Sauron#5050'},
                                             'position2': {'name': 'Theoden', 'nation': 'Theoden Federation', 'discord_handle': 'Theoden#0974'}}}
        expected = {'foo1': 'bar1'}
        expected.update(expected_personnel)
        expected.update(personnel_info)
        assert vars == expected
    
    def test_with_non_existent_personnel_group(self):
        personnel = {'personnel1': {'position1': 'Frodo', 'position2': 'Gandalf'}}
        personnel_info = {'info1': {'Frodo': {'nation': 'Frodonia', 'discord_handle': 'Frodo#1234'},
                                    'Gandalf': {'nation': 'Gandalf Republic', 'discord_handle': 'Gandalf#4321'},
                                    'Sauron': {'nation': 'Sauron', 'discord_handle': 'Sauron#5050'}},
                          'info2': {'Theoden': {'nation': 'Theoden Federation', 'discord_handle': 'Theoden#0974'}}}
        vars = {'foo1': 'bar1'}
        vars.update(personnel)
        vars.update(personnel_info)

        with pytest.raises(exceptions.LoaderConfigError):
            file_varloader.add_personnel_info(vars, ['personnel1', 'personnel2'], ['info1', 'info2'])
    
    def test_with_non_existent_personnel_info_group(self):
        personnel = {'personnel1': {'position1': 'Frodo', 'position2': 'Gandalf'},
                     'personnel2': {'position1': 'Sauron', 'position2': 'Theoden'}}
        personnel_info = {'info2': {'Theoden': {'nation': 'Theoden Federation', 'discord_handle': 'Theoden#0974'}}}
        vars = {'foo1': 'bar1'}
        vars.update(personnel)
        vars.update(personnel_info)

        with pytest.raises(exceptions.LoaderConfigError):
            file_varloader.add_personnel_info(vars, ['personnel1', 'personnel2'], ['info1', 'info2'])
    
    def test_with_non_existent_personnel_name(self):
        personnel = {'personnel1': {'position1': 'Frodo', 'position2': 'Gandalf'},
                     'personnel2': {'position1': 'Sauron', 'position2': 'Theoden'}}
        personnel_info = {'info1': {'Gandalf': {'nation': 'Gandalf Republic', 'discord_handle': 'Gandalf#4321'},
                                    'Sauron': {'nation': 'Sauron', 'discord_handle': 'Sauron#5050'}},
                          'info2': {'Theoden': {'nation': 'Theoden Federation', 'discord_handle': 'Theoden#0974'}}}
        vars = {'foo1': 'bar1'}
        vars.update(personnel)
        vars.update(personnel_info)

        with pytest.raises(exceptions.LoaderConfigError):
            file_varloader.add_personnel_info(vars, ['personnel1', 'personnel2'], ['info1', 'info2'])


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
