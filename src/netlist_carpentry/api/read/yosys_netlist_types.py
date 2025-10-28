from typing import Dict, List, TypedDict, Union

from typing_extensions import NotRequired

from netlist_carpentry.core.signal import T_SIGNAL_STATES

BitAlias = Union[int, T_SIGNAL_STATES]


class PortAttributes(TypedDict):
    direction: str
    bits: List[BitAlias]
    upto: NotRequired[int]
    offset: NotRequired[int]
    signed: NotRequired[int]


class YosysCell(TypedDict):
    hide_name: int
    type: str
    parameters: Dict[str, str]
    parameter_default_values: NotRequired[Dict[str, str]]
    attributes: Dict[str, str]
    port_directions: NotRequired[Dict[str, str]]
    connections: Dict[str, List[BitAlias]]


class Netnames(TypedDict):
    hide_name: int
    bits: List[BitAlias]
    attributes: Dict[str, str]
    upto: NotRequired[int]
    offset: NotRequired[int]
    signed: NotRequired[int]


class YosysModule(TypedDict):
    attributes: Dict[str, str]
    parameters: Dict[str, str]
    parameter_default_values: NotRequired[Dict[str, str]]
    ports: Dict[str, PortAttributes]
    cells: Dict[str, YosysCell]
    netnames: Dict[str, Netnames]


class YosysData(TypedDict):
    creator: str
    modules: Dict[str, YosysModule]


AllYosysTypes = Union[YosysData, YosysCell, YosysModule, Netnames, PortAttributes]
