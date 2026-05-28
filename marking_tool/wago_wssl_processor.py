from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from io import BytesIO
import uuid
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile


@dataclass(frozen=True)
class WsslTemplateFile:
    """One root-level file inside a WSSL ZIP archive."""

    filename: str
    content: bytes


@dataclass(frozen=True)
class WsslComponentStyle:
    """Visual overrides for one cloned WSSL text component."""

    bold: bool
    text_stretching_factor: float


@dataclass(frozen=True)
class WsslComponent:
    """One generated WSSL component value."""

    text: str
    style: WsslComponentStyle


_TERMINAL_STRIP_DEMO_VALUES = ("-X118", "-X1112", "-X192A5", "", "-X6311", "-X6312", "", "STOP")

_TERMINAL_STRIP_TEMPLATE_VERSION = """<?xml version="1.0" encoding="UTF-8"?>
<Version version="4.9.5.2"/>
"""

_TERMINAL_STRIP_TEMPLATE_METADATA = """<?xml version="1.0" encoding="UTF-8"?>
<MetaData>
   <metadata projectType="UserProject">
      <description>Terminal Strip</description>
      <customerName></customerName>
      <OrderNumber></OrderNumber>
      <customerNumber></customerNumber>
      <plantNumber></plantNumber>
      <creator></creator>
      <auditor></auditor>
      <auditTime></auditTime>
      <templateID>20090110</templateID>
      <savedWithAppVersion>4.9.5.2</savedWithAppVersion>
      <workDirection>HORIZONTAL</workDirection>
      <creationTime></creationTime>
      <ModificationTime></ModificationTime>
      <printTime></printTime>
   </metadata>
</MetaData>
"""

_TERMINAL_STRIP_TEMPLATE_TABLE_CONFIG = """<?xml version="1.0" encoding="UTF-8"?>
<TableConfig/>
"""

_TERMINAL_STRIP_TEMPLATE_IMPORT_CONFIG = """<?xml version="1.0" encoding="UTF-8"?>
<ImportConfig/>
"""

