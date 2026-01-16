from __future__ import annotations

import json
import os
import re
from typing import Iterable


_DEFAULT_TEMPLATE_PATH = "pin_templates.json"


def canonicalize_pin_token(token: str) -> str:
    cleaned = str(token).replace("\u00a0", " ")
    cleaned = re.sub(r"\s+", "", cleaned)
    cleaned = (
        cleaned.replace("’", "'")
        .replace("‘", "'")
        .replace("`", "'")
        .replace("´", "'")
    )
    return cleaned.upper()


def _pin_sort_key(token: str) -> tuple[int, int | str]:
    if token.isdigit():
        return (0, int(token))
    return (1, token)


def canonical_pinset_key(pins: Iterable[str]) -> str:
    unique_tokens = {canonicalize_pin_token(pin) for pin in pins if pin is not None}
    unique_tokens.discard("")
    sorted_tokens = sorted(unique_tokens, key=_pin_sort_key)
    return ",".join(sorted_tokens)


def load_pin_templates(path: str = _DEFAULT_TEMPLATE_PATH) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_pin_templates(templates: dict, path: str = _DEFAULT_TEMPLATE_PATH) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(templates, handle, indent=2, sort_keys=True)
        handle.write("\n")


def infer_builtin_template(pinset_key: str) -> dict | None:
    tokens = [token for token in pinset_key.split(",") if token]
    if not tokens:
        return None

    neutral_tokens = {token for token in tokens if "N" in token}
    allowed_neutrals = {"N", "N'", "7N", "8N"}
    if neutral_tokens - allowed_neutrals:
        return None
    if neutral_tokens and neutral_tokens not in ({"N", "N'"}, {"7N", "8N"}, {"N", "7N"}):
        return None

    numeric_tokens = {token for token in tokens if token.isdigit()}
    numeric_sets = {
        frozenset({"1", "2"}): [("1", "2")],
        frozenset({"1", "2", "3", "4"}): [("1", "2"), ("3", "4")],
        frozenset({"1", "2", "3", "4", "5", "6"}): [("1", "2"), ("3", "4"), ("5", "6")],
        frozenset({"1", "2", "3", "4", "5", "6", "7", "8"}): [
            ("1", "2"),
            ("3", "4"),
            ("5", "6"),
            ("7", "8"),
        ],
    }
    if frozenset(numeric_tokens) not in numeric_sets:
        return None

    expected_tokens = set(numeric_tokens) | set(neutral_tokens)
    if set(tokens) != expected_tokens:
        return None

    front: list[str] = []
    back: list[str] = []
    neutral_map: list[dict[str, str]] = []

    for left, right in numeric_sets[frozenset(numeric_tokens)]:
        front.append(left)
        back.append(right)

    if neutral_tokens == {"N", "N'"}:
        front.append("N")
        back.append("N'")
        neutral_map.append({"front": "N", "back": "N'"})
    elif neutral_tokens == {"7N", "8N"}:
        front.append("7N")
        back.append("8N")
        neutral_map.append({"front": "7N", "back": "8N"})
    elif neutral_tokens == {"N", "7N"}:
        front.append("N")
        back.append("7N")
        neutral_map.append({"front": "N", "back": "7N"})

    template: dict[str, object] = {
        "front": sorted(set(front), key=_pin_sort_key),
        "back": sorted(set(back), key=_pin_sort_key),
    }
    if neutral_map:
        template["neutral_map"] = neutral_map
    return template


def resolve_pin_template(pins: Iterable[str], templates: dict) -> tuple[dict | None, str]:
    pinset_key = canonical_pinset_key(pins)
    if pinset_key in templates:
        return templates[pinset_key], pinset_key
    return infer_builtin_template(pinset_key), pinset_key


def _self_test() -> None:
    assert canonical_pinset_key(["3", "1", "2"]) == "1,2,3"
