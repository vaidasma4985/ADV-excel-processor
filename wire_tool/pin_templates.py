from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "pin_templates.json"
_NEUTRAL_TOKENS = {"N", "N'", "7N", "8N"}


def pin_sort_key(pin: str) -> tuple[int, int, str]:
    if pin.isdigit():
        return (0, int(pin), pin)
    return (1, 0, pin)


def load_templates(path: Path | None = None) -> Dict[Tuple[Tuple[str, ...], str], Dict[str, Any]]:
    template_path = path or TEMPLATE_PATH
    if not template_path.exists():
        return {}
    with template_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    templates: Dict[Tuple[Tuple[str, ...], str], Dict[str, Any]] = {}
    for entry in payload or []:
        pinset = tuple(sorted({str(pin) for pin in entry.get("pinset", [])}, key=pin_sort_key))
        type_signature = str(entry.get("type_signature") or "").strip()
        templates[(pinset, type_signature)] = {
            "pinset": list(pinset),
            "type_signature": type_signature,
            "front_pins": sorted([str(pin) for pin in entry.get("front_pins", [])], key=pin_sort_key),
            "back_pins": sorted([str(pin) for pin in entry.get("back_pins", [])], key=pin_sort_key),
            "neutral_front_token": entry.get("neutral_front_token"),
            "neutral_back_token": entry.get("neutral_back_token"),
            "front_only": bool(entry.get("front_only", False)),
        }
    return templates


def save_templates(
    templates: Dict[Tuple[Tuple[str, ...], str], Dict[str, Any]],
    path: Path | None = None,
) -> None:
    template_path = path or TEMPLATE_PATH
    serialized: List[Dict[str, Any]] = []
    for (_pinset, _signature), template in sorted(
        templates.items(),
        key=lambda item: (item[0][1], item[0][0]),
    ):
        serialized.append(
            {
                "pinset": template.get("pinset", []),
                "type_signature": template.get("type_signature", ""),
                "front_pins": template.get("front_pins", []),
                "back_pins": template.get("back_pins", []),
                "neutral_front_token": template.get("neutral_front_token"),
                "neutral_back_token": template.get("neutral_back_token"),
                "front_only": bool(template.get("front_only", False)),
            }
        )
    template_path.write_text(json.dumps(serialized, indent=2, sort_keys=True), encoding="utf-8")


def resolve_template_for_pinset(
    pinset: Iterable[str],
    type_signature: str,
    templates: Dict[Tuple[Tuple[str, ...], str], Dict[str, Any]],
) -> Dict[str, Any] | None:
    key = (tuple(sorted(pinset, key=pin_sort_key)), type_signature)
    return templates.get(key)


def _known_neutral_mapping(pinset: set[str]) -> tuple[str | None, str | None] | None:
    if {"N", "N'"}.issubset(pinset):
        return "N", "N'"
    if {"7N", "N'"}.issubset(pinset):
        return "7N", "N'"
    if {"7N", "8N"}.issubset(pinset):
        return "7N", "8N"
    if any(token in pinset for token in _NEUTRAL_TOKENS):
        return None
    return (None, None)


def infer_front_back_defaults(pinset: Iterable[str]) -> Dict[str, Any] | None:
    pinset_set = {str(pin) for pin in pinset}
    neutral_mapping = _known_neutral_mapping(pinset_set)
    if neutral_mapping is None:
        return None

    numeric_pins = sorted([pin for pin in pinset_set if pin.isdigit()], key=lambda value: int(value))
    mapping = {
        ("1", "2"),
        ("1", "2", "3", "4"),
        ("1", "2", "3", "4", "5", "6"),
        ("1", "2", "3", "4", "5", "6", "7", "8"),
    }
    numeric_tuple = tuple(numeric_pins)
    if numeric_tuple not in mapping:
        return None

    front_pins = [pin for pin in numeric_pins if int(pin) % 2 == 1]
    back_pins = [pin for pin in numeric_pins if int(pin) % 2 == 0]
    neutral_front, neutral_back = neutral_mapping
    if neutral_front:
        front_pins.append(neutral_front)
    if neutral_back:
        back_pins.append(neutral_back)

    return {
        "pinset": sorted(pinset_set, key=pin_sort_key),
        "type_signature": "",
        "front_pins": sorted(front_pins, key=pin_sort_key),
        "back_pins": sorted(back_pins, key=pin_sort_key),
        "neutral_front_token": neutral_front,
        "neutral_back_token": neutral_back,
        "front_only": False,
    }
