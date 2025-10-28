# mypy: disable-error-code="unreachable,comparison-overlap"
import os
from typing import Dict

import pytest
from pydantic import ValidationError
from utils import save_results

from netlist_carpentry import WIRE_SEGMENT_X
from netlist_carpentry.core.exceptions import EvaluationError
from netlist_carpentry.core.netlist_elements.element_path import PortPath, WireSegmentPath
from netlist_carpentry.core.netlist_elements.element_type import EType
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.netlist_elements.port import Port
from netlist_carpentry.core.netlist_elements.wire_segment import WIRE_SEGMENT_1
from netlist_carpentry.core.port_direction import PortDirection
from netlist_carpentry.core.signal import Signal
from netlist_carpentry.utils._gate_lib_base import LibUtils
from netlist_carpentry.utils.gate_lib import (
    DFF,
    Demultiplexer,
    DLatch,
    Multiplexer,
    _BinaryGate,
    _BinaryNto1Gate,
    _PrimitiveGate,
    _ReduceGate,
    _UnaryGate,
)


@pytest.fixture
def primitive_gate() -> Instance:
    return _PrimitiveGate(raw_path='a.b.primitive_gate_inst', instance_type='primitive_gate', module=None)


@pytest.fixture
def unary_gate() -> Instance:
    return _UnaryGate(raw_path='a.b.unary_gate_inst', instance_type='unary_gate', module=None)


@pytest.fixture
def reduce_gate() -> Instance:
    return _ReduceGate(raw_path='a.b.reduce_gate_inst', instance_type='reduce_gate', width=4, module=None)


@pytest.fixture
def binary_gate() -> Instance:
    return _BinaryGate(raw_path='a.b.binary_gate_inst', instance_type='binary_gate', module=None)


def set_curr_module() -> None:
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

    LibUtils.change_current_module(m)


def test_gate_lib_map() -> None:
    from netlist_carpentry.utils.gate_lib import _build_gate_lib_map, _gate_lib_map

    _build_gate_lib_map()
    assert len(_gate_lib_map) == 34  # Currently 34 gates in library


def test_current_module() -> None:
    from utils import empty_module

    LibUtils._gatelib_current_module = None
    assert LibUtils.curr_module() is None
    m = empty_module()
    LibUtils.change_current_module(m)
    assert LibUtils.curr_module() is m


def test_ws2v() -> None:
    from utils import empty_module

    m = empty_module()
    m.create_wire('w1')
    m.create_wire('w4', 4)
    inst = m.create_instance(Module(raw_path='some_submodule'), 'test_inst')
    LibUtils.change_current_module(m)
    p = Port(raw_path='test_module1.port1', direction=PortDirection.IN, module_or_instance=inst)
    p.create_port_segment(0).change_connection(WireSegmentPath(raw='test_module1.w1.0'))
    ps_str1 = LibUtils.p2ws2v(p)
    assert ps_str1 == 'w1'

    p = Port(raw_path='test_module1.port1', direction=PortDirection.IN, module_or_instance=inst)
    p.create_port_segment(0).change_connection(WireSegmentPath(raw='test_module1.w4.0'))
    ps_str2 = LibUtils.p2ws2v(p)
    assert ps_str2 == 'w4[0]'

    LibUtils.change_current_module(Module(raw_path='some_invalid_module'))
    with pytest.raises(AttributeError):
        LibUtils.p2ws2v(Port(raw_path='a.b.c', module_or_instance=inst, direction=PortDirection.IN))


def test_primitive_gate(primitive_gate: _PrimitiveGate) -> None:
    assert primitive_gate.name == 'primitive_gate_inst'
    assert primitive_gate.type is EType.INSTANCE
    assert primitive_gate.instance_type == 'primitive_gate'
    with pytest.raises(NotImplementedError):
        primitive_gate.output_port
    assert primitive_gate.is_primitive
    assert primitive_gate.is_combinatorial
    assert not primitive_gate.is_sequential
    assert primitive_gate.verilog_template == 'assign {out} = {in1};'


def test_unary_gate(unary_gate: _UnaryGate) -> None:
    assert unary_gate.name == 'unary_gate_inst'
    assert unary_gate.type is EType.INSTANCE
    assert unary_gate.instance_type == 'unary_gate'
    assert len(unary_gate.connections) == 2
    assert unary_gate.connections['A'] == {0: WIRE_SEGMENT_X.path}
    assert unary_gate.connections['Y'] == {0: WIRE_SEGMENT_X.path}
    assert len(unary_gate.ports) == 2
    assert unary_gate.output_port == unary_gate.ports['Y']
    assert unary_gate.input_port == unary_gate.ports['A']
    assert unary_gate.ports['A'].path == PortPath(raw=f'{unary_gate.path.raw}.A')
    assert unary_gate.ports['Y'].path == PortPath(raw=f'{unary_gate.path.raw}.Y')
    assert unary_gate.is_primitive
    assert unary_gate.verilog_template == 'assign {out} = {in1};'
    assert unary_gate.verilog == ''
    assert unary_gate.signal_in(0) is Signal.FLOATING
    assert unary_gate.signal_out(0) is Signal.UNDEFINED


def test_unary_gate_8bit() -> None:
    g = _UnaryGate(raw_path='a.b.unary_gate_inst', instance_type='unary_gate', width=8, module=None)
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


def test_unary_gate_eval(unary_gate: _UnaryGate) -> None:
    assert unary_gate.output_port.signal is Signal.UNDEFINED
    unary_gate._set_output({0: Signal.HIGH})
    assert unary_gate.output_port.signal is Signal.HIGH

    with pytest.raises(NotImplementedError):
        unary_gate._calc_output()


def _test_signal_conf1(gate: _UnaryGate, sin: Signal, sout_prev: Signal, sout_new: Signal, idx: int = 0) -> None:
    assert gate.signal_out(idx) == sout_prev
    gate.input_port.set_signal(sin, index=idx)
    assert gate.signal_in(idx) == sin
    assert gate.signal_out(idx) == sout_prev
    gate.evaluate()
    assert gate.signal_out(idx) == sout_new


