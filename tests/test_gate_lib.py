# mypy: disable-error-code="unreachable,comparison-overlap"
import os
from typing import Dict

import pytest
from utils import save_results

from netlist_carpentry import WIRE_SEGMENT_X
from netlist_carpentry.core.enums.direction import Direction
from netlist_carpentry.core.enums.element_type import EType
from netlist_carpentry.core.enums.signal import Signal
from netlist_carpentry.core.exceptions import EvaluationError
from netlist_carpentry.core.netlist_elements.element_path import PortPath, WireSegmentPath
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.netlist_elements.wire_segment import WIRE_SEGMENT_1
from netlist_carpentry.utils.gate_lib import (
    ADFF,
    ADFFE,
    DFF,
    DFFE,
    BinaryGate,
    BinaryNto1Gate,
    Demultiplexer,
    DLatch,
    Multiplexer,
    PrimitiveGate,
    ReduceGate,
    ScanADFF,
    ScanADFFE,
    ScanDFF,
    ScanDFFE,
    UnaryGate,
)
from netlist_carpentry.utils.log import LOG


@pytest.fixture
def primitive_gate() -> Instance:
    return PrimitiveGate(raw_path='a.b.primitive_gate_inst', instance_type='primitive_gate', module=None)


@pytest.fixture
def unary_gate() -> Instance:
    return UnaryGate(raw_path='a.b.unary_gate_inst', instance_type='unary_gate', module=None)


@pytest.fixture
def reduce_gate() -> Instance:
    return ReduceGate(raw_path='a.b.reduce_gate_inst', instance_type='reduce_gate', parameters={'A_WIDTH': 4}, module=None)


@pytest.fixture
def binary_gate() -> Instance:
    return BinaryGate(raw_path='a.b.binary_gate_inst', instance_type='binary_gate', module=None)


@pytest.fixture()
def simple_module() -> Module:
    from utils import empty_module

    m = empty_module()
    m.raw_path = 'a'
    m.create_wire('wire', 4)
    m.create_wire('wireA1', 3)
    m.create_wire('wireA2', 1)
    m.create_wire('wireB', 4)
    for i in range(8):
        m.create_wire(f'wmuxD_{i}', 4)
        m.create_wire(f'wmuxY_{i}', 4)
    m.create_wire('wmuxS', 3)
    m.create_wire('carry')
    m.create_wire('clk')
    m.create_wire('rst')
    m.create_wire('en')
    return m


