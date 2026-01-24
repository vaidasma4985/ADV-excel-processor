from __future__ import annotations

from collections import defaultdict
import heapq
import re
from typing import Any, Dict, Iterable, List, Set, Tuple

import pandas as pd

Node = str
Issue = Dict[str, Any]
VirtualLink = Dict[str, Any]
VirtualEdge = Dict[Tuple[Node, Node], Dict[str, Any]]


_MAIN_ROOT_PATTERN = re.compile(r"^(MT2|LT2|MT|IT|LT)/(L1|L2|L3|N)$")
_SUB_ROOT_PATTERN = re.compile(r"^F\d+/(L1|L2|L3|N)$")
_ROOT_TOKEN_PATTERN = re.compile(r"(MT2|LT2|MT|IT|LT|F\d+)/(L1|L2|L3|N)")
_PASS_THROUGH_PAIRS = (
    ("1", "2"),
    ("3", "4"),
    ("5", "6"),
    ("7", "8"),
    ("9", "10"),
    ("11", "12"),
    ("13", "14"),
    ("21", "22"),
    ("31", "32"),
    ("41", "42"),
    ("N", "N'"),
    ("N", "7N"),
    ("7N", "N'"),
)
_VIRTUAL_LINK_TYPE = "GV2AF3"
_VIRTUAL_EDGE_WEIGHT = 10
_IMAGE_COLUMNS = (
    "Image",
    "Image path",
    "Image Path",
    "ImagePath",
    "Image File",
    "ImageFile",
    "ImageFilePath",
)


def _is_missing(value: Any) -> bool:
    if value is None or pd.isna(value):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _issue(
    severity: str,
    code: str,
    message: str,
    row_index: Any | None = None,
    context: Dict[str, Any] | None = None,
) -> Issue:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "row_index": row_index,
        "context": context or {},
    }


def _normalize_wireno(value: Any) -> str | None:
    if _is_missing(value):
        return None
    normalized = str(value).strip().replace(" ", "")
    return normalized or None


def _normalize_terminal(value: Any) -> str | None:
    if _is_missing(value):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    normalized = str(value).strip().upper()
    normalized = (
        normalized.replace("’", "'")
        .replace("‘", "'")
        .replace("`", "'")
        .replace("´", "'")
    )
    if not normalized:
        return None
    if re.fullmatch(r"\d+", normalized):
        return normalized
    return normalized


def _normalize_name(value: Any) -> str | None:
    if _is_missing(value):
        return None
    return str(value).strip() or None


def _device_node(name: Any, cp: Any) -> Node | None:
    name_str = _normalize_name(name)
    if not name_str:
        return None
    cp_str = _normalize_terminal(cp)
    if not cp_str:
        return None
    return f"{name_str}:{cp_str}"


def _device_name(node: Node) -> str:
    return node.split(":", 1)[0]


def _is_net_node(node: Node) -> bool:
    return node.startswith("NET:")


def _net_name(node: Node) -> str:
    return node.replace("NET:", "", 1)


def _strip_contact_suffix(name: str) -> str:
    return name.split(":", 1)[0]


def _logical_base_name(name: str) -> str:
    if re.search(r"\.\d+$", name):
        return name.rsplit(".", 1)[0]
    return name


def _base_device_name(name: Any) -> str | None:
    name_str = _normalize_name(name)
    if not name_str:
        return None
    return _strip_contact_suffix(name_str)


def _base_of(name: Any) -> str | None:
    return _base_device_name(name)


def _part_suffix(name: str) -> str | None:
    if "." not in name:
        return None
    base, suffix = name.rsplit(".", 1)
    if not base or not suffix:
        return None
    return suffix


def _part_base(name: str) -> str:
    if "." not in name:
        return name
    return name.rsplit(".", 1)[0]


def _extract_root_tokens(wireno: str | None) -> List[str]:
    if not wireno:
        return []
    return [f"{match[0]}/{match[1]}" for match in _ROOT_TOKEN_PATTERN.findall(wireno)]


def _is_root_or_subroot_token(token: str) -> bool:
    return bool(_SUB_ROOT_PATTERN.match(token) or _MAIN_ROOT_PATTERN.match(token))


def _extract_root_chain_nets(path: List[Node]) -> List[str]:
    root_chain: List[str] = []
    last_token: str | None = None
    for node in path:
        if not _is_net_node(node):
            continue
        token = _net_name(node)
        if not _is_root_or_subroot_token(token):
            continue
        if token == last_token:
            continue
        root_chain.append(token)
        last_token = token
    return root_chain


def _is_virtual_link_row(wireno: str | None, type_a: str | None, type_b: str | None) -> bool:
    """GV2AF3 adapter rows represent continuity links without wires."""
    return not wireno and _VIRTUAL_LINK_TYPE in {type_a, type_b}


def _extract_image_value(row: pd.Series, suffix: str) -> str | None:
    for base in _IMAGE_COLUMNS:
        key = f"{base}{suffix}"
        if key not in row:
            continue
        value = row.get(key)
        if _is_missing(value):
            continue
        return str(value).strip()
    return None


def build_simplified_chain_items(
    path: List[Node],
    feeder_end_name: str,
) -> List[str]:
    items: List[str] = []
    for node in path:
        if _is_net_node(node):
            token = _net_name(node)
            if _is_root_or_subroot_token(token):
                items.append(token)
            continue
        items.append(_device_name(node))

    chain: List[str] = []
    for item in items:
        if chain and chain[-1] == item:
            continue
        chain.append(item)

    if not chain or chain[0] != feeder_end_name:
        chain.insert(0, feeder_end_name)

    return chain


def _extract_wireno_tokens(wireno: str | None) -> List[str]:
    if not wireno:
        return []
    tokens = [token for token in re.split(r"[;,]", wireno) if token]
    return [token.strip() for token in tokens if token.strip()]


def _is_front_terminal(term: str | None) -> bool:
    if not term:
        return False
    if term.isdigit():
        return int(term) % 2 == 1
    return _neutral_kind(term) == "front"


def _is_bus_token(token: str) -> bool:
    return bool(_MAIN_ROOT_PATTERN.match(token) or _SUB_ROOT_PATTERN.match(token))


