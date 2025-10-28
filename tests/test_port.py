# mypy: disable-error-code="unreachable,comparison-overlap"
import copy
import os

import pytest
from pydantic import ValidationError

from netlist_carpentry import WIRE_SEGMENT_X
from netlist_carpentry.core.exceptions import (
    IdentifierConflictError,
    InvalidSignalError,
    ObjectLockedError,
    ObjectNotFoundError,
    ParentNotFoundError,
)
from netlist_carpentry.core.netlist_elements.element_path import WirePath, WireSegmentPath
from netlist_carpentry.core.netlist_elements.element_type import EType
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.netlist_elements.port import Port
from netlist_carpentry.core.netlist_elements.port_segment import PortSegment
from netlist_carpentry.core.netlist_elements.wire import Signal
from netlist_carpentry.core.port_direction import PortDirection


@pytest.fixture
def standard_port_in() -> Port[Instance]:
    from utils import standard_port_in

    return standard_port_in()


@pytest.fixture
def standard_port_out() -> Port[Module]:
    from utils import standard_port_out

    return standard_port_out()


@pytest.fixture
def locked_port() -> Port[Module]:
    from utils import locked_port as ip

    return ip()


def test_port_creation(standard_port_in: Port[Instance], standard_port_out: Port[Module]) -> None:
    assert standard_port_in.name == 'test_port1'
    assert standard_port_in.path.name == 'test_port1'
    assert standard_port_in.path.type is EType.PORT
    assert standard_port_in.path.raw == 'test_module1.test_port1'
    assert standard_port_in.width == 1
    assert standard_port_in.offset == 0
    assert standard_port_in.direction == PortDirection.IN
    assert standard_port_in.is_instance_port
    assert not standard_port_in.is_module_port
    assert standard_port_in.type is EType.PORT
    assert standard_port_in.signal is Signal.FLOATING  # Unconnected load port => Signal.FLOATING
    assert standard_port_in.signal_array == {0: Signal.FLOATING}
    assert standard_port_in.signal_str == 'z'
    assert standard_port_in._listeners == {0} - {0}  # Funny eyes <=> empty set

    assert standard_port_out.width == 2
    assert standard_port_out.direction == PortDirection.OUT
    assert not standard_port_out.is_instance_port
    assert standard_port_out.is_module_port
    assert standard_port_out[0].path.raw == 'test_module1.test_port2.0'
    assert standard_port_out[1].path.raw == 'test_module1.test_port2.1'
    assert standard_port_out[0] == standard_port_out[0]
    assert standard_port_out[1] == standard_port_out[1]
    assert standard_port_out._listeners == {0} - {0}  # Funny eyes <=> empty set
    assert standard_port_out.signal is Signal.UNDEFINED  # Unconnected driving port (i.e. no load) => Signal.UNDEFINED until evaluated
    assert standard_port_out.signal_array == {0: Signal.UNDEFINED, 1: Signal.UNDEFINED}
    assert standard_port_out.signal_str == 'xx'
    assert standard_port_out.has_undefined_signals
    assert not standard_port_out.is_tied_partly

    assert standard_port_in.can_carry_signal

    with pytest.raises(ParentNotFoundError):
        Port(raw_path='a.b', direction=PortDirection.IN, module_or_instance=None).is_module_port


def test_port_len(standard_port_in: Port[Instance], standard_port_out: Port[Module]) -> None:
    assert len(standard_port_in) == 1
    assert len(standard_port_in) == len(standard_port_in.segments)

    assert len(standard_port_out) == 2
    assert len(standard_port_out) == len(standard_port_out.segments)


def test_port_iter(standard_port_in: Port[Instance], standard_port_out: Port[Module]) -> None:
    for idx, seg in standard_port_in:
        assert standard_port_in[idx] == seg
    for idx, seg in standard_port_out:
        assert standard_port_out[idx] == seg


def test_port_parent_init() -> None:
    with pytest.raises(ValidationError):
        Port(raw_path='a.b.c', direction=PortDirection.IN, module_or_instance=NetlistElement(raw_path='a.b'))


def test_parent(standard_port_in: Port[Instance]) -> None:
    from utils import empty_module

    m = empty_module()
    standard_port_in.module_or_instance = m
    parent = standard_port_in.parent
    assert parent == m

    standard_port_in.module_or_instance = None
    with pytest.raises(ParentNotFoundError):
        standard_port_in.parent


