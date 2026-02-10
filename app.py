from __future__ import annotations

import pandas as pd
import streamlit as st


def render_component_correction() -> None:
    # Lazy import to isolate tools
    from component_correction.processor import process_excel  # DO NOT TOUCH processor.py

    st.subheader("Component correction")

    uploaded = st.file_uploader("Įkelkite Component list", type=["xlsx"], key="comp_uploader")
    terminal_uploaded = st.file_uploader(
        "Įkelkite Terminal list", type=["xlsx"], key="terminal_uploader"
    )

    if uploaded is None and terminal_uploaded is not None:
        st.info("Component list privalomas. Įkelkite Component list failą.")
        return
    if uploaded is None:
        st.info("Įkelk Excel (.xlsx) failą, tada spausk „Apdoroti failą“.")
        return

    transformer_needed = False
    missing_transformer_columns = False
    try:
        raw_df = pd.read_excel(uploaded, sheet_name=0)
        normalized_columns = {col: str(col).strip() for col in raw_df.columns}
        name_col = next(
            (original for original, normalized in normalized_columns.items() if normalized == "Name"),
            None,
        )
        gs_col = next(
            (
                original
                for original, normalized in normalized_columns.items()
                if normalized.lower() in {"group sorting", "group sortin"}
            ),
            None,
        )
        if name_col is None or gs_col is None:
            missing_transformer_columns = True
        else:
            name_series = raw_df[name_col].astype(str)
            gs_series = raw_df[gs_col].astype(str)
            cond_name = name_series.str.contains(
                r"(^|[^A-Z0-9])\-X102([^A-Z0-9]|$)",
                regex=True,
                na=False,
            )
            cond_gs_text = gs_series.str.strip().eq("Transformer 460/230")
            transformer_needed = cond_name.any() or cond_gs_text.any()
    except Exception:
        missing_transformer_columns = True

    if transformer_needed:
        st.markdown(
            """
            <div style="background-color:#d4edda;padding:16px;border-radius:8px;">
              <span style="color:#1b5e20;font-size:28px;font-weight:800;">
                EXTERNAL TRANSFORMER TERMINALS NEEDED
              </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif missing_transformer_columns:
        st.warning("Missing columns for transformer check.")

    if st.button("Apdoroti failą", key="comp_run"):
        try:
            if terminal_uploaded is None:
                st.warning(
                    "⚠️ Terminal list neįkeltas. PE terminalų (WAGO.2002-3207_ADV) kiekis gali būti netikslus."
                )
            cleaned_df, removed_df, out_bytes, stats = process_excel(
                uploaded.getvalue(), terminal_list_bytes=terminal_uploaded.getvalue() if terminal_uploaded else None
            )

            st.subheader("Statistika")
            st.write(f"Įvesties eilučių: **{stats['input_rows']}**")
            st.write(f"Cleaned eilučių: **{stats['cleaned_rows']}**")
            st.write(f"Removed eilučių: **{stats['removed_rows']}**")

            st.subheader("Apdoroti duomenys (Cleaned)")
            st.dataframe(cleaned_df, use_container_width=True)

            st.subheader("Ištrintos eilutės (Removed)")
            if removed_df.empty:
                st.info("Ištrintų eilučių nėra.")
            else:
                st.dataframe(removed_df, use_container_width=True)

            st.download_button(
                label="Atsisiųsti rezultatą (Excel)",
                data=out_bytes,
                file_name="processed_components.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        except ValueError as e:
            st.error(f"Klaida: {e}")
        except Exception as e:
            st.error(f"Įvyko netikėta klaida apdorojant failą: {e}")


def render_wire_tool() -> None:
    from wire_tool.wire_app import render_wire_page  # new module

    render_wire_page()


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
