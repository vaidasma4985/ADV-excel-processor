REQUIRED_COLUMNS = [
    "Wireno",
    "Line-Function",
    "Name",
    "C.name",
    "Type",
    "Set Value",
    "PINDATA",
    "BILLEDE",
    "Name.1",
    "C.name.1",
    "Type.1",
    "PINDATA.1",
    "BILLEDE.1",
    "Voltage Ue",
]


def validate_required_columns(df) -> tuple[bool, list[str]]:
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    return not missing, missing
