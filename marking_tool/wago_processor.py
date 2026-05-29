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
class WagoWscxFontDefinition:
    """One WSCX font definition available to an output profile."""

    font_id: str
    height: int
    width: int
    bold: bool


@dataclass(frozen=True)
class WagoWscxDataFontRule:
    """Map real-data text length to one profile-local WSCX font."""

    font_id: str
    min_length: int


@dataclass(frozen=True)
class WagoWscxProfile:
    """Immutable WSCX export settings for one WAGO marking type."""

    marking_type: str
    format_name: str
    material_device: str
    data_font_face: str
    data_font_bold: bool
    font_definitions: tuple[WagoWscxFontDefinition, ...]
    data_font_rules: tuple[WagoWscxDataFontRule, ...]
    orientation: int
    compress: bool
    terminal_strip_blank_cell_width: int | None
    fuse_strip_blank_cell_width_policy: str | None
    generated_label_font_id: str
    wscx_generated_label_font_height: int


TERMINAL_STRIP_WSCX_SETTINGS = WagoWscxProfile(
    marking_type="Terminal Strip",
    format_name="WSCX",
    material_device="2009-110",
    data_font_face="Arial",
    data_font_bold=True,
    font_definitions=(
        WagoWscxFontDefinition(font_id="0", height=1000, width=1000, bold=True),
        WagoWscxFontDefinition(font_id="4", height=1000, width=900, bold=True),
        WagoWscxFontDefinition(font_id="5", height=1000, width=700, bold=True),
        WagoWscxFontDefinition(font_id="1", height=700, width=1000, bold=False),
        WagoWscxFontDefinition(font_id="2", height=700, width=1000, bold=False),
        WagoWscxFontDefinition(font_id="3", height=4000, width=800, bold=False),
    ),
    data_font_rules=(
        WagoWscxDataFontRule(font_id="5", min_length=7),
        WagoWscxDataFontRule(font_id="4", min_length=6),
        WagoWscxDataFontRule(font_id="0", min_length=0),
    ),
    orientation=90,
    compress=True,
    terminal_strip_blank_cell_width=800,
    fuse_strip_blank_cell_width_policy=None,
    generated_label_font_id="1",
    wscx_generated_label_font_height=700,
)

FUSE_STRIP_WSCX_SETTINGS = WagoWscxProfile(
    marking_type="Fuse Strip",
    format_name="WSCX",
    material_device="210-872",
    data_font_face="Arial",
    data_font_bold=True,
    font_definitions=(
        WagoWscxFontDefinition(font_id="0", height=2910, width=800, bold=True),
        WagoWscxFontDefinition(font_id="1", height=700, width=800, bold=False),
        WagoWscxFontDefinition(font_id="2", height=700, width=800, bold=False),
        WagoWscxFontDefinition(font_id="3", height=4000, width=800, bold=False),
    ),
    data_font_rules=(
        WagoWscxDataFontRule(font_id="0", min_length=0),
    ),
    orientation=270,
    compress=True,
    terminal_strip_blank_cell_width=None,
    fuse_strip_blank_cell_width_policy="space_column",
    generated_label_font_id="1",
    wscx_generated_label_font_height=700,
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
    profile: WagoWscxProfile,
) -> str:
    """Build one observed-template WAGO StripCell for one Terminal Strip row."""
    compress_value = "True" if profile.compress else "False"
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
        f"                                <Orientation>{profile.orientation}</Orientation>\n"
        "                                <TextContent>\n"
        f"                                    <String>{_xml_escape(text)}</String>\n"
        f'                                    <Font RefersToID="{style.font_id}" />\n'
        '                                    <Color RefersToID="0" />\n'
        "                                </TextContent>\n"
        "                            </Content>\n"
        "                        </StripCell>"
    )


