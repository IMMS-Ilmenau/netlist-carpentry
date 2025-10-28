import os

import pytest

from netlist_carpentry import CFG, read
from netlist_carpentry.core.circuit import Circuit
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.opt.constant_folds import opt_constant, opt_constant_mux_inputs, opt_constant_propagation
from netlist_carpentry.core.signal import Signal


@pytest.fixture()
def mux() -> Circuit:
    CFG.simplify_escaped_identifiers = True
    return read('tests/files/decentral_mux.v')


@pytest.fixture
def module() -> Module:
    from tests.utils import connected_module

    return connected_module()


def test_opt_constant(mux: Circuit) -> None:
    m = mux.first
    assert len(m.instances) == 96
    assert len(m.wires) == 67
    is_changed = opt_constant(m)
    assert is_changed
    assert len(m.instances) == 80
    assert '§mux' not in m.instances_by_types
    assert len(m.wires) == 67

    is_changed = opt_constant(m)
    assert not is_changed


def test_opt_constant_mux_inputs(mux: Circuit) -> None:
    m = mux.first
    assert len(m.instances) == 96
    assert len(m.wires) == 67
    is_changed = opt_constant_mux_inputs(m)
    assert is_changed
    assert len(m.instances) == 80
    assert '§mux' not in m.instances_by_types
    assert len(m.wires) == 67

    is_changed = opt_constant_mux_inputs(m)
    assert not is_changed


def test_opt_constant_propagation(module: Module) -> None:
    assert len(module.instances) == 5
    assert len(module.wires) == 12
    assert not opt_constant_propagation(module)
    assert len(module.instances) == 5
    assert len(module.wires) == 12

    module.disconnect(module.instances['and_inst'].ports['A'][0])
    module.disconnect(module.instances['and_inst'].ports['B'][0])
    module.instances['and_inst'].ports['A'].tie_signal('0', 0)
    module.instances['and_inst'].ports['B'].tie_signal('1', 0)
    assert opt_constant_propagation(module)
    assert len(module.instances) == 4
    assert len(module.wires) == 11
    assert module.instances['xor_inst'].ports['A'][0].raw_ws_path == '0'

    module.disconnect(module.instances['or_inst'].ports['A'][0])
    module.disconnect(module.instances['or_inst'].ports['B'][0])
    module.instances['or_inst'].ports['A'].tie_signal('0', 0)
    module.instances['or_inst'].ports['B'].tie_signal('1', 0)
    assert opt_constant_propagation(module)
    assert len(module.instances) == 1
    assert len(module.wires) == 8
    module.optimize()
    assert len(module.instances) == 1
    assert len(module.wires) == 3
    assert module.instances['dff_inst'].ports['D'][0].raw_ws_path == '1'
    assert module.instances['dff_inst'].ports['D'][0].signal is Signal.HIGH
    assert module.ports['out'][0].raw_ws_path == '0'
    assert module.ports['out'][0].signal is Signal.LOW


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
