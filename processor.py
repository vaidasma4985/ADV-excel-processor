from __future__ import annotations

import io
from typing import Tuple, List

import pandas as pd
from pandas import DataFrame
from openpyxl.styles import PatternFill


# ----- Helper functions -----


def _check_required_columns(df: DataFrame, required: list[str]) -> None:
    """Raise ValueError if any required columns are missing."""
    missing = [col for col in required if col not in df.columns]
    if missing:
        # The app will show this nicely in Lithuanian
        raise ValueError(", ".join(missing))


def _to_numeric_series(series: pd.Series) -> pd.Series:
    """Convert a Series to numeric, coercing errors to NaN."""
    return pd.to_numeric(series, errors="coerce")


def _is_valid_name_prefix(name: object) -> bool:
    """
    Check if Name has a valid terminal prefix (-F, -K, -X).

    Logic:
    - Find the first '-' character in the string.
    - Take the two characters starting at that '-'.
    - Valid if they are '-F', '-K' or '-X'.

    This works for:
    - "-X7037"
    - "+6010-X7037"  -> first '-' is before 'X', so prefix2 = '-X'
    """
    if pd.isna(name):
        return False

    s = str(name).strip()
    if not s:
        return False

    dash_idx = s.find("-")
    if dash_idx == -1 or dash_idx >= len(s) - 1:
        return False

    prefix2 = s[dash_idx : dash_idx + 2]
    return prefix2 in ("-F", "-K", "-X")


# ----- Core processing function -----


