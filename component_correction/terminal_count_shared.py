"""
SHARED MODULE

This file is used for Terminal TMB count logic.
It may be used by both Marking Tool and Component Correction.
Changing this logic can affect both parts.
"""

from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd


_TERMINAL_NUMERIC_CONN_PATTERN = re.compile(r"^\d+$")

TERMINAL_TYPE_SPECIAL_X6311 = "SPECIAL_X6311"
TERMINAL_TYPE_SPECIAL_GS_4010 = "SPECIAL_GS_4010"
TERMINAL_TYPE_SIGNAL = "SIGNAL"
TERMINAL_TYPE_NORMAL = "NORMAL"

_TERMINAL_TYPE_MIDDLE_ROOTS = {"230VL", "24VDC", "TX-I", "TX-O", "D0/-"}
_TERMINAL_TYPE_BOTTOM_ROOTS = {"0VDC", "230VN", "GND", "0V"}


def _stringify_cell(value: Any) -> str:
    """Convert a cell value to a simple trimmed string."""
    if pd.isna(value):
        return ""
    return str(value).strip()


def _normalize_terminal_conns_root(value: Any) -> str:
    """Return the logical Conns. root used for placement decisions."""
    text = _stringify_cell(value)
    if _TERMINAL_NUMERIC_CONN_PATTERN.fullmatch(text):
        return text
    if text.startswith("0VDC"):
        return "0VDC"
    if text.startswith("230VN"):
        return "230VN"
    if text.startswith("230VL"):
        return "230VL"
    if text.startswith("24VDC"):
        return "24VDC"
    if text == "GND":
        return "GND"
    if text == "0V":
        return "0V"
    return text


def _get_numeric_conn_physical_slot(value: Any) -> str:
    """Return the physical TMB slot for pure numeric Conns. values."""
    text = _stringify_cell(value)
    if not _TERMINAL_NUMERIC_CONN_PATTERN.fullmatch(text):
        return ""

    numeric_value = int(text)
    modulo_value = numeric_value % 3
    if modulo_value == 1:
        return "TOP"
    if modulo_value == 2:
        return "MIDDLE"
    return "BOTTOM"


def _build_positional_numeric_rows(numeric_values: list) -> list[list[str]]:
    """Build TMB chunks that keep numeric Conns. values in their physical slots."""
    blocks: list[list[str]] = []
    current_block = ["", "", ""]
    current_block_index: int | None = None
    slot_indices = {"TOP": 0, "MIDDLE": 1, "BOTTOM": 2}

    for numeric_value in numeric_values:
        conns_value = _stringify_cell(numeric_value)
        physical_slot = _get_numeric_conn_physical_slot(conns_value)
        if not physical_slot:
            continue

        conn_number = int(conns_value)
        block_index = (conn_number - 1) // 3
        slot_index = slot_indices[physical_slot]
        if current_block_index is None:
            current_block_index = block_index
        if block_index != current_block_index or current_block[slot_index]:
            blocks.append(current_block)
            current_block = ["", "", ""]
            current_block_index = block_index
        current_block[slot_index] = conns_value

    if current_block_index is not None:
        blocks.append(current_block)
    return blocks


def _get_terminal_conn_floor_for_type_detection(value: Any) -> str:
    """Return the connection floor used by shared Terminal Type detection."""
    text = _stringify_cell(value)
    if _TERMINAL_NUMERIC_CONN_PATTERN.fullmatch(text):
        return "TOP"

    conns_root = _normalize_terminal_conns_root(text)
    if conns_root in _TERMINAL_TYPE_MIDDLE_ROOTS:
        return "MIDDLE"
    if conns_root in _TERMINAL_TYPE_BOTTOM_ROOTS:
        return "BOTTOM"
    return "TOP_OTHER"


def _is_x8_terminal_name(value: Any) -> bool:
    """Return whether a terminal name should keep the X*8 signal layout."""
    return bool(re.fullmatch(r"^-X.*8$", _stringify_cell(value)))