def test_gate_lib_map(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import _build_gate_lib_map, _gate_lib_map

    _build_gate_lib_map()
    assert len(_gate_lib_map) == 41  # Currently 41 gates in library


def test_primitive_gate(primitive_gate: PrimitiveGate) -> None:
    assert primitive_gate.name == 'primitive_gate_inst'
    assert primitive_gate.type is EType.INSTANCE
    assert primitive_gate.instance_type == 'primitive_gate'
    with pytest.raises(NotImplementedError):
        primitive_gate.output_port
    assert not primitive_gate.is_blackbox
    assert not primitive_gate.is_module_instance
    assert primitive_gate.is_primitive
    assert primitive_gate.is_combinational
    assert not primitive_gate.is_sequential
    assert primitive_gate.verilog_template == 'assign {out} = {in1};'
    with pytest.raises(NotImplementedError):
        primitive_gate.verilog_net_map


def test_unary_gate(unary_gate: UnaryGate) -> None:
    assert unary_gate.name == 'unary_gate_inst'
    assert unary_gate.type is EType.INSTANCE
    assert unary_gate.instance_type == 'unary_gate'
    assert len(unary_gate.connections) == 2
    assert unary_gate.connections['A'] == {0: WIRE_SEGMENT_X.path}
    assert unary_gate.connections['Y'] == {0: WIRE_SEGMENT_X.path}
    assert len(unary_gate.ports) == 2
    assert unary_gate.output_port == unary_gate.ports['Y']
    assert unary_gate.input_port == unary_gate.ports['A']
    assert unary_gate.a_signed is False
    assert unary_gate.ports['A'].path == PortPath(raw=f'{unary_gate.path.raw}.A')
    assert unary_gate.ports['Y'].path == PortPath(raw=f'{unary_gate.path.raw}.Y')
    assert unary_gate.is_primitive
    assert unary_gate.verilog_template == 'assign {out} = {in1};'
    assert unary_gate.verilog == ''
    assert unary_gate.signal_in(0) is Signal.FLOATING
    assert unary_gate.signal_out(0) is Signal.UNDEFINED
    unary_gate.sync_parameters()
    assert unary_gate.sync_parameters() == {'A_SIGNED': False, 'A_WIDTH': 1, 'Y_WIDTH': 1}

    unary_gate.ports['A'].parameters['signed'] = True
    warns = LOG.warns_quantity
    assert unary_gate.a_signed is False
    assert unary_gate.parameters['A_SIGNED'] is False
    assert LOG.warns_quantity == warns + 1


def test_unary_gate_8bit(simple_module: Module) -> None:
    g = UnaryGate(raw_path='a.b.unary_gate_inst', instance_type='unary_gate', parameters={'Y_WIDTH': 8}, module=simple_module)
    assert len(g.connections) == 2
    assert len(g.connections['A']) == 8
    assert len(g.connections['Y']) == 8
    assert len(g.ports) == 2
    assert g.output_port == g.ports['Y']
    assert g.input_port == g.ports['A']
    assert g.output_port.width == 8
    assert g.input_port.width == 8
    assert list(range(8)) == list(g.output_port.segments.keys())
    assert list(range(8)) == list(g.input_port.segments.keys())
    assert g.sync_parameters() == {'A_SIGNED': False, 'A_WIDTH': 8, 'Y_WIDTH': 8}


def test_unary_gate_split(simple_module: Module) -> None:
    g = UnaryGate(raw_path='a.b.unary_gate_inst', instance_type='unary_gate', parameters={'Y_WIDTH': 8}, module=simple_module)
    simple_module.add_instance(g)
    a = simple_module.create_port('A', Direction.IN, width=8)
    y = simple_module.create_port('Y', Direction.OUT, width=8)
    simple_module.connect(a, g.ports['A'])
    simple_module.connect(g.ports['Y'], y)
    connections = g.connections
    assert g.splittable
    assert g.name in simple_module.instances
    splitted = g.split()
    assert g.name not in simple_module.instances
    assert len(splitted) == 8
    for idx, inst in splitted.items():
        assert inst.name in simple_module.instances
        assert inst.width == 1
        assert inst.ports['A'].width == 1
        assert inst.ports['Y'].width == 1
        assert inst.ports['A'][0].ws_path == connections['A'][idx]
        assert inst.ports['Y'][0].ws_path == connections['Y'][idx]


def test_unary_gate_eval(unary_gate: UnaryGate) -> None:
    assert unary_gate.output_port.signal is Signal.UNDEFINED
    unary_gate._set_output({0: Signal.HIGH})
    assert unary_gate.output_port.signal is Signal.HIGH

    with pytest.raises(NotImplementedError):
        unary_gate._calc_output()


def _test_signal_conf1(gate: UnaryGate, sin: Signal, sout_prev: Signal, sout_new: Signal, idx: int = 0) -> None:
    assert gate.signal_out(idx) == sout_prev
    gate.input_port.set_signal(sin, index=idx)
    assert gate.signal_in(idx) == sin
    assert gate.signal_out(idx) == sout_prev
    gate.evaluate()
    assert gate.signal_out(idx) == sout_new


def _test_signal_conf1_n(gate: UnaryGate, sin: Signal, sout_prev: Signal, sout_new: Signal) -> None:
    for i in range(gate.width):
        if i == 1:
            assert gate.signal_in(i) is Signal.HIGH
            gate.input_port.set_signal(sin, index=i)
            assert gate.signal_in(i) is Signal.HIGH
            gate.evaluate()
        elif i == 2:
            assert gate.signal_out(i) is Signal.UNDEFINED
            gate.input_port.set_signal(sin, index=i)
            assert gate.signal_in(i) is Signal.FLOATING
            gate.evaluate()
            assert gate.signal_out(i) is Signal.UNDEFINED
        else:
            _test_signal_conf1(gate, sin, sout_prev, sout_new, i)


def test_buffer(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import Buffer

    g = Buffer(raw_path='a.buf_inst', parameters={'Y_WIDTH': 4}, module=simple_module)
    assert g.name == 'buf_inst'
    assert g.instance_type == '§buf'
    assert g.verilog_template == 'assign {out} = {in1};'

    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: g.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    g.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.3'), index=3)
    assert g.verilog == "assign {wire[3], wire[1:0]} = {wireA2, 1'b1, wireA1[0]};"
    assert g.verilog_net_map == {'Y': '{wire[3], wire[1:0]}', 'A': "{wireA2, 1'b1, wireA1[0]}"}

    _test_signal_conf1_n(g, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf1_n(g, Signal.LOW, Signal.UNDEFINED, Signal.LOW)
    _test_signal_conf1_n(g, Signal.HIGH, Signal.LOW, Signal.HIGH)
    _test_signal_conf1_n(g, Signal.FLOATING, Signal.HIGH, Signal.UNDEFINED)


def test_not_gate(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import NotGate

    g = NotGate(raw_path='a.not_inst', parameters={'Y_WIDTH': 4}, module=simple_module)
    assert g.verilog_template == 'assign {out} = ~{in1};'
    assert g.name == 'not_inst'
    assert g.instance_type == '§not'

    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: g.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    g.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.3'), index=3)
    assert g.verilog == "assign {wire[3], wire[1:0]} = ~{wireA2, 1'b1, wireA1[0]};"

    _test_signal_conf1_n(g, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf1_n(g, Signal.LOW, Signal.UNDEFINED, Signal.HIGH)
    _test_signal_conf1_n(g, Signal.HIGH, Signal.HIGH, Signal.LOW)
    _test_signal_conf1_n(g, Signal.FLOATING, Signal.LOW, Signal.UNDEFINED)


def test_neg_gate(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import NegGate

    g = NegGate(raw_path='a.neg_inst', parameters={'Y_WIDTH': 4}, module=simple_module)
    assert g.verilog_template == 'assign {out} = -{in1};'
    assert g.name == 'neg_inst'
    assert g.instance_type == '§neg'

    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: g.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    g.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.3'), index=3)
    assert g.verilog == "assign {wire[3], wire[1:0]} = -{wireA2, 1'b1, wireA1[0]};"

    g.ports['A'][0].set_signal(Signal.HIGH)
    g.ports['A'][2].tie_signal(Signal.HIGH)
    g.ports['A'][3].set_signal(Signal.LOW)  # 0111 -> 7 ==> neg makes it -7 ==> 1001
    g.evaluate()
    assert g.output_port.signal_array == {0: Signal.HIGH, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.HIGH}

    g.ports['A'][0].set_signal(Signal.HIGH)
    g.ports['A'][2].tie_signal(Signal.HIGH)
    g.ports['A'][3].set_signal(Signal.HIGH)  # 1111 -> 15 ==> neg makes it -15 ==> 10001, but the upper 1 is cut off ==> 0001
    g.evaluate()
    assert g.output_port.signal_array == {0: Signal.HIGH, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW}  # 4: Signal.HIGH
    g.modify_connection('Y', WireSegmentPath(raw='a.carry.0'), index=4)
    g.evaluate()
    assert g.output_port.signal_array == {0: Signal.HIGH, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW, 4: Signal.HIGH}


def _test_signal_confr_n(gate: UnaryGate, sin: Signal, sout_prev: Signal, sout_new: Signal) -> None:
    assert gate.signal_out() == sout_prev
    for i in range(gate.width):
        gate.input_port.set_signal(sin, index=i)
        if i == 1:
            assert gate.signal_in(i) == Signal.HIGH
        elif i == 2:
            assert gate.signal_in(i) == Signal.FLOATING
        else:
            assert gate.signal_in(i) == sin
    assert gate.signal_out() == sout_prev
    gate.evaluate()
    assert gate.signal_out() == Signal.UNDEFINED or sout_new
    gate.modify_connection('A', WireSegmentPath(raw='a.wireA1.1'), index=1)
    gate.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    gate.input_port.set_signal(sin, 1)
    gate.input_port.set_signal(sin, 2)
    gate.evaluate()
    assert gate.signal_out() == sout_new
    gate.modify_connection('A', WIRE_SEGMENT_1.path, index=1)
    gate.modify_connection('A', WIRE_SEGMENT_X.path, index=2)


def test_reducer(reduce_gate: ReduceGate) -> None:
    assert reduce_gate.name == 'reduce_gate_inst'
    assert reduce_gate.type is EType.INSTANCE
    assert reduce_gate.instance_type == 'reduce_gate'
    assert len(reduce_gate.connections) == 2
    assert reduce_gate.connections['A'] == {0: WIRE_SEGMENT_X.path, 1: WIRE_SEGMENT_X.path, 2: WIRE_SEGMENT_X.path, 3: WIRE_SEGMENT_X.path}
    assert reduce_gate.connections['Y'] == {0: WIRE_SEGMENT_X.path}
    assert len(reduce_gate.ports) == 2
    assert reduce_gate.output_port == reduce_gate.ports['Y']
    assert reduce_gate.input_port == reduce_gate.ports['A']
    assert reduce_gate.ports['A'].path == PortPath(raw=f'{reduce_gate.path.raw}.A')
    assert reduce_gate.ports['Y'].path == PortPath(raw=f'{reduce_gate.path.raw}.Y')
    assert reduce_gate.is_primitive
    assert reduce_gate.verilog_template == 'assign {out} = {operator}{in1};'
    assert all(reduce_gate.signal_in(i) is Signal.FLOATING for i in reduce_gate.ports['A'].segments)
    assert reduce_gate.signal_out() is Signal.UNDEFINED
    reduce_gate.ports['A'].parameters['signed'] = 1
    assert reduce_gate.sync_parameters() == {'A_WIDTH': 4, 'A_SIGNED': True, 'Y_WIDTH': 1}
    assert not reduce_gate.splittable


def test_reduce_and(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import ReduceAnd

    r = ReduceAnd(raw_path='a.reduce_and_inst', parameters={'A_WIDTH': 4}, module=simple_module)
    assert r.verilog_template == 'assign {out} = &{in1};'
    r.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    r.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: r.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    r.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    r.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    assert r.verilog == "assign wire[0] = &{wireA2, 1'b1, wireA1[0]};"
    assert r.verilog_net_map == {'Y': 'wire[0]', 'A': "{wireA2, 1'b1, wireA1[0]}"}

    _test_signal_confr_n(r, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_confr_n(r, Signal.FLOATING, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_confr_n(r, Signal.HIGH, Signal.UNDEFINED, Signal.HIGH)
    _test_signal_confr_n(r, Signal.LOW, Signal.HIGH, Signal.LOW)

    r.input_port.set_signal(Signal.LOW, index=0)
    r.input_port.set_signal(Signal.HIGH, index=1)
    r.input_port.set_signal(Signal.LOW, index=2)
    r.input_port.set_signal(Signal.HIGH, index=3)
    r.evaluate()
    assert r.signal_out() == Signal.UNDEFINED

    r.tie_port('A', index=2, sig_value='1')
    r.evaluate()
    assert r.signal_out() == Signal.LOW


def test_reduce_and_bad_verilog(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import ReduceAnd

    r = ReduceAnd(raw_path='a.reduce_and_inst', parameters={'A_WIDTH': 4}, module=simple_module)
    r.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    r.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: r.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    r.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    assert r.verilog == ''  # No output specified -> useless instance


def test_reduce_or(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import ReduceOr

    r = ReduceOr(raw_path='a.reduce_or_inst', parameters={'A_WIDTH': 4}, module=simple_module)
    assert r.verilog_template == 'assign {out} = |{in1};'
    r.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    r.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: r.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    r.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    r.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    assert r.verilog == "assign wire[0] = |{wireA2, 1'b1, wireA1[0]};"

    _test_signal_confr_n(r, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_confr_n(r, Signal.FLOATING, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_confr_n(r, Signal.HIGH, Signal.UNDEFINED, Signal.HIGH)
    _test_signal_confr_n(r, Signal.LOW, Signal.HIGH, Signal.LOW)

    r.input_port.set_signal(Signal.LOW, index=0)
    r.input_port.set_signal(Signal.HIGH, index=1)
    r.input_port.set_signal(Signal.LOW, index=2)
    r.input_port.set_signal(Signal.HIGH, index=3)
    r.evaluate()
    assert r.signal_out() == Signal.HIGH

    r.input_port.set_signal(Signal.FLOATING, index=1)
    r.evaluate()
    assert r.signal_out() == Signal.HIGH

    r.modify_connection('A', WireSegmentPath(raw='0'), index=1)
    r.input_port.set_signal(Signal.FLOATING, index=3)
    r.evaluate()
    assert r.signal_out() == Signal.UNDEFINED


def test_reduce_bool(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import ReduceBool

    r = ReduceBool(raw_path='a.reduce_bool_inst', parameters={'A_WIDTH': 4}, module=simple_module)
    assert r.verilog_template == 'assign {out} = |{in1};'  # TODO EQY unable to prove equality for !(!wire), but can prove equality for |wire
    r.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    r.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: r.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    r.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    r.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    assert (
        r.verilog == "assign wire[0] = |{wireA2, 1'b1, wireA1[0]};"
    )  # TODO EQY unable to prove equality for !(!wire), but can prove equality for |wire

    _test_signal_confr_n(r, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_confr_n(r, Signal.FLOATING, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_confr_n(r, Signal.HIGH, Signal.UNDEFINED, Signal.HIGH)
    _test_signal_confr_n(r, Signal.LOW, Signal.HIGH, Signal.LOW)

    r.input_port.set_signal(Signal.LOW, index=0)
    r.input_port.set_signal(Signal.HIGH, index=1)
    r.input_port.set_signal(Signal.LOW, index=2)
    r.input_port.set_signal(Signal.HIGH, index=3)
    r.evaluate()
    assert r.signal_out() == Signal.HIGH

    r.input_port.set_signal(Signal.FLOATING, index=1)
    r.evaluate()
    assert r.signal_out() == Signal.HIGH

    r.modify_connection('A', WireSegmentPath(raw='0'), index=1)
    r.input_port.set_signal(Signal.FLOATING, index=3)
    r.evaluate()
    assert r.signal_out() == Signal.UNDEFINED


def test_reduce_xor(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import ReduceXor

    r = ReduceXor(raw_path='a.reduce_xor_inst', parameters={'A_WIDTH': 4}, module=simple_module)
    assert r.verilog_template == 'assign {out} = ^{in1};'
    r.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    r.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: r.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    r.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    r.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    assert r.verilog == "assign wire[0] = ^{wireA2, 1'b1, wireA1[0]};"

    _test_signal_confr_n(r, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_confr_n(r, Signal.FLOATING, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_confr_n(r, Signal.HIGH, Signal.UNDEFINED, Signal.LOW)
    _test_signal_confr_n(r, Signal.LOW, Signal.LOW, Signal.LOW)

    r.input_port.set_signal(Signal.LOW, index=0)
    r.input_port.set_signal(Signal.HIGH, index=1)
    r.input_port.set_signal(Signal.HIGH, index=2)
    r.input_port.set_signal(Signal.HIGH, index=3)
    r.modify_connection('A', WireSegmentPath(raw='a.wireA1.1'), index=1)
    r.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    r.evaluate()
    assert r.signal_out() == Signal.HIGH

    r.input_port.set_signal(Signal.FLOATING, index=1)
    r.evaluate()
    assert r.signal_out() == Signal.UNDEFINED


def test_reduce_xnor(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import ReduceXnor

    r = ReduceXnor(raw_path='a.reduce_xnor_inst', parameters={'A_WIDTH': 4}, module=simple_module)
    assert r.verilog_template == 'assign {out} = ~^{in1};'
    r.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    r.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: r.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    r.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    r.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    assert r.verilog == "assign wire[0] = ~^{wireA2, 1'b1, wireA1[0]};"

    _test_signal_confr_n(r, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_confr_n(r, Signal.FLOATING, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_confr_n(r, Signal.HIGH, Signal.UNDEFINED, Signal.HIGH)
    _test_signal_confr_n(r, Signal.LOW, Signal.HIGH, Signal.HIGH)

    r.input_port.set_signal(Signal.LOW, index=0)
    r.input_port.set_signal(Signal.HIGH, index=1)
    r.input_port.set_signal(Signal.HIGH, index=2)
    r.input_port.set_signal(Signal.HIGH, index=3)
    r.modify_connection('A', WireSegmentPath(raw='a.wireA1.1'), index=1)
    r.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    r.evaluate()
    assert r.signal_out() == Signal.LOW

    r.input_port.set_signal(Signal.FLOATING, index=1)
    r.evaluate()
    assert r.signal_out() == Signal.UNDEFINED


def test_logic_not(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import LogicNot

    ln = LogicNot(raw_path='a.logic_not_inst', parameters={'A_WIDTH': 4}, module=simple_module)
    assert ln.verilog_template == 'assign {out} = !{in1};'
    ln.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    ln.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: r.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    ln.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    ln.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    assert ln.verilog == "assign wire[0] = !{wireA2, 1'b1, wireA1[0]};"

    _test_signal_confr_n(ln, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_confr_n(ln, Signal.FLOATING, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_confr_n(ln, Signal.HIGH, Signal.UNDEFINED, Signal.LOW)
    _test_signal_confr_n(ln, Signal.LOW, Signal.LOW, Signal.HIGH)

    ln.input_port.set_signal(Signal.LOW, index=0)
    ln.input_port.set_signal(Signal.LOW, index=1)
    ln.input_port.set_signal(Signal.LOW, index=2)
    ln.input_port.set_signal(Signal.LOW, index=3)
    ln.modify_connection('A', WireSegmentPath(raw='a.wireA1.1'), index=1)
    ln.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    ln.evaluate()
    assert ln.signal_out() == Signal.HIGH

    ln.input_port.set_signal(Signal.HIGH, index=1)
    ln.evaluate()
    assert ln.signal_out() == Signal.LOW


def test_binary_gate(binary_gate: BinaryGate) -> None:
    assert binary_gate.name == 'binary_gate_inst'
    assert binary_gate.type is EType.INSTANCE
    assert binary_gate.instance_type == 'binary_gate'
    assert len(binary_gate.connections) == 3
    assert binary_gate.connections['A'] == {0: WIRE_SEGMENT_X.path}
    assert binary_gate.connections['B'] == {0: WIRE_SEGMENT_X.path}
    assert binary_gate.connections['Y'] == {0: WIRE_SEGMENT_X.path}
    assert len(binary_gate.ports) == 3
    assert binary_gate.output_port == binary_gate.ports['Y']
    assert binary_gate.input_ports == (binary_gate.ports['A'], binary_gate.ports['B'])
    assert binary_gate.a_signed is False
    assert binary_gate.b_signed is False
    assert binary_gate.ports['A'].path == PortPath(raw=f'{binary_gate.path.raw}.A')
    assert binary_gate.ports['B'].path == PortPath(raw=f'{binary_gate.path.raw}.B')
    assert binary_gate.ports['Y'].path == PortPath(raw=f'{binary_gate.path.raw}.Y')
    assert binary_gate.is_primitive
    assert binary_gate.verilog_template == 'assign {out} = {in1} {operator} {in2};'
    assert binary_gate.verilog == ''
    assert binary_gate.signals_in(0) == (Signal.FLOATING, Signal.FLOATING)
    assert binary_gate.signal_out(0) is Signal.UNDEFINED
    binary_gate.ports['B'].parameters['signed'] = '1'
    assert binary_gate.sync_parameters() == {'A_WIDTH': 1, 'A_SIGNED': False, 'B_SIGNED': True, 'B_WIDTH': 1, 'Y_WIDTH': 1}
    assert binary_gate.splittable

    binary_gate.ports['A'].parameters['signed'] = True
    binary_gate.ports['B'].parameters['signed'] = False
    warns = LOG.warns_quantity
    assert binary_gate.a_signed is False
    assert binary_gate.b_signed is True
    assert binary_gate.parameters['A_SIGNED'] is False
    assert binary_gate.parameters['B_SIGNED'] is True
    assert LOG.warns_quantity == warns + 2


def test_binary_gate_8bit(simple_module: Module) -> None:
    g = BinaryGate(raw_path='a.b.binary_gate_inst', instance_type='binary_gate', parameters={'Y_WIDTH': 8}, module=simple_module)
    assert len(g.connections) == 3
    assert len(g.connections['A']) == 8
    assert len(g.connections['B']) == 8
    assert len(g.connections['Y']) == 8
    assert len(g.ports) == 3
    assert g.output_port == g.ports['Y']
    assert g.input_ports == (g.ports['A'], g.ports['B'])
    assert g.output_port.width == 8
    assert g.input_ports[0].width == 8
    assert g.input_ports[1].width == 8
    assert list(range(8)) == list(g.output_port.segments.keys())
    assert list(range(8)) == list(g.input_ports[0].segments.keys())
    assert list(range(8)) == list(g.input_ports[1].segments.keys())


def test_binary_gate_split(simple_module: Module) -> None:
    g = BinaryGate(raw_path='a.b.binary_gate_inst', instance_type='binary_gate', parameters={'Y_WIDTH': 8}, module=simple_module)
    simple_module.add_instance(g)
    a = simple_module.create_port('A', Direction.IN, width=8)
    b = simple_module.create_port('B', Direction.IN, width=8)
    y = simple_module.create_port('Y', Direction.OUT, width=8)
    simple_module.connect(a, g.ports['A'])
    simple_module.connect(b, g.ports['B'])
    simple_module.connect(g.ports['Y'], y)
    connections = g.connections
    assert g.splittable
    assert g.name in simple_module.instances
    splitted = g.split()
    assert g.name not in simple_module.instances
    assert len(splitted) == 8
    for idx, inst in splitted.items():
        assert inst.name in simple_module.instances
        assert inst.width == 1
        assert inst.ports['A'].width == 1
        assert inst.ports['B'].width == 1
        assert inst.ports['Y'].width == 1
        assert inst.ports['A'][0].ws_path == connections['A'][idx]
        assert inst.ports['B'][0].ws_path == connections['B'][idx]
        assert inst.ports['Y'][0].ws_path == connections['Y'][idx]


def test_binary_gate_eval(binary_gate: BinaryGate) -> None:
    assert binary_gate.output_port.signal is Signal.UNDEFINED
    binary_gate._set_output({0: Signal.HIGH})
    assert binary_gate.output_port.signal is Signal.HIGH

    with pytest.raises(NotImplementedError):
        binary_gate._calc_output()


def _test_signal_conf2(gate: BinaryGate, sin1: Signal, sin2: Signal, sout_prev: Signal, sout_new: Signal, idx: int = 0) -> None:
    if idx == 1:
        assert gate.signals_in(idx)[0] == Signal.HIGH
        gate.input_ports[0].set_signal(sin1, index=idx)
        gate.input_ports[1].set_signal(sin2, index=idx)
        assert gate.signals_in(idx) == (Signal.HIGH, sin2)
    elif idx == 2:
        assert gate.signals_in(idx) == (Signal.FLOATING, Signal.FLOATING)
        gate.input_ports[0].set_signal(sin1, index=idx)
        gate.input_ports[1].set_signal(sin2, index=idx)
        assert gate.signals_in(idx) == (Signal.FLOATING, Signal.FLOATING)
    else:
        assert gate.signal_out(idx) == sout_prev
        gate.input_ports[0].set_signal(sin1, index=idx)
        gate.input_ports[1].set_signal(sin2, index=idx)
        assert gate.signals_in(idx) == (sin1, sin2)
        assert gate.signal_out(idx) == sout_prev
        gate.evaluate()
        assert gate.signal_out(idx) == sout_new


def _test_signal_conf2_n(gate: BinaryGate, sin1: Signal, sin2: Signal, sout_prev: Signal, sout_new: Signal) -> None:
    for i in range(gate.width):
        _test_signal_conf2(gate, sin1, sin2, sout_prev, sout_new, i)


def test_and_gate(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import AndGate

    g = AndGate(raw_path='a.and_inst', parameters={'Y_WIDTH': 4}, module=simple_module)
    assert g.name == 'and_inst'
    assert g.instance_type == '§and'
    assert g.verilog_template == 'assign {out} = {in1} & {in2};'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: g.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    g.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('B', WireSegmentPath(raw='a.wireB.2'), index=2)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.3'), index=3)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.3'), index=3)
    assert g.verilog == "assign {wire[3], wire[1:0]} = {wireA2, 1'b1, wireA1[0]} & {wireB[3], wireB[1:0]};"
    assert g.verilog_net_map == {'Y': '{wire[3], wire[1:0]}', 'A': "{wireA2, 1'b1, wireA1[0]}", 'B': '{wireB[3], wireB[1:0]}'}

    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.LOW, Signal.UNDEFINED, Signal.LOW)
    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.HIGH, Signal.LOW, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.FLOATING, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.FLOATING, Signal.LOW, Signal.UNDEFINED, Signal.LOW)
    _test_signal_conf2_n(g, Signal.FLOATING, Signal.HIGH, Signal.LOW, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.FLOATING, Signal.FLOATING, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.LOW, Signal.LOW, Signal.UNDEFINED, Signal.LOW)
    _test_signal_conf2_n(g, Signal.LOW, Signal.HIGH, Signal.LOW, Signal.LOW)
    _test_signal_conf2_n(g, Signal.HIGH, Signal.HIGH, Signal.LOW, Signal.HIGH)


def test_and_gate_signed(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import AndGate

    g = AndGate(raw_path='a.and_inst', parameters={'Y_WIDTH': 4}, module=simple_module)
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: g.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    g.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('B', WireSegmentPath(raw='a.wireB.2'), index=2)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.3'), index=3)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.3'), index=3)
    g.parameters['A_SIGNED'] = True
    g.parameters['B_SIGNED'] = True
    assert g.verilog == "assign {wire[3], wire[1:0]} = $signed({wireA2, 1'b1, wireA1[0]}) & $signed({wireB[3], wireB[1:0]});"
    assert g.verilog_net_map == {'Y': '{wire[3], wire[1:0]}', 'A': "{wireA2, 1'b1, wireA1[0]}", 'B': '{wireB[3], wireB[1:0]}'}


def test_or_gate(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import OrGate

    g = OrGate(raw_path='a.or_inst', parameters={'Y_WIDTH': 4}, module=simple_module)
    assert g.name == 'or_inst'
    assert g.instance_type == '§or'
    assert g.verilog_template == 'assign {out} = {in1} | {in2};'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: g.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    g.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('B', WireSegmentPath(raw='a.wireB.2'), index=2)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.3'), index=3)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.3'), index=3)
    assert g.verilog == "assign {wire[3], wire[1:0]} = {wireA2, 1'b1, wireA1[0]} | {wireB[3], wireB[1:0]};"

    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.LOW, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.HIGH, Signal.UNDEFINED, Signal.HIGH)
    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.FLOATING, Signal.HIGH, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.FLOATING, Signal.LOW, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.FLOATING, Signal.HIGH, Signal.UNDEFINED, Signal.HIGH)
    _test_signal_conf2_n(g, Signal.FLOATING, Signal.FLOATING, Signal.HIGH, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.LOW, Signal.LOW, Signal.UNDEFINED, Signal.LOW)
    _test_signal_conf2_n(g, Signal.LOW, Signal.HIGH, Signal.LOW, Signal.HIGH)
    _test_signal_conf2_n(g, Signal.HIGH, Signal.HIGH, Signal.HIGH, Signal.HIGH)


def test_xor_gate(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import XorGate

    g = XorGate(raw_path='a.xor_inst', parameters={'Y_WIDTH': 4}, module=simple_module)
    assert g.name == 'xor_inst'
    assert g.instance_type == '§xor'
    assert g.verilog_template == 'assign {out} = {in1} ^ {in2};'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: g.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    g.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('B', WireSegmentPath(raw='a.wireB.2'), index=2)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.3'), index=3)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.3'), index=3)
    assert g.verilog == "assign {wire[3], wire[1:0]} = {wireA2, 1'b1, wireA1[0]} ^ {wireB[3], wireB[1:0]};"

    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.LOW, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.HIGH, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.FLOATING, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.FLOATING, Signal.LOW, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.FLOATING, Signal.HIGH, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.FLOATING, Signal.FLOATING, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.LOW, Signal.LOW, Signal.UNDEFINED, Signal.LOW)
    _test_signal_conf2_n(g, Signal.LOW, Signal.HIGH, Signal.LOW, Signal.HIGH)
    _test_signal_conf2_n(g, Signal.HIGH, Signal.HIGH, Signal.HIGH, Signal.LOW)


def test_xnor_gate(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import XnorGate

    g = XnorGate(raw_path='a.xnor_inst', parameters={'Y_WIDTH': 4}, module=simple_module)
    assert g.name == 'xnor_inst'
    assert g.instance_type == '§xnor'
    assert g.verilog_template == 'assign {out} = {in1} ^~ {in2};'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: g.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    g.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('B', WireSegmentPath(raw='a.wireB.2'), index=2)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.3'), index=3)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.3'), index=3)
    assert g.verilog == "assign {wire[3], wire[1:0]} = {wireA2, 1'b1, wireA1[0]} ^~ {wireB[3], wireB[1:0]};"

    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.LOW, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.HIGH, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.FLOATING, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.FLOATING, Signal.LOW, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.FLOATING, Signal.HIGH, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.FLOATING, Signal.FLOATING, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.LOW, Signal.LOW, Signal.UNDEFINED, Signal.HIGH)
    _test_signal_conf2_n(g, Signal.LOW, Signal.HIGH, Signal.HIGH, Signal.LOW)
    _test_signal_conf2_n(g, Signal.HIGH, Signal.HIGH, Signal.LOW, Signal.HIGH)


def test_nor_gate(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import NorGate

    g = NorGate(raw_path='a.nor_inst', parameters={'Y_WIDTH': 4}, module=simple_module)
    assert g.name == 'nor_inst'
    assert g.instance_type == '§nor'
    assert g.verilog_template == 'assign {out} = ~({in1} | {in2});'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: g.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    g.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('B', WireSegmentPath(raw='a.wireB.2'), index=2)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.3'), index=3)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.3'), index=3)
    assert g.verilog == "assign {wire[3], wire[1:0]} = ~({wireA2, 1'b1, wireA1[0]} | {wireB[3], wireB[1:0]});"

    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.LOW, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.HIGH, Signal.UNDEFINED, Signal.LOW)
    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.FLOATING, Signal.LOW, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.FLOATING, Signal.LOW, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.FLOATING, Signal.HIGH, Signal.UNDEFINED, Signal.LOW)
    _test_signal_conf2_n(g, Signal.FLOATING, Signal.FLOATING, Signal.LOW, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.LOW, Signal.LOW, Signal.UNDEFINED, Signal.HIGH)
    _test_signal_conf2_n(g, Signal.LOW, Signal.HIGH, Signal.HIGH, Signal.LOW)
    _test_signal_conf2_n(g, Signal.HIGH, Signal.HIGH, Signal.LOW, Signal.LOW)


def test_nand_gate(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import NandGate

    g = NandGate(raw_path='a.nand_inst', parameters={'Y_WIDTH': 4}, module=simple_module)
    assert g.name == 'nand_inst'
    assert g.instance_type == '§nand'
    assert g.verilog_template == 'assign {out} = ~({in1} & {in2});'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: g.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    g.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('B', WireSegmentPath(raw='a.wireB.2'), index=2)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.3'), index=3)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.3'), index=3)
    assert g.verilog == "assign {wire[3], wire[1:0]} = ~({wireA2, 1'b1, wireA1[0]} & {wireB[3], wireB[1:0]});"

    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.LOW, Signal.UNDEFINED, Signal.HIGH)
    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.HIGH, Signal.HIGH, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.UNDEFINED, Signal.FLOATING, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.FLOATING, Signal.LOW, Signal.UNDEFINED, Signal.HIGH)
    _test_signal_conf2_n(g, Signal.FLOATING, Signal.HIGH, Signal.HIGH, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.FLOATING, Signal.FLOATING, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf2_n(g, Signal.LOW, Signal.LOW, Signal.UNDEFINED, Signal.HIGH)
    _test_signal_conf2_n(g, Signal.LOW, Signal.HIGH, Signal.HIGH, Signal.HIGH)
    _test_signal_conf2_n(g, Signal.HIGH, Signal.HIGH, Signal.HIGH, Signal.LOW)


def test_shift_signed_gate(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import ShiftSigned

    g = ShiftSigned(raw_path='a.shift_inst', parameters={'Y_WIDTH': 4}, module=simple_module)
    assert g.name == 'shift_inst'
    assert g.instance_type == '§shift'
    assert not g.splittable
    assert g.verilog_template == 'assign {out} = {in1} >> {in2};'
    g.parameters['B_SIGNED'] = True
    assert g.b_signed is True
    assert g.verilog_template == 'assign {out} = {in1} << -{in2};'
    assert g.verilog == ''
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: g.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    g.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('B', WireSegmentPath(raw='a.wireB.2'), index=2)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.3'), index=3)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.3'), index=3)
    assert g.verilog == "assign {wire[3], wire[1:0]} = {wireA2, 1'b1, wireA1[0]} << -{wireB[3], wireB[1:0]};"
    g.parameters['B_SIGNED'] = False
    assert g.verilog == "assign {wire[3], wire[1:0]} = {wireA2, 1'b1, wireA1[0]} >> {wireB[3], wireB[1:0]};"
    g.parameters['A_SIGNED'] = True
    assert g.verilog == "assign {wire[3], wire[1:0]} = $signed({wireA2, 1'b1, wireA1[0]}) >> {wireB[3], wireB[1:0]};"
    g.parameters['B_SIGNED'] = True
    assert g.verilog == "assign {wire[3], wire[1:0]} = $signed({wireA2, 1'b1, wireA1[0]}) << -{wireB[3], wireB[1:0]};"

    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.1'), index=1)
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.2'), index=2)

    # A unsigned, B unsigned: logical right shift
    g.ports['A'].set_signals('0110')
    g.ports['B'].set_signals('0001')
    g.evaluate()
    assert g.ports['Y'].signal_array == {3: Signal.LOW, 2: Signal.LOW, 1: Signal.HIGH, 0: Signal.HIGH}

    # A signed, B unsigned: right shift, but A is signed
    g.parameters['A_SIGNED'] = True
    g.ports['A'].set_signals('0110')
    g.ports['B'].set_signals('0001')
    g.evaluate()
    assert g.ports['Y'].signal_array == {3: Signal.LOW, 2: Signal.LOW, 1: Signal.HIGH, 0: Signal.HIGH}
    g.parameters['A_SIGNED'] = True
    g.ports['A'].set_signals('1011')  # -5
    g.ports['B'].set_signals('0010')
    g.evaluate()
    assert g.ports['Y'].signal_array == {3: Signal.HIGH, 2: Signal.HIGH, 1: Signal.HIGH, 0: Signal.LOW}

    # A signed, B signed: left shift, but A is signed
    g.parameters['B_SIGNED'] = True
    g.ports['A'].set_signals('1011')  # -5
    g.ports['B'].set_signals('0001')  # B == 1 > 0: Right Shift by 1: '1011' >> 1 = '1101' in signed context
    g.evaluate()
    assert g.ports['Y'].signal_array == {3: Signal.HIGH, 2: Signal.HIGH, 1: Signal.LOW, 0: Signal.HIGH}
    g.parameters['A_SIGNED'] = True
    g.ports['A'].set_signals('1011')  # -5
    g.ports['B'].set_signals('1111')  # B == -1 < 0: Left Shift by 1: '1011' << 1 = '0110'
    g.evaluate()
    assert g.ports['Y'].signal_array == {3: Signal.LOW, 2: Signal.HIGH, 1: Signal.HIGH, 0: Signal.LOW}

    # A unsigned, B signed: logical left shift
    g.parameters['A_SIGNED'] = False
    g.ports['A'].set_signals('1011')  # 11
    g.ports['B'].set_signals('0001')  # B == 1 > 0: Right Shift by 1: '1011' >> 1 = '0101' since A is unsigned
    g.evaluate()
    assert g.ports['Y'].signal_array == {3: Signal.LOW, 2: Signal.HIGH, 1: Signal.LOW, 0: Signal.HIGH}
    g.parameters['A_SIGNED'] = True
    g.ports['A'].set_signals('1011')  # -5
    g.ports['B'].set_signals('1111')  # B == -1 < 0: Left Shift by 1: '1011' << 1 = '0110'
    g.evaluate()
    assert g.ports['Y'].signal_array == {3: Signal.LOW, 2: Signal.HIGH, 1: Signal.HIGH, 0: Signal.LOW}

    g.ports['A'].parameters['signed'] = '0'
    g.ports['B'].parameters['signed'] = '1'
    assert g.sync_parameters() == {'A_WIDTH': 4, 'A_SIGNED': False, 'B_WIDTH': 4, 'B_SIGNED': True, 'Y_WIDTH': 4}


def test_shl_gate(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import ShiftLeft

    g = ShiftLeft(raw_path='a.shl_inst', parameters={'Y_WIDTH': 4}, module=simple_module)
    assert g.name == 'shl_inst'
    assert g.instance_type == '§shl'
    assert g.verilog_template == 'assign {out} = {in1} << {in2};'
    assert g.verilog == ''
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: g.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    g.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('B', WireSegmentPath(raw='a.wireB.2'), index=2)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.3'), index=3)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.3'), index=3)
    assert g.verilog == "assign {wire[3], wire[1:0]} = {wireA2, 1'b1, wireA1[0]} << {wireB[3], wireB[1:0]};"
    g.parameters['A_SIGNED'] = True
    assert g.verilog == "assign {wire[3], wire[1:0]} = $signed({wireA2, 1'b1, wireA1[0]}) << {wireB[3], wireB[1:0]};"
    g.parameters['B_SIGNED'] = True  # B_SIGNED == 1 should not change Verilog output
    assert g.verilog == "assign {wire[3], wire[1:0]} = $signed({wireA2, 1'b1, wireA1[0]}) << {wireB[3], wireB[1:0]};"

    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.1'), index=1)
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.2'), index=2)

    g.ports['A'].set_signals('0011')
    g.ports['B'].set_signals('0010')
    g.evaluate()
    assert g.ports['Y'].signal_array == {3: Signal.HIGH, 2: Signal.HIGH, 1: Signal.LOW, 0: Signal.LOW}

    g.ports['A'].set_signals('0011')
    g.ports['B'].set_signals('0011')
    g.evaluate()
    assert g.ports['Y'].signal_array == {3: Signal.HIGH, 2: Signal.LOW, 1: Signal.LOW, 0: Signal.LOW}

    g.ports['A'].set_signals('0011')
    g.ports['B'].set_signals('0100')
    g.evaluate()
    assert g.ports['Y'].signal_array == {3: Signal.LOW, 2: Signal.LOW, 1: Signal.LOW, 0: Signal.LOW}


def test_shr_gate(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import ShiftRight

    g = ShiftRight(raw_path='a.shr_inst', parameters={'Y_WIDTH': 4}, module=simple_module)
    assert g.name == 'shr_inst'
    assert g.instance_type == '§shr'
    assert g.verilog_template == 'assign {out} = {in1} >> {in2};'
    assert g.verilog == ''
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: g.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    g.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('B', WireSegmentPath(raw='a.wireB.2'), index=2)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.3'), index=3)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.1'), index=1)
    # 2nd is missing on purpose: g.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    g.modify_connection('Y', WireSegmentPath(raw='a.wire.3'), index=3)
    assert g.verilog == "assign {wire[3], wire[1:0]} = {wireA2, 1'b1, wireA1[0]} >> {wireB[3], wireB[1:0]};"
    g.parameters['A_SIGNED'] = True
    assert g.verilog == "assign {wire[3], wire[1:0]} = $signed({wireA2, 1'b1, wireA1[0]}) >> {wireB[3], wireB[1:0]};"
    g.parameters['B_SIGNED'] = True  # B_SIGNED == 1 should not change Verilog output
    assert g.verilog == "assign {wire[3], wire[1:0]} = $signed({wireA2, 1'b1, wireA1[0]}) >> {wireB[3], wireB[1:0]};"

    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.1'), index=1)
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.2'), index=2)

    g.ports['A'].set_signals('1100')
    g.ports['B'].set_signals('0010')
    g.evaluate()
    assert g.ports['Y'].signal_array == {3: Signal.LOW, 2: Signal.LOW, 1: Signal.HIGH, 0: Signal.HIGH}

    g.ports['A'].set_signals('1100')
    g.ports['B'].set_signals('0011')
    g.evaluate()
    assert g.ports['Y'].signal_array == {3: Signal.LOW, 2: Signal.LOW, 1: Signal.LOW, 0: Signal.HIGH}

    g.ports['A'].set_signals('1100')
    g.ports['B'].set_signals('0100')
    g.evaluate()
    assert g.ports['Y'].signal_array == {3: Signal.LOW, 2: Signal.LOW, 1: Signal.LOW, 0: Signal.LOW}


def test_comparison_gate(simple_module: Module) -> None:
    g = BinaryNto1Gate(raw_path='a.comp_inst', module=simple_module)
    assert g.verilog == ''
    assert not g.splittable


def _test_signal_conf2_arith(gate: BinaryGate, sins1: Dict[int, Signal], sins2: Dict[int, Signal], sout: Signal) -> None:
    for i, s in sins1.items():
        gate.input_ports[0].set_signal(s, i)
        if i == 1:
            assert gate.input_ports[0][i].signal == Signal.HIGH
        else:
            assert gate.input_ports[0][i].signal == s
    for i, s in sins2.items():
        gate.input_ports[1].set_signal(s, i)
        assert gate.input_ports[1][i].signal == s
    gate.modify_connection('A', WireSegmentPath(raw='a.wireA1.1'), index=1)
    gate.input_ports[0].set_signal(sins1[1], 1)
    gate.evaluate()
    assert gate.output_port.signal == sout
    gate.ports['A'][1].set_ws_path('')
    gate.tie_port('A', index=1, sig_value='1')


def test_logic_and_gate(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import LogicAnd

    g = LogicAnd(raw_path='a.logic_and_inst', parameters={'A_WIDTH': 2}, module=simple_module)
    assert g.name == 'logic_and_inst'
    assert g.instance_type == '§logic_and'
    assert g.verilog_template == 'assign {out} = {in1} && {in2};'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    assert g.verilog == "assign wire[0] = {1'b1, wireA1[0]} && wireB[1:0];"
    assert g.verilog_net_map == {'Y': 'wire[0]', 'A': "{1'b1, wireA1[0]}", 'B': 'wireB[1:0]'}

    _test_signal_conf2_arith(g, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.FLOATING, 0: Signal.FLOATING}, {1: Signal.FLOATING, 0: Signal.FLOATING}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.LOW}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.HIGH}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.LOW}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.LOW}, Signal.LOW)


def test_logic_or_gate(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import LogicOr

    g = LogicOr(raw_path='a.logic_or_inst', parameters={'A_WIDTH': 2}, module=simple_module)
    assert g.name == 'logic_or_inst'
    assert g.instance_type == '§logic_or'
    assert g.verilog_template == 'assign {out} = {in1} || {in2};'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    assert g.verilog == "assign wire[0] = {1'b1, wireA1[0]} || wireB[1:0];"

    _test_signal_conf2_arith(g, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.FLOATING, 0: Signal.FLOATING}, {1: Signal.FLOATING, 0: Signal.FLOATING}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.LOW}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.HIGH}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.LOW}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.LOW}, Signal.HIGH)


