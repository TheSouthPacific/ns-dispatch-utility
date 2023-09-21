from unittest import mock

import pytest
import toml

from nsdu import loader_api
from nsdu.loaders import file_dispatch_loader


class TestDispatchConfigManager:
    def test_load_from_file_with_multiple_files(self, toml_files):
        dispatch_config_1 = {
            "nation1": {
                "test1": {
                    "ns_id": "12345",
                    "title": "Test title 1",
                    "category": "1",
                    "subcategory": "100",
                },
                "test2": {
                    "ns_id": "67890",
                    "title": "Test title 2",
                    "category": "1",
                    "subcategory": "100",
                },
                "test3": {
                    "title": "Test title 3",
                    "category": "1",
                    "subcategory": "100",
                },
            },
            "nation2": {
                "test4": {
                    "title": "Test title 4",
                    "category": "1",
                    "subcategory": "100",
                }
            },
        }
        dispatch_config_2 = {
            "nation1": {
                "test5": {
                    "ns_id": "98765",
                    "title": "Test title 1",
                    "category": "1",
                    "subcategory": "100",
                }
            },
            "nation2": {
                "test6": {
                    "ns_id": "54321",
                    "title": "Test title 4",
                    "category": "1",
                    "subcategory": "100",
                }
            },
        }
        dispatch_config_dir = toml_files(
            {
                "dispatch_config_1.toml": dispatch_config_1,
                "dispatch_config_2.toml": dispatch_config_2,
            }
        )
        ins = file_dispatch_loader.DispatchConfigManager()

        file_1_path_str = str(dispatch_config_dir / "dispatch_config_1.toml")
        file_2_path_str = str(dispatch_config_dir / "dispatch_config_2.toml")

        ins.load_from_files([file_1_path_str, file_2_path_str])

        assert ins.all_dispatch_config == {
            file_1_path_str: dispatch_config_1,
            file_2_path_str: dispatch_config_2,
        }

    def test_load_from_file_with_an_non_existent_file(self, toml_files):
        dispatch_config = {
            "nation1": {
                "test1": {
                    "title": "Test title 1",
                    "category": "1",
                    "subcategory": "100",
                }
            }
        }
        file_path = toml_files({"dispatch_config.toml": dispatch_config})
        ins = file_dispatch_loader.DispatchConfigManager()

        with pytest.raises(loader_api.LoaderError):
            ins.load_from_files([str(file_path), "abcd.toml"])

    def test_get_canonical_dispatch_config(self):
        dispatch_config_1 = {
            "nation1": {
                "test1": {
                    "ns_id": "12345",
                    "title": "Test title 1",
                    "category": "1",
                    "subcategory": "100",
                },
                "test2": {
                    "action": "voodoo",
                    "title": "Test title 2",
                    "category": "1",
                    "subcategory": "100",
                },
            },
            "nation2": {
                "test4": {
                    "title": "Test title 4",
                    "category": "1",
                    "subcategory": "100",
                }
            },
        }
        dispatch_config_2 = {
            "nation1": {
                "test3": {
                    "ns_id": "98765",
                    "title": "Test title 3",
                    "category": "1",
                    "subcategory": "100",
                }
            },
            "nation2": {
                "test5": {
                    "action": "remove",
                    "ns_id": "54321",
                    "title": "Test title 5",
                    "category": "1",
                    "subcategory": "100",
                },
                "test6": {
                    "title": "Test title 6",
                    "category": "1",
                    "subcategory": "100",
                },
                "test7": {
                    "action": "remove",
                    "ns_id": "76543",
                    "title": "Test title 7",
                    "category": "1",
                    "subcategory": "100",
                },
            },
        }
        ins = file_dispatch_loader.DispatchConfigManager()
        ins.all_dispatch_config = {
            "config1.toml": dispatch_config_1,
            "config2.toml": dispatch_config_2,
        }

        r = ins.get_canonical_dispatch_config()

        expected = {
            "nation1": {
                "test1": {
                    "action": "edit",
                    "ns_id": "12345",
                    "title": "Test title 1",
                    "category": "1",
                    "subcategory": "100",
                },
                "test2": {
                    "action": "skip",
                    "title": "Test title 2",
                    "category": "1",
                    "subcategory": "100",
                },
                "test3": {
                    "action": "edit",
                    "ns_id": "98765",
                    "title": "Test title 3",
                    "category": "1",
                    "subcategory": "100",
                },
            },
            "nation2": {
                "test4": {
                    "action": "create",
                    "title": "Test title 4",
                    "category": "1",
                    "subcategory": "100",
                },
                "test5": {
                    "action": "remove",
                    "ns_id": "54321",
                    "title": "Test title 5",
                    "category": "1",
                    "subcategory": "100",
                },
                "test6": {
                    "action": "create",
                    "title": "Test title 6",
                    "category": "1",
                    "subcategory": "100",
                },
                "test7": {
                    "action": "remove",
                    "ns_id": "76543",
                    "title": "Test title 7",
                    "category": "1",
                    "subcategory": "100",
                },
            },
        }
        assert r == expected

    def test_save_after_add_new_dispatch_id_for_all_new_dispatches(self, toml_files):
        dispatch_config_1 = {
            "nation1": {
                "test1": {
                    "ns_id": "12345",
                    "title": "Test title 1",
                    "category": "1",
                    "subcategory": "100",
                },
                "test2": {
                    "title": "Test title 3",
                    "category": "1",
                    "subcategory": "100",
                },
            },
            "nation2": {
                "test3": {
                    "ns_id": "12345",
                    "title": "Test title 4",
                    "category": "1",
                    "subcategory": "100",
                }
            },
        }
        dispatch_config_2 = {
            "nation1": {
                "test4": {
                    "ns_id": "98765",
                    "title": "Test title 1",
                    "category": "1",
                    "subcategory": "100",
                }
            },
            "nation2": {
                "test5": {
                    "title": "Test title 4",
                    "category": "1",
                    "subcategory": "100",
                }
            },
        }
        dispatch_config_dir = toml_files(
            {
                "dispatch_config_1.toml": dispatch_config_1,
                "dispatch_config_2.toml": dispatch_config_2,
            }
        )
        ins = file_dispatch_loader.DispatchConfigManager()
        dispatch_config_file_1_path = dispatch_config_dir / "dispatch_config_1.toml"
        dispatch_config_file_2_path = dispatch_config_dir / "dispatch_config_2.toml"
        ins.load_from_files(
            [str(dispatch_config_file_1_path), str(dispatch_config_file_2_path)]
        )

        ins.add_new_dispatch_id("test2", "23456")
        ins.add_new_dispatch_id("test5", "54321")
        ins.save()

        expected_1 = {
            "nation1": {
                "test1": {
                    "ns_id": "12345",
                    "title": "Test title 1",
                    "category": "1",
                    "subcategory": "100",
                },
                "test2": {
                    "ns_id": "23456",
                    "title": "Test title 3",
                    "category": "1",
                    "subcategory": "100",
                },
            },
            "nation2": {
                "test3": {
                    "ns_id": "12345",
                    "title": "Test title 4",
                    "category": "1",
                    "subcategory": "100",
                }
            },
        }
        expected_2 = {
            "nation1": {
                "test4": {
                    "ns_id": "98765",
                    "title": "Test title 1",
                    "category": "1",
                    "subcategory": "100",
                }
            },
            "nation2": {
                "test5": {
                    "ns_id": "54321",
                    "title": "Test title 4",
                    "category": "1",
                    "subcategory": "100",
                }
            },
        }

        assert toml.load(dispatch_config_file_1_path) == expected_1
        assert toml.load(dispatch_config_file_2_path) == expected_2

    def test_save_after_add_new_dispatch_id_for_only_one_new_dispatch(self, toml_files):
        dispatch_config_1 = {
            "nation1": {
                "test1": {
                    "ns_id": "12345",
                    "title": "Test title 1",
                    "category": "1",
                    "subcategory": "100",
                },
                "test2": {
                    "title": "Test title 3",
                    "category": "1",
                    "subcategory": "100",
                },
            },
            "nation2": {
                "test3": {
                    "ns_id": "12345",
                    "title": "Test title 4",
                    "category": "1",
                    "subcategory": "100",
                }
            },
        }
        dispatch_config_2 = {
            "nation1": {
                "test4": {
                    "ns_id": "98765",
                    "title": "Test title 1",
                    "category": "1",
                    "subcategory": "100",
                }
            },
            "nation2": {
                "test5": {
                    "title": "Test title 4",
                    "category": "1",
                    "subcategory": "100",
                }
            },
        }
        dispatch_config_dir = toml_files(
            {
                "dispatch_config_1.toml": dispatch_config_1,
                "dispatch_config_2.toml": dispatch_config_2,
            }
        )
        ins = file_dispatch_loader.DispatchConfigManager()
        dispatch_config_file_1_path = dispatch_config_dir / "dispatch_config_1.toml"
        dispatch_config_file_2_path = dispatch_config_dir / "dispatch_config_2.toml"
        ins.load_from_files(
            [str(dispatch_config_file_1_path), str(dispatch_config_file_2_path)]
        )

        ins.add_new_dispatch_id("test2", "23456")
        ins.save()

        expected_1 = {
            "nation1": {
                "test1": {
                    "ns_id": "12345",
                    "title": "Test title 1",
                    "category": "1",
                    "subcategory": "100",
                },
                "test2": {
                    "ns_id": "23456",
                    "title": "Test title 3",
                    "category": "1",
                    "subcategory": "100",
                },
            },
            "nation2": {
                "test3": {
                    "ns_id": "12345",
                    "title": "Test title 4",
                    "category": "1",
                    "subcategory": "100",
                }
            },
        }
        expected_2 = {
            "nation1": {
                "test4": {
                    "ns_id": "98765",
                    "title": "Test title 1",
                    "category": "1",
                    "subcategory": "100",
                }
            },
            "nation2": {
                "test5": {
                    "title": "Test title 4",
                    "category": "1",
                    "subcategory": "100",
                }
            },
        }

        assert toml.load(dispatch_config_file_1_path) == expected_1
        assert toml.load(dispatch_config_file_2_path) == expected_2


