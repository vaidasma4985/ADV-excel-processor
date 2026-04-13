from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd


PLACEHOLDER_FILENAME = "Markings_placeholder.xlsx"

_SOURCE_LABELS = {
    "component": ("Component Marking", "component input"),
    "terminal": ("Terminal Marking", "terminal input"),
    "wire": ("Cable Marking", "wire input"),
}

_TERMINAL_EXPECTED_COLUMNS = {
    "name": "Name",
    "conns": "Conns.",
    "group sorting": "Group Sorting",
}


def _normalize_column_name(value: Any) -> str:
    """Return a simple normalized column label for matching."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return " ".join(text.replace("\n", " ").split()).lower()


def parse_terminal_input(file_bytes: bytes) -> tuple[pd.DataFrame, list[str]]:
    """Parse terminal Excel input into a clean DataFrame without applying business rules."""
    debug_info: list[str] = []

    if not file_bytes:
        return pd.DataFrame(columns=list(_TERMINAL_EXPECTED_COLUMNS.values())), ["terminal parser: no file bytes provided"]

    try:
        raw_df = pd.read_excel(BytesIO(file_bytes), sheet_name=0)
    except Exception as exc:
        debug_info.append(f"terminal parser: failed to read Excel file ({exc})")
        return pd.DataFrame(columns=list(_TERMINAL_EXPECTED_COLUMNS.values())), debug_info

    if raw_df is None:
        debug_info.append("terminal parser: pandas returned no data")
        return pd.DataFrame(columns=list(_TERMINAL_EXPECTED_COLUMNS.values())), debug_info

    raw_df = raw_df.dropna(how="all").copy()
    raw_non_empty_rows = len(raw_df)

    normalized_to_original: dict[str, str] = {}
    cleaned_columns: list[str] = []
    for column in raw_df.columns:
        normalized_name = _normalize_column_name(column)
        cleaned_name = " ".join(str(column).strip().split()) if str(column).strip() else str(column).strip()
        cleaned_columns.append(cleaned_name)
        if normalized_name and normalized_name not in normalized_to_original:
            normalized_to_original[normalized_name] = cleaned_name

    raw_df.columns = cleaned_columns

    selected_columns: list[str] = []
    rename_map: dict[str, str] = {}
    missing_columns: list[str] = []

    for normalized_name, output_name in _TERMINAL_EXPECTED_COLUMNS.items():
        matched_column = normalized_to_original.get(normalized_name)
        if matched_column:
            selected_columns.append(matched_column)
            rename_map[matched_column] = output_name
        else:
            missing_columns.append(output_name)

    found_columns = [rename_map[column_name] for column_name in selected_columns]

    if selected_columns:
        terminal_df = raw_df.loc[:, selected_columns].rename(columns=rename_map).copy()
    else:
        terminal_df = pd.DataFrame()

    if "Name" in terminal_df.columns:
        terminal_df["Name"] = terminal_df["Name"].apply(lambda value: "" if pd.isna(value) else str(value).strip())
        terminal_df = terminal_df[terminal_df["Name"] != ""].reset_index(drop=True)
        rows_after_name_filter = len(terminal_df)
    else:
        rows_after_name_filter = len(terminal_df)

    debug_info.append(f"terminal parser: loaded {raw_non_empty_rows} non-empty rows from first sheet")
    debug_info.append(
        "terminal parser: found expected columns -> "
        + (", ".join(found_columns) if found_columns else "none")
    )
    debug_info.append(
        "terminal parser: missing expected columns -> "
        + (", ".join(missing_columns) if missing_columns else "none")
    )

    if "Name" in terminal_df.columns:
        debug_info.append(f"terminal parser: kept {rows_after_name_filter} rows with non-empty Name")
        preview_names = terminal_df["Name"].head(5).tolist()
        debug_info.append(
            "terminal parser: first 5 Name values -> "
            + (", ".join(preview_names) if preview_names else "none")
        )
    else:
        debug_info.append("terminal parser: Name column missing, so row filtering by terminal name was skipped")

    return terminal_df, debug_info


def build_placeholder_results(inputs: dict[str, dict[str, Any]]) -> tuple[dict[str, pd.DataFrame], list[str], list[str]]:
    """Build placeholder output sheets only for uploaded file types."""
    sheets: dict[str, pd.DataFrame] = {}
    warnings: list[str] = []
    debug_info: list[str] = []

    for source_key in ("component", "terminal", "wire"):
        file_info = inputs.get(source_key, {})
        file_bytes = file_info.get("bytes")
        file_name = (file_info.get("name") or "").strip()
        sheet_name, source_label = _SOURCE_LABELS[source_key]

        if file_bytes:
            terminal_df = None
            if source_key == "terminal":
                terminal_df, terminal_debug = parse_terminal_input(file_bytes)
                debug_info.extend(terminal_debug)
                if terminal_df is not None and not terminal_df.empty:
                    sheets[sheet_name] = terminal_df
                else:
                    sheets[sheet_name] = pd.DataFrame(
                        [
                            {
                                "source_file": file_name or "uploaded_file",
                                "source_type": source_label,
                                "status": "placeholder_generated",
                                "note": "Placeholder output only. Real marking rules are not implemented yet.",
                                "parsed_rows": len(terminal_df) if terminal_df is not None else "",
                            }
                        ]
                    )
            else:
                sheets[sheet_name] = pd.DataFrame(
                    [
                        {
                            "source_file": file_name or "uploaded_file",
                            "source_type": source_label,
                            "status": "placeholder_generated",
                            "note": "Placeholder output only. Real marking rules are not implemented yet.",
                            "parsed_rows": len(terminal_df) if terminal_df is not None else "",
                        }
                    ]
                )
            debug_info.append(f"{source_key}: uploaded `{file_name or 'uploaded_file'}` -> sheet `{sheet_name}`")
        else:
            warnings.append(f"{source_label.capitalize()} not uploaded. `{sheet_name}` sheet was skipped.")
            debug_info.append(f"{source_key}: missing upload -> sheet skipped")

    return sheets, warnings, debug_info


def export_placeholder_workbook(sheets: dict[str, pd.DataFrame]) -> bytes:
    """Write available placeholder sheets to one Excel workbook in memory."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    output.seek(0)
    return output.getvalue()