def test_lt_gate(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import LessThan

    g = LessThan(raw_path='a.lt_inst', parameters={'A_WIDTH': 2}, module=simple_module)
    assert g.name == 'lt_inst'
    assert g.instance_type == '§lt'
    assert g.verilog_template == 'assign {out} = {in1} < {in2};'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    assert g.verilog == "assign wire[0] = {1'b1, wireA1[0]} < wireB[1:0];"

    _test_signal_conf2_arith(g, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.FLOATING, 0: Signal.FLOATING}, {1: Signal.FLOATING, 0: Signal.FLOATING}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.LOW}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.HIGH}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.LOW}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.HIGH}, Signal.LOW)


def test_le_gate(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import LessEqual

    g = LessEqual(raw_path='a.le_inst', parameters={'A_WIDTH': 2}, module=simple_module)
    assert g.name == 'le_inst'
    assert g.instance_type == '§le'
    assert g.verilog_template == 'assign {out} = {in1} <= {in2};'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    assert g.verilog == "assign wire[0] = {1'b1, wireA1[0]} <= wireB[1:0];"

    _test_signal_conf2_arith(g, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.FLOATING, 0: Signal.FLOATING}, {1: Signal.FLOATING, 0: Signal.FLOATING}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.LOW}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.HIGH}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.LOW}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.HIGH}, Signal.LOW)


