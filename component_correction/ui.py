from __future__ import annotations

import hashlib
import base64
import re
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st


TERMINAL_TYPE_OPTIONS = ["2002-3201", "2002-3207"]
TERMINAL_TYPE_MAP = {"2002-3201": "WAGO.2002-3201_ADV", "2002-3207": "WAGO.2002-3207_ADV"}
RELAY_ALLOWED_RAW_TYPES = {
    "RGZE1S48M",
    "RXG22P7",
    "RXG22BD",
    "RE17LCBM",
    "RXM4GB2P7",
    "RXZE2S114M",
    "RXM4GB2BD",
}
FUSE_CONFLICT_TYPES = {"2002-1611/1000-836", "2002-1611/1000-541"}


def _normalize_selected_terminal_type(type_value: str) -> str:
    value = "" if type_value is None else str(type_value).strip()
    token_match = re.search(r"2002-3201|2002-3207", value)
    return token_match.group(0) if token_match else value


def _bytes_sig(name: str, b: bytes) -> tuple[str, int, str]:
    return (name or "", len(b), hashlib.md5(b).hexdigest())


def _img_to_data_url(path: str) -> str:
    b = Path(path).read_bytes()
    return "data:image/png;base64," + base64.b64encode(b).decode("utf-8")


def _uploader_changed(upl, sig_key: str) -> tuple[bool, tuple[str, int, str] | None]:
    if upl is None:
        return (False, None)

    b = upl.getvalue()
    sig = _bytes_sig(getattr(upl, "name", ""), b)
    return (st.session_state.get(sig_key) != sig, sig)


def _load_from_uploader_if_new(
    upl,
    bytes_key: str,
    active_sig_key: str,
    uploader_sig_key: str,
    name_key: str | None = None,
) -> None:
    changed, sig = _uploader_changed(upl, uploader_sig_key)
    if not changed or sig is None:
        return

    b = upl.getvalue()
    st.session_state[bytes_key] = b
    st.session_state[active_sig_key] = sig
    st.session_state[uploader_sig_key] = sig
    if name_key is not None:
        st.session_state[name_key] = getattr(upl, "name", "")
    st.session_state["terminal_layout_mode"] = None

    for k in [
        "workflow_state",
        "processed",
        "results",
        "missing_gs_draft",
        "type_fix_draft",
        "missing_gs_df",
        "unrec_type_df",
        "gs_fix_df",
        "gs_fix_draft",
        "type_fix_df",
        "fix_applied_flash",
        "gs_fix_editor",
        "type_fix_editor",
    ]:
        st.session_state.pop(k, None)

    st.session_state["workflow_state"] = "idle"


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


def _build_unrecognized_terminal_types_df(component_bytes: bytes) -> tuple[pd.DataFrame | None, pd.DataFrame, list[str]]:
    try:
        raw_df = pd.read_excel(
            BytesIO(component_bytes),
            sheet_name=0,
            engine="openpyxl",
        )
        raw_df.columns = raw_df.columns.astype(str).str.strip()
    except Exception:
        return None, pd.DataFrame(), ["read_error"]

    required_cols = ["Name", "Type", "Group Sorting"]
    missing_cols = [c for c in required_cols if c not in raw_df.columns]
    if missing_cols:
        return raw_df, pd.DataFrame(), missing_cols

    from component_correction.processor import classify_component

    rows = []
    for idx, row in raw_df.iterrows():
        name = row.get("Name", "")
        raw_type = row.get("Type", "")
        group_sorting = row.get("Group Sorting", "")

        name_str = "" if pd.isna(name) else str(name)
        if not re.search(r"-X\d+", name_str):
            continue

        gs_present = (not pd.isna(group_sorting)) and (str(group_sorting).strip() != "")
        if not gs_present:
            continue

        type_str = "" if pd.isna(raw_type) else str(raw_type).strip()
        if type_str in {"2002-1301", "2002-1307"}:
            continue

        info = classify_component(name, raw_type, group_sorting)
        is_unrecognized = (not info.get("allowed_raw_type", False)) and (not info.get("removed_by_name_prefix", False))
        if not is_unrecognized:
            continue

        rows.append(
            {
                "Name": name_str,
                "Type": type_str,
                "Group Sorting": group_sorting,
                "Correct Type": "",
                "_idx": idx,
            }
        )

    if not rows:
        return raw_df, pd.DataFrame(columns=["Name", "Type", "Group Sorting", "Correct Type", "_idx"]), []

    unrec_df = pd.DataFrame(rows)
    unrec_df = unrec_df.drop_duplicates(subset=["Name", "Type", "Group Sorting", "_idx"])
    unrec_df = unrec_df.sort_values(by=["Type", "Name"], kind="stable")
    return raw_df, unrec_df, []


