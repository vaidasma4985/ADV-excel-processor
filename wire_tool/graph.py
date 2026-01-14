from __future__ import annotations

from collections import defaultdict, deque
import re
from typing import Any, Dict, Iterable, List, Set, Tuple

import pandas as pd

Node = str
Issue = Dict[str, Any]
GraphDebug = Dict[str, Any]


_MAIN_ROOT_PATTERN = re.compile(r"^(MT|IT|LT)/(L1|L2|L3|N)$")
_ROOT_TOKEN_PATTERN = re.compile(r"(MT|IT|LT)/(L1|L2|L3|N)")
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
    return str(value).strip() or None


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
    return name.split(":", 1)[0].split(".", 1)[0]


def _base_device_name(name: Any) -> str | None:
    name_str = _normalize_name(name)
    if not name_str:
        return None
    return _strip_contact_suffix(name_str)


def _extract_root_tokens(wireno: str | None) -> List[str]:
    if not wireno:
        return []
    return [f"{match[0]}/{match[1]}" for match in _ROOT_TOKEN_PATTERN.findall(wireno)]


def _split_logical_base(name: str) -> Tuple[str | None, bool]:
    m = re.match(r"^(?P<base>-[A-Z]+\d+)(?P<suffix>\.\d+)?$", name)
    if not m:
        return None, False
    base = m.group("base")
    if not base.startswith(("-F", "-Q")):
        return None, False
    return base, bool(m.group("suffix"))


def _add_logical_edges(
    adjacency: Dict[Node, Set[Node]],
    device_terminals: Dict[str, Set[str]],
) -> Tuple[int, List[Dict[str, Any]], Dict[Tuple[str, str], str]]:
    base_groups: Dict[str, List[str]] = defaultdict(list)
    base_has_suffix: Dict[str, bool] = defaultdict(bool)

    for device_name in device_terminals:
        base, has_suffix = _split_logical_base(device_name)
        if base is None:
            continue
        base_groups[base].append(device_name)
        if has_suffix:
            base_has_suffix[base] = True

    logical_edges: Set[Tuple[Node, Node]] = set()
    logical_edge_types: Dict[Tuple[str, str], str] = {}
    sample_groups: List[Dict[str, Any]] = []

    for base, devices in sorted(base_groups.items()):
        if not base_has_suffix[base]:
            continue
        if len(devices) < 2:
            continue
        sample_groups.append({"base": base, "parts": sorted(devices)})
        for i, left in enumerate(devices):
            for right in devices[i + 1 :]:
                for left_term in device_terminals.get(left, set()):
                    for right_term in device_terminals.get(right, set()):
                        left_node = f"{left}:{left_term}"
                        right_node = f"{right}:{right_term}"
                        adjacency.setdefault(left_node, set()).add(right_node)
                        adjacency.setdefault(right_node, set()).add(left_node)
                        edge = tuple(sorted((left_node, right_node)))
                        logical_edges.add(edge)
                        logical_edge_types[edge] = "logical"

    return len(logical_edges), sample_groups[:5], logical_edge_types


def build_graph(df_power: pd.DataFrame) -> Tuple[Dict[Node, Set[Node]], List[Issue], GraphDebug]:
    adjacency: Dict[Node, Set[Node]] = {}
    issues: List[Issue] = []
    device_terminals: Dict[str, Set[str]] = defaultdict(set)

    for row_index, row in df_power.iterrows():
        if "Line-Function" in row and row["Line-Function"] != "Power":
            continue
        wireno = _normalize_wireno(row.get("Wireno"))
        root_tokens = _extract_root_tokens(wireno)

        name_a = _base_device_name(row.get("Name"))
        cp_a = _normalize_terminal(row.get("C.name"))
        name_b = _base_device_name(row.get("Name.1"))
        cp_b = _normalize_terminal(row.get("C.name.1"))

        from_node = _device_node(name_a, cp_a)
        to_node = _device_node(name_b, cp_b)

        if name_a and cp_a:
            device_terminals[name_a].add(cp_a)
        if name_b and cp_b:
            device_terminals[name_b].add(cp_b)

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
            adjacency[from_node].add(to_node)
            adjacency[to_node].add(from_node)

        for root in root_tokens:
            net_node = f"NET:{root}"
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

    logical_edges_count, logical_groups, logical_edge_types = _add_logical_edges(
        adjacency,
        device_terminals,
    )

    graph_debug: GraphDebug = {
        "logical_edges_added": logical_edges_count,
        "logical_groups_sample": logical_groups,
        "logical_edge_types": logical_edge_types,
    }

    return adjacency, issues, graph_debug


