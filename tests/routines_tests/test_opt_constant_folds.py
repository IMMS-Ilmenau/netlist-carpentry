import os

import pytest

from netlist_carpentry import LOG, SignalArray, read
from netlist_carpentry.core.circuit import Circuit
from netlist_carpentry.core.enums.direction import Direction
from netlist_carpentry.core.enums.signal import Signal
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.io.write.py2v import P2VTransformer as P2V
from netlist_carpentry.routines import opt_constant
from netlist_carpentry.routines.opt.constant_folds import opt_constant_mux_inputs, opt_constant_propagation
from netlist_carpentry.utils.gate_factory import dlatch
from netlist_carpentry.utils.gate_lib import ADFFE, AndGate, Multiplexer, NandGate, NorGate, NotGate, OrGate, XnorGate, XorGate
from tests.utils import save_results


def _binary_gate_module(gate_cls: type, const: Signal, const_port: str = 'B') -> Module:
    module = Module(name='m')
    x = module.create_port('x', Direction.IN)
    y = module.create_port('y', Direction.OUT)
    inst = module.create_instance(gate_cls, 'inst')
    free_port = 'A' if const_port == 'B' else 'B'
    module.connect(x, inst.ports[free_port])
    module.connect(inst.ports['Y'], y)
    inst.ports[const_port].tie_signal(const, 0)
    return module


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
    assert len(module.instances) == 3
    assert len(module.wires) == 10
    assert 'xor_inst' not in module.instances  # XOR with constant 0 passes the other input through
    assert module.instances['not_inst'].ports['A'][0].raw_ws_path == 'test_module1.wire_or.0'
    assert module.instances['dff_inst'].ports['D'][0].raw_ws_path == 'test_module1.wire_or.0'

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
    assert module.ports['out_ff'].signal_array == SignalArray(signals={0: Signal.HIGH})


def test_opt_constant_propagation_dlatch() -> None:
    module = Module(name='testModule1')
    en = module.create_port('EN', Direction.IN)
    d = module.create_port('D', Direction.IN)
    q = module.create_port('Q', Direction.OUT)

    dl = dlatch(module, 'DLatch', Q=q, D=d)
    dl.tie_port('EN', 0, 0)
    assert opt_constant_propagation(module)
    assert module.ports['Q'].driver() == {0: []}
    assert module.ports['Q'].signal is Signal.FLOATING
    assert module.ports['Q'].signal_array == SignalArray(signals={0: Signal.FLOATING})
    assert 'DLatch' not in module.instances

    module.disconnect(q)
    dl = dlatch(module, 'DLatch', Q=q, D=d)
    dl.tie_port('EN', 0, 1)
    assert opt_constant_propagation(module)
    assert module.ports['Q'].driver() == {0: [module.ports['D'][0]]}
    assert 'DLatch' not in module.instances

    module.disconnect(q)
    dl = dlatch(module, 'DLatch', Q=q, D=d, EN=en)
    assert not opt_constant_propagation(module)


@pytest.mark.parametrize('const_port', ['A', 'B'])
def test_opt_constant_propagation_rule_and_low_is_constant(const_port: str) -> None:
    module = _binary_gate_module(AndGate, Signal.LOW, const_port)
    assert opt_constant_propagation(module)
    assert 'inst' not in module.instances
    assert module.ports['y'].is_tied_defined
    assert module.ports['y'].signal is Signal.LOW


@pytest.mark.parametrize('const_port', ['A', 'B'])
def test_opt_constant_propagation_rule_nand_low_is_constant(const_port: str) -> None:
    module = _binary_gate_module(NandGate, Signal.LOW, const_port)
    assert opt_constant_propagation(module)
    assert 'inst' not in module.instances
    assert module.ports['y'].is_tied_defined
    assert module.ports['y'].signal is Signal.HIGH


@pytest.mark.parametrize('const_port', ['A', 'B'])
def test_opt_constant_propagation_rule_or_high_is_constant(const_port: str) -> None:
    module = _binary_gate_module(OrGate, Signal.HIGH, const_port)
    assert opt_constant_propagation(module)
    assert 'inst' not in module.instances
    assert module.ports['y'].is_tied_defined
    assert module.ports['y'].signal is Signal.HIGH


@pytest.mark.parametrize('const_port', ['A', 'B'])
def test_opt_constant_propagation_rule_nor_high_is_constant(const_port: str) -> None:
    module = _binary_gate_module(NorGate, Signal.HIGH, const_port)
    assert opt_constant_propagation(module)
    assert 'inst' not in module.instances
    assert module.ports['y'].is_tied_defined
    assert module.ports['y'].signal is Signal.LOW


