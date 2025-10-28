from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Optional, Tuple, Union

import matplotlib.pyplot as plt
import networkx as nx

NodeColor = str
NodeSize = int
FormatDict = Dict[str, Tuple[NodeColor, NodeSize]]


class Visualization:
    def __init__(self, graph: nx.MultiDiGraph[str], default_color: str = 'lightblue', default_size: int = 300):
        self.graph = graph
        self.default_color = default_color
        self.default_size = default_size
        self.format_dict: FormatDict = {}
        for n in self.graph.nodes:
            self.format_dict[n] = (self.default_color, self.default_size)

    @property
    def labels(self) -> Dict[str, str]:
        labels = {}
        for node in self.graph.nodes:
            ntype: str = self.graph.nodes[node]['ntype_info']  # type: ignore[misc]
            if ntype == 'input':
                labels[node] = node
            elif ntype == 'output':
                labels[node] = node
            else:
                labels[node] = ntype
        return labels

    def format_node(self, node_name: str, *, node_color: Optional[NodeColor] = None, node_size: Optional[NodeSize] = None) -> None:
        if node_name not in self.graph.nodes:
            raise AttributeError(f"Unable to format node: No node '{node_name}' exists in the given graph!")
        if node_color is None:
            node_color = self.format_dict[node_name][0] if node_name in self.format_dict else self.default_color
        if node_size is None:
            node_size = self.format_dict[node_name][1] if node_name in self.format_dict else self.default_size
        self.format_dict[node_name] = (node_color, node_size)

    def format_nodes(
        self, predicate: Callable[[str, Dict[str, object]], bool], *, node_color: Optional[NodeColor] = None, node_size: Optional[NodeSize] = None
    ) -> None:
        nodes = [n for n, d in self.graph.nodes(data=True) if predicate(n, d)]  # type: ignore[misc]
        for n in nodes:
            self.format_node(n, node_color=node_color, node_size=node_size)

    def _clean_graph(self) -> None:
        """
        The module graph by default contains additional node data (i.e. the Python object itself),
        which cannot be exported, so it must be removed first.
        This is done here by removing the `ndata` attribute completely.
        """
        for node in self.graph.nodes:
            if 'ndata' in self.graph.nodes[node]:  # type: ignore[misc]
                self.graph.nodes[node].pop('ndata')  # type: ignore[misc]

    def visualize(self, figsize: Tuple[float, float] = (10, 8)) -> None:
        self._clean_graph()
        pos = nx.kamada_kawai_layout(self.graph)

        plt.figure(figsize=figsize)
        for n in self.graph.nodes:
            format_tuple = self.format_dict[n]
            color = format_tuple[0] if len(format_tuple) >= 1 else self.default_color
            size = format_tuple[1] if len(format_tuple) >= 2 else self.default_size
            nodes = [n]
            nx.draw_networkx_nodes(self.graph, pos, nodelist=nodes, node_size=size, node_color=color)
        nx.draw_networkx_edges(self.graph, pos, node_size=self.default_size)
        nx.draw_networkx_labels(self.graph, pos, self.labels)
        plt.show()

    def export_graphml(self, path: Union[str, Path]) -> None:
        self._clean_graph()
        if isinstance(path, str):
            path = Path(path)
        path.parent.mkdir(exist_ok=True)
        nx.write_graphml(self.graph, path)

    def visualize_in_out(
        self,
        *,
        node_size: int = 700,
        figsize: Tuple[float, float] = (10, 8),
        in_color: NodeColor = 'green',
        out_color: NodeColor = 'red',
        default_color: NodeColor = 'lightblue',
    ) -> None:
        for node in self.graph.nodes:
            ntype: str = self.graph.nodes[node]['ntype_info']  # type: ignore[misc]
            if ntype == 'input':
                self.format_node(node, node_color=in_color, node_size=node_size)
            elif ntype == 'output':
                self.format_node(node, node_color=out_color, node_size=node_size)
            else:
                self.format_node(node, node_color=default_color, node_size=node_size)

        self.visualize(figsize)
