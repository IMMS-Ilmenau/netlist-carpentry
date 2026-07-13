# mypy: disable-error-code="unreachable,comparison-overlap"
import os

import pytest
from pydantic import ValidationError

from netlist_carpentry.core.enums.direction import Direction
from netlist_carpentry.core.enums.element_type import EType
from netlist_carpentry.core.enums.signal import Signal
from netlist_carpentry.core.exceptions import (
    IdentifierConflictError,
    MultipleDriverError,
    ObjectLockedError,
    ObjectNotFoundError,
    ParentNotFoundError,
    UnsupportedOperationError,
)
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.netlist_elements.port import Port
from netlist_carpentry.core.netlist_elements.wire import Wire
from netlist_carpentry.core.netlist_elements.wire_segment import WireSegment
from netlist_carpentry.core.types import SignalArray


@pytest.fixture
def standard_wire() -> Wire:
    from utils import standard_wire

    return standard_wire()


@pytest.fixture
def locked_wire() -> Wire:
    from utils import locked_wire as iw

    return iw()


def _add_multidriver(standard_wire: Wire, name: str = 'p4') -> None:
    p = Port(name=name, direction=Direction.IN, module_or_instance=Module(name='a'))
    p.create_port_segment(1)
    standard_wire[1].add_port_segment(p[1])


def test_wire_creation(standard_wire: Wire) -> None:
    # # Test the creation of a wire
    assert standard_wire.name == 'wire1'
    assert standard_wire.type is EType.WIRE
    assert standard_wire.path.name == 'wire1'
    assert standard_wire.path.type is EType.WIRE
    assert standard_wire.path.raw == 'wire1'
    assert standard_wire.width == 1
    assert standard_wire.offset == 1
    assert standard_wire.signal == Signal.UNDEFINED
    assert standard_wire.signal_array == SignalArray(signals={0: Signal.UNDEFINED})
    assert standard_wire.signal_str == 'x'
    assert standard_wire.signal_int is None
    assert len(standard_wire.segments) == 1
    assert standard_wire[1] == standard_wire[1]
    assert len(standard_wire.connected_port_segments) == 1
    assert len(standard_wire.connected_port_segments[1]) == 3
    # assert standard_wire.is_connected is False
    # assert standard_wire.is_unconnected is False
    # assert standard_wire.is_undefined is not True
    # assert standard_wire.is_defined is not None

    assert standard_wire.can_carry_signal
    standard_wire[1].set_signal('1')
    assert standard_wire.signal == Signal.HIGH
    assert standard_wire.signal_array == SignalArray(signals={0: Signal.HIGH})


def test_wire_len(standard_wire: Wire) -> None:
    assert len(standard_wire) == 1
    assert len(standard_wire) == len(standard_wire.segments)

    empty_wire = Wire(name='', module=Module(name='m'))

    assert len(empty_wire) == 0
    assert len(empty_wire) == len(empty_wire.segments)


def test_wire_iter(standard_wire: Wire) -> None:
    for idx, seg in standard_wire:
        assert standard_wire[idx] == seg


def test_eq(standard_wire: Wire) -> None:
    w1 = standard_wire.model_copy(deep=True)
    assert standard_wire == w1

    w2 = Wire(name='wrong_path', module=Module(name='m'))
    assert standard_wire != w2

    w3 = 'wrong_type'
    assert standard_wire != w3
    assert standard_wire.__eq__(w3) == NotImplemented

    w4 = standard_wire.model_copy(deep=True)
    assert w4 == standard_wire
    assert standard_wire == w4

    w5 = standard_wire.model_copy(deep=True)
    w5[1].port_segments.clear()
    assert not w5 == standard_wire
    assert not standard_wire == w5

    w6 = standard_wire.model_copy(deep=True)
    w6.segments.clear()
    assert not w6 == standard_wire
    assert not standard_wire == w6


def test_wire_parent_init() -> None:
    with pytest.raises(ValidationError):
        Wire(name='c', module=NetlistElement(name='test_module1'))