def test_port_signal_int(standard_port_in: Port[Instance], standard_port_out: Port[Module]) -> None:
    assert standard_port_in.signal_int is None
    standard_port_in.tie_signal('1', 0)
    assert standard_port_in.signal_int == 1
    standard_port_in.set_signed(True)
    standard_port_in.tie_signal('1', 0)
    assert standard_port_in.signal_int == -1

    assert standard_port_out.signal_int is None
    standard_port_out[0].set_ws_path('')
    standard_port_out[1].set_ws_path('')
    standard_port_out.tie_signal('1', 0)
    standard_port_out.tie_signal('1', 1)
    assert standard_port_out.signal_int == 3
    standard_port_out.set_signed(True)
    assert standard_port_out.signal_int == -1
    standard_port_out.tie_signal('0', 0)
    standard_port_out.tie_signal('1', 1)  # MSB_FIRST is false for standard_port_out => in 01, the 0 is actually the LSB
    assert standard_port_out.signal_int == 1


def test_port_is_partly_connected(standard_port_out: Port[Module]) -> None:
    assert standard_port_out.is_connected_partly

    standard_port_out[0].set_ws_path('')

    assert standard_port_out.is_connected_partly

    standard_port_out[1].set_ws_path('')

    assert not standard_port_out.is_connected_partly


def test_port_is_fully_connected(standard_port_out: Port[Module]) -> None:
    assert standard_port_out.is_connected

    standard_port_out[0].set_ws_path('')

    assert not standard_port_out.is_connected

    standard_port_out[1].set_ws_path('')

    assert not standard_port_out.is_connected


def test_port_is_unconnected(standard_port_out: Port[Module]) -> None:
    assert not standard_port_out.is_unconnected
    assert not standard_port_out.is_unconnected_partly

    standard_port_out[0].set_ws_path('')

    assert not standard_port_out.is_unconnected
    assert standard_port_out.is_unconnected_partly

    standard_port_out[1].set_ws_path('')

    assert standard_port_out.is_unconnected
    assert standard_port_out.is_unconnected_partly


def test_port_is_floating(standard_port_out: Port[Module]) -> None:
    assert not standard_port_out.is_floating
    assert not standard_port_out.is_floating_partly

    standard_port_out[0].set_ws_path('Z')

    assert not standard_port_out.is_floating
    assert standard_port_out.is_floating_partly

    standard_port_out[1].set_ws_path('Z')

    assert standard_port_out.is_floating
    assert standard_port_out.is_floating_partly


def test_port_is_tied(standard_port_out: Port[Module]) -> None:
    assert not standard_port_out.is_tied_defined
    assert not standard_port_out.is_tied_defined_partly
    assert not standard_port_out.is_tied_undefined
    assert not standard_port_out.is_tied_undefined_partly
    assert not standard_port_out.is_tied

    standard_port_out[0].set_ws_path('')
    standard_port_out[0].tie_signal('0')
    assert not standard_port_out.is_tied_defined
    assert standard_port_out.is_tied_defined_partly
    assert not standard_port_out.is_tied_undefined
    assert not standard_port_out.is_tied_undefined_partly
    assert not standard_port_out.is_tied

    standard_port_out[1].set_ws_path('')
    standard_port_out[1].tie_signal('1')
    assert standard_port_out.is_tied_defined
    assert standard_port_out.is_tied_defined_partly
    assert not standard_port_out.is_tied_undefined
    assert not standard_port_out.is_tied_undefined_partly
    assert standard_port_out.is_tied

    standard_port_out[0].tie_signal('Z')
    assert not standard_port_out.is_tied_defined
    assert standard_port_out.is_tied_defined_partly
    assert not standard_port_out.is_tied_undefined
    assert standard_port_out.is_tied_undefined_partly
    assert standard_port_out.is_tied

    standard_port_out[1].tie_signal('X')
    assert not standard_port_out.is_tied_defined
    assert not standard_port_out.is_tied_defined_partly
    assert standard_port_out.is_tied_undefined
    assert standard_port_out.is_tied_undefined_partly
    assert standard_port_out.is_tied


def test_port_offset(standard_port_out: Port[Module]) -> None:
    assert standard_port_out.offset == 0
    standard_port_out.remove_port_segment(0)  # Now only one segment left: the one with index 1
    assert standard_port_out.offset == 1
    standard_port_out.remove_port_segment(1)  # Now no segments left: no offset
    assert standard_port_out.offset is None


