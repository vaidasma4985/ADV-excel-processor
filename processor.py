from __future__ import annotations

import re
from io import BytesIO
from typing import Any, Dict, List, Tuple

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows

YELLOW_FILL = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _ensure_cols(df: pd.DataFrame, cols: List[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"Trūksta privalomų stulpelių: {', '.join(missing)}")


def _append_removed(parts: List[pd.DataFrame], df_part: pd.DataFrame, reason: str) -> None:
    if df_part.empty:
        return
    tmp = df_part.copy()
    tmp["Removed Reason"] = reason
    parts.append(tmp)


def _to_num(v: Any) -> float | None:
    x = pd.to_numeric(v, errors="coerce")
    return None if pd.isna(x) else float(x)


def _gs_int(v: Any) -> int | None:
    n = _to_num(v)
    return None if n is None else int(n)


def _gs_str(v: Any) -> str:
    n = _gs_int(v)
    return "" if n is None else str(n)


def _starts_with_any(s: pd.Series, prefixes: Tuple[str, ...]) -> pd.Series:
    return s.astype(str).str.startswith(prefixes, na=False)


def _next_free_gs(existing: set[int], preferred: int) -> int:
    g = preferred
    while g in existing:
        g += 1
    existing.add(g)
    return g


def _extract_x_first2(name: str) -> str | None:
    m = re.search(r"-X(\d{2})\d{2}\b", str(name))
    return m.group(1) if m else None


def _extract_x4(name: str) -> int | None:
    """
    Ištraukia X**** kaip int:
      -X1912 -> 1912
      -X1114 -> 1114
    """
    m = re.search(r"-X(\d{4})\b", str(name))
    return int(m.group(1)) if m else None


def _terminal_sort_key(name: str) -> int:
    """
    Rikiavimo raktas, kad X192A* galėtume laikyti "tarp" X1922 ir X1953.
    Prielaida: X192A3 = 1923 (t.y. 192 + A3).
    """
    s = str(name)

    m = re.search(r"-X(\d{4})\b", s)
    if m:
        return int(m.group(1))

    m = re.search(r"-X(\d{3})A(\d)\b", s)  # X192A3
    if m:
        return int(m.group(1) + m.group(2))  # "192"+"3" => 1923

    m = re.search(r"-X(\d+)", s)
    if m:
        return int(m.group(1))

    return 10**9


# -----------------------------------------------------------------------------
# Terminal rule: X192A insertion inside one GS group
# -----------------------------------------------------------------------------
def apply_x192a_terminal_gs_rules(df: pd.DataFrame) -> pd.DataFrame:
    """
    Vienoje terminalų GS grupėje (pvz. 2010), jei yra X192A*:
      - X**** iki X192A paliekam tame pačiame GS (2010)
      - visi X192A* perkelti į naują neegzistuojantį GS = next_free(2010+1) (pvz. 2011)
      - visi terminalai "po X192A" perkelti į dar sekantį GS = next_free(2011+1) (pvz. 2012)
      - kitų GS grupių nekeičiam

    SVARBU: eilutės, kurioms pakeičiam GS, pažymimos kaip GS_IS_GENERATED=True,
    kad dangteliai būtų dedami tik pagal originalų GS (GS_ORIG), o ne sugeneruotą.
    """

    terminal_types = {"WAGO.2002-3201_ADV", "WAGO.2002-3207_ADV"}
    is_terminal = df["Type"].astype(str).isin(terminal_types)

    gs_num = pd.to_numeric(df["Group Sorting"], errors="coerce")
    has_gs = gs_num.notna()

    existing_gs: set[int] = set(gs_num.dropna().astype(int).tolist())

    work = df[is_terminal & has_gs].copy()
    if work.empty:
        return df

    work["_base_gs"] = gs_num[is_terminal & has_gs].astype(int)
    work["_xkey"] = work["Name"].astype(str).apply(_terminal_sort_key)
    work["_is_x192a"] = work["Name"].astype(str).str.contains(r"-X192A\d+\b", regex=True, na=False)

    for base_gs, grp in work.groupby("_base_gs", sort=True):
        if not grp["_is_x192a"].any():
            continue

        gs_for_x192a = _next_free_gs(existing_gs, int(base_gs) + 1)
        max_x192a_key = int(grp.loc[grp["_is_x192a"], "_xkey"].max())

        after_mask = (grp["_xkey"] > max_x192a_key) & (~grp["_is_x192a"])

        gs_for_after = None
        if after_mask.any():
            gs_for_after = _next_free_gs(existing_gs, gs_for_x192a + 1)

        idx_x192a = grp.loc[grp["_is_x192a"]].index
        df.loc[idx_x192a, "Group Sorting"] = gs_for_x192a
        df.loc[idx_x192a, "GS_IS_GENERATED"] = True

        if gs_for_after is not None:
            idx_after = grp.loc[after_mask].index
            df.loc[idx_after, "Group Sorting"] = gs_for_after
            df.loc[idx_after, "GS_IS_GENERATED"] = True

    return df


# -----------------------------------------------------------------------------
# Main processing
# -----------------------------------------------------------------------------
def process_excel(file_bytes: bytes) -> Tuple[pd.DataFrame, pd.DataFrame, bytes, Dict[str, int]]:
    df = pd.read_excel(BytesIO(file_bytes), sheet_name=0, engine="openpyxl")
    input_rows = len(df)

    required = ["Name", "Type", "Quantity", "Group Sorting"]
    _ensure_cols(df, required)

    df["Name"] = df["Name"].astype(str)
    df["Type"] = df["Type"].astype(str)

    # ensure columns exist
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
    # STEP 0 – remove non-numeric Group Sorting (but not empty)
    # -------------------------------------------------------------------------
    gs_raw = df["Group Sorting"]
    gs_num = pd.to_numeric(gs_raw, errors="coerce")
    non_numeric = gs_raw.notna() & (gs_raw.astype(str).str.strip() != "") & gs_num.isna()
    _append_removed(removed_parts, df[non_numeric], "Removed: Group Sorting is not numeric")
    df = df[~non_numeric].copy()

    # ---- NEW: store ORIGINAL GS from uploaded file, before any GS edits ----
    df["GS_ORIG"] = pd.to_numeric(df["Group Sorting"], errors="coerce")  # float or NaN
    df["GS_IS_GENERATED"] = False  # by default nothing is generated

    # -------------------------------------------------------------------------
    # STEP 1 – remove by Name prefixes
    # -------------------------------------------------------------------------
    remove_prefixes = ("-B", "-C", "-R", "-M", "-P", "-Q", "-S", "-W", "-T")
    m1 = _starts_with_any(df["Name"], remove_prefixes)
    _append_removed(removed_parts, df[m1], "Removed by Name prefix (-B/-C/-R/-M/-P/-Q/-S/-W/-T)")
    df = df[~m1].copy()

    # -------------------------------------------------------------------------
    # STEP 2 – invalid prefix highlight (not removed)
    # -------------------------------------------------------------------------
    valid_prefixes = ("-F", "-K", "-X")
    df["_highlight_invalid_prefix"] = ~_starts_with_any(df["Name"], valid_prefixes)

    # -------------------------------------------------------------------------
    # STEP 3 – Type allowlist
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
    m3 = df["Type"].isin(allowed_types)
    _append_removed(removed_parts, df[~m3], "Removed by Type filter (not in allowed list)")
    df = df[m3].copy()

    # -------------------------------------------------------------------------
    # STEP 4 – map types (WAGO/SE) + _ADV
    # -------------------------------------------------------------------------
    # WAGO list for prefix
    wago_types = {
        "2002-1611/1000-541",
        "2002-1611/1000-836",
        "2002-3201",
        "2002-3207",
        "249-116",
    }
    mw = df["Type"].isin(wago_types)
    df.loc[mw, "Type"] = "WAGO." + df.loc[mw, "Type"].astype(str)

    se_map = {
        "RGZE1S48M": "SE.RGZE1S48M",
        "RXG22P7": "SE.RXG22P7",
        "RXG22BD": "SE.RXG22BD",
        "RXM4GB2BD": "SE.RXM4GB2BD",
        "RXZE2S114M": "SE.RXZE2S114M",
        "A9F04604": "SE.A9F04604",
    }
    df["Type"] = df["Type"].replace(se_map)

    adv_map = {
        "WAGO.2002-3207": "WAGO.2002-3207_ADV",
        "WAGO.2002-3201": "WAGO.2002-3201_ADV",
        "WAGO.2002-3292": "WAGO.2002-3292_ADV",
        "WAGO.2002-991": "WAGO.2002-991_ADV",
        "WAGO.249-116": "WAGO.249-116_ADV",
        "WAGO.2002-1611/1000-541": "WAGO.2002-1611/1000-541_ADV",
        "WAGO.2002-1611/1000-836": "WAGO.2002-1611/1000-836_ADV",
        "SE.A9F04604": "SE.A9F04604_ADV",
    }
    df["Type"] = df["Type"].replace(adv_map)

    # -------------------------------------------------------------------------
    # STEP 4b – relay merge by Name (2POLE/4POLE)
    # -------------------------------------------------------------------------
    def _merge_relay(base_type: str, combined_type: str) -> None:
        nonlocal df
        mb = df["Type"].astype(str).eq(base_type)
        if not mb.any():
            return

        drop_idxs: List[int] = []
        for name_val, grp in df[df["Name"].isin(df.loc[mb, "Name"])].groupby("Name", sort=False):
            idxs = grp.index.to_list()
            keep = None
            for i in idxs:
                if df.at[i, "Type"] == base_type:
                    keep = i
                    break
            if keep is None:
                keep = idxs[0]

            for i in idxs:
                if i != keep:
                    drop_idxs.append(i)

            df.at[keep, "Type"] = combined_type
            df.at[keep, "Quantity"] = 1

        if drop_idxs:
            _append_removed(removed_parts, df.loc[drop_idxs], "Removed: merged into relay combined row")
            df = df.drop(index=drop_idxs).copy()

    _merge_relay("SE.RGZE1S48M", "SE.RGZE1S48M + SE.RXG22P7")
    _merge_relay("SE.RXZE2S114M", "SE.RXZE2S114M + SE.RXM4GB2BD")

    # -------------------------------------------------------------------------
    # STEP 5 – Terminal GS insertion rule for X192A*
    # (IMPORTANT: before +GS into Name)
    # -------------------------------------------------------------------------
    df = apply_x192a_terminal_gs_rules(df)

    # -------------------------------------------------------------------------
    # STEP 6 – Fuses GS grouping (per your latest spec)
    # -------------------------------------------------------------------------
    existing_gs: set[int] = set(pd.to_numeric(df["Group Sorting"], errors="coerce").dropna().astype(int).tolist())

    m541 = df["Type"].astype(str).eq("WAGO.2002-1611/1000-541_ADV")
    m836 = df["Type"].astype(str).eq("WAGO.2002-1611/1000-836_ADV")

    if m541.any():
        gs541 = _next_free_gs(existing_gs, 1)
        df.loc[m541, "Group Sorting"] = gs541

    if m836.any():
        names = df.loc[m836, "Name"].astype(str)

        mf9 = names.str.contains(r"-F9", regex=True, na=False)
        mf192a = names.str.contains(r"-F192A", regex=True, na=False)
        mf192 = names.str.contains(r"-F192", regex=True, na=False) & (~mf192a)

        if mf9.any():
            gs_f9 = _next_free_gs(existing_gs, 1)
            df.loc[df.loc[m836].index[mf9.values], "Group Sorting"] = gs_f9

        if mf192a.any():
            gs_f192a = _next_free_gs(existing_gs, 1)
            df.loc[df.loc[m836].index[mf192a.values], "Group Sorting"] = gs_f192a

        not_f9 = ~mf9
        not_f192a = ~mf192a

        is_f1xxx = names.str.contains(r"-F1\d{3}", regex=True, na=False)
        group3_mask = not_f9 & not_f192a & (mf192 | is_f1xxx)

        if group3_mask.any():
            gs_g3 = _next_free_gs(existing_gs, 1)
            df.loc[df.loc[m836].index[group3_mask.values], "Group Sorting"] = gs_g3

        group5_mask = not_f9 & not_f192a & (~group3_mask)
        if group5_mask.any():
            gs_g5 = _next_free_gs(existing_gs, 1)
            df.loc[df.loc[m836].index[group5_mask.values], "Group Sorting"] = gs_g5

    # -------------------------------------------------------------------------
    # STEP 7 – Add +GS to Name (terminals + fuses + relays)
    # -------------------------------------------------------------------------
    gss = df["Group Sorting"].apply(_gs_str)
    has_gs = gss.ne("")
    not_prefixed = ~df["Name"].astype(str).str.startswith("+", na=False)
    df.loc[has_gs & not_prefixed, "Name"] = "+" + gss[has_gs & not_prefixed] + df.loc[has_gs & not_prefixed, "Name"].astype(str)

    # -------------------------------------------------------------------------
    # STEP 8 – Terminal split by Quantity + Designation (3201/3207 only)
    # -------------------------------------------------------------------------
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0)

    rows: List[dict] = []
    for _, r in df.iterrows():
        d = r.to_dict()
        t = str(d.get("Type", ""))
        qty = pd.to_numeric(d.get("Quantity", 0), errors="coerce")

        if t in ("WAGO.2002-3201_ADV", "WAGO.2002-3207_ADV") and pd.notna(qty) and qty > 1:
            n = int(qty)
            base = d.copy()
            base["Quantity"] = 1
            base["Designation"] = ""
            rows.append(base)

            for i in range(1, n):
                rr = d.copy()
                rr["Quantity"] = 1
                rr["Designation"] = str(i)
                rr["Accessories"] = ""
                rr["Quantity of accessories"] = 0
                rr["Accessories2"] = ""
                rr["Quantity of accessories2"] = 0
                rows.append(rr)
        else:
            d["Designation"] = d.get("Designation", "")
            rows.append(d)

    df = pd.DataFrame(rows)

    # -------------------------------------------------------------------------
    # STEP 9 – PE rename + PE /3 reduction
    # -------------------------------------------------------------------------
    name_s = df["Name"].astype(str)
    pe_mask = name_s.str.contains(r"-PE\d+\b", regex=True, na=False)

    if pe_mask.any():
        keep: List[int] = []
        for pe_name, grp in df[pe_mask].groupby("Name", sort=False):
            idxs = grp.index.to_list()
            cnt = len(idxs)
            need = (cnt + 2) // 3  # ceil(cnt/3)
            keep.extend(idxs[:need])

        df = df[(~pe_mask) | (df.index.isin(keep))].copy()

    # -------------------------------------------------------------------------
    # STEP 10 – Accessories:
    # A) Terminal covers WAGO.2002-3292_ADV
    #    IMPORTANT: covers are added ONLY for ORIGINAL GS (GS_ORIG) and ONLY for rows
    #    where GS_IS_GENERATED=False (so X192/X192A moved rows won't get covers)
    # B) Fuse accessories (2002-991 / 249-116) on last element of each fuse GS group
    # -------------------------------------------------------------------------
    df["Accessories"] = df["Accessories"].fillna("")
    df["Accessories2"] = df["Accessories2"].fillna("")
    df["Quantity of accessories"] = pd.to_numeric(df["Quantity of accessories"], errors="coerce").fillna(0).astype(int)
    df["Quantity of accessories2"] = pd.to_numeric(df["Quantity of accessories2"], errors="coerce").fillna(0).astype(int)

    terminal_types = {"WAGO.2002-3201_ADV", "WAGO.2002-3207_ADV"}
    is_terminal_all = df["Type"].astype(str).isin(terminal_types)

    # --- cover eligible terminals: ONLY ORIGINAL rows ---
    is_original = ~df["GS_IS_GENERATED"].fillna(False)
    is_terminal = is_terminal_all & is_original

    gs_orig_num = pd.to_numeric(df["GS_ORIG"], errors="coerce")
    df["_gs_orig_sort"] = gs_orig_num.fillna(10**9).astype(int)

    def _set_cover(idx: int) -> None:
        if str(df.at[idx, "Accessories"]).strip() == "":
            df.at[idx, "Accessories"] = "WAGO.2002-3292_ADV"
            df.at[idx, "Quantity of accessories"] = 1

    # 1010 & 1110 (based on ORIGINAL GS only)
    for g in (1010, 1110):
        m = is_terminal & df["_gs_orig_sort"].eq(g)
        if not m.any():
            continue
        tmp = df[m].copy()
        tmp["_sub"] = tmp["Name"].astype(str).apply(_extract_x_first2)
        for _, grp in tmp.groupby("_sub", sort=False):
            last_idx = grp.index.to_list()[-1]
            _set_cover(last_idx)

    # 1030 special: cover after X**14 per subgroup (based on ORIGINAL GS only)
    m1030 = is_terminal & df["_gs_orig_sort"].eq(1030)
    if m1030.any():
        tmp = df[m1030].copy()
        tmp["_sub"] = tmp["Name"].astype(str).apply(_extract_x_first2)

        for _, grp in tmp.groupby("_sub", sort=False):
            idx14 = None
            for idx in grp.index:
                x4 = _extract_x4(df.at[idx, "Name"])
                if x4 is not None and str(x4).endswith("14"):
                    idx14 = idx
            if idx14 is None:
                idx14 = grp.index.to_list()[-1]
            _set_cover(idx14)

    # other ORIGINAL GS: last terminal in ORIGINAL GS gets cover
    for gs_val, grp in df[is_terminal & gs_orig_num.notna()].groupby("_gs_orig_sort", sort=True):
        if int(gs_val) in (1010, 1110, 1030):
            continue
        last_idx = grp.index.to_list()[-1]
        _set_cover(last_idx)

    # Fuse accessories on last row of each fuse-GS group (uses CURRENT GS – ok)
    gs_num2 = pd.to_numeric(df["Group Sorting"], errors="coerce")
    df["_gs_sort"] = gs_num2.fillna(10**9).astype(int)

    is_fuse = df["Type"].astype(str).isin({"WAGO.2002-1611/1000-541_ADV", "WAGO.2002-1611/1000-836_ADV"})
    if is_fuse.any():
        for gs_val, grp in df[is_fuse & gs_num2.notna()].groupby("_gs_sort", sort=True):
            last_idx = grp.index.to_list()[-1]
            df.at[last_idx, "Accessories"] = "WAGO.2002-991_ADV"
            df.at[last_idx, "Quantity of accessories"] = 1

            names_grp = grp["Name"].astype(str)
            has_f9 = names_grp.str.contains(r"-F9", regex=True, na=False).any()
            if df.at[last_idx, "Type"] == "WAGO.2002-1611/1000-541_ADV" or (not has_f9):
                df.at[last_idx, "Accessories2"] = "WAGO.249-116_ADV"
                df.at[last_idx, "Quantity of accessories2"] = 1

    # -------------------------------------------------------------------------
    # STEP 11 – Function designation into Name
    # -------------------------------------------------------------------------
    def type_to_func(t: str) -> str:
        m = {
            "SE.A9F04604_ADV": "POWER",
            "WAGO.2002-1611/1000-541_ADV": "FUSES",
            "WAGO.2002-1611/1000-836_ADV": "FUSES",
            "SE.RGZE1S48M + SE.RXG22P7": "2POLE",
            "SE.RXZE2S114M + SE.RXM4GB2BD": "4POLE",
            "WAGO.2002-3201_ADV": "CONTROL",
            "WAGO.2002-3207_ADV": "CONTROL",
        }
        return m.get(t, "")

    df["_func"] = df["Type"].astype(str).map(type_to_func).fillna("")
    hasf = df["_func"].astype(str).ne("")
    df.loc[hasf, "Name"] = "=" + df.loc[hasf, "_func"].astype(str) + df.loc[hasf, "Name"].astype(str)
    df.drop(columns=["_func"], inplace=True, errors="ignore")

    # -------------------------------------------------------------------------
    # STEP 12 – Final sort by numeric GS then Name (stable)
    # -------------------------------------------------------------------------
    df = df.sort_values(["_gs_sort", "Name"], kind="stable").drop(
        columns=["_gs_sort", "_gs_orig_sort"], errors="ignore"
    )

    # -------------------------------------------------------------------------
    # Removed DF
    # -------------------------------------------------------------------------
    removed_df = pd.concat(removed_parts, ignore_index=True) if removed_parts else pd.DataFrame()
    if removed_df.empty:
        removed_df = pd.DataFrame(columns=list(df.columns) + ["Removed Reason"])
    elif "Removed Reason" not in removed_df.columns:
        removed_df["Removed Reason"] = ""

    cleaned_df = df.copy()

    # -------------------------------------------------------------------------
    # Workbook output
    # -------------------------------------------------------------------------
    wb = Workbook()
    ws_c = wb.active
    ws_c.title = "Cleaned"
    ws_r = wb.create_sheet("Removed")

    # Cleaned
    out_clean = cleaned_df.drop(columns=["_highlight_invalid_prefix"], errors="ignore")
    for row in dataframe_to_rows(out_clean, index=False, header=True):
        ws_c.append(row)

    # Force Name column as TEXT (keep '=' for EPLAN)
    for r in range(2, ws_c.max_row + 1):
        c = ws_c.cell(row=r, column=1)
        c.number_format = "@"
        c.data_type = "s"

    # Highlight invalid prefixes
    if "_highlight_invalid_prefix" in cleaned_df.columns:
        flags = cleaned_df["_highlight_invalid_prefix"].tolist()
        for excel_row, bad in enumerate(flags, start=2):
            if bool(bad):
                for col in range(1, ws_c.max_column + 1):
                    ws_c.cell(row=excel_row, column=col).fill = YELLOW_FILL

    # Removed
    for row in dataframe_to_rows(removed_df, index=False, header=True):
        ws_r.append(row)

    # Force Removed Name as TEXT too
    if ws_r.max_row >= 1:
        headers = [ws_r.cell(row=1, column=c).value for c in range(1, ws_r.max_column + 1)]
        if "Name" in headers:
            name_col = headers.index("Name") + 1
            for r in range(2, ws_r.max_row + 1):
                c = ws_r.cell(row=r, column=name_col)
                c.number_format = "@"
                c.data_type = "s"

    bio = BytesIO()
    wb.save(bio)
    out_bytes = bio.getvalue()

    stats = {
        "input_rows": input_rows,
        "cleaned_rows": len(out_clean),
        "removed_rows": len(removed_df),
    }

    return out_clean, removed_df, out_bytes, stats
