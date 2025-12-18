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
    # -K1921 -> 1921
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
    # Read first sheet
    df = pd.read_excel(BytesIO(file_bytes), sheet_name=0, engine="openpyxl")
    input_rows = len(df)

    required = ["Name", "Type", "Quantity", "Group Sorting"]
    _ensure_cols(df, required)

    # Normalize columns (keep originals too)
    df["Name"] = df["Name"].astype(str)
    df["Type"] = df["Type"].astype(str)

    # Extra columns needed by your pipeline
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
    # STEP 2 – VALIDATE NAME PREFIXES FOR YELLOW HIGHLIGHT (AFTER STEP 1)
    # Valid only: -F, -K, -X
    # (These invalid rows are NOT removed)
    # -------------------------------------------------------------------------
    valid_prefixes = ("-F", "-K", "-X")
    invalid_for_highlight = ~_starts_with_any(df["Name"], valid_prefixes)
    df["_highlight_invalid_prefix"] = invalid_for_highlight

    # -------------------------------------------------------------------------
    # STEP 3 – FILTER BY TYPE VALUES (ALLOW LIST)
    # + we keep the "special not removed" types too
    # -------------------------------------------------------------------------
    allowed_types = {
        # original allow list
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
        # Keepers you asked not to remove
        "RE17LCBM",
        "39.00.8.230.8240",
        # New BACKUP component
        "RE22R1AMR",
    }

    mask_type_allowed = df["Type"].isin(allowed_types)
    _append_removed(
        removed_parts,
        df[~mask_type_allowed],
        "Removed by Type filter (not in allowed list)",
    )
    df = df[mask_type_allowed].copy()

    # -------------------------------------------------------------------------
    # STEP 4 – MAP COMPONENT TYPES (WAGO / SCHNEIDER / SPECIAL)
    # -------------------------------------------------------------------------
    # WAGO list (explicit)
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

    # Prefix WAGO.
    df.loc[df["Type"].isin(wago_types), "Type"] = "WAGO." + df.loc[df["Type"].isin(wago_types), "Type"].astype(str)

    # Schneider / SE mappings
    se_map = {
        "RGZE1S48M": "SE.RGZE1S48M",
        "RXG22P7": "SE.RXG22P7",
        "RXG22BD": "SE.RXG22BD",
        "RXM4GB2BD": "SE.RXM4GB2BD",
        "RXZE2S114M": "SE.RXZE2S114M",
        "A9F04604": "SE.A9F04604",
        # If someday appears
        "A9F04601": "SE.A9F04601",
    }
    df["Type"] = df["Type"].replace(se_map)

    # Special keepers / renames
    df.loc[df["Type"] == "RE17LCBM", "Type"] = "SE.RE17LCBM_ADV"
    df.loc[df["Type"] == "RE22R1AMR", "Type"] = "SE.RE22R1AMR_ADV"
    df.loc[df["Type"] == "39.00.8.230.8240", "Type"] = "FIN.39.00.8.230.8240_ADV"

    # -------------------------------------------------------------------------
    # STEP 4b – Apply _ADV suffix mapping (your requested list)
    # NOTE: Do NOT double-suffix
    # -------------------------------------------------------------------------
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

    # Also ensure these accessory items exist as ADV when we set them later
    # (We will set WAGO.2002-3292_ADV, WAGO.2002-991_ADV, WAGO.249-116_ADV explicitly)

    # -------------------------------------------------------------------------
    # STEP 4c – RELAY MERGE (2POLE/4POLE) based on base codes in pair group
    # Search by two codes: SE.RGZE1S48M and SE.RXZE2S114M on same Name
    # Keep 1 row per Name with combined Type
    # -------------------------------------------------------------------------
    # Prepare for merge before +GS changes Name
    # We'll do merge on current df["Name"] (original)
    two_pole_base = "SE.RGZE1S48M"
    four_pole_base = "SE.RXZE2S114M"

    # For 2POLE: if Name contains base type row, merge whole group to that combined
    mask_2pole = df["Type"].astype(str).eq(two_pole_base) | df["Type"].astype(str).eq(two_pole_base + "_ADV")
    # but in our mapping RGZE1S48M becomes SE.RGZE1S48M (no _ADV for this set)
    mask_2pole = df["Type"].astype(str).eq(two_pole_base)

    mask_4pole = df["Type"].astype(str).eq(four_pole_base)

    # Merge helper
    def _merge_relay(base_mask: pd.Series, combined_type: str) -> None:
        nonlocal df, removed_parts
        if not base_mask.any():
            return
        base_rows = df[base_mask].copy()
        keep_indices = []
        drop_indices = []

        # group by Name
        for name_val, grp in df[df["Name"].isin(base_rows["Name"])].groupby("Name", sort=False):
            # keep the base row if exists, else keep first
            grp_idx = list(grp.index)
            base_in_grp = [i for i in grp_idx if df.at[i, "Type"] == df.loc[base_mask, "Type"].iloc[0] or df.at[i, "Type"] == combined_type]
            keep_i = None
            for i in grp_idx:
                if df.at[i, "Type"] == df.loc[base_mask, "Type"].iloc[0] or df.at[i, "Type"] == df.loc[base_mask, "Type"].iloc[0]:
                    keep_i = i
                    break
            if keep_i is None:
                keep_i = grp_idx[0]

            keep_indices.append(keep_i)
            for i in grp_idx:
                if i != keep_i:
                    drop_indices.append(i)

            df.at[keep_i, "Type"] = combined_type
            df.at[keep_i, "Quantity"] = 1

        if drop_indices:
            _append_removed(
                removed_parts,
                df.loc[drop_indices],
                "Removed: merged into relay combined row",
            )
            df = df.drop(index=drop_indices).copy()

    # Actual merge:
    _merge_relay(mask_2pole, "SE.RGZE1S48M + SE.RXG22P7")
    _merge_relay(mask_4pole, "SE.RXZE2S114M + SE.RXM4GB2BD")

    # -------------------------------------------------------------------------
    # STEP 5 – GROUP SORTING assignment for relays:
    # Only TWO numbers total: one for 2POLE, one for 4POLE
    # -------------------------------------------------------------------------
    # Determine next free small GS starting at 1 (avoid colliding with existing numeric GS)
    existing_gs = set(_to_numeric_series(df["Group Sorting"]).dropna().astype(int).tolist())

    def _next_free_gs(start: int = 1) -> int:
        g = start
        while g in existing_gs:
            g += 1
        existing_gs.add(g)
        return g

    # Assign 2POLE GS then 4POLE GS
    mask_2pole_combined = df["Type"].astype(str).eq("SE.RGZE1S48M + SE.RXG22P7")
    mask_4pole_combined = df["Type"].astype(str).eq("SE.RXZE2S114M + SE.RXM4GB2BD")

    if mask_2pole_combined.any():
        gs_2pole = _next_free_gs(1)
        df.loc[mask_2pole_combined, "Group Sorting"] = gs_2pole
    else:
        gs_2pole = None

    if mask_4pole_combined.any():
        gs_4pole = _next_free_gs((gs_2pole or 1) + 1)
        df.loc[mask_4pole_combined, "Group Sorting"] = gs_4pole
    else:
        gs_4pole = None

    # -------------------------------------------------------------------------
    # STEP 5a – TIMED RELAYS (-K192*) group sorting SEQUENCE (after relays)
    # + add WAGO.249-116_ADV on last timed relay
    # -------------------------------------------------------------------------
    name_s = df["Name"].astype(str)
    mask_timed = name_s.str.contains(r"-K192", regex=True, na=False)

    # Timed relays are those with -K192* names (you wanted this family)
    if mask_timed.any():
        max_relays_gs = 0
        gs_relays = _to_numeric_series(df.loc[mask_2pole_combined | mask_4pole_combined, "Group Sorting"]).dropna()
        if not gs_relays.empty:
            max_relays_gs = int(gs_relays.astype(int).max())

        timed_df = df[mask_timed].copy()
        timed_df["_kno"] = timed_df["Name"].apply(_extract_k_number)
        timed_df = timed_df.sort_values(["_kno"], kind="stable")

        start_gs = max_relays_gs + 1
        for offset, idx in enumerate(timed_df.index):
            df.at[idx, "Group Sorting"] = start_gs + offset

        # Accessories on last timed relay
        last_idx = timed_df.index[-1]
        df.at[last_idx, "Accessories"] = "WAGO.249-116_ADV"
        df.at[last_idx, "Quantity of accessories"] = 1

        max_timed_gs = start_gs + len(timed_df.index) - 1
    else:
        # if none, timed "max" is max relay gs
        gs_relays = _to_numeric_series(df.loc[mask_2pole_combined | mask_4pole_combined, "Group Sorting"]).dropna()
        max_timed_gs = int(gs_relays.astype(int).max()) if not gs_relays.empty else 0

    # -------------------------------------------------------------------------
    # STEP 5b – BACKUP group (RE22R1AMR + K561/K562/K563) GS = next after timed
    # + add WAGO.249-116_ADV on last backup component
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

        # Add accessory on last backup component (stable order)
        backup_idxs = df[mask_backup_all].index.to_list()
        last_idx = backup_idxs[-1]
        df.at[last_idx, "Accessories"] = "WAGO.249-116_ADV"
        df.at[last_idx, "Quantity of accessories"] = 1

        # Mark forced function
        df.loc[mask_backup_all, "_force_function"] = "BACKUP"
        max_backup_gs = backup_gs
    else:
        max_backup_gs = max_timed_gs

    # -------------------------------------------------------------------------
    # STEP 5c – Finder 1POLE (FIN.39...) GS = after BACKUP (which is after timed)
    # + add WAGO.249-116_ADV
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
    # (must happen before PE renaming and final function prefix)
    # -------------------------------------------------------------------------
    gs_str = df["Group Sorting"].apply(_gs_to_str)
    has_gs = gs_str.astype(str).ne("")
    # Only prefix if not already +...
    df.loc[has_gs & ~df["Name"].astype(str).str.startswith("+", na=False), "Name"] = (
        "+" + gs_str[has_gs].astype(str) + df.loc[has_gs & ~df["Name"].astype(str).str.startswith("+", na=False), "Name"].astype(str)
    )

    # -------------------------------------------------------------------------
    # STEP 7 – PE renaming (WAGO.2002-3207_ADV) group-based (same GS -> same PE index)
    # -------------------------------------------------------------------------
    pe_type = "WAGO.2002-3207_ADV"
    mask_pe = df["Type"].astype(str).eq(pe_type)
    if mask_pe.any():
        pe_gs = _to_numeric_series(df.loc[mask_pe, "Group Sorting"])
        # unique gs sorted
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
    # STEP 8 – TERMINAL / PE COVER ACCESSORIES (WAGO.2002-3292_ADV)
    # - 1010 and 1110: cover only on last terminal of each "sub-group" by first 2 digits after -X
    # - other GS: cover on last terminal in GS group
    # -------------------------------------------------------------------------
    terminal_types = {"WAGO.2002-3201_ADV", "WAGO.2002-3207_ADV"}
    mask_term = df["Type"].astype(str).isin(terminal_types)

    def _subgroup_key_for_1010_1110(name_val: str) -> str:
        # expects "+1010-X118" etc.
        import re
        m = re.search(r"-X(\d{2})", str(name_val))
        return m.group(1) if m else "??"

    def _set_cover_on_last(idxs: List[int]) -> None:
        if not idxs:
            return
        last = idxs[-1]
        df.at[last, "Accessories"] = "WAGO.2002-3292_ADV"
        df.at[last, "Quantity of accessories"] = 1

    if mask_term.any():
        # Clear any existing cover to avoid duplicates
        # (optional – comment out if you want to preserve input)
        # df.loc[mask_term, "Accessories"] = df.loc[mask_term, "Accessories"].replace("WAGO.2002-3292_ADV", "")

        term_df = df[mask_term].copy()
        term_df["_gs"] = _to_numeric_series(term_df["Group Sorting"]).fillna(-1).astype(int)

        # Special for GS 1010 and 1110
        for special_gs in (1010, 1110):
            gmask = term_df["_gs"].eq(special_gs)
            if gmask.any():
                sub = term_df[gmask].copy()
                sub["_key"] = sub["Name"].apply(_subgroup_key_for_1010_1110)
                for _, grp in sub.groupby("_key", sort=False):
                    idxs = grp.index.to_list()
                    _set_cover_on_last(idxs)

        # Generic for other GS: cover on last row per GS group (excluding 1010/1110)
        other = term_df[~term_df["_gs"].isin([1010, 1110])].copy()
        if not other.empty:
            for _, grp in other.groupby("_gs", sort=False):
                idxs = grp.index.to_list()
                _set_cover_on_last(idxs)

    # -------------------------------------------------------------------------
    # STEP 9 – TERMINAL SPLIT BY QUANTITY (WAGO.2002-3201_ADV, WAGO.2002-3207_ADV)
    # + Designation: first blank, then 1..n-1
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
            # accessories stay on the row they were assigned to earlier only if you want it preserved
            rows.append(base)

            for i in range(1, n):
                r = row_dict.copy()
                r["Quantity"] = 1
                r["Designation"] = str(i)
                # keep accessories empty on split copies
                r["Accessories"] = ""
                r["Quantity of accessories"] = 0
                r["Accessories2"] = ""
                r["Quantity of accessories2"] = 0
                rows.append(r)
        else:
            # ensure fields exist
            row_dict["Designation"] = row_dict.get("Designation", "")
            rows.append(row_dict)

    df = pd.DataFrame(rows)

    # -------------------------------------------------------------------------
    # STEP 9b – PE terminal reduction rule: keep ceil(count/3) per PE group
    # (ONLY rows whose Name contains -PE<number>)
    # -------------------------------------------------------------------------
    name_s2 = df["Name"].astype(str)
    pe_num = name_s2.str.extract(r"-PE(\d+)", expand=False)
    mask_pe2 = pe_num.notna()

    if mask_pe2.any():
        keep_indices: List[int] = []
        pe_df = df[mask_pe2].copy()

        for pe_name, grp in pe_df.groupby("Name", sort=False):
            idxs = grp.index.to_list()
            count = len(idxs)
            needed = (count + 2) // 3  # ceil(count/3)
            keep_indices.extend(idxs[:needed])

        df = df[(~mask_pe2) | (df.index.isin(keep_indices))].copy()

    # -------------------------------------------------------------------------
    # STEP 10 – FUNCTION DESIGNATION -> into Name (DT full)
    # =FUNC + Name
    # BACKUP and 1POLE are forced by _force_function
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

    forced = df["_force_function"].astype(str) if "_force_function" in df.columns else pd.Series([""] * len(df))

    funcs: List[str] = []
    for idx in df.index:
        f = ""
        if "_force_function" in df.columns:
            ff = str(df.at[idx, "_force_function"]) if pd.notna(df.at[idx, "_force_function"]) else ""
            if ff.strip():
                f = ff.strip()
        if not f:
            f = type_to_function(str(df.at[idx, "Type"]))
        funcs.append(f)

    df["_function"] = funcs
    # Only apply if function exists
    has_func = df["_function"].astype(str).ne("")
    df.loc[has_func, "Name"] = "=" + df.loc[has_func, "_function"].astype(str) + df.loc[has_func, "Name"].astype(str)

    # cleanup helper cols
    df.drop(columns=[c for c in ["_function", "_force_function"] if c in df.columns], inplace=True, errors="ignore")

    # -------------------------------------------------------------------------
    # Build Removed DF
    # -------------------------------------------------------------------------
    removed_df = pd.concat(removed_parts, ignore_index=True) if removed_parts else pd.DataFrame(columns=list(df.columns) + ["Removed Reason"])

    # Ensure Removed includes Removed Reason
    if "Removed Reason" not in removed_df.columns:
        removed_df["Removed Reason"] = ""

    # -------------------------------------------------------------------------
    # Output workbook (Cleaned + Removed), styling invalid prefixes on Cleaned
    # Name column saved as TEXT even if starts with '='
    # -------------------------------------------------------------------------
    cleaned_df = df.copy()

    wb = Workbook()
    ws_clean = wb.active
    ws_clean.title = "Cleaned"
    ws_removed = wb.create_sheet("Removed")

    # Write cleaned
    for r_idx, row in enumerate(dataframe_to_rows(cleaned_df.drop(columns=["_highlight_invalid_prefix"], errors="ignore"), index=False, header=True), start=1):
        ws_clean.append(row)

    # Apply text formatting to Name column (col 1)
    for r in range(2, ws_clean.max_row + 1):
        cell = ws_clean.cell(row=r, column=1)
        cell.number_format = "@"
        cell.data_type = "s"  # force string, avoid Excel formula parsing

    # Highlight invalid prefix rows (based on stored flag from early step)
    # Need align row indices: header=1, data starts at row 2
    if "_highlight_invalid_prefix" in cleaned_df.columns:
        flags = cleaned_df["_highlight_invalid_prefix"].tolist()
        for i, is_invalid in enumerate(flags, start=2):
            if bool(is_invalid):
                for c in range(1, ws_clean.max_column + 1):
                    ws_clean.cell(row=i, column=c).fill = YELLOW_FILL

    # Write removed
    for r in dataframe_to_rows(removed_df, index=False, header=True):
        ws_removed.append(r)

    # Make Removed Name column also text (if present)
    # Find Name column index
    if ws_removed.max_row >= 1:
        headers = [ws_removed.cell(row=1, column=c).value for c in range(1, ws_removed.max_column + 1)]
        if "Name" in headers:
            name_col = headers.index("Name") + 1
            for r in range(2, ws_removed.max_row + 1):
                cell = ws_removed.cell(row=r, column=name_col)
                cell.number_format = "@"
                cell.data_type = "s"

    # Save to bytes
    bio = BytesIO()
    wb.save(bio)
    out_bytes = bio.getvalue()

    stats = {
        "input_rows": input_rows,
        "cleaned_rows": len(cleaned_df),
        "removed_rows": len(removed_df),
    }

    # Return cleaned_df without helper highlight col in preview
    cleaned_preview = cleaned_df.drop(columns=["_highlight_invalid_prefix"], errors="ignore")

    return cleaned_preview, removed_df, out_bytes, stats
