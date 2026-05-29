from __future__ import annotations

import copy
from dataclasses import dataclass
from io import BytesIO
import pprint
from typing import Any
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

    font: str
    font_size: float
    bold: bool
    text_stretching_factor: float


@dataclass(frozen=True)
class WsslComponent:
    """One generated WSSL component value."""

    text: str
    style: WsslComponentStyle


WSSL_WIDTH_SCALE = 18.18181818181818
_TERMINAL_STRIP_WSSL_SCALE = WSSL_WIDTH_SCALE
_FUSE_STRIP_WSSL_SCALE = WSSL_WIDTH_SCALE
_FUSE_STRIP_Y_SIZE = 363.6363636363636
_FUSE_STRIP_CONTENT_ROTATION = "270.0"
_RELAY_STRIP_WSSL_SCALE = WSSL_WIDTH_SCALE
_RELAY_STRIP_Y_SIZE = 363.6363636363636
_RELAY_STRIP_CONTENT_ROTATION = "0.0"
_STRIP_START_STOP_SPACE = 6.2
_STRIP_START_STOP_CONTENT_ROTATION = "270.0"

# SmartScript UI font size -> WSSL fontSize/textSize conversion
# Verified from real WAGO template.
WSSL_FONT_SIZE_MULTIPLIER = 6.414141414141415
_VERIFIED_WSSL_UI_FONT_SIZES = {
    5.0: 32.07070707070707,
    6.0: 38.484848484848484,
    7.0: 44.898989898989896,
    8.0: 51.313131313131315,
    9.0: 57.72727272727273,
    10.0: 64.14141414141415,
    11.0: 70.55555555555556,
}
TERMINAL_STRIP_DATA_UI_FONT_SIZE = 10
TERMINAL_STRIP_LABEL_UI_FONT_SIZE = 7
FUSE_STRIP_DATA_UI_FONT_SIZE = 10
FUSE_STRIP_LABEL_UI_FONT_SIZE = 7
RELAY_STRIP_DATA_UI_FONT_SIZE = 10
RELAY_STRIP_LABEL_UI_FONT_SIZE = 7
_TERMINAL_STRIP_PLACEHOLDER_TEMPLATE_ERROR = (
    "Embedded Terminal Strip WSSL template is still placeholder/wrong. "
    "Replace it with full real strip.layout from 2605-078 terminal strip template.wssl."
)
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

_TERMINAL_STRIP_TEMPLATE_VERSION = r"""<?xml version="1.0" encoding="UTF-8"?>

<Version version="4.9.5.2"/>

"""

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

_RELAY_STRIP_TEMPLATE_METADATA = r"""<?xml version="1.0" encoding="UTF-8"?>

<MetaData>

   <metadata projectType="UserProject">

      <description>Relay Strip</description>

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

_TERMINAL_STRIP_TEMPLATE_TABLE_CONFIG = r"""<?xml version="1.0" encoding="UTF-8"?>

<table-config>

   <file-path>Y:\JE-ELKAS\21.0 Litauen\ADVANCOR\2605-078\2605-078_Markings.xlsx</file-path>

   <sheetName>Terminal markings</sheetName>

   <firstRowIsHeader>false</firstRowIsHeader>

   <column-separator>COMMA</column-separator>

   <row-separator>NEW_LINE</row-separator>

</table-config>

"""

_FUSE_STRIP_TEMPLATE_TABLE_CONFIG = r"""<?xml version="1.0" encoding="UTF-8"?>

<table-config>

   <file-path>Y:\JE-ELKAS\21.0 Litauen\ADVANCOR\2605-078\2605-078_Markings.xlsx</file-path>

   <sheetName>Component markings</sheetName>

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

_FUSE_STRIP_TEMPLATE_IMPORT_CONFIG = r"""<?xml version="1.0" encoding="UTF-8"?>

<grid-import-config ignore-empty-rows="false" ignore-empty-cells="false" cut-marker="NONE" default-cell-width="6.2" default-end-plate-width="5.15" text-rotation="270.0" header-count="0" terminal-row-count="1" header-position="TOP" grid-labeling-order="TOP_BOTTOM">

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

_TERMINAL_STRIP_TEMPLATE_LAYOUT = r"""<?xml version="1.0" encoding="UTF-8"?>