_TERMINAL_STRIP_TEMPLATE_LAYOUT = """<?xml version="1.0" encoding="UTF-8"?>
<Strip>
   <strip appVersion="4.9.5.2" xMinChildlessWidth="54.54545454545455" xSize="9745.27" ySize="200.0" flowOn="true" stripMode="synchronized">
      <componentList>
         <Grid contentRotation="270.0" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" identifier="00000000-0000-4000-8000-000000000100" openTerminalSide="NONE" endplateWidthStr="0.0" separatorThickness="1.0">
            <childList>
               <GridEndPlate identifier="00000000-0000-4000-8000-000000000101" xPos="0.0" xSize="0.0" yPos="0.0" ySize="200.0"/>
               <OuterGridRowCol identifier="00000000-0000-4000-8000-000000000102" orientation="COLUMN" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0"/>
               <GridCell column="0" row="0" identifier="00000000-0000-4000-8000-000000000103" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0">
                  <childList>
                     <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="00000000-0000-4000-8000-000000000001" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="TEMPLATE" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>
                  </childList>
               </GridCell>
               <GridRowCol identifier="00000000-0000-4000-8000-000000000104" orientation="ROW" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0"/>
            </childList>
         </Grid>
         <Grid contentRotation="270.0" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" xPos="287.45454545454544" xSize="287.45454545454544" yPos="0.0" ySize="200.0" identifier="00000000-0000-4000-8000-000000000200" openTerminalSide="NONE" endplateWidthStr="0.0" separatorThickness="1.0">
            <childList>
               <GridEndPlate identifier="00000000-0000-4000-8000-000000000201" xPos="0.0" xSize="0.0" yPos="0.0" ySize="200.0"/>
               <OuterGridRowCol identifier="00000000-0000-4000-8000-000000000202" orientation="COLUMN" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0"/>
               <GridCell column="0" row="0" identifier="00000000-0000-4000-8000-000000000203" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0">
                  <childList>
                     <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="00000000-0000-4000-8000-000000000002" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="TEMPLATE_2" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>
                  </childList>
               </GridCell>
               <GridRowCol identifier="00000000-0000-4000-8000-000000000204" orientation="ROW" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0"/>
            </childList>
         </Grid>
      </componentList>
   </strip>
</Strip>
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


def _terminal_strip_component_style(text: str) -> WsslComponentStyle:
    """Resolve Terminal Strip demo style for data, blanks, and generated STOP."""
    normalized_text = text.strip().upper()
    is_stop = normalized_text == "STOP"
    is_blank = text == ""
    return WsslComponentStyle(
        bold=not (is_stop or is_blank),
        text_stretching_factor=1.0 if is_stop or is_blank else _resolve_terminal_strip_stretch(text),
    )


def _component_list_grids(component_list: ET.Element) -> list[ET.Element]:
    """Return top-level Grid blocks used as Terminal Strip clone units."""
    grids = component_list.findall("Grid")
    if not grids:
        raise ValueError("Terminal Strip WSSL template componentList missing Grid blocks")
    return grids


def _first_grid_wago_text_component(grid: ET.Element) -> ET.Element:
    """Return the first WagoTextComponent inside the template Grid."""
    template_component = grid.find(".//WagoTextComponent")
    if template_component is None:
        raise ValueError("Terminal Strip WSSL template Grid missing WagoTextComponent")
    return template_component


def _assign_new_identifiers(element: ET.Element) -> None:
    """Give cloned template nodes fresh UUID identifiers."""
    for node in element.iter():
        if "identifier" in node.attrib:
            node.set("identifier", str(uuid.uuid4()))


def _build_terminal_strip_grid(component: WsslComponent, template_grid: ET.Element) -> ET.Element:
    """Clone one complete top-level Grid and mutate its primary text component."""
    cloned_grid = deepcopy(template_grid)
    _assign_new_identifiers(cloned_grid)
    text_components = cloned_grid.findall(".//WagoTextComponent")
    if not text_components:
        raise ValueError("Terminal Strip WSSL template Grid missing WagoTextComponent")

    primary_component = text_components[0]
    primary_component.set("text", component.text)
    primary_component.set("textStretchingFactorStr", str(component.style.text_stretching_factor))
    primary_component.set("bold", str(component.style.bold).lower())
    for extra_component in text_components[1:]:
        extra_component.set("text", "")
    return cloned_grid


def _validate_terminal_strip_component_list(component_list: ET.Element) -> None:
    """Validate generated Terminal Strip componentList contains populated Grid blocks."""
    generated_grids = component_list.findall("Grid")
    if not generated_grids:
        raise ValueError("No Grid blocks generated")
    for generated_grid in generated_grids:
        if generated_grid.find(".//GridCell/childList/WagoTextComponent") is None:
            raise ValueError("Generated Grid missing WagoTextComponent")


def _terminal_strip_demo_components() -> list[WsslComponent]:
    """Build demo Terminal Strip WSSL components."""
    return [
        WsslComponent(text=text, style=_terminal_strip_component_style(text))
        for text in _TERMINAL_STRIP_DEMO_VALUES
    ]


def _build_terminal_strip_layout() -> str:
    """Clone full Grid blocks and replace the template componentList with generated grids."""
    root = ET.fromstring(_TERMINAL_STRIP_TEMPLATE_LAYOUT)
    strip = root.find("strip")
    component_list = root.find(".//componentList")
    if strip is None or component_list is None:
        raise ValueError("Terminal Strip WSSL template missing strip/componentList")

    template_grids = _component_list_grids(component_list)
    template_grid = next(
        (grid for grid in template_grids if len(grid.findall(".//WagoTextComponent")) == 1),
        template_grids[0],
    )
    grid_x_size = float(template_grid.attrib["xSize"])
    if len(template_grids) >= 2:
        grid_step = float(template_grids[1].attrib["xPos"]) - float(template_grids[0].attrib["xPos"])
    else:
        grid_step = grid_x_size

    generated_grids = [
        _build_terminal_strip_grid(component, template_grid)
        for component in _terminal_strip_demo_components()
    ]
    for index, grid in enumerate(generated_grids):
        grid.set("xPos", str(index * grid_step))

    component_list.clear()
    for cloned_grid in generated_grids:
        component_list.append(cloned_grid)
    _validate_terminal_strip_component_list(component_list)
    strip.set("xSize", str((len(generated_grids) - 1) * grid_step + grid_x_size))

    ET.indent(root, space="   ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def _build_wssl_zip_bytes(template_files: list[WsslTemplateFile]) -> bytes:
    """Build one WSSL ZIP with root-level template file names only."""
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for template_file in template_files:
            archive.writestr(template_file.filename, template_file.content)
    return output.getvalue()


def build_terminal_strip_wssl_bytes() -> bytes:
    """Build a demo Terminal Strip WSSL archive using Grid-based template cloning."""
    return _build_wssl_zip_bytes(
        [
            WsslTemplateFile("version.info", _TERMINAL_STRIP_TEMPLATE_VERSION.encode("utf-8")),
            WsslTemplateFile("strip.layout", _build_terminal_strip_layout().encode("utf-8")),
            WsslTemplateFile("meta.data", _TERMINAL_STRIP_TEMPLATE_METADATA.encode("utf-8")),
            WsslTemplateFile("table.config", _TERMINAL_STRIP_TEMPLATE_TABLE_CONFIG.encode("utf-8")),
            WsslTemplateFile("import.config", _TERMINAL_STRIP_TEMPLATE_IMPORT_CONFIG.encode("utf-8")),
        ]
    )
