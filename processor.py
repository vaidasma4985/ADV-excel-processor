from __future__ import annotations

import io
import re
from typing import Tuple, List

import pandas as pd
from pandas import DataFrame
from openpyxl.styles import PatternFill


def _check_required_columns(df: DataFrame, required: list[str]) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(", ".join(missing))


def _to_numeric_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _is_valid_name_prefix(name: object) -> bool:
    """
    Tikrinam -F / -K / -X prefiksą (pirmas '-' nuo kairės).
    Veikia su +GS prefiksais, pvz. '+1010-X228'.
    """
    if pd.isna(name):
        return False
    s = str(name).strip()
    if not s:
        return False
    dash_idx = s.find("-")
    if dash_idx == -1 or dash_idx >= len(s) - 1:
        return False
    prefix2 = s[dash_idx:dash_idx + 2]
    return prefix2 in ("-F", "-K", "-X")


def _extract_x_prefix_two_digits(name: object) -> str | None:
    """
    Iš pavadinimo tipo '+1010-X118' arba '+1030-X1113' ištraukia
    pirmus du skaitmenis po '-X'.
    """
    if pd.isna(name):
        return None
    s = str(name)
    m = re.search(r"-X(\d+)", s)
    if not m:
        return None
    digits = m.group(1)
    if len(digits) < 2:
        return None
    return digits[:2]


def _allocate_new_gs(existing: set[int], start: int = 1) -> int:
    """
    Parenka naują Group Sorting reikšmę, kurios dar nėra `existing` rinkinyje.
    """
    new = start
    while new in existing:
        new += 1
    existing.add(new)
    return new


def _merge_relays(df: DataFrame, existing_gs: set[int]) -> tuple[DataFrame, set[int]]:
    """
    Sujungia rėlių eiles pagal Name.

    Tikslas:
    - SE.RGZE1S48M (2 poliai) + bet koks antras komponentas su tuo pačiu Name:
        Type  -> 'SE.RGZE1S48M + SE.RXG22P7'
        Group Sorting -> vienas bendras GS visoms 2-polių rėlėms

    - SE.RXZE2S114M (4 poliai) + bet koks antras komponentas su tuo pačiu Name:
        Type  -> 'SE.RXZE2S114M + SE.RXM4GB2BD'
        Group Sorting -> vienas bendras GS visoms 4-polių rėlėms
    """

    if "Name" not in df.columns or "Type" not in df.columns:
        return df, existing_gs

    to_drop: List[int] = []
    grouped = df.groupby("Name")

    has_rgze = (df["Type"] == "SE.RGZE1S48M").any()
    has_rxze = (df["Type"] == "SE.RXZE2S114M").any()

    gs_rgze: int | None = None
    gs_rxze: int | None = None

    if has_rgze:
        gs_rgze = _allocate_new_gs(existing_gs, start=1)
    if has_rxze:
        gs_rxze = _allocate_new_gs(existing_gs, start=1)

    # 2 polių rėlės – SE.RGZE1S48M
    if gs_rgze is not None:
        for name, idxs in grouped.groups.items():
            sub = df.loc[idxs]
            mask_rgze = sub["Type"] == "SE.RGZE1S48M"
            if mask_rgze.any() and len(sub) >= 2:
                base_idx = sub[mask_rgze].index[0]
                coil_idxs = [i for i in idxs if i != base_idx]
                df.at[base_idx, "Type"] = "SE.RGZE1S48M + SE.RXG22P7"
                df.at[base_idx, "Group Sorting"] = gs_rgze
                to_drop.extend(coil_idxs)

    # 4 polių rėlės – SE.RXZE2S114M
    if gs_rxze is not None:
        for name, idxs in grouped.groups.items():
            sub = df.loc[idxs]
            # jei jau paversta į 2 polių rėlę, praleidžiam
            if (sub["Type"] == "SE.RGZE1S48M + SE.RXG22P7").any():
                continue
            mask_rxze = sub["Type"] == "SE.RXZE2S114M"
            if mask_rxze.any() and len(sub) >= 2:
                base_idx = sub[mask_rxze].index[0]
                coil_idxs = [i for i in idxs if i != base_idx]
                df.at[base_idx, "Type"] = "SE.RXZE2S114M + SE.RXM4GB2BD"
                df.at[base_idx, "Group Sorting"] = gs_rxze
                to_drop.extend(coil_idxs)

    if to_drop:
        df = df.drop(index=to_drop).copy()

    return df, existing_gs


