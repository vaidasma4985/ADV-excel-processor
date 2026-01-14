import streamlit as st


_TITLE = "Wire sizing tool"


def _sort_issues(issues):
    severity_rank = {"ERROR": 0, "WARNING": 1, "WARN": 1}
    return sorted(issues, key=lambda issue: (severity_rank.get(issue["severity"], 99), issue["code"]))


def _to_excel_bytes(df):
    import io
    import pandas as pd

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()


def _clear_results():
    for key in (
        "wire_results_computed",
        "wire_results_debug",
        "wire_results_raw_df",
        "wire_results_simplified_df",
        "wire_results_grouped_df",
        "wire_results_issues_df",
        "wire_results_unreachable_df",
    ):
        st.session_state.pop(key, None)


def render_wire_page() -> None:
    from wire_tool.io import load_connection_list
    from wire_tool.validators import validate_required_columns

    st.subheader(_TITLE)
    uploaded_file = st.file_uploader(
        "Upload connection list Excel file",
        type=["xlsx", "xlsm", "xls"],
    )
    if not uploaded_file:
        st.info("Upload a connection list to preview Power rows.")
        return

    import hashlib

    file_bytes = uploaded_file.getvalue()
    file_id = (uploaded_file.name, hashlib.sha256(file_bytes).hexdigest())
    if st.session_state.get("wire_tool_file_id") != file_id:
        st.session_state["wire_tool_file_id"] = file_id
        _clear_results()

    try:
        df = load_connection_list(uploaded_file)
    except Exception as exc:
        st.error(f"Failed to load Excel file: {exc}")
        st.stop()

    ok, missing = validate_required_columns(df)
    if not ok:
        st.error(f"Missing required columns: {', '.join(missing)}")
        st.stop()

    df_power = df[df["Line-Function"] == "Power"].copy()
    st.metric("Total rows", len(df))
    st.metric("Power rows", len(df_power))

    if df_power.empty:
        st.warning("No Power rows found")
        return

    with st.expander("Preview: Power rows"):
        st.dataframe(df_power.head(50), use_container_width=True)

    if st.button("Compute feeder paths"):
        from wire_tool.graph import build_graph, compute_feeder_paths

        adjacency, issues = build_graph(df_power)
        feeders, aggregated, feeder_issues, debug = compute_feeder_paths(adjacency)
        issues.extend(feeder_issues)

        import pandas as pd

        feeder_columns = [
            "feeder_end_name",
            "feeder_end_cp",
            "supply_net",
            "reachable",
            "path_nodes_raw",
            "path_names_collapsed",
            "device_chain",
            "path_len_nodes",
        ]
        feeders_df = pd.DataFrame(feeders, columns=feeder_columns)

        aggregated_columns = [
            "feeder_end_name",
            "feeder_end_cps",
            "supply_net",
            "path_names_collapsed",
            "device_chain_grouped",
            "reachable",
            "path_len_nodes",
        ]
        aggregated_df = pd.DataFrame(aggregated, columns=aggregated_columns)

        issues_df = pd.DataFrame(_sort_issues(issues))
        unreachable_df = feeders_df[~feeders_df["reachable"]].copy()
        simplified_columns = [
            "feeder_end_name",
            "feeder_end_cps",
            "supply_net",
            "path_names_collapsed",
            "device_chain_grouped",
            "reachable",
            "path_len_nodes",
        ]
        simplified_df = aggregated_df[simplified_columns].copy()

        # Store computed data in session_state so downloads/tables persist on rerun.
        st.session_state.update(
            {
                "wire_results_computed": True,
                "wire_results_debug": debug,
                "wire_results_raw_df": feeders_df,
                "wire_results_simplified_df": simplified_df,
                "wire_results_grouped_df": aggregated_df,
                "wire_results_issues_df": issues_df,
                "wire_results_unreachable_df": unreachable_df,
            }
        )

    if st.session_state.get("wire_results_computed"):
        feeders_df = st.session_state["wire_results_raw_df"]
        aggregated_df = st.session_state["wire_results_grouped_df"]
        simplified_df = st.session_state["wire_results_simplified_df"]
        issues_df = st.session_state["wire_results_issues_df"]
        unreachable_df = st.session_state["wire_results_unreachable_df"]
        debug = st.session_state["wire_results_debug"]

        feeders_found = len(feeders_df)
        unreachable_count = len(unreachable_df)
        issues_count = len(issues_df)

        st.metric("Feeders found", feeders_found)
        st.metric("Unreachable feeders", unreachable_count)
        st.metric("Issues", issues_count)

        simplified_tab, detailed_tab = st.tabs(["Simplified view", "Detailed view"])

        with simplified_tab:
            st.dataframe(simplified_df, use_container_width=True)

        with detailed_tab:
            with st.expander("Details: per-contact paths (raw)"):
                st.dataframe(feeders_df, use_container_width=True)

            with st.expander("Details: grouped summary"):
                st.dataframe(aggregated_df, use_container_width=True)

            with st.expander("Debug: feeder path computation"):
                st.write(
                    {
                        "total_nodes": debug["total_nodes"],
                        "total_edges": debug["total_edges"],
                        "main_root_nets": debug["main_root_nets"],
                        "sub_root_nets": debug["sub_root_nets"],
                        "feeder_ends_found": debug["feeder_ends_found"],
                        "unreachable_feeders_count": debug["unreachable_feeders_count"],
                    }
                )

            with st.expander("Downloads"):
                if unreachable_count > 0:
                    unreachable_excel = _to_excel_bytes(unreachable_df)
                    st.download_button(
                        "Download unreachable feeders",
                        data=unreachable_excel,
                        file_name="unreachable_feeders.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

                if issues_count > 0:
                    issues_excel = _to_excel_bytes(issues_df)
                    st.download_button(
                        "Download issues",
                        data=issues_excel,
                        file_name="wire_tool_issues.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

            if issues_count > 0:
                st.dataframe(issues_df, use_container_width=True)
