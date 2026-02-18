from __future__ import annotations

import streamlit as st

from component_correction.ui import render_component_correction
from wire_tool.ui import render_wire_tool


def main() -> None:
    st.set_page_config(page_title="Excel įrankiai", layout="wide")
    st.title("Excel įrankiai")

    if "mode" not in st.session_state:
        st.session_state.mode = "none"

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Component correction", use_container_width=True):
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
