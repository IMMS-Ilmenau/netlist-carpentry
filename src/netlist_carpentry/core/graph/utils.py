from __future__ import annotations

from typing import Set, Tuple

from networkx import MultiDiGraph as MDG


def all_edges(graph: MDG[str], node_name: str) -> Set[Tuple[str, str, str]]:
    """
    Returns a set of all edges (both incoming and outgoing) connected to the given node in the graph.

    Each tuple in the returned set follows the structure (edge_start, edge_end, edge_key). Accordingly,
    for all incoming edges, edge_end is `node_name` and for all outgoing edges, edge_start is `node_name`.
    The edge_key determines the ports over which both nodes are connected. The edge_key follows the structure
    `{port_name_edge_start}§{port_name_edge_end}`. The section sign (`§`) is used to divide between both ports.
    This character depends on the config entry `CFG.nc_identifier_internal`.

    Args:
        graph (networkx.MultiDiGraph): The input graph.
        node_name (str): The name of the node.

    Returns:
        Set[Tuple[str, str, str]]: A set of tuples representing the edges, where each tuple contains the source node,
            target node, and edge key.
    """
    return set(graph.edges(node_name, keys=True)).union(set(graph.in_edges(node_name, keys=True)))
