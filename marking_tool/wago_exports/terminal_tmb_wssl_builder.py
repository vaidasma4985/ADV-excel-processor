from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from io import BytesIO
from typing import Any
import uuid
from zipfile import ZIP_DEFLATED, ZipFile

from marking_tool.wago_exports.shared_wssl import ui_font_to_wssl_size


# SmartScript UI font size -> WSSL fontSize/textSize conversion
# Verified from real WAGO template.
TMB_DATA_UI_FONT_SIZE = 10
TMB_LABEL_UI_FONT_SIZE = 7


@dataclass(frozen=True)
class WagoTerminalTmbSettings:
    """Immutable WSSL export settings for Terminal TMB."""

    marking_type: str
    format_name: str
    material_number: str
    template_id: str
    data_font_face: str
    data_font_bold: bool
    tmb_section_label_bold: bool
    saved_with_app_version: str
    work_direction: str
    tmb_section_label_ui_font_size: float
    tmb_data_ui_font_size: float


TERMINAL_TMB_WSSL_SETTINGS = WagoTerminalTmbSettings(
    marking_type="Terminal TMB",
    format_name="WSSL",
    material_number="2009-115",
    template_id="20090115",
    data_font_face="Arial",
    data_font_bold=True,
    tmb_section_label_bold=False,
    saved_with_app_version="4.9.5.3",
    work_direction="HORIZONTAL",
    tmb_section_label_ui_font_size=TMB_LABEL_UI_FONT_SIZE,
    tmb_data_ui_font_size=TMB_DATA_UI_FONT_SIZE,
)


@dataclass(frozen=True)
class WagoTerminalTmbComponentStyle:
    """Resolved WSSL style for one Terminal TMB component."""

    bold: bool
    font_size: float | int
    text_size: float | int
    text_stretching_factor: float

_WAGO_TMB_DEMO_VALUES = ("1", "2", "3", "", "4", "5", "", "6", "7", "8")
_GENERATED_TMB_LABELS = {"TOP", "MIDDLE", "BOTTOM"}
_TMB_FIRST_X_POS = 10.622236114940005
_TMB_X_POS_STEP = 94.54552815855232
_TMB_COMPONENT_X_SIZE = 72.37651138670707
_TMB_STRIP_RIGHT_MARGIN = 10.0

_TMB_TEMPLATE_VERSION_INFO = f"""<?xml version="1.0" encoding="UTF-8"?>
<Version version="{TERMINAL_TMB_WSSL_SETTINGS.saved_with_app_version}"/>
"""

_TMB_TEMPLATE_META_DATA = f"""<?xml version="1.0" encoding="UTF-8"?>
<MetaData>
   <metadata projectType="UserProject">
      <description>{TERMINAL_TMB_WSSL_SETTINGS.marking_type}</description>
      <customerName></customerName>
      <OrderNumber></OrderNumber>
      <customerNumber></customerNumber>
      <plantNumber></plantNumber>
      <creator></creator>
      <auditor></auditor>
      <auditTime></auditTime>
      <templateID>{TERMINAL_TMB_WSSL_SETTINGS.template_id}</templateID>
      <savedWithAppVersion>{TERMINAL_TMB_WSSL_SETTINGS.saved_with_app_version}</savedWithAppVersion>
      <workDirection>{TERMINAL_TMB_WSSL_SETTINGS.work_direction}</workDirection>
      <creationTime></creationTime>
      <ModificationTime></ModificationTime>
      <printTime></printTime>
   </metadata>
</MetaData>
"""

_TMB_STRIP_LAYOUT_OPEN_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<Strip>
   <strip appVersion="4.9.5.3" xMinChildlessWidth="54.54545454545455" xSize="{x_size}" ySize="174.54545454545453" flowOn="false" stripMode="synchronized">
      <componentList>
"""

_TMB_STRIP_LAYOUT_CLOSE = """      </componentList>
   </strip>
