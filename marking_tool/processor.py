from __future__ import annotations

from io import BytesIO
import re
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
    "type": "TYPE",
}

_PROJECT_CODE_PATTERN = re.compile(r"^\s*(\d{4}-\d{3})\b")
_TERMINAL_NAME_A_PATTERN = re.compile(r"^(?P<prefix>-X)(?P<base>\d+)A(?P<order>\d+)$")
_TERMINAL_NAME_STANDARD_PATTERN = re.compile(r"^(?P<prefix>-X)(?P<base>\d+)(?P<order>\d)$")
_TERMINAL_MIDDLE_CONN_VALUES = {"230VL", "24VDC", "24VDC1", "24VDC2"}


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


def _make_excel_text_safe(value: Any) -> str:
    """Keep exported values as plain strings for text-formatted Excel cells."""
    return _stringify_cell(value)


def derive_output_filename(terminal_file_name: str) -> str:
    """Build the output workbook filename from the uploaded terminal file name."""
    match = _PROJECT_CODE_PATTERN.match((terminal_file_name or "").strip())
    if not match:
        return "Markings.xlsx"
    return f"{match.group(1)}_Markings.xlsx"


def _terminal_name_sort_key(name: Any) -> tuple[int, int, int, str]:
    """Build a conservative sort key that keeps A-suffix terminals after normal ones."""
    text = _stringify_cell(name)

    a_match = _TERMINAL_NAME_A_PATTERN.fullmatch(text)
    if a_match:
        return (
            int(a_match.group("base")),
            1,
            int(a_match.group("order")),
            text,
        )

    standard_match = _TERMINAL_NAME_STANDARD_PATTERN.fullmatch(text)
    if standard_match:
        return (
            int(standard_match.group("base")),
            0,
            int(standard_match.group("order")),
            text,
        )

    return (10**9, 10**9, 10**9, text)


def _terminal_conns_sort_key(value: Any) -> tuple[int, int, str]:
    """Sort numeric connection labels first, then middle values, then text, then blanks, then 230VN."""
    text = _stringify_cell(value)
    if re.fullmatch(r"\d+", text):
        return (0, int(text), text)
    if text in _TERMINAL_MIDDLE_CONN_VALUES:
        return (1, 10**9, text)
    if text == "":
        return (3, 10**9, "")
    if text == "230VN":
        return (4, 10**9, text)
    return (2, 10**9, text)


