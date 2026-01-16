from __future__ import annotations

from datetime import datetime, timezone
import os
import re
from typing import Iterable, Optional

import yaml


_POWER_PIN_RE = re.compile(r"^(?:[1-8]|N|N'|7N|8N|NS)$")


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


def resolve_mapping(pinset_key_value: str, templates: dict) -> Optional[dict]:
    return templates.get("pinsets", {}).get(pinset_key_value)


def load_templates(path: str) -> dict:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}

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
        yaml.safe_dump(data, handle, sort_keys=False)


def _pin_sort_key(token: str) -> tuple[int, int | str]:
    if token.isdigit():
        return (0, int(token))
    return (1, token)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_templates() -> dict:
    return {
        "pinsets": {
            "1,2": {"front": ["1"], "back": ["2"]},
            "1,2,3,4": {"front": ["1", "3"], "back": ["2", "4"]},
            "1,2,3,4,5,6": {"front": ["1", "3", "5"], "back": ["2", "4", "6"]},
            "1,2,3,4,5,6,7,8": {
                "front": ["1", "3", "5", "7"],
                "back": ["2", "4", "6", "8"],
            },
            "1,2,3,4,5,6,7N,8N": {
                "front": ["1", "3", "5", "7N"],
                "back": ["2", "4", "6", "8N"],
            },
            "1,2,3,4,N,N'": {"front": ["1", "3", "N"], "back": ["2", "4", "N'"]},
            "1,2,3,4,5,6,N,N'": {
                "front": ["1", "3", "5", "N"],
                "back": ["2", "4", "6", "N'"],
            },
        }
    }
