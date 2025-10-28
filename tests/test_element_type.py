import os

import pytest

from netlist_carpentry.core.netlist_elements.element_type import EType, get_class
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.netlist_elements.port import Port
from netlist_carpentry.core.netlist_elements.wire import Wire
from netlist_carpentry.core.netlist_elements.wire_segment import WireSegment


def test_can_carry_signal():
    assert not EType.UNSPECIFIED.can_carry_signal
    assert not EType.MODULE.can_carry_signal
    assert not EType.INSTANCE.can_carry_signal
    assert EType.PORT.can_carry_signal
    assert EType.PORT_SEGMENT.can_carry_signal
    assert EType.WIRE.can_carry_signal
    assert EType.WIRE_SEGMENT.can_carry_signal


def test_is_segment():
    assert not EType.UNSPECIFIED.is_segment
    assert not EType.MODULE.is_segment
    assert not EType.INSTANCE.is_segment
    assert not EType.PORT.is_segment
    assert EType.PORT_SEGMENT.is_segment
    assert not EType.WIRE.is_segment
    assert EType.WIRE_SEGMENT.is_segment


def test_get_class():
    # ElementsEnum.MODULE
    class_ = get_class(EType.MODULE)
    assert class_ == Module

    # ElementsEnum.INSTANCE
    class_ = get_class('instance')
    assert class_ == Instance

    # ElementsEnum.PORT
    class_ = get_class('port')
    assert class_ == Port

    # ElementsEnum.WIRE
    class_ = get_class('wire')
    assert class_ == Wire

    # ElementsEnum.WIRE_SEGMENT
    class_ = get_class('wire_segment')
    assert class_ == WireSegment

    # ElementsEnum.UNSPECIFIED
    class_ = get_class('unspecified')
    assert class_ == NetlistElement

    with pytest.raises(ValueError):
        get_class('unknown')


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