def _compress_path_names(path: List[Node]) -> List[str]:
    collapsed: List[str] = []
    last_name: str | None = None

    for node in path:
        if _is_net_node(node):
            name = _net_name(node)
        else:
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


def _shortest_path_to_roots(
    adjacency: Dict[Node, Set[Node]],
    start_nodes: Iterable[Node],
    root_nodes: Set[Node],
) -> Tuple[List[Node], Node | None]:
    start_list = sorted(start_nodes)
    if not start_list:
        return [], None

    visited: Set[Node] = set(start_list)
    parent: Dict[Node, Node] = {}
    queue: deque[Node] = deque(start_list)

    while queue:
        current = queue.popleft()
        if current in root_nodes:
            path_nodes: List[Node] = [current]
            while current not in start_list:
                current = parent[current]
                path_nodes.append(current)
            path_nodes.reverse()
            return path_nodes, path_nodes[-1]
        for neighbor in sorted(adjacency.get(current, set())):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            parent[neighbor] = current
            queue.append(neighbor)

    return [], None


def _direct_net_neighbors(adjacency: Dict[Node, Set[Node]], nodes: Iterable[Node]) -> List[str]:
    nets: Set[str] = set()
    for node in nodes:
        for neighbor in adjacency.get(node, set()):
            if _is_net_node(neighbor):
                nets.add(_net_name(neighbor))
    return sorted(nets)


def _bfs_distances(adjacency: Dict[Node, Set[Node]], start_nodes: Iterable[Node]) -> Dict[Node, int]:
    distances: Dict[Node, int] = {}
    queue: deque[Node] = deque()
    for node in start_nodes:
        distances[node] = 0
        queue.append(node)

    while queue:
        current = queue.popleft()
        for neighbor in adjacency.get(current, set()):
            if neighbor in distances:
                continue
            distances[neighbor] = distances[current] + 1
            queue.append(neighbor)
    return distances


def _device_nodes(adjacency: Dict[Node, Set[Node]]) -> Dict[str, Set[Node]]:
    devices: Dict[str, Set[Node]] = defaultdict(set)
    for node in adjacency:
        if _is_net_node(node):
            continue
        devices[_device_name(node)].add(node)
    return devices


def _find_downstream_feeder(
    adjacency: Dict[Node, Set[Node]],
    device_nodes: Dict[str, Set[Node]],
    root_nodes: Set[Node],
    distances: Dict[Node, int],
    device_min_distance: Dict[str, int],
    start_device: str,
    eligible_devices: Set[str],
) -> bool:
    start_nodes = device_nodes.get(start_device, set())
    if not start_nodes:
        return False
    start_distance = device_min_distance[start_device]
    queue: deque[Node] = deque(start_nodes)
    visited: Set[Node] = set(start_nodes)

    while queue:
        current = queue.popleft()
        for neighbor in adjacency.get(current, set()):
            if neighbor in visited or neighbor in root_nodes:
                continue
            if neighbor not in distances:
                continue
            if distances[neighbor] < start_distance:
                continue
            visited.add(neighbor)
            if not _is_net_node(neighbor):
                neighbor_device = _device_name(neighbor)
                if (
                    neighbor_device != start_device
                    and neighbor_device in eligible_devices
                    and device_min_distance.get(neighbor_device, -1) > start_distance
                ):
                    return True
            queue.append(neighbor)
    return False


def _reachable_between_devices(
    adjacency: Dict[Node, Set[Node]],
    device_nodes: Dict[str, Set[Node]],
    left_device: str,
    right_device: str,
) -> bool:
    start_nodes = device_nodes.get(left_device, set())
    target_nodes = device_nodes.get(right_device, set())
    if not start_nodes or not target_nodes:
        return False
    visited: Set[Node] = set(start_nodes)
    queue: deque[Node] = deque(start_nodes)
    while queue:
        current = queue.popleft()
        if current in target_nodes:
            return True
        for neighbor in adjacency.get(current, set()):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            queue.append(neighbor)
    return False