def _test_signal_conf1_n(gate: _UnaryGate, sin: Signal, sout_prev: Signal, sout_new: Signal) -> None:
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


def test_buffer() -> None:
    from netlist_carpentry.utils.gate_lib import Buffer

    g = Buffer(raw_path='a.buf_inst', width=4, module=None)
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
    set_curr_module()
    assert g.verilog == "assign {wire[3], wire[1:0]} = {wireA2, 1'b1, wireA1[0]};"

    _test_signal_conf1_n(g, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf1_n(g, Signal.LOW, Signal.UNDEFINED, Signal.LOW)
    _test_signal_conf1_n(g, Signal.HIGH, Signal.LOW, Signal.HIGH)
    _test_signal_conf1_n(g, Signal.FLOATING, Signal.HIGH, Signal.UNDEFINED)


def test_not_gate() -> None:
    from netlist_carpentry.utils.gate_lib import NotGate

    g = NotGate(raw_path='a.not_inst', width=4, module=None)
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
    set_curr_module()
    assert g.verilog == "assign {wire[3], wire[1:0]} = ~{wireA2, 1'b1, wireA1[0]};"

    _test_signal_conf1_n(g, Signal.UNDEFINED, Signal.UNDEFINED, Signal.UNDEFINED)
    _test_signal_conf1_n(g, Signal.LOW, Signal.UNDEFINED, Signal.HIGH)
    _test_signal_conf1_n(g, Signal.HIGH, Signal.HIGH, Signal.LOW)
    _test_signal_conf1_n(g, Signal.FLOATING, Signal.LOW, Signal.UNDEFINED)


def test_neg_gate() -> None:
    from netlist_carpentry.utils.gate_lib import NegGate

    g = NegGate(raw_path='a.neg_inst', width=4, module=None)
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
    set_curr_module()
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


def _test_signal_confr_n(gate: _UnaryGate, sin: Signal, sout_prev: Signal, sout_new: Signal) -> None:
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


def test_reducer(reduce_gate: _ReduceGate) -> None:
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


def test_reduce_and() -> None:
    from netlist_carpentry.utils.gate_lib import ReduceAnd

    r = ReduceAnd(raw_path='a.reduce_and_inst', width=4, module=None)
    assert r.verilog_template == 'assign {out} = &{in1};'
    r.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    r.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: r.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    r.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    r.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    set_curr_module()
    assert r.verilog == "assign wire[0] = &{wireA2, 1'b1, wireA1[0]};"

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


def test_reduce_and_bad_verilog() -> None:
    from netlist_carpentry.utils.gate_lib import ReduceAnd

    r = ReduceAnd(raw_path='a.reduce_and_inst', width=4, module=None)
    r.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    r.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: r.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    r.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    set_curr_module()
    assert r.verilog == ''  # No output specified -> useless instance


def test_reduce_or() -> None:
    from netlist_carpentry.utils.gate_lib import ReduceOr

    r = ReduceOr(raw_path='a.reduce_or_inst', width=4, module=None)
    assert r.verilog_template == 'assign {out} = |{in1};'
    r.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    r.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: r.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    r.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    r.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    set_curr_module()
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


def test_reduce_bool() -> None:
    from netlist_carpentry.utils.gate_lib import ReduceBool

    r = ReduceBool(raw_path='a.reduce_bool_inst', width=4, module=None)
    assert r.verilog_template == 'assign {out} = |{in1};'  # TODO EQY unable to prove equality for !(!wire), but can prove equality for |wire
    r.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    r.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: r.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    r.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    r.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    set_curr_module()
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


def test_reduce_xor() -> None:
    from netlist_carpentry.utils.gate_lib import ReduceXor

    r = ReduceXor(raw_path='a.reduce_xor_inst', width=4, module=None)
    assert r.verilog_template == 'assign {out} = ^{in1};'
    r.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    r.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: r.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    r.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    r.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    set_curr_module()
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


def test_reduce_xnor() -> None:
    from netlist_carpentry.utils.gate_lib import ReduceXnor

    r = ReduceXnor(raw_path='a.reduce_xnor_inst', width=4, module=None)
    assert r.verilog_template == 'assign {out} = ~^{in1};'
    r.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    r.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: r.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    r.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    r.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    set_curr_module()
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


def test_logic_not() -> None:
    from netlist_carpentry.utils.gate_lib import LogicNot

    ln = LogicNot(raw_path='a.logic_not_inst', width=4, module=None)
    assert ln.verilog_template == 'assign {out} = !{in1};'
    ln.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    ln.tie_port('A', index=1, sig_value='1')
    # 2nd is missing on purpose: r.modify_connection('A', WireSegmentPath(raw='a.wireA1.2'), index=2)
    ln.modify_connection('A', WireSegmentPath(raw='a.wireA2.0'), index=3)

    ln.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    set_curr_module()
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


def test_binary_gate(binary_gate: _BinaryGate) -> None:
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
    assert binary_gate.ports['A'].path == PortPath(raw=f'{binary_gate.path.raw}.A')
    assert binary_gate.ports['B'].path == PortPath(raw=f'{binary_gate.path.raw}.B')
    assert binary_gate.ports['Y'].path == PortPath(raw=f'{binary_gate.path.raw}.Y')
    assert binary_gate.is_primitive
    assert binary_gate.verilog_template == 'assign {out} = {in1} {operator} {in2};'
    assert binary_gate.verilog == ''
    assert binary_gate.signals_in(0) == (Signal.FLOATING, Signal.FLOATING)
    assert binary_gate.signal_out(0) is Signal.UNDEFINED


def test_binary_gate_8bit() -> None:
    g = _BinaryGate(raw_path='a.b.binary_gate_inst', instance_type='binary_gate', width=8, module=None)
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


def test_binary_gate_eval(binary_gate: _BinaryGate) -> None:
    assert binary_gate.output_port.signal is Signal.UNDEFINED
    binary_gate._set_output({0: Signal.HIGH})
    assert binary_gate.output_port.signal is Signal.HIGH

    with pytest.raises(NotImplementedError):
        binary_gate._calc_output()


def _test_signal_conf2(gate: _BinaryGate, sin1: Signal, sin2: Signal, sout_prev: Signal, sout_new: Signal, idx: int = 0) -> None:
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


def _test_signal_conf2_n(gate: _BinaryGate, sin1: Signal, sin2: Signal, sout_prev: Signal, sout_new: Signal) -> None:
    for i in range(gate.width):
        _test_signal_conf2(gate, sin1, sin2, sout_prev, sout_new, i)


def test_and_gate() -> None:
    from netlist_carpentry.utils.gate_lib import AndGate

    g = AndGate(raw_path='a.and_inst', width=4, module=None)
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
    set_curr_module()
    assert g.verilog == "assign {wire[3], wire[1:0]} = {wireA2, 1'b1, wireA1[0]} & {wireB[3], wireB[1:0]};"

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


def test_and_gate_signed() -> None:
    from netlist_carpentry.utils.gate_lib import AndGate

    g = AndGate(raw_path='a.and_inst', width=4, module=None)
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
    set_curr_module()
    assert g.verilog == "assign {wire[3], wire[1:0]} = $signed({wireA2, 1'b1, wireA1[0]}) & $signed({wireB[3], wireB[1:0]});"


def test_or_gate() -> None:
    from netlist_carpentry.utils.gate_lib import OrGate

    g = OrGate(raw_path='a.or_inst', width=4, module=None)
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
    set_curr_module()
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


def test_xor_gate() -> None:
    from netlist_carpentry.utils.gate_lib import XorGate

    g = XorGate(raw_path='a.xor_inst', width=4, module=None)
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
    set_curr_module()
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


def test_xnor_gate() -> None:
    from netlist_carpentry.utils.gate_lib import XnorGate

    g = XnorGate(raw_path='a.xnor_inst', width=4, module=None)
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
    set_curr_module()
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


def test_nor_gate() -> None:
    from netlist_carpentry.utils.gate_lib import NorGate

    g = NorGate(raw_path='a.nor_inst', width=4, module=None)
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
    set_curr_module()
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


def test_nand_gate() -> None:
    from netlist_carpentry.utils.gate_lib import NandGate

    g = NandGate(raw_path='a.nand_inst', width=4, module=None)
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
    set_curr_module()
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


def test_shift_signed_gate() -> None:
    from netlist_carpentry.utils.gate_lib import ShiftSigned

    g = ShiftSigned(raw_path='a.shift_inst', width=4, module=None)
    assert g.name == 'shift_inst'
    assert g.instance_type == '§shift'
    assert g.verilog_template == 'assign {out} = {in1} >> {in2};'
    g.parameters['B_SIGNED'] = '1'
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
    set_curr_module()
    assert g.verilog == "assign {wire[3], wire[1:0]} = {wireA2, 1'b1, wireA1[0]} << -{wireB[3], wireB[1:0]};"
    g.parameters['B_SIGNED'] = '0'
    assert g.verilog == "assign {wire[3], wire[1:0]} = {wireA2, 1'b1, wireA1[0]} >> {wireB[3], wireB[1:0]};"
    g.parameters['A_SIGNED'] = '1'
    assert g.verilog == "assign {wire[3], wire[1:0]} = $signed({wireA2, 1'b1, wireA1[0]}) >> {wireB[3], wireB[1:0]};"
    g.parameters['B_SIGNED'] = '1'
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
    g.ports['A'].set_signed(True)
    g.ports['A'].set_signals('0110')
    g.ports['B'].set_signals('0001')
    g.evaluate()
    assert g.ports['Y'].signal_array == {3: Signal.LOW, 2: Signal.LOW, 1: Signal.HIGH, 0: Signal.HIGH}
    g.ports['A'].set_signed(True)
    g.ports['A'].set_signals('1011')  # -5
    g.ports['B'].set_signals('0010')
    g.evaluate()
    assert g.ports['Y'].signal_array == {3: Signal.HIGH, 2: Signal.HIGH, 1: Signal.HIGH, 0: Signal.LOW}

    # A signed, B signed: left shift, but A is signed
    g.ports['B'].set_signed(True)
    g.ports['A'].set_signals('1011')  # -5
    g.ports['B'].set_signals('0001')  # B == 1 > 0: Right Shift by 1: '1011' >> 1 = '1101' in signed context
    g.evaluate()
    assert g.ports['Y'].signal_array == {3: Signal.HIGH, 2: Signal.HIGH, 1: Signal.LOW, 0: Signal.HIGH}
    g.ports['A'].set_signed(True)
    g.ports['A'].set_signals('1011')  # -5
    g.ports['B'].set_signals('1111')  # B == -1 < 0: Left Shift by 1: '1011' << 1 = '0110'
    g.evaluate()
    assert g.ports['Y'].signal_array == {3: Signal.LOW, 2: Signal.HIGH, 1: Signal.HIGH, 0: Signal.LOW}

    # A unsigned, B signed: logical left shift
    g.ports['A'].set_signed(False)
    g.ports['A'].set_signals('1011')  # 11
    g.ports['B'].set_signals('0001')  # B == 1 > 0: Right Shift by 1: '1011' >> 1 = '0101' since A is unsigned
    g.evaluate()
    assert g.ports['Y'].signal_array == {3: Signal.LOW, 2: Signal.HIGH, 1: Signal.LOW, 0: Signal.HIGH}
    g.ports['A'].set_signed(True)
    g.ports['A'].set_signals('1011')  # -5
    g.ports['B'].set_signals('1111')  # B == -1 < 0: Left Shift by 1: '1011' << 1 = '0110'
    g.evaluate()
    assert g.ports['Y'].signal_array == {3: Signal.LOW, 2: Signal.HIGH, 1: Signal.HIGH, 0: Signal.LOW}


def test_shl_gate() -> None:
    from netlist_carpentry.utils.gate_lib import ShiftLeft

    g = ShiftLeft(raw_path='a.shl_inst', width=4, module=None)
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
    set_curr_module()
    assert g.verilog == "assign {wire[3], wire[1:0]} = {wireA2, 1'b1, wireA1[0]} << {wireB[3], wireB[1:0]};"
    g.parameters['A_SIGNED'] = '1'
    assert g.verilog == "assign {wire[3], wire[1:0]} = $signed({wireA2, 1'b1, wireA1[0]}) << {wireB[3], wireB[1:0]};"
    g.parameters['B_SIGNED'] = '1'  # B_SIGNED == 1 should not change Verilog output
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


def test_shr_gate() -> None:
    from netlist_carpentry.utils.gate_lib import ShiftRight

    g = ShiftRight(raw_path='a.shr_inst', width=4, module=None)
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
    set_curr_module()
    assert g.verilog == "assign {wire[3], wire[1:0]} = {wireA2, 1'b1, wireA1[0]} >> {wireB[3], wireB[1:0]};"
    g.parameters['A_SIGNED'] = '1'
    assert g.verilog == "assign {wire[3], wire[1:0]} = $signed({wireA2, 1'b1, wireA1[0]}) >> {wireB[3], wireB[1:0]};"
    g.parameters['B_SIGNED'] = '1'  # B_SIGNED == 1 should not change Verilog output
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


def test_comparison_gate() -> None:
    g = _BinaryNto1Gate(raw_path='a.comp_inst', module=None)
    set_curr_module()
    assert g.verilog == ''


def _test_signal_conf2_arith(gate: _BinaryGate, sins1: Dict[int, Signal], sins2: Dict[int, Signal], sout: Signal) -> None:
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


def test_logic_and_gate() -> None:
    from netlist_carpentry.utils.gate_lib import LogicAnd

    g = LogicAnd(raw_path='a.logic_and_inst', width=2, module=None)
    assert g.name == 'logic_and_inst'
    assert g.instance_type == '§logic_and'
    assert g.verilog_template == 'assign {out} = {in1} && {in2};'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    set_curr_module()
    assert g.verilog == "assign wire[0] = {1'b1, wireA1[0]} && wireB[1:0];"

    _test_signal_conf2_arith(g, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.FLOATING, 0: Signal.FLOATING}, {1: Signal.FLOATING, 0: Signal.FLOATING}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.LOW}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.HIGH}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.LOW}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.LOW}, Signal.LOW)


