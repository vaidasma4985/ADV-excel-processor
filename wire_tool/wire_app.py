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


def _simplify_device_chain(chain: str) -> str:
    if not chain:
        return ""
    parts = [part.strip() for part in chain.split("->")]
    simplified = []
    seen = set()
    for part in parts:
        token = part.replace("NET:", "").strip()
        if not token:
            continue
        token = token.split(":", 1)[0].strip()
        token = token.split("/", 1)[0].strip()
        if not token:
            continue
        if token.startswith("-") or token in {"MT", "IT", "LT"}:
            if token not in seen:
                simplified.append(token)
                seen.add(token)
    return " -> ".join(simplified)


def _supply_group(supply_net: str) -> str:
    if not supply_net:
        return ""
    return supply_net.split("/", 1)[0].strip()


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
        feeders_df["supply_group"] = feeders_df["supply_net"].apply(_supply_group)
        feeders_df["device_chain_simplified"] = feeders_df["path_names_collapsed"].apply(
            _simplify_device_chain
        )
        feeders_df["feeder_end_cps"] = feeders_df["feeder_end_cp"]

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
        aggregated_df["supply_group"] = aggregated_df["supply_net"].apply(_supply_group)
        aggregated_df["device_chain_simplified"] = aggregated_df[
            "device_chain_grouped"
        ].apply(_simplify_device_chain)

        issues_df = pd.DataFrame(_sort_issues(issues))
        unreachable_df = feeders_df[~feeders_df["reachable"]].copy()
        simplified_columns = [
            "feeder_end_name",
            "feeder_end_cps",
            "supply_group",
            "device_chain_simplified",
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

        st.subheader("Validation / Spot-check")
        feeder_options = sorted(aggregated_df["feeder_end_name"].unique())
        if not feeder_options:
            st.info("No feeders detected for validation.")
        else:
            selected_feeder = st.selectbox(
                "Select feeder end",
                feeder_options,
                key="wire_validation_feeder",
            )
            selected_summary = aggregated_df[
                aggregated_df["feeder_end_name"] == selected_feeder
            ].head(1)
            if not selected_summary.empty:
                summary_row = selected_summary.iloc[0]
                st.write(
                    {
                        "supply_group": summary_row["supply_group"],
                        "reachable": summary_row["reachable"],
                        "path_len_nodes": summary_row["path_len_nodes"],
                    }
                )
                st.markdown(
                    f"**Device chain (simplified):** `{summary_row['device_chain_simplified']}`"
                )

            with st.expander("Raw path details"):
                raw_details = feeders_df[
                    feeders_df["feeder_end_name"] == selected_feeder
                ][
                    [
                        "feeder_end_name",
                        "feeder_end_cp",
                        "supply_net",
                        "path_nodes_raw",
                        "path_names_collapsed",
                        "device_chain",
                        "device_chain_simplified",
                        "reachable",
                        "path_len_nodes",
                    ]
                ]
                st.dataframe(raw_details, use_container_width=True)

            with st.expander("Source rows"):
                name_match = df_power["Name"].astype(str).str.contains(
                    selected_feeder, na=False, regex=False
                )
                name1_match = df_power["Name.1"].astype(str).str.contains(
                    selected_feeder, na=False, regex=False
                )
                source_rows = df_power[name_match | name1_match]
                st.dataframe(source_rows, use_container_width=True)

        simplified_tab, detailed_tab = st.tabs(["Simplified view", "Detailed view"])

        with simplified_tab:
            st.dataframe(simplified_df, use_container_width=True)

        with detailed_tab:
            minimal_columns = [
                "feeder_end_name",
                "feeder_end_cps",
                "supply_group",
                "device_chain_simplified",
                "reachable",
                "path_len_nodes",
            ]
            st.subheader("Per-contact paths (summary)")
            st.dataframe(feeders_df[minimal_columns], use_container_width=True)
            with st.expander("Extra columns: per-contact paths (raw)"):
                st.dataframe(feeders_df, use_container_width=True)

            st.subheader("Grouped summary (minimal)")
            st.dataframe(aggregated_df[minimal_columns], use_container_width=True)
            with st.expander("Extra columns: grouped summary"):
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
