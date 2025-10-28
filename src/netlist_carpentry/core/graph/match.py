from __future__ import annotations

import time
from copy import deepcopy
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx

from netlist_carpentry import CFG, LOG
from netlist_carpentry.core.graph.utils import all_edges


class Match:
    def __init__(self, pattern_graph: nx.MultiDiGraph[str], matches: List[nx.MultiDiGraph[str]]):
        self._pattern_graph = pattern_graph
        self._matches = matches

    @property
    def pattern_graph(self) -> nx.MultiDiGraph[str]:
        """
        Returns a deep copy of the pattern graph.

        The returned graph is a **copy of the actual pattern graph** to prevent external modifications.

        Returns:
            networkx.MultiDiGraph: A deep copy of the pattern graph.
        """
        return deepcopy(self._pattern_graph)

    @property
    def matches(self) -> List[nx.MultiDiGraph[str]]:
        """
        Returns a deep copy of the list of matched subgraphs found in the original circuit.

        The returned list is a **copy of the actual list** to prevent external modifications to the internal state.
        """
        return deepcopy(self._matches)

    @property
    def count(self) -> int:
        """
        Returns the number of matches found for the pattern graph.

        This property is useful to quickly determine how many subgraphs in the original circuit match the given pattern,
        without having to access the actual matched subgraphs (e. g. for filtering or statistical analysis).

        Returns:
            int: The number of matches found for the pattern graph.
        """
        return len(self.matches)

    @property
    def pairings(self) -> Dict[str, Dict[int, str]]:
        """
        Returns a dictionary of pairings between nodes in the pattern graph and their corresponding matched nodes.

        This property uses graph isomorphism to establish these pairings. Graph isomorphism is a powerful tool for
        identifying structurally identical subgraphs within larger graphs. By leveraging this concept, the parts
        of the original circuit matching the given pattern can be identified, even if they have different node labels
        or edge configurations. Since the found matches already are isomorph to the pattern, the isomorphism function
        is only used to get the mapping between all found matching subgraphs and the pattern.

        One of the main advantages of using graph isomorphism is its **Flexibility**.
        It finds matches between subgraphs with varying node and edge attributes (but with correct instance types in
        the circuit). It can handle minor differences in the structure of the matched subgraphs (such as instance
        names, which are structurally irrelevant), making it more resilient to noise or variations in the data.

        For example, a pattern graph with two nodes 'A' and 'B' connected by an edge. Both nodes are circuit instances
        of a certain type. If the original circuit contains two identical subgraphs with nodes 'X'-'Y' (where X has
        the same type as A, and Y the same as B) and 'P'-'Q' (P.type == A.type and Q.type == B.type), the `pairings`
        property would return a dictionary mapping 'A' to {'0': 'X', '1': 'P'} and 'B' to {'0': 'Y', '1': 'Q'}.

        Returns:
            Dict[str, Dict[int, str]]: A dictionary mapping pattern graph nodes to dictionaries of matched node IDs.
        """
        iso_dict: Dict[str, Dict[int, str]] = {}
        LOG.debug(f'Collecting pairings for {self.count} matches and a pattern with {len(self.pattern_graph.nodes)} nodes...')
        start = time.time()
        for i, m in enumerate(self.matches):
            # Each found match should be isomorph to the pattern
            # Now find mappings for each match
            iso: Optional[Dict[str, str]] = nx.algorithms.isomorphism.vf2pp.vf2pp_isomorphism(self.pattern_graph, m)
            # TODO check how iso can be None -> happens with openMSP430
            if iso is None:
                LOG.error(f'Unable to find isomorphisms for match {i}: {m.name}! Skipping this occurrence...')
                continue
            for pattern_key, node in iso.items():
                # For first match: create empty dictionary for every instance in the pattern graph
                # All corresponding instances of found matches can thus be paired with the correct pattern instance
                if pattern_key not in iso_dict:
                    iso_dict[pattern_key] = {}
                # Example {"some_pattern_inst": {0: "matching_inst_graph0", 1: "matching_inst_graph1", ...}}
                iso_dict[pattern_key][i] = node
        LOG.debug(f'Collected pairings in {round(time.time() - start, 2)} s!')
        return iso_dict

    def get_interfaces(self, circuit_graph: nx.MultiDiGraph[str]) -> Dict[int, Dict[Tuple[str, str, int], Set[Tuple[str, str, int]]]]:
        """
        Returns a dictionary of interfaces for each matched subgraph in the original circuit.

        This method constructs an interface for each match by identifying the connections between the matched subgraph
        and the rest of the circuit. The returned dictionary maps each match index to its corresponding interface,
        which is represented as a nested dictionary.


        The interface dictionary has the following structure:
        - The outermost key is the match index (an integer).
        - The next level of keys is a tuple following the schema (`instance_name`, `port_name`, `segment_number`), which
            represents the unique connection point of the current instance, i.e. a port of an instance of the pattern.
        - The values for each connection tuple is a set containing all other end points as tuples with with the given
            port segment is connected via the same wire. The tuple again follows the schema (`opposing_instance_name`,
            `port_of_opposing_instance`, `segment_number`).

        If the key tuple references a driving port, the value set contains all load ports.
        If the key tuple references a load port, the value set conntains all driving ports (which should only be one).
        If the port is dangling (i.e. there is no opposing end point), the port is not listed.

        This way, each connection (with at least one end point inside the pattern) is listed along with every opposing
        end point connected to this port.
        For example, if a match has two instances ('inst1' and 'inst2'), which are connected between each other (via the output
        port 'Y' of 'inst1' and 'A' of 'inst2'), the interface dictionary might look like this:

            {
                0: {
                    ('inst1', 'A', 0): {('inst3', 'Y', 0)},
                    ('inst1', 'B', 0): {('inst4', 'Y', 0)},
                    ('inst1', 'Y', 0): {('inst5', 'D', 0), ('inst2', 'A', 0)},
                    ('inst2', 'A', 0): {('inst1', 'Y', 0)},
                    ('inst2', 'Y', 0): {(None, 'out_port', 0), ('inst6', 'A', 0)},
                },
                1: {
                    ('inst6', 'A', 0): {('inst2', 'Y', 0)},
                    ('inst6', 'Y', 0): {('inst7', 'A', 0)},
                    ('inst7', 'A', 0): {('inst6', 'Y', 0)},
                }
            }

        In this example, `inst1` has three connections outside the pattern, one for each port `A`, `B` and `Y`.
        However, `inst1` also has a connection inside the pattern to `inst2` via its port `Y` (index 0) and the
        port `A` of `inst2` (where the index is 0 again).
        If an instance is connected to a module port, then this connection does not have an instance.
        This can be seen for port `Y` of `inst2`, where the instance name is `None`, indicating that the referenced
        port `out_port` is a module port.
        If a port is missing in the returned dictionary, then this port is unconnected in the circuit.
        Thus there is no corresponding edge in the circuit graph.
        This can be indirectly seen at `inst7`, where only the port `A` is listed and no second port.

        This method is useful for analyzing the interactions between matched subgraphs and their surroundings in the
        original circuit.

        Args:
            circuit_graph (networkx.MultiDiGraph[str]): The original circuit graph.

        Returns:
            Dict[int, Dict[Tuple[str, str, int], Set[Tuple[str, str, int]]]]: A dictionary of interfaces for each matched subgraph.
        """
        interfaces: Dict[int, Dict[Tuple[str, str, int], Set[Tuple[str, str, int]]]] = {}
        LOG.debug(f'Collecting interfaces for {self.count} matches and a pattern with {len(self.pattern_graph.nodes)} nodes...')
        start = time.time()
        for i, m in enumerate(self.matches):
            self._build_interface_match(circuit_graph, interfaces, i, m)
        LOG.debug(f'Collected interfaces in {round(time.time() - start, 2)} s!')
        return interfaces

    def _build_interface_match(
        self,
        circuit_graph: nx.MultiDiGraph[str],
        interface: Dict[int, Dict[Tuple[str, str, int], Set[Tuple[str, str, int]]]],
        match_idx: int,
        match_graph: nx.MultiDiGraph[str],
    ) -> None:
        """
        Builds an interface for a matched subgraph in the original circuit.

        This method constructs an interface dictionary that captures the connections between nodes in the matched
        subgraph and other parts of the circuit. It does this by iterating over all edges incident to each node in
        the matched subgraph, and then constructing a nested dictionary structure to represent these connections.

        Args:
            circuit_graph (networkx.MultiDiGraph[str]): The original circuit graph.
            interface (Dict[int, Dict[Tuple[str, str, int], Set[Tuple[str, str, int]]]]): A dictionary to store the interfaces for each match.
            match_idx (int): The index of the current match in the list of matches.
            match_graph (networkx.MultiDiGraph[str]): The matched subgraph.
        """
        interface[match_idx] = {}
        for n in match_graph.nodes:
            LOG.debug(f'\tProcessing node {n} (of match nr. {match_idx})...')
            # For each node in the matched subgraph, initialize an empty dictionary to store its interfaces
            edges = all_edges(circuit_graph, n)
            for start, end, pnames in edges:
                dr_seg = circuit_graph.edges[start, end, pnames]['dr_seg']
                ld_seg = circuit_graph.edges[start, end, pnames]['ld_seg']
                LOG.debug(f'\t\tCurrently at edge {(start, end, pnames)}')
                self._build_interface_port(interface[match_idx], n, start, end, pnames, (dr_seg, ld_seg))

    def _build_interface_port(
        self,
        interface: Dict[Tuple[str, str, int], Set[Tuple[str, str, int]]],
        node: str,
        start: str,
        end: str,
        pnames: str,
        seg_indices: Tuple[int, int],
    ) -> None:
        """
        Builds the port part of the interface dictionary for the given node and pattern match graph.

        This method constructs an interface dictionary that captures the connectivity information between nodes in
        the original circuit graph. It takes into account the edges connected to each node, including their start and
        end points, as well as port names.

        The constructed interface dictionary shows how nodes within the pattern match are connected in the circuit.
        This is useful for further analysis and processing (e. g. Pattern Replacement) of the matched subgraphs.

        Args:
            interface (Dict[Tuple[str, str, int], Set[Tuple[str, str, int]]]): The dictionary to be updated with connectivity information.
            node (str): The current node being processed in the pattern match graph.
            start (str): The starting point of an edge connected to the current node. Either start or end is the node itself.
            end (str): The ending point of an edge connected to the current node. Either start or end is the node itself.
            pnames (str): A string containing port names separated by an identifier (default: '§'), which provides additional
                information about the edges in the circuit graph.
            seg_indices: The segment indices of both ports on each end of the edge. The first entry is the segment of
                the start port of the edge, and the second entry is the segment of the end port of the edge.
        """
        # Create a tuple representing the connection point of the current instance
        p_tuple = self._get_pattern_tuple(node, start, end, pnames, seg_indices)

        # Get the opposing end point of the edge as a tuple
        i_tuple = self._get_interface_tuple(node, start, end, pnames, seg_indices)

        # Update the interface dictionary with the connection information
        self._update_dict(interface, p_tuple, i_tuple)

    def _update_dict(
        self, interface: Dict[Tuple[str, str, int], Set[Tuple[str, str, int]]], p_tuple: Tuple[str, str, int], i_tuple: Tuple[str, str, int]
    ) -> None:
        """
        Updates the interface dictionary with the given interface tuple, such that the values for each key (p_tuple)
        representing the opposing end points (i_tuple).

        Args:
            interface (Dict[Tuple[str, str, int], Set[Tuple[str, str, int]]]): The dictionary to be updated.
            p_tuple (Tuple[str, str, int]): The tuple containing the pattern port information.
            i_tuple (Tuple[str, str, int]): The tuple containing the interface (i. e. opposing end) port information.
        """
        if p_tuple not in interface:
            interface[p_tuple] = set()
        interface[p_tuple].add(i_tuple)

    def _get_pattern_tuple(self, node: str, start: str, end: str, pnames: str, seg_indices: Tuple[int, int]) -> Tuple[str, str, Optional[int]]:
        """
        Creates a tuple containing the pattern port information for the given node and edge in the circuit graph.

        This method determines which end of the edge corresponds to the current node and collects the corresponding
        port name and segment index. The resulting tuple can be used as a key in the interface dictionary.

        Args:
            node (str): The current node being processed in the pattern match graph.
            start (str): The starting point of an edge connected to the current node. Either start or end is the node itself.
            end (str): The ending point of an edge connected to the current node. Either start or end is the node itself.
            pnames (str): A string containing port names separated by an identifier (default: '§'), which provides additional
                information about the edges in the circuit graph.
            seg_indices: The segment indices of both ports on each end of the edge. The first entry is the segment of
                the start port of the edge, and the second entry is the segment of the end port of the edge.

        Returns:
            Tuple[str, str, int]: A tuple containing the pattern port information (node name, port name, and segment index).
        """
        # Determine which end of the edge corresponds to the current node and collect port information
        port_idx = 0 if start == node else 1 if end == node else None
        port_name = pnames.split(CFG.id_internal)[port_idx]
        seg_idx = seg_indices[0] if node == start else seg_indices[1] if node == end else None
        return (node, port_name, seg_idx)

    def _get_interface_tuple(
        self, node: str, start: str, end: str, pnames: str, seg_indices: Tuple[int, int]
    ) -> Tuple[Optional[str], str, Optional[int]]:
        """
        Returns a tuple representing the interface of a given edge in the circuit graph.

        This method takes as input an edge (defined by its start and end nodes, as well as the port names associated
        with this edge) and returns a tuple containing the instance at the opposing end of the edge and the port name
        of the instance at the opposing end. If the opposing end is not an instance (i.e., it's a module port), then
        `None` is returned for the instance.

        Args:
            node: The node that the interface belongs to.
            start: The starting node of the edge.
            end: The ending node of the edge.
            pnames: A string containing the port names associated with this edge, separated by an identifier (default: '§').
            seg_indices: The segment indices of both ports on each end of the edge. The first entry is the segment of
                the start port of the edge, and the second entry is the segment of the end port of the edge.

        Returns:
            Tuple[str, str, int]: A tuple containing the instance at the opposing end (node name, port name, and segment index).
        """

        # Determine which end of the edge corresponds to the opposing node and collect port information
        other_end = end if start == node else start if end == node else None
        p_idx = 1 if start == node else 0 if end == node else None
        seg_idx = seg_indices[1] if start == node else seg_indices[0] if end == node else None
        # Port of the opposing instance at the given edge (which is the edge endpoint)
        other_port = pnames.split(CFG.id_internal)[p_idx]
        if other_end == other_port:
            # Other end is a module port, so not associated with an instance
            other_end = None
        # Tuple with the instance at the opposing end of the edge, and the port of the instance at the opposing end
        return (other_end, other_port, seg_idx)
