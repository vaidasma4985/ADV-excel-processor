from __future__ import annotations

from collections import defaultdict
import heapq
import re
from typing import Any, Dict, Iterable, List, Set, Tuple

import pandas as pd

Node = str
Issue = Dict[str, Any]


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


def _extract_root_tokens(wireno: str | None) -> List[str]:
    if not wireno:
        return []
    return [f"{match[0]}/{match[1]}" for match in _ROOT_TOKEN_PATTERN.findall(wireno)]


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


def build_graph(
    df_power: pd.DataFrame,
    device_templates: Dict[str, Dict[str, Any]] | None = None,
) -> Tuple[
    Dict[Node, Set[Node]],
    List[Issue],
    Dict[str, Set[str]],
    Dict[str, Set[str]],
    Dict[str, int],
]:
    adjacency: Dict[Node, Set[Node]] = {}
    issues: List[Issue] = []
    device_terminals: Dict[str, Set[str]] = defaultdict(set)
    device_parts: Dict[str, Set[str]] = defaultdict(set)

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
        if name_b and cp_b:
            device_terminals[name_b].add(cp_b)
        if name_a_raw and name_a:
            device_parts[_logical_base_name(name_a)].add(name_a)
        if name_b_raw and name_b:
            device_parts[_logical_base_name(name_b)].add(name_b)

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

    for device_name, terminals in device_terminals.items():
        for left, right in _PASS_THROUGH_PAIRS:
            if left in terminals and right in terminals:
                node_left = f"{device_name}:{left}"
                node_right = f"{device_name}:{right}"
                adjacency.setdefault(node_left, set()).add(node_right)
                adjacency.setdefault(node_right, set()).add(node_left)

    if device_templates:
        _add_template_edges(adjacency, device_terminals, device_templates)

    logical_edges_stats = _add_logical_edges(adjacency, device_terminals, device_parts)

    return adjacency, issues, device_terminals, device_parts, logical_edges_stats


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


def _stacked_split_role(terminals: Set[str]) -> str | None:
    front_neutrals = {"N", "7N"}
    back_neutrals = {"N'", "8N"}
    has_odd = any(term.isdigit() and int(term) % 2 == 1 for term in terminals)
    has_even = any(term.isdigit() and int(term) % 2 == 0 for term in terminals)
    has_front_neutral = any(term in front_neutrals for term in terminals)
    has_back_neutral = any(term in back_neutrals for term in terminals)
    has_front = has_odd or has_front_neutral
    has_back = has_even or has_back_neutral
    if has_front and not has_back:
        return "front"
    if has_back and not has_front:
        return "back"
    return None


def _add_logical_edges(
    adjacency: Dict[Node, Set[Node]],
    device_terminals: Dict[str, Set[str]],
    logical_groups: Dict[str, Set[str]],
) -> Dict[str, int]:
    logical_edges_added = 0
    logical_edges_skipped = 0
    for base_name in sorted(logical_groups):
        parts = sorted(logical_groups[base_name])
        if len(parts) < 2:
            continue
        for left, right in zip(parts, parts[1:]):
            terminals_left = device_terminals.get(left, set())
            terminals_right = device_terminals.get(right, set())
            role_left = _stacked_split_role(terminals_left)
            role_right = _stacked_split_role(terminals_right)
            if not role_left or not role_right or role_left == role_right:
                logical_edges_skipped += 1
                continue
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
    return {
        "added": logical_edges_added,
        "skipped": logical_edges_skipped,
    }


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


def identify_root_devices(adjacency: Dict[Node, Set[Node]]) -> Set[str]:
    root_nets = {
        node
        for node in adjacency
        if _is_net_node(node) and _MAIN_ROOT_PATTERN.match(_net_name(node))
    }
    device_nodes = [node for node in adjacency if not _is_net_node(node)]
    root_devices: Set[str] = set()
    for node in device_nodes:
        name = _device_name(node)
        if not any(net in root_nets for net in adjacency.get(node, set())):
            continue
        has_external_device_neighbor = False
        for neighbor in adjacency.get(node, set()):
            if _is_net_node(neighbor):
                continue
            if _device_name(neighbor) != name:
                has_external_device_neighbor = True
                break
        if not has_external_device_neighbor:
            root_devices.add(name)
    return root_devices


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
    logical_edges_added: Dict[str, int] | int | None = None,
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
    q_heuristic_applied = 0
    q_heuristic_blocked_nodes = 0

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
        q_blocked_nodes = set()
        q_match = re.match(r"^-Q(\d+)$", feeder_name)
        if q_match and feeder_name != "-Q81":
            q_digits = q_match.group(1)
            if len(q_digits) >= 3:
                f_prefix = q_digits[:-1]
                preferred_prefix = f"-F{f_prefix}"
                preferred_devices = {
                    name for name in device_names if name.startswith(preferred_prefix)
                }
                if preferred_devices:
                    group_prefix = q_digits[:-2]
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
        "feeder_end_bases_count": len(feeder_end_bases),
        "feeder_end_bases_sample": feeder_end_bases[:10],
        "stacked_example": stacked_example,
        "stacked_groups_sample": stacked_groups_sample,
        "logical_edges_added": logical_edges_stats.get("added", 0),
        "logical_edges_skipped": logical_edges_stats.get("skipped", 0),
        "q_branch_heuristic_applied_count": q_heuristic_applied,
        "q_branch_heuristic_blocked_nodes": q_heuristic_blocked_nodes,
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