def test_port_signed_unsigned(standard_port_out: Port[Module]) -> None:
    assert standard_port_out.parameters == {}
    assert not standard_port_out.signed
    assert standard_port_out.unsigned
    standard_port_out.parameters['signed'] = 1
    assert standard_port_out.signed
    assert not standard_port_out.unsigned
    standard_port_out.parameters['signed'] = 23  # Should not happen, but then treat it as non-zero==>signed
    assert standard_port_out.signed
    assert not standard_port_out.unsigned
    standard_port_out.parameters['signed'] = '1'  # Should not happen, but then treat it as non-zero==>signed
    assert standard_port_out.signed
    assert not standard_port_out.unsigned
    standard_port_out.parameters['signed'] = True  # Should not happen, but then treat it as non-zero==>signed
    assert standard_port_out.signed
    assert not standard_port_out.unsigned
    standard_port_out.parameters['signed'] = 0
    assert not standard_port_out.signed
    assert standard_port_out.unsigned
    standard_port_out.parameters['signed'] = '0'  # Should not happen, but then treat it as zero==>unsigned
    assert not standard_port_out.signed
    assert standard_port_out.unsigned
    standard_port_out.parameters['signed'] = False  # Should not happen, but then treat it as zero==>unsigned
    assert not standard_port_out.signed
    assert standard_port_out.unsigned


def test_port_is_input(standard_port_in: Port[Instance], standard_port_out: Port[Module]) -> None:
    assert standard_port_in.is_input
    assert not standard_port_out.is_input

    standard_port_out.direction = PortDirection.IN_OUT
    assert standard_port_out.is_input
    assert standard_port_out.direction == PortDirection.IN_OUT


def test_port_is_output(standard_port_in: Port[Instance], standard_port_out: Port[Module]) -> None:
    assert not standard_port_in.is_output
    assert standard_port_out.is_output

    standard_port_in.direction = PortDirection.IN_OUT
    assert standard_port_in.is_output
    assert standard_port_in.direction == PortDirection.IN_OUT


def test_port_is_driver(standard_port_in: Port[Instance], standard_port_out: Port[Module]) -> None:
    assert not standard_port_in.is_driver
    assert not standard_port_out.is_driver

    standard_port_in.module_or_instance = Module(raw_path='a')
    standard_port_out.module_or_instance = Instance(raw_path='a.b', instance_type='c', module=None)
    assert standard_port_in.is_driver
    assert standard_port_out.is_driver


def test_port_is_load(standard_port_in: Port[Instance], standard_port_out: Port[Module]) -> None:
    assert standard_port_in.is_load
    assert standard_port_out.is_load

    standard_port_in.module_or_instance = Module(raw_path='a')
    standard_port_out.module_or_instance = Instance(raw_path='a.b', instance_type='c', module=None)
    assert not standard_port_in.is_load
    assert not standard_port_out.is_load


def test_connected_wire_segments(standard_port_in: Port[Instance], standard_port_out: Port[Module]) -> None:
    set1 = standard_port_in.connected_wire_segments
    assert len(set1) == 1
    assert standard_port_in[0].ws_path in set1

    standard_port_out[1].change_connection(WireSegmentPath(raw='test_module1.d.0'))
    set2 = standard_port_out.connected_wire_segments
    assert len(set2) == 2
    assert standard_port_out[0].ws_path in set2
    assert standard_port_out[1].ws_path in set2

    pseg = standard_port_in.get_port_segment(0)
    pseg.set_name('1')
    standard_port_in._add_port_segment(pseg)
    set3 = standard_port_in.connected_wire_segments
    assert len(set3) == 1
    assert standard_port_in[0].ws_path in set3
    assert standard_port_in[1].ws_path in set3

    p = Port(raw_path='', direction=PortDirection.IN_OUT, module_or_instance=None)
    set4 = p.connected_wire_segments
    assert not set4


def test_connected_wires(standard_port_in: Port[Instance], standard_port_out: Port[Module]) -> None:
    assert len(standard_port_in.connected_wires) == 0
    assert standard_port_out.connected_wires == {WirePath(raw='test_module1.wire1')}
    standard_port_out[1].change_connection(WireSegmentPath(raw='test_module1.d.0'))
    assert standard_port_out.connected_wires == {WirePath(raw='test_module1.wire1'), WirePath(raw='test_module1.d')}