def test_eq_gate(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import Equal

    g = Equal(raw_path='a.eq_inst', parameters={'A_WIDTH': 2}, module=simple_module)
    assert g.name == 'eq_inst'
    assert g.instance_type == '§eq'
    assert g.verilog_template == 'assign {out} = {in1} == {in2};'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    assert g.verilog == "assign wire[0] = {1'b1, wireA1[0]} == wireB[1:0];"

    _test_signal_conf2_arith(g, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.FLOATING, 0: Signal.FLOATING}, {1: Signal.FLOATING, 0: Signal.FLOATING}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.LOW}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.HIGH}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.LOW}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.HIGH}, Signal.LOW)


def test_ne_gate(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import NotEqual

    g = NotEqual(raw_path='a.ne_inst', parameters={'A_WIDTH': 2}, module=simple_module)
    assert g.name == 'ne_inst'
    assert g.instance_type == '§ne'
    assert g.verilog_template == 'assign {out} = {in1} != {in2};'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    assert g.verilog == "assign wire[0] = {1'b1, wireA1[0]} != wireB[1:0];"

    _test_signal_conf2_arith(g, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.FLOATING, 0: Signal.FLOATING}, {1: Signal.FLOATING, 0: Signal.FLOATING}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.LOW}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.HIGH}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.LOW}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.HIGH}, Signal.HIGH)


def test_gt_gate(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import GreaterThan

    g = GreaterThan(raw_path='a.gt_inst', parameters={'A_WIDTH': 2}, module=simple_module)
    assert g.name == 'gt_inst'
    assert g.instance_type == '§gt'
    assert g.verilog_template == 'assign {out} = {in1} > {in2};'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    assert g.verilog == "assign wire[0] = {1'b1, wireA1[0]} > wireB[1:0];"

    _test_signal_conf2_arith(g, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.FLOATING, 0: Signal.FLOATING}, {1: Signal.FLOATING, 0: Signal.FLOATING}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.LOW}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.HIGH}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.LOW}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.HIGH}, Signal.HIGH)


def test_ge_gate(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import GreaterEqual

    g = GreaterEqual(raw_path='a.ge_inst', parameters={'A_WIDTH': 2}, module=simple_module)
    assert g.name == 'ge_inst'
    assert g.instance_type == '§ge'
    assert g.verilog_template == 'assign {out} = {in1} >= {in2};'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    assert g.verilog == "assign wire[0] = {1'b1, wireA1[0]} >= wireB[1:0];"

    _test_signal_conf2_arith(g, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.FLOATING, 0: Signal.FLOATING}, {1: Signal.FLOATING, 0: Signal.FLOATING}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.LOW}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.HIGH}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.LOW}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.HIGH}, Signal.HIGH)


def _init_mux_structure(m: Multiplexer) -> None:
    for i in range(8):
        m.modify_connection(f'D{i}', WireSegmentPath(raw=f'a.wmuxD_{i}.0'), index=0)
        # 2nd is missing on purpose: m.modify_connection(f'D{i}', WireSegmentPath(raw=f'a.wmuxD_{i}.1'), index=1)
        m.modify_connection(f'D{i}', WireSegmentPath(raw=f'a.wmuxD_{i}.2'), index=2)
        m.modify_connection(f'D{i}', WireSegmentPath(raw=f'a.wmuxD_{i}.3'), index=3)

    m.modify_connection('Y', WireSegmentPath(raw='a.wmuxY_1.0'), index=0)
    # 2nd is missing on purpose: m.modify_connection('Y', WireSegmentPath(raw='a.wmuxY_1.1'), index=1)
    m.modify_connection('Y', WireSegmentPath(raw='a.wmuxY_1.2'), index=2)
    m.modify_connection('Y', WireSegmentPath(raw='a.wmuxY_1.3'), index=3)

    for i in range(3):
        m.modify_connection('S', WireSegmentPath(raw=f'a.wmuxS.{i}'), index=i)


def test_mux_structure(simple_module: Module) -> None:
    m = Multiplexer(raw_path='a.mux_inst', parameters={'BIT_WIDTH': 3, 'WIDTH': 4}, module=simple_module)

    assert m.name == 'mux_inst'
    assert m.instance_type == '§mux'
    assert m.bit_width == 3
    assert len(m.d_ports) == 8
    assert m.s_port == m.ports['S']
    assert m.output_port == m.ports['Y']
    assert len(m.ports) == 8 + 1 + 1  # 8 data inputs, 1 control input (3-bit wide) and 1 output
    assert len(m.connections) == 8 + 1 + 1  # 8 inputs, 1 control input (3-bit wide) and 1 output
    assert 'D0' in m.ports
    assert 'D7' in m.ports
    assert 'D8' not in m.ports
    assert 'S' in m.ports
    assert 'Y' in m.ports
    assert m.ports['D0'].width == 4
    assert m.ports['S'].width == 3
    assert m.ports['Y'].width == 4
    assert not m.s_defined
    assert m.s_val == -1
    assert m.active_input is None
    assert m.verilog_template == 'always @(*) begin\n\tcase ({sel})\n{cases}\n\tendcase\nend'
    assert m.output_port.signal is Signal.UNDEFINED
    assert m.splittable

    _init_mux_structure(m)
    case_str = ''
    for i in range(8):
        case_str += f"\t\t3'b{format(i, '03b')} : " + '{wmuxY_1[3:2], wmuxY_1[0]} <= {' + f'wmuxD_{i}[3:2], wmuxD_{i}[0]' + '};\n'
    target_str = 'always @(*) begin\n\tcase (wmuxS)\n' + case_str + '\tendcase\nend'
    save_results(target_str + '\n\n\n' + m.verilog, 'txt')
    assert m.verilog == target_str
    assert m.verilog_net_map == {
        'Y': '{wmuxY_1[3:2], wmuxY_1[0]}',
        'S': 'wmuxS',
        'D0': '{wmuxD_0[3:2], wmuxD_0[0]}',
        'D1': '{wmuxD_1[3:2], wmuxD_1[0]}',
        'D2': '{wmuxD_2[3:2], wmuxD_2[0]}',
        'D3': '{wmuxD_3[3:2], wmuxD_3[0]}',
        'D4': '{wmuxD_4[3:2], wmuxD_4[0]}',
        'D5': '{wmuxD_5[3:2], wmuxD_5[0]}',
        'D6': '{wmuxD_6[3:2], wmuxD_6[0]}',
        'D7': '{wmuxD_7[3:2], wmuxD_7[0]}',
    }


def test_mux_split(simple_module: Module) -> None:
    m = Multiplexer(raw_path='a.mux_inst', parameters={'BIT_WIDTH': 3, 'WIDTH': 4}, module=simple_module)
    simple_module.add_instance(m)
    d0 = simple_module.create_port('D0', Direction.IN, width=4)
    d1 = simple_module.create_port('D1', Direction.IN, width=4)
    d2 = simple_module.create_port('D2', Direction.IN, width=4)
    d3 = simple_module.create_port('D3', Direction.IN, width=4)
    d4 = simple_module.create_port('D4', Direction.IN, width=4)
    d5 = simple_module.create_port('D5', Direction.IN, width=4)
    d6 = simple_module.create_port('D6', Direction.IN, width=4)
    d7 = simple_module.create_port('D7', Direction.IN, width=4)
    s = simple_module.create_port('S', Direction.OUT, width=3)
    y = simple_module.create_port('Y', Direction.OUT, width=4)
    simple_module.connect(d0, m.ports['D0'])
    simple_module.connect(d1, m.ports['D1'])
    simple_module.connect(d2, m.ports['D2'])
    simple_module.connect(d3, m.ports['D3'])
    simple_module.connect(d4, m.ports['D4'])
    simple_module.connect(d5, m.ports['D5'])
    simple_module.connect(d6, m.ports['D6'])
    simple_module.connect(d7, m.ports['D7'])
    simple_module.connect(s, m.ports['S'])
    simple_module.connect(m.ports['Y'], y)
    connections = m.connections
    assert m.splittable
    assert m.name in simple_module.instances
    splitted = m.split()
    assert m.name not in simple_module.instances
    assert len(splitted) == 4
    for idx, inst in splitted.items():
        assert inst.name in simple_module.instances
        assert inst.width == 1
        assert inst.ports['D0'].width == 1
        assert inst.ports['D7'].width == 1
        assert inst.ports['S'].width == 3
        assert inst.ports['Y'].width == 1
        assert inst.ports['D0'][0].ws_path == connections['D0'][idx]
        assert inst.ports['D7'][0].ws_path == connections['D7'][idx]
        assert inst.ports['S'][0].ws_path == connections['S'][0]
        assert inst.ports['S'][1].ws_path == connections['S'][1]
        assert inst.ports['S'][2].ws_path == connections['S'][2]
        assert inst.ports['Y'][0].ws_path == connections['Y'][idx]


