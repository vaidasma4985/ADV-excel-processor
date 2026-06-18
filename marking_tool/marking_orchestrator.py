from __future__ import annotations

from io import BytesIO
import re
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from .component_marking import process_component_result
from .render import export_placeholder_workbook
from .terminal_marking import process_terminal_result
from .wago_exports import (
    build_fuses_2009_wssl_bytes,
    build_fuses_2009_wssl_debug_messages,
    build_fuses_2009_wssl_filename,
    build_fuse_strip_wssl_bytes,
    build_fuse_strip_wssl_debug_messages,
    build_fuse_strip_wssl_filename,
    build_relay_strip_wssl_bytes,
    build_relay_strip_wssl_debug_messages,
    build_relay_strip_wssl_filename,
    build_terminal_tmb_wssl_bytes,
    build_terminal_strip_wssl_bytes,
    build_terminal_strip_wssl_debug_messages,
    build_terminal_strip_wssl_filename,
    build_wago_tmb_wssl_filename,
)
from .wire_cable_marking import build_wire_placeholder_result


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


def build_component_relay_xmlil_filename(project_number: str | None) -> str:
    """Build the component relay XMLIL filename from the resolved project number."""
    if not project_number:
        return "1.xmlil"
    return f"{project_number}.xmlil"


def build_wago_markings_zip_filename(project_number: str | None) -> str:
    """Build the combined WAGO markings ZIP filename."""
    project_prefix = project_number or "1"
    return f"{project_prefix}_WAGO_markings.zip"


def _build_wago_markings_zip(wago_files: list[dict[str, bytes | str]]) -> bytes:
    """Package generated WAGO files into one download payload."""
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for wago_file in wago_files:
            archive.writestr(str(wago_file["filename"]), bytes(wago_file["bytes"]))
    return output.getvalue()


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
    dict[str, dict[str, bytes | str] | None],
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
    xmlil_outputs: dict[str, dict[str, bytes | str] | None] = {
        "component_relays": None,
    }
    wago_outputs: dict[str, dict[str, bytes | str] | None] = {
        "terminal_strip_wssl": None,
        "terminal_tmb": None,
        "fuse_strip_wssl": None,
        "fuses_2009_wssl": None,
        "relay_strip_wssl": None,
        "markings_zip": None,
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
            wago_strip_rows = terminal_result.get("wago_strip_rows") or []
            wago_outputs["terminal_strip_wssl"] = {
                "bytes": build_terminal_strip_wssl_bytes(wago_strip_rows),
                "filename": build_terminal_strip_wssl_filename(resolved_project_number),
            }
            developer_debug_messages.append("Terminal Strip WSSL experimental output enabled")
            developer_debug_messages.extend(build_terminal_strip_wssl_debug_messages(wago_strip_rows))
            wago_tmb_rows = terminal_result.get("wago_tmb_rows") or []
            wago_outputs["terminal_tmb"] = {
                "bytes": build_terminal_tmb_wssl_bytes(wago_tmb_rows),
                "filename": build_wago_tmb_wssl_filename(resolved_project_number),
            }
            developer_debug_messages.append("Terminal TMB WSSL profile used")
            developer_debug_messages.append(
                "WAGO Terminal TMB WSSL generated -> "
                + f"terminal TMB rows count = {len(wago_tmb_rows)}"
            )
        elif source_key == "component":
            component_result = process_component_result(
                file_bytes,
                file_name,
                project_number=resolved_project_number,
            )
            sheets.update(component_result["sheets"])
            user_info_messages.extend(component_result["user_info_messages"])
            developer_debug_messages.extend(component_result["developer_debug_messages"])
            debug_workbooks["component"] = component_result["debug_workbook"]
            if component_result.get("production_workbook"):
                production_workbooks["component"] = {
                    "bytes": component_result["production_workbook"],
                    "filename": build_component_production_filename(resolved_project_number),
                }
            if component_result.get("relay_xmlil_bytes"):
                xmlil_outputs["component_relays"] = {
                    "bytes": component_result["relay_xmlil_bytes"],
                    "filename": build_component_relay_xmlil_filename(resolved_project_number),
            }
            wago_fuse_strip_rows = component_result.get("wago_fuse_strip_rows") or []
            if wago_fuse_strip_rows:
                wago_outputs["fuse_strip_wssl"] = {
                    "bytes": build_fuse_strip_wssl_bytes(wago_fuse_strip_rows),
                    "filename": build_fuse_strip_wssl_filename(resolved_project_number),
                }
                developer_debug_messages.extend(build_fuse_strip_wssl_debug_messages(wago_fuse_strip_rows))
            wago_relay_strip_rows = component_result.get("wago_relay_strip_rows") or []
            if wago_relay_strip_rows:
                wago_outputs["relay_strip_wssl"] = {
                    "bytes": build_relay_strip_wssl_bytes(wago_relay_strip_rows),
                    "filename": build_relay_strip_wssl_filename(resolved_project_number),
                }
                developer_debug_messages.extend(build_relay_strip_wssl_debug_messages(wago_relay_strip_rows))
            wago_fuses_2009_rows = component_result.get("wago_fuses_2009_rows") or []
            if wago_fuses_2009_rows:
                wago_outputs["fuses_2009_wssl"] = {
                    "bytes": build_fuses_2009_wssl_bytes(wago_fuses_2009_rows),
                    "filename": build_fuses_2009_wssl_filename(resolved_project_number),
                }
                developer_debug_messages.extend(build_fuses_2009_wssl_debug_messages(wago_fuses_2009_rows))
        else:
            wire_sheet, wire_user_info = build_wire_placeholder_result(file_name, source_label, file_bytes)
            sheets[sheet_name] = wire_sheet
            user_info_messages.extend(wire_user_info)
            developer_debug_messages.extend(wire_sheet.get("developer_debug_messages", []))

        developer_debug_messages.append(f"{source_key}: uploaded `{file_name or 'uploaded_file'}` -> sheet `{sheet_name}`")

    wago_files = [
        wago_file
        for output_key in (
            "terminal_strip_wssl",
            "fuse_strip_wssl",
            "relay_strip_wssl",
            "terminal_tmb",
            "fuses_2009_wssl",
        )
        for wago_file in [wago_outputs.get(output_key)]
        if wago_file
    ]
    if len(wago_files) > 1:
        wago_outputs["markings_zip"] = {
            "bytes": _build_wago_markings_zip(wago_files),
            "filename": build_wago_markings_zip_filename(resolved_project_number),
        }
        developer_debug_messages.append(
            "WAGO markings ZIP generated -> "
            + ", ".join(str(wago_file["filename"]) for wago_file in wago_files)
        )

    return (
        sheets,
        warnings,
        user_info_messages,
        developer_debug_messages,
        debug_workbooks,
        production_workbooks,
        xmlil_outputs,
        wago_outputs,
    )
