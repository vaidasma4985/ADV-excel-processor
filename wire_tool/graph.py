from __future__ import annotations

from collections import defaultdict
import heapq
import re
from typing import Any, Dict, Iterable, List, Set, Tuple

import pandas as pd

from wire_tool.pin_templates import (
    is_power_pin,
    load_templates,
    normalize_pin_token,
    pinset_key,
    resolve_mapping,
)
Node = str
Issue = Dict[str, Any]


_MAIN_ROOT_PATTERN = re.compile(r"^(MT2|LT2|MT|IT|LT)/(L1|L2|L3|N)$")
_SUB_ROOT_PATTERN = re.compile(r"^F\d+/(L1|L2|L3|N)$")
_ROOT_TOKEN_PATTERN = re.compile(r"(MT2|LT2|MT|IT|LT|F\d+)/(L1|L2|L3|N)")
_PIN_PAIR_ORDER = (("1", "2"), ("3", "4"), ("5", "6"), ("7", "8"))
_NEUTRAL_PAIRS = (("N", "N'"), ("7N", "8N"))


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


def _pin_sort_key(token: str) -> tuple[int, int | str]:
    if token.isdigit():
        return (0, int(token))
    return (1, token)


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


def _extract_root_tokens(wireno: str | None) -> List[str]:
    if not wireno:
        return []
    return [f"{match[0]}/{match[1]}" for match in _ROOT_TOKEN_PATTERN.findall(wireno)]


def _extract_wireno_tokens(wireno: str | None) -> List[str]:
    if not wireno:
        return []
    tokens = [token for token in re.split(r"[;,]", wireno) if token]
    return [token.strip() for token in tokens if token.strip()]


def _extract_pindata_tokens(value: Any) -> List[str]:
    if _is_missing(value):
        return []
    raw = str(value).replace("\u00a0", " ").strip()
    if not raw:
        return []
    tokens = [token for token in re.split(r"[;,]", raw) if token]
    normalized = [normalize_pin_token(token) for token in tokens]
    return [token for token in normalized if token]


def _power_pin_token(value: str | None) -> str | None:
    if not value:
        return None
    token = normalize_pin_token(value)
    if is_power_pin(token):
        return token
    return None


def _is_front_terminal(term: str | None) -> bool:
    if not term:
        return False
    if term.isdigit():
        return int(term) % 2 == 1
    return _neutral_kind(term) == "front"


def _is_bus_token(token: str) -> bool:
    return bool(_MAIN_ROOT_PATTERN.match(token) or _SUB_ROOT_PATTERN.match(token))


