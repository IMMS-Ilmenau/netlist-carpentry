from copy import copy
from queue import Queue
from typing import List, Set, Tuple

from netlist_carpentry import LOG
from netlist_carpentry.core.netlist_elements.element_path import ElementPath
from netlist_carpentry.core.netlist_elements.mixins.module_base import ModuleBaseMixin
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.netlist_elements.port_segment import PortSegment
from netlist_carpentry.core.netlist_elements.wire_segment import WireSegment


class ModuleBfsMixin(ModuleBaseMixin):
    def bfs_paths_between(self, start: ElementPath, end: ElementPath, return_first_only: bool = True) -> Set[Tuple[ElementPath, ...]]:
        """
        Performs a breadth-first search (BFS) to find all paths between two given elements in the digital circuit.

        Args:
            start (ElementPath): The starting point of the path.
            end (ElementPath): The ending point of the path.
            return_first_only (bool): Whether to only return the first occurrence, or all found paths. Defaults to True.

        Returns:
            Set[Tuple[ElementPath, ...]]: A set of tuples, where each tuple represents a path from the start to the end element.
        """
        if not self.is_in_module(start) or not self.is_in_module(end):
            LOG.error(f'Unable to find path between {start.raw} and {end.raw}: at least one of both paths is outside of this module!')
            return set()
        return self._bfs_paths_between(start, end, return_first_only=return_first_only)

    def _bfs_paths_between(self, start: ElementPath, end: ElementPath, return_first_only: bool = True) -> Set[Tuple[ElementPath, ...]]:
        """
        Performs a breadth-first search (BFS) to find a single path between two given elements in the digital circuit.

        Args:
            start (ElementPath): The starting point of the path.
            end (ElementPath): The ending point of the path.
            return_first_only (bool): Whether to only return the first occurrence, or all found paths. Defaults to True.

        Returns:
            Set[Tuple[ElementPath, ...]]: A set of tuples, where each tuple represents a path from the start to the end element.
        """
        is_explored: Set[ElementPath] = set()
        path_list: List[List[ElementPath]] = [[end]]
        q: Queue[ElementPath] = Queue()
        q.put(end)
        while not q.empty():
            curr_path = q.get()
            if curr_path == start and return_first_only:
                return self._bfs_path_postprocess(path_list, start)
            for path in self._bfs_next_paths(curr_path):
                self._bfs_update_path_list(path_list, curr_path, path)
                if path not in is_explored:  # To prevent double-checking on feedback loops
                    is_explored.add(path)
                    q.put(path)
        return self._bfs_path_postprocess(path_list, start)

    def _bfs_path_postprocess(self, path_list: List[List[ElementPath]], start: ElementPath) -> Set[Tuple[ElementPath, ...]]:
        """
        Post-processes the BFS result to extract the path from the start to the end element.

        Args:
            path_list (List[List[ElementPath]]): The list of paths found by the BFS.
            start (ElementPath): The starting point of the path.

        Returns:
            Set[Tuple[ElementPath, ...]]: A set of tuples, where each tuple represents a path from the start to the end element.
        """
        # When this function is called by Module._dfs_single_path_between:
        # Target path lists (i.e. the ones leading from start to end) are most probably somewhere near the end of the path list
        # Reverse list for better performance in large modules
        bfs_lists = set()
        for lst in reversed(path_list):
            if lst[-1] == start:
                bfs_lists.add(tuple(lst[::-1]))
        return bfs_lists

    def _bfs_update_path_list(self, path_list: List[List[ElementPath]], curr_path: ElementPath, next_path: ElementPath) -> None:
        """
        Updates the list of paths found by the BFS.

        Args:
            path_list (List[List[ElementPath]]): The list of paths found by the BFS.
            curr_path (ElementPath): The current path being explored.
            next_path (ElementPath): The next path to be added to the list.
        """
        for lst in path_list:
            if lst[-1] == curr_path:
                cpy_lst = copy(lst)
                cpy_lst.append(next_path)
                path_list.append(cpy_lst)

    def _bfs_next_paths(self, curr_path: ElementPath) -> Set[ElementPath]:
        """
        Finds the next paths to be explored in the BFS.

        Args:
            curr_path (ElementPath): The current path being explored.

        Returns:
            Set[ElementPath]: A set of next paths to be explored.
        """
        e: NetlistElement = self.get_from_path(curr_path)  # type: ignore[call-overload]
        if isinstance(e, PortSegment):
            return self._bfs_single_path_next_from_port(e)
        if isinstance(e, WireSegment):
            return self._bfs_single_path_next_from_wire(e)
        return set()

    def _bfs_single_path_next_from_port(self, port_segment: PortSegment) -> Set[ElementPath]:
        """
        Finds the next paths to be explored in the BFS when the current element is a port segment.

        Args:
            port_segment (PortSegment): The current port segment being explored.

        Returns:
            Set[ElementPath]: A set of next paths to be explored.
        """
        if port_segment.is_load:  # Instance input port or Module output port -> driven by wire
            # Next path element is a wire
            wire_seg = self.get_from_path(port_segment.ws_path)
            return {wire_seg.path} if isinstance(wire_seg, WireSegment) and wire_seg is not None else set()
        elif port_segment.is_instance_port and port_segment.is_driver:  # Instance output port
            # Next path element is the input port of the instance for which port e is an output port
            inst = self.instances[port_segment.parent_parent_name]
            return {pseg.path for p in inst.input_ports for pseg in p.segments.values()}
        # Module input port
        return set()

    def _bfs_single_path_next_from_wire(self, wire_segment: WireSegment) -> Set[ElementPath]:
        """
        Finds the next paths to be explored in the BFS when the current element is a wire segment.

        Args:
            wire_segment (WireSegment): The current wire segment being explored.

        Returns:
            Set[ElementPath]: A set of next paths to be explored.
        """
        return {drv.path for drv in wire_segment.driver()}
