from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd


PLACEHOLDER_FILENAME = "Markings_placeholder.xlsx"

_SOURCE_LABELS = {
    "component": ("Component Marking", "component input"),
    "terminal": ("Terminal Marking", "terminal input"),
    "wire": ("Cable Marking", "wire input"),
}


def build_placeholder_results(inputs: dict[str, dict[str, Any]]) -> tuple[dict[str, pd.DataFrame], list[str], list[str]]:
    """Build placeholder output sheets only for uploaded file types."""
    sheets: dict[str, pd.DataFrame] = {}
    warnings: list[str] = []
    debug_info: list[str] = []

    for source_key in ("component", "terminal", "wire"):
        file_info = inputs.get(source_key, {})
        file_bytes = file_info.get("bytes")
        file_name = (file_info.get("name") or "").strip()
        sheet_name, source_label = _SOURCE_LABELS[source_key]

        if file_bytes:
            sheets[sheet_name] = pd.DataFrame(
                [
                    {
                        "source_file": file_name or "uploaded_file",
                        "source_type": source_label,
                        "status": "placeholder_generated",
                        "note": "Placeholder output only. Real marking rules are not implemented yet.",
                    }
                ]
            )
            debug_info.append(f"{source_key}: uploaded `{file_name or 'uploaded_file'}` -> sheet `{sheet_name}`")
        else:
            warnings.append(f"{source_label.capitalize()} not uploaded. `{sheet_name}` sheet was skipped.")
            debug_info.append(f"{source_key}: missing upload -> sheet skipped")

    return sheets, warnings, debug_info


def export_placeholder_workbook(sheets: dict[str, pd.DataFrame]) -> bytes:
    """Write available placeholder sheets to one Excel workbook in memory."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    output.seek(0)
    return output.getvalue()
