from __future__ import annotations

import re

from app.domain.exceptions import InvalidPseudoError

DEFAULT_HASHTAG = "HETIC"

# Accepted input: 3 alphanum chars, optionally followed by "#" + exactly 5 alphanum chars.
# If the hashtag is omitted, DEFAULT_HASHTAG is appended.
_INPUT_PATTERN = re.compile(r"^[A-Za-z0-9]{3}(#[A-Za-z0-9]{5})?$")

# Final, post-normalisation: uppercase only, always with a 5-char hashtag.
_FINAL_PATTERN = re.compile(r"^[A-Z0-9]{3}#[A-Z0-9]{5}$")


def normalize_and_validate(raw: str | None) -> str:
    """Uppercase + validate a raw pseudo, appending `#HETIC` if no hashtag is given.

    Examples:
        "abc"        -> "ABC#HETIC"
        "A12"        -> "A12#HETIC"
        "abc#hello"  -> "ABC#HELLO"
        "abc#xy"     -> InvalidPseudoError (hashtag too short)
    """
    if not isinstance(raw, str) or not raw:
        raise InvalidPseudoError("pseudo must be a non-empty string")
    candidate = raw.strip().upper()
    if not _INPUT_PATTERN.fullmatch(candidate):
        raise InvalidPseudoError(
            f"pseudo {raw!r} does not match the expected format "
            f"'XXX' or 'XXX#YYYYY' (3 alphanum + optional '#' + 5 alphanum)"
        )
    if "#" not in candidate:
        candidate = f"{candidate}#{DEFAULT_HASHTAG}"
    if not _FINAL_PATTERN.fullmatch(candidate):
        # Defensive — should never trigger given the input pattern + default rule.
        raise InvalidPseudoError(f"pseudo {raw!r} failed final normalization")
    return candidate