@pytest.mark.parametrize('const_port', ['A', 'B'])
def test_opt_constant_propagation_rule_and_high_passes_input(const_port: str) -> None:
    module = _binary_gate_module(AndGate, Signal.HIGH, const_port)
    assert opt_constant_propagation(module)
    assert 'inst' not in module.instances
    assert module.ports['y'][0].raw_ws_path == module.ports['x'][0].raw_ws_path


@pytest.mark.parametrize('const_port', ['A', 'B'])
def test_opt_constant_propagation_rule_or_low_passes_input(const_port: str) -> None:
    module = _binary_gate_module(OrGate, Signal.LOW, const_port)
    assert opt_constant_propagation(module)
    assert 'inst' not in module.instances
    assert module.ports['y'][0].raw_ws_path == module.ports['x'][0].raw_ws_path


@pytest.mark.parametrize('const_port', ['A', 'B'])
def test_opt_constant_propagation_rule_xor_low_passes_input(const_port: str) -> None:
    module = _binary_gate_module(XorGate, Signal.LOW, const_port)
    assert opt_constant_propagation(module)
    assert 'inst' not in module.instances
    assert module.ports['y'][0].raw_ws_path == module.ports['x'][0].raw_ws_path


@pytest.mark.parametrize('const_port', ['A', 'B'])
def test_opt_constant_propagation_rule_xnor_high_passes_input(const_port: str) -> None:
    module = _binary_gate_module(XnorGate, Signal.HIGH, const_port)
    assert opt_constant_propagation(module)
    assert 'inst' not in module.instances
    assert module.ports['y'][0].raw_ws_path == module.ports['x'][0].raw_ws_path


def _assert_single_inverter(module: Module) -> None:
    assert 'inst' not in module.instances
    assert len(module.instances) == 1
    inv = next(iter(module.instances.values()))
    assert inv.instance_type == '§not'
    assert inv.ports['A'][0].raw_ws_path == module.ports['x'][0].raw_ws_path
    assert inv.ports['Y'][0].raw_ws_path == module.ports['y'][0].raw_ws_path


@pytest.mark.parametrize('const_port', ['A', 'B'])
def test_opt_constant_propagation_rule_nand_high_inverts_input(const_port: str) -> None:
    module = _binary_gate_module(NandGate, Signal.HIGH, const_port)
    assert opt_constant_propagation(module)
    _assert_single_inverter(module)


@pytest.mark.parametrize('const_port', ['A', 'B'])
def test_opt_constant_propagation_rule_nor_low_inverts_input(const_port: str) -> None:
    module = _binary_gate_module(NorGate, Signal.LOW, const_port)
    assert opt_constant_propagation(module)
    _assert_single_inverter(module)


@pytest.mark.parametrize('const_port', ['A', 'B'])
def test_opt_constant_propagation_rule_xor_high_inverts_input(const_port: str) -> None:
    module = _binary_gate_module(XorGate, Signal.HIGH, const_port)
    assert opt_constant_propagation(module)
    _assert_single_inverter(module)


@pytest.mark.parametrize('const_port', ['A', 'B'])
def test_opt_constant_propagation_rule_xnor_low_inverts_input(const_port: str) -> None:
    module = _binary_gate_module(XnorGate, Signal.LOW, const_port)
    assert opt_constant_propagation(module)
    _assert_single_inverter(module)


@pytest.mark.parametrize('gate_cls', [AndGate, NandGate, OrGate, XorGate])
def test_opt_constant_propagation_rule_undefined_constant_is_not_folded(gate_cls: type) -> None:
    module = _binary_gate_module(gate_cls, Signal.UNDEFINED)
    assert not opt_constant_propagation(module)
    assert 'inst' in module.instances
    assert module.instances['inst'].ports['Y'][0].raw_ws_path == module.ports['y'][0].raw_ws_path


def test_opt_constant_propagation_rule_partial_is_not_folded() -> None:
    module = Module(name='m')
    a = module.create_port('a', Direction.IN, width=2)
    b = module.create_port('b', Direction.IN, width=2)
    y = module.create_port('y', Direction.OUT, width=2)
    inst = module.create_instance(XorGate, 'inst', {'A_WIDTH': 2, 'B_WIDTH': 2, 'Y_WIDTH': 2})
    module.connect(a, inst.ports['A'])
    module.connect(b, inst.ports['B'])
    module.connect(inst.ports['Y'], y)
    module.disconnect(inst.ports['B'][0])
    inst.ports['B'].tie_signal(1, 0)

    assert not opt_constant_propagation(module)
    assert list(module.instances) == ['inst']