def identify_root_devices(adjacency: Dict[Node, Set[Node]]) -> Set[str]:
    """Return device names that touch main root nets (MT/MT2/IT/LT/LT2)."""
    root_devices: Set[str] = set()
    for node, neighbors in adjacency.items():
        if not _is_net_node(node):
            continue
        if not _MAIN_ROOT_PATTERN.match(_net_name(node)):
            continue
        for nb in neighbors:
            if _is_net_node(nb):
                continue
            root_devices.add(_device_name(nb))
    return root_devices


def build_graph(
    df_power: pd.DataFrame,
    device_templates: Dict[str, Dict[str, Any]] | None = None,
) -> Tuple[
    Dict[Node, Set[Node]],
    List[Issue],
    Dict[str, Set[str]],
    Dict[str, Set[str]],
    Dict[str, int],
    List[VirtualLink],
    VirtualEdge,
]:
    adjacency: Dict[Node, Set[Node]] = {}
    issues: List[Issue] = []
    device_terminals: Dict[str, Set[str]] = defaultdict(set)
    device_parts: Dict[str, Set[str]] = defaultdict(set)
    device_nets: Dict[str, Set[str]] = defaultdict(set)
    wired_between_parts: Set[str] = set()
    direct_device_edges: Set[frozenset[str]] = set()

    # BUS / NET hub threshold:
    # Net token is treated as a "bus" only if it connects to >= 4 device pins.
    # This reduces false bus detection and prevents path "jumps".
    BUS_HUB_DEGREE_THRESHOLD = 4

    parsed_rows: List[Dict[str, Any]] = []
    net_pin_degree: Dict[str, Set[Node]] = defaultdict(set)
    virtual_links: List[VirtualLink] = []
    virtual_edges: VirtualEdge = {}

    # Pass 1: parse + collect stats (no edges yet)
    for row_index, row in df_power.iterrows():
        wireno = _normalize_wireno(row.get("Wireno"))
        wireno_tokens = _extract_wireno_tokens(wireno)
        type_a = _normalize_name(row.get("Type"))
        type_b = _normalize_name(row.get("Type.1"))

        name_a_raw = _normalize_name(row.get("Name"))
        name_b_raw = _normalize_name(row.get("Name.1"))
        name_a = _base_of(name_a_raw)
        cp_a = _normalize_terminal(row.get("C.name"))
        name_b = _base_of(name_b_raw)
        cp_b = _normalize_terminal(row.get("C.name.1"))

        if _is_virtual_link_row(wireno, type_a, type_b):
            link = {
                "from_name_raw": name_a_raw,
                "from_pin": cp_a,
                "from_type": type_a,
                "from_image": _extract_image_value(row, ""),
                "to_name_raw": name_b_raw,
                "to_pin": cp_b,
                "to_type": type_b,
                "to_image": _extract_image_value(row, ".1"),
                "original_row_index": row_index,
            }
            virtual_links.append(link)
            from_node = _device_node(name_a_raw, cp_a)
            to_node = _device_node(name_b_raw, cp_b)
            if from_node and to_node:
                virtual_edges[(from_node, to_node)] = {
                    "edge_type": "virtual",
                    "virtual_type": type_a or type_b or _VIRTUAL_LINK_TYPE,
                    "original_row_index": row_index,
                    "from_image": link["from_image"],
                    "to_image": link["to_image"],
                    "weight": _VIRTUAL_EDGE_WEIGHT,
                }
                adjacency.setdefault(from_node, set()).add(to_node)
                adjacency.setdefault(to_node, set())
            if name_a_raw and cp_a:
                device_terminals[name_a_raw].add(cp_a)
            if name_b_raw and cp_b:
                device_terminals[name_b_raw].add(cp_b)
            if name_a_raw:
                device_parts[_logical_base_name(name_a_raw)].add(name_a_raw)
            if name_b_raw:
                device_parts[_logical_base_name(name_b_raw)].add(name_b_raw)
            continue

        from_node = _device_node(name_a, cp_a)
        to_node = _device_node(name_b, cp_b)

        parsed_rows.append(
            {
                "row_index": row_index,
                "wireno": row.get("Wireno"),
                "wireno_tokens": wireno_tokens,
                "name_a_raw": name_a_raw,
                "name_b_raw": name_b_raw,
                "name_a": name_a,
                "cp_a": cp_a,
                "name_b": name_b,
                "cp_b": cp_b,
                "from_node": from_node,
                "to_node": to_node,
            }
        )

        if name_a and cp_a:
            device_terminals[name_a].add(cp_a)
        if name_b and cp_b:
            device_terminals[name_b].add(cp_b)
        if name_a_raw and name_a:
            device_parts[_logical_base_name(name_a)].add(name_a)
        if name_b_raw and name_b:
            device_parts[_logical_base_name(name_b)].add(name_b)

        if name_a_raw and name_b_raw:
            part_a_suffix = _part_suffix(name_a_raw)
            part_b_suffix = _part_suffix(name_b_raw)
            if (
                part_a_suffix
                and part_b_suffix
                and part_a_suffix != part_b_suffix
                and _part_base(name_a_raw) == _part_base(name_b_raw)
            ):
                wired_between_parts.add(_part_base(name_a_raw))
                direct_device_edges.add(frozenset({name_a_raw, name_b_raw}))
            if name_a_raw != name_b_raw:
                direct_device_edges.add(frozenset({name_a_raw, name_b_raw}))

        if wireno_tokens:
            if name_a_raw:
                device_nets[name_a_raw].update(wireno_tokens)
            if name_b_raw:
                device_nets[name_b_raw].update(wireno_tokens)

        # net degree counts (unique device pins connected to token)
        for token in wireno_tokens:
            if from_node:
                net_pin_degree[token].add(from_node)
            if to_node:
                net_pin_degree[token].add(to_node)

    bus_tokens_active: Set[str] = {
        token
        for token, pins in net_pin_degree.items()
        if _is_bus_token(token) and len(pins) >= BUS_HUB_DEGREE_THRESHOLD
    }

    # Pass 2: build graph edges
    for entry in parsed_rows:
        row_index = entry["row_index"]
        wireno_tokens: List[str] = entry["wireno_tokens"]
        name_a_raw = entry["name_a_raw"]
        name_b_raw = entry["name_b_raw"]
        cp_a = entry["cp_a"]
        cp_b = entry["cp_b"]
        from_node: Node | None = entry["from_node"]
        to_node: Node | None = entry["to_node"]

        if not from_node and not to_node:
            issues.append(
                _issue(
                    "ERROR",
                    "W201",
                    "Missing endpoint data for Power row; no device nodes created.",
                    row_index=row_index,
                    context={
                        "wireno": entry.get("wireno"),
                        "from_name": name_a_raw,
                        "to_name": name_b_raw,
                    },
                )
            )
            continue

        nodes = [node for node in (from_node, to_node) if node]
        for node in nodes:
            adjacency.setdefault(node, set())

        if from_node and to_node:
            suppress_direct = False
            if wireno_tokens and _is_front_terminal(cp_a) and _is_front_terminal(cp_b):
                suppress_direct = any(token in bus_tokens_active for token in wireno_tokens)
            if not suppress_direct:
                adjacency[from_node].add(to_node)
                adjacency[to_node].add(from_node)

        for token in wireno_tokens:
            net_node = f"NET:{token}"
            adjacency.setdefault(net_node, set())
            if from_node:
                adjacency[net_node].add(from_node)
                adjacency[from_node].add(net_node)
            if to_node:
                adjacency[net_node].add(to_node)
                adjacency[to_node].add(net_node)

    for device_name, terminals in device_terminals.items():
        for left, right in _PASS_THROUGH_PAIRS:
            if left in terminals and right in terminals:
                node_left = f"{device_name}:{left}"
                node_right = f"{device_name}:{right}"
                adjacency.setdefault(node_left, set()).add(node_right)
                adjacency.setdefault(node_right, set()).add(node_left)

    if device_templates:
        _add_template_edges(adjacency, device_terminals, device_templates)

    logical_edges_stats = _add_logical_edges(
        adjacency,
        device_terminals,
        device_templates or {},
        wired_between_parts,
        device_nets,
        direct_device_edges,
    )

    if virtual_edges:
        issues.append(
            _issue(
                "INFO",
                "VIRTUAL_EDGES",
                f"Applied {len(virtual_edges)} virtual continuity edges.",
            )
        )

    return (
        adjacency,
        issues,
        device_terminals,
        device_parts,
        logical_edges_stats,
        virtual_links,
        virtual_edges,
    )