</Strip>
"""

_TMB_TEXT_COMPONENT_TEMPLATE = """         <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="{x_pos}" xSize="{x_size}" yPos="14.544008255004883" ySize="145.44900608062744" bdrColor="#000000FF" bdrRadius="0.0" borderSize="4.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="SIMPLE_LOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="{identifier}" bold="{bold}" fgColor="#000000FF" font="{font}" fontSize="{font_size}" italic="false" lineSpacingStr="-9.621212121212121" nodeAligmentStr="CENTER" text="{text}" textAlignmentStr="CENTER" textSize="{text_size}" textStretchingFactorStr="{text_stretching_factor}"/>
"""


def build_wago_tmb_wssl_filename(project_number: str | None) -> str:
    """Build the Terminal TMB WSSL filename."""
    project_prefix = project_number or "1"
    return f"{project_prefix}_Terminal TMB.wssl"


def _xml_attribute_escape(value: str) -> str:
    """Escape one XML attribute value."""
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _resolve_tmb_label_kind(row: Mapping[str, Any]) -> str:
    """Classify one TMB row using kind first, with text fallback only when kind is missing."""
    row_kind = row.get("kind")
    text = str(row.get("Text", "")).strip()
    if row_kind in {"group_label", "section_label", "generated_label"}:
        return "generated_label"
    if text == "":
        return "blank"
    if row_kind is not None:
        return "real_data"
    if text.upper() in _GENERATED_TMB_LABELS:
        return "generated_label"
    return "real_data"


def _resolve_tmb_component_style(row: Mapping[str, Any], settings: WagoTerminalTmbSettings) -> WagoTerminalTmbComponentStyle:
    """Resolve WSSL-only font and fit style for one Terminal TMB value."""
    label_kind = _resolve_tmb_label_kind(row)
    text = str(row.get("Text", ""))
    data_font_size = ui_font_to_wssl_size(settings.tmb_data_ui_font_size)
    section_label_font_size = ui_font_to_wssl_size(settings.tmb_section_label_ui_font_size)
    if label_kind == "generated_label":
        return WagoTerminalTmbComponentStyle(
            bold=settings.tmb_section_label_bold,
            font_size=section_label_font_size,
            text_size=section_label_font_size,
            text_stretching_factor=0.42,
        )
    if label_kind == "blank":
        return WagoTerminalTmbComponentStyle(
            bold=False,
            font_size=data_font_size,
            text_size=data_font_size,
            text_stretching_factor=1.0,
        )
    text_length = len(text)
    if text_length <= 2:
        text_stretching_factor = 1.0
    elif text_length == 3:
        text_stretching_factor = 0.84
    elif text_length == 4:
        text_stretching_factor = 0.70
    else:
        text_stretching_factor = 0.42
    return WagoTerminalTmbComponentStyle(
        bold=settings.data_font_bold,
        font_size=data_font_size,
        text_size=data_font_size,
        text_stretching_factor=text_stretching_factor,
    )


def _build_wago_text_component(
    row: Mapping[str, Any],
    x_pos: float,
    settings: WagoTerminalTmbSettings,
) -> str:
    """Build one flat Terminal TMB WagoTextComponent."""
    text = str(row.get("Text", ""))
    style = _resolve_tmb_component_style(row, settings)
    return _TMB_TEXT_COMPONENT_TEMPLATE.format(
        identifier=str(uuid.uuid4()),
        text=_xml_attribute_escape(text),
        x_pos=str(x_pos),
        x_size=str(_TMB_COMPONENT_X_SIZE),
        bold=str(style.bold).lower(),
        font=_xml_attribute_escape(settings.data_font_face),
        font_size=str(style.font_size),
        text_size=str(style.text_size),
        text_stretching_factor=str(style.text_stretching_factor),
    )


def _tmb_rows_for_output(tmb_rows: list[dict[str, Any]] | None) -> list[Mapping[str, Any]]:
    """Use real TMB rows when present; keep demo rows as fallback only."""
    if tmb_rows:
        return tmb_rows
    return [
        {"Text": value, "kind": "blank" if value == "" else "normal"}
        for value in _WAGO_TMB_DEMO_VALUES
    ]


def _build_strip_layout(
    tmb_rows: list[dict[str, Any]] | None = None,
    *,
    settings: WagoTerminalTmbSettings,
) -> str:
    """Build the flat working Terminal TMB strip.layout shape."""
    output_rows = _tmb_rows_for_output(tmb_rows)
    component_positions = [
        _TMB_FIRST_X_POS + ((index - 1) * _TMB_X_POS_STEP)
        for index, _ in enumerate(output_rows, start=1)
    ]
    strip_x_size = max(
        x_pos + _TMB_COMPONENT_X_SIZE
        for x_pos in component_positions
    ) + _TMB_STRIP_RIGHT_MARGIN
    components = "".join(
        _build_wago_text_component(row, x_pos, settings)
        for row, x_pos in zip(output_rows, component_positions)
    )
    return _TMB_STRIP_LAYOUT_OPEN_TEMPLATE.format(x_size=str(strip_x_size)) + components + _TMB_STRIP_LAYOUT_CLOSE


def build_terminal_tmb_wssl_bytes(tmb_rows: list[dict[str, Any]] | None = None) -> bytes:
    """Build production Terminal TMB WSSL using its isolated profile."""
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("version.info", _TMB_TEMPLATE_VERSION_INFO.encode("utf-8"))
        archive.writestr(
            "strip.layout",
            _build_strip_layout(tmb_rows, settings=TERMINAL_TMB_WSSL_SETTINGS).encode("utf-8"),
        )
        archive.writestr("meta.data", _TMB_TEMPLATE_META_DATA.encode("utf-8"))
    return output.getvalue()


def build_wago_tmb_wssl_bytes(tmb_rows: list[dict[str, Any]] | None = None) -> bytes:
    """Backward-compatible alias for Terminal TMB WSSL generation."""
    return build_terminal_tmb_wssl_bytes(tmb_rows)