def test_parent(standard_wire: Wire) -> None:
    from utils import empty_module

    m = empty_module()
    standard_wire.module = m
    parent = standard_wire.parent
    assert parent == m
    assert standard_wire.has_parent

    standard_wire.module = None
    with pytest.raises(ParentNotFoundError):
        standard_wire.parent


def test_wire_offset() -> None:
    from utils import wire_4b

    w = wire_4b()
    assert w.offset == 1
    w.remove_wire_segment(1)
    assert w.offset == 2

    w = Wire(name='c', module=Module(name='m'))
    assert w.offset is None  # No segments: no offset


def test_wire_signed_unsigned(standard_wire: Wire) -> None:
    assert standard_wire.parameters == {}
    assert not standard_wire.signed
    assert standard_wire.unsigned
    standard_wire.parameters['signed'] = 1
    assert standard_wire.signed
    assert not standard_wire.unsigned
    standard_wire.parameters['signed'] = 23  # Should not happen, but then treat it as non-zero==>signed
    assert standard_wire.signed
    assert not standard_wire.unsigned
    standard_wire.parameters['signed'] = '1'  # Should not happen, but then treat it as non-zero==>signed
    assert standard_wire.signed
    assert not standard_wire.unsigned
    standard_wire.parameters['signed'] = True  # Should not happen, but then treat it as non-zero==>signed
    assert standard_wire.signed
    assert not standard_wire.unsigned
    standard_wire.parameters['signed'] = 0
    assert not standard_wire.signed
    assert standard_wire.unsigned
    standard_wire.parameters['signed'] = '0'  # Should not happen, but then treat it as zero==>unsigned
    assert not standard_wire.signed
    assert standard_wire.unsigned
    standard_wire.parameters['signed'] = False  # Should not happen, but then treat it as zero==>unsigned
    assert not standard_wire.signed
    assert standard_wire.unsigned


def test_add_wire_segment(standard_wire: Wire, locked_wire: Wire) -> None:
    assert len(standard_wire.segments) == 1  # There is one wire segment in the standard wire by default

    seg0 = WireSegment(name='0', wire=standard_wire)
    standard_wire._add_wire_segment(seg0)
    assert len(standard_wire.segments) == 2
    assert standard_wire[0] == seg0
    assert standard_wire[0].index == 0
    assert seg0.index == 0

    seg1 = WireSegment(name='1', wire=standard_wire)
    with pytest.raises(IdentifierConflictError):
        standard_wire._add_wire_segment(seg1)  # Do not accidentally overwrite previous entries

    assert len(locked_wire.segments) == 1
    with pytest.raises(ObjectLockedError):
        locked_wire._add_wire_segment(seg1)
    assert len(locked_wire.segments) == 1


def test_create_wire_segment(standard_wire: Wire, locked_wire: Wire) -> None:
    assert len(standard_wire.segments) == 1  # There is one wire segment in the standard wire by default

    added = standard_wire.create_wire_segment(2)
    assert added == standard_wire.segments[2]
    assert len(standard_wire.segments) == 2
    assert standard_wire[2].name == '2'
    assert standard_wire[1].name == '1'
    assert standard_wire[2].index == 2
    assert standard_wire[1].index == 1

    with pytest.raises(IdentifierConflictError):
        added = standard_wire.create_wire_segment(2)  # Do not accidentally overwrite previous entries

    assert len(locked_wire.segments) == 1
    with pytest.raises(ObjectLockedError):
        added = locked_wire.create_wire_segment(2)
    assert len(locked_wire.segments) == 1


