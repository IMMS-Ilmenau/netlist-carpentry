"""Module for typed dictionaries used throughout the gate library for convenience."""

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, TypedDict

from pydantic import BaseModel, ConfigDict, NonNegativeInt, PositiveInt, PrivateAttr
from typing_extensions import NotRequired, deprecated

from netlist_carpentry import Signal
from netlist_carpentry.core.types import SignalArray

if TYPE_CHECKING:
    from netlist_carpentry import Instance


@deprecated('TypedParams will be removed in v1.0.0! Use gate_lib_dataclasses.Parameters instead.')
class TypedParams(TypedDict):
    pass


@deprecated('_CombinationalParams will be removed in v1.0.0! Use gate_lib_dataclasses.Parameters instead.')
class _CombinationalParams(TypedParams):
    Y_WIDTH: NotRequired[PositiveInt]
    A_WIDTH: NotRequired[PositiveInt]
    A_SIGNED: NotRequired[bool]


@deprecated('_SequentialParams will be removed in v1.0.0! Use gate_lib_dataclasses.Parameters instead.')
class _SequentialParams(TypedParams):
    WIDTH: NotRequired[PositiveInt]


class Parameters(BaseModel):
    model_config = ConfigDict(extra='allow')

    def __getitem__(self, key: str) -> object:
        if key in self:
            return getattr(self, key, None)  # type: ignore
        raise KeyError(f'No parameter {key} found!')

    def __setitem__(self, key: str, value: object) -> None:
        setattr(self, key, value)

    def __contains__(self, item: str) -> bool:
        return getattr(self, item, None) is not None  # type: ignore

    def __len__(self) -> NonNegativeInt:
        return len(self.as_dict())

    def __eq__(self, value: object) -> bool:
        if isinstance(value, Parameters):
            return self.as_dict() == value.as_dict()
        if isinstance(value, dict):
            return self.as_dict() == value
        return NotImplemented

    def __repr__(self) -> str:
        return self.__class__.__name__ + repr(self.as_dict())

    def get(self, key: str, default: Optional[object] = None) -> object:
        return self.as_dict().get(key, default)

    def as_dict(self) -> Dict[str, object]:
        """Returns this parameter set as a dictionary.

        Does not include parameters that are `None`.

        Returns:
            Dict[str, object]: This parameter set as a dictionary.
        """
        return self.model_dump(exclude_none=True)  # type: ignore[misc]

    def items(self) -> List[Tuple[str, object]]:
        """Returns the parameter names and values as a list of tuples.

        This is basically the same as `dict.items()`.

        Returns:
            List[Tuple[str, object]]: The parameter names and values as a list of tuples.
        """
        return list(self.as_dict().items())


class PortParams(Parameters):
    upto: Optional[int] = None
    offset: Optional[int] = None
    signed: Optional[int] = None


class InstanceParams(Parameters):
    _parent: Optional['Instance'] = PrivateAttr(default=None)

    def _get_parent(self, port: str, key: str, default: Optional[PositiveInt]) -> Optional[PositiveInt]:
        if self._parent is not None:
            return int(getattr(self._parent.ports[port], key))  # type: ignore
        return default


class GateParams(InstanceParams):
    pass


class ClockParamsMixin:
    CLK_POLARITY: Optional[Signal] = None


class EnableParamsMixin:
    EN_POLARITY: Optional[Signal] = None


class ResetParamsMixin:
    RST_POLARITY: Optional[Signal] = None
    RST_VALUE: Optional[int] = None


class LoadParamsMixin:
    LOAD_POLARITY: Optional[Signal] = None


class SRParamsMixin:
    CLR_POLARITY: Optional[Signal] = None
    SET_POLARITY: Optional[Signal] = None


class ClockParams(ClockParamsMixin, GateParams):
    pass


class EnableParams(EnableParamsMixin, GateParams):
    pass


class ResetParams(ResetParamsMixin, GateParams):
    pass


class LoadParams(LoadParamsMixin, GateParams):
    pass


class SRParams(SRParamsMixin, GateParams):
    pass


class WireParams(Parameters):
    """Common parameters for Wires."""

    signed: Optional[int] = None


class UnaryParams(GateParams):
    """Common parameters for Unary cells and derived classes."""

    Y_WIDTH: Optional[PositiveInt] = None
    A_WIDTH: Optional[PositiveInt] = None
    A_SIGNED: Optional[bool] = False