def _detect_conflicting_duplicates(component_bytes: bytes) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_df = pd.read_excel(
        BytesIO(component_bytes),
        sheet_name=0,
        engine="openpyxl",
    )
    raw_df.columns = raw_df.columns.astype(str).str.strip()
    raw_df["_idx"] = raw_df.index

    if "Name" not in raw_df.columns or "Type" not in raw_df.columns:
        return raw_df, pd.DataFrame(columns=["Name", "Type", "Delete", "_idx", "Rule"])

    work_df = raw_df.copy()
    work_df["Name"] = work_df["Name"].fillna("").astype(str).str.strip()
    work_df["Type"] = work_df["Type"].fillna("").astype(str).str.strip()

    relay_pattern = "|".join(re.escape(token) for token in sorted(RELAY_ALLOWED_RAW_TYPES, key=len, reverse=True))
    fuse_pattern = "|".join(re.escape(token) for token in sorted(FUSE_CONFLICT_TYPES, key=len, reverse=True))

    def _extract_type_token(type_value: str) -> str:
        relay_match = re.search(relay_pattern, type_value)
        if relay_match:
            return relay_match.group(0)
        fuse_match = re.search(fuse_pattern, type_value)
        if fuse_match:
            return fuse_match.group(0)
        return type_value

    work_df["_type_token"] = work_df["Type"].map(_extract_type_token)
    conflicts_frames: list[pd.DataFrame] = []

    f_df = work_df[work_df["Name"].str.startswith("-F", na=False)].copy()
    for name, group in f_df.groupby("Name", sort=False):
        type_tokens = set(group["_type_token"].tolist())
        if not FUSE_CONFLICT_TYPES.issubset(type_tokens):
            continue
        conflict_rows = group[group["_type_token"].isin(FUSE_CONFLICT_TYPES)][["Name", "Type", "_idx"]].copy()
        conflict_rows["Rule"] = "FUSE_PAIR"
        conflicts_frames.append(conflict_rows)

    k_df = work_df[work_df["Name"].str.startswith("-K", na=False)].copy()
    for name, group in k_df.groupby("Name", sort=False):
        distinct_types = set(group["_type_token"].tolist())
        if len(distinct_types) < 2:
            continue
        if (group["Type"] == "AK-OB 110").any():
            continue
        all_relay = distinct_types.issubset(RELAY_ALLOWED_RAW_TYPES)
        if (not all_relay) or (all_relay and len(distinct_types) >= 3):
            conflict_rows = group[["Name", "Type", "_idx"]].copy()
            conflict_rows["Rule"] = "K_MIXED" if not all_relay else "K_RELAY_3PLUS"
            conflicts_frames.append(conflict_rows)

    if not conflicts_frames:
        return raw_df, pd.DataFrame(columns=["Name", "Type", "Delete", "_idx", "Rule"])

    conflicts_df = pd.concat(conflicts_frames, ignore_index=True)
    conflicts_df = conflicts_df.drop_duplicates(subset=["_idx"], keep="first")
    conflicts_df["Delete"] = False
    conflicts_df = conflicts_df[["Name", "Type", "Delete", "_idx", "Rule"]]
    conflicts_df = conflicts_df.sort_values(by=["Name", "Type", "_idx"], kind="stable")
    return raw_df, conflicts_df


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