def test_mux_behavior(simple_module: Module) -> None:
    m = Multiplexer(raw_path='a.mux_inst', parameters={'BIT_WIDTH': 3, 'WIDTH': 4}, module=simple_module)
    _init_mux_structure(m)

    # Select Ports
    m.ports['S'].set_signal(Signal.HIGH, 0)  # 1 => 1
    m.ports['S'].set_signal(Signal.HIGH, 1)  # 2 => 1
    m.ports['S'].set_signal(Signal.LOW, 2)  # 4 => 0

    assert m.s_defined
    assert m.s_val == 3  # S_0 + S_1 = 1 + 2 => s_val = 3
    assert m.active_input == m.ports['D3']
    m.evaluate()
    assert m.output_port.signal is Signal.UNDEFINED

    for i in range(8):
        m.modify_connection(f'D{i}', WireSegmentPath(raw=f'a.wmuxD{i}.1'), index=1)
    m.modify_connection('Y', WireSegmentPath(raw='a.wmuxY_1.1'), index=1)

    # Data Ports
    m.ports['D0'].set_signal(Signal.HIGH)
    m.ports['D1'].set_signal(Signal.LOW, index=1)
    m.ports['D2'].set_signal(Signal.FLOATING, index=2)

    # Change S
    m.ports['S'].set_signal(Signal.LOW, 1)  # => s_val = 1
    assert m.active_input == m.ports['D1']
    m.evaluate()
    assert m.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.LOW, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    m.ports['S'].set_signal(Signal.LOW, 0)  # => s_val = 0
    assert m.active_input == m.ports['D0']
    m.evaluate()
    assert m.output_port.signal_array == {0: Signal.HIGH, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    m.ports['S'].set_signal(Signal.HIGH, 1)  # => s_val = 2
    assert m.active_input == m.ports['D2']
    m.evaluate()
    assert m.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}


def _init_demux_structure(d: Demultiplexer) -> None:
    for i in range(8):
        d.modify_connection(f'Y{i}', WireSegmentPath(raw=f'a.wmuxY_{i}.0'), index=0)
        # 2nd is missing on purpose: d.modify_connection(f'Y{i}', WireSegmentPath(raw=f'a.wmuxY_{i}.1'), index=1)
        d.modify_connection(f'Y{i}', WireSegmentPath(raw=f'a.wmuxY_{i}.2'), index=2)
        d.modify_connection(f'Y{i}', WireSegmentPath(raw=f'a.wmuxY_{i}.3'), index=3)

    d.modify_connection('D', WireSegmentPath(raw='a.wmuxD_1.0'), index=0)
    # 2nd is missing on purpose: d.modify_connection('D', WireSegmentPath(raw='a.wmuxD_1.1'), index=1)
    d.modify_connection('D', WireSegmentPath(raw='a.wmuxD_1.2'), index=2)
    d.modify_connection('D', WireSegmentPath(raw='a.wmuxD_1.3'), index=3)

    for i in range(3):
        d.modify_connection('S', WireSegmentPath(raw=f'a.wmuxS.{i}'), index=i)


def test_demux_structure(simple_module: Module) -> None:
    d = Demultiplexer(raw_path='a.demux_inst', parameters={'BIT_WIDTH': 3, 'WIDTH': 4}, module=simple_module)

    assert d.name == 'demux_inst'
    assert d.instance_type == '§demux'
    assert d.bit_width == 3
    assert len(d.y_ports) == 8
    assert d.s_port == d.ports['S']
    assert d.input_port == d.ports['D']
    assert len(d.ports) == 8 + 1 + 1  # 8 data outputs, 1 control input (3-bit wide) and 1 input
    assert len(d.connections) == 8 + 1 + 1  # 8 outputs, 1 control input (3-bit wide) and 1 input
    assert 'Y0' in d.ports
    assert 'Y7' in d.ports
    assert 'Y8' not in d.ports
    assert 'S' in d.ports
    assert 'D' in d.ports
    assert d.ports['Y0'].width == 4
    assert d.ports['S'].width == 3
    assert d.ports['D'].width == 4
    assert not d.s_defined
    assert d.s_val == -1
    assert d.active_output is None
    assert d.verilog_template == 'always @(*) begin\n\tcase ({sel})\n{cases}\n\tendcase\nend'
    assert d.input_port.signal is Signal.UNDEFINED
    assert d.splittable
    with pytest.raises(NotImplementedError):
        d.output_port.signal

    _init_demux_structure(d)
    case_str = ''
    for i in range(8):
        case_str += f"\t\t3'b{format(i, '03b')} : " + '{' + f'wmuxY_{i}[3:2], wmuxY_{i}[0]' + '} <= {wmuxD_1[3:2], wmuxD_1[0]};\n'
    target_str = 'always @(*) begin\n\tcase (wmuxS)\n' + case_str + '\tendcase\nend'
    save_results(target_str + '\n\n\n' + d.verilog, 'txt')
    assert d.verilog == target_str
    assert d.verilog_net_map == {
        'D': '{wmuxD_1[3:2], wmuxD_1[0]}',
        'S': 'wmuxS',
        'Y0': '{wmuxY_0[3:2], wmuxY_0[0]}',
        'Y1': '{wmuxY_1[3:2], wmuxY_1[0]}',
        'Y2': '{wmuxY_2[3:2], wmuxY_2[0]}',
        'Y3': '{wmuxY_3[3:2], wmuxY_3[0]}',
        'Y4': '{wmuxY_4[3:2], wmuxY_4[0]}',
        'Y5': '{wmuxY_5[3:2], wmuxY_5[0]}',
        'Y6': '{wmuxY_6[3:2], wmuxY_6[0]}',
        'Y7': '{wmuxY_7[3:2], wmuxY_7[0]}',
    }


def test_demux_split(simple_module: Module) -> None:
    dm = Demultiplexer(raw_path='a.mux_inst', parameters={'BIT_WIDTH': 3, 'WIDTH': 4}, module=simple_module)
    simple_module.add_instance(dm)
    d = simple_module.create_port('D', Direction.OUT, width=4)
    s = simple_module.create_port('S', Direction.OUT, width=3)
    y0 = simple_module.create_port('Y0', Direction.OUT, width=4)
    y1 = simple_module.create_port('Y1', Direction.OUT, width=4)
    y2 = simple_module.create_port('Y2', Direction.OUT, width=4)
    y3 = simple_module.create_port('Y3', Direction.OUT, width=4)
    y4 = simple_module.create_port('Y4', Direction.OUT, width=4)
    y5 = simple_module.create_port('Y5', Direction.OUT, width=4)
    y6 = simple_module.create_port('Y6', Direction.OUT, width=4)
    y7 = simple_module.create_port('Y7', Direction.OUT, width=4)
    simple_module.connect(d, dm.ports['D'])
    simple_module.connect(s, dm.ports['S'])
    simple_module.connect(dm.ports['Y0'], y0)
    simple_module.connect(dm.ports['Y1'], y1)
    simple_module.connect(dm.ports['Y2'], y2)
    simple_module.connect(dm.ports['Y3'], y3)
    simple_module.connect(dm.ports['Y4'], y4)
    simple_module.connect(dm.ports['Y5'], y5)
    simple_module.connect(dm.ports['Y6'], y6)
    simple_module.connect(dm.ports['Y7'], y7)
    connections = dm.connections
    assert dm.splittable
    assert dm.name in simple_module.instances
    splitted = dm.split()
    assert dm.name not in simple_module.instances
    assert len(splitted) == 4
    for idx, inst in splitted.items():
        assert inst.name in simple_module.instances
        assert inst.width == 1
        assert inst.ports['D'].width == 1
        assert inst.ports['S'].width == 3
        assert inst.ports['Y0'].width == 1
        assert inst.ports['Y7'].width == 1
        assert inst.ports['D'][0].ws_path == connections['D'][idx]
        assert inst.ports['S'][0].ws_path == connections['S'][0]
        assert inst.ports['S'][1].ws_path == connections['S'][1]
        assert inst.ports['S'][2].ws_path == connections['S'][2]
        assert inst.ports['Y0'][0].ws_path == connections['Y0'][idx]
        assert inst.ports['Y7'][0].ws_path == connections['Y7'][idx]


def test_demux_behavior(simple_module: Module) -> None:
    d = Demultiplexer(raw_path='a.demux_inst', parameters={'BIT_WIDTH': 3, 'WIDTH': 4}, module=simple_module)
    _init_demux_structure(d)

    # Select Ports
    d.ports['S'].set_signal(Signal.HIGH, 0)  # 1 => 1
    d.ports['S'].set_signal(Signal.HIGH, 1)  # 2 => 1
    d.ports['S'].set_signal(Signal.LOW, 2)  # 4 => 0

    assert d.s_defined
    assert d.s_val == 3  # S_0 + S_1 = 1 + 2 => s_val = 3
    assert d.active_output == d.ports['Y3']
    d.evaluate()
    with pytest.raises(NotImplementedError):
        d.output_port

    d.ports['D'].set_signal(Signal.HIGH)

    # Change S
    d.ports['S'].set_signal(Signal.LOW, 1)  # => s_val = 1
    assert d.active_output == d.ports['Y1']
    assert d.ports['Y1'].signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    d.evaluate()
    assert d.ports['Y0'].signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    assert d.ports['Y1'].signal_array == {0: Signal.HIGH, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    assert d.ports['Y2'].signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    d.ports['S'].set_signal(Signal.LOW, 0)  # => s_val = 0
    assert d.active_output == d.ports['Y0']
    assert d.ports['Y0'].signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    d.evaluate()
    assert d.ports['Y0'].signal_array == {0: Signal.HIGH, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    assert d.ports['Y1'].signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    assert d.ports['Y2'].signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    d.ports['S'].set_signal(Signal.HIGH, 1)  # => s_val = 2
    assert d.active_output == d.ports['Y2']
    assert d.ports['Y2'].signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    d.evaluate()
    assert d.ports['Y0'].signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    assert d.ports['Y1'].signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    assert d.ports['Y2'].signal_array == {0: Signal.HIGH, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}


def test_adder_structure(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import Adder

    a = Adder(raw_path='a.adder_inst', parameters={'Y_WIDTH': 4}, module=simple_module)

    assert 'A' in a.ports
    assert 'B' in a.ports
    assert 'Y' in a.ports
    assert a.ports['A'].width == 4
    assert a.ports['B'].width == 4
    assert a.ports['Y'].width == 4
    assert a.input_ports == (a.ports['A'], a.ports['B'])
    assert a.output_port == a.ports['Y']
    assert a.verilog_template == 'assign {out} = {in1} + {in2};'
    a.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    a.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: a.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    a.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    a.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    a.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)
    # 2nd is missing on purpose: a.modify_connection('B', WireSegmentPath(raw='a.wireB.2'), index=2)
    a.modify_connection('B', WireSegmentPath(raw='a.wireB.3'), index=3)

    a.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    a.modify_connection('Y', WireSegmentPath(raw='a.wire.1'), index=1)
    # 2nd is missing on purpose: a.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    a.modify_connection('Y', WireSegmentPath(raw='a.wire.3'), index=3)
    a.modify_connection('Y', WireSegmentPath(raw='a.carry.0'), index=4)
    assert a.ports['Y'].width == 5
    with pytest.raises(ValueError):
        a.verilog
    a.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    target_str = "assign {carry, wire} = {wireA2, 2'bx1, wireA1[0]} + {wireB[3], 1'bx, wireB[1:0]};"
    assert a.verilog == target_str

    with pytest.raises(EvaluationError):
        a._calc_output()

    a.ports['A'].parameters['signed'] = '0'
    a.ports['B'].parameters['signed'] = '1'
    assert a.sync_parameters() == {'A_WIDTH': 4, 'A_SIGNED': False, 'B_WIDTH': 4, 'B_SIGNED': True, 'Y_WIDTH': 5}
    assert not a.splittable

    a.disconnect('Y', 4)
    a.disconnect('Y', 3)
    assert a.verilog == "assign wire[2:0] = {2'bx1, wireA1[0]} + $signed({1'bx, wireB[1:0]});"
    assert a.verilog_net_map == {'Y': 'wire[2:0]', 'A': "{2'bx1, wireA1[0]}", 'B': "{1'bx, wireB[1:0]}"}


def test_adder_behavior(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import Adder

    a = Adder(raw_path='a.adder_inst', parameters={'Y_WIDTH': 4}, module=simple_module)

    a.tie_port('A', 0, '0')
    a.tie_port('A', 1, '0')
    a.tie_port('A', 2, '0')
    a.tie_port('A', 3, '0')
    a.tie_port('B', 0, '0')
    a.tie_port('B', 1, '1')
    a.tie_port('B', 2, '1')
    a.tie_port('B', 3, '0')
    assert a.ports['Y'].width == 4

    a.evaluate()  # 0 + 6 = 6
    assert a.output_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.LOW}
    a.tie_port('A', 2, '1')
    a.tie_port('A', 3, '1')
    a.evaluate()  # 12 + 6 = 18 (but no carry => 10010 ==> 0010 => 2)
    assert a.output_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.LOW, 3: Signal.LOW}  # 4: Signal.HIGH

    # Add fifth output connection
    a.modify_connection('Y', WireSegmentPath(raw='a.carry.0'), index=4)
    a.evaluate()  # 12 + 6 = 18
    assert a.output_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.LOW, 3: Signal.LOW, 4: Signal.HIGH}

    a.parameters['B_SIGNED'] = True
    a.tie_port('B', 0, '0')
    a.tie_port('B', 1, '1')
    a.tie_port('B', 2, '0')
    a.tie_port('B', 3, '1')  # 1010 in two's complement: -6
    a.evaluate()  # 12 + (-6) = 6
    assert a.output_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.LOW, 4: Signal.LOW}
    a.tie_port('A', 3, 'Z')
    with pytest.raises(EvaluationError):
        a.evaluate()


def test_subtractor_structure(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import Subtractor

    s = Subtractor(raw_path='a.subtractor_inst', parameters={'Y_WIDTH': 4}, module=simple_module)

    assert 'A' in s.ports
    assert 'B' in s.ports
    assert 'Y' in s.ports
    assert s.ports['A'].width == 4
    assert s.ports['B'].width == 4
    assert s.ports['Y'].width == 4
    assert s.input_ports == (s.ports['A'], s.ports['B'])
    assert s.output_port == s.ports['Y']
    assert s.verilog_template == 'assign {out} = {in1} - {in2};'
    s.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    s.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: a.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    s.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    s.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    s.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)
    # 2nd is missing on purpose: a.modify_connection('B', WireSegmentPath(raw='a.wireB.2'), index=2)
    s.modify_connection('B', WireSegmentPath(raw='a.wireB.3'), index=3)

    s.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    s.modify_connection('Y', WireSegmentPath(raw='a.wire.1'), index=1)
    # 2nd is missing on purpose: a.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    s.modify_connection('Y', WireSegmentPath(raw='a.wire.3'), index=3)
    with pytest.raises(ValueError):
        s.verilog
    s.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    target_str = "assign wire = {wireA2, 2'bx1, wireA1[0]} - {wireB[3], 1'bx, wireB[1:0]};"
    assert s.verilog == target_str