def _compress_path_names(path: List[Node]) -> List[str]:
    collapsed: List[str] = []
    last_name: str | None = None

    for node in path:
        if _is_net_node(node):
            continue
        name = _device_name(node)
        if name != last_name:
            collapsed.append(name)
            last_name = name

    return collapsed


def _collapse_consecutive_duplicates(names: List[str]) -> List[str]:
    collapsed: List[str] = []
    for name in names:
        if not collapsed or name != collapsed[-1]:
            collapsed.append(name)
    return collapsed


def _extract_device_names_from_path(path: List[Node]) -> List[str]:
    names: List[str] = []
    for node in path:
        if _is_net_node(node):
            continue
        device_name = _strip_contact_suffix(_device_name(node))
        if not device_name.startswith("-"):
            continue
        names.append(device_name)
    return _collapse_consecutive_duplicates(names)


def _insert_virtual_links(
    chain_items: List[str],
    virtual_links: List[VirtualLink],
) -> List[str]:
    if not virtual_links:
        return chain_items

    adapter_map: Dict[Tuple[str, str], str] = {}
    for link in sorted(virtual_links, key=lambda item: item.get("original_row_index", 0)):
        from_name = link.get("from_name_raw")
        to_name = link.get("to_name_raw")
        if not from_name or not to_name:
            continue
        adapter_type = link.get("from_type") or link.get("to_type") or _VIRTUAL_LINK_TYPE
        adapter_map.setdefault((from_name, to_name), adapter_type)

    device_sequence = [item for item in chain_items if item.startswith("-")]
    if len(device_sequence) < 2:
        return chain_items

    updated: List[str] = []
    device_index = 0
    for item in chain_items:
        updated.append(item)
        if item.startswith("-"):
            if device_index < len(device_sequence) - 1:
                next_device = device_sequence[device_index + 1]
                adapter_type = adapter_map.get((item, next_device))
                if adapter_type:
                    updated.append(f"[{adapter_type}]")
            device_index += 1
    return updated


def _virtual_edge_count(path: List[Node], virtual_edges: VirtualEdge) -> int:
    if not path or not virtual_edges:
        return 0
    count = 0
    for left, right in zip(path, path[1:]):
        if (left, right) in virtual_edges:
            count += 1
    return count


def _logical_terminal_edges(
    terminals_a: Set[str],
    terminals_b: Set[str],
) -> Set[Tuple[str, str]]:
    edges: Set[Tuple[str, str]] = set()
    numbers_a = {term for term in terminals_a if term.isdigit()}
    numbers_b = {term for term in terminals_b if term.isdigit()}
    odds_a = {term for term in numbers_a if int(term) % 2 == 1}
    odds_b = {term for term in numbers_b if int(term) % 2 == 1}
    evens_a = {term for term in numbers_a if int(term) % 2 == 0}
    evens_b = {term for term in numbers_b if int(term) % 2 == 0}

    neutral_pairs = _neutral_logical_pairs(terminals_a, terminals_b)
    edges.update(neutral_pairs)

    common_numbers = numbers_a & numbers_b
    for number in sorted(common_numbers, key=lambda value: int(value)):
        edges.add((number, number))

    if not common_numbers:
        if odds_a and odds_b:
            edges.add((min(odds_a, key=int), min(odds_b, key=int)))
        if evens_a and evens_b:
            edges.add((min(evens_a, key=int), min(evens_b, key=int)))

    if not evens_a and evens_b:
        for odd, even in (("1", "2"), ("3", "4"), ("5", "6")):
            if odd in numbers_a and even in numbers_b:
                edges.add((odd, even))
    if not evens_b and evens_a:
        for odd, even in (("1", "2"), ("3", "4"), ("5", "6")):
            if odd in numbers_b and even in numbers_a:
                edges.add((even, odd))

    return edges


def _neutral_kind(term: str) -> str | None:
    normalized = term.strip().upper()
    if not _is_neutral_terminal(normalized):
        return None
    if normalized in {"N'", "8N"}:
        return "end"
    if normalized in {"N", "7N"}:
        return "front"
    return None


