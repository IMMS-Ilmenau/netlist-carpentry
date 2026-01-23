"""A wrapper module for Dash Cytoscape, handling the creation of cytoscape graph objects."""
# mypy: disable-error-code="no-any-unimported, misc"

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import dash_cytoscape as cyto
from dash import Dash, Input, Output, State, dcc, html
from dash.development.base_component import Component
from pydantic import PositiveInt

from netlist_carpentry import CFG
from netlist_carpentry.core.graph.module_graph import ModuleGraph
from netlist_carpentry.core.graph.visualization.formatting import Format
from netlist_carpentry.core.graph.visualization.formatting_types import CytoscapeGraphDict, StyleDict, StylesheetDict
from netlist_carpentry.core.graph.visualization.visualization_base import VisualizationBase


class CytoscapeGraph(VisualizationBase):
    def __init__(
        self, graph: ModuleGraph, format: Optional[Format] = None, default_color: str = 'lightblue', default_size: PositiveInt = 300
    ) -> None:
        super().__init__(graph, format, default_color, default_size)
        self._shown_nodes: List[str] = []
        self._shown_node_types: List[str] = []
        self._shown_edges: List[str] = []
        self.stylesheet: List[StylesheetDict] = self._init_stylesheet()

    def get_cytoscape_graph(self) -> List[CytoscapeGraphDict]:
        data: List[CytoscapeGraphDict] = []
        for n in self.graph.nodes:
            object_type = self.graph.node_type(n)
            object_subtype = self.graph.node_subtype(n)
            n_data: CytoscapeGraphDict = {'data': {'id': n, 'label': n, 'object_type': object_type, 'object_subtype': object_subtype}}
            if 'node_formats' in self.format_dict and n in self.format_dict['node_formats']:
                n_data['classes'] = self.format_dict['node_formats'][n]
            data.append(n_data)
        for s, t, u in self.graph.edges:
            u = '' if not isinstance(u, str) else u
            e_data: CytoscapeGraphDict = {'data': {'source': s, 'target': t, 'label': u.replace(CFG.id_internal, '->')}}
            data.append(e_data)
        return data

    def _init_stylesheet(self) -> List[StylesheetDict]:
        stylesheet = []
        node_dict: StylesheetDict = {'selector': 'node', 'style': {}}
        stylesheet.append(node_dict)
        if 'formats' in self.format_dict:
            formats = self.format_dict['formats']
            for format_name in formats:
                curr_format = formats[format_name]
                fdict: StylesheetDict = {'selector': f'.{format_name}', 'style': {}}
                if 'color' in curr_format:
                    fdict['style']['background-color'] = curr_format['color']
                if 'size' in curr_format:
                    fdict['style']['height'] = str(curr_format['size'] / 10) + 'px'
                    fdict['style']['width'] = str(curr_format['size'] / 10) + 'px'
                stylesheet.append(fdict)
        edge_dict: StylesheetDict = {'selector': 'edge', 'style': {'curve-style': 'bezier', 'target-arrow-shape': 'triangle'}}
        stylesheet.append(edge_dict)
        return stylesheet

    def update_stylesheet(self) -> List[StylesheetDict]:
        stylesheet = self._init_stylesheet()
        stylesheet.append(
            {
                'selector': ', '.join([f"node[id='{eid}']" for eid in self._shown_nodes]),
                'style': {
                    'color': 'white',
                    'content': 'data(label)',  # Show the label data
                    'font-size': '14px',
                    'text-valign': 'center',
                    'text-halign': 'center',
                },
            }
        )
        stylesheet.append(
            {
                'selector': ', '.join([f"node[id='{eid}']" for eid in self._shown_node_types]),
                'style': {
                    'color': 'white',
                    'content': 'data(object_subtype)',  # Show the label data
                    'font-size': '14px',
                    'font-style': 'italic',
                    'text-valign': 'center',
                    'text-halign': 'center',
                },
            }
        )
        stylesheet.append(
            {
                'selector': ', '.join([f"edge[id='{eid}']" for eid in self._shown_edges]),
                'style': {
                    'color': 'white',
                    'label': 'data(label)',  # Show the label
                    'text-background-color': 'black',
                    'text-background-opacity': 1,
                    'text-background-padding': '3px',
                },
            }
        )
        self.stylesheet = stylesheet
        return stylesheet

    def get_dash_graph(self, style: Optional[Dict[str, str]] = None, **fwd_params: Optional[Dict[str, object]]) -> Dash:
        if style is None:
            style = {'width': '100%', 'height': '550px', 'background-color': 'black'}
        app = Dash()

        cyto.load_extra_layouts()
        elements = self.get_cytoscape_graph()
        stylesheet = self._init_stylesheet()
        text_style: StyleDict = {'background-color': 'black', 'color': 'white'}
        children: List[Component] = [
            dcc.Store(id='clicked-nodes-store', data=[]),
            dcc.Store(id='clicked-edges-store', data=[]),
            html.Div(
                [
                    cyto.Cytoscape(
                        id='circuit-graph',
                        layout={'name': 'klay', 'directed': True},
                        style=style,
                        elements=elements,
                        stylesheet=stylesheet,
                    ),
                    html.P(id='cytoscape-mouseoverNodeData-output', style=text_style),
                    html.P(id='cytoscape-mouseoverEdgeData-output', style=text_style),
                ],
                style=text_style,
            ),
        ]
        app.layout = html.Div(children)
        self.register_callbacks(app)
        return app

    def show(self, **kwargs: object) -> None:
        style: Optional[Dict[str, str]] = kwargs.pop('style', None)  # type:ignore[assignment]
        app = self.get_dash_graph(style=style)
        app.run(**kwargs)  # type: ignore[arg-type]

    def register_callbacks(self, app: Dash) -> None:
        """Registers callback methods for the Dash app to react to user input.

        Registers a bunch of methods that react to edge/node tapping and hovering,
        and handling the corresponding tasks.

        Args:
            app (Dash): The Dash app where the callback should be registered.
        """

        # Callback to handle the toggle logic
        @app.callback(
            [Output('circuit-graph', 'stylesheet', allow_duplicate=True), Output('clicked-nodes-store', 'data')],
            Input('circuit-graph', 'tapNodeData'),
            State('clicked-nodes-store', 'data'),
            prevent_initial_call=True,
        )
        def toggle_node_label(node_data: Dict[str, str], active_ids: Optional[List[str]]) -> Tuple[List[StylesheetDict], List[str]]:
            return self._toggle_node_label(node_data, active_ids)

        @app.callback(
            [Output('circuit-graph', 'stylesheet', allow_duplicate=True), Output('clicked-edges-store', 'data')],
            Input('circuit-graph', 'tapEdgeData'),
            State('clicked-edges-store', 'data'),
            prevent_initial_call=True,
        )
        def toggle_edge_label(edge_data: Dict[str, str], visible_ids: Optional[List[str]]) -> Tuple[List[StylesheetDict], List[str]]:
            return self._toggle_edge_label(edge_data, visible_ids)

        @app.callback(Output('cytoscape-mouseoverNodeData-output', 'children'), Input('circuit-graph', 'mouseoverNodeData'))
        def displayHoverNodeData(data: Dict[str, str]) -> str:
            return self._display_hover_node_data(data)

        @app.callback(Output('cytoscape-mouseoverEdgeData-output', 'children'), Input('circuit-graph', 'mouseoverEdgeData'))
        def displayHoverEdgeData(data: Dict[str, str]) -> str:
            return self._display_hover_edge_data(data)

    def _toggle_node_label(self, node_data: Dict[str, str], active_ids: Optional[List[str]]) -> Tuple[List[StylesheetDict], List[str]]:
        """Toggles the visibility of a node label when the node is clicked."""
        clicked_id = node_data.get('id', '')
        if clicked_id in self._shown_nodes:
            self._shown_nodes.remove(clicked_id)  # Hide label if already showing
            self._shown_node_types.append(clicked_id)
        elif clicked_id in self._shown_node_types:
            self._shown_node_types.remove(clicked_id)
        else:
            self._shown_nodes.append(clicked_id)  # Show label if hidden
        return self.update_stylesheet(), self._shown_nodes

    def _toggle_edge_label(self, edge_data: Dict[str, str], visible_ids: Optional[List[str]]) -> Tuple[List[StylesheetDict], List[str]]:
        """Toggles the visibility of an edge label when the edge is clicked."""
        clicked_id = edge_data.get('id', '')
        if clicked_id in self._shown_edges:
            self._shown_edges.remove(clicked_id)  # Hide it
        else:
            self._shown_edges.append(clicked_id)  # Show it
        return self.update_stylesheet(), self._shown_edges

    def _display_hover_node_data(self, data: Dict[str, str]) -> str:
        if data:
            return f"Hovered over Node '{data['id']}': {data['object_type'].capitalize()} of type {data['object_subtype']}"
        return ''

    def _display_hover_edge_data(self, data: Dict[str, str]) -> str:
        if data:
            start_node = data['source']
            end_node = data['target']
            start_port = data['label'].split('->')[0]
            end_port = data['label'].split('->')[1]
            if self.graph.node_type(start_node) == 'INSTANCE':
                start = f'port {start_port} of instance {start_node} (type {self.graph.node_subtype(start_node)})'
            else:
                start = f'module port {start_node}'
            if self.graph.node_type(end_node) == 'INSTANCE':
                end = f'port {end_port} of instance {end_node} (type {self.graph.node_subtype(end_node)})'
            else:
                end = f'module port {end_node}'
            return 'Hovered over net from ' + start + ' to ' + end
        return ''