def test_logic_or_gate() -> None:
    from netlist_carpentry.utils.gate_lib import LogicOr

    g = LogicOr(raw_path='a.logic_or_inst', width=2, module=None)
    assert g.name == 'logic_or_inst'
    assert g.instance_type == '§logic_or'
    assert g.verilog_template == 'assign {out} = {in1} || {in2};'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    set_curr_module()
    assert g.verilog == "assign wire[0] = {1'b1, wireA1[0]} || wireB[1:0];"

    _test_signal_conf2_arith(g, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.FLOATING, 0: Signal.FLOATING}, {1: Signal.FLOATING, 0: Signal.FLOATING}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.LOW}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.HIGH}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.LOW}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.LOW}, Signal.HIGH)


def test_lt_gate() -> None:
    from netlist_carpentry.utils.gate_lib import LessThan

    g = LessThan(raw_path='a.lt_inst', width=2, module=None)
    assert g.name == 'lt_inst'
    assert g.instance_type == '§lt'
    assert g.verilog_template == 'assign {out} = {in1} < {in2};'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    set_curr_module()
    assert g.verilog == "assign wire[0] = {1'b1, wireA1[0]} < wireB[1:0];"

    _test_signal_conf2_arith(g, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.FLOATING, 0: Signal.FLOATING}, {1: Signal.FLOATING, 0: Signal.FLOATING}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.LOW}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.HIGH}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.LOW}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.HIGH}, Signal.LOW)


