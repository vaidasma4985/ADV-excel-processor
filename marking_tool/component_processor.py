from __future__ import annotations

from typing import Any

import pandas as pd


def build_component_placeholder_result(file_name: str, source_label: str) -> tuple[pd.DataFrame, list[str]]:
    """Return the current placeholder output for component uploads."""
    return (
        pd.DataFrame(
            [
                {
                    "source_file": file_name or "uploaded_file",
                    "source_type": source_label,
                    "status": "placeholder_generated",
                    "note": "Placeholder output only. Real marking rules are not implemented yet.",
                    "parsed_rows": "",
                }
            ]
        ),
        [f"{source_label} uploaded -> placeholder sheet created"],
    )
