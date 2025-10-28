# mypy: disable-error-code="unreachable,comparison-overlap"
import copy
import os

import pytest

from netlist_carpentry import LOG
from netlist_carpentry.core.exceptions import (
    DetachedSegmentError,
    ObjectLockedError,
    ParentNotFoundError,
    SignalAssignmentError,
)
from netlist_carpentry.core.netlist_elements.element_type import EType
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.netlist_elements.port import Port
from netlist_carpentry.core.netlist_elements.wire_segment import (
    WIRE_SEGMENT_0,
    WIRE_SEGMENT_1,
    WIRE_SEGMENT_X,
    WIRE_SEGMENT_Z,
    WireSegment,
    WireSegmentConst0,
    WireSegmentConst1,
    WireSegmentConstX,
    WireSegmentConstZ,
)
from netlist_carpentry.core.port_direction import PortDirection
from netlist_carpentry.core.signal import Signal
from netlist_carpentry.utils.cfg import CFG
from netlist_carpentry.utils.log import initialize_logging


@pytest.fixture
def wire_segment() -> WireSegment:
    from utils import standard_wire

    wire = standard_wire()
    inst = Instance(raw_path='a.b', instance_type='c', module=None)
    module = Module(raw_path='a')
    p1 = Port(raw_path='a.b.c.p1', direction=PortDirection.OUT, module_or_instance=inst)
    p2 = Port(raw_path='a.b.d.p2', direction=PortDirection.IN, module_or_instance=inst)
    p3 = Port(raw_path='a.b.p3', direction=PortDirection.OUT, module_or_instance=module)
    p1.create_port_segment(0).set_ws_path('a.b.c.0')
    p2.create_port_segment(0).set_ws_path('a.b.c.0')
    p3.create_port_segment(0).set_ws_path('a.b.c.0')
    w = WireSegment(raw_path='a.b.c.0', wire=wire)
    w.add_port_segments([p1[0], p2[0], p3[0]])
    return w


@pytest.fixture
def locked_seg() -> WireSegment:
    from utils import locked_wire_segment as iws

    return iws()


def _add_multidriver(wire_segment: WireSegment) -> None:
    p = Port(raw_path='a.b.p4', direction=PortDirection.IN, module_or_instance=Module(raw_path='a'))
    p.create_port_segment(0)
    wire_segment.add_port_segment(p[0])


def test_wire_segment_basics(wire_segment: WireSegment) -> None:
    assert wire_segment.name == '0'
    assert wire_segment.path.type is EType.WIRE_SEGMENT
    assert wire_segment.path.raw == 'a.b.c.0'
    assert wire_segment.type is EType.WIRE_SEGMENT
    assert wire_segment.index == 0
    assert wire_segment.signal is Signal.UNDEFINED

    with pytest.raises(AttributeError):
        wire_segment.signal = Signal.HIGH  # type: ignore

    assert len(wire_segment.port_segments) == 3
    assert wire_segment.port_segments[0].is_driver
    assert not wire_segment.port_segments[0].is_load
    assert not wire_segment.port_segments[1].is_driver
    assert wire_segment.port_segments[1].is_load
    assert not wire_segment.port_segments[2].is_driver
    assert wire_segment.port_segments[2].is_load
    assert wire_segment.nr_connected_ports == 3

    wire_segment.index = 2
    assert wire_segment.index == 2
    wire_segment.index = 'foo'
    assert wire_segment.index == 2

    assert wire_segment.can_carry_signal


def test_wire_segment_parent_wire() -> None:
    CFG.allow_detached_segments = False
    with pytest.raises(DetachedSegmentError):
        WireSegment(raw_path='a.b.c.0', wire=None)
    with pytest.raises(TypeError):
        WireSegment(raw_path='a.b.c.0', wire=NetlistElement(raw_path='a.b.c'))
    CFG.allow_detached_segments = True


