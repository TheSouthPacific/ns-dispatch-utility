import pytest

from nsdu.loader_api import DispatchMetadata, DispatchOp
from nsdu.loaders import file_dispatch_loader


@pytest.mark.parametrize(
    "metadata_dict,expected",
    [
        [
            {
                "op": "create",
                "title": "t",
                "category": "c",
                "subcategory": "sc",
            },
            DispatchMetadata(None, DispatchOp.CREATE, "nat", "t", "c", "sc"),
        ],
        [
            {
                "ns_id": "12345",
                "op": "create",
                "title": "t",
                "category": "c",
                "subcategory": "sc",
            },
            DispatchMetadata(None, DispatchOp.CREATE, "nat", "t", "c", "sc"),
        ],
        [
            {
                "ns_id": "12345",
                "op": "edit",
                "title": "t",
                "category": "c",
                "subcategory": "sc",
            },
            DispatchMetadata("12345", DispatchOp.EDIT, "nat", "t", "c", "sc"),
        ],
        [
            {
                "ns_id": "12345",
                "op": "delete",
                "title": "t",
                "category": "c",
                "subcategory": "sc",
            },
            DispatchMetadata("12345", DispatchOp.DELETE, "nat", "t", "c", "sc"),
        ],
    ],
)
def test_parse_valid_dispatch_metadata_dict(metadata_dict, expected):
    result = file_dispatch_loader.parse_dispatch_metadata_dict(metadata_dict, "nat")

    assert result == expected


@pytest.mark.parametrize(
    "metadata_dict",
    [
        {
            "op": "create",
            "category": "c",
            "subcategory": "sc",
        },
        {
            "op": "create",
            "title": "t",
            "category": "c",
        },
        {
            "op": "create",
            "title": "t",
            "subcategory": "sc",
        },
        {
            "op": "edit",
            "title": "t",
            "category": "c",
            "subcategory": "sc",
        },
        {
            "op": "delete",
            "title": "t",
            "category": "c",
            "subcategory": "sc",
        },
    ],
)
def test_parse_invalid_dispatch_metadata_dict(metadata_dict):
    with pytest.raises(ValueError):
        file_dispatch_loader.parse_dispatch_metadata_dict(metadata_dict, "nat")


@pytest.mark.parametrize(
    "files_content,expected",
    [
        [
            [
                {
                    "nat1": {
                        "n1": {
                            "op": "create",
                            "title": "t",
                            "category": "c",
                            "subcategory": "sc",
                        },
                        "n2": {
                            "op": "create",
                            "title": "t",
                            "category": "c",
                            "subcategory": "sc",
                        },
                    },
                    "nat2": {
                        "n3": {
                            "op": "create",
                            "title": "t",
                            "category": "c",
                            "subcategory": "sc",
                        }
                    },
                },
                {
                    "nat2": {
                        "n4": {
                            "op": "create",
                            "title": "t",
                            "category": "c",
                            "subcategory": "sc",
                        }
                    }
                },
            ],
            {
                "n1": DispatchMetadata(None, DispatchOp.CREATE, "nat1", "t", "c", "sc"),
                "n2": DispatchMetadata(None, DispatchOp.CREATE, "nat1", "t", "c", "sc"),
                "n3": DispatchMetadata(None, DispatchOp.CREATE, "nat2", "t", "c", "sc"),
                "n4": DispatchMetadata(None, DispatchOp.CREATE, "nat2", "t", "c", "sc"),
            },
        ],
        [
            [
                {
                    "nat1": {
                        "n1": {
                            "op": "create",
                            "title": "t",
                            "category": "c",
                            "subcategory": "sc",
                        },
                        "n2": {
                            "title": "t",
                            "category": "c",
                            "subcategory": "sc",
                        },
                    },
                },
            ],
            {
                "n1": DispatchMetadata(None, DispatchOp.CREATE, "nat1", "t", "c", "sc"),
            },
        ],
        [
            [
                {
                    "nat1": {
                        "n1": {
                            "op": "create",
                            "title": "t",
                            "category": "c",
                            "subcategory": "sc",
                        },
                    }
                },
                {
                    "nat2": {
                        "n1": {
                            "op": "create",
                            "title": "t",
                            "category": "c",
                            "subcategory": "sc",
                        },
                    }
                },
            ],
            {
                "n1": DispatchMetadata(None, DispatchOp.CREATE, "nat2", "t", "c", "sc"),
            },
        ],
        [
            [
                {
                    "nat1": {
                        "n1": {
                            "op": "create",
                            "title": "t",
                            "category": "c",
                            "subcategory": "sc",
                        },
                    },
                    "nat2": {
                        "n1": {
                            "op": "create",
                            "title": "t",
                            "category": "c",
                            "subcategory": "sc",
                        }
                    },
                },
            ],
            {
                "n1": DispatchMetadata(None, DispatchOp.CREATE, "nat2", "t", "c", "sc"),
            },
        ],
        [[{}], {}],
    ],
)
def test_parse_dispatch_metadata_files(files_content, expected):
    result = file_dispatch_loader.parse_dispatch_metadata_files(files_content)

    assert result == expected