def _run_precheck_or_process(component_bytes: bytes, terminal_bytes: bytes | None) -> None:
    missing_gs_raw_df, missing_gs_errors_df, missing_gs_cols = _build_missing_gs_terminals_df(component_bytes)
    _type_raw_df, type_fix_errors_df, type_fix_cols = _build_unrecognized_terminal_types_df(component_bytes)

    if missing_gs_cols and missing_gs_cols != ["read_error"]:
        st.warning("Missing GS tikrinimui trūksta stulpelių: " + ", ".join(missing_gs_cols))
        return
    if type_fix_cols and type_fix_cols != ["read_error"]:
        st.warning("Type tikrinimui trūksta stulpelių: " + ", ".join(type_fix_cols))
        return
    if missing_gs_cols == ["read_error"] or missing_gs_raw_df is None:
        st.warning("Missing GS tikrinimui nepavyko nuskaityti Component failo.")
        return
    if type_fix_cols == ["read_error"]:
        st.warning("Type tikrinimui nepavyko nuskaityti Component failo.")
        return

    if (not missing_gs_errors_df.empty) or (not type_fix_errors_df.empty):
        st.session_state["gs_fix_df"] = missing_gs_errors_df.copy()
        st.session_state["gs_fix_draft"] = missing_gs_errors_df.copy()
        st.session_state["type_fix_df"] = type_fix_errors_df.copy()
        st.session_state["type_fix_draft"] = type_fix_errors_df.copy()
        st.session_state["workflow_state"] = "needs_fix"
        st.session_state.pop("results", None)
        st.session_state.pop("gs_fix_editor", None)
        st.session_state.pop("type_fix_editor", None)
        st.rerun()

    if terminal_bytes is None:
        st.warning("⚠️ Terminal list neįkeltas. PE terminalų (WAGO.2002-3207_ADV) kiekis gali būti netikslus.")

    st.session_state["results"] = _run_processing(component_bytes, terminal_bytes)
    st.session_state.pop("gs_fix_df", None)
    st.session_state.pop("gs_fix_draft", None)
    st.session_state.pop("type_fix_df", None)
    st.session_state.pop("type_fix_draft", None)
    st.session_state.pop("gs_fix_editor", None)
    st.session_state.pop("type_fix_editor", None)
    st.session_state["workflow_state"] = "ready"
    st.session_state["run_id"] = st.session_state.get("run_id", 0) + 1
    st.rerun()


