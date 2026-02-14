from __future__ import annotations

import re
from io import BytesIO

import pandas as pd
import streamlit as st


def _build_unrecognized_df(component_bytes: bytes) -> pd.DataFrame:
    raw_df = pd.read_excel(
        BytesIO(component_bytes),
        sheet_name=0,
        engine="openpyxl",
    )
    raw_df.columns = raw_df.columns.astype(str).str.strip()

    required_debug_cols = ["Name", "Type", "Quantity", "Group Sorting"]
    missing_debug_cols = [c for c in required_debug_cols if c not in raw_df.columns]
    if missing_debug_cols:
        raise ValueError(
            "Debug: trūksta stulpelių neapdorotų komponentų analizei: " + ", ".join(missing_debug_cols)
        )

    from component_correction.processor import classify_component  # lazy/local use in helper

    rows = []
    prefix_pattern = r"(-[XFTCGK][A-Z0-9]+)"
    for _, row in raw_df.iterrows():
        name = row.get("Name", "")
        raw_type = row.get("Type", "")
        group_sorting = row.get("Group Sorting", "")
        info = classify_component(name, raw_type, group_sorting)

        name_str = "" if pd.isna(name) else str(name)
        prefix_ok = bool(pd.notna(name) and re.search(prefix_pattern, name_str))
        is_unrecognized = (
            prefix_ok and (not info.get("allowed_raw_type", False)) and (not info.get("removed_by_name_prefix", False))
        )
        if not is_unrecognized:
            continue

        rows.append(
            {
                "Name": name_str,
                "Type": "" if pd.isna(raw_type) else str(raw_type),
                "Normalized Type": info.get("normalized_type", ""),
                "Group Sorting": "" if pd.isna(group_sorting) else group_sorting,
                "Domain": info.get("domain", "other"),
                "Reason": info.get("reason", "type_not_allowed"),
                "Allowed raw type": info.get("allowed_raw_type", False),
                "Would be processed": info.get("would_be_processed", False),
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "Name",
                "Type",
                "Normalized Type",
                "Group Sorting",
                "Domain",
                "Reason",
                "Allowed raw type",
                "Would be processed",
            ]
        )

    unrec_df = pd.DataFrame(rows)
    unrec_df = unrec_df.drop_duplicates(subset=["Name", "Type", "Group Sorting"])
    unrec_df = unrec_df.sort_values(by=["Type", "Name"], kind="stable")
    return unrec_df


