from __future__ import annotations

from typing import Any

from .component_processor import build_component_placeholder_result
from .terminal_processor import (
    derive_output_filename,
    export_placeholder_workbook,
    process_terminal_result,
)
from .wire_processor import build_wire_placeholder_result


_SOURCE_LABELS = {
    "component": ("Component Marking", "component input"),
    "terminal": ("Terminal Marking", "terminal input"),
    "wire": ("Cable Marking", "wire input"),
}


def build_placeholder_results(
    inputs: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], list[str], list[str], list[str], dict[str, bytes | None]]:
    """Coordinate component, terminal, and wire processing without holding business logic."""
    sheets: dict[str, Any] = {}
    warnings: list[str] = []
    user_info_messages: list[str] = []
    developer_debug_messages: list[str] = []
    debug_workbooks: dict[str, bytes | None] = {
        "component": None,
        "terminal": None,
        "wire": None,
    }

    for source_key in ("component", "terminal", "wire"):
        file_info = inputs.get(source_key, {})
        file_bytes = file_info.get("bytes")
        file_name = (file_info.get("name") or "").strip()
        sheet_name, source_label = _SOURCE_LABELS[source_key]

        if not file_bytes:
            warnings.append(f"{source_label.capitalize()} not uploaded. `{sheet_name}` sheet was skipped.")
            user_info_messages.append(f"{source_label} missing -> skipped")
            developer_debug_messages.append(f"{source_key}: missing upload -> sheet skipped")
            continue

        if source_key == "terminal":
            terminal_result = process_terminal_result(file_bytes, file_name)
            sheets["Terminal markings"] = terminal_result["sheet"]
            user_info_messages.extend(terminal_result["user_info_messages"])
            developer_debug_messages.extend(terminal_result["developer_debug_messages"])
            debug_workbooks["terminal"] = terminal_result["debug_workbook"]
        elif source_key == "component":
            component_sheet, component_user_info = build_component_placeholder_result(file_name, source_label)
            sheets[sheet_name] = component_sheet
            user_info_messages.extend(component_user_info)
        else:
            wire_sheet, wire_user_info = build_wire_placeholder_result(file_name, source_label)
            sheets[sheet_name] = wire_sheet
            user_info_messages.extend(wire_user_info)

        developer_debug_messages.append(f"{source_key}: uploaded `{file_name or 'uploaded_file'}` -> sheet `{sheet_name}`")

    return sheets, warnings, user_info_messages, developer_debug_messages, debug_workbooks