def test_subtractor_behavior(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import Subtractor

    s = Subtractor(raw_path='a.subtractor_inst', parameters={'Y_WIDTH': 4}, module=simple_module)

    s.tie_port('A', 0, '0')
    s.tie_port('A', 1, '0')
    s.tie_port('A', 2, '1')
    s.tie_port('A', 3, '1')
    s.tie_port('B', 0, '0')
    s.tie_port('B', 1, '1')
    s.tie_port('B', 2, '1')
    s.tie_port('B', 3, '0')
    assert s.ports['Y'].width == 4

    s.evaluate()  # 12 - 6 = 6
    assert s.output_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.LOW}
    s.tie_port('B', 3, '1')
    s.evaluate()  # 12 - 14 = -2 (but no carry and unsigned: -2 = 11110 ==> 1110 => 14)
    assert s.output_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.HIGH}  # 4: Signal.HIGH

    # Add fifth output connection
    s.modify_connection('Y', WireSegmentPath(raw='a.carry.0'), index=4)
    s.evaluate()
    assert s.output_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.HIGH, 4: Signal.HIGH}
    s.parameters['B_SIGNED'] = True
    s.tie_port('B', 0, '1')
    s.tie_port('B', 1, '0')
    s.tie_port('B', 2, '1')
    s.tie_port('B', 3, '1')  # 1101 in two's complement: -3
    s.evaluate()  # 12 - (-3) = 15 ==> 01111
    assert s.output_port.signal_array == {0: Signal.HIGH, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.HIGH, 4: Signal.LOW}
    s.tie_port('A', 3, 'Z')
    with pytest.raises(EvaluationError):
        s.evaluate()


def test_multiplier_structure(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import Multiplier

    m = Multiplier(raw_path='a.multiplier_inst', parameters={'Y_WIDTH': 4}, module=simple_module)

    assert 'A' in m.ports
    assert 'B' in m.ports
    assert 'Y' in m.ports
    assert m.ports['A'].width == 4
    assert m.ports['B'].width == 4
    assert m.ports['Y'].width == 4
    assert m.input_ports == (m.ports['A'], m.ports['B'])
    assert m.output_port == m.ports['Y']
    assert m.verilog_template == 'assign {out} = {in1} * {in2};'
    m.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    m.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: a.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    m.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    m.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    m.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)
    # 2nd is missing on purpose: a.modify_connection('B', WireSegmentPath(raw='a.wireB.2'), index=2)
    m.modify_connection('B', WireSegmentPath(raw='a.wireB.3'), index=3)

    m.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    m.modify_connection('Y', WireSegmentPath(raw='a.wire.1'), index=1)
    # 2nd is missing on purpose: a.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    m.modify_connection('Y', WireSegmentPath(raw='a.wire.3'), index=3)
    m.modify_connection('Y', WireSegmentPath(raw='a.carry.0'), index=4)
    assert m.ports['Y'].width == 5
    with pytest.raises(ValueError):
        m.verilog
    m.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    target_str = "assign {carry, wire} = {wireA2, 2'bx1, wireA1[0]} * {wireB[3], 1'bx, wireB[1:0]};"
    assert m.verilog == target_str


def test_multiplier_behavior(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import Multiplier

    m = Multiplier(raw_path='a.multiplier_inst', parameters={'Y_WIDTH': 4}, module=simple_module)

    m.tie_port('A', 0, '0')
    m.tie_port('A', 1, '0')
    m.tie_port('A', 2, '0')
    m.tie_port('A', 3, '0')
    m.tie_port('B', 0, '0')
    m.tie_port('B', 1, '1')
    m.tie_port('B', 2, '1')
    m.tie_port('B', 3, '0')
    assert m.ports['Y'].width == 4

    m.evaluate()  # 0 * 6 = 0
    assert m.output_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW}
    m.tie_port('A', 2, '1')
    m.evaluate()  # 4 * 6 = 24 (but no carry => 11000 ==> 1000 => 16)
    assert m.output_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.HIGH}  # 4: Signal.HIGH

    # Add fifth output connection
    m.modify_connection('Y', WireSegmentPath(raw='a.carry.0'), index=4)
    m.evaluate()
    assert m.output_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.HIGH, 4: Signal.HIGH}
    m.ports['B'].set_signed(True)
    m.tie_port('B', 0, '1')
    m.tie_port('B', 1, '0')
    m.tie_port('B', 2, '1')
    m.tie_port('B', 3, '1')  # 1101 in two's complement: -3
    m.evaluate()  # 4 * (-3) = -12 ==> 10100 in two's complement
    assert m.output_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.HIGH, 3: Signal.LOW, 4: Signal.HIGH}
    m.tie_port('A', 3, 'Z')
    with pytest.raises(EvaluationError):
        m.evaluate()


def test_clocked_gate(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import ClkMixin

    g = ClkMixin(
        instance_type='clocked_gate',
        raw_path='a.clocked_gate_inst',
        parameters={'CLK_POLARITY': Signal.LOW, 'RST_POLARITY': Signal.LOW},
        module=simple_module,
    )

    assert g.name == 'clocked_gate_inst'
    assert g.instance_type == 'clocked_gate'
    assert g.clk_polarity is Signal.LOW
    assert 'CLK' in g.ports
    assert g.ports['CLK'].is_input
    assert g.ports['CLK'] is g.clk_port
    assert g.clk_port.width == 1
    assert g.clk_port.signal is Signal.FLOATING
    assert not g.is_combinational
    assert g.is_sequential
    assert g.splittable


def test_clocked_gate_split(simple_module: Module) -> None:
    dff = ADFFE(
        instance_type='clocked_gate',
        raw_path='a.clocked_gate_inst',
        parameters={'CLK_POLARITY': Signal.LOW, 'RST_POLARITY': Signal.LOW, 'WIDTH': 8},
        module=simple_module,
    )
    simple_module.add_instance(dff)
    d = simple_module.create_port('D', Direction.IN, width=8)
    q = simple_module.create_port('Q', Direction.OUT, width=8)
    clk = simple_module.create_port('clk', Direction.OUT)
    rst = simple_module.create_port('rst', Direction.OUT)
    en = simple_module.create_port('en', Direction.OUT)
    simple_module.connect(d, dff.ports['D'])
    simple_module.connect(clk, dff.ports['CLK'])
    simple_module.connect(rst, dff.ports['RST'])
    simple_module.connect(en, dff.ports['EN'])
    simple_module.connect(dff.ports['Q'], q)
    connections = dff.connections
    assert dff.splittable
    assert dff.name in simple_module.instances
    splitted = dff.split()
    assert dff.name not in simple_module.instances
    assert len(splitted) == 8
    for idx, inst in splitted.items():
        assert inst.name in simple_module.instances
        assert inst.width == 1
        assert inst.ports['D'].width == 1
        assert inst.ports['CLK'].width == 1
        assert inst.ports['RST'].width == 1
        assert inst.ports['EN'].width == 1
        assert inst.ports['Q'].width == 1
        assert inst.ports['D'][0].ws_path == connections['D'][idx]
        assert inst.ports['CLK'][0].ws_path == connections['CLK'][0]
        assert inst.ports['RST'][0].ws_path == connections['RST'][0]
        assert inst.ports['EN'][0].ws_path == connections['EN'][0]
        assert inst.ports['Q'][0].ws_path == connections['Q'][idx]


def _init_dff_structure(ff: DFF, init_rst_en: bool = False, init_all_in: bool = False) -> None:
    ff.modify_connection('D', WireSegmentPath(raw='a.wireA1.0'), index=0)
    ff.tie_port('D', index=1, sig_value='1')
    # 2nd is missing on purpose: ff.modify_connection('D', WireSegmentPath(raw='a.wireA1.2'), index=2)
    ff.modify_connection('D', WireSegmentPath(raw='a.wireA2.0'), index=3)

    ff.modify_connection('Q', WireSegmentPath(raw='a.wire.0'), index=0)
    ff.modify_connection('Q', WireSegmentPath(raw='a.wire.1'), index=1)
    ff.modify_connection('Q', WireSegmentPath(raw='a.wire.2'), index=2)
    ff.modify_connection('Q', WireSegmentPath(raw='a.wire.3'), index=3)

    ff.modify_connection('CLK', WireSegmentPath(raw='a.clk.0'))

    if init_all_in:
        ff.modify_connection('D', WireSegmentPath(raw='a.wireA1.1'), index=1)
        ff.modify_connection('D', WireSegmentPath(raw='a.wireA1.2'), index=2)

    if init_rst_en:
        ff.modify_connection('RST', WireSegmentPath(raw='a.rst.0'))
        ff.modify_connection('EN', WireSegmentPath(raw='a.en.0'))


def _clk(ff: DFF, cycles: int = 1) -> None:
    for i in range(cycles):
        ff.set_clk(Signal.HIGH)
        assert ff.clk_port.signal is Signal.HIGH
        ff.set_clk(Signal.LOW)
        assert ff.clk_port.signal is Signal.LOW


def test_dff_structure(simple_module: Module) -> None:
    ff = DFF(raw_path='a.dff_inst', parameters={'WIDTH': 4, 'ARST_POLARITY': Signal.LOW}, module=simple_module)

    assert ff.name == 'dff_inst'
    assert ff.instance_type == '§dff'
    assert ff.clk_polarity is Signal.HIGH

    assert len(ff.ports) == 3
    assert 'D' in ff.ports
    assert 'CLK' in ff.ports
    assert 'Q' in ff.ports
    assert ff.ports['D'].is_input
    assert ff.ports['CLK'].is_input
    assert ff.ports['Q'].is_output
    assert ff.input_port == ff.ports['D']
    assert ff.clk_port == ff.ports['CLK']
    assert ff.output_port == ff.ports['Q']
    assert ff.output_port.signal is Signal.UNDEFINED
    assert ff.input_port.width == 4
    assert ff.clk_port.width == 1
    assert ff.output_port.width == 4
    assert list(range(4)) == list(ff.input_port.segments.keys())
    assert list(range(4)) == list(ff.output_port.segments.keys())
    assert ff.scan_ff_equivalent == ScanDFF
    assert ff.verilog_template == 'always @({header}) begin\n\t{set_out}\nend'

    _init_dff_structure(ff)
    target_v = "always @(posedge clk) begin\n\twire\t<=\t{wireA2, 2'bx1, wireA1[0]};\nend"
    save_results(ff.verilog, 'txt')
    assert ff.verilog == target_v
    assert ff.verilog_net_map == {'D': "{wireA2, 2'bx1, wireA1[0]}", 'Q': 'wire', 'CLK': 'clk'}


def test_dff_behaviour(simple_module: Module) -> None:
    ff = DFF(raw_path='a.dff_inst', parameters={'WIDTH': 4}, module=simple_module)
    _init_dff_structure(ff, init_all_in=True)
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    ff.input_port.set_signals('01xz')
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}


def test_dff_to_scan(simple_module: Module) -> None:
    ff = DFF(raw_path='a.dff_inst', parameters={'WIDTH': 4}, module=simple_module)

    scan_ff = ff.get_scanff()
    assert scan_ff.name == 'dff_inst_scan'
    assert scan_ff.parameters == ff.parameters


def test_adff_structure(simple_module: Module) -> None:
    ff = ADFF(raw_path='a.dff_inst', parameters={'WIDTH': 4, 'ARST_POLARITY': Signal.LOW}, module=simple_module)

    assert ff.name == 'dff_inst'
    assert ff.instance_type == '§adff'
    assert ff.clk_polarity is Signal.HIGH
    assert ff.rst_polarity is Signal.LOW

    assert len(ff.ports) == 4
    assert 'D' in ff.ports
    assert 'CLK' in ff.ports
    assert 'RST' in ff.ports
    assert 'Q' in ff.ports
    assert ff.ports['D'].is_input
    assert ff.ports['CLK'].is_input
    assert ff.ports['RST'].is_input
    assert ff.ports['Q'].is_output
    assert ff.input_port == ff.ports['D']
    assert ff.clk_port == ff.ports['CLK']
    assert ff.rst_port == ff.ports['RST']
    assert ff.output_port == ff.ports['Q']
    assert ff.output_port.signal is Signal.UNDEFINED
    assert ff.input_port.width == 4
    assert ff.clk_port.width == 1
    assert ff.rst_port.width == 1
    assert ff.output_port.width == 4
    assert list(range(4)) == list(ff.input_port.segments.keys())
    assert list(range(4)) == list(ff.output_port.segments.keys())
    assert ff.scan_ff_equivalent == ScanADFF
    assert ff.verilog_template == 'always @({header}) begin\n\tif ({is_rst}) begin\n\t\t{rst_out}\n\tend else begin\n\t\t{set_out}\n\tend\nend'

    _init_dff_structure(ff)
    ff.modify_connection('RST', WireSegmentPath(raw='a.rst.0'))
    target_v = "always @(posedge clk or negedge rst) begin\n\tif (~rst) begin\n\t\twire\t<=\t4'b0000;\n\tend else begin\n\t\twire\t<=\t{wireA2, 2'bx1, wireA1[0]};\n\tend\nend"
    save_results(ff.verilog, 'txt')
    assert ff.verilog == target_v
    assert ff.verilog_net_map == {'D': "{wireA2, 2'bx1, wireA1[0]}", 'Q': 'wire', 'CLK': 'clk', 'RST': 'rst'}


def test_adff_behaviour(simple_module: Module) -> None:
    ff = ADFF(raw_path='a.dff_inst', parameters={'WIDTH': 4}, module=simple_module)
    _init_dff_structure(ff, init_all_in=True)
    ff.modify_connection('RST', WireSegmentPath(raw='a.rst.0'))
    assert ff.rst_polarity is Signal.HIGH
    assert ff.rst_val_int == 0
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    ff.set_rst(Signal.LOW)
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    ff.set_rst(Signal.HIGH)
    assert ff.output_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW}
    ff.input_port.set_signals('01xz')
    assert ff.output_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW}
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW}
    ff.set_rst(Signal.LOW)
    assert ff.output_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW}
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}


