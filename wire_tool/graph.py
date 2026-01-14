from __future__ import annotations

from collections import defaultdict, deque
import re
from typing import Any, Dict, Iterable, List, Set, Tuple

import pandas as pd

Node = str
Issue = Dict[str, Any]
EdgeKey = Tuple[Node, Node]


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


def _base_device_name(name: Any) -> str | None:
    name_str = _normalize_name(name)
    if not name_str:
        return None
    return name_str.split(":", 1)[0]


def _base_of(name: str) -> str:
    return name.split(":", 1)[0].split(".", 1)[0]


def _extract_root_tokens(wireno: str | None) -> List[str]:
    if not wireno:
        return []
    return [f"{match[0]}/{match[1]}" for match in _ROOT_TOKEN_PATTERN.findall(wireno)]


def _edge_key(node_a: Node, node_b: Node) -> EdgeKey:
    return tuple(sorted((node_a, node_b)))


def _add_edge(
    adjacency: Dict[Node, Set[Node]],
    edge_weights: Dict[EdgeKey, float],
    edge_kinds: Dict[EdgeKey, Set[str]],
    node_a: Node,
    node_b: Node,
    *,
    weight: float,
    kind: str,
) -> None:
    if node_a == node_b:
        return
    adjacency.setdefault(node_a, set()).add(node_b)
    adjacency.setdefault(node_b, set()).add(node_a)
    key = _edge_key(node_a, node_b)
    edge_weights[key] = min(weight, edge_weights.get(key, weight))
    edge_kinds.setdefault(key, set()).add(kind)


