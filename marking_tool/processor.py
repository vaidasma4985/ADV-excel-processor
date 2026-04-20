from __future__ import annotations

import re
from typing import Any

from .component_processor import process_component_result
from .terminal_processor import (
    export_placeholder_workbook,
    process_terminal_result,
)
from .wire_processor import build_wire_placeholder_result


_SOURCE_LABELS = {
    "component": ("Component Marking", "component input"),
    "terminal": ("Terminal Marking", "terminal input"),
    "wire": ("Cable Marking", "wire input"),
}

_PROJECT_CODE_PATTERN = re.compile(r"^\s*(\d{4}-\d{3})\b")


def extract_project_number(file_name: str) -> str | None:
    """Extract the leading project number used by the marking tool when present."""
    match = _PROJECT_CODE_PATTERN.match((file_name or "").strip())
    if not match:
        return None
    return match.group(1)


def resolve_project_number(inputs: dict[str, dict[str, Any]]) -> str | None:
    """Resolve one shared project number from uploaded component/terminal/wire filenames."""
    detected_project_numbers = {
        project_number
        for source_key in ("component", "terminal", "wire")
        if inputs.get(source_key, {}).get("bytes")
        for project_number in [extract_project_number(inputs.get(source_key, {}).get("name", ""))]
        if project_number
    }
    if len(detected_project_numbers) == 1:
        return next(iter(detected_project_numbers))
    return None


def build_marking_output_filename(project_number: str | None) -> str:
    """Build the main Markings workbook filename from the resolved project number."""
    if not project_number:
        return "Markings.xlsx"
    return f"{project_number}_Markings.xlsx"


def build_component_production_filename(project_number: str | None) -> str:
    """Build the component production workbook filename from the resolved project number."""
    if not project_number:
        return "component_production_check.xlsx"
    return f"{project_number}_component_production_check.xlsx"


def derive_output_filename(terminal_file_name: str) -> str:
    """Backward-compatible single-file filename helper using the shared project pattern."""
    return build_marking_output_filename(extract_project_number(terminal_file_name))


def build_placeholder_results(
    inputs: dict[str, dict[str, Any]],
    resolved_project_number: str | None = None,
) -> tuple[
    dict[str, Any],
    list[str],
    list[str],
    list[str],
    dict[str, bytes | None],
    dict[str, dict[str, bytes | str] | None],
]:
    """Coordinate component, terminal, and wire processing without holding business logic."""
    sheets: dict[str, Any] = {}
    warnings: list[str] = []
    user_info_messages: list[str] = []
    developer_debug_messages: list[str] = []
    detected_project_numbers = sorted(
        {
            project_number
            for source_key in ("component", "terminal", "wire")
            if inputs.get(source_key, {}).get("bytes")
            for project_number in [extract_project_number(inputs.get(source_key, {}).get("name", ""))]
            if project_number
        }
    )
    if resolved_project_number is None:
        resolved_project_number = resolve_project_number(inputs)

    if not detected_project_numbers:
        developer_debug_messages.append("marking project number: none detected across uploaded filenames")
    elif resolved_project_number:
        developer_debug_messages.append(f"marking project number resolved -> {resolved_project_number}")
    else:
        developer_debug_messages.append(
            "marking project number conflict -> "
            + ", ".join(detected_project_numbers)
            + " | using no project number"
        )

    debug_workbooks: dict[str, bytes | None] = {
        "component": None,
        "terminal": None,
        "wire": None,
    }
    production_workbooks: dict[str, dict[str, bytes | str] | None] = {
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
            component_result = process_component_result(file_bytes, file_name)
            sheets.update(component_result["sheets"])
            user_info_messages.extend(component_result["user_info_messages"])
            developer_debug_messages.extend(component_result["developer_debug_messages"])
            debug_workbooks["component"] = component_result["debug_workbook"]
            if component_result.get("production_workbook"):
                production_workbooks["component"] = {
                    "bytes": component_result["production_workbook"],
                    "filename": build_component_production_filename(resolved_project_number),
                }
        else:
            wire_sheet, wire_user_info = build_wire_placeholder_result(file_name, source_label)
            sheets[sheet_name] = wire_sheet
            user_info_messages.extend(wire_user_info)

        developer_debug_messages.append(f"{source_key}: uploaded `{file_name or 'uploaded_file'}` -> sheet `{sheet_name}`")

    return sheets, warnings, user_info_messages, developer_debug_messages, debug_workbooks, production_workbooks