def test_add_port_segment(standard_port_in: Port[Instance], locked_port: Port[Module]) -> None:
    seg2 = PortSegment(raw_path=standard_port_in.raw_path + '.1', port=standard_port_in)
    added = standard_port_in._add_port_segment(seg2)
    assert added == seg2
    assert len(standard_port_in.segments) == 2
    assert standard_port_in[1] == seg2
    assert seg2.port is standard_port_in

    seg3 = PortSegment(raw_path=standard_port_in.raw_path + '.1', port=standard_port_in)
    with pytest.raises(IdentifierConflictError):
        standard_port_in._add_port_segment(seg3)
    assert len(standard_port_in.segments) == 2
    assert standard_port_in[1] == seg2

    assert len(locked_port.segments) == 1
    with pytest.raises(ObjectLockedError):
        locked_port._add_port_segment(seg2)
    assert len(locked_port.segments) == 1
    assert seg2.port is not locked_port


def test_create_port_segment(standard_port_in: Port[Instance], locked_port: Port[Module]) -> None:
    is_created = standard_port_in.create_port_segment(1)
    assert is_created == standard_port_in[1]
    assert len(standard_port_in.segments) == 2

    with pytest.raises(IdentifierConflictError):
        standard_port_in.create_port_segment(1)
    assert len(standard_port_in.segments) == 2

    assert len(locked_port.segments) == 1
    with pytest.raises(ObjectLockedError):
        locked_port.create_port_segment(1)
    assert len(locked_port.segments) == 1


def test_create_port_segments(standard_port_in: Port[Instance], locked_port: Port[Module]) -> None:
    with pytest.raises(IdentifierConflictError):
        standard_port_in.create_port_segments(3)
    standard_port_in.segments.clear()

    port_segments = standard_port_in.create_port_segments(3, 1)
    assert port_segments == standard_port_in.segments
    assert len(standard_port_in.segments) == 3
    assert standard_port_in[1].name == '1'
    assert standard_port_in[2].name == '2'
    assert standard_port_in[3].name == '3'
    assert standard_port_in[1].index == 1
    assert standard_port_in[2].index == 2
    assert standard_port_in[3].index == 3

    assert len(locked_port.segments) == 1
    with pytest.raises(ObjectLockedError):
        locked_port.create_port_segments(3)
    assert len(locked_port.segments) == 1


def test_remove_port_segment(standard_port_in: Port[Instance], locked_port: Port[Module]) -> None:
    standard_port_in.remove_port_segment(0)
    assert len(standard_port_in.segments) == 0

    with pytest.raises(ObjectNotFoundError):
        standard_port_in.remove_port_segment(0)
    assert len(standard_port_in.segments) == 0

    assert len(locked_port.segments) == 1
    with pytest.raises(ObjectLockedError):
        locked_port.remove_port_segment(0)
    assert len(locked_port.segments) == 1


def test_get_port_segment(standard_port_in: Port[Instance]) -> None:
    seg = standard_port_in.get_port_segment(0)
    assert seg.name == '0'

    seg = standard_port_in.get_port_segment(69)
    assert seg is None


def test_tie_signal(standard_port_in: Port[Instance]) -> None:
    assert standard_port_in.is_load
    assert standard_port_in.has_undefined_signals
    assert standard_port_in.is_tied_partly
    standard_port_in[0].set_ws_path('')

    with pytest.raises(InvalidSignalError):
        standard_port_in.tie_signal('abc', 0)
    assert standard_port_in[0].raw_ws_path == ''

    standard_port_in.tie_signal('0', 0)
    assert not standard_port_in.has_undefined_signals
    assert standard_port_in.is_tied_partly
    assert standard_port_in[0].raw_ws_path == '0'
    assert standard_port_in[0].signal == Signal.LOW

    standard_port_in.tie_signal('1', 0)
    assert not standard_port_in.has_undefined_signals
    assert standard_port_in.is_tied_partly
    assert standard_port_in[0].raw_ws_path == '1'
    assert standard_port_in[0].signal == Signal.HIGH

    standard_port_in.tie_signal('Z', 0)
    assert standard_port_in.has_undefined_signals
    assert standard_port_in.is_tied_partly
    assert standard_port_in[0].raw_ws_path == 'Z'
    assert standard_port_in[0].signal == Signal.FLOATING

    with pytest.raises(ObjectNotFoundError):
        standard_port_in.tie_signal('0', 1)
    assert standard_port_in.has_undefined_signals
    assert standard_port_in.is_tied_partly