def test_le_gate() -> None:
    from netlist_carpentry.utils.gate_lib import LessEqual

    g = LessEqual(raw_path='a.le_inst', width=2, module=None)
    assert g.name == 'le_inst'
    assert g.instance_type == '§le'
    assert g.verilog_template == 'assign {out} = {in1} <= {in2};'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    set_curr_module()
    assert g.verilog == "assign wire[0] = {1'b1, wireA1[0]} <= wireB[1:0];"

    _test_signal_conf2_arith(g, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.FLOATING, 0: Signal.FLOATING}, {1: Signal.FLOATING, 0: Signal.FLOATING}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.LOW}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.HIGH}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.LOW}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.HIGH}, Signal.LOW)


def test_eq_gate() -> None:
    from netlist_carpentry.utils.gate_lib import Equal

    g = Equal(raw_path='a.eq_inst', width=2, module=None)
    assert g.name == 'eq_inst'
    assert g.instance_type == '§eq'
    assert g.verilog_template == 'assign {out} = {in1} == {in2};'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    set_curr_module()
    assert g.verilog == "assign wire[0] = {1'b1, wireA1[0]} == wireB[1:0];"

    _test_signal_conf2_arith(g, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.FLOATING, 0: Signal.FLOATING}, {1: Signal.FLOATING, 0: Signal.FLOATING}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.LOW}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.HIGH}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.LOW}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.HIGH}, Signal.LOW)


def test_ne_gate() -> None:
    from netlist_carpentry.utils.gate_lib import NotEqual

    g = NotEqual(raw_path='a.ne_inst', width=2, module=None)
    assert g.name == 'ne_inst'
    assert g.instance_type == '§ne'
    assert g.verilog_template == 'assign {out} = {in1} != {in2};'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    set_curr_module()
    assert g.verilog == "assign wire[0] = {1'b1, wireA1[0]} != wireB[1:0];"

    _test_signal_conf2_arith(g, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.FLOATING, 0: Signal.FLOATING}, {1: Signal.FLOATING, 0: Signal.FLOATING}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.LOW}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.HIGH}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.LOW}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.HIGH}, Signal.HIGH)


def test_gt_gate() -> None:
    from netlist_carpentry.utils.gate_lib import GreaterThan

    g = GreaterThan(raw_path='a.gt_inst', width=2, module=None)
    assert g.name == 'gt_inst'
    assert g.instance_type == '§gt'
    assert g.verilog_template == 'assign {out} = {in1} > {in2};'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    set_curr_module()
    assert g.verilog == "assign wire[0] = {1'b1, wireA1[0]} > wireB[1:0];"

    _test_signal_conf2_arith(g, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.FLOATING, 0: Signal.FLOATING}, {1: Signal.FLOATING, 0: Signal.FLOATING}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.LOW}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.HIGH}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.LOW}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.HIGH}, Signal.HIGH)


