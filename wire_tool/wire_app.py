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

    st.dataframe(df_power.head(50), use_container_width=True)

    if st.button("Compute feeder paths"):
        from wire_tool.graph import build_graph, compute_feeder_paths

        adjacency, issues = build_graph(df_power)
        feeders, feeder_issues, debug = compute_feeder_paths(adjacency)
        issues.extend(feeder_issues)

        feeders_found = len(feeders)
        unreachable_count = sum(1 for feeder in feeders if not feeder["reachable_to_any_root"])
        issues_count = len(issues)

        st.metric("Feeders found", feeders_found)
        st.metric("Unreachable feeders", unreachable_count)
        st.metric("Issues", issues_count)

        import pandas as pd

        feeder_columns = [
            "feeder_end_name",
            "supply_net_any",
            "supply_net_main",
            "reachable_to_any_root",
            "reachable_to_main",
            "path_nodes_raw",
            "path_names_collapsed",
            "path_len_nodes",
        ]
        feeders_df = pd.DataFrame(feeders, columns=feeder_columns)
        st.dataframe(feeders_df, use_container_width=True)

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

        failed_feeders = feeders_df[~feeders_df["reachable_to_main"]].copy()
        if not failed_feeders.empty:
            failed_feeders["reason"] = failed_feeders["reachable_to_any_root"].apply(
                lambda reachable: "W203" if reachable else "W202"
            )
        failed_excel = _to_excel_bytes(failed_feeders)
        st.download_button(
            "Download feeders missing main supply",
            data=failed_excel,
            file_name="feeders_missing_main_supply.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        issues_df = pd.DataFrame(_sort_issues(issues))
        issues_excel = _to_excel_bytes(issues_df)
        st.download_button(
            "Download issues",
            data=issues_excel,
            file_name="wire_tool_issues.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        if issues:
            st.dataframe(issues_df, use_container_width=True)
