from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite
import re
from typing import Any


_WAGO_TEST_STRIP_ROWS = (
    {"Space": 5.2, "Text": "TEST"},
    {"Space": 5.2, "Text": "WAGO"},
)


@dataclass(frozen=True)
class WagoWscxSettings:
    """Immutable WSCX export settings for one WAGO marking type."""

    marking_type: str
    material_device: str
    font_face: str
    data_bold: bool
    orientation: int
    compress: bool
    blank_cell_width: int | None
    group_label_font_id: str
    generated_label_font_size: int


WAGO_TERMINAL_STRIP_SETTINGS = WagoWscxSettings(
    marking_type="Terminal Strip",
    material_device="2009-110",
    font_face="Arial",
    data_bold=True,
    orientation=90,
    compress=True,
    blank_cell_width=800,
    group_label_font_id="1",
    generated_label_font_size=7,
)

WAGO_FUSE_STRIP_SETTINGS = WagoWscxSettings(
    marking_type="Fuse Strip",
    material_device="210-872",
    font_face="Arial",
    data_bold=True,
    orientation=90,
    compress=True,
    blank_cell_width=None,
    group_label_font_id="1",
    generated_label_font_size=7,
)

_WAGO_STOP_ROW = {"Space": 6.2, "Text": "STOP", "kind": "generated_label"}
_GENERATED_LABEL_PATTERN = re.compile(r"^(?:A\d+|\d+V(?:AC|DC)|TOP|MIDDLE|BOTTOM|STOP)$", re.IGNORECASE)


@dataclass(frozen=True)
class WagoWscxCellStyle:
    """Resolved WSCX style for one strip cell."""

    font_id: str


def _xml_escape(value: Any) -> str:
    """Escape one text value for a WSCX XML text node."""
    return (
        "" if value is None else str(value)
    ).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _space_to_wago_width(space: Any) -> int:
    """Convert one Terminal Strip Space millimeter value to WAGO width units."""
    try:
        numeric_space = float(space)
    except (TypeError, ValueError):
        return 0
    if not isfinite(numeric_space):
        return 0
    return int(round(numeric_space * 1000))


def _build_wago_strip_cell(
    width: int,
    text: Any,
    style: WagoWscxCellStyle,
    settings: WagoWscxSettings,
) -> str:
    """Build one observed-template WAGO StripCell for one Terminal Strip row."""
    compress_value = "True" if settings.compress else "False"
    return (
        "                        <StripCell>\n"
        f"                            <Width>{width}</Width>\n"
        "                            <Content>\n"
        "                                <Type>Text</Type>\n"
        "                                <VerticalAlign>Middle</VerticalAlign>\n"
        "                                <HorizontalAlign>Center</HorizontalAlign>\n"
        "                                <Margin>0</Margin>\n"
        "                                <Proportional>False</Proportional>\n"
        f"                                <Compress>{compress_value}</Compress>\n"
        "                                <Freeze>False</Freeze>\n"
        f"                                <Orientation>{settings.orientation}</Orientation>\n"
        "                                <TextContent>\n"
        f"                                    <String>{_xml_escape(text)}</String>\n"
        f'                                    <Font RefersToID="{style.font_id}" />\n'
        '                                    <Color RefersToID="0" />\n'
        "                                </TextContent>\n"
        "                            </Content>\n"
        "                        </StripCell>"
    )


def _build_wago_strip_row(strip_rows: Iterable[Mapping[str, Any]], settings: WagoWscxSettings) -> str:
    """Build the single WAGO StripRow containing all terminal strip cells."""
    strip_cells = "\n".join(
        _build_wago_strip_cell(strip_row["Width"], strip_row.get("Text", ""), strip_row["Style"], settings)
        for strip_row in strip_rows
    )
    return (
        "                <StripRow>\n"
        "                    <Height>11000</Height>\n"
        "                    <StripCells>\n"
        f"{strip_cells}\n"
        "                    </StripCells>\n"
        "                </StripRow>"
    )


def _build_wago_strip_block(strip_rows: list[dict[str, Any]], settings: WagoWscxSettings) -> str:
    """Build one WAGO StripBlock from ordered Terminal Strip rows."""
    terminal_width = sum(strip_row["Width"] for strip_row in strip_rows)
    return (
        "        <StripBlock>\n"
        "            <Type>Regular</Type>\n"
        f"            <Terminals>{len(strip_rows)}</Terminals>\n"
        f"            <TerminalWidth>{terminal_width}</TerminalWidth>\n"
        "            <StripRows>\n"
        f"{_build_wago_strip_row(strip_rows, settings)}\n"
        "            </StripRows>\n"
        "        </StripBlock>"
    )


def _resolve_wago_label_kind(strip_row: Mapping[str, Any]) -> str:
    """Classify one WAGO row as blank, generated label, or real marking data."""
    row_kind = strip_row.get("kind")
    if row_kind in {"group_label", "section_label", "generated_label"}:
        return "generated_label"
    text = str(strip_row.get("Text", "")).strip()
    if text == "":
        return "blank"
    if row_kind is not None:
        return "real_data"
    if _GENERATED_LABEL_PATTERN.match(text):
        return "generated_label"
    return "real_data"


def _resolve_wscx_cell_style(strip_row: Mapping[str, Any], settings: WagoWscxSettings) -> WagoWscxCellStyle:
    """Resolve WSCX cell font and character spacing for one export type."""
    label_kind = _resolve_wago_label_kind(strip_row)
    if label_kind != "real_data":
        return WagoWscxCellStyle(font_id=settings.group_label_font_id)
    return WagoWscxCellStyle(font_id="0")