def render_component_correction() -> None:
    # Lazy import to isolate tools
    from component_correction.processor import process_excel  # DO NOT TOUCH processor.py

    st.subheader("Component correction")
    st.caption("UI build: debug-v2 (type recognition via processor.classify_component)")

    component_file = st.file_uploader("Įkelkite Component list", type=["xlsx"], key="comp_uploader")
    terminal_file = st.file_uploader("Įkelkite Terminal list", type=["xlsx"], key="terminal_uploader")

    if component_file is not None:
        st.session_state["component_bytes"] = component_file.getvalue()
        st.session_state["component_name"] = component_file.name

    if terminal_file is not None:
        st.session_state["terminal_bytes"] = terminal_file.getvalue()
        st.session_state["terminal_name"] = terminal_file.name

    if st.button("Išvalyti", key="comp_clear"):
        for k in ["component_bytes", "component_name", "terminal_bytes", "terminal_name", "results", "run_id"]:
            st.session_state.pop(k, None)
        st.rerun()

    component_bytes = st.session_state.get("component_bytes")
    terminal_bytes = st.session_state.get("terminal_bytes")

    if component_bytes is None and terminal_bytes is not None:
        st.info("Component list privalomas. Įkelkite Component list failą.")
        return
    if component_bytes is None:
        st.info("Įkelk Excel (.xlsx) failą, tada spausk „Apdoroti failą“.")
        return

    transformer_needed = False
    missing_transformer_columns = False
    try:
        raw_df = pd.read_excel(BytesIO(component_bytes), sheet_name=0)
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
        if "component_bytes" not in st.session_state:
            st.warning("Pirmiausia įkelkite Component list failą.")
            return

        try:
            if terminal_bytes is None:
                st.warning(
                    "⚠️ Terminal list neįkeltas. PE terminalų (WAGO.2002-3207_ADV) kiekis gali būti netikslus."
                )

            component_io = BytesIO(st.session_state["component_bytes"])
            component_io.seek(0)
            current_component_bytes = component_io.getvalue()

            current_terminal_bytes = None
            if "terminal_bytes" in st.session_state:
                terminal_io = BytesIO(st.session_state["terminal_bytes"])
                terminal_io.seek(0)
                current_terminal_bytes = terminal_io.getvalue()

            cleaned_df, removed_df, excel_bytes, _stats = process_excel(
                current_component_bytes,
                terminal_list_bytes=current_terminal_bytes,
            )

            unrec_df = _build_unrecognized_df(current_component_bytes)

            st.session_state["results"] = {
                "cleaned_df": cleaned_df,
                "removed_df": removed_df,
                "unrec_df": unrec_df,
                "excel_bytes": excel_bytes,
            }
            st.session_state["run_id"] = st.session_state.get("run_id", 0) + 1

        except Exception as e:
            st.error(f"Įvyko netikėta klaida apdorojant failą: {e}")

    results = st.session_state.get("results")
    if not results:
        return

    cleaned_df = results.get("cleaned_df", pd.DataFrame())
    removed_df = results.get("removed_df", pd.DataFrame())
    unrec_df = results.get("unrec_df", pd.DataFrame())
    excel_bytes = results.get("excel_bytes", b"")

    with st.expander("Debug", expanded=False):
        tab_unrecognized, tab_cleaned, tab_removed, tab_raw = st.tabs(
            ["Unrecognized", "Cleaned", "Removed", "Raw preview"]
        )

        with tab_unrecognized:
            if unrec_df.empty:
                st.info("Unrecognized components nerasta.")
            else:
                search = st.text_input("Paieška (Name/Type)", "")
                reason_options = ["All"] + sorted(unrec_df["Reason"].astype(str).unique().tolist())
                reason_filter = st.selectbox("Reason", reason_options)
                only_type_not_allowed = st.checkbox("Rodyti tik type_not_allowed", value=True)

                filtered_df = unrec_df.copy()
                if search.strip():
                    q = search.strip().lower()
                    filtered_df = filtered_df[
                        filtered_df["Name"].astype(str).str.lower().str.contains(q, na=False)
                        | filtered_df["Type"].astype(str).str.lower().str.contains(q, na=False)
                    ]
                if reason_filter != "All":
                    filtered_df = filtered_df[filtered_df["Reason"] == reason_filter]
                if only_type_not_allowed:
                    filtered_df = filtered_df[filtered_df["Reason"] == "type_not_allowed"]

                if filtered_df.empty:
                    st.info("Unrecognized components nerasta pagal pasirinktus filtrus.")
                else:
                    st.dataframe(filtered_df, use_container_width=True)

        with tab_cleaned:
            if cleaned_df.empty:
                st.info("Cleaned duomenų nėra.")
            else:
                st.dataframe(cleaned_df, use_container_width=True)

        with tab_removed:
            if removed_df.empty:
                st.info("Ištrintų eilučių nėra.")
            else:
                st.dataframe(removed_df, use_container_width=True)

        with tab_raw:
            try:
                raw_preview_df = pd.read_excel(
                    BytesIO(component_bytes),
                    sheet_name=0,
                    engine="openpyxl",
                )
                raw_preview_df.columns = raw_preview_df.columns.astype(str).str.strip()
                if raw_preview_df.empty:
                    st.info("Raw preview tuščias.")
                else:
                    st.dataframe(raw_preview_df, use_container_width=True)
            except Exception as raw_exc:
                st.warning(f"Raw preview nepavyko nuskaityti: {raw_exc}")
                st.exception(raw_exc)

    st.download_button(
        label="Atsisiųsti rezultatą (Excel)",
        data=excel_bytes,
        file_name="processed_components.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


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
