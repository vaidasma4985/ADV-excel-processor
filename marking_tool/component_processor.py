from __future__ import annotations

from io import BytesIO
from pathlib import Path
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


def _build_component_production_df(component_marking_df: pd.DataFrame) -> pd.DataFrame:
    """Build the production-check sheet data with a dedicated Marked column."""
    production_df = pd.DataFrame(index=component_marking_df.index)
    for column_name in ("Name", "TYPE", "Quantity", "Total quantity"):
        if column_name in component_marking_df.columns:
            production_df[column_name] = component_marking_df[column_name]
        else:
            production_df[column_name] = ""
    production_df["Marked"] = ""
    return production_df.loc[:, ["Name", "TYPE", "Quantity", "Total quantity", "Marked"]].reset_index(drop=True)


def _merge_relay_rows_for_production(
    component_marking_df: pd.DataFrame,
) -> tuple[pd.DataFrame, int, list[str]]:
    """Merge relay rows by Name for production output only."""
    if component_marking_df.empty or "Category" not in component_marking_df.columns or "Name" not in component_marking_df.columns:
        return component_marking_df.copy().reset_index(drop=True), 0, []

    ordered_component_df = component_marking_df.copy().reset_index(drop=True)
    ordered_component_df["_original_order"] = range(len(ordered_component_df))
    relay_categories = {"RELAY_4P", "RELAY_2P"}
    relay_df = ordered_component_df.loc[ordered_component_df["Category"].isin(relay_categories)].copy()
    non_relay_df = ordered_component_df.loc[~ordered_component_df["Category"].isin(relay_categories)].copy()

    if relay_df.empty:
        return ordered_component_df.drop(columns=["_original_order"]).reset_index(drop=True), 0, []
    merged_rows: list[dict[str, Any]] = []
    merge_warnings: list[str] = []
    merged_group_count = 0

    for name_value, name_group_df in relay_df.groupby("Name", sort=False, dropna=False):
        ordered_group_df = name_group_df.sort_values("_original_order", kind="mergesort").reset_index(drop=True)
        first_row = ordered_group_df.iloc[0].to_dict()

        seen_types: set[str] = set()
        merged_types: list[str] = []
        for type_value in ordered_group_df.get("TYPE", pd.Series(dtype=object)).tolist():
            normalized_type = _stringify_cell(type_value)
            if normalized_type and normalized_type not in seen_types:
                seen_types.add(normalized_type)
                merged_types.append(normalized_type)

        first_row["TYPE"] = "+".join(merged_types)

        for quantity_column in ("Quantity", "Total quantity"):
            if quantity_column not in ordered_group_df.columns:
                continue
            quantity_values = [_stringify_cell(value) for value in ordered_group_df[quantity_column].tolist()]
            distinct_values = list(dict.fromkeys(quantity_values))
            first_row[quantity_column] = quantity_values[0] if quantity_values else ""
            if len(distinct_values) > 1:
                merge_warnings.append(
                    f"relay merge warning: conflicting {quantity_column} for Name `{_stringify_cell(name_value)}` -> kept first value `{first_row[quantity_column]}`"
                )

        first_row["_original_order"] = int(ordered_group_df["_original_order"].iloc[0])
        merged_rows.append(first_row)
        if len(ordered_group_df) > 1:
            merged_group_count += 1

    merged_relay_df = pd.DataFrame(merged_rows)
    combined_df = pd.concat([non_relay_df, merged_relay_df], ignore_index=True, sort=False)

    if "_original_order" not in combined_df.columns:
        combined_df["_original_order"] = range(len(combined_df))

    combined_df = combined_df.sort_values("_original_order", kind="mergesort").drop(columns=["_original_order"]).reset_index(drop=True)
    return combined_df, merged_group_count, merge_warnings


def _build_component_production_filename(file_name: str) -> str:
    """Build a stable filename for the separate production workbook."""
    base_name = Path(file_name or "component_marking").stem or "component_marking"
    return f"{base_name}_production_check.xlsx"


