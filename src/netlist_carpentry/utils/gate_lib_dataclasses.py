"""Module for typed dictionaries used throughout the gate library for convenience."""

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, TypedDict

from pydantic import BaseModel, ConfigDict, NonNegativeInt, PositiveInt, PrivateAttr
from typing_extensions import NotRequired, deprecated

from netlist_carpentry import Signal

if TYPE_CHECKING:
    from netlist_carpentry import Instance


@deprecated('TypedParams will be removed in 1.0.0! Use gate_lib_dataclasses.Parameters instead.')
class TypedParams(TypedDict):
    pass


@deprecated('_CombinationalParams will be removed in 1.0.0! Use gate_lib_dataclasses.Parameters instead.')
class _CombinationalParams(TypedParams):
    Y_WIDTH: NotRequired[PositiveInt]
    A_WIDTH: NotRequired[PositiveInt]
    A_SIGNED: NotRequired[bool]


@deprecated('_SequentialParams will be removed in 1.0.0! Use gate_lib_dataclasses.Parameters instead.')
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

    def __len__(self) -> NonNegativeInt:
        return len(self.as_dict())

    def __contains__(self, key: str) -> bool:
        return getattr(self, key, None) is not None  # type: ignore

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


@deprecated('AllParams will be removed in 1.0.0! Use gate_lib_dataclasses.Parameters instead.')
class AllParams(UnaryParams, BinaryParams, MuxParams, DFFParams):
    pass
