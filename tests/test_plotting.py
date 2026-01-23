from __future__ import annotations

import os
from pathlib import Path

import pytest
from matplotlib.figure import Figure

from netlist_carpentry.core.exceptions import ObjectNotFoundError
from netlist_carpentry.core.graph.module_graph import ModuleGraph
from netlist_carpentry.core.graph.visualization.plotting import Plotting


@pytest.fixture()
def graph() -> ModuleGraph:
    from utils import connected_module

    return connected_module().graph()


def test_init(graph: ModuleGraph) -> None:
    v = Plotting(graph, default_color='black', default_size=700)

    assert v.default_color == 'black'
    assert v.default_size == 700
    assert v.format_dict['formats'] == {}
    assert v.format_dict['labels'] == {}
    assert v.format_dict['node_formats'] == {}


def test_set_labels_default(graph: ModuleGraph) -> None:
    v = Plotting(graph)
    assert 'labels' in v.format_dict
    format_dict = v.set_labels_default()
    assert format_dict == v.format_dict['labels']
    for node in graph.nodes:
        assert node in format_dict
        if graph.node_subtype(node) == 'input' or graph.node_subtype(node) == 'output':
            assert format_dict[node] == node
        else:
            assert format_dict[node] == graph.node_subtype(node)


def test_set_format(graph: ModuleGraph) -> None:
    v = Plotting(graph)

    format_dict = v.set_format('format1', node_color='black')
    assert v.format_dict == format_dict
    assert format_dict['formats']['format1']['color'] == 'black'
    assert 'size' not in format_dict['formats']['format1']

    format_dict = v.set_format('format1', node_size=300)
    assert v.format_dict == format_dict
    assert format_dict['formats']['format1']['size'] == 300
    assert 'color' not in format_dict['formats']['format1']


def test_format_node(graph: ModuleGraph) -> None:
    v = Plotting(graph)
    with pytest.raises(ObjectNotFoundError):
        v.format_node('in1', 'nonexisting_format')
    v.set_format('format1', node_color='white', node_size=500)
    v.format_node('in1', 'format1')
    assert v.format_dict['formats']['format1'] == {'color': 'white', 'size': 500}
    assert v.format_dict['node_formats'] == {'in1': 'format1'}

    v.set_format('format2', node_color='white')
    v.format_node('in1', 'format2')
    assert v.format_dict['formats']['format2'] == {'color': 'white'}
    assert v.format_dict['node_formats'] == {'in1': 'format2'}
    v.set_format('format2')
    v.format_node('in3', 'format2')
    assert v.format_dict['formats']['format2'] == {}
    assert v.format_dict['node_formats'] == {'in1': 'format2', 'in3': 'format2'}

    with pytest.raises(ObjectNotFoundError):
        v.format_node('nonexisting_node', 'format2')


def test_format_nodes(graph: ModuleGraph) -> None:
    v = Plotting(graph)
    v.set_format('format1', node_color='black', node_size=700)
    v.format_nodes(lambda n, d: d.get('nsubtype') == 'input', format_name='format1')
    for n in v.graph.nodes:
        if v.graph.node_subtype(n) == 'input':
            assert v.format_dict['node_formats'][n] == 'format1'
        else:
            assert n not in v.format_dict['node_formats']


def test_clean_graph(graph: ModuleGraph) -> None:
    v = Plotting(graph)
    for n in graph.nodes:
        assert 'ndata' in graph.nodes[n]
    v._clean_graph()
    for n in graph.nodes:
        assert 'ndata' not in graph.nodes[n]
    v._clean_graph()  # Multiple runs must not break cleaning function
    for n in graph.nodes:
        assert 'ndata' not in graph.nodes[n]


def test_build_figure(graph: ModuleGraph) -> None:
    v = Plotting(graph, default_color='black', default_size=700)
    f = v.build_figure((3, 4))
    assert isinstance(f, Figure)


def test_show(graph: ModuleGraph) -> None:
    v = Plotting(graph, default_color='black', default_size=700)
    v.show(figpath='tests/files/gen/vis.svg')


def test_export_graphml(graph: ModuleGraph) -> None:
    v = Plotting(graph)
    graphml_path = 'tests/files/gen/graph_path.graphml'
    if os.path.exists(graphml_path):
        os.remove(graphml_path)
    v.export_graphml(graphml_path)
    assert os.path.exists(graphml_path)

    graphml_path2 = Path('tests/files/gen/graph_path.graphml')
    if os.path.exists(graphml_path2):
        os.remove(graphml_path2)
    v.export_graphml(graphml_path2)
    assert os.path.exists(graphml_path2)


def test_visualize_in_out(graph: ModuleGraph) -> None:
    v = Plotting(graph)
    prev = v.format_dict
    new = v.format_in_out()
    assert prev == new

    with pytest.raises(ObjectNotFoundError):
        v.format_in_out(in_format='nonexisting_formats')

    v.set_format('green', node_color='green')
    v.set_format('red', node_color='red')
    fdict = v.format_in_out(in_format='green', out_format='red')

    assert fdict == v.format_dict
    for n in graph.nodes:
        if graph.node_subtype(n) == 'input':
            assert fdict['node_formats'][n] == 'green'
        elif graph.node_subtype(n) == 'output':
            assert fdict['node_formats'][n] == 'red'
        else:
            assert n not in fdict['node_formats']


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
