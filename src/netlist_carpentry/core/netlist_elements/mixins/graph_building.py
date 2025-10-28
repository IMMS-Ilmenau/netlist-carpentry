from __future__ import annotations

from typing import Set

import networkx as nx
from tqdm import tqdm

from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath
from netlist_carpentry.core.netlist_elements.mixins.module_base import ModuleBaseMixin
from netlist_carpentry.core.protocols.netlist_elements import PortSegmentLike
from netlist_carpentry.utils.cfg import CFG


class GraphBuildingMixin(ModuleBaseMixin):
    def get_driving_ports(self, ws_path: WireSegmentPath) -> Set[PortSegmentLike]:
        raise NotImplementedError(f'Not implemented for mixin {self.__class__.__name__}. Any class using this mixin must implement this property.')

    def get_load_ports(self, ws_path: WireSegmentPath) -> Set[PortSegmentLike]:
        raise NotImplementedError(f'Not implemented for mixin {self.__class__.__name__}. Any class using this mixin must implement this property.')

    def build_graph(self) -> nx.MultiDiGraph[str]:
        """
        Builds a graph from the module by representing instances and ports as nodes,
        and connections between them as edges.

        The method iterates over all instances and ports in the module. For each instance or port,
        it adds a node to the graph with relevant information (e.g., name, type). Then, for each wire segment,
        it adds an edge between the corresponding nodes representing the driver and load of that wire segment.

        Returns:
            A networkx MultiDiGraph object representing the connectivity of the module.
        """
        g: nx.MultiDiGraph[str] = nx.MultiDiGraph()
        self._build_nodes(g)
        self._build_edges(g)
        return g

    def _build_nodes(self, g: nx.MultiDiGraph[str]) -> None:
        """
        Adds nodes to the graph based on the instances and ports of this module.

        For each instance and port, this method adds a node to the graph with relevant information (e.g., name, type).

        Args:
            g (networkx.MultiDiGraph): The current state of the module graph.
        """
        if self.instances:  # Suppresses tqdm output if empty
            for inst in tqdm(self.instances.values(), desc='Building Instance Nodes'):
                g.add_node(inst.name, ntype=inst.type.name, ntype_info=inst.instance_type, ndata=inst)
        if self.ports:  # Suppresses tqdm output if empty
            for port in tqdm(self.ports.values(), desc='Building Port Nodes'):
                g.add_node(port.name, ntype=port.type.name, ntype_info=port.direction.value, ndata=port)

    def _build_edges(self, g: nx.MultiDiGraph[str]) -> None:
        """
        Adds edges to the graph based on the wires of this module.

        For each wire (and each wire segment), this method finds its driver and load nodes,
        then adds an edge between these nodes in the graph. The edge is labeled with the name
        of the corresponding wire segment.

        Args:
            g (networkx.MultiDiGraph): The current state of the module graph.
        """
        if self.wires:  # Suppresses tqdm output if empty
            for wire in tqdm(self.wires.values(), desc='Building Edges'):
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
                            g.add_edge(dr_name, ld_name, key=key, ename=ws.super_wire_name, dr_seg=dr_seg_idx, ld_seg=ld_seg_idx)  # type: ignore[no-untyped-call]