def test_parent() -> None:
    from utils import standard_wire

    w = standard_wire()
    parent = w[1].parent
    assert parent == w

    with pytest.raises(ParentNotFoundError):
        WireSegment(raw_path='a.b.c.0', wire=None).parent


def test_eq(wire_segment: WireSegment) -> None:
    n2 = copy.deepcopy(wire_segment)
    assert wire_segment == n2

    n3 = WireSegment(raw_path='wrong_path.0', wire=None)
    assert wire_segment != n3

    n4 = 'wrong_type'
    assert wire_segment != n4
    assert wire_segment.__eq__(n4) == NotImplemented


def test_is_constant(wire_segment: WireSegment) -> None:
    assert not wire_segment.is_constant
    assert WIRE_SEGMENT_0.is_constant
    assert WIRE_SEGMENT_1.is_constant
    assert WIRE_SEGMENT_X.is_constant


def test_is_defined_constant(wire_segment: WireSegment) -> None:
    assert not wire_segment.is_defined_constant
    assert WIRE_SEGMENT_0.is_defined_constant
    assert WIRE_SEGMENT_1.is_defined_constant
    assert not WIRE_SEGMENT_X.is_defined_constant


def test_super_wire_name(wire_segment: WireSegment) -> None:
    from utils import standard_wire

    wire = standard_wire()
    assert wire_segment.super_wire_name == 'c'

    still_valid = WireSegment(raw_path='a.0', wire=wire)
    assert still_valid.super_wire_name == 'a'

    invalid = WireSegment(raw_path='0', wire=wire)
    assert invalid.super_wire_name == ''

    invalid = WireSegment(raw_path='', wire=wire)
    assert invalid.super_wire_name == ''


def test_super_module_name(wire_segment: WireSegment) -> None:
    assert wire_segment.super_module_name == 'b'

    still_valid = WireSegment(raw_path='a.b.0', wire=None)
    assert still_valid.super_module_name == 'a'

    invalid = WireSegment(raw_path='a.0', wire=None)
    assert invalid.super_module_name == ''

    invalid = WireSegment(raw_path='0', wire=None)
    assert invalid.super_module_name == ''

    invalid = WireSegment(raw_path='', wire=None)
    assert invalid.super_module_name == ''


def test_add_port_segment(wire_segment: WireSegment, locked_seg: WireSegment) -> None:
    from utils import standard_port_in as spi

    p = spi()
    added = wire_segment.add_port_segment(p[0])
    assert added == p[0]
    assert len(wire_segment.port_segments) == 4
    assert wire_segment.port_segments[-1] == p[0]

    assert len(locked_seg.port_segments) == 1
    with pytest.raises(ObjectLockedError):
        locked_seg.add_port_segment(p[0])
    assert len(locked_seg.port_segments) == 1


def test_add_port_segments(wire_segment: WireSegment) -> None:
    from utils import standard_port_in as spo
    from utils import standard_port_out as spi

    assert len(wire_segment.port_segments) == 3
    p1 = spi()
    p2 = spo()
    all_added = wire_segment.add_port_segments([p1[0], p2[0]])
    assert all_added == [p1[0], p2[0]]
    assert len(wire_segment.port_segments) == 5


def test_remove_port_segment(wire_segment: WireSegment, locked_seg: WireSegment) -> None:
    p1 = wire_segment.port_segments[0]
    wire_segment.remove_port_segment(p1)
    assert len(wire_segment.port_segments) == 2
    assert p1 not in wire_segment.port_segments

    assert len(locked_seg.port_segments) == 1
    p1 = locked_seg.port_segments[0]
    with pytest.raises(ObjectLockedError):
        locked_seg.remove_port_segment(p1)
    assert len(locked_seg.port_segments) == 1


def test_wire_segment_set_signal(wire_segment: WireSegment) -> None:
    wire_segment.set_signal(Signal.HIGH)
    assert wire_segment.signal is Signal.HIGH

    wire_segment.set_signal(1)
    assert wire_segment.signal is Signal.HIGH

    wire_segment.set_signal('0')
    assert wire_segment.signal is Signal.LOW

    wire_segment.set_signal(1)
    assert wire_segment.signal is Signal.HIGH

    with pytest.raises(SignalAssignmentError):
        WIRE_SEGMENT_0.set_signal(0)
    with pytest.raises(SignalAssignmentError):
        WIRE_SEGMENT_0.set_signal(1)