def build_graph(
    df_power: pd.DataFrame,
) -> Tuple[Dict[Node, Set[Node]], List[Issue], Dict[str, Any]]:
    adjacency: Dict[Node, Set[Node]] = {}
    issues: List[Issue] = []
    device_terminals: Dict[str, Set[str]] = defaultdict(set)
    base_members: Dict[str, Set[str]] = defaultdict(set)
    base_has_suffix: Dict[str, bool] = defaultdict(bool)
    edge_weights: Dict[EdgeKey, float] = {}
    edge_kinds: Dict[EdgeKey, Set[str]] = {}
    logical_edges_added = 0

    for row_index, row in df_power.iterrows():
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
            base_members[_base_of(name_a)].add(name_a)
            if "." in name_a:
                base_has_suffix[_base_of(name_a)] = True
        if name_b and cp_b:
            device_terminals[name_b].add(cp_b)
            base_members[_base_of(name_b)].add(name_b)
            if "." in name_b:
                base_has_suffix[_base_of(name_b)] = True

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
            _add_edge(
                adjacency,
                edge_weights,
                edge_kinds,
                from_node,
                to_node,
                weight=1.0,
                kind="wire",
            )

        for root in root_tokens:
            net_node = f"NET:{root}"
            if from_node:
                _add_edge(
                    adjacency,
                    edge_weights,
                    edge_kinds,
                    net_node,
                    from_node,
                    weight=1.0,
                    kind="net",
                )
            if to_node:
                _add_edge(
                    adjacency,
                    edge_weights,
                    edge_kinds,
                    net_node,
                    to_node,
                    weight=1.0,
                    kind="net",
                )

    for device_name, terminals in device_terminals.items():
        for left, right in _PASS_THROUGH_PAIRS:
            if left in terminals and right in terminals:
                node_left = f"{device_name}:{left}"
                node_right = f"{device_name}:{right}"
                _add_edge(
                    adjacency,
                    edge_weights,
                    edge_kinds,
                    node_left,
                    node_right,
                    weight=1.0,
                    kind="passthrough",
                )

    logical_groups_sample: List[Dict[str, Any]] = []
    for base, members in sorted(base_members.items()):
        if len(members) < 2 or not base_has_suffix.get(base, False):
            continue
        members_sorted = sorted(members)
        if len(logical_groups_sample) < 5:
            logical_groups_sample.append({"base": base, "members": members_sorted})
        for index, left in enumerate(members_sorted):
            for right in members_sorted[index + 1 :]:
                for term_left in device_terminals.get(left, set()):
                    for term_right in device_terminals.get(right, set()):
                        node_left = f"{left}:{term_left}"
                        node_right = f"{right}:{term_right}"
                        key = _edge_key(node_left, node_right)
                        had_logical = "logical" in edge_kinds.get(key, set())
                        _add_edge(
                            adjacency,
                            edge_weights,
                            edge_kinds,
                            node_left,
                            node_right,
                            weight=0.1,
                            kind="logical",
                        )
                        if not had_logical:
                            logical_edges_added += 1

    graph_debug = {
        "logical_edges_added": logical_edges_added,
        "logical_groups_sample": logical_groups_sample,
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
    # Filter out NET nodes and non-device labels; keep only base device names.
    names: List[str] = []
    for node in path:
        if _is_net_node(node):
            continue
        device_name = _base_of(_device_name(node))
        if not device_name.startswith("-"):
            continue
        names.append(device_name)
    return _collapse_consecutive_duplicates(names)


def _edge_weight(edge_weights: Dict[EdgeKey, float], node_a: Node, node_b: Node) -> float:
    return edge_weights.get(_edge_key(node_a, node_b), 1.0)


def _dijkstra_distances(
    adjacency: Dict[Node, Set[Node]],
    edge_weights: Dict[EdgeKey, float],
    start_nodes: Iterable[Node],
) -> Dict[Node, float]:
    import heapq

    start_list = list(start_nodes)
    if not start_list:
        return {}
    distances: Dict[Node, float] = {}
    heap: List[Tuple[float, Node]] = []
    for node in start_list:
        distances[node] = 0.0
        heapq.heappush(heap, (0.0, node))
    while heap:
        current_distance, current = heapq.heappop(heap)
        if current_distance != distances.get(current, float("inf")):
            continue
        for neighbor in adjacency.get(current, set()):
            weight = _edge_weight(edge_weights, current, neighbor)
            next_distance = current_distance + weight
            if next_distance < distances.get(neighbor, float("inf")):
                distances[neighbor] = next_distance
                heapq.heappush(heap, (next_distance, neighbor))
    return distances


def _shortest_path_to_roots(
    adjacency: Dict[Node, Set[Node]],
    edge_weights: Dict[EdgeKey, float],
    start_nodes: Iterable[Node],
    root_nodes: Set[Node],
) -> Tuple[List[Node], Node | None]:
    import heapq

    start_list = sorted(start_nodes)
    if not start_list:
        return [], None

    distances: Dict[Node, float] = {}
    parent: Dict[Node, Node | None] = {}
    heap: List[Tuple[float, Node]] = []

    for node in start_list:
        distances[node] = 0.0
        parent[node] = None
        heapq.heappush(heap, (0.0, node))

    while heap:
        current_distance, current = heapq.heappop(heap)
        if current_distance != distances.get(current, float("inf")):
            continue
        if current in root_nodes:
            path_nodes: List[Node] = [current]
            while parent[current] is not None:
                current = parent[current]
                path_nodes.append(current)
            path_nodes.reverse()
            return path_nodes, path_nodes[-1]
        for neighbor in sorted(adjacency.get(current, set())):
            weight = _edge_weight(edge_weights, current, neighbor)
            next_distance = current_distance + weight
            if next_distance < distances.get(neighbor, float("inf")):
                distances[neighbor] = next_distance
                parent[neighbor] = current
                heapq.heappush(heap, (next_distance, neighbor))

    return [], None


def _direct_net_neighbors(adjacency: Dict[Node, Set[Node]], nodes: Iterable[Node]) -> List[str]:
    nets: Set[str] = set()
    for node in nodes:
        for neighbor in adjacency.get(node, set()):
            if _is_net_node(neighbor):
                nets.add(_net_name(neighbor))
    return sorted(nets)


def compute_feeder_paths(
    adjacency: Dict[Node, Set[Node]],
    graph_debug: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Issue], Dict[str, Any]]:
    issues: List[Issue] = []
    feeders: List[Dict[str, Any]] = []
    edge_weights = graph_debug.get("edge_weights", {})
    epsilon = 1e-6

    root_nets = {
        node
        for node in adjacency
        if _is_net_node(node) and _MAIN_ROOT_PATTERN.match(_net_name(node))
    }

    base_nodes: Dict[str, Set[Node]] = defaultdict(set)
    device_nodes: Dict[str, Set[Node]] = defaultdict(set)
    for node in adjacency:
        if _is_net_node(node):
            continue
        device_id = _device_name(node)
        base = _base_of(device_id)
        base_nodes[base].add(node)
        device_nodes[device_id].add(node)

    def _is_feeder_base(base_name: str) -> bool:
        return base_name.startswith(("-F", "-Q", "-X")) and base_name != "-Q81"

    candidate_bases = {base for base in base_nodes if _is_feeder_base(base)}

    distances = _dijkstra_distances(adjacency, edge_weights, root_nets)
    base_min_distance: Dict[str, float] = {}
    for base, nodes in base_nodes.items():
        if not nodes:
            continue
        base_min_distance[base] = min(distances.get(node, float("inf")) for node in nodes)

    def _downstream_bases(base_name: str) -> Set[str]:
        start_nodes = base_nodes.get(base_name, set())
        if not start_nodes:
            return set()
        base_distance = base_min_distance.get(base_name, float("inf"))
        visited = set(start_nodes)
        queue = deque(start_nodes)
        downstream: Set[str] = set()
        while queue:
            current = queue.popleft()
            current_distance = distances.get(current, float("inf"))
            for neighbor in adjacency.get(current, set()):
                if _is_net_node(neighbor):
                    continue
                neighbor_distance = distances.get(neighbor, float("inf"))
                if neighbor_distance + epsilon < current_distance:
                    continue
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append(neighbor)
                neighbor_base = _base_of(_device_name(neighbor))
                if neighbor_base in candidate_bases:
                    neighbor_base_distance = base_min_distance.get(neighbor_base, float("inf"))
                    if neighbor_base_distance > base_distance + epsilon:
                        downstream.add(neighbor_base)
        return downstream

    downstream_map = {base: _downstream_bases(base) for base in candidate_bases}
    feeder_bases = {base for base in candidate_bases if not downstream_map.get(base)}

    def _prefer_downstream_q(bases: Set[str]) -> Set[str]:
        preferred = set(bases)
        for base in list(bases):
            if not base.startswith("-F"):
                continue
            for downstream_base in downstream_map.get(base, set()):
                if downstream_base.startswith("-Q"):
                    preferred.discard(base)
                    break
        return preferred

    feeder_bases = _prefer_downstream_q(feeder_bases)
    feeder_nodes_sorted = sorted(
        node
        for base in feeder_bases
        for node in base_nodes.get(base, set())
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

    logical_connectivity_checks: Dict[str, str] = {}
    left_device = "-F121.2"
    right_device = "-F121.1"
    left_nodes = device_nodes.get(left_device, set())
    right_nodes = device_nodes.get(right_device, set())
    if not left_nodes or not right_nodes:
        logical_connectivity_checks[f"{left_device}_to_{right_device}"] = "not_present"
    else:
        visited = set(left_nodes)
        queue = deque(left_nodes)
        reachable = False
        while queue and not reachable:
            current = queue.popleft()
            if current in right_nodes:
                reachable = True
                break
            for neighbor in adjacency.get(current, set()):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append(neighbor)
        logical_connectivity_checks[f"{left_device}_to_{right_device}"] = (
            "reachable" if reachable else "not_reachable"
        )

    debug = {
        "total_nodes": len(adjacency),
        "total_edges": sum(len(neighbors) for neighbors in adjacency.values()) // 2,
        "main_root_nets": sorted(_net_name(node) for node in root_nets),
        "sub_root_nets": [],
        "feeder_ends_found": sorted({feeder["feeder_end_name"] for feeder in feeders}),
        "unreachable_feeders_count": sum(1 for feeder in feeders if not feeder["reachable"]),
        "logical_connectivity_checks": logical_connectivity_checks,
    }
    debug.update(graph_debug)

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
