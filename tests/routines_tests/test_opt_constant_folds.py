import os

import pytest

from netlist_carpentry import LOG, read
from netlist_carpentry.core.circuit import Circuit
from netlist_carpentry.core.enums.direction import Direction
from netlist_carpentry.core.enums.signal import Signal
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.io.write.py2v import P2VTransformer as P2V
from netlist_carpentry.routines import opt_constant
from netlist_carpentry.routines.opt.constant_folds import opt_constant_mux_inputs, opt_constant_propagation
from netlist_carpentry.utils.gate_factory import dlatch
from netlist_carpentry.utils.gate_lib import ADFFE
from tests.utils import save_results


@pytest.fixture()
def mux() -> Circuit:
    return read('tests/files/decentral_mux.v')


@pytest.fixture()
def module() -> Module:
    from tests.utils import connected_module

    return connected_module()


def test_opt_constant(mux: Circuit) -> None:
    m = mux.first
    assert len(m.instances) == 96
    assert len(m.wires) == 67
    is_changed = opt_constant(m)
    save_results(P2V().module2v(m), 'v')
    assert is_changed
    assert len(m.instances) == 48
    assert '§mux' not in m.instances_by_types
    assert len(m.wires) == 66  # Removed "wire [31:0] i"

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
    assert len(module.instances) == 0
    assert len(module.wires) == 7
    module.optimize()
    assert len(module.instances) == 0
    assert len(module.wires) == 0
    assert module.ports['out_ff'][0].raw_ws_path == '1'
    assert module.ports['out_ff'][0].signal is Signal.HIGH
    assert module.ports['out'][0].raw_ws_path == '0'
    assert module.ports['out'][0].signal is Signal.LOW


def test_opt_constant_propagation_dff_rst(module: Module) -> None:
    dff: ADFFE = module.instances['dff_inst']
    module.disconnect(dff.rst_port)
    dff.rst_port.tie_signal(0)
    assert dff.in_reset
    assert opt_constant_propagation(module)
    assert 'dff_inst' not in module.instances
    assert 'out_ff' not in module.wires
    assert module.ports['out_ff'].is_connected
    assert module.ports['out_ff'].is_tied_defined
    assert module.ports['out_ff'].signal_array == dff.rst_val


def test_opt_constant_propagation_dff_rst_no_cp(module: Module) -> None:
    dff: ADFFE = module.instances['dff_inst']
    module.disconnect(dff.rst_port)
    dff.rst_port.tie_signal(1)
    assert not dff.in_reset
    assert not opt_constant_propagation(module)
    assert 'dff_inst' in module.instances
    assert 'out_ff' in module.wires


def test_opt_constant_propagation_dff_en_clk(module: Module) -> None:
    dff: ADFFE = module.instances['dff_inst']
    module.disconnect(dff.en_port)
    warns = LOG.warns_quantity
    dff.en_port.tie_signal(0)
    assert not opt_constant_propagation(module)
    assert LOG.warns_quantity == warns + 1
    dff.en_port.tie_signal(1)
    assert not opt_constant_propagation(module)
    assert LOG.warns_quantity == warns + 1

    module.disconnect(dff.clk_port)
    assert not opt_constant_propagation(module)
    assert LOG.warns_quantity == warns + 2


def test_opt_constant_propagation_dff_d(module: Module) -> None:
    dff: ADFFE = module.instances['dff_inst']
    module.disconnect(dff.ports['D'])
    dff.ports['D'].tie_signal(1)
    assert opt_constant_propagation(module)
    assert 'dff_inst' not in module.instances
    assert 'out_ff' not in module.wires
    assert module.ports['out_ff'].is_connected
    assert module.ports['out_ff'].is_tied_defined
    assert module.ports['out_ff'].signal_array == {0: Signal.HIGH}


def test_opt_constant_propagation_dlatch() -> None:
    module = Module(raw_path='testModule1')
    en = module.create_port('EN', Direction.IN)
    d = module.create_port('D', Direction.IN)
    q = module.create_port('Q', Direction.OUT)

    dl = dlatch(module, 'DLatch', Q=q, D=d)
    dl.tie_port('EN', 0, 0)
    assert opt_constant_propagation(module)
    assert module.ports['Q'].driver() == {0: None}
    assert module.ports['Q'].signal is Signal.FLOATING
    assert module.ports['Q'].signal_array == {0: Signal.FLOATING}
    assert 'DLatch' not in module.instances

    module.disconnect(q)
    dl = dlatch(module, 'DLatch', Q=q, D=d)
    dl.tie_port('EN', 0, 1)
    assert opt_constant_propagation(module)
    assert module.ports['Q'].driver() == {0: module.ports['D'][0]}
    assert 'DLatch' not in module.instances

    module.disconnect(q)
    dl = dlatch(module, 'DLatch', Q=q, D=d, EN=en)
    assert not opt_constant_propagation(module)


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