def test_ge_gate() -> None:
    from netlist_carpentry.utils.gate_lib import GreaterEqual

    g = GreaterEqual(raw_path='a.ge_inst', width=2, module=None)
    assert g.name == 'ge_inst'
    assert g.instance_type == '§ge'
    assert g.verilog_template == 'assign {out} = {in1} >= {in2};'
    g.modify_connection('A', WireSegmentPath(raw='a.wireA1.0'), index=0)
    g.tie_port('A', index=1, sig_value='1')

    g.modify_connection('B', WireSegmentPath(raw='a.wireB.0'), index=0)
    g.modify_connection('B', WireSegmentPath(raw='a.wireB.1'), index=1)

    g.modify_connection('Y', WireSegmentPath(raw='a.wire.0'), index=0)
    set_curr_module()
    assert g.verilog == "assign wire[0] = {1'b1, wireA1[0]} >= wireB[1:0];"

    _test_signal_conf2_arith(g, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, {1: Signal.UNDEFINED, 0: Signal.UNDEFINED}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.FLOATING, 0: Signal.FLOATING}, {1: Signal.FLOATING, 0: Signal.FLOATING}, Signal.UNDEFINED)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.LOW}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.HIGH}, Signal.HIGH)
    _test_signal_conf2_arith(g, {1: Signal.LOW, 0: Signal.HIGH}, {1: Signal.HIGH, 0: Signal.LOW}, Signal.LOW)
    _test_signal_conf2_arith(g, {1: Signal.HIGH, 0: Signal.LOW}, {1: Signal.LOW, 0: Signal.HIGH}, Signal.HIGH)


def _init_mux_structure(m: Multiplexer) -> None:
    for i in range(8):
        m.modify_connection(f'D_{i}', WireSegmentPath(raw=f'a.wmuxD_{i}.0'), index=0)
        # 2nd is missing on purpose: m.modify_connection(f'D_{i}', WireSegmentPath(raw=f'a.wmuxD_{i}.1'), index=1)
        m.modify_connection(f'D_{i}', WireSegmentPath(raw=f'a.wmuxD_{i}.2'), index=2)
        m.modify_connection(f'D_{i}', WireSegmentPath(raw=f'a.wmuxD_{i}.3'), index=3)

    m.modify_connection('Y', WireSegmentPath(raw='a.wmuxY_1.0'), index=0)
    # 2nd is missing on purpose: m.modify_connection('Y', WireSegmentPath(raw='a.wmuxY_1.1'), index=1)
    m.modify_connection('Y', WireSegmentPath(raw='a.wmuxY_1.2'), index=2)
    m.modify_connection('Y', WireSegmentPath(raw='a.wmuxY_1.3'), index=3)

    for i in range(3):
        m.modify_connection('S', WireSegmentPath(raw=f'a.wmuxS.{i}'), index=i)


def test_mux_structure() -> None:
    with pytest.raises(ValidationError):
        Multiplexer(raw_path='', bit_width=0)
    m = Multiplexer(raw_path='a.mux_inst', bit_width=3, width=4, module=None)

    assert m.name == 'mux_inst'
    assert m.instance_type == '§mux'
    assert m.bit_width == 3
    assert len(m.d_ports) == 8
    assert m.s_port == m.ports['S']
    assert m.output_port == m.ports['Y']
    assert len(m.ports) == 8 + 1 + 1  # 8 data inputs, 1 control input (3-bit wide) and 1 output
    assert len(m.connections) == 8 + 1 + 1  # 8 inputs, 1 control input (3-bit wide) and 1 output
    assert 'D_0' in m.ports
    assert 'D_7' in m.ports
    assert 'D_8' not in m.ports
    assert 'S' in m.ports
    assert 'Y' in m.ports
    assert m.ports['D_0'].width == 4
    assert m.ports['S'].width == 3
    assert m.ports['Y'].width == 4
    assert not m.s_defined
    assert m.s_val == -1
    assert m.active_input is None
    assert m.verilog_template == 'always @(*) begin\n\tcase ({sel})\n{cases}\n\tendcase\nend'
    assert m.output_port.signal is Signal.UNDEFINED

    _init_mux_structure(m)
    set_curr_module()
    case_str = ''
    for i in range(8):
        case_str += f"\t\t3'b{format(i, '03b')} : " + '{wmuxY_1[3:2], wmuxY_1[0]} <= {' + f'wmuxD_{i}[3:2], wmuxD_{i}[0]' + '};\n'
    target_str = 'always @(*) begin\n\tcase (wmuxS)\n' + case_str + '\tendcase\nend'
    save_results(target_str + '\n\n\n' + m.verilog, 'txt')
    assert m.verilog == target_str


def test_mux_behavior() -> None:
    m = Multiplexer(raw_path='a.mux_inst', bit_width=3, width=4, module=None)
    _init_mux_structure(m)

    # Select Ports
    m.ports['S'].set_signal(Signal.HIGH, 0)  # 1 => 1
    m.ports['S'].set_signal(Signal.HIGH, 1)  # 2 => 1
    m.ports['S'].set_signal(Signal.LOW, 2)  # 4 => 0

    assert m.s_defined
    assert m.s_val == 3  # S_0 + S_1 = 1 + 2 => s_val = 3
    assert m.active_input == m.ports['D_3']
    m.evaluate()
    assert m.output_port.signal is Signal.UNDEFINED

    for i in range(8):
        m.modify_connection(f'D_{i}', WireSegmentPath(raw=f'a.wmuxD_{i}.1'), index=1)
    m.modify_connection('Y', WireSegmentPath(raw='a.wmuxY_1.1'), index=1)

    # Data Ports
    m.ports['D_0'].set_signal(Signal.HIGH)
    m.ports['D_1'].set_signal(Signal.LOW, index=1)
    m.ports['D_2'].set_signal(Signal.FLOATING, index=2)

    # Change S
    m.ports['S'].set_signal(Signal.LOW, 1)  # => s_val = 1
    assert m.active_input == m.ports['D_1']
    m.evaluate()
    assert m.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.LOW, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    m.ports['S'].set_signal(Signal.LOW, 0)  # => s_val = 0
    assert m.active_input == m.ports['D_0']
    m.evaluate()
    assert m.output_port.signal_array == {0: Signal.HIGH, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    m.ports['S'].set_signal(Signal.HIGH, 1)  # => s_val = 2
    assert m.active_input == m.ports['D_2']
    m.evaluate()
    assert m.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}