# -------- FUNCTION DESIGNATION MAP --------

FUNCTION_MAP: dict[str, str] = {
    "SE.A9F04604": "POWER",
    "WAGO.2002-1611/1000-541": "FUSES",
    "WAGO.2002-1611/1000-836": "FUSES",
    "SE.RGZE1S48M + SE.RXG22P7": "2POLE",
    "SE.RXZE2S114M + SE.RXM4GB2BD": "4POLE",
    "WAGO.2002-3201": "CONTROL",
    "WAGO.2002-3207": "CONTROL",
}


def process_excel(file_bytes: bytes) -> Tuple[DataFrame, DataFrame, bytes]:
    buffer = io.BytesIO(file_bytes)
    df = pd.read_excel(buffer, sheet_name=0)

    required_columns = ["Name", "Type", "Quantity", "Group Sorting"]
    _check_required_columns(df, required_columns)

    original_columns = list(df.columns)
    removed_chunks: List[DataFrame] = []

    # -------------------------------------------------------------------------
    # STEP 1 – REMOVE ROWS BY NAME PREFIX
    # -------------------------------------------------------------------------
    remove_prefixes = ("-B", "-C", "-R", "-M", "-P", "-Q", "-S", "-W", "-T")
    name_str = df["Name"].astype(str)
    mask_remove_step1 = name_str.str.startswith(remove_prefixes, na=False)
    if mask_remove_step1.any():
        rem1 = df[mask_remove_step1].copy()
        rem1["Removed Reason"] = "Removed by Name prefix (-B/-C/-R/-M/-P/-Q/-S/-W/-T)"
        removed_chunks.append(rem1)
    df = df[~mask_remove_step1].copy()

    # STEP 2 – prefix validation tik formatavimui (darysim gale, EXCEL dalyje)

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
    mask_remove_step3 = ~mask_keep_type
    if mask_remove_step3.any():
        rem3 = df[mask_remove_step3].copy()
        rem3["Removed Reason"] = "Removed by Type filter (not in allowed list)"
        removed_chunks.append(rem3)
    df = df[mask_keep_type].copy()

    # -------------------------------------------------------------------------
    # STEP 4 – MAP WAGO / SCHNEIDER TIPUS
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
    if mask_wago.any():
        df.loc[mask_wago, "Type"] = "WAGO." + df.loc[mask_wago, "Type"].astype(str)

    # RGZE bazė -> SE.RGZE1S48M
    mask_rgze = df["Type"] == "RGZE1S48M"
    if mask_rgze.any():
        df.loc[mask_rgze, "Type"] = "SE.RGZE1S48M"

    # Kiti Schneider
    schneider_map = {
        "A9F04604": "SE.A9F04604",
        "RXG22P7": "SE.RXG22P7",
        "RXG22BD": "SE.RXG22BD",
        "RXM4GB2BD": "SE.RXM4GB2BD",
        "RXZE2S114M": "SE.RXZE2S114M",
    }
    for old, new in schneider_map.items():
        m = df["Type"] == old
        if m.any():
            df.loc[m, "Type"] = new

    # -------------------------------------------------------------------------
    # STEP 5 – FUSE GROUP SORTING
    # -------------------------------------------------------------------------
    gs_all_raw = _to_numeric_series(df["Group Sorting"])
    existing_gs: set[int] = set(
        int(v) for v in gs_all_raw.dropna().astype(int).unique()
    )

    # WAGO.2002-1611/1000-541 – visi į vieną naują GS
    mask_541 = df["Type"] == "WAGO.2002-1611/1000-541"
    if mask_541.any():
        new_gs_541 = _allocate_new_gs(existing_gs, start=1)
        df.loc[mask_541, "Group Sorting"] = new_gs_541

    # WAGO.2002-1611/1000-836 – F9** atskirai, kiti atskirai
    mask_836 = df["Type"] == "WAGO.2002-1611/1000-836"
    if mask_836.any():
        names_836 = df.loc[mask_836, "Name"].astype(str)
        f9_mask_sub = names_836.str.contains(r"-F9\d*", regex=True)
        idx_all = df[mask_836].index
        mask_836_f9 = pd.Series(False, index=df.index)
        mask_836_f9.loc[idx_all] = f9_mask_sub
        mask_836_other = mask_836 & ~mask_836_f9

        if mask_836_f9.any():
            new_gs_f9 = _allocate_new_gs(existing_gs, start=1)
            df.loc[mask_836_f9, "Group Sorting"] = new_gs_f9
        if mask_836_other.any():
            new_gs_other = _allocate_new_gs(existing_gs, start=1)
            df.loc[mask_836_other, "Group Sorting"] = new_gs_other

    # -------------------------------------------------------------------------
    # STEP 5b – RELAY MERGE (RGZE / RXZE POROS)
    # -------------------------------------------------------------------------
    df, existing_gs = _merge_relays(df, existing_gs)

    # -------------------------------------------------------------------------
    # STEP 6 – NAME = +GS-NAME
    # -------------------------------------------------------------------------
    gs_numeric = _to_numeric_series(df["Group Sorting"])
    mask_has_gs = gs_numeric.notna()
    if mask_has_gs.any():
        gs_str = gs_numeric[mask_has_gs].astype(int).astype(str)
        df.loc[mask_has_gs, "Name"] = (
            "+" + gs_str + df.loc[mask_has_gs, "Name"].astype(str)
        )

    # -------------------------------------------------------------------------
    # STEP 7 – PE RENAMING (WAGO.2002-3207)
    # -------------------------------------------------------------------------
    mask_pe_all = df["Type"] == "WAGO.2002-3207"
    if mask_pe_all.any():
        pe_df = df.loc[mask_pe_all].copy()
        pe_df["GroupSortingNum"] = _to_numeric_series(pe_df["Group Sorting"])
        pe_df_valid = pe_df[pe_df["GroupSortingNum"].notna()].copy()
        if not pe_df_valid.empty:
            unique_gs = sorted(pe_df_valid["GroupSortingNum"].unique())
            gs_to_index = {gs: i + 1 for i, gs in enumerate(unique_gs)}
            pe_df_valid["PE_Index"] = pe_df_valid["GroupSortingNum"].map(gs_to_index)
            gs_str_pe = pe_df_valid["GroupSortingNum"].astype(int).astype(str)
            pe_df_valid["Name"] = (
                "+" + gs_str_pe + "-PE" + pe_df_valid["PE_Index"].astype(str)
            )
            df.loc[pe_df_valid.index, "Name"] = pe_df_valid["Name"]

    # -------------------------------------------------------------------------
    # STEP 8 – NAUJI STULPELIAI
    # -------------------------------------------------------------------------
    df["Accessories"] = ""
    df["Quantity of accessories"] = 0
    df["Accessories2"] = ""
    df["Quantity of accessories2"] = 0
    df["Designation"] = ""
    df["Function"] = ""  # čia rašysim =CONTROL+... ir pan.

    # -------------------------------------------------------------------------
    # STEP 9 – TERMINALŲ SPLITINIMAS PAGAL QUANTITY
    # -------------------------------------------------------------------------
    rows: List[dict] = []
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        t = row_dict.get("Type")
        qty_raw = row_dict.get("Quantity", 0)
        qty = pd.to_numeric(qty_raw, errors="coerce")

        if (
            t in ("WAGO.2002-3201", "WAGO.2002-3207")
            and pd.notna(qty)
            and qty > 1
        ):
            n = int(qty)

            base = row_dict.copy()
            base["Quantity"] = 1
            base["Designation"] = ""
            base["Accessories"] = ""
            base["Quantity of accessories"] = 0
            base["Accessories2"] = ""
            base["Quantity of accessories2"] = 0
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
    # STEP 10 – ACCESSORIES (TERMINALAI + FUSE)
    # -------------------------------------------------------------------------
    gs_all = _to_numeric_series(df["Group Sorting"])
    is_terminal = df["Type"].isin(["WAGO.2002-3201", "WAGO.2002-3207"])

    # GS = 1030, grupelės pagal -X** pirmus du skaitmenis
    mask_gs1030 = is_terminal & (gs_all == 1030)
    if mask_gs1030.any():
        names_1030 = df.loc[mask_gs1030, "Name"]
        subgroup_keys_1030 = names_1030.apply(_extract_x_prefix_two_digits)
        valid_keys = sorted(k for k in subgroup_keys_1030.dropna().unique())
        for key in valid_keys:
            idxs = subgroup_keys_1030[subgroup_keys_1030 == key].index
            if len(idxs) > 0:
                last_idx = idxs[-1]
                if df.at[last_idx, "Accessories"] != "WAGO.2002-3292":
                    df.at[last_idx, "Accessories"] = "WAGO.2002-3292"
                    df.at[last_idx, "Quantity of accessories"] = 1

    # GS = 1010, grupelės pagal 2 pirmus skaitmenis po -X
    mask_gs1010 = is_terminal & (gs_all == 1010)
    if mask_gs1010.any():
        names_1010 = df.loc[mask_gs1010, "Name"]
        subgroup_keys_1010 = names_1010.apply(_extract_x_prefix_two_digits)
        valid_keys = sorted(k for k in subgroup_keys_1010.dropna().unique())
        for key in valid_keys:
            idxs = subgroup_keys_1010[subgroup_keys_1010 == key].index
            if len(idxs) > 0:
                last_idx = idxs[-1]
                if df.at[last_idx, "Accessories"] != "WAGO.2002-3292":
                    df.at[last_idx, "Accessories"] = "WAGO.2002-3292"
                    df.at[last_idx, "Quantity of accessories"] = 1

    # GS = 1110 – tokia pati logika kaip 1010
    mask_gs1110 = is_terminal & (gs_all == 1110)
    if mask_gs1110.any():
        names_1110 = df.loc[mask_gs1110, "Name"]
        subgroup_keys_1110 = names_1110.apply(_extract_x_prefix_two_digits)
        valid_keys = sorted(k for k in subgroup_keys_1110.dropna().unique())
        for key in valid_keys:
            idxs = subgroup_keys_1110[subgroup_keys_1110 == key].index
            if len(idxs) > 0:
                last_idx = idxs[-1]
                if df.at[last_idx, "Accessories"] != "WAGO.2002-3292":
                    df.at[last_idx, "Accessories"] = "WAGO.2002-3292"
                    df.at[last_idx, "Quantity of accessories"] = 1

    # Kitos terminalų grupės – dangtelis tik paskutinėje GS eilutėje
    mask_other = (
        is_terminal
        & gs_all.notna()
        & ~(mask_gs1030 | mask_gs1010 | mask_gs1110)
    )
    if mask_other.any():
        grouped_other = df[mask_other].groupby(gs_all[mask_other])
        for _, idxs in grouped_other.groups.items():
            idxs = list(idxs)
            last_idx = idxs[-1]
            if df.at[last_idx, "Accessories"] != "WAGO.2002-3292":
                df.at[last_idx, "Accessories"] = "WAGO.2002-3292"
                df.at[last_idx, "Quantity of accessories"] = 1

    # Fuse accessories
    mask_541 = df["Type"] == "WAGO.2002-1611/1000-541"
    if mask_541.any():
        idxs_541 = df[mask_541].index
        last_541 = idxs_541[-1]
        df.at[last_541, "Accessories"] = "WAGO.2002-991"
        df.at[last_541, "Quantity of accessories"] = 1
        df.at[last_541, "Accessories2"] = "WAGO.249-116"
        df.at[last_541, "Quantity of accessories2"] = 1

    mask_836 = df["Type"] == "WAGO.2002-1611/1000-836"
    if mask_836.any():
        names_836 = df.loc[mask_836, "Name"].astype(str)
        f9_mask_sub = names_836.str.contains(r"-F9\d*", regex=True)
        idxs_all_836 = df[mask_836].index
        idxs_f9 = idxs_all_836[f9_mask_sub.values]
        idxs_other_836 = idxs_all_836[~f9_mask_sub.values]

        if len(idxs_f9) > 0:
            last_f9 = idxs_f9[-1]
            df.at[last_f9, "Accessories"] = "WAGO.2002-991"
            df.at[last_f9, "Quantity of accessories"] = 1

        if len(idxs_other_836) > 0:
            last_other = idxs_other_836[-1]
            df.at[last_other, "Accessories"] = "WAGO.2002-991"
            df.at[last_other, "Quantity of accessories"] = 1
            df.at[last_other, "Accessories2"] = "WAGO.249-116"
            df.at[last_other, "Quantity of accessories2"] = 1

    # -------------------------------------------------------------------------
    # STEP 11 – PE DESIGNATION SEKA (pirmas tuščias, kiti 1..n-1)
    # -------------------------------------------------------------------------
    mask_pe_type = df["Type"] == "WAGO.2002-3207"
    if mask_pe_type.any():
        grouped_pe = df[mask_pe_type].groupby(df.loc[mask_pe_type, "Name"])
        for _, idxs in grouped_pe.groups.items():
            idxs = list(idxs)
            for j, idx in enumerate(idxs):
                if j == 0:
                    df.at[idx, "Designation"] = ""
                else:
                    df.at[idx, "Designation"] = str(j)

    # -------------------------------------------------------------------------
    # STEP 12 – FUNCTION DESIGNATION (NAUJAS STULPELIS Function)
    # -------------------------------------------------------------------------
    func_codes = df["Type"].map(FUNCTION_MAP)
    mask_fd = func_codes.notna()
    if mask_fd.any():
        # kaip tekstą: ' =CONTROL+1010-X118' (apostrofas paslepiamas, Excel rodo =...)
        df.loc[mask_fd, "Function"] = (
            "'" + "=" + func_codes[mask_fd] + df.loc[mask_fd, "Name"].astype(str)
        )

    # -------------------------------------------------------------------------
    # BUILD REMOVED DF
    # -------------------------------------------------------------------------
    if removed_chunks:
        removed_df = pd.concat(removed_chunks, ignore_index=True)
    else:
        removed_df = pd.DataFrame(columns=original_columns + ["Removed Reason"])

    cleaned_df = df.reset_index(drop=True)
    removed_df = removed_df.reset_index(drop=True)

    # -------------------------------------------------------------------------
    # STULPELIŲ TVARKA
    # -------------------------------------------------------------------------
    cols = list(cleaned_df.columns)
    # Norim, kad pirmi būtų Name ir Function (jei yra)
    ordered = []
    for key in ("Name", "Function"):
        if key in cols:
            ordered.append(key)
            cols.remove(key)

    if "Designation" in cols:
        cols.remove("Designation")
        cols.append("Designation")

    accessory_cols = [
        "Accessories",
        "Quantity of accessories",
        "Accessories2",
        "Quantity of accessories2",
    ]
    if all(c in cols for c in accessory_cols):
        base_cols = [c for c in cols if c not in accessory_cols]
        if "Group Sorting" in base_cols:
            pos = base_cols.index("Group Sorting") + 1
        else:
            pos = len(base_cols)
        mid = base_cols[:pos] + accessory_cols + base_cols[pos:]
    else:
        mid = cols

    final_cols = ordered + [c for c in mid if c not in ordered]
    cleaned_df = cleaned_df[final_cols]

    # -------------------------------------------------------------------------
    # EXCEL Į BYTES (OPENPYXL + GELTONAS HIGHLIGHT)
    # -------------------------------------------------------------------------
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        cleaned_df.to_excel(writer, sheet_name="Cleaned", index=False)
        removed_df.to_excel(writer, sheet_name="Removed", index=False)

        workbook = writer.book
        ws_cleaned = workbook["Cleaned"]

        yellow_fill = PatternFill(
            start_color="FFFF00", end_color="FFFF00", fill_type="solid"
        )
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
