from __future__ import annotations

import copy
import pprint
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
    _format_wssl_float,
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


_TERMINAL_STRIP_WSSL_SCALE = 18.18181818181818
TERMINAL_STRIP_DATA_UI_FONT_SIZE = 10
TERMINAL_STRIP_LABEL_UI_FONT_SIZE = 7
_TERMINAL_STRIP_ALLOWED_TEXT_ATTR_CHANGES = {
    "text",
    "identifier",
    "xSize",
    "font",
    "fontSize",
    "textSize",
    "textStretchingFactorStr",
    "bold",
}
_TERMINAL_STRIP_ALIGNMENT_ATTRS = {
    "xPos",
    "yPos",
    "tlbrPadding",
    "textAlignmentStr",
    "nodeAligmentStr",
    "lineSpacingStr",
    "contentRotation",
    "contentRotationAnchor",
}

_TERMINAL_STRIP_TEMPLATE_METADATA = r"""<?xml version="1.0" encoding="UTF-8"?>

<MetaData>

   <metadata projectType="UserProject">

      <description></description>

      <customerName></customerName>

      <OrderNumber></OrderNumber>

      <customerNumber></customerNumber>

      <plantNumber></plantNumber>

      <creator></creator>

      <auditor></auditor>

      <auditTime>null</auditTime>

      <templateID>20090110</templateID>

      <savedWithAppVersion>4.9.5.2</savedWithAppVersion>

      <workDirection>HORIZONTAL</workDirection>

      <creationTime>2026-05-25T10:51:24</creationTime>

      <ModificationTime>2026-05-25T13:12:22</ModificationTime>

      <printTime>null</printTime>

   </metadata>

</MetaData>

"""

_TERMINAL_STRIP_TEMPLATE_TABLE_CONFIG = r"""<?xml version="1.0" encoding="UTF-8"?>

<table-config>

   <file-path>Y:\JE-ELKAS\21.0 Litauen\ADVANCOR\2605-078\2605-078_Markings.xlsx</file-path>

   <sheetName>Terminal markings</sheetName>

   <firstRowIsHeader>false</firstRowIsHeader>

   <column-separator>COMMA</column-separator>

   <row-separator>NEW_LINE</row-separator>

</table-config>

"""

_TERMINAL_STRIP_TEMPLATE_IMPORT_CONFIG = r"""<?xml version="1.0" encoding="UTF-8"?>

<grid-import-config ignore-empty-rows="false" ignore-empty-cells="false" cut-marker="NONE" default-cell-width="5.2" default-end-plate-width="0.8" text-rotation="270.0" header-count="0" terminal-row-count="1" header-position="TOP" grid-labeling-order="TOP_BOTTOM">

   <data-mapping>

      <mappings>

         <mapping>

            <meta-target identifier="Text"/>

            <associated-data startRowIndex="2" endRowIndex="107" startColumnIndex="7" endColumnIndex="7" classifier="data-range-discriminator"/>

         </mapping>

         <mapping>

            <meta-target identifier="Width"/>

            <associated-data startRowIndex="2" endRowIndex="107" startColumnIndex="6" endColumnIndex="6" classifier="data-range-discriminator"/>

         </mapping>

      </mappings>

      <sequences/>

   </data-mapping>

</grid-import-config>

"""


def build_terminal_strip_wssl_filename(project_number: str | None) -> str:
    """Build the Terminal Strip WSSL filename."""
    project_prefix = project_number or "1"
    return f"{project_prefix}_Terminal Strip.wssl"


def _resolve_terminal_strip_stretch(text: str) -> float:
    """Resolve demo Terminal Strip WSSL text stretching."""
    text_length = len(text)
    if text_length <= 5:
        return 1.0
    if text_length == 6:
        return 0.9
    return 0.7


def _terminal_strip_component_style(text: str, kind: str | None = None) -> WsslComponentStyle:
    """Resolve Terminal Strip WSSL style for real data and generated labels."""
    is_generated = kind in {
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
            font_size=ui_font_to_wssl_size(TERMINAL_STRIP_LABEL_UI_FONT_SIZE),
            bold=False,
            text_stretching_factor=1.0,
        )
    return WsslComponentStyle(
        font="Arial",
        font_size=ui_font_to_wssl_size(TERMINAL_STRIP_DATA_UI_FONT_SIZE),
        bold=True,
        text_stretching_factor=_resolve_terminal_strip_stretch(text),
    )


