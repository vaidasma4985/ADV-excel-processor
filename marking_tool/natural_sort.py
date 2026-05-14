from __future__ import annotations

import re
from typing import Any


_MARKING_NAME_SORT_PATTERN = re.compile(r"^(?P<prefix>.*?)(?P<number>\d+)(?P<suffix>.*)$")
_MARKING_SUFFIX_SORT_PART_PATTERN = re.compile(r"\d+|\D+")


def _stringify_sort_value(value: Any) -> str:
    """Return a stable string representation for marking sort helpers."""
    if value is None:
        return ""
    try:
        if value != value:
            return ""
    except Exception:
        pass
    return str(value).strip()


def natural_marking_suffix_sort_key(value: Any) -> tuple[tuple[int, int | str], ...]:
    """Build a comparable natural key for the optional suffix after a marking number."""
    suffix_text = _stringify_sort_value(value).casefold()
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part)
        for part in _MARKING_SUFFIX_SORT_PART_PATTERN.findall(suffix_text)
    )


def natural_marking_name_sort_key(
    value: Any,
) -> tuple[int, str, int, int, tuple[tuple[int, int | str], ...], str]:
    """Build a prefix + numeric + suffix natural sort key for marking Name/Text values."""
    marking_name = _stringify_sort_value(value)
    normalized_name = marking_name.casefold()
    match = _MARKING_NAME_SORT_PATTERN.match(marking_name)
    if not match:
        return (1, normalized_name, 0, 0, (), normalized_name)

    suffix_text = _stringify_sort_value(match.group("suffix"))
    return (
        0,
        _stringify_sort_value(match.group("prefix")).casefold(),
        int(match.group("number")),
        0 if suffix_text == "" else 1,
        natural_marking_suffix_sort_key(suffix_text),
        normalized_name,
    )
