from __future__ import annotations

from collections import defaultdict, deque
import re
from typing import Any, Dict, Iterable, List, Set, Tuple

import pandas as pd

Node = str
Issue = Dict[str, Any]


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
    ("N", "N'"),
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
    normalized = str(value).strip()
    normalized = normalized.replace("’", "'").replace("‘", "'").replace("´", "'").replace("`", "'")
    normalized = normalized.upper()
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
    cleaned = wireno.strip().rstrip(",")
    if not cleaned:
        return []
    tokens = [token.strip() for token in re.split(r"[;,]", cleaned)]
    return [token for token in tokens if token]


def build_graph(
    df_power: pd.DataFrame,
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

    for row_index, row in df_power.iterrows():
        wireno = _normalize_wireno(row.get("Wireno"))
        wireno_tokens = _extract_wireno_tokens(wireno)
        root_tokens = _extract_root_tokens(wireno)

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
            suppress_bus_edge = bool(root_tokens) and _is_front_terminal(cp_a) and _is_front_terminal(cp_b)
            if not suppress_bus_edge:
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

    logical_edges_added = _add_logical_edges(adjacency, device_terminals, device_parts)

    return adjacency, issues, device_terminals, device_parts, logical_edges_added


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

    if "N" in terminals_a and "N" in terminals_b:
        edges.add(("N", "N"))

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

    visited: Set[Node] = set(start_list)
    parent: Dict[Node, Node] = {}
    queue: deque[Node] = deque(start_list)
    blocked = blocked_nodes or set()

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
            if neighbor in blocked:
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


def _is_even_terminal(term: str) -> bool:
    return term.isdigit() and int(term) % 2 == 0


def _is_front_terminal(term: str) -> bool:
    if term.isdigit():
        return int(term) % 2 == 1
    if term == "N":
        return True
    if term == "N'":
        return False
    if term.endswith("N") and "'" not in term:
        return True
    return False


def _is_end_terminal(term: str) -> bool:
    if term.isdigit():
        return int(term) % 2 == 0
    return term == "N'"


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

    net_nodes = {node for node in adjacency if _is_net_node(node)}
    root_nets = {node for node in net_nodes if _MAIN_ROOT_PATTERN.match(_net_name(node))}
    sub_root_nets = sorted(
        _net_name(node)
        for node in net_nodes
        if not _MAIN_ROOT_PATTERN.match(_net_name(node))
    )

    device_nodes = [node for node in adjacency if not _is_net_node(node)]
    device_names = {_device_name(node) for node in device_nodes}
    logical_base_terminals: Dict[str, Set[str]] = defaultdict(set)
    for device_name in device_names:
        logical_base_terminals[_logical_base_name(device_name)].update(
            device_terminals.get(device_name, set())
        )

    base_to_terminals_union: Dict[str, Set[str]] = defaultdict(set)
    for device_name in device_names:
        base_name = _logical_base_name(device_name)
        base_to_terminals_union[base_name].update(device_terminals.get(device_name, set()))

    def _is_f_end(terminals: Iterable[str]) -> bool:
        return not any(_is_even_terminal(term) for term in terminals)

    feeder_f_bases = {
        base
        for base, terminals in base_to_terminals_union.items()
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

    def _feeder_base_for_node(node: Node) -> str | None:
        name = _device_name(node)
        logical_base = _logical_base_name(name)
        if logical_base in feeder_f_bases:
            return logical_base
        if name in feeder_q_bases or name in feeder_x_bases:
            return name
        return None

    base_to_nodes: Dict[str, Set[Node]] = defaultdict(set)
    for node in feeder_nodes_sorted:
        base = _feeder_base_for_node(node)
        if base:
            base_to_nodes[base].add(node)

    feeder_end_bases = sorted(base_to_nodes)
    blocked_nodes_all: Set[Node] = set()
    for nodes in base_to_nodes.values():
        blocked_nodes_all.update(nodes)
    node_to_feeder_base = {
        node: base for base, nodes in base_to_nodes.items() for node in nodes
    }

    for feeder_node in feeder_nodes_sorted:
        feeder_name = _device_name(feeder_node)
        feeder_cp = feeder_node.split(":", 1)[1] if ":" in feeder_node else ""
        direct_nets = _direct_net_neighbors(adjacency, [feeder_node])
        feeder_base = _feeder_base_for_node(feeder_node)
        allowed_nodes = base_to_nodes.get(feeder_base, set()) if feeder_base else set()
        blocked = blocked_nodes_all - allowed_nodes

        direct_root_neighbors = sorted(
            neighbor
            for neighbor in adjacency.get(feeder_node, set())
            if neighbor in root_nets
        )
        if direct_root_neighbors:
            path_any = [feeder_node, direct_root_neighbors[0]]
            supply_any = direct_root_neighbors[0]
        else:
            path_any, supply_any = _shortest_path_to_roots(
                adjacency,
                [feeder_node],
                root_nets,
                blocked_nodes=blocked,
            )

        if path_any and feeder_base:
            traversed_bases = {
                node_to_feeder_base[node]
                for node in path_any
                if node in node_to_feeder_base
            }
            traversed_bases.discard(feeder_base)
            if traversed_bases:
                issues.append(
                    _issue(
                        "WARNING",
                        "W220",
                        "Feeder path traverses another feeder end base.",
                        context={
                            "feeder_name": feeder_name,
                            "feeder_base": feeder_base,
                            "other_bases": sorted(traversed_bases),
                        },
                    )
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
    bases_with_even_terminals_sample = [
        base
        for base, terminals in sorted(base_to_terminals_union.items())
        if any(_is_even_terminal(term) for term in terminals)
    ][:10]

    debug = {
        "total_nodes": len(adjacency),
        "total_edges": sum(len(neighbors) for neighbors in adjacency.values()) // 2,
        "main_root_nets": sorted(_net_name(node) for node in root_nets),
        "sub_root_nets": sub_root_nets[:25],
        "sub_root_nets_count": len(sub_root_nets),
        "net_nodes_from_wireno_count": len(net_nodes),
        "feeder_ends_found": sorted({feeder["feeder_end_name"] for feeder in feeders}),
        "feeder_end_bases_count": len(feeder_end_bases),
        "feeder_end_bases_sample": feeder_end_bases[:10],
        "bases_with_even_terminals_sample": bases_with_even_terminals_sample,
        "blocked_nodes_count": len(blocked_nodes_all),
        "example_blocked_bases": feeder_end_bases[:5],
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
