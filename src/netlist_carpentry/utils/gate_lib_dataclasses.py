"""Module for typed dictionaries used throughout the gate library for convenience."""

from typing import TypedDict

from pydantic import PositiveInt
from typing_extensions import NotRequired

from netlist_carpentry import Signal


class TypedParams(TypedDict):
    pass


class InstanceParams(TypedParams):
    pass


class _CombinationalParams(TypedParams):
    Y_WIDTH: NotRequired[PositiveInt]
    A_WIDTH: NotRequired[PositiveInt]
    A_SIGNED: NotRequired[bool]


class UnaryParams(_CombinationalParams):
    pass


class BinaryParams(_CombinationalParams):
    B_WIDTH: NotRequired[PositiveInt]
    B_SIGNED: NotRequired[bool]


class MuxParams(_CombinationalParams):
    WIDTH: NotRequired[PositiveInt]
    BIT_WIDTH: NotRequired[PositiveInt]


class _SequentialParams(TypedParams):
    WIDTH: NotRequired[PositiveInt]


class DFFParams(_SequentialParams):
    CLK_POLARITY: NotRequired[Signal]
    EN_POLARITY: NotRequired[Signal]
    ARST_POLARITY: NotRequired[Signal]
    ARST_VALUE: NotRequired[int]


class DLatchParams(_SequentialParams):
    EN_POLARTY: NotRequired[Signal]


class AllParams(UnaryParams, BinaryParams, MuxParams, DFFParams):
    pass
