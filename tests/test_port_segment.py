# mypy: disable-error-code="unreachable,comparison-overlap"
import copy
import os

import pytest

from netlist_carpentry.core.exceptions import (
    AlreadyConnectedError,
    DetachedSegmentError,
    InvalidSignalError,
    ObjectLockedError,
    ParentNotFoundError,
)
from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath
from netlist_carpentry.core.netlist_elements.element_type import EType
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.netlist_elements.port import Port, PortDirection
from netlist_carpentry.core.netlist_elements.port_segment import PortSegment
from netlist_carpentry.core.signal import Signal
from netlist_carpentry.utils.cfg import CFG


@pytest.fixture
def port_segment() -> PortSegment:
    return PortSegment(raw_path='a.b.c.0', port=None).set_ws_path('a.b.wire1.wire_seg1')


@pytest.fixture
def const_port_segment() -> PortSegment:
    return PortSegment(raw_path='a.b.c.1', port=None).set_ws_path('1')


@pytest.fixture
def standard_port_in() -> Port[Instance]:
    from utils import standard_port_in

    return standard_port_in()


@pytest.fixture
def standard_port_out() -> Port[Module]:
    from utils import standard_port_out

    return standard_port_out()


def test_port_segment_basics(port_segment: PortSegment, const_port_segment: PortSegment) -> None:
    assert port_segment.name == '0'
    assert port_segment.path.type is EType.PORT_SEGMENT
    assert port_segment.path.raw == 'a.b.c.0'
    assert port_segment.type is EType.PORT_SEGMENT
    assert port_segment.index == 0
    assert port_segment.ws_path == WireSegmentPath(raw='a.b.wire1.wire_seg1')
    assert port_segment.wire_name == 'wire1'
    assert port_segment.signal is Signal.UNDEFINED
    assert port_segment.port is None
    assert port_segment != Signal.UNDEFINED  # Test __eq__ for bad types

    with pytest.raises(ParentNotFoundError):
        port_segment.direction

    assert const_port_segment.path.raw == 'a.b.c.1'
    assert const_port_segment.index == 1
    assert const_port_segment.ws_path == WireSegmentPath(raw='1')
    assert const_port_segment.wire_name == ''
    assert const_port_segment.port is None

    super_port = Port(raw_path='a.b.c', direction=PortDirection.IN, module_or_instance=Instance(raw_path='a.b', instance_type='c', module=None))
    const_port_segment.port = super_port
    assert const_port_segment.signal is Signal.HIGH

    with pytest.raises(ValueError):
        PortSegment(raw_path='a.b.c', port=None)

    assert port_segment.can_carry_signal


def test_parent(port_segment: PortSegment, standard_port_in: Port[Instance]) -> None:
    parent = standard_port_in[0].parent
    assert parent == standard_port_in

    with pytest.raises(ParentNotFoundError):
        port_segment.parent


def test_port_segment_parent_port() -> None:
    CFG.allow_detached_segments = False
    with pytest.raises(DetachedSegmentError):
        PortSegment(raw_path='a.b.c.0', port=None)
    with pytest.raises(TypeError):
        PortSegment(raw_path='a.b.c.0', port=NetlistElement(raw_path='a.b.c'))
    CFG.allow_detached_segments = True


def test_signal(port_segment: PortSegment) -> None:
    super_port = Port(raw_path='a.b.c', direction=PortDirection.IN, module_or_instance=Instance(raw_path='a.b', instance_type='c', module=None))
    port_segment.port = super_port
    assert port_segment.signal == Signal.UNDEFINED
    port_segment.set_ws_path('0')
    assert port_segment.signal == Signal.LOW
    port_segment.set_ws_path('Z')
    assert port_segment.signal == Signal.FLOATING
    port_segment.set_ws_path('X')
    assert port_segment.signal == Signal.FLOATING  # Is an unconnected instance input port -> Floating signal
    port_segment.set_ws_path('1')
    assert port_segment.signal == Signal.HIGH
    port_segment.set_ws_path('')
    assert port_segment.signal == Signal.FLOATING  # Is an unconnected instance input port -> Floating signal


