import re
import pandas as pd
from typing import Any


def _next_free_gs(existing: set[int], preferred: int) -> int:
    """Return preferred if free, else next free integer above preferred."""
    g = preferred
    while g in existing:
        g += 1
    existing.add(g)
    return g


def _terminal_sort_key(name: str) -> int:
    """
    Terminalų rikiavimo raktas, kad X192A* įsiterptų tarp X1922 ir X1953.

    Pavyzdžiai:
      -X1912  -> 1912
      -X1922  -> 1922
      -X192A3 -> 1923  (192 + A3 => 1923)
      -X192A7 -> 1927
      -X1953  -> 1953

    Pastaba: jei X192A turi dvigubus skaitmenis (pvz. X192A12), šitą taisyklę reikės patikslinti.
    """
    s = str(name)

    m = re.search(r"-X(\d{4})\b", s)  # normalus 4 skaitmenų X****
    if m:
        return int(m.group(1))

    m = re.search(r"-X(\d{3})A(\d)\b", s)  # X192A3 (3 skaitmenys + A + 1 skaitmuo)
    if m:
        return int(m.group(1) + m.group(2))  # "192"+"3" => 1923

    # fallback: bandome ištraukti bet kokį X skaičių
    m = re.search(r"-X(\d+)", s)
    if m:
        return int(m.group(1))

    return 10**9  # jei nesuprantamas – keliauja į galą


def apply_x192a_terminal_gs_rules(df: pd.DataFrame) -> pd.DataFrame:
    """
    Terminalų X192A* GS įterpimo taisyklė (pagal tavo paskutinį patikslinimą):

    Jei terminalų GS grupėje (pvz. 2010) yra X192A*:
      - visi X192A* -> naujas GS = next_free(2010+1) (pvz. 2011)
      - visi terminalai "po X192A" (pagal X numerį), kurie buvo tame pačiame 2010,
        -> naujas GS = next_free(2011+1) (pvz. 2012)
      - terminalai iki X192A (pvz. X1912, X1922) lieka 2010
      - kitų GS grupių nekeičiam
    """

    if df.empty:
        return df

    # Veikia tik terminalams
    terminal_types = {"WAGO.2002-3201_ADV", "WAGO.2002-3207_ADV"}
    is_terminal = df["Type"].astype(str).isin(terminal_types)

    # Tik su skaitiniu GS
    gs_num = pd.to_numeric(df["Group Sorting"], errors="coerce")
    has_gs = gs_num.notna()

    # Surenkam jau egzistuojančius GS (visame df)
    existing_gs: set[int] = set(gs_num.dropna().astype(int).tolist())

    # Dirbam per kiekvieną terminalų GS grupę atskirai
    work = df[is_terminal & has_gs].copy()
    work["_base_gs"] = gs_num[is_terminal & has_gs].astype(int)

    # Rikiavimo raktas pagal terminalo numerį (kad nustatyti "po X192A")
    work["_xkey"] = work["Name"].astype(str).apply(_terminal_sort_key)

    # X192A maskė (tik terminalų Name)
    work["_is_x192a"] = work["Name"].astype(str).str.contains(r"-X192A\d+\b", regex=True, na=False)

    # Eisim per kiekvieną bazinį GS
    for base_gs, grp in work.groupby("_base_gs", sort=True):
        if not grp["_is_x192a"].any():
            continue  # šitoj grupėj X192A nėra – nieko nekeičiam

        # Naujas GS X192A* terminalams: base+1 (arba sekantis laisvas)
        gs_for_x192a = _next_free_gs(existing_gs, int(base_gs) + 1)

        # Koks yra didžiausias X192A terminalo rikiavimo raktas toje grupėje?
        max_x192a_key = int(grp.loc[grp["_is_x192a"], "_xkey"].max())

        # Terminalai po X192A (pvz. X1953) – tai tie, kurių xkey > max_x192a_key ir kurie NĖRA X192A
        after_mask = (grp["_xkey"] > max_x192a_key) & (~grp["_is_x192a"])

        if after_mask.any():
            gs_for_after = _next_free_gs(existing_gs, gs_for_x192a + 1)
        else:
            gs_for_after = None

        # Pritaikom į originalų df pagal indeksus
        x192a_idxs = grp.loc[grp["_is_x192a"]].index
        df.loc[x192a_idxs, "Group Sorting"] = gs_for_x192a

        if gs_for_after is not None:
            after_idxs = grp.loc[after_mask].index
            df.loc[after_idxs, "Group Sorting"] = gs_for_after

    # cleanup helper cols if they got in (df original not touched by helper cols)
    return df
