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


def _preview_reason_ok(df) -> None:
    if "reason" in df.columns:
        st.dataframe(df[df["reason"] == "ok"].head(20), use_container_width=True)
    else:
        st.warning("Reason column not present; showing the first 20 rows instead.")
        st.dataframe(df.head(20), use_container_width=True)


def render_wire_page() -> None:
    from wire_tool.io import load_connection_list
    from wire_tool.validators import validate_required_columns
    from wire_tool.graph import scan_pin_templates
    from wire_tool.pin_templates import is_front_only_pinset, load_templates, save_templates

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

    df_power = df[df["Line-Function"].astype(str).str.strip().str.lower() == "power"].copy()
    st.metric("Total rows", len(df))
    st.metric("Power rows", len(df_power))

    if df_power.empty:
        st.warning("No Power rows found")
        return

    with st.expander("Preview: Power rows"):
        st.dataframe(df_power.head(50), use_container_width=True)

    st.subheader("Pin template resolver")
    templates_path = "data/pin_templates.json"
    templates = load_templates(templates_path)
    templates_needed, inconsistent_devices, scan_debug = scan_pin_templates(
        df_power,
        templates=templates,
    )

    st.caption(
        "Only power pins are shown (1-8 + neutral tokens). Aux/control pins are excluded."
    )

    if inconsistent_devices:
        st.warning("Inconsistent power pinsets detected; templates will not be requested.")
        st.dataframe(inconsistent_devices, use_container_width=True)

    if not templates_needed:
        st.success("All pinsets resolved by built-ins or saved templates.")
    else:
        st.info(
            f"{len(templates_needed)} unknown pinset(s) detected. "
            "Define FRONT/BACK pins to persist templates for future runs."
        )

        grouped: dict[tuple[str, str], dict[str, object]] = {}
        for entry in templates_needed:
            pinset_key = entry["pinset_key"]
            type_signature = entry.get("type_signature", "")
            grouped[(pinset_key, type_signature)] = {
                "pins": entry.get("pins", []),
                "example_devices": entry.get("example_devices", []),
                "example_device_context": entry.get("example_device_context", []),
                "type_signature": type_signature,
            }

        for (pinset_key, _type_signature), data in grouped.items():
            pins = data["pins"] or pinset_key.split(",")
            devices = data.get("example_devices", [])
            context_rows = data.get("example_device_context", [])
            type_signature = data.get("type_signature") or ""
            group_label = type_signature or "(unknown)"
            group_id = f"{pinset_key}__{group_label}".replace("|", "_")
            st.markdown(f"**Pinset `{pinset_key}`**")
            st.caption(f"Type signature: {group_label}")
            if devices:
                st.caption(f"Example devices: {', '.join(devices[:5])}")
            if pins:
                st.caption(f"Power pins: {', '.join(pins)}")
            if context_rows:
                st.dataframe(context_rows, use_container_width=True)

            front_key = f"pin_front_{group_id}"
            back_key = f"pin_back_{group_id}"
            neutral_front_key = f"pin_neutral_front_{group_id}"
            neutral_back_key = f"pin_neutral_back_{group_id}"

            front_selection = st.multiselect(
                "FRONT pins",
                options=pins,
                key=front_key,
            )
            remaining = [pin for pin in pins if pin not in front_selection]
            st.multiselect(
                "BACK pins",
                options=remaining,
                key=back_key,
            )
            st.text_input(
                "Neutral front token (optional)",
                key=neutral_front_key,
            )
            st.text_input(
                "Neutral back token (optional)",
                key=neutral_back_key,
            )

        if st.button("Save pin templates"):
            errors: list[str] = []
            for (pinset_key, _type_signature), data in grouped.items():
                type_signature = data.get("type_signature") or ""
                group_label = type_signature or "(unknown)"
                group_id = f"{pinset_key}__{group_label}".replace("|", "_")
                pins = data["pins"] or pinset_key.split(",")
                front_selection = st.session_state.get(f"pin_front_{group_id}", [])
                back_selection = st.session_state.get(f"pin_back_{group_id}", [])
                neutral_front = st.session_state.get(
                    f"pin_neutral_front_{group_id}",
                    "",
                ).strip()
                neutral_back = st.session_state.get(
                    f"pin_neutral_back_{group_id}",
                    "",
                ).strip()
                front_only_allowed = is_front_only_pinset(pinset_key)

                if not front_selection:
                    errors.append(f"{pinset_key}: select at least one FRONT pin.")
                if set(front_selection) & set(back_selection):
                    errors.append(f"{pinset_key}: FRONT and BACK pins must be disjoint.")
                if not back_selection and not front_only_allowed:
                    errors.append(
                        f"{pinset_key}: BACK pins are empty; only allowed for front-only pinsets."
                    )
                if back_selection and set(front_selection) | set(back_selection) != set(pins):
                    errors.append(f"{pinset_key}: FRONT+BACK must cover all pins.")
                if (neutral_front and not neutral_back) or (neutral_back and not neutral_front):
                    errors.append(
                        f"{pinset_key}: provide both neutral tokens or leave both blank."
                    )
                if neutral_front and neutral_front not in pins:
                    errors.append(
                        f"{pinset_key}: neutral front token '{neutral_front}' is not in pinset."
                    )
                if neutral_back and neutral_back not in pins:
                    errors.append(
                        f"{pinset_key}: neutral back token '{neutral_back}' is not in pinset."
                    )

            if errors:
                st.error("\n".join(errors))
            else:
                for (pinset_key, _type_signature), data in grouped.items():
                    type_signature = data.get("type_signature") or ""
                    group_label = type_signature or "(unknown)"
                    group_id = f"{pinset_key}__{group_label}".replace("|", "_")
                    pins = data["pins"] or pinset_key.split(",")
                    front_selection = st.session_state.get(
                        f"pin_front_{group_id}",
                        [],
                    )
                    back_selection = st.session_state.get(
                        f"pin_back_{group_id}",
                        [],
                    )
                    neutral_front = st.session_state.get(
                        f"pin_neutral_front_{group_id}",
                        "",
                    ).strip()
                    neutral_back = st.session_state.get(
                        f"pin_neutral_back_{group_id}",
                        "",
                    ).strip()
                    front_only = False
                    if not back_selection and is_front_only_pinset(pinset_key):
                        front_only = True

                    mapping: dict[str, object] = {
                        "front_pins": front_selection,
                        "back_pins": back_selection,
                        "front_only": front_only,
                    }
                    if neutral_front and neutral_back:
                        mapping["neutral_front_token"] = neutral_front
                        mapping["neutral_back_token"] = neutral_back
                    pinset_entry = templates.setdefault("pinsets", {})
                    pinset_entry.setdefault(pinset_key, {})
                    type_signature_key = type_signature or "*"
                    pinset_entry[pinset_key][type_signature_key] = mapping

                save_templates(templates_path, templates)
                st.success("Pin templates saved. Rerun the graph to apply changes.")

    st.caption(
        "Scan stats: devices={devices_total}, resolved={resolved_devices}, "
        "unknown pinsets={unknown_pinsets}, inconsistent={inconsistent_devices}, "
        "root excluded={root_devices_excluded}".format(
            **scan_debug
        )
    )
    with st.expander("Pin resolver debug"):
        st.write(
            {
                "devices_in_power_rows": scan_debug["devices_total"],
                "pinsets_total": scan_debug["pinsets_total"],
                "pinsets_unknown": scan_debug["unknown_pinsets"],
                "pinsets_resolved": scan_debug["resolved_groups"],
                "root_devices_excluded": scan_debug["root_devices_excluded"],
            }
        )
        if templates_needed:
            st.write("Top unknown pinsets:")
            preview = [
                {
                    "pinset_key": entry["pinset_key"],
                    "example_devices": ", ".join(entry.get("example_devices", [])[:5]),
                }
                for entry in templates_needed[:5]
            ]
            st.dataframe(preview, use_container_width=True)

    if st.button("Compute feeder paths"):
        from wire_tool.graph import build_graph, compute_feeder_paths

        (
            adjacency,
            issues,
            device_terminals,
            device_parts,
            logical_edges_added,
        ) = build_graph(df_power, templates=templates, templates_path=templates_path)
        feeders, aggregated, feeder_issues, debug = compute_feeder_paths(
            adjacency,
            device_terminals=device_terminals,
            device_parts=device_parts,
            logical_edges_added=logical_edges_added,
        )
        issues.extend(feeder_issues)

        import pandas as pd

        feeder_columns = [
            "feeder_end_name",
            "feeder_end_cp",
            "supply_net",
            "subroot_net",
            "path_main",
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
            "subroot_net",
            "path_main",
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
            "subroot_net",
            "path_main",
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

            with st.expander("Preview: reason == ok (if available)"):
                _preview_reason_ok(feeders_df)

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
                        "feeder_end_bases_count": debug["feeder_end_bases_count"],
                        "feeder_end_bases_sample": debug["feeder_end_bases_sample"],
                        "stacked_example": debug["stacked_example"],
                        "stacked_groups_sample": debug["stacked_groups_sample"],
                        "logical_edges_added": debug["logical_edges_added"],
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
