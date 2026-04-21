from __future__ import annotations

import uuid
from typing import Any

import streamlit as st

from marking_tool.processor import (
    build_marking_output_filename,
    build_placeholder_results,
    export_placeholder_workbook,
    resolve_project_number,
)


MARKING_STATE_KEYS = [
    "marking_component_bytes",
    "marking_component_name",
    "marking_terminal_bytes",
    "marking_terminal_name",
    "marking_wire_bytes",
    "marking_wire_name",
    "marking_results",
    "marking_user_info",
    "marking_warnings",
    "marking_debug_info",
    "marking_run_id",
    "marking_uploader_token",
]


def clear_marking_tool_state() -> None:
    for key in MARKING_STATE_KEYS:
        st.session_state.pop(key, None)
    st.session_state["marking_uploader_token"] = uuid.uuid4().hex[:8]


def _ensure_marking_defaults() -> None:
    defaults: dict[str, Any] = {
        "marking_component_bytes": None,
        "marking_component_name": "",
        "marking_terminal_bytes": None,
        "marking_terminal_name": "",
        "marking_wire_bytes": None,
        "marking_wire_name": "",
        "marking_results": None,
        "marking_user_info": [],
        "marking_warnings": [],
        "marking_debug_info": [],
        "marking_run_id": None,
        "marking_uploader_token": uuid.uuid4().hex[:8],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _store_uploaded_file(upload_key: str, bytes_key: str, name_key: str) -> None:
    uploaded_file = st.session_state.get(upload_key)
    if uploaded_file is None:
        st.session_state[bytes_key] = None
        st.session_state[name_key] = ""
        return

    st.session_state[bytes_key] = uploaded_file.getvalue()
    st.session_state[name_key] = uploaded_file.name


def _uploader_key(field_name: str) -> str:
    return f"{field_name}_{st.session_state['marking_uploader_token']}"


def _current_inputs() -> dict[str, dict[str, Any]]:
    return {
        "component": {
            "bytes": st.session_state.get("marking_component_bytes"),
            "name": st.session_state.get("marking_component_name"),
        },
        "terminal": {
            "bytes": st.session_state.get("marking_terminal_bytes"),
            "name": st.session_state.get("marking_terminal_name"),
        },
        "wire": {
            "bytes": st.session_state.get("marking_wire_bytes"),
            "name": st.session_state.get("marking_wire_name"),
        },
    }


def _build_debug_filename(base_filename: str, suffix: str) -> str:
    if base_filename.lower().endswith(".xlsx"):
        return f"{base_filename[:-5]}_{suffix}.xlsx"
    return f"{base_filename}_{suffix}.xlsx"


def _process_marking_inputs() -> None:
    inputs = _current_inputs()
    has_any_upload = any(file_info.get("bytes") for file_info in inputs.values())

    if not has_any_upload:
        st.session_state["marking_results"] = None
        st.session_state["marking_user_info"] = []
        st.session_state["marking_warnings"] = ["No files uploaded. Upload at least one input file before processing."]
        st.session_state["marking_debug_info"] = ["process skipped: no uploads available"]
        st.session_state["marking_run_id"] = None
        return

    resolved_project_number = resolve_project_number(inputs)
    sheets, warnings, user_info_messages, debug_info, debug_workbooks, production_workbooks = build_placeholder_results(
        inputs,
        resolved_project_number=resolved_project_number,
    )
    workbook_bytes = export_placeholder_workbook(sheets)
    output_filename = build_marking_output_filename(resolved_project_number)

    st.session_state["marking_results"] = {
        "workbook_bytes": workbook_bytes,
        "filename": output_filename,
        "project_number": resolved_project_number or "",
        "sheet_names": list(sheets.keys()),
        "developer_debug_messages": debug_info,
        "debug_workbooks": debug_workbooks,
        "production_workbooks": production_workbooks,
        "debug_status": {
            tool_name: {
                "uploaded": bool(inputs.get(tool_name, {}).get("bytes")),
                "has_debug_workbook": bool(debug_workbooks.get(tool_name)),
            }
            for tool_name in ("component", "terminal", "wire")
        },
    }
    st.session_state["marking_user_info"] = user_info_messages
    st.session_state["marking_warnings"] = warnings
    st.session_state["marking_debug_info"] = debug_info
    st.session_state["marking_run_id"] = uuid.uuid4().hex[:8]


def render_marking_tool() -> None:
    _ensure_marking_defaults()

    st.subheader("Marking tool")
    st.caption("Placeholder skeleton for future marking workflows.")

    warnings = st.session_state.get("marking_warnings") or []
    if warnings:
        for warning in warnings:
            st.warning(warning)

    results = st.session_state.get("marking_results")
    if results is None:
        c1, c2, c3 = st.columns(3)
        component_upload_key = _uploader_key("marking_component_upload")
        terminal_upload_key = _uploader_key("marking_terminal_upload")
        wire_upload_key = _uploader_key("marking_wire_upload")

        with c1:
            st.file_uploader(
                "Component input",
                type=["xlsx", "xlsm", "xls"],
                key=component_upload_key,
                on_change=_store_uploaded_file,
                args=(component_upload_key, "marking_component_bytes", "marking_component_name"),
            )
        with c2:
            st.file_uploader(
                "Terminal input",
                type=["xlsx", "xlsm", "xls"],
                key=terminal_upload_key,
                on_change=_store_uploaded_file,
                args=(terminal_upload_key, "marking_terminal_bytes", "marking_terminal_name"),
            )
        with c3:
            st.file_uploader(
                "Wire input",
                type=["xlsx", "xlsm", "xls"],
                key=wire_upload_key,
                on_change=_store_uploaded_file,
                args=(wire_upload_key, "marking_wire_bytes", "marking_wire_name"),
            )

        if st.button("Process", key="marking_process_button", use_container_width=True):
            _process_marking_inputs()
            st.rerun()
    else:
        st.success("Placeholder workbook created.")
        resolved_project_number = (results.get("project_number") or "").strip()
        if resolved_project_number:
            st.caption(f"Project number: {resolved_project_number}")
        user_info_messages = st.session_state.get("marking_user_info") or []
        developer_debug_messages = results.get("developer_debug_messages", [])
        st.download_button(
            f"Download {results['filename']}",
            data=results["workbook_bytes"],
            file_name=results["filename"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        component_production_workbook = (results.get("production_workbooks") or {}).get("component")
        if component_production_workbook:
            component_production_filename = str(component_production_workbook["filename"])
            st.download_button(
                f"Download {component_production_filename}",
                data=component_production_workbook["bytes"],
                file_name=component_production_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="marking_component_production_download",
            )
        st.caption("Generated sheets: " + ", ".join(results["sheet_names"]))

        with st.expander("Info", expanded=False):
            for message in user_info_messages or ["No additional info."]:
                st.text(message)

        with st.expander("Developer debug", expanded=False):
            debug_workbooks = results.get("debug_workbooks", {}) if results else {}
            debug_status = results.get("debug_status", {}) if results else {}
            debug_filename_base = results.get("filename", "Markings.xlsx") if results else "Markings.xlsx"
            tool_labels = {
                "component": "Component",
                "terminal": "Terminal",
                "wire": "Wire",
            }
            tool_suffixes = {
                "component": "component_debug",
                "terminal": "terminal_debug",
                "wire": "wire_debug",
            }
            component_col, terminal_col, wire_col = st.columns(3)

            for tool_name, column in zip(("component", "terminal", "wire"), (component_col, terminal_col, wire_col)):
                with column:
                    st.markdown(f"**{tool_labels[tool_name]}**")
                    tool_uploaded = bool(debug_status.get(tool_name, {}).get("uploaded"))
                    tool_has_debug_workbook = bool(debug_status.get(tool_name, {}).get("has_debug_workbook"))
                    st.caption(
                        f"Input uploaded: {'Yes' if tool_uploaded else 'No'} | "
                        f"Debug workbook: {'Available' if tool_has_debug_workbook else 'Unavailable'}"
                    )
                    tool_debug_workbook = debug_workbooks.get(tool_name)
                    if tool_debug_workbook:
                        tool_debug_filename = _build_debug_filename(debug_filename_base, tool_suffixes[tool_name])
                        st.download_button(
                            f"Download {tool_debug_filename}",
                            data=tool_debug_workbook,
                            file_name=tool_debug_filename,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"marking_{tool_name}_debug_download",
                            use_container_width=True,
                        )
                    else:
                        st.text("No debug workbook available")

            if developer_debug_messages:
                st.markdown("**Developer debug**")
                for message in developer_debug_messages:
                    st.text(message)
