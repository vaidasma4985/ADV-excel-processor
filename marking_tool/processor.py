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
    "visible": "Visible",
}
_TERMINAL_OUTPUT_COLUMNS = [*_TERMINAL_EXPECTED_COLUMNS.values(), "Terminal Type"]

_PROJECT_CODE_PATTERN = re.compile(r"^\s*(\d{4}-\d{3})\b")
_TERMINAL_NAME_A_PATTERN = re.compile(r"^(?P<prefix>-X)(?P<base>\d+)A(?P<order>\d+)$")
_TERMINAL_NAME_STANDARD_PATTERN = re.compile(r"^(?P<prefix>-X)(?P<base>\d+)(?P<order>\d)$")
_TERMINAL_NUMERIC_CONN_PATTERN = re.compile(r"^\d+$")
_TERMINAL_STRIP_TERMINAL_SPACE = 5.27
_TERMINAL_STRIP_COVER_SPACE = 0.8
_TERMINAL_CONN_POSITION_MAP = {
    "RX-O": ("TOP", 1),
    "RX-I": ("TOP", 1),
    "D1/+": ("TOP", 1),
    "230VL": ("MIDDLE", 2),
    "24VDC": ("MIDDLE", 2),
    "24VDC1": ("MIDDLE", 2),
    "24VDC2": ("MIDDLE", 2),
    "TX-I": ("MIDDLE", 2),
    "TX-O": ("MIDDLE", 2),
    "D0/-": ("MIDDLE", 2),
    "0VDC": ("BOTTOM", 3),
    "230VN": ("BOTTOM", 3),
    "GND": ("BOTTOM", 3),
    "0V": ("BOTTOM", 3),
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


def _make_excel_text_safe(value: Any) -> str:
    """Keep exported values as plain strings for text-formatted Excel cells."""
    return _stringify_cell(value)


def _normalize_terminal_conns_value(value: Any) -> str:
    """Normalize terminal Conns. values without affecting other terminal fields."""
    text = _stringify_cell(value)
    if text == "0":
        return ""
    return text


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


def _get_terminal_conn_position(value: Any) -> tuple[str, int, str]:
    """Return deterministic connection placement derived from Supporting Data mapping."""
    text = _stringify_cell(value)
    if _TERMINAL_NUMERIC_CONN_PATTERN.fullmatch(text):
        return ("TOP", 1, text)
    floor, index = _TERMINAL_CONN_POSITION_MAP.get(text, ("TOP_OTHER", 1))
    return floor, index, text


def _terminal_conns_sort_key(value: Any) -> tuple[int, int, str]:
    """Build a stable base sort for later Name-local connection reordering."""
    text = _stringify_cell(value)
    if _TERMINAL_NUMERIC_CONN_PATTERN.fullmatch(text):
        return (0, int(text), text)
    if text == "":
        return (2, 10**9, text)

    floor, _, normalized_value = _get_terminal_conn_position(text)
    if floor in {"TOP", "TOP_OTHER"}:
        return (1, 10**9, normalized_value)
    if floor == "MIDDLE":
        return (3, 10**9, normalized_value)
    if floor == "BOTTOM":
        return (4, 10**9, text)
    return (1, 10**9, normalized_value)


def _reorder_terminal_name_group(group_df: pd.DataFrame) -> pd.DataFrame:
    """Reorder one exact Name group using its already detected Terminal Type."""
    if group_df.empty or "Conns." not in group_df.columns:
        return group_df

    terminal_type = (
        _stringify_cell(group_df["Terminal Type"].iloc[0])
        if "Terminal Type" in group_df.columns and not group_df.empty
        else "NORMAL"
    ) or "NORMAL"

    numeric_rows: list[pd.Series] = []
    top_like_rows: list[pd.Series] = []
    middle_rows: list[pd.Series] = []
    blank_rows: list[pd.Series] = []
    bottom_rows: list[pd.Series] = []

    for _, row in group_df.iterrows():
        conns_value = _stringify_cell(row.get("Conns.", ""))
        if _TERMINAL_NUMERIC_CONN_PATTERN.fullmatch(conns_value):
            numeric_rows.append(row)
        elif conns_value == "":
            blank_rows.append(row)
        else:
            floor, _, _ = _get_terminal_conn_position(conns_value)
            if floor == "MIDDLE":
                middle_rows.append(row)
            elif floor == "BOTTOM":
                bottom_rows.append(row)
            else:
                top_like_rows.append(row)

    numeric_rows = sorted(
        numeric_rows,
        key=lambda row: (
            int(_stringify_cell(row.get("Conns.", "0"))),
            _stringify_cell(row.get("Conns.", "")),
        ),
    )

    def _signal_style_rows(
        available_numeric_rows: list[pd.Series],
        available_top_like_rows: list[pd.Series],
        available_blank_rows: list[pd.Series],
        available_middle_rows: list[pd.Series],
        available_bottom_rows: list[pd.Series],
    ) -> list[pd.Series]:
        return [
            *available_numeric_rows,
            *available_top_like_rows,
            *available_blank_rows,
            *available_middle_rows,
            *available_bottom_rows,
        ]

    def _pop_first_matching_row(rows: list[pd.Series], matcher: Any) -> pd.Series | None:
        for index, row in enumerate(rows):
            if matcher(row):
                return rows.pop(index)
        return None

    reordered_rows: list[pd.Series]
    if terminal_type == "SPECIAL_GS_7030":
        remaining_numeric_rows = list(numeric_rows)
        remaining_top_like_rows = list(top_like_rows)
        remaining_blank_rows = list(blank_rows)
        remaining_middle_rows = list(middle_rows)
        remaining_bottom_rows = list(bottom_rows)

        first_blank_row = remaining_blank_rows.pop(0) if remaining_blank_rows else None
        first_230vl_row = _pop_first_matching_row(
            remaining_middle_rows,
            lambda row: _stringify_cell(row.get("Conns.", "")) == "230VL",
        )
        first_230vn_row = _pop_first_matching_row(
            remaining_bottom_rows,
            lambda row: _stringify_cell(row.get("Conns.", "")) == "230VN",
        )

        reordered_rows = [row for row in (first_blank_row, first_230vl_row, first_230vn_row) if row is not None]

        signal_like_rows = [*remaining_numeric_rows, *remaining_top_like_rows]
        while signal_like_rows or remaining_middle_rows or remaining_bottom_rows or remaining_blank_rows:
            next_signal_row = signal_like_rows.pop(0) if signal_like_rows else None
            next_230vl_row = _pop_first_matching_row(
                remaining_middle_rows,
                lambda row: _stringify_cell(row.get("Conns.", "")) == "230VL",
            )
            next_230vn_or_blank_row = _pop_first_matching_row(
                remaining_bottom_rows,
                lambda row: _stringify_cell(row.get("Conns.", "")) == "230VN",
            )
            if next_230vn_or_blank_row is None and remaining_blank_rows:
                next_230vn_or_blank_row = remaining_blank_rows.pop(0)

            triplet_rows = [row for row in (next_signal_row, next_230vl_row, next_230vn_or_blank_row) if row is not None]
            if not triplet_rows:
                break
            reordered_rows.extend(triplet_rows)

        remaining_unused_rows = [
            *remaining_middle_rows,
            *remaining_bottom_rows,
            *remaining_blank_rows,
        ]
        reordered_rows.extend(remaining_unused_rows)
    elif terminal_type == "SPECIAL_GS_4010":
        remaining_numeric_rows = list(numeric_rows)
        remaining_top_like_rows = list(top_like_rows)
        remaining_blank_rows = list(blank_rows)
        remaining_middle_rows = list(middle_rows)
        remaining_bottom_rows = list(bottom_rows)

        first_numeric_row = remaining_numeric_rows.pop(0) if remaining_numeric_rows else None
        first_blank_row = remaining_blank_rows.pop(0) if remaining_blank_rows else None
        zero_vdc_row = _pop_first_matching_row(
            remaining_bottom_rows,
            lambda row: _stringify_cell(row.get("Conns.", "")) == "0VDC",
        )

        reordered_rows = [row for row in (first_numeric_row, first_blank_row, zero_vdc_row) if row is not None]
        reordered_rows.extend(
            _signal_style_rows(
                remaining_numeric_rows,
                remaining_top_like_rows,
                remaining_blank_rows,
                remaining_middle_rows,
                remaining_bottom_rows,
            )
        )
    elif terminal_type == "SIGNAL":
        reordered_rows = _signal_style_rows(numeric_rows, top_like_rows, blank_rows, middle_rows, bottom_rows)
    else:
        normal_top_rows = [*numeric_rows, *top_like_rows]
        if not normal_top_rows and middle_rows and bottom_rows:
            reordered_rows = [
                *blank_rows,
                *middle_rows,
                *bottom_rows,
            ]
        else:
            first_top_row = normal_top_rows[0] if normal_top_rows else None
            remaining_top_rows = normal_top_rows[1:] if len(normal_top_rows) > 1 else []
            first_middle_row = middle_rows[0] if middle_rows else None
            remaining_middle_rows = middle_rows[1:] if len(middle_rows) > 1 else []
            reordered_rows = [
                *([first_top_row] if first_top_row is not None else []),
                *([first_middle_row] if first_middle_row is not None else []),
                *remaining_top_rows,
                *remaining_middle_rows,
                *blank_rows,
                *bottom_rows,
            ]

    if not reordered_rows:
        return group_df.iloc[0:0].copy()
    return pd.DataFrame(reordered_rows).reset_index(drop=True)


def _reorder_terminal_conns_by_name(terminal_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int], list[str], list[str], list[str]]:
    """Apply Terminal-Type-based Name-local ordering while preserving GS and Name group order."""
    if terminal_df.empty or "Name" not in terminal_df.columns or "Group Sorting" not in terminal_df.columns:
        return terminal_df, {}, [], [], []

    reordered_groups: list[pd.DataFrame] = []
    reordered_group_counts: dict[str, int] = {}
    first_reordered_groups: list[str] = []
    first_normal_groups: list[str] = []
    first_special_gs_7030_groups: list[str] = []
    for _, name_group_df in terminal_df.groupby(["Group Sorting", "Name"], sort=False, dropna=False):
        ordered_group_df = _reorder_terminal_name_group(name_group_df.reset_index(drop=True))
        reordered_groups.append(ordered_group_df)

        terminal_type = (
            _stringify_cell(ordered_group_df["Terminal Type"].iloc[0])
            if "Terminal Type" in ordered_group_df.columns and not ordered_group_df.empty
            else "NORMAL"
        ) or "NORMAL"
        reordered_group_counts[terminal_type] = reordered_group_counts.get(terminal_type, 0) + 1

        if len(first_reordered_groups) < 5:
            name_value = _stringify_cell(ordered_group_df["Name"].iloc[0]) if "Name" in ordered_group_df.columns and not ordered_group_df.empty else ""
            conns_preview = ", ".join(ordered_group_df["Conns."].head(10).tolist()) if "Conns." in ordered_group_df.columns else ""
            first_reordered_groups.append(f"{name_value} => {terminal_type}: [{conns_preview}]")
        if terminal_type == "NORMAL" and len(first_normal_groups) < 5:
            name_value = _stringify_cell(ordered_group_df["Name"].iloc[0]) if "Name" in ordered_group_df.columns and not ordered_group_df.empty else ""
            conns_preview = ", ".join(ordered_group_df["Conns."].head(10).tolist()) if "Conns." in ordered_group_df.columns else ""
            first_normal_groups.append(f"{name_value}: [{conns_preview}]")
        if terminal_type == "SPECIAL_GS_7030" and len(first_special_gs_7030_groups) < 3:
            name_value = _stringify_cell(ordered_group_df["Name"].iloc[0]) if "Name" in ordered_group_df.columns and not ordered_group_df.empty else ""
            conns_preview = ", ".join(ordered_group_df["Conns."].head(12).tolist()) if "Conns." in ordered_group_df.columns else ""
            first_special_gs_7030_groups.append(f"{name_value}: [{conns_preview}]")

    if not reordered_groups:
        return terminal_df.iloc[0:0].copy(), reordered_group_counts, first_reordered_groups, first_normal_groups, first_special_gs_7030_groups
    return pd.concat(reordered_groups, ignore_index=True), reordered_group_counts, first_reordered_groups, first_normal_groups, first_special_gs_7030_groups


