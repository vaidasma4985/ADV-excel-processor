from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
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
_FUSE_STRIP_CONTENT_ROTATION = "270.0"

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
_TERMINAL_STRIP_PLACEHOLDER_TEMPLATE_ERROR = (
    "Embedded Terminal Strip WSSL template is still placeholder/wrong. "
    "Replace it with full real strip.layout from 2605-078 terminal strip template.wssl."
)

_TERMINAL_STRIP_TEMPLATE_VERSION = r"""<?xml version="1.0" encoding="UTF-8"?>

<Version version="4.9.5.2"/>

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


def _safe_terminal_strip_space(value: Any) -> float:
    """Normalize one WAGO Space value for Terminal Strip WSSL diagnostics."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


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


def _build_wssl_zip_bytes(template_files: list[WsslTemplateFile]) -> bytes:
    """Build one WSSL ZIP with root-level template file names only."""
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for template_file in template_files:
            archive.writestr(template_file.filename, template_file.content)
    return output.getvalue()

