from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional, overload

from pydantic import BaseModel, ConfigDict
from typing_extensions import Self

from netlist_carpentry import CFG, LOG
from netlist_carpentry.core.exceptions import (
    AlreadyConnectedError,
    DetachedSegmentError,
    InvalidPortDirectionError,
    InvalidSignalError,
    ObjectLockedError,
    ParentNotFoundError,
)
from netlist_carpentry.core.netlist_elements.element_path import PortSegmentPath, WireSegmentPath
from netlist_carpentry.core.netlist_elements.element_type import EType
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.netlist_elements.segment_base import _Segment
from netlist_carpentry.core.port_direction import PortDirection
from netlist_carpentry.core.protocols.signals import LogicLevel, SignalOrLogicLevel
from netlist_carpentry.core.signal import Signal

if TYPE_CHECKING:
    from netlist_carpentry.core.netlist_elements.port import Port


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
        if isinstance(value, PortSegment):
            return self.raw_path == value.raw_path and self.raw_ws_path == value.raw_ws_path
        return False

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        from netlist_carpentry.core.netlist_elements.port import Port

        if self.port is None:
            if not CFG.allow_detached_segments:
                raise DetachedSegmentError(
                    f'No parent port provided for port segment {self.raw_path}! If this is intended, set CFG.allow_detached_segments to True!'
                )
        elif not isinstance(self.port, Port):
            raise TypeError(f'PortSegment.port {self.raw_path} should be a port object, but is a {type(self.port).__name__}!')
        return super().model_post_init(__context)

    @property
    def path(self) -> PortSegmentPath:
        """
        Returns the PortSegmentPath of the netlist element.

        The PortSegmentPath object is constructed using the element's type and its raw hierarchical path.

        Returns:
            PortSegmentPath: The hierarchical path of the netlist element.
        """
        return PortSegmentPath(raw=self.raw_path)

    @property
    def raw_ws_path(self) -> str:
        """
        Returns the raw wire segment path of the port connected to this wire segment.

        The wire segment path indicates to which wire this port segment is connected.
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
    def parent(self) -> Port[NetlistElement]:
        from netlist_carpentry.core.netlist_elements.port import Port

        if isinstance(self.port, Port):
            return self.port
        elif self.port is None:
            raise ParentNotFoundError(
                f'No parent port specified for port segment {self.raw_path}. '
                + 'This is probably due to a bad instantiation (missing or bad "port" parameter), or a subsequent modification of the port, which corrupted the segment.'
            )
        raise TypeError(f'Bad type: Parent object of port segment {self.raw_path} is {type(self.port).__name__}, but should be {Port.__name__}')

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
    def wire_name(self) -> str:
        """Returns the name of the wire segment connected to this port segment."""
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
        return int(self.signal.value) if self.signal.is_defined else None

    @property
    def is_connected(self) -> bool:
        """
        Checks if the port segment is connected to a wire segment.

        Returns:
            bool: Whether the port segment is connected to a wire segment.

        Examples:
            ```python
            >>> port_seg = PortSegment(raw_element_path='module1.port1.0', port=Port(...)).set_ws_path('module1.wire1.0')
            >>> print(port_seg.is_connected)
            True
            >>> port_seg = PortSegment(raw_element_path='module1.port1.0', port=Port(...))
            >>> print(port_seg.is_connected)
            False
            ```
        """
        return not self.is_unconnected

    @property
    def is_unconnected(self) -> bool:
        """
        Checks if the port segment is unconnected.

        Returns:
            bool: Whether the port segment is unconnected.

        Examples:
            ```python
            >>> port_seg = PortSegment(raw_element_path='module1.port1.0', port=Port(...)).set_ws_path('module1.wire1.0')
            >>> print(port_seg.is_unconnected)
            False
            >>> port_seg = PortSegment(raw_element_path='module1.port1.0', port=Port(...))
            >>> print(port_seg.is_unconnected)
            True
            ```
        """
        return self.raw_ws_path == '' or self.raw_ws_path == 'X'  # Empty is treated as unconnected

    @property
    def is_floating(self) -> bool:
        """
        Checks if the port segment is floating.

        Returns:
            bool: Whether the port segment is floating.

        Examples:
            ```python
            >>> port_seg = PortSegment(raw_element_path='module1.port1.0', port=Port(...)).tie_signal("Z")
            >>> print(port_seg.is_floating)
            True
            >>> port_seg = PortSegment(raw_element_path='module1.port1.0', port=Port(...))
            >>> print(port_seg.is_floating)
            False
            ```
        """
        return self.raw_ws_path == 'Z'

    @property
    def is_tied(self) -> bool:
        """
        Checks if the port segment is a constant.

        A port segment is considered a constant if it is tied to either `0`, `1`, `Z` or `X`.

        Returns:
            bool: Whether the port segment is a constant.
        """
        return self.is_tied_undefined or self.is_tied_defined

    @property
    def is_tied_defined(self) -> bool:
        """
        Checks if the port segment is tied to a defined constant wire.

        A port segment is considered as tied to a defined constant wire if its raw wire segment path is either `0` or `1`.
        This means, this wire segment always either carries the signal value `0` or `1`.

        Returns:
            bool: Whether the port segment is tied to a defined constant wire.
        """
        return self.raw_ws_path == '0' or self.raw_ws_path == '1'

    @property
    def is_tied_undefined(self) -> bool:
        """
        Checks if the port segment is tied to an undefined constant wire.

        A port segment is considered as tied to an undefined constant wire if its raw wire segment path is either `Z`, `X` or ` ` (empty).

        Returns:
            bool: Whether the port segment is tied to an undefined constant wire.
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
    def direction(self) -> PortDirection:
        """Returns the direction of the port."""
        return self.parent.direction

    @property
    def parent_name(self) -> str:
        """
        Retrieves the name of the parent Port element from the path.

        If a parent is available (i.e. the hierarchy level is 1 or more), it is returned.
        The parent Port is the second last item in the ElementPath.
        Otherwise, an empty string is returned, indicating the lack of a parent Port.

        Returns:
            str: The name of the parent Port element if defined in the path, otherwise an empty string.
        """
        if self.path.hierarchy_level >= 1:
            return self.path.parent.name
        return ''

    @property
    def parent_parent_name(self) -> str:
        """
        Retrieves the name of the instance or module that contains this PortSegment.

        If a parent is available (i.e. the hierarchy level is 2 or more), it is returned.
        The instance or module name is the third last item in the ElementPath.
        Otherwise, an empty string is returned, indicating the lack of a parent instance or module.

        Returns:
            str: The name of the instance or module if defined in the path, otherwise an empty string.
        """
        if self.path.hierarchy_level >= 2:
            return self.path.nth_parent(2).name  # parent of port segment parent: either module or instance to which the port belongs
        return ''

    def set_ws_path(self, ws_path: str) -> Self:
        """
        Sets or updates the wire segment path for this port segment.

        Args:
            ws_path (str): The new wire segment path to be set.

        Returns:
            PortSegment: This port segment with its wire segment path updated.
        """
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
            InvalidPortDirectionError: If this port segment belongs to an instance output port,
                which is driven by the instance inputs and the instance's internal logic.
            InvalidSignalError: If an invalid value is provided.
        """
        signal_val = str(signal.value).upper() if isinstance(signal, Signal) else signal
        if not self.is_tied:
            raise AlreadyConnectedError(
                f'Unable to tie signal on port segment {self.raw_path} to value {signal_val}: Disconnect it first from its current wire!'
            )
        if self.is_instance_port and self.is_output:
            raise InvalidPortDirectionError(
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

        **Does only work for NON-CONSTANT port segments!** This method is intended to be used in
        the signal evaluation process, where constant signals should be treated accordingly.
        Accordingly, it should be avoided that constant inputs are accidentally modified during signal evaluation.
        To change the signal of a port segment to be a constant value, use the `tie_signal` method instead.

        Args:
            signal (Signal): The new signal to be set.

        Example:
            ```python
            >>> port_seg = PortSegment(raw_path='a.b.c.1')
            >>> port_seg.set_signal(Signal.HIGH)
            True
            >>> port_seg.signal
            Signal.HIGH
            ```
        """
        if not isinstance(signal, Signal):
            signal = Signal.get(signal)
        prev_signal = self.signal
        if self.is_tied and self.is_load:
            LOG.warn(f'Cannot set signal on port segment {self.raw_path}: Port Segment is tied to {self.signal}!')
        elif signal != prev_signal:
            self._signal = signal
            self.notify_listeners()

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
        self.set_ws_path(new_wire_segment_path.raw)

    def __hash__(self) -> int:
        return hash((self.raw_path, self.raw_ws_path))

    def __str__(self) -> str:
        return f'{self.__class__.__name__} "{self.name}" with path {self.path.raw}'

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.path.raw}, Signal:{self.signal.value})'
