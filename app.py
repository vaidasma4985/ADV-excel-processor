from __future__ import annotations

import streamlit as st

from component_correction.ui import render_component_correction
from wire_tool.ui import render_wire_tool


def _reset_component_correction_state() -> None:
    for key in [
        "component_bytes",
        "component_name",
        "terminal_bytes",
        "terminal_name",
        "results",
        "run_id",
        "gs_fix_df",
        "gs_fix_draft",
        "type_fix_df",
        "type_fix_draft",
        "gs_fix_editor",
        "type_fix_editor",
        "fix_applied_flash",
        "workflow_state",
        "component_active_sig",
        "component_uploader_sig",
        "terminal_active_sig",
        "terminal_uploader_sig",
        "terminal_layout_mode",
        "needs_layout_choice",
        "terminal_missing",
        "dup_conflicts_df",
        "dup_conflicts_draft",
    ]:
        st.session_state.pop(key, None)


def main() -> None:
    st.set_page_config(page_title="Excel įrankiai", layout="wide")
    st.title("Excel įrankiai")

    if "mode" not in st.session_state:
        st.session_state.mode = "none"

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Component correction", use_container_width=True):
            component_state_active = any(
                [
                    st.session_state.get("component_bytes") is not None,
                    bool(st.session_state.get("component_name")),
                    st.session_state.get("terminal_bytes") is not None,
                    bool(st.session_state.get("terminal_name")),
                    st.session_state.get("results") is not None,
                    st.session_state.get("run_id") is not None,
                    "gs_fix_df" in st.session_state,
                    "gs_fix_draft" in st.session_state,
                    "type_fix_df" in st.session_state,
                    "type_fix_draft" in st.session_state,
                    "gs_fix_editor" in st.session_state,
                    "type_fix_editor" in st.session_state,
                    bool(st.session_state.get("fix_applied_flash")),
                    bool(st.session_state.get("workflow_state")),
                    "component_active_sig" in st.session_state,
                    "component_uploader_sig" in st.session_state,
                    "terminal_active_sig" in st.session_state,
                    "terminal_uploader_sig" in st.session_state,
                    st.session_state.get("terminal_layout_mode") is not None,
                    bool(st.session_state.get("needs_layout_choice")),
                    bool(st.session_state.get("terminal_missing")),
                    "dup_conflicts_df" in st.session_state,
                    "dup_conflicts_draft" in st.session_state,
                ]
            )
            if st.session_state.mode == "component" and component_state_active:
                _reset_component_correction_state()
            st.session_state.mode = "component"
    with c2:
        if st.button("Wire sizing tool", use_container_width=True):
            st.session_state.mode = "wire"

    st.divider()

    if st.session_state.mode == "component":
        render_component_correction()
    elif st.session_state.mode == "wire":
        render_wire_tool()
    else:
        st.info("Pasirink įrankį viršuje.")


if __name__ == "__main__":
    main()
