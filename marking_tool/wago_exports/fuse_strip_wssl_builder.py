from __future__ import annotations

import copy
from typing import Any
import uuid
import xml.etree.ElementTree as ET

from .shared_wssl import (
    WsslComponentStyle,
    WsslTemplateFile,
    _build_wssl_zip_bytes,
    _count_terminal_strip_grid_groups,
    _first_terminal_strip_cell_template,
    _first_terminal_strip_grid_template,
    _float_attr,
    _format_wssl_float,
    _FUSE_STRIP_CONTENT_ROTATION,
    _FUSE_STRIP_TEMPLATE_IMPORT_CONFIG,
    _FUSE_STRIP_TEMPLATE_TABLE_CONFIG,
    _grid_wago_text_components,
    _refresh_identifiers,
    _safe_terminal_strip_space,
    _terminal_strip_grid_endplate,
    _terminal_strip_grid_row_col,
    _terminal_strip_grid_row_col_child_list,
    _terminal_strip_outer_grid_cell,
    _terminal_strip_outer_grid_row_col,
    _TERMINAL_STRIP_TEMPLATE_LAYOUT,
    _TERMINAL_STRIP_TEMPLATE_VERSION,
    _validate_terminal_strip_template_counts,
    ui_font_to_wssl_size,
)


_FUSE_STRIP_WSSL_SCALE = 18.18181818181818
_FUSE_STRIP_Y_SIZE = 363.6363636363636
FUSE_STRIP_DATA_UI_FONT_SIZE = 10
FUSE_STRIP_LABEL_UI_FONT_SIZE = 7


_FUSE_STRIP_TEMPLATE_METADATA = r"""<?xml version="1.0" encoding="UTF-8"?>

<MetaData>

   <metadata projectType="UserProject">

      <description>Fuse Strip</description>

      <customerName></customerName>

      <OrderNumber></OrderNumber>

      <customerNumber></customerNumber>

      <plantNumber></plantNumber>

      <creator></creator>

      <auditor></auditor>

      <auditTime>null</auditTime>

      <templateID>2100872</templateID>

      <savedWithAppVersion>4.9.5.2</savedWithAppVersion>

      <workDirection>HORIZONTAL</workDirection>

      <creationTime>2026-05-25T10:51:24</creationTime>

      <ModificationTime>2026-05-25T13:12:22</ModificationTime>

      <printTime>null</printTime>

   </metadata>

</MetaData>

"""


def build_fuse_strip_wssl_filename(project_number: str | None) -> str:
    """Build the Fuse Strip WSSL filename."""
    project_prefix = project_number or "1"
    return f"{project_prefix}_Fuse Strip.wssl"


def _fuse_strip_wssl_width(space: float) -> float:
    """Convert one Fuse Strip Space value to WSSL layout units."""
    return space * _FUSE_STRIP_WSSL_SCALE


def _derive_fuse_strip_row_kind(row: dict[str, Any], text: str) -> str:
    """Resolve Fuse Strip row kind from explicit kind first, then text fallback."""
    row_kind = row.get("kind")
    if row_kind:
        return str(row_kind)
    normalized_text = text.strip().upper()
    if text == "":
        return "blank"
    if normalized_text in {"24VDC", "230VAC"}:
        return "generated_label"
    return "real_data"


