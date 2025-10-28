from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, overload

from pydantic import BaseModel, ConfigDict

from netlist_carpentry import LOG
from netlist_carpentry.core.exceptions import (
    DetachedSegmentError,
    EvaluationError,
    ParentNotFoundError,
    SignalAssignmentError,
)
from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath
from netlist_carpentry.core.netlist_elements.element_type import EType
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.netlist_elements.port_segment import PortSegment
from netlist_carpentry.core.netlist_elements.segment_base import _Segment
from netlist_carpentry.core.protocols.signals import LogicLevel, SignalOrLogicLevel
from netlist_carpentry.core.signal import Signal
from netlist_carpentry.utils.cfg import CFG
from netlist_carpentry.utils.custom_list import CustomList

if TYPE_CHECKING:
    from netlist_carpentry.core.netlist_elements.wire import Wire


class WireSegment(_Segment, BaseModel):
    """
    Represents a wire segment within a netlist.

    A wire segment is a part of a wire that carries a signal between ports.
    A wire may consist of multiple wire segments, but should at least contain one.
    The number of wire segments in a wire indicates the width of the wire.
    If a wire has only one wire segment, it is a single-bit wire.
    If a wire has e.g. 4 wire segments, it is a 4-bit wire.
    A wire segment can have multiple ports connected to it, but should have exactly one driver and at least one load.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _signal: Signal = Signal.UNDEFINED
    _port_segments: CustomList[PortSegment] = CustomList()
    wire: Optional[NetlistElement]

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, WireSegment):
            return NotImplemented
        if not super().__eq__(value):
            return False
        return (self.wire is None and value.wire is None) or (self.wire is not None and value.wire is not None and self.wire.path == value.wire.path)

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        from netlist_carpentry.core.netlist_elements.wire import Wire

        if self.wire is None:
            if not CFG.allow_detached_segments:
                raise DetachedSegmentError(
                    f'No parent wire provided for wire segment {self.raw_path}! If this is intended, set CFG.allow_detached_segments to True!'
                )
        elif not isinstance(self.wire, Wire):
            raise TypeError(f'wireSegment.wire {self.raw_path} should be a wire object, but is a {type(self.wire).__name__}!')
        return super().model_post_init(__context)

    @property
    def path(self) -> WireSegmentPath:
        """
        Returns the WireSegmentPath of the netlist element.

        The WireSegmentPath object is constructed using the element's type and its raw hierarchical path.

        Returns:
            WireSegmentPath: The hierarchical path of the netlist element.
        """
        return WireSegmentPath(raw=self.raw_path)

    @property
    def type(self) -> EType:
        """The type of the element, which is a wire segment."""
        return EType.WIRE_SEGMENT

    @property
    def parent(self) -> Wire:
        from netlist_carpentry.core.netlist_elements.wire import Wire

        if isinstance(self.wire, Wire):
            return self.wire
        elif self.wire is None:
            raise ParentNotFoundError(
                f'No parent wire specified for wire segment {self.raw_path}. '
                + 'This is probably due to a bad instantiation (missing or bad "wire" parameter), or a subsequent modification of the wire, which corrupted the wire segment.'
            )
        raise TypeError(f'Bad type: Parent object of wire segment {self.raw_path} is {type(self.wire).__name__}, but should be {Wire.__name__}')

    @property
    def signal(self) -> Signal:
        """The signal on this wire segment."""
        return self._signal

    @property
    def port_segments(self) -> CustomList[PortSegment]:
        """The port segments connected to this wire segment."""
        return self._port_segments

    @property
    def nr_connected_ports(self) -> int:
        """The number of port segments connected to this wire segment."""
        return len(set(self.port_segments))

    @property
    def is_constant(self) -> bool:
        """
        Checks if the wire segment represents a constant value.

        A wire segment is considered a constant if its raw path is 'Z' or an empty string
        (both mean floating/high impedance), or if it's defined as a constant ('0' or '1').

        Returns:
            bool: True if the wire segment is a constant, False otherwise.
        """
        return False

    @property
    def is_defined_constant(self) -> bool:
        """
        Checks if the wire segment represents a defined constant value.

        A wire segment is considered defined and a constant if its raw path is '0' or '1'.

        Returns:
            bool: True if the wire segment is a defined constant, False otherwise.
        """
        return False

    @property
    def super_wire_name(self) -> str:
        """
        Retrieves the name of the parent Wire element.

        If a parent is available (i.e. the hierarchy level is 1 or more), it is returned.
        The parent Wire is the second last item in the ElementPath.
        Otherwise, an empty string is returned, indicating the lack of a parent Wire.

        Returns:
            str: The name of the parent Wire element if defined in the path, otherwise an empty string.
        """
        if self.path.hierarchy_level >= 1:
            return self.path.parent.name
        return ''

    @property
    def super_module_name(self) -> str:
        """
        Retrieves the name of the module that contains this WireSegment.

        If a parent is available (i.e. the hierarchy level is 2 or more), it is returned.
        The module name is the third last item in the ElementPath.
        Otherwise, an empty string is returned, indicating the lack of a parent module.

        Returns:
            str: The name of the module if defined in the path, otherwise an empty string.
        """
        if self.path.hierarchy_level >= 2:
            return self.path.nth_parent(2).name  # parent of wire segment parent: module to which the wire belongs
        return ''

    def add_port_segment(self, port_segment: PortSegment) -> PortSegment:
        """
        Adds a port segment to the set of ports connected to this wire segment.

        Args:
            port_segment (PortSegment): The port segment to add.

        Returns:
            PortSegment: The PortSegment object that was added to this wire segment.
        """
        return self.port_segments.add(port_segment, locked=self.locked)

    def add_port_segments(self, port_segments: Iterable[PortSegment]) -> List[PortSegment]:
        """
        Adds multiple ports to the set of ports connected to this wire segment.

        Args:
            port_segments: An iterable of PortSegment objects to add.

        Returns:
            List[PortSegment] A list with all port segments that were added.
        """
        return [self.add_port_segment(p) for p in port_segments]

    def remove_port_segment(self, port_segment: PortSegment) -> None:
        """
        Removes a port segment from the set of ports connected to this wire segment.

        Args:
            port_segment: The port segment to remove.
        """
        self.port_segments.remove(port_segment, locked=self.locked)

    @overload
    def set_signal(self, signal: LogicLevel) -> None: ...
    @overload
    def set_signal(self, signal: Signal) -> None: ...

    def set_signal(self, signal: SignalOrLogicLevel) -> None:
        """
        Sets the signal of this wire segment to the given new signal.

        This method is intended to be used in the signal evaluation process, where the signal of this wire segment is driven onto it
        by the driving port (e.g. a module input port or an instance output port driving this wire segment).
        This method is called during the signal evaluation process whenever the driving port of this wire segment updates its signal value.

        Args:
            signal (SignalOrLogicLevel): The new signal to set on the wire segment.
        """
        if not isinstance(signal, Signal):
            signal = Signal.get(signal)
        if self._signal.name != signal.name:
            self._signal = signal
            self.notify_listeners()

    def has_defined_signal(self) -> bool:
        """
        Checks if the signal on this wire segment is defined.

        A defined signal is a signal with a value that is not "x" (undefined) or "z" (unconnected/floating).
        A signal with value 0 or 1 is considered defined.
        """
        return self.signal.is_defined

    def driver(self, warn_if_issue: bool = False) -> List[PortSegment]:
        """
        Returns a list of port segments driving this wire segment.

        A driver is a port segment that is connected to this wire segment and is driving the signal on it.
        A wire segment should have only one driver, so this function should return a list with only one element.
        If the list has more or less than one element, a warning is logged.

        Args:
            warn_if_issue (bool): Whether or not to log a warning if there are more or less than 1 drivers. Defaults to False.

        Returns:
            List[PortSegment]: A list of port segments driving this wire segment.
        """
        drv_list = self._get_connection_dict(get_drivers=True)
        if warn_if_issue and len(drv_list) != 1:
            LOG.warn(f'Wire Segment {self.name} does have {len(drv_list)} drivers, instead of 1! (path is {self.path})')
        return drv_list

    def loads(self, warn_if_issue: bool = False) -> List[PortSegment]:
        """
        Returns a list of port segments being driven by this wire segment.

        A load is a port segment that is connected to this wire segment and is being driven by the signal on it.
        A wire segment can have multiple loads.
        If the list is empty (i.e., if there are no loads), a warning is logged if warn_if_issue is set to True.

        Args:
            warn_if_issue (bool): Whether or not to log a warning if there are no loads. Defaults to False.

        Returns:
            List[PortSegment]: A list of port segments being driven by this wire segment.
        """
        lds_list = self._get_connection_dict(get_drivers=False)
        if warn_if_issue and not lds_list:
            LOG.warn(f'Wire Segment {self.name} does not have any loads! (path is {self.path})')
        return lds_list

    def _get_connection_dict(self, get_drivers: bool) -> List[PortSegment]:
        """
        Retrieves a list of port segments based on their connection type to this wire segment.

        Args:
            get_drivers (bool): If True, returns port segments that are driving the wire segment (drivers).
                                If False, returns port segments that are being driven by the wire segment (loads).

        Returns:
            List[PortSegment]: A list of port segments matching the specified connection type (drivers or loads).
        """
        return [p for p in self.port_segments if (p.is_driver and get_drivers) or (p.is_load and not get_drivers)]

    def has_no_driver(self) -> bool:
        """
        Checks if this wire segment has no ports driving it.

        Returns:
            bool: True if the wire segment has no drivers, False otherwise.
        """
        return not self.driver()

    def has_multiple_drivers(self) -> bool:
        """
        Checks if this wire segment has multiple ports driving it.

        A wire segment should have only one driver, so this function should return False.
        If the function returns True, a warning is logged.

        Returns:
            bool: True if the wire segment has multiple drivers, False otherwise.
        """
        return len(self.driver()) > 1

    def has_no_loads(self) -> bool:
        """
        Checks if this wire segment has no ports being driven by it.

        A wire segment should have at least one load (otherwise it is dangling), so this function should return False.
        If the function returns True, a warning is logged.

        Returns:
            bool: True if the wire segment has no loads, False otherwise.
        """
        return not self.loads()

    def is_dangling(self) -> bool:
        """
        Checks if this wire segment is dangling.

        A wire segment is dangling if it has no ports driving it or no ports being driven by it.
        A wire segment should have exactly one driver and at least one load, so this function should normally return False.
        If the function returns True (i.e. if the wire segment has no drivers or no loads), a warning is logged.

        Returns:
            bool: True if the wire segment is dangling, False otherwise.
        """
        return self.has_no_driver() or self.has_no_loads()

    def has_problems(self) -> bool:
        """
        Checks if this wire segment has any problems.

        A wire segment has problems if it is dangling (i.e. it has no drivers or no loads) or if it has multiple drivers.

        Returns:
            bool: True if the wire segment has problems, False otherwise.
        """
        return self.is_dangling() or self.has_multiple_drivers()

    def evaluate(self) -> None:
        if not self.is_constant:
            new_signal = self._get_curr_signal()
            self.set_signal(new_signal)
            self._update_loads(new_signal)

    def _get_curr_signal(self) -> Signal:
        """
        Determines the current signal for this wire segment based on its drivers.

        Returns:
            The signal being driven by the driver(s). If there are multiple drivers, an EvaluationError is raised.
            If there are no drivers, Signal.UNDEFINED is returned.

        Raises:
            EvaluationError: If there are multiple drivers on this wire segment.
        """
        drv = self.driver()
        if len(drv) > 1:
            raise EvaluationError(f'Unable to evaluate wire segment {self.name}: found {len(drv)} drivers for bit {self.index}!')
        return Signal.UNDEFINED if not drv else drv[0].signal

    def _update_loads(self, new_signal: Signal) -> None:
        """
        Updates the signals of all loads connected to this wire segment with the new signal.

        Args:
            new_signal (Signal): The new signal to propagate to the loads.
        """
        lds = self.loads()
        for ld in lds:
            ld.set_signal(new_signal)

    def __hash__(self) -> int:
        return hash((self.raw_path, tuple(p.raw_path for p in self.port_segments)))

    def __str__(self) -> str:
        return f'{self.__class__.__name__} "{self.name}" with path {self.path.raw}'

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.path.raw}, Signal:{self.signal.value})'


class _WireSegmentConst(WireSegment):
    """A constant wire segment that always has the same signal value."""

    @property
    def is_constant(self) -> bool:
        return True

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        pass

    def set_signal(self, new_signal: SignalOrLogicLevel) -> None:
        raise SignalAssignmentError('Cannot set the signal of a constant wire segment!')

    def _get_curr_signal(self) -> Signal:
        """Returns the constant signal value of this wire segment."""
        return self.signal

    @property
    def is_placeholder_instance(self) -> bool:
        """
        A placeholder represents an element that does not have a specific path.

        This property is always True for constant wire segments.
        """
        return True

    def __str__(self) -> str:
        return f'Constant WireSegment "{self.name}" with path {self.path.raw} and signal {self.signal.value}'

    def __repr__(self) -> str:
        return f'Constant WireSegment "{self.signal.value}" WireSeg({self.path.raw})'


class WireSegmentConst0(_WireSegmentConst):
    """A wire segment that represents a constant 0 signal."""

    @property
    def is_defined_constant(self) -> bool:
        return True

    @property
    def signal(self) -> Signal:
        """Returns the constant signal value for this wire segment, which is always Signal.LOW."""
        return Signal.LOW


class WireSegmentConst1(_WireSegmentConst):
    """A wire segment that represents a constant 1 signal."""

    @property
    def is_defined_constant(self) -> bool:
        return True

    @property
    def signal(self) -> Signal:
        """Returns the constant signal value for this wire segment, which is always Signal.HIGH."""
        return Signal.HIGH


class WireSegmentConstZ(_WireSegmentConst):
    """A wire segment that represents a floating signal."""

    @property
    def is_defined_constant(self) -> bool:
        return False

    @property
    def signal(self) -> Signal:
        """Returns the constant signal value for this wire segment, which is always Signal.FLOATING."""
        return Signal.FLOATING


class WireSegmentConstX(_WireSegmentConst):
    """A wire segment that represents an unconnected signal (which has the value `X`/`UNDEFINED`)."""

    @property
    def is_defined_constant(self) -> bool:
        return False

    @property
    def signal(self) -> Signal:
        """Returns the constant signal value for this wire segment, which is always Signal.UNDEFINED."""
        return Signal.UNDEFINED


WIRE_SEGMENT_0 = WireSegmentConst0(raw_path='0', wire=None).change_mutability(is_now_locked=True)
"""A locked (unchangeable) placeholder representing the constant 0. Its signal is always 0."""

WIRE_SEGMENT_1 = WireSegmentConst1(raw_path='1', wire=None).change_mutability(is_now_locked=True)
"""A locked (unchangeable) placeholder representing the constant 1. Its signal is always 1."""

WIRE_SEGMENT_Z = WireSegmentConstZ(raw_path='Z', wire=None).change_mutability(is_now_locked=True)
"""A locked (unchangeable) placeholder representing a floating state. Its signal is always z (floating)."""

WIRE_SEGMENT_X = WireSegmentConstX(raw_path='X', wire=None).change_mutability(is_now_locked=True)
"""A locked (unchangeable) placeholder representing an unconnected state. Its signal is always x (unknown, don't-care)."""

CONST_MAP_VAL2OBJ: Dict[str, _WireSegmentConst] = {
    '0': WIRE_SEGMENT_0,
    '1': WIRE_SEGMENT_1,
    'Z': WIRE_SEGMENT_Z,
    'X': WIRE_SEGMENT_X,
    '': WIRE_SEGMENT_X,
}
"""A mapping from constant values to their corresponding wire segment objects."""

CONST_MAP_VAL2VERILOG: Dict[str, str] = {'0': "1'b0", '1': "1'b1", 'Z': "1'bz", 'X': "1'bx", '': "1'bx"}
"""A mapping from constant values to Verilog signal representations."""

CONST_MAP_YOSYS2OBJ: Dict[str, _WireSegmentConst] = {'0': WIRE_SEGMENT_0, '1': WIRE_SEGMENT_1, 'x': WIRE_SEGMENT_X, 'z': WIRE_SEGMENT_Z}
"""A mapping from Yosys wire segment strings to their corresponding wire segment objects."""
