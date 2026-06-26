import pytest

from app.domain.exceptions import InvalidPseudoError
from app.domain.pseudo import normalize_and_validate


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("abc", "ABC"),
        ("ABC", "ABC"),
        ("a12", "A12"),
        ("123", "123"),
        ("AbC", "ABC"),
        ("  abc  ", "ABC"),
    ],
)
def test_normalize_and_validate_accepts_valid_input(raw, expected):
    assert normalize_and_validate(raw) == expected


@pytest.mark.parametrize(
    "bad_input",
    [
        "",
        "AB",          # trop court
        "ABCD",        # trop long
        "ab",          # trop court
        "ab-",         # caractère invalide
        "a#c",         # plus de hashtag accepté
        "a@c",         # caractère invalide
        "###",
        "a b",         # espace interne
    ],
)
def test_normalize_and_validate_rejects_invalid_input(bad_input):
    with pytest.raises(InvalidPseudoError):
        normalize_and_validate(bad_input)


@pytest.mark.parametrize("bad_input", [None, 42, [], object()])
def test_normalize_and_validate_rejects_non_string(bad_input):
    with pytest.raises(InvalidPseudoError):
        normalize_and_validate(bad_input)  # type: ignore[arg-type]
