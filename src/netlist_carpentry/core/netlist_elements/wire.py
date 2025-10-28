from __future__ import annotations

import builtins
from typing import TYPE_CHECKING, Callable, Dict, Generator, List, Literal, Optional, Set, Tuple, Union, overload

from pydantic import BaseModel
from typing_extensions import Self

from netlist_carpentry import LOG
from netlist_carpentry.core.exceptions import ParentNotFoundError
from netlist_carpentry.core.netlist_elements.element_path import WirePath
from netlist_carpentry.core.netlist_elements.element_type import EType
from netlist_carpentry.core.netlist_elements.mixins.metadata import METADATA_DICT, NESTED_DICT
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.netlist_elements.port_segment import PortSegment
from netlist_carpentry.core.netlist_elements.wire_segment import WireSegment
from netlist_carpentry.core.protocols.signals import LogicLevel, SignalDict, SignalOrLogicLevel
from netlist_carpentry.core.signal import Signal
from netlist_carpentry.utils.custom_dict import CustomDict

if TYPE_CHECKING:
    from netlist_carpentry.core.netlist_elements.module import Module


class Wire(NetlistElement, BaseModel):
    """
    Represents a wire in a netlist.

    The wire is composed of multiple wire segments, which are connected together to form a single wire.
    The wire segments are stored in a dictionary, where the keys are the indices of the wire segments
    and the values are the wire segments themselves.
    """

    _segments = CustomDict[int, WireSegment]()
    msb_first: bool = True
    """Whether this port is MSB (most significant bit) first or not"""
    module: Optional[NetlistElement]

    def __getitem__(self, index: int) -> WireSegment:
        """
        Allows subscripting of a Wire object to access its wire segments directly.

        This is mainly for convenience, to use Wire[i] instead of Wire.segments[i].

        Args:
            index (int): The index of the desired wire segment.

        Returns:
            WireSegment: The wire segment at the specified index.
        """
        if index in self.segments:
            return self.segments[index]
        raise IndexError(f'Wire {self.raw_path} does not have a segment {index}!')

    def __len__(self) -> int:
        return len(self.segments)

    def __iter__(self) -> Generator[Tuple[int, WireSegment], None, None]:  # type: ignore[override]
        return iter(s for s in self.segments.items())

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, Wire):
            return NotImplemented
        if not super().__eq__(value):
            return False
        return self.segments == value.segments

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        from netlist_carpentry.core.netlist_elements.module import Module

        if self.module is None or isinstance(self.module, Module):
            return super().model_post_init(__context)
        raise TypeError(f'Wire.module {self.raw_path} should be a module, but is a {type(self.module).__name__}!')

    @property
    def path(self) -> WirePath:
        """
        Returns the WirePath of the netlist element.

        The WirePath object is constructed using the element's type and its raw hierarchical path.

        Returns:
            WirePath: The hierarchical path of the netlist element.
        """
        return WirePath(raw=self.raw_path)

    @property
    def type(self) -> EType:
        """The type of the element, which is a wire."""
        return EType.WIRE

    @property
    def parent(self) -> Module:
        from netlist_carpentry.core.netlist_elements.module import Module

        if isinstance(self.module, Module):
            return self.module
        elif self.module is None:
            raise ParentNotFoundError(
                f'No parent module specified for wire {self.raw_path}. '
                + 'This is probably due to a bad instantiation (missing or bad "module" parameter), or a subsequent modification of the module, which corrupted the wire.'
            )
        raise TypeError(f'Bad type: Parent object of wire {self.raw_path} is {type(self.module).__name__}, but should be {Module.__name__}')

    @property
    def segments(self) -> CustomDict[int, WireSegment]:
        """
        Retrieves the dictionary of wire segments.

        Returns:
            A dictionary with integer keys representing wire segment indices and values being WireSegment objects.
        """
        return self._segments

    @property
    def signal(self) -> Signal:
        """
        Returns the signal associated with this wire.

        **Does only work for 1-bit wide wires, as a convenient alternative for `wire.signal_array`.**

        If there's only one segment in the wire (i.e. the wire is exactly 1 bit wide), returns the signal of that segment.
        Otherwise, returns Signal.UNDEFINED to indicate ambiguity.
        This is meant as a shortcut of signal_array[0], since many wires commonly are only 1 bit wide.
        Thus, this property should only be used for 1-bit wide wires!

        Returns:
            Signal: The signal associated with this wire, if this wire is 1 bit wide, otherwise returns Signal.UNDEFINED.
        """
        if len(self.segments) == 1:
            return self[next(iter(self.segments))].signal
        LOG.warn(
            f'Unable to return signal of wire {self.name} (at {self.raw_path}): Wire is {len(self.segments)} bit wide and thus does have multiple signals. Use "Wire.signal_array" instead!'
        )
        return Signal.UNDEFINED

    @property
    def signal_array(self) -> Dict[int, Signal]:
        """
        A dictionary of wire segment indices to the signals of the corresponding wire segments.

        Returns:
            A dictionary with integer keys representing wire segment indices and values being Signal objects
            representing the signal of each wire segment.
        """
        return {idx: self[idx].signal for idx in self.segments}

    @property
    def signal_str(self) -> str:
        """
        The signal currently applied to this wire as a string (MSB first).

        The length of the string corresponds to the width of this wire.
        Offset is ignored by this property. If a 4 bit wire has an offset of 3, the returned
        string only consists of the actually present segments (i.e. the string consists of the signals
        at the 4 present segments).
        Analogously, if segments are missing in between, they are also ignored and treated as if there
        was no gap. If a wire has a segment with index 0 and with index 2, but a segment for index 1 is
        missing, the returned string will have the values of the segments 2 and 0 (in descending order),
        without including or mentioning the gap at index 1.

        If the signal string for a 4 bit wire is '1010', then the segments with indices 3 and 1 (plus offset)
        are currently 1 and the other two segments are 0.
        If the string contains 'x', the corresponding segment has an undefined value, and if the string
        contains 'z', the corresponding segment is floating.
        """
        sorted_keys = sorted(self.signal_array.keys(), reverse=True)
        return ''.join(self.signal_array[k].value for k in sorted_keys)

    @property
    def signal_int(self) -> Optional[int]:
        """
        The signal currently applied to this wire as an integer, if possible.

        If `Wire.signed` is False, the value is treated as an unsigned signal.
        If `Wire.signed` is True, the value is treated as a signed signal, using the two's
        complement, if the sign bit is `1`.

        Offset is ignored when calculating this property. If a 4 bit wire has an offset of 3, the returned
        integer is built form the actually present segments (i.e. the integer value is between 0 and 15).
        Analogously, if segments are missing in between, they are also ignored and treated as if there
        was no gap. If a wire has a segment with index 0 and with index 2, but a segment for index 1 is
        missing, the returned integer will be the decimal representation of the values of the segments 2 and 0,
        without including or mentioning the gap at index 1. The calculated number ranges thus between 0 and 3,
        and *not* between 0 and 7.

        If the signal string for a 4 bit wire is '1001', then this property will return 9.
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
    def width(self) -> int:
        """
        The width of the wire, which is the number of wire segments that compose it.

        Returns:
            The number of wire segments in the wire (int).
        """
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
    def ports(self) -> Dict[int, List[PortSegment]]:
        """
        Dictionary mapping port names to dictionaries of wire segment indices and corresponding element paths.

        Returns:
            A dictionary where each key is a port name (str), and the value is another dictionary.
            The inner dictionary has wire segment indices (int) as keys, and the values are ElementPaths
            representing the instance path of the port connected at this wire index.
        """
        port_dict = {}
        for s_idx in self.segments:
            port_dict[s_idx] = self[s_idx].port_segments
        return port_dict

    @property
    def connected_port_segments(self) -> Set[PortSegment]:
        """
        Retrieves a set of all (unique) port segments connected to this wire.

        Returns:
            A set of PortSegment objects representing the port segments connected to this wire.
        """
        return {p for s in self.segments.values() for p in s.port_segments}

    @property
    def nr_connected_port_segments(self) -> int:
        """
        The total number of unique port segments connected to this wire.

        Sums up the number of connected port segments for each wire segment in the wire.

        Returns:
            The total number of connected port segments (int).
        """
        return len(self.connected_port_segments)

    def _add_wire_segment(self, wire_segment: WireSegment) -> None:
        """
        Adds a new wire segment to the wire.

        Args:
            wire_segment (WireSegment): The wire segment to be added.
        """
        self.segments.add(wire_segment.index, wire_segment, locked=self.locked)

    def create_wire_segment(self, index: int) -> WireSegment:
        """
        Creates a new wire segment and adds it to the wire.

        Args:
            index (int): The index where a new wire segment should be added.

        Returns:
            WireSegment: The WireSegment that was added to this wire.
        """
        seg = WireSegment(raw_path=f'{self.raw_path}.{index}', wire=self)
        self._add_wire_segment(seg)
        return seg

    def create_wire_segments(self, count: int, offset: int = 0) -> Dict[int, WireSegment]:
        """
        Creates a wire segment and adds it to this wire.

        The number of wire segments can be specified via `count`, which will create and add exactly this
        much wire segments (in ascending order) to this wire.
        With `offset`, the start index can be set

        Args:
            count (int): The amount of WireSegments to be created and added to this wire.
            offset (int, optional): The index from which the generated wire segments start.

        Returns:
            List[WireSegment]: A list of WireSegment objects created and added to this wire.
        """
        return {i: self.create_wire_segment(i) for i in range(offset, offset + count)}

    def remove_wire_segment(self, index: int) -> None:
        """
        Removes a wire segment at the specified index from the wire.

        This method attempts to remove a wire segment from the internal segments dictionary using the specified index.
        The operation checks for immutability and performs the removal if allowed.

        Args:
            index (int): The index of the wire segment to be removed.
        """
        if index in self.segments:
            for ps in self[index].port_segments:
                if ps.raw_ws_path == self[index].raw_path:
                    ps.set_ws_path('')
        self.segments.remove(index, locked=self.locked)

    def get_wire_segment(self, index: int) -> Optional[WireSegment]:
        """
        Retrieves a wire segment at the specified index from the wire.

        This method attempts to retrieve a wire segment from the internal segments dictionary using the specified index.

        Args:
            index (int): The index of the wire segment to be retrieved.

        Returns:
            Optional[WireSegment]: The wire segment at the specified index, or None if not found.
        """
        return self.segments.get(index, None)

    def get_wire_segments(self, name: str = '', fuzzy: bool = False) -> Dict[int, WireSegment]:
        """
        Retrieves a dictionary of wire segments with the specified name.

        This method retrieves a dictionary of wire segments that match the specified name.
        If fuzzy is True, the method will also return segments whose name contains the specified name.

        Args:
            name (str, optional): The name of the wire segment to retrieve. Defaults to ''.
            fuzzy (bool, optional): Whether to allow fuzzy matching. Defaults to False.

        Returns:
            Dict[int, WireSegment]: A dictionary of wire segments with the specified name or containing the specified name if fuzzy is True.
        """
        if name:
            return {i: self[i] for i in self.segments if name == self[i].name or (name in self[i].name and fuzzy)}
        LOG.warn(f'A "name" must be set to get wire segments, but name was "{name}"!')
        return {}

    @overload
    def set_signal(self, signal: LogicLevel, index: int = 0) -> None: ...
    @overload
    def set_signal(self, signal: Signal, index: int = 0) -> None: ...

    def set_signal(self, signal: SignalOrLogicLevel, index: int = 0) -> None:
        """
        Sets the signal of the wire segment at the given index to the given new signal.

        This method is intended to be used in the signal evaluation process, where the signal of this wire is driven onto it
        by the driving port (e.g. a module input port or an instance output port).
        This method is called during the signal evaluation process whenever the driving port of this wire updates its signal value.

        Args:
            signal (SignalOrLogicLevel): The new signal to set on the wire.
            index (int): The index of the wire to set the signal on. Defaults to 0, which is the LSB of the wire.

        Raises:
            ValueError: If the index is out of range of the wire's segments.
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
                raise IndexError(f'Cannot set signals on wire {self.raw_path}, since it does not have any segments!')

    def set_signed(self, signed: bool) -> None:
        self.parameters['signed'] = int(signed)

    def driver(self) -> Dict[int, List[PortSegment]]:
        """
        Returns a dictionary of wire segment indices to lists of driving ports.

        The method retrieves the connections that are considered as drivers (which ideally is only one driver) for each wire segment in the wire.

        Returns:
            A dictionary mapping wire segment indices (int) to a list of Port objects
            representing the driver connections (should be only one) at each index.
        """
        return self._drv_or_lds_connections(get_drv=True)

    def loads(self) -> Dict[int, List[PortSegment]]:
        """
        Returns a dictionary of wire segment indices to lists of load ports.

        The method retrieves the connections that are considered as loads for each wire segment in the wire.

        Returns:
            A dictionary with integer keys representing wire segment indices and values being lists of Port objects,
            which represent the load ports connected at those indices.
        """
        return self._drv_or_lds_connections(get_drv=False)

    def _drv_or_lds_connections(self, get_drv: bool) -> Dict[int, List[PortSegment]]:
        """
        Retrieves connections for either drivers or loads on the wire.

        Args:
            get_drv (bool): Whether to retrieve driver connections (True) or load connections (False).

        Returns:
            A dictionary mapping each wire segment index to a list of Port objects.
        """
        con_dict = {}
        for s in self.segments:
            if get_drv:
                # Retrieve driver connections
                con_dict[s] = self[s].driver()
            else:
                # Retrieve load connections
                con_dict[s] = self[s].loads()
        return con_dict

    def has_no_driver(self, get_mapping: bool = False) -> Union[bool, Dict[int, bool]]:
        """
        Retrieves a boolean indicating whether a wire segment has no driver connection at all wire indices.

        Args:
            get_mapping (bool, optional): Whether to retrieve a dictionary mapping wire segment indices to boolean values indicating
                whether the segment at that index has no driver connection. Defaults to False.

        Returns:
            If get_mapping is False, a boolean indicating whether all wire segments have no driver connection.
            If get_mapping is True, a dictionary mapping wire segment indices to boolean values indicating whether the segment at that index
            has no driver connection.
        """
        return self._get_from_segments(get_mapping, 'has_no_driver', 'all')

    def has_multiple_drivers(self, get_mapping: bool = False) -> Union[bool, Dict[int, bool]]:
        """
        Determines if any wire segment has multiple driver connections.

        This method checks each wire segment in the wire to see if it has more than one driver connection.

        Args:
            get_mapping (bool, optional): If True, return a dictionary mapping wire segment indices to booleans indicating
                whether each segment has multiple drivers. If False, return a single boolean indicating if any segment has
                multiple drivers. Defaults to False.

        Returns:
            If get_mapping is True, a dictionary mapping wire segment indices to boolean values indicating whether the segment
            at that index has multiple driver connections. If get_mapping is False, a boolean indicating whether any wire
            segment has multiple driver connections.
        """
        return self._get_from_segments(get_mapping, 'has_multiple_drivers', 'any')

    def has_no_loads(self, get_mapping: bool = False) -> Union[bool, Dict[int, bool]]:
        """
        Retrieves a boolean indicating whether any wire segment has no load connections.

        Args:
            get_mapping (bool, optional): Whether to retrieve a dictionary mapping wire segment indices to boolean values indicating
                whether the segment at that index has no load connection. Defaults to False.

        Returns:
            If get_mapping is False, a boolean indicating whether all wire segments have no load connection.
            If get_mapping is True, a dictionary mapping wire segment indices to boolean values indicating whether the segment at that index
            has no load connection.
        """
        return self._get_from_segments(get_mapping, 'has_no_loads', 'all')

    def is_dangling(self, get_mapping: bool = False) -> Union[bool, Dict[int, bool]]:
        """
        Retrieves a boolean indicating whether any wire segment is dangling (has no driver or load connections at all wire indices).

        Args:
            get_mapping (bool, optional): Whether to retrieve a dictionary mapping wire segment indices to boolean values indicating
                whether the segment at that index is dangling. Defaults to False.

        Returns:
            If get_mapping is True, a dictionary mapping wire segment indices to boolean values indicating whether the segment
            at that index is dangling. If get_mapping is False, a boolean indicating whether any wire segment is dangling.
        """
        return self._get_from_segments(get_mapping, 'is_dangling', 'any')

    def has_problems(self, get_mapping: bool = False) -> Union[bool, Dict[int, bool]]:
        """
        Retrieves a boolean indicating whether any wire segment has problems (has no driver or load connections, or has multiple drivers).

        Args:
            get_mapping (bool, optional): Whether to retrieve a dictionary mapping wire segment indices to boolean values indicating
                whether the segment at that index has problems. Defaults to False.

        Returns:
            If get_mapping is True, a dictionary mapping wire segment indices to boolean values indicating whether the segment
            at that index has problems. If get_mapping is False, a boolean indicating whether any wire segment has problems.
        """
        return self._get_from_segments(get_mapping, 'has_problems', 'any')

    def _get_from_segments(self, get_mapping: bool, function_name: str, filter: Literal['any', 'all']) -> Union[bool, Dict[int, bool]]:
        """
        Retrieves a boolean value from all wire segments of this wire.

        This method loops over all wire segments in the wire and calls the specified method on each of them. The results are stored in a dictionary
        mapping each wire segment index to the result of the method call.
        If get_mapping is False, the method returns whether any of the results of the method calls were True.

        Args:
            get_mapping (bool): Whether to retrieve a dictionary mapping wire segment indices to results or to retrieve a boolean indicating whether
                any of the results of the method calls were True.
            function_name (str): The name of the method to call on each wire segment.
            filter (Literal['any', 'all']): Whether to check if the condition is True for all wire segments (all) or for at least one of them (any).

        Returns:
            If get_mapping is True, a dictionary mapping wire segment indices (int) to the result of the method call (bool).
            If get_mapping is False, a boolean indicating whether any of the results of the method calls were True.
        """
        mapping = {}
        for s_idx in self.segments:
            s = self[s_idx]
            fnc: Callable[..., bool] = getattr(s, function_name)
            mapping[s_idx] = fnc()
        any_or_all: Callable[[Generator[bool, None, None]], bool] = getattr(builtins, filter)
        return mapping if get_mapping else any_or_all(mapping[k] for k in mapping)

    def _set_name_recursively(self, old_name: str, new_name: str) -> None:
        for _, ws in self:
            ws.raw_path = ws.path.replace(old_name, new_name).raw

    def change_mutability(self, is_now_locked: bool, recursive: bool = False) -> Self:
        if recursive:
            for w in self.segments.values():
                w.change_mutability(is_now_locked=is_now_locked)
        return super().change_mutability(is_now_locked)

    def evaluate(self) -> None:
        for s in self.segments.values():
            s.evaluate()

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
        return hash((self.raw_path, tuple(hash(s) for s in self.segments.values()), tuple(hash(p) for p in self.parameters.values())))

    def __str__(self) -> str:
        return f'{self.__class__.__name__} "{self.name}" with path {self.path.raw} ({self.width} bit(s) wide)'

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.name} at {self.path.raw})'
