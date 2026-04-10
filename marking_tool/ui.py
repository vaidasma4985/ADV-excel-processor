from __future__ import annotations

import uuid
from typing import Any

import streamlit as st

from marking_tool.processor import PLACEHOLDER_FILENAME, build_placeholder_results, export_placeholder_workbook


MARKING_STATE_KEYS = [
    "marking_component_bytes",
    "marking_component_name",
    "marking_terminal_bytes",
    "marking_terminal_name",
    "marking_wire_bytes",
    "marking_wire_name",
    "marking_results",
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


def _process_marking_inputs() -> None:
    inputs = _current_inputs()
    has_any_upload = any(file_info.get("bytes") for file_info in inputs.values())

    if not has_any_upload:
        st.session_state["marking_results"] = None
        st.session_state["marking_warnings"] = ["No files uploaded. Upload at least one input file before processing."]
        st.session_state["marking_debug_info"] = ["process skipped: no uploads available"]
        st.session_state["marking_run_id"] = None
        return

    sheets, warnings, debug_info = build_placeholder_results(inputs)
    workbook_bytes = export_placeholder_workbook(sheets)

    st.session_state["marking_results"] = {
        "workbook_bytes": workbook_bytes,
        "filename": PLACEHOLDER_FILENAME,
        "sheet_names": list(sheets.keys()),
    }
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
        st.download_button(
            "Download placeholder workbook",
            data=results["workbook_bytes"],
            file_name=results["filename"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        st.caption("Generated sheets: " + ", ".join(results["sheet_names"]))

        with st.expander("Debug / info", expanded=False):
            run_id = st.session_state.get("marking_run_id")
            st.write({"run_id": run_id, "results_ready": results is not None})
            debug_info = st.session_state.get("marking_debug_info") or ["No debug info yet."]
            for item in debug_info:
                st.text(item)