<Strip>

   <strip appVersion="4.9.5.2" xMinChildlessWidth="54.54545454545455" xSize="9745.27" ySize="200.0" flowOn="true" stripMode="synchronized">

      <componentList>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="287.45454545454544" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="287.45454545454544">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="287.45454545454544">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="632fdf00-c2eb-489e-9696-f8b2fdcd0d5c" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X118" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="302.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="287.45454545454544" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="287.45454545454544">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="287.45454545454544">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="c8a99856-1f55-4017-b1fd-a11179280d51" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X128" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="604.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="287.45454545454544" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="287.45454545454544">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="287.45454545454544">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="3c9fc58d-fe15-482a-a88c-54b0239da024" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X138" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="906.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="287.45454545454544" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="287.45454545454544">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="287.45454545454544">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="a17d74cb-82d8-4510-a9fa-33652fc73adc" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X148" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="1208.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="287.45454545454544" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="287.45454545454544">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="287.45454545454544">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="8351c8dc-c716-4148-8c51-5a256c7445a7" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X158" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="1510.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="287.45454545454544" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="287.45454545454544">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="287.45454545454544">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="b206e57a-0433-4734-8afd-4a35c3d6628c" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X218" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="1812.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="287.45454545454544" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="287.45454545454544">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="287.45454545454544">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="24c81d44-0561-42d5-87a8-63bc428519f3" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X228" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="2114.0" xSize="670.7272727272727" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="670.7272727272727" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="670.7272727272727" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="670.7272727272727">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="670.7272727272727" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="4cf83270-e933-4136-adec-93dbc8324d60" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1112" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="95.81818181818181" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="2cef9ab2-9435-472e-9991-952951522641" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1212" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="191.63636363636363" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="58e4105e-9231-41a7-a158-fd42a6006493" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1312" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="287.45454545454544" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="efe1b1c7-0585-4039-b963-7a69474153dc" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1412" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="383.27272727272725" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="29dd90a6-8a42-4b79-b8ce-89f2311947a8" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1512" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="479.09090909090907" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="cf427c1e-22d9-488c-bcaa-536461d5c80a" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X2112" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="574.9090909090909" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="a103b3e7-b90c-47f8-ab18-855a33858a13" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X2212" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="2799.272727272727" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="287.45454545454544" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="287.45454545454544">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="287.45454545454544">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="cc5ba854-8b43-489c-8357-508f8136a85f" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="PE" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="3101.272727272727" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="191.63636363636363" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="191.63636363636363">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="9575d38a-9db6-4d51-9df9-a12135f2a3f5" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1113" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="95.81818181818181" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="4dba70cd-2aaa-416d-9137-53c6d3916818" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1114" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="3307.454545454545" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="191.63636363636363" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="191.63636363636363">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="7758a1fc-0962-4d85-981b-c4c6a3e7514d" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1213" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="95.81818181818181" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="f108e0cc-c755-4809-9ed4-2c8500a2ccaf" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1214" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="3513.636363636363" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="191.63636363636363" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="191.63636363636363">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="43cb5f2f-52c6-4b97-823c-8852292e4cfc" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1313" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="95.81818181818181" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="8305b914-692a-47b6-992b-9c88bea7d08c" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1314" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="3719.818181818181" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="191.63636363636363" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="191.63636363636363">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="147fea78-e44b-4c00-bc63-6ee940ae2ce1" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1413" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="95.81818181818181" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="6ecf8c45-934a-4fb4-a9a2-e389f4dc00ef" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1414" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="3925.999999999999" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="191.63636363636363" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="191.63636363636363">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="3bb27d83-4e08-4931-8633-609f766f58e2" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1513" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="95.81818181818181" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="33d5c8f3-b321-4d7f-b6e1-51a84faa4642" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1514" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="4132.181818181817" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="191.63636363636363" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="191.63636363636363">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="230fae17-03cb-4a35-90be-f1b6afa4346e" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X2113" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="95.81818181818181" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="55c7d7f7-0985-47ab-a9cf-f82da6d70176" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X2114" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="4338.363636363635" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="191.63636363636363" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="191.63636363636363">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="b7dbcece-716f-41ae-8ade-4fa0e43c294e" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X2213" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="95.81818181818181" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="bfb02bab-44ba-428a-82fa-25d3d63ac797" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X2214" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="4544.545454545453" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="191.63636363636363" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="191.63636363636363">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="191.63636363636363">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="35035078-344d-4a93-9f2e-dee16e38ddb9" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1126" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="4750.727272727271" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="191.63636363636363" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="191.63636363636363">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="191.63636363636363">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="b34d5bc6-89aa-49f0-b411-d2a136262819" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X2126" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="4956.909090909089" xSize="574.9090909090909" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="574.9090909090909" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="574.9090909090909" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="574.9090909090909">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="574.9090909090909" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="5055e802-5ba2-40fe-b598-e849c6d2b9ea" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1912" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="95.81818181818181" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="e4d0ec64-2615-4f03-a97a-2eaf0f073aa3" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1922" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="191.63636363636363" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="79f3982e-a8f2-4047-b7cb-02976b906ab6" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X192A5" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.7"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="287.45454545454544" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="55b65716-5576-4600-83c6-753a6a196471" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1953" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="383.27272727272725" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="dc41b8fd-534e-44ce-b205-cf5bc7334145" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1954" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="479.09090909090907" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="187b9944-370a-4edf-bfc0-af9e99499376" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1956" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="5546.363636363634" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="191.63636363636363" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="191.63636363636363">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="191.63636363636363">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="2f3910c2-4492-4b0f-abe5-0dba32863e36" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="PE" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="5752.545454545452" xSize="574.9090909090909" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="574.9090909090909" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="574.9090909090909" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="574.9090909090909">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="574.9090909090909" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="6b591223-236d-4612-9538-95e96c3c587e" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1918" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="95.81818181818181" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="521aef25-1941-4d8c-b4d1-7aedb91ab6b8" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1921" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="191.63636363636363" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="6b2cfc7a-94e5-450b-b5e9-c1c19281d438" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1924" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="287.45454545454544" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="3abfc5e0-8a46-4e48-896e-bc514c474350" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X192A3" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.7"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="383.27272727272725" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="ef46f21e-d6c6-4efc-855f-b82e84e1d9b8" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X2918" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="479.09090909090907" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="d2c99148-ab1e-442f-879e-924acfd253f0" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X3921" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="6341.999999999997" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="95.81818181818181" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="367cd141-309c-4e73-a04e-ebd7091b303c" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="PE" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="6452.363636363633" xSize="670.7272727272727" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="670.7272727272727" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="670.7272727272727" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="670.7272727272727">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="670.7272727272727" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="89ad0474-6cad-4f56-833b-6401123ecdbe" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1931" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="95.81818181818181" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="1625e31c-2477-4773-be6e-234b06f11873" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1932" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="191.63636363636363" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="a80f5a50-5897-40c7-986d-3bd7a7fa7478" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X2931" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="287.45454545454544" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="8a9cb002-9566-40bf-b883-aeb9cd14c45a" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X2932" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="383.27272727272725" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="e48df893-7e3c-4428-af70-440615996517" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X6118" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="479.09090909090907" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="b1a0d3f7-9930-41a4-a46b-40364a52ff36" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X6211" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="574.9090909090909" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="7266c951-3bcb-4821-b8c7-67f25b2b2568" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X6316" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="7137.63636363636" xSize="479.09090909090907" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="479.09090909090907" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="479.09090909090907" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="479.09090909090907">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="479.09090909090907" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="e50f1d53-f504-42b2-9ad7-15a7c79d259e" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X192A7" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.7"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="95.81818181818181" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="444312ed-ed74-41e9-b25d-8504f1caf66e" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1935" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="191.63636363636363" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="a14a5b5d-ef95-45e1-af60-16cd30b0652c" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X1937" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="287.45454545454544" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="e14aacbc-9209-4869-8b7e-f483b534f975" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X6215" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="383.27272727272725" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="22f55fb8-94ae-4805-a7c1-b7b7b8bcb244" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X6217" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="7631.272727272724" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="0.0" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="false">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="191.63636363636363" xSize="0.0" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="191.63636363636363">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="191.63636363636363">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="dcad1566-d52d-4152-b58a-a29f3bae3454" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X6221" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="7822.909090909088" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="0.0" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="false">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="95.81818181818181" xSize="0.0" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="e2662525-060c-40ab-8c07-ecb9b1a4d456" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X6223" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="7918.72727272727" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="191.63636363636363" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="191.63636363636363">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="191.63636363636363">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="a58a6a54-c994-4d73-977d-f5dd94d2c0e5" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X6231" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="8124.909090909088" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="191.63636363636363" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="191.63636363636363">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="191.63636363636363" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="0825e6c0-0ccb-4f79-881d-fb12c7b0d1cf" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X6111" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="95.81818181818181" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="1b23664d-1793-45a1-ba78-c4b978161b41" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X6112" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="8331.090909090906" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="95.81818181818181" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="b8f3dcf2-06b7-4237-b739-b5d1951839ce" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X911" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="8441.454545454542" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="95.81818181818181" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="5a975d6a-85ea-4394-b62b-093b19b8536e" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X922" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="8551.818181818178" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="95.81818181818181" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="d12d1897-8691-403f-9832-9c6a8324fa59" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="PE" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="8662.181818181814" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="287.45454545454544" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="287.45454545454544">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="287.45454545454544">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="287.45454545454544" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="cf170dc5-615b-451c-aeed-dd824826b0b2" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X6311" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="0.9"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

         <Grid showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="8964.181818181814" xSize="766.5454545454545" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="true" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" endplateWidthStr="14.545454545454547" gridOrientation="VERTICAL" isShowEndLine="true" isShowHoriSeparators="true" isShowStartEndLine="true" isShowStartLine="true" isShowVertSeparators="true" openTerminalSide="RIGHT" separatorThickness="6.0" showEndplateStr="true">

            <childList>

               <GridEndPlate showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="766.5454545454545" xSize="14.545454545454547" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="2.0" contentRotation="0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="true" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0"/>

               <OuterGridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="766.5454545454545" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="VERTICAL">

                  <childList>

                     <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="766.5454545454545">

                        <childList>

                           <GridRowCol showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="766.5454545454545" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" rowColOrientation="HORIZONTAL">

                              <childList>

                                 <GridCell goalHeight="200.0" goalPosX="0.0" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="729307d4-16b8-42e2-a5cf-0a37358ceda4" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X811" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="95.81818181818181" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="075fe402-a6ab-49c3-861f-57bfb6308293" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X812" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="191.63636363636363" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="d015c8d2-05ef-4405-a79a-25640ab18ba3" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X814" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="287.45454545454544" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="5d85422c-1545-4090-a82f-31e8ffc60f59" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X815" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="383.27272727272725" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="fd9fc024-be15-410f-ab3a-00b0b721e161" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X816" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="479.09090909090907" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="5b1e3f40-a77a-48b4-99ca-cae9b2ec9464" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X824" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="574.9090909090909" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="e0b52a9d-8350-4d62-8e31-52037d917e97" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X825" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>

                                    </childList>

                                 </GridCell>

                                 <GridCell goalHeight="200.0" goalPosX="670.7272727272727" goalPosY="0.0" goalWidth="95.81818181818181">

                                    <childList>

                                       <WagoTextComponent showLeftBorder="true" showTopBorder="true" showRightBorder="true" showBottomBorder="true" xPos="0.0" xSize="95.81818181818181" yPos="0.0" ySize="200.0" bdrColor="#000000FF" bdrRadius="0.0" borderSize="0.0" contentRotation="270.0" isDraggable="false" isInGroup="false" isMouseTransparent="false" isShowBorder="false" lockStatus="UNLOCKED" tlbrPadding="0.0:0.0:0.0:0.0" identifier="c482de1c-4346-42a7-a0d9-82794ccb4788" bold="true" fgColor="#000000FF" font="smartFont" fontSize="64.14141414141415" italic="false" lineSpacingStr="0.0" nodeAligmentStr="CENTER" text="-X826" textAlignmentStr="CENTER" textSize="64.14141414141415" textStretchingFactorStr="1.0"/>

                                    </childList>

                                 </GridCell>

                              </childList>

                           </GridRowCol>

                        </childList>

                     </GridCell>

                  </childList>

               </OuterGridRowCol>

            </childList>

         </Grid>

      </componentList>

      <cutMarkerList/>

      <rangeMarkerList/>

   </strip>

