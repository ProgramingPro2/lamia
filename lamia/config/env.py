"""Read canonical ``LAMIA_*`` environment variables, with ``STRIX_*`` fallback.

The first name that is present wins, including when its value is empty, so a
set Lamia variable overrides a legacy Strix variable. Lookup is
case-insensitive, matching the settings models.
"""

from __future__ import annotations

import os


def first_set(*names: str) -> str | None:
    """Return the value of the first listed variable that is present."""
    if not names:
        return None
    folded = {key.upper(): key for key in os.environ}
    for name in names:
        actual = folded.get(name.upper())
        if actual is not None:
            return os.environ[actual]
    return None


def first_nonempty(*names: str, default: str = "") -> str:
    """Return the chosen variable, or ``default`` when it is missing or blank."""
    value = first_set(*names)
    if value is None:
        return default
    stripped = value.strip()
    return stripped or default