def test_create_wire_segments(standard_wire: Wire, locked_wire: Wire) -> None:
    standard_wire.segments.clear()
    ws = standard_wire.create_wire_segments(3)
    assert ws == standard_wire.segments
    assert len(standard_wire.segments) == 3
    assert standard_wire[2].name == '2'
    assert standard_wire[1].name == '1'
    assert standard_wire[0].name == '0'
    assert standard_wire[2].index == 2
    assert standard_wire[1].index == 1
    assert standard_wire[0].index == 0

    with pytest.raises(IdentifierConflictError):
        standard_wire.create_wire_segments(3, 1)

    ws = standard_wire.create_wire_segments(1, offset=3)
    assert len(ws) == 1
    assert ws[3] == standard_wire.segments[3]
    assert len(standard_wire.segments) == 4
    assert standard_wire[3].name == '3'
    assert standard_wire[2].name == '2'
    assert standard_wire[1].name == '1'
    assert standard_wire[0].name == '0'
    assert standard_wire[3].index == 3
    assert standard_wire[2].index == 2
    assert standard_wire[1].index == 1
    assert standard_wire[0].index == 0

    assert len(locked_wire.segments) == 1
    with pytest.raises(ObjectLockedError):
        locked_wire.create_wire_segments(2)
    assert len(locked_wire.segments) == 1  # locked wire - no segments can be added


def test_remove_wire_segment(standard_wire: Wire, locked_wire: Wire) -> None:
    assert len(standard_wire.segments) == 1  # There is one wire segment in the standard wire by default

    standard_wire.remove_wire_segment(1)
    assert len(standard_wire.segments) == 0

    with pytest.raises(ObjectNotFoundError):
        standard_wire.remove_wire_segment(1)

    assert len(locked_wire.segments) == 1
    with pytest.raises(ObjectLockedError):
        locked_wire.remove_wire_segment(1)
    assert len(locked_wire.segments) == 1


def test_get_wire_segment(standard_wire: Wire) -> None:
    assert len(standard_wire.segments) == 1  # There is one wire segment in the standard wire by default

    seg = standard_wire.get_wire_segment(1)
    assert seg == standard_wire[1]
    assert seg.index == 1

    seg = standard_wire.get_wire_segment(0)
    assert seg is None


def test_get_wire_segments(standard_wire: Wire) -> None:
    assert len(standard_wire.segments) == 1  # There is one wire segment in the standard wire by default

    segs = standard_wire.get_wire_segments(name='1')
    assert len(segs) == 1
    assert segs == {1: standard_wire[1]}
    assert segs[1].name == '1'

    segs = standard_wire.get_wire_segments(name='2')
    assert segs == {}

    segs = standard_wire.get_wire_segments(name='')
    assert segs == {}


def test_set_signal(standard_wire: Wire) -> None:
    standard_wire.set_signal(Signal.HIGH, 1)
    assert standard_wire.signal_array[0] == Signal.HIGH
    # Although segment 1 may indicate that there is also an segment 0, this is not the case
    # The wire only has one segment, which is at index 1
    # This conforms to "wire[1:1]" in Verilog
    # However, the signal_array still starts with index 0, ignoring the offset, since it is
    # a vector of the SIGNALS of the corresponding wire and not of the segments
    # Accordingly, the integer value is still either 0 or 1 (since it is a 1-bit vector)
    # Thus, signal_array[0] refers to the signal of the lowest segment, which is segment 1
    assert standard_wire.signal_int == 1

    standard_wire.set_signal(Signal.HIGH, 1)
    assert standard_wire.signal_array[0] == Signal.HIGH
    assert standard_wire.signal_int == 1

    standard_wire.set_signal(0, 1)
    assert standard_wire.signal_array[0] == Signal.LOW
    assert standard_wire.signal_int == 0

    standard_wire.set_signal('Z', 1)
    assert standard_wire.signal_array[0] == Signal.FLOATING
    assert standard_wire.signal_int is None


