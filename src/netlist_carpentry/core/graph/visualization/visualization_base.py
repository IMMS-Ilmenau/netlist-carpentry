from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Dict, Optional

from pydantic import NonNegativeInt, PositiveInt

from netlist_carpentry.core.exceptions import ObjectNotFoundError
from netlist_carpentry.core.graph.module_graph import ModuleGraph
from netlist_carpentry.core.graph.visualization.formatting import Format
from netlist_carpentry.core.graph.visualization.formatting_types import FormatDict


class VisualizationBase(ABC):
    def __init__(
        self,
        graph: ModuleGraph,
        format: Optional[Format] = None,
        default_color: str = 'lightblue',
        default_size: NonNegativeInt = 300,
    ):
        self.graph = graph
        self.default_color = default_color
        self.default_size = default_size
        self.format = format if format is not None else Format()

    @property
    def format_dict(self) -> FormatDict:
        return self.format.format_dict

    def set_labels_default(self, show_instance_names: bool = False) -> Dict[str, str]:
        return self.format.set_labels_default(self.graph, show_instance_names=show_instance_names)

    def set_format(self, name: str, *, node_color: Optional[str] = None, node_size: Optional[PositiveInt] = None) -> FormatDict:
        return self.format.set_format(name, node_color=node_color, node_size=node_size)

    def format_node(self, node_name: str, format_name: str) -> FormatDict:
        if node_name not in self.graph.nodes:
            raise ObjectNotFoundError(f"Unable to format node: No node '{node_name}' exists in the given graph!")
        return self.format.format_node(node_name, format_name)

    def format_nodes(self, predicate: Callable[[str, Dict[str, object]], bool], *, format_name: str) -> None:
        self.format.format_nodes(self.graph, predicate, format_name=format_name)

    def format_in_out(
        self,
        *,
        in_format: Optional[str] = None,
        out_format: Optional[str] = None,
    ) -> FormatDict:
        for node in self.graph.nodes:
            ntype: str = self.graph.node_subtype(node)
            if ntype == 'input' and in_format is not None:
                self.format_node(node, in_format)
            elif ntype == 'output' and out_format is not None:
                self.format_node(node, out_format)
        return self.format_dict

    @abstractmethod
    def show(self, **kwargs: object) -> None:
        pass
