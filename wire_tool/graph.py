from __future__ import annotations

from collections import deque
from typing import Any, Dict, Iterable, List, Set, Tuple

import pandas as pd

Node = str
Issue = Dict[str, Any]


SUPPLY_PREFIXES = ("MT/", "IT/", "LT/")


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


def _device_node(name: Any, cp: Any) -> Node | None:
    if _is_missing(name):
        return None
    name_str = str(name).strip()
    if _is_missing(cp):
        return name_str
    cp_str = str(cp).strip()
    if not cp_str:
        return name_str
    return f"{name_str}:{cp_str}"


def _device_name(node: Node) -> str:
    return node.split(":", 1)[0]


def _is_net_node(node: Node) -> bool:
    return node.startswith("NET:")


def _net_name(node: Node) -> str:
    return node.replace("NET:", "", 1)


def build_graph(df_power: pd.DataFrame) -> Tuple[Dict[Node, Set[Node]], List[Issue]]:
    adjacency: Dict[Node, Set[Node]] = {}
    issues: List[Issue] = []

    for row_index, row in df_power.iterrows():
        wireno = _normalize_wireno(row.get("Wireno"))
        net_node = f"NET:{wireno}" if wireno else None

        from_node = _device_node(row.get("Name"), row.get("C.name"))
        to_node = _device_node(row.get("Name.1"), row.get("C.name.1"))

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

        nodes = [node for node in (from_node, to_node, net_node) if node]
        for node in nodes:
            adjacency.setdefault(node, set())

        if net_node and from_node:
            adjacency[net_node].add(from_node)
            adjacency[from_node].add(net_node)
        if net_node and to_node:
            adjacency[net_node].add(to_node)
            adjacency[to_node].add(net_node)
        if from_node and to_node:
            adjacency[from_node].add(to_node)
            adjacency[to_node].add(from_node)

    return adjacency, issues


def bfs_parents(adjacency: Dict[Node, Set[Node]], start_nodes: Iterable[Node]) -> Dict[Node, Node]:
    start_list = sorted(start_nodes)
    visited: Set[Node] = set(start_list)
    parent: Dict[Node, Node] = {}
    queue: deque[Node] = deque(start_list)

    while queue:
        current = queue.popleft()
        neighbors = sorted(adjacency.get(current, set()))
        for neighbor in neighbors:
            if neighbor in visited:
                continue
            visited.add(neighbor)
            parent[neighbor] = current
            queue.append(neighbor)

    return parent


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


def _shortest_path_to_supply(
    adjacency: Dict[Node, Set[Node]],
    start_nodes: Iterable[Node],
    supply_roots: Set[Node],
) -> Tuple[List[Node], Node | None]:
    start_list = sorted(start_nodes)
    visited: Set[Node] = set(start_list)
    parent: Dict[Node, Node] = {}
    queue: deque[Node] = deque(start_list)

    while queue:
        current = queue.popleft()
        if current in supply_roots:
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


def compute_feeder_paths(
    adjacency: Dict[Node, Set[Node]],
) -> Tuple[List[Dict[str, Any]], List[Issue], Dict[str, Any]]:
    issues: List[Issue] = []
    feeders: List[Dict[str, Any]] = []

    supply_roots = {
        node
        for node in adjacency
        if _is_net_node(node) and _net_name(node).startswith(SUPPLY_PREFIXES)
    }

    feeder_nodes = [
        node
        for node in adjacency
        if not _is_net_node(node)
        and _device_name(node).startswith(("-F", "-Q"))
        and _device_name(node) != "-Q81"
    ]
    feeder_names = sorted({_device_name(node) for node in feeder_nodes})

    for feeder_name in feeder_names:
        candidate_nodes = [node for node in feeder_nodes if _device_name(node) == feeder_name]
        path_nodes, supply_node = _shortest_path_to_supply(
            adjacency,
            candidate_nodes,
            supply_roots,
        )
        reachable = bool(path_nodes)

        if not reachable:
            issues.append(
                _issue(
                    "ERROR",
                    "W202",
                    "Feeder end is unreachable from any supply root net.",
                    context={"feeder_name": feeder_name},
                )
            )

        supply_net = _net_name(supply_node) if supply_node else ""
        path_nodes_raw = " -> ".join(path_nodes)
        path_names_collapsed = " -> ".join(_compress_path_names(path_nodes))

        feeders.append(
            {
                "feeder_end_name": feeder_name,
                "supply_net": supply_net,
                "path_nodes_raw": path_nodes_raw,
                "path_names_collapsed": path_names_collapsed,
                "path_len_nodes": len(path_nodes),
                "reachable": reachable,
            }
        )

    debug = {
        "total_nodes": len(adjacency),
        "total_edges": sum(len(neighbors) for neighbors in adjacency.values()) // 2,
        "supply_root_nets_found": sorted(_net_name(node) for node in supply_roots),
        "feeder_ends_found": feeder_names,
        "unreachable_feeders_count": sum(1 for feeder in feeders if not feeder["reachable"]),
    }

    return feeders, issues, debug