def test_set_signal(standard_port_in: Port[Instance]) -> None:
    assert standard_port_in.is_load
    standard_port_in[0].set_ws_path('test_module1.d')
    standard_port_in.set_signal(signal=Signal.HIGH)
    assert standard_port_in.signal is Signal.HIGH
    standard_port_in.set_signal(signal=0)
    assert standard_port_in.signal is Signal.LOW
    standard_port_in.set_signal(signal='Z')
    assert standard_port_in.signal is Signal.FLOATING

    standard_port_in.module_or_instance = Module(raw_path='a')
    assert standard_port_in.is_driver
    standard_port_in.set_signal(signal=Signal.LOW)
    assert standard_port_in.signal is Signal.LOW

    standard_port_in.set_signal(signal=Signal.HIGH)
    assert standard_port_in.signal is Signal.HIGH


def test_set_signals(standard_port_out: Port[Module]) -> None:
    standard_port_out.msb_first = False
    standard_port_out.set_signals(2)  # 01
    assert standard_port_out.signal_int == 2
    assert standard_port_out.signal_array == {1: Signal.LOW, 0: Signal.HIGH}  # by default: standard_port_out is lsbfirst
    assert standard_port_out.signal_str == '01'
    standard_port_out.msb_first = True
    standard_port_out.set_signals(2)  # 10
    assert standard_port_out.signal_int == 2
    assert standard_port_out.signal_array == {1: Signal.HIGH, 0: Signal.LOW}  # standard_port_out is now msbfirst
    assert standard_port_out.signal_str == '10'
    standard_port_out.set_signals(2)  # 10
    assert standard_port_out.signal_int == 2
    standard_port_out.set_signals('11')  # 3
    assert standard_port_out.signal_int == 3
    standard_port_out.set_signals('xz')
    assert standard_port_out.signal_int is None
    assert standard_port_out.signal_array == {0: Signal.FLOATING, 1: Signal.UNDEFINED}
    standard_port_out.set_signals({0: Signal.LOW, 1: Signal.HIGH})  # 2
    assert standard_port_out.signal_int == 2
    standard_port_out.set_signed(True)
    standard_port_out.set_signals(-1)  # 11
    assert standard_port_out.signed
    assert standard_port_out.parameters['signed'] == 1
    assert standard_port_out.signal_int == -1
    standard_port_out.set_signed(False)
    standard_port_out.remove_port_segment(0)
    # only one segment left, it's the one with index 1 (which is "1"), but the integer value does not care about the offset
    assert standard_port_out.signal_int == 1
    standard_port_out.remove_port_segment(1)
    with pytest.raises(IndexError):
        standard_port_out.set_signals('1010')  # No segments left, cannot set signals


def test_count_signal(standard_port_out: Port[Module]) -> None:
    assert standard_port_out.count_signals(Signal.UNDEFINED) == 2
    assert standard_port_out.count_signals(Signal.FLOATING) == 0
    assert standard_port_out.count_signals(Signal.HIGH) == 0
    assert standard_port_out.count_signals(Signal.LOW) == 0

    standard_port_out.set_signal(Signal.HIGH, index=1)
    assert standard_port_out.count_signals(Signal.UNDEFINED) == 1
    assert standard_port_out.count_signals(Signal.FLOATING) == 0
    assert standard_port_out.count_signals(Signal.HIGH) == 1
    assert standard_port_out.count_signals(Signal.LOW) == 0


def test_set_signed(standard_port_out: Port[Module]) -> None:
    assert not standard_port_out.signed
    is_set = standard_port_out.set_signed(True)
    assert is_set
    assert standard_port_out.signed
    is_set = standard_port_out.set_signed(True)
    assert not is_set
    assert standard_port_out.signed
    is_set = standard_port_out.set_signed(0)
    assert is_set
    assert not standard_port_out.signed


