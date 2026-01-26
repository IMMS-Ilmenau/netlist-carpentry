"""Wrapper module for networkx.MultiDiGraph, with customizations specifically for using the MultiDiGraph class for module graphs in digital circuits."""
# mypy: disable-error-code="misc,no-any-return"

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Set, Tuple, Union, overload

from networkx import MultiDiGraph

if TYPE_CHECKING:
    from netlist_carpentry import Instance, Module, Port

    # MyPy sees this as a generic class
    BaseGraph = MultiDiGraph[str]
else:
    BaseGraph = MultiDiGraph  # Runtime sees this as a standard class

NODE_TYPES = Literal['INSTANCE', 'PORT']
NODE_CLASSES = Union['Instance', 'Port[Module]']
DATA_CATEGORIES = Literal['ndata', 'ntype', 'nsubtype']


class ModuleGraph(BaseGraph):
    @overload
    def get_data(self, node_name: str, key: Literal['ntype']) -> NODE_TYPES: ...
    @overload
    def get_data(self, node_name: str, key: Literal['nsubtype']) -> str: ...
    @overload
    def get_data(self, node_name: str, key: Literal['ndata']) -> NODE_CLASSES: ...
    @overload
    def get_data(self, node_name: str, key: DATA_CATEGORIES) -> str: ...
    @overload
    def get_data(self, node_name: str, key: str) -> object: ...
    def get_data(self, node_name: str, key: Union[DATA_CATEGORIES, str]) -> object:
        return self.nodes[node_name][key]

    @overload
    def set_data(self, node_name: str, val: NODE_TYPES, key: Literal['ntype']) -> None: ...
    @overload
    def set_data(self, node_name: str, val: str, key: Literal['nsubtype']) -> None: ...
    @overload
    def set_data(self, node_name: str, val: NODE_CLASSES, key: Literal['ndata']) -> None: ...
    @overload
    def set_data(self, node_name: str, val: object, key: str) -> None: ...
    def set_data(self, node_name: str, val: object, key: str) -> None:
        self.nodes[node_name][key] = val

    def node_type(self, node_name: str) -> NODE_TYPES:
        """Returns the node type of the given node.

        The node type is the EType name of the element modeled by the node.
        In this context, a node represents either an instance or a module port.
        Thus, the node_type is either `INSTANCE` or `PORT`.

        Returns:
            Literal['INSTANCE', 'PORT']: Whether this node is an instance (`INSTANCE`) or a module port (`PORT`).
        """
        return self.get_data(node_name, 'ntype')

    def node_subtype(self, node_name: str) -> str:
        """The node type specification (subtype) of the given node.

        In the graph context, the node type is either "PORT" or "INSTANCE"
        (depending on what the node models).
        In contrast, the subtype further specifies the role of the node.
        For ports, the subtype is the port direction, i.e. `input`, `output` or `inout`.
        For instances, the subtype is the instance type, e.g. for a node modeling an AND gate,
        this method returns `§and`, and for a submodule node, this method returns the name of
        the instantiated module (NOT the instance name).

        Args:
            node_name (str): The name to retrieve the subtype of.

        Returns:
            str: The subtype (port direction for module ports, instance type for instances) of the given node.
        """
        return self.get_data(node_name, 'nsubtype')

    def all_edges(self, node_name: str) -> Set[Tuple[str, str, str]]:
        """
        Returns a set of all edges (both incoming and outgoing) connected to the given node in the graph.

        Each tuple in the returned set follows the structure (edge_start, edge_end, edge_key). Accordingly,
        for all incoming edges, edge_end is `node_name` and for all outgoing edges, edge_start is `node_name`.
        The edge_key determines the ports over which both nodes are connected. The edge_key follows the structure
        `{port_name_edge_start}§{port_name_edge_end}`. The section sign (`§`) is used to divide between both ports.
        This character depends on the config entry `CFG.nc_identifier_internal`.

        Args:
            node_name (str): The name of the node.

        Returns:
            Set[Tuple[str, str, str]]: A set of tuples representing the edges, where each tuple contains the source node,
                target node, and edge key.
        """
        return set(self.edges(node_name, keys=True)).union(set(self.in_edges(node_name, keys=True)))
