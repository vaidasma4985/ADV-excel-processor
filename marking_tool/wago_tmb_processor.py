from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import uuid
from zipfile import ZIP_DEFLATED, ZipFile


@dataclass(frozen=True)
class WagoTerminalTmbSettings:
    """Immutable WSSL export settings for Terminal TMB."""

    marking_type: str
    material_number: str
    template_id: str
    font_face: str
    data_bold: bool
    group_label_bold: bool
    section_label_bold: bool
    format_name: str
    saved_with_app_version: str
    work_direction: str
    generated_label_font_size: int
    data_font_size: float


WAGO_TERMINAL_TMB_SETTINGS = WagoTerminalTmbSettings(
    marking_type="Terminal TMB",
    material_number="2009-115",
    template_id="20090115",
    font_face="Arial",
    data_bold=True,
    group_label_bold=False,
    section_label_bold=False,
    format_name="WSSL",
    saved_with_app_version="4.9.5.3",
    work_direction="HORIZONTAL",
    generated_label_font_size=7,
    data_font_size=64.14141414141415,
)


@dataclass(frozen=True)
class WagoTerminalTmbComponentStyle:
    """Resolved WSSL style for one Terminal TMB component."""

    bold: bool
    font_size: float | int
    text_size: float | int
    text_stretching_factor: float

_WAGO_TMB_DEMO_VALUES = ("1", "2", "3", "", "4", "5", "", "6", "7", "8")
_TMB_FIRST_X_POS = 10.622236114940005
_TMB_X_POS_STEP = 94.54552815855232
_TMB_COMPONENT_X_SIZE = 72.37651138670707
_TMB_STRIP_RIGHT_MARGIN = 10.0

_TMB_TEMPLATE_VERSION_INFO = f"""<?xml version="1.0" encoding="UTF-8"?>
<Version version="{WAGO_TERMINAL_TMB_SETTINGS.saved_with_app_version}"/>
"""

_TMB_TEMPLATE_META_DATA = f"""<?xml version="1.0" encoding="UTF-8"?>
<MetaData>
   <metadata projectType="UserProject">
      <description>{WAGO_TERMINAL_TMB_SETTINGS.marking_type}</description>
      <customerName></customerName>
      <OrderNumber></OrderNumber>
      <customerNumber></customerNumber>
      <plantNumber></plantNumber>
      <creator></creator>
      <auditor></auditor>
      <auditTime></auditTime>
      <templateID>{WAGO_TERMINAL_TMB_SETTINGS.template_id}</templateID>
      <savedWithAppVersion>{WAGO_TERMINAL_TMB_SETTINGS.saved_with_app_version}</savedWithAppVersion>
      <workDirection>{WAGO_TERMINAL_TMB_SETTINGS.work_direction}</workDirection>
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

_TMB_TEXT_COMPONENT_TEMPLATE = """         <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="{x_pos}" xSize="{x_size}" yPos="14.544008255004883" ySize="145.44900608062744" bdrColor="#000000FF" bdrRadius="0.0" borderSize="4.0" contentRotation="0.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="SIMPLE_LOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="{identifier}" bold="{bold}" fgColor="#000000FF" font="{font}" fontSize="{font_size}" italic="false" lineSpacingStr="-9.621212121212121" nodeAligmentStr="CENTER" text="{text}" textAlignmentStr="CENTER" textSize="{text_size}" textStretchingFactorStr="{text_stretching_factor}"/>
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


def _resolve_tmb_component_style(text: str, settings: WagoTerminalTmbSettings) -> WagoTerminalTmbComponentStyle:
    """Resolve WSSL-only font and fit style for one Terminal TMB value."""
    normalized_text = text.strip().upper()
    if normalized_text in {"TOP", "MIDDLE", "BOTTOM"}:
        return WagoTerminalTmbComponentStyle(
            bold=settings.section_label_bold,
            font_size=settings.generated_label_font_size,
            text_size=settings.generated_label_font_size,
            text_stretching_factor=1.0,
        )
    if not normalized_text:
        return WagoTerminalTmbComponentStyle(
            bold=False,
            font_size=settings.data_font_size,
            text_size=settings.data_font_size,
            text_stretching_factor=1.0,
        )
    text_stretching_factor = 1.0
    if len(text) >= 8:
        text_stretching_factor = 0.7
    elif len(text) >= 6:
        text_stretching_factor = 0.85
    return WagoTerminalTmbComponentStyle(
        bold=settings.data_bold,
        font_size=settings.data_font_size,
        text_size=settings.data_font_size,
        text_stretching_factor=text_stretching_factor,
    )


def _build_wago_text_component(text: str, x_pos: float) -> str:
    """Build one flat Terminal TMB WagoTextComponent."""
    style = _resolve_tmb_component_style(text, WAGO_TERMINAL_TMB_SETTINGS)
    return _TMB_TEXT_COMPONENT_TEMPLATE.format(
        identifier=str(uuid.uuid4()),
        text=_xml_attribute_escape(text),
        x_pos=str(x_pos),
        x_size=str(_TMB_COMPONENT_X_SIZE),
        bold=str(style.bold).lower(),
        font=_xml_attribute_escape(WAGO_TERMINAL_TMB_SETTINGS.font_face),
        font_size=str(style.font_size),
        text_size=str(style.text_size),
        text_stretching_factor=str(style.text_stretching_factor),
    )


def _build_strip_layout() -> str:
    """Build the flat working Terminal TMB strip.layout shape."""
    component_positions = [
        _TMB_FIRST_X_POS + ((index - 1) * _TMB_X_POS_STEP)
        for index, _ in enumerate(_WAGO_TMB_DEMO_VALUES, start=1)
    ]
    strip_x_size = max(
        x_pos + _TMB_COMPONENT_X_SIZE
        for x_pos in component_positions
    ) + _TMB_STRIP_RIGHT_MARGIN
    components = "".join(
        _build_wago_text_component(text, x_pos)
        for text, x_pos in zip(_WAGO_TMB_DEMO_VALUES, component_positions)
    )
    return _TMB_STRIP_LAYOUT_OPEN_TEMPLATE.format(x_size=str(strip_x_size)) + components + _TMB_STRIP_LAYOUT_CLOSE


def build_wago_tmb_wssl_bytes() -> bytes:
    """Build a demo Terminal TMB WSSL ZIP with the flat componentList template."""
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("version.info", _TMB_TEMPLATE_VERSION_INFO.encode("utf-8"))
        archive.writestr("strip.layout", _build_strip_layout().encode("utf-8"))
        archive.writestr("meta.data", _TMB_TEMPLATE_META_DATA.encode("utf-8"))
    return output.getvalue()