def _classify_terminal_name_group(name_group_df: pd.DataFrame) -> str:
    """Classify one exact terminal Name group using the requested detection priority."""
    if name_group_df.empty:
        return "NORMAL"

    group_sorting_values = name_group_df["Group Sorting"].apply(_stringify_cell) if "Group Sorting" in name_group_df.columns else pd.Series(dtype=str)
    if group_sorting_values.eq("7030").any():
        return "SPECIAL_GS_7030"

    conns_values = name_group_df["Conns."].apply(_stringify_cell) if "Conns." in name_group_df.columns else pd.Series(dtype=str)
    is_group_sorting_4010 = bool(group_sorting_values.eq("4010").any())
    has_zero_vdc = bool(conns_values.eq("0VDC").any())
    has_numeric_conns = bool(conns_values.map(lambda value: bool(_TERMINAL_NUMERIC_CONN_PATTERN.fullmatch(value))).any())
    has_blank_conns = bool(conns_values.eq("").any())
    if is_group_sorting_4010 and has_zero_vdc and has_numeric_conns and has_blank_conns:
        return "SPECIAL_GS_4010"

    numeric_conns_count = int(conns_values.map(lambda value: bool(_TERMINAL_NUMERIC_CONN_PATTERN.fullmatch(value))).sum())
    if numeric_conns_count >= 3:
        return "SIGNAL"
    return "NORMAL"


def _apply_terminal_type_classification(terminal_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int], list[str], dict[str, int]]:
    """Add the Terminal Type column based on exact Name-group classification."""
    if terminal_df.empty or "Name" not in terminal_df.columns:
        classified_df = terminal_df.copy()
        if "Terminal Type" not in classified_df.columns:
            classified_df["Terminal Type"] = ""
        return classified_df, {}, [], {}

    classified_df = terminal_df.copy()
    group_types: dict[str, str] = {}
    detection_stats = {
        "special_gs_4010_groups": 0,
        "gs_4010_fallback_groups": 0,
    }
    for name_value, name_group_df in classified_df.groupby("Name", sort=False, dropna=False):
        group_type = _classify_terminal_name_group(name_group_df)
        group_types[name_value] = group_type
        group_sorting_values = (
            name_group_df["Group Sorting"].apply(_stringify_cell)
            if "Group Sorting" in name_group_df.columns
            else pd.Series(dtype=str)
        )
        if group_sorting_values.eq("4010").any():
            if group_type == "SPECIAL_GS_4010":
                detection_stats["special_gs_4010_groups"] += 1
            else:
                detection_stats["gs_4010_fallback_groups"] += 1
    classified_df["Terminal Type"] = classified_df["Name"].map(group_types).fillna("NORMAL")

    desired_columns = [column_name for column_name in ("Name", "Conns.", "Group Sorting", "TYPE") if column_name in classified_df.columns]
    desired_columns.append("Terminal Type")
    remaining_columns = [column_name for column_name in classified_df.columns if column_name not in desired_columns]
    classified_df = classified_df.loc[:, desired_columns + remaining_columns]

    type_counts = {
        terminal_type: int(count)
        for terminal_type, count in classified_df[["Name", "Terminal Type"]]
        .drop_duplicates(subset=["Name"])
        ["Terminal Type"]
        .value_counts(sort=False)
        .items()
    }

    first_classified_groups: list[str] = []
    for name_value, name_group_df in classified_df.groupby("Name", sort=False, dropna=False):
        if not name_value:
            continue
        terminal_type = _stringify_cell(name_group_df["Terminal Type"].iloc[0])
        group_sorting_preview = ", ".join(pd.unique(name_group_df["Group Sorting"]).tolist()) if "Group Sorting" in name_group_df.columns else ""
        conns_preview = ", ".join(name_group_df["Conns."].head(6).tolist()) if "Conns." in name_group_df.columns else ""
        first_classified_groups.append(
            f"{name_value} => {terminal_type} (GS: [{group_sorting_preview or 'none'}], Conns.: [{conns_preview or 'none'}])"
        )
        if len(first_classified_groups) >= 10:
            break

    return classified_df, type_counts, first_classified_groups, detection_stats


def _split_terminal_pe_rows(
    terminal_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int | list[str] | str]]:
    """Split PE rows out of the normal terminal stream and normalize them for later steps."""
    if terminal_df.empty or "Conns." not in terminal_df.columns:
        empty_pe_df = terminal_df.iloc[0:0].copy()
        if "Terminal Type" not in empty_pe_df.columns:
            empty_pe_df["Terminal Type"] = ""
        return terminal_df.copy(), empty_pe_df, {
            "detected_pe_rows": 0,
            "name_groups_with_pe": 0,
            "pe_gs_groups": [],
            "split_summary": "0 normal rows / 0 PE rows",
        }

    pe_mask = terminal_df["Conns."].apply(_stringify_cell).eq("\u23DA")
    detected_pe_rows = int(pe_mask.sum())

    normal_df = terminal_df.loc[~pe_mask].copy().reset_index(drop=True)
    pe_df = terminal_df.loc[pe_mask].copy().reset_index(drop=True)

    if "Terminal Type" not in normal_df.columns:
        normal_df["Terminal Type"] = ""
    if "Terminal Type" not in pe_df.columns:
        pe_df["Terminal Type"] = ""

    name_groups_with_pe = 0
    if detected_pe_rows and "Name" in terminal_df.columns:
        name_groups_with_pe = int(
            terminal_df.loc[pe_mask, "Name"].apply(_stringify_cell).nunique(dropna=True)
        )

    if not pe_df.empty:
        pe_df["Name"] = "PE"
        pe_df["Conns."] = "PE"
        pe_df["Terminal Type"] = "PE"

        pe_df["_group_sorting_sort"] = pe_df["Group Sorting"].astype(int)
        pe_df["_original_order"] = range(len(pe_df))
        pe_df = pe_df.sort_values(
            by=["_group_sorting_sort", "Group Sorting", "_original_order"],
            kind="mergesort",
        ).drop(columns=["_group_sorting_sort", "_original_order"]).reset_index(drop=True)

    pe_gs_groups = (
        pe_df["Group Sorting"].drop_duplicates().tolist()
        if not pe_df.empty and "Group Sorting" in pe_df.columns
        else []
    )

    return normal_df, pe_df, {
        "detected_pe_rows": detected_pe_rows,
        "name_groups_with_pe": name_groups_with_pe,
        "pe_gs_groups": pe_gs_groups[:10],
        "split_summary": f"{len(normal_df)} normal rows / {len(pe_df)} PE rows",
    }