def test_dffe_structure(simple_module: Module) -> None:
    ff = DFFE(raw_path='a.dff_inst', parameters={'WIDTH': 4, 'ARST_POLARITY': Signal.LOW}, module=simple_module)

    assert ff.name == 'dff_inst'
    assert ff.instance_type == '§dffe'
    assert ff.clk_polarity is Signal.HIGH

    assert len(ff.ports) == 4
    assert 'D' in ff.ports
    assert 'CLK' in ff.ports
    assert 'EN' in ff.ports
    assert 'Q' in ff.ports
    assert ff.ports['D'].is_input
    assert ff.ports['CLK'].is_input
    assert ff.ports['EN'].is_input
    assert ff.ports['Q'].is_output
    assert ff.input_port == ff.ports['D']
    assert ff.clk_port == ff.ports['CLK']
    assert ff.en_port == ff.ports['EN']
    assert ff.output_port == ff.ports['Q']
    assert ff.output_port.signal is Signal.UNDEFINED
    assert ff.input_port.width == 4
    assert ff.clk_port.width == 1
    assert ff.en_port.width == 1
    assert ff.output_port.width == 4
    assert list(range(4)) == list(ff.input_port.segments.keys())
    assert list(range(4)) == list(ff.output_port.segments.keys())
    assert ff.scan_ff_equivalent == ScanDFFE
    assert ff.verilog_template == 'always @({header}) begin\n\tif ({en}) begin\n\t\t{set_out}\n\tend\nend'

    _init_dff_structure(ff)
    ff.modify_connection('EN', WireSegmentPath(raw='a.en.0'))
    target_v = "always @(posedge clk) begin\n\tif (en) begin\n\t\twire\t<=\t{wireA2, 2'bx1, wireA1[0]};\n\tend\nend"
    save_results(ff.verilog, 'txt')
    assert ff.verilog == target_v


def test_dffe_behaviour(simple_module: Module) -> None:
    ff = DFFE(raw_path='a.dff_inst', parameters={'WIDTH': 4}, module=simple_module)
    _init_dff_structure(ff, init_all_in=True)
    ff.modify_connection('EN', WireSegmentPath(raw='a.en.0'))
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    ff.input_port.set_signals('01xz')
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    ff.set_en(Signal.HIGH)
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}


def test_adffe_structure(simple_module: Module) -> None:
    ff = ADFFE(raw_path='a.dff_inst', parameters={'WIDTH': 4, 'ARST_POLARITY': Signal.LOW}, module=simple_module)

    assert ff.name == 'dff_inst'
    assert ff.instance_type == '§adffe'
    assert ff.clk_polarity is Signal.HIGH
    assert ff.en_polarity is Signal.HIGH
    assert ff.rst_polarity is Signal.LOW
    assert ff.rst_val == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW}

    assert len(ff.ports) == 5
    assert 'D' in ff.ports
    assert 'CLK' in ff.ports
    assert 'EN' in ff.ports
    assert 'RST' in ff.ports
    assert 'Q' in ff.ports
    assert ff.ports['D'].is_input
    assert ff.ports['CLK'].is_input
    assert ff.ports['EN'].is_input
    assert ff.ports['RST'].is_input
    assert ff.ports['Q'].is_output
    assert ff.input_port == ff.ports['D']
    assert ff.clk_port == ff.ports['CLK']
    assert ff.en_port == ff.ports['EN']
    assert ff.rst_port == ff.ports['RST']
    assert ff.output_port == ff.ports['Q']
    assert ff.output_port.signal is Signal.UNDEFINED
    assert ff.input_port.width == 4
    assert ff.clk_port.width == 1
    assert ff.en_port.width == 1
    assert ff.rst_port.width == 1
    assert ff.output_port.width == 4
    assert list(range(4)) == list(ff.input_port.segments.keys())
    assert list(range(4)) == list(ff.output_port.segments.keys())
    assert ff.scan_ff_equivalent == ScanADFFE

    _init_dff_structure(ff, True)
    save_results(ff.verilog, 'txt')
    assert (
        ff.verilog_template == 'always @({header}) begin\n\tif ({is_rst}) begin\n\t\t{rst_out}\n\tend else if ({en}) begin\n\t\t{set_out}\n\tend\nend'
    )
    target_v = "always @(posedge clk or negedge rst) begin\n\tif (~rst) begin\n\t\twire\t<=\t4'b0000;\n\tend else if (en) begin\n\t\twire\t<=\t{wireA2, 2'bx1, wireA1[0]};\n\tend\nend"
    assert ff.verilog == target_v
    assert ff.verilog_net_map == {'D': "{wireA2, 2'bx1, wireA1[0]}", 'Q': 'wire', 'CLK': 'clk', 'RST': 'rst', 'EN': 'en'}


def test_adffe_behavior_init(simple_module: Module) -> None:
    ff = ADFFE(raw_path='a.dff_inst', parameters={'WIDTH': 4}, module=simple_module)
    _init_dff_structure(ff, True, True)

    assert not ff.in_reset
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    _clk(ff)
    ff.set_rst(Signal.HIGH)
    assert ff.in_reset
    assert ff.output_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW}
    _clk(ff)
    ff.set_rst(Signal.LOW)
    assert not ff.in_reset
    assert ff.output_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW}
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    _clk(ff)
    ff.rst_val_int = 0xF
    ff.set_rst(Signal.HIGH)
    assert ff.in_reset
    assert ff.output_port.signal_array == {0: Signal.HIGH, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.HIGH}
    _clk(ff)
    ff.set_rst(Signal.LOW)
    assert not ff.in_reset
    assert ff.output_port.signal_array == {0: Signal.HIGH, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.HIGH}


def test_adffe_behavior_clk(simple_module: Module) -> None:
    ff = ADFFE(raw_path='a.dff_inst', parameters={'WIDTH': 4}, module=simple_module)
    _init_dff_structure(ff, True, True)

    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    _clk(ff)
    ff.set_rst(Signal.HIGH)
    _clk(ff)
    ff.set_rst(Signal.LOW)
    assert ff.output_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW}
    ff.set_en(Signal.HIGH)

    ff.input_port.set_signal(Signal.HIGH)
    ff.input_port.set_signal(Signal.HIGH, index=1)
    assert ff.output_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW}
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.HIGH, 1: Signal.HIGH, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}

    ff.input_port.set_signal(Signal.LOW, index=1)
    assert ff.output_port.signal_array == {0: Signal.HIGH, 1: Signal.HIGH, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.HIGH, 1: Signal.LOW, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}


def test_adffe_behavior_4bit(simple_module: Module) -> None:
    ff = ADFFE(raw_path='a.dff_inst', parameters={'WIDTH': 4}, module=simple_module)
    _init_dff_structure(ff, True, True)

    assert ff.output_port.signal is Signal.UNDEFINED
    _clk(ff)
    ff.set_rst(Signal.HIGH)
    _clk(ff)
    ff.set_rst(Signal.LOW)
    assert ff.output_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW}
    ff.set_en(Signal.HIGH)

    # Set first bit, others are still undefined
    ff.input_port.set_signal(Signal.HIGH)
    assert ff.output_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW}
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.HIGH, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}

    ff.input_port.set_signal(Signal.LOW)
    ff.input_port.set_signal(Signal.HIGH, index=1)
    ff.input_port.set_signal(Signal.HIGH, index=2)
    ff.input_port.set_signal(Signal.HIGH, index=3)
    assert ff.output_port.signal_array == {0: Signal.HIGH, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.HIGH}


def test_adffe_behavior_en(simple_module: Module) -> None:
    ff = ADFFE(raw_path='a.dff_inst', module=simple_module)
    ff.modify_connection('D', WireSegmentPath(raw='a.wireA1.0'), index=0)
    ff.modify_connection('Q', WireSegmentPath(raw='a.wire.0'), index=0)
    ff.modify_connection('CLK', WireSegmentPath(raw='a.clk.0'))
    ff.modify_connection('RST', WireSegmentPath(raw='a.rst.0'))
    ff.modify_connection('EN', WireSegmentPath(raw='a.enable_signal.0'))

    assert ff.output_port.signal is Signal.UNDEFINED

    # Reset
    _clk(ff)
    ff.set_rst(Signal.HIGH)
    _clk(ff)
    ff.set_rst(Signal.LOW)
    _clk(ff)
    assert ff.output_port.signal is Signal.UNDEFINED

    # EN Unconnected -> Undefined enable signal -> do not enable
    ff.modify_connection('EN', WireSegmentPath(raw=''))
    assert ff.en_port.signal is Signal.FLOATING
    ff.input_port.set_signal(Signal.HIGH)
    assert ff.output_port.signal is Signal.UNDEFINED
    _clk(ff)
    assert ff.output_port.signal is Signal.UNDEFINED

    # EN High
    ff.modify_connection('EN', WireSegmentPath(raw='a.enable_signal.0'))
    ff.set_en(Signal.HIGH)
    assert ff.en_port.signal is Signal.HIGH
    assert ff.output_port.signal is Signal.UNDEFINED

    ff.input_port.set_signal(Signal.HIGH)
    assert ff.output_port.signal is Signal.UNDEFINED
    _clk(ff)
    assert ff.output_port.signal is Signal.HIGH

    # EN Low
    ff.set_en(Signal.LOW)
    ff.input_port.set_signal(Signal.LOW)
    assert ff.output_port.signal is Signal.HIGH
    _clk(ff)
    assert ff.output_port.signal is Signal.HIGH

    ff.en_polarity = Signal.LOW
    assert ff.output_port.signal is Signal.HIGH
    _clk(ff)
    assert ff.output_port.signal is Signal.LOW


def _init_scan_structure(ff: DFF) -> None:
    ff.module.connect(ff.module.create_port('se', Direction.IN), ff.ports['SE'], 'se_wire')
    ff.module.connect(ff.module.create_port('si', Direction.IN, width=4), ff.ports['SI'], 'si_wire')
    ff.module.connect(ff.ports['SO'], ff.module.create_port('so', Direction.OUT, width=4), 'so_wire')


def test_scandff_structure(simple_module: Module) -> None:
    ff = ScanDFF(raw_path='a.dff_inst', parameters={'WIDTH': 4, 'ARST_POLARITY': Signal.LOW}, module=simple_module)
    simple_module.instances['dff_inst'] = ff

    assert ff.name == 'dff_inst'
    assert ff.instance_type == '§scan_dff'
    assert ff.clk_polarity is Signal.HIGH

    assert len(ff.ports) == 6
    assert 'D' in ff.ports
    assert 'CLK' in ff.ports
    assert 'Q' in ff.ports
    assert 'SE' in ff.ports
    assert 'SI' in ff.ports
    assert 'SO' in ff.ports
    assert ff.ports['D'].is_input
    assert ff.ports['CLK'].is_input
    assert ff.ports['Q'].is_output
    assert ff.ports['SE'].is_input
    assert ff.ports['SI'].is_input
    assert ff.ports['SO'].is_output
    assert ff.input_port == ff.ports['D']
    assert ff.clk_port == ff.ports['CLK']
    assert ff.output_port == ff.ports['Q']
    assert ff.se_port == ff.ports['SE']
    assert ff.si_port == ff.ports['SI']
    assert ff.so_port == ff.ports['SO']
    assert ff.output_port.signal is Signal.UNDEFINED
    assert ff.input_port.width == 4
    assert ff.clk_port.width == 1
    assert ff.output_port.width == 4
    assert ff.se_port.width == 1
    assert ff.si_port.width == 4
    assert ff.so_port.width == 4
    assert list(range(4)) == list(ff.input_port.segments.keys())
    assert list(range(4)) == list(ff.output_port.segments.keys())
    assert ff.scan_ff_equivalent == DFF
    assert ff.verilog_template == '{so}\nalways @({header}) begin\n\tif ({se}) begin\n\t\t{si}\n\tend else begin\n\t\t{set_out}\n\tend\nend'

    _init_dff_structure(ff)
    _init_scan_structure(ff)
    target_v = "assign\tso_wire\t=\twire;\nalways @(posedge clk) begin\n\tif (se_wire) begin\n\t\twire\t<=\tsi_wire;\n\tend else begin\n\t\twire\t<=\t{wireA2, 2'bx1, wireA1[0]};\n\tend\nend"
    save_results(ff.verilog, 'txt')
    assert ff.verilog == target_v
    assert ff.verilog_net_map == {'D': "{wireA2, 2'bx1, wireA1[0]}", 'Q': 'wire', 'CLK': 'clk', 'SE': 'se_wire', 'SI': 'si_wire', 'SO': 'so_wire'}


def test_scandff_behaviour(simple_module: Module) -> None:
    ff = ScanDFF(raw_path='a.dff_inst', parameters={'WIDTH': 4}, module=simple_module)
    simple_module.instances['dff_inst'] = ff
    _init_dff_structure(ff, init_all_in=True)
    _init_scan_structure(ff)
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    ff.input_port.set_signals('01xz')
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    assert ff.so_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}
    ff.si_port.set_signals('0110')
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}
    assert ff.so_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}
    ff.se_port.set_signals('1')
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.LOW}
    assert ff.so_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.LOW}


def test_scanadff_structure(simple_module: Module) -> None:
    ff = ScanADFF(raw_path='a.dff_inst', parameters={'WIDTH': 4, 'ARST_POLARITY': Signal.LOW}, module=simple_module)
    simple_module.instances['dff_inst'] = ff

    assert ff.name == 'dff_inst'
    assert ff.instance_type == '§scan_adff'
    assert ff.clk_polarity is Signal.HIGH

    assert len(ff.ports) == 7
    assert 'D' in ff.ports
    assert 'CLK' in ff.ports
    assert 'RST' in ff.ports
    assert 'Q' in ff.ports
    assert 'SE' in ff.ports
    assert 'SI' in ff.ports
    assert 'SO' in ff.ports
    assert ff.ports['D'].is_input
    assert ff.ports['CLK'].is_input
    assert ff.ports['RST'].is_input
    assert ff.ports['Q'].is_output
    assert ff.ports['SE'].is_input
    assert ff.ports['SI'].is_input
    assert ff.ports['SO'].is_output
    assert ff.input_port == ff.ports['D']
    assert ff.clk_port == ff.ports['CLK']
    assert ff.rst_port == ff.ports['RST']
    assert ff.output_port == ff.ports['Q']
    assert ff.se_port == ff.ports['SE']
    assert ff.si_port == ff.ports['SI']
    assert ff.so_port == ff.ports['SO']
    assert ff.output_port.signal is Signal.UNDEFINED
    assert ff.input_port.width == 4
    assert ff.clk_port.width == 1
    assert ff.rst_port.width == 1
    assert ff.output_port.width == 4
    assert ff.se_port.width == 1
    assert ff.si_port.width == 4
    assert ff.so_port.width == 4
    assert list(range(4)) == list(ff.input_port.segments.keys())
    assert list(range(4)) == list(ff.output_port.segments.keys())
    assert ff.scan_ff_equivalent == ADFF
    assert (
        ff.verilog_template
        == '{so}\nalways @({header}) begin\n\tif ({is_rst}) begin\n\t\t{rst_out}\n\tend else if ({se}) begin\n\t\t{si}\n\tend else begin\n\t\t{set_out}\n\tend\nend'
    )

    _init_dff_structure(ff)
    _init_scan_structure(ff)
    ff.modify_connection('RST', WireSegmentPath(raw='a.rst.0'))
    target_v = "assign\tso_wire\t=\twire;\nalways @(posedge clk or negedge rst) begin\n\tif (~rst) begin\n\t\twire\t<=\t4'b0000;\n\tend else if (se_wire) begin\n\t\twire\t<=\tsi_wire;\n\tend else begin\n\t\twire\t<=\t{wireA2, 2'bx1, wireA1[0]};\n\tend\nend"
    save_results(ff.verilog, 'txt')
    assert ff.verilog == target_v