def render_component_correction() -> None:
    st.subheader("Component correction")
    if "workflow_state" not in st.session_state:
        st.session_state["workflow_state"] = "idle"

    pre_component_bytes = st.session_state.get("component_bytes")
    if pre_component_bytes is not None:
        try:
            conflict_raw_df, conflicts_df = _detect_conflicting_duplicates(pre_component_bytes)
        except Exception as conflict_exc:
            st.error(f"Nepavyko patikrinti konfliktuojančių dublikatų: {conflict_exc}")
            return

        if not conflicts_df.empty:
            terminal_bytes = st.session_state.get("terminal_bytes")
            st.error("Different components share the same Name.\nDelete the wrong rows and correct the drawings.")
            st.session_state["dup_conflicts_df"] = conflicts_df.copy()
            edited_conflicts_df = st.data_editor(
                st.session_state["dup_conflicts_df"],
                num_rows="fixed",
                use_container_width=True,
                key="dup_conflicts_draft",
                disabled=["Name", "Type", "_idx", "Rule"],
                column_config={
                    "_idx": None,
                    "Rule": None,
                    "Delete": st.column_config.CheckboxColumn("Delete"),
                },
            )

            if st.button("Delete selected", key="delete_dup_conflicts"):
                selected_idx = (
                    edited_conflicts_df.loc[edited_conflicts_df["Delete"] == True, "_idx"].astype(int).drop_duplicates()
                )
                if selected_idx.empty:
                    st.warning("Pasirinkite bent vieną eilutę ištrynimui.")
                else:
                    corrected_raw_df = conflict_raw_df.loc[~conflict_raw_df["_idx"].isin(selected_idx)].copy()
                    corrected_raw_df = corrected_raw_df.drop(columns=["_idx"], errors="ignore")

                    output_buffer = BytesIO()
                    with pd.ExcelWriter(output_buffer, engine="openpyxl") as writer:
                        corrected_raw_df.to_excel(writer, index=False)
                    corrected_bytes = output_buffer.getvalue()

                    st.session_state["component_bytes"] = corrected_bytes
                    existing_name = st.session_state.get("component_name", "")
                    existing_sig = st.session_state.get("component_active_sig")
                    if isinstance(existing_sig, tuple) and len(existing_sig) > 0 and existing_sig[0]:
                        existing_name = existing_sig[0]
                    st.session_state["component_active_sig"] = _bytes_sig(existing_name, corrected_bytes)

                    for k in [
                        "processed",
                        "results",
                        "missing_gs_draft",
                        "type_fix_draft",
                        "missing_gs_df",
                        "unrec_type_df",
                        "gs_fix_df",
                        "gs_fix_draft",
                        "type_fix_df",
                        "fix_applied_flash",
                        "gs_fix_editor",
                        "type_fix_editor",
                        "dup_conflicts_draft",
                    ]:
                        st.session_state.pop(k, None)

                    _, post_conflicts_df = _detect_conflicting_duplicates(corrected_bytes)
                    if not post_conflicts_df.empty:
                        st.session_state["dup_conflicts_df"] = post_conflicts_df.copy()
                        st.rerun()
                    else:
                        st.session_state.pop("dup_conflicts_df", None)
                        st.session_state.pop("dup_conflicts_draft", None)
                        _run_precheck_or_process(corrected_bytes, terminal_bytes)
            return

    if "workflow_state" not in st.session_state:
        st.session_state["workflow_state"] = "idle"

    component_file = (
        st.file_uploader("Įkelkite Component list", type=["xlsx"], key="comp_uploader")
        if st.session_state.get("component_bytes") is None
        else None
    )
    terminal_file = (
        st.file_uploader("Įkelkite Terminal list", type=["xlsx"], key="terminal_uploader")
        if st.session_state.get("terminal_bytes") is None
        else None
    )

    _load_from_uploader_if_new(
        component_file,
        "component_bytes",
        "component_active_sig",
        "component_uploader_sig",
        name_key="component_name",
    )
    _load_from_uploader_if_new(
        terminal_file,
        "terminal_bytes",
        "terminal_active_sig",
        "terminal_uploader_sig",
        name_key="terminal_name",
    )

    if st.session_state.get("fix_applied_flash"):
        st.success("Pakeitimai pritaikyti. Duomenys perapdoroti.")
        st.session_state["fix_applied_flash"] = False

    component_bytes = st.session_state.get("component_bytes")
    terminal_bytes = st.session_state.get("terminal_bytes")
    workflow_state = st.session_state.get("workflow_state", "idle")
    st.session_state.setdefault("terminal_missing", False)
    if "terminal_layout_mode" not in st.session_state:
        st.session_state["terminal_layout_mode"] = None
    if "needs_layout_choice" not in st.session_state:
        st.session_state["needs_layout_choice"] = False
    terminal_missing_condition = (
        st.session_state.get("component_bytes") is not None and st.session_state.get("terminal_bytes") is None
    )
    st.session_state["terminal_missing"] = bool(terminal_missing_condition)

    if component_bytes is None and terminal_bytes is not None:
        st.info("Component list privalomas. Įkelkite Component list failą.")
        return
    if component_bytes is None:
        st.info("Įkelk Excel (.xlsx) failą, tada spausk „Apdoroti failą“.")
        return
    if st.session_state.get("terminal_missing"):
        st.warning("⚠️ Terminal list neįkeltas. PE terminalų (WAGO.2002-3207_ADV) kiekis gali būti netikslus.")

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

    try:
        conflict_raw_df, conflicts_df = _detect_conflicting_duplicates(component_bytes)
    except Exception as conflict_exc:
        st.error(f"Nepavyko patikrinti konfliktuojančių dublikatų: {conflict_exc}")
        return

    if not conflicts_df.empty:
        st.error("Different components share the same Name.\nDelete the wrong rows and correct the drawings.")
        st.session_state["dup_conflicts_df"] = conflicts_df.copy()
        edited_conflicts_df = st.data_editor(
            st.session_state["dup_conflicts_df"],
            num_rows="fixed",
            use_container_width=True,
            key="dup_conflicts_draft",
            disabled=["Name", "Type", "_idx", "Rule"],
            column_config={
                "_idx": None,
                "Rule": None,
                "Delete": st.column_config.CheckboxColumn("Delete"),
            },
        )

        if st.button("Delete selected", key="delete_dup_conflicts"):
            selected_idx = (
                edited_conflicts_df.loc[edited_conflicts_df["Delete"] == True, "_idx"].astype(int).drop_duplicates()
            )
            if selected_idx.empty:
                st.warning("Pasirinkite bent vieną eilutę ištrynimui.")
            else:
                corrected_raw_df = conflict_raw_df.loc[~conflict_raw_df["_idx"].isin(selected_idx)].copy()
                corrected_raw_df = corrected_raw_df.drop(columns=["_idx"], errors="ignore")

                output_buffer = BytesIO()
                with pd.ExcelWriter(output_buffer, engine="openpyxl") as writer:
                    corrected_raw_df.to_excel(writer, index=False)
                corrected_bytes = output_buffer.getvalue()

                st.session_state["component_bytes"] = corrected_bytes
                existing_name = st.session_state.get("component_name", "")
                existing_sig = st.session_state.get("component_active_sig")
                if isinstance(existing_sig, tuple) and len(existing_sig) > 0 and existing_sig[0]:
                    existing_name = existing_sig[0]
                st.session_state["component_active_sig"] = _bytes_sig(existing_name, corrected_bytes)

                for k in [
                    "processed",
                    "results",
                    "missing_gs_draft",
                    "type_fix_draft",
                    "missing_gs_df",
                    "unrec_type_df",
                    "gs_fix_df",
                    "gs_fix_draft",
                    "type_fix_df",
                    "fix_applied_flash",
                    "gs_fix_editor",
                    "type_fix_editor",
                    "dup_conflicts_draft",
                ]:
                    st.session_state.pop(k, None)

                    _, post_conflicts_df = _detect_conflicting_duplicates(corrected_bytes)
                    if not post_conflicts_df.empty:
                        st.session_state["dup_conflicts_df"] = post_conflicts_df.copy()
                        st.rerun()
                    else:
                        st.session_state.pop("dup_conflicts_df", None)
                        st.session_state.pop("dup_conflicts_draft", None)
                        _run_precheck_or_process(corrected_bytes, terminal_bytes)
        return

    if workflow_state == "idle" and st.session_state.get("results") is None:
        missing_gs_raw_df, missing_gs_errors_df, missing_gs_cols = _build_missing_gs_terminals_df(component_bytes)
        _type_raw_df, type_fix_errors_df, type_fix_cols = _build_unrecognized_terminal_types_df(component_bytes)
        if (
            missing_gs_cols != ["read_error"]
            and type_fix_cols != ["read_error"]
            and (not missing_gs_cols)
            and (not type_fix_cols)
            and ((not missing_gs_errors_df.empty) or (not type_fix_errors_df.empty))
        ):
            st.session_state["gs_fix_df"] = missing_gs_errors_df.copy()
            st.session_state["gs_fix_draft"] = missing_gs_errors_df.copy()
            st.session_state["type_fix_df"] = type_fix_errors_df.copy()
            st.session_state["type_fix_draft"] = type_fix_errors_df.copy()
            st.session_state["workflow_state"] = "needs_fix"
            st.session_state.pop("results", None)
            st.session_state.pop("gs_fix_editor", None)
            st.session_state.pop("type_fix_editor", None)
            st.rerun()

    show_process_button = not (
        workflow_state == "needs_fix"
        or (workflow_state == "ready" and st.session_state.get("results") is not None)
    )

    if show_process_button and component_bytes is not None:
        selected_mode = st.session_state.get("terminal_layout_mode")
        left_button_type = "primary" if selected_mode == "two_rails" else "secondary"
        right_button_type = "primary" if selected_mode == "one_rail" else "secondary"
        st.markdown(
            """
            <style>
            .layout-image-wrapper {
                height: 420px;
                display: flex;
                justify-content: center;
                align-items: center;
            }
            .layout-image {
                max-height: 400px;
                max-width: 100%;
                object-fit: contain;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        left_col, right_col = st.columns(2, vertical_alignment="top")

        with left_col:
            with st.container(border=True):
                st.markdown("**Terminal layout: 2 DIN rails**")
                try:
                    img_src = _img_to_data_url("component_correction/Pictures/layout_2_din.png")
                    st.markdown(
                        f"""
                        <div class="layout-image-wrapper">
                            <img src="{img_src}" class="layout-image"/>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                except Exception:
                    st.caption("Image not found: component_correction/Pictures/layout_2_din.png")
                if st.button(
                    "Select 2 DIN rails",
                    key="layout_two_rails",
                    use_container_width=True,
                    type=left_button_type,
                ):
                    st.session_state["terminal_layout_mode"] = "two_rails"
                    st.rerun()

        with right_col:
            with st.container(border=True):
                st.markdown("**Terminal layout: 1 DIN rail**")
                try:
                    img_src = _img_to_data_url("component_correction/Pictures/layout_1_din.png")
                    st.markdown(
                        f"""
                        <div class="layout-image-wrapper">
                            <img src="{img_src}" class="layout-image"/>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                except Exception:
                    st.caption("Image not found: component_correction/Pictures/layout_1_din.png")
                if st.button(
                    "Select 1 DIN rail",
                    key="layout_one_rail",
                    use_container_width=True,
                    type=right_button_type,
                ):
                    st.session_state["terminal_layout_mode"] = "one_rail"
                    st.rerun()

    if show_process_button and st.button(
        "Apdoroti failą",
        key="comp_run",
        disabled=(component_bytes is None or st.session_state.get("terminal_layout_mode") is None),
    ):
        try:
            missing_gs_raw_df, missing_gs_errors_df, missing_gs_cols = _build_missing_gs_terminals_df(component_bytes)
            _type_raw_df, type_fix_errors_df, type_fix_cols = _build_unrecognized_terminal_types_df(component_bytes)

            if missing_gs_cols and missing_gs_cols != ["read_error"]:
                st.warning("Missing GS tikrinimui trūksta stulpelių: " + ", ".join(missing_gs_cols))
            elif type_fix_cols and type_fix_cols != ["read_error"]:
                st.warning("Type tikrinimui trūksta stulpelių: " + ", ".join(type_fix_cols))
            elif missing_gs_cols == ["read_error"] or missing_gs_raw_df is None:
                st.warning("Missing GS tikrinimui nepavyko nuskaityti Component failo.")
            elif type_fix_cols == ["read_error"]:
                st.warning("Type tikrinimui nepavyko nuskaityti Component failo.")
            elif (not missing_gs_errors_df.empty) or (not type_fix_errors_df.empty):
                st.session_state["gs_fix_df"] = missing_gs_errors_df.copy()
                st.session_state["gs_fix_draft"] = missing_gs_errors_df.copy()
                st.session_state["type_fix_df"] = type_fix_errors_df.copy()
                st.session_state["type_fix_draft"] = type_fix_errors_df.copy()
                st.session_state["workflow_state"] = "needs_fix"
                st.session_state.pop("results", None)
                st.session_state.pop("gs_fix_editor", None)
                st.session_state.pop("type_fix_editor", None)
                st.rerun()
            else:
                st.session_state["results"] = _run_processing(component_bytes, terminal_bytes)
                st.session_state.pop("gs_fix_df", None)
                st.session_state.pop("gs_fix_draft", None)
                st.session_state.pop("type_fix_df", None)
                st.session_state.pop("type_fix_draft", None)
                st.session_state.pop("gs_fix_editor", None)
                st.session_state.pop("type_fix_editor", None)
                st.session_state["workflow_state"] = "ready"
                st.session_state["run_id"] = st.session_state.get("run_id", 0) + 1
                st.rerun()

        except Exception as e:
            st.error(f"Įvyko netikėta klaida apdorojant failą: {e}")

    if st.session_state.get("workflow_state") == "needs_fix":
        st.subheader("Terminal corrections")

        if "gs_fix_df" not in st.session_state:
            st.session_state["gs_fix_df"] = pd.DataFrame(columns=["Name", "Type", "Group Sorting", "_idx"])
        if "gs_fix_draft" not in st.session_state:
            st.session_state["gs_fix_draft"] = st.session_state["gs_fix_df"].copy()
        if "type_fix_df" not in st.session_state:
            st.session_state["type_fix_df"] = pd.DataFrame(
                columns=["Name", "Type", "Group Sorting", "Correct Type", "_idx"]
            )
        if "type_fix_draft" not in st.session_state:
            st.session_state["type_fix_draft"] = st.session_state["type_fix_df"].copy()

        with st.form("fix_form", clear_on_submit=False):
            left_col, right_col = st.columns(2)

            with left_col:
                st.markdown("### Missing Group sorting for terminals")
                edited_gs_draft = st.data_editor(
                    st.session_state["gs_fix_draft"],
                    num_rows="fixed",
                    use_container_width=True,
                    key="gs_fix_editor",
                    disabled=["Name", "Type", "_idx"],
                    column_config={
                        "_idx": None,
                        "Group Sorting": st.column_config.NumberColumn("Group sorting", step=1),
                    },
                )

            with right_col:
                st.markdown("### Unrecognized type number for terminals")
                with st.expander("Terminal type options", expanded=False):
                    st.write(TERMINAL_TYPE_OPTIONS)

                edited_type_draft = st.data_editor(
                    st.session_state["type_fix_draft"],
                    num_rows="fixed",
                    use_container_width=True,
                    key="type_fix_editor",
                    disabled=["Name", "Type", "Group Sorting", "_idx"],
                    column_config={
                        "_idx": None,
                        "Correct Type": st.column_config.SelectboxColumn(
                            "Correct Type",
                            options=TERMINAL_TYPE_OPTIONS,
                            required=True,
                        ),
                    },
                )

            apply_clicked = st.form_submit_button("Taikyti pakeitimus")

        if apply_clicked:
            st.session_state["gs_fix_draft"] = edited_gs_draft
            st.session_state["type_fix_draft"] = edited_type_draft

            gs_fix_df = edited_gs_draft.copy()
            type_fix_df = edited_type_draft.copy()

            gs_values = gs_fix_df["Group Sorting"] if "Group Sorting" in gs_fix_df.columns else pd.Series(dtype=float)
            gs_as_text = gs_values.astype(str).str.strip()
            gs_numeric = pd.to_numeric(gs_values, errors="coerce")
            invalid_mask = gs_as_text.eq("") | gs_numeric.isna() | (gs_numeric % 1 != 0)
            if "_idx" not in gs_fix_df.columns:
                invalid_mask = pd.Series([True])

            type_values = (
                type_fix_df["Correct Type"] if "Correct Type" in type_fix_df.columns else pd.Series(dtype=str)
            )
            normalized_types = type_values.map(_normalize_selected_terminal_type)
            invalid_type_mask = ~normalized_types.astype(str).str.strip().isin(TERMINAL_TYPE_OPTIONS)
            if "_idx" not in type_fix_df.columns:
                invalid_type_mask = pd.Series([True])

            if invalid_mask.any():
                st.error("Klaida: terminalų (2002-3201 / 2002-3207) Group Sorting turi būti sveiki skaičiai.")
            elif invalid_type_mask.any():
                st.error("Klaida: parink Correct Type iš leidžiamų reikšmių.")
            else:
                try:
                    # --- CRITICAL FIX: load raw_df directly from bytes (single source of truth) ---
                    raw_df = pd.read_excel(BytesIO(component_bytes), sheet_name=0, engine="openpyxl")
                    raw_df.columns = raw_df.columns.astype(str).str.strip()

                    required_apply_cols = ["Name", "Type", "Group Sorting"]
                    missing_apply_cols = [c for c in required_apply_cols if c not in raw_df.columns]
                    if missing_apply_cols:
                        st.warning("Nepavyko pritaikyti pataisymų: trūksta stulpelių: " + ", ".join(missing_apply_cols))
                    else:
                        corrected_raw_df = raw_df.copy()

                        # Apply GS fixes
                        for _, row in gs_fix_df.iterrows():
                            corrected_raw_df.loc[int(row["_idx"]), "Group Sorting"] = int(float(row["Group Sorting"]))

                        # Apply Type fixes (WRITE BASE TYPE ONLY)
                        for _, row in type_fix_df.iterrows():
                            normalized_choice = _normalize_selected_terminal_type(row.get("Correct Type", ""))
                            corrected_raw_df.loc[int(row["_idx"]), "Type"] = normalized_choice

                        output_buffer = BytesIO()
                        with pd.ExcelWriter(output_buffer, engine="openpyxl") as writer:
                            corrected_raw_df.to_excel(writer, index=False)
                        corrected_bytes = output_buffer.getvalue()

                        st.session_state["component_bytes"] = corrected_bytes
                        existing_name = st.session_state.get("component_name", "")
                        existing_sig = st.session_state.get("component_active_sig")
                        if isinstance(existing_sig, tuple) and len(existing_sig) > 0 and existing_sig[0]:
                            existing_name = existing_sig[0]
                        st.session_state["component_active_sig"] = _bytes_sig(existing_name, corrected_bytes)
                        st.session_state["workflow_state"] = "idle"
                        st.session_state["results"] = None
                        st.session_state["terminal_layout_mode"] = None
                        st.session_state["needs_layout_choice"] = True
                        st.session_state.pop("gs_fix_df", None)
                        st.session_state.pop("gs_fix_draft", None)
                        st.session_state.pop("type_fix_df", None)
                        st.session_state.pop("type_fix_draft", None)
                        st.session_state.pop("gs_fix_editor", None)
                        st.session_state.pop("type_fix_editor", None)
                        st.session_state["fix_applied_flash"] = True
                        st.rerun()
                except Exception as e:
                    st.error(f"Įvyko klaida taikant pataisymus: {e}")

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

        if st.button("Išvalyti", key="comp_clear"):
            for k in [
                "component_bytes",
                "component_name",
                "terminal_bytes",
                "terminal_name",
                "results",
                "run_id",
                "gs_fix_df",
                "gs_fix_draft",
                "type_fix_df",
                "type_fix_draft",
                "gs_fix_editor",
                "type_fix_editor",
                "fix_applied_flash",
                "workflow_state",
                "component_active_sig",
                "component_uploader_sig",
                "terminal_active_sig",
                "terminal_uploader_sig",
            ]:
                st.session_state.pop(k, None)
            st.rerun()
