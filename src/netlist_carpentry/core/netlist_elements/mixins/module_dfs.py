from typing import List, Set, Tuple

from netlist_carpentry import LOG
from netlist_carpentry.core.netlist_elements.element_path import ElementPath
from netlist_carpentry.core.netlist_elements.mixins.module_base import ModuleBaseMixin
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.netlist_elements.port_segment import PortSegment
from netlist_carpentry.core.netlist_elements.wire_segment import WireSegment


class ModuleDfsMixin(ModuleBaseMixin):
    def dfs_paths_between(self, start: ElementPath, end: ElementPath, max_paths: int = 1) -> Set[Tuple[ElementPath, ...]]:
        """
        Performs a depth-first search (DFS) to find all paths between two given elements in the digital circuit.

        Args:
            start (ElementPath): The starting point of the path.
            end (ElementPath): The ending point of the path.
            max_paths (int): How many occurrences to find. Set to -1 to find all occurrences. Defaults to 1.

        Returns:
            Set[Tuple[ElementPath, ...]]: A set of tuples, where each tuple represents a path from the start to the end element.
        """
        if not self.is_in_module(start) or not self.is_in_module(end):
            LOG.error(f'Unable to find path between {start.raw} and {end.raw}: at least one of both paths is outside of this module!')
            return set()
        return self._dfs_paths_between(start, end, max_paths, set(), [start])

    def _dfs_paths_between(
        self, start: ElementPath, end: ElementPath, max_paths: int, found_paths: Set[Tuple[ElementPath, ...]], curr_path: List[ElementPath]
    ) -> Set[Tuple[ElementPath, ...]]:
        if start == end:
            return {(start,)}
        for next_path in self._dfs_next_paths(start):
            if next_path.raw == end.raw and next_path.type == end.type:
                found_paths.add(tuple([*curr_path, next_path]))
                LOG.info(f'Found path between start and end paths, {len(curr_path)} element(s).')
            if max_paths >= 0 and len(found_paths) == max_paths:
                return found_paths
            if next_path in curr_path:
                # LOOP detected at {next_path.raw}!
                continue
            curr_path.append(next_path)
            self._dfs_paths_between(next_path, end, max_paths, found_paths, curr_path)
            if max_paths >= 0 and len(found_paths) == max_paths:
                return found_paths
            curr_path.remove(next_path)
        return found_paths

    def _dfs_next_paths(self, curr_path: ElementPath) -> Set[ElementPath]:
        """
        Finds the next paths to be explored in the DFS.

        Args:
            curr_path (ElementPath): The current path being explored.

        Returns:
            Set[ElementPath]: A set of next paths to be explored.
        """
        e: NetlistElement = self.get_from_path(curr_path)  # type: ignore[call-overload]
        if isinstance(e, PortSegment):
            return self._dfs_single_path_next_from_port(e)
        if isinstance(e, WireSegment):
            return self._dfs_single_path_next_from_wire(e)
        return set()

    def _dfs_single_path_next_from_port(self, port_segment: PortSegment) -> Set[ElementPath]:
        """
        Finds the next paths to be explored in the DFS when the current element is a port segment.

        Args:
            port_segment (PortSegment): The current port segment being explored.

        Returns:
            Set[ElementPath]: A set of next paths to be explored.
        """
        if port_segment.is_driver:  # Instance output port or module input port
            # Next path element is a wire
            wire_seg = self.get_from_path(port_segment.ws_path)
            return {wire_seg.path} if isinstance(wire_seg, WireSegment) and wire_seg is not None else set()
        elif port_segment.is_load and port_segment.is_instance_port:
            # Next path element is the output port of the instance for which port e is an input port
            inst = self.instances[port_segment.parent_parent_name]
            return {pseg.path for p in inst.output_ports for pseg in p.segments.values()}
        # Module output port
        return set()

    def _dfs_single_path_next_from_wire(self, wire_segment: WireSegment) -> Set[ElementPath]:
        """
        Finds the next paths to be explored in the DFS when the current element is a wire segment.

        Args:
            wire_segment (WireSegment): The current wire segment being explored.

        Returns:
            Set[ElementPath]: A set of next paths to be explored.
        """
        return {ld.path for ld in wire_segment.loads()}
