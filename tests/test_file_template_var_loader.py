import pytest

from nsdu.loader_api import LoaderError
from nsdu.loaders import file_template_var_loader as loader


class TestLoadTemplateVarsFromTomlFiles:
    @pytest.mark.parametrize(
        "template_vars,expected",
        [
            [
                {
                    "vars1.toml": {"foo1": {"bar1": "john1"}},
                    "vars2.toml": {"foo2": {"bar2": "john2"}},
                },
                {"foo1": {"bar1": "john1"}, "foo2": {"bar2": "john2"}},
            ],
            [{"vars.toml": {}}, {}],
            [{}, {}],
        ],
    )
    def test_with_existing_files_returns_variables(
        self, toml_files, template_vars, expected
    ):
        var_paths = toml_files(template_vars).file_paths
        result = loader.load_template_vars_from_files(var_paths)

        assert result == expected

    def test_with_non_existent_file_raises_exception(self):
        with pytest.raises(LoaderError):
            loader.load_template_vars_from_files(["a"])


class TestPeopleInfoStore:
    def test_get_non_existent_person_raises_exception(self):
        obj = loader.PeopleInfoStore({})

        with pytest.raises(LoaderError):
            obj[""]

    @pytest.mark.parametrize(
        "template_vars,group_names,expected",
        [
            [
                {
                    "i1": {
                        "n1": {
                            "nation": "nat1",
                            "discord_handle": "n1#1",
                        },
                        "n2": {
                            "nation": "nat2",
                            "discord_handle": "n2#2",
                        },
                    },
                    "i2": {
                        "n3": {
                            "nation": "nat3",
                            "discord_handle": "n3#3",
                        }
                    },
                },
                ["i1", "i2"],
                {
                    "n1": {
                        "name": "n1",
                        "nation": "nat1",
                        "discord_handle": "n1#1",
                    },
                    "n2": {
                        "name": "n2",
                        "nation": "nat2",
                        "discord_handle": "n2#2",
                    },
                    "n3": {
                        "name": "n3",
                        "nation": "nat3",
                        "discord_handle": "n3#3",
                    },
                },
            ],
            [{}, [], {}],
        ],
    )
    def test_load_from_people_info_var_groups_returns_dict(
        self, template_vars, group_names, expected
    ):
        result = loader.PeopleInfoStore.from_people_info_var_groups(
            template_vars, group_names
        )

        assert result == expected

    def test_load_non_existent_info_var_group_raises_exception(self):
        with pytest.raises(LoaderError):
            loader.PeopleInfoStore.from_people_info_var_groups({}, ["i"])


class TestReplacePersonnelNamesWithInfo:
    def test_with_existing_groups_returns_replaced_vars(self):
        people_info = loader.PeopleInfoStore(
            {
                "n1": {"nation": "nat1", "discord_handle": "n1#1"},
                "n2": {"nation": "nat2", "discord_handle": "n2#2"},
                "n3": {"nation": "nat3", "discord_handle": "n3#3"},
            }
        )
        template_vars = {
            "foo1": "bar1",
            "p1": {"pos1": "n1", "pos2": ["n1", "n2"]},
            "p2": {"pos3": "n3"},
        }

        loader.replace_personnel_names_with_info(
            template_vars, ["p1", "p2"], people_info
        )

        expected = {
            "foo1": "bar1",
            "p1": {
                "pos1": {
                    "name": "n1",
                    "nation": "nat1",
                    "discord_handle": "n1#1",
                },
                "pos2": [
                    {
                        "name": "n1",
                        "nation": "nat1",
                        "discord_handle": "n1#1",
                    },
                    {
                        "name": "n2",
                        "nation": "nat2",
                        "discord_handle": "n2#2",
                    },
                ],
            },
            "p2": {
                "pos3": {
                    "name": "n3",
                    "nation": "nat3",
                    "discord_handle": "n3#3",
                }
            },
        }
        assert template_vars == expected

    def test_with_non_existent_personnel_group_raises_exception(self):
        people_info = loader.PeopleInfoStore({})

        with pytest.raises(LoaderError):
            loader.replace_personnel_names_with_info({}, ["p"], people_info)


def test_get_template_vars_returns_template_vars(toml_files):
    vars1 = {
        "foo": "bar",
        "p": {"pos1": "n1", "pos2": ["n2"]},
    }
    vars2 = {
        "i": {
            "n1": {"nation": "nat1", "discord_handle": "n1#1"},
            "n2": {"nation": "nat2", "discord_handle": "n2#2"},
        },
    }
    var_paths = toml_files({"vars1.toml": vars1, "vars2.toml": vars2}).file_paths

    config = {
        "template_var_paths": var_paths,
        "personnel_groups": ["p"],
        "people_info_groups": ["i"],
    }
    result = loader.get_template_vars({"file_template_var_loader": config})

    expected = {
        "foo": "bar",
        "p": {
            "pos1": {
                "name": "n1",
                "nation": "nat1",
                "discord_handle": "n1#1",
            },
            "pos2": [
                {
                    "name": "n2",
                    "nation": "nat2",
                    "discord_handle": "n2#2",
                },
            ],
        },
        "i": {
            "n1": {"nation": "nat1", "discord_handle": "n1#1"},
            "n2": {"nation": "nat2", "discord_handle": "n2#2"},
        },
    }
    assert result == expected
