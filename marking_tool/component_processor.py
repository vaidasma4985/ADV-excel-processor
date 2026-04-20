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

_COMPONENT_OPTIONAL_COLUMNS = {
    "description": "Description",
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

_PRODUCTION_COLUMNS = ["Name", "TYPE", "Quantity", "Marked", "Description"]
_RELAY_SECTION_LABEL = "Relays"
_FUSE_SECTION_LABEL = "Fuses"
_PRODUCTION_TECHNICAL_FLAG_COLUMN = "_IncludeInCalculation"


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

    found_optional_columns = [
        canonical_name
        for normalized_name, canonical_name in _COMPONENT_OPTIONAL_COLUMNS.items()
        if normalized_name in normalized_columns
    ]
    developer_debug_messages.append(
        "component parser: found optional columns -> "
        + (", ".join(found_optional_columns) if found_optional_columns else "none")
    )

    selected_columns = [
        normalized_columns[normalized_name]
        for normalized_name in _COMPONENT_EXPECTED_COLUMNS
        if normalized_name in normalized_columns
    ]
    selected_columns.extend(
        normalized_columns[normalized_name]
        for normalized_name in _COMPONENT_OPTIONAL_COLUMNS
        if normalized_name in normalized_columns
    )
    column_aliases = {**_COMPONENT_EXPECTED_COLUMNS, **_COMPONENT_OPTIONAL_COLUMNS}
    component_df = raw_df.loc[:, selected_columns].copy()
    component_df = component_df.rename(
        columns={
            normalized_columns[normalized_name]: canonical_name
            for normalized_name, canonical_name in column_aliases.items()
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


def _component_name_sort_key(value: Any) -> str:
    """Build a stable, case-insensitive Name sort key for grouped sections."""
    return _stringify_cell(value).casefold()


def _coerce_excel_number(value: Any) -> int | float | None:
    """Return a numeric value when Excel should store the cell as a number."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        numeric_value = float(value)
        return int(numeric_value) if numeric_value.is_integer() else numeric_value

    text = _stringify_cell(value).replace(" ", "")
    if not text:
        return None

    numeric_value = pd.to_numeric(text, errors="coerce")
    if pd.isna(numeric_value) and "," in text and "." not in text:
        numeric_value = pd.to_numeric(text.replace(",", "."), errors="coerce")
    if pd.isna(numeric_value):
        return None

    numeric_value = float(numeric_value)
    return int(numeric_value) if numeric_value.is_integer() else numeric_value


def _sort_grouped_component_rows(component_df: pd.DataFrame) -> pd.DataFrame:
    """Sort grouped component rows by Name while keeping equal names adjacent and stable."""
    if component_df.empty:
        return component_df.copy().reset_index(drop=True)

    sorted_df = component_df.copy()
    sorted_df["_name_sort_key"] = sorted_df["Name"].map(_component_name_sort_key)
    sorted_df = sorted_df.sort_values(
        by=["_name_sort_key", "_original_order"],
        kind="mergesort",
    ).drop(columns=["_name_sort_key"])
    return sorted_df.reset_index(drop=True)


def _build_production_section_row(label: str) -> dict[str, Any]:
    """Create a visual section row for grouped relay or fuse entries."""
    return {
        "Name": label,
        "TYPE": "",
        "Quantity": "",
        "Marked": "",
        "Description": "",
        "_is_section": True,
        _PRODUCTION_TECHNICAL_FLAG_COLUMN: 0,
    }


def _component_rows_to_production_records(component_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert actual component rows into production-sheet records."""
    if component_df.empty:
        return []

    production_rows = pd.DataFrame(index=component_df.index)
    for column_name in ("Name", "TYPE", "Quantity", "Description"):
        if column_name in component_df.columns:
            production_rows[column_name] = component_df[column_name]
        else:
            production_rows[column_name] = ""
    production_rows["Marked"] = ""
    production_rows["_is_section"] = False
    production_rows[_PRODUCTION_TECHNICAL_FLAG_COLUMN] = 1
    return production_rows.loc[:, [*_PRODUCTION_COLUMNS, "_is_section", _PRODUCTION_TECHNICAL_FLAG_COLUMN]].to_dict("records")


def _build_component_production_df(
    component_marking_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Build the production-check sheet rows without merging relay TYPE values."""
    if component_marking_df.empty:
        empty_df = pd.DataFrame(columns=[*_PRODUCTION_COLUMNS, "_is_section", _PRODUCTION_TECHNICAL_FLAG_COLUMN])
        return empty_df, {"relay_rows": 0, "fuse_rows": 0}

    working_df = component_marking_df.copy().reset_index(drop=True)
    for column_name in ("Name", "TYPE", "Quantity", "Description", "Category"):
        if column_name not in working_df.columns:
            working_df[column_name] = ""
    working_df["_original_order"] = range(len(working_df))

    relay_categories = {"RELAY_4P", "RELAY_2P"}
    relay_df = working_df.loc[working_df["Category"].isin(relay_categories)].copy()
    fuse_df = working_df.loc[working_df["Category"] == "FUSE"].copy()
    other_df = working_df.loc[
        ~working_df["Category"].isin(relay_categories | {"FUSE"})
    ].copy().sort_values("_original_order", kind="mergesort")

    ordered_records: list[dict[str, Any]] = []

    sorted_relay_df = _sort_grouped_component_rows(relay_df)
    if not sorted_relay_df.empty:
        ordered_records.append(_build_production_section_row(_RELAY_SECTION_LABEL))
        ordered_records.extend(_component_rows_to_production_records(sorted_relay_df))

    sorted_fuse_df = _sort_grouped_component_rows(fuse_df)
    if not sorted_fuse_df.empty:
        ordered_records.append(_build_production_section_row(_FUSE_SECTION_LABEL))
        ordered_records.extend(_component_rows_to_production_records(sorted_fuse_df))

    ordered_records.extend(_component_rows_to_production_records(other_df))

    production_df = pd.DataFrame(
        ordered_records,
        columns=[*_PRODUCTION_COLUMNS, "_is_section", _PRODUCTION_TECHNICAL_FLAG_COLUMN],
    )
    return production_df.reset_index(drop=True), {
        "relay_rows": len(sorted_relay_df),
        "fuse_rows": len(sorted_fuse_df),
    }


def _build_component_production_filename(file_name: str) -> str:
    """Build a stable filename for the separate production workbook."""
    base_name = Path(file_name or "component_marking").stem or "component_marking"
    return f"{base_name}_production_check.xlsx"


def _export_component_production_workbook(production_df: pd.DataFrame) -> bytes:
    """Export a separate production workbook with manual 1/0 marking cells."""
    try:
        import xlsxwriter
        from xlsxwriter.utility import xl_col_to_name
    except ModuleNotFoundError as exc:
        raise RuntimeError("xlsxwriter is required for component production workbook export") from exc

    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    production_sheet = workbook.add_worksheet("Production check")
    calculation_sheet = workbook.add_worksheet("Calculation")

    header_format = workbook.add_format(
        {
            "bold": True,
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        }
    )
    text_format = workbook.add_format({"border": 1, "valign": "vcenter"})
    quantity_format = workbook.add_format(
        {"border": 1, "align": "center", "valign": "vcenter", "num_format": "0.############"}
    )
    marked_format = workbook.add_format({"border": 1, "align": "center", "valign": "vcenter"})
    green_row_format = workbook.add_format({"bg_color": "#C6EFCE", "border": 1})
    red_row_format = workbook.add_format({"bg_color": "#F4CCCC", "border": 1})
    section_format = workbook.add_format(
        {"bold": True, "font_size": 13, "border": 1, "align": "left", "valign": "vcenter"}
    )
    calculation_text_format = workbook.add_format({"border": 1, "valign": "vcenter"})
    calculation_number_format = workbook.add_format(
        {"border": 1, "align": "center", "valign": "vcenter", "num_format": "0.############"}
    )
    marked_header_format = workbook.add_format(
        {"bold": True, "border": 1, "align": "center", "valign": "vcenter", "bg_color": "#C6EFCE"}
    )
    missing_header_format = workbook.add_format(
        {"bold": True, "border": 1, "align": "center", "valign": "vcenter", "bg_color": "#F4CCCC"}
    )
    marked_calculation_number_format = workbook.add_format(
        {"border": 1, "align": "center", "valign": "vcenter", "num_format": "0.############", "bg_color": "#C6EFCE"}
    )
    missing_calculation_number_format = workbook.add_format(
        {"border": 1, "align": "center", "valign": "vcenter", "num_format": "0.############", "bg_color": "#F4CCCC"}
    )
    technical_flag_format = workbook.add_format({"num_format": "0"})

    columns = list(_PRODUCTION_COLUMNS)
    column_widths = {
        "Name": 28,
        "TYPE": 24,
        "Quantity": 12,
        "Marked": 10,
        "Description": 42,
    }
    column_indexes = {column_name: column_index for column_index, column_name in enumerate(columns)}
    marked_col_index = column_indexes["Marked"]
    technical_flag_col_index = len(columns)

    for col_index, column_name in enumerate(columns):
        production_sheet.write(0, col_index, column_name, header_format)
        production_sheet.set_column(col_index, col_index, column_widths[column_name])
    production_sheet.write_comment(0, marked_col_index, "1 = Marked\n0 = Missing")
    production_sheet.write(0, technical_flag_col_index, _PRODUCTION_TECHNICAL_FLAG_COLUMN, header_format)
    production_sheet.set_column(technical_flag_col_index, technical_flag_col_index, None, None, {"hidden": True})

    production_sheet.freeze_panes(1, 0)

    for row_offset, row_data in enumerate(production_df.to_dict("records"), start=1):
        is_section_row = bool(row_data.get("_is_section"))
        production_sheet.set_row(row_offset, 24 if is_section_row else 20)

        include_flag = int(row_data.get(_PRODUCTION_TECHNICAL_FLAG_COLUMN, 0) or 0)
        production_sheet.write_number(row_offset, technical_flag_col_index, include_flag, technical_flag_format)

        if is_section_row:
            production_sheet.merge_range(
                row_offset,
                0,
                row_offset,
                len(columns) - 1,
                _stringify_cell(row_data.get("Name")),
                section_format,
            )
            continue

        for text_column in ("Name", "TYPE", "Description"):
            value = _stringify_cell(row_data.get(text_column))
            column_index = column_indexes[text_column]
            if value:
                production_sheet.write(row_offset, column_index, value, text_format)
            else:
                production_sheet.write_blank(row_offset, column_index, None, text_format)

        quantity_value = row_data.get("Quantity")
        quantity_column_index = column_indexes["Quantity"]
        numeric_quantity = _coerce_excel_number(quantity_value)
        if numeric_quantity is not None:
            production_sheet.write_number(row_offset, quantity_column_index, numeric_quantity, quantity_format)
        elif _stringify_cell(quantity_value):
            production_sheet.write(row_offset, quantity_column_index, _stringify_cell(quantity_value), quantity_format)
        else:
            production_sheet.write_blank(row_offset, quantity_column_index, None, quantity_format)

        marked_value = _stringify_cell(row_data.get("Marked"))
        if marked_value:
            numeric_marked = _coerce_excel_number(marked_value)
            if numeric_marked is not None:
                production_sheet.write_number(row_offset, marked_col_index, numeric_marked, marked_format)
            else:
                production_sheet.write(row_offset, marked_col_index, marked_value, marked_format)
        else:
            production_sheet.write_blank(row_offset, marked_col_index, None, marked_format)

    last_data_row = len(production_df)
    if last_data_row >= 1:
        marked_col_letter = xl_col_to_name(marked_col_index)
        technical_flag_col_letter = xl_col_to_name(technical_flag_col_index)
        production_sheet.conditional_format(
            1,
            0,
            last_data_row,
            len(columns) - 1,
            {
                "type": "formula",
                "criteria": f'=AND(${technical_flag_col_letter}2=1,${marked_col_letter}2<>"",${marked_col_letter}2=1)',
                "format": green_row_format,
            },
        )
        production_sheet.conditional_format(
            1,
            0,
            last_data_row,
            len(columns) - 1,
            {
                "type": "formula",
                "criteria": f'=AND(${technical_flag_col_letter}2=1,${marked_col_letter}2<>"",${marked_col_letter}2=0)',
                "format": red_row_format,
            },
        )

    calculation_columns = [
        "Type numeriai",
        "Total quantity",
        "Not Marked Quantity",
        "Marked Quantity",
        "Missing Quantity",
    ]
    calculation_widths = {
        "Type numeriai": 24,
        "Total quantity": 16,
        "Not Marked Quantity": 20,
        "Marked Quantity": 18,
        "Missing Quantity": 18,
    }
    for col_index, column_name in enumerate(calculation_columns):
        header_cell_format = header_format
        if column_name == "Marked Quantity":
            header_cell_format = marked_header_format
        elif column_name == "Missing Quantity":
            header_cell_format = missing_header_format
        calculation_sheet.write(0, col_index, column_name, header_cell_format)
        calculation_sheet.set_column(col_index, col_index, calculation_widths[column_name])
    calculation_sheet.freeze_panes(1, 0)

    actual_rows_df = production_df.loc[~production_df.get("_is_section", pd.Series(dtype=bool)).fillna(False)].copy()
    calculation_types = list(
        dict.fromkeys(actual_rows_df.get("TYPE", pd.Series(dtype=object)).map(_stringify_cell).tolist())
    )

    if calculation_types:
        last_excel_row = last_data_row + 1
        type_range = f"'Production check'!$B$2:$B${last_excel_row}"
        quantity_range = f"'Production check'!$C$2:$C${last_excel_row}"
        marked_range = f"'Production check'!$D$2:$D${last_excel_row}"
        include_range = f"'Production check'!${xl_col_to_name(technical_flag_col_index)}$2:${xl_col_to_name(technical_flag_col_index)}${last_excel_row}"

        for row_index, type_value in enumerate(calculation_types, start=1):
            calculation_sheet.write(row_index, 0, type_value, calculation_text_format)
            calculation_sheet.write_formula(
                row_index,
                1,
                f'=SUMIFS({quantity_range},{type_range},$A{row_index + 1},{include_range},1)',
                calculation_number_format,
            )
            calculation_sheet.write_formula(
                row_index,
                2,
                f"=B{row_index + 1}-D{row_index + 1}-E{row_index + 1}",
                calculation_number_format,
            )
            calculation_sheet.write_formula(
                row_index,
                3,
                f'=SUMIFS({quantity_range},{type_range},$A{row_index + 1},{include_range},1,{marked_range},1)',
                marked_calculation_number_format,
            )
            calculation_sheet.write_formula(
                row_index,
                4,
                f'=SUMIFS({quantity_range},{type_range},$A{row_index + 1},{include_range},1,{marked_range},0)',
                missing_calculation_number_format,
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

    production_df, grouped_row_counts = _build_component_production_df(component_marking_df)
    production_workbook_bytes = _export_component_production_workbook(production_df)
    category_counts = component_marking_df["Category"].value_counts(dropna=False)

    developer_debug_messages.append(f"component parser: moved {len(unused_df)} rows to Unused")
    developer_debug_messages.append(f"component parser: FUSE rows -> {int(category_counts.get('FUSE', 0))}")
    developer_debug_messages.append(f"component parser: RELAY_4P rows -> {int(category_counts.get('RELAY_4P', 0))}")
    developer_debug_messages.append(f"component parser: RELAY_2P rows -> {int(category_counts.get('RELAY_2P', 0))}")
    developer_debug_messages.append(f"component parser: OTHER rows -> {int(category_counts.get('OTHER', 0))}")
    developer_debug_messages.append(f"component parser: final component rows -> {len(component_marking_df)}")
    developer_debug_messages.append(f"component parser: final unused rows -> {len(unused_df)}")
    developer_debug_messages.append("relay TYPE merge removed from component production workbook")
    developer_debug_messages.append(f"grouped relay rows count: {grouped_row_counts['relay_rows']}")
    developer_debug_messages.append(f"grouped fuse rows count: {grouped_row_counts['fuse_rows']}")
    developer_debug_messages.append("production workbook header note added to Marked")
    developer_debug_messages.append("calculation sheet created")
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