def process_excel(file_bytes: bytes) -> Tuple[DataFrame, DataFrame, bytes]:
    """
    Main processing function.

    Parameters
    ----------
    file_bytes : bytes
        Raw bytes of the uploaded Excel file.

    Returns
    -------
    cleaned_df : DataFrame
        Data for the "Cleaned" sheet.

    removed_df : DataFrame
        Data for the "Removed" sheet, with extra column "Removed Reason".

    output_workbook_bytes : bytes
        Bytes of the final Excel workbook with two sheets ("Cleaned" and "Removed"),
        with yellow-highlighted rows in "Cleaned" where Name prefix is invalid.
    """
    # Read Excel into DataFrame from the first sheet
    buffer = io.BytesIO(file_bytes)
    df = pd.read_excel(buffer, sheet_name=0)

    required_columns = ["Name", "Type", "Quantity", "Group Sorting"]
    _check_required_columns(df, required_columns)

    # Keep original columns order for the Removed sheet
    original_columns = list(df.columns)

    removed_chunks: List[DataFrame] = []

    # -------------------------------------------------------------------------
    # STEP 1 – REMOVE ROWS BY NAME PREFIX
    # -------------------------------------------------------------------------
    remove_prefixes = ("-B", "-C", "-R", "-M", "-P", "-Q", "-S", "-W", "-T")
    name_str = df["Name"].astype(str)

    mask_remove_step1 = name_str.str.startswith(remove_prefixes, na=False)

    if mask_remove_step1.any():
        removed_step1 = df[mask_remove_step1].copy()
        removed_step1["Removed Reason"] = (
            "Removed by Name prefix (-B/-C/-R/-M/-P/-Q/-S/-W/-T)"
        )
        removed_chunks.append(removed_step1)

    df = df[~mask_remove_step1].copy()

    # -------------------------------------------------------------------------
    # STEP 2 – VALIDATE REMAINING NAME PREFIXES (for highlighting later)
    # (Nothing removed here – tik žymėjimas geltona vėliau.)
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # STEP 3 – FILTER BY TYPE VALUES
    # -------------------------------------------------------------------------
    allowed_types = {
        "2002-1611/1000-541",
        "2002-1611/1000-836",
        "2002-3201",
        "2002-3207",
        "RXZE2S114M",
        "RXM4GB2P7",
        "RXM4GB2BD",
        "RXG22P7",
        "RXG22BD",
        "RGZE1S48M",
        "A9F04604",
    }

    mask_keep_type = df["Type"].isin(allowed_types)
    mask_removed_step3 = ~mask_keep_type

    if mask_removed_step3.any():
        removed_step3 = df[mask_removed_step3].copy()
        removed_step3["Removed Reason"] = (
            "Removed by Type filter (not in allowed list)"
        )
        removed_chunks.append(removed_step3)

    df = df[mask_keep_type].copy()

    # -------------------------------------------------------------------------
    # STEP 4 – MAP COMPONENT TYPES (WAGO / SCHNEIDER)
    # -------------------------------------------------------------------------
    wago_types = {
        "2002-1301",
        "2002-1304",
        "2002-1307",
        "2002-1392",
        "2002-1611/1000-541",
        "2002-1611/1000-836",
        "2002-3201",
        "2002-3207",
        "2006-8031",
        "2006-8034",
        "249-116",
    }

    # WAGO mapping
    mask_wago = df["Type"].isin(wago_types)
    if mask_wago.any():
        df.loc[mask_wago, "Type"] = (
            "WAGO." + df.loc[mask_wago, "Type"].astype(str)
        )

    # Schneider relay base mapping
    mask_rgze = df["Type"] == "RGZE1S48M"
    if mask_rgze.any():
        df.loc[mask_rgze, "Type"] = "SE.RGZE1S48M"

    # -------------------------------------------------------------------------
    # STEP 5 – UPDATE NAME USING GROUP SORTING (FOR NON-EMPTY GROUP SORTING)
    # -------------------------------------------------------------------------
    gs_numeric = _to_numeric_series(df["Group Sorting"])
    mask_has_gs = gs_numeric.notna()

    if mask_has_gs.any():
        gs_str = gs_numeric[mask_has_gs].astype(int).astype(str)
        df.loc[mask_has_gs, "Name"] = (
            "+" + gs_str + df.loc[mask_has_gs, "Name"].astype(str)
        )

    # -------------------------------------------------------------------------
    # STEP 6 – SPECIAL HANDLING FOR PE TERMINALS (TYPE = WAGO.2002-3207)
    # -------------------------------------------------------------------------
    mask_pe_all = df["Type"] == "WAGO.2002-3207"
    if mask_pe_all.any():
        pe_df = df.loc[mask_pe_all].copy()
        pe_df["GroupSortingNum"] = _to_numeric_series(pe_df["Group Sorting"])

        # Tik PE su normaliu skaičiumi Group Sorting dalyvauja numeracijoje
        pe_df_valid = pe_df[pe_df["GroupSortingNum"].notna()].copy()

        if not pe_df_valid.empty:
            # Unikalios GS reikšmės, surūšiuotos didėjimo tvarka
            unique_gs = sorted(pe_df_valid["GroupSortingNum"].unique())

            # 1-a GS reikšmė -> PE1, 2-a -> PE2, t.t.
            gs_to_index = {gs: i + 1 for i, gs in enumerate(unique_gs)}

            pe_df_valid["PE_Index"] = pe_df_valid["GroupSortingNum"].map(gs_to_index)

            # Galutinis pavadinimas: "+<GroupSorting>-PE<index>"
            gs_str_pe = pe_df_valid["GroupSortingNum"].astype(int).astype(str)
            pe_df_valid["Name"] = (
                "+" + gs_str_pe + "-PE" + pe_df_valid["PE_Index"].astype(str)
            )

            # Grąžinam atnaujintus Name į pagrindinį df
            df.loc[pe_df_valid.index, "Name"] = pe_df_valid["Name"]

        # PE eilutės su ne-skaitine Group Sorting palieka jau esamą Name

    # -------------------------------------------------------------------------
    # BUILD REMOVED DF
    # -------------------------------------------------------------------------
    if removed_chunks:
        removed_df = pd.concat(removed_chunks, ignore_index=True)
    else:
        # Empty but with consistent columns
        removed_df = pd.DataFrame(columns=original_columns + ["Removed Reason"])

    cleaned_df = df.reset_index(drop=True)
    removed_df = removed_df.reset_index(drop=True)

    # -------------------------------------------------------------------------
    # BUILD FINAL EXCEL WORKBOOK IN MEMORY
    # -------------------------------------------------------------------------
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Write both sheets without index columns
        cleaned_df.to_excel(writer, sheet_name="Cleaned", index=False)
        removed_df.to_excel(writer, sheet_name="Removed", index=False)

        workbook = writer.book
        ws_cleaned = workbook["Cleaned"]

        # Yellow fill for invalid Name prefixes
        yellow_fill = PatternFill(
            start_color="FFFF00", end_color="FFFF00", fill_type="solid"
        )

        # Header row is 1; data starts at row 2
        max_col = ws_cleaned.max_column

        for excel_row_idx, row in enumerate(
            cleaned_df.itertuples(index=False), start=2
        ):
            name_val = getattr(row, "Name", None)
            if not _is_valid_name_prefix(name_val):
                for col_idx in range(1, max_col + 1):
                    cell = ws_cleaned.cell(row=excel_row_idx, column=col_idx)
                    cell.fill = yellow_fill

    output_workbook_bytes = output.getvalue()

    return cleaned_df, removed_df, output_workbook_bytes