def _neutral_logical_pairs(
    terminals_a: Set[str],
    terminals_b: Set[str],
) -> Set[Tuple[str, str]]:
    fronts_a = sorted({term for term in terminals_a if _neutral_kind(term) == "front"})
    ends_a = sorted({term for term in terminals_a if _neutral_kind(term) == "end"})
    fronts_b = sorted({term for term in terminals_b if _neutral_kind(term) == "front"})
    ends_b = sorted({term for term in terminals_b if _neutral_kind(term) == "end"})

    pairs: Set[Tuple[str, str]] = set()
    if fronts_a and fronts_b:
        pairs.add((fronts_a[0], fronts_b[0]))
    if ends_a and ends_b:
        pairs.add((ends_a[0], ends_b[0]))
    if not pairs:
        if fronts_a and ends_b:
            pairs.add((fronts_a[0], ends_b[0]))
        elif ends_a and fronts_b:
            pairs.add((ends_a[0], fronts_b[0]))
    return pairs


def _stacked_split_role(terminals: Set[str], template: Dict[str, Any] | None) -> str | None:
    if not terminals or not template:
        return None
    front_pins = {str(pin) for pin in template.get("front_pins", [])}
    back_pins = {str(pin) for pin in template.get("back_pins", [])}
    if not front_pins and not back_pins:
        return None

    front_matches = {pin for pin in terminals if pin in front_pins}
    back_matches = {pin for pin in terminals if pin in back_pins}
    unmatched = terminals - front_matches - back_matches
    if unmatched:
        return None
    if front_matches and not back_matches:
        return "front"
    if back_matches and not front_matches:
        return "back"
    return None


def _f_family_key(name: str) -> str | None:
    match = re.match(r"^(-F\d+)(?:\.(\d+))?$", name)
    if not match:
        return None
    return match.group(1)


def _device_nodes_by_name(adjacency: Dict[Node, Set[Node]]) -> Dict[str, Set[Node]]:
    mapping: Dict[str, Set[Node]] = defaultdict(set)
    for node in adjacency:
        if _is_net_node(node):
            continue
        mapping[_device_name(node)].add(node)
    return mapping


def _has_wire_between_devices(
    adjacency: Dict[Node, Set[Node]],
    nodes_by_name: Dict[str, Set[Node]],
    dev_a: str,
    dev_b: str,
) -> bool:
    for node in nodes_by_name.get(dev_a, set()):
        for neighbor in adjacency.get(node, set()):
            if _is_net_node(neighbor):
                continue
            if _device_name(neighbor) == dev_b:
                return True
    return False


def _add_logical_edges(
    adjacency: Dict[Node, Set[Node]],
    device_terminals: Dict[str, Set[str]],
    device_templates: Dict[str, Dict[str, Any]],
    wired_between_parts: Set[str],
    device_nets: Dict[str, Set[str]],
    direct_device_edges: Set[frozenset[str]],
) -> Dict[str, int]:
    logical_edges_added = 0
    logical_edges_skipped = 0
    stacked_candidates = 0
    stacked_applied = 0
    stacked_rejected_wired = 0
    stacked_rejected_ambiguous = 0
    stacked_rejected_examples: List[Dict[str, Any]] = []
    stacked_rejected_pin_mismatch = 0
    stacked_groups_sample: List[Dict[str, Any]] = []
    stacked_applied_pairs: List[Dict[str, str]] = []  # IMPORTANT: used later for stable grouping

    nodes_by_name = _device_nodes_by_name(adjacency)

    family_members: Dict[str, Set[str]] = defaultdict(set)
    for device_name in device_terminals:
        family_key = _f_family_key(device_name)
        if family_key:
            family_members[family_key].add(device_name)

    for family_key in sorted(family_members):
        members = family_members[family_key]

        front_candidate = None
        if f"{family_key}.2" in members:
            front_candidate = f"{family_key}.2"
        elif family_key in members:
            # NOTE: base name without .2 is treated as potential “front” only if there is no explicit .2
            front_candidate = family_key

        back_candidate = f"{family_key}.1" if f"{family_key}.1" in members else None
        if not front_candidate or not back_candidate:
            continue

        # If both exist (base and .2), do NOT alias base->.2 automatically.
        if front_candidate == family_key and f"{family_key}.2" in members:
            continue

        stacked_candidates += 1
        base_part_name = family_key
        left, right = front_candidate, back_candidate

        direct_edge = frozenset({left, right}) in direct_device_edges
        nets_left = device_nets.get(left, set())
        nets_right = device_nets.get(right, set())
        common_nets = sorted(nets_left & nets_right)
        has_wire_between = _has_wire_between_devices(adjacency, nodes_by_name, left, right)

        # HARD RULE: if there is ANY evidence of wiring/connection between .2 and .1 -> DO NOT stack.
        if base_part_name in wired_between_parts or direct_edge or common_nets or has_wire_between:
            stacked_rejected_wired += 1
            if len(stacked_rejected_examples) < 3:
                stacked_rejected_examples.append(
                    {
                        "base": base_part_name,
                        "parts": [left, right],
                        "common_nets": common_nets,
                        "found_edge": direct_edge or has_wire_between,
                        "reason": "wired",
                    }
                )
            continue

        # If we have no nets at all, stacking is ambiguous -> refuse.
        if not nets_left or not nets_right:
            stacked_rejected_ambiguous += 1
            if len(stacked_rejected_examples) < 3:
                stacked_rejected_examples.append(
                    {
                        "base": base_part_name,
                        "parts": [left, right],
                        "common_nets": common_nets,
                        "found_edge": direct_edge,
                        "reason": "ambiguous",
                    }
                )
            continue

        terminals_left = device_terminals.get(left, set())
        terminals_right = device_terminals.get(right, set())
        role_left = _stacked_split_role(terminals_left, device_templates.get(left))
        role_right = _stacked_split_role(terminals_right, device_templates.get(right))

        # Must be complementary roles (front-only vs back-only), otherwise refuse.
        if not role_left or not role_right or role_left == role_right:
            stacked_rejected_pin_mismatch += 1
            logical_edges_skipped += 1
            continue

        # Add logical bridge edges between the two parts
        for term_left, term_right in _logical_terminal_edges(terminals_left, terminals_right):
            node_left = f"{left}:{term_left}"
            node_right = f"{right}:{term_right}"
            adjacency.setdefault(node_left, set())
            adjacency.setdefault(node_right, set())
            if node_right not in adjacency[node_left]:
                adjacency[node_left].add(node_right)
                adjacency[node_right].add(node_left)
                logical_edges_added += 1

        stacked_applied += 1
        stacked_applied_pairs.append({"base": base_part_name, "front": left, "back": right})

        if len(stacked_groups_sample) < 3:
            stacked_groups_sample.append({"base": base_part_name, "parts": [left, right]})

    return {
        "added": logical_edges_added,
        "skipped": logical_edges_skipped,
        "stacked_candidates": stacked_candidates,
        "stacked_applied": stacked_applied,
        "stacked_rejected_wired": stacked_rejected_wired,
        "stacked_rejected_ambiguous": stacked_rejected_ambiguous,
        "stacked_rejected_pin_mismatch": stacked_rejected_pin_mismatch,
        "stacked_rejected_examples": stacked_rejected_examples,
        "stacked_groups_sample": stacked_groups_sample,
        "stacked_applied_pairs": stacked_applied_pairs,
    }


