from __future__ import annotations

import copy
from typing import Any
import uuid
import xml.etree.ElementTree as ET

from .shared_wssl import (
    WsslComponentStyle,
    WsslTemplateFile,
    _build_wssl_zip_bytes,
    _format_wssl_float,
    _TERMINAL_STRIP_TEMPLATE_VERSION,
    ui_font_to_wssl_size,
)


FUSES_2009_DATA_UI_FONT_SIZE = 10
FUSES_2009_LABEL_UI_FONT_SIZE = 7
FUSES_2009_FIRST_X_POS = 10.622236114940005
FUSES_2009_X_STEP = 94.54545454545455
FUSES_2009_COMPONENT_X_SIZE = 72.37651138670707
FUSES_2009_RIGHT_MARGIN = 10.0
_FUSES_2009_STRIP_Y_SIZE = 174.54545454545453
_FUSES_2009_COMPONENT_Y_POS = 14.544026374816895
_FUSES_2009_COMPONENT_Y_SIZE = 145.44900608062744
_FUSES_2009_CONTENT_ROTATION = "270.0"
_FUSES_2009_TEXT_STRETCH = 0.5


_FUSES_2009_TEMPLATE_METADATA = r"""<?xml version="1.0" encoding="UTF-8"?>

<MetaData>

   <metadata projectType="UserProject">

      <description>FUSES</description>

      <customerName></customerName>

      <OrderNumber></OrderNumber>

      <customerNumber></customerNumber>

      <plantNumber></plantNumber>

      <creator></creator>

      <auditor></auditor>

      <auditTime>null</auditTime>

      <templateID>20090115</templateID>

      <savedWithAppVersion>4.9.5.2</savedWithAppVersion>

      <workDirection>HORIZONTAL</workDirection>

      <creationTime>2026-05-25T10:51:24</creationTime>

      <ModificationTime>2026-05-25T13:12:22</ModificationTime>

      <printTime>null</printTime>

   </metadata>

</MetaData>

"""

_FUSES_2009_TEMPLATE_TABLE_CONFIG = r"""<?xml version="1.0" encoding="UTF-8"?>

<table-config>

   <file-path>Y:\JE-ELKAS\21.0 Litauen\ADVANCOR\2605-078\2605-078_Markings.xlsx</file-path>

   <sheetName>Component markings</sheetName>

   <firstRowIsHeader>false</firstRowIsHeader>

   <column-separator>COMMA</column-separator>

   <row-separator>NEW_LINE</row-separator>

</table-config>

"""

_FUSES_2009_TEMPLATE_IMPORT_CONFIG = r"""<?xml version="1.0" encoding="UTF-8"?>

<import-config/>

"""

_FUSES_2009_TEMPLATE_LAYOUT = r"""<?xml version="1.0" encoding="UTF-8"?>

<Strip>

   <strip appVersion="4.9.5.2" xMinChildlessWidth="54.54545454545455" xSize="92.99874750164707" ySize="174.54545454545453" flowOn="false" stripMode="synchronized">

      <componentList>

         <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="10.622236114940005" xSize="72.37651138670707" yPos="14.544026374816895" ySize="145.44900608062744" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="d9646d25-1620-45b3-bc8e-f355d8e91c49" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="-9.621212121212121" nodeAligmentStr="CENTER" text="" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.5"/>

      </componentList>

   </strip>

</Strip>

"""


def build_fuses_2009_wssl_filename(project_number: str | None) -> str:
    """Build the Component Marking FUSES 2009-115 WSSL filename."""
    project_prefix = project_number or "1"
    return f"{project_prefix}_Fuses.wssl"


def _normalize_fuses_2009_text(text: str) -> str:
    """Normalize Component Marking FUSES block labels for Wago 2009-115."""
    stripped_text = text.strip()
    if stripped_text == "Fuses 24VDC":
        return "24VDC"
    if stripped_text == "Fuses 230VAC":
        return "230VAC"
    return stripped_text


