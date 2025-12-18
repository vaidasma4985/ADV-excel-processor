from __future__ import annotations

from io import BytesIO
from typing import Dict, List, Tuple, Any

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows


YELLOW_FILL = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")


# ---------------------------
# Helpers
# ---------------------------
def _to_numeric_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def _gs_to_str(v: Any) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
        return ""
    n = pd.to_numeric(v, errors="coerce")
    if pd.isna(n):
        return ""
    return str(int(float(n)))


def _ensure_cols(df: pd.DataFrame, cols: List[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"Trūksta privalomų stulpelių: {', '.join(missing)}. "
            "Patikrink, ar Excel struktūra teisinga."
        )


def _append_removed(removed_parts: List[pd.DataFrame], df_part: pd.DataFrame, reason: str) -> None:
    if df_part.empty:
        return
    tmp = df_part.copy()
    tmp["Removed Reason"] = reason
    removed_parts.append(tmp)


def _extract_k_number(name: str) -> int:
    import re
    m = re.search(r"-K(\d+)", str(name))
    if not m:
        return 10**9
    return int(m.group(1))


def _starts_with_any(s: pd.Series, prefixes: Tuple[str, ...]) -> pd.Series:
    return s.astype(str).str.startswith(prefixes, na=False)


# ---------------------------
# Main processing
# ---------------------------
def process_excel(file_bytes: bytes) -> Tuple[pd.DataFrame, pd.DataFrame, bytes, Dict[str, int]]:
    df = pd.read_excel(BytesIO(file_bytes), sheet_name=0, engine="openpyxl")
    input_rows = len(df)

    required = ["Name", "Type", "Quantity", "Group Sorting"]
    _ensure_cols(df, required)

    df["Name"] = df["Name"].astype(str)
    df["Type"] = df["Type"].astype(str)

    # Ensure columns exist
    for col, default in [
        ("Accessories", ""),
        ("Quantity of accessories", 0),
        ("Accessories2", ""),
        ("Quantity of accessories2", 0),
        ("Designation", ""),
    ]:
        if col not in df.columns:
            df[col] = default

    removed_parts: List[pd.DataFrame] = []

    # -------------------------------------------------------------------------
    # STEP 1 – REMOVE ROWS BY NAME PREFIX
    # -------------------------------------------------------------------------
    remove_prefixes = ("-B", "-C", "-R", "-M", "-P", "-Q", "-S", "-W", "-T")
    mask_remove = _starts_with_any(df["Name"], remove_prefixes)
    _append_removed(
        removed_parts,
        df[mask_remove],
        "Removed by Name prefix (-B/-C/-R/-M/-P/-Q/-S/-W/-T)",
    )
    df = df[~mask_remove].copy()

    # -------------------------------------------------------------------------
    # STEP 2 – VALIDATE NAME PREFIXES FOR YELLOW HIGHLIGHT
    # Valid only: -F, -K, -X (invalid NOT removed)
    # -------------------------------------------------------------------------
    valid_prefixes = ("-F", "-K", "-X")
    df["_highlight_invalid_prefix"] = ~_starts_with_any(df["Name"], valid_prefixes)

    # -------------------------------------------------------------------------
    # STEP 3 – FILTER BY TYPE VALUES (ALLOW LIST)
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
        "RE17LCBM",
        "39.00.8.230.8240",
        "RE22R1AMR",
    }

    mask_type_allowed = df["Type"].isin(allowed_types)
    _append_removed(removed_parts, df[~mask_type_allowed], "Removed by Type filter (not in allowed list)")
    df = df[mask_type_allowed].copy()

    # -------------------------------------------------------------------------
    # STEP 4 – MAP TYPES
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
    mask_wago = df["Type"].isin(wago_types)
    df.loc[mask_wago, "Type"] = "WAGO." + df.loc[mask_wago, "Type"].astype(str)

    se_map = {
        "RGZE1S48M": "SE.RGZE1S48M",
        "RXG22P7": "SE.RXG22P7",
        "RXG22BD": "SE.RXG22BD",
        "RXM4GB2BD": "SE.RXM4GB2BD",
        "RXZE2S114M": "SE.RXZE2S114M",
        "A9F04604": "SE.A9F04604",
        "A9F04601": "SE.A9F04601",
    }
    df["Type"] = df["Type"].replace(se_map)

    # Special keepers / renames
    df.loc[df["Type"] == "RE17LCBM", "Type"] = "SE.RE17LCBM_ADV"
    df.loc[df["Type"] == "RE22R1AMR", "Type"] = "SE.RE22R1AMR_ADV"
    df.loc[df["Type"] == "39.00.8.230.8240", "Type"] = "FIN.39.00.8.230.8240_ADV"

    # ADV suffix mapping
    adv_targets = {
        "WAGO.2002-3207": "WAGO.2002-3207_ADV",
        "WAGO.2002-3201": "WAGO.2002-3201_ADV",
        "WAGO.2002-3292": "WAGO.2002-3292_ADV",
        "WAGO.2002-991": "WAGO.2002-991_ADV",
        "WAGO.249-116": "WAGO.249-116_ADV",
        "WAGO.2002-1611/1000-541": "WAGO.2002-1611/1000-541_ADV",
        "WAGO.2002-1611/1000-836": "WAGO.2002-1611/1000-836_ADV",
        "SE.A9F04601": "SE.A9F04601_ADV",
        "SE.A9F04604": "SE.A9F04604_ADV",
    }
    df["Type"] = df["Type"].replace(adv_targets)

    # -------------------------------------------------------------------------
    # STEP 4c – RELAY MERGE (minimal: keep combined Type per Name)
    # -------------------------------------------------------------------------
    def _merge_by_base(base_type: str, combined_type: str) -> None:
        nonlocal df
        base_mask = df["Type"].astype(str).eq(base_type)
        if not base_mask.any():
            return

        drop_idxs: List[int] = []
        for name_val, grp in df[df["Name"].isin(df.loc[base_mask, "Name"])].groupby("Name", sort=False):
            idxs = grp.index.to_list()
            keep_idx = None
            for i in idxs:
                if df.at[i, "Type"] == base_type:
                    keep_idx = i
                    break
            if keep_idx is None:
                keep_idx = idxs[0]

            for i in idxs:
                if i != keep_idx:
                    drop_idxs.append(i)

            df.at[keep_idx, "Type"] = combined_type
            df.at[keep_idx, "Quantity"] = 1

        if drop_idxs:
            _append_removed(removed_parts, df.loc[drop_idxs], "Removed: merged into relay combined row")
            df = df.drop(index=drop_idxs).copy()

    _merge_by_base("SE.RGZE1S48M", "SE.RGZE1S48M + SE.RXG22P7")
    _merge_by_base("SE.RXZE2S114M", "SE.RXZE2S114M + SE.RXM4GB2BD")

    # -------------------------------------------------------------------------
    # STEP 5 – Relay GS (only TWO numbers)
    # -------------------------------------------------------------------------
    existing_gs = set(_to_numeric_series(df["Group Sorting"]).dropna().astype(int).tolist())

    def _next_free_gs(start: int = 1) -> int:
        g = start
        while g in existing_gs:
            g += 1
        existing_gs.add(g)
        return g

    mask_2pole = df["Type"].astype(str).eq("SE.RGZE1S48M + SE.RXG22P7")
    mask_4pole = df["Type"].astype(str).eq("SE.RXZE2S114M + SE.RXM4GB2BD")

    if mask_2pole.any():
        gs_2pole = _next_free_gs(1)
        df.loc[mask_2pole, "Group Sorting"] = gs_2pole
    else:
        gs_2pole = None

    if mask_4pole.any():
        gs_4pole = _next_free_gs((gs_2pole or 1) + 1)
        df.loc[mask_4pole, "Group Sorting"] = gs_4pole
    else:
        gs_4pole = None

    # -------------------------------------------------------------------------
    # STEP 5a – TIMED RELAYS (-K192*) GS SEQUENCE (after relays)
    # -------------------------------------------------------------------------
    name_s = df["Name"].astype(str)
    mask_timed = name_s.str.contains(r"-K192", regex=True, na=False)

    if mask_timed.any():
        gs_relays = _to_numeric_series(df.loc[mask_2pole | mask_4pole, "Group Sorting"]).dropna()
        max_relays_gs = int(gs_relays.astype(int).max()) if not gs_relays.empty else 0

        timed_df = df[mask_timed].copy()
        timed_df["_kno"] = timed_df["Name"].apply(_extract_k_number)
        timed_df = timed_df.sort_values(["_kno"], kind="stable")

        start_gs = max_relays_gs + 1
        for offset, idx in enumerate(timed_df.index):
            df.at[idx, "Group Sorting"] = start_gs + offset

        last_idx = timed_df.index[-1]
        df.at[last_idx, "Accessories"] = "WAGO.249-116_ADV"
        df.at[last_idx, "Quantity of accessories"] = 1

        max_timed_gs = start_gs + len(timed_df.index) - 1
    else:
        gs_relays = _to_numeric_series(df.loc[mask_2pole | mask_4pole, "Group Sorting"]).dropna()
        max_timed_gs = int(gs_relays.astype(int).max()) if not gs_relays.empty else 0

    # -------------------------------------------------------------------------
    # ✅ STEP 5a.1 – FUSES GS (fix: gives fuses their own GS so +GS goes into Name)
    # -------------------------------------------------------------------------
    mask_541 = df["Type"].astype(str).eq("WAGO.2002-1611/1000-541_ADV")
    mask_836 = df["Type"].astype(str).eq("WAGO.2002-1611/1000-836_ADV")

    if mask_541.any():
        gs_541 = _next_free_gs(1)
        df.loc[mask_541, "Group Sorting"] = gs_541

    if mask_836.any():
        # split by Name containing -F9**
        n836 = df.loc[mask_836, "Name"].astype(str)
        mask_836_f9 = n836.str.contains(r"-F9", regex=True, na=False)
        idxs = df[mask_836].index

        if mask_836_f9.any():
            gs_836_f9 = _next_free_gs(1)
            df.loc[idxs[mask_836_f9.values], "Group Sorting"] = gs_836_f9

        if (~mask_836_f9).any():
            gs_836_other = _next_free_gs(1)
            df.loc[idxs[(~mask_836_f9).values], "Group Sorting"] = gs_836_other

    # -------------------------------------------------------------------------
    # STEP 5b – BACKUP group (RE22 + K561/2/3) GS = next after timed
    # -------------------------------------------------------------------------
    mask_backup_names = (
        name_s.str.startswith("-K561", na=False)
        | name_s.str.startswith("-K562", na=False)
        | name_s.str.startswith("-K563", na=False)
    )
    mask_re22 = df["Type"].astype(str).eq("SE.RE22R1AMR_ADV")
    mask_backup_all = mask_backup_names | mask_re22

    if mask_backup_all.any():
        backup_gs = max_timed_gs + 1
        df.loc[mask_backup_all, "Group Sorting"] = backup_gs

        backup_idxs = df[mask_backup_all].index.to_list()
        last_idx = backup_idxs[-1]
        df.at[last_idx, "Accessories"] = "WAGO.249-116_ADV"
        df.at[last_idx, "Quantity of accessories"] = 1

        df.loc[mask_backup_all, "_force_function"] = "BACKUP"
        max_backup_gs = backup_gs
    else:
        max_backup_gs = max_timed_gs

    # -------------------------------------------------------------------------
    # STEP 5c – Finder GS after BACKUP
    # -------------------------------------------------------------------------
    mask_fin = df["Type"].astype(str).eq("FIN.39.00.8.230.8240_ADV")
    if mask_fin.any():
        fin_gs = max_backup_gs + 1
        df.loc[mask_fin, "Group Sorting"] = fin_gs

        fin_idxs = df[mask_fin].index.to_list()
        last_idx = fin_idxs[-1]
        df.at[last_idx, "Accessories"] = "WAGO.249-116_ADV"
        df.at[last_idx, "Quantity of accessories"] = 1

        df.loc[mask_fin, "_force_function"] = "1POLE"

    # -------------------------------------------------------------------------
    # STEP 6 – ADD +GS TO NAME (for all rows with non-empty GS)
    # -------------------------------------------------------------------------
    gs_str = df["Group Sorting"].apply(_gs_to_str)
    has_gs = gs_str.astype(str).ne("")
    df.loc[has_gs & ~df["Name"].astype(str).str.startswith("+", na=False), "Name"] = (
        "+" + gs_str[has_gs].astype(str) + df.loc[has_gs & ~df["Name"].astype(str).str.startswith("+", na=False), "Name"].astype(str)
    )

    # -------------------------------------------------------------------------
    # STEP 7 – PE renaming (WAGO.2002-3207_ADV)
    # -------------------------------------------------------------------------
    pe_type = "WAGO.2002-3207_ADV"
    mask_pe = df["Type"].astype(str).eq(pe_type)
    if mask_pe.any():
        pe_gs = _to_numeric_series(df.loc[mask_pe, "Group Sorting"])
        uniq = sorted([int(x) for x in pe_gs.dropna().astype(int).unique().tolist()])
        gs_to_pe = {gs: i + 1 for i, gs in enumerate(uniq)}
        for idx in df[mask_pe].index:
            gs_val = _to_numeric_series(pd.Series([df.at[idx, "Group Sorting"]])).iloc[0]
            if pd.isna(gs_val):
                continue
            gs_int = int(gs_val)
            pe_idx = gs_to_pe.get(gs_int, 1)
            df.at[idx, "Name"] = f"+{gs_int}-PE{pe_idx}"

    # -------------------------------------------------------------------------
    # STEP 9 – TERMINAL SPLIT BY QUANTITY (WAGO.2002-3201_ADV, WAGO.2002-3207_ADV)
    # -------------------------------------------------------------------------
    rows: List[dict] = []
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        t = str(row_dict.get("Type", ""))
        qty_raw = row_dict.get("Quantity", 0)
        qty = pd.to_numeric(qty_raw, errors="coerce")

        if t in ("WAGO.2002-3201_ADV", "WAGO.2002-3207_ADV") and pd.notna(qty) and qty > 1:
            n = int(qty)
            base = row_dict.copy()
            base["Quantity"] = 1
            base["Designation"] = ""
            rows.append(base)

            for i in range(1, n):
                r = row_dict.copy()
                r["Quantity"] = 1
                r["Designation"] = str(i)
                r["Accessories"] = ""
                r["Quantity of accessories"] = 0
                r["Accessories2"] = ""
                r["Quantity of accessories2"] = 0
                rows.append(r)
        else:
            row_dict["Designation"] = row_dict.get("Designation", "")
            rows.append(row_dict)

    df = pd.DataFrame(rows)

    # -------------------------------------------------------------------------
    # STEP 10 – FUNCTION DESIGNATION -> into Name (DT full)
    # TIMED_RELAYS for -K192* (by Name)
    # -------------------------------------------------------------------------
    def type_to_function(t: str) -> str:
        mapping = {
            "SE.A9F04604_ADV": "POWER",
            "SE.A9F04601_ADV": "POWER",
            "WAGO.2002-1611/1000-541_ADV": "FUSES",
            "WAGO.2002-1611/1000-836_ADV": "FUSES",
            "SE.RGZE1S48M + SE.RXG22P7": "2POLE",
            "SE.RXZE2S114M + SE.RXM4GB2BD": "4POLE",
            "WAGO.2002-3201_ADV": "CONTROL",
            "WAGO.2002-3207_ADV": "CONTROL",
        }
        return mapping.get(t, "")

    funcs: List[str] = []
    for idx in df.index:
        f = ""
        name_val = str(df.at[idx, "Name"]) if pd.notna(df.at[idx, "Name"]) else ""

        # 1) TIMED_RELAYS for -K192*
        if "-K192" in name_val:
            f = "TIMED_RELAYS"

        # 2) force functions (BACKUP, 1POLE) if not timed
        if not f and "_force_function" in df.columns:
            ff = str(df.at[idx, "_force_function"]) if pd.notna(df.at[idx, "_force_function"]) else ""
            if ff.strip():
                f = ff.strip()

        # 3) default by Type
        if not f:
            f = type_to_function(str(df.at[idx, "Type"]))

        funcs.append(f)

    df["_function"] = funcs
    has_func = df["_function"].astype(str).ne("")
    df.loc[has_func, "Name"] = "=" + df.loc[has_func, "_function"].astype(str) + df.loc[has_func, "Name"].astype(str)

    df.drop(columns=[c for c in ["_function", "_force_function"] if c in df.columns], inplace=True, errors="ignore")

    # -------------------------------------------------------------------------
    # Removed
    # -------------------------------------------------------------------------
    removed_df = pd.concat(removed_parts, ignore_index=True) if removed_parts else pd.DataFrame(columns=list(df.columns) + ["Removed Reason"])
    if "Removed Reason" not in removed_df.columns:
        removed_df["Removed Reason"] = ""

    cleaned_df = df.copy()

    # -------------------------------------------------------------------------
    # Workbook (Cleaned + Removed), Name as TEXT (keep leading '=')
    # -------------------------------------------------------------------------
    wb = Workbook()
    ws_clean = wb.active
    ws_clean.title = "Cleaned"
    ws_removed = wb.create_sheet("Removed")

    for r in dataframe_to_rows(cleaned_df.drop(columns=["_highlight_invalid_prefix"], errors="ignore"), index=False, header=True):
        ws_clean.append(r)

    # Force Name column (col 1) as text
    for r in range(2, ws_clean.max_row + 1):
        cell = ws_clean.cell(row=r, column=1)
        cell.number_format = "@"
        cell.data_type = "s"

    # Highlight invalid prefixes
    if "_highlight_invalid_prefix" in cleaned_df.columns:
        flags = cleaned_df["_highlight_invalid_prefix"].tolist()
        for i, is_invalid in enumerate(flags, start=2):
            if bool(is_invalid):
                for c in range(1, ws_clean.max_column + 1):
                    ws_clean.cell(row=i, column=c).fill = YELLOW_FILL

    for r in dataframe_to_rows(removed_df, index=False, header=True):
        ws_removed.append(r)

    # Removed Name col as text
    if ws_removed.max_row >= 1:
        headers = [ws_removed.cell(row=1, column=c).value for c in range(1, ws_removed.max_column + 1)]
        if "Name" in headers:
            name_col = headers.index("Name") + 1
            for r in range(2, ws_removed.max_row + 1):
                cell = ws_removed.cell(row=r, column=name_col)
                cell.number_format = "@"
                cell.data_type = "s"

    bio = BytesIO()
    wb.save(bio)
    out_bytes = bio.getvalue()

    stats = {
        "input_rows": input_rows,
        "cleaned_rows": len(cleaned_df),
        "removed_rows": len(removed_df),
    }

    cleaned_preview = cleaned_df.drop(columns=["_highlight_invalid_prefix"], errors="ignore")
    return cleaned_preview, removed_df, out_bytes, stats