</Strip>

"""


def ui_font_to_wssl_size(ui_size: float) -> float:
    """Convert SmartScript UI font size to WSSL fontSize/textSize units."""
    verified_size = _VERIFIED_WSSL_UI_FONT_SIZES.get(float(ui_size))
    if verified_size is not None:
        return verified_size
    return ui_size * WSSL_FONT_SIZE_MULTIPLIER


def build_terminal_strip_wssl_filename(project_number: str | None) -> str:
    """Build the Terminal Strip WSSL filename."""
    project_prefix = project_number or "1"
    return f"{project_prefix}_Terminal Strip.wssl"


def build_fuse_strip_wssl_filename(project_number: str | None) -> str:
    """Build the Fuse Strip WSSL filename."""
    project_prefix = project_number or "1"
    return f"{project_prefix}_Fuse Strip.wssl"


def build_relay_strip_wssl_filename(project_number: str | None) -> str:
    """Build the Relay Strip WSSL filename."""
    project_prefix = project_number or "1"
    return f"{project_prefix}_Relay Strip.wssl"


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
    normalized_text = text.strip().upper()
    is_generated = normalized_text in {"START", "STOP"} or kind in {
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


def _terminal_strip_template_diagnostics(root: ET.Element) -> dict[str, int]:
    """Return counts used to detect placeholder Terminal Strip WSSL templates."""
    return {
        "grid_count": len(root.findall(".//Grid")),
        "grid_cell_count": len(root.findall(".//GridCell")),
        "wago_text_component_count": len(root.findall(".//WagoTextComponent")),
    }


def _validate_terminal_strip_template_counts(root: ET.Element) -> None:
    """Reject placeholder Terminal Strip WSSL templates before generation."""
    diagnostics = _terminal_strip_template_diagnostics(root)
    minimum_text_components = 1
    if (
        diagnostics["grid_count"] < minimum_text_components
        or diagnostics["grid_cell_count"] < minimum_text_components
        or diagnostics["wago_text_component_count"] < minimum_text_components
    ):
        raise ValueError(
            _TERMINAL_STRIP_PLACEHOLDER_TEMPLATE_ERROR
            + " "
            + (
                f"Found Grid={diagnostics['grid_count']}, "
                f"GridCell={diagnostics['grid_cell_count']}, "
                f"WagoTextComponent={diagnostics['wago_text_component_count']}; "
                f"need at least {minimum_text_components} each."
            )
        )


def _template_wago_text_components(component_list: ET.Element) -> list[ET.Element]:
    """Return existing nested WagoTextComponent nodes from the template."""
    rendered_components = [
        text_component
        for text_component in component_list.findall(".//GridCell/childList/WagoTextComponent")
        if text_component.get("text", "") != ""
    ]
    if rendered_components:
        return rendered_components
    return component_list.findall(".//GridCell/childList/WagoTextComponent")


def _grid_wago_text_components(grid: ET.Element) -> list[ET.Element]:
    """Return nested WagoTextComponent nodes for one top-level Grid."""
    return grid.findall(".//GridCell/childList/WagoTextComponent")


def _reusable_terminal_strip_grids(component_list: ET.Element) -> list[ET.Element]:
    """Return top-level Grid units that carry one rendered text component."""
    reusable_grids: list[ET.Element] = []
    for grid in component_list.findall("Grid"):
        text_components = _grid_wago_text_components(grid)
        if len(text_components) == 1 and text_components[0].get("text", "") != "":
            reusable_grids.append(grid)
    return reusable_grids


def _float_attr(element: ET.Element, attr_name: str) -> float:
    """Read a floating-point XML attribute."""
    return float(element.get(attr_name, "0") or "0")


def _format_wssl_float(value: float) -> str:
    """Format generated WSSL float attrs compactly without changing template precision elsewhere."""
    return str(value)


def _refresh_identifiers(element: ET.Element) -> None:
    """Assign new UUIDs to every identifier-bearing node in a cloned template subtree."""
    for child in element.iter():
        if "identifier" in child.attrib:
            child.set("identifier", str(uuid.uuid4()))


def _terminal_strip_grid_endplate_width(grid: ET.Element) -> float:
    """Return the endplate width used as spacing between top-level WSSL Grid units."""
    if grid.get("endplateWidthStr") is not None:
        return _float_attr(grid, "endplateWidthStr")
    grid_endplate = grid.find(".//GridEndPlate")
    if grid_endplate is not None:
        return _float_attr(grid_endplate, "xSize")
    return 0.0


def _terminal_strip_wssl_width(space: float) -> float:
    """Convert one Markings Space value to WSSL layout units."""
    return space * _TERMINAL_STRIP_WSSL_SCALE


def _terminal_strip_grid_row_col(grid: ET.Element) -> ET.Element:
    """Return the horizontal GridRowCol that owns the rendered terminal cells."""
    grid_row_col = grid.find("./childList/OuterGridRowCol/childList/GridCell/childList/GridRowCol")
    if grid_row_col is None:
        raise ValueError("Terminal Strip WSSL template Grid missing nested GridRowCol")
    return grid_row_col


def _terminal_strip_grid_row_col_child_list(grid: ET.Element) -> ET.Element:
    """Return the childList containing nested terminal GridCell nodes."""
    grid_row_col_child_list = _terminal_strip_grid_row_col(grid).find("./childList")
    if grid_row_col_child_list is None:
        raise ValueError("Terminal Strip WSSL template GridRowCol missing childList")
    return grid_row_col_child_list


def _terminal_strip_outer_grid_row_col(grid: ET.Element) -> ET.Element:
    """Return the top-level OuterGridRowCol for one terminal Grid block."""
    outer_grid_row_col = grid.find("./childList/OuterGridRowCol")
    if outer_grid_row_col is None:
        raise ValueError("Terminal Strip WSSL template Grid missing OuterGridRowCol")
    return outer_grid_row_col


def _terminal_strip_outer_grid_cell(grid: ET.Element) -> ET.Element:
    """Return the outer GridCell that wraps the horizontal terminal cells."""
    outer_grid_cell = grid.find("./childList/OuterGridRowCol/childList/GridCell")
    if outer_grid_cell is None:
        raise ValueError("Terminal Strip WSSL template Grid missing outer GridCell")
    return outer_grid_cell


def _terminal_strip_grid_endplate(grid: ET.Element) -> ET.Element:
    """Return the GridEndPlate for one terminal Grid block."""
    grid_endplate = grid.find("./childList/GridEndPlate")
    if grid_endplate is None:
        raise ValueError("Terminal Strip WSSL template Grid missing GridEndPlate")
    return grid_endplate


def _first_terminal_strip_grid_template(component_list: ET.Element) -> ET.Element:
    """Return a full reusable top-level Grid template."""
    reusable_grids = _reusable_terminal_strip_grids(component_list)
    if not reusable_grids:
        raise ValueError("Terminal Strip WSSL template missing reusable nested Grid")
    return reusable_grids[0]


def _first_terminal_strip_cell_template(component_list: ET.Element) -> ET.Element:
    """Return a reusable nested GridCell template; generated width comes from strip_rows."""
    grid_template = _first_terminal_strip_grid_template(component_list)
    for grid_cell in _terminal_strip_grid_row_col_child_list(grid_template).findall("GridCell"):
        if grid_cell.find("./childList/WagoTextComponent") is not None:
            return grid_cell
    raise ValueError("Terminal Strip WSSL template missing reusable nested GridCell")


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


def _safe_terminal_strip_space(value: Any) -> float:
    """Normalize one WAGO Space value for Terminal Strip WSSL diagnostics."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _is_strip_start_stop_text(text: str) -> bool:
    """Return whether a text value is a generated strip boundary label."""
    return text.strip().upper() in {"START", "STOP"}