@pytest.mark.parametrize('a_width, b_width', [(4, 8), (8, 4)])
def test_opt_constant_propagation_rule_unequal_port_widths(a_width: int, b_width: int) -> None:
    module = Module(name='m')
    a = module.create_port('a', Direction.IN, width=a_width)
    y = module.create_port('y', Direction.OUT, width=8)
    inst = module.create_instance(AndGate, 'and_inst', {'A_WIDTH': a_width, 'B_WIDTH': b_width, 'Y_WIDTH': 8})
    module.connect(a, inst.ports['A'])
    module.connect(inst.ports['Y'], y)
    for idx in range(b_width):
        inst.ports['B'].tie_signal(1, idx)

    assert not opt_constant_propagation(module)
    assert 'and_inst' in module.instances
    assert module.ports['y'].is_connected


@pytest.mark.parametrize('creation_order', [['g1', 'g2'], ['g2', 'g1']], ids=['forward', 'reverse'])
def test_opt_constant_propagation_rule_cascade(creation_order: list[str]) -> None:
    module = Module(name='m')
    c = module.create_port('c', Direction.IN)
    module.create_port('x', Direction.IN)
    y = module.create_port('y', Direction.OUT)
    gate_types = {'g1': OrGate, 'g2': XorGate}
    insts = {name: module.create_instance(gate_types[name], name) for name in creation_order}
    module.connect(c, insts['g1'].ports['A'])
    insts['g1'].ports['B'].tie_signal(1, 0)
    module.connect(insts['g1'].ports['Y'], insts['g2'].ports['A'])
    module.connect(module.ports['x'], insts['g2'].ports['B'])
    module.connect(insts['g2'].ports['Y'], y)

    assert opt_constant_propagation(module)
    assert not {'g1', 'g2'} & set(module.instances)
    _assert_single_inverter(module)


def test_opt_constant_propagation_rule_all_loads_are_reconnected() -> None:
    module = Module(name='m')
    x = module.create_port('x', Direction.IN)
    y = module.create_port('y', Direction.OUT)
    inst = module.create_instance(AndGate, 'inst')
    n1 = module.create_instance(NotGate, 'n1')
    n2 = module.create_instance(NotGate, 'n2')
    module.connect(x, inst.ports['A'])
    inst.ports['B'].tie_signal(1, 0)
    module.connect(inst.ports['Y'], y)
    module.connect(inst.ports['Y'], n1.ports['A'])
    module.connect(inst.ports['Y'], n2.ports['A'])

    assert opt_constant_propagation(module)
    assert 'inst' not in module.instances
    x_wire = module.ports['x'][0].raw_ws_path
    assert module.ports['y'][0].raw_ws_path == x_wire
    assert module.instances['n1'].ports['A'][0].raw_ws_path == x_wire
    assert module.instances['n2'].ports['A'][0].raw_ws_path == x_wire


def test_opt_constant_propagation_rule_free_input_keeps_other_loads() -> None:
    module = Module(name='m')
    x = module.create_port('x', Direction.IN)
    y = module.create_port('y', Direction.OUT)
    inst = module.create_instance(AndGate, 'inst')
    other = module.create_instance(NotGate, 'other')
    module.connect(x, inst.ports['A'])
    module.connect(x, other.ports['A'])
    inst.ports['B'].tie_signal(1, 0)
    module.connect(inst.ports['Y'], y)

    assert opt_constant_propagation(module)
    assert 'inst' not in module.instances
    assert 'other' in module.instances
    x_wire = module.ports['x'][0].raw_ws_path
    assert module.ports['y'][0].raw_ws_path == x_wire
    assert module.instances['other'].ports['A'][0].raw_ws_path == x_wire


@pytest.mark.parametrize('s_value, selected, other', [(Signal.LOW, 'x0', 'x1'), (Signal.HIGH, 'x1', 'x0')])
def test_opt_constant_propagation_rule_mux_constant_select_passes_selected_input(s_value: Signal, selected: str, other: str) -> None:
    module = Module(name='m')
    x0 = module.create_port('x0', Direction.IN)
    x1 = module.create_port('x1', Direction.IN)
    y = module.create_port('y', Direction.OUT)
    inst = module.create_instance(Multiplexer, 'inst')
    module.connect(x0, inst.ports['D0'])
    module.connect(x1, inst.ports['D1'])
    module.connect(inst.ports['Y'], y)
    inst.ports['S'].tie_signal(s_value, 0)

    assert opt_constant_propagation(module)
    assert 'inst' not in module.instances
    assert module.ports['y'][0].raw_ws_path == module.ports[selected][0].raw_ws_path
    assert module.ports['y'][0].raw_ws_path != module.ports[other][0].raw_ws_path


