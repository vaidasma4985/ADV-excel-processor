from __future__ import annotations

from collections import defaultdict, deque
import re
from typing import Any, Dict, Iterable, List, Set, Tuple

import pandas as pd

Node = str
Issue = Dict[str, Any]


_MAIN_ROOT_PATTERN = re.compile(r"^(MT|IT|LT)/(L1|L2|L3|N)$")
_SUB_ROOT_PATTERN = re.compile(r"^F\\d+/(L1|L2|L3|N)$")
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
    device_terminals: Dict[str, Set[str]] = defaultdict(set)

    for row_index, row in df_power.iterrows():
        wireno = _normalize_wireno(row.get("Wireno"))
        net_node = f"NET:{wireno}" if wireno else None

        name_a = _normalize_name(row.get("Name"))
        cp_a = _normalize_terminal(row.get("C.name"))
        name_b = _normalize_name(row.get("Name.1"))
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

    for device_name, terminals in device_terminals.items():
        for left, right in _PASS_THROUGH_PAIRS:
            if left in terminals and right in terminals:
                node_left = f"{device_name}:{left}"
                node_right = f"{device_name}:{right}"
                adjacency.setdefault(node_left, set()).add(node_right)
                adjacency.setdefault(node_right, set()).add(node_left)

    return adjacency, issues


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


def _simplified_chain(path: List[Node]) -> str:
    if not path:
        return ""

    reversed_path = list(reversed(path))
    # Build a human-friendly chain from supply net to feeder, skipping NET nodes.
    chain: List[str] = []
    last_name: str | None = None

    root_node = reversed_path[0]
    if _is_net_node(root_node):
        root_name = _net_name(root_node)
    else:
        root_name = _device_name(root_node)

    chain.append(root_name)
    last_name = root_name

    for node in reversed_path[1:]:
        if _is_net_node(node):
            continue
        name = _device_name(node)
        if name != last_name:
            chain.append(name)
            last_name = name

    return " -> ".join(chain)


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


def compute_feeder_paths(
    adjacency: Dict[Node, Set[Node]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Issue], Dict[str, Any]]:
    issues: List[Issue] = []
    feeders: List[Dict[str, Any]] = []

    main_root_nets = {
        node
        for node in adjacency
        if _is_net_node(node) and _MAIN_ROOT_PATTERN.match(_net_name(node))
    }
    sub_root_nets = {
        node
        for node in adjacency
        if _is_net_node(node) and _SUB_ROOT_PATTERN.match(_net_name(node))
    }

    feeder_nodes = [
        node
        for node in adjacency
        if not _is_net_node(node)
        and _device_name(node).startswith(("-F", "-Q"))
        and _device_name(node) != "-Q81"
    ]
    feeder_nodes_sorted = sorted(feeder_nodes)

    for feeder_node in feeder_nodes_sorted:
        feeder_name = _device_name(feeder_node)
        feeder_cp = feeder_node.split(":", 1)[1] if ":" in feeder_node else ""
        direct_nets = _direct_net_neighbors(adjacency, [feeder_node])

        path_any, supply_any = _shortest_path_to_roots(
            adjacency,
            [feeder_node],
            main_root_nets | sub_root_nets,
        )

        reachable = bool(path_any)
        if not reachable:
            issues.append(
                _issue(
                    "ERROR",
                    "W202",
                    "Feeder end is unreachable from any root net (main or sub).",
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
        simplified_chain = _simplified_chain(path_any)

        feeders.append(
            {
                "feeder_end_name": feeder_name,
                "feeder_end_cp": feeder_cp,
                "supply_net": supply_net,
                "reachable": reachable,
                "path_nodes_raw": path_nodes_raw,
                "path_names_collapsed": path_names_collapsed,
                "simplified_chain": simplified_chain,
                "path_len_nodes": len(path_any),
            }
        )

    aggregated = _aggregate_feeder_paths(feeders)

    debug = {
        "total_nodes": len(adjacency),
        "total_edges": sum(len(neighbors) for neighbors in adjacency.values()) // 2,
        "main_root_nets": sorted(_net_name(node) for node in main_root_nets),
        "sub_root_nets": sorted(_net_name(node) for node in sub_root_nets),
        "feeder_ends_found": sorted({feeder["feeder_end_name"] for feeder in feeders}),
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
                "path_names_collapsed": "",
                "simplified_chain_grouped": "",
                "simplified_chain_candidates": defaultdict(int),
                "reachable": False,
                "path_len_nodes": 0,
            },
        )
        if feeder["feeder_end_cp"]:
            entry["feeder_end_cps"].add(feeder["feeder_end_cp"])

        if feeder["reachable"]:
            entry["reachable"] = True
            if not entry["path_names_collapsed"]:
                entry["path_names_collapsed"] = feeder["path_names_collapsed"]
            if feeder["simplified_chain"]:
                entry["simplified_chain_candidates"][feeder["simplified_chain"]] += 1
            if entry["path_len_nodes"] == 0:
                entry["path_len_nodes"] = feeder["path_len_nodes"]
            else:
                entry["path_len_nodes"] = min(entry["path_len_nodes"], feeder["path_len_nodes"])

    aggregated = []
    for (_name, _supply), entry in sorted(grouped.items()):
        cps = sorted(entry["feeder_end_cps"], key=lambda cp: (len(cp), cp))
        if entry["simplified_chain_candidates"]:
            chain_lengths = {
                chain: len(chain.split(" -> ")) for chain in entry["simplified_chain_candidates"]
            }
            shortest_length = min(chain_lengths.values())
            shortest_chains = [
                chain
                for chain, length in chain_lengths.items()
                if length == shortest_length
            ]
            entry["simplified_chain_grouped"] = max(
                shortest_chains,
                key=lambda chain: entry["simplified_chain_candidates"][chain],
            )
        aggregated.append(
            {
                "feeder_end_name": entry["feeder_end_name"],
                "feeder_end_cps": ", ".join(cps),
                "supply_net": entry["supply_net"],
                "path_names_collapsed": entry["path_names_collapsed"],
                "simplified_chain_grouped": entry["simplified_chain_grouped"],
                "reachable": entry["reachable"],
                "path_len_nodes": entry["path_len_nodes"],
            }
        )

    return aggregated
