from nsdu import utils


class TestGetDispatchInfo:
    def test_get_dispatch_info(self):
        dispatch_config = {
            "nation1": {
                "dispatch1": {
                    "title": "Test Title 1",
                    "ns_id": "1234567",
                    "category": "1",
                    "subcategory": "100",
                },
                "dispatch2": {
                    "title": "Test Title 2",
                    "ns_id": "7654321",
                    "category": "2",
                    "subcategory": "120",
                },
            },
            "nation2": {
                "dispatch3": {
                    "title": "Test Title 1",
                    "ns_id": "1234567",
                    "category": "1",
                    "subcategory": "100",
                }
            },
        }

        r = utils.get_dispatch_info(dispatch_config)
        assert r == {
            "dispatch1": {
                "title": "Test Title 1",
                "ns_id": "1234567",
                "category": "1",
                "subcategory": "100",
                "owner_nation": "nation1",
            },
            "dispatch2": {
                "title": "Test Title 2",
                "ns_id": "7654321",
                "category": "2",
                "subcategory": "120",
                "owner_nation": "nation1",
            },
            "dispatch3": {
                "title": "Test Title 1",
                "ns_id": "1234567",
                "category": "1",
                "subcategory": "100",
                "owner_nation": "nation2",
            },
        }


class TestCanonicalNationName:
    def test_uppercase_letters_converts_to_all_lower_case_letters(self):
        assert utils.canonical_nation_name("Testopia opia") == "testopia opia"

    def test_underscores_removed(self):
        assert utils.canonical_nation_name("testopia_opia") == "testopia opia"
