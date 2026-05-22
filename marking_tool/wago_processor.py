from __future__ import annotations

from collections.abc import Iterable, Mapping
from math import isfinite
from typing import Any


_WAGO_TEST_STRIP_ROWS = (
    {"Space": 5.2, "Text": "TEST"},
    {"Space": 5.2, "Text": "WAGO"},
)
_WAGO_GROUP_SEPARATOR_WIDTH = 5200
_WAGO_STOP_ROW = {"Space": 6.2, "Text": "STOP", "kind": "normal"}


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


def _build_wago_strip_cell(width: int, text: Any, font_id: str) -> str:
    """Build one observed-template WAGO StripCell for one Terminal Strip row."""
    return (
        "                        <StripCell>\n"
        f"                            <Width>{width}</Width>\n"
        "                            <Content>\n"
        "                                <Type>Text</Type>\n"
        "                                <VerticalAlign>Middle</VerticalAlign>\n"
        "                                <HorizontalAlign>Center</HorizontalAlign>\n"
        "                                <Margin>0</Margin>\n"
        "                                <Proportional>False</Proportional>\n"
        "                                <Compress>True</Compress>\n"
        "                                <Freeze>False</Freeze>\n"
        "                                <Orientation>90</Orientation>\n"
        "                                <TextContent>\n"
        f"                                    <String>{_xml_escape(text)}</String>\n"
        f'                                    <Font RefersToID="{font_id}" />\n'
        '                                    <Color RefersToID="0" />\n'
        "                                </TextContent>\n"
        "                            </Content>\n"
        "                        </StripCell>"
    )


def _build_wago_strip_row(strip_rows: Iterable[Mapping[str, Any]]) -> str:
    """Build the single WAGO StripRow containing all terminal strip cells."""
    strip_cells = "\n".join(
        _build_wago_strip_cell(strip_row["Width"], strip_row.get("Text", ""), strip_row["FontID"])
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


def _build_wago_strip_block(strip_rows: list[dict[str, Any]]) -> str:
    """Build one WAGO StripBlock from ordered Terminal Strip rows."""
    terminal_width = sum(strip_row["Width"] for strip_row in strip_rows)
    return (
        "        <StripBlock>\n"
        "            <Type>Regular</Type>\n"
        f"            <Terminals>{len(strip_rows)}</Terminals>\n"
        f"            <TerminalWidth>{terminal_width}</TerminalWidth>\n"
        "            <StripRows>\n"
        f"{_build_wago_strip_row(strip_rows)}\n"
        "            </StripRows>\n"
        "        </StripBlock>"
    )


def _wago_strip_row_font_id(strip_row: Mapping[str, Any], marking_type: str) -> str:
    """Choose the WAGO text attribute for one generated strip row."""
    row_kind = strip_row.get("kind")
    if row_kind == "group_label" and marking_type == "Fuse Strip":
        return "2"
    if row_kind in {"group_label", "blank_separator"}:
        return "1"
    return "0"


def _wago_strip_row_width(strip_row: Mapping[str, Any]) -> int:
    """Use a wider WAGO gap for generated logical-group separators."""
    if strip_row.get("kind") == "blank_separator":
        return _WAGO_GROUP_SEPARATOR_WIDTH
    return _space_to_wago_width(strip_row.get("Space"))


def _with_final_wago_stop_row(strip_rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Keep one WAGO STOP marker at the end of the flattened strip."""
    rows_without_stop = [
        strip_row
        for strip_row in strip_rows
        if str(strip_row.get("Text", "")).strip().upper() != "STOP"
    ]
    return [*rows_without_stop, _WAGO_STOP_ROW]


def _normalize_wago_strip_row(strip_row: Mapping[str, Any], marking_type: str) -> dict[str, Any]:
    """Prepare one final Terminal Strip Space/Text row for WSCX output."""
    return {
        "Width": _wago_strip_row_width(strip_row),
        "Text": strip_row.get("Text", ""),
        "FontID": _wago_strip_row_font_id(strip_row, marking_type),
    }


def _build_wago_text_attributes() -> str:
    """Build the observed WAGO font/color attributes used by terminal strip text."""
    return """    <TextAttributes>
        <Fonts>
            <Font ID="0">
                <FaceName>Arial</FaceName>
                <Height>2910</Height>
                <Width>800</Width>
                <Italic>False</Italic>
                <Bold>True</Bold>
                <Underline>False</Underline>
                <StrikeOut>False</StrikeOut>
                <PitchAndFamily>0x00000002</PitchAndFamily>
                <CharSet>1</CharSet>
                <Plotter>False</Plotter>
            </Font>
            <Font ID="1">
                <FaceName>Arial</FaceName>
                <Height>500</Height>
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
                <FaceName>Arial</FaceName>
                <Height>2500</Height>
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
    marking_type: str = "Terminal Strip",
    marking_material: str = "2009-110",
) -> bytes:
    """Build UTF-8 WAGO SmartScript XML from one flat final strip row list."""
    provided_rows = list(strip_rows) if strip_rows is not None else []
    rows = provided_rows if provided_rows else list(_WAGO_TEST_STRIP_ROWS)
    normalized_rows = [
        _normalize_wago_strip_row(strip_row, marking_type)
        for strip_row in _with_final_wago_stop_row(rows)
    ]
    wscx_text = (
        '<?xml version="1.0" encoding="utf-8" ?>\n'
        "<ContinuousStrip>\n"
        "    <Height>11000</Height>\n"
        f"    <MetaInfo>{_xml_escape(marking_material)}</MetaInfo>\n"
        "    <StripBlocks>\n"
        "        <Distance>0</Distance>\n"
        f"{_build_wago_strip_block(normalized_rows)}\n"
        "    </StripBlocks>\n"
        f"{_build_wago_text_attributes()}\n"
        f"    <Device>{_xml_escape(marking_type)}</Device>\n"
        "</ContinuousStrip>\n"
    )
    return wscx_text.encode("utf-8")