def _wago_strip_row_width(strip_row: Mapping[str, Any], settings: WagoWscxSettings) -> int:
    """Choose the WAGO width for one generated strip row."""
    if settings.blank_cell_width is not None and _xml_escape(strip_row.get("Text", "")) == "":
        return settings.blank_cell_width
    return _space_to_wago_width(strip_row.get("Space"))


def _with_final_wago_stop_row(strip_rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Keep one WAGO STOP marker at the end of the flattened strip."""
    rows_without_stop = [
        strip_row
        for strip_row in strip_rows
        if str(strip_row.get("Text", "")).strip().upper() != "STOP"
    ]
    return [*rows_without_stop, _WAGO_STOP_ROW]


def _normalize_wago_strip_row(strip_row: Mapping[str, Any], settings: WagoWscxSettings) -> dict[str, Any]:
    """Prepare one final Terminal Strip Space/Text row for WSCX output."""
    return {
        "Width": _wago_strip_row_width(strip_row, settings),
        "Text": strip_row.get("Text", ""),
        "Style": _resolve_wscx_cell_style(strip_row, settings),
    }


def _build_wago_text_attributes(settings: WagoWscxSettings) -> str:
    """Build the observed WAGO font/color attributes used by terminal strip text."""
    data_bold_value = "True" if settings.data_bold else "False"
    return f"""    <TextAttributes>
        <Fonts>
            <Font ID="0">
                <FaceName>{_xml_escape(settings.font_face)}</FaceName>
                <Height>2910</Height>
                <Width>800</Width>
                <Italic>False</Italic>
                <Bold>{data_bold_value}</Bold>
                <Underline>False</Underline>
                <StrikeOut>False</StrikeOut>
                <PitchAndFamily>0x00000002</PitchAndFamily>
                <CharSet>1</CharSet>
                <Plotter>False</Plotter>
            </Font>
            <Font ID="1">
                <FaceName>{_xml_escape(settings.font_face)}</FaceName>
                <Height>{settings.generated_label_font_size * 100}</Height>
                <Width>800</Width>
                <Italic>False</Italic>
                <Bold>False</Bold>
                <Underline>False</Underline>
                <StrikeOut>False</StrikeOut>
                <PitchAndFamily>0x00000002</PitchAndFamily>
                <CharSet>1</CharSet>
                <Plotter>False</Plotter>
            </Font>
            <Font ID="2">
                <FaceName>{_xml_escape(settings.font_face)}</FaceName>
                <Height>{settings.generated_label_font_size * 100}</Height>
                <Width>800</Width>
                <Italic>False</Italic>
                <Bold>False</Bold>
                <Underline>False</Underline>
                <StrikeOut>False</StrikeOut>
                <PitchAndFamily>0x00000002</PitchAndFamily>
                <CharSet>1</CharSet>
                <Plotter>False</Plotter>
            </Font>
            <Font ID="3">
                <FaceName>{_xml_escape(settings.font_face)}</FaceName>
                <Height>4000</Height>
                <Width>800</Width>
                <Italic>False</Italic>
                <Bold>False</Bold>
                <Underline>False</Underline>
                <StrikeOut>False</StrikeOut>
                <PitchAndFamily>0x00000002</PitchAndFamily>
                <CharSet>1</CharSet>
                <Plotter>False</Plotter>
            </Font>
        </Fonts>
        <Colors>
            <Color Format="RGB" ID="0">0x000000</Color>
        </Colors>
    </TextAttributes>"""


def build_wago_wscx_bytes(
    strip_rows: Iterable[Mapping[str, Any]] | None = None,
    *,
    settings: WagoWscxSettings | None = None,
    marking_type: str = "Terminal Strip",
    marking_material: str = "2009-110",
    append_stop: bool = True,
) -> bytes:
    """Build UTF-8 WAGO SmartScript XML from one flat final strip row list."""
    if settings is not None:
        active_settings = settings
    elif marking_type == WAGO_FUSE_STRIP_SETTINGS.marking_type:
        active_settings = WAGO_FUSE_STRIP_SETTINGS
    elif marking_type == WAGO_TERMINAL_STRIP_SETTINGS.marking_type and marking_material == WAGO_TERMINAL_STRIP_SETTINGS.material_device:
        active_settings = WAGO_TERMINAL_STRIP_SETTINGS
    else:
        active_settings = WagoWscxSettings(
            marking_type=marking_type,
            material_device=marking_material,
            font_face="Arial",
            data_bold=True,
            orientation=90,
            compress=True,
            blank_cell_width=800 if marking_type == "Terminal Strip" else None,
            group_label_font_id="1",
            generated_label_font_size=7,
        )
    provided_rows = list(strip_rows) if strip_rows is not None else []
    rows = provided_rows if provided_rows else list(_WAGO_TEST_STRIP_ROWS)
    rows_for_output = _with_final_wago_stop_row(rows) if append_stop else rows
    normalized_rows = [
        _normalize_wago_strip_row(strip_row, active_settings)
        for strip_row in rows_for_output
    ]
    wscx_text = (
        '<?xml version="1.0" encoding="utf-8" ?>\n'
        "<ContinuousStrip>\n"
        "    <Height>11000</Height>\n"
        f"    <MetaInfo>{_xml_escape(active_settings.material_device)}</MetaInfo>\n"
        "    <StripBlocks>\n"
        "        <Distance>0</Distance>\n"
        f"{_build_wago_strip_block(normalized_rows, active_settings)}\n"
        "    </StripBlocks>\n"
        f"{_build_wago_text_attributes(active_settings)}\n"
        f"    <Device>{_xml_escape(active_settings.material_device)}</Device>\n"
        "</ContinuousStrip>\n"
    )
    return wscx_text.encode("utf-8")