def _export_component_production_workbook(production_df: pd.DataFrame) -> bytes:
    """Export a separate production workbook with manual 1/0 marking cells."""
    try:
        import xlsxwriter
    except ModuleNotFoundError as exc:
        raise RuntimeError("xlsxwriter is required for component production workbook export") from exc

    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    worksheet = workbook.add_worksheet("Production check")

    header_format = workbook.add_format(
        {
            "bold": True,
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        }
    )
    text_format = workbook.add_format({"border": 1, "valign": "vcenter"})
    marked_format = workbook.add_format({"border": 1, "align": "center", "valign": "vcenter"})
    green_row_format = workbook.add_format({"bg_color": "#C6EFCE", "border": 1})
    red_row_format = workbook.add_format({"bg_color": "#F4CCCC", "border": 1})

    columns = ["Name", "TYPE", "Quantity", "Total quantity", "Marked"]
    column_widths = {
        "Name": 28,
        "TYPE": 24,
        "Quantity": 12,
        "Total quantity": 14,
        "Marked": 10,
    }
    marked_col_index = columns.index("Marked")

    for col_index, column_name in enumerate(columns):
        worksheet.write(0, col_index, column_name, header_format)
        worksheet.set_column(col_index, col_index, column_widths[column_name])
    worksheet.write_comment(0, marked_col_index, "1 = Marked\n0 = Missing")

    worksheet.freeze_panes(1, 0)

    for row_offset, row_values in enumerate(production_df[columns].itertuples(index=False, name=None), start=1):
        worksheet.set_row(row_offset, 20)
        worksheet.write(row_offset, 0, _stringify_cell(row_values[0]), text_format)
        worksheet.write(row_offset, 1, _stringify_cell(row_values[1]), text_format)
        worksheet.write(row_offset, 2, _stringify_cell(row_values[2]), text_format)
        worksheet.write(row_offset, 3, _stringify_cell(row_values[3]), text_format)
        worksheet.write_blank(row_offset, marked_col_index, None, marked_format)

    last_data_row = len(production_df)
    if last_data_row >= 1:
        worksheet.conditional_format(
            1,
            0,
            last_data_row,
            len(columns) - 1,
            {
                "type": "formula",
                "criteria": f"=${chr(ord('A') + marked_col_index)}2=1",
                "format": green_row_format,
            },
        )
        worksheet.conditional_format(
            1,
            0,
            last_data_row,
            len(columns) - 1,
            {
                "type": "formula",
                "criteria": f"=${chr(ord('A') + marked_col_index)}2=0",
                "format": red_row_format,
            },
        )

    workbook.close()
    output.seek(0)
    return output.getvalue()


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

    production_source_df, merged_relay_group_count, relay_merge_warnings = _merge_relay_rows_for_production(component_marking_df)
    production_df = _build_component_production_df(production_source_df)
    production_workbook_bytes = _export_component_production_workbook(production_df)
    category_counts = component_marking_df["Category"].value_counts(dropna=False)

    developer_debug_messages.append(f"component parser: moved {len(unused_df)} rows to Unused")
    developer_debug_messages.append(f"component parser: FUSE rows -> {int(category_counts.get('FUSE', 0))}")
    developer_debug_messages.append(f"component parser: RELAY_4P rows -> {int(category_counts.get('RELAY_4P', 0))}")
    developer_debug_messages.append(f"component parser: RELAY_2P rows -> {int(category_counts.get('RELAY_2P', 0))}")
    developer_debug_messages.append(f"component parser: OTHER rows -> {int(category_counts.get('OTHER', 0))}")
    developer_debug_messages.append(f"component parser: final component rows -> {len(component_marking_df)}")
    developer_debug_messages.append(f"component parser: final unused rows -> {len(unused_df)}")
    developer_debug_messages.append(f"relay rows merged by Name: {merged_relay_group_count}")
    developer_debug_messages.append(
        "relay merge warnings: "
        + (" | ".join(relay_merge_warnings) if relay_merge_warnings else "none")
    )
    developer_debug_messages.append("production workbook header note added to Marked")
    developer_debug_messages.append("component production workbook created")
    developer_debug_messages.append(f"production rows exported: {len(production_df)}")
    developer_debug_messages.append("production workbook uses filtered Component Marking rows only")

    user_info_messages = [
        "component input processed successfully",
        f"component rows exported: {len(component_marking_df)}",
        f"unused component rows exported: {len(unused_df)}",
        "component production workbook created",
        f"production rows exported: {len(production_df)}",
        "production workbook uses filtered Component Marking rows only",
    ]

    return {
        "sheets": {
            "Component Marking": component_marking_df,
            "Unused": unused_df,
        },
        "user_info_messages": user_info_messages,
        "developer_debug_messages": developer_debug_messages,
        "debug_workbook": None,
        "production_workbook": production_workbook_bytes,
        "production_filename": _build_component_production_filename(file_name),
        "source_file": file_name or "uploaded_file",
    }
