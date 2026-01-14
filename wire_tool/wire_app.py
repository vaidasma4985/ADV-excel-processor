import streamlit as st

from wire_tool.graph import bfs_parents, build_graph, compute_feeder_paths
from wire_tool.io import load_connection_list
from wire_tool.validators import validate_required_columns


_Q81_NAME = "-Q81"


def _sort_issues(issues):
    severity_rank = {"ERROR": 0, "WARN": 1}
    return sorted(issues, key=lambda issue: (severity_rank.get(issue["severity"], 99), issue["code"]))


def render_wire_page() -> None:
    st.subheader("Wire sizing tool")
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
        adjacency, issues = build_graph(df_power)
        start_nodes = [node for node in adjacency if node[0] == _Q81_NAME]

        if not start_nodes:
            issues.append(
                {
                    "severity": "ERROR",
                    "code": "W203",
                    "message": "No -Q81 start node found in Power rows.",
                    "row_index": None,
                    "context": {},
                }
            )
            st.error("-Q81 was not found in Power rows; unable to compute feeder paths.")
            st.dataframe(_sort_issues(issues), use_container_width=True)
            st.stop()

        parents = bfs_parents(adjacency, start_nodes)
        feeders, feeder_issues = compute_feeder_paths(adjacency, parents, start_nodes)
        issues.extend(feeder_issues)

        feeders_found = len(feeders)
        unreachable_count = sum(1 for feeder in feeders if not feeder["reachable"])
        issues_count = len(issues)

        st.metric("Feeders found", feeders_found)
        st.metric("Unreachable feeders", unreachable_count)
        st.metric("Issues", issues_count)

        st.dataframe(feeders, use_container_width=True)

        if issues:
            st.dataframe(_sort_issues(issues), use_container_width=True)
