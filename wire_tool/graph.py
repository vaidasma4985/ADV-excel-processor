from __future__ import annotations

from collections import defaultdict, deque
import heapq
import re
from typing import Any, Dict, Iterable, List, Set, Tuple

import pandas as pd

Node = str
Issue = Dict[str, Any]
GraphDebug = Dict[str, Any]


_MAIN_ROOT_PATTERN = re.compile(r"^(MT|IT|LT)/(L1|L2|L3)$")
_ROOT_TOKEN_PATTERN = re.compile(r"(MT|IT|LT)/(L1|L2|L3)")
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


def _strip_terminal_suffix(name: str) -> str:
    return name.split(":", 1)[0]


def _base_device_name(name: Any) -> str | None:
    name_str = _normalize_name(name)
    if not name_str:
        return None
    return _strip_terminal_suffix(name_str)


def _extract_root_tokens(wireno: str | None) -> List[str]:
    if not wireno:
        return []
    return [f"{match[0]}/{match[1]}" for match in _ROOT_TOKEN_PATTERN.findall(wireno)]


def _feeder_device_base(name: str) -> str | None:
    if not name:
        return None
    match = re.match(r"^-(?P<prefix>[FQ])(?P<num>\d+)(?:\.\d+)?$", name)
    if not match:
        return None
    return f"-{match.group('prefix')}{match.group('num')}"


def _split_logical_base(name: str) -> Tuple[str | None, bool]:
    m = re.match(r"^(?P<base>-(?:F|Q)\d+)(?P<suffix>\.\d+)?$", name)
    if not m:
        return None, False
    base = m.group("base")
    return base, bool(m.group("suffix"))


def _add_edge(
    adjacency: Dict[Node, Set[Node]],
    edge_weights: Dict[Tuple[Node, Node], float],
    edge_kinds: Dict[Tuple[Node, Node], str],
    left_node: Node,
    right_node: Node,
    kind: str,
    weight: float,
) -> None:
    adjacency.setdefault(left_node, set()).add(right_node)
    adjacency.setdefault(right_node, set()).add(left_node)
    edge = tuple(sorted((left_node, right_node)))
    edge_weights[edge] = weight
    edge_kinds[edge] = kind


def _add_logical_edges(
    adjacency: Dict[Node, Set[Node]],
    edge_weights: Dict[Tuple[Node, Node], float],
    edge_kinds: Dict[Tuple[Node, Node], str],
    device_terminals: Dict[str, Set[str]],
) -> Tuple[int, List[Dict[str, Any]]]:
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
                        _add_edge(
                            adjacency,
                            edge_weights,
                            edge_kinds,
                            left_node,
                            right_node,
                            kind="logical",
                            weight=0.1,
                        )
                        logical_edges.add(tuple(sorted((left_node, right_node))))

    return len(logical_edges), sample_groups[:5]