def _shortest_path_to_roots(
    adjacency: Dict[Node, Set[Node]],
    start_nodes: Iterable[Node],
    root_nodes: Set[Node],
    blocked_nodes: Set[Node] | None = None,
    edge_weights: Dict[Tuple[Node, Node], int] | None = None,
) -> Tuple[List[Node], Node | None]:
    start_list = sorted(start_nodes)
    if not start_list:
        return [], None

    blocked_nodes = blocked_nodes or set()
    edge_weights = edge_weights or {}
    best_cost: Dict[Node, Tuple[int, int]] = {}
    parent: Dict[Node, Node] = {}

    def _device_count(node: Node) -> int:
        return 0 if _is_net_node(node) else 1

    queue: List[Tuple[int, int, Node]] = []
    for start in start_list:
        if start in blocked_nodes:
            continue
        cost = (0, _device_count(start))
        best_cost[start] = cost
        heapq.heappush(queue, (cost[0], cost[1], start))

    while queue:
        distance, device_count, current = heapq.heappop(queue)
        current_cost = (distance, device_count)
        if current_cost > best_cost.get(current, current_cost):
            continue
        if current in root_nodes:
            path_nodes: List[Node] = [current]
            while current not in start_list:
                current = parent[current]
                path_nodes.append(current)
            path_nodes.reverse()
            return path_nodes, path_nodes[-1]

        neighbors = sorted(adjacency.get(current, set()))
        if _is_net_node(current):
            neighbors = sorted(neighbors, key=lambda neighbor: (neighbor in blocked_nodes, neighbor))

        for neighbor in neighbors:
            if neighbor in blocked_nodes:
                continue
            weight = edge_weights.get((current, neighbor), 1)
            next_cost = (distance + weight, device_count + _device_count(neighbor))
            if neighbor in best_cost and next_cost >= best_cost[neighbor]:
                continue
            best_cost[neighbor] = next_cost
            parent[neighbor] = current
            heapq.heappush(queue, (next_cost[0], next_cost[1], neighbor))

    return [], None


def _first_subroot_in_path(path: List[Node]) -> str:
    for node in path:
        if not _is_net_node(node):
            continue
        net_name = _net_name(node)
        if _SUB_ROOT_PATTERN.match(net_name):
            return net_name
    return ""


def _first_main_root_in_path(path: List[Node]) -> str:
    for node in path:
        if not _is_net_node(node):
            continue
        net_name = _net_name(node)
        if _MAIN_ROOT_PATTERN.match(net_name):
            return net_name
    return ""


def _last_device_before_root(path: List[Node]) -> str:
    if not path:
        return ""
    for node in reversed(path):
        if _is_net_node(node):
            continue
        return _device_name(node)
    return ""


def _direct_net_neighbors(adjacency: Dict[Node, Set[Node]], nodes: Iterable[Node]) -> List[str]:
    nets: Set[str] = set()
    for node in nodes:
        for neighbor in adjacency.get(node, set()):
            if _is_net_node(neighbor):
                nets.add(_net_name(neighbor))
    return sorted(nets)


def _device_terminals_from_nodes(adjacency: Dict[Node, Set[Node]]) -> Dict[str, Set[str]]:
    device_terminals: Dict[str, Set[str]] = defaultdict(set)
    for node in adjacency:
        if _is_net_node(node):
            continue
        name = _device_name(node)
        cp = node.split(":", 1)[1] if ":" in node else ""
        if name and cp:
            device_terminals[name].add(cp)
    return device_terminals


def _add_template_edges(
    adjacency: Dict[Node, Set[Node]],
    device_terminals: Dict[str, Set[str]],
    device_templates: Dict[str, Dict[str, Any]],
) -> int:
    edges_added = 0
    for device_name, template in device_templates.items():
        terminals = device_terminals.get(device_name, set())
        if not terminals:
            continue
        if template.get("front_only") and not template.get("back_pins"):
            continue

        front_pins = [str(pin) for pin in template.get("front_pins", [])]
        back_pins = [str(pin) for pin in template.get("back_pins", [])]
        neutral_front = template.get("neutral_front_token")
        neutral_back = template.get("neutral_back_token")

        front_numbers = sorted([pin for pin in front_pins if pin.isdigit()], key=int)
        back_numbers = sorted([pin for pin in back_pins if pin.isdigit()], key=int)

        for left, right in zip(front_numbers, back_numbers):
            if left in terminals and right in terminals:
                node_left = f"{device_name}:{left}"
                node_right = f"{device_name}:{right}"
                adjacency.setdefault(node_left, set()).add(node_right)
                adjacency.setdefault(node_right, set()).add(node_left)
                edges_added += 1

        if neutral_front and neutral_back:
            if neutral_front in terminals and neutral_back in terminals:
                node_left = f"{device_name}:{neutral_front}"
                node_right = f"{device_name}:{neutral_back}"
                adjacency.setdefault(node_left, set()).add(node_right)
                adjacency.setdefault(node_right, set()).add(node_left)
                edges_added += 1
    return edges_added