def _build_terminal_tmb_sheet(terminal_df: pd.DataFrame) -> pd.DataFrame:
    """Repack already-prepared flat terminal rows into Top/Middle/Bottom chunks of 3."""
    tmb_columns = ["Terminal Name", "Top", "Middle", "Bottom"]
    if terminal_df.empty or "Name" not in terminal_df.columns:
        return pd.DataFrame(columns=tmb_columns)

    terminal_blocks = _build_terminal_blocks(terminal_df)
    tmb_rows = [
        {
            "Terminal Name": terminal_block["terminal_name"],
            "Top": terminal_block["chunk"][0] if len(terminal_block["chunk"]) >= 1 else "",
            "Middle": terminal_block["chunk"][1] if len(terminal_block["chunk"]) >= 2 else "",
            "Bottom": terminal_block["chunk"][2] if len(terminal_block["chunk"]) >= 3 else "",
        }
        for terminal_block in terminal_blocks
    ]
    return pd.DataFrame(tmb_rows, columns=tmb_columns)


def _build_terminal_blocks(terminal_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Build terminal blocks from the prepared flat terminal stream using the TMB chunking rules."""
    if terminal_df.empty or "Name" not in terminal_df.columns:
        return []

    tmb_rows: list[dict[str, str]] = []
    group_columns = ["Name"]
    if "Group Sorting" in terminal_df.columns:
        group_columns = ["Group Sorting", "Name"]

    for _, name_group_df in terminal_df.groupby(group_columns, sort=False, dropna=False):
        group_rows = name_group_df.reset_index(drop=True)
        terminal_name = _stringify_cell(group_rows["Name"].iloc[0]) if not group_rows.empty else ""
        group_sorting_value = (
            _stringify_cell(group_rows["Group Sorting"].iloc[0])
            if "Group Sorting" in group_rows.columns and not group_rows.empty
            else ""
        )
        terminal_type = (
            _stringify_cell(group_rows["Terminal Type"].iloc[0])
            if "Terminal Type" in group_rows.columns and not group_rows.empty
            else ""
        )
        conns_values = (
            group_rows["Conns."].apply(_stringify_cell).tolist()
            if "Conns." in group_rows.columns
            else [""] * len(group_rows)
        )
        source_indices = name_group_df.index.tolist()

        for start_index in range(0, len(conns_values), 3):
            chunk = conns_values[start_index:start_index + 3]
            tmb_rows.append(
                {
                    "terminal_name": terminal_name,
                    "group_sorting": group_sorting_value,
                    "terminal_type": terminal_type,
                    "chunk": chunk,
                    "end_row_index": source_indices[min(start_index + len(chunk) - 1, len(source_indices) - 1)],
                }
            )

    return tmb_rows


def _expand_terminal_pe_rows(
    terminal_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int | list[str]]]:
    """Expand PE contacts into flat terminal rows in multiples of 3 per GS."""
    if (
        terminal_df.empty
        or "Terminal Type" not in terminal_df.columns
        or "Group Sorting" not in terminal_df.columns
    ):
        return terminal_df.iloc[0:0].copy(), {
            "pe_group_count": 0,
            "generated_pe_flat_rows": 0,
            "first_pe_gs_groups": [],
            "plus_one_debug_messages": [],
        }

    pe_terminal_df = terminal_df.loc[
        terminal_df["Terminal Type"].apply(_stringify_cell).eq("PE")
    ].copy()
    if pe_terminal_df.empty:
        return pe_terminal_df, {
            "pe_group_count": 0,
            "generated_pe_flat_rows": 0,
            "first_pe_gs_groups": [],
            "plus_one_debug_messages": [],
        }

    pe_terminal_df["_group_sorting_sort"] = pe_terminal_df["Group Sorting"].astype(int)
    pe_terminal_df["_original_order"] = range(len(pe_terminal_df))
    pe_terminal_df = pe_terminal_df.sort_values(
        by=["_group_sorting_sort", "Group Sorting", "_original_order"],
        kind="mergesort",
    ).reset_index(drop=True)

    expanded_pe_rows: list[dict[str, Any]] = []
    first_pe_gs_groups: list[str] = []
    plus_one_debug_messages: list[str] = []
    pe_all_gs_values = set(pe_terminal_df["Group Sorting"].apply(_stringify_cell).tolist())
    for group_sorting_value, pe_group_df in pe_terminal_df.groupby("Group Sorting", sort=False, dropna=False):
        group_sorting_value = _stringify_cell(group_sorting_value)
        pe_contact_count = len(pe_group_df)
        pe_terminal_count = (pe_contact_count + 2) // 3
        if group_sorting_value == "5025":
            pe_terminal_count += 1
            plus_one_debug_messages.append("terminal pe: +1 PE applied for GS 5025")
        elif group_sorting_value == "5020" and "5025" not in pe_all_gs_values:
            pe_terminal_count += 1
            plus_one_debug_messages.append("terminal pe: +1 PE applied for GS 5020 (no 5025 present)")
        generated_row_count = pe_terminal_count * 3
        if len(first_pe_gs_groups) < 5:
            first_pe_gs_groups.append(
                f"GS {group_sorting_value} -> contacts={pe_contact_count}, terminals={pe_terminal_count}, rows={generated_row_count}"
            )
        template_row = pe_group_df.iloc[0].to_dict()
        for _ in range(generated_row_count):
            expanded_row = template_row.copy()
            expanded_row["Name"] = "PE"
            expanded_row["Conns."] = "PE"
            expanded_row["Group Sorting"] = group_sorting_value
            expanded_row["Terminal Type"] = "PE"
            expanded_pe_rows.append(expanded_row)

    expanded_pe_df = pd.DataFrame(expanded_pe_rows, columns=pe_terminal_df.columns)
    return expanded_pe_df, {
        "pe_group_count": int(pe_terminal_df["Group Sorting"].nunique()),
        "generated_pe_flat_rows": len(expanded_pe_df),
        "first_pe_gs_groups": first_pe_gs_groups,
        "plus_one_debug_messages": plus_one_debug_messages,
    }


def _build_terminal_tmb_sheet_with_debug(
    terminal_df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    """Build terminal TMB output from already-prepared flat terminal rows."""
    developer_debug_messages: list[str] = []
    terminal_tmb_df = _build_terminal_tmb_sheet(terminal_df)
    developer_debug_messages.append("terminal pe tmb: using flat Terminal Marking rows as the only PE source")
    return terminal_tmb_df, developer_debug_messages


def _build_terminal_tmb_count_map(terminal_df: pd.DataFrame) -> dict[tuple[str, str], int]:
    """Build a TMB terminal-unit count map keyed by (Group Sorting, Terminal Name)."""
    if terminal_df.empty:
        return {}

    tmb_count_map: dict[tuple[str, str], int] = {}
    for terminal_block in _build_terminal_blocks(terminal_df):
        group_sorting_value = _stringify_cell(terminal_block.get("group_sorting", ""))
        terminal_name = _stringify_cell(terminal_block.get("terminal_name", ""))
        key = (group_sorting_value, terminal_name)
        tmb_count_map[key] = tmb_count_map.get(key, 0) + 1

    return tmb_count_map


def _build_terminal_strip_sequences(terminal_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Build ordered strip sequences from flat terminal rows without TMB chunking."""
    if terminal_df.empty or "Group Sorting" not in terminal_df.columns:
        return []

    strip_df = terminal_df.reset_index(drop=True).copy()
    if "_strip_source_row_index" not in strip_df.columns:
        strip_df["_strip_source_row_index"] = strip_df.index

    sequence_records = strip_df.to_dict(orient="records")
    strip_sequences: list[dict[str, Any]] = []
    cursor = 0

    while cursor < len(sequence_records):
        current_record = sequence_records[cursor]
        current_group_sorting = _stringify_cell(current_record.get("Group Sorting", ""))
        current_sequence_kind = (
            "PE" if _stringify_cell(current_record.get("Terminal Type", "")) == "PE" else "NON_PE"
        )
        current_rows: list[dict[str, Any]] = []

        while cursor < len(sequence_records):
            candidate_record = sequence_records[cursor]
            candidate_group_sorting = _stringify_cell(candidate_record.get("Group Sorting", ""))
            candidate_sequence_kind = (
                "PE" if _stringify_cell(candidate_record.get("Terminal Type", "")) == "PE" else "NON_PE"
            )
            if candidate_group_sorting != current_group_sorting or candidate_sequence_kind != current_sequence_kind:
                break
            current_rows.append(candidate_record)
            cursor += 1

        strip_sequences.append(
            {
                "group_sorting": current_group_sorting,
                "sequence_kind": current_sequence_kind,
                "sequence_index": len(strip_sequences),
                "rows": current_rows,
                "source_rows": [int(record["_strip_source_row_index"]) for record in current_rows],
                "source_names": [_stringify_cell(record.get("Name", "")) for record in current_rows],
            }
        )

    return strip_sequences


def _build_terminal_strip_blocks(
    terminal_df: pd.DataFrame,
    tmb_count_map: dict[tuple[str, str], int],
) -> list[dict[str, Any]]:
    """Plan Terminal Strip blocks directly from the prepared flat terminal rows."""
    if terminal_df.empty or "Group Sorting" not in terminal_df.columns or "Name" not in terminal_df.columns:
        return []

    strip_sequences = _build_terminal_strip_sequences(terminal_df)
    strip_blocks: list[dict[str, Any]] = []

    def _append_cover_block(group_sorting: str, boundary_reason: str, inserted_for: str) -> None:
        previous_block_type = strip_blocks[-1]["block_type"] if strip_blocks else ""
        strip_blocks.append(
            {
                "group_sorting": group_sorting,
                "block_type": "COVER",
                "text": "",
                "space": _TERMINAL_STRIP_COVER_SPACE,
                "source_rows": [],
                "source_names": [],
                "chunk_size": 0,
                "sequence_kind": "COVER",
                "sequence_index": None,
                "chunk_index": None,
                "chunk_count": 0,
                "subgroup_key": "",
                "boundary_reason": boundary_reason,
                "inserted_for": inserted_for,
                "previous_block_type": previous_block_type,
                "next_block_type": "",
                "size_source": "STATIC_COVER",
                "tmb_terminal_count": 0,
                "planner_chunk_size": 0,
            }
        )

    def _append_sequence_blocks(sequence: dict[str, Any]) -> None:
        group_sorting_value = _stringify_cell(sequence.get("group_sorting", ""))
        sequence_kind = _stringify_cell(sequence.get("sequence_kind", ""))
        sequence_index = int(sequence.get("sequence_index", 0))
        sequence_rows = list(sequence.get("rows", []))
        if not sequence_rows:
            return

        if sequence_kind == "PE":
            planner_chunk_count = (len(sequence_rows) + 2) // 3
            tmb_terminal_count = int(tmb_count_map.get((group_sorting_value, "PE"), 0))
            resolved_terminal_count = tmb_terminal_count if tmb_terminal_count > 0 else planner_chunk_count
            strip_blocks.append(
                {
                    "group_sorting": group_sorting_value,
                    "block_type": "PE",
                    "text": "PE",
                    "space": round(resolved_terminal_count * _TERMINAL_STRIP_TERMINAL_SPACE, 2),
                    "source_rows": [int(record["_strip_source_row_index"]) for record in sequence_rows],
                    "source_names": [_stringify_cell(record.get("Name", "")) for record in sequence_rows],
                    "chunk_size": resolved_terminal_count,
                    "sequence_kind": "PE",
                    "sequence_index": sequence_index,
                    "chunk_index": 0,
                    "chunk_count": 1,
                    "subgroup_key": "",
                    "boundary_reason": "",
                    "inserted_for": "",
                    "previous_block_type": "",
                    "next_block_type": "",
                    "size_source": "TMB" if tmb_terminal_count > 0 else "FALLBACK",
                    "tmb_terminal_count": tmb_terminal_count if tmb_terminal_count > 0 else 0,
                    "planner_chunk_size": planner_chunk_count,
                    "terminal_count": resolved_terminal_count,
                }
            )
            return

        name_runs: list[dict[str, Any]] = []
        run_cursor = 0
        while run_cursor < len(sequence_rows):
            current_name = _stringify_cell(sequence_rows[run_cursor].get("Name", ""))
            current_run_rows: list[dict[str, Any]] = []
            while run_cursor < len(sequence_rows):
                candidate_row = sequence_rows[run_cursor]
                candidate_name = _stringify_cell(candidate_row.get("Name", ""))
                if candidate_name != current_name:
                    break
                current_run_rows.append(candidate_row)
                run_cursor += 1
            name_runs.append(
                {
                    "name": current_name,
                    "subgroup": _extract_terminal_cover_subgroup(current_name),
                    "rows": current_run_rows,
                }
            )

        subgroup_runs: list[list[dict[str, Any]]] = []
        if group_sorting_value in {"1010", "1110", "1030"} and name_runs and all(run["subgroup"] for run in name_runs):
            current_subgroup_runs = [name_runs[0]]
            current_subgroup_value = name_runs[0]["subgroup"]
            for name_run in name_runs[1:]:
                if name_run["subgroup"] != current_subgroup_value:
                    subgroup_runs.append(current_subgroup_runs)
                    current_subgroup_runs = [name_run]
                    current_subgroup_value = name_run["subgroup"]
                else:
                    current_subgroup_runs.append(name_run)
            subgroup_runs.append(current_subgroup_runs)
        else:
            subgroup_runs = [name_runs]

        for subgroup_name_runs in subgroup_runs:
            subgroup_key = _stringify_cell(subgroup_name_runs[0].get("subgroup", "")) if subgroup_name_runs else ""
            cover_after_run_index = len(subgroup_name_runs) - 1
            cover_reason = "gs_end" if group_sorting_value not in {"1010", "1110", "1030"} else "subgroup_end"
            if group_sorting_value == "1030":
                ending_14_indices = [
                    index
                    for index, name_run in enumerate(subgroup_name_runs)
                    if _stringify_cell(name_run.get("name", "")).endswith("14")
                ]
                if ending_14_indices:
                    cover_after_run_index = ending_14_indices[-1]
                    cover_reason = "gs1030_after_14"

            for name_run_index, name_run in enumerate(subgroup_name_runs):
                name_run_rows = list(name_run.get("rows", []))
                terminal_name = _stringify_cell(name_run.get("name", ""))
                planner_chunk_size = (len(name_run_rows) + 2) // 3
                tmb_terminal_count = int(tmb_count_map.get((group_sorting_value, terminal_name), 0))
                resolved_terminal_count = tmb_terminal_count if tmb_terminal_count > 0 else planner_chunk_size
                strip_blocks.append(
                    {
                        "group_sorting": group_sorting_value,
                        "block_type": "TERMINAL",
                        "text": terminal_name,
                        "space": round(resolved_terminal_count * _TERMINAL_STRIP_TERMINAL_SPACE, 2),
                        "source_rows": [int(record["_strip_source_row_index"]) for record in name_run_rows],
                        "source_names": [_stringify_cell(record.get("Name", "")) for record in name_run_rows],
                        "chunk_size": resolved_terminal_count,
                        "sequence_kind": "NON_PE",
                        "sequence_index": sequence_index,
                        "chunk_index": 0,
                        "chunk_count": 1,
                        "subgroup_key": subgroup_key,
                        "boundary_reason": "",
                        "inserted_for": "",
                        "previous_block_type": "",
                        "next_block_type": "",
                        "size_source": "TMB" if tmb_terminal_count > 0 else "FALLBACK_CHUNK",
                        "tmb_terminal_count": tmb_terminal_count,
                        "planner_chunk_size": planner_chunk_size,
                        "terminal_count": resolved_terminal_count,
                    }
                )

                if name_run_index == cover_after_run_index:
                    _append_cover_block(group_sorting_value, cover_reason, "non_pe_boundary")

    for sequence_index, strip_sequence in enumerate(strip_sequences):
        previous_sequence = strip_sequences[sequence_index - 1] if sequence_index > 0 else None
        next_sequence = strip_sequences[sequence_index + 1] if sequence_index + 1 < len(strip_sequences) else None
        sequence_kind = _stringify_cell(strip_sequence.get("sequence_kind", ""))
        group_sorting_value = _stringify_cell(strip_sequence.get("group_sorting", ""))

        if sequence_kind == "PE" and previous_sequence is not None:
            _append_cover_block(group_sorting_value, "before_pe_group", "pe_boundary")

        _append_sequence_blocks(strip_sequence)

        if sequence_kind == "PE" and next_sequence is not None:
            _append_cover_block(group_sorting_value, "after_pe_group", "pe_boundary")

    cleaned_blocks: list[dict[str, Any]] = []
    for block in strip_blocks:
        if block["block_type"] == "COVER":
            if not cleaned_blocks or cleaned_blocks[-1]["block_type"] == "COVER":
                continue
        cleaned_blocks.append(block)

    if cleaned_blocks and cleaned_blocks[0]["block_type"] == "COVER":
        cleaned_blocks.pop(0)
    if cleaned_blocks and cleaned_blocks[-1]["block_type"] == "COVER":
        cleaned_blocks.pop()

    for block_index, block in enumerate(cleaned_blocks):
        previous_block = cleaned_blocks[block_index - 1] if block_index > 0 else None
        next_block = cleaned_blocks[block_index + 1] if block_index + 1 < len(cleaned_blocks) else None
        block["previous_block_type"] = previous_block["block_type"] if previous_block is not None else ""
        block["next_block_type"] = next_block["block_type"] if next_block is not None else ""

    return cleaned_blocks


def _summarize_terminal_strip_blocks(strip_blocks: list[dict[str, Any]]) -> list[str]:
    """Return compact block-level debug lines for Terminal Strip planning."""
    summaries: list[str] = []
    for block_index, block in enumerate(strip_blocks):
        summaries.append(
            "idx={idx} gs={gs} type={block_type} text={text} space={space} seq={sequence_kind}:{sequence_index} "
            "chunk={chunk_index}/{chunk_count} subgroup={subgroup_key} reason={boundary_reason}".format(
                idx=block_index,
                gs=_stringify_cell(block.get("group_sorting", "")) or "-",
                block_type=_stringify_cell(block.get("block_type", "")) or "-",
                text=_stringify_cell(block.get("text", "")) or '""',
                space=block.get("space", ""),
                sequence_kind=_stringify_cell(block.get("sequence_kind", "")) or "-",
                sequence_index=block.get("sequence_index", ""),
                chunk_index="" if block.get("chunk_index") is None else int(block.get("chunk_index", 0)) + 1,
                chunk_count=block.get("chunk_count", 0),
                subgroup_key=_stringify_cell(block.get("subgroup_key", "")) or "-",
                boundary_reason=_stringify_cell(block.get("boundary_reason", "")) or "-",
            )
        )
    return summaries


def _summarize_terminal_strip_boundaries(strip_blocks: list[dict[str, Any]]) -> list[str]:
    """Return compact cover/boundary debug lines for Terminal Strip planning."""
    boundary_summaries: list[str] = []
    for block_index, block in enumerate(strip_blocks):
        if _stringify_cell(block.get("block_type", "")) != "COVER":
            continue
        boundary_summaries.append(
            "idx={idx} gs={gs} reason={reason} inserted_for={inserted_for} prev={prev} next={next}".format(
                idx=block_index,
                gs=_stringify_cell(block.get("group_sorting", "")) or "-",
                reason=_stringify_cell(block.get("boundary_reason", "")) or "-",
                inserted_for=_stringify_cell(block.get("inserted_for", "")) or "-",
                prev=_stringify_cell(block.get("previous_block_type", "")) or "-",
                next=_stringify_cell(block.get("next_block_type", "")) or "-",
            )
        )
    return boundary_summaries


def _validate_terminal_strip_blocks(strip_blocks: list[dict[str, Any]]) -> list[str]:
    """Return warning-only validation messages for Terminal Strip plans."""
    warnings: list[str] = []
    valid_block_types = {"TERMINAL", "PE", "COVER"}

    if strip_blocks and _stringify_cell(strip_blocks[0].get("block_type", "")) == "COVER":
        warnings.append("terminal strip validate: leading COVER block detected")
    if strip_blocks and _stringify_cell(strip_blocks[-1].get("block_type", "")) == "COVER":
        warnings.append("terminal strip validate: trailing COVER block detected")

    for block_index, block in enumerate(strip_blocks):
        block_type = _stringify_cell(block.get("block_type", ""))
        if block_type not in valid_block_types:
            warnings.append(f"terminal strip validate: invalid block_type at index {block_index} -> {block_type or 'blank'}")
            continue

        if block_type == "COVER":
            if block_index > 0 and _stringify_cell(strip_blocks[block_index - 1].get("block_type", "")) == "COVER":
                warnings.append(f"terminal strip validate: duplicate consecutive COVER at index {block_index}")
            if block.get("space") != _TERMINAL_STRIP_COVER_SPACE or _stringify_cell(block.get("text", "")) != "":
                warnings.append(f"terminal strip validate: COVER row mismatch at index {block_index}")
            if not _stringify_cell(block.get("boundary_reason", "")):
                warnings.append(f"terminal strip validate: COVER without boundary_reason at index {block_index}")
            continue

        expected_terminal_count = (
            int(block.get("tmb_terminal_count", 0))
            if _stringify_cell(block.get("size_source", "")) == "TMB" and int(block.get("tmb_terminal_count", 0)) > 0
            else int(block.get("planner_chunk_size", block.get("chunk_size", 0)))
        )
        expected_space = round(expected_terminal_count * _TERMINAL_STRIP_TERMINAL_SPACE, 2)
        actual_space = block.get("space")
        if actual_space != expected_space:
            warnings.append(
                f"terminal strip validate: space mismatch at index {block_index} -> expected {expected_space}, got {actual_space}"
            )
        if not _stringify_cell(block.get("group_sorting", "")):
            warnings.append(f"terminal strip validate: missing Group Sorting at index {block_index}")
        if block_type == "PE":
            next_block = strip_blocks[block_index + 1] if block_index + 1 < len(strip_blocks) else None
            next_next_block = strip_blocks[block_index + 2] if block_index + 2 < len(strip_blocks) else None
            if (
                next_block is not None
                and next_next_block is not None
                and _stringify_cell(next_block.get("block_type", "")) == "COVER"
                and _stringify_cell(next_next_block.get("block_type", "")) == "PE"
                and _stringify_cell(next_next_block.get("group_sorting", "")) == _stringify_cell(block.get("group_sorting", ""))
            ):
                warnings.append(f"terminal strip validate: COVER inside PE group near index {block_index}")

    return warnings


def _build_terminal_strip_debug_sheet(strip_blocks: list[dict[str, Any]]) -> pd.DataFrame:
    """Build a flat debug sheet for Terminal Strip planning diagnostics."""
    debug_columns = [
        "Seq",
        "GS",
        "Block Type",
        "Text",
        "Space",
        "Sequence Kind",
        "Subgroup Key",
        "Boundary Reason",
        "Chunk Size",
        "Size Source",
        "TMB Terminal Count",
        "Planner Chunk Size",
        "Source Rows Preview",
        "Source Names Preview",
    ]
    if not strip_blocks:
        return pd.DataFrame(columns=debug_columns)

    debug_rows = [
        {
            "Seq": index + 1,
            "GS": _stringify_cell(block.get("group_sorting", "")),
            "Block Type": _stringify_cell(block.get("block_type", "")),
            "Text": _stringify_cell(block.get("text", "")),
            "Space": block.get("space"),
            "Sequence Kind": _stringify_cell(block.get("sequence_kind", "")),
            "Subgroup Key": _stringify_cell(block.get("subgroup_key", "")),
            "Boundary Reason": _stringify_cell(block.get("boundary_reason", "")),
            "Chunk Size": block.get("chunk_size", 0),
            "Size Source": _stringify_cell(block.get("size_source", "")),
            "TMB Terminal Count": block.get("tmb_terminal_count", 0),
            "Planner Chunk Size": block.get("planner_chunk_size", 0),
            "Source Rows Preview": ", ".join(str(value) for value in block.get("source_rows", [])[:6]),
            "Source Names Preview": ", ".join(block.get("source_names", [])[:6]),
        }
        for index, block in enumerate(strip_blocks)
    ]
    return pd.DataFrame(debug_rows, columns=debug_columns)


def _render_terminal_strip_blocks(strip_blocks: list[dict[str, Any]]) -> pd.DataFrame:
    """Render planned Terminal Strip blocks into the export sheet rows."""
    strip_columns = ["Space", "Text"]
    if not strip_blocks:
        return pd.DataFrame(columns=strip_columns)

    rendered_blocks: list[dict[str, Any]] = []
    for block in strip_blocks:
        if rendered_blocks and rendered_blocks[-1]["block_type"] == "COVER" and block["block_type"] == "COVER":
            continue
        rendered_blocks.append(block)

    if rendered_blocks and rendered_blocks[-1]["block_type"] == "COVER":
        rendered_blocks.pop()

    rendered_rows = [
        {
            "Space": block["space"],
            "Text": block["text"],
        }
        for block in rendered_blocks
    ]
    return pd.DataFrame(rendered_rows, columns=strip_columns)


def _build_terminal_strip_sheet_with_debug(
    terminal_df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str], pd.DataFrame]:
    """Build Terminal Strip rows from strip-only planner blocks."""
    developer_debug_messages = ["terminal strip: generation started"]
    if terminal_df.empty:
        developer_debug_messages.append("terminal strip: generated terminal rows -> 0")
        developer_debug_messages.append("terminal strip: NON_PE sequences -> 0")
        developer_debug_messages.append("terminal strip: PE sequences -> 0")
        developer_debug_messages.append("terminal strip: planned TERMINAL blocks -> 0")
        developer_debug_messages.append("terminal strip: planned PE blocks -> 0")
        developer_debug_messages.append("terminal strip: planned COVER blocks -> 0")
        developer_debug_messages.append("terminal strip: first 10 sequence previews -> none")
        developer_debug_messages.append("terminal strip: first 10 strip blocks preview -> none")
        developer_debug_messages.append("terminal strip: first 10 rendered rows preview -> none")
        developer_debug_messages.append("terminal strip: boundary summary -> none")
        developer_debug_messages.append("terminal strip: first 10 GS transitions -> none")
        developer_debug_messages.append("terminal strip: first 10 cover placement reasons -> none")
        developer_debug_messages.append("terminal strip: first 10 PE boundary events -> none")
        developer_debug_messages.append("terminal strip: blocks sized from TMB -> 0")
        developer_debug_messages.append("terminal strip: blocks sized from fallback -> 0")
        developer_debug_messages.append("terminal strip: first 15 size resolution previews -> none")
        developer_debug_messages.append("terminal strip: first 10 missing TMB size keys -> none")
        developer_debug_messages.append("terminal strip: PE groups planned as single blocks -> 0")
        developer_debug_messages.append("terminal strip: first 10 PE block previews -> none")
        developer_debug_messages.append("terminal strip: first 10 missing PE TMB size keys -> none")
        developer_debug_messages.append("terminal strip: validation warnings -> none")
        return pd.DataFrame(columns=["Space", "Text"]), developer_debug_messages, pd.DataFrame()

    strip_input_df = terminal_df.reset_index(drop=True).copy()
    strip_input_df["_strip_source_row_index"] = strip_input_df.index
    strip_sequences = _build_terminal_strip_sequences(strip_input_df)
    tmb_count_map = _build_terminal_tmb_count_map(terminal_df)
    strip_blocks = _build_terminal_strip_blocks(strip_input_df, tmb_count_map)
    terminal_strip_df = _render_terminal_strip_blocks(strip_blocks)
    terminal_strip_debug_df = _build_terminal_strip_debug_sheet(strip_blocks)

    non_pe_sequence_count = sum(1 for sequence in strip_sequences if sequence["sequence_kind"] == "NON_PE")
    pe_sequence_count = sum(1 for sequence in strip_sequences if sequence["sequence_kind"] == "PE")
    terminal_block_count = sum(1 for block in strip_blocks if block["block_type"] == "TERMINAL")
    pe_block_count = sum(1 for block in strip_blocks if block["block_type"] == "PE")
    cover_block_count = sum(1 for block in strip_blocks if block["block_type"] == "COVER")
    tmb_sized_block_count = sum(1 for block in strip_blocks if _stringify_cell(block.get("size_source", "")) == "TMB")
    fallback_sized_block_count = sum(
        1 for block in strip_blocks if _stringify_cell(block.get("size_source", "")) in {"FALLBACK_CHUNK", "FALLBACK"}
    )
    block_summaries = _summarize_terminal_strip_blocks(strip_blocks)
    boundary_summaries = _summarize_terminal_strip_boundaries(strip_blocks)
    validation_warnings = _validate_terminal_strip_blocks(strip_blocks)
    size_resolution_previews = [
        "{type} gs={gs} text={text} source={size_source} tmb={tmb_count} planner={planner} space={space}".format(
            type=_stringify_cell(block.get("block_type", "")) or "-",
            gs=_stringify_cell(block.get("group_sorting", "")) or "-",
            text=_stringify_cell(block.get("text", "")) or '""',
            size_source=_stringify_cell(block.get("size_source", "")) or "-",
            tmb_count=block.get("tmb_terminal_count", 0),
            planner=block.get("planner_chunk_size", 0),
            space=block.get("space", ""),
        )
        for block in strip_blocks
        if _stringify_cell(block.get("block_type", "")) in {"TERMINAL", "PE"}
    ]
    missing_tmb_size_keys = [
        "{gs}:{text}".format(
            gs=_stringify_cell(block.get("group_sorting", "")) or "-",
            text=_stringify_cell(block.get("text", "")) or "-",
        )
        for block in strip_blocks
        if _stringify_cell(block.get("size_source", "")) in {"FALLBACK_CHUNK", "FALLBACK"}
    ]
    pe_block_previews = [
        "gs={gs} source={source} terminals={terminal_count} planner={planner} space={space}".format(
            gs=_stringify_cell(block.get("group_sorting", "")) or "-",
            source=_stringify_cell(block.get("size_source", "")) or "-",
            terminal_count=block.get("terminal_count", block.get("chunk_size", 0)),
            planner=block.get("planner_chunk_size", 0),
            space=block.get("space", ""),
        )
        for block in strip_blocks
        if _stringify_cell(block.get("block_type", "")) == "PE"
    ]
    missing_pe_tmb_size_keys = [
        "{gs}:PE".format(gs=_stringify_cell(block.get("group_sorting", "")) or "-")
        for block in strip_blocks
        if _stringify_cell(block.get("block_type", "")) == "PE" and _stringify_cell(block.get("size_source", "")) != "TMB"
    ]
    strip_sequence_previews = [
        {
            "group_sorting": sequence["group_sorting"],
            "sequence_kind": sequence["sequence_kind"],
            "row_count": len(sequence.get("rows", [])),
            "source_names": sequence.get("source_names", [])[:6],
        }
        for sequence in strip_sequences[:10]
    ]
    strip_blocks_preview = block_summaries[:15]
    gs_transitions: list[str] = []
    for block_index, block in enumerate(strip_blocks[1:], start=1):
        previous_gs = _stringify_cell(strip_blocks[block_index - 1].get("group_sorting", ""))
        current_gs = _stringify_cell(block.get("group_sorting", ""))
        if current_gs != previous_gs:
            gs_transitions.append(f"idx={block_index} {previous_gs or '-'} -> {current_gs or '-'}")
    cover_placement_reasons = [
        "{reason} gs={gs} prev={prev} next={next}".format(
            reason=_stringify_cell(block.get("boundary_reason", "")) or "-",
            gs=_stringify_cell(block.get("group_sorting", "")) or "-",
            prev=_stringify_cell(block.get("previous_block_type", "")) or "-",
            next=_stringify_cell(block.get("next_block_type", "")) or "-",
        )
        for block in strip_blocks
        if _stringify_cell(block.get("block_type", "")) == "COVER"
    ]
    pe_boundary_events = [
        summary
        for summary in boundary_summaries
        if "before_pe_group" in summary or "after_pe_group" in summary
    ]
    strip_preview_rows = terminal_strip_df.head(10).to_dict(orient="records")
    developer_debug_messages.append(f"terminal strip: NON_PE sequences -> {non_pe_sequence_count}")
    developer_debug_messages.append(f"terminal strip: PE sequences -> {pe_sequence_count}")
    developer_debug_messages.append(f"terminal strip: planned TERMINAL blocks -> {terminal_block_count}")
    developer_debug_messages.append(f"terminal strip: planned PE blocks -> {pe_block_count}")
    developer_debug_messages.append(f"terminal strip: planned COVER blocks -> {cover_block_count}")
    developer_debug_messages.append(
        "terminal strip: first 10 sequence previews -> "
        + (" | ".join(str(sequence) for sequence in strip_sequence_previews) if strip_sequence_previews else "none")
    )
    developer_debug_messages.append(
        "terminal strip: first 15 planned strip blocks preview -> "
        + (" | ".join(str(block) for block in strip_blocks_preview) if strip_blocks_preview else "none")
    )
    developer_debug_messages.append(
        "terminal strip: boundary summary -> "
        + (" | ".join(boundary_summaries[:10]) if boundary_summaries else "none")
    )
    developer_debug_messages.append(
        "terminal strip: first 10 GS transitions -> "
        + (" | ".join(gs_transitions[:10]) if gs_transitions else "none")
    )
    developer_debug_messages.append(
        "terminal strip: first 10 cover placement reasons -> "
        + (" | ".join(cover_placement_reasons[:10]) if cover_placement_reasons else "none")
    )
    developer_debug_messages.append(
        "terminal strip: first 10 PE boundary events -> "
        + (" | ".join(pe_boundary_events[:10]) if pe_boundary_events else "none")
    )
    developer_debug_messages.append(f"terminal strip: blocks sized from TMB -> {tmb_sized_block_count}")
    developer_debug_messages.append(f"terminal strip: blocks sized from fallback -> {fallback_sized_block_count}")
    developer_debug_messages.append(
        "terminal strip: first 15 size resolution previews -> "
        + (" | ".join(size_resolution_previews[:15]) if size_resolution_previews else "none")
    )
    developer_debug_messages.append(
        "terminal strip: first 10 missing TMB size keys -> "
        + (" | ".join(missing_tmb_size_keys[:10]) if missing_tmb_size_keys else "none")
    )
    developer_debug_messages.append(f"terminal strip: PE groups planned as single blocks -> {pe_block_count}")
    developer_debug_messages.append(
        "terminal strip: first 10 PE block previews -> "
        + (" | ".join(pe_block_previews[:10]) if pe_block_previews else "none")
    )
    developer_debug_messages.append(
        "terminal strip: first 10 missing PE TMB size keys -> "
        + (" | ".join(missing_pe_tmb_size_keys[:10]) if missing_pe_tmb_size_keys else "none")
    )
    developer_debug_messages.append(
        "terminal strip: first 10 rendered rows preview -> "
        + (" | ".join(str(row) for row in strip_preview_rows) if strip_preview_rows else "none")
    )
    developer_debug_messages.extend(
        validation_warnings if validation_warnings else ["terminal strip: validation warnings -> none"]
    )
    return terminal_strip_df, developer_debug_messages, terminal_strip_debug_df