def test_set_signals() -> None:
    from utils import wire_4b

    w = wire_4b()
    w.msb_first = False
    # Wire.set_signals assigns signals msb-first or lsb-first depending on Wire.msb_first
    w.set_signals('1011')  # 1011b (LSB) is 11d, but internal representation remains MSB: 1101
    assert w.signal_int == 13  # Internal representation: 1101
    assert w.signal_array == SignalArray(signals={3: Signal.HIGH, 2: Signal.HIGH, 1: Signal.LOW, 0: Signal.HIGH}, msb_first=False)
    assert w.signal_str == '1011'
    w.msb_first = True
    assert w.signal_str == '1101'
    assert w.offset == 1
    w.set_signals(2)  # 0010
    assert w.signal_int == 2
    w.set_signals(2)  # 0010
    assert w.signal_int == 2
    w.set_signals('1011')  # 1011b is 11d
    assert w.signal_int == 11
    w.set_signals({0: Signal.HIGH, 1: Signal.LOW})  # only 2 lowest bits are overwritten
    assert w.signal_int == 9
    assert w.signal_array == SignalArray(signals={3: Signal.HIGH, 2: Signal.LOW, 1: Signal.LOW, 0: Signal.HIGH})
    assert w.signal_str == '1001'
    w.set_signals('01xz')
    assert w.signal_int is None
    assert w.signal_array == SignalArray(signals={3: Signal.LOW, 2: Signal.HIGH, 1: Signal.UNDEFINED, 0: Signal.FLOATING})
    assert w.signal_str == '01xz'
    w.msb_first = False
    w.set_signals('01xz')  # Already in lsb-first format
    assert w.signal_int is None
    assert w.signal_array == SignalArray(signals={3: Signal.FLOATING, 2: Signal.UNDEFINED, 1: Signal.HIGH, 0: Signal.LOW}, msb_first=False)
    assert w.signal_str == '01xz'
    w.msb_first = True
    assert w.signal_str == 'zx10'

    w.set_signed(True)
    w.set_signals('1111')  # -1
    assert w.signed
    assert w.parameters['signed'] == 1
    assert w.signal_int == -1
    w.set_signed(False)
    assert not w.signed
    assert w.parameters['signed'] == 0
    assert w.signal_int == 15

    w = Wire(name='c', module=Module(name='m'))
    with pytest.raises(ValueError):
        w.set_signals('1010')


def test_set_signed(standard_wire: Wire) -> None:
    assert not standard_wire.signed
    standard_wire.set_signed(True)
    assert standard_wire.signed
    standard_wire.set_signed(True)
    assert standard_wire.signed
    standard_wire.set_signed(0)
    assert not standard_wire.signed


def test_wire_driver(standard_wire: Wire) -> None:
    assert standard_wire.driver() == {1: standard_wire[1].driver()[0]}
    w_port = standard_wire.connected_port_segments[1][0]
    assert standard_wire.driver()[1] == w_port

    standard_wire[1].port_segments.pop(0)
    assert standard_wire.driver()[1] is None


def test_wire_load(standard_wire: Wire) -> None:
    assert standard_wire.loads() == {1: standard_wire[1].loads()}
    assert standard_wire.loads() == {1: [standard_wire[1].port_segments[1], standard_wire[1].port_segments[2]]}

    standard_wire[1].port_segments.pop(-1)
    standard_wire[1].port_segments.pop(-1)

    assert standard_wire.loads() == {1: []}


def test_has_no_driver(standard_wire: Wire) -> None:
    assert not standard_wire.has_no_driver()
    assert standard_wire.has_no_driver(get_mapping=True) == {1: False}
    standard_wire.connected_port_segments[1].pop(0)
    assert standard_wire.has_no_driver()
    assert standard_wire.has_no_driver(get_mapping=True) == {1: True}
    assert len(standard_wire.connected_port_segments[1]) == 2


def test_has_multiple_drivers(standard_wire: Wire) -> None:
    assert not standard_wire.has_multiple_drivers()
    assert standard_wire.has_multiple_drivers(get_mapping=True) == {1: False}
    _add_multidriver(standard_wire)
    assert standard_wire.has_multiple_drivers()
    assert standard_wire.has_multiple_drivers(get_mapping=True) == {1: True}
    assert len(standard_wire.connected_port_segments[1]) == 4


