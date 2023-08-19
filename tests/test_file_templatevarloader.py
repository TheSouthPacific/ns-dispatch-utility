import pytest

from nsdu import exceptions
from nsdu.loaders import file_templatevarloader


class TestLoadTemplateVarsFromTomlFiles:
    def test_with_existing_files(self, toml_files):
        paths = toml_files(
            {
                "test1.toml": {"foo1": {"bar1": "john1"}},
                "test2.toml": {"foo2": {"bar2": "john2"}},
            }
        )

        r = file_templatevarloader.load_template_vars_from_files(
            [str(paths / "test1.toml"), str(paths / "test2.toml")]
        )

        expected = {"foo1": {"bar1": "john1"}, "foo2": {"bar2": "john2"}}
        assert r == expected

    def test_with_non_existent_file(self):
        with pytest.raises(exceptions.LoaderConfigError):
            file_templatevarloader.load_template_vars_from_files(["non_existent.toml"])

    def test_with_empty_file(self, toml_files):
        paths = toml_files(
            {"test1.toml": {"foo1": {"bar1": "john1"}}, "test2.toml": ""}
        )

        r = file_templatevarloader.load_template_vars_from_files(
            [str(paths / "test1.toml"), str(paths / "test2.toml")]
        )
        assert r == {"foo1": {"bar1": "john1"}}

    def test_with_empty_file_list(self):
        """Load vars if no file is provided in the list.
        Nothing should happen.
        """

        file_templatevarloader.load_template_vars_from_files([])


class TestReplaceNameWithPersonnelInfo:
    def test_with_existing_info(self):
        personnel_info = {
            "Frodo": {
                "name": "Frodo",
                "nation": "Frodonia",
                "discord_handle": "Frodo#1234",
            },
            "Gandalf": {
                "name": "Frodo",
                "nation": "Gandalf Republic",
                "discord_handle": "Gandalf#4321",
            },
        }

        r = file_templatevarloader.replace_name_with_personnel_info(
            "Frodo", personnel_info
        )

        assert r == {
            "name": "Frodo",
            "nation": "Frodonia",
            "discord_handle": "Frodo#1234",
        }

    def test_with_non_existing_info(self):
        personnel_info = {
            "Frodo": {
                "name": "Frodo",
                "nation": "Frodonia",
                "discord_handle": "Frodo#1234",
            },
            "Gandalf": {
                "name": "Frodo",
                "nation": "Gandalf Republic",
                "discord_handle": "Gandalf#4321",
            },
        }

        with pytest.raises(exceptions.LoaderConfigError):
            file_templatevarloader.replace_name_with_personnel_info(
                "Random", personnel_info
            )


class TestReplaceNameListWithPersonnelInfo:
    def test_with_existing_info(self):
        personnel_info = {
            "Frodo": {
                "name": "Frodo",
                "nation": "Frodonia",
                "discord_handle": "Frodo#1234",
            },
            "Gandalf": {
                "name": "Gandalf",
                "nation": "Gandalf Republic",
                "discord_handle": "Gandalf#4321",
            },
        }

        r = file_templatevarloader.replace_name_list_with_personnel_info(
            ["Frodo", "Gandalf"], personnel_info
        )

        assert r == [
            {"name": "Frodo", "nation": "Frodonia", "discord_handle": "Frodo#1234"},
            {
                "name": "Gandalf",
                "nation": "Gandalf Republic",
                "discord_handle": "Gandalf#4321",
            },
        ]

    def test_with_non_existing_info(self):
        personnel_info = {
            "Frodo": {
                "name": "Frodo",
                "nation": "Frodonia",
                "discord_handle": "Frodo#1234",
            },
            "Gandalf": {
                "name": "Gandalf",
                "nation": "Gandalf Republic",
                "discord_handle": "Gandalf#4321",
            },
        }

        with pytest.raises(exceptions.LoaderConfigError):
            file_templatevarloader.replace_name_list_with_personnel_info(
                ["Frodo", "Random"], personnel_info
            )


class TestMergePersonnelInfoGroups:
    def test_with_existent_groups(self):
        template_vars = {
            "info1": {
                "Frodo": {"nation": "Frodonia", "discord_handle": "Frodo#1234"},
                "Gandalf": {
                    "nation": "Gandalf Republic",
                    "discord_handle": "Gandalf#4321",
                },
            },
            "info2": {
                "Theoden": {
                    "nation": "Theoden Federation",
                    "discord_handle": "Theoden#0974",
                }
            },
        }

        r = file_templatevarloader.merge_personnel_info_groups(
            template_vars, ["info1", "info2"]
        )

        expected = {
            "Frodo": {
                "name": "Frodo",
                "nation": "Frodonia",
                "discord_handle": "Frodo#1234",
            },
            "Gandalf": {
                "name": "Gandalf",
                "nation": "Gandalf Republic",
                "discord_handle": "Gandalf#4321",
            },
            "Theoden": {
                "name": "Theoden",
                "nation": "Theoden Federation",
                "discord_handle": "Theoden#0974",
            },
        }
        assert r == expected

    def test_with_non_existent_groups(self):
        template_vars = {
            "info1": {
                "Frodo": {"nation": "Frodonia", "discord_handle": "Frodo#1234"},
                "Gandalf": {
                    "nation": "Gandalf Republic",
                    "discord_handle": "Gandalf#4321",
                },
            },
            "info2": {
                "Theoden": {
                    "nation": "Theoden Federation",
                    "discord_handle": "Theoden#0974",
                }
            },
        }

        with pytest.raises(exceptions.LoaderConfigError):
            file_templatevarloader.merge_personnel_info_groups(
                template_vars, ["info1", "random"]
            )