def _extract_terminal_cover_subgroup(name: Any) -> str:
    """Extract the 2-digit subgroup used for cover placement in selected GS groups."""
    match = re.match(r"^-X(?P<subgroup>\d{2})", _stringify_cell(name))
    return match.group("subgroup") if match else ""


def _build_terminal_cover_subgroups(gs_df: pd.DataFrame) -> list[pd.DataFrame]:
    """Split one GS block into cover-placement subgroups when required."""
    if gs_df.empty or "Group Sorting" not in gs_df.columns:
        return [gs_df]

    group_sorting_value = _stringify_cell(gs_df["Group Sorting"].iloc[0])
    if group_sorting_value not in {"1010", "1110", "1030"} or "Name" not in gs_df.columns:
        return [gs_df]

    subgroup_values = gs_df["Name"].apply(_extract_terminal_cover_subgroup)
    if subgroup_values.eq("").any():
        return [gs_df]

    subgroup_df = gs_df.copy()
    subgroup_df["_cover_subgroup"] = subgroup_values
    subgroup_groups = [
        subgroup_group_df.drop(columns=["_cover_subgroup"]).copy()
        for _, subgroup_group_df in subgroup_df.groupby("_cover_subgroup", sort=False, dropna=False)
    ]
    return subgroup_groups or [gs_df]