def build_graph(df_power: pd.DataFrame) -> Tuple[Dict[Node, Set[Node]], List[Issue], GraphDebug]:
    adjacency: Dict[Node, Set[Node]] = {}
    issues: List[Issue] = []
    device_terminals: Dict[str, Set[str]] = defaultdict(set)
    edge_weights: Dict[Tuple[Node, Node], float] = {}
    edge_kinds: Dict[Tuple[Node, Node], str] = {}

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
            _add_edge(adjacency, edge_weights, edge_kinds, from_node, to_node, "wire", 1.0)

        for root in root_tokens:
            net_node = f"NET:{root}"
            adjacency.setdefault(net_node, set())
            if from_node:
                _add_edge(adjacency, edge_weights, edge_kinds, net_node, from_node, "net", 1.0)
            if to_node:
                _add_edge(adjacency, edge_weights, edge_kinds, net_node, to_node, "net", 1.0)

    for device_name, terminals in device_terminals.items():
        for left, right in _PASS_THROUGH_PAIRS:
            if left in terminals and right in terminals:
                node_left = f"{device_name}:{left}"
                node_right = f"{device_name}:{right}"
                _add_edge(
                    adjacency, edge_weights, edge_kinds, node_left, node_right, "internal", 1.0
                )

    logical_edges_count, logical_groups = _add_logical_edges(
        adjacency,
        edge_weights,
        edge_kinds,
        device_terminals,
    )

    graph_debug: GraphDebug = {
        "logical_edges_added": logical_edges_count,
        "logical_groups_sample": logical_groups,
        "edge_weights": edge_weights,
        "edge_kinds": edge_kinds,
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
    # Filter out NET nodes and non-device labels; keep device names only.
    names: List[str] = []
    for node in path:
        if _is_net_node(node):
            continue
        device_name = _device_name(node)
        if not device_name.startswith("-"):
            continue
        names.append(device_name)
    return _collapse_consecutive_duplicates(names)


def _shortest_path_to_roots(
    adjacency: Dict[Node, Set[Node]],
    edge_weights: Dict[Tuple[Node, Node], float],
    start_nodes: Iterable[Node],
    root_nodes: Set[Node],
) -> Tuple[List[Node], Node | None]:
    start_list = sorted(start_nodes)
    if not start_list:
        return [], None

    distances: Dict[Node, float] = {}
    parent: Dict[Node, Node] = {}
    heap: List[Tuple[float, Node]] = []

    for node in start_list:
        distances[node] = 0.0
        heapq.heappush(heap, (0.0, node))

    while heap:
        current_distance, current = heapq.heappop(heap)
        if current_distance != distances.get(current):
            continue
        if current in root_nodes:
            path_nodes: List[Node] = [current]
            while current not in start_list:
                current = parent[current]
                path_nodes.append(current)
            path_nodes.reverse()
            return path_nodes, path_nodes[-1]
        for neighbor in adjacency.get(current, set()):
            edge = tuple(sorted((current, neighbor)))
            weight = edge_weights.get(edge, 1.0)
            tentative = current_distance + weight
            if tentative < distances.get(neighbor, float("inf")):
                distances[neighbor] = tentative
                parent[neighbor] = current
                heapq.heappush(heap, (tentative, neighbor))

    return [], None


def _direct_net_neighbors(adjacency: Dict[Node, Set[Node]], nodes: Iterable[Node]) -> List[str]:
    nets: Set[str] = set()
    for node in nodes:
        for neighbor in adjacency.get(node, set()):
            if _is_net_node(neighbor):
                nets.add(_net_name(neighbor))
    return sorted(nets)


def _dijkstra_distances(
    adjacency: Dict[Node, Set[Node]],
    edge_weights: Dict[Tuple[Node, Node], float],
    start_nodes: Iterable[Node],
) -> Dict[Node, float]:
    distances: Dict[Node, float] = {}
    heap: List[Tuple[float, Node]] = []
    for node in start_nodes:
        distances[node] = 0.0
        heapq.heappush(heap, (0.0, node))

    while heap:
        current_distance, current = heapq.heappop(heap)
        if current_distance != distances.get(current):
            continue
        for neighbor in adjacency.get(current, set()):
            edge = tuple(sorted((current, neighbor)))
            weight = edge_weights.get(edge, 1.0)
            tentative = current_distance + weight
            if tentative < distances.get(neighbor, float("inf")):
                distances[neighbor] = tentative
                heapq.heappush(heap, (tentative, neighbor))
    return distances


def _device_nodes(adjacency: Dict[Node, Set[Node]]) -> Dict[str, Set[Node]]:
    devices: Dict[str, Set[Node]] = defaultdict(set)
    for node in adjacency:
        if _is_net_node(node):
            continue
        devices[_device_name(node)].add(node)
    return devices


def _find_downstream_feeder_base(
    adjacency: Dict[Node, Set[Node]],
    root_nodes: Set[Node],
    distances: Dict[Node, float],
    base_min_distance: Dict[str, float],
    base_to_nodes: Dict[str, Set[Node]],
    start_base: str,
    eligible_bases: Set[str],
) -> bool:
    start_nodes = base_to_nodes.get(start_base, set())
    if not start_nodes:
        return False
    start_distance = base_min_distance[start_base]
    queue: deque[Node] = deque(start_nodes)
    visited: Set[Node] = set(start_nodes)
    epsilon = 1e-6

    while queue:
        current = queue.popleft()
        for neighbor in adjacency.get(current, set()):
            if neighbor in visited or neighbor in root_nodes:
                continue
            neighbor_distance = distances.get(neighbor)
            if neighbor_distance is None:
                continue
            if neighbor_distance + epsilon < start_distance:
                continue
            visited.add(neighbor)
            if not _is_net_node(neighbor):
                neighbor_base = _feeder_device_base(_device_name(neighbor))
                if (
                    neighbor_base
                    and neighbor_base != start_base
                    and neighbor_base in eligible_bases
                    and base_min_distance.get(neighbor_base, -1.0)
                    > start_distance + epsilon
                ):
                    return True
            queue.append(neighbor)
    return False


def _prefer_downstream_q(
    adjacency: Dict[Node, Set[Node]],
    root_nodes: Set[Node],
    distances: Dict[Node, float],
    base_min_distance: Dict[str, float],
    base_to_nodes: Dict[str, Set[Node]],
    candidate_bases: Set[str],
) -> Set[str]:
    filtered = set(candidate_bases)
    epsilon = 1e-6
    q_bases = {base for base in candidate_bases if base.startswith("-Q")}
    if not q_bases:
        return filtered

    for base in sorted(candidate_bases):
        if not base.startswith("-F"):
            continue
        start_nodes = base_to_nodes.get(base, set())
        if not start_nodes:
            continue
        start_distance = base_min_distance[base]
        queue: deque[Node] = deque(start_nodes)
        visited: Set[Node] = set(start_nodes)
        while queue:
            current = queue.popleft()
            for neighbor in adjacency.get(current, set()):
                if neighbor in visited or neighbor in root_nodes:
                    continue
                neighbor_distance = distances.get(neighbor)
                if neighbor_distance is None:
                    continue
                if neighbor_distance + epsilon < start_distance:
                    continue
                visited.add(neighbor)
                if not _is_net_node(neighbor):
                    neighbor_base = _feeder_device_base(_device_name(neighbor))
                    if (
                        neighbor_base
                        and neighbor_base in q_bases
                        and base_min_distance.get(neighbor_base, -1.0)
                        > start_distance + epsilon
                    ):
                        filtered.discard(base)
                        queue.clear()
                        break
                queue.append(neighbor)
    return filtered


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
    edge_weights = (graph_debug or {}).get("edge_weights", {})

    root_nets = {
        node
        for node in adjacency
        if _is_net_node(node) and _MAIN_ROOT_PATTERN.match(_net_name(node))
    }
    device_nodes = _device_nodes(adjacency)
    excluded_devices = {"-Q81"}
    eligible_device_names = {
        name
        for name in device_nodes
        if _feeder_device_base(name) is not None and name not in excluded_devices
    }
    base_to_devices: Dict[str, Set[str]] = defaultdict(set)
    base_to_nodes: Dict[str, Set[Node]] = defaultdict(set)

    for device_name, nodes in device_nodes.items():
        if device_name not in eligible_device_names:
            continue
        base = _feeder_device_base(device_name)
        if base is None:
            continue
        base_to_devices[base].add(device_name)
        base_to_nodes[base].update(nodes)

    eligible_bases = {base for base in base_to_devices if base_to_devices[base]}

    distances = _dijkstra_distances(adjacency, edge_weights, root_nets)
    base_min_distance: Dict[str, float] = {}
    reachable_bases: Set[str] = set()

    for base, nodes in base_to_nodes.items():
        reachable_node_distances = [distances[node] for node in nodes if node in distances]
        if not reachable_node_distances:
            continue
        reachable_bases.add(base)
        base_min_distance[base] = min(reachable_node_distances)

    feeder_end_bases: Set[str] = set()
    for base in sorted(eligible_bases):
        if base not in reachable_bases:
            continue
        has_downstream = _find_downstream_feeder_base(
            adjacency,
            root_nets,
            distances,
            base_min_distance,
            base_to_nodes,
            base,
            eligible_bases,
        )
        if not has_downstream:
            feeder_end_bases.add(base)

    feeder_end_bases = _prefer_downstream_q(
        adjacency,
        root_nets,
        distances,
        base_min_distance,
        base_to_nodes,
        feeder_end_bases,
    )

    feeder_nodes_sorted = sorted(
        node for base in feeder_end_bases for node in base_to_nodes.get(base, set())
    )

    for feeder_node in feeder_nodes_sorted:
        feeder_name = _device_name(feeder_node)
        feeder_cp = feeder_node.split(":", 1)[1] if ":" in feeder_node else ""
        direct_nets = _direct_net_neighbors(adjacency, [feeder_node])

        path_any, supply_any = _shortest_path_to_roots(
            adjacency,
            edge_weights,
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
        "logical_connectivity_checks": {
            "-F121.2_to_-F121.1": (
                "reachable"
                if _reachable_between_devices(
                    adjacency,
                    device_nodes,
                    "-F121.2",
                    "-F121.1",
                )
                else "not_reachable"
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
