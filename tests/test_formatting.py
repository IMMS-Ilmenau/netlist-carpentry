import os

import pytest

from netlist_carpentry.core.exceptions import ObjectNotFoundError
from netlist_carpentry.core.graph.visualization.formatting import Format


@pytest.fixture()
def formatting() -> Format:
    return Format()


def test_set_labels_default(formatting: Format) -> None:
    from utils import connected_module

    assert 'labels' in formatting.format_dict
    graph = connected_module().graph()
    format_dict = formatting.set_labels_default(graph)
    assert format_dict == formatting.format_dict['labels']
    for node in graph.nodes:
        assert node in format_dict
        if graph.node_subtype(node) == 'input' or graph.node_subtype(node) == 'output':
            assert format_dict[node] == node
        else:
            assert format_dict[node] == graph.node_subtype(node)


def test_set_format(formatting: Format) -> None:
    format_dict = formatting.set_format('format1', node_color='black')
    assert formatting.format_dict == format_dict
    assert format_dict['formats']['format1']['color'] == 'black'
    assert 'size' not in format_dict['formats']['format1']

    format_dict = formatting.set_format('format1', node_size=300)
    assert formatting.format_dict == format_dict
    assert format_dict['formats']['format1']['size'] == 300
    assert 'color' not in format_dict['formats']['format1']


def test_format_node(formatting: Format) -> None:
    formatting.set_format('format1', node_color='white', node_size=500)
    formatting.format_node('in1', 'format1')
    assert formatting.format_dict['formats']['format1'] == {'color': 'white', 'size': 500}
    assert formatting.format_dict['node_formats'] == {'in1': 'format1'}

    formatting.set_format('format2', node_color='white')
    formatting.format_node('in1', 'format2')
    assert formatting.format_dict['formats']['format2'] == {'color': 'white'}
    assert formatting.format_dict['node_formats'] == {'in1': 'format2'}
    formatting.set_format('format2')
    formatting.format_node('in3', 'format2')
    assert formatting.format_dict['formats']['format2'] == {}
    assert formatting.format_dict['node_formats'] == {'in1': 'format2', 'in3': 'format2'}

    with pytest.raises(ObjectNotFoundError):
        formatting.format_node('some_node', 'nonexisting_format')


def test_format_nodes(formatting: Format) -> None:
    from utils import connected_module

    graph = connected_module().graph()
    formatting.set_format('format1', node_color='black', node_size=700)
    formatting.format_nodes(graph, lambda n, d: d.get('nsubtype') == 'input', format_name='format1')
    for n in graph.nodes:
        if graph.node_subtype(n) == 'input':
            assert formatting.format_dict['node_formats'][n] == 'format1'
        else:
            assert n not in formatting.format_dict['node_formats']


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