def test_change_connection(standard_port_in: Port[Instance], standard_port_out: Port[Module]) -> None:
    standard_port_in.change_connection(WIRE_SEGMENT_X.path)
    assert standard_port_in[0].raw_ws_path == 'X'

    with pytest.raises(ObjectNotFoundError):
        standard_port_in.change_connection(WIRE_SEGMENT_X.path, 1)

    standard_port_out.change_connection(WireSegmentPath(raw='test_module1'), 1)
    assert standard_port_out[0].raw_ws_path == 'test_module1.wire1.0'
    assert standard_port_out[1].raw_ws_path == 'test_module1'

    standard_port_out.change_connection(WireSegmentPath(raw='test_module1'), -1)
    assert standard_port_out[0].raw_ws_path == 'test_module1'
    assert standard_port_out[1].raw_ws_path == 'test_module1'

    standard_port_in.change_mutability(True)
    with pytest.raises(ObjectLockedError):
        standard_port_in.change_connection(WIRE_SEGMENT_X.path)


def test_set_name(standard_port_out: Port[Module]) -> None:
    standard_port_out.set_name('PORT')
    assert standard_port_out.raw_path == 'test_module1.PORT'
    assert standard_port_out[0].raw_path == 'test_module1.PORT.0'
    assert standard_port_out[1].raw_path == 'test_module1.PORT.1'


def test_change_mutability(standard_port_out: Port[Module]) -> None:
    assert not standard_port_out.locked
    standard_port_out.change_mutability(is_now_locked=True)
    assert standard_port_out.locked
    assert not standard_port_out[0].locked
    assert not standard_port_out[1].locked

    standard_port_out.change_mutability(is_now_locked=True, recursive=True)
    assert standard_port_out.locked
    assert standard_port_out[0].locked
    assert standard_port_out[1].locked


def test_normalize_metadata(standard_port_out: Port[Module]) -> None:
    found = standard_port_out.normalize_metadata()
    assert found == {}
    found = standard_port_out.normalize_metadata(include_empty=True)
    assert found == {'test_module1.test_port2': {}, 'test_module1.test_port2.0': {}, 'test_module1.test_port2.1': {}}
    standard_port_out.metadata.set('key', 'foo')
    standard_port_out.metadata.set('key2', 'bar', 'baz')
    standard_port_out[0].metadata.set('key', 'foo')
    standard_port_out[1].metadata.set('key', 'foo')
    standard_port_out[1].metadata.set('key', 'foo', 'baz')
    found = standard_port_out.normalize_metadata()
    target = {
        'test_module1.test_port2': {'general': {'key': 'foo'}, 'baz': {'key2': 'bar'}},
        'test_module1.test_port2.0': {'general': {'key': 'foo'}},
        'test_module1.test_port2.1': {'general': {'key': 'foo'}, 'baz': {'key': 'foo'}},
    }
    assert found == target

    found = standard_port_out.normalize_metadata(sort_by='category')
    target = {
        'general': {
            'test_module1.test_port2': {'key': 'foo'},
            'test_module1.test_port2.0': {'key': 'foo'},
            'test_module1.test_port2.1': {'key': 'foo'},
        },
        'baz': {'test_module1.test_port2': {'key2': 'bar'}, 'test_module1.test_port2.1': {'key': 'foo'}},
    }
    assert found == target

    # Checks if {"key": "foo"} is part of val
    found = standard_port_out.normalize_metadata(sort_by='category', filter=lambda cat, md: 'key' in md and md['key'] == 'foo')
    target = {
        'general': {
            'test_module1.test_port2': {'key': 'foo'},
            'test_module1.test_port2.0': {'key': 'foo'},
            'test_module1.test_port2.1': {'key': 'foo'},
        },
        'baz': {'test_module1.test_port2.1': {'key': 'foo'}},
    }
    assert found == target

    # Illegal operation should be resolved to False
    found = standard_port_out.normalize_metadata(sort_by='category', filter=lambda cat, md: md.is_integer())
    target = {}
    assert found == target


def test_port_hash(standard_port_in: Port[Instance]) -> None:
    assert hash(standard_port_in) == hash(standard_port_in)

    spi2 = copy.deepcopy(standard_port_in)
    assert hash(standard_port_in) == hash(spi2)

    spi2[0].raw_path = spi2[0].raw_path[:-1] + '42'
    assert hash(standard_port_in) != hash(spi2)


def test_port_str(standard_port_in: Port[Instance]) -> None:
    # Test the string representation of a port
    assert str(standard_port_in) == 'Port "test_port1" with path test_module1.test_port1 (input port)'


def test_port_repr(standard_port_in: Port[Instance]) -> None:
    # Test the representation of a port
    assert repr(standard_port_in) == 'Port(test_port1 at test_module1.test_port1)'


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
