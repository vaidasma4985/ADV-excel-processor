from __future__ import annotations

from typing import Any

import pandas as pd


def build_wire_placeholder_result(file_name: str, source_label: str) -> tuple[dict[str, Any], list[str]]:
    """Return the current placeholder output for wire uploads."""
    placeholder_df = pd.DataFrame(
        [
            {
                "source_file": file_name or "uploaded_file",
                "source_type": source_label,
                "status": "placeholder_generated",
                "note": "Placeholder output only. Real marking rules are not implemented yet.",
                "parsed_rows": "",
            }
        ]
    )
    return (
        {
            "layout": "wire_markings",
            "cables_df": placeholder_df,
            "power_wires_df": pd.DataFrame(columns=placeholder_df.columns),
        },
        [f"{source_label} uploaded -> placeholder sheet created"],
    )
