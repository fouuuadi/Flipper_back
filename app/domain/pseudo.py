from __future__ import annotations

import re

from app.domain.exceptions import InvalidPseudoError

# Pseudo : exactement 3 caractères alphanumériques, normalisés en majuscules
# (style initiales de borne d'arcade). Plus de hashtag.
_PATTERN = re.compile(r"^[A-Z0-9]{3}$")


def normalize_and_validate(raw: str | None) -> str:
    """Uppercase + valide un pseudo de 3 caractères alphanumériques.

    Examples:
        "abc" -> "ABC"
        "A12" -> "A12"
        "ab"  -> InvalidPseudoError (trop court)
        "abcd" -> InvalidPseudoError (trop long)
    """
    if not isinstance(raw, str) or not raw:
        raise InvalidPseudoError("pseudo must be a non-empty string")
    candidate = raw.strip().upper()
    if not _PATTERN.fullmatch(candidate):
        raise InvalidPseudoError(
            f"pseudo {raw!r} does not match the expected format "
            f"'XXX' (exactly 3 alphanumeric characters)"
        )
    return candidate
