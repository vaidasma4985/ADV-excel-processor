import json

import streamlit as st


_TITLE = "Wire sizing tool"
_ROOT_DEVICE_DENY_TAGS = {"-Q81"}
_ROOT_DEVICE_DENY_TYPE_SIGNATURES = {"C125S4FM"}
_ROOT_DEVICE_ALLOW_TAGS: set[str] = set()


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


def _normalize_terminal(value):
    import pandas as pd

    if value is None or pd.isna(value):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    normalized = str(value).strip().upper()
    normalized = (
        normalized.replace("’", "'")
        .replace("‘", "'")
        .replace("`", "'")
        .replace("´", "'")
    )
    return normalized or None


def _normalize_name(value):
    import pandas as pd

    if value is None or pd.isna(value):
        return None
    return str(value).strip() or None


def _base_device_name(value):
    name_str = _normalize_name(value)
    if not name_str:
        return None
    return name_str.split(":", 1)[0]


def _extract_wireno_tokens(wireno):
    if not wireno:
        return []
    import re

    tokens = [token for token in re.split(r"[;,]", str(wireno)) if token]
    return [token.strip() for token in tokens if token.strip()]


def _pinset_allows_front_only(pinset):
    neutral_front_tokens = {"N", "7N"}
    neutral_back_tokens = {"N'", "8N"}
    for pin in pinset:
        if pin.isdigit():
            if int(pin) % 2 == 0:
                return False
        elif pin in neutral_back_tokens:
            return False
        elif pin not in neutral_front_tokens:
            return False
    return True