def classify_terminal_tmb_type(
    conns_values: list,
    *,
    group_sorting: str = "",
    terminal_name: str = "",
) -> str:
    """Classify one terminal group for TMB count behavior."""
    name_value = _stringify_cell(terminal_name)
    if name_value == "-X6311":
        return TERMINAL_TYPE_SPECIAL_X6311

    normalized_values = [_stringify_cell(conns_value) for conns_value in conns_values]
    conns_roots = [_normalize_terminal_conns_root(value) for value in normalized_values]
    has_numeric_conns = any(_TERMINAL_NUMERIC_CONN_PATTERN.fullmatch(value) for value in normalized_values)
    has_blank_conns = any(value == "" for value in normalized_values)
    if (
        _stringify_cell(group_sorting) == "4010"
        and "0VDC" in conns_roots
        and has_numeric_conns
        and has_blank_conns
    ):
        return TERMINAL_TYPE_SPECIAL_GS_4010

    numeric_conns_count = sum(1 for value in normalized_values if _TERMINAL_NUMERIC_CONN_PATTERN.fullmatch(value))
    has_middle_or_bottom_conns = any(
        _get_terminal_conn_floor_for_type_detection(value) in {"MIDDLE", "BOTTOM"}
        for value in normalized_values
    )
    if numeric_conns_count >= 3:
        if _is_x8_terminal_name(name_value):
            return TERMINAL_TYPE_SIGNAL
        if not has_middle_or_bottom_conns:
            return TERMINAL_TYPE_SIGNAL
    return TERMINAL_TYPE_NORMAL


def _count_non_empty_chunks(chunks: list[list[str]]) -> int:
    """Count chunks that contain at least one display value."""
    return sum(1 for chunk in chunks if any(_stringify_cell(value) for value in chunk))


def _count_flat_chunks(values: list[str]) -> int:
    """Count fallback chunks of three values, preserving blank rows."""
    return math.ceil(len(values) / 3) if values else 0


def _is_feeders_signals_group(group_sorting: Any, conns_values: list[str]) -> bool:
    """Return whether GS 5020/6010 should use the Feeders+signals TMB count."""
    if _stringify_cell(group_sorting) not in {"5020", "6010"}:
        return False

    conns_roots = [_normalize_terminal_conns_root(value) for value in conns_values]
    numeric_count = sum(1 for value in conns_values if _TERMINAL_NUMERIC_CONN_PATTERN.fullmatch(value))
    return bool(numeric_count >= 3 and "230VL" in conns_roots and "230VN" in conns_roots)


def _is_power_header_with_positional_numbers_group(
    *,
    conns_values: list[str],
    terminal_name: str,
    terminal_type: str,
) -> bool:
    """Return whether a normal group should use power-header positional numeric count."""
    if (_stringify_cell(terminal_type) or "NORMAL") != "NORMAL" or _is_x8_terminal_name(terminal_name):
        return False

    conns_roots = [_normalize_terminal_conns_root(value) for value in conns_values]
    return bool(
        "230VL" in conns_roots
        and "230VN" in conns_roots
        and any(_TERMINAL_NUMERIC_CONN_PATTERN.fullmatch(value) for value in conns_values)
    )


def _is_normal_numeric_position_group(
    *,
    conns_values: list[str],
    terminal_name: str,
    terminal_type: str,
) -> bool:
    """Return whether a normal numeric-only group should use physical TMB count."""
    if (_stringify_cell(terminal_type) or "NORMAL") != "NORMAL" or _is_x8_terminal_name(terminal_name):
        return False
    if not any(_TERMINAL_NUMERIC_CONN_PATTERN.fullmatch(value) for value in conns_values):
        return False
    return all(value == "" or _TERMINAL_NUMERIC_CONN_PATTERN.fullmatch(value) for value in conns_values)