def _normalize_fuses_2009_rows(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Normalize source Component Marking FUSES / Wago 2009-115 values."""
    normalized_rows: list[dict[str, Any]] = []
    for row in rows or []:
        text = _normalize_fuses_2009_text(str(row.get("Text") or ""))
        row_kind = str(row.get("kind") or "")
        kind = "blank"
        if row_kind in {"group_label", "generated_label", "section_label"}:
            kind = "group_label"
        elif row_kind in {"blank", "blank_separator"}:
            kind = "blank"
        elif text in {"24VDC", "230VAC"}:
            kind = "group_label"
        elif text != "":
            kind = "real_data"
        normalized_rows.append({"text": text, "kind": kind})
    return normalized_rows


def _fuses_2009_component_style(text: str, kind: str) -> WsslComponentStyle:
    """Resolve flat FUSES WSSL text style."""
    if kind == "group_label":
        return WsslComponentStyle(
            font="Arial",
            font_size=ui_font_to_wssl_size(FUSES_2009_LABEL_UI_FONT_SIZE),
            bold=False,
            text_stretching_factor=_FUSES_2009_TEXT_STRETCH,
        )
    if text == "":
        return WsslComponentStyle(
            font="Arial",
            font_size=ui_font_to_wssl_size(FUSES_2009_LABEL_UI_FONT_SIZE),
            bold=False,
            text_stretching_factor=_FUSES_2009_TEXT_STRETCH,
        )
    return WsslComponentStyle(
        font="Arial",
        font_size=ui_font_to_wssl_size(FUSES_2009_DATA_UI_FONT_SIZE),
        bold=True,
        text_stretching_factor=_FUSES_2009_TEXT_STRETCH,
    )


def _apply_fuses_2009_row_to_text_component(
    text_component: ET.Element,
    row: dict[str, Any],
    index: int,
) -> None:
    """Apply one FUSES 2009-115 source row to a cloned flat WagoTextComponent."""
    text = str(row["text"])
    style = _fuses_2009_component_style(text, str(row["kind"]))
    text_component.set("text", text)
    text_component.set("xPos", _format_wssl_float(FUSES_2009_FIRST_X_POS + index * FUSES_2009_X_STEP))
    text_component.set("xSize", _format_wssl_float(FUSES_2009_COMPONENT_X_SIZE))
    text_component.set("yPos", _format_wssl_float(_FUSES_2009_COMPONENT_Y_POS))
    text_component.set("ySize", _format_wssl_float(_FUSES_2009_COMPONENT_Y_SIZE))
    text_component.set("identifier", str(uuid.uuid4()))
    text_component.set("font", style.font)
    text_component.set("fontSize", _format_wssl_float(style.font_size))
    text_component.set("textSize", _format_wssl_float(style.font_size))
    text_component.set("bold", str(style.bold).lower())
    text_component.set("contentRotation", _FUSES_2009_CONTENT_ROTATION)
    text_component.set("textStretchingFactorStr", str(style.text_stretching_factor))


def _fuses_2009_generated_values_preview(normalized_rows: list[dict[str, Any]]) -> list[str]:
    """Return the first generated FUSES values for developer diagnostics."""
    return [str(row["text"]) for row in normalized_rows[:20]]


def _fuses_2009_strip_x_size(row_count: int) -> float:
    """Calculate flat FUSES 2009-115 strip width from generated component count."""
    if row_count <= 0:
        return FUSES_2009_RIGHT_MARGIN
    last_x_pos = FUSES_2009_FIRST_X_POS + (row_count - 1) * FUSES_2009_X_STEP
    return last_x_pos + FUSES_2009_COMPONENT_X_SIZE + FUSES_2009_RIGHT_MARGIN


def _fuses_2009_debug_messages(normalized_rows: list[dict[str, Any]], strip_x_size: float) -> list[str]:
    """Build developer debug messages for FUSES 2009-115 WSSL generation."""
    blank_count = sum(1 for row in normalized_rows if row["text"] == "")
    return [
        "FUSES 2009-115 WSSL generated",
        f"FUSES 2009-115 WSSL source row count = {len(normalized_rows)}",
        f"FUSES 2009-115 WSSL non-empty count = {len(normalized_rows) - blank_count}",
        f"FUSES 2009-115 WSSL blank count = {blank_count}",
        "FUSES 2009-115 WSSL first 20 generated values -> "
        + repr(_fuses_2009_generated_values_preview(normalized_rows)),
        f"FUSES 2009-115 WSSL strip xSize = {strip_x_size}",
    ]


def _validate_fuses_2009_layout(
    root: ET.Element,
    component_list: ET.Element,
    normalized_rows: list[dict[str, Any]],
) -> None:
    """Validate flat FUSES 2009-115 WSSL output structure and source-row fidelity."""
    if root.findall(".//Grid") or root.findall(".//GridCell") or root.findall(".//GridEndPlate"):
        raise ValueError("FUSES 2009-115 WSSL must not contain Grid/GridCell/GridEndPlate nodes")
    text_components = component_list.findall("./WagoTextComponent")
    if len(text_components) != len(normalized_rows):
        raise ValueError(
            "FUSES 2009-115 WSSL component count does not match source rows: "
            + f"components={len(text_components)}, rows={len(normalized_rows)}"
        )
    generated_values = [node.get("text", "") for node in text_components]
    source_values = [str(row["text"]) for row in normalized_rows]
    if generated_values != source_values:
        raise ValueError("FUSES 2009-115 WSSL generated values do not match normalized source row order")
    non_empty_values = [value for value in generated_values if value != ""]
    if non_empty_values and non_empty_values[0] == "Fuses 24VDC":
        raise ValueError("FUSES 2009-115 WSSL did not normalize Fuses 24VDC to 24VDC")


def build_fuses_2009_wssl_debug_messages(rows: list[dict[str, Any]] | None = None) -> list[str]:
    """Build developer debug messages without generating the FUSES WSSL archive."""
    normalized_rows = _normalize_fuses_2009_rows(rows)
    if not normalized_rows:
        return ["FUSES 2009-115 WSSL skipped because no source rows were available"]
    return _fuses_2009_debug_messages(normalized_rows, _fuses_2009_strip_x_size(len(normalized_rows)))


def _build_fuses_2009_layout(rows: list[dict[str, Any]] | None = None) -> str:
    """Build a flat Wago 2009-115 FUSES WSSL strip.layout from source rows."""
    root = ET.fromstring(_FUSES_2009_TEMPLATE_LAYOUT)
    strip = root.find(".//strip")
    if strip is None:
        raise ValueError("FUSES 2009-115 WSSL template missing strip node")
    component_list = strip.find("./componentList")
    if component_list is None:
        raise ValueError("FUSES 2009-115 WSSL template missing componentList")
    template_component = component_list.find("./WagoTextComponent")
    if template_component is None:
        raise ValueError("FUSES 2009-115 WSSL template missing WagoTextComponent")

    normalized_rows = _normalize_fuses_2009_rows(rows)
    for child in list(component_list):
        component_list.remove(child)

    for index, row in enumerate(normalized_rows):
        cloned_component = copy.deepcopy(template_component)
        _apply_fuses_2009_row_to_text_component(cloned_component, row, index)
        component_list.append(cloned_component)

    strip_x_size = _fuses_2009_strip_x_size(len(normalized_rows))
    strip.set("xSize", _format_wssl_float(strip_x_size))
    strip.set("ySize", _format_wssl_float(_FUSES_2009_STRIP_Y_SIZE))
    _validate_fuses_2009_layout(root, component_list, normalized_rows)
    for message in _fuses_2009_debug_messages(normalized_rows, strip_x_size):
        print(message)

    ET.indent(root, space="   ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def build_fuses_2009_wssl_bytes(rows: list[dict[str, Any]] | None = None) -> bytes:
    """Build a flat FUSES Wago 2009-115 WSSL archive from Component Marking rows."""
    return _build_wssl_zip_bytes(
        [
            WsslTemplateFile("version.info", _TERMINAL_STRIP_TEMPLATE_VERSION.encode("utf-8")),
            WsslTemplateFile("strip.layout", _build_fuses_2009_layout(rows).encode("utf-8")),
            WsslTemplateFile("meta.data", _FUSES_2009_TEMPLATE_METADATA.encode("utf-8")),
            WsslTemplateFile("table.config", _FUSES_2009_TEMPLATE_TABLE_CONFIG.encode("utf-8")),
            WsslTemplateFile("import.config", _FUSES_2009_TEMPLATE_IMPORT_CONFIG.encode("utf-8")),
        ]
    )