def _collect_device_power_info(df_power):
    from wire_tool.pin_templates import pin_sort_key

    device_pins: dict[str, set[str]] = {}
    device_types: dict[str, set[str]] = {}
    device_nets: dict[str, set[str]] = {}

    for _, row in df_power.iterrows():
        wireno_tokens = _extract_wireno_tokens(row.get("Wireno"))
        for side in ("", ".1"):
            name = _base_device_name(row.get(f"Name{side}"))
            if not name:
                continue
            terminal = _normalize_terminal(row.get(f"C.name{side}"))
            if terminal:
                device_pins.setdefault(name, set()).add(terminal)
            type_value = row.get(f"Type{side}")
            type_token = _normalize_name(type_value)
            if type_token:
                device_types.setdefault(name, set()).add(type_token)
            if wireno_tokens:
                device_nets.setdefault(name, set()).update(wireno_tokens)

    pinsets = {
        device: tuple(sorted(pins, key=pin_sort_key)) for device, pins in device_pins.items()
    }
    type_signatures = {
        device: "|".join(sorted(types))
        for device, types in device_types.items()
    }
    for device in device_pins:
        type_signatures.setdefault(device, "UNKNOWN")

    nets = {device: sorted(values) for device, values in device_nets.items()}
    return pinsets, type_signatures, nets


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

    df_power = df[
        df["Line-Function"].astype(str).str.strip().str.lower() == "power"
    ].copy()
    st.metric("Total rows", len(df))
    st.metric("Power rows", len(df_power))

    if df_power.empty:
        st.warning("No Power rows found")
        return

    with st.expander("Preview: Power rows"):
        st.dataframe(df_power.head(50), use_container_width=True)

    from wire_tool.pin_templates import (
        infer_front_back_defaults,
        load_templates,
        pin_sort_key,
        resolve_template_for_pinset,
        save_templates,
        templates_from_json_bytes,
        templates_to_json_bytes,
    )
    from wire_tool.graph import build_graph, identify_root_devices

    templates = load_templates()
    pinsets, type_signatures, device_nets = _collect_device_power_info(df_power)

    adjacency, _, _, _, _ = build_graph(df_power)
    root_devices = identify_root_devices(adjacency)
    root_devices |= {name for name in pinsets if name in _ROOT_DEVICE_DENY_TAGS}
    for device, signature in type_signatures.items():
        if signature in _ROOT_DEVICE_DENY_TYPE_SIGNATURES:
            root_devices.add(device)
    for device in _ROOT_DEVICE_ALLOW_TAGS:
        root_devices.discard(device)

    auto_resolved = 0
    unknown_groups = []
    grouped_devices = {}
    for device, pinset in pinsets.items():
        if device in root_devices:
            continue
        signature = type_signatures.get(device, "UNKNOWN")
        grouped_devices.setdefault((pinset, signature), []).append(device)

    for (pinset, signature), devices in grouped_devices.items():
        template = resolve_template_for_pinset(pinset, signature, templates)
        if template is None:
            template = infer_front_back_defaults(pinset)
            if template is not None:
                auto_resolved += 1
        if template is None:
            unknown_groups.append((pinset, signature, devices))

    st.subheader("Templates")
    if st.session_state.pop("templates_upload_success", False):
        st.toast("Templates applied", icon="✅")
    st.download_button(
        "Download templates",
        data=templates_to_json_bytes(templates),
        file_name="pin_templates.json",
        mime="application/json",
    )
    uploaded_templates = st.file_uploader(
        "Upload pin_templates.json",
        type=["json"],
    )
    apply_upload = st.button(
        "Apply uploaded templates",
        disabled=uploaded_templates is None,
    )
    if apply_upload and uploaded_templates is not None:
        try:
            uploaded_data = uploaded_templates.getvalue()
            uploaded_templates_dict = templates_from_json_bytes(uploaded_data)
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")
        except ValueError:
            st.error("Template file has wrong schema")
        else:
            save_templates(uploaded_templates_dict)
            st.session_state["templates_upload_success"] = True
            st.rerun()

    st.subheader("Pin template resolver")
    st.write(
        {
            "devices_scanned_power": len(pinsets),
            "unknown_pinset_groups": len(unknown_groups),
            "auto_resolved_groups": auto_resolved,
            "excluded_root_devices": len(root_devices),
        }
    )

    if unknown_groups:
        st.info(
            "Define pin templates for unknown power pinsets. Only Power rows are used."
        )
    else:
        st.success("All power pinsets resolved (saved templates or defaults).")

    for index, (pinset, signature, devices) in enumerate(
        sorted(unknown_groups, key=lambda item: (item[1], item[0]))
    ):
        pinset_list = list(pinset)
        device_examples = devices[:5]
        expander_title = f"Pinset: {', '.join(pinset_list)} | Type: {signature}"
        with st.expander(expander_title, expanded=False):
            st.write(f"Type signature: {signature}")
            st.write(f"Example devices: {', '.join(device_examples)}")
            table_rows = []
            for device in sorted(devices):
                table_rows.append(
                    {
                        "device": device,
                        "nets": ", ".join(device_nets.get(device, [])),
                        "pins": ", ".join(pinset_list),
                    }
                )
            st.table(table_rows)

            front_key = f"front_pins_{index}"
            back_key = f"back_pins_{index}"
            neutral_key = f"neutral_warn_{index}"
            form_key = f"tpl_form_{index}"
            with st.form(key=form_key, clear_on_submit=True):
                default_front = [pin for pin in pinset_list if pin.isdigit() and int(pin) % 2 == 1]
                front_pins = st.multiselect(
                    "Front pins",
                    options=pinset_list,
                    default=default_front,
                    key=front_key,
                )
                remaining = [pin for pin in pinset_list if pin not in front_pins]
                back_pins = st.multiselect(
                    "Back pins",
                    options=remaining,
                    default=[],
                    key=back_key,
                )

                neutral_tokens = {"N", "N'", "7N", "8N"}
                front_neutral = [pin for pin in front_pins if pin in neutral_tokens]
                back_neutral = [pin for pin in back_pins if pin in neutral_tokens]

                if len(front_neutral) > 1 or len(back_neutral) > 1:
                    st.error("Select at most one neutral token in front/back pins.")
                    st.session_state[neutral_key] = True
                else:
                    st.session_state[neutral_key] = False

                submitted = st.form_submit_button("Save template")
                if submitted:
                    if st.session_state.get(neutral_key):
                        st.stop()
                    if not set(front_pins).issubset(pinset_list) or not set(back_pins).issubset(
                        pinset_list
                    ):
                        st.error("Selected pins must come from the pinset.")
                        st.stop()

                    front_only_allowed = _pinset_allows_front_only(pinset_list)
                    front_only = not back_pins and front_only_allowed

                    if not back_pins and not front_only_allowed:
                        st.error(
                            "Back pins are required for this pinset. Use front-only only when pinset has only front pins."
                        )
                        st.stop()

                    if back_pins and set(front_pins) | set(back_pins) != set(pinset_list):
                        st.error("Front/back pins must cover the full pinset.")
                        st.stop()

                    template = {
                        "pinset": sorted(pinset_list, key=pin_sort_key),
                        "type_signature": signature,
                        "front_pins": sorted(front_pins, key=pin_sort_key),
                        "back_pins": sorted(back_pins, key=pin_sort_key),
                        "neutral_front_token": front_neutral[0] if front_neutral else None,
                        "neutral_back_token": back_neutral[0] if back_neutral else None,
                        "front_only": front_only,
                    }
                    templates[(tuple(sorted(pinset_list, key=pin_sort_key)), signature)] = template
                    save_templates(templates)
                    st.toast("Template saved", icon="✅")
                    st.rerun()

    if st.button("Compute feeder paths"):
        from wire_tool.graph import build_graph, compute_feeder_paths

        device_templates = {}
        for device, pinset in pinsets.items():
            if device in root_devices:
                continue
            signature = type_signatures.get(device, "UNKNOWN")
            template = resolve_template_for_pinset(pinset, signature, templates)
            if template is None:
                template = infer_front_back_defaults(pinset)
                if template is not None:
                    template = {
                        **template,
                        "type_signature": signature,
                    }
            if template:
                device_templates[device] = template

        (
            adjacency,
            issues,
            device_terminals,
            device_parts,
            logical_edges_added,
        ) = build_graph(df_power, device_templates=device_templates)
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
            "root_chain_str",
            "spine_str",
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
            "root_chain_str",
            "spine_str",
        ]
        aggregated_df = pd.DataFrame(aggregated, columns=aggregated_columns)

        issues_df = pd.DataFrame(_sort_issues(issues))
        unreachable_df = feeders_df[~feeders_df["reachable"]].copy()
        simplified_columns = [
            "feeder_end_name",
            "root_chain_str",
            "spine_str",
            "reachable",
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

        st.subheader("Simplified view")
        st.dataframe(simplified_df, use_container_width=True)

        with st.expander("Detailed view"):
            with st.expander("Details: per-contact paths (raw)"):
                st.dataframe(feeders_df, use_container_width=True)

            with st.expander("Details: grouped summary"):
                st.dataframe(aggregated_df, use_container_width=True)

            cable_df = st.session_state.get("cable_df")
            if cable_df is not None:
                with st.expander("Preview: cable rows"):
                    if "reason" in cable_df.columns:
                        st.dataframe(
                            cable_df[cable_df["reason"] == "ok"].head(50),
                            use_container_width=True,
                        )
                    else:
                        st.info("Cable preview skipped: missing 'reason' column.")

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
