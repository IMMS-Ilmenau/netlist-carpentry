from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Callable,
    Dict,
    Generator,
    Generic,
    Literal,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
    overload,
)

from pydantic import BaseModel
from typing_extensions import Self

from netlist_carpentry import LOG
from netlist_carpentry.core.exceptions import ObjectLockedError, ObjectNotFoundError, ParentNotFoundError
from netlist_carpentry.core.netlist_elements.element_path import PortPath, WirePath, WireSegmentPath
from netlist_carpentry.core.netlist_elements.element_type import EType
from netlist_carpentry.core.netlist_elements.mixins.metadata import METADATA_DICT, NESTED_DICT
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.netlist_elements.port_segment import PortSegment
from netlist_carpentry.core.port_direction import PortDirection
from netlist_carpentry.core.protocols.signals import LogicLevel, SignalDict, SignalOrLogicLevel
from netlist_carpentry.core.signal import Signal
from netlist_carpentry.utils.custom_dict import CustomDict

if TYPE_CHECKING:
    from netlist_carpentry import Instance, Module

T_PARENT = TypeVar('T_PARENT', bound='Union[Module, Instance]')


class Port(NetlistElement, BaseModel, Generic[T_PARENT]):
    """
    Represents a port in the netlist.

    This class is generic to sensibly differentiate between module and instance ports.
    The value of the generic is derived from `module_or_instance` and is used mainly for type annotation.
    If this port belongs to a module, use `Port[Module]` otherwise use `Port[Instance]`.

    Attributes:
        direction (PortDirection): The direction of this port.
        msb_first (bool, optional): Whether the index order of this port is MSB first. Defaults to True.
        module_or_instance(Optional[Module, Instance]): The parent object (module or instance) to which this port belongs.
            Can also be None, in which case the port does not belong to any object initially, but should be assigned to an instance or module later.
    """

    direction: PortDirection
    """The direction of this port, indicating whether it's an input, output, or bidirectional connection."""
    _segments = CustomDict[int, PortSegment]()
    _signal: Signal = Signal.UNDEFINED
    msb_first: bool = True
    """Whether this port is MSB (most significant bit) first or not"""
    module_or_instance: Optional[T_PARENT]

    def __getitem__(self, index: int) -> PortSegment:
        """
        Allows subscripting of a Port object to access its port segments directly.

        This is mainly for convenience, to use Port[i] instead of Port.segments[i].

        Args:
            index (int): The index of the desired port segment.

        Returns:
            PortSegment: The port segment at the specified index.
        """
        if index in self.segments:
            return self.segments[index]
        raise IndexError(f'Port {self.raw_path} does not have a segment {index}!')

    def __len__(self) -> int:
        return len(self.segments)

    def __iter__(self) -> Generator[Tuple[int, PortSegment], None, None]:  # type: ignore[override]
        return iter(s for s in self.segments.items())

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        from netlist_carpentry.core.netlist_elements.instance import Instance
        from netlist_carpentry.core.netlist_elements.module import Module

        if self.module_or_instance is None or isinstance(self.module_or_instance, Module) or isinstance(self.module_or_instance, Instance):
            return super().model_post_init(__context)
        raise TypeError(
            f'Port.module_or_instance {self.raw_path} should be either a module or an instance, but is a {type(self.module_or_instance).__name__}!'
        )

    @property
    def path(self) -> PortPath:
        """
        Returns the PortPath of the netlist element.

        The PortPath object is constructed using the element's type and its raw hierarchical path.

        Returns:
            PortPath: The hierarchical path of the netlist element.
        """
        return PortPath(raw=self.raw_path)

    @property
    def type(self) -> EType:
        """The type of the element, which is a port."""
        return EType.PORT

    @property
    def parent(self) -> T_PARENT:
        if not hasattr(self, 'module_or_instance'):
            LOG.warn('ATTR MISS')
        if self.module_or_instance is not None:
            return self.module_or_instance
        raise ParentNotFoundError(
            f'No parent port specified for port {self.raw_path}. '
            + 'This is probably due to a bad instantiation (missing or bad "module_or_instance" parameter), or a subsequent modification of either the module or instance, which corrupted the port.'
        )

    @property
    def segments(self) -> CustomDict[int, PortSegment]:
        """Returns the port segments of this port, where the key is the bit index."""
        return self._segments

    @property
    def signal(self) -> Signal:
        """
        Returns the signal associated with this port.

        **Does only work for 1-bit wide ports, as a convenient alternative for `Port.signal_array`.**

        If there's only one segment in the port (i.e. the port is exactly 1 bit wide), returns the signal of that segment.
        Otherwise, returns Signal.UNDEFINED to indicate ambiguity.
        This is meant as a shortcut of signal_array[0], since many ports commonly are only 1 bit wide.
        Thus, this property should only be used for 1-bit wide ports!

        Returns:
            Signal: The signal associated with this port, if this port is 1 bit wide, otherwise returns Signal.UNDEFINED.
        """
        if len(self.segments) == 1:
            return self[next(iter(self.segments))].signal
        LOG.warn(
            f'Unable to return signal of port {self.name} (at {self.raw_path}): Port is {len(self.segments)} bit wide and thus does have multiple signals. Use "Port.signal_array" instead!'
        )
        return Signal.UNDEFINED

    @property
    def signal_int(self) -> Optional[int]:
        """
        The signal currently applied to this port as an integer, if possible.

        If `Port.signed` is False, the value is treated as an unsigned signal.
        If `Port.signed` is True, the value is treated as a signed signal, using the two's
        complement, if the sign bit is `1`.

        Offset is ignored when calculating this property. If a 4 bit port has an offset of 3, the returned
        integer is built form the actually present segments (i.e. the integer value is between 0 and 15).
        Analogously, if segments are missing in between, they are also ignored and treated as if there
        was no gap. If a port has a segment with index 0 and with index 2, but a segment for index 1 is
        missing, the returned integer will be the decimal representation of the values of the segments 2 and 0,
        without including or mentioning the gap at index 1. The calculated number ranges thus between 0 and 3,
        and *not* between 0 and 7.

        If the signal string for a 4 bit port is '1001', then this property will return 9.
        If the string contains 'x' or 'z', the signal does not form an integer and this property returns `None`.
        """
        try:
            sig_str_msb = self.signal_str if self.msb_first else ''.join(reversed(self.signal_str))
            int_val = int(sig_str_msb, 2)
            if self.signed and sig_str_msb[0] == '1':  # Is signed and sign bit is set
                int_val -= 1 << self.width
            return int_val
        except ValueError:
            return None

    @property
    def signal_array(self) -> Dict[int, Signal]:
        """
        Returns an array of signals associated with this port, ordered by bit index.

        If the port is empty (i.e., no segments), returns an empty list.
        Otherwise, returns a list of signals corresponding to each segment in the port,
        where the index of the list corresponds to the bit index of the segment.

        Returns:
            Dict[int, Signal]: The array of signals associated with each segment of this port.
        """
        return {idx: self[idx].signal for idx in self.segments}

    @property
    def signal_str(self) -> str:
        """
        The signal currently applied to this port as a string (MSB first).

        The length of the string corresponds to the width of this port.
        Offset is ignored by this property. If a 4 bit port has an offset of 3, the returned
        string only consists of the actually present segments (i.e. the string consists of the signals
        at the 4 present segments).
        Analogously, if segments are missing in between, they are also ignored and treated as if there
        was no gap. If a port has a segment with index 0 and with index 2, but a segment for index 1 is
        missing (not to be confused with an unconnected segment), the returned string will have the values
        of the segments 2 and 0 (in descending order), without including or mentioning the gap at index 1.

        If the signal string for a 4 bit port is '1010', then the segments with indices 3 and 1 (plus offset)
        are currently 1 and the other two segments are 0.
        If the string contains 'x', the corresponding segment has an undefined value, and if the string
        contains 'z', the corresponding segment is floating.
        """
        sorted_keys = sorted(self.signal_array.keys(), reverse=True)
        return ''.join(self.signal_array[k].value for k in sorted_keys)

    @property
    def has_undefined_signals(self) -> bool:
        """
        Whether any of the port's signals are undefined (e.g. "X" or "Z").

        False, if the signals on all port segments are either "0" or "1".
        Otherwise, returns True.
        """
        return any(s.is_undefined for s in self.signal_array.values())

    @property
    def is_tied(self) -> bool:
        """
        True if all of the port's segments are tied to a constant (e.g. "0" or "1").
        Unconnected ("X") or floating port segments ("Z") are also considered tied in this context.
        To check if all port segments are tied to "0" or "1", use `Port.is_tied_defined`.

        False, if any segments are connected to a wire.
        """
        return all(s.is_tied for s in self.segments.values())

    @property
    def is_tied_partly(self) -> bool:
        """
        True if any of the port's segments are tied to a constant (e.g. "0" or "1").
        Unconnected ("X") or floating port segments ("Z") are also considered tied in this context.
        To check if all port segments are tied to "0" or "1", use `Port.is_tied_defined`.

        False, if all segments are connected to a wire.
        """
        return any(s.is_tied for s in self.segments.values())

    @property
    def is_connected_partly(self) -> bool:
        """
        Determines whether the port is partly connected.

        A port is considered partly connected if at least one of its segments is connected to a wire.

        Returns:
            bool: True if at least one segment is connected, False otherwise.
        """
        return any(seg.is_connected for seg in self.segments.values())

    @property
    def is_connected(self) -> bool:
        """
        Determines whether the port is fully connected.

        A port is considered fully connected if all of its segments are connected to a wire.

        Returns:
            bool: True if all segments are connected, False otherwise.
        """
        return all(seg.is_connected for seg in self.segments.values())

    @property
    def is_unconnected(self) -> bool:
        """
        Determines whether the port is completely unconnected.

        A port is considered completely unconnected if none of its segments are connected to a wire.

        Returns:
            bool: True if no segments are connected, False otherwise.
        """
        return not self.is_connected_partly

    @property
    def is_unconnected_partly(self) -> bool:
        """
        Determines whether the port is partly unconnected.

        A port is considered partly unconnected if at least one of its segments is unconnected.

        Returns:
            bool: True if at least one segment is unconnected, False otherwise.
        """
        return not self.is_connected

    @property
    def is_floating(self) -> bool:
        """
        Determines whether the port is completely floating.

        A port is considered completely floating if at least one of its segments is floating.

        Returns:
            bool: True if at least one segment is floating, False otherwise.
        """
        return all(seg.is_floating for seg in self.segments.values())

    @property
    def is_floating_partly(self) -> bool:
        """
        Determines whether the port is partly floating.

        A port is considered partly floating if at least one of its segments is floating.

        Returns:
            bool: True if at least one segment is floating, False otherwise.
        """
        return any(seg.is_floating for seg in self.segments.values())

    @property
    def is_tied_defined(self) -> bool:
        """True if all segments are tied to a defined value (0 or 1), False otherwise."""
        return all(ps.is_tied_defined for _, ps in self)

    @property
    def is_tied_defined_partly(self) -> bool:
        """True if at least one segment is tied to a defined value (0 or 1), False otherwise."""
        return any(ps.is_tied_defined for _, ps in self)

    @property
    def is_tied_undefined(self) -> bool:
        """
        True if all segments are tied to an undefined value (X or Z), False otherwise.

        If True, every segment is either unconnected or floating. Can also be mixed.
        If False, at least one segment is either connected or tied to 0 or 1.
        """
        return all(ps.is_tied_undefined for _, ps in self)

    @property
    def is_tied_undefined_partly(self) -> bool:
        """
        True if at least one segment is tied to an undefined value (X or Z), False otherwise.

        If True, at least one segment is either unconnected or floating.
        If False, all segments are either connected or tied to 0 or 1.
        """
        return any(ps.is_tied_undefined for _, ps in self)

    @property
    def width(self) -> int:
        """The width of the port in bits, which is simply the number of port segments in the port."""
        return len(self.segments)

    @property
    def offset(self) -> Optional[int]:
        return min(self.segments.keys()) if self.segments else None

    @property
    def lsb_first(self) -> bool:
        """
        Whether the LSB (least significant bit) comes first.

        This property is coupled with Port.msb_first.
        To change this value, change `Port.msb_first`, and this property is updated accordingly.
        """
        return not self.msb_first

    @property
    def signed(self) -> bool:
        # Normally, signed should only be either 0 or 1, but treat non-zero cases as signed (e.g. '1'/'0' or True/False)
        return 'signed' in self.parameters and int(self.parameters['signed']) != 0

    @property
    def unsigned(self) -> bool:
        return not self.signed

    @property
    def is_instance_port(self) -> bool:
        """
        Whether this port is an instance port.

        True, if this port is an instance port.
        False, if this port is a module port.
        """
        from netlist_carpentry.core.netlist_elements.instance import Instance

        return isinstance(self.parent, Instance)

    @property
    def is_module_port(self) -> bool:
        """
        Whether this port is a module port.

        True, if this port is a module port.
        False, if this port is an instance port.
        """
        return not self.is_instance_port

    @property
    def is_input(self) -> bool:
        """
        Whether this port is an input port.

        Returns:
            bool: True if this port is an input port, False otherwise.
        """
        return self.direction.is_input

    @property
    def is_output(self) -> bool:
        """
        Whether this port is an output port.

        Returns:
            bool: True if this port is an output port, False otherwise.
        """
        return self.direction.is_output

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
    def connected_wire_segments(self) -> Set[WireSegmentPath]:
        """
        Returns a set of paths of wire segments connected to this port.

        A port is considered connected to a wire segment if at least one of its segments is connected to that wire segment.

        Returns:
            Set[WireSegmentPath]: A set of paths of wire segments connected to this port.
        """
        return set(s.ws_path for s in self.segments.values())

    @property
    def connected_wires(self) -> Set[WirePath]:
        """
        Returns a set of paths of wires connected to this port.

        A port is considered connected to a wire if at least one of its segments is connected to that wire.

        Returns:
            Set[WirePath]: A set of paths of wires connected to this port.
        """
        # "if" clause skips constant wire segments, which do not have a parent by definition
        return set(ws.parent for ws in self.connected_wire_segments if ws.has_parent())

    def _add_port_segment(self, port_segment: PortSegment) -> PortSegment:
        """
        Adds a port segment to this port.

        Args:
            port_segment (PortSegment): The PortSegment to add to this port.

        Returns:
            PortSegment: The PortSegment that was added to this port.
        """
        return self.segments.add(port_segment.index, port_segment, locked=self.locked)

    def create_port_segment(self, index: int) -> PortSegment:
        """
        Creates a port segment and adds it to this port.

        Args:
            index (int): The index for which a PortSegment should be created and added to this port.

        Returns:
            PortSegment: The PortSegment that was created and added to this port.
        """
        return self._add_port_segment(PortSegment(raw_path=f'{self.raw_path}.{index}', port=self))

    def create_port_segments(self, count: int, offset: int = 0) -> Dict[int, PortSegment]:
        """
        Creates a port segment and adds it to this port.

        The number of port segments can be specified via `count`, which will create and add exactly this
        much port segments (in ascending order) to this port.
        With `offset`, the start index can be set

        Args:
            count (int): The amount of PortSegments to be created and added to this port.
            offset (int, optional): The index from which the generated port segments start.

        Returns:
            List[PortSegment]: A list of PortSegment objects created and added to this port.
        """
        return {i: self.create_port_segment(i) for i in range(offset, offset + count)}

    def remove_port_segment(self, index: int) -> None:
        """
        Removes a port segment from this port.

        Args:
            index: The index of the PortSegment to remove from this port.
        """
        self.segments.remove(index, locked=self.locked)

    def get_port_segment(self, index: int) -> Optional[PortSegment]:
        """
        Returns a PortSegment with the given index from this port.

        Args:
            index: The index of the PortSegment to retrieve from this port.

        Returns:
            Optional[PortSegment]: The PortSegment with the given index, or None if no port segment with that index exists.
        """
        return self.segments.get(index, None)

    @overload
    def tie_signal(self, signal: LogicLevel, index: int = 0) -> None: ...
    @overload
    def tie_signal(self, signal: Signal, index: int = 0) -> None: ...

    def tie_signal(self, signal: SignalOrLogicLevel, index: int = 0) -> None:
        """
        Ties a signal to a constant value on the specified port segment.

        If the specified index corresponds to an existing port segment, ties its
        constant signal value and returns True. Otherwise, does nothing and returns False.

        If `signal` is `X`, which is interpreted as `UNDEFINED`, the port segment is unconnected to achieve this.

        **Does not work for instance output ports, as they are always driven by their parent instances.**

        Args:
            signal (SignalOrLogicLevel): The new constant signal value. **'X' unconnects the port**.
            index (int): The bit index of the port segment. Defaults to 0.

        Raises:
            ObjectNotFoundError: If no segment with the given index exists.
            AlreadyConnectedError: (raised by: PortSegment.tie_signal) If this segment is belongs to a load port and is already connected to a wire,
                from which it receives its value.
            InvalidPortDirectionError: (raised by: PortSegment.tie_signal) If this port segment belongs to an instance output port,
                which is driven by the instance inputs and the instance's internal logic.
            InvalidSignalError: (raised by: PortSegment.tie_signal) If an invalid value is provided.
        """
        if index not in self.segments:
            raise ObjectNotFoundError(f'No PortSegment with index {index} exists in Port "{self.raw_path}"!')
        return self[index].tie_signal(signal)

    @overload
    def set_signal(self, signal: LogicLevel, index: int = 0) -> None: ...
    @overload
    def set_signal(self, signal: Signal, index: int = 0) -> None: ...

    def set_signal(self, signal: SignalOrLogicLevel, index: int = 0) -> None:
        """
        Sets the signal of the port segment at the given index to the given new signal.

        **Does only work for NON-CONSTANT port segments!** This method is intended to be used in
        the signal evaluation process, where constant signals should be treated accordingly.
        Accordingly, it should be avoided that constant inputs are accidentally modified during signal evaluation.
        To change the signal of a port segment to be a constant value, use the `tie_signal` method instead.

        Args:
            signal (SignalOrLogicLevel): The new signal to set on the port segment.
            index (int): The index of the port segment to set the signal on. Defaults to 0, which is the LSB of the port.

        Raises:
            ValueError: If the index is out of range of the port's segments.
        """
        self[index].set_signal(signal)
        self.notify_listeners()

    @overload
    def set_signals(self, signal: int) -> None: ...
    @overload
    def set_signals(self, signal: str) -> None: ...
    @overload
    def set_signals(self, signal: SignalDict) -> None: ...
    def set_signals(self, signal: Union[int, str, SignalDict]) -> None:
        if isinstance(signal, int):
            signal = Signal.from_int(signal, msb_first=self.msb_first, fixed_width=self.width)
        if isinstance(signal, str):
            signal = Signal.from_bin(signal, msb_first=self.msb_first, fixed_width=self.width)
        for idx, sig in signal.items():
            if self.offset is not None:
                self[idx + self.offset].set_signal(sig)
            else:
                raise IndexError(f'Cannot set signals on port {self.raw_path}, since it does not have any segments!')

    def count_signals(self, target_signal: Signal) -> int:
        """
        Counts the number of occurrences of a given signal in this port's signal array.

        Args:
            target_signal (Signal): The signal to count occurrences of.

        Returns:
            int: The number of times the target signal appears in this port's signal array.

        Example:
            ```python
            >>> sig_a = Signal.HIGH
            >>> sig_b = Signal.LOW
            >>> some_port.set_signal(sig_a, index=0)
            >>> some_port.set_signal(sig_a, index=1)
            >>> some_port.set_signal(sig_b, index=2)
            >>> print(some_port.count_signals(Signal.HIGH))
            2
            ```
        """
        return len([sig for sig in self.signal_array.values() if sig == target_signal])

    def set_signed(self, signed: bool) -> bool:
        prev = self.signed
        self.parameters['signed'] = int(signed)
        return prev != self.signed

    def change_connection(self, new_wire_segment_path: WireSegmentPath, index: int = 0) -> None:
        """
        Changes the connection of a port segment to the given wire segment path.

        Args:
            new_wire_segment_path (WireSegmentPath): The new wire segment path to connect the port segment to.
            index (int, optional): The index of the port segment to change the connection for. Defaults to 0.

        Note:
            If index is -1, changes the connections of all segments in this port to the same given wire segment.
        """
        if self.locked:
            raise ObjectLockedError(f'Unable to connect port {self.raw_path} to {new_wire_segment_path.raw}: Port is locked!')
        if index == -1:
            for idx in self.segments:
                self.change_connection(new_wire_segment_path, idx)
        elif index not in self.segments:
            raise ObjectNotFoundError(f'Port {self.raw_path} does not have a segment with index {index}!')
        else:
            self[index].change_connection(new_wire_segment_path)

    def _set_name_recursively(self, old_name: str, new_name: str) -> None:
        for _, ps in self:
            ps.raw_path = ps.path.replace(old_name, new_name).raw

    def change_mutability(self, is_now_locked: bool, recursive: bool = False) -> Self:
        if recursive:
            for p in self.segments.values():
                p.change_mutability(is_now_locked=is_now_locked)
        return super().change_mutability(is_now_locked)

    def normalize_metadata(
        self,
        include_empty: bool = False,
        sort_by: Literal['path', 'category'] = 'path',
        filter: Callable[[str, NESTED_DICT], bool] = lambda cat, md: True,
    ) -> METADATA_DICT:
        md = super().normalize_metadata(include_empty=include_empty, sort_by=sort_by, filter=filter)
        for s in self.segments.values():
            s_md = s.normalize_metadata(include_empty=include_empty, sort_by=sort_by, filter=filter)
            for cat, val in s_md.items():
                if cat in md:
                    md[cat].update(val)
                else:
                    md[cat] = val
        return md

    def __hash__(self) -> int:
        return hash(
            (
                self.raw_path,
                self.is_instance_port,
                self.direction.value,
                tuple((s.raw_path, s.raw_ws_path) for s in self.segments.values()),
                tuple(hash((p, v)) for p, v in self.parameters.items()),
            )
        )

    def __str__(self) -> str:
        return f'{self.__class__.__name__} "{self.name}" with path {self.path.raw} ({self.direction.value} port)'

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.name} at {self.path.raw})'
