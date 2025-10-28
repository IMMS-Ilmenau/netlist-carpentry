from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from networkx import MultiDiGraph as MDG

from netlist_carpentry.api.read.yosys_netlist import YosysNetlistReader as YNR
from netlist_carpentry.core.circuit import Circuit
from netlist_carpentry.core.graph.constraint import Constraint
from netlist_carpentry.core.graph.pattern import Pattern
from netlist_carpentry.core.netlist_elements.module import Module


class PatternGenerator:
    """
    This class is a utility class used to create pattern objects from given HDL code,
    circuits, or JSON netlists.

    The method `build_from_circuit` can be used to create a pattern object by providing
    a circuit object, which will be used to find structurally matching subcircuits in a
    larger circuit. In addition a replacement circuit object can be passed as well, which
    is then used to replace any pattern occurrences in the original circuit.
    In this case, both circuits must have the same interface, i.e. the top module must
    have the same input/output ports in both circuits.

    The methods `build_from_verilog` and `build_from_yosys_netlist` work analogously,
    where the pattern and replacement circuits are either specified in Verilog code,
    or as Yosys-generated JSON netlists.
    """

    @classmethod
    def build_from_circuit(
        cls,
        match_circuit: Circuit,
        replacement_circuit: Circuit = Circuit(name=''),
        remove_ports: bool = True,
        ignore_port_names: bool = False,
        constraints: List[Constraint] = [],
    ) -> Pattern:
        """
        Builds a Pattern instance from Verilog files.

        Args:
            match_circuit (Circuit): The circuit object representing the structure to find.
            replacement_circuit (Circuit, optional): The circuit object representing the replacement structure.
                If not specified, the pattern can only be used for analysis and not for modification. Defaults to ''.
            remove_ports (bool, optional): Whether to remove all input and output ports of the patterns. Defaults to True.
                If set to True, all ports are removed, and only the instances inside the module (and the connections between them)
                are used as pattern. If set to False, the graph of the given modules is used directly, including its module ports.
                The matching algorithm will then only find matches, if the whole structure (including the module ports) is found!
            ignore_port_names (bool, optional): Whether to check port names when trying to match the pattern against found instances.
                Defaults to False, in which case all port names must match the given pattern.
            constraints (List[Constraint], optional): List of constraints that need to be satisfied by any matching subgraphs.
                Defaults to [], which means no constraints are applied.

        Returns:
            Pattern: A Pattern instance representing the specified subgraph pattern and optionally a replacement graph.
        """
        find_graph, find_module = PatternGenerator._from_circuit(match_circuit, remove_ports)
        if replacement_circuit:
            replacement_graph, replacement_module = PatternGenerator._from_circuit(replacement_circuit, remove_ports)
            mapping = Pattern.get_mapping(find_module, replacement_module)
            return Pattern(find_graph, replacement_graph, ignore_port_names=ignore_port_names, matching_constraints=constraints, mapping=mapping)
        return Pattern(find_graph, ignore_port_names=ignore_port_names, matching_constraints=constraints)

    @classmethod
    def build_from_verilog(
        cls,
        match_pattern_file: str,
        replacement_pattern_file: str = '',
        remove_ports: bool = True,
        ignore_port_names: bool = False,
        constraints: List[Constraint] = [],
    ) -> Pattern:
        """
        Builds a Pattern instance from Verilog files.

        Args:
            match_pattern_file (str): The path to the Verilog file containing the pattern to find.
            replacement_pattern_file (str, optional): The path to the Verilog file containing the replacement pattern.
                If not specified, the pattern can only be used for analysis and not for modification. Defaults to ''.
            remove_ports (bool, optional): Whether to remove all input and output ports of the patterns. Defaults to True.
                If set to True, all ports are removed, and only the instances inside the module (and the connections between them)
                are used as pattern. If set to False, the graph of the given modules is used directly, including its module ports.
                The matching algorithm will then only find matches, if the whole structure (including the module ports) is found!
            ignore_port_names (bool, optional): Whether to check port names when trying to match the pattern against found instances.
                Defaults to False, in which case all port names must match the given pattern.
            constraints (List[Constraint], optional): List of constraints that need to be satisfied by any matching subgraphs.
                Defaults to [], which means no constraints are applied.

        Returns:
            Pattern: A Pattern instance representing the specified subgraph pattern and optionally a replacement graph.
        """
        find_graph, find_module = PatternGenerator._module_from_verilog(match_pattern_file, remove_ports)
        if replacement_pattern_file:
            replacement_graph, replacement_module = PatternGenerator._module_from_verilog(replacement_pattern_file, remove_ports)
            mapping = Pattern.get_mapping(find_module, replacement_module)
            return Pattern(find_graph, replacement_graph, ignore_port_names=ignore_port_names, matching_constraints=constraints, mapping=mapping)
        return Pattern(find_graph, ignore_port_names=ignore_port_names, matching_constraints=constraints)

    @classmethod
    def build_from_yosys_netlists(
        cls,
        match_pattern_file: str,
        replacement_pattern_file: str = '',
        remove_ports: bool = True,
        ignore_port_names: bool = False,
        constraints: List[Constraint] = [],
    ) -> Pattern:
        """
        Builds a Pattern instance from Yosys netlist files.

        Args:
            match_pattern_file (str): The path to the Yosys netlist file containing the pattern to find.
            replacement_pattern_file (str, optional): The path to the Yosys netlist file containing the replacement pattern.
                If not specified, the pattern can only be used for analysis and not for modification. Defaults to ''.
            remove_ports (bool, optional): Whether to remove all input and output ports of the patterns. Defaults to True.
                If set to True, all ports are removed, and only the instances inside the module (and the connections between them)
                are used as pattern. If set to False, the graph of the given modules is used directly, including its module ports.
                The matching algorithm will then only find matches, if the whole structure (including the module ports) is found!
            ignore_port_names (bool, optional): Whether to check port names when trying to match the pattern against found instances.
                Defaults to False, in which case all port names must match the given pattern.
            constraints (List[Constraint], optional): List of constraints that need to be satisfied by any matching subgraphs.
                Defaults to [], which means no constraints are applied.

        Returns:
            Pattern: A Pattern instance representing the specified subgraph pattern and optionally a replacement graph.
        """
        find_graph, find_module = PatternGenerator._module_from_json(match_pattern_file, remove_ports)
        if replacement_pattern_file:
            replacement_graph, replacement_module = PatternGenerator._module_from_json(replacement_pattern_file, remove_ports)
            mapping = Pattern.get_mapping(find_module, replacement_module)
            return Pattern(find_graph, replacement_graph, ignore_port_names=ignore_port_names, matching_constraints=constraints, mapping=mapping)
        return Pattern(find_graph, ignore_port_names=ignore_port_names, matching_constraints=constraints)

    @classmethod
    def _module_from_verilog(cls, file_path: str, remove_ports: bool) -> Tuple[MDG[str], Module]:
        """
        Reads a Verilog file from the given file path and returns its graph representation along with the module.

        Args:
            file_path (str): Path to the Verilog file.
            remove_ports (bool): Whether to remove all input and output ports of the module graph from the given file.
                If set to True, all ports are removed, and only the instances inside the module (and the connections between them)
                are used in the graph. If set to False, the graph of the given modules is used directly, including its module ports.
                The matching algorithm will then only find matches, if the whole structure (including the module ports) is found!

        Returns:
            Tuple[networkx.MultiDiGraph, Module]: Graph representation of the module in the provided file, plus the module itself.

        Raises:
            ValueError: If the provided file contains more or less than one module.
        """
        from netlist_carpentry.api.read.read_utils import read

        circuit = read(Path(file_path))
        return PatternGenerator._from_circuit(circuit, remove_ports)

    @classmethod
    def _module_from_json(cls, file_path: str, remove_ports: bool) -> Tuple[MDG[str], Module]:
        """
        Reads a Yosys netlist from the given file path and returns its graph representation along with the module.

        Args:
            file_path (str): Path to the Yosys netlist file.
            remove_ports (bool): Whether to remove all input and output ports of the module graph from the given file.
                If set to True, all ports are removed, and only the instances inside the module (and the connections between them)
                are used in the graph. If set to False, the graph of the given modules is used directly, including its module ports.
                The matching algorithm will then only find matches, if the whole structure (including the module ports) is found!

        Returns:
            Tuple[networkx.MultiDiGraph, Module]: Graph representation of the module in the provided file, plus the module itself.

        Raises:
            ValueError: If the provided file contains more or less than one module.
        """
        circuit = YNR(Path(file_path)).transform_to_circuit()
        return PatternGenerator._from_circuit(circuit, remove_ports)

    @classmethod
    def _from_circuit(cls, circuit: Circuit, remove_ports: bool) -> Tuple[MDG[str], Module]:
        """
        Converts a Circuit object into a graph representation and its corresponding Module.

        Args:
            circuit (Circuit): The circuit to convert.
            remove_ports (bool): Whether to remove all input and output ports of the module graph from the given circuit.
                If set to True, all ports are removed, and only the instances inside the module (and the connections between them)
                are used in the graph. If set to False, the graph of the given modules is used directly, including its module ports.
                The matching algorithm will then only find matches, if the whole structure (including the module ports) is found!

        Returns:
            Tuple[networkx.MultiDiGraph, Module]: Graph representation of the module in the provided circuit, plus the module itself.

        Raises:
            ValueError: If the provided circuit contains more or less than one module.
        """
        err_msg = 'Can currently only build pattern if the provided file contains exactly 1 module, but found {cnt} modules in circuit {circuit}!'
        if len(circuit.modules) != 1:
            raise ValueError(err_msg.format(cnt=len(circuit.modules), circuit=circuit.name))
        module = circuit.first
        module_graph = module.graph()
        Pattern._add_node_metadata(module_graph)
        if remove_ports:
            Pattern._remove_ports_from_pattern_graphs(module_graph)
        return (module_graph, module)
