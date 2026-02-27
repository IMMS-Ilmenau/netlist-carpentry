"""Mixin for building module graphs."""

from __future__ import annotations

from typing import Callable, List

from tqdm import tqdm

from netlist_carpentry.core.exceptions import PathResolutionError
from netlist_carpentry.core.graph.module_graph import ModuleGraph
from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath
from netlist_carpentry.core.netlist_elements.mixins.module_base import ModuleBaseMixin
from netlist_carpentry.core.netlist_elements.port_segment import PortSegment
from netlist_carpentry.utils.cfg import CFG


class GraphBuildingMixin(ModuleBaseMixin):
    def _get_connected_nodes(self, ws_path: WireSegmentPath, ps_fc: Callable[[PortSegment], bool] = lambda ps: True) -> List[PortSegment]:
        """Returns a list of port segment instances connected to the wire that is represented by the given wire segment path.

        Args:
            ws_path (WireSegmentPath): Path of the wire segment in question.
            ps_fc (Callable[[PortSegment], bool], optional): Filter function to filter port segments based on a given condition.
                Defaults to `lambda ps: True`, which does not filter any port segments and passes all connected port segments.
                The filter function (if given) must take a port segment instance and return a bool.

        Returns:
            List[PortSegment]: A list of port segments that are connected to the given wire segment path
                and match the filter function (if given).
        """
        try:
            ws = self.get_from_path(ws_path)
            return [ps for ps in ws.port_segments if ps_fc(ps)]
        except PathResolutionError as e:
            raise PathResolutionError(f'Unable to find wire segment {ws_path.raw} in module {self.name}!') from e

    def get_driving_ports(self, ws_path: WireSegmentPath) -> List[PortSegment]:
        """
        Retrieves the driving port segments of a given wire segment (i.e. the instances driving this wire segment).

        For each wire segment, the list of driving ports should contain exactly one entry,
        otherwise driver conflicts will arise.

        Args:
            ws_path (WireSegmentPath): The path of the wire segment for which to retrieve driving ports.

        Returns:
            List[PortSegment]: A list of port segments driving the wire segment associated with the given path.
        """
        return self._get_connected_nodes(ws_path, ps_fc=lambda ps: ps.is_driver)

    def get_load_ports(self, ws_path: WireSegmentPath) -> List[PortSegment]:
        """
        Retrieves the load port segments of a given wire segment (i.e. the instances driven by this wire segment).

        Args:
            ws_path (WireSegmentPath): The path of the wire segment for which to retrieve load ports.

        Returns:
            List[PortSegment]: A list of port segments being load of the wire segment associated with the given path.
        """
        return self._get_connected_nodes(ws_path, ps_fc=lambda ps: ps.is_load)

    def graph(self) -> ModuleGraph:
        """
        Builds a graph from the module by representing instances and ports as nodes, and connections between them as edges.

        The module graph represents the connectivity between instances and ports within a module.
        The method iterates over all instances and ports in the module. For each instance or port,
        it adds a node to the graph with relevant information (e.g., name, type). Then, for each wire segment,
        it adds an edge between the corresponding nodes representing the driver and load of that wire segment.

        Returns:
            ModuleGraph: A graph object representing the connectivity of the module.
        """
        g: ModuleGraph = ModuleGraph()
        self._build_nodes(g)
        self._build_edges(g)
        return g

    def _build_nodes(self, g: ModuleGraph) -> None:
        """
        Adds nodes to the graph based on the instances and ports of this module.

        For each instance and port, this method adds a node to the graph with relevant information (e.g., name, type).

        Args:
            g (ModuleGraph): The current state of the module graph.
        """
        if self.instances:  # Suppresses tqdm output if empty
            for inst in tqdm(self.instances.values(), desc='Building Instance Nodes', leave=False):
                g.add_node(inst.name, ntype=inst.type.name, nsubtype=inst.instance_type, ndata=inst)
        if self.ports:  # Suppresses tqdm output if empty
            for port in tqdm(self.ports.values(), desc='Building Port Nodes', leave=False):
                g.add_node(port.name, ntype=port.type.name, nsubtype=port.direction.value, ndata=port)

    def _build_edges(self, g: ModuleGraph) -> None:
        """
        Adds edges to the graph based on the wires of this module.

        For each wire (and each wire segment), this method finds its driver and load nodes,
        then adds an edge between these nodes in the graph. The edge is labeled with the name
        of the corresponding wire segment.

        Args:
            g (ModuleGraph): The current state of the module graph.
        """
        if self.wires:  # Suppresses tqdm output if empty
            for wire in tqdm(self.wires.values(), desc='Building Edges', leave=False):
                for _, ws in wire:
                    drvs = self.get_driving_ports(ws.path)
                    lds = self.get_load_ports(ws.path)
                    for dr in drvs:  # Should only contain one single element
                        p1_path = dr.path.parent
                        dr_name = p1_path.parent.name if dr.is_instance_port else p1_path.name
                        dr_seg_idx = int(dr.name)  # Name of the driving segment is the index
                        for ld in lds:
                            p2_path = ld.path.parent
                            ld_name = p2_path.parent.name if ld.is_instance_port else p2_path.name
                            ld_seg_idx = int(ld.name)  # Name of the load segment is the index
                            pname1 = p1_path.name if p1_path.name else dr_name
                            pname2 = p2_path.name if p2_path.name else ld_name
                            key = f'{pname1}{CFG.id_internal}{pname2}'
                            ename = ws.parent.name if ws.has_parent else ''
                            g.add_edge(dr_name, ld_name, key=key, ename=ename, dr_seg=dr_seg_idx, ld_seg=ld_seg_idx)