def test_has_no_loads(standard_wire: Wire) -> None:
    assert not standard_wire.has_no_loads()
    assert standard_wire.has_no_loads(get_mapping=True) == {1: False}
    standard_wire.connected_port_segments[1].pop(-1)
    standard_wire.connected_port_segments[1].pop(-1)
    assert standard_wire.has_no_loads()
    assert standard_wire.has_no_loads(get_mapping=True) == {1: True}
    assert len(standard_wire.connected_port_segments[1]) == 1


def test_is_dangling(standard_wire: Wire) -> None:
    assert not standard_wire.is_dangling()
    assert standard_wire.is_dangling(get_mapping=True) == {1: False}
    p1 = standard_wire.connected_port_segments[1].pop(0)
    assert standard_wire.is_dangling()
    assert standard_wire.is_dangling(get_mapping=True) == {1: True}
    standard_wire.connected_port_segments[1].append(p1)
    standard_wire.connected_port_segments[1].pop(0)
    assert not standard_wire.is_dangling()
    assert standard_wire.is_dangling(get_mapping=True) == {1: False}
    standard_wire.connected_port_segments[1].pop(0)
    assert standard_wire.is_dangling()
    assert standard_wire.is_dangling(get_mapping=True) == {1: True}


def test_has_problems(standard_wire: Wire) -> None:
    assert not standard_wire.has_problems()
    assert standard_wire.has_problems(get_mapping=True) == {1: False}
    _add_multidriver(standard_wire)
    assert standard_wire.has_problems()
    assert standard_wire.has_problems(get_mapping=True) == {1: True}
    p1 = standard_wire.connected_port_segments[1].pop(0)
    p1 = standard_wire.connected_port_segments[1].pop(-1)
    assert standard_wire.has_problems()
    assert standard_wire.has_problems(get_mapping=True) == {1: True}
    standard_wire.connected_port_segments[1].append(p1)
    standard_wire.connected_port_segments[1].pop(0)
    assert not standard_wire.has_problems()
    assert standard_wire.has_problems(get_mapping=True) == {1: False}
    standard_wire.connected_port_segments[1].pop(0)
    assert standard_wire.has_problems()
    assert standard_wire.has_problems(get_mapping=True) == {1: True}


def test_set_name() -> None:
    from utils import wire_4b

    w = wire_4b()
    assert 'wire4b' in w.parent.wires
    assert 'WIRE' not in w.parent.wires
    for _, ws in w:
        for ps in ws.port_segments:
            assert 'wire4b' in ps.raw_ws_path
            assert 'WIRE' not in ps.raw_ws_path

    w.set_name('WIRE')
    assert w.raw_path == 'test_module1.WIRE'
    assert w[1].raw_path == 'test_module1.WIRE.1'
    assert w[2].raw_path == 'test_module1.WIRE.2'
    assert w[3].raw_path == 'test_module1.WIRE.3'
    assert w[4].raw_path == 'test_module1.WIRE.4'
    assert 'wire4b' not in w.parent.wires
    assert 'WIRE' in w.parent.wires

    for _, ws in w:
        for ps in ws.port_segments:
            assert 'wire4b' not in ps.ws_path.parts
            assert 'WIRE' in ps.ws_path.parts

    w.set_name('WIREWIRE')  # Checks path.replace, if the name is already present as "subpart"
    assert w.raw_path == 'test_module1.WIREWIRE'
    assert w[1].raw_path == 'test_module1.WIREWIRE.1'
    assert w[2].raw_path == 'test_module1.WIREWIRE.2'
    assert w[3].raw_path == 'test_module1.WIREWIRE.3'
    assert w[4].raw_path == 'test_module1.WIREWIRE.4'
    assert 'WIRE' not in w.parent.wires
    assert 'WIREWIRE' in w.parent.wires

    for _, ws in w:
        for ps in ws.port_segments:
            assert 'WIRE' not in ps.ws_path.parts
            assert 'WIREWIRE' in ps.ws_path.parts

    w.parent.create_port('WIREWIRE', width=4)
    with pytest.raises(UnsupportedOperationError):
        w.set_name('NEW_NAME')


