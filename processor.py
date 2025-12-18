from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List, Tuple

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows

YELLOW_FILL = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")


# -----------------------------
# Helpers
# -----------------------------
def _ensure_cols(df: pd.DataFrame, cols: List[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"Trūksta privalomų stulpelių: {', '.join(missing)}")


def _to_num(v: Any) -> float | None:
    x = pd.to_numeric(v, errors="coerce")
    return None if pd.isna(x) else float(x)


def _to_numeric_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def _gs_str(v: Any) -> str:
    n = _to_num(v)
    if n is None:
        return ""
    return str(int(n))


def _append_removed(parts: List[pd.DataFrame], df_part: pd.DataFrame, reason: str) -> None:
    if df_part.empty:
        return
    tmp = df_part.copy()
    tmp["Removed Reason"] = reason
    parts.append(tmp)


def _starts_with_any(s: pd.Series, prefixes: Tuple[str, ...]) -> pd.Series:
    return s.astype(str).str.startswith(prefixes, na=False)


def _extract_k_number(name: str) -> int:
    import re

    m = re.search(r"-K(\d+)", str(name))
    if not m:
        return 10**9
    return int(m.group(1))


def _extract_x_two_digits(name: str) -> str | None:
    import re

    m = re.search(r"-X(\d{2})", str(name))
    return m.group(1) if m else None


def _next_free_gs(existing: set[int], start: int = 1) -> int:
    g = start
    while g in existing:
        g += 1
    existing.add(g)
    return g


# -----------------------------
# Main
# -----------------------------
def process_excel(file_bytes: bytes) -> Tuple[pd.DataFrame, pd.DataFrame, bytes, Dict[str, int]]:
    df = pd.read_excel(BytesIO(file_bytes), sheet_name=0, engine="openpyxl")
    input_rows = len(df)

    required = ["Name", "Type", "Quantity", "Group Sorting"]
    _ensure_cols(df, required)

    # Normalize
    df["Name"] = df["Name"].astype(str)
    df["Type"] = df["Type"].astype(str)

    # Ensure extra columns exist (we will fill later)
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

    # -----------------------------
    # STEP 1 – remove by name prefix
    # -----------------------------
    remove_prefixes = ("-B", "-C", "-R", "-M", "-P", "-Q", "-S", "-W", "-T")
    m1 = _starts_with_any(df["Name"], remove_prefixes)
    _append_removed(removed_parts, df[m1], "Removed by Name prefix (-B/-C/-R/-M/-P/-Q/-S/-W/-T)")
    df = df[~m1].copy()

    # -----------------------------
    # STEP 2 – invalid prefix highlight (not removed)
    # -----------------------------
    valid_prefixes = ("-F", "-K", "-X")
    df["_highlight_invalid_prefix"] = ~_starts_with_any(df["Name"], valid_prefixes)

    # -----------------------------
    # STEP 3 – Type allow list (including special keepers)
    # -----------------------------
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
        "RE22R1AMR",
        "39.00.8.230.8240",
    }
    m3 = df["Type"].isin(allowed_types)
    _append_removed(removed_parts, df[~m3], "Removed by Type filter (not in allowed list)")
    df = df[m3].copy()

    # -----------------------------
    # STEP 4 – map types (WAGO/SE/FIN + ADV)
    # -----------------------------
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

    # Special keepers -> ADV types
    df.loc[df["Type"] == "RE17LCBM", "Type"] = "SE.RE17LCBM_ADV"
    df.loc[df["Type"] == "RE22R1AMR", "Type"] = "SE.RE22R1AMR_ADV"
    df.loc[df["Type"] == "39.00.8.230.8240", "Type"] = "FIN.39.00.8.230.8240_ADV"

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

    # -----------------------------
    # STEP 4b – relay merge by Name (keep base row)
    # -----------------------------
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

    # -----------------------------
    # STEP 5 – GS allocator base (existing)
    # -----------------------------
    existing_gs = set(_to_numeric_series(df["Group Sorting"]).dropna().astype(int).tolist())

    # -----------------------------
    # STEP 5a – relays get ONLY 2 GS numbers
    # -----------------------------
    m2p = df["Type"].astype(str).eq("SE.RGZE1S48M + SE.RXG22P7")
    m4p = df["Type"].astype(str).eq("SE.RXZE2S114M + SE.RXM4GB2BD")

    if m2p.any():
        gs_2p = _next_free_gs(existing_gs, 1)
        df.loc[m2p, "Group Sorting"] = gs_2p
    else:
        gs_2p = None

    if m4p.any():
        gs_4p = _next_free_gs(existing_gs, (gs_2p or 1) + 1)
        df.loc[m4p, "Group Sorting"] = gs_4p
    else:
        gs_4p = None

    max_relay_gs = 0
    gs_rel = _to_numeric_series(df.loc[m2p | m4p, "Group Sorting"]).dropna()
    if not gs_rel.empty:
        max_relay_gs = int(gs_rel.astype(int).max())

    # -----------------------------
    # STEP 5b – timed relays (-K192*) GS SEQUENCE after relays
    # -----------------------------
    name_s = df["Name"].astype(str)
    mtimed = name_s.str.contains(r"-K192", regex=True, na=False)

    if mtimed.any():
        timed = df[mtimed].copy()
        timed["_kno"] = timed["Name"].apply(_extract_k_number)
        timed = timed.sort_values(["_kno"], kind="stable")

        start = max_relay_gs + 1
        for offset, idx in enumerate(timed.index):
            df.at[idx, "Group Sorting"] = start + offset

        # accessory to last timed
        last_idx = timed.index[-1]
        df.at[last_idx, "Accessories"] = "WAGO.249-116_ADV"
        df.at[last_idx, "Quantity of accessories"] = 1

        max_timed_gs = start + len(timed.index) - 1
    else:
        max_timed_gs = max_relay_gs

    # -----------------------------
    # ✅ STEP 5c – FUSES GS (THIS FIXES YOUR “no +* for fuses”)
    # -----------------------------
    m541 = df["Type"].astype(str).eq("WAGO.2002-1611/1000-541_ADV")
    m836 = df["Type"].astype(str).eq("WAGO.2002-1611/1000-836_ADV")

    # 541: one new GS for all
    if m541.any():
        gs541 = _next_free_gs(existing_gs, 1)
        df.loc[m541, "Group Sorting"] = gs541

    # 836: split into two groups: names containing -F9 vs others
    if m836.any():
        n836 = df.loc[m836, "Name"].astype(str)
        mf9 = n836.str.contains(r"-F9", regex=True, na=False)
        idxs = df[m836].index

        if mf9.any():
            gs836_f9 = _next_free_gs(existing_gs, 1)
            df.loc[idxs[mf9.values], "Group Sorting"] = gs836_f9

        if (~mf9).any():
            gs836_other = _next_free_gs(existing_gs, 1)
            df.loc[idxs[(~mf9).values], "Group Sorting"] = gs836_other

    # -----------------------------
    # STEP 5d – BACKUP group (RE22 + K561/2/3) GS = next after timed
    # -----------------------------
    mbackup_names = (
        name_s.str.startswith("-K561", na=False)
        | name_s.str.startswith("-K562", na=False)
        | name_s.str.startswith("-K563", na=False)
    )
    mre22 = df["Type"].astype(str).eq("SE.RE22R1AMR_ADV")
    mbackup = mbackup_names | mre22

    if mbackup.any():
        gs_backup = max_timed_gs + 1
        df.loc[mbackup, "Group Sorting"] = gs_backup
        df.loc[mbackup, "_force_function"] = "BACKUP"

        last_idx = df[mbackup].index.to_list()[-1]
        df.at[last_idx, "Accessories"] = "WAGO.249-116_ADV"
        df.at[last_idx, "Quantity of accessories"] = 1

        max_backup_gs = gs_backup
    else:
        max_backup_gs = max_timed_gs

    # -----------------------------
    # STEP 5e – Finder 1POLE after BACKUP
    # -----------------------------
    mfin = df["Type"].astype(str).eq("FIN.39.00.8.230.8240_ADV")
    if mfin.any():
        gs_fin = max_backup_gs + 1
        df.loc[mfin, "Group Sorting"] = gs_fin
        df.loc[mfin, "_force_function"] = "1POLE"

        last_idx = df[mfin].index.to_list()[-1]
        df.at[last_idx, "Accessories"] = "WAGO.249-116_ADV"
        df.at[last_idx, "Quantity of accessories"] = 1

    # -----------------------------
    # STEP 6 – add +GS to Name (for all rows with GS)
    # -----------------------------
    gss = df["Group Sorting"].apply(_gs_str)
    has_gs = gss.ne("")
    not_prefixed = ~df["Name"].astype(str).str.startswith("+", na=False)

    df.loc[has_gs & not_prefixed, "Name"] = "+" + gss[has_gs & not_prefixed] + df.loc[has_gs & not_prefixed, "Name"].astype(str)

    # -----------------------------
    # STEP 7 – PE renaming (WAGO.2002-3207_ADV -> +GS-PE<n>)
    # -----------------------------
    mpe = df["Type"].astype(str).eq("WAGO.2002-3207_ADV")
    if mpe.any():
        pe_gs = _to_numeric_series(df.loc[mpe, "Group Sorting"]).dropna().astype(int)
        uniq = sorted(pe_gs.unique().tolist())
        gs_to_pe = {gs: i + 1 for i, gs in enumerate(uniq)}

        for idx in df[mpe].index:
            gs_val = _to_num(df.at[idx, "Group Sorting"])
            if gs_val is None:
                continue
            gs_int = int(gs_val)
            pe_idx = gs_to_pe.get(gs_int, 1)
            df.at[idx, "Name"] = f"+{gs_int}-PE{pe_idx}"

    # -----------------------------
    # STEP 8 – FUSE accessories rules (as per your earlier requirements)
    # - last 541 gets 2002-991 + 249-116 (in Accessories2)
    # - 836: last -F9 group gets 2002-991
    # - 836: last non-F9 group gets 2002-991 + 249-116
    # -----------------------------
    df["Accessories"] = df["Accessories"].fillna("")
    df["Accessories2"] = df["Accessories2"].fillna("")
    df["Quantity of accessories"] = pd.to_numeric(df["Quantity of accessories"], errors="coerce").fillna(0).astype(int)
    df["Quantity of accessories2"] = pd.to_numeric(df["Quantity of accessories2"], errors="coerce").fillna(0).astype(int)

    if m541.any():
        idxs = df[m541].index.to_list()
        if idxs:
            last = idxs[-1]
            df.at[last, "Accessories"] = "WAGO.2002-991_ADV"
            df.at[last, "Quantity of accessories"] = 1
            df.at[last, "Accessories2"] = "WAGO.249-116_ADV"
            df.at[last, "Quantity of accessories2"] = 1

    if m836.any():
        # find two groups again after +GS prefix (still contains -F9 somewhere)
        names = df.loc[m836, "Name"].astype(str)
        mf9 = names.str.contains(r"-F9", regex=True, na=False)
        idxs_all = df[m836].index.to_list()

        idxs_f9 = [i for i, is_f9 in zip(df[m836].index, mf9.values) if bool(is_f9)]
        idxs_other = [i for i, is_f9 in zip(df[m836].index, mf9.values) if not bool(is_f9)]

        if idxs_f9:
            last = idxs_f9[-1]
            df.at[last, "Accessories"] = "WAGO.2002-991_ADV"
            df.at[last, "Quantity of accessories"] = 1

        if idxs_other:
            last = idxs_other[-1]
            df.at[last, "Accessories"] = "WAGO.2002-991_ADV"
            df.at[last, "Quantity of accessories"] = 1
            df.at[last, "Accessories2"] = "WAGO.249-116_ADV"
            df.at[last, "Quantity of accessories2"] = 1

    # -----------------------------
    # STEP 9 – Terminal split by Quantity + Designation (3201/3207 only)
    # -----------------------------
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

    # -----------------------------
    # ✅ STEP 9b – PE “/3” reduction (keep ceil(count/3) rows per PE group)
    # Group key is final PE Name like "+1025-PE1"
    # -----------------------------
    name_s2 = df["Name"].astype(str)
    pe_num = name_s2.str.extract(r"-PE(\d+)", expand=False)
    mpe2 = pe_num.notna()

    if mpe2.any():
        keep: List[int] = []
        pe_df = df[mpe2].copy()
        for pe_name, grp in pe_df.groupby("Name", sort=False):
            idxs = grp.index.to_list()
            cnt = len(idxs)
            need = (cnt + 2) // 3  # ceil(cnt/3)
            keep.extend(idxs[:need])

        df = df[(~mpe2) | (df.index.isin(keep))].copy()

    # -----------------------------
    # STEP 10 – Function designation -> into Name
    # TIMED_RELAYS for -K192* by Name (always)
    # BACKUP / 1POLE by forced flag
    # else by Type map
    # -----------------------------
    def type_to_func(t: str) -> str:
        m = {
            "SE.A9F04604_ADV": "POWER",
            "WAGO.2002-1611/1000-541_ADV": "FUSES",
            "WAGO.2002-1611/1000-836_ADV": "FUSES",
            "SE.RGZE1S48M + SE.RXG22P7": "2POLE",
            "SE.RXZE2S114M + SE.RXM4GB2BD": "4POLE",
            "WAGO.2002-3201_ADV": "CONTROL",
            "WAGO.2002-3207_ADV": "CONTROL",
            "SE.RE17LCBM_ADV": "TIMED_RELAYS",  # jei kada norėsi ir pagal Type
        }
        return m.get(t, "")

    funcs: List[str] = []
    for idx in df.index:
        namev = str(df.at[idx, "Name"]) if pd.notna(df.at[idx, "Name"]) else ""
        f = ""

        if "-K192" in namev:
            f = "TIMED_RELAYS"

        if not f and "_force_function" in df.columns:
            ff = str(df.at[idx, "_force_function"]) if pd.notna(df.at[idx, "_force_function"]) else ""
            if ff.strip():
                f = ff.strip()

        if not f:
            f = type_to_func(str(df.at[idx, "Type"]))

        funcs.append(f)

    df["_function"] = funcs
    hasf = df["_function"].astype(str).ne("")
    df.loc[hasf, "Name"] = "=" + df.loc[hasf, "_function"].astype(str) + df.loc[hasf, "Name"].astype(str)

    df.drop(columns=[c for c in ["_function", "_force_function"] if c in df.columns], inplace=True, errors="ignore")

    # -----------------------------
    # Removed DF
    # -----------------------------
    removed_df = pd.concat(removed_parts, ignore_index=True) if removed_parts else pd.DataFrame()
    if not removed_df.empty and "Removed Reason" not in removed_df.columns:
        removed_df["Removed Reason"] = ""
    if removed_df.empty:
        removed_df = pd.DataFrame(columns=list(df.columns) + ["Removed Reason"])

    cleaned_df = df.copy()

    # -----------------------------
    # Workbook output (Name forced as TEXT, highlight invalid prefixes)
    # -----------------------------
    wb = Workbook()
    ws_c = wb.active
    ws_c.title = "Cleaned"
    ws_r = wb.create_sheet("Removed")

    # Cleaned rows
    out_clean = cleaned_df.drop(columns=["_highlight_invalid_prefix"], errors="ignore")
    for row in dataframe_to_rows(out_clean, index=False, header=True):
        ws_c.append(row)

    # Force Name col as text (keep '=')
    for r in range(2, ws_c.max_row + 1):
        cell = ws_c.cell(row=r, column=1)
        cell.number_format = "@"
        cell.data_type = "s"

    # Highlight invalid prefixes
    if "_highlight_invalid_prefix" in cleaned_df.columns:
        flags = cleaned_df["_highlight_invalid_prefix"].tolist()
        for excel_row, bad in enumerate(flags, start=2):
            if bool(bad):
                for col in range(1, ws_c.max_column + 1):
                    ws_c.cell(row=excel_row, column=col).fill = YELLOW_FILL

    # Removed rows
    for row in dataframe_to_rows(removed_df, index=False, header=True):
        ws_r.append(row)

    # Force Removed Name as text too
    if ws_r.max_row >= 1:
        headers = [ws_r.cell(row=1, column=c).value for c in range(1, ws_r.max_column + 1)]
        if "Name" in headers:
            name_col = headers.index("Name") + 1
            for r in range(2, ws_r.max_row + 1):
                cell = ws_r.cell(row=r, column=name_col)
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
