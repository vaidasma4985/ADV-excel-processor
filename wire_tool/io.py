import pandas as pd


def load_connection_list(uploaded_file) -> pd.DataFrame:
    df = pd.read_excel(uploaded_file)
    df.columns = df.columns.str.strip()
    df = df.apply(lambda col: col.map(lambda value: value.strip() if isinstance(value, str) else value))
    return df
