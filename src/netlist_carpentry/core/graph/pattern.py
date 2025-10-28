from __future__ import annotations

import time
from typing import Dict, Iterable, List, Optional, Set, Tuple

from networkx import MultiDiGraph as MDG

from netlist_carpentry import CFG, EMPTY_GRAPH, LOG
from netlist_carpentry.core.graph.constraint import Constraint
from netlist_carpentry.core.graph.match import Match
from netlist_carpentry.core.graph.utils import all_edges
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.netlist_elements.port_segment import PortSegment
from netlist_carpentry.core.netlist_elements.wire_segment import WireSegment
from netlist_carpentry.core.port_direction import PortDirection
from netlist_carpentry.utils.gate_lib import get


class Pattern:
    """
    The Pattern class represents a subgraph pattern in a digital circuit graph.

    It is used to match specific patterns within the graph, allowing for efficient
    identification and manipulation of components or subcircuits. This class is
    essential for tasks such as optimization, verification, and synthesis of digital
    circuits.

    In a graph representing a digital circuit, this class can be used to identify
    common patterns like cascading logic gates (e.g., AND, OR, NOT), or more complex
    components like redundant multiplexers. These patterns help in searching for and
    analyzing specific parts of the circuit, facilitating tasks (e. g. debugging,
    testing and refinement).

    Additionally, this class can also be used to specify a replacement graph that will
    replace the matched pattern in the original graph. This allows for the simplification
    or transformation of digital circuits by replacing complex patterns with simpler ones.

    To use this class, create an instance by providing a subgraph that represents the
    desired pattern and optionally a replacement graph. Then, utilize the provided methods
    to match this pattern within a larger graph representing the digital circuit. If a
    replacement graph is given, it can be used to replace all (or certain) occurrences.
    """

    @classmethod
    def get_data(cls, graph: MDG[str], node_name: str, key: str) -> str:
        return graph.nodes[node_name][key]  # type: ignore

    @classmethod
    def set_data(cls, graph: MDG[str], node_name: str, key: str, val: object) -> None:
        graph.nodes[node_name][key] = val  # type: ignore

    @classmethod
    def _add_node_metadata(cls, graph: MDG[str]) -> None:
        """
        Adds metadata to the nodes of a given graph.

        This method iterates over all nodes in the graph and adds two new attributes:
            - 'n_input_inst': A boolean indicating whether the node is adjacent to an input port.
            - 'n_output_inst': A boolean indicating whether the node is adjacent to an output port.

        These metadata are useful for analyzing the connectivity of the circuit graph.
        By identifying which nodes are connected to input or output ports, it becomes easier to
        understand how signals flow through the circuit and make informed decisions about
        optimization or modification.

        Args:
            graph (MDG[str]): The graph to which metadata should be added.
        """
        for n in graph.nodes:
            graph.nodes[n].setdefault('n_input_inst', False)
            graph.nodes[n].setdefault('n_output_inst', False)
        port_nodes = [n for n in graph.nodes if Pattern.get_data(graph, n, 'ntype') == 'PORT']
        for p in port_nodes:
            neighbors = set(graph.successors(p)).union(set(graph.predecessors(p)))
            direction = Pattern.get_data(graph, p, 'ntype_info')
            for n in neighbors:
                if direction == 'input':
                    Pattern.set_data(graph, n, 'n_input_inst', True)
                if direction == 'output':
                    Pattern.set_data(graph, n, 'n_output_inst', True)

    @classmethod
    def _remove_ports_from_pattern_graphs(cls, graph: MDG[str]) -> None:
        nodes_to_remove = [n for n in graph.nodes if Pattern.get_data(graph, n, 'ntype') == 'PORT']
        graph.remove_nodes_from(nodes_to_remove)

    @classmethod
    def get_mapping(cls, pattern_module: Module, replacement_module: Module) -> Dict[Tuple[str, str, int], Tuple[str, str, int]]:
        """
        This method generates a mapping between the ports of a pattern module and its corresponding replacement module.

        The generated mapping can be used to replace instances of the pattern module with the replacement module in a larger circuit graph,
        ensuring that all port connections are correctly maintained.

        Args:
            pattern_module (Module): The module representing the pattern to be replaced.
            replacement_module (Module): The module representing the replacement for the pattern.

        Returns:
            Dict[Tuple[str, str, int], Tuple[str, str, int]]: A dictionary where each key is a tuple containing the name of the instance currently being processed,
            the name of the current port of the instance, and the current segment of the port (is -1, if the port consists only of one segment, or if all segments are equal).
            Each corresponding value is a tuple with the same information for the equivalent port in the replacement module.

        Raises:
            ValueError: If the ports of the pattern and replacement modules do not match.
        """
        # Compare ports
        if set(pattern_module.ports.keys()) != set(replacement_module.ports.keys()):
            # Ports do not match
            missing_in_pattern = set(replacement_module.ports.keys()).difference(set(pattern_module.ports.keys()))
            missing_in_replacement = set(pattern_module.ports.keys()).difference(set(replacement_module.ports.keys()))
            err_msg = 'Port names in pattern and replacement module differ: {miss1}{and_}{miss2}'
            miss1 = f'Ports missing in the pattern module {pattern_module.name}: {missing_in_pattern}' if missing_in_pattern else ''
            miss2 = f'Ports missing in the replacement module {replacement_module.name}: {missing_in_replacement}' if missing_in_replacement else ''
            and_ = ' and ' if miss1 and miss2 else ''
            raise ValueError(err_msg.format(miss1=miss1, miss2=miss2, and_=and_))

        # Build mapping for input and output ports
        mapping: Dict[Tuple[str, str, int], Tuple[str, str, int]] = {}
        Pattern._build_mapping(mapping, pattern_module, replacement_module, get_input_ports=True)
        Pattern._build_mapping(mapping, pattern_module, replacement_module, get_input_ports=False)
        return mapping

    @classmethod
    def _build_mapping(
        cls, mapping: Dict[Tuple[str, str, int], Tuple[str, str, int]], pattern_module: Module, replacement_module: Module, get_input_ports: bool
    ) -> None:
        """
        This method builds a mapping between the ports of a pattern module and its corresponding replacement module.

        It constructs this mapping by comparing the port names and their respective segments in both modules.
        The generated mapping is stored in the provided dictionary.

        Args:
            mapping (Dict[Tuple[str, str, int], Tuple[str, str, int]]): A dictionary to store the mapping between pattern ports and replacement ports.
            pattern_module (Module): The module representing the pattern to be replaced.
            replacement_module (Module): The module representing the replacement for the pattern.
            get_input_ports (bool): Flag indicating whether to consider input ports or output ports.

        Notes:
            This method assumes that both modules have been checked for port name consistency beforehand.
            It iterates over each port in either the input or output ports of the pattern module, depending on the get_input_ports flag.
            For every port, it generates a unique identifier (as a tuple) and uses this identifier as a key in the mapping dictionary.
            The corresponding value is another tuple representing the equivalent port in the replacement module.

        Raises:
            KeyError: If there's an inconsistency between pattern ports and replacement ports that hasn't been caught beforehand.
        """
        ports = pattern_module.input_ports if get_input_ports else pattern_module.output_ports
        for pattern_port in ports:
            # Generate a unique identifier (tuple) for the current port in the pattern module
            pattern_port_map = Pattern._get_map_tuple(pattern_module, pattern_port.segments.values(), get_input_ports)
            replacement_port = replacement_module.ports[pattern_port.name]
            replacement_port_map = Pattern._get_map_tuple(replacement_module, replacement_port.segments.values(), get_input_ports)
            mapping[replacement_port_map] = pattern_port_map

    @classmethod
    def _get_map_tuple(cls, module: Module, port_segments: Iterable[PortSegment], get_input_port_tuple: bool) -> Tuple[str, str, int]:
        """
        Generates a tuple for the mapping process between ports of modules.

        This method takes in a module and the currently processed port segments. It returns a tuple containing the name of the instance currently being processed,
        the name of the current port of the instance, and the current segment of the port (is -1, if the port consists only of one segment, or if all segments are equal).

        Args:
            module (Module): The module for which to generate the mapping tuple.
            port_segments (List[PortSegment]): A list of PortSegments that should be mapped.
            get_input_port_tuple (bool): Whether to retrieve input port tuples or output port tuples.

        Returns:
            Tuple[str, str, int]: A tuple containing instance name, port name and segment index for mapping purposes.

        Raises:
            ValueError: If unable to create mapping due to differing nodes.
        """
        p_maps: List[PortSegment] = []
        get_ports = module.get_load_ports if get_input_port_tuple else module.get_driving_ports
        for seg in port_segments:
            nodes = get_ports(seg.ws_path)
            p_maps.extend(nodes)
        # If instance name (0) and port name (1) are equal, index number (2) is no longer needed
        if all(p_maps[0].parent_parent_name == p.parent_parent_name and p_maps[0].parent_name == p.parent_name for p in p_maps):
            return (p_maps[0].parent_parent_name, p_maps[0].parent_name, -1)
        else:
            # TODO: support for port connections, where multiple wires are connected to different port segments
            raise ValueError(f'Unable to create mapping, since some nodes are differing: {p_maps}')

    def __init__(
        self,
        graph: MDG[str],
        replacement_graph: MDG[str] = EMPTY_GRAPH,
        ignore_port_names: bool = True,
        matching_constraints: List[Constraint] = [],
        mapping: Dict[Tuple[str, str, int], Tuple[str, str, int]] = {},
        ignore_boundary_conditions: bool = False,
    ):
        """
        Args:
            graph (networkx.MultiDiGraph): The graph representing the pattern structure to find in the circuit.
            replacement_graph (networkx.MultiDiGraph): The graph representing the replacement structure to replace pattern matches with.
            ignore_port_names (bool): Whether to check if the port names of the pattern match the port names of the circuit. Defaults to True.
            matching_constraints (List): A list of constraints for the matching algorithm. Currently unused.
            mapping (Dict[Tuple[str, str, int], Tuple[str, str, int]]): A dictionary that maps the original nodes and edges to their new counterparts.
            ignore_boundary_conditions (bool): Whether to ignore any boundary conditions when matching the pattern to a given circuit. Defaults to False.
        """
        self._graph = graph
        self._replacement_graph = replacement_graph
        self._ignore_port_names = ignore_port_names
        self._matching_constraints = matching_constraints
        self.mapping = mapping
        self._ignore_boundary_conditions = ignore_boundary_conditions

        self._add_node_metadata(self.graph)
        self._add_node_metadata(self.replacement_graph)

    @property
    def graph(self) -> MDG[str]:
        """
        Returns the pattern graph.

        This property provides read-only access to the internal pattern graph.
        The pattern graph is a MultiDiGraph representing the structure of the
        pattern to be matched in the target graph.

        Returns:
            networkx.MultiDiGraph: The pattern graph.
        """
        return self._graph

    @property
    def replacement_graph(self) -> MDG[str]:
        """
        Retrieves the replacement graph associated with this pattern.

        The replacement graph is used to specify the structure that should replace
        occurrences of the original graph (the pattern graph) in a larger network.
        This property allows for the inspection and modification of the replacement graph.

        Returns:
            networkx.MultiDiGraph: The replacement graph.
        """
        return self._replacement_graph

    @property
    def matching_constraints(self) -> List[Constraint]:
        """Returns the list of matching constraints associated with this pattern."""
        return self._matching_constraints

    @property
    def ignore_boundary_conditions(self) -> bool:
        return self._ignore_boundary_conditions

    def _get_instance_type(self, graph: MDG[str], node_name: str) -> str:
        """
        Returns the instance type of a given node in the graph.

        Args:
            graph (networkx.MultiDiGraph): The input graph.
            node_name (str): The name of the node.

        Returns:
            str: The instance type of the node.
        """
        return self.get_data(graph, node_name, 'ntype_info')

    def find_matches(self, circuit_graph: MDG[str], max_match_count: int = -1) -> Match:
        """
        Attempts to find matches for this pattern in the given circuit graph.

        Args:
            circuit_graph (networkx.MultiDiGraph): The circuit graph to search for matches.
            max_match_count (int, optional): The maximum number of matches to find. If set to -1, no limit is applied. Defaults to -1.

        Returns:
            Match: A Match object containing the found matches. If no matches were found, the Match object is empty.

        Notes:
            This method checks if the pattern is not empty before attempting to find matches.
            It uses a random node from the pattern as a starting point for the search.
        """
        # Check if pattern is not empty
        LOG.info(f'Starting Pattern Matching algorithm on a graph with {len(circuit_graph.nodes)} nodes...')
        start = time.time()
        if len(self.graph.nodes) == 0:
            LOG.warn('Pattern is empty, no matches can be found!')
            return Match(self.graph, [])

        # Find possible start nodes in circuit graph (get random node to start from)
        start_node = next(iter(self.graph.nodes))
        m = self._find_matching_circuit_nodes(circuit_graph, start_node, max_match_count)
        LOG.info(f'Finished Pattern Matching algorithm on a graph with {len(circuit_graph.nodes)} nodes in {round(time.time() - start, 2)} s...')
        return m

    def count_matches(self, circuit_graph: MDG[str]) -> int:
        """
        Counts the number of matches of this pattern in the given circuit graph.

        This method checks if the pattern is not empty and then finds possible start nodes
        in the circuit graph. It uses a helper function to recursively explore all possible
        matches starting from each node in the circuit graph that could potentially match
        the first node in the pattern.

        Args:
            circuit_graph (networkx.MultiDiGraph): The graph to search for matches in.

        Returns:
            int: The number of matches found.
        """
        return self.find_matches(circuit_graph).count

    def _find_matching_circuit_nodes(self, circuit_graph: MDG[str], pattern_start_node: str, max_match_count: int = -1) -> Match:
        """
        Finds the number of matching circuit nodes in the circuit graph that match the given pattern.

        This method starts by identifying potential starting nodes in the circuit graph with the same instance type as the
        pattern's start node. It then attempts to match the rest of the pattern, incrementing a counter for each successful match.

        Args:
            circuit_graph (networkx.MultiDiGraph): The input circuit graph.
            pattern_start_node (str): The name of the starting node in the pattern.
            max_match_count (int): The maximum number of matches to find. If set to -1, no limit is applied. Defaults to -1.

        Returns:
            Match: The match object containing all matching subgraphs found in the circuit graph.
        """
        found_pattern_matches: List[MDG[str]] = []
        circuit_nodes_with_types = circuit_graph.nodes.data('ntype_info')
        node_type = self._get_instance_type(self.graph, pattern_start_node)

        # Iterate over all nodes in the circuit graph with their corresponding instance types
        LOG.debug(f'Searching for node with type {node_type}, which is the type of the start node from the pattern...')
        for circuit_start_node, start_node_type in circuit_nodes_with_types:
            if len(found_pattern_matches) >= max_match_count and max_match_count > 0:
                break
            LOG.debug(f'\tComparing node {circuit_start_node} from the circuit with {pattern_start_node} from the pattern...')
            if start_node_type == node_type:
                # Found instance with correct type to start pattern matching
                # is_pattern_match returns True if the pattern is matched and thus found_pattern_matches is incremented
                LOG.debug(f'\tNode {circuit_start_node} has correct type, now trying to match this node and its neighbors to the pattern!')
                new_subgraph = self._is_pattern_match(circuit_graph, {(pattern_start_node, circuit_start_node)})
                if new_subgraph and self.matches_constraints(new_subgraph, circuit_graph):
                    found_pattern_matches.append(new_subgraph)
        return Match(self.graph, found_pattern_matches)

    def _is_pattern_match(self, circuit_graph: MDG[str], node_tuples_to_check: Set[Tuple[str, str]]) -> Optional[MDG[str]]:
        """
        Checks if the given pattern matches a subgraph in the circuit graph.

        This method checks for structural similarities between the pattern and the circuit graph.
        It iterates through the nodes of the pattern and checks if their corresponding nodes in the circuit graph
        have similar edges. If any discrepancies are found, it immediately returns False.

        Args:
            circuit_graph (networkx.MultiDiGraph): The input circuit graph.
            node_tuples_to_check (Set[Tuple[str, str]]): A set of tuples containing pairs of nodes from the pattern and the circuit graph.

        Returns:
            networkx.MultiDiGraph: The subgraph of the circuit if the pattern matches a subgraph in the circuit graph, None otherwise.
        """
        # Keep track of the processed nodes to avoid infinite loops
        processed_circuit_nodes: List[str] = []
        processed_pattern_nodes: List[str] = []

        subgraph: MDG[str] = MDG()

        # Continue processing until all node tuples have been checked
        while node_tuples_to_check:
            # Trying to match the next circuit node to the pattern and then update the subgraph and the node sets accordingly
            if not self._next_node_matches(circuit_graph, node_tuples_to_check, subgraph, processed_circuit_nodes, processed_pattern_nodes):
                # Next node tuple does not match between circuit and pattern
                # Stop matching algorithm since current structure does not match the pattern
                LOG.debug('\t\tThis section does not match the given pattern!')
                return None

        if not self.ignore_boundary_conditions:
            if not self._match_occurrence_boundaries(circuit_graph, subgraph, processed_circuit_nodes, processed_pattern_nodes):
                return None

        # All node tuples have been checked and no discrepancies were found
        LOG.debug('\t\tThis section matches the given pattern!')
        return subgraph

    def _next_node_matches(
        self, circuit: MDG[str], nodes_to_check: Set[Tuple[str, str]], subgraph: MDG[str], processed_cnodes: List[str], processed_pnodes: List[str]
    ) -> bool:
        """
        Checks if the next pair of circuit and pattern nodes match.

        This method is used in the process of checking for a pattern match between the given circuit graph and the pattern.
        It takes a set of node tuples to check, where each tuple contains a pair of nodes from the pattern and the circuit graph,
        as well as sets of processed circuit and pattern nodes to avoid infinite loops.

        The method first retrieves the next pair of nodes to check from the set of node tuples. It then adds the current
        circuit node to the subgraph of the possible pattern match, including its corresponding node data.

        Next, it collects all edges connected to the current circuit and pattern nodes that haven't been processed yet.
        The method checks if these edges match by comparing their structures. If they don't match, it immediately returns False.
        This means, the current node in the `nodes_to_check` set does not match with the given pattern, and the pattern matching
        process can be stopped.

        If the edges do match, the method updates the set of node tuples to check by adding new pairs of nodes
        corresponding to the matched edges. It also marks the current nodes as processed and continues with the next pair of nodes.

        Args:
            circuit (networkx.MultiDiGraph): The circuit graph.
            nodes_to_check (Set[Tuple[str, str]]): A set of tuples containing pairs of nodes from the pattern and the circuit graph.
            subgraph (networkx.MultiDiGraph): The subgraph of the possible pattern match.
            processed_cnodes (List[str]): A list of processed circuit nodes, in processing order.
            processed_pnodes (List[str]): A list of processed pattern nodes, in processing order.

        Returns:
            bool: True if the nodes match, False otherwise.
        """
        # Get the next pair of circuit and pattern nodes to check
        pnode, cnode = nodes_to_check.pop()

        # Add current node to the circuit subgraph of a possible pattern match
        # Also provide node data of the original node to the new node in the subgraph
        cndata = dict(circuit.nodes.data())[cnode]
        subgraph.add_node(cnode, **cndata)

        # Get the edges connected to the current circuit and pattern nodes that haven't been processed yet
        circuit_edges = self.interesting_edges(circuit, cnode, processed_cnodes)
        pattern_edges = self.interesting_edges(self.graph, pnode, processed_pnodes)

        # Mark the current nodes as processed
        processed_cnodes.append(cnode)
        processed_pnodes.append(pnode)

        # Check if the edges match and update the set of node tuples to check
        # Returns False if the edges don't match, indicating that the current circuit node is not a pattern match
        return self._circuit_edges_match_pattern(circuit, nodes_to_check, pattern_edges, circuit_edges, subgraph, pnode, cnode)

    def _match_occurrence_boundaries(
        self, circuit_graph: MDG[str], subgraph: MDG[str], processed_circuit_nodes: List[str], processed_pattern_nodes: List[str]
    ) -> bool:
        # Check whether the instances of the found pattern drive other signals, which are not included in this pattern
        # In such case, reject the found pattern occurrence, since this is not an exact match
        for n in subgraph.nodes:
            corresponding_pattern_node = processed_pattern_nodes[processed_circuit_nodes.index(n)]
            # This condition only applies to non-output instances of the pattern
            # These are nodes that are not connected to pattern outputs
            if not self.get_data(self.graph, corresponding_pattern_node, 'n_output_inst'):
                # Compare outgoing degrees of both the circuit node and the found pattern occurrence node
                # If both outgoing degrees are equal, there are no instances inbetween and this is an exact match
                circuit_degree = circuit_graph.out_degree(n)
                pattern_degree = self.graph.out_degree(corresponding_pattern_node)
                if circuit_degree != pattern_degree:
                    # In the circuit, the node probably drives another instance which is not part of this pattern
                    # Thus, this is not an exact match and is rejected
                    dbg_msg = f'\t\tThis section does not match boundaries: node {n} has degree {circuit_degree} in circuit, but degree {pattern_degree} in the pattern!'
                    LOG.debug(dbg_msg)
                    return False
        return True

    def _get_node_type(self, graph: MDG[str], node: str) -> str:
        """
        Returns the type of a given node in the graph.

        Args:
            graph (networkx.MultiDiGraph): The input graph.
            node (str): The name of the node.

        Returns:
            str: The type of the node.
        """
        return self.get_data(graph, node, 'ntype_info')

    def _circuit_edges_match_pattern(
        self,
        circuit: MDG[str],
        nodes_to_check_next: Set[Tuple[str, str]],
        pattern_node_edges: Set[Tuple[str, str, str]],
        circuit_node_edges: Set[Tuple[str, str, str]],
        subgraph: MDG[str],
        pattern_node: str,
        circuit_node: str,
    ) -> bool:
        """
        Checks if the given pattern edges (i.e. the edges of the current pattern node) match with corresponding edges in the circuit
        (i.e. the edges of the correspondig circuit node) and updates the set of node tuples to check next.

        When called, all given pattern edges are tried to match against the circuit edges.
        In every step, every pattern edge is taken and compared to every circuit edge in the given list (which should only contain edges of the current node).
        If the opposing nodes of both edges are of the same type (i.e. both are AND-nodes), they might match.
        In this case, it is checked, whether the ports are the same (then this part of the pattern matches as well).
        Otherwise, the current circuit edge does not match with the pattern edge and the next circuit edge is tested.

        Args:
            circuit (networkx.MultiDiGraph): The input circuit graph.
            nodes_to_check_next (Set[Tuple[str, str]]): A set of tuples containing pairs of nodes from the pattern and the circuit that need to be checked for matching.
            pattern_node_edges (Set[Tuple[str, str, str]]): A set of edges in the pattern graph.
            circuit_node_edges (Set[Tuple[str, str, str]]): A set of edges in the circuit graph.
            subgraph (networkx.MultiDiGraph): The subgraph representing the found match in the circuit.
            pattern_node (str): The pattern node currently being matched against the circuit.
            circuit_node (str): The circuit node currently being assumed to match the pattern node.

        Returns:
            bool: True if a match is found and the node tuples have been updated, False otherwise.
        """
        for pu, pv, pkey in pattern_node_edges:
            pv_type = self._get_node_type(self.graph, pv)
            pu_type = self._get_node_type(self.graph, pu)
            for cu, cv, ckey in circuit_node_edges:
                # TODO what if ports are switched, e. g. AND or OR gates? Should not matter
                matching_port_names = self._ignore_port_names or pkey == ckey
                v_types_equal = pv_type == self._get_node_type(circuit, cv)
                u_types_equal = pu_type == self._get_node_type(circuit, cu)
                symmetric_structure = (pu == pattern_node and cu == circuit_node) or (pv == pattern_node and cv == circuit_node)

                if matching_port_names and v_types_equal and u_types_equal and symmetric_structure:
                    # Must be symmetric structure, so that pattern node and circuit node are on the same end of the edge
                    next_tuple = (pv, cv) if (pv, cv) != (pattern_node, circuit_node) else (pu, cu)
                    nodes_to_check_next.add(next_tuple)
                    subgraph.add_edge(cu, cv, ckey)
                    break
            else:
                return False
        return True

    def matches_constraints(self, potential_match_graph: MDG[str], circuit_graph: MDG[str]) -> bool:
        return all(constraint.check(potential_match_graph, circuit_graph) for constraint in self.matching_constraints)

    def interesting_edges(self, graph: MDG[str], curr_node: str, processed_nodes: List[str]) -> Set[Tuple[str, str, str]]:
        """
        Returns a set of edges connected to the given node that have not been processed yet.

        An edge is considered unprocessed if either node is not in the given `processed_nodes` list.
        If both end points are in the `processed_nodes` list, the edges is considered processed.

        Args:
            graph (networkx.MultiDiGraph): The graph to process.
            curr_node (str): The current node to consider.
            processed_nodes (List[str]): A list of nodes that have already been processed, in processing order.

        Returns:
            Set[Tuple[str, str, str]]: A set of edges connected to the given node that have not been processed yet.
            The first tuple element is the start of the edge, the second element is the end of the edge, and the third element is the key (for multi-edge connections).
        """
        return {(u, v, k) for u, v, k in all_edges(graph, curr_node) if u not in processed_nodes or v not in processed_nodes}

    def replace(self, module: Module, iterations: int = -1, replace_all_parallel: bool = False) -> int:
        """
        Replaces occurrences of a pattern in the given module.

        This method takes a module and a mapping as input. The mapping is used to determine how the pattern should be replaced.
        It returns the number of replacements made.

        The replacement process involves finding all occurrences of the pattern in the module, and then replacing them according to the provided mapping.
        If the module is marked as locked, no replacements are made and a warning message is logged.

        Args:
            module (Module): The module in which to replace the pattern.
            iterations (int): The number of replacement iterations to perform.
            replace_all_parallel (bool): If set to True, all occurrences of the pattern will be replaced in parallel (i.e. in the same iteration).
                Otherwise, only one occurrence per iteration will be replaced. If set to True, it may result in issues for overlapping occurrences.

        Returns:
            int: The number of replacements made.

        Notes:
            This method modifies the input module. If you want to preserve the original module, create a copy before calling this method.
        """
        LOG.info(f'Starting Pattern Replacement algorithm in module {module.name}...')
        start = time.time()
        if module.locked:
            LOG.warn(f'Unable to replace pattern in module {module.name}, since the module is marked as locked!')
            return 0
        replacements_count = 0
        i = 0
        while True:
            i += 1
            total_iterations_str = f' of {iterations} ' if iterations > 0 else ' '
            LOG.debug(f'Replacement iteration {i}{total_iterations_str}in progress...')
            mgraph = module.graph()
            matches = self.find_matches(mgraph, -1 if replace_all_parallel else 1)
            new_replacements = self._replace(module, matches, replacements_count)
            replacements_count += new_replacements
            if iterations > 0 and i >= iterations:
                LOG.info(f'Finished replacement algorithm after {i} iterations, stopping...')
                break
            if new_replacements == 0:
                LOG.debug(f'No more replacement occurrences found, stopping replacement algorithm after {i} iterations...')
                break
        LOG.info(f'Finished replacement of {replacements_count} pattern occurrences in module {module.name} in {round(time.time() - start, 2)} s!')
        return replacements_count

    def _replace(self, module: Module, matches: Match, replacements_count: int) -> int:
        """
        Replaces the pattern occurrences in a given module.

        This method is responsible for replacing all occurrences of a specific pattern within a given module.
        It iterates through each match found by the `find_matches` method and performs the necessary replacements.

        For each match, it first collects instances from the module to replace with the pattern instances.
        Then, it creates instance (circuit-pattern) pairings for each node to map circuit to the pattern.
        If an occurrence contains locked instances, it skips this occurrence.
        Otherwise, it replaces the current occurrence and connects the new pattern instances.

        Args:
            module (Module): The input module where replacements will be performed.
            matches (Match): An object representing the found pattern matches in the module.
            replacements_count (int): The number of replacements performed so far. Functions as a counter.

        Returns:
            Tuple[int, Set[Instance]]: A tuple containing the number of replacements performed and a set of instances to delete after replacement.
        """
        # The number of replacements performed in this method call
        new_replacements_count = 0
        skips = 0
        for i, match in enumerate(matches.matches):
            LOG.debug(f'Iteration {i + 1} of {matches.count}:')
            # Collect instances from module to replace with the pattern instances
            instances_to_replace: Set[Instance] = set(module.instances[n] for n in match.nodes)

            # Collect instance (circuit-pattern) pairings for each node to map circuit to the pattern
            c2p_pairings: Dict[str, str] = self._circuit_to_pattern_pairing(matches.pairings, match, i)
            LOG.debug(f'\tCollected circuit-to-pattern mapping: {c2p_pairings}')

            if any(p.width > 1 for i in instances_to_replace for p in i.ports.values()):
                LOG.error(f'Not replacing match "{match.name}" (index {i}) since it does not match exactly the width of the pattern!')
                continue
            if not c2p_pairings:
                LOG.error(f'Found no pairings for match "{match.name}"! This might be caused by boundary conditions invalidating the match...')
                continue

            # Replace current occurrence
            if any(inst.locked for inst in instances_to_replace):
                self._skip_locked_occurrence(instances_to_replace)
                skips += 1
            else:
                new_instances_mapping = self._replace_occurrence(module, replacements_count + i - skips)
                self._connect_pattern_interface(module, new_instances_mapping, c2p_pairings)
                self._connect_pattern_internal(module, new_instances_mapping, c2p_pairings, replacements_count + i - skips)
                new_replacements_count += 1
                for inst in instances_to_replace:
                    module.remove_instance(inst)
        if skips:
            LOG.debug(f'Skipped {skips} pattern occurrences due to immutability.')
        return new_replacements_count

    def _circuit_to_pattern_pairing(self, match_pairing: Dict[str, Dict[int, str]], match: MDG[str], i: int) -> Dict[str, str]:
        """
        Creates a dictionary that maps circuit nodes to their corresponding pattern nodes
        based on the given match pairing and iteration index.

        Args:
            match_pairing (Dict[str, Dict[int, str]]): The pairing between circuit and pattern nodes across multiple matches.
            match (networkx.MultiDiGraph): The current match being processed.
            i (int): The iteration index of the current match.

        Returns:
            Dict[str, str]: A dictionary where each key is a circuit node and its corresponding value is the matched pattern node.
        """
        try:
            return {n: next(pair_n for pair_n in match_pairing if match_pairing[pair_n][i] == n) for n in match.nodes}
        except StopIteration:
            LOG.error(f'Unable to find circuit-to-pattern pairing for match "{match.name}"!')
            return {}

    def _skip_locked_occurrence(self, module_instances: Set[Instance]) -> None:
        """
        Logs a warning message and skips the replacement of an locked pattern occurrence.

        This function is called when an instance in the module that is part of a pattern occurrence is marked as locked.
        It logs a warning message to notify the user and skips the replacement of this occurrence.

        Args:
            module_instances (Set[Instance]): A set of instances from the module that form the current pattern occurrence.
        """
        insts = [inst for inst in module_instances if inst.locked]
        for inst in insts:
            warn_msg = f'Unable to replace pattern occurrence at instance {inst.name} (path {inst.path}, type {inst.instance_type}), since this instance is marked as locked!'
            LOG.warn(warn_msg)

    def _replace_occurrence(self, module: Module, replacement_counter: int) -> Dict[str, str]:
        """
        Replaces an occurrence of the pattern in the given module.

        This function creates new instances for each node in the replacement graph and adds them to the module.
        It returns a dictionary mapping the names of the nodes in the replacement graph
        to their corresponding instance names in the module.

        Args:
            module (Module): The module where the occurrence is being replaced.
            replacement_counter (int): A counter used to generate unique instance names.

        Returns:
            Dict[str, str]: A dictionary with keys as node names from the replacement graph
                and values as instance names in the module.
        """
        pattern_inst_mapping: Dict[str, str] = {}
        for new_inst_node in self.replacement_graph.nodes:
            # Create and add Instance for current instance node from the replacement graph
            inst_name = f'{new_inst_node}{CFG.id_external}replaced{replacement_counter}'
            inst_type = dict(self.replacement_graph.nodes.data())[new_inst_node]['ntype_info']
            LOG.debug(f'\tAdding pattern node {inst_name} (type {inst_type})...')
            pattern_inst: Instance = self.replacement_graph.nodes[new_inst_node]['ndata']
            width = max(p.width for p in pattern_inst.ports.values())
            new_inst_cls = get(inst_type) if get(inst_type) is not None else Instance
            module.add_instance(new_inst_cls(raw_path=f'{module.name}.{inst_name}', instance_type=inst_type, width=width))

            # Update mapping
            pattern_inst_mapping[new_inst_node] = inst_name
        return pattern_inst_mapping

    def _connect_pattern_interface(
        self,
        module: Module,
        pattern_name_mapping: Dict[str, str],
        cp_pairings: Dict[str, str],
    ) -> None:
        """
        Connects the replaced pattern instances to the rest of the circuit.

        This method takes a module with newly added pattern instances and connects them to the corresponding wires in the circuit.
        The connection is established by mapping the pattern instance names to their corresponding circuit instance names
        using the `pattern_name_mapping` dictionary.
        Then, for each edge in the replacement graph, it finds the corresponding wire segment in the circuit
        and connects the pattern instance to it.

        Args:
            module (Module): The module containing the newly added pattern instances.
            pattern_name_mapping (Dict[str, str]): A dictionary mapping default pattern instance names to their corresponding pattern
                instance names in the circuit (i.e. maps the original pattern name to the modified pattern name for uniqueness).
            cp_pairings (Dict[str, str]): A dictionary mapping circuit instances to their corresponding pattern instances.
        """
        for new_tuple, old_tuple in self.mapping.items():
            # Map the new instance tuple to the corresponding pattern instance name
            # (replace the generic pattern name with the real instance name)
            new_tuple = (pattern_name_mapping[new_tuple[0]], new_tuple[1], new_tuple[2])
            debug_msg = f'\tConnecting segment {new_tuple[2]} of port {new_tuple[1]} of pattern instance {new_tuple[0]} to the same wire as segment {old_tuple[2]} of port {old_tuple[1]} of the former circuit instance {old_tuple[0]}'
            LOG.debug(debug_msg)

            # Get the referenced old port segments from the module
            old_psegs = self._get_old_port_segments(module, old_tuple, cp_pairings)

            # Get the wire segment from the module
            wp_seg_list: List[Tuple[Optional[WireSegment], PortSegment]] = [
                (module.get_from_path(old_pseg.ws_path), old_pseg) for old_pseg in old_psegs if old_pseg.is_connected
            ]

            # Connect the pattern instance to the wire segment
            for wp_seg_tuple in wp_seg_list:
                self._connect_instance(wp_seg_tuple[0], module.instances[new_tuple[0]], new_tuple, wp_seg_tuple[1])
            LOG.debug(f'\tFinished connection of {new_tuple} -> {old_tuple}!')

    def _connect_pattern_internal(
        self, module: Module, instance_renaming_mapping: Dict[str, str], pattern2instance_mapping: Dict[str, str], counter: int
    ) -> None:
        processed_connections: List[Tuple[str, str, str]] = []
        wire_counter2 = 0
        for pattern_node in self.replacement_graph.nodes:
            for pattern_u, pattern_v, port_key in all_edges(self.replacement_graph, pattern_node):
                base_u_name = next((k for k, v in pattern2instance_mapping.items() if v == pattern_u), pattern_u)
                base_v_name = next((k for k, v in pattern2instance_mapping.items() if v == pattern_v), pattern_v)
                origin_inst = module.instances[instance_renaming_mapping[base_u_name]]
                target_inst = module.instances[instance_renaming_mapping[base_v_name]]
                origin_pname, target_pname = port_key.split(CFG.id_internal)
                origin_p = origin_inst.ports[origin_pname]
                target_p = target_inst.ports[target_pname]
                wname = f'{CFG.id_internal}pattern_replace{CFG.id_internal}{counter}{CFG.id_internal}{wire_counter2}'
                module.create_wire(wname, width=origin_p.width)
                wire_counter2 += 1
                w = module.wires[wname]
                segment_list = origin_p.segments if len(origin_p.segments) >= len(target_p.segments) else target_p.segments
                for seg_i in segment_list:
                    origin_inst.connect_modify(origin_pname, w[seg_i].path, PortDirection.OUT, seg_i)
                    target_inst.connect_modify(target_pname, w[seg_i].path, PortDirection.OUT, seg_i)
                    w[seg_i].add_port_segments([origin_p[seg_i], target_p[seg_i]])
                processed_connections.append((pattern_u, pattern_v, port_key))

    def _get_old_port_segments(self, module: Module, old_tuple: Tuple[str, str, int], pairs: Dict[str, str]) -> List[PortSegment]:
        """
        Retrieves the port segment from an old instance that was part of a pattern match.

        This method takes into account the pairings between circuit instances and pattern instances to identify
        the correct port segment. It first identifies all circuit instances with names matching the pattern
        instance name in the pairing dictionary, then selects the first one (assuming uniqueness for simplicity -
        there should never be multiple instances with the same name in the same module).

        Args:
            module (Module): The module containing the old instances.
            old_tuple (Tuple[str, str, int]): A tuple containing the old instance name, port name, and segment index.
            pairs (Dict[str, str]): A dictionary mapping circuit instance names to pattern instance names.

        Returns:
            List[PortSegment]: The port segment of the old instance that corresponds to the given pattern instance
                (if the index in the tuple is a valid index), or the whole segment list of the port (if the segment
                index is `-1`).
        """
        old_iname, old_p, old_seg_i = old_tuple
        # Identify all circuit instances with names matching the pattern instance name in the pairing dictionary
        old_insts_with_name = [circuit_inst for circuit_inst, pattern_inst in pairs.items() if pattern_inst == old_iname]

        # Select the first one (assuming uniqueness)
        old_inst = module.instances[old_insts_with_name[0]]

        # Get the port segment from the selected instance
        if old_seg_i != -1:
            return [old_inst.ports[old_p][old_seg_i]]
        return list(old_inst.ports[old_p].segments.values())

    def _connect_instance(
        self, wire_seg: Optional[WireSegment], new_inst: Instance, new_inst_tuple: Tuple[str, str, int], old_port_seg: PortSegment
    ) -> None:
        """
        Connects an instance to a given wire segment.

        Args:
            wire_seg (WireSegment): The wire segment to connect the instance to.
            new_inst (Instance): The instance to be connected.
            new_inst_tuple (Tuple[str, str, int]): A tuple containing information about the connection.
                It consists of three elements:
                - The name of the pattern instance
                - The port name on which the segment is located
                - The index of the segment in the port's segments list
            old_port_seg (PortSegment): The original PortSegment that was connected to this wire.

        Note: If the given wire segment does not exist, no connection will be made and a message will be logged.
        """
        if wire_seg is None:
            # Unconnected port
            LOG.debug(f'Encountered an unconnected port ({old_port_seg.path}), no connection will be made!')
        else:
            _, new_port, _ = new_inst_tuple
            new_inst.connect_modify(new_port, old_port_seg.ws_path, old_port_seg.direction, old_port_seg.index)
            new_port_seg = new_inst.ports[new_port][old_port_seg.index]
            wire_seg.add_port_segment(new_port_seg)
            wire_seg.remove_port_segment(old_port_seg)


EMPTY_PATTERN = Pattern(EMPTY_GRAPH)
