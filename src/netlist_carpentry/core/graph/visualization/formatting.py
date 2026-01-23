"""Module for handling graph formats, for customization of the graphical representation."""

from typing import Callable, Dict, Optional

from pydantic import BaseModel, NonNegativeInt, PositiveInt

from netlist_carpentry.core.exceptions import ObjectNotFoundError
from netlist_carpentry.core.graph.module_graph import ModuleGraph
from netlist_carpentry.core.graph.visualization.formatting_types import FormatDict


class Format(BaseModel):
    format_dict: FormatDict = {'formats': {}, 'labels': {}, 'node_formats': {}}
    default_color: str = 'lightblue'
    default_size: NonNegativeInt = 300

    def set_labels_default(self, graph: ModuleGraph, show_instance_names: bool = False) -> Dict[str, str]:
        for node in graph.nodes:
            ntype = graph.node_subtype(node)
            if ntype == 'input' or ntype == 'output':
                self.format_dict['labels'][node] = node
            else:
                self.format_dict['labels'][node] = node if show_instance_names else ntype
        return self.format_dict['labels']

    def set_format(self, name: str, *, node_color: Optional[str] = None, node_size: Optional[PositiveInt] = None) -> FormatDict:
        self.format_dict['formats'][name] = {}
        if node_color:
            self.format_dict['formats'][name]['color'] = node_color
        if node_size:
            self.format_dict['formats'][name]['size'] = node_size
        return self.format_dict

    def format_node(self, node_name: str, format_name: str) -> FormatDict:
        if format_name not in self.format_dict['formats']:
            raise ObjectNotFoundError(f"Unable to format node: Undefined format '{format_name}'!")
        self.format_dict['node_formats'][node_name] = format_name
        return self.format_dict

    def format_nodes(self, graph: ModuleGraph, predicate: Callable[[str, Dict[str, object]], bool], *, format_name: str) -> None:
        nodes = [n for n, d in graph.nodes(data=True) if predicate(n, d)]  # type: ignore[misc]
        for n in nodes:
            self.format_node(n, format_name)