def _init_demux_structure(d: Demultiplexer) -> None:
    for i in range(8):
        d.modify_connection(f'Y_{i}', WireSegmentPath(raw=f'a.wmuxY_{i}.0'), index=0)
        # 2nd is missing on purpose: d.modify_connection(f'Y_{i}', WireSegmentPath(raw=f'a.wmuxY_{i}.1'), index=1)
        d.modify_connection(f'Y_{i}', WireSegmentPath(raw=f'a.wmuxY_{i}.2'), index=2)
        d.modify_connection(f'Y_{i}', WireSegmentPath(raw=f'a.wmuxY_{i}.3'), index=3)

    d.modify_connection('D', WireSegmentPath(raw='a.wmuxD_1.0'), index=0)
    # 2nd is missing on purpose: d.modify_connection('D', WireSegmentPath(raw='a.wmuxD_1.1'), index=1)
    d.modify_connection('D', WireSegmentPath(raw='a.wmuxD_1.2'), index=2)
    d.modify_connection('D', WireSegmentPath(raw='a.wmuxD_1.3'), index=3)

    for i in range(3):
        d.modify_connection('S', WireSegmentPath(raw=f'a.wmuxS.{i}'), index=i)


def test_demux_structure() -> None:
    with pytest.raises(ValidationError):
        Demultiplexer(raw_path='a.demux_inst', bit_width=0, width=4, module=None)
    d = Demultiplexer(raw_path='a.demux_inst', bit_width=3, width=4, module=None)

    assert d.name == 'demux_inst'
    assert d.instance_type == '§demux'
    assert d.bit_width == 3
    assert len(d.y_ports) == 8
    assert d.s_port == d.ports['S']
    assert d.input_port == d.ports['D']
    assert len(d.ports) == 8 + 1 + 1  # 8 data outputs, 1 control input (3-bit wide) and 1 input
    assert len(d.connections) == 8 + 1 + 1  # 8 outputs, 1 control input (3-bit wide) and 1 input
    assert 'Y_0' in d.ports
    assert 'Y_7' in d.ports
    assert 'Y_8' not in d.ports
    assert 'S' in d.ports
    assert 'D' in d.ports
    assert d.ports['Y_0'].width == 4
    assert d.ports['S'].width == 3
    assert d.ports['D'].width == 4
    assert not d.s_defined
    assert d.s_val == -1
    assert d.active_output is None
    assert d.verilog_template == 'always @(*) begin\n\tcase ({sel})\n{cases}\n\tendcase\nend'
    assert d.input_port.signal is Signal.UNDEFINED
    with pytest.raises(NotImplementedError):
        d.output_port.signal

    _init_demux_structure(d)
    set_curr_module()
    case_str = ''
    for i in range(8):
        case_str += f"\t\t3'b{format(i, '03b')} : " + '{' + f'wmuxY_{i}[3:2], wmuxY_{i}[0]' + '} <= {wmuxD_1[3:2], wmuxD_1[0]};\n'
    target_str = 'always @(*) begin\n\tcase (wmuxS)\n' + case_str + '\tendcase\nend'
    save_results(target_str + '\n\n\n' + d.verilog, 'txt')
    assert d.verilog == target_str


