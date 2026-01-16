from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
from typing import Iterable, Optional


_POWER_PIN_RE = re.compile(r"^(?:[1-8]|N|N'|7N|8N|NS)$")
_FRONT_ONLY_NUMBERS = {"1", "3", "5", "7"}
_BACK_ONLY_NUMBERS = {"2", "4", "6", "8"}
_SUPPORTED_NEUTRAL_PAIRS = {("N", "N'"), ("7N", "8N")}


def normalize_pin_token(pin: str) -> str:
    cleaned = str(pin).replace("\u00a0", " ")
    cleaned = re.sub(r"\s+", "", cleaned)
    cleaned = (
        cleaned.replace("’", "'")
        .replace("‘", "'")
        .replace("`", "'")
        .replace("´", "'")
    )
    return cleaned.upper()


def is_power_pin(pin: str) -> bool:
    canonical = normalize_pin_token(pin)
    return bool(_POWER_PIN_RE.match(canonical))


def pinset_key(pins: Iterable[str]) -> str:
    tokens = [normalize_pin_token(pin) for pin in pins]
    tokens = [token for token in tokens if token and is_power_pin(token)]
    unique = sorted(set(tokens), key=_pin_sort_key)
    return ",".join(unique)


def resolve_template_for_pinset(
    pinset_key_value: str,
    type_signature: str,
    templates: dict,
) -> Optional[dict]:
    pinsets = templates.get("pinsets", {})
    if pinset_key_value in pinsets:
        entry = pinsets[pinset_key_value]
        if isinstance(entry, dict) and "front_pins" in entry:
            return entry
        if isinstance(entry, dict):
            return entry.get(type_signature) or entry.get("*")
    return infer_front_back_defaults(pinset_key_value)


def infer_front_back_defaults(pinset_key_value: str) -> Optional[dict]:
    tokens = [token for token in pinset_key_value.split(",") if token]
    if not tokens:
        return None

    neutrals = {token for token in tokens if token in {"N", "N'", "7N", "8N", "NS"}}
    numbers = {token for token in tokens if token.isdigit()}

    neutral_pair = None
    if neutrals:
        if neutrals == {"N", "N'"}:
            neutral_pair = ("N", "N'")
        elif neutrals == {"7N", "8N"}:
            neutral_pair = ("7N", "8N")
        else:
            return None

    expected_sets = {
        frozenset({"1", "2"}): (["1"], ["2"]),
        frozenset({"1", "2", "3", "4"}): (["1", "3"], ["2", "4"]),
        frozenset({"1", "2", "3", "4", "5", "6"}): (["1", "3", "5"], ["2", "4", "6"]),
        frozenset({"1", "2", "3", "4", "5", "6", "7", "8"}): (
            ["1", "3", "5", "7"],
            ["2", "4", "6", "8"],
        ),
    }
    if frozenset(numbers) not in expected_sets:
        return None

    front_pins, back_pins = expected_sets[frozenset(numbers)]
    template = {
        "front_pins": front_pins,
        "back_pins": back_pins,
        "front_only": False,
    }
    if neutral_pair:
        template["neutral_front_token"] = neutral_pair[0]
        template["neutral_back_token"] = neutral_pair[1]
    return template


def is_front_only_pinset(pinset_key_value: str) -> bool:
    tokens = [token for token in pinset_key_value.split(",") if token]
    if not tokens:
        return False
    numbers = {token for token in tokens if token.isdigit()}
    neutrals = {token for token in tokens if token in {"N", "N'", "7N", "8N", "NS"}}
    if numbers and not numbers.issubset(_FRONT_ONLY_NUMBERS):
        return False
    if neutrals - {"N", "7N", "NS"}:
        return False
    if numbers & _BACK_ONLY_NUMBERS:
        return False
    return True


def load_templates(path: str) -> dict:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

    defaults = _default_templates()
    pinsets = data.get("pinsets", {})
    updated = False
    for key, value in defaults.get("pinsets", {}).items():
        if key not in pinsets:
            pinsets[key] = value
            updated = True
    data["pinsets"] = pinsets
    data.setdefault("meta", {})
    if updated or "updated_at" not in data["meta"]:
        data["meta"]["updated_at"] = _timestamp()
    if updated or not os.path.exists(path):
        save_templates(path, data)
    return data


def save_templates(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data.setdefault("meta", {})
    data["meta"]["updated_at"] = _timestamp()
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=False)
        handle.write("\n")


def _pin_sort_key(token: str) -> tuple[int, int | str]:
    if token.isdigit():
        return (0, int(token))
    return (1, token)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_templates() -> dict:
    return {
        "pinsets": {
            "1,2": {"front_pins": ["1"], "back_pins": ["2"], "front_only": False},
            "1,2,3,4": {
                "front_pins": ["1", "3"],
                "back_pins": ["2", "4"],
                "front_only": False,
            },
            "1,2,3,4,5,6": {
                "front_pins": ["1", "3", "5"],
                "back_pins": ["2", "4", "6"],
                "front_only": False,
            },
            "1,2,3,4,5,6,7,8": {
                "front_pins": ["1", "3", "5", "7"],
                "back_pins": ["2", "4", "6", "8"],
                "front_only": False,
            },
            "1,2,3,4,5,6,7N,8N": {
                "front_pins": ["1", "3", "5", "7N"],
                "back_pins": ["2", "4", "6", "8N"],
                "neutral_front_token": "7N",
                "neutral_back_token": "8N",
                "front_only": False,
            },
            "1,2,3,4,N,N'": {
                "front_pins": ["1", "3", "N"],
                "back_pins": ["2", "4", "N'"],
                "neutral_front_token": "N",
                "neutral_back_token": "N'",
                "front_only": False,
            },
            "1,2,3,4,5,6,N,N'": {
                "front_pins": ["1", "3", "5", "N"],
                "back_pins": ["2", "4", "6", "N'"],
                "neutral_front_token": "N",
                "neutral_back_token": "N'",
                "front_only": False,
            },
        }
    }