class TestFileDispatchLoaderObj:
    def test_get_dispatch_template(self, text_files):
        template_path = text_files(
            {"test1.txt": "Test text 1", "test2.txt": "Test text 2"}
        )

        obj = file_dispatch_loader.FileDispatchLoader(
            mock.Mock(), template_path, ".txt"
        )

        assert obj.get_dispatch_template("test1") == "Test text 1"

    def test_get_dispatch_template_with_non_existing_file(self, tmp_path):
        obj = file_dispatch_loader.FileDispatchLoader(mock.Mock(), tmp_path, ".txt")

        assert obj.get_dispatch_template("test2") is None


class TestFileDispatchLoaderIntegration:
    @pytest.fixture
    def dispatch_files(self, text_files):
        return text_files(
            {
                "test1.txt": "Test text 1",
                "test2.txt": "Test text 2",
                "test3.txt": "Test text 3",
                "test4.txt": "Test text 4",
            }
        )

    def test_with_no_dispatch_creation_or_removal(self, dispatch_files, toml_files):
        dispatch_config_1 = {
            "nation1": {
                "test1": {
                    "ns_id": "12345",
                    "title": "Test title 1",
                    "category": "1",
                    "subcategory": "100",
                },
                "test2": {
                    "ns_id": "67890",
                    "title": "Test title 2",
                    "category": "1",
                    "subcategory": "100",
                },
            },
            "nation2": {
                "test3": {
                    "ns_id": "78654",
                    "title": "Test title 3",
                    "category": "1",
                    "subcategory": "100",
                }
            },
        }
        dispatch_config_2 = {
            "nation1": {
                "test4": {
                    "ns_id": "98765",
                    "title": "Test title 4",
                    "category": "1",
                    "subcategory": "100",
                }
            }
        }
        dispatch_config_dir = toml_files(
            {
                "dispatch_config_1.toml": dispatch_config_1,
                "dispatch_config_2.toml": dispatch_config_2,
            }
        )
        loader_config = {
            "dispatch_config_paths": [
                str(dispatch_config_dir / "dispatch_config_1.toml"),
                str(dispatch_config_dir / "dispatch_config_2.toml"),
            ],
            "dispatch_template_path": str(dispatch_files),
        }

        loader = file_dispatch_loader.init_dispatch_loader(
            {"file_dispatch_loader": loader_config}
        )
        r_dispatch_config = file_dispatch_loader.get_dispatch_metadata(loader)
        r_dispatch_text = file_dispatch_loader.get_dispatch_template(loader, "test1")
        file_dispatch_loader.cleanup_dispatch_loader(loader)

        assert r_dispatch_config["nation1"]["test4"]["ns_id"] == "98765"
        assert r_dispatch_text == "Test text 1"

    def test_with_one_dispatch_creation_and_one_removal(
        self, dispatch_files, toml_files
    ):
        dispatch_config_1 = {
            "nation1": {
                "test1": {
                    "ns_id": "12345",
                    "title": "Test title 1",
                    "category": "1",
                    "subcategory": "100",
                },
                "test2": {
                    "title": "Test title 2",
                    "category": "1",
                    "subcategory": "100",
                },
            },
            "nation2": {
                "test3": {
                    "ns_id": "78654",
                    "title": "Test title 3",
                    "category": "1",
                    "subcategory": "100",
                }
            },
        }
        dispatch_config_2 = {
            "nation1": {
                "test4": {
                    "action": "remove",
                    "ns_id": "98765",
                    "title": "Test title 4",
                    "category": "1",
                    "subcategory": "100",
                }
            }
        }
        dispatch_config_dir = toml_files(
            {
                "dispatch_config_1.toml": dispatch_config_1,
                "dispatch_config_2.toml": dispatch_config_2,
            }
        )
        loader_config = {
            "dispatch_config_paths": [
                str(dispatch_config_dir / "dispatch_config_1.toml"),
                str(dispatch_config_dir / "dispatch_config_2.toml"),
            ],
            "dispatch_template_path": str(dispatch_files),
        }

        loader = file_dispatch_loader.init_dispatch_loader(
            {"file_dispatch_loader": loader_config}
        )

        loader = file_dispatch_loader.init_dispatch_loader(
            {"file_dispatch_loader": loader_config}
        )
        r_dispatch_config = file_dispatch_loader.get_dispatch_metadata(loader)
        r_dispatch_text = file_dispatch_loader.get_dispatch_template(loader, "test1")
        file_dispatch_loader.add_dispatch_id(loader, "test2", "54321")
        file_dispatch_loader.cleanup_dispatch_loader(loader)

        assert r_dispatch_config["nation1"]["test4"]["action"] == "remove"
        assert r_dispatch_text == "Test text 1"
        assert (
            toml.load(dispatch_config_dir / "dispatch_config_1.toml")["nation1"][
                "test2"
            ]["ns_id"]
            == "54321"
        )
