"""Base class with shared attributes and methods among segment (or slice) classes."""

from __future__ import annotations

from typing import Dict, Optional, overload

from pydantic import NonNegativeInt

from netlist_carpentry import Signal
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.protocols.signals import LogicLevel, SignalOrLogicLevel


class _Segment(NetlistElement):
    @property
    def index(self) -> int:
        """
        The index of the PortSegment in the Port, which is retrieved from the name.

        If this PortSegment instance is a placeholder instance (i.e. the path is empty and thus
        no name is available), then this value is -1 instead.
        """
        return int(self.name) if not self.is_placeholder_instance else -1

    @index.setter
    def index(self, new_index: NonNegativeInt) -> None:
        self.set_name(str(new_index))

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        # Check that path name ends with a digit to retrieve the index of the segment
        # If no path was provided (i.e. an empty segment/placeholder instance is modelled), do not raise an error
        if not self.is_placeholder_instance and not self.path.name.isdigit():
            raise ValueError(f'Segment path name must end with a digit (i.e. the index of the port segment), but got {self.path.raw}')
        return super().model_post_init(__context)

    @overload
    def set_signal(self, signal: LogicLevel) -> None: ...
    @overload
    def set_signal(self, signal: Signal) -> None: ...

    def set_signal(self, signal: SignalOrLogicLevel) -> None:
        """
        Sets the signal of this segment to the given new signal.

        Args:
            signal (SignalOrLogicLevel): The new signal to set on the segment.

        Raises:
            NotImplementedError: Not implemented in base class.
        """
        raise NotImplementedError(f'Not implemented for class {self.__class__.__name__}!')

    def set_name(self, new_name: str) -> None:
        if new_name.isdecimal():
            return super().set_name(new_name)
        raise ValueError(f'Cannot apply name {new_name} to segment {self.raw_path}: Only numeric values are allowed!')
