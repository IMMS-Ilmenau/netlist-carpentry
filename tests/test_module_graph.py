import os

import pytest
from networkx import MultiDiGraph

from netlist_carpentry.core.enums.direction import Direction
from netlist_carpentry.core.graph.module_graph import ModuleGraph
from netlist_carpentry.core.netlist_elements.port import Port
from netlist_carpentry.utils.gate_lib import AndGate


@pytest.fixture()
def mgraph() -> ModuleGraph:
    from utils import connected_module

    return connected_module().graph()


def test_module_graph_basics() -> None:
    mg = ModuleGraph()
    assert isinstance(mg, ModuleGraph)
    assert isinstance(mg, MultiDiGraph)


def test_get_data(mgraph: ModuleGraph) -> None:
    with pytest.raises(KeyError):
        mgraph.get_data('non_existent_node', 'ntype')
    with pytest.raises(KeyError):
        mgraph.get_data('in1', 'non_existent_category')

    assert mgraph.get_data('in1', 'ntype') == 'PORT'
    assert mgraph.get_data('in1', 'nsubtype') == 'input'
    assert isinstance(mgraph.get_data('in1', 'ndata'), Port)

    assert mgraph.get_data('and_inst', 'ntype') == 'INSTANCE'
    assert mgraph.get_data('and_inst', 'nsubtype') == '§and'
    assert isinstance(mgraph.get_data('and_inst', 'ndata'), AndGate)


def test_set_data(mgraph: ModuleGraph) -> None:
    with pytest.raises(KeyError):
        mgraph.set_data('non_existent_node', 'ntype', 'PORT')

    mgraph.set_data('and_inst', 'PORT', 'ntype')
    assert mgraph.get_data('and_inst', 'ntype') == 'PORT'
    mgraph.set_data('and_inst', 'input', 'nsubtype')
    assert mgraph.get_data('and_inst', 'nsubtype') == 'input'
    mgraph.set_data('in1', Port(raw_path='a.b.c', direction=Direction.IN, module_or_instance=None), 'ndata')
    assert mgraph.get_data('in1', 'ndata').raw_path == 'a.b.c'

    mgraph.set_data('in1', 'INSTANCE', 'ntype')
    assert mgraph.get_data('in1', 'ntype') == 'INSTANCE'
    mgraph.set_data('in1', '§and', 'nsubtype')
    assert mgraph.get_data('in1', 'nsubtype') == '§and'
    mgraph.set_data('and_inst', AndGate(raw_path='a.b.c'), 'ndata')
    assert mgraph.get_data('and_inst', 'ndata').raw_path == 'a.b.c'


def test_node_type(mgraph: ModuleGraph) -> None:
    type1 = mgraph.node_type('in1')
    assert type1 == 'PORT'
    type2 = mgraph.node_type('dff_inst')
    assert type2 == 'INSTANCE'

    with pytest.raises(KeyError):
        mgraph.node_type('nonexistent_node')


def test_node_subtype(mgraph: ModuleGraph) -> None:
    type1 = mgraph.node_subtype('in1')
    assert type1 == 'input'
    type2 = mgraph.node_subtype('dff_inst')
    assert type2 == '§adffe'

    with pytest.raises(KeyError):
        mgraph.node_subtype('nonexistent_node')


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