def test_wire_segment_has_defined_signal(wire_segment: WireSegment) -> None:
    assert not wire_segment.has_defined_signal()
    wire_segment.set_signal(Signal.LOW)
    assert wire_segment.has_defined_signal()
    wire_segment.set_signal(Signal.HIGH)
    assert wire_segment.has_defined_signal()
    wire_segment.set_signal(Signal.FLOATING)
    assert not wire_segment.has_defined_signal()


def test_get_driver(wire_segment: WireSegment) -> None:
    assert wire_segment.driver() == [wire_segment.port_segments[0]]


def test_get_drivers_multiple(wire_segment: WireSegment) -> None:
    initialize_logging(no_file=True)
    warns = LOG.warns_quantity
    _add_multidriver(wire_segment)

    assert len(wire_segment.driver(True)) == 2
    assert LOG.warns_quantity == warns + 1


def test_get_loads(wire_segment: WireSegment) -> None:
    initialize_logging(no_file=True)
    warns = LOG.warns_quantity
    assert wire_segment.loads(True) == [wire_segment.port_segments[1], wire_segment.port_segments[2]]

    wire_segment.port_segments.pop(-1)
    wire_segment.port_segments.pop(-1)
    assert not wire_segment.loads(True)
    assert LOG.warns_quantity == warns + 1


def test_has_no_driver(wire_segment: WireSegment) -> None:
    assert not wire_segment.has_no_driver()
    wire_segment.port_segments.pop(0)
    assert wire_segment.has_no_driver()
    assert wire_segment.nr_connected_ports == 2


def test_has_multiple_drivers(wire_segment: WireSegment) -> None:
    assert not wire_segment.has_multiple_drivers()
    _add_multidriver(wire_segment)
    assert wire_segment.has_multiple_drivers()
    assert wire_segment.nr_connected_ports == 4


def test_has_no_loads(wire_segment: WireSegment) -> None:
    assert not wire_segment.has_no_loads()
    wire_segment.port_segments.pop(-1)
    assert not wire_segment.has_no_loads()
    wire_segment.port_segments.pop(-1)
    assert wire_segment.has_no_loads()
    assert wire_segment.nr_connected_ports == 1


def test_is_dangling(wire_segment: WireSegment) -> None:
    assert not wire_segment.is_dangling()
    p1 = wire_segment.port_segments.pop(0)
    assert wire_segment.is_dangling()
    wire_segment.port_segments.append(p1)
    wire_segment.port_segments.pop(0)
    assert not wire_segment.is_dangling()
    wire_segment.port_segments.pop(0)
    assert wire_segment.is_dangling()


def test_has_problems(wire_segment: WireSegment) -> None:
    assert not wire_segment.has_problems()
    _add_multidriver(wire_segment)
    assert wire_segment.has_problems()
    wire_segment.port_segments.pop(-1)
    wire_segment.port_segments.pop(-1)
    assert not wire_segment.has_problems()
    wire_segment.port_segments.pop(-1)
    assert wire_segment.has_problems()


def test_evaluate(wire_segment: WireSegment) -> None:
    for p in wire_segment.port_segments:
        assert p.signal == Signal.UNDEFINED
    wire_segment.evaluate()
    for p in wire_segment.port_segments:
        assert p.signal == Signal.UNDEFINED

    wire_segment.port_segments[0].set_ws_path('a.b.c.d')
    wire_segment.evaluate()

    wire_segment.driver()[0].set_signal(Signal.LOW)
    assert wire_segment.signal == Signal.UNDEFINED
    assert wire_segment.port_segments[0].signal == Signal.LOW
    assert wire_segment.port_segments[1].signal == Signal.UNDEFINED
    assert wire_segment.port_segments[2].signal == Signal.UNDEFINED
    wire_segment.evaluate()
    assert wire_segment.signal == Signal.LOW
    assert wire_segment.port_segments[0].signal == Signal.LOW
    assert wire_segment.port_segments[1].signal == Signal.LOW
    assert wire_segment.port_segments[2].signal == Signal.LOW