def _validate_terminal_strip_component_list(component_list: ET.Element) -> None:
    """Validate Terminal Strip componentList preserves real Grid structure."""
    grids = component_list.findall("Grid")
    if not grids:
        raise ValueError("No Grid blocks generated")
    if component_list.findall("WagoTextComponent"):
        raise ValueError("Terminal Strip componentList contains flat WagoTextComponent nodes")
    for grid in grids:
        if grid.find(".//GridCell/childList/WagoTextComponent") is None:
            raise ValueError("Generated Grid missing WagoTextComponent")


def _first_populated_wago_text_component(component_list: ET.Element) -> ET.Element:
    """Return the first template text component that is actually carrying label text."""
    for text_component in component_list.findall(".//GridCell/childList/WagoTextComponent"):
        if text_component.get("text", "") != "":
            return text_component
    raise ValueError("Terminal Strip WSSL template missing populated WagoTextComponent")


def _format_terminal_strip_attr_diff(
    original_attrs: dict[str, str],
    generated_attrs: dict[str, str],
) -> dict[str, tuple[str | None, str | None]]:
    """Return all attribute differences between original and generated text nodes."""
    attr_names = sorted(set(original_attrs) | set(generated_attrs))
    return {
        attr_name: (original_attrs.get(attr_name), generated_attrs.get(attr_name))
        for attr_name in attr_names
        if original_attrs.get(attr_name) != generated_attrs.get(attr_name)
    }


def _dump_terminal_strip_text_diagnostics(
    original_attrs: dict[str, str],
    generated_component: ET.Element,
) -> None:
    """Dump developer diagnostics for the first rendered WSSL text component."""
    generated_attrs = dict(generated_component.attrib)
    attr_diff = _format_terminal_strip_attr_diff(original_attrs, generated_attrs)
    unexpected_diff = {
        attr_name: values
        for attr_name, values in attr_diff.items()
        if attr_name not in _TERMINAL_STRIP_ALLOWED_TEXT_ATTR_CHANGES
    }
    alignment_diff = {
        attr_name: values
        for attr_name, values in attr_diff.items()
        if attr_name in _TERMINAL_STRIP_ALIGNMENT_ATTRS
        or attr_name.startswith("transform")
        or attr_name.startswith("contentRotation")
    }
    diagnostics = {
        "original_first_populated_template_label": original_attrs,
        "generated_first_label": generated_attrs,
        "all_attribute_differences": attr_diff,
        "unexpected_attribute_differences": unexpected_diff,
        "alignment_attribute_differences": alignment_diff,
    }
    print("terminal strip WSSL text diagnostics:")
    pprint.pprint(diagnostics, sort_dicts=True)


def _terminal_strip_wssl_width(space: float) -> float:
    """Convert one Markings Space value to WSSL layout units."""
    return space * _TERMINAL_STRIP_WSSL_SCALE


def _derive_terminal_strip_row_kind(row: dict[str, Any], text: str) -> str:
    """Resolve a normalized WSSL row kind without changing row order or content."""
    row_kind = row.get("kind")
    if row_kind:
        return str(row_kind)
    if text == "":
        return "blank"
    return "real_data"