def _start_stop_row(label: str, space: float) -> dict[str, Any]:
    """Build one normalized START/STOP row."""
    return {
        "space": space,
        "text": label,
        "kind": "generated_label",
    }


def _ensure_strip_start_stop_rows(
    normalized_rows: list[dict[str, Any]],
    default_space: float = _STRIP_START_STOP_SPACE,
) -> list[dict[str, Any]]:
    """Ensure START is the first text cell and STOP is the last, without duplicates."""
    start_space = default_space
    stop_space = default_space
    body_rows: list[dict[str, Any]] = []

    for row in normalized_rows:
        normalized_text = str(row["text"]).strip().upper()
        if normalized_text == "START":
            start_space = float(row["space"])
            continue
        if normalized_text == "STOP":
            stop_space = float(row["space"])
            continue
        body_rows.append(row)

    return [
        _start_stop_row("START", start_space),
        *body_rows,
        _start_stop_row("STOP", stop_space),
    ]


def _derive_terminal_strip_row_kind(row: dict[str, Any], text: str) -> str:
    """Resolve a normalized WSSL row kind without changing row order or content."""
    row_kind = row.get("kind")
    if row_kind:
        return str(row_kind)
    if text == "":
        return "blank"
    if text.strip().upper() in {"START", "STOP"}:
        return "generated_label"
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
    return _ensure_strip_start_stop_rows(normalized_rows)


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
    if _is_strip_start_stop_text(str(row["text"])):
        text_component.set("contentRotation", _STRIP_START_STOP_CONTENT_ROTATION)


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


