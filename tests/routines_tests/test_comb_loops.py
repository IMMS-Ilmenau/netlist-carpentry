import os

import pytest

from netlist_carpentry import Module
from netlist_carpentry.core.circuit import Circuit
from netlist_carpentry.routines import find_comb_loops, has_comb_loops
from netlist_carpentry.routines.check.comb_loops import combinational_subgraph, module_find_comb_loops
from netlist_carpentry.utils.gate_factory import and_gate, dff


@pytest.fixture()
def connected_module() -> Module:
    from utils import connected_module

    return connected_module()


@pytest.fixture()
def comb_loop_module() -> Module:
    from utils import comb_loop_module

    return comb_loop_module()


@pytest.fixture()
def connected_circuit() -> Circuit:
    from utils import connected_circuit

    return connected_circuit()


@pytest.fixture()
def comb_loop_circuit() -> Circuit:
    from utils import comb_loop_circuit

    return comb_loop_circuit()


def test_has_comb_loops(comb_loop_module: Module, connected_module: Module) -> None:
    assert not has_comb_loops(connected_module)
    assert has_comb_loops(comb_loop_module)
    comb_loop_module.remove_instance(comb_loop_module.instances['not_inst5'])
    comb_loop_module.disconnect(comb_loop_module.instances['not_inst6'].ports['A'])  # Remove the corresponding wire
    assert not has_comb_loops(comb_loop_module)
    and_inst2 = and_gate(
        comb_loop_module, 'and_inst2', A=comb_loop_module.instances['not_inst4'].ports['Y'], Y=comb_loop_module.instances['not_inst6'].ports['A']
    )
    assert has_comb_loops(comb_loop_module)
    comb_loop_module.remove_instance(and_inst2)
    comb_loop_module.disconnect(comb_loop_module.instances['not_inst6'].ports['A'])  # Remove the corresponding wire
    dff(comb_loop_module, 'dff_inst2', D=comb_loop_module.instances['not_inst4'].ports['Y'], Q=comb_loop_module.instances['not_inst6'].ports['A'])
    assert not has_comb_loops(comb_loop_module)


def test_has_comb_loops_circuit(comb_loop_circuit: Circuit, connected_circuit: Circuit) -> None:
    assert not has_comb_loops(connected_circuit)
    assert has_comb_loops(comb_loop_circuit)
    comb_loop_module = comb_loop_circuit['test_module1']
    comb_loop_module.remove_instance(comb_loop_module.instances['not_inst5'])
    comb_loop_module.disconnect(comb_loop_module.instances['not_inst6'].ports['A'])  # Remove the corresponding wire
    assert not has_comb_loops(comb_loop_circuit)
    and_inst2 = and_gate(
        comb_loop_module, 'and_inst2', A=comb_loop_module.instances['not_inst4'].ports['Y'], Y=comb_loop_module.instances['not_inst6'].ports['A']
    )
    assert has_comb_loops(comb_loop_circuit)
    comb_loop_module.remove_instance(and_inst2)
    comb_loop_module.disconnect(comb_loop_module.instances['not_inst6'].ports['A'])  # Remove the corresponding wire
    dff(comb_loop_module, 'dff_inst2', D=comb_loop_module.instances['not_inst4'].ports['Y'], Q=comb_loop_module.instances['not_inst6'].ports['A'])
    assert not has_comb_loops(comb_loop_circuit)


def test_module_find_comb_loops(comb_loop_module: Module, connected_module: Module) -> None:
    loop = module_find_comb_loops(comb_loop_module)
    assert len(loop) == 1
    assert len(loop[0]) == 12
    assert 'or_inst' in loop[0]
    assert 'xor_inst' in loop[0]
    for i in range(10):
        assert f'not_inst{i}' in loop[0]

    no_loop = module_find_comb_loops(connected_module)
    assert len(no_loop) == 0


def test_find_comb_loops_circuit(comb_loop_circuit: Circuit, connected_circuit: Circuit) -> None:
    loop_dict = find_comb_loops(comb_loop_circuit)
    assert 'test_module1' in loop_dict
    loop = loop_dict['test_module1']
    assert len(loop) == 1
    assert len(loop[0]) == 12
    assert 'or_inst' in loop[0]
    assert 'xor_inst' in loop[0]
    for i in range(10):
        assert f'not_inst{i}' in loop[0]

    assert 'wrapper' in loop_dict
    no_loop = loop_dict['wrapper']
    assert len(no_loop) == 0

    no_loop_dict = find_comb_loops(connected_circuit)
    assert 'test_module1' in no_loop_dict
    no_loop = no_loop_dict['test_module1']
    assert len(no_loop) == 0


def test_combinational_subgraph(comb_loop_module: Module) -> None:
    normal_graph = comb_loop_module.graph()
    subgraph = combinational_subgraph(comb_loop_module)
    assert len(normal_graph.nodes) == 23
    assert len(subgraph.nodes) == 22
    assert 'dff_inst' in normal_graph.nodes
    assert 'dff_inst' not in subgraph.nodes


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