def build_graph(
    df_power: pd.DataFrame,
    templates: dict | None = None,
    templates_path: str = "data/pin_templates.yaml",
) -> Tuple[
    Dict[Node, Set[Node]],
    List[Issue],
    Dict[str, Set[str]],
    Dict[str, Set[str]],
    int,
]:
    adjacency: Dict[Node, Set[Node]] = {}
    issues: List[Issue] = []
    device_terminals: Dict[str, Set[str]] = defaultdict(set)
    device_parts: Dict[str, Set[str]] = defaultdict(set)
    device_pinsets: Dict[str, Set[str]] = defaultdict(set)
    if templates is None:
        templates = load_templates(templates_path)

    for row_index, row in df_power.iterrows():
        wireno = _normalize_wireno(row.get("Wireno"))
        wireno_tokens = _extract_wireno_tokens(wireno)

        name_a_raw = _normalize_name(row.get("Name"))
        name_b_raw = _normalize_name(row.get("Name.1"))
        name_a = _base_of(name_a_raw)
        cp_a = _normalize_terminal(row.get("C.name"))
        name_b = _base_of(name_b_raw)
        cp_b = _normalize_terminal(row.get("C.name.1"))

        from_node = _device_node(name_a, cp_a)
        to_node = _device_node(name_b, cp_b)

        if name_a and cp_a:
            device_terminals[name_a].add(cp_a)
            power_pin = _power_pin_token(cp_a)
            if power_pin:
                device_pinsets[name_a].add(power_pin)
        if name_b and cp_b:
            device_terminals[name_b].add(cp_b)
            power_pin = _power_pin_token(cp_b)
            if power_pin:
                device_pinsets[name_b].add(power_pin)
        if name_a_raw and name_a:
            device_parts[_logical_base_name(name_a)].add(name_a)
        if name_b_raw and name_b:
            device_parts[_logical_base_name(name_b)].add(name_b)
        if name_a:
            _ = _extract_pindata_tokens(row.get("PINDATA"))

        if not from_node and not to_node:
            issues.append(
                _issue(
                    "ERROR",
                    "W201",
                    "Missing endpoint data for Power row; no device nodes created.",
                    row_index=row_index,
                    context={
                        "wireno": row.get("Wireno"),
                        "from_name": row.get("Name"),
                        "to_name": row.get("Name.1"),
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
                suppress_direct = any(_is_bus_token(token) for token in wireno_tokens)
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

    pin_edges_added, _ = _add_pin_template_edges(
        adjacency,
        device_pinsets,
        templates,
    )
    logical_edges_added = pin_edges_added + _add_logical_edges(
        adjacency,
        device_terminals,
        device_parts,
    )

    return adjacency, issues, device_terminals, device_parts, logical_edges_added


def scan_pin_templates(
    df_power: pd.DataFrame,
    templates: dict | None = None,
    templates_path: str = "data/pin_templates.yaml",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    if templates is None:
        templates = load_templates(templates_path)

    device_pinsets: Dict[str, Set[str]] = defaultdict(set)
    device_pinset_keys_seen: Dict[str, Set[str]] = defaultdict(set)
    device_power_nets: Dict[str, Set[str]] = defaultdict(set)
    for _, row in df_power.iterrows():
        wireno = _normalize_wireno(row.get("Wireno"))
        row_nets = _extract_root_tokens(wireno)
        name_a = _base_of(_normalize_name(row.get("Name")))
        name_b = _base_of(_normalize_name(row.get("Name.1")))
        cp_a = _normalize_terminal(row.get("C.name"))
        cp_b = _normalize_terminal(row.get("C.name.1"))

        if name_a and cp_a:
            power_pin = _power_pin_token(cp_a)
            if power_pin:
                device_pinsets[name_a].add(power_pin)
        if name_b and cp_b:
            power_pin = _power_pin_token(cp_b)
            if power_pin:
                device_pinsets[name_b].add(power_pin)
        if name_a:
            pindata_tokens = _extract_pindata_tokens(row.get("PINDATA"))
            filtered_pindata = [token for token in pindata_tokens if is_power_pin(token)]
            if len(filtered_pindata) >= 2:
                device_pinset_keys_seen[name_a].add(pinset_key(filtered_pindata))

        for device in (name_a, name_b):
            if device and row_nets:
                device_power_nets[device].update(row_nets)

    pinset_devices: Dict[str, List[str]] = defaultdict(list)
    pinset_pins: Dict[str, List[str]] = {}
    inconsistent_devices: List[Dict[str, Any]] = []
    resolved_pinsets: Set[str] = set()
    resolved_devices = 0
    for device, pins in device_pinsets.items():
        pinset_keys = device_pinset_keys_seen.get(device, set())
        if len(pinset_keys) > 1:
            inconsistent_devices.append(
                {
                    "device": device,
                    "pinset_keys": sorted(pinset_keys),
                }
            )
            continue
        device_key = pinset_key(pins)
        if not device_key:
            continue
        template = resolve_mapping(device_key, templates)
        if template is None:
            pinset_devices[device_key].append(device)
            pinset_pins.setdefault(device_key, sorted(pins, key=_pin_sort_key))
        else:
            resolved_devices += 1
            resolved_pinsets.add(device_key)

    templates_needed: List[Dict[str, Any]] = []
    for key in sorted(pinset_devices):
        devices = sorted(pinset_devices[key])
        example_devices = devices[:10]
        example_context = []
        for device in example_devices:
            example_context.append(
                {
                    "device": device,
                    "nets": sorted(device_power_nets.get(device, set())),
                    "pins": sorted(device_pinsets.get(device, set()), key=_pin_sort_key),
                }
            )
        templates_needed.append(
            {
                "pinset_key": key,
                "pins": pinset_pins.get(key, []),
                "example_devices": example_devices,
                "example_device_context": example_context,
            }
        )

    debug = {
        "devices_total": len(device_pinsets),
        "resolved_devices": resolved_devices,
        "unknown_pinsets": len(pinset_devices),
        "inconsistent_devices": len(inconsistent_devices),
        "pinsets_total": len(pinset_devices) + len(resolved_pinsets),
    }
    return templates_needed, inconsistent_devices, debug


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
    # Filter out NET nodes and non-device labels; keep only base device names.
    names: List[str] = []
    for node in path:
        if _is_net_node(node):
            continue
        device_name = _strip_contact_suffix(_device_name(node))
        if not device_name.startswith("-"):
            continue
        names.append(device_name)
    return _collapse_consecutive_duplicates(names)


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


def _template_pairs(mapping: dict, pins: Set[str]) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    front_set = set(mapping.get("front", []))
    back_set = set(mapping.get("back", []))

    for left, right in _PIN_PAIR_ORDER:
        if left in pins and right in pins and left in front_set and right in back_set:
            pairs.append((left, right))

    for left, right in _NEUTRAL_PAIRS:
        if left in pins and right in pins and left in front_set and right in back_set:
            pairs.append((left, right))

    neutral_mapping = mapping.get("neutral")
    if isinstance(neutral_mapping, dict):
        left = neutral_mapping.get("front")
        right = neutral_mapping.get("back")
        if left and right and left in pins and right in pins:
            if left in front_set and right in back_set:
                pairs.append((left, right))
    for neutral in mapping.get("neutral_map", []) or []:
        left = neutral.get("front")
        right = neutral.get("back")
        if left and right and left in pins and right in pins:
            if left in front_set and right in back_set:
                pairs.append((left, right))

    return pairs


def _add_pin_template_edges(
    adjacency: Dict[Node, Set[Node]],
    device_pinsets: Dict[str, Set[str]],
    templates: dict,
) -> Tuple[int, List[Dict[str, Any]]]:
    edges_added = 0
    templates_needed: List[Dict[str, Any]] = []

    for device_name, pins in sorted(device_pinsets.items()):
        key = pinset_key(pins)
        if not key:
            continue
        mapping = resolve_mapping(key, templates)
        if mapping is None:
            templates_needed.append(
                {
                    "device": device_name,
                    "pinset_key": key,
                    "pins": sorted(pins, key=_pin_sort_key),
                }
            )
            continue

        for left, right in _template_pairs(mapping, pins):
            node_left = f"{device_name}:{left}"
            node_right = f"{device_name}:{right}"
            adjacency.setdefault(node_left, set())
            adjacency.setdefault(node_right, set())
            if node_right not in adjacency[node_left]:
                adjacency[node_left].add(node_right)
                edges_added += 1

    return edges_added, templates_needed


def _neutral_kind(term: str) -> str | None:
    normalized = term.strip().upper()
    if not _is_neutral_terminal(normalized):
        return None
    if normalized == "N'":
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


def _add_logical_edges(
    adjacency: Dict[Node, Set[Node]],
    device_terminals: Dict[str, Set[str]],
    logical_groups: Dict[str, Set[str]],
) -> int:
    logical_edges_added = 0
    for base_name in sorted(logical_groups):
        parts = sorted(logical_groups[base_name])
        if len(parts) < 2:
            continue
        for left, right in zip(parts, parts[1:]):
            terminals_left = device_terminals.get(left, set())
            terminals_right = device_terminals.get(right, set())
            for term_left, term_right in _logical_terminal_edges(
                terminals_left,
                terminals_right,
            ):
                node_left = f"{left}:{term_left}"
                node_right = f"{right}:{term_right}"
                adjacency.setdefault(node_left, set())
                adjacency.setdefault(node_right, set())
                if node_right not in adjacency[node_left]:
                    adjacency[node_left].add(node_right)
                    adjacency[node_right].add(node_left)
                    logical_edges_added += 1
    return logical_edges_added


def _shortest_path_to_roots(
    adjacency: Dict[Node, Set[Node]],
    start_nodes: Iterable[Node],
    root_nodes: Set[Node],
    blocked_nodes: Set[Node] | None = None,
) -> Tuple[List[Node], Node | None]:
    start_list = sorted(start_nodes)
    if not start_list:
        return [], None

    blocked_nodes = blocked_nodes or set()
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
            neighbors = sorted(
                neighbors,
                key=lambda neighbor: (neighbor in blocked_nodes, neighbor),
            )
        for neighbor in neighbors:
            if neighbor in blocked_nodes:
                continue
            next_cost = (distance + 1, device_count + _device_count(neighbor))
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


def _has_even_terminal(terminals: Iterable[str]) -> bool:
    even_terminals = {"2", "4", "6", "8"}
    return any(term in even_terminals for term in terminals)


def _is_neutral_terminal(term: str) -> bool:
    normalized = term.strip().upper()
    return normalized in {"N", "N'", "7N"}


def _is_q_device(name: str) -> bool:
    return bool(re.match(r"^-Q\d+", name)) and name != "-Q81"


def _is_f_device(name: str) -> bool:
    return bool(re.match(r"^-F\d+", name))


def compute_feeder_paths(
    adjacency: Dict[Node, Set[Node]],
    device_terminals: Dict[str, Set[str]] | None = None,
    device_parts: Dict[str, Set[str]] | None = None,
    logical_edges_added: int | None = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Issue], Dict[str, Any]]:
    issues: List[Issue] = []
    feeders: List[Dict[str, Any]] = []
    if device_terminals is None:
        device_terminals = _device_terminals_from_nodes(adjacency)
    if device_parts is None:
        device_parts = {}

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
    logical_base_terminals: Dict[str, Set[str]] = defaultdict(set)
    for device_name in device_names:
        logical_base_terminals[_logical_base_name(device_name)].update(
            device_terminals.get(device_name, set())
        )

    def _is_f_end(terminals: Iterable[str]) -> bool:
        input_terms = {"1", "3", "5", "N"}
        output_terms = {"2", "4", "6", "8"}
        has_input = any(
            term in input_terms or _is_neutral_terminal(term)
            for term in terminals
        )
        has_output = any(term in output_terms for term in terminals)
        return has_input and not has_output

    feeder_f_bases = {
        base
        for base, terminals in logical_base_terminals.items()
        if _is_f_device(base) and _is_f_end(terminals)
    }
    feeder_q_bases = {name for name in device_names if _is_q_device(name)}
    feeder_x_bases = {name for name in device_names if name.startswith("-X")}
    feeder_nodes = [
        node
        for node in device_nodes
        if _logical_base_name(_device_name(node)) in feeder_f_bases
        or _device_name(node) in feeder_q_bases
        or _device_name(node) in feeder_x_bases
    ]
    feeder_nodes_sorted = sorted(feeder_nodes)

    for feeder_node in feeder_nodes_sorted:
        feeder_name = _device_name(feeder_node)
        feeder_cp = feeder_node.split(":", 1)[1] if ":" in feeder_node else ""
        direct_nets = _direct_net_neighbors(adjacency, [feeder_node])
        feeder_base = _logical_base_name(feeder_name)
        blocked_nodes = {
            node
            for node in feeder_nodes
            if _logical_base_name(_device_name(node)) != feeder_base
        }

        path_any, supply_any = _shortest_path_to_roots(
            adjacency,
            [feeder_node],
            root_nets,
            blocked_nodes=blocked_nodes,
        )

        reachable = bool(path_any)
        first_subroot_token = _first_subroot_in_path(path_any)
        path_main = " -> ".join(_compress_path_names(path_any))
        if not reachable:
            path_closest, closest_net = _shortest_path_to_roots(
                adjacency,
                [feeder_node],
                {node for node in adjacency if _is_net_node(node)},
                blocked_nodes=blocked_nodes,
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
            }
        )

    aggregated = _aggregate_feeder_paths(feeders)

    feeder_end_bases = sorted({_device_name(node) for node in feeder_nodes})
    stacked_example = None
    for base_name in sorted(device_parts):
        parts = device_parts.get(base_name, set())
        if len(parts) > 1:
            stacked_example = {
                "base": base_name,
                "parts": sorted(parts),
                "terminals_union": sorted(logical_base_terminals.get(base_name, set())),
            }
            break

    stacked_groups_sample = [
        {"base": base_name, "parts": sorted(parts)}
        for base_name, parts in sorted(device_parts.items())
        if len(parts) > 1
    ][:3]

    debug = {
        "total_nodes": len(adjacency),
        "total_edges": sum(len(neighbors) for neighbors in adjacency.values()) // 2,
        "main_root_nets": sorted(_net_name(node) for node in root_nets),
        "sub_root_nets": sorted(_net_name(node) for node in sub_root_nets),
        "feeder_ends_found": sorted({feeder["feeder_end_name"] for feeder in feeders}),
        "feeder_end_bases_count": len(feeder_end_bases),
        "feeder_end_bases_sample": feeder_end_bases[:10],
        "stacked_example": stacked_example,
        "stacked_groups_sample": stacked_groups_sample,
        "logical_edges_added": logical_edges_added or 0,
        "unreachable_feeders_count": sum(1 for feeder in feeders if not feeder["reachable"]),
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
        else:
            entry["path_len_nodes"] = min(entry["path_len_nodes"], feeder["path_len_nodes"])

    aggregated = []
    for (_name, _supply), entry in sorted(grouped.items()):
        cps = sorted(entry["feeder_end_cps"], key=lambda cp: (len(cp), cp))
        if entry["device_chain_candidates"]:
            chain_lengths = {
                chain: len(chain.split(" -> ")) for chain in entry["device_chain_candidates"]
            }
            shortest_length = min(chain_lengths.values())
            shortest_chains = [
                chain
                for chain, length in chain_lengths.items()
                if length == shortest_length
            ]
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
            }
        )

    return aggregated