def _select_terminal_cover_targets(gs_df: pd.DataFrame) -> set[int]:
    """Return row positions after which one cover row should be inserted."""
    if gs_df.empty or "Group Sorting" not in gs_df.columns:
        return set()

    cover_source_df = gs_df
    if "Terminal Type" in gs_df.columns:
        non_pe_df = gs_df.loc[~gs_df["Terminal Type"].apply(_stringify_cell).eq("PE")]
        if not non_pe_df.empty:
            cover_source_df = non_pe_df

    group_sorting_value = _stringify_cell(gs_df["Group Sorting"].iloc[0])
    subgroup_dfs = _build_terminal_cover_subgroups(cover_source_df)
    target_positions: set[int] = set()

    for subgroup_df in subgroup_dfs:
        if subgroup_df.empty:
            continue

        subgroup_positions = subgroup_df.index.tolist()
        if not subgroup_positions:
            continue

        target_position = subgroup_positions[-1]
        if group_sorting_value == "1030" and "Name" in subgroup_df.columns:
            name_series = subgroup_df["Name"].apply(_stringify_cell)
            ending_14_mask = name_series.str.endswith("14", na=False)
            if ending_14_mask.any():
                target_position = subgroup_df.loc[ending_14_mask].index[-1]

        target_positions.add(target_position)

    if group_sorting_value not in {"1010", "1110", "1030"} and not target_positions:
        target_positions.add(cover_source_df.index[-1])

    return target_positions