def _is_neutral_terminal(term: str) -> bool:
    normalized = term.strip().upper()
    return normalized in {"N", "N'", "7N", "8N"}


def _is_q_device(name: str) -> bool:
    return bool(re.match(r"^-Q\d+", name)) and name != "-Q81"


def _is_f_device(name: str) -> bool:
    return bool(re.match(r"^-F\d+", name))


def compute_feeder_paths(
    adjacency: Dict[Node, Set[Node]],
    device_terminals: Dict[str, Set[str]] | None = None,
    device_parts: Dict[str, Set[str]] | None = None,
    logical_edges_added: Dict[str, Any] | int | None = None,
    virtual_links: List[VirtualLink] | None = None,
    virtual_edges: VirtualEdge | None = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Issue], Dict[str, Any]]:
    issues: List[Issue] = []
    feeders: List[Dict[str, Any]] = []
    if device_terminals is None:
        device_terminals = _device_terminals_from_nodes(adjacency)
    if device_parts is None:
        device_parts = {}
    virtual_edge_weights = {
        edge: data.get("weight", 1) for edge, data in (virtual_edges or {}).items()
    }

    root_nets = {
        node
        for node in adjacency
        if _is_net_node(node) and _MAIN_ROOT_PATTERN.match(_net_name(node))
    }
    sub_root_nets = {
        node
        for node in adjacency
        if _is_net_node(node) and _SUB_ROOT_PATTERN.match(_net_name(node))
    }

    device_nodes = [node for node in adjacency if not _is_net_node(node)]
    device_names = {_device_name(node) for node in device_nodes}

    # ---- IMPORTANT FIX:
    # Only treat .1/.2 as the same “logical base” if stacking was ACTUALLY applied.
    stacked_applied_pairs: List[Dict[str, str]] = []
    if isinstance(logical_edges_added, dict):
        stacked_applied_pairs = list(logical_edges_added.get("stacked_applied_pairs", []) or [])

    name_to_group: Dict[str, str] = {}
    for item in stacked_applied_pairs:
        base = str(item.get("base") or "").strip()
        front = str(item.get("front") or "").strip()
        back = str(item.get("back") or "").strip()
        if base and front and back:
            name_to_group[front] = base
            name_to_group[back] = base

    def group_key(name: str) -> str:
        return name_to_group.get(name, name)

    # group terminals by group_key (NOT by naive _logical_base_name)
    group_terminals: Dict[str, Set[str]] = defaultdict(set)
    for name in device_names:
        group_terminals[group_key(name)].update(device_terminals.get(name, set()))

    def _is_f_end(terminals: Iterable[str]) -> bool:
        input_terms = {"1", "3", "5", "N", "7N"}
        output_terms = {"2", "4", "6", "8", "N'", "8N"}
        has_input = any(term in input_terms or _is_neutral_terminal(term) for term in terminals)
        has_output = any(term in output_terms for term in terminals)
        return has_input and not has_output

    feeder_f_groups = {
        g
        for g, terminals in group_terminals.items()
        if _is_f_device(g) and _is_f_end(terminals)
    }

    # --- Minimal reproducible debug dump for a problematic family (hardcoded by request)
    def _family_debug(base: str) -> Dict[str, Any] | None:
        members = sorted(
            [name for name in device_names if name == base or name.startswith(f"{base}.")]
        )
        if not members:
            return None

        nodes_by_name = _device_nodes_by_name(adjacency)

        def nets_for(name: str) -> List[str]:
            nets: Set[str] = set()
            for node in nodes_by_name.get(name, set()):
                for nb in adjacency.get(node, set()):
                    if _is_net_node(nb):
                        nets.add(_net_name(nb))
            return sorted(nets)

        def has_direct_device_edge(a: str, b: str) -> bool:
            for node in nodes_by_name.get(a, set()):
                for nb in adjacency.get(node, set()):
                    if _is_net_node(nb):
                        continue
                    if _device_name(nb) == b:
                        return True
            return False

        edges_between: List[Dict[str, Any]] = []
        for i, a in enumerate(members):
            for b in members[i + 1 :]:
                edges_between.append(
                    {
                        "a": a,
                        "b": b,
                        "direct_edge": has_direct_device_edge(a, b),
                        "common_nets": sorted(set(nets_for(a)) & set(nets_for(b))),
                    }
                )

        stacked = any(item.get("base") == base for item in stacked_applied_pairs)
        stack_reason = "applied" if stacked else "refused"
        if not stacked:
            # Mirror hard rule: any evidence of wiring/connection => refuse stacking
            if any(e["direct_edge"] or e["common_nets"] for e in edges_between):
                stack_reason = "refused:wired_between_parts"

        per_member = []
        for name in members:
            terms = sorted(device_terminals.get(name, set()), key=lambda t: (not t.isdigit(), t))
            per_member.append(
                {
                    "name": name,
                    "terminals": terms,
                    "nets": nets_for(name),
                    "is_feeder_end_by_self": _is_f_device(name) and _is_f_end(terms),
                    "group_key": group_key(name),
                    "is_feeder_end_by_group": group_key(name) in feeder_f_groups,
                }
            )

        return {
            "base": base,
            "members": members,
            "stacked": stacked,
            "stack_decision": stack_reason,
            "edges_between_members": edges_between,
            "per_member": per_member,
        }

    f611_debug = _family_debug("-F611")
    feeder_q_names = {name for name in device_names if _is_q_device(name)}
    feeder_x_names = {name for name in device_names if name.startswith("-X")}

    feeder_nodes = [
        node
        for node in device_nodes
        if group_key(_device_name(node)) in feeder_f_groups
        or _device_name(node) in feeder_q_names
        or _device_name(node) in feeder_x_names
    ]
    feeder_nodes_sorted = sorted(feeder_nodes)

    q_heuristic_applied = 0
    q_heuristic_blocked_nodes = 0

    for feeder_node in feeder_nodes_sorted:
        feeder_name = _device_name(feeder_node)
        feeder_cp = feeder_node.split(":", 1)[1] if ":" in feeder_node else ""
        direct_nets = _direct_net_neighbors(adjacency, [feeder_node])

        feeder_group = group_key(feeder_name)

        # block all OTHER feeder end nodes, but keep same logical group
        blocked_nodes = {
            node
            for node in feeder_nodes
            if group_key(_device_name(node)) != feeder_group
        }

        q_blocked_nodes = set()
        q_blocked_prefix = ""
        q_match = re.match(r"^-Q(\d+)$", feeder_name)
        if q_match and feeder_name != "-Q81":
            q_digits = q_match.group(1)
            if len(q_digits) >= 3 and q_digits[-1] in {"7", "8"}:
                base_digits = q_digits[:-1]
                try:
                    preferred_number = int(base_digits) + (0 if q_digits[-1] == "7" else 1)
                except ValueError:
                    preferred_number = None
                preferred_prefix = f"-F{preferred_number}" if preferred_number is not None else ""

                preferred_devices = {name for name in device_names if preferred_prefix and name.startswith(preferred_prefix)}
                if preferred_prefix and preferred_devices:
                    group_prefix = q_digits[:-2]
                    q_blocked_prefix = f"-F{group_prefix}"
                    for name in device_names:
                        if not name.startswith(f"-F{group_prefix}"):
                            continue
                        if name.startswith(preferred_prefix):
                            continue
                        for node in device_nodes:
                            if _device_name(node) == name:
                                q_blocked_nodes.add(node)
                    if q_blocked_nodes:
                        q_heuristic_applied += 1
                        q_heuristic_blocked_nodes += len(q_blocked_nodes)
                        blocked_nodes |= q_blocked_nodes

        path_any, supply_any = _shortest_path_to_roots(
            adjacency,
            [feeder_node],
            root_nets,
            blocked_nodes=blocked_nodes,
            edge_weights=virtual_edge_weights,
        )

        if not path_any and q_blocked_nodes:
            fallback_blocked_nodes = blocked_nodes - q_blocked_nodes
            fallback_path, fallback_supply = _shortest_path_to_roots(
                adjacency,
                [feeder_node],
                root_nets,
                blocked_nodes=fallback_blocked_nodes,
                edge_weights=virtual_edge_weights,
            )
            if fallback_path:
                path_any = fallback_path
                supply_any = fallback_supply
                blocked_device_names = sorted({_device_name(node) for node in q_blocked_nodes})
                issues.append(
                    _issue(
                        "WARN",
                        "W2QFALLBACK",
                        "Q-heuristic blocked a valid path; fallback used.",
                        context={
                            "feeder_name": feeder_name,
                            "feeder_cp": feeder_cp,
                            "blocked_prefix": q_blocked_prefix,
                            "blocked_devices_sample": blocked_device_names[:5],
                        },
                    )
                )

        reachable = bool(path_any)
        virtual_edges_count = _virtual_edge_count(path_any, virtual_edges or {})
        virtual_edges_used = virtual_edges_count > 0
        first_subroot_token = _first_subroot_in_path(path_any)
        path_main = " -> ".join(_compress_path_names(path_any))
        root_chain_nets = _extract_root_chain_nets(path_any)
        root_chain_str = " -> ".join(root_chain_nets)
        spine_str = f"{feeder_name} -> {root_chain_str} -> -Q81" if root_chain_str else f"{feeder_name} -> -Q81"
        chain_items = build_simplified_chain_items(path_any, feeder_name)
        chain_items = _insert_virtual_links(chain_items, virtual_links or [])
        if reachable or root_chain_nets:
            if not chain_items or chain_items[-1] != "-Q81":
                chain_items.append("-Q81")
        else:
            if not chain_items or chain_items[-1] != "[UNREACHED]":
                chain_items.append("[UNREACHED]")
            if not root_chain_str:
                root_chain_str = "(NO ROOT)"
        simplified_chain = " -> ".join(chain_items)

        if not reachable:
            path_closest, closest_net = _shortest_path_to_roots(
                adjacency,
                [feeder_node],
                {node for node in adjacency if _is_net_node(node)},
                blocked_nodes=blocked_nodes,
                edge_weights=virtual_edge_weights,
            )
            closest_net_token = _net_name(closest_net) if closest_net else ""
            last_device_before_root = _last_device_before_root(path_closest[:-1])
            first_subroot_token = _first_subroot_in_path(path_closest)

            issues.append(
                _issue(
                    "ERROR",
                    "W202",
                    "Feeder end is unreachable from any root net (MT/MT2/IT/LT/LT2).",
                    context={
                        "feeder_name": feeder_name,
                        "feeder_cp": feeder_cp,
                        "direct_nets": direct_nets,
                        "closest_net_token": closest_net_token,
                        "last_device_before_root": last_device_before_root,
                        "first_subroot_token_seen": first_subroot_token,
                    },
                )
            )

        supply_net = _first_main_root_in_path(path_any)
        if not reachable:
            supply_net = f"UNRESOLVED (last={last_device_before_root}, net={closest_net_token})"

        path_nodes_raw = " -> ".join(path_any)
        path_names_collapsed = " -> ".join(
            _compress_path_names(path_any) + ([supply_net] if supply_net else [])
        )
        device_chain = " -> ".join(_extract_device_names_from_path(path_any))

        feeders.append(
            {
                "feeder_end_name": feeder_name,
                "feeder_end_cp": feeder_cp,
                "supply_net": supply_net,
                "subroot_net": first_subroot_token,
                "path_main": path_main,
                "reachable": reachable,
                "path_nodes_raw": path_nodes_raw,
                "path_names_collapsed": path_names_collapsed,
                "device_chain": device_chain,
                "path_len_nodes": len(path_any),
                "root_chain_str": root_chain_str,
                "spine_str": spine_str,
                "simplified_chain": simplified_chain,
                "virtual_edges_used": virtual_edges_used,
                "virtual_edges_count": virtual_edges_count,
            }
        )

    aggregated = _aggregate_feeder_paths(feeders)

    feeder_end_groups = sorted({group_key(_device_name(node)) for node in feeder_nodes})

    stacked_example = None
    for base_name in sorted(device_parts):
        parts = device_parts.get(base_name, set())
        if len(parts) > 1:
            stacked_example = {
                "base": base_name,
                "parts": sorted(parts),
                "terminals_union": sorted(group_terminals.get(base_name, set())),
            }
            break

    stacked_groups_sample = [
        {"base": base_name, "parts": sorted(parts)}
        for base_name, parts in sorted(device_parts.items())
        if len(parts) > 1
    ][:3]

    if isinstance(logical_edges_added, dict):
        logical_edges_stats = logical_edges_added
    else:
        logical_edges_stats = {"added": logical_edges_added or 0, "skipped": 0}

    debug = {
        "total_nodes": len(adjacency),
        "total_edges": sum(len(neighbors) for neighbors in adjacency.values()) // 2,
        "main_root_nets": sorted(_net_name(node) for node in root_nets),
        "sub_root_nets": sorted(_net_name(node) for node in sub_root_nets),
        "feeder_ends_found": sorted({feeder["feeder_end_name"] for feeder in feeders}),
        "feeder_end_bases_count": len(feeder_end_groups),
        "feeder_end_bases_sample": feeder_end_groups[:10],
        "stacked_example": stacked_example,
        "stacked_groups_sample": logical_edges_stats.get("stacked_groups_sample", stacked_groups_sample),
        "logical_edges_added": logical_edges_stats.get("added", 0),
        "logical_edges_skipped": logical_edges_stats.get("skipped", 0),
        "stacked_candidates_count": logical_edges_stats.get("stacked_candidates", 0),
        "stacked_applied_count": logical_edges_stats.get("stacked_applied", 0),
        "stacked_rejected_wired_count": logical_edges_stats.get("stacked_rejected_wired", 0),
        "stacked_rejected_ambiguous_count": logical_edges_stats.get("stacked_rejected_ambiguous", 0),
        "stacked_rejected_pin_mismatch_count": logical_edges_stats.get("stacked_rejected_pin_mismatch", 0),
        "stacked_groups_rejected_due_to_wires_count": logical_edges_stats.get("stacked_rejected_wired", 0),
        "stacked_groups_rejected_examples": logical_edges_stats.get("stacked_rejected_examples", []),
        "q_branch_heuristic_applied_count": q_heuristic_applied,
        "q_branch_heuristic_blocked_nodes": q_heuristic_blocked_nodes,
        "unreachable_feeders_count": sum(1 for feeder in feeders if not feeder["reachable"]),
        "family_debug_-F611": f611_debug,
        "virtual_links_count": len(virtual_links or []),
        "virtual_links": virtual_links or [],
        "virtual_edges_count": len(virtual_edges or {}),
    }

    return feeders, aggregated, issues, debug