@pytest.mark.parametrize('s_value, selected, const', [(Signal.LOW, 'D0', Signal.HIGH), (Signal.HIGH, 'D1', Signal.LOW)])
def test_opt_constant_propagation_rule_mux_constant_select_constant_input_is_constant(s_value: Signal, selected: str, const: Signal) -> None:
    module = Module(name='m')
    x = module.create_port('x', Direction.IN)
    y = module.create_port('y', Direction.OUT)
    inst = module.create_instance(Multiplexer, 'inst')
    other = 'D1' if selected == 'D0' else 'D0'
    module.connect(x, inst.ports[other])
    inst.ports[selected].tie_signal(const, 0)
    module.connect(inst.ports['Y'], y)
    inst.ports['S'].tie_signal(s_value, 0)

    assert opt_constant_propagation(module)
    assert 'inst' not in module.instances
    assert module.ports['y'].is_tied_defined
    assert module.ports['y'].signal is const


@pytest.mark.parametrize('s_undefined', [False, True], ids=['free_select', 'undefined_select'])
def test_opt_constant_propagation_rule_mux_non_constant_select_is_not_folded(s_undefined: bool) -> None:
    module = Module(name='m')
    x0 = module.create_port('x0', Direction.IN)
    x1 = module.create_port('x1', Direction.IN)
    y = module.create_port('y', Direction.OUT)
    inst = module.create_instance(Multiplexer, 'inst')
    module.connect(x0, inst.ports['D0'])
    module.connect(x1, inst.ports['D1'])
    module.connect(inst.ports['Y'], y)
    if s_undefined:
        inst.ports['S'].tie_signal(Signal.UNDEFINED, 0)
    else:
        module.connect(module.create_port('s', Direction.IN), inst.ports['S'])

    assert not opt_constant_propagation(module)
    assert 'inst' in module.instances
    assert module.instances['inst'].ports['Y'][0].raw_ws_path == module.ports['y'][0].raw_ws_path


def test_opt_constant_propagation_rule_mux_constant_select_mixed_bits() -> None:
    module = Module(name='m')
    x0 = module.create_port('x0', Direction.IN, width=2)
    x = module.create_port('x', Direction.IN)
    y = module.create_port('y', Direction.OUT, width=2)
    inst = module.create_instance(Multiplexer, 'inst', {'WIDTH': 2})
    module.connect(x0, inst.ports['D0'])
    inst.ports['D1'].tie_signal(1, 0)
    module.connect(x[0], inst.ports['D1'][1])
    module.connect(inst.ports['Y'], y)
    inst.ports['S'].tie_signal(Signal.HIGH, 0)

    assert opt_constant_propagation(module)
    assert 'inst' not in module.instances
    assert module.ports['y'][0].raw_ws_path == '1'
    assert module.ports['y'][1].raw_ws_path == module.ports['x'][0].raw_ws_path


@pytest.mark.parametrize('selected', [0, 1, 2, 3])
def test_opt_constant_propagation_rule_mux_4to1_constant_select(selected: int) -> None:
    module = Module(name='m')
    d_ports = [module.create_port(f'd{i}', Direction.IN) for i in range(4)]
    y = module.create_port('y', Direction.OUT)
    inst = module.create_instance(Multiplexer, 'inst', {'WIDTH': 1, 'BIT_WIDTH': 2})
    for i, d in enumerate(d_ports):
        module.connect(d, inst.ports[f'D{i}'])
    module.connect(inst.ports['Y'], y)
    for bit in range(2):
        inst.ports['S'].tie_signal(Signal.HIGH if (selected >> bit) & 1 else Signal.LOW, bit)

    assert opt_constant_propagation(module)
    assert 'inst' not in module.instances
    assert module.ports['y'][0].raw_ws_path == module.ports[f'd{selected}'][0].raw_ws_path
    for i in range(4):
        if i != selected:
            assert module.ports['y'][0].raw_ws_path != module.ports[f'd{i}'][0].raw_ws_path


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
