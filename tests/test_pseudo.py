import pytest

from app.domain.exceptions import InvalidPseudoError
from app.domain.pseudo import DEFAULT_HASHTAG, normalize_and_validate


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("abc", f"ABC#{DEFAULT_HASHTAG}"),
        ("ABC", f"ABC#{DEFAULT_HASHTAG}"),
        ("a12", f"A12#{DEFAULT_HASHTAG}"),
        ("123", f"123#{DEFAULT_HASHTAG}"),
        ("abc#hello", "ABC#HELLO"),
        ("abc#bar12", "ABC#BAR12"),
        ("Foo#PoTaT", "FOO#POTAT"),
        ("  abc  ", f"ABC#{DEFAULT_HASHTAG}"),
    ],
)
def test_normalize_and_validate_accepts_valid_input(raw, expected):
    assert normalize_and_validate(raw) == expected


@pytest.mark.parametrize(
    "bad_input",
    [
        "",
        "AB",            # too short before #
        "ABCD",          # too long before #
        "abc#xy",        # hashtag too short
        "abc#toolong",   # hashtag too long
        "abc-#hello",    # invalid char before #
        "abc#hel-o",     # invalid char after #
        "###",
        "abc#",
        "abc##",
    ],
)
def test_normalize_and_validate_rejects_invalid_input(bad_input):
    with pytest.raises(InvalidPseudoError):
        normalize_and_validate(bad_input)


@pytest.mark.parametrize("bad_input", [None, 42, [], object()])
def test_normalize_and_validate_rejects_non_string(bad_input):
    with pytest.raises(InvalidPseudoError):
        normalize_and_validate(bad_input)  # type: ignore[arg-type]