def _normalize_fuse_strip_wssl_rows(strip_rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Normalize real Component Marking Fuse Strip rows for WSSL generation."""
    normalized_rows: list[dict[str, Any]] = []
    source_rows = list(strip_rows or [])
    row_index = 0
    while row_index < len(source_rows):
        row = source_rows[row_index]
        text = str(row.get("Text") or "")
        if text.strip().upper() == "STOP":
            row_index += 1
            continue
        space = _safe_terminal_strip_space(row.get("Space"))
        kind = _derive_fuse_strip_row_kind(row, text)
        next_row = source_rows[row_index + 1] if row_index + 1 < len(source_rows) else None
        if kind in {"group_label", "generated_label", "section_label"} and text not in {"24VDC", "230VAC"} and next_row is not None:
            next_text = str(next_row.get("Text") or "")
            if next_text in {"24VDC", "230VAC"}:
                normalized_rows.append(
                    {
                        "space": space,
                        "text": f"+{text.lstrip('+')} {next_text}",
                        "kind": "group_label",
                    }
                )
                row_index += 2
                continue
        normalized_rows.append(
            {
                "space": space,
                "text": text,
                "kind": kind,
            }
        )
        row_index += 1
    return normalized_rows


def _fuse_strip_component_style(text: str, kind: str | None = None) -> WsslComponentStyle:
    """Resolve Fuse Strip WSSL style for fuse data and generated labels."""
    normalized_text = text.strip().upper()
    is_generated = normalized_text in {"24VDC", "230VAC"} or kind in {
        "cabinet_label",
        "generated_label",
        "group_header",
        "group_label",
        "header",
        "section_label",
    }
    if is_generated:
        return WsslComponentStyle(
            font="Arial",
            font_size=ui_font_to_wssl_size(FUSE_STRIP_LABEL_UI_FONT_SIZE),
            bold=False,
            text_stretching_factor=1.0,
        )
    return WsslComponentStyle(
        font="Arial",
        font_size=ui_font_to_wssl_size(FUSE_STRIP_DATA_UI_FONT_SIZE),
        bold=True,
        text_stretching_factor=1.0,
    )


def _apply_fuse_strip_row_to_text_component(
    text_component: ET.Element,
    row: dict[str, Any],
) -> None:
    """Apply one normalized Fuse Strip row to a nested WagoTextComponent."""
    style = _fuse_strip_component_style(str(row["text"]), str(row["kind"]))
    text_component.set("text", str(row["text"]))
    text_component.set("identifier", str(uuid.uuid4()))
    text_component.set("font", style.font)
    text_component.set("fontSize", _format_wssl_float(style.font_size))
    text_component.set("textSize", _format_wssl_float(style.font_size))
    text_component.set("bold", str(style.bold).lower())
    text_component.set("contentRotation", _FUSE_STRIP_CONTENT_ROTATION)
    text_component.set("textStretchingFactorStr", str(style.text_stretching_factor))


def _set_fuse_strip_cell_geometry(
    grid_cell: ET.Element,
    row: dict[str, Any],
    goal_pos_x: float,
) -> None:
    """Update one nested Fuse Strip GridCell and its text component to row width."""
    width = _fuse_strip_wssl_width(float(row["space"]))
    grid_cell.set("goalPosX", _format_wssl_float(goal_pos_x))
    grid_cell.set("goalWidth", _format_wssl_float(width))
    grid_cell.set("goalHeight", _format_wssl_float(_FUSE_STRIP_Y_SIZE))
    text_component = grid_cell.find("./childList/WagoTextComponent")
    if text_component is None:
        raise ValueError("Fuse Strip WSSL nested GridCell missing WagoTextComponent")
    text_component.set("xSize", _format_wssl_float(width))
    text_component.set("ySize", _format_wssl_float(_FUSE_STRIP_Y_SIZE))
    _apply_fuse_strip_row_to_text_component(text_component, row)


def _set_fuse_strip_grid_group_geometry(
    grid: ET.Element,
    x_pos: float,
    content_width: float,
    endplate_width: float,
) -> None:
    """Update one Fuse Strip Grid wrapper dimensions while preserving template nesting."""
    grid.set("xPos", _format_wssl_float(x_pos))
    grid.set("xSize", _format_wssl_float(content_width))
    grid.set("ySize", _format_wssl_float(_FUSE_STRIP_Y_SIZE))
    grid.set("contentRotation", _FUSE_STRIP_CONTENT_ROTATION)
    grid.set("endplateWidthStr", _format_wssl_float(endplate_width))
    grid.set("showEndplateStr", "true" if endplate_width > 0 else "false")

    grid_endplate = _terminal_strip_grid_endplate(grid)
    grid_endplate.set("xPos", _format_wssl_float(content_width))
    grid_endplate.set("xSize", _format_wssl_float(endplate_width))
    grid_endplate.set("ySize", _format_wssl_float(_FUSE_STRIP_Y_SIZE))
    grid_endplate.set("isShowBorder", "true" if endplate_width > 0 else "false")

    outer_grid_row_col = _terminal_strip_outer_grid_row_col(grid)
    outer_grid_row_col.set("xSize", _format_wssl_float(content_width))
    outer_grid_row_col.set("ySize", _format_wssl_float(_FUSE_STRIP_Y_SIZE))
    outer_grid_row_col.set("contentRotation", _FUSE_STRIP_CONTENT_ROTATION)

    outer_grid_cell = _terminal_strip_outer_grid_cell(grid)
    outer_grid_cell.set("goalWidth", _format_wssl_float(content_width))
    outer_grid_cell.set("goalHeight", _format_wssl_float(_FUSE_STRIP_Y_SIZE))

    grid_row_col = _terminal_strip_grid_row_col(grid)
    grid_row_col.set("xSize", _format_wssl_float(content_width))
    grid_row_col.set("ySize", _format_wssl_float(_FUSE_STRIP_Y_SIZE))
    grid_row_col.set("contentRotation", _FUSE_STRIP_CONTENT_ROTATION)


def _build_fuse_strip_group_grid(
    grid_template: ET.Element,
    cell_template: ET.Element,
    group_rows: list[dict[str, Any]],
    x_pos: float,
    endplate_width: float,
) -> ET.Element:
    """Clone one full template Grid and fill it with the Fuse Strip group's cells."""
    if not group_rows:
        raise ValueError("Fuse Strip WSSL cannot build an empty Grid group")

    cloned_grid = copy.deepcopy(grid_template)
    _refresh_identifiers(cloned_grid)
    row_col_child_list = _terminal_strip_grid_row_col_child_list(cloned_grid)
    for child in list(row_col_child_list):
        row_col_child_list.remove(child)

    next_cell_x_pos = 0.0
    for row in group_rows:
        cloned_cell = copy.deepcopy(cell_template)
        _refresh_identifiers(cloned_cell)
        _set_fuse_strip_cell_geometry(cloned_cell, row, next_cell_x_pos)
        row_col_child_list.append(cloned_cell)
        next_cell_x_pos += _fuse_strip_wssl_width(float(row["space"]))

    _set_fuse_strip_grid_group_geometry(
        cloned_grid,
        x_pos=x_pos,
        content_width=next_cell_x_pos,
        endplate_width=endplate_width,
    )
    return cloned_grid


def _replace_fuse_strip_grids_from_rows(
    strip: ET.Element,
    component_list: ET.Element,
    normalized_rows: list[dict[str, Any]],
) -> list[ET.Element]:
    """Replace componentList with Fuse Strip Grid groups; blank rows become endplates."""
    grid_template = _first_terminal_strip_grid_template(component_list)
    cell_template = _first_terminal_strip_cell_template(component_list)
    for child in list(component_list):
        component_list.remove(child)

    generated_grids: list[ET.Element] = []
    current_group_rows: list[dict[str, Any]] = []
    current_group_x_pos = 0.0
    next_x_pos = 0.0
    for row in normalized_rows:
        row_width = _fuse_strip_wssl_width(float(row["space"]))
        if row["text"] == "":
            if current_group_rows:
                cloned_grid = _build_fuse_strip_group_grid(
                    grid_template,
                    cell_template,
                    current_group_rows,
                    current_group_x_pos,
                    row_width,
                )
                component_list.append(cloned_grid)
                generated_grids.append(cloned_grid)
                current_group_rows = []
            next_x_pos += row_width
            current_group_x_pos = next_x_pos
            continue

        if not current_group_rows:
            current_group_x_pos = next_x_pos
        current_group_rows.append(row)
        next_x_pos += row_width

    if current_group_rows:
        cloned_grid = _build_fuse_strip_group_grid(
            grid_template,
            cell_template,
            current_group_rows,
            current_group_x_pos,
            0.0,
        )
        component_list.append(cloned_grid)
        generated_grids.append(cloned_grid)

    strip.set("xSize", _format_wssl_float(next_x_pos))
    strip.set("ySize", _format_wssl_float(_FUSE_STRIP_Y_SIZE))
    return generated_grids


def _fuse_strip_generated_item_preview(normalized_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return developer preview rows showing generated Fuse Strip item type and width."""
    return [
        {
            "Space": row["space"],
            "Text": row["text"],
            "width": _fuse_strip_wssl_width(float(row["space"])),
            "type": "ENDPLATE" if row["text"] == "" else "TEXT",
        }
        for row in normalized_rows[:20]
    ]


def _fuse_strip_generation_debug_messages(
    normalized_rows: list[dict[str, Any]],
    generated_grid_count: int,
    strip_x_size: float,
) -> list[str]:
    """Build developer debug messages for Fuse Strip WSSL generation."""
    blank_count = sum(1 for row in normalized_rows if row["text"] == "")
    text_count = len(normalized_rows) - blank_count
    return [
        "Fuse Strip WSSL generated",
        f"Fuse Strip WSSL input row count = {len(normalized_rows)}",
        f"Fuse Strip WSSL non-empty text cell count = {text_count}",
        f"Fuse Strip WSSL blank/endplate count = {blank_count}",
        f"Fuse Strip WSSL generated Grid count = {generated_grid_count}",
        "Fuse Strip WSSL first 20 generated items -> "
        + repr(_fuse_strip_generated_item_preview(normalized_rows)),
        f"Fuse Strip WSSL total calculated strip xSize = {strip_x_size}",
        "Fuse Strip WSSL value source validation -> text=row['Text'], width=row['Space'] * WSSL_WIDTH_SCALE",
        "Fuse Strip WSSL blank/endplate validation -> Text == '' creates ENDPLATE; no text component",
        "Fuse Strip WSSL width validation -> no fuse-name width mapping; wider cells come only from wider input Space",
    ]


def _validate_fuse_strip_generated_layout(
    strip: ET.Element,
    component_list: ET.Element,
    normalized_rows: list[dict[str, Any]],
    generated_grids: list[ET.Element],
) -> None:
    """Validate Fuse Strip WSSL output was generated only from row Space/Text semantics."""
    text_components = [
        text_component
        for grid in generated_grids
        for text_component in _grid_wago_text_components(grid)
    ]
    expected_text_count = sum(1 for row in normalized_rows if row["text"] != "")
    generated_text_count = len([node for node in text_components if node.get("text", "") != ""])
    if generated_text_count != expected_text_count:
        raise ValueError(
            "Fuse Strip WSSL generated text count does not match non-empty input rows: "
            + f"generated={generated_text_count}, rows={expected_text_count}"
        )
    if any(node.get("text", "") == "" for node in text_components):
        raise ValueError("Fuse Strip WSSL blank row generated an empty WagoTextComponent")
    if component_list.findall("WagoTextComponent") or component_list.findall("./Grid/childList/WagoTextComponent"):
        raise ValueError("Fuse Strip WSSL contains direct WagoTextComponent under componentList/Grid")
    expected_x_size = sum(_fuse_strip_wssl_width(float(row["space"])) for row in normalized_rows)
    generated_x_size = _float_attr(strip, "xSize")
    if abs(generated_x_size - expected_x_size) > 0.001:
        raise ValueError(
            "Fuse Strip WSSL strip xSize does not match sum(Space) * WSSL_WIDTH_SCALE: "
            + f"generated={generated_x_size}, expected={expected_x_size}"
        )


def build_fuse_strip_wssl_debug_messages(strip_rows: list[dict[str, Any]] | None = None) -> list[str]:
    """Build developer debug messages without generating the Fuse Strip WSSL archive."""
    normalized_rows = _normalize_fuse_strip_wssl_rows(strip_rows)
    if not normalized_rows:
        return ["Fuse Strip WSSL skipped because no real Fuse Strip rows were available"]
    return _fuse_strip_generation_debug_messages(
        normalized_rows,
        generated_grid_count=_count_terminal_strip_grid_groups(normalized_rows),
        strip_x_size=sum(_fuse_strip_wssl_width(float(row["space"])) for row in normalized_rows),
    )


def _build_fuse_strip_layout(strip_rows: list[dict[str, Any]] | None = None) -> str:
    """Build Fuse Strip WSSL strip.layout from Fuse Strip Space/Text rows."""
    root = ET.fromstring(_TERMINAL_STRIP_TEMPLATE_LAYOUT)
    _validate_terminal_strip_template_counts(root)
    component_list = root.find(".//componentList")
    if component_list is None:
        raise ValueError("Fuse Strip WSSL template missing componentList")
    strip = root.find(".//strip")
    if strip is None:
        raise ValueError("Fuse Strip WSSL template missing strip node")

    normalized_rows = _normalize_fuse_strip_wssl_rows(strip_rows)
    generated_grids = _replace_fuse_strip_grids_from_rows(strip, component_list, normalized_rows)
    text_components = [
        text_component
        for grid in generated_grids
        for text_component in _grid_wago_text_components(grid)
    ]
    _validate_fuse_strip_generated_layout(strip, component_list, normalized_rows, generated_grids)
    strip_x_size = sum(_fuse_strip_wssl_width(float(row["space"])) for row in normalized_rows)
    for message in _fuse_strip_generation_debug_messages(
        normalized_rows,
        generated_grid_count=len(generated_grids),
        strip_x_size=strip_x_size,
    ):
        print(message)
    if any(text_component.get("contentRotation") != _FUSE_STRIP_CONTENT_ROTATION for text_component in text_components):
        raise ValueError("Fuse Strip WSSL generated text component has wrong contentRotation")

    ET.indent(root, space="   ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def build_fuse_strip_wssl_bytes(strip_rows: list[dict[str, Any]] | None = None) -> bytes:
    """Build a Fuse Strip WSSL archive from Component Marking Fuse Strip rows."""
    return _build_wssl_zip_bytes(
        [
            WsslTemplateFile("version.info", _TERMINAL_STRIP_TEMPLATE_VERSION.encode("utf-8")),
            WsslTemplateFile("strip.layout", _build_fuse_strip_layout(strip_rows).encode("utf-8")),
            WsslTemplateFile("meta.data", _FUSE_STRIP_TEMPLATE_METADATA.encode("utf-8")),
            WsslTemplateFile("table.config", _FUSE_STRIP_TEMPLATE_TABLE_CONFIG.encode("utf-8")),
            WsslTemplateFile("import.config", _FUSE_STRIP_TEMPLATE_IMPORT_CONFIG.encode("utf-8")),
        ]
    )
