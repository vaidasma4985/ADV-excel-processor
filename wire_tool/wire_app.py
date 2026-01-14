import streamlit as st


_TITLE = "Wire sizing tool"


def _sort_issues(issues):
    severity_rank = {"ERROR": 0, "WARN": 1}
    return sorted(issues, key=lambda issue: (severity_rank.get(issue["severity"], 99), issue["code"]))


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
        unreachable_count = sum(1 for feeder in feeders if not feeder["reachable"])
        issues_count = len(issues)

        st.metric("Feeders found", feeders_found)
        st.metric("Unreachable feeders", unreachable_count)
        st.metric("Issues", issues_count)

        import pandas as pd

        feeder_columns = [
            "feeder_end_name",
            "supply_net",
            "path_nodes_raw",
            "path_names_collapsed",
            "path_len_nodes",
            "reachable",
        ]
        st.dataframe(pd.DataFrame(feeders, columns=feeder_columns), use_container_width=True)

        with st.expander("Debug: feeder path computation"):
            st.write(
                {
                    "total_nodes": debug["total_nodes"],
                    "total_edges": debug["total_edges"],
                    "supply_root_nets_found": debug["supply_root_nets_found"],
                    "feeder_ends_found": debug["feeder_ends_found"],
                    "unreachable_feeders_count": debug["unreachable_feeders_count"],
                }
            )

        if issues:
            st.dataframe(_sort_issues(issues), use_container_width=True)