def test_signal_int(port_segment: PortSegment) -> None:
    super_port = Port(raw_path='a.b.c', direction=PortDirection.IN, module_or_instance=Instance(raw_path='a.b', instance_type='c', module=None))
    port_segment.port = super_port
    assert port_segment.signal_int is None
    port_segment.set_ws_path('0')
    assert port_segment.signal_int == 0
    port_segment.set_ws_path('Z')
    assert port_segment.signal_int is None
    port_segment.set_ws_path('X')
    assert port_segment.signal_int is None
    port_segment.set_ws_path('1')
    assert port_segment.signal_int == 1
    port_segment.set_ws_path('')
    assert port_segment.signal_int is None


def test_port_is_connected(port_segment: PortSegment) -> None:
    assert port_segment.is_connected
    assert not port_segment.is_unconnected

    port_segment.set_ws_path('X')

    assert not port_segment.is_connected
    assert port_segment.is_unconnected

    port_segment.set_ws_path('')

    assert not port_segment.is_connected
    assert port_segment.is_unconnected


def test_port_is_floating(port_segment: PortSegment) -> None:
    assert not port_segment.is_floating
    port_segment.set_ws_path('Z')

    assert port_segment.is_floating
    port_segment.set_ws_path('')

    assert not port_segment.is_floating


def test_is_constant(port_segment: PortSegment) -> None:
    assert not port_segment.is_tied
    port_segment.set_ws_path('0')
    assert port_segment.is_tied
    port_segment.set_ws_path('1')
    assert port_segment.is_tied
    port_segment.set_ws_path('Z')
    assert port_segment.is_tied
    port_segment.set_ws_path('X')
    assert port_segment.is_tied
    port_segment.set_ws_path('')
    assert port_segment.is_tied


def test_is_defined_constant(port_segment: PortSegment) -> None:
    assert not port_segment.is_tied_defined
    port_segment.set_ws_path('0')
    assert port_segment.is_tied_defined
    port_segment.set_ws_path('1')
    assert port_segment.is_tied_defined
    port_segment.set_ws_path('Z')
    assert not port_segment.is_tied_defined
    port_segment.set_ws_path('X')
    assert not port_segment.is_tied_defined
    port_segment.set_ws_path('')
    assert not port_segment.is_tied_defined


def test_is_undefined_constant(port_segment: PortSegment) -> None:
    assert not port_segment.is_tied_undefined
    port_segment.set_ws_path('0')
    assert not port_segment.is_tied_undefined
    port_segment.set_ws_path('1')
    assert not port_segment.is_tied_undefined
    port_segment.set_ws_path('Z')
    assert port_segment.is_tied_undefined
    port_segment.set_ws_path('X')
    assert port_segment.is_tied_undefined
    port_segment.set_ws_path('')
    assert port_segment.is_tied_undefined


def test_port_is_input(standard_port_in: Port[Instance], standard_port_out: Port[Module]) -> None:
    assert standard_port_in[0].is_input
    assert not standard_port_out[0].is_input

    standard_port_out[0].parent.direction = PortDirection.IN_OUT
    assert standard_port_out[0].is_input
    assert standard_port_out[0].parent.direction == PortDirection.IN_OUT


def test_port_is_output(standard_port_in: Port[Instance], standard_port_out: Port[Module]) -> None:
    assert not standard_port_in[0].is_output
    assert standard_port_out[0].is_output

    standard_port_in[0].parent.direction = PortDirection.IN_OUT
    assert standard_port_in[0].is_output
    assert standard_port_in[0].parent.direction == PortDirection.IN_OUT


def test_port_is_driver(standard_port_in: Port[Instance], standard_port_out: Port[Module]) -> None:
    assert not standard_port_in[0].is_driver
    assert not standard_port_out[0].is_driver

    standard_port_in.module_or_instance = Module(raw_path='a')
    standard_port_out.module_or_instance = Instance(raw_path='a.b', instance_type='c', module=None)
    assert standard_port_in[0].is_driver
    assert standard_port_out[0].is_driver


def test_port_is_load(standard_port_in: Port[Instance], standard_port_out: Port[Module]) -> None:
    assert standard_port_in[0].is_load
    assert standard_port_out[0].is_load

    standard_port_in.module_or_instance = Module(raw_path='a')
    standard_port_out.module_or_instance = Instance(raw_path='a.b', instance_type='c', module=None)
    assert not standard_port_in[0].is_load
    assert not standard_port_out[0].is_load


def test_port_direction(standard_port_in: Port[Instance], standard_port_out: Port[Module]) -> None:
    assert standard_port_in[0].direction == PortDirection.IN
    assert standard_port_out[0].direction == PortDirection.OUT

    standard_port_in[0].parent.direction = PortDirection.IN_OUT
    assert standard_port_in[0].parent.direction == PortDirection.IN_OUT
    assert standard_port_in[0].direction == PortDirection.IN_OUT