class BinaryParams(GateParams):
    """Common parameters for Binary cells and derived classes."""

    Y_WIDTH: Optional[PositiveInt] = None
    A_WIDTH: Optional[PositiveInt] = None
    A_SIGNED: Optional[bool] = False
    B_WIDTH: Optional[PositiveInt] = None
    B_SIGNED: Optional[bool] = False


class MuxParams(GateParams):
    """Common parameters for Muxes and Demuxes."""

    WIDTH: Optional[PositiveInt] = None
    BIT_WIDTH: Optional[PositiveInt] = None


class DFFParams(ClockParams, EnableParams, ResetParams, LoadParams, SRParams):
    """Common parameters for DFFs and derived classes."""

    WIDTH: Optional[PositiveInt] = None


class DLatchParams(GateParams):
    """Common parameters for DLatches."""

    EN_POLARITY: Optional[Signal] = None
    WIDTH: Optional[PositiveInt] = None


class MemoryParams(ClockParams, EnableParams):
    MEMID: Optional[str] = None
    """The name of the original object that became this mem_v2 cell."""
    SIZE: Optional[PositiveInt] = None
    """The number of words in the memory."""
    WIDTH: Optional[PositiveInt] = None
    """The number of address bits."""
    ABITS: Optional[PositiveInt] = None
    """The number of data bits per word."""
    OFFSET: Optional[PositiveInt] = None
    """The address offset."""
    INIT: Optional[SignalArray] = None
    """The initial memory contents."""
    RD_PORTS: Optional[PositiveInt] = None
    """The number of read ports on this memory cell."""
    RD_CE_OVER_SRST: Optional[SignalArray] = None
    """This parameter is `RD_PORTS` bits wide, determining relative synchronous reset and enable priority for each read port."""
    RD_CLK_ENABLE: Optional[SignalArray] = None
    """This parameter is `RD_PORTS` bits wide, containing a clock enable bit for each read port."""
    RD_CLK_POLARITY: Optional[SignalArray] = None
    """This parameter is `RD_PORTS` bits wide, containing a clock polarity bit for each read port."""
    RD_COLLISION_X_MASK: Optional[SignalArray] = None
    """This parameter is `RD_PORTS*WR_PORTS` bits wide, containing a concatenation of all COLLISION_X_MASK values of the original memrd cells."""
    RD_INIT_VALUE: Optional[SignalArray] = None
    """This parameter is `RD_PORTS*WIDTH` bits wide, containing the initial value for each synchronous read port."""
    RD_TRANSPARENCY_MASK: Optional[SignalArray] = None
    """This parameter is `RD_PORTS*WR_PORTS` bits wide, containing a concatenation of all TRANSPARENCY_MASK values of the original memrd cells."""
    RD_WIDE_CONTINUATION: Optional[SignalArray] = None
    """This parameter is `RD_PORTS` bits wide, containing a bitmask of "wide continuation" read ports.

    Such ports are used to represent the extra data bits of wide ports in the combined cell,
    and must have all control signals identical with the preceding port, except for address,
    which must have the proper sub-cell address encoded in the low bits."""
    WR_PORTS: Optional[PositiveInt] = None
    """The number of read ports on this memory cell."""
    WR_CLK_ENABLE: Optional[SignalArray] = None
    """This parameter is `WR_PORTS` bits wide, containing a clock enable bit for each write port."""
    WR_CLK_POLARITY: Optional[SignalArray] = None
    """This parameter is `WR_PORTS` bits wide, containing a clock polarity bit for each write port."""
    WR_PRIORITY_MASK: Optional[SignalArray] = None
    """This parameter is `WR_PORTS*WR_PORTS` bits wide, containing a concatenation of all PRIORITY_MASK values of the original memwr cells."""
    WR_WIDE_CONTINUATION: Optional[SignalArray] = None
    """This parameter is `WR_PORTS` bits wide, containing a bitmask of "wide continuation" write ports.

    Such ports are used to represent the extra data bits of wide ports in the combined cell,
    and must have all control signals identical with the preceding port, except for address,
    which must have the proper sub-cell address encoded in the low bits."""


class BRAMParams(MemoryParams):
    pass


@deprecated('AllParams will be removed in v1.0.0! Use gate_lib_dataclasses.Parameters instead.')
class AllParams(UnaryParams, BinaryParams, MuxParams, DFFParams):
    pass