def test_demux_behavior() -> None:
    d = Demultiplexer(raw_path='a.demux_inst', bit_width=3, width=4, module=None)
    _init_demux_structure(d)

    # Select Ports
    d.ports['S'].set_signal(Signal.HIGH, 0)  # 1 => 1
    d.ports['S'].set_signal(Signal.HIGH, 1)  # 2 => 1
    d.ports['S'].set_signal(Signal.LOW, 2)  # 4 => 0

    assert d.s_defined
    assert d.s_val == 3  # S_0 + S_1 = 1 + 2 => s_val = 3
    assert d.active_output == d.ports['Y_3']
    d.evaluate()
    with pytest.raises(NotImplementedError):
        d.output_port

    d.ports['D'].set_signal(Signal.HIGH)

    # Change S
    d.ports['S'].set_signal(Signal.LOW, 1)  # => s_val = 1
    assert d.active_output == d.ports['Y_1']
    assert d.ports['Y_1'].signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    d.evaluate()
    assert d.ports['Y_0'].signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    assert d.ports['Y_1'].signal_array == {0: Signal.HIGH, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    assert d.ports['Y_2'].signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    d.ports['S'].set_signal(Signal.LOW, 0)  # => s_val = 0
    assert d.active_output == d.ports['Y_0']
    assert d.ports['Y_0'].signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    d.evaluate()
    assert d.ports['Y_0'].signal_array == {0: Signal.HIGH, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    assert d.ports['Y_1'].signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    assert d.ports['Y_2'].signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    d.ports['S'].set_signal(Signal.HIGH, 1)  # => s_val = 2
    assert d.active_output == d.ports['Y_2']
    assert d.ports['Y_2'].signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    d.evaluate()
    assert d.ports['Y_0'].signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    assert d.ports['Y_1'].signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    assert d.ports['Y_2'].signal_array == {0: Signal.HIGH, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}


def test_adder_structure() -> None:
    from netlist_carpentry.utils.gate_lib import Adder

    a = Adder(raw_path='a.adder_inst', width=4, module=None)

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
    set_curr_module()
    with pytest.raises(ValueError):
        a.verilog
    a.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    target_str = "assign {carry, wire} = {wireA2, 2'bx1, wireA1[0]} + {wireB[3], 1'bx, wireB[1:0]};"
    assert a.verilog == target_str

    with pytest.raises(EvaluationError):
        a._calc_output()


def test_adder_behavior() -> None:
    from netlist_carpentry.utils.gate_lib import Adder

    a = Adder(raw_path='a.adder_inst', width=4, module=None)
    set_curr_module()

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

    a.parameters['B_SIGNED'] = 1
    a.tie_port('B', 0, '0')
    a.tie_port('B', 1, '1')
    a.tie_port('B', 2, '0')
    a.tie_port('B', 3, '1')  # 1010 in two's complement: -6
    a.evaluate()  # 12 + (-6) = 6
    assert a.output_port.signal_array == {0: Signal.LOW, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.LOW, 4: Signal.LOW}
    a.tie_port('A', 3, 'Z')
    with pytest.raises(EvaluationError):
        a.evaluate()


def test_subtractor_structure() -> None:
    from netlist_carpentry.utils.gate_lib import Subtractor

    s = Subtractor(raw_path='a.subtractor_inst', width=4, module=None)

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
    set_curr_module()
    with pytest.raises(ValueError):
        s.verilog
    s.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    target_str = "assign wire = {wireA2, 2'bx1, wireA1[0]} - {wireB[3], 1'bx, wireB[1:0]};"
    assert s.verilog == target_str


def test_subtractor_behavior() -> None:
    from netlist_carpentry.utils.gate_lib import Subtractor

    s = Subtractor(raw_path='a.subtractor_inst', width=4, module=None)
    set_curr_module()

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
    s.parameters['B_SIGNED'] = 1
    s.tie_port('B', 0, '1')
    s.tie_port('B', 1, '0')
    s.tie_port('B', 2, '1')
    s.tie_port('B', 3, '1')  # 1101 in two's complement: -3
    s.evaluate()  # 12 - (-3) = 15 ==> 01111
    assert s.output_port.signal_array == {0: Signal.HIGH, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.HIGH, 4: Signal.LOW}
    s.tie_port('A', 3, 'Z')
    with pytest.raises(EvaluationError):
        s.evaluate()


def test_multiplier_structure() -> None:
    from netlist_carpentry.utils.gate_lib import Multiplier

    m = Multiplier(raw_path='a.multiplier_inst', width=4, module=None)

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
    set_curr_module()
    with pytest.raises(ValueError):
        m.verilog
    m.modify_connection('Y', WireSegmentPath(raw='a.wire.2'), index=2)
    target_str = "assign {carry, wire} = {wireA2, 2'bx1, wireA1[0]} * {wireB[3], 1'bx, wireB[1:0]};"
    assert m.verilog == target_str


def test_multiplier_behavior() -> None:
    from netlist_carpentry.utils.gate_lib import Multiplier

    m = Multiplier(raw_path='a.multiplier_inst', width=4, module=None)
    set_curr_module()

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
    m.parameters['B_SIGNED'] = 1
    m.tie_port('B', 0, '1')
    m.tie_port('B', 1, '0')
    m.tie_port('B', 2, '1')
    m.tie_port('B', 3, '1')  # 1101 in two's complement: -3
    m.evaluate()  # 4 * (-3) = -12 ==> 10100 in two's complement
    assert m.output_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.HIGH, 3: Signal.LOW, 4: Signal.HIGH}
    m.tie_port('A', 3, 'Z')
    with pytest.raises(EvaluationError):
        m.evaluate()


def test_clocked_gate() -> None:
    from netlist_carpentry.utils.gate_lib import _ClockedGate

    g = _ClockedGate(instance_type='clocked_gate', raw_path='a.clocked_gate_inst', clk_polarity=Signal.LOW, rst_polarity=Signal.LOW, module=None)

    assert g.name == 'clocked_gate_inst'
    assert g.instance_type == 'clocked_gate'
    assert g.rst_val == {0: Signal.LOW}
    assert g.clk_polarity is Signal.LOW
    assert g.rst_polarity is Signal.LOW
    assert 'CLK' in g.ports
    assert 'RST' in g.ports
    assert g.ports['CLK'].is_input
    assert g.ports['RST'].is_input
    assert g.ports['CLK'] is g.clk_port
    assert g.ports['RST'] is g.rst_port
    assert g.clk_port.width == 1
    assert g.rst_port.width == 1
    assert g.clk_signal is Signal.FLOATING
    assert not g.clk_redge
    assert not g.clk_fedge
    assert not g.rst_redge
    assert not g.rst_fedge
    assert not g.is_combinatorial
    assert g.is_sequential
    assert g.verilog_template == 'always @({clk} or {rst}) begin\n\t{behavior}\nend'


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


def test_dff_structure() -> None:
    ff = DFF(raw_path='a.dff_inst', rst_polarity=Signal.LOW, width=4, module=None)

    assert ff.name == 'dff_inst'
    assert ff.instance_type == '§dff'
    assert ff.clk_polarity is Signal.HIGH
    assert ff.en_polarity is Signal.HIGH
    assert ff.rst_polarity is Signal.LOW
    assert ff.rst_val == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW}
    assert not ff.init_finished

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
    assert ff.clk_port._listeners == {ff}
    assert ff.rst_port._listeners == {ff}
    assert ff.verilog_template == 'always @({clk}{two_sig}{rst}) begin\n\t{set_out}\nend'

    _init_dff_structure(ff)
    set_curr_module()
    target_v = "always @(posedge clk) begin\n\twire\t<=\t{wireA2, 2'bx1, wireA1[0]};\nend"
    assert ff.verilog == target_v

    _init_dff_structure(ff, True)
    save_results(ff.verilog, 'txt')
    assert (
        ff.verilog_template
        == 'always @({clk}{two_sig}{rst}) begin\n\tif ({is_rst}) begin\n\t\t{rst_out}\n\tend else{enable}begin\n\t\t{set_out}\n\tend\nend'
    )
    target_v = "always @(posedge clk or negedge rst) begin\n\tif (~rst) begin\n\t\twire\t<=\t4'b0000;\n\tend else if (en) begin\n\t\twire\t<=\t{wireA2, 2'bx1, wireA1[0]};\n\tend\nend"
    assert ff.verilog == target_v


