import pandas as pd


_NODE_COLUMNS = ("Name", "C.name", "Name.1", "C.name.1")


def _normalize_node_value(value):
    if value is None or pd.isna(value):
        return None
    normalized = str(value).replace("\u00a0", " ").strip()
    if not normalized:
        return None
    return normalized


def load_connection_list(uploaded_file) -> pd.DataFrame:
    df = pd.read_excel(uploaded_file)
    df.columns = df.columns.str.strip()

    for column in _NODE_COLUMNS:
        if column in df.columns:
            df[column] = df[column].map(_normalize_node_value)

    return df