def _build_wago_strip_row(strip_rows: Iterable[Mapping[str, Any]], profile: WagoWscxProfile) -> str:
    """Build the single WAGO StripRow containing all terminal strip cells."""
    strip_cells = "\n".join(
        _build_wago_strip_cell(strip_row["Width"], strip_row.get("Text", ""), strip_row["Style"], profile)
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


def _build_wago_strip_block(strip_rows: list[dict[str, Any]], profile: WagoWscxProfile) -> str:
    """Build one WAGO StripBlock from ordered Terminal Strip rows."""
    terminal_width = sum(strip_row["Width"] for strip_row in strip_rows)
    return (
        "        <StripBlock>\n"
        "            <Type>Regular</Type>\n"
        f"            <Terminals>{len(strip_rows)}</Terminals>\n"
        f"            <TerminalWidth>{terminal_width}</TerminalWidth>\n"
        "            <StripRows>\n"
        f"{_build_wago_strip_row(strip_rows, profile)}\n"
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


def _resolve_wscx_cell_style(strip_row: Mapping[str, Any], profile: WagoWscxProfile) -> WagoWscxCellStyle:
    """Resolve WSCX cell font and character spacing for one export type."""
    label_kind = _resolve_wago_label_kind(strip_row)
    if label_kind != "real_data":
        return WagoWscxCellStyle(font_id=profile.generated_label_font_id)
    text_length = len(str(strip_row.get("Text", "")))
    for font_rule in profile.data_font_rules:
        if text_length >= font_rule.min_length:
            return WagoWscxCellStyle(font_id=font_rule.font_id)
    return WagoWscxCellStyle(font_id=profile.data_font_rules[-1].font_id)


def _wago_strip_row_width(strip_row: Mapping[str, Any], profile: WagoWscxProfile) -> int:
    """Choose the WAGO width for one generated strip row."""
    if profile.terminal_strip_blank_cell_width is not None and _xml_escape(strip_row.get("Text", "")) == "":
        return profile.terminal_strip_blank_cell_width
    return _space_to_wago_width(strip_row.get("Space"))


def _with_final_wago_stop_row(strip_rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Keep one WAGO STOP marker at the end of the flattened strip."""
    rows_without_stop = [
        strip_row
        for strip_row in strip_rows
        if str(strip_row.get("Text", "")).strip().upper() != "STOP"
    ]
    return [*rows_without_stop, _WAGO_STOP_ROW]


def _normalize_wago_strip_row(strip_row: Mapping[str, Any], profile: WagoWscxProfile) -> dict[str, Any]:
    """Prepare one final Terminal Strip Space/Text row for WSCX output."""
    return {
        "Width": _wago_strip_row_width(strip_row, profile),
        "Text": strip_row.get("Text", ""),
        "Style": _resolve_wscx_cell_style(strip_row, profile),
    }


def _build_wago_text_attributes(profile: WagoWscxProfile) -> str:
    """Build the observed WAGO font/color attributes used by terminal strip text."""
    font_definitions = "\n".join(
        (
            f'            <Font ID="{_xml_escape(font_definition.font_id)}">\n'
            f"                <FaceName>{_xml_escape(profile.data_font_face)}</FaceName>\n"
            f"                <Height>{font_definition.height}</Height>\n"
            f"                <Width>{font_definition.width}</Width>\n"
            "                <Italic>False</Italic>\n"
            f"                <Bold>{'True' if font_definition.bold else 'False'}</Bold>\n"
            "                <Underline>False</Underline>\n"
            "                <StrikeOut>False</StrikeOut>\n"
            "                <PitchAndFamily>0x00000002</PitchAndFamily>\n"
            "                <CharSet>1</CharSet>\n"
            "                <Plotter>False</Plotter>\n"
            "            </Font>"
        )
        for font_definition in profile.font_definitions
    )
    return f"""    <TextAttributes>
        <Fonts>
{font_definitions}
        </Fonts>
        <Colors>
            <Color Format="RGB" ID="0">0x000000</Color>
        </Colors>
    </TextAttributes>"""


def _build_wago_wscx_bytes(
    strip_rows: Iterable[Mapping[str, Any]] | None = None,
    *,
    profile: WagoWscxProfile,
    append_stop: bool = True,
) -> bytes:
    """Build UTF-8 WAGO SmartScript XML from one flat final strip row list."""
    provided_rows = list(strip_rows) if strip_rows is not None else []
    rows = provided_rows if provided_rows else list(_WAGO_TEST_STRIP_ROWS)
    rows_for_output = _with_final_wago_stop_row(rows) if append_stop else rows
    normalized_rows = [
        _normalize_wago_strip_row(strip_row, profile)
        for strip_row in rows_for_output
    ]
    wscx_text = (
        '<?xml version="1.0" encoding="utf-8" ?>\n'
        "<ContinuousStrip>\n"
        "    <Height>11000</Height>\n"
        f"    <MetaInfo>{_xml_escape(profile.material_device)}</MetaInfo>\n"
        "    <StripBlocks>\n"
        "        <Distance>0</Distance>\n"
        f"{_build_wago_strip_block(normalized_rows, profile)}\n"
        "    </StripBlocks>\n"
        f"{_build_wago_text_attributes(profile)}\n"
        f"    <Device>{_xml_escape(profile.material_device)}</Device>\n"
        "</ContinuousStrip>\n"
    )
    return wscx_text.encode("utf-8")


def build_terminal_strip_wscx_bytes(strip_rows: Iterable[Mapping[str, Any]] | None = None) -> bytes:
    """Build production Terminal Strip WSCX using its isolated profile."""
    return _build_wago_wscx_bytes(strip_rows, profile=TERMINAL_STRIP_WSCX_SETTINGS)


def build_fuse_strip_wscx_bytes(strip_rows: Iterable[Mapping[str, Any]] | None = None) -> bytes:
    """Build production Fuse Strip WSCX using its isolated profile."""
    return _build_wago_wscx_bytes(strip_rows, profile=FUSE_STRIP_WSCX_SETTINGS)
