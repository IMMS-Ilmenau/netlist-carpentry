import os

import pytest
from dash import Dash

from netlist_carpentry.core.graph.module_graph import ModuleGraph
from netlist_carpentry.core.graph.visualization.cytoscape import CytoscapeGraph as CW
from netlist_carpentry.core.graph.visualization.formatting import Format


@pytest.fixture()
def graph() -> ModuleGraph:
    from utils import dff_module

    return dff_module().graph()


def test_get_cytoscape_graph(graph: ModuleGraph) -> None:
    format = Format()
    cw = CW(graph, format)
    cy_graph = cw.get_cytoscape_graph()

    assert len(cy_graph) == 7
    assert cy_graph == [
        {'data': {'id': 'dff_inst', 'label': 'dff_inst', 'object_type': 'INSTANCE', 'object_subtype': '§dff'}},
        {'data': {'id': 'D', 'label': 'D', 'object_type': 'PORT', 'object_subtype': 'input'}},
        {'data': {'id': 'CLK', 'label': 'CLK', 'object_type': 'PORT', 'object_subtype': 'input'}},
        {'data': {'id': 'Q', 'label': 'Q', 'object_type': 'PORT', 'object_subtype': 'output'}},
        {'data': {'label': 'Q->Q', 'source': 'dff_inst', 'target': 'Q'}},
        {'data': {'label': 'D->D', 'source': 'D', 'target': 'dff_inst'}},
        {'data': {'label': 'CLK->CLK', 'source': 'CLK', 'target': 'dff_inst'}},
    ]

    format.format_dict['node_formats'] = {'dff_inst': 'f1', 'D': 'f2', 'Q': 'f3'}
    cy_graph = cw.get_cytoscape_graph()

    assert len(cy_graph) == 7
    assert cy_graph == [
        {'data': {'id': 'dff_inst', 'label': 'dff_inst', 'object_type': 'INSTANCE', 'object_subtype': '§dff'}, 'classes': 'f1'},
        {'data': {'id': 'D', 'label': 'D', 'object_type': 'PORT', 'object_subtype': 'input'}, 'classes': 'f2'},
        {'data': {'id': 'CLK', 'label': 'CLK', 'object_type': 'PORT', 'object_subtype': 'input'}},
        {'data': {'id': 'Q', 'label': 'Q', 'object_type': 'PORT', 'object_subtype': 'output'}, 'classes': 'f3'},
        {'data': {'label': 'Q->Q', 'source': 'dff_inst', 'target': 'Q'}},
        {'data': {'label': 'D->D', 'source': 'D', 'target': 'dff_inst'}},
        {'data': {'label': 'CLK->CLK', 'source': 'CLK', 'target': 'dff_inst'}},
    ]


def test_cw_init_stylesheet() -> None:
    format = Format()
    cw = CW(None, format)
    stylesheets = cw._init_stylesheet()
    assert stylesheets == cw.stylesheet
    assert len(stylesheets) == 2
    assert stylesheets[0] == {'selector': 'node', 'style': {}}
    assert stylesheets[1] == {'selector': 'edge', 'style': {'curve-style': 'bezier', 'target-arrow-shape': 'triangle'}}

    format.format_dict['formats'] = {}
    format.format_dict['formats']['f1'] = {'color': 'black', 'size': 30}
    format.format_dict['formats']['f2'] = {'color': 'white'}
    format.format_dict['formats']['f3'] = {'size': 300}
    stylesheets = cw._init_stylesheet()
    assert len(stylesheets) == 5
    assert stylesheets[0] == {'selector': 'node', 'style': {}}
    assert stylesheets[1] == {'selector': '.f1', 'style': {'background-color': 'black', 'width': '3.0px', 'height': '3.0px'}}
    assert stylesheets[2] == {'selector': '.f2', 'style': {'background-color': 'white'}}
    assert stylesheets[3] == {'selector': '.f3', 'style': {'width': '30.0px', 'height': '30.0px'}}
    assert stylesheets[4] == {'selector': 'edge', 'style': {'curve-style': 'bezier', 'target-arrow-shape': 'triangle'}}


def test_cw_update_stylesheet(graph: ModuleGraph) -> None:
    format = Format()
    cw = CW(graph, format)
    assert len(cw.stylesheet) == 2
    cw.update_stylesheet()
    assert len(cw.stylesheet) == 5  # Now the selectors for the labels as well


def test_show(graph: ModuleGraph) -> None:
    cw = CW(graph)
    with pytest.raises(ValueError):
        cw.show(port='invalid')


def test_register_callbacks(graph: ModuleGraph) -> None:
    cw = CW(graph)
    cw.register_callbacks(Dash())


