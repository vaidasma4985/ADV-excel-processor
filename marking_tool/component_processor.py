from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd


_COMPONENT_EXPECTED_COLUMNS = {
    "name": "Name",
    "type": "TYPE",
    "quantity": "Quantity",
    "total quantity": "Total quantity",
}

_FUSE_TYPES = {
    "2002-1611/1000-541",
    "2002-1611/1000-836",
}

_RELAY_4P_TYPES = {
    "RXM4GB2P7",
    "RXM4GB2BD",
    "RXZE2S114M",
}

_RELAY_2P_TYPES = {
    "RXG22BD",
    "RXG22P7",
    "RGZE1S48M",
}


def _normalize_column_name(value: Any) -> str:
    """Return a simple normalized column label for matching."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    normalized = " ".join(text.replace("\n", " ").split()).lower()
    return normalized.replace(".", "")


def _stringify_cell(value: Any) -> str:
    """Convert a cell value to a simple trimmed string."""
    if pd.isna(value):
        return ""
    return str(value).strip()


def _load_component_input(file_bytes: bytes) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Read the first sheet, drop fully empty rows, and retain expected columns if present."""
    developer_debug_messages: list[str] = []
    raw_df = pd.read_excel(BytesIO(file_bytes), sheet_name=0, dtype=object)
    raw_df = raw_df.dropna(axis=0, how="all").reset_index(drop=True)
    developer_debug_messages.append(f"component parser: loaded {len(raw_df)} non-empty rows from first sheet")

    normalized_columns = {
        _normalize_column_name(column_name): column_name
        for column_name in raw_df.columns
    }
    found_columns = [
        canonical_name
        for normalized_name, canonical_name in _COMPONENT_EXPECTED_COLUMNS.items()
        if normalized_name in normalized_columns
    ]
    missing_columns = [
        canonical_name
        for normalized_name, canonical_name in _COMPONENT_EXPECTED_COLUMNS.items()
        if normalized_name not in normalized_columns
    ]
    developer_debug_messages.append(
        "component parser: found expected columns -> "
        + (", ".join(found_columns) if found_columns else "none")
    )
    developer_debug_messages.append(
        "component parser: missing expected columns -> "
        + (", ".join(missing_columns) if missing_columns else "none")
    )

    selected_columns = [
        normalized_columns[normalized_name]
        for normalized_name in _COMPONENT_EXPECTED_COLUMNS
        if normalized_name in normalized_columns
    ]
    component_df = raw_df.loc[:, selected_columns].copy()
    component_df = component_df.rename(
        columns={
            normalized_columns[normalized_name]: canonical_name
            for normalized_name, canonical_name in _COMPONENT_EXPECTED_COLUMNS.items()
            if normalized_name in normalized_columns
        }
    )

    for column_name in component_df.columns:
        if component_df[column_name].dtype == object:
            component_df[column_name] = component_df[column_name].map(
                lambda value: _stringify_cell(value) if pd.notna(value) else value
            )

    return component_df, found_columns, developer_debug_messages


def _is_unused_component_name(name: Any) -> bool:
    """Apply the requested conservative Unused split rules."""
    text = _stringify_cell(name)
    if text == "":
        return True
    if text.startswith("+"):
        return True
    if text.startswith("-B"):
        return True
    if text.startswith("-W"):
        return True
    if text.startswith("-M") and not text.startswith("-M92"):
        return True
    if text.startswith("-X") and not text.startswith("-X921"):
        return True
    return False


def _normalize_component_type(value: Any) -> str:
    """Normalize TYPE values conservatively for classification."""
    return _stringify_cell(value).upper()


def _classify_component_type(value: Any) -> str:
    """Classify component rows by normalized TYPE."""
    normalized_type = _normalize_component_type(value)
    if normalized_type in _FUSE_TYPES:
        return "FUSE"
    if normalized_type in _RELAY_4P_TYPES:
        return "RELAY_4P"
    if normalized_type in _RELAY_2P_TYPES:
        return "RELAY_2P"
    return "OTHER"


def process_component_result(file_bytes: bytes, file_name: str) -> dict[str, Any]:
    """Parse the component workbook and split rows into Component Marking and Unused."""
    component_df, _, developer_debug_messages = _load_component_input(file_bytes)

    if "Name" in component_df.columns:
        unused_mask = component_df["Name"].map(_is_unused_component_name)
    else:
        unused_mask = pd.Series(True, index=component_df.index)

    unused_df = component_df.loc[unused_mask].reset_index(drop=True)
    component_marking_df = component_df.loc[~unused_mask].reset_index(drop=True)

    if "TYPE" in component_marking_df.columns:
        component_marking_df["Category"] = component_marking_df["TYPE"].map(_classify_component_type)
    else:
        component_marking_df["Category"] = "OTHER"

    category_counts = component_marking_df["Category"].value_counts(dropna=False)

    developer_debug_messages.append(f"component parser: moved {len(unused_df)} rows to Unused")
    developer_debug_messages.append(f"component parser: FUSE rows -> {int(category_counts.get('FUSE', 0))}")
    developer_debug_messages.append(f"component parser: RELAY_4P rows -> {int(category_counts.get('RELAY_4P', 0))}")
    developer_debug_messages.append(f"component parser: RELAY_2P rows -> {int(category_counts.get('RELAY_2P', 0))}")
    developer_debug_messages.append(f"component parser: OTHER rows -> {int(category_counts.get('OTHER', 0))}")
    developer_debug_messages.append(f"component parser: final component rows -> {len(component_marking_df)}")
    developer_debug_messages.append(f"component parser: final unused rows -> {len(unused_df)}")

    user_info_messages = [
        "component input processed successfully",
        f"component rows exported: {len(component_marking_df)}",
        f"unused component rows exported: {len(unused_df)}",
    ]

    return {
        "sheets": {
            "Component Marking": component_marking_df,
            "Unused": unused_df,
        },
        "user_info_messages": user_info_messages,
        "developer_debug_messages": developer_debug_messages,
        "debug_workbook": None,
        "source_file": file_name or "uploaded_file",
    }
