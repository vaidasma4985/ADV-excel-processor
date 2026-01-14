from __future__ import annotations

from collections import deque
from typing import Any, Dict, Iterable, List, Set, Tuple

import pandas as pd

Node = Tuple[str, str]
Issue = Dict[str, Any]


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return pd.isna(value)


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


def build_graph(df_power: pd.DataFrame) -> Tuple[Dict[Node, Set[Node]], List[Issue]]:
    adjacency: Dict[Node, Set[Node]] = {}
    issues: List[Issue] = []

    for row_index, row in df_power.iterrows():
        name_a = row.get("Name")
        cp_a = row.get("C.name")
        name_b = row.get("Name.1")
        cp_b = row.get("C.name.1")

        if _is_missing(name_a) or _is_missing(cp_a) or _is_missing(name_b) or _is_missing(cp_b):
            issues.append(
                _issue(
                    "ERROR",
                    "W201",
                    "Missing endpoint data for Power row; skipping graph edge.",
                    row_index=row_index,
                    context={
                        "wireno": row.get("Wireno"),
                        "from_name": name_a,
                        "to_name": name_b,
                    },
                )
            )
            continue

        node_a = (str(name_a).strip(), str(cp_a).strip())
        node_b = (str(name_b).strip(), str(cp_b).strip())

        adjacency.setdefault(node_a, set()).add(node_b)
        adjacency.setdefault(node_b, set()).add(node_a)

    return adjacency, issues


def bfs_parents(adjacency: Dict[Node, Set[Node]], start_nodes: Iterable[Node]) -> Dict[Node, Node]:
    start_list = sorted(start_nodes, key=lambda node: (node[0], node[1]))
    visited: Set[Node] = set(start_list)
    parent: Dict[Node, Node] = {}
    queue: deque[Node] = deque(start_list)

    while queue:
        current = queue.popleft()
        neighbors = sorted(adjacency.get(current, set()), key=lambda node: (node[0], node[1]))
        for neighbor in neighbors:
            if neighbor in visited:
                continue
            visited.add(neighbor)
            parent[neighbor] = current
            queue.append(neighbor)

    return parent


def _compress_path_names(path: List[Node]) -> List[str]:
    names: List[str] = []
    last_name: str | None = None
    for name, _cp in path:
        if name != last_name:
            names.append(name)
            last_name = name
    return names


def compute_feeder_paths(
    adjacency: Dict[Node, Set[Node]],
    parent: Dict[Node, Node],
    start_nodes: Iterable[Node],
) -> Tuple[List[Dict[str, Any]], List[Issue]]:
    start_set = set(start_nodes)
    issues: List[Issue] = []
    feeders: List[Dict[str, Any]] = []

    feeder_nodes = [
        node
        for node in adjacency
        if node[0].startswith("-Q") and node[0] != "-Q81"
    ]
    feeder_nodes_sorted = sorted(feeder_nodes, key=lambda node: (node[0], node[1]))

    for node in feeder_nodes_sorted:
        reachable = node in start_set or node in parent
        path_nodes: List[Node] = []
        path_names: List[str] = []

        if not reachable:
            issues.append(
                _issue(
                    "ERROR",
                    "W202",
                    "Feeder end is unreachable from -Q81.",
                    context={"feeder_name": node[0], "feeder_cp": node[1]},
                )
            )
        else:
            current = node
            path_nodes.append(current)
            while current not in start_set:
                current = parent[current]
                path_nodes.append(current)
            path_nodes.reverse()
            path_names = _compress_path_names(path_nodes)

        feeders.append(
            {
                "feeder_end_name": node[0],
                "feeder_end_cp": node[1],
                "path_names_str": " -> ".join(path_names),
                "path_len_nodes": len(path_nodes),
                "reachable": reachable,
            }
        )

    return feeders, issues