def test_cw_get_dash_graph(graph: ModuleGraph) -> None:
    cw = CW(graph, Format())
    dash = cw.get_dash_graph()
    children = dash.layout.children
    assert len(children) == 3
    assert children[0].id == 'clicked-nodes-store'
    assert children[1].id == 'clicked-edges-store'
    assert children[2].children[0].id == 'circuit-graph'
    assert children[2].children[0].elements == [
        {'data': {'id': 'dff_inst', 'label': 'dff_inst', 'object_type': 'INSTANCE', 'object_subtype': '§dff'}},
        {'data': {'id': 'D', 'label': 'D', 'object_type': 'PORT', 'object_subtype': 'input'}},
        {'data': {'id': 'CLK', 'label': 'CLK', 'object_type': 'PORT', 'object_subtype': 'input'}},
        {'data': {'id': 'Q', 'label': 'Q', 'object_type': 'PORT', 'object_subtype': 'output'}},
        {'data': {'label': 'Q->Q', 'source': 'dff_inst', 'target': 'Q'}},
        {'data': {'label': 'D->D', 'source': 'D', 'target': 'dff_inst'}},
        {'data': {'label': 'CLK->CLK', 'source': 'CLK', 'target': 'dff_inst'}},
    ]
    assert children[2].children[0].layout == {'name': 'klay', 'directed': True}
    assert children[2].children[0].style == {'width': '100%', 'height': '550px', 'background-color': 'black'}

    dash = cw.get_dash_graph(style={'abc': 'def', 'foo': 'bar'})
    assert dash.layout.children[2].children[0].style == {'abc': 'def', 'foo': 'bar'}
    assert children[2].children[1].id == 'cytoscape-mouseoverNodeData-output'
    assert children[2].children[2].id == 'cytoscape-mouseoverEdgeData-output'


def test_toggle_node_label(graph: ModuleGraph) -> None:
    format = Format()
    cw = CW(graph, format)
    assert cw._shown_nodes == []
    assert cw._shown_node_types == []
    cw._toggle_node_label({'id': 'a'}, [])
    assert cw._shown_nodes == ['a']
    assert cw._shown_node_types == []
    cw._toggle_node_label({'id': 'b'}, [])
    assert cw._shown_nodes == ['a', 'b']
    assert cw._shown_node_types == []
    cw._toggle_node_label({'id': 'a'}, [])
    assert cw._shown_nodes == ['b']
    assert cw._shown_node_types == ['a']
    cw._toggle_node_label({'id': 'c'}, [])
    assert cw._shown_nodes == ['b', 'c']
    assert cw._shown_node_types == ['a']
    cw._toggle_node_label({'id': 'c'}, [])
    assert cw._shown_nodes == ['b']
    assert cw._shown_node_types == ['a', 'c']
    cw._toggle_node_label({'id': 'c'}, [])
    assert cw._shown_nodes == ['b']
    assert cw._shown_node_types == ['a']


def test_toggle_edge_label(graph: ModuleGraph) -> None:
    format = Format()
    cw = CW(graph, format)
    assert cw._shown_edges == []
    cw._toggle_edge_label({'id': 'a'}, [])
    assert cw._shown_edges == ['a']
    cw._toggle_edge_label({'id': 'b'}, [])
    assert cw._shown_edges == ['a', 'b']
    cw._toggle_edge_label({'id': 'a'}, [])
    assert cw._shown_edges == ['b']


def test_display_hover_node_data(graph: ModuleGraph) -> None:
    cw = CW(graph)
    created_str = cw._display_hover_node_data({})
    target_str = ''
    assert created_str == target_str

    created_str = cw._display_hover_node_data({'id': 'dff_inst', 'object_type': 'INSTANCE', 'object_subtype': '§dff'})
    target_str = "Hovered over Node 'dff_inst': Instance of type §dff"
    assert created_str == target_str


def test_display_hover_edge_data(graph: ModuleGraph) -> None:
    cw = CW(graph)
    created_str = cw._display_hover_edge_data({})
    target_str = ''
    assert created_str == target_str

    created_str = cw._display_hover_edge_data({'source': 'dff_inst', 'target': 'Q', 'label': 'Q->Q'})
    target_str = 'Hovered over net from port Q of instance dff_inst (type §dff) to module port Q'
    assert created_str == target_str

    created_str = cw._display_hover_edge_data({'source': 'D', 'target': 'dff_inst', 'label': 'D->D'})
    target_str = 'Hovered over net from module port D to port D of instance dff_inst (type §dff)'
    assert created_str == target_str


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
