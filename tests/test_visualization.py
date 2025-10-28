from __future__ import annotations

import os
from pathlib import Path

import pytest
from networkx import MultiDiGraph

from netlist_carpentry.core.graph.visualization import Visualization


@pytest.fixture
def graph() -> MultiDiGraph[str]:
    from utils import connected_module

    return connected_module().graph()


def test_format_node(graph: MultiDiGraph[str]) -> None:
    v = Visualization(graph)
    assert v.format_dict['in1'] == ('lightblue', 300)
    v.format_node('in1', node_color='black', node_size=700)
    assert v.format_dict['in1'] == ('black', 700)
    v.format_node('in2', node_color='black')
    assert v.format_dict['in2'] == ('black', 300)
    v.format_node('in3', node_size=700)
    assert v.format_dict['in3'] == ('lightblue', 700)

    with pytest.raises(AttributeError):
        v.format_node('nonexisting_node', node_color='black', node_size=700)


def test_format_nodes(graph: MultiDiGraph[str]) -> None:
    v = Visualization(graph)
    v.format_nodes(lambda n, d: d.get('ntype_info') == 'input', node_color='black', node_size=700)
    for n in v.graph.nodes:
        if v.graph.nodes[n]['ntype_info'] == 'input':
            assert v.format_dict[n] == ('black', 700)
        else:
            assert v.format_dict[n] == ('lightblue', 300)


def test_clean_graph(graph: MultiDiGraph[str]) -> None:
    v = Visualization(graph)
    for n in graph.nodes:
        assert 'ndata' in graph.nodes[n]
    v._clean_graph()
    for n in graph.nodes:
        assert 'ndata' not in graph.nodes[n]
    v._clean_graph()  # Multiple runs must not break cleaning function
    for n in graph.nodes:
        assert 'ndata' not in graph.nodes[n]


def test_visualize(graph: MultiDiGraph[str]) -> None:
    v = Visualization(graph, 'black', 700)
    for n in v.graph:
        assert v.format_dict[n] == ('black', 700)
    v.visualize()


def test_export_graphml(graph: MultiDiGraph[str]) -> None:
    v = Visualization(graph)
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


def test_visualize_in_out(graph: MultiDiGraph[str]) -> None:
    v = Visualization(graph)
    v.visualize_in_out()


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