def test_super_port_name(port_segment: PortSegment) -> None:
    assert port_segment.parent_name == 'c'

    still_valid = PortSegment(raw_path='a.0', port=None)
    assert still_valid.parent_name == 'a'

    invalid = PortSegment(raw_path='0', port=None)
    assert invalid.parent_name == ''

    invalid = PortSegment(raw_path='', port=None)
    assert invalid.parent_name == ''


def test_super_inst_or_module_name(port_segment: PortSegment) -> None:
    assert port_segment.parent_parent_name == 'b'

    still_valid = PortSegment(raw_path='a.b.0', port=None)
    assert still_valid.parent_parent_name == 'a'

    invalid = PortSegment(raw_path='a.0', port=None)
    assert invalid.parent_parent_name == ''

    invalid = PortSegment(raw_path='0', port=None)
    assert invalid.parent_parent_name == ''

    invalid = PortSegment(raw_path='', port=None)
    assert invalid.parent_parent_name == ''


def test_tie_signal(port_segment: PortSegment) -> None:
    super_port = Port(raw_path='a.b.c', direction=PortDirection.IN, module_or_instance=Instance(raw_path='a.b', instance_type='c', module=None))
    port_segment.port = super_port
    port_segment.set_ws_path('')
    assert port_segment.raw_ws_path == ''

    with pytest.raises(InvalidSignalError):
        port_segment.tie_signal('abc')
    assert port_segment.raw_ws_path == ''

    port_segment.tie_signal('0')
    assert port_segment.raw_ws_path == '0'
    assert port_segment.signal == Signal.LOW

    port_segment.tie_signal('1')
    assert port_segment.raw_ws_path == '1'
    assert port_segment.signal == Signal.HIGH

    port_segment.tie_signal('Z')
    assert port_segment.raw_ws_path == 'Z'
    assert port_segment.signal == Signal.FLOATING

    port_segment.tie_signal('X')
    assert port_segment.raw_ws_path == 'X'
    assert port_segment.signal == Signal.FLOATING  # Is an unconnected instance input port -> Floating signal


def test_tie_signal_driver_segment(port_segment: PortSegment) -> None:
    port_segment.port = Port(raw_path='a.b.c.p', direction=PortDirection.OUT, module_or_instance=None)
    assert port_segment.raw_ws_path == 'a.b.wire1.wire_seg1'

    with pytest.raises(AlreadyConnectedError):
        port_segment.tie_signal('0')
    assert not port_segment.raw_ws_path == '0'
    assert not port_segment.signal == Signal.LOW


def test_set_signal(port_segment: PortSegment) -> None:
    assert port_segment.signal is Signal.UNDEFINED
    port_segment.set_signal(signal=Signal.HIGH)
    assert port_segment.signal is Signal.HIGH

    port_segment.set_signal(signal=0)
    assert port_segment.signal is Signal.LOW

    port_segment.set_signal(signal='1')
    assert port_segment.signal is Signal.HIGH


def test_change_connection(port_segment: PortSegment) -> None:
    port_segment.change_connection(WireSegmentPath(raw='a.b.wire1.seg2'))
    assert port_segment.raw_ws_path == 'a.b.wire1.seg2'
    assert port_segment.wire_name == 'wire1'

    port_segment.change_connection()
    assert port_segment.raw_ws_path == ''
    assert port_segment.wire_name == ''

    port_segment.change_mutability(is_now_locked=True)
    with pytest.raises(ObjectLockedError):
        port_segment.change_connection(WireSegmentPath(raw='a.b.wire1.seg2'))
    assert port_segment.raw_ws_path == ''


def test_port_segment_hash(port_segment: PortSegment) -> None:
    assert hash(port_segment) == hash(port_segment)

    ps2 = copy.deepcopy(port_segment)
    assert hash(port_segment) == hash(ps2)

    ps2.raw_path = ps2.raw_path[:-1] + '42'
    assert hash(port_segment) != hash(ps2)


def test_port_segment_str(port_segment: PortSegment) -> None:
    assert str(port_segment) == 'PortSegment "0" with path a.b.c.0'


def test_port_segment_repr(port_segment: PortSegment) -> None:
    assert repr(port_segment) == 'PortSegment(a.b.c.0, Signal:x)'


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