def _aggregate_feeder_paths(feeders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[tuple[str, str], Dict[str, Any]] = {}

    for feeder in feeders:
        name = feeder["feeder_end_name"]
        supply_net = feeder["supply_net"]
        entry = grouped.setdefault(
            (name, supply_net),
            {
                "feeder_end_name": name,
                "feeder_end_cps": set(),
                "supply_net": supply_net,
                "subroot_net": "",
                "path_main": "",
                "path_names_collapsed": "",
                "device_chain_grouped": "",
                "device_chain_candidates": defaultdict(int),
                "reachable": True,
                "path_len_nodes": 0,
                "root_chain_str": "",
                "spine_str": "",
                "simplified_chain": "",
                "virtual_edges_used": False,
                "virtual_edges_count": 0,
            },
        )
        if feeder["feeder_end_cp"]:
            entry["feeder_end_cps"].add(feeder["feeder_end_cp"])

        entry["reachable"] = entry["reachable"] and feeder["reachable"]
        if not entry["subroot_net"] and feeder.get("subroot_net"):
            entry["subroot_net"] = feeder["subroot_net"]
        if not entry["path_main"] and feeder.get("path_main"):
            entry["path_main"] = feeder["path_main"]
        if not entry["path_names_collapsed"]:
            entry["path_names_collapsed"] = feeder["path_names_collapsed"]
        if feeder["device_chain"]:
            entry["device_chain_candidates"][feeder["device_chain"]] += 1
        if entry["path_len_nodes"] == 0:
            entry["path_len_nodes"] = feeder["path_len_nodes"]
            entry["root_chain_str"] = feeder.get("root_chain_str", "")
            entry["spine_str"] = feeder.get("spine_str", "")
            entry["simplified_chain"] = feeder.get("simplified_chain", "")
            entry["virtual_edges_used"] = feeder.get("virtual_edges_used", False)
            entry["virtual_edges_count"] = feeder.get("virtual_edges_count", 0)
        else:
            if feeder["path_len_nodes"] < entry["path_len_nodes"]:
                entry["path_len_nodes"] = feeder["path_len_nodes"]
                entry["root_chain_str"] = feeder.get("root_chain_str", "")
                entry["spine_str"] = feeder.get("spine_str", "")
                entry["simplified_chain"] = feeder.get("simplified_chain", "")
                entry["virtual_edges_used"] = feeder.get("virtual_edges_used", False)
                entry["virtual_edges_count"] = feeder.get("virtual_edges_count", 0)
            else:
                entry["path_len_nodes"] = min(entry["path_len_nodes"], feeder["path_len_nodes"])

    aggregated = []
    for (_name, _supply), entry in sorted(grouped.items()):
        cps = sorted(entry["feeder_end_cps"], key=lambda cp: (len(cp), cp))
        if entry["device_chain_candidates"]:
            chain_lengths = {chain: len(chain.split(" -> ")) for chain in entry["device_chain_candidates"]}
            shortest_length = min(chain_lengths.values())
            shortest_chains = [chain for chain, length in chain_lengths.items() if length == shortest_length]
            entry["device_chain_grouped"] = max(
                shortest_chains,
                key=lambda chain: entry["device_chain_candidates"][chain],
            )
        aggregated.append(
            {
                "feeder_end_name": entry["feeder_end_name"],
                "feeder_end_cps": ", ".join(cps),
                "supply_net": entry["supply_net"],
                "subroot_net": entry["subroot_net"],
                "path_main": entry["path_main"],
                "path_names_collapsed": entry["path_names_collapsed"],
                "device_chain_grouped": entry["device_chain_grouped"],
                "reachable": entry["reachable"],
                "path_len_nodes": entry["path_len_nodes"],
                "root_chain_str": entry["root_chain_str"],
                "spine_str": entry["spine_str"],
                "simplified_chain": entry["simplified_chain"],
                "virtual_edges_used": entry["virtual_edges_used"],
                "virtual_edges_count": entry["virtual_edges_count"],
            }
        )

    return aggregated