def test_set_name_connections() -> None:
    m = Module(name='m')
    w = m.create_wire('w', width=2)
    p1 = m.create_port('p1', direction=Direction.IN, width=2)
    p2 = m.create_port('p2', direction=Direction.OUT, width=2)
    m.connect(w[0], p1[0])
    m.connect(w[0], p2[0])
    assert w.connected_port_segments[0][0] == p1[0]
    assert w.connected_port_segments[0][1] == p2[0]
    assert w.connected_port_segments[1] == []
    assert w[0].raw_path == 'm.w.0'
    assert w[1].raw_path == 'm.w.1'
    assert p1[0].raw_ws_path == 'm.w.0'
    assert p1[1].raw_ws_path == ''
    assert p2[0].raw_ws_path == 'm.w.0'
    assert p2[1].raw_ws_path == ''

    w.set_name('new_w')
    assert w.connected_port_segments[0][0] == p1[0]
    assert w.connected_port_segments[0][1] == p2[0]
    assert w.connected_port_segments[1] == []
    assert w[0].raw_path == 'm.new_w.0'
    assert w[1].raw_path == 'm.new_w.1'
    assert p1[0].raw_ws_path == 'm.new_w.0'
    assert p1[1].raw_ws_path == ''
    assert p2[0].raw_ws_path == 'm.new_w.0'
    assert p2[1].raw_ws_path == ''

    m.connect(w[1], p1[1])
    m.connect(w[1], p2[1])
    assert w.connected_port_segments[0][0] == p1[0]
    assert w.connected_port_segments[0][1] == p2[0]
    assert w.connected_port_segments[1][0] == p1[1]
    assert w.connected_port_segments[1][1] == p2[1]
    assert w[0].raw_path == 'm.new_w.0'
    assert w[1].raw_path == 'm.new_w.1'
    assert p1[0].raw_ws_path == 'm.new_w.0'
    assert p1[1].raw_ws_path == 'm.new_w.1'
    assert p2[0].raw_ws_path == 'm.new_w.0'
    assert p2[1].raw_ws_path == 'm.new_w.1'


def test_change_mutability(standard_wire: Wire) -> None:
    assert not standard_wire.locked
    standard_wire.change_mutability(is_now_locked=True)
    assert standard_wire.locked
    assert not next(iter(standard_wire.segments.values())).locked

    standard_wire.change_mutability(is_now_locked=True, recursive=True)
    assert standard_wire.locked
    assert next(iter(standard_wire.segments.values())).locked


def test_copy_object(standard_wire: Wire) -> None:
    with pytest.warns(FutureWarning):
        new_w = standard_wire.copy_object('new_wire')
    assert isinstance(new_w, Wire)
    assert new_w.raw_path == 'new_wire'
    assert new_w.connected_port_segments == {1: []}
    assert new_w.connected_port_segments != standard_wire.connected_port_segments
    assert new_w.module is None
    assert new_w.module is standard_wire.module
    assert new_w.width == standard_wire.width
    assert new_w.offset == standard_wire.offset

    m = Module(name='m')
    m.add_wire(standard_wire)
    assert standard_wire in m.wires.values()
    new_w2 = standard_wire.copy_object('new_wire')
    assert new_w2 in m.wires.values()
    assert new_w2.module is m
    assert new_w2.module is standard_wire.module

    with pytest.raises(IdentifierConflictError):
        standard_wire.copy_object('new_wire')