def _compute_terminal_cover_insert_positions(
    terminal_df: pd.DataFrame,
) -> tuple[set[int], int, int]:
    """Compute terminal-block end positions that should receive one inserted cover row after them."""
    if terminal_df.empty or "Group Sorting" not in terminal_df.columns or "Conns." not in terminal_df.columns:
        return set(), 0, 0

    terminal_df = terminal_df.reset_index(drop=True)
    insert_positions: set[int] = set()
    inserted_cover_rows = 0
    skipped_duplicate_covers = 0

    for _, gs_df in terminal_df.groupby("Group Sorting", sort=False, dropna=False):
        group_sorting_value = _stringify_cell(gs_df["Group Sorting"].iloc[0]) if not gs_df.empty else ""
        if not group_sorting_value:
            continue

        target_positions = _select_terminal_cover_targets(gs_df)
        if not target_positions:
            continue

        gs_blocks = _build_terminal_blocks(gs_df)

        for terminal_block in gs_blocks:
            block_end_row_index = int(terminal_block["end_row_index"])
            if block_end_row_index not in target_positions:
                continue

            if block_end_row_index in insert_positions:
                skipped_duplicate_covers += 1
                continue

            insert_positions.add(block_end_row_index)
            inserted_cover_rows += 1

    return insert_positions, inserted_cover_rows, skipped_duplicate_covers


