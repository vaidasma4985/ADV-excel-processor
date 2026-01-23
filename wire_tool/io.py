import pandas as pd


_NODE_COLUMNS = ("Name", "C.name", "Name.1", "C.name.1")


def _normalize_node_value(value):
    if value is None or pd.isna(value):
        return None
    normalized = str(value).replace("\u00a0", " ").strip()
    if not normalized:
        return None
    return normalized


def _is_missing(value) -> bool:
    if value is None or pd.isna(value):
        return True
    return isinstance(value, str) and not value.strip()


def _base_device_name(value) -> str | None:
    name_str = _normalize_node_value(value)
    if not name_str:
        return None
    return name_str.split(":", 1)[0]


def _is_q81_self_row(row: pd.Series) -> bool:
    """Drop Q81 self rows without wireno; they are UI markers, not routing edges."""
    left = _base_device_name(row.get("Name"))
    right = _base_device_name(row.get("Name.1"))
    if left != "-Q81" or right != "-Q81":
        return False
    return _is_missing(row.get("Wireno"))


def load_connection_list(uploaded_file) -> tuple[pd.DataFrame, dict]:
    df = pd.read_excel(uploaded_file)
    df.columns = df.columns.str.strip()

    for column in _NODE_COLUMNS:
        if column in df.columns:
            df[column] = df[column].map(_normalize_node_value)

    n_dropped_q81_self = 0
    if {"Name", "Name.1", "Wireno"}.issubset(df.columns):
        q81_mask = df.apply(_is_q81_self_row, axis=1)
        n_dropped_q81_self = int(q81_mask.sum())
        if n_dropped_q81_self:
            df = df.loc[~q81_mask].copy()

    meta = {"n_dropped_q81_self": n_dropped_q81_self}
    return df, meta
