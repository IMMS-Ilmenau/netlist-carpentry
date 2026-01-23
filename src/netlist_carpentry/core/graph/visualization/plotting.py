"""Module for graph visualization via plotting (WIP)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.figure import Figure
from pydantic import PositiveInt

from netlist_carpentry.core.graph.visualization.visualization_base import VisualizationBase


class Plotting(VisualizationBase):
    def _clean_graph(self) -> None:
        """
        The module graph by default contains additional node data (i.e. the Python object itself),
        which cannot be exported, so it must be removed first.
        This is done here by removing the `ndata` attribute completely.
        """
        for node in self.graph.nodes:
            if 'ndata' in self.graph.nodes[node]:  # type: ignore[misc]
                self.graph.nodes[node].pop('ndata')  # type: ignore[misc]

    def build_figure(self, figsize: Tuple[float, float] = (10, 8)) -> Figure:
        """Create a matplotlib Figure of the graph with the current formatting rules.

        Args:
            figsize (Tuple[float, float], optional): The size of the figure in inches. Defaults to (10, 8).

        Returns:
            Figure: The created figure.
        """
        self._clean_graph()
        pos = nx.kamada_kawai_layout(self.graph)

        f = plt.figure(figsize=figsize)
        for n in self.graph.nodes:
            nodes, size, color = self._show_single(n)
            nx.draw_networkx_nodes(self.graph, pos, nodelist=nodes, node_size=size, node_color=color)
        nx.draw_networkx_edges(self.graph, pos, node_size=self.default_size)
        nx.draw_networkx_labels(self.graph, pos, self.format_dict['labels'])
        return f

    def show(self, figsize: Tuple[float, float] = (10, 8), figpath: Optional[str] = None, **kwargs: object) -> None:  # type: ignore[override]
        self.build_figure(figsize=figsize)
        if figpath is None:
            plt.show()
        else:
            plt.savefig(figpath)

    def _show_single(self, n: str) -> Tuple[List[str], PositiveInt, str]:
        if n in self.format_dict['node_formats']:
            format_name = self.format_dict['node_formats'][n]
            color = self.format_dict['formats'][format_name].get('color', self.default_color)
            size = self.format_dict['formats'][format_name].get('size', self.default_size)
        else:
            color = self.default_color
            size = self.default_size
        nodes = [n]
        return (nodes, size, color)

    def export_graphml(self, path: Union[str, Path]) -> None:
        """Export the graph in graphml format to display e.g using Gephy.

        Args:
            path (Union[str, Path]): The path where the graph should be saved.
        """
        self._clean_graph()
        if isinstance(path, str):
            path = Path(path)
        path.parent.mkdir(exist_ok=True)
        nx.write_graphml(self.graph, path)