def _count_feeders_signals_blocks(conns_values: list[str]) -> int:
    """Count GS 5020/6010 Feeders+signals TMB blocks."""
    terminal_numbers = [
        conns_value
        for conns_value in conns_values
        if _TERMINAL_NUMERIC_CONN_PATTERN.fullmatch(conns_value)
    ]
    voltage_230vl_values = [
        conns_value
        for conns_value in conns_values
        if _normalize_terminal_conns_root(conns_value) == "230VL"
    ]
    voltage_230vn_values = [
        conns_value
        for conns_value in conns_values
        if _normalize_terminal_conns_root(conns_value) == "230VN"
    ]
    other_values = [
        conns_value
        for conns_value in conns_values
        if not _TERMINAL_NUMERIC_CONN_PATTERN.fullmatch(conns_value)
        and _normalize_terminal_conns_root(conns_value) not in {"230VL", "230VN"}
    ]

    special_chunks = [["", voltage_230vl_values[0], voltage_230vn_values[0]]]
    special_chunks.extend(_build_positional_numeric_rows(terminal_numbers))
    trailing_values = [
        *other_values,
        *voltage_230vl_values[1:],
        *voltage_230vn_values[1:],
    ]
    special_chunks.extend(
        trailing_values[start_index:start_index + 3]
        for start_index in range(0, len(trailing_values), 3)
    )
    return _count_non_empty_chunks(special_chunks)


def _count_power_header_with_positional_numbers_blocks(conns_values: list[str]) -> int:
    """Count power-header positional TMB blocks."""
    used_indices: set[int] = set()

    def _first_index_matching(matcher: Any) -> int | None:
        for index, conns_value in enumerate(conns_values):
            if index not in used_indices and matcher(conns_value):
                return index
        return None

    blank_index = _first_index_matching(lambda value: _stringify_cell(value) == "")
    if blank_index is not None:
        used_indices.add(blank_index)
    voltage_230vl_index = _first_index_matching(
        lambda value: _normalize_terminal_conns_root(value) == "230VL"
    )
    if voltage_230vl_index is not None:
        used_indices.add(voltage_230vl_index)
    voltage_230vn_index = _first_index_matching(
        lambda value: _normalize_terminal_conns_root(value) == "230VN"
    )
    if voltage_230vn_index is not None:
        used_indices.add(voltage_230vn_index)

    numeric_values: list[str] = []
    other_values: list[str] = []
    for index, conns_value in enumerate(conns_values):
        if index in used_indices:
            continue
        if _TERMINAL_NUMERIC_CONN_PATTERN.fullmatch(conns_value):
            numeric_values.append(conns_value)
        else:
            other_values.append(conns_value)

    return 1 + _count_non_empty_chunks(_build_positional_numeric_rows(numeric_values)) + _count_flat_chunks(other_values)


def _count_normal_numeric_position_blocks(conns_values: list[str]) -> int:
    """Count normal numeric positional TMB blocks."""
    numeric_values = [
        conns_value
        for conns_value in conns_values
        if _TERMINAL_NUMERIC_CONN_PATTERN.fullmatch(conns_value)
    ]
    return _count_non_empty_chunks(_build_positional_numeric_rows(numeric_values))


def get_terminal_tmb_block_count_for_conns(
    conns_values: list,
    *,
    group_sorting: str = "",
    terminal_name: str = "",
    terminal_type: str = "",
) -> int:
    """Return the current TMB block count for a sequence of Conns. values."""
    normalized_values = [_stringify_cell(conns_value) for conns_value in conns_values]
    if not normalized_values:
        return 0

    resolved_terminal_type = _stringify_cell(terminal_type) or classify_terminal_tmb_type(
        normalized_values,
        group_sorting=group_sorting,
        terminal_name=terminal_name,
    )

    if _is_feeders_signals_group(group_sorting, normalized_values):
        return _count_feeders_signals_blocks(normalized_values)

    if resolved_terminal_type == TERMINAL_TYPE_SPECIAL_GS_4010:
        return _count_flat_chunks(normalized_values)

    # SPECIAL_X6311 currently changes order only, not count.
    if resolved_terminal_type == TERMINAL_TYPE_SPECIAL_X6311:
        return _count_flat_chunks(normalized_values)

    if _is_power_header_with_positional_numbers_group(
        conns_values=normalized_values,
        terminal_name=terminal_name,
        terminal_type=resolved_terminal_type,
    ):
        return _count_power_header_with_positional_numbers_blocks(normalized_values)

    if _is_normal_numeric_position_group(
        conns_values=normalized_values,
        terminal_name=terminal_name,
        terminal_type=resolved_terminal_type,
    ):
        return _count_normal_numeric_position_blocks(normalized_values)

    return _count_flat_chunks(normalized_values)