def _insert_terminal_cover_rows(
    terminal_df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    """Insert flat cover rows as blank Conns. rows using GS-specific placement rules."""
    developer_debug_messages: list[str] = []
    if terminal_df.empty or "Group Sorting" not in terminal_df.columns or "Conns." not in terminal_df.columns:
        return terminal_df.reset_index(drop=True), developer_debug_messages

    terminal_df = terminal_df.reset_index(drop=True)
    output_rows: list[dict[str, Any]] = []
    insert_positions, inserted_cover_rows, skipped_duplicate_covers = _compute_terminal_cover_insert_positions(terminal_df)

    for row_index, row in terminal_df.iterrows():
        output_rows.append(row.to_dict())
        if row_index not in insert_positions:
            continue

        cover_row = row.to_dict()
        cover_row["Conns."] = ""
        output_rows.append(cover_row)

    covered_terminal_df = pd.DataFrame(output_rows, columns=terminal_df.columns)
    developer_debug_messages.append(f"terminal cover: inserted cover rows -> {inserted_cover_rows}")
    developer_debug_messages.append(f"terminal cover: skipped duplicate covers -> {skipped_duplicate_covers}")
    preview_rows = covered_terminal_df.loc[:, [column_name for column_name in ("Group Sorting", "Name", "Conns.") if column_name in covered_terminal_df.columns]].head(12).to_dict(orient="records")
    developer_debug_messages.append(
        "terminal cover: first 12 rows preview -> "
        + (" | ".join(str(row) for row in preview_rows) if preview_rows else "none")
    )
    return covered_terminal_df, developer_debug_messages


def _reintegrate_terminal_pe_rows(normal_terminal_df: pd.DataFrame, pe_terminal_df: pd.DataFrame) -> pd.DataFrame:
    """Merge normal and PE terminal rows back into one flat stream ordered by GS ascending."""
    if normal_terminal_df.empty and pe_terminal_df.empty:
        return pd.DataFrame()
    if normal_terminal_df.empty:
        return pe_terminal_df.reset_index(drop=True)
    if pe_terminal_df.empty:
        return normal_terminal_df.reset_index(drop=True)

    normal_merged_df = normal_terminal_df.copy()
    pe_merged_df = pe_terminal_df.copy()

    normal_merged_df["_terminal_output_origin"] = "normal"
    pe_merged_df["_terminal_output_origin"] = "pe"
    normal_merged_df["_terminal_output_order"] = range(len(normal_merged_df))
    pe_merged_df["_terminal_output_order"] = range(len(pe_merged_df))

    terminal_output_df = pd.concat([normal_merged_df, pe_merged_df], ignore_index=True)
    terminal_output_df["_group_sorting_sort"] = terminal_output_df["Group Sorting"].astype(int)
    terminal_output_df["_terminal_output_origin_sort"] = (
        terminal_output_df["_terminal_output_origin"].eq("pe").astype(int)
    )
    terminal_output_df = terminal_output_df.sort_values(
        by=["_group_sorting_sort", "_terminal_output_origin_sort", "_terminal_output_order"],
        kind="mergesort",
    ).drop(
        columns=[
            "_group_sorting_sort",
            "_terminal_output_origin",
            "_terminal_output_origin_sort",
            "_terminal_output_order",
        ]
    ).reset_index(drop=True)

    return terminal_output_df


def parse_terminal_input(file_bytes: bytes) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Parse terminal Excel input into a clean DataFrame with minimal filtering only."""
    user_info_messages: list[str] = []
    developer_debug_messages: list[str] = []

    if not file_bytes:
        return (
            pd.DataFrame(columns=_TERMINAL_OUTPUT_COLUMNS),
            ["terminal input missing -> skipped"],
            ["terminal parser: no file bytes provided"],
        )

    try:
        raw_df = pd.read_excel(BytesIO(file_bytes), sheet_name=0)
    except Exception as exc:
        user_info_messages.append("terminal input could not be processed")
        developer_debug_messages.append(f"terminal parser: failed to read Excel file ({exc})")
        return pd.DataFrame(columns=_TERMINAL_OUTPUT_COLUMNS), user_info_messages, developer_debug_messages

    if raw_df is None:
        user_info_messages.append("terminal input could not be processed")
        developer_debug_messages.append("terminal parser: pandas returned no data")
        return pd.DataFrame(columns=_TERMINAL_OUTPUT_COLUMNS), user_info_messages, developer_debug_messages

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

    for column_name in ("Name", "Conns.", "Group Sorting", "TYPE", "Visible"):
        if column_name in terminal_df.columns:
            terminal_df[column_name] = terminal_df[column_name].apply(_stringify_cell)

    zero_to_blank_conversions = 0
    if "Conns." in terminal_df.columns:
        zero_to_blank_conversions = int(terminal_df["Conns."].eq("0").sum())
        terminal_df["Conns."] = terminal_df["Conns."].apply(_normalize_terminal_conns_value)
        if zero_to_blank_conversions:
            developer_debug_messages.append("terminal normalize: converted Conns. value '0' to blank")
        developer_debug_messages.append(
            f"terminal normalize: zero-to-blank conversions -> {zero_to_blank_conversions}"
        )

    if "Name" not in terminal_df.columns or "Group Sorting" not in terminal_df.columns:
        if "Terminal Type" not in terminal_df.columns:
            terminal_df["Terminal Type"] = ""
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
    visible_no_mask = (
        terminal_df["Visible"].str.casefold().eq("no")
        if "Visible" in terminal_df.columns
        else pd.Series(False, index=terminal_df.index)
    )
    removed_visible_no = int(visible_no_mask.sum())
    terminal_df = terminal_df.loc[~visible_no_mask].copy()
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

    normal_terminal_df, pe_terminal_contacts_df, pe_stats = _split_terminal_pe_rows(terminal_df)
    expanded_pe_terminal_df, expanded_pe_stats = _expand_terminal_pe_rows(pe_terminal_contacts_df)

    developer_debug_messages.append(f"terminal pe: detected PE rows -> {pe_stats['detected_pe_rows']}")
    developer_debug_messages.append(f"terminal pe: split PE from normal rows -> {pe_stats['split_summary']}")
    developer_debug_messages.append(
        "terminal pe: PE GS groups -> "
        + (", ".join(pe_stats["pe_gs_groups"]) if pe_stats["pe_gs_groups"] else "none")
    )
    developer_debug_messages.append("terminal pe: renamed PE rows to Name=PE, Conns.=PE")
    developer_debug_messages.append(
        "terminal pe: expanded PE flat rows -> "
        + str(expanded_pe_stats.get("generated_pe_flat_rows", 0))
    )
    developer_debug_messages.append(
        "terminal pe: first 5 GS groups with expanded PE -> "
        + (", ".join(expanded_pe_stats.get("first_pe_gs_groups", [])) if expanded_pe_stats.get("first_pe_gs_groups") else "none")
    )
    developer_debug_messages.extend(expanded_pe_stats.get("plus_one_debug_messages", []))
    for pe_group_summary in expanded_pe_stats.get("first_pe_gs_groups", []):
        developer_debug_messages.append(f"terminal pe: {pe_group_summary}")
    developer_debug_messages.append("terminal detection: started")
    normal_terminal_df, terminal_type_counts, classified_groups_preview, detection_stats = _apply_terminal_type_classification(normal_terminal_df)

    normal_terminal_df["_group_sorting_sort"] = normal_terminal_df["Group Sorting"].astype(int)
    normal_terminal_df["_original_order"] = range(len(normal_terminal_df))
    normal_terminal_df["_terminal_name_sort"] = normal_terminal_df["Name"].apply(_terminal_name_sort_key)
    if "Conns." in normal_terminal_df.columns:
        normal_terminal_df["_terminal_conns_sort"] = normal_terminal_df["Conns."].apply(_terminal_conns_sort_key)
    else:
        normal_terminal_df["_terminal_conns_sort"] = [(2, 10**9, "")] * len(normal_terminal_df)
    normal_terminal_df = normal_terminal_df.sort_values(
        by=["_group_sorting_sort", "_terminal_name_sort", "Name", "_terminal_conns_sort", "_original_order"],
        kind="mergesort",
    ).drop(columns=["_group_sorting_sort", "_terminal_name_sort", "_terminal_conns_sort", "_original_order"]).reset_index(drop=True)
    normal_terminal_df, reordered_group_counts, reordered_groups_preview, normal_groups_preview, special_gs_7030_groups_preview = _reorder_terminal_conns_by_name(normal_terminal_df)

    terminal_df = _reintegrate_terminal_pe_rows(normal_terminal_df, expanded_pe_terminal_df)

    user_info_messages.append("terminal input processed successfully")
    user_info_messages.append(f"terminal rows exported: {len(terminal_df)}")
    user_info_messages.append(f"terminal groups classified: {terminal_df['Name'].nunique()}")
    user_info_messages.append(f"terminal groups reordered by terminal type: {terminal_df['Name'].nunique()}")
    user_info_messages.append(
        "removed rows summary: "
        f"{removed_visible_no + removed_non_numeric_group_sorting + removed_group_sorting_7210 + removed_xtb + removed_xpe}"
    )

    developer_debug_messages.append(f"terminal parser: removed {removed_visible_no} rows due to Visible == No")
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
    developer_debug_messages.append(
        "terminal detection: group counts by type -> "
        + (
            ", ".join(
                f"{terminal_type}={terminal_type_counts.get(terminal_type, 0)}"
                for terminal_type in ("SPECIAL_GS_7030", "SPECIAL_GS_4010", "SIGNAL", "NORMAL")
            )
            if terminal_type_counts
            else "none"
        )
    )
    developer_debug_messages.append(
        "terminal detection: first 10 classified Name groups -> "
        + (" | ".join(classified_groups_preview) if classified_groups_preview else "none")
    )
    developer_debug_messages.append("terminal detection: narrowed SPECIAL_GS_4010 criteria applied")
    developer_debug_messages.append(
        "terminal detection: SPECIAL_GS_4010 groups count -> "
        + str(detection_stats.get("special_gs_4010_groups", 0))
    )
    developer_debug_messages.append(
        "terminal detection: 4010 fallback groups count -> "
        + str(detection_stats.get("gs_4010_fallback_groups", 0))
    )
    developer_debug_messages.append("terminal parser: applied GS/Name/Conns sorting")
    developer_debug_messages.append("terminal reorder: applied Supporting Data conn placement mapping")
    developer_debug_messages.append("terminal reorder: applied Terminal Type based Conns ordering")
    developer_debug_messages.append("terminal reorder: applied SPECIAL_GS_7030 flat sorting mode")
    developer_debug_messages.append("terminal reorder: applied NORMAL middle-after-first-signal rule")
    developer_debug_messages.append("terminal reorder: applied NORMAL no-signal blank/middle/bottom rule")
    developer_debug_messages.append("terminal pe: expanded PE rows inserted into Terminal Marking")
    developer_debug_messages.append(
        "terminal reorder: first 5 reordered Name groups -> "
        + (" | ".join(reordered_groups_preview) if reordered_groups_preview else "none")
    )
    developer_debug_messages.append(
        "terminal reorder: first 5 NORMAL groups after reorder -> "
        + (" | ".join(normal_groups_preview) if normal_groups_preview else "none")
    )
    developer_debug_messages.append(
        "terminal reorder: SPECIAL_GS_7030 groups count -> "
        + str(reordered_group_counts.get("SPECIAL_GS_7030", 0))
    )
    developer_debug_messages.append(
        "terminal reorder: SPECIAL_GS_7030 groups reordered -> "
        + str(reordered_group_counts.get("SPECIAL_GS_7030", 0))
    )
    developer_debug_messages.append(
        "terminal reorder: first 3 SPECIAL_GS_7030 groups preview -> "
        + (" | ".join(special_gs_7030_groups_preview) if special_gs_7030_groups_preview else "none")
    )
    developer_debug_messages.append(
        "terminal reorder: SPECIAL_GS_4010 groups count -> "
        + str(reordered_group_counts.get("SPECIAL_GS_4010", 0))
    )
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
    first_gs_values_after_pe_reintegration = terminal_df["Group Sorting"].head(10).tolist() if "Group Sorting" in terminal_df.columns else []
    developer_debug_messages.append(
        "terminal output: first 10 GS values after PE reintegration -> "
        + (", ".join(first_gs_values_after_pe_reintegration) if first_gs_values_after_pe_reintegration else "none")
    )
    preview_columns = [column_name for column_name in ("Group Sorting", "Name", "Conns.", "TYPE", "Terminal Type") if column_name in terminal_df.columns]
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
    first_name_groups_preview: list[str] = []
    if not terminal_df.empty and "Conns." in terminal_df.columns:
        for (group_sorting_value, name_value), name_group_df in terminal_df.groupby(["Group Sorting", "Name"], sort=False):
            conns_preview = ", ".join(name_group_df["Conns."].head(10).tolist())
            first_name_groups_preview.append(f"{group_sorting_value}/{name_value}: [{conns_preview}]")
            if len(first_name_groups_preview) >= 5:
                break
    developer_debug_messages.append(
        "terminal reorder: first 5 GS/Name groups after Conns reorder -> "
        + (" | ".join(first_name_groups_preview) if first_name_groups_preview else "none")
    )

    return terminal_df, user_info_messages, developer_debug_messages


def build_placeholder_results(
    inputs: dict[str, dict[str, Any]]
) -> tuple[dict[str, pd.DataFrame], list[str], list[str], list[str], dict[str, bytes | None]]:
    """Build placeholder output sheets only for uploaded file types."""
    sheets: dict[str, pd.DataFrame] = {}
    warnings: list[str] = []
    user_info_messages: list[str] = []
    developer_debug_messages: list[str] = []
    debug_workbooks: dict[str, bytes | None] = {
        "component": None,
        "terminal": None,
        "wire": None,
    }

    for source_key in ("component", "terminal", "wire"):
        file_info = inputs.get(source_key, {})
        file_bytes = file_info.get("bytes")
        file_name = (file_info.get("name") or "").strip()
        sheet_name, source_label = _SOURCE_LABELS[source_key]

        if file_bytes:
            terminal_df = None
            if source_key == "terminal":
                terminal_debug_messages: list[str] = []
                terminal_df, terminal_user_info, terminal_debug = parse_terminal_input(file_bytes)
                user_info_messages.extend(terminal_user_info)
                developer_debug_messages.extend(terminal_debug)
                terminal_debug_messages.extend(terminal_debug)
                if terminal_df is not None and not terminal_df.empty:
                    sheets[sheet_name] = terminal_df
                    developer_debug_messages.append("terminal tmb: generation started")
                    terminal_debug_messages.append("terminal tmb: generation started")
                    terminal_tmb_df, terminal_pe_tmb_debug = _build_terminal_tmb_sheet_with_debug(terminal_df)
                    sheets["Terminal TMB"] = terminal_tmb_df
                    developer_debug_messages.extend(terminal_pe_tmb_debug)
                    terminal_debug_messages.extend(terminal_pe_tmb_debug)
                    developer_debug_messages.append(f"terminal tmb: generated rows -> {len(terminal_tmb_df)}")
                    terminal_debug_messages.append(f"terminal tmb: generated rows -> {len(terminal_tmb_df)}")
                    terminal_tmb_preview_rows = (
                        terminal_tmb_df.head(5).to_dict(orient="records")
                        if terminal_tmb_df is not None and not terminal_tmb_df.empty
                        else []
                    )
                    terminal_tmb_preview_message = (
                        "terminal tmb: first 5 generated rows preview -> "
                        + (" | ".join(str(row) for row in terminal_tmb_preview_rows) if terminal_tmb_preview_rows else "none")
                    )
                    developer_debug_messages.append(terminal_tmb_preview_message)
                    terminal_debug_messages.append(terminal_tmb_preview_message)
                    terminal_strip_df, terminal_strip_debug, terminal_strip_debug_df = _build_terminal_strip_sheet_with_debug(terminal_df)
                    sheets["Terminal Strip"] = terminal_strip_df
                    developer_debug_messages.extend(terminal_strip_debug)
                    terminal_debug_messages.extend(terminal_strip_debug)
                    terminal_debug_sheets: dict[str, pd.DataFrame] = {
                        "Terminal Marking": terminal_df,
                        "General": _build_debug_messages_sheet(terminal_debug_messages),
                    }
                    if terminal_strip_debug_df is not None and not terminal_strip_debug_df.empty:
                        sheets["Terminal Strip Debug"] = terminal_strip_debug_df
                        terminal_debug_sheets["Terminal Strip Debug"] = terminal_strip_debug_df
                    debug_workbooks["terminal"] = export_placeholder_workbook(terminal_debug_sheets)
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

    return sheets, warnings, user_info_messages, developer_debug_messages, debug_workbooks


def _build_debug_messages_sheet(messages: list[str]) -> pd.DataFrame:
    """Build a simple debug-message sheet for debug workbooks."""
    return pd.DataFrame(
        [{"Seq": index + 1, "Message": message} for index, message in enumerate(messages)],
        columns=["Seq", "Message"],
    )


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
