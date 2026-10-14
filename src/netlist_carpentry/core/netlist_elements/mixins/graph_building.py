"""Mixin for building module graphs."""

from __future__ import annotations

from typing import Callable, List

from tqdm import tqdm

from netlist_carpentry.core.exceptions import PathResolutionError
from netlist_carpentry.core.graph.module_graph import ModuleGraph
from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath
from netlist_carpentry.core.netlist_elements.mixins.module_base import ModuleBaseMixin
from netlist_carpentry.core.netlist_elements.port import ANY_PORT
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
            for inst in tqdm(self.instances.values(), desc='Building Instance Nodes', leave=False, disable=CFG.disable_tqdm):
                g.add_node(inst.name, ntype=inst.type.name, nsubtype=inst.instance_type, ndata=inst)
        if self.ports:  # Suppresses tqdm output if empty
            for port in tqdm(self.ports.values(), desc='Building Port Nodes', leave=False, disable=CFG.disable_tqdm):
                g.add_node(port.name, ntype=port.type.name, nsubtype=port.direction.value, ndata=port)

    def _build_edges(self, g: ModuleGraph) -> None:
        """
        Adds edges to the graph based on the wires of this module.

        For each wire, this method iterates over its segments and identifies the driving
        port segment(s) and load port segment(s). An edge is created from each driver node
        to each load node for every connected (driver_segment, load_segment) pair.

        If the port belongs to a **module** (``is_module_port``), the node name is the port name itself (e.g. ``"in1"``).
        If the port belongs to an **instance** (``is_instance_port``), the node name is the instance name (e.g. ``"and_inst"``).

        The Edge key follows the format ``{driver_port_name}§{load_port_name}`` where the section sign separates the source and target port names.
        When multiple edges exist between the same pair of nodes (e.g. multi-bit buses), the edge key is made unique by appending
        the driver and load segment indices: ``{driver_port_name}[{driver_seg_idx}]{load_port_name}[{load_seg_idx}]``.

        Edge attributes:
        - ``ename``: The wire name (edge name) connecting the driver and load
        - ``dr_seg``: The driver segment index
        - ``ld_seg``: The load segment index
        - `width`: The width of the wire modeled by this edge. Is 1 for edges with indexed keys (e.g. `in1[0]§out1[0]`)

        Args:
            g (ModuleGraph): The current state of the module graph.
        """
        if self.wires:  # Suppresses tqdm output if empty
            for wire in tqdm(self.wires.values(), desc='Building Edges', leave=False, disable=CFG.disable_tqdm):
                for wire_seg in wire.segments.values():
                    drivers = [ps for ps in wire_seg.port_segments if ps.is_driver]
                    loads = [ps for ps in wire_seg.port_segments if ps.is_load]

                    for drv in drivers:
                        for ld in loads:
                            # Resolve the graph node name for each port segment
                            # Module ports are nodes by their own name, instance ports are grouped under the instance node
                            drv_port = drv.parent
                            drv_node = drv_port.name if drv.is_module_port else drv_port.parent.name
                            ld_port = ld.parent
                            ld_node = ld_port.name if ld.is_module_port else ld_port.parent.name

                            edge_key = f'{drv_port.name}[{drv.index}]{CFG.id_internal}{ld_port.name}[{ld.index}]'

                            if not g.has_edge(drv_node, ld_node, key=edge_key):
                                g.add_edge(drv_node, ld_node, key=edge_key, ename=wire.name, dr_seg=drv.index, ld_seg=ld.index, width=1)

                            if drv_port.width == ld_port.width:  # Could probably merge these together, if all are connected 1:1
                                self._build_edges_try_merge(g, wire.name, drv_port, ld_port)

    def _build_edges_try_merge(self, g: ModuleGraph, wname: str, drv_port: ANY_PORT, ld_port: ANY_PORT) -> None:
        drv_offset = drv_port.offset or 0
        ld_offset = ld_port.offset or 0
        n_d = drv_port.name if drv_port.is_module_port else drv_port.parent.name
        n_l = ld_port.name if ld_port.is_module_port else ld_port.parent.name
        p_d = drv_port.name
        p_l = ld_port.name
        mergeable = all(g.has_edge(n_d, n_l, f'{p_d}[{i + drv_offset}]{CFG.id_internal}{p_l}[{i + ld_offset}]') for i in range(drv_port.width))
        if not mergeable:
            return
        for i in range(drv_port.width):
            g.remove_edge(n_d, n_l, f'{p_d}[{i + drv_offset}]{CFG.id_internal}{p_l}[{i + ld_offset}]')
        # TODO dr_seg/ld_seg should be None
        g.add_edge(n_d, n_l, f'{p_d}{CFG.id_internal}{p_l}', dr_seg=None, ld_seg=None, width=drv_port.width, ename=wname)