def _clk(ff: DFF, cycles: int = 1) -> None:
    for i in range(cycles):
        ff.set_clk(Signal.HIGH)
        assert ff._prev_clk is not Signal.HIGH
        assert ff._curr_clk is Signal.HIGH
        assert ff.clk_redge or not ff._init_finished  # When FF init not finished, rising edge wont be detected, because previous value is x
        assert not ff.clk_fedge
        ff.set_clk(Signal.LOW)
        assert ff._prev_clk is not Signal.LOW
        assert ff._curr_clk is Signal.LOW
        assert not ff.clk_redge
        assert ff.clk_fedge


def test_dff_behavior_init() -> None:
    ff = DFF(raw_path='a.dff_inst', width=4, module=None)
    _init_dff_structure(ff, True)

    assert not ff.init_finished
    assert not ff.in_reset
    assert ff.output_port.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED, 2: Signal.UNDEFINED, 3: Signal.UNDEFINED}
    _clk(ff)
    ff.set_rst(Signal.HIGH)
    assert not ff.init_finished
    assert ff.in_reset
    assert ff.output_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW}
    _clk(ff)
    ff.set_rst(Signal.LOW)
    assert ff.init_finished
    assert not ff.in_reset
    assert ff.output_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW}
    _clk(ff)
    assert ff.output_port.signal_array == {0: Signal.LOW, 1: Signal.LOW, 2: Signal.LOW, 3: Signal.LOW}
    _clk(ff)
    ff.rst_val_int = 0xF
    ff.set_rst(Signal.HIGH)
    assert ff.init_finished
    assert ff.in_reset
    assert ff.output_port.signal_array == {0: Signal.HIGH, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.HIGH}
    _clk(ff)
    ff.set_rst(Signal.LOW)
    assert ff.init_finished
    assert not ff.in_reset
    assert ff.output_port.signal_array == {0: Signal.HIGH, 1: Signal.HIGH, 2: Signal.HIGH, 3: Signal.HIGH}


def test_dff_behavior_clk() -> None:
    ff = DFF(raw_path='a.dff_inst', width=4, module=None)
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


def test_dff_behavior_4bit() -> None:
    ff = DFF(raw_path='a.dff_inst', width=4, module=None)
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


def test_dff_behavior_en() -> None:
    ff = DFF(raw_path='a.dff_inst', module=None)
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

    # EN Unconnected -> Undefined enable signal -> do not enable
    ff.modify_connection('EN', WireSegmentPath(raw=''))
    assert ff.en_port.signal is Signal.FLOATING
    ff.input_port.set_signal(Signal.HIGH)
    assert ff.output_port.signal is Signal.LOW
    _clk(ff)
    assert ff.output_port.signal is Signal.LOW

    # EN High
    ff.modify_connection('EN', WireSegmentPath(raw='a.enable_signal.0'))
    ff.set_en(Signal.HIGH)
    assert ff.en_port.signal is Signal.HIGH
    assert ff.output_port.signal is Signal.LOW

    ff.input_port.set_signal(Signal.HIGH)
    assert ff.output_port.signal is Signal.LOW
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


def test_edge_detection() -> None:
    ff = DFF(raw_path='a.dff_inst', module=None)

    assert ff._edge_detection(Signal.UNDEFINED, Signal.UNDEFINED) == (Signal.UNDEFINED, False, False)
    assert ff._edge_detection(Signal.UNDEFINED, Signal.LOW) == (Signal.UNDEFINED, False, False)
    assert ff._edge_detection(Signal.UNDEFINED, Signal.HIGH) == (Signal.UNDEFINED, False, False)
    assert ff._edge_detection(Signal.UNDEFINED, Signal.FLOATING) == (Signal.UNDEFINED, False, False)
    assert ff._edge_detection(Signal.LOW, Signal.UNDEFINED) == (Signal.LOW, False, False)
    assert ff._edge_detection(Signal.LOW, Signal.LOW) == (Signal.LOW, False, False)
    assert ff._edge_detection(Signal.LOW, Signal.HIGH) == (Signal.LOW, True, False)
    assert ff._edge_detection(Signal.LOW, Signal.FLOATING) == (Signal.LOW, False, False)
    assert ff._edge_detection(Signal.HIGH, Signal.UNDEFINED) == (Signal.HIGH, False, False)
    assert ff._edge_detection(Signal.HIGH, Signal.LOW) == (Signal.HIGH, False, True)
    assert ff._edge_detection(Signal.HIGH, Signal.HIGH) == (Signal.HIGH, False, False)
    assert ff._edge_detection(Signal.HIGH, Signal.FLOATING) == (Signal.HIGH, False, False)
    assert ff._edge_detection(Signal.FLOATING, Signal.UNDEFINED) == (Signal.FLOATING, False, False)
    assert ff._edge_detection(Signal.FLOATING, Signal.LOW) == (Signal.FLOATING, False, False)
    assert ff._edge_detection(Signal.FLOATING, Signal.HIGH) == (Signal.FLOATING, False, False)
    assert ff._edge_detection(Signal.FLOATING, Signal.FLOATING) == (Signal.FLOATING, False, False)


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


def test_dlatch_structure() -> None:
    dl = DLatch(raw_path='a.dlatch_inst', width=4, module=None)

    assert dl.name == 'dlatch_inst'
    assert dl.instance_type == '§dlatch'
    assert dl.en_polarity is Signal.HIGH
    assert not dl.init_finished

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
    set_curr_module()
    target_v = "always @(*) begin\n\tif (clk) begin\n\t\t{wire[3], wire[1:0]} = {wireA2, 1'b1, wireA1[0]};\n\tend\nend"
    dl.en_polarity = Signal.LOW
    target_v = "always @(*) begin\n\tif (~clk) begin\n\t\t{wire[3], wire[1:0]} = {wireA2, 1'b1, wireA1[0]};\n\tend\nend"
    save_results(dl.verilog, 'txt')
    assert dl.verilog == target_v


def test_dlatch_behavior() -> None:
    dl = DLatch(raw_path='a.dlatch_inst', width=4, module=None)

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


def test_get() -> None:
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
