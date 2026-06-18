from __future__ import annotations

from io import BytesIO
import re
from typing import Any

import pandas as pd


CABLE_MARKING_COLUMNS = ["Cable"]
POWER_WIRE_COLUMNS = ["Power Wire"]

_CABLE_NAME_PATTERN = re.compile(r"^(?:\+(?P<cabinet>[^/]+)/)?(?P<marking>-W\d+)$")
_NATURAL_MARKING_PATTERN = re.compile(r"^(-W)(\d+)$")
_NATURAL_CABINET_PATTERN = re.compile(r"^(\+)([A-Za-z]+)(\d+)$")


def _cell_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _natural_marking_key(marking: str) -> tuple[str, int, str]:
    match = _NATURAL_MARKING_PATTERN.match(marking)
    if not match:
        return (marking, 0, marking)
    return (match.group(1), int(match.group(2)), marking)


def _natural_cabinet_key(cabinet: str) -> tuple[str, str, int, str]:
    match = _NATURAL_CABINET_PATTERN.match(cabinet)
    if not match:
        return (cabinet, "", 0, cabinet)
    return (match.group(1), match.group(2), int(match.group(3)), cabinet)


def _empty_cables_df() -> pd.DataFrame:
    return pd.DataFrame(columns=CABLE_MARKING_COLUMNS)


def _empty_power_wires_df() -> pd.DataFrame:
    return pd.DataFrame(columns=POWER_WIRE_COLUMNS)


def _build_cables_df(markings: list[str]) -> pd.DataFrame:
    sorted_markings = sorted(set(markings), key=_natural_marking_key)
    duplicated_markings = [
        marking
        for marking in sorted_markings
        for _ in range(2)
    ]
    return pd.DataFrame(
        [{"Cable": marking} for marking in duplicated_markings],
        columns=CABLE_MARKING_COLUMNS,
    )


def _build_power_wires_df() -> pd.DataFrame:
    return _empty_power_wires_df()


def build_cable_marking_result(
    file_bytes: bytes | None,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Build the first real Cable Marking block from the uploaded wire workbook."""
    if not file_bytes:
        return (
            _empty_cables_df(),
            _empty_power_wires_df(),
            [],
            [],
            ["wire cable marking: no file bytes supplied"],
        )

    source_df = pd.read_excel(BytesIO(file_bytes))
    source_df = source_df.rename(columns=lambda column_name: str(column_name).strip())
    required_columns = {"Cb.name", "Line-Function"}
    missing_columns = sorted(required_columns - set(source_df.columns))
    if missing_columns:
        return (
            _empty_cables_df(),
            _empty_power_wires_df(),
            [],
            [],
            ["wire cable marking: missing required columns -> " + ", ".join(missing_columns)],
        )

    markings: list[str] = []
    markings_by_cabinet: dict[str, list[str]] = {}
    for _, row in source_df.iterrows():
        cb_name = _cell_text(row.get("Cb.name"))
        if not cb_name:
            continue
        if _cell_text(row.get("Line-Function")).casefold() != "internal cable":
            continue

        match = _CABLE_NAME_PATTERN.match(cb_name)
        if not match:
            continue

        cabinet = match.group("cabinet")
        marking = match.group("marking")
        markings.append(marking)
        if cabinet:
            markings_by_cabinet.setdefault(f"+{cabinet}", []).append(marking)

    cables_df = _build_cables_df(markings)
    power_wires_df = _build_power_wires_df()
    sorted_cabinets = sorted(markings_by_cabinet, key=_natural_cabinet_key)
    cable_blocks: list[dict[str, Any]] = []
    power_wire_blocks: list[dict[str, Any]] = []
    if len(sorted_cabinets) > 1:
        assigned_marking_count = sum(len(cabinet_markings) for cabinet_markings in markings_by_cabinet.values())
        if assigned_marking_count == len(markings):
            for cabinet in sorted_cabinets:
                cable_blocks.append(
                    {
                        "cabinet": cabinet,
                        "title": f"{cabinet} - CABLES",
                        "subtitle": "Phoenix WML 6",
                        "df": _build_cables_df(markings_by_cabinet[cabinet]),
                    }
                )
                power_wire_blocks.append(
                    {
                        "cabinet": cabinet,
                        "title": f"{cabinet} - POWER WIRES",
                        "subtitle": "Phoenix UC-WMT (15x4)",
                        "df": _build_power_wires_df(),
                    }
                )

    debug_messages = [
        "wire cable marking: "
        + f"{len(source_df)} rows scanned, {len(markings)} valid cable rows, "
        + f"{len(set(markings))} unique cable markings"
    ]
    if cable_blocks:
        debug_messages.append(
            "wire cable marking: multiple cabinets detected ("
            + ", ".join(sorted_cabinets)
            + ") -> side-by-side Cable Marking blocks enabled"
        )
    elif len(sorted_cabinets) > 1:
        debug_messages.append(
            "wire cable marking: multiple cabinets detected ("
            + ", ".join(sorted_cabinets)
            + ") with uncabineted cable rows -> using existing combined CABLES block"
        )

    return cables_df, power_wires_df, cable_blocks, power_wire_blocks, debug_messages
