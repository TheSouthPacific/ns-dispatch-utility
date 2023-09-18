import pytest

from nsdu import utils


class TestCanonicalNationName:
    @pytest.mark.parametrize(
        "name,expected",
        [["United States", "united states"], ["united_states", "united states"]],
    )
    def test_uppercase_letters_converts_to_all_lower_case_letters(self, name, expected):
        result = utils.canonical_nation_name(name)
        assert result == expected
