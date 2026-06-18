from __future__ import annotations

from typing import Any

import pandas as pd

from .cable_marking_builder import (
    CABLE_MARKING_COLUMNS,
    POWER_WIRE_COLUMNS,
    build_cable_marking_result,
)


def build_wire_placeholder_result(
    file_name: str,
    source_label: str,
    file_bytes: bytes | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Return Wire/Cable package output for wire uploads."""
    (
        cables_df,
        power_wires_df,
        cable_blocks,
        power_wire_blocks,
        developer_debug_messages,
    ) = build_cable_marking_result(file_bytes)
    if cables_df.empty:
        cables_df = pd.DataFrame(columns=CABLE_MARKING_COLUMNS)
    if power_wires_df.empty:
        power_wires_df = pd.DataFrame(columns=POWER_WIRE_COLUMNS)

    sheet = {
        "layout": "wire_markings",
        "cables_df": cables_df,
        "power_wires_df": power_wires_df,
        "developer_debug_messages": developer_debug_messages,
    }
    if cable_blocks:
        sheet["cable_blocks"] = cable_blocks
        sheet["power_wire_blocks"] = power_wire_blocks

    return (sheet, [f"{source_label} uploaded -> Cable Marking sheet created"])
