"""Collection of TypedDicts to simplify handling of Yosys-generated JSON netlists."""

from typing import Dict, List, Literal, TypedDict, Union

from pydantic import PositiveInt
from typing_extensions import NotRequired

from netlist_carpentry.core.enums.signal import T_SIGNAL_STATES
from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath

BitAlias = Union[int, T_SIGNAL_STATES]


class PortAttributes(TypedDict):
    direction: str
    bits: List[BitAlias]
    upto: NotRequired[int]
    offset: NotRequired[int]
    signed: NotRequired[int]


YosysPortDirections = Dict[str, Literal['input', 'output', 'inout']]


class YosysCell(TypedDict):
    hide_name: Literal[0, 1]
    type: str
    parameters: Dict[str, str]
    parameter_default_values: NotRequired[Dict[str, str]]
    attributes: Dict[str, str]
    port_directions: NotRequired[YosysPortDirections]
    connections: Dict[str, List[BitAlias]]


class Netnames(TypedDict):
    hide_name: Literal[0, 1]
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

ModuleName = str
NetNumber = PositiveInt
NewModuleName = str
OldModuleName = str

NetNumberMappingDict = Dict[ModuleName, Dict[PositiveInt, WireSegmentPath]]
ModuleNameMapping = Dict[NewModuleName, OldModuleName]