def test_scanadff_behaviour(simple_module: Module) -> None:
    ff = ScanADFF(raw_path='a.dff_inst', parameters={'WIDTH': 4}, module=simple_module)
    simple_module.instances['dff_inst'] = ff
    _init_dff_structure(ff, init_all_in=True)
    _init_scan_structure(ff)
    ff.rst_polarity = Signal.LOW  # Low active
    ff.modify_connection('RST', WireSegmentPath(raw='a.rst.0'))
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    ff.input_port.set_signals('01xz')
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    assert ff.so_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    ff.set_rst(1)
    assert ff.so_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    ff.set_rst(0)
    assert ff.so_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW}
    ff.set_rst(1)
    assert ff.so_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW}
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}
    ff.si_port.set_signals('0110')
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}
    assert ff.so_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}
    ff.se_port.set_signals('1')
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.LOW}
    assert ff.so_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.LOW}


def test_scandffe_structure(simple_module: Module) -> None:
    ff = ScanDFFE(raw_path='a.dff_inst', parameters={'WIDTH': 4, 'ARST_POLARITY': Signal.LOW}, module=simple_module)
    simple_module.instances['dff_inst'] = ff

    assert ff.name == 'dff_inst'
    assert ff.instance_type == '§scan_dffe'
    assert ff.clk_polarity is Signal.HIGH

    assert len(ff.ports) == 7
    assert 'D' in ff.ports
    assert 'CLK' in ff.ports
    assert 'EN' in ff.ports
    assert 'Q' in ff.ports
    assert 'SE' in ff.ports
    assert 'SI' in ff.ports
    assert 'SO' in ff.ports
    assert ff.ports['D'].is_input
    assert ff.ports['CLK'].is_input
    assert ff.ports['EN'].is_input
    assert ff.ports['Q'].is_output
    assert ff.ports['SE'].is_input
    assert ff.ports['SI'].is_input
    assert ff.ports['SO'].is_output
    assert ff.input_port == ff.ports['D']
    assert ff.clk_port == ff.ports['CLK']
    assert ff.en_port == ff.ports['EN']
    assert ff.output_port == ff.ports['Q']
    assert ff.se_port == ff.ports['SE']
    assert ff.si_port == ff.ports['SI']
    assert ff.so_port == ff.ports['SO']
    assert ff.output_port.signal is Signal.UNDEFINED
    assert ff.input_port.width == 4
    assert ff.clk_port.width == 1
    assert ff.en_port.width == 1
    assert ff.output_port.width == 4
    assert ff.se_port.width == 1
    assert ff.si_port.width == 4
    assert ff.so_port.width == 4
    assert list(range(4)) == list(ff.input_port.segments.keys())
    assert list(range(4)) == list(ff.output_port.segments.keys())
    assert ff.scan_ff_equivalent == DFFE
    assert ff.verilog_template == '{so}\nalways @({header}) begin\n\tif ({se}) begin\n\t\t{si}\n\tend else if ({en}) begin\n\t\t{set_out}\n\tend\nend'

    _init_dff_structure(ff)
    _init_scan_structure(ff)
    ff.modify_connection('EN', WireSegmentPath(raw='a.en.0'))
    target_v = "assign\tso_wire\t=\twire;\nalways @(posedge clk) begin\n\tif (se_wire) begin\n\t\twire\t<=\tsi_wire;\n\tend else if (en) begin\n\t\twire\t<=\t{wireA2, 2'bx1, wireA1[0]};\n\tend\nend"
    save_results(ff.verilog, 'txt')
    assert ff.verilog == target_v


def test_scandffe_behaviour(simple_module: Module) -> None:
    ff = ScanDFFE(raw_path='a.dff_inst', parameters={'WIDTH': 4}, module=simple_module)
    simple_module.instances['dff_inst'] = ff
    _init_dff_structure(ff, init_all_in=True)
    _init_scan_structure(ff)
    ff.modify_connection('EN', WireSegmentPath(raw='a.en.0'))
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    ff.input_port.set_signals('01xz')
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    assert ff.so_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    ff.set_en(0)
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    assert ff.so_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    ff.set_en(1)
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}
    ff.si_port.set_signals('0110')
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}
    assert ff.so_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}
    ff.se_port.set_signals('1')
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.LOW}
    assert ff.so_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.LOW}


def test_scanadffe_structure(simple_module: Module) -> None:
    ff = ScanADFFE(raw_path='a.dff_inst', parameters={'WIDTH': 4, 'ARST_POLARITY': Signal.LOW}, module=simple_module)
    simple_module.instances['dff_inst'] = ff

    assert ff.name == 'dff_inst'
    assert ff.instance_type == '§scan_adffe'
    assert ff.clk_polarity is Signal.HIGH

    assert len(ff.ports) == 8
    assert 'D' in ff.ports
    assert 'CLK' in ff.ports
    assert 'RST' in ff.ports
    assert 'EN' in ff.ports
    assert 'Q' in ff.ports
    assert 'SE' in ff.ports
    assert 'SI' in ff.ports
    assert 'SO' in ff.ports
    assert ff.ports['D'].is_input
    assert ff.ports['CLK'].is_input
    assert ff.ports['RST'].is_input
    assert ff.ports['EN'].is_input
    assert ff.ports['Q'].is_output
    assert ff.ports['SE'].is_input
    assert ff.ports['SI'].is_input
    assert ff.ports['SO'].is_output
    assert ff.input_port == ff.ports['D']
    assert ff.clk_port == ff.ports['CLK']
    assert ff.rst_port == ff.ports['RST']
    assert ff.en_port == ff.ports['EN']
    assert ff.output_port == ff.ports['Q']
    assert ff.se_port == ff.ports['SE']
    assert ff.si_port == ff.ports['SI']
    assert ff.so_port == ff.ports['SO']
    assert ff.output_port.signal is Signal.UNDEFINED
    assert ff.input_port.width == 4
    assert ff.clk_port.width == 1
    assert ff.rst_port.width == 1
    assert ff.en_port.width == 1
    assert ff.output_port.width == 4
    assert ff.se_port.width == 1
    assert ff.si_port.width == 4
    assert ff.so_port.width == 4
    assert list(range(4)) == list(ff.input_port.segments.keys())
    assert list(range(4)) == list(ff.output_port.segments.keys())
    assert ff.scan_ff_equivalent == ADFFE
    assert (
        ff.verilog_template
        == '{so}\nalways @({header}) begin\n\tif ({is_rst}) begin\n\t\t{rst_out}\n\tend else if ({se}) begin\n\t\t{si}\n\tend else if ({en}) begin\n\t\t{set_out}\n\tend\nend'
    )

    _init_dff_structure(ff, init_rst_en=True)
    _init_scan_structure(ff)
    target_v = "assign\tso_wire\t=\twire;\nalways @(posedge clk or negedge rst) begin\n\tif (~rst) begin\n\t\twire\t<=\t4'b0000;\n\tend else if (se_wire) begin\n\t\twire\t<=\tsi_wire;\n\tend else if (en) begin\n\t\twire\t<=\t{wireA2, 2'bx1, wireA1[0]};\n\tend\nend"
    save_results(ff.verilog, 'txt')
    assert ff.verilog == target_v


def test_scanadffe_behaviour(simple_module: Module) -> None:
    ff = ScanADFFE(raw_path='a.dff_inst', parameters={'WIDTH': 4}, module=simple_module)
    simple_module.instances['dff_inst'] = ff
    _init_dff_structure(ff, init_all_in=True, init_rst_en=True)
    _init_scan_structure(ff)
    ff.rst_polarity = Signal.LOW  # Low active
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    ff.input_port.set_signals('01xz')
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    assert ff.so_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    ff.set_rst(1)
    assert ff.so_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    ff.set_rst(0)
    assert ff.so_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW}
    ff.set_rst(1)
    assert ff.so_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW}
    _clk(ff)
    ff.set_en(0)
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    assert ff.so_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    ff.set_en(1)
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}
    ff.si_port.set_signals('0110')
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}
    assert ff.so_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}
    ff.se_port.set_signals('1')
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.HIGH, 3: Signal.LOW}
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.LOW}
    assert ff.so_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.LOW}


def _init_dlatch_structure(dl: DLatch, init_all: bool = False) -> None:
    dl.modify_connection('D', WireSegmentPath(raw='a.wireA1.0'), index=0)
    dl.tie_port('D', index=1, sig_value='1')
    # 2nd is missing on purpose: dl.modify_connection('D', WireSegmentPath(raw='a.wireA1.2'), index=2)
    dl.modify_connection('D', WireSegmentPath(raw='a.wireA2.0'), index=3)

    dl.modify_connection('Q', WireSegmentPath(raw='a.wire.0'), index=0)
    dl.modify_connection('Q', WireSegmentPath(raw='a.wire.1'), index=1)
    # 2nd is missing on purpose: dl.modify_connection('Q', WireSegmentPath(raw='a.wire.2'), index=2)
    dl.modify_connection('Q', WireSegmentPath(raw='a.wire.3'), index=3)

    dl.modify_connection('EN', WireSegmentPath(raw='a.clk.0'), index=0)

    if init_all:
        dl.modify_connection('D', WireSegmentPath(raw='a.wireA1.2'), index=2)
        dl.modify_connection('Q', WireSegmentPath(raw='a.wire.2'), index=2)


def test_dlatch_structure(simple_module: Module) -> None:
    dl = DLatch(raw_path='a.dlatch_inst', parameters={'WIDTH': 4}, module=simple_module)

    assert dl.name == 'dlatch_inst'
    assert dl.instance_type == '§dlatch'
    assert dl.en_polarity is Signal.HIGH

    assert len(dl.ports) == 3
    assert 'D' in dl.ports
    assert 'EN' in dl.ports
    assert 'Q' in dl.ports
    assert dl.ports['D'].is_input
    assert dl.ports['EN'].is_input
    assert dl.ports['Q'].is_output
    assert dl.input_port == dl.ports['D']
    assert dl.en_port == dl.ports['EN']
    assert dl.output_port == dl.ports['Q']
    assert dl.output_port.signal is Signal.UNDEFINED
    assert dl.input_port.width == 4
    assert dl.en_port.width == 1
    assert dl.output_port.width == 4
    assert list(range(4)) == list(dl.input_port.segments.keys())
    assert list(range(4)) == list(dl.output_port.segments.keys())
    assert dl.verilog_template == 'always @(*) begin\n\tif ({en}) begin\n{assignments}\n\tend\nend'

    _init_dlatch_structure(dl)
    target_v = "always @(*) begin\n\tif (clk) begin\n\t\t{wire[3], wire[1:0]} = {wireA2, 1'b1, wireA1[0]};\n\tend\nend"
    dl.en_polarity = Signal.LOW
    target_v = "always @(*) begin\n\tif (~clk) begin\n\t\t{wire[3], wire[1:0]} = {wireA2, 1'b1, wireA1[0]};\n\tend\nend"
    save_results(dl.verilog, 'txt')
    assert dl.verilog == target_v
    assert dl.verilog_net_map == {'D': "{wireA2, 2'bx1, wireA1[0]}", 'Q': "{wire[3], 1'bx, wire[1:0]}", 'EN': 'clk'}


def test_dlatch_behavior(simple_module: Module) -> None:
    dl = DLatch(raw_path='a.dlatch_inst', parameters={'WIDTH': 4}, module=simple_module)

    assert all(s == Signal.FLOATING for s in dl.input_port.signal_array.values())
    assert dl.en_port.signal == Signal.FLOATING
    assert all(s == Signal.UNDEFINED for s in dl.output_port.signal_array.values())
    dl.evaluate()
    assert all(s == Signal.FLOATING for s in dl.input_port.signal_array.values())
    assert dl.en_port.signal == Signal.FLOATING
    assert all(s == Signal.UNDEFINED for s in dl.output_port.signal_array.values())

    dl.modify_connection('D', WireSegmentPath(raw='0'), index=0)
    dl.tie_port('D', index=1, sig_value='1')
    dl.modify_connection('D', WireSegmentPath(raw='a.wireA1.2'), index=2)
    dl.modify_connection('D', WireSegmentPath(raw='Z'), index=3)
    dl.input_port.set_signal(Signal.LOW, 0)
    dl.input_port.set_signal(Signal.HIGH, 1)
    dl.input_port.set_signal(Signal.UNDEFINED, 2)
    dl.input_port.set_signal(Signal.FLOATING, 3)
    dl.evaluate()
    assert dl.input_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.UNDEFINED, 3: Signal.FLOATING}
    assert dl.en_port.signal == Signal.FLOATING
    assert all(s == Signal.UNDEFINED for s in dl.output_port.signal_array.values())

    dl.modify_connection('EN', WireSegmentPath(raw='a.clk.0'))
    dl.en_port.set_signal(Signal.LOW)
    dl.evaluate()
    assert dl.input_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.UNDEFINED, 3: Signal.FLOATING}
    assert dl.en_port.signal == Signal.LOW
    assert all(s == Signal.UNDEFINED for s in dl.output_port.signal_array.values())

    dl.en_port.set_signal(Signal.HIGH)
    dl.evaluate()
    assert dl.input_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.UNDEFINED, 3: Signal.FLOATING}
    assert dl.en_port.signal == Signal.HIGH
    assert dl.output_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.UNDEFINED, 3: Signal.FLOATING}

    dl.modify_connection('D', WireSegmentPath(raw='a.wireA1.3'), index=3)
    dl.input_port.set_signal(Signal.LOW, 2)
    dl.input_port.set_signal(Signal.HIGH, 3)
    dl.evaluate()
    assert dl.input_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.LOW, 3: Signal.HIGH}
    assert dl.en_port.signal == Signal.HIGH
    assert dl.output_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.LOW, 3: Signal.HIGH}

    dl.en_port.set_signal(Signal.LOW)
    dl.input_port.set_signal(Signal.HIGH, 2)
    dl.input_port.set_signal(Signal.LOW, 3)
    assert dl.input_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.LOW}
    assert dl.en_port.signal == Signal.LOW
    assert dl.output_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.LOW, 3: Signal.HIGH}


def test_get(simple_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import AndGate, get

    and_class = get('§and')
    assert and_class == AndGate

    dff_class = get('§dff')
    assert dff_class == DFF

    invalid_class = get('§nonexistent')
    assert invalid_class is None

    invalid_class = get('invalid')
    assert invalid_class is None


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