def test_evaluate(standard_wire: Wire) -> None:
    for p in standard_wire.connected_port_segments[1]:
        assert p.signal == Signal.UNDEFINED
    standard_wire.evaluate()
    for p in standard_wire.connected_port_segments[1]:
        assert p.signal == Signal.UNDEFINED

    standard_wire.driver()[1].set_signal(0)
    assert standard_wire.signal_array[0] == Signal.UNDEFINED
    assert standard_wire.connected_port_segments[1][0].signal == Signal.LOW
    assert standard_wire.connected_port_segments[1][1].signal == Signal.UNDEFINED
    assert standard_wire.connected_port_segments[1][2].signal == Signal.UNDEFINED
    standard_wire.evaluate()
    assert standard_wire.signal_array[0] == Signal.LOW
    assert standard_wire.connected_port_segments[1][0].signal == Signal.LOW
    assert standard_wire.connected_port_segments[1][1].signal == Signal.LOW
    assert standard_wire.connected_port_segments[1][2].signal == Signal.LOW

    _add_multidriver(standard_wire)
    with pytest.raises(MultipleDriverError):
        standard_wire.driver()[1].set_signal('1')


def test_normalize_metadata() -> None:
    from utils import wire_4b

    w = wire_4b()
    found = w.normalize_metadata()
    assert found == {}

    found = w.normalize_metadata(include_empty=True)
    assert found == {
        'test_module1.wire4b': {},
        'test_module1.wire4b.1': {},
        'test_module1.wire4b.2': {},
        'test_module1.wire4b.3': {},
        'test_module1.wire4b.4': {},
    }
    w.metadata.set('key', 'foo')
    w.metadata.set('key2', 'bar', 'baz')
    w[1].metadata.set('key', 'foo')
    w[2].metadata.set('key', 'foo')
    w[2].metadata.set('key', 'foo', 'baz')
    found = w.normalize_metadata()
    target = {
        'test_module1.wire4b': {'general': {'key': 'foo'}, 'baz': {'key2': 'bar'}},
        'test_module1.wire4b.1': {'general': {'key': 'foo'}},
        'test_module1.wire4b.2': {'general': {'key': 'foo'}, 'baz': {'key': 'foo'}},
    }
    assert found == target

    found = w.normalize_metadata(include_empty=True)
    target = {
        'test_module1.wire4b': {'general': {'key': 'foo'}, 'baz': {'key2': 'bar'}},
        'test_module1.wire4b.1': {'general': {'key': 'foo'}},
        'test_module1.wire4b.2': {'general': {'key': 'foo'}, 'baz': {'key': 'foo'}},
        'test_module1.wire4b.3': {},
        'test_module1.wire4b.4': {},
    }
    assert found == target

    found = w.normalize_metadata(sort_by='category')
    target = {
        'general': {'test_module1.wire4b': {'key': 'foo'}, 'test_module1.wire4b.1': {'key': 'foo'}, 'test_module1.wire4b.2': {'key': 'foo'}},
        'baz': {'test_module1.wire4b': {'key2': 'bar'}, 'test_module1.wire4b.2': {'key': 'foo'}},
    }
    assert found == target

    # Checks if {"key": "foo"} is part of val
    found = w.normalize_metadata(sort_by='category', filter=lambda cat, md: 'key' in md and md['key'] == 'foo')
    target = {
        'general': {'test_module1.wire4b': {'key': 'foo'}, 'test_module1.wire4b.1': {'key': 'foo'}, 'test_module1.wire4b.2': {'key': 'foo'}},
        'baz': {'test_module1.wire4b.2': {'key': 'foo'}},
    }
    assert found == target

    # Illegal operation should be resolved to False
    found = w.normalize_metadata(sort_by='category', filter=lambda cat, md: md.is_integer())
    target = {}
    assert found == target


def test_wire_str(standard_wire: Wire) -> None:
    # # Test the string representation of a wire
    assert str(standard_wire) == 'Wire "wire1" with path wire1 (1 bit(s) wide)'


def test_wire_repr(standard_wire: Wire) -> None:
    # # # Test the representation of a wire
    assert repr(standard_wire) == 'Wire(wire1 at wire1)'


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