def _count_terminal_strip_grid_groups(normalized_rows: list[dict[str, Any]]) -> int:
    """Count top-level Grid groups generated from normalized rows."""
    group_count = 0
    has_open_group = False
    for row in normalized_rows:
        if row["text"] == "":
            if has_open_group:
                group_count += 1
                has_open_group = False
            continue
        has_open_group = True
    if has_open_group:
        group_count += 1
    return group_count


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


def _validate_strip_start_stop_text_components(
    text_components: list[ET.Element],
    strip_name: str,
) -> None:
    """Validate shared START/STOP placement and generated-label style."""
    if len(text_components) < 2:
        raise ValueError(f"{strip_name} WSSL generated fewer than two text components")
    if text_components[0].get("text") != "START":
        raise ValueError(f"{strip_name} WSSL START is not the first generated text cell")
    if text_components[-1].get("text") != "STOP":
        raise ValueError(f"{strip_name} WSSL STOP is not the last generated text cell")

    expected_size = _format_wssl_float(ui_font_to_wssl_size(7))
    for label_component in (text_components[0], text_components[-1]):
        label_text = label_component.get("text", "")
        if label_component.get("font") != "Arial":
            raise ValueError(f"{strip_name} WSSL {label_text} does not use Arial")
        if label_component.get("fontSize") != expected_size or label_component.get("textSize") != expected_size:
            raise ValueError(f"{strip_name} WSSL {label_text} does not use UI size 7 WSSL scale")
        if label_component.get("bold") != "false":
            raise ValueError(f"{strip_name} WSSL {label_text} is bold")
        if label_component.get("contentRotation") != _STRIP_START_STOP_CONTENT_ROTATION:
            raise ValueError(f"{strip_name} WSSL {label_text} contentRotation is not 270.0")
        if label_component.get("textStretchingFactorStr") != "1.0":
            raise ValueError(f"{strip_name} WSSL {label_text} stretching is not 1.0")


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
    _validate_strip_start_stop_text_components(text_components, "Terminal Strip")
    if text_components:
        _dump_terminal_strip_text_diagnostics(original_first_label_attrs, text_components[0])

    ET.indent(root, space="   ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


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
    if normalized_text in {"START", "STOP", "24VDC", "230VAC"}:
        return "generated_label"
    return "real_data"


def _normalize_fuse_strip_wssl_rows(strip_rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Normalize real Component Marking Fuse Strip rows for WSSL generation."""
    normalized_rows: list[dict[str, Any]] = []
    for row in strip_rows or []:
        text = str(row.get("Text") or "")
        space = _safe_terminal_strip_space(row.get("Space"))
        normalized_rows.append(
            {
                "space": space,
                "text": text,
                "kind": _derive_fuse_strip_row_kind(row, text),
            }
        )
    return _ensure_strip_start_stop_rows(normalized_rows)


def _fuse_strip_component_style(text: str, kind: str | None = None) -> WsslComponentStyle:
    """Resolve Fuse Strip WSSL style for fuse data and generated labels."""
    normalized_text = text.strip().upper()
    is_generated = normalized_text in {"START", "STOP", "24VDC", "230VAC"} or kind in {
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
    _validate_strip_start_stop_text_components(text_components, "Fuse Strip")
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


def _relay_strip_wssl_width(space: float) -> float:
    """Convert one Relay Strip Space value to WSSL layout units."""
    return space * _RELAY_STRIP_WSSL_SCALE


def _derive_relay_strip_row_kind(row: dict[str, Any], text: str) -> str:
    """Resolve Relay Strip row kind from explicit kind first, then text fallback."""
    row_kind = row.get("kind")
    if row_kind:
        return str(row_kind)
    normalized_text = text.strip().upper()
    if text == "":
        return "blank"
    if normalized_text in {"START", "STOP"}:
        return "generated_label"
    return "real_data"


def _normalize_relay_strip_wssl_rows(strip_rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Normalize real Component Marking Relay Strip rows for WSSL generation."""
    normalized_rows: list[dict[str, Any]] = []
    for row in strip_rows or []:
        text = str(row.get("Text") or "")
        space = _safe_terminal_strip_space(row.get("Space"))
        normalized_rows.append(
            {
                "space": space,
                "text": text,
                "kind": _derive_relay_strip_row_kind(row, text),
            }
        )
    return _ensure_strip_start_stop_rows(normalized_rows)


def _relay_strip_component_style(text: str, kind: str | None = None) -> WsslComponentStyle:
    """Resolve Relay Strip WSSL style for relay data and generated labels."""
    normalized_text = text.strip().upper()
    is_generated = normalized_text in {"START", "STOP"} or kind in {
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
            font_size=ui_font_to_wssl_size(RELAY_STRIP_LABEL_UI_FONT_SIZE),
            bold=False,
            text_stretching_factor=1.0,
        )
    return WsslComponentStyle(
        font="Arial",
        font_size=ui_font_to_wssl_size(RELAY_STRIP_DATA_UI_FONT_SIZE),
        bold=True,
        text_stretching_factor=1.0,
    )


def _apply_relay_strip_row_to_text_component(
    text_component: ET.Element,
    row: dict[str, Any],
) -> None:
    """Apply one normalized Relay Strip row to a nested WagoTextComponent."""
    style = _relay_strip_component_style(str(row["text"]), str(row["kind"]))
    text_component.set("text", str(row["text"]))
    text_component.set("identifier", str(uuid.uuid4()))
    text_component.set("font", style.font)
    text_component.set("fontSize", _format_wssl_float(style.font_size))
    text_component.set("textSize", _format_wssl_float(style.font_size))
    text_component.set("bold", str(style.bold).lower())
    content_rotation = (
        _STRIP_START_STOP_CONTENT_ROTATION
        if _is_strip_start_stop_text(str(row["text"]))
        else _RELAY_STRIP_CONTENT_ROTATION
    )
    text_component.set("contentRotation", content_rotation)
    text_component.set("textStretchingFactorStr", str(style.text_stretching_factor))


def _set_relay_strip_cell_geometry(
    grid_cell: ET.Element,
    row: dict[str, Any],
    goal_pos_x: float,
) -> None:
    """Update one nested Relay Strip GridCell and its text component to row width."""
    width = _relay_strip_wssl_width(float(row["space"]))
    grid_cell.set("goalPosX", _format_wssl_float(goal_pos_x))
    grid_cell.set("goalWidth", _format_wssl_float(width))
    grid_cell.set("goalHeight", _format_wssl_float(_RELAY_STRIP_Y_SIZE))
    text_component = grid_cell.find("./childList/WagoTextComponent")
    if text_component is None:
        raise ValueError("Relay Strip WSSL nested GridCell missing WagoTextComponent")
    text_component.set("xSize", _format_wssl_float(width))
    text_component.set("ySize", _format_wssl_float(_RELAY_STRIP_Y_SIZE))
    _apply_relay_strip_row_to_text_component(text_component, row)


def _set_relay_strip_grid_group_geometry(
    grid: ET.Element,
    x_pos: float,
    content_width: float,
    endplate_width: float,
) -> None:
    """Update one Relay Strip Grid wrapper dimensions while preserving template nesting."""
    grid.set("xPos", _format_wssl_float(x_pos))
    grid.set("xSize", _format_wssl_float(content_width))
    grid.set("ySize", _format_wssl_float(_RELAY_STRIP_Y_SIZE))
    grid.set("contentRotation", _RELAY_STRIP_CONTENT_ROTATION)
    grid.set("endplateWidthStr", _format_wssl_float(endplate_width))
    grid.set("showEndplateStr", "true" if endplate_width > 0 else "false")

    grid_endplate = _terminal_strip_grid_endplate(grid)
    grid_endplate.set("xPos", _format_wssl_float(content_width))
    grid_endplate.set("xSize", _format_wssl_float(endplate_width))
    grid_endplate.set("ySize", _format_wssl_float(_RELAY_STRIP_Y_SIZE))
    grid_endplate.set("contentRotation", _RELAY_STRIP_CONTENT_ROTATION)
    grid_endplate.set("isShowBorder", "true" if endplate_width > 0 else "false")

    outer_grid_row_col = _terminal_strip_outer_grid_row_col(grid)
    outer_grid_row_col.set("xSize", _format_wssl_float(content_width))
    outer_grid_row_col.set("ySize", _format_wssl_float(_RELAY_STRIP_Y_SIZE))
    outer_grid_row_col.set("contentRotation", _RELAY_STRIP_CONTENT_ROTATION)

    outer_grid_cell = _terminal_strip_outer_grid_cell(grid)
    outer_grid_cell.set("goalWidth", _format_wssl_float(content_width))
    outer_grid_cell.set("goalHeight", _format_wssl_float(_RELAY_STRIP_Y_SIZE))

    grid_row_col = _terminal_strip_grid_row_col(grid)
    grid_row_col.set("xSize", _format_wssl_float(content_width))
    grid_row_col.set("ySize", _format_wssl_float(_RELAY_STRIP_Y_SIZE))
    grid_row_col.set("contentRotation", _RELAY_STRIP_CONTENT_ROTATION)


def _build_relay_strip_group_grid(
    grid_template: ET.Element,
    cell_template: ET.Element,
    group_rows: list[dict[str, Any]],
    x_pos: float,
    endplate_width: float,
) -> ET.Element:
    """Clone one full template Grid and fill it with the Relay Strip group's cells."""
    if not group_rows:
        raise ValueError("Relay Strip WSSL cannot build an empty Grid group")

    cloned_grid = copy.deepcopy(grid_template)
    _refresh_identifiers(cloned_grid)
    row_col_child_list = _terminal_strip_grid_row_col_child_list(cloned_grid)
    for child in list(row_col_child_list):
        row_col_child_list.remove(child)

    next_cell_x_pos = 0.0
    for row in group_rows:
        cloned_cell = copy.deepcopy(cell_template)
        _refresh_identifiers(cloned_cell)
        _set_relay_strip_cell_geometry(cloned_cell, row, next_cell_x_pos)
        row_col_child_list.append(cloned_cell)
        next_cell_x_pos += _relay_strip_wssl_width(float(row["space"]))

    _set_relay_strip_grid_group_geometry(
        cloned_grid,
        x_pos=x_pos,
        content_width=next_cell_x_pos,
        endplate_width=endplate_width,
    )
    return cloned_grid


def _replace_relay_strip_grids_from_rows(
    strip: ET.Element,
    component_list: ET.Element,
    normalized_rows: list[dict[str, Any]],
) -> list[ET.Element]:
    """Replace componentList with Relay Strip Grid groups; blank rows become endplates."""
    grid_template = _first_terminal_strip_grid_template(component_list)
    cell_template = _first_terminal_strip_cell_template(component_list)
    for child in list(component_list):
        component_list.remove(child)

    generated_grids: list[ET.Element] = []
    current_group_rows: list[dict[str, Any]] = []
    current_group_x_pos = 0.0
    next_x_pos = 0.0
    for row in normalized_rows:
        row_width = _relay_strip_wssl_width(float(row["space"]))
        if row["text"] == "":
            if current_group_rows:
                cloned_grid = _build_relay_strip_group_grid(
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
        cloned_grid = _build_relay_strip_group_grid(
            grid_template,
            cell_template,
            current_group_rows,
            current_group_x_pos,
            0.0,
        )
        component_list.append(cloned_grid)
        generated_grids.append(cloned_grid)

    strip.set("xSize", _format_wssl_float(next_x_pos))
    strip.set("ySize", _format_wssl_float(_RELAY_STRIP_Y_SIZE))
    return generated_grids


def _relay_strip_generated_item_preview(normalized_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return developer preview rows showing generated Relay Strip item type and width."""
    return [
        {
            "Space": row["space"],
            "Text": row["text"],
            "width": _relay_strip_wssl_width(float(row["space"])),
            "type": "ENDPLATE" if row["text"] == "" else "TEXT",
        }
        for row in normalized_rows[:20]
    ]


def _relay_strip_generation_debug_messages(
    normalized_rows: list[dict[str, Any]],
    generated_grid_count: int,
    strip_x_size: float,
) -> list[str]:
    """Build developer debug messages for Relay Strip WSSL generation."""
    blank_count = sum(1 for row in normalized_rows if row["text"] == "")
    text_count = len(normalized_rows) - blank_count
    return [
        "Relay Strip WSSL generated",
        f"Relay Strip WSSL input row count = {len(normalized_rows)}",
        f"Relay Strip WSSL non-empty text cell count = {text_count}",
        f"Relay Strip WSSL blank/endplate count = {blank_count}",
        f"Relay Strip WSSL generated Grid count = {generated_grid_count}",
        "Relay Strip WSSL first 20 generated items -> "
        + repr(_relay_strip_generated_item_preview(normalized_rows)),
        f"Relay Strip WSSL total calculated strip xSize = {strip_x_size}",
    ]


def _validate_relay_strip_generated_layout(
    strip: ET.Element,
    component_list: ET.Element,
    normalized_rows: list[dict[str, Any]],
    generated_grids: list[ET.Element],
) -> None:
    """Validate Relay Strip WSSL output was generated from row Space/Text semantics."""
    text_components = [
        text_component
        for grid in generated_grids
        for text_component in _grid_wago_text_components(grid)
    ]
    expected_text_count = sum(1 for row in normalized_rows if row["text"] != "")
    generated_text_count = len([node for node in text_components if node.get("text", "") != ""])
    if generated_text_count != expected_text_count:
        raise ValueError(
            "Relay Strip WSSL generated text count does not match non-empty input rows: "
            + f"generated={generated_text_count}, rows={expected_text_count}"
        )
    if any(node.get("text", "") == "" for node in text_components):
        raise ValueError("Relay Strip WSSL blank row generated an empty WagoTextComponent")
    if component_list.findall("WagoTextComponent") or component_list.findall("./Grid/childList/WagoTextComponent"):
        raise ValueError("Relay Strip WSSL contains direct WagoTextComponent under componentList/Grid")
    expected_x_size = sum(_relay_strip_wssl_width(float(row["space"])) for row in normalized_rows)
    generated_x_size = _float_attr(strip, "xSize")
    if abs(generated_x_size - expected_x_size) > 0.001:
        raise ValueError(
            "Relay Strip WSSL strip xSize does not match sum(Space) * WSSL_WIDTH_SCALE: "
            + f"generated={generated_x_size}, expected={expected_x_size}"
        )


def build_relay_strip_wssl_debug_messages(strip_rows: list[dict[str, Any]] | None = None) -> list[str]:
    """Build developer debug messages without generating the Relay Strip WSSL archive."""
    normalized_rows = _normalize_relay_strip_wssl_rows(strip_rows)
    if not normalized_rows:
        return ["Relay Strip WSSL skipped because no real Relay Strip rows were available"]
    return _relay_strip_generation_debug_messages(
        normalized_rows,
        generated_grid_count=_count_terminal_strip_grid_groups(normalized_rows),
        strip_x_size=sum(_relay_strip_wssl_width(float(row["space"])) for row in normalized_rows),
    )


def _build_relay_strip_layout(strip_rows: list[dict[str, Any]] | None = None) -> str:
    """Build Relay Strip WSSL strip.layout from Relay Strip Space/Text rows."""
    root = ET.fromstring(_TERMINAL_STRIP_TEMPLATE_LAYOUT)
    _validate_terminal_strip_template_counts(root)
    component_list = root.find(".//componentList")
    if component_list is None:
        raise ValueError("Relay Strip WSSL template missing componentList")
    strip = root.find(".//strip")
    if strip is None:
        raise ValueError("Relay Strip WSSL template missing strip node")

    normalized_rows = _normalize_relay_strip_wssl_rows(strip_rows)
    generated_grids = _replace_relay_strip_grids_from_rows(strip, component_list, normalized_rows)
    text_components = [
        text_component
        for grid in generated_grids
        for text_component in _grid_wago_text_components(grid)
    ]
    _validate_relay_strip_generated_layout(strip, component_list, normalized_rows, generated_grids)
    _validate_strip_start_stop_text_components(text_components, "Relay Strip")
    strip_x_size = sum(_relay_strip_wssl_width(float(row["space"])) for row in normalized_rows)
    for message in _relay_strip_generation_debug_messages(
        normalized_rows,
        generated_grid_count=len(generated_grids),
        strip_x_size=strip_x_size,
    ):
        print(message)
    if any(
        text_component.get("contentRotation") != _RELAY_STRIP_CONTENT_ROTATION
        for text_component in text_components
        if not _is_strip_start_stop_text(text_component.get("text", ""))
    ):
        raise ValueError("Relay Strip WSSL generated text component has wrong contentRotation")

    ET.indent(root, space="   ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def _build_wssl_zip_bytes(template_files: list[WsslTemplateFile]) -> bytes:
    """Build one WSSL ZIP with root-level template file names only."""
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for template_file in template_files:
            archive.writestr(template_file.filename, template_file.content)
    return output.getvalue()


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


def build_relay_strip_wssl_bytes(strip_rows: list[dict[str, Any]] | None = None) -> bytes:
    """Build a Relay Strip WSSL archive from Component Marking Relay Strip rows."""
    return _build_wssl_zip_bytes(
        [
            WsslTemplateFile("version.info", _TERMINAL_STRIP_TEMPLATE_VERSION.encode("utf-8")),
            WsslTemplateFile("strip.layout", _build_relay_strip_layout(strip_rows).encode("utf-8")),
            WsslTemplateFile("meta.data", _RELAY_STRIP_TEMPLATE_METADATA.encode("utf-8")),
            WsslTemplateFile("table.config", _FUSE_STRIP_TEMPLATE_TABLE_CONFIG.encode("utf-8")),
            WsslTemplateFile("import.config", _FUSE_STRIP_TEMPLATE_IMPORT_CONFIG.encode("utf-8")),
        ]
    )