def test_wire_segment_hash(wire_segment: WireSegment) -> None:
    assert hash(wire_segment) == hash(wire_segment)

    ws2 = copy.deepcopy(wire_segment)
    assert hash(wire_segment) == hash(ws2)

    ws2.port_segments[0].raw_path = ws2.port_segments[0].raw_path[:-1] + '42'
    assert hash(wire_segment) != hash(ws2)


def test_wire_segment_str(wire_segment: WireSegment) -> None:
    assert str(wire_segment) == 'WireSegment "0" with path a.b.c.0'

    assert str(WIRE_SEGMENT_0) == 'Constant WireSegment "0" with path 0 and signal 0'
    assert str(WIRE_SEGMENT_1) == 'Constant WireSegment "1" with path 1 and signal 1'
    assert str(WIRE_SEGMENT_Z) == 'Constant WireSegment "Z" with path Z and signal z'
    assert str(WIRE_SEGMENT_X) == 'Constant WireSegment "X" with path X and signal x'


def test_wire_segment_repr(wire_segment: WireSegment) -> None:
    assert repr(wire_segment) == 'WireSegment(a.b.c.0, Signal:x)'

    assert repr(WIRE_SEGMENT_0) == 'Constant WireSegment "0" WireSeg(0)'
    assert repr(WIRE_SEGMENT_1) == 'Constant WireSegment "1" WireSeg(1)'
    assert repr(WIRE_SEGMENT_Z) == 'Constant WireSegment "z" WireSeg(Z)'
    assert repr(WIRE_SEGMENT_X) == 'Constant WireSegment "x" WireSeg(X)'


def test_wire_segment_constants() -> None:
    assert isinstance(WIRE_SEGMENT_0, WireSegmentConst0)
    assert WIRE_SEGMENT_0.signal == Signal.LOW
    assert WIRE_SEGMENT_0.raw_path == '0'
    assert WIRE_SEGMENT_0.is_constant
    assert WIRE_SEGMENT_0.is_defined_constant
    WIRE_SEGMENT_0.evaluate()
    assert WIRE_SEGMENT_0.signal == Signal.LOW

    assert isinstance(WIRE_SEGMENT_1, WireSegmentConst1)
    assert WIRE_SEGMENT_1.signal == Signal.HIGH
    assert WIRE_SEGMENT_1.raw_path == '1'
    assert WIRE_SEGMENT_1.is_constant
    assert WIRE_SEGMENT_1.is_defined_constant
    WIRE_SEGMENT_1.evaluate()
    assert WIRE_SEGMENT_1.signal == Signal.HIGH

    assert isinstance(WIRE_SEGMENT_Z, WireSegmentConstZ)
    assert WIRE_SEGMENT_Z.signal == Signal.FLOATING
    assert WIRE_SEGMENT_Z.raw_path == 'Z'
    assert WIRE_SEGMENT_Z.is_constant
    assert not WIRE_SEGMENT_Z.is_defined_constant
    WIRE_SEGMENT_Z.evaluate()
    assert WIRE_SEGMENT_Z.signal == Signal.FLOATING

    assert isinstance(WIRE_SEGMENT_X, WireSegmentConstX)
    assert WIRE_SEGMENT_X.signal == Signal.UNDEFINED
    assert WIRE_SEGMENT_X.raw_path == 'X'
    assert WIRE_SEGMENT_X.is_constant
    assert not WIRE_SEGMENT_X.is_defined_constant
    WIRE_SEGMENT_X.evaluate()
    assert WIRE_SEGMENT_X.signal == Signal.UNDEFINED


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
