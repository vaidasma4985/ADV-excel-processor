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


def _build_missing_gs_terminals_df(component_bytes: bytes) -> tuple[pd.DataFrame | None, pd.DataFrame, list[str]]:
    try:
        raw_df = pd.read_excel(
            BytesIO(component_bytes),
            sheet_name=0,
            engine="openpyxl",
        )
        raw_df.columns = raw_df.columns.astype(str).str.strip()
    except Exception:
        return None, pd.DataFrame(), ["read_error"]

    required_cols = ["Type", "Group Sorting"]
    missing_cols = [c for c in required_cols if c not in raw_df.columns]
    if missing_cols:
        return raw_df, pd.DataFrame(), missing_cols

    raw_type_str = raw_df["Type"].astype(str).str.strip()
    terminal_type_mask = (
        raw_type_str.isin(["2002-3201", "2002-3207"])
        | raw_type_str.isin(["WAGO.2002-3201_ADV", "WAGO.2002-3207_ADV"])
        | raw_type_str.str.contains(r"\b2002-3201\b|\b2002-3207\b", regex=True, na=False)
    )

    gs = raw_df["Group Sorting"]
    gs_missing = gs.isna() | (gs.astype(str).str.strip() == "")

    errors_df = raw_df.loc[terminal_type_mask & gs_missing, ["Name", "Type", "Group Sorting"]].copy()
    errors_df["_idx"] = errors_df.index
    return raw_df, errors_df, []


def _run_processing(component_bytes: bytes, terminal_bytes: bytes | None) -> dict[str, pd.DataFrame | bytes]:
    from component_correction.processor import process_excel

    cleaned_df, removed_df, excel_bytes, _stats = process_excel(
        component_bytes,
        terminal_list_bytes=terminal_bytes,
    )
    unrec_df = _build_unrecognized_df(component_bytes)
    return {
        "cleaned_df": cleaned_df,
        "removed_df": removed_df,
        "unrec_df": unrec_df,
        "excel_bytes": excel_bytes,
    }