def _normalize_terminal_strip_wssl_rows(strip_rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Normalize real WAGO strip rows for Terminal Strip WSSL generation."""
    normalized_rows: list[dict[str, Any]] = []
    for row in strip_rows or []:
        text = str(row.get("Text") or "")
        space = _safe_terminal_strip_space(row.get("Space"))
        normalized_rows.append(
            {
                "space": space,
                "text": text,
                "kind": _derive_terminal_strip_row_kind(row, text),
            }
        )
    return normalized_rows


def build_terminal_strip_wssl_debug_messages(strip_rows: list[dict[str, Any]] | None = None) -> list[str]:
    """Build developer debug messages for Terminal Strip WSSL row plumbing."""
    normalized_rows = _normalize_terminal_strip_wssl_rows(strip_rows)
    if not normalized_rows:
        return ["Terminal Strip WSSL received no strip_rows; generated layout will be empty"]

    blank_row_count = sum(1 for row in normalized_rows if row["text"] == "")
    non_empty_label_count = len(normalized_rows) - blank_row_count
    preview_rows = [
        {
            "Space": row["space"],
            "Text": row["text"],
            "Generated width": _terminal_strip_wssl_width(float(row["space"])),
            "Generated type": "ENDPLATE" if row["text"] == "" else "TEXT",
        }
        for row in normalized_rows[:20]
    ]
    messages = [
        f"Terminal Strip WSSL total strip_rows count = {len(normalized_rows)}",
        f"Terminal Strip WSSL total generated Grid count = {_count_terminal_strip_grid_groups(normalized_rows)}",
        f"Terminal Strip WSSL total generated text cells = {non_empty_label_count}",
        f"Terminal Strip WSSL total generated endplates = {blank_row_count}",
        "Terminal Strip WSSL first 20 generated items -> " + repr(preview_rows),
        "Terminal Strip WSSL geometry source: strip_rows Space/Text only; width = Space * 18.18181818181818",
    ]
    return messages


def _terminal_strip_rows_for_layout(strip_rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Return normalized real rows only."""
    return _normalize_terminal_strip_wssl_rows(strip_rows)


def _apply_terminal_strip_row_to_text_component(
    text_component: ET.Element,
    row: dict[str, Any],
) -> None:
    """Apply one normalized Terminal Strip row to a nested WagoTextComponent."""
    style = _terminal_strip_component_style(str(row["text"]), str(row["kind"]))
    text_component.set("text", str(row["text"]))
    text_component.set("identifier", str(uuid.uuid4()))
    text_component.set("font", style.font)
    text_component.set("fontSize", _format_wssl_float(style.font_size))
    text_component.set("textSize", _format_wssl_float(style.font_size))
    text_component.set("textStretchingFactorStr", str(style.text_stretching_factor))
    text_component.set("bold", str(style.bold).lower())


def _set_terminal_strip_cell_geometry(
    grid_cell: ET.Element,
    row: dict[str, Any],
    goal_pos_x: float,
) -> None:
    """Update one nested terminal GridCell and its text component to row width."""
    width = _terminal_strip_wssl_width(float(row["space"]))
    grid_cell.set("goalPosX", _format_wssl_float(goal_pos_x))
    grid_cell.set("goalWidth", _format_wssl_float(width))
    text_component = grid_cell.find("./childList/WagoTextComponent")
    if text_component is None:
        raise ValueError("Terminal Strip WSSL nested GridCell missing WagoTextComponent")
    text_component.set("xSize", _format_wssl_float(width))
    _apply_terminal_strip_row_to_text_component(text_component, row)


def _set_terminal_strip_grid_group_geometry(
    grid: ET.Element,
    x_pos: float,
    content_width: float,
    endplate_width: float,
) -> None:
    """Update the top-level Grid wrapper dimensions while preserving template nesting."""
    grid.set("xPos", _format_wssl_float(x_pos))
    grid.set("xSize", _format_wssl_float(content_width))
    grid.set("endplateWidthStr", _format_wssl_float(endplate_width))
    grid.set("showEndplateStr", "true" if endplate_width > 0 else "false")

    grid_endplate = _terminal_strip_grid_endplate(grid)
    grid_endplate.set("xPos", _format_wssl_float(content_width))
    grid_endplate.set("xSize", _format_wssl_float(endplate_width))
    grid_endplate.set("isShowBorder", "true" if endplate_width > 0 else "false")

    outer_grid_row_col = _terminal_strip_outer_grid_row_col(grid)
    outer_grid_row_col.set("xSize", _format_wssl_float(content_width))

    outer_grid_cell = _terminal_strip_outer_grid_cell(grid)
    outer_grid_cell.set("goalWidth", _format_wssl_float(content_width))

    grid_row_col = _terminal_strip_grid_row_col(grid)
    grid_row_col.set("xSize", _format_wssl_float(content_width))


def _build_terminal_strip_group_grid(
    grid_template: ET.Element,
    cell_template: ET.Element,
    group_rows: list[dict[str, Any]],
    x_pos: float,
    endplate_width: float,
) -> ET.Element:
    """Clone one full template Grid and fill it with the group's non-blank cells."""
    if not group_rows:
        raise ValueError("Terminal Strip WSSL cannot build an empty Grid group")

    cloned_grid = copy.deepcopy(grid_template)
    _refresh_identifiers(cloned_grid)
    row_col_child_list = _terminal_strip_grid_row_col_child_list(cloned_grid)
    for child in list(row_col_child_list):
        row_col_child_list.remove(child)

    next_cell_x_pos = 0.0
    for row in group_rows:
        cloned_cell = copy.deepcopy(cell_template)
        _refresh_identifiers(cloned_cell)
        _set_terminal_strip_cell_geometry(cloned_cell, row, next_cell_x_pos)
        row_col_child_list.append(cloned_cell)
        next_cell_x_pos += _terminal_strip_wssl_width(float(row["space"]))

    _set_terminal_strip_grid_group_geometry(
        cloned_grid,
        x_pos=x_pos,
        content_width=next_cell_x_pos,
        endplate_width=endplate_width,
    )
    return cloned_grid


def _replace_terminal_strip_grids_from_rows(
    strip: ET.Element,
    component_list: ET.Element,
    normalized_rows: list[dict[str, Any]],
) -> list[ET.Element]:
    """Replace componentList with grouped Grid blocks; blank rows become endplates."""
    grid_template = _first_terminal_strip_grid_template(component_list)
    cell_template = _first_terminal_strip_cell_template(component_list)
    for child in list(component_list):
        component_list.remove(child)

    generated_grids: list[ET.Element] = []
    current_group_rows: list[dict[str, Any]] = []
    current_group_x_pos = 0.0
    next_x_pos = 0.0
    for row in normalized_rows:
        row_width = _terminal_strip_wssl_width(float(row["space"]))
        if row["text"] == "":
            if current_group_rows:
                cloned_grid = _build_terminal_strip_group_grid(
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
        cloned_grid = _build_terminal_strip_group_grid(
            grid_template,
            cell_template,
            current_group_rows,
            current_group_x_pos,
            0.0,
        )
        component_list.append(cloned_grid)
        generated_grids.append(cloned_grid)

    strip.set("xSize", _format_wssl_float(next_x_pos))
    return generated_grids


def _terminal_strip_generated_item_preview(normalized_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return developer preview rows showing generated item type and width."""
    return [
        {
            "Space": row["space"],
            "Text": row["text"],
            "Generated width": _terminal_strip_wssl_width(float(row["space"])),
            "Generated type": "ENDPLATE" if row["text"] == "" else "TEXT",
        }
        for row in normalized_rows[:20]
    ]


def _print_terminal_strip_generation_diagnostics(
    normalized_rows: list[dict[str, Any]],
    generated_grids: list[ET.Element],
    text_components: list[ET.Element],
) -> None:
    """Print developer verification for generated Terminal Strip WSSL."""
    generated_text_count = len([node for node in text_components if node.get("text")])
    generated_endplate_count = sum(1 for row in normalized_rows if row["text"] == "")
    print("Terminal Strip WSSL developer verification:")
    print(f"  total strip_rows count = {len(normalized_rows)}")
    print(f"  total generated Grid count = {len(generated_grids)}")
    print(f"  total generated text cells = {generated_text_count}")
    print(f"  total generated endplates = {generated_endplate_count}")
    print("  first 20 generated items:")
    pprint.pprint(_terminal_strip_generated_item_preview(normalized_rows), sort_dicts=False)
    print("  no hardcoded texts: generated text values are copied from strip_rows Text")
    print("  no hardcoded cell count: generated counts are derived from strip_rows")
    print(
        "  no hardcoded widths except conversion factor: "
        + f"width = strip_rows Space * {_TERMINAL_STRIP_WSSL_SCALE}"
    )
    print("  all generated geometry comes from strip_rows Space values")


def _build_terminal_strip_layout(strip_rows: list[dict[str, Any]] | None = None) -> str:
    """Mutate the existing Terminal Strip template text nodes in place."""
    root = ET.fromstring(_TERMINAL_STRIP_TEMPLATE_LAYOUT)
    _validate_terminal_strip_template_counts(root)
    component_list = root.find(".//componentList")
    if component_list is None:
        raise ValueError("Terminal Strip WSSL template missing componentList")

    _validate_terminal_strip_component_list(component_list)
    original_first_label_attrs = dict(_first_populated_wago_text_component(component_list).attrib)
    strip = root.find(".//strip")
    if strip is None:
        raise ValueError("Terminal Strip WSSL template missing strip node")
    normalized_rows = _terminal_strip_rows_for_layout(strip_rows)
    generated_grids = _replace_terminal_strip_grids_from_rows(strip, component_list, normalized_rows)
    text_components = [
        text_component
        for grid in generated_grids
        for text_component in _grid_wago_text_components(grid)
    ]
    _print_terminal_strip_generation_diagnostics(normalized_rows, generated_grids, text_components)
    if text_components:
        _dump_terminal_strip_text_diagnostics(original_first_label_attrs, text_components[0])

    ET.indent(root, space="   ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def build_terminal_strip_wssl_bytes(strip_rows: list[dict[str, Any]] | None = None) -> bytes:
    """Build a Terminal Strip WSSL archive using Grid-based template mutation."""
    return _build_wssl_zip_bytes(
        [
            WsslTemplateFile("version.info", _TERMINAL_STRIP_TEMPLATE_VERSION.encode("utf-8")),
            WsslTemplateFile("strip.layout", _build_terminal_strip_layout(strip_rows).encode("utf-8")),
            WsslTemplateFile("meta.data", _TERMINAL_STRIP_TEMPLATE_METADATA.encode("utf-8")),
            WsslTemplateFile("table.config", _TERMINAL_STRIP_TEMPLATE_TABLE_CONFIG.encode("utf-8")),
            WsslTemplateFile("import.config", _TERMINAL_STRIP_TEMPLATE_IMPORT_CONFIG.encode("utf-8")),
        ]
    )