def compute_feeder_paths(
    adjacency: Dict[Node, Set[Node]],
    graph_debug: GraphDebug | None = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Issue], Dict[str, Any]]:
    issues: List[Issue] = []
    feeders: List[Dict[str, Any]] = []

    root_nets = {
        node
        for node in adjacency
        if _is_net_node(node) and _MAIN_ROOT_PATTERN.match(_net_name(node))
    }
    device_nodes = _device_nodes(adjacency)
    eligible_pattern = re.compile(r"^-(Q|F)\d+")
    excluded_devices = {"-Q81"}
    eligible_devices = {
        name
        for name in device_nodes
        if eligible_pattern.match(name) and name not in excluded_devices
    }

    distances = _bfs_distances(adjacency, root_nets)
    device_min_distance: Dict[str, int] = {}
    reachable_devices: Set[str] = set()

    for device_name, nodes in device_nodes.items():
        reachable_node_distances = [distances[node] for node in nodes if node in distances]
        if not reachable_node_distances:
            continue
        reachable_devices.add(device_name)
        device_min_distance[device_name] = min(reachable_node_distances)

    feeder_end_devices = []
    for device_name in sorted(eligible_devices):
        if device_name not in reachable_devices:
            continue
        has_downstream = _find_downstream_feeder(
            adjacency,
            device_nodes,
            root_nets,
            distances,
            device_min_distance,
            device_name,
            eligible_devices,
        )
        if not has_downstream:
            feeder_end_devices.append(device_name)

    feeder_nodes_sorted = sorted(
        node for device in feeder_end_devices for node in device_nodes.get(device, set())
    )

    for feeder_node in feeder_nodes_sorted:
        feeder_name = _device_name(feeder_node)
        feeder_cp = feeder_node.split(":", 1)[1] if ":" in feeder_node else ""
        direct_nets = _direct_net_neighbors(adjacency, [feeder_node])

        path_any, supply_any = _shortest_path_to_roots(
            adjacency,
            [feeder_node],
            root_nets,
        )

        reachable = bool(path_any)
        if not reachable:
            issues.append(
                _issue(
                    "ERROR",
                    "W202",
                    "Feeder end is unreachable from any root net (MT/IT/LT).",
                    context={
                        "feeder_name": feeder_name,
                        "feeder_cp": feeder_cp,
                        "direct_nets": direct_nets,
                    },
                )
            )

        supply_net = _net_name(supply_any) if supply_any else ""
        path_nodes_raw = " -> ".join(path_any)
        path_names_collapsed = " -> ".join(_compress_path_names(path_any))
        device_chain = " -> ".join(_extract_device_names_from_path(path_any))

        feeders.append(
            {
                "feeder_end_name": feeder_name,
                "feeder_end_cp": feeder_cp,
                "supply_net": supply_net,
                "reachable": reachable,
                "path_nodes_raw": path_nodes_raw,
                "path_names_collapsed": path_names_collapsed,
                "device_chain": device_chain,
                "path_len_nodes": len(path_any),
            }
        )

    aggregated = _aggregate_feeder_paths(feeders)

    debug = {
        "total_nodes": len(adjacency),
        "total_edges": sum(len(neighbors) for neighbors in adjacency.values()) // 2,
        "main_root_nets": sorted(_net_name(node) for node in root_nets),
        "sub_root_nets": [],
        "feeder_ends_found": sorted({feeder["feeder_end_name"] for feeder in feeders}),
        "unreachable_feeders_count": sum(1 for feeder in feeders if not feeder["reachable"]),
        "logical_edges_added": (graph_debug or {}).get("logical_edges_added", 0),
        "logical_groups_sample": (graph_debug or {}).get("logical_groups_sample", []),
        "logical_edge_types": (graph_debug or {}).get("logical_edge_types", {}),
        "logical_connectivity_checks": {
            "-F121.2_to_-F121.1": _reachable_between_devices(
                adjacency,
                device_nodes,
                "-F121.2",
                "-F121.1",
            )
            if "-F121.2" in device_nodes and "-F121.1" in device_nodes
            else "not_present",
        },
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
                "path_names_collapsed": entry["path_names_collapsed"],
                "device_chain_grouped": entry["device_chain_grouped"],
                "reachable": entry["reachable"],
                "path_len_nodes": entry["path_len_nodes"],
            }
        )

    return aggregated
