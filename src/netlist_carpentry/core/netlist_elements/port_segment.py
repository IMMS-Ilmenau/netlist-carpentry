"""Module for handling of port segments (i.e. port slices) inside a circuit module."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Union, overload

from pydantic import BaseModel, ConfigDict
from typing_extensions import Self

from netlist_carpentry import CFG, LOG, Direction, Signal
from netlist_carpentry.core.enums.element_type import EType
from netlist_carpentry.core.exceptions import (
    AlreadyConnectedError,
    DetachedSegmentError,
    InvalidDirectionError,
    InvalidSignalError,
    ObjectLockedError,
    ParentNotFoundError,
    SignalAssignmentError,
)
from netlist_carpentry.core.netlist_elements.element_path import PortSegmentPath, WireSegmentPath
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.netlist_elements.segment_base import _Segment
from netlist_carpentry.core.protocols.signals import LogicLevel, SignalOrLogicLevel

if TYPE_CHECKING:
    from netlist_carpentry import Instance, Module, Port
    from netlist_carpentry.core.netlist_elements.wire_segment import WireSegment


class PortSegment(_Segment, BaseModel):
    """
    A PortSegment is a NetlistElement that represents a segment of a Port.

    A PortSegment is the smallest unit of a Port and is responsible for connecting two WireSegments together.
    To be functional, a port must have at least one PortSegment.
    A port with a width of e.g. 4 bits will have 4 PortSegments.
    A PortSegment (being part of a port) is connected to a WireSegment and is responsible for propagating
    the signal from the WireSegment to the Port.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _raw_ws_path: str = ''
    _signal: Signal = Signal.UNDEFINED
    port: Optional[NetlistElement]

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, PortSegment):
            return NotImplemented
        if not super().__eq__(value):
            return False
        same_parents = (not self.has_parent and not value.has_parent) or (self.parent.path == value.parent.path)
        return same_parents and self.ws_path == value.ws_path

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        if not self.has_parent:
            if not CFG.allow_detached_segments:
                raise DetachedSegmentError(
                    f'No parent port provided for port segment {self.raw_path}! If this is intended, set CFG.allow_detached_segments to True!'
                )
        return super().model_post_init(__context)

    @property
    def path(self) -> PortSegmentPath:
        """
        Returns the PortSegmentPath of the netlist element.

        The PortSegmentPath object is constructed using the element's type and its raw hierarchical path.

        Returns:
            PortSegmentPath: The hierarchical path of the netlist element.
        """
        if self.has_parent:
            return PortSegmentPath(raw='.'.join([*self.parent.path.parts, self.name]))
        return PortSegmentPath(raw=self.name)

    @property
    def raw_ws_path(self) -> str:
        """
        Returns the raw wire segment path that this port segment is connected to.

        The wire segment path indicates which wire this port segment is connected to.
        The schema follows the common structure, consisting of the different hierarchy levels,
        separated by the separation character.

        If this variable is e.g. `top_module.some_wire.0`, then this port segment is connected to
        the 0-th bit of the wire `some_wire` in the module `top_module`.
        """
        return self._raw_ws_path

    @property
    def type(self) -> EType:
        """The type of the element, which is a port segment."""
        return EType.PORT_SEGMENT

    @property
    def parent(self) -> Union['Port[Module]', 'Port[Instance]']:
        from netlist_carpentry.core.netlist_elements.port import Port

        if isinstance(self.port, Port):
            return self.port
        elif self.port is None:
            raise ParentNotFoundError(
                f'No parent port specified for port segment {self.name}. '
                + 'This is probably due to a bad instantiation (missing or bad "port" parameter), or a subsequent modification of the port, which corrupted the segment.'
            )
        raise TypeError(f'Bad type: Parent object of port segment {self.name} is {type(self.port).__name__}, but should be {Port.__name__}')

    @property
    def grandparent(self) -> Union[Module, Instance]:
        """
        Retrieves the instance or module that contains this PortSegment.

        If a parent is available (i.e. the hierarchy level is 2 or more), it is returned.

        Returns:
            Union[Module, Instance]: The instance or module if it exists.

        Raises:
            ParentNotFoundError: If no parent or grandparent was found.
        """
        return self.parent.parent  # parent of port segment parent: either module or instance to which the port belongs

    @property
    def ws_path(self) -> WireSegmentPath:
        """
        The WireSegmentPath object of the wire segment connected to this port segment.

        Returns the WireSegmentPath object of the wire segment connected to this port segment, or
        the placeholder path (indicating an unconnected port segment) if it is not connected.
        """
        from netlist_carpentry import WIRE_SEGMENT_X

        if self.raw_ws_path == '':
            return WIRE_SEGMENT_X.path
        return WireSegmentPath(raw=self.raw_ws_path)

    @property
    def ws(self) -> 'WireSegment':
        """Returns the wire segment connected to this port segment."""
        return self.parent.module.get_from_path(self.ws_path)

    @property
    def wire_name(self) -> str:
        """
        Returns the name of the wire segment connected to this port segment.

        Returns the second-to-last component of the wire segment path, which corresponds
        to the wire name. Returns an empty string if the port segment is unconnected
        or if the path does not have enough components.
        """
        return self.ws_path[-2] if self.ws_path.hierarchy_level >= 1 else ''

    @property
    def signal(self) -> Signal:
        """Returns the signal of the port segment."""
        # Check for constant instance inputs or module outputs
        if self.is_tied and self.is_load:
            from netlist_carpentry import CONST_MAP_VAL2OBJ, WIRE_SEGMENT_X

            if self.is_unconnected:
                return CONST_MAP_VAL2OBJ['Z'].signal
            return CONST_MAP_VAL2OBJ.get(self.raw_ws_path, WIRE_SEGMENT_X).signal
        return self._signal

    @property
    def signal_int(self) -> Optional[int]:
        """The signal of this port segment as an integer (0 or 1), if it is defined, otherwise None."""
        return int(self.signal) if self.signal.is_defined else None

    @property
    def is_connected(self) -> bool:
        """
        Checks if the port segment is connected to a wire segment.

        A port segment is considered connected if its wire segment path is neither empty nor 'X'.
        Note that tied states ('0', '1', 'Z') are considered connected.

        Returns:
            bool: True if the port segment is connected to a wire segment, False otherwise.

        Examples:
            ```python
            >>> port_seg = PortSegment(name='0', port=Port(...)).set_ws_path('module1.wire1.0')
            >>> port_seg.is_connected
            True
            >>> port_seg = PortSegment(name='0', port=Port(...))
            >>> port_seg.is_connected
            False
            ```
        """
        return not self.is_unconnected

    @property
    def is_unconnected(self) -> bool:
        """
        Checks if the port segment is unconnected.

        A port segment is considered unconnected if its wire segment path is empty ('') or 'X'.
        Note that 'X' is treated as an undefined/unconnected state.

        Returns:
            bool: True if the port segment is unconnected, False otherwise.

        Examples:
            ```python
            >>> port_seg = PortSegment(name='0', port=Port(...)).set_ws_path('module1.wire1.0')
            >>> port_seg.is_unconnected
            False
            >>> port_seg = PortSegment(name='0', port=Port(...))
            >>> port_seg.is_unconnected
            True
            ```
        """
        return self.raw_ws_path == '' or self.raw_ws_path == 'X'

    @property
    def is_floating(self) -> bool:
        """
        Checks if the port segment is floating (tied to high-impedance 'Z').

        A port segment is considered floating if its wire segment path is 'Z'.

        Returns:
            bool: True if the port segment is floating, False otherwise.

        Examples:
            ```python
            >>> port_seg = PortSegment(name='0', port=Port(...)).tie_signal('Z')
            >>> port_seg.is_floating
            True
            >>> port_seg = PortSegment(name='0', port=Port(...))
            >>> port_seg.is_floating
            False
            ```
        """
        return self.raw_ws_path == 'Z'

    @property
    def is_tied(self) -> bool:
        """
        Checks if the port segment is tied to a constant value.

        A port segment is considered tied if it is connected to a constant wire ('0', '1', 'Z', 'X')
        or is unconnected (empty path, treated as undefined).

        Returns:
            bool: True if the port segment is tied to a constant, False otherwise.
        """
        return self.is_tied_undefined or self.is_tied_defined

    @property
    def is_tied_defined(self) -> bool:
        """
        Checks if the port segment is tied to a defined constant wire.

        A port segment is considered tied to a defined constant if its raw wire segment path is either `'0'` or `'1'`.
        This means the wire segment always carries a defined signal value (logic 0 or logic 1).

        Returns:
            bool: True if the port segment is tied to a defined constant ('0' or '1'), False otherwise.
        """
        return self.raw_ws_path == '0' or self.raw_ws_path == '1'

    @property
    def is_tied_undefined(self) -> bool:
        """
        Checks if the port segment is tied to an undefined or floating state.

        A port segment is considered tied to an undefined state if it is either:
        - Floating (tied to `'Z'`, high-impedance)
        - Unconnected (raw wire segment path is empty `''` or `'X'`)

        Note: An unconnected port segment (empty path) is included here because it behaves
        like a floating input in signal evaluation. It is NOT truly "tied" in the hardware sense,
        but is grouped with undefined states for signal propagation purposes.

        Returns:
            bool: True if the port segment is floating or unconnected, False otherwise.
        """
        return self.is_floating or self.is_unconnected

    @property
    def is_instance_port(self) -> bool:
        """
        Whether the port associated with this port segment is an instance port.

        True, if the superordinate port is an instance port.
        False, if the superordinate port is a module port.
        """
        return self.parent.is_instance_port

    @property
    def is_module_port(self) -> bool:
        """
        Whether the port associated with this port segment is a module port.

        True, if the superordinate port is a module port.
        False, if the superordinate port is an instance port.
        """
        return self.parent.is_module_port

    @property
    def is_input(self) -> bool:
        """
        Whether this port is an input port.

        Returns:
            bool: True if this port is an input port, False otherwise.
        """
        return self.parent.is_input

    @property
    def is_output(self) -> bool:
        """
        Whether this port is an output port.

        Returns:
            bool: True if this port is an output port, False otherwise.
        """
        return self.parent.is_output

    @property
    def is_driver(self) -> bool:
        """
        Whether this port is a driver port, i.e. a port driving a signal.

        A driver port is an input port of a module, or an output port of an instance.

        Returns:
            bool: True if this port is a driver port, False otherwise.
        """
        return (self.is_instance_port and self.is_output) or (self.is_module_port and self.is_input)

    @property
    def is_load(self) -> bool:
        """
        Whether this port is a load port, i.e. a port being driven by a signal.

        A load port is an output port of a module, or an input port of an instance.

        Returns:
            bool: True if this port is a load port, False otherwise.
        """
        return (self.is_instance_port and self.is_input) or (self.is_module_port and self.is_output)

    @property
    def direction(self) -> Direction:
        """Returns the direction of the port."""
        return self.parent.direction

    def set_ws_path(self, ws_path: Union[str, WireSegmentPath]) -> Self:
        """
        Sets or updates the wire segment path for this port segment.

        Args:
            ws_path (Union[str, WireSegmentPath]): The new wire segment path to be set,
                either as plain string or as path object.

        Returns:
            PortSegment: This port segment with its wire segment path updated.
        """
        if isinstance(ws_path, WireSegmentPath):
            ws_path = ws_path.raw
        self._raw_ws_path = ws_path
        return self

    @overload
    def tie_signal(self, signal: LogicLevel) -> None: ...
    @overload
    def tie_signal(self, signal: Signal) -> None: ...

    def tie_signal(self, signal: SignalOrLogicLevel) -> None:
        """
        Ties the signal value of this port segment to a constant by setting the wire path to a constant value ('0', '1', 'Z', or 'X').

        **Does not work for instance output ports, as they are always driven by their parent instances.**

        Args:
            signal (SignalOrLogicLevel): The constant signal value to be set. Must be one of '0', '1', 'Z', or 'X'.
                Choosing 'X' unconnects the port segment completely.
                May alternatively be a Signal object.

        Raises:
            AlreadyConnectedError: If this segment is belongs to a load port and is already connected to a wire,
                from which it receives its value.
            InvalidDirectionError: If this port segment belongs to an instance output port,
                which is driven by the instance inputs and the instance's internal logic.
            InvalidSignalError: If an invalid value is provided.
        """
        signal_val = str(signal.value).upper() if isinstance(signal, Signal) else str(signal)
        if not self.is_tied:
            raise AlreadyConnectedError(
                f'Unable to tie signal on port segment {self.raw_path} to value {signal_val}: Disconnect it first from its current wire!'
            )
        if self.is_instance_port and self.is_output:
            raise InvalidDirectionError(
                f'Cannot tie constant signal on instance output port segment {self.raw_path}, since it is driven by the instance it belongs to!'
            )
        if signal_val not in ['0', '1', 'Z', 'X']:
            raise InvalidSignalError(
                f"Unable to tie signal on port segment {self.raw_path} to value {signal_val}: Value must be one of '0', '1', 'Z' or 'X'."
            )
        LOG.debug(f'Tieing constant signal {signal_val} on port segment {self.raw_path}.')
        self.set_ws_path(str(signal_val))

    @overload
    def set_signal(self, signal: LogicLevel) -> None: ...
    @overload
    def set_signal(self, signal: Signal) -> None: ...

    def set_signal(self, signal: SignalOrLogicLevel) -> None:
        """
        Sets the signal of the port segment and notifies all listeners of the change.

        **Only works for NON-CONSTANT port segments!** This method is intended to be used in
        the signal evaluation process, where constant signals should be treated accordingly.
        Accordingly, it should be avoided that constant inputs are accidentally modified during signal evaluation.
        To change the signal of a port segment to be a constant value, use the `tie_signal` method instead.

        Args:
            signal (SignalOrLogicLevel): The new signal to be set. Can be a ``Signal`` enum value
                or a logic level string ('0', '1').

        Raises:
            SignalAssignmentError: If this port segment is tied to a constant value (e.g. '0' or '1',
                or is floating/unconnected). To change the signal of a tied port segment,
                use the ``tie_signal()`` method instead.
        """
        if not isinstance(signal, Signal):
            signal = Signal.get(signal)
        if self.is_tied and self.is_load:
            raise SignalAssignmentError(
                f'Cannot set signal on port segment {self.raw_path}: Port Segment is tied to {self.signal}! '
                + 'To change the signal value of a tied port segment, use the `tie_signal()` method instead.'
            )
        self._signal = signal

    def driver(self) -> Optional[PortSegment]:
        """
        Returns the driver of this port segment if it has one, otherwise None.

        Can only be retrieved if this port segment belongs to a load port and is connected to a wire.

        Raises:
            InvalidDirectionError: If this port segment is a signal-driving port
                (e.g. instance output or module input).

        Returns:
            Optional[PortSegment]: The opposing port segment that drives signal values onto this port segment.
                Returns None if this port segment is unconnected.
        """
        if self.is_driver:
            raise InvalidDirectionError(
                f'Cannot get driving port of port segment {self.raw_path}: This port segment is a driver and thus does not have a driver!'
            )
        if self.is_unconnected:
            return None
        return self.parent.module.wires[self.ws_path.parent.name].driver()[self.index]

    def loads(self) -> List[PortSegment]:
        """
        Returns the loads of this port segment as a list of port segments.

        If this port segment itself belongs to a load port, it is also included in the list of loads.

        Returns:
            List[PortSegment]: A list of all port segments that receive the same signal via the same wire.
                Returns an empty list if this port segment is unconnected.
        """
        if self.is_unconnected:
            return []
        return self.parent.module.wires[self.ws_path.parent.name].loads()[self.index]

    def change_connection(self, new_wire_segment_path: WireSegmentPath = WireSegmentPath(raw='')) -> None:
        """
        Changes the connection of this PortSegment to a new wire segment path.

        Args:
            new_wire_segment_path (WireSegmentPath): The new wire segment path for the connection.
                If not specified or set to `WireSegmentPath(raw='')` (an empty path), it is considered as unconnected.
                Defaults to `WireSegmentPath(raw='')`.

        Raises:
            ObjectLockedError: If this PortSegment is locked.
        """
        if self.locked:
            raise ObjectLockedError(f'Unable to connect port segment {self.raw_path} to {new_wire_segment_path.raw}: Port segment is locked!')
        self.set_ws_path(new_wire_segment_path)

    def __str__(self) -> str:
        return f'{self.__class__.__name__} "{self.name}" with path {self.path.raw}'

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.path.raw}, Signal:{self.signal.value})'