def render_component_correction() -> None:
    st.subheader("Component correction")
    st.caption("UI build: debug-v2 (type recognition via processor.classify_component)")

    if "workflow_state" not in st.session_state:
        st.session_state["workflow_state"] = "idle"

    component_file = st.file_uploader("Įkelkite Component list", type=["xlsx"], key="comp_uploader")
    terminal_file = st.file_uploader("Įkelkite Terminal list", type=["xlsx"], key="terminal_uploader")

    if component_file is not None:
        new_component_bytes = component_file.getvalue()
        if st.session_state.get("component_bytes") != new_component_bytes:
            st.session_state["component_bytes"] = new_component_bytes
            st.session_state["component_name"] = component_file.name
            for k in ["results", "pending_gs_df", "workflow_state", "gs_fix_applied", "gs_fix_editor"]:
                st.session_state.pop(k, None)
            st.session_state["workflow_state"] = "idle"

    if terminal_file is not None:
        st.session_state["terminal_bytes"] = terminal_file.getvalue()
        st.session_state["terminal_name"] = terminal_file.name

    if st.session_state.get("gs_fix_applied"):
        st.success("GS pritaikyti. Duomenys perapdoroti.")
        st.session_state["gs_fix_applied"] = False

    component_bytes = st.session_state.get("component_bytes")
    terminal_bytes = st.session_state.get("terminal_bytes")
    workflow_state = st.session_state.get("workflow_state", "idle")

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

    if workflow_state != "needs_gs_fix" and st.button("Apdoroti failą", key="comp_run"):
        try:
            missing_gs_raw_df, missing_gs_errors_df, missing_gs_cols = _build_missing_gs_terminals_df(component_bytes)

            if missing_gs_cols and missing_gs_cols != ["read_error"]:
                st.warning("Missing GS tikrinimui trūksta stulpelių: " + ", ".join(missing_gs_cols))
            elif missing_gs_cols == ["read_error"] or missing_gs_raw_df is None:
                st.warning("Missing GS tikrinimui nepavyko nuskaityti Component failo.")
            elif not missing_gs_errors_df.empty:
                st.session_state["pending_gs_df"] = missing_gs_errors_df
                st.session_state["workflow_state"] = "needs_gs_fix"
                st.session_state.pop("results", None)
                st.rerun()
            else:
                if terminal_bytes is None:
                    st.warning(
                        "⚠️ Terminal list neįkeltas. PE terminalų (WAGO.2002-3207_ADV) kiekis gali būti netikslus."
                    )

                st.session_state["results"] = _run_processing(component_bytes, terminal_bytes)
                st.session_state["workflow_state"] = "ready"
                st.session_state["run_id"] = st.session_state.get("run_id", 0) + 1
                st.rerun()

        except Exception as e:
            st.error(f"Įvyko netikėta klaida apdorojant failą: {e}")

    if st.session_state.get("workflow_state") == "needs_gs_fix":
        st.error(
            "Neužpildyti Group Sorting laukai terminalams (2002-3201 / 2002-3207). "
            "Užpildyk žemiau ir spausk 'Taikyti pakeitimus'."
        )
        st.subheader("Trūkstami Group Sorting (terminalai)")

        pending_gs_df = st.session_state.get("pending_gs_df", pd.DataFrame())
        editor_df = st.data_editor(
            pending_gs_df,
            num_rows="fixed",
            use_container_width=True,
            key="gs_fix_editor",
        )
        st.session_state["pending_gs_df"] = editor_df

        if st.button("Taikyti pakeitimus", key="apply_gs_fixes_main"):
            gs_values = editor_df["Group Sorting"]
            gs_as_text = gs_values.astype(str).str.strip()
            gs_numeric = pd.to_numeric(gs_values, errors="coerce")
            invalid_mask = gs_as_text.eq("") | gs_numeric.isna() | (gs_numeric % 1 != 0)

            if invalid_mask.any():
                st.error("Klaida: terminalų (2002-3201 / 2002-3207) Group Sorting turi būti sveiki skaičiai.")
            else:
                try:
                    raw_df, _errors_df, missing_cols = _build_missing_gs_terminals_df(component_bytes)
                    if raw_df is None or missing_cols:
                        st.warning("Nepavyko pritaikyti GS pataisymų: trūksta stulpelių arba failas neperskaitomas.")
                    else:
                        corrected_raw_df = raw_df.copy()
                        for _, row in editor_df.iterrows():
                            corrected_raw_df.loc[int(row["_idx"]), "Group Sorting"] = int(float(row["Group Sorting"]))

                        output_buffer = BytesIO()
                        with pd.ExcelWriter(output_buffer, engine="openpyxl") as writer:
                            corrected_raw_df.to_excel(writer, index=False)
                        corrected_bytes = output_buffer.getvalue()

                        st.session_state["component_bytes"] = corrected_bytes
                        st.session_state["results"] = _run_processing(corrected_bytes, terminal_bytes)
                        st.session_state["workflow_state"] = "ready"
                        st.session_state["run_id"] = st.session_state.get("run_id", 0) + 1
                        st.session_state.pop("pending_gs_df", None)
                        st.session_state.pop("gs_fix_editor", None)
                        st.session_state["gs_fix_applied"] = True
                        st.rerun()
                except Exception as e:
                    st.error(f"Įvyko klaida taikant GS pataisymus: {e}")

    results = st.session_state.get("results")
    ready_state = st.session_state.get("workflow_state") == "ready" and results is not None

    if ready_state:
        excel_bytes = results.get("excel_bytes", b"")

        st.download_button(
            label="Atsisiųsti rezultatą (Excel)",
            data=excel_bytes,
            file_name="processed_components.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        with st.expander("Debug", expanded=False):
            tab_unrecognized, tab_raw = st.tabs(["Unrecognized", "Raw preview"])

            with tab_unrecognized:
                unrec_df = results.get("unrec_df", pd.DataFrame())
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

            with tab_raw:
                try:
                    raw_preview_df = pd.read_excel(
                        BytesIO(st.session_state["component_bytes"]),
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

        if st.button("Išvalyti", key="comp_clear"):
            for k in [
                "component_bytes",
                "component_name",
                "terminal_bytes",
                "terminal_name",
                "results",
                "run_id",
                "pending_gs_df",
                "gs_fix_editor",
                "gs_fix_applied",
                "workflow_state",
            ]:
                st.session_state.pop(k, None)
            st.rerun()


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