class TestAddPersonnelInfo:
    def test_with_existing_groups(self):
        personnel = {
            "personnel1": {"position1": "Frodo", "position2": ["Gandalf", "Sauron"]},
            "personnel2": {"position1": "Theoden"},
        }
        personnel_info = {
            "info1": {
                "Frodo": {"nation": "Frodonia", "discord_handle": "Frodo#1234"},
                "Gandalf": {
                    "nation": "Gandalf Republic",
                    "discord_handle": "Gandalf#4321",
                },
                "Sauron": {"nation": "Sauron", "discord_handle": "Sauron#5050"},
            },
            "info2": {
                "Theoden": {
                    "nation": "Theoden Federation",
                    "discord_handle": "Theoden#0974",
                }
            },
        }
        vars = {"foo1": "bar1"}
        vars.update(personnel)
        vars.update(personnel_info)

        file_templatevarloader.add_personnel_info(
            vars, ["personnel1", "personnel2"], ["info1", "info2"]
        )

        expected = {
            "personnel1": {
                "position1": {
                    "name": "Frodo",
                    "nation": "Frodonia",
                    "discord_handle": "Frodo#1234",
                },
                "position2": [
                    {
                        "name": "Gandalf",
                        "nation": "Gandalf Republic",
                        "discord_handle": "Gandalf#4321",
                    },
                    {
                        "name": "Sauron",
                        "nation": "Sauron",
                        "discord_handle": "Sauron#5050",
                    },
                ],
            },
            "personnel2": {
                "position1": {
                    "name": "Theoden",
                    "nation": "Theoden Federation",
                    "discord_handle": "Theoden#0974",
                }
            },
            "foo1": "bar1",
            "info1": {
                "Frodo": {"nation": "Frodonia", "discord_handle": "Frodo#1234"},
                "Gandalf": {
                    "nation": "Gandalf Republic",
                    "discord_handle": "Gandalf#4321",
                },
                "Sauron": {"nation": "Sauron", "discord_handle": "Sauron#5050"},
            },
            "info2": {
                "Theoden": {
                    "nation": "Theoden Federation",
                    "discord_handle": "Theoden#0974",
                }
            },
        }
        assert vars == expected


class TestFileVarLoader:
    def test_integration(self, toml_files):
        vars_1 = {
            "personnel1": {"position1": "Frodo", "position2": ["Gandalf", "Sauron"]},
            "personnel2": {"position1": "Theoden"},
        }
        vars_2 = {"foo1": "bar1", "foo2": "bar2"}
        vars_3 = {
            "info1": {
                "Frodo": {"nation": "Frodonia", "discord_handle": "Frodo#1234"},
                "Gandalf": {
                    "nation": "Gandalf Republic",
                    "discord_handle": "Gandalf#4321",
                },
                "Sauron": {"nation": "Sauron", "discord_handle": "Sauron#5050"},
            },
            "info2": {
                "Theoden": {
                    "nation": "Theoden Federation",
                    "discord_handle": "Theoden#0974",
                }
            },
        }
        path = toml_files(
            {"test1.toml": vars_1, "test2.toml": vars_2, "test3.toml": vars_3}
        )
        config = {
            "template_var_paths": [
                str(path / "test1.toml"),
                str(path / "test2.toml"),
                str(path / "test3.toml"),
            ],
            "personnel_groups": ["personnel1", "personnel2"],
            "personnel_info_groups": ["info1", "info2"],
        }

        r = file_templatevarloader.get_template_vars({"file_templatevarloader": config})

        expected = {
            "personnel1": {
                "position1": {
                    "name": "Frodo",
                    "nation": "Frodonia",
                    "discord_handle": "Frodo#1234",
                },
                "position2": [
                    {
                        "name": "Gandalf",
                        "nation": "Gandalf Republic",
                        "discord_handle": "Gandalf#4321",
                    },
                    {
                        "name": "Sauron",
                        "nation": "Sauron",
                        "discord_handle": "Sauron#5050",
                    },
                ],
            },
            "personnel2": {
                "position1": {
                    "name": "Theoden",
                    "nation": "Theoden Federation",
                    "discord_handle": "Theoden#0974",
                }
            },
            "foo1": "bar1",
            "foo2": "bar2",
            "info1": {
                "Frodo": {"nation": "Frodonia", "discord_handle": "Frodo#1234"},
                "Gandalf": {
                    "nation": "Gandalf Republic",
                    "discord_handle": "Gandalf#4321",
                },
                "Sauron": {"nation": "Sauron", "discord_handle": "Sauron#5050"},
            },
            "info2": {
                "Theoden": {
                    "nation": "Theoden Federation",
                    "discord_handle": "Theoden#0974",
                }
            },
        }
        assert r == expected