def parse_terminal_input(file_bytes: bytes) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Parse terminal Excel input into a clean DataFrame with minimal filtering only."""
    user_info_messages: list[str] = []
    developer_debug_messages: list[str] = []

    if not file_bytes:
        return (
            pd.DataFrame(columns=list(_TERMINAL_EXPECTED_COLUMNS.values())),
            ["terminal input missing -> skipped"],
            ["terminal parser: no file bytes provided"],
        )

    try:
        raw_df = pd.read_excel(BytesIO(file_bytes), sheet_name=0)
    except Exception as exc:
        user_info_messages.append("terminal input could not be processed")
        developer_debug_messages.append(f"terminal parser: failed to read Excel file ({exc})")
        return pd.DataFrame(columns=list(_TERMINAL_EXPECTED_COLUMNS.values())), user_info_messages, developer_debug_messages

    if raw_df is None:
        user_info_messages.append("terminal input could not be processed")
        developer_debug_messages.append("terminal parser: pandas returned no data")
        return pd.DataFrame(columns=list(_TERMINAL_EXPECTED_COLUMNS.values())), user_info_messages, developer_debug_messages

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

    developer_debug_messages.append(f"terminal parser: loaded {raw_non_empty_rows} non-empty rows from first sheet")
    developer_debug_messages.append(
        "terminal parser: found expected columns -> "
        + (", ".join(found_columns) if found_columns else "none")
    )
    developer_debug_messages.append(
        "terminal parser: missing expected columns -> "
        + (", ".join(missing_columns) if missing_columns else "none")
    )

    for column_name in ("Name", "Conns.", "Group Sorting", "TYPE"):
        if column_name in terminal_df.columns:
            terminal_df[column_name] = terminal_df[column_name].apply(_stringify_cell)

    if "Name" not in terminal_df.columns or "Group Sorting" not in terminal_df.columns:
        user_info_messages.append("terminal input processed with missing required columns")
        user_info_messages.append(f"terminal rows exported: {len(terminal_df)}")
        developer_debug_messages.append("terminal parser: required filtering columns missing, so terminal row cleanup was skipped")
        developer_debug_messages.append(f"terminal parser: final terminal rows -> {len(terminal_df)}")
        preview_names = terminal_df["Name"].head(5).tolist() if "Name" in terminal_df.columns else []
        developer_debug_messages.append(
            "terminal parser: first 5 final Name values -> "
            + (", ".join(preview_names) if preview_names else "none")
        )
        return terminal_df.reset_index(drop=True), user_info_messages, developer_debug_messages

    raw_xtb_matches = int(terminal_df["Name"].str.startswith("-XTB", na=False).sum())
    non_empty_name_mask = terminal_df["Name"] != ""
    rows_with_non_empty_name = int(non_empty_name_mask.sum())
    terminal_df = terminal_df[non_empty_name_mask].copy()

    valid_group_mask = terminal_df["Group Sorting"].str.fullmatch(r"\d+")
    rows_with_numeric_group_sorting = int(valid_group_mask.sum())
    removed_non_numeric_group_sorting = int((~valid_group_mask).sum())
    terminal_df = terminal_df[valid_group_mask].copy()

    gs_7210_mask = terminal_df["Group Sorting"].eq("7210")
    removed_group_sorting_7210 = int(gs_7210_mask.sum())
    terminal_df = terminal_df[~gs_7210_mask].copy()

    xtb_mask = terminal_df["Name"].str.startswith("-XTB", na=False)
    removed_xtb = int(xtb_mask.sum())
    terminal_df = terminal_df[~xtb_mask].copy()

    xpe_mask = terminal_df["Name"].eq("-XPE")
    removed_xpe = int(xpe_mask.sum())
    terminal_df = terminal_df[~xpe_mask].copy().reset_index(drop=True)

    terminal_df["_group_sorting_sort"] = terminal_df["Group Sorting"].astype(int)
    terminal_df["_original_order"] = range(len(terminal_df))
    terminal_df["_terminal_name_sort"] = terminal_df["Name"].apply(_terminal_name_sort_key)
    if "Conns." in terminal_df.columns:
        terminal_df["_terminal_conns_sort"] = terminal_df["Conns."].apply(_terminal_conns_sort_key)
    else:
        terminal_df["_terminal_conns_sort"] = [(2, 10**9, "")] * len(terminal_df)
    terminal_df = terminal_df.sort_values(
        by=["_group_sorting_sort", "_terminal_name_sort", "Name", "_terminal_conns_sort", "_original_order"],
        kind="mergesort",
    ).drop(columns=["_group_sorting_sort", "_terminal_name_sort", "_terminal_conns_sort", "_original_order"]).reset_index(drop=True)

    user_info_messages.append("terminal input processed successfully")
    user_info_messages.append(f"terminal rows exported: {len(terminal_df)}")
    user_info_messages.append(
        "removed rows summary: "
        f"{removed_non_numeric_group_sorting + removed_group_sorting_7210 + removed_xtb + removed_xpe}"
    )

    developer_debug_messages.append(f"terminal parser: rows with non-empty Name -> {rows_with_non_empty_name}")
    developer_debug_messages.append(
        "terminal parser: rows with numeric Group Sorting after non-empty Name filter -> "
        f"{rows_with_numeric_group_sorting}"
    )
    developer_debug_messages.append(f"terminal parser: raw rows matching -XTB* by Name -> {raw_xtb_matches}")
    developer_debug_messages.append(f"terminal parser: removed {removed_non_numeric_group_sorting} rows due to non-numeric Group Sorting")
    developer_debug_messages.append(f"terminal parser: removed {removed_group_sorting_7210} rows due to Group Sorting == 7210")
    developer_debug_messages.append(f"terminal parser: removed {removed_xtb} rows due to Name startswith -XTB after earlier cleanup")
    developer_debug_messages.append(f"terminal parser: removed {removed_xpe} rows due to Name == -XPE after earlier cleanup")
    developer_debug_messages.append("terminal parser: applied GS/Name/Conns sorting")
    developer_debug_messages.append("terminal parser: applied middle-value sorting (230VL / 24VDC*)")
    developer_debug_messages.append("terminal parser: forced 230VN to end-of-block bottom position")
    developer_debug_messages.append(f"terminal parser: final terminal rows -> {len(terminal_df)}")

    preview_names = terminal_df["Name"].head(5).tolist()
    developer_debug_messages.append(
        "terminal parser: first 5 final Name values -> "
        + (", ".join(preview_names) if preview_names else "none")
    )
    sorted_preview_names = terminal_df["Name"].head(10).tolist()
    developer_debug_messages.append(
        "terminal parser: first 10 sorted Name values -> "
        + (", ".join(sorted_preview_names) if sorted_preview_names else "none")
    )
    preview_columns = [column_name for column_name in ("Group Sorting", "Name", "Conns.", "TYPE") if column_name in terminal_df.columns]
    preview_rows = terminal_df.loc[:, preview_columns].head(15).to_dict(orient="records") if preview_columns else []
    developer_debug_messages.append(
        "terminal parser: first 15 sorted rows preview -> "
        + (" | ".join(str(row) for row in preview_rows) if preview_rows else "none")
    )

    first_group_value = terminal_df["Group Sorting"].iloc[0] if not terminal_df.empty else ""
    first_group_df = terminal_df[terminal_df["Group Sorting"].eq(first_group_value)] if first_group_value != "" else pd.DataFrame()
    first_name_value = first_group_df["Name"].iloc[0] if not first_group_df.empty else ""
    first_name_conns = (
        first_group_df.loc[first_group_df["Name"].eq(first_name_value), "Conns."].head(10).tolist()
        if "Conns." in terminal_df.columns and first_name_value != ""
        else []
    )
    developer_debug_messages.append(
        "terminal parser: first 10 Conns. values for first Name in first GS group -> "
        + (", ".join(first_name_conns) if first_name_conns else "none")
    )

    return terminal_df, user_info_messages, developer_debug_messages


def build_placeholder_results(
    inputs: dict[str, dict[str, Any]]
) -> tuple[dict[str, pd.DataFrame], list[str], list[str], list[str]]:
    """Build placeholder output sheets only for uploaded file types."""
    sheets: dict[str, pd.DataFrame] = {}
    warnings: list[str] = []
    user_info_messages: list[str] = []
    developer_debug_messages: list[str] = []

    for source_key in ("component", "terminal", "wire"):
        file_info = inputs.get(source_key, {})
        file_bytes = file_info.get("bytes")
        file_name = (file_info.get("name") or "").strip()
        sheet_name, source_label = _SOURCE_LABELS[source_key]

        if file_bytes:
            terminal_df = None
            if source_key == "terminal":
                terminal_df, terminal_user_info, terminal_debug = parse_terminal_input(file_bytes)
                user_info_messages.extend(terminal_user_info)
                developer_debug_messages.extend(terminal_debug)
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
                user_info_messages.append(f"{source_label} uploaded -> placeholder sheet created")
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
            developer_debug_messages.append(f"{source_key}: uploaded `{file_name or 'uploaded_file'}` -> sheet `{sheet_name}`")
        else:
            warnings.append(f"{source_label.capitalize()} not uploaded. `{sheet_name}` sheet was skipped.")
            user_info_messages.append(f"{source_label} missing -> skipped")
            developer_debug_messages.append(f"{source_key}: missing upload -> sheet skipped")

    return sheets, warnings, user_info_messages, developer_debug_messages


def export_placeholder_workbook(sheets: dict[str, pd.DataFrame]) -> bytes:
    """Write available placeholder sheets to one Excel workbook in memory."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            export_df = df.copy()
            for column_name in export_df.columns:
                export_df[column_name] = export_df[column_name].apply(_make_excel_text_safe)
            export_df.to_excel(writer, sheet_name=sheet_name, index=False)
            worksheet = writer.book[sheet_name]
            for row in worksheet.iter_rows(min_row=2):
                for cell in row:
                    cell.number_format = "@"
                    if cell.value is None:
                        cell.value = ""
                    else:
                        cell.value = str(cell.value)
    output.seek(0)
    return output.getvalue()
